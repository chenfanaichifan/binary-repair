"""Phase-8C C10: semantic regression evidence for repaired candidates.

The module classifies the *declared* PoC/regression differential evidence for an
original/candidate pair.  It never invents execution evidence and never claims
full semantic equivalence: it only compares the regression cases that the
declared PoC manifest actually executed and reports the exact fields that
changed (exit code, crash, stdout, stderr, timeout, errno state).

Decisions
---------
``accepted``  - the PoC differential passed and every compared regression case
                preserved its recorded original behaviour.
``rejected``  - the PoC differential failed, a regression case changed, or the
                candidate crashed/timed out: the candidate introduces a
                semantic regression and must not be accepted.
``not_run``   - no candidate or no usable oracle evidence: the semantic
                regression contract could not be evaluated (never a pass).

Data privacy: the detailed per-case comparison is private evidence.  Callers
that publish an aggregate (hidden lane) must use :meth:`public_summary`, which
strips case ids/details.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

SCHEMA_VERSION = 1
STATUSES = ("pass", "fail", "not_run", "unavailable", "invalid")
DECISIONS = ("accepted", "rejected", "not_run")

#: Fields compared for every original/candidate regression case pair.
COMPARED_FIELDS = (
    "exit_code",
    "crashed",
    "stdout_hex",
    "stderr",
    "timed_out",
    "errno_value",
)

#: Limitation recorded on every accepted result: the comparison is bounded to
#: the declared regression cases, never a whole-program equivalence proof.
BOUNDED_LIMITATION = (
    "semantic regression is bounded to the declared regression/PoC case ids; "
    "it is not a full semantic-equivalence proof of the candidate"
)


class SemanticRegressionError(RuntimeError):
    """The semantic-regression request itself is unusable (fail closed)."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(payload: Any) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("ascii")


def _case_dict(case: Any) -> dict[str, Any]:
    if isinstance(case, dict):
        return dict(case)
    if hasattr(case, "to_dict"):
        value = case.to_dict()
        return dict(value) if isinstance(value, dict) else {}
    return {}


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("utf-8", "replace")
    return "" if value is None else str(value)


def _stdout_view(case: dict[str, Any]) -> str:
    hex_value = case.get("stdout_hex")
    if isinstance(hex_value, str) and hex_value:
        return "hex:" + hex_value
    return "text:" + _text(case.get("stdout"))


def _errno_view(case: dict[str, Any]) -> tuple[Any, Any]:
    return (case.get("errno_value"), tuple(case.get("syscall_errors") or ()))


def compare_case(
    original: dict[str, Any],
    candidate: dict[str, Any],
) -> list[str]:
    """Return the regression mismatches for one original/candidate case pair."""
    mismatches: list[str] = []
    base_id = _text(original.get("case_id") or candidate.get("case_id") or "?")
    if candidate.get("crashed") is True:
        mismatches.append(f"{base_id}: candidate crashed")
    if candidate.get("timed_out") is True:
        mismatches.append(f"{base_id}: candidate timed out")
    original_exit = original.get("exit_code")
    candidate_exit = candidate.get("exit_code")
    if original_exit != candidate_exit:
        mismatches.append(
            f"{base_id}: exit_code {original_exit!r} -> {candidate_exit!r}"
        )
    if bool(original.get("crashed")) != bool(candidate.get("crashed")):
        mismatches.append(
            f"{base_id}: crashed {bool(original.get('crashed'))} -> "
            f"{bool(candidate.get('crashed'))}"
        )
    if bool(original.get("timed_out")) != bool(candidate.get("timed_out")):
        mismatches.append(
            f"{base_id}: timed_out {bool(original.get('timed_out'))} -> "
            f"{bool(candidate.get('timed_out'))}"
        )
    original_stdout = _stdout_view(original)
    candidate_stdout = _stdout_view(candidate)
    if original_stdout != candidate_stdout:
        mismatches.append(f"{base_id}: stdout changed")
    if _text(original.get("stderr")) != _text(candidate.get("stderr")):
        mismatches.append(f"{base_id}: stderr changed")
    if _errno_view(original) != _errno_view(candidate):
        mismatches.append(f"{base_id}: errno state changed")
    return mismatches


