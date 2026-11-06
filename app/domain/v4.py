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
    model_config = ConfigDict(extra="forbid")
    states_explored: int = Field(ge=0)
    states_pruned: int = Field(ge=0)
    resource_pruned: int = Field(ge=0)
    max_depth: int = Field(ge=0)
    complete: bool
    unexplored: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _complete_has_no_unexplored(self) -> "ExplorationAccounting":
        if self.complete and self.unexplored:
            raise ValueError("complete exploration must have unexplored == []")
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
    forbidden_ranges: list[ForbiddenRange] = Field(min_length=1)
    hooks: list[str] = Field(min_length=1)
    exploration_accounting: ExplorationAccounting
    solver_accounting: SolverAccounting
    calibration: Calibration
    replay: Replay
    claimed_scope: Literal["model"]
    not_claimed: list[str] = Field(min_length=1)

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

    evidence = validate_v4_evidence(
        data,
        candidate_sha256=candidate_sha256,
        original_sha256=original_sha256,
    )
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(evidence.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)
    return evidence


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
    "V4EvidenceError",
    "validate_v4_evidence",
    "write_v4_evidence",
]
