"""Runtime evidence records shared by the native and emulated runners."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class RuntimeCase:
    input_len: int
    exit_code: int | None = None
    timed_out: bool = False
    stdout_len: int = 0
    stderr_len: int = 0
    canary_intact: bool | None = None
    output_len: int | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RuntimeEvidence:
    tier: str = "static_only"
    engine: str = ""
    cases: list[RuntimeCase] = field(default_factory=list)
    verdict: str = "not_run"
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tier": self.tier,
            "engine": self.engine,
            "verdict": self.verdict,
            "cases": [case.to_dict() for case in self.cases],
            "limitations": list(self.limitations),
        }


def judge(cases: list[RuntimeCase], capacity: int) -> str:
    """Gate over runtime cases: every case must stay inside the capacity."""
    if not cases:
        return "not_run"
    for case in cases:
        if case.error or case.timed_out:
            return "fail"
        if case.exit_code != 0:
            return "fail"
        if case.canary_intact is False:
            return "fail"
        limit = min(case.input_len, max(capacity - 1, 0))
        if case.output_len is not None and case.output_len > limit:
            return "fail"
    return "pass"