def pair_regression_cases(
    evidence: dict[str, Any],
    expected_case_ids: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """Pair original/candidate evidence cases by case id, preserving order.

    ``poc_runner`` evidence records all original cases first and then the
    candidate cases of the same group.  The pairing is by exact ``case_id``;
    an unmatched case is reported and never silently dropped.
    """
    expected = [str(item) for item in (expected_case_ids or []) if str(item)]
    cases = [_case_dict(case) for case in (evidence.get("regression") or [])]
    originals: dict[str, dict[str, Any]] = {}
    candidates: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for case in cases:
        case_id = _text(case.get("case_id"))
        if not case_id:
            continue
        executable = _text(case.get("executable") or "").lower()
        bucket = candidates if executable == "candidate" else originals
        if case_id not in order:
            order.append(case_id)
        bucket.setdefault(case_id, case)
    selected = expected or order
    pairs: list[dict[str, Any]] = []
    for case_id in selected:
        original = originals.get(case_id)
        candidate = candidates.get(case_id)
        if original is None or candidate is None:
            pairs.append({
                "case_id": case_id,
                "kind": "unpaired",
                "matched": False,
                "mismatches": [
                    "missing original evidence" if original is None
                    else "missing candidate evidence"
                ],
                "original": original,
                "candidate": candidate,
            })
            continue
        mismatches = compare_case(original, candidate)
        pairs.append({
            "case_id": case_id,
            "kind": _text(original.get("kind") or candidate.get("kind") or "regression"),
            "matched": not mismatches,
            "mismatches": mismatches,
            "original": original,
            "candidate": candidate,
        })
    return pairs


@dataclass
class SemanticRegressionResult:
    """Private classification of one semantic-regression evaluation."""

    status: str = "not_run"
    decision: str = "not_run"
    regression: bool | None = None
    expected_case_ids: list[str] = field(default_factory=list)
    cases: list[dict[str, Any]] = field(default_factory=list)
    oracle: dict[str, Any] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)
    evidence_sha256: str | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": self.status,
            "decision": self.decision,
            "regression": self.regression,
            "expected_case_ids": list(self.expected_case_ids),
            "cases": [dict(case) for case in self.cases],
            "oracle": dict(self.oracle),
            "limitations": list(self.limitations),
            "evidence_sha256": self.evidence_sha256,
            "reason": self.reason,
        }

    def public_summary(self, *, hidden: bool = False) -> dict[str, Any]:
        """Aggregate-only projection that never leaks case details.

        ``hidden=True`` additionally hashes case ids so a private corpus cannot
        leak identifiers through a published aggregate.
        """
        matched = sum(1 for case in self.cases if case.get("matched"))
        mismatched = len(self.cases) - matched
        summary: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "status": self.status,
            "decision": self.decision,
            "regression": self.regression,
            "case_count": len(self.cases),
            "matched_count": matched,
            "mismatched_count": mismatched,
            "limitations": list(self.limitations),
        }
        if hidden:
            summary["expected_case_count"] = len(self.expected_case_ids)
        else:
            summary["expected_case_ids"] = list(self.expected_case_ids)
            summary["case_ids"] = [
                str(case.get("case_id")) for case in self.cases
            ]
        return summary


def _result(
    *,
    status: str,
    decision: str,
    regression: bool | None,
    pairs: list[dict[str, Any]] | None = None,
    expected_case_ids: Iterable[str] | None = None,
    limitations: Iterable[str] = (),
    oracle: dict[str, Any] | None = None,
    evidence_sha256: str | None = None,
    reason: str | None = None,
) -> SemanticRegressionResult:
    return SemanticRegressionResult(
        status=status,
        decision=decision,
        regression=regression,
        expected_case_ids=[str(item) for item in (expected_case_ids or [])],
        cases=list(pairs or []),
        oracle=dict(oracle or {}),
        limitations=list(limitations),
        evidence_sha256=evidence_sha256,
        reason=reason,
    )


