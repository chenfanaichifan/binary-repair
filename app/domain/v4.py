"""Typed V4 symbolic evidence.

A V4 gate is a model-level claim. A JSON file that merely says ``passed`` and
carries matching hashes is not enough: the claim must state what was explored,
what the solver accounted for, how the tool was calibrated, and what the replay
did. Missing any required section makes the result NOT VERIFIED.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

HEX64 = r"^[a-f0-9]{64}$"
EMPTY_DISJUNCTION_DISCLOSURE = (
    "the candidate-side unsat is the empty-disjunction case: no free() occurs "
    "on the path, so it is not a solved constraint"
)


class V4EvidenceError(ValueError):
    """The V4 evidence is not a complete, typed model-level claim."""


class ForbiddenRange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def _ordered(self) -> "ForbiddenRange":
        if self.end <= self.start:
            raise ValueError("forbidden range end must be greater than start")
        return self


class ExplorationAccounting(BaseModel):
    """The state counts the harness actually reports.

    ``active``/``deferred``/``unconstrained``/``errored`` left over on a
    ``complete`` run make completeness a lie, so they are rejected together
    with a non-empty ``unexplored`` list.
    """

    model_config = ConfigDict(extra="forbid")
    initial: int = Field(ge=0)
    deadended: int = Field(ge=0)
    errored: int = Field(ge=0)
    unconstrained: int = Field(ge=0)
    deferred: int = Field(ge=0)
    active: int = Field(ge=0)
    pruned: int = Field(ge=0)
    complete: bool
    unexplored: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _complete_has_no_open_states(self) -> "ExplorationAccounting":
        if self.complete and self.unexplored:
            raise ValueError("complete exploration must have unexplored == []")
        if self.complete and any(
            (self.errored, self.unconstrained, self.deferred, self.active)
        ):
            raise ValueError(
                "complete exploration cannot leave errored/unconstrained/"
                "deferred/active states"
            )
        return self


class SolverAccounting(BaseModel):
    model_config = ConfigDict(extra="forbid")
    engine: str = Field(min_length=1)
    version: str = Field(min_length=1)
    queries: int = Field(ge=1)
    sat: int = Field(ge=0)
    unsat: int = Field(ge=0)
    unknown: int = Field(ge=0)
    eval: int = Field(ge=0)
    timeouts: int = Field(ge=0)
    steps: int = Field(ge=0)
    max_steps: int = Field(ge=1)
    complete: bool

    @model_validator(mode="after")
    def _step_cap(self) -> "SolverAccounting":
        if self.steps >= self.max_steps:
            raise ValueError("solver step cap reached; a capped run is not proven")
        if self.complete and (self.unknown != 0 or self.timeouts != 0):
            raise ValueError("complete solver accounting requires unknown == 0 and timeouts == 0")
        return self


class Calibration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    suite: str = Field(min_length=1)
    cases: int = Field(ge=1)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    known_good: bool
    known_bad: bool
    known_bad_rejected: bool
    complete: bool

    @model_validator(mode="after")
    def _counts(self) -> "Calibration":
        if self.cases < 2:
            raise ValueError("calibration requires cases >= 2")
        if self.passed + self.failed > self.cases:
            raise ValueError("calibration passed+failed exceeds cases")
        if not (self.known_good and self.known_bad and self.known_bad_rejected):
            raise ValueError(
                "calibration requires known_good, known_bad and known_bad_rejected"
            )
        if self.known_good and self.passed < 1:
            raise ValueError("known_good requires passed >= 1")
        if self.known_bad_rejected and self.failed < 1:
            raise ValueError("known_bad_rejected requires failed >= 1")
        return self


class Replay(BaseModel):
    model_config = ConfigDict(extra="forbid")
    command: str = Field(min_length=1)
    runs: int = Field(ge=2)
    identical: bool
    evidence_sha256: str = Field(pattern=HEX64)


class V4Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    gate: Literal["V4"] = "V4"
    kind: Literal["symbolic"] = "symbolic"
    scope: Literal["model"] = "model"
    state: Literal["passed"]
    ran: Literal[True] = True
    candidate_sha256: str = Field(pattern=HEX64)
    original_sha256: str = Field(pattern=HEX64)
    tool_versions: dict[str, str] = Field(min_length=1)
    preconditions: list[str] = Field(min_length=1)
    memory_predicates: list[str] = Field(min_length=1)
    forbidden_ranges: list[ForbiddenRange] | None = None
    hooks: list[str] = Field(min_length=1)
    exploration_accounting: ExplorationAccounting
    solver_accounting: SolverAccounting
    calibration: Calibration
    replay: Replay
    property_kind: Literal["pointer-flow", "memory-range"]
    claimed_scope: Literal["model"]
    not_claimed: list[str] = Field(min_length=1)
    source: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _complete(self) -> "V4Evidence":
        if not self.exploration_accounting.complete:
            raise ValueError("exploration accounting is incomplete")
        if not self.solver_accounting.complete:
            raise ValueError("solver accounting is incomplete")
        if not self.calibration.complete:
            raise ValueError("calibration is incomplete")
        if not self.replay.identical:
            raise ValueError("replay is not identical")
        if any(not key.strip() or not value.strip() for key, value in self.tool_versions.items()):
            raise ValueError("tool_versions entries must be non-empty")
        if not any("binary-level" in item.lower() for item in self.not_claimed):
            raise ValueError("not_claimed must explicitly exclude binary-level proof")
        if self.property_kind != "pointer-flow" and not self.forbidden_ranges:
            raise ValueError(
                "only pointer-flow may leave forbidden_ranges empty; "
                "memory-range needs at least one range"
            )
        return self


def write_v4_evidence(
    path: str | Path,
    data: object,
    *,
    candidate_sha256: str | None = None,
    original_sha256: str | None = None,
) -> V4Evidence:
    """Validate and atomically write one typed V4 artifact.

    This is the producer's write landing point. It refuses incomplete content;
    a caller without a reviewed solver-accounting harness cannot use it to
    manufacture a pass.
    """

    evidence = (
        data
        if isinstance(data, V4Evidence)
        else validate_v4_evidence(
            data,
            candidate_sha256=candidate_sha256,
            original_sha256=original_sha256,
        )
    )
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(evidence.model_dump(mode="json", exclude_none=True), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)
    return evidence



def _with_empty_disjunction_disclosure(
    not_claimed: list[str],
    *,
    cases: list[dict],
    candidate_sha256: str,
) -> list[str]:
    """Force the caveat only for a candidate unsat with free_calls=0."""

    if any(
        "empty-disjunction" in item.lower() or "empty disjunction" in item.lower()
        for item in not_claimed
    ):
        return not_claimed
    candidate = next(
        (
            case for case in cases
            if case.get("kind") == "known_good"
            and case.get("binary_sha256") == candidate_sha256
        ),
        None,
    )
    if candidate is None:
        return not_claimed
    solver = candidate.get("solver") or {}
    witness = candidate.get("witness") or {}
    if int(solver.get("unsat", 0)) > 0 and int(witness.get("free_calls", -1)) == 0:
        return not_claimed + [EMPTY_DISJUNCTION_DISCLOSURE]
    return not_claimed


def from_v4_harness(data: object) -> V4Evidence:
    """Minimal converter: M3 ``v4_harness`` output -> product V4Evidence.

    The harness already records the real exploration, solver, calibration and
    replay facts. This function maps those facts into the one product schema;
    it does not re-derive a verdict and it rejects missing or inconsistent
    sections instead of filling them with defaults.
    """

    if not isinstance(data, dict):
        raise V4EvidenceError("v4_harness output must be an object")
    try:
        cases = data["cases"]
        states = data["states"]
        solver = data["solver"]
        engine = data["engine"]
        replay = data["replay"]
        if not isinstance(cases, list) or not isinstance(states, dict):
            raise V4EvidenceError("v4_harness cases/states have the wrong shape")
        if not isinstance(solver, dict) or not isinstance(engine, dict):
            raise V4EvidenceError("v4_harness solver/engine have the wrong shape")
        if not isinstance(replay, dict):
            raise V4EvidenceError("v4_harness replay has the wrong shape")

        known_good_cases = [c for c in cases if c.get("kind") == "known_good"]
        known_bad_cases = [c for c in cases if c.get("kind") == "known_bad"]
        known_good = bool(known_good_cases)
        known_bad = bool(known_bad_cases)
        known_bad_rejected = bool(known_bad_cases) and all(
            c.get("observed") == "violated" for c in known_bad_cases
        )
        calibration_passed = sum(
            1 for c in known_good_cases if c.get("observed") == "holds"
        )
        calibration_failed = sum(
            1 for c in known_bad_cases if c.get("observed") == "violated"
        )

        digests = replay.get("digests") or []
        if not isinstance(digests, list) or not digests:
            raise V4EvidenceError("v4_harness replay has no digest")
        evidence_sha256 = str(digests[0])
        runs = int(replay.get("runs", len(digests)))
        identical = bool(
            replay.get("identical", runs >= 2 and len(set(digests)) == 1)
        )

        hooks = []
        for hook in data.get("hooks") or []:
            if not isinstance(hook, dict) or not hook.get("symbol"):
                raise V4EvidenceError("v4_harness hook is missing its symbol")
            hooks.append(str(hook["symbol"]))
        if not hooks:
            raise V4EvidenceError("v4_harness output has no hooks")

        tool_versions = {
            str(name): str(version)
            for name, version in engine.items()
            if name and version
        }
        if not tool_versions:
            raise V4EvidenceError("v4_harness engine has no versions")

        input_domain = str(data.get("input_domain") or "").strip()
        property_text = str(data.get("property_text") or "").strip()
        if not input_domain or not property_text:
            raise V4EvidenceError("v4_harness input_domain/property_text is empty")

        state_names = (
            "initial", "deadended", "errored", "unconstrained",
            "deferred", "active", "pruned",
        )
        missing_states = [name for name in state_names if name not in states]
        if missing_states:
            raise V4EvidenceError(
                "v4_harness states missing: " + ", ".join(missing_states)
            )
        exploration = {name: int(states[name]) for name in state_names}
        exploration["complete"] = bool(data["complete"])
        exploration["unexplored"] = list(data["unexplored"])

        solver_names = ("eval", "sat", "unsat", "unknown", "timeouts")
        missing_solver = [name for name in solver_names if name not in solver]
        if missing_solver:
            raise V4EvidenceError(
                "v4_harness solver missing: " + ", ".join(missing_solver)
            )
        solver_accounting = {
            "engine": "angr",
            "version": str(engine["angr"]),
            "queries": sum(int(solver[name]) for name in ("eval", "sat", "unsat", "unknown")),
            "sat": int(solver["sat"]),
            "unsat": int(solver["unsat"]),
            "unknown": int(solver["unknown"]),
            "eval": int(solver["eval"]),
            "timeouts": int(solver["timeouts"]),
            "steps": int(data["steps"]),
            "max_steps": int(data["max_steps"]),
            "complete": bool(data["complete"]),
        }

        payload = {
            "schema_version": 1,
            "gate": "V4",
            "kind": "symbolic",
            "scope": "model",
            "state": "passed",
            "ran": True,
            "candidate_sha256": str(data["candidate_sha256"]),
            "original_sha256": str(data["original_sha256"]),
            "tool_versions": tool_versions,
            "preconditions": [input_domain],
            "memory_predicates": [property_text],
            "property_kind": data["property_kind"],
            "hooks": hooks,
            "exploration_accounting": exploration,
            "solver_accounting": solver_accounting,
            "calibration": {
                "suite": str(data.get("generated_by") or "v4_harness"),
                "cases": len(cases),
                "passed": calibration_passed,
                "failed": calibration_failed,
                "known_good": known_good,
                "known_bad": known_bad,
                "known_bad_rejected": known_bad_rejected,
                "complete": bool(data.get("complete")),
            },
            "replay": {
                "command": str(data.get("generated_by") or "v4_harness"),
                "runs": runs,
                "identical": identical,
                "evidence_sha256": evidence_sha256,
            },
            "claimed_scope": data["claimed_scope"],
            "not_claimed": _with_empty_disjunction_disclosure(
                list(data["not_claimed"]),
                cases=cases,
                candidate_sha256=str(data["candidate_sha256"]),
            ),
            "source": {
                "target_entry": data.get("target_entry"),
                "entry_address": data.get("entry_address"),
                "contract_sha256": data.get("contract_sha256"),
                "property_text": property_text,
                "input_domain": input_domain,
                "generated_by": data.get("generated_by"),
                "property_kind": data["property_kind"],
                "cases": cases,
                "engine": engine,
            },
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise V4EvidenceError(f"v4_harness output cannot be converted: {exc}") from exc

    return validate_v4_evidence(
        payload,
        candidate_sha256=str(data["candidate_sha256"]),
        original_sha256=str(data["original_sha256"]),
    )


def validate_v4_evidence(
    data: object,
    *,
    candidate_sha256: str | None = None,
    original_sha256: str | None = None,
) -> V4Evidence:
    """Validate a complete V4 claim and its identity bindings.

    Raises V4EvidenceError for a missing section, incomplete accounting, a
    failed replay, or a hash mismatch. Callers must treat that as NOT VERIFIED,
    never as a pass.
    """

    try:
        evidence = V4Evidence.model_validate(data)
    except Exception as exc:  # pydantic.ValidationError and nested TypeErrors
        raise V4EvidenceError(str(exc)) from exc
    if candidate_sha256 is not None and evidence.candidate_sha256 != candidate_sha256:
        raise V4EvidenceError(
            f"candidate hash {evidence.candidate_sha256} != {candidate_sha256}"
        )
    if original_sha256 is not None and evidence.original_sha256 != original_sha256:
        raise V4EvidenceError(
            f"original hash {evidence.original_sha256} != {original_sha256}"
        )
    return evidence


__all__ = [
    "V4Evidence",
    "EMPTY_DISJUNCTION_DISCLOSURE",
    "V4EvidenceError",
    "from_v4_harness",
    "validate_v4_evidence",
    "write_v4_evidence",
]
