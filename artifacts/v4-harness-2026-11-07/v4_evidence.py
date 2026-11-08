"""Typed V4 evidence and its only writer.

Nothing here trusts a caller: `write_v4_evidence` re-checks every invariant the
acceptance standard asks for (docs/handoffs/62 §3) and refuses to write a file
that does not satisfy them. Hand-assembled JSON cannot pass through it, which is
the point — the producer must not be able to write a V4 file by hand.

The shape is the one the V4 producer was asked to fill:

    cases >= 2, one known_good and one known_bad
    known_good / known_bad / known_bad_rejected
    complete is True and unexplored is empty
    unknown == 0 and timeouts == 0
    steps < max_steps
    claimed_scope == "model"
    not_claimed names the binary-level exclusion
    replay.runs >= 2 and replay.identical is True
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

Scope = Literal["metadata", "static", "binary", "model", "replay"]
Verdict = Literal["holds", "violated", "unknown"]


class V4EvidenceError(ValueError):
    """Raised when the evidence would not satisfy the V4 checklist."""


@dataclass
class SolverAccounting:
    eval: int = 0
    sat: int = 0
    unsat: int = 0
    unknown: int = 0
    timeouts: int = 0

    @property
    def queries(self) -> int:
        return self.eval + self.sat + self.unsat + self.unknown

    def add(self, other: "SolverAccounting") -> None:
        self.eval += other.eval
        self.sat += other.sat
        self.unsat += other.unsat
        self.unknown += other.unknown
        self.timeouts += other.timeouts


@dataclass
class StateAccounting:
    """Where every state ended up. Nothing may be dropped quietly."""

    initial: int = 0
    deadended: int = 0
    errored: int = 0
    unconstrained: int = 0
    deferred: int = 0
    active: int = 0
    pruned: int = 0


@dataclass
class V4Case:
    id: str
    kind: Literal["known_good", "known_bad"]
    binary_sha256: str
    expected: Verdict
    observed: Verdict
    property_text: str
    steps: int
    max_steps: int
    states: StateAccounting
    solver: SolverAccounting
    witness: dict[str, Any] | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def agrees(self) -> bool:
        return self.expected == self.observed


@dataclass
class Replay:
    runs: int
    digests: list[str]

    @property
    def identical(self) -> bool:
        return len(self.digests) >= 2 and len(set(self.digests)) == 1


@dataclass
class V4Evidence:
    gate: str
    candidate_sha256: str
    original_sha256: str
    contract_sha256: str
    target_entry: str
    entry_address: str
    property_text: str
    input_domain: str
    hooks: list[dict[str, str]]
    cases: list[V4Case]
    claimed_scope: Scope
    not_claimed: list[str]
    complete: bool
    unexplored: list[str]
    unknown: int
    timeouts: int
    steps: int
    max_steps: int
    solver: SolverAccounting
    states: StateAccounting
    replay: Replay
    engine: dict[str, str]
    generated_by: str = "v4_harness.py"
    schema_version: int = 1

    # -- derived flags the checklist names explicitly -------------------------
    @property
    def known_good(self) -> str | None:
        for c in self.cases:
            if c.kind == "known_good":
                return c.id
        return None

    @property
    def known_bad(self) -> str | None:
        for c in self.cases:
            if c.kind == "known_bad":
                return c.id
        return None

    @property
    def known_bad_rejected(self) -> bool:
        """The harness must not accept the broken binary as repaired."""
        for c in self.cases:
            if c.kind == "known_bad":
                return c.observed == "violated"
        return False

    def payload(self) -> dict[str, Any]:
        data = asdict(self)
        data["known_good"] = self.known_good
        data["known_bad"] = self.known_bad
        data["known_bad_rejected"] = self.known_bad_rejected
        data["replay"]["identical"] = self.replay.identical
        return data

    # -- the checklist, as code ------------------------------------------------
    def check(self) -> None:
        problems: list[str] = []

        kinds = [c.kind for c in self.cases]
        if len(self.cases) < 2:
            problems.append(f"cases must be >= 2, got {len(self.cases)}")
        if kinds.count("known_good") != 1:
            problems.append("exactly one known_good case is required")
        if kinds.count("known_bad") != 1:
            problems.append("exactly one known_bad case is required")
        if not self.known_bad_rejected:
            problems.append("known_bad_rejected is false: the harness accepted a broken binary")

        for c in self.cases:
            if not c.agrees:
                problems.append(f"case {c.id}: expected {c.expected}, observed {c.observed}")
            if c.steps >= c.max_steps:
                problems.append(f"case {c.id}: steps {c.steps} reached max_steps {c.max_steps}")
            if c.states.active or c.states.deferred or c.states.unconstrained:
                problems.append(f"case {c.id}: states left unexplored")
            if c.states.errored:
                problems.append(f"case {c.id}: {c.states.errored} errored state(s)")

        if not self.complete:
            problems.append("complete is false")
        if self.unexplored:
            problems.append(f"unexplored is not empty: {self.unexplored}")
        if self.unknown != 0:
            problems.append(f"unknown must be 0, got {self.unknown}")
        if self.timeouts != 0:
            problems.append(f"timeouts must be 0, got {self.timeouts}")
        if self.steps >= self.max_steps:
            problems.append(f"steps {self.steps} reached max_steps {self.max_steps}")
        if self.claimed_scope != "model":
            problems.append(f"claimed_scope must be 'model', got {self.claimed_scope!r}")

        joined = " ".join(self.not_claimed).lower()
        if "binary-level" not in joined:
            problems.append("not_claimed must exclude the binary-level reading")
        if not self.entry_address.startswith("0x"):
            problems.append("entry_address must be recorded as 0x…")
        if self.replay.runs < 2:
            problems.append("replay.runs must be >= 2")
        if not self.replay.identical:
            problems.append("replay digests differ: the result is not reproducible")

        if problems:
            raise V4EvidenceError("; ".join(problems))


def write_v4_evidence(path: str | Path, evidence: V4Evidence) -> Path:
    """Validate, then write. A rejected evidence object writes nothing."""
    evidence.check()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(evidence.payload(), indent=2, sort_keys=True, ensure_ascii=False)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(text + "\n", encoding="utf-8", newline="\n")
    tmp.replace(target)
    return target


__all__ = [
    "Replay",
    "SolverAccounting",
    "StateAccounting",
    "V4Case",
    "V4Evidence",
    "V4EvidenceError",
    "write_v4_evidence",
]