def evaluate_evidence(
    evidence: Any,
    *,
    expected_regression_ids: Iterable[str] | None = None,
    hidden: bool = False,
    require_cases: bool = True,
) -> SemanticRegressionResult:
    """Classify already-collected ``poc_runner`` evidence (no execution).

    ``hidden`` only affects helpers that publish results; the classification
    itself is identical for public and hidden samples.
    """
    if not isinstance(evidence, dict) or not evidence:
        return _result(
            status="not_run", decision="not_run", regression=None,
            limitations=["no oracle evidence was supplied; semantic regression "
                         "was not evaluated (never a pass)"],
            reason="no oracle evidence",
        )
    oracle = {
        "runner": evidence.get("runner") or None,
        "tier": evidence.get("tier") or None,
        "status": evidence.get("status") or "unknown",
        "stdout_signature": evidence.get("stdout_signature") or None,
        "no_input": bool(evidence.get("no_input")),
    }
    oracle["evidence_sha256"] = _sha256_bytes(_canonical(evidence))
    status = _text(evidence.get("status") or "")
    if status == "unavailable":
        limitation = "; ".join(
            _text(item) for item in (evidence.get("limitations") or [])
            if _text(item)
        ) or "external PoC/oracle runner unavailable"
        return _result(
            status="not_run", decision="not_run", regression=None,
            expected_case_ids=expected_regression_ids,
            limitations=[f"oracle unavailable: {limitation}"],
            oracle=oracle, evidence_sha256=oracle["evidence_sha256"],
            reason="oracle unavailable",
        )
    if status not in {"pass", "fail"}:
        return _result(
            status="not_run", decision="not_run", regression=None,
            expected_case_ids=expected_regression_ids,
            limitations=[f"oracle status {status or 'unknown'} is not executable "
                         "evidence; semantic regression was not evaluated"],
            oracle=oracle, evidence_sha256=oracle["evidence_sha256"],
            reason=f"oracle status {status or 'unknown'}",
        )
    pairs = pair_regression_cases(evidence, expected_regression_ids)
    mismatches = [
        mismatch for case in pairs if not case.get("matched")
        for mismatch in (case.get("mismatches") or [])
    ]
    if status == "fail":
        return _result(
            status="fail", decision="rejected", regression=False,
            pairs=pairs, expected_case_ids=expected_regression_ids,
            limitations=[
                "the declared PoC differential did not pass on the candidate; "
                "the candidate is rejected and semantic regression is not "
                "claimed",
                BOUNDED_LIMITATION,
            ],
            oracle=oracle, evidence_sha256=oracle["evidence_sha256"],
            reason="PoC differential failed",
        )
    if mismatches:
        return _result(
            status="fail", decision="rejected", regression=False,
            pairs=pairs, expected_case_ids=expected_regression_ids,
            limitations=[
                f"{len(mismatches)} declared regression case field(s) changed; "
                "the candidate introduces a semantic regression",
                BOUNDED_LIMITATION,
            ],
            oracle=oracle, evidence_sha256=oracle["evidence_sha256"],
            reason="regression case mismatch",
        )
    if not pairs and require_cases and not oracle["no_input"]:
        return _result(
            status="not_run", decision="not_run", regression=None,
            expected_case_ids=expected_regression_ids,
            limitations=[
                "the oracle evidence contains no declared regression cases; "
                "semantic regression was not evaluated (never a pass)",
            ],
            oracle=oracle, evidence_sha256=oracle["evidence_sha256"],
            reason="no regression evidence",
        )
    limitations = [BOUNDED_LIMITATION]
    if oracle["no_input"] and not pairs:
        limitations.append(
            "the declared no-input model executed no regression cases; the "
            "PoC differential is the only semantic evidence"
        )
    return _result(
        status="pass", decision="accepted", regression=None if not pairs else True,
        pairs=pairs, expected_case_ids=expected_regression_ids,
        limitations=limitations, oracle=oracle,
        evidence_sha256=oracle["evidence_sha256"],
    )


def run_live(
    original: bytes,
    candidate: bytes | None,
    poc_manifest: dict[str, Any] | str,
    *,
    run_poc: Callable[..., Any] | None = None,
    expected_regression_ids: Iterable[str] | None = None,
    hidden: bool = False,
) -> SemanticRegressionResult:
    """Execute the declared PoC/regression differential and classify it.

    This is the live path (used by tests and standalone callers); the benchmark
    runner reuses :func:`evaluate_evidence` on the oracle evidence that the
    repair/verification stages already produced, so no extra guest execution is
    introduced.
    """
    if candidate is None:
        return _result(
            status="not_run", decision="not_run", regression=None,
            expected_case_ids=expected_regression_ids,
            limitations=["no candidate bytes exist; semantic regression was "
                         "not evaluated (never a pass)"],
            reason="no candidate",
        )
    if run_poc is None:
        try:
            from app.services.poc_runner import run_poc as run_poc_impl
        except Exception as exc:  # noqa: BLE001 - unavailable runner is evidence
            return _result(
                status="not_run", decision="not_run", regression=None,
                expected_case_ids=expected_regression_ids,
                limitations=[f"oracle runner unavailable: {type(exc).__name__}: {exc}"],
                reason="oracle runner unavailable",
            )
        run_poc = run_poc_impl
    try:
        from app.services.poc_runner import load_manifest

        spec = load_manifest(poc_manifest)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return _result(
            status="invalid", decision="not_run", regression=None,
            expected_case_ids=expected_regression_ids,
            limitations=[f"PoC regression manifest is unusable: "
                         f"{type(exc).__name__}: {exc}"],
            reason="invalid PoC manifest",
        )
    try:
        raw = run_poc(original, candidate, spec)
    except Exception as exc:  # noqa: BLE001 - recorded, never hidden
        return _result(
            status="not_run", decision="not_run", regression=None,
            expected_case_ids=expected_regression_ids,
            limitations=[f"oracle runner failed: {type(exc).__name__}: {exc}"],
            reason="oracle runner failed",
        )
    evidence = raw.to_dict() if hasattr(raw, "to_dict") else raw
    return evaluate_evidence(
        evidence,
        expected_regression_ids=expected_regression_ids,
        hidden=hidden,
    )


__all__ = [
    "BOUNDED_LIMITATION",
    "COMPARED_FIELDS",
    "DECISIONS",
    "SCHEMA_VERSION",
    "STATUSES",
    "SemanticRegressionError",
    "SemanticRegressionResult",
    "compare_case",
    "evaluate_evidence",
    "pair_regression_cases",
    "run_live",
]
