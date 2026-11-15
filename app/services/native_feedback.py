"""Typed native-gate failure feedback for a bounded AI repair retry.

Only observed evidence is emitted.  Missing trace data (registers, stack,
control-flow) is left absent rather than synthesized.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

_SIGNAL_RE = re.compile(r"signal (\d+)")
_RETRYABLE = frozenset({
    "candidate_crash", "security_still_triggered",
    "regression_crash", "regression_mismatch",
})
MAX_TEXT = 400


def _truncate(value: Any, limit: int = MAX_TEXT) -> str:
    return str(value if value is not None else "")[:limit]


def _signal(text: str) -> int | None:
    match = _SIGNAL_RE.search(text or "")
    return int(match.group(1)) if match else None


def _case_dict(case: Any) -> dict[str, Any]:
    return {
        "case_id": getattr(case, "case_id", ""),
        "kind": getattr(case, "kind", ""),
        "executable": getattr(case, "executable", ""),
        "exit_code": getattr(case, "exit_code", None),
        "crashed": bool(getattr(case, "crashed", False)),
        "timed_out": bool(getattr(case, "timed_out", False)),
        "stdout": _truncate(getattr(case, "stdout", "")),
        "stderr": _truncate(getattr(case, "stderr", "")),
        "expected_ok": bool(getattr(case, "expected_ok", False)),
    }


@dataclass
class NativeFeedback:
    case_id: str
    failure_class: str
    retryable: bool
    retry_reason: str
    original: dict[str, Any] | None = None
    candidate: dict[str, Any] | None = None
    signal: int | None = None
    abi_findings: list[dict[str, Any]] = field(default_factory=list)
    expected: dict[str, Any] | None = None
    observed: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "case_id": self.case_id,
            "stage": "native_gate",
            "failure_class": self.failure_class,
            "retryable": self.retryable,
            "retry_reason": self.retry_reason,
            "original": self.original,
            "candidate": self.candidate,
            "signal": self.signal,
            "abi_findings": list(self.abi_findings),
            "expected": self.expected,
            "observed": self.observed,
            "limitations": [
                "register/stack/control-flow diffs are absent unless an external tracer supplied them",
            ],
        }


def analyze_native_failure(poc_evidence: Any, *,
                           injection: dict[str, Any] | None = None,
                           case_id: str = "") -> NativeFeedback | None:
    """Analyze a failed PocEvidence; return feedback only for a real failure."""
    if poc_evidence is None or getattr(poc_evidence, "status", "") != "fail":
        return None
    cases = list(getattr(poc_evidence, "cases", []) or [])
    regression = list(getattr(poc_evidence, "regression", []) or [])
    candidate_cases = [c for c in cases if getattr(c, "executable", "") == "candidate"]
    candidate_reg = [c for c in regression if getattr(c, "executable", "") == "candidate"]
    failure_case = next((c for c in candidate_cases if not getattr(c, "expected_ok", True)), None)
    failure_reg = next((c for c in candidate_reg if not getattr(c, "expected_ok", True)), None)
    observed = failure_case or failure_reg
    if observed is None:
        return None
    timed_out = bool(getattr(observed, "timed_out", False))
    crashed = bool(getattr(observed, "crashed", False))
    if timed_out:
        failure_class, retryable = "timeout", False
        reason = "timeout is not automatically retried; it needs a separate diagnosis"
    elif failure_case is not None and crashed:
        failure_class, retryable = "candidate_crash", True
        reason = "candidate crashed on a PoC/regression case; bounded semantic retry allowed"
    elif failure_case is not None:
        failure_class, retryable = "security_still_triggered", True
        reason = "candidate did not produce the expected safe result on a PoC case"
    elif failure_reg is not None and crashed:
        failure_class, retryable = "regression_crash", True
        reason = "candidate crashed on a normal regression input"
    else:
        failure_class, retryable = "regression_mismatch", True
        reason = "candidate changed normal observable behavior"
    original = next((c for c in cases if getattr(c, "executable", "") == "original"
                     and getattr(c, "case_id", "") == getattr(observed, "case_id", "")), None)
    abi = (injection or {}).get("abi") or {}
    findings = list(abi.get("findings") or []) if isinstance(abi, dict) else []
    return NativeFeedback(
        case_id=case_id or str(getattr(observed, "case_id", "")),
        failure_class=failure_class,
        retryable=retryable,
        retry_reason=reason,
        original=_case_dict(original) if original is not None else None,
        candidate=_case_dict(observed),
        signal=_signal(getattr(observed, "stderr", "")),
        abi_findings=[item for item in findings if isinstance(item, dict)][:8],
        expected={"kind": getattr(observed, "kind", ""),
                  "expected_ok_was": bool(getattr(observed, "expected_ok", False))},
        observed={"stdout": _truncate(getattr(observed, "stdout", "")),
                  "stderr": _truncate(getattr(observed, "stderr", ""))},
    )
