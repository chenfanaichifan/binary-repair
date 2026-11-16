"""Phase-8D capability promotion gate (pure policy, no I/O).

The gate is intentionally conservative.  It evaluates one requested transition
of a capability record and returns allowed/denied with explicit evidence
checks.  It does not read artifacts and it never mutates a record.

Only the next legal state can be reached:

    discovered -> analysis_only -> candidate_generated
              -> independently_verified -> generalized -> promoted

A transition is denied when required evidence is missing, when any required
evidence is ``not_run``/``blocked``, when an internal/published
``false_verified`` is non-zero, when hidden/holdout evidence is absent for
generalization, when promotion lacks independent human approval, or when
auto-promotion is requested.

A denied decision is a normal result, not an error.  A ``promoted`` decision is
still not a capability claim by itself: the caller must publish the approval
and evidence refs, and the release process must keep the promotion gate output
separate from capability claims.
"""
from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

SCHEMA_VERSION = 1
KIND = "phase8d_promotion_decision"
STATES: tuple[str, ...] = (
    "discovered",
    "analysis_only",
    "candidate_generated",
    "independently_verified",
    "generalized",
    "promoted",
)
LEGAL_NEXT: dict[str, str] = {
    "discovered": "analysis_only",
    "analysis_only": "candidate_generated",
    "candidate_generated": "independently_verified",
    "independently_verified": "generalized",
    "generalized": "promoted",
}
ORDER: dict[str, int] = {state: index for index, state in enumerate(STATES)}
BLOCKED_VALUES: frozenset[str] = frozenset({"not_run", "blocked", "unavailable", "inconclusive"})
APPROVAL_ROLES: tuple[str, ...] = ("independent-reviewer", "security-reviewer", "governance-board")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DECISIONS: tuple[str, ...] = ("allowed", "denied")


class PromotionError(ValueError):
    """Malformed promotion request; callers should treat it as not_run."""


def _get(evidence: Mapping[str, Any], path: str) -> Any:
    value: Any = evidence
    for part in path.split("."):
        if not isinstance(value, Mapping) or part not in value:
            return None
        value = value[part]
    return value


def _nonempty_refs(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(
        isinstance(item, str) and item.strip() for item in value
    )


def _sha(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _truthy(value: Any) -> bool:
    return value is True


def _blocked_marker(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in BLOCKED_VALUES
    if isinstance(value, list):
        return any(_blocked_marker(item) for item in value)
    if isinstance(value, Mapping):
        return any(_blocked_marker(item) for item in value.values())
    return False


def _check(condition: bool, check_id: str, detail: str) -> dict[str, Any]:
    return {"id": check_id, "status": "passed" if condition else "failed", "detail": detail}


def legal_transition(current: str, target: str) -> bool:
    return LEGAL_NEXT.get(current) == target


def required_checks(target: str, evidence: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return evidence checks for entering *target*.

    The record's current state is an assertion that prior levels were reached;
    ``evaluate_transition`` additionally requires
    ``prior_state_evidence_complete`` and ``prior_evidence_refs``.  Evidence for
    the target level itself is checked here, not fabricated from later levels.
    """
    checks: list[dict[str, Any]] = []
    if target == "analysis_only":
        checks.extend([
            _check(_nonempty_refs(_get(evidence, "discovery.evidence_refs")),
                   "discovery.evidence_refs",
                   "discovery evidence refs are required"),
            _check(_get(evidence, "discovery.discovery_source") not in (None, ""),
                   "discovery.discovery_source",
                   "discovery source is required"),
            _check(_sha(_get(evidence, "analysis.artifact_sha256")),
                   "analysis.artifact_sha256",
                   "analysis artifact sha256 is required"),
            _check(_nonempty_refs(_get(evidence, "analysis.evidence_refs")),
                   "analysis.evidence_refs",
                   "analysis evidence refs are required"),
            _check(_nonempty_refs(_get(evidence, "analysis.limitations")),
                   "analysis.limitations",
                   "analysis limitations are required"),
        ])
    elif target == "candidate_generated":
        checks.extend([
            _check(_sha(_get(evidence, "candidate.candidate_sha256")),
                   "candidate.candidate_sha256",
                   "candidate sha256 is required"),
            _check(_sha(_get(evidence, "candidate.patch_plan_sha256")),
                   "candidate.patch_plan_sha256",
                   "patch plan sha256 is required"),
            _check(_nonempty_refs(_get(evidence, "candidate.integrity_evidence_refs")),
                   "candidate.integrity_evidence_refs",
                   "candidate integrity evidence is required"),
        ])
    elif target == "independently_verified":
        checks.extend([
            _check(_get(evidence, "verification.decision") == "verified",
                   "verification.decision",
                   "independent verifier must decide verified"),
            _check(_truthy(_get(evidence, "verification.independent")),
                   "verification.independent",
                   "verifier must be independent"),
            _check(_truthy(_get(evidence, "verification.oracle_executed")),
                   "verification.oracle_executed",
                   "an oracle must actually execute"),
            _check(_get(evidence, "verification.false_verified") == 0,
                   "verification.false_verified",
                   "false_verified must be exactly 0"),
            _check(_truthy(_get(evidence, "verification.regression_pass")),
                   "verification.regression_pass",
                   "bounded regression evidence must pass"),
            _check(_nonempty_refs(_get(evidence, "verification.evidence_refs")),
                   "verification.evidence_refs",
                   "verification evidence refs are required"),
        ])
    elif target in {"generalized", "promoted"}:
        checks.extend([
            _check(_truthy(_get(evidence, "generalization.public_verified")),
                   "generalization.public_verified",
                   "public verification evidence is required"),
            _check(_truthy(_get(evidence, "generalization.hidden_verified")),
                   "generalization.hidden_verified",
                   "hidden verification is required"),
            _check((_get(evidence, "generalization.hidden_verified_count") or 0) > 0,
                   "generalization.hidden_verified_count",
                   "at least one independently verified hidden sample is required"),
            _check(_truthy(_get(evidence, "generalization.holdout_verified")),
                   "generalization.holdout_verified",
                   "holdout verification is required"),
            _check(_truthy(_get(evidence, "generalization.regression_pass")),
                   "generalization.regression_pass",
                   "regression must pass on public and hidden cases"),
            _check(_get(evidence, "generalization.false_verified") == 0,
                   "generalization.false_verified",
                   "hidden/aggregate false_verified must be 0"),
            _check(_sha(_get(evidence, "generalization.hidden_commitment_sha256")),
                   "generalization.hidden_commitment_sha256",
                   "hidden commitment digest is required"),
            _check(_sha(_get(evidence, "generalization.hidden_aggregate_sha256")),
                   "generalization.hidden_aggregate_sha256",
                   "hidden aggregate digest is required"),
            _check(_nonempty_refs(_get(evidence, "generalization.evidence_refs")),
                   "generalization.evidence_refs",
                   "generalization evidence refs are required"),
        ])
    if target == "promoted":
        approval = _get(evidence, "approval") or {}
        checks.extend([
            _check(_truthy(_get(evidence, "generalization.no_unresolved_blockers")),
                   "generalization.no_unresolved_blockers",
                   "no unresolved blockers may remain before promotion"),
            _check(isinstance(approval, Mapping) and bool(str(approval.get("approved_by") or "").strip()),
                   "approval.approved_by",
                   "a human/independent approver id is required"),
            _check(isinstance(approval, Mapping) and approval.get("independent") is True,
                   "approval.independent",
                   "approval must be independent of the repair/verification author"),
            _check(isinstance(approval, Mapping) and approval.get("role") in APPROVAL_ROLES,
                   "approval.role",
                   "approval role must be an independent reviewer/security/governance role"),
            _check(isinstance(approval, Mapping) and bool(str(approval.get("approval_ref") or "").strip()),
                   "approval.approval_ref",
                   "approval must cite an auditable approval reference"),
            _check(isinstance(approval, Mapping) and DATE_RE.fullmatch(str(approval.get("approved_at") or "")) is not None,
                   "approval.approved_at",
                   "approval date must be YYYY-MM-DD"),
        ])
    return checks

def validate_history(history: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Validate a claimed state history never skips a level."""
    problems: list[str] = []
    last = None
    seen: list[str] = []
    for index, item in enumerate(history):
        state = str(item.get("state") if isinstance(item, Mapping) else item or "")
        if state not in STATES:
            problems.append(f"history[{index}] invalid state {state!r}")
            continue
        if last is not None and ORDER[state] != ORDER[last] + 1:
            problems.append(f"history[{index}] illegal jump {last}->{state}")
        seen.append(state)
        last = state
    return {"ok": not problems, "violations": problems, "states": seen}


def evaluate_transition(
    record: Mapping[str, Any],
    *,
    target: str,
    evidence: Mapping[str, Any],
    auto_promotion: bool = False,
) -> dict[str, Any]:
    """Evaluate one requested promotion transition without mutating anything."""
    if not isinstance(record, Mapping):
        raise PromotionError("record must be a mapping")
    if target not in STATES:
        raise PromotionError(f"unknown target state {target!r}")
    if not isinstance(evidence, Mapping):
        raise PromotionError("evidence must be a mapping")
    current = str(record.get("current_state") or "")
    if current not in STATES:
        raise PromotionError(f"current_state is not a legal state: {current!r}")
    record_id = str(record.get("record_id") or "")
    if not record_id:
        raise PromotionError("record_id is required")
    violations: list[str] = []
    checks: list[dict[str, Any]] = []

    if auto_promotion:
        violations.append("auto-promotion is forbidden")
    if record.get("auto_promotion") is True or evidence.get("auto_promotion") is True:
        violations.append("auto-promotion marker is forbidden")
    if not legal_transition(current, target):
        expected = LEGAL_NEXT.get(current)
        violations.append(
            f"illegal transition {current}->{target}; legal next is {expected!r}")
    if _blocked_marker(evidence):
        violations.append("required evidence contains not_run/blocked/unavailable")
    if record.get("status") in BLOCKED_VALUES:
        violations.append(f"record status is {record.get('status')!r}; not_run is never a pass")
    false_verified = _get(evidence, "verification.false_verified")
    if false_verified not in (None, 0):
        violations.append(f"verification.false_verified={false_verified!r} must be 0")
    internal = _get(evidence, "verification.false_verified_internal")
    if internal not in (None, 0):
        violations.append(f"verification.false_verified_internal={internal!r} must be 0")
    prior_complete = record.get("prior_state_evidence_complete") is True
    prior_refs = record.get("prior_evidence_refs")
    if not prior_complete:
        violations.append("prior_state_evidence_complete must be true")
    if not _nonempty_refs(prior_refs):
        violations.append("prior_evidence_refs are required")
    history = record.get("state_history")
    history_result = validate_history(history) if history is not None else {"ok": True, "violations": []}
    if history is not None and not history_result["ok"]:
        violations.extend(history_result["violations"])
    checks = required_checks(target, evidence)
    checks.extend([
        _check(prior_complete, "prior_state_evidence_complete",
               "prior levels must be evidenced before the next transition"),
        _check(_nonempty_refs(prior_refs), "prior_evidence_refs",
               "prior evidence refs are required"),
        _check(not auto_promotion, "auto_promotion", "auto-promotion must be false"),
        _check(not _blocked_marker(evidence), "no_not_run_evidence",
               "no required evidence may be not_run/blocked"),
        _check(record.get("status") not in BLOCKED_VALUES, "record_status",
               "record status may not be not_run/blocked"),
    ])
    failed = [check for check in checks if check["status"] != "passed"]
    for check in failed:
        violations.append(f"{check['id']}: {check['detail']}")
    decision = "allowed" if not violations else "denied"
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "record_id": record_id,
        "from_state": current,
        "target_state": target,
        "decision": decision,
        "ok": decision == "allowed",
        "violations": violations,
        "checks": checks,
        "auto_promotion": False,
        "human_review_required": target in {"generalized", "promoted"},
        "independent_approval_required": target == "promoted",
        "not_run_is_pass": False,
        "evidence_refs": sorted({
            str(ref)
            for path in ("discovery.evidence_refs", "analysis.evidence_refs",
                         "candidate.integrity_evidence_refs", "verification.evidence_refs",
                         "generalization.evidence_refs")
            for ref in (_get(evidence, path) or [])
        }),
    }


def evaluate_chain(
    record: Mapping[str, Any],
    *,
    steps: Iterable[Mapping[str, Any]],
    auto_promotion: bool = False,
) -> dict[str, Any]:
    """Evaluate a sequence of ``{"target","evidence"}`` transitions in order.

    The caller must supply the updated record state for each step; this helper
    rejects histories that skip a level or include duplicate/reverse states.
    """
    current = str(record.get("current_state") or "")
    decisions: list[dict[str, Any]] = []
    simulated = dict(record)
    history: list[dict[str, Any]] = [{"state": current}] if current in STATES else []
    for step in steps:
        target = str(step.get("target") or "")
        result = evaluate_transition(
            simulated, target=target, evidence=step.get("evidence") or {},
            auto_promotion=auto_promotion,
        )
        decisions.append(result)
        if result["decision"] != "allowed":
            break
        simulated = {**simulated, "current_state": target, "status": "open"}
        history.append({"state": target})
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "phase8d_promotion_chain",
        "record_id": str(record.get("record_id") or ""),
        "decisions": decisions,
        "final_state": simulated.get("current_state"),
        "history": history,
        "history_validation": validate_history(history),
        "auto_promotion": False,
        "all_allowed": all(item["decision"] == "allowed" for item in decisions),
    }
