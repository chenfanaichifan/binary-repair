"""Unified capability Gap Registry record schema (Phase-7).

One record type for every kind of capability gap, independently of how it was
discovered:

* the 12 explicit ``docs/status/claims.json`` non-goals
  (``discovery_source="claims_non_goal"``);
* the mitigated runtime-evidence gap from the committed coverage audit
  (``discovery_source="failure_driven"``);
* candidates produced by the six discovery mechanisms
  (``discovery_source`` in knowledge / failure_driven / differential / mutation /
  metamorphic / sample_based / knowledge_source_scan).

Design rules:

* deterministic ids - the id is a pure function of the discovery source and a
  stable key (claim id / audit gap id / candidate key), so re-running discovery
  is byte-identical;
* no automatic promotion - only the claims migration may produce
  ``status="non_goal"`` and only an engineered mitigation may produce
  ``status="resolved"``; every discovery mechanism produces ``candidate`` and
  the artifact builder rejects anything else;
* a candidate can never claim ``verified``/``resolved`` by itself;
* every record carries ``proposed_experiment`` either as an executable proposal
  (``status="proposed"`` with ``experiment_id`` + ``steps``) or as an explicit
  ``status="cannot_plan"`` with a reason - a silent empty plan is invalid.

The module is stdlib-only and does no I/O; scripts/build_universe_dimension_registry
and scripts/discover_capability_gaps own artifact provenance.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable, Mapping

SCHEMA_VERSION = 1
KIND = "capability_gap_registry"

GAP_STATUSES: tuple[str, ...] = (
    "candidate",
    "open",
    "blocked",
    "non_goal",
    "resolved",
    "rejected",
)
SEVERITIES: tuple[str, ...] = ("critical", "high", "medium", "low", "info")
DISCOVERY_SOURCES: tuple[str, ...] = (
    "claims_non_goal",
    "knowledge",
    "failure_driven",
    "differential",
    "mutation",
    "metamorphic",
    "sample_based",
    "knowledge_source_scan",
)
RUNNABLE_DISCOVERY_SOURCES: tuple[str, ...] = (
    "knowledge",
    "failure_driven",
    "differential",
)
NOT_RUN_DISCOVERY_SOURCES: tuple[str, ...] = (
    "mutation",
    "metamorphic",
    "sample_based",
    "knowledge_source_scan",
)
FALSE_VERIFIED_RISK: tuple[str, ...] = ("none", "low", "medium", "high")
EXPERIMENT_STATUSES: tuple[str, ...] = ("proposed", "cannot_plan")

REQUIRED_FIELDS: tuple[str, ...] = (
    "schema_version",
    "gap_id",
    "discovery_source",
    "category",
    "subcategory",
    "target",
    "observed_failure",
    "existing_capability",
    "severity",
    "status",
    "evidence_refs",
    "proposed_experiment",
    "owner",
    "review_by",
    "verification_required",
    "false_verified_risk",
)

GAP_ID_RE = re.compile(r"^GAP-[A-Z0-9][A-Z0-9._-]*$")
REVIEW_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SOURCE_PREFIX = {
    "claims_non_goal": "CLAIM",
    "knowledge": "KNOW",
    "failure_driven": "FAIL",
    "differential": "DIFF",
    "mutation": "MUT",
    "metamorphic": "META",
    "sample_based": "SAMPLE",
    "knowledge_source_scan": "KSRC",
}

_SEVERITY_BY_CATEGORY = {
    "engine_gap": "high",
    "gate_mismatch": "high",
    "matrix_claim_mismatch": "medium",
    "oracle_gap": "medium",
    "runtime_gap": "medium",
    "non_goal": "info",
}

_FALSE_RISK_BY_CATEGORY = {
    "engine_gap": "medium",
    "gate_mismatch": "high",
    "matrix_claim_mismatch": "medium",
    "oracle_gap": "medium",
    "runtime_gap": "high",
    "non_goal": "medium",
}


# ---------------------------------------------------------------------------
# Id / canonical helpers
# ---------------------------------------------------------------------------


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _slug(text: str) -> str:
    """Uppercase deterministic slug for readable claim/mitigation ids."""
    slug = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").upper()
    return slug or "X"


def deterministic_gap_id(discovery_source: str, key: str) -> str:
    """Deterministic gap id: pure function of source + stable key.

    Claims/mitigations use a readable slug of the claim/audit id; discovery
    candidates use a short SHA-256 of the candidate key so ids stay stable across
    re-runs without depending on ordering or wall clock.
    """
    prefix = _SOURCE_PREFIX.get(discovery_source, "GAP")
    if discovery_source in {"claims_non_goal", "failure_driven"}:
        slug = _slug(key)
        if len(slug) > 80:
            slug = slug[:64].rstrip("-") + "-" + _short_hash(key)
        return f"GAP-{prefix}-{slug}"
    return f"GAP-{prefix}-{_short_hash(f'{discovery_source}|{key}')}"


def _short_hash(text: str, length: int = 12) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length].upper()


# ---------------------------------------------------------------------------
# Experience / plan helpers
# ---------------------------------------------------------------------------


def proposed_experiment(
    *,
    status: str,
    experiment_id: str | None = None,
    steps: Iterable[str] | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    """Build a valid proposed-experiment object (or an explicit cannot_plan)."""
    if status not in EXPERIMENT_STATUSES:
        raise ValueError(f"invalid proposed_experiment status: {status!r}")
    if status == "proposed":
        steps_list = [str(step) for step in (steps or []) if str(step).strip()]
        if not experiment_id or not steps_list:
            raise ValueError("proposed experiment needs experiment_id and steps")
        return {
            "status": "proposed",
            "experiment_id": experiment_id,
            "steps": steps_list,
        }
    if not reason or not str(reason).strip():
        raise ValueError("cannot_plan needs a reason")
    return {"status": "cannot_plan", "reason": str(reason)}


def cannot_plan(reason: str) -> dict[str, Any]:
    return proposed_experiment(status="cannot_plan", reason=reason)


# ---------------------------------------------------------------------------
# Record construction
# ---------------------------------------------------------------------------


def make_record(
    *,
    discovery_source: str,
    gap_id: str,
    category: str,
    subcategory: str,
    target: dict[str, Any],
    observed_failure: str,
    existing_capability: str,
    severity: str,
    status: str,
    evidence_refs: Iterable[str],
    plan: dict[str, Any],
    owner: str,
    review_by: str,
    verification_required: bool,
    false_verified_risk: str,
) -> dict[str, Any]:
    """Construct one validated GapRecord dict."""
    record = {
        "schema_version": SCHEMA_VERSION,
        "gap_id": str(gap_id),
        "discovery_source": str(discovery_source),
        "category": str(category),
        "subcategory": str(subcategory),
        "target": dict(target),
        "observed_failure": str(observed_failure),
        "existing_capability": str(existing_capability),
        "severity": str(severity),
        "status": str(status),
        "evidence_refs": [str(ref) for ref in evidence_refs],
        "proposed_experiment": dict(plan),
        "owner": str(owner),
        "review_by": str(review_by),
        "verification_required": bool(verification_required),
        "false_verified_risk": str(false_verified_risk),
    }
    problems = _record_problems(record)
    if problems:
        raise ValueError(f"invalid gap record {gap_id}: {'; '.join(problems)}")
    return record


def _record_problems(record: Mapping[str, Any]) -> list[str]:
    problems: list[str] = []
    if not isinstance(record, Mapping):
        return ["record is not an object"]
    missing = [field for field in REQUIRED_FIELDS if field not in record]
    if missing:
        problems.append(f"missing fields {missing}")
        return problems
    if record.get("schema_version") != SCHEMA_VERSION:
        problems.append(f"schema_version {record.get('schema_version')!r}")
    gap_id = str(record.get("gap_id") or "")
    if not GAP_ID_RE.match(gap_id):
        problems.append(f"invalid gap_id {gap_id!r}")
    if record.get("discovery_source") not in DISCOVERY_SOURCES:
        problems.append(f"invalid discovery_source {record.get('discovery_source')!r}")
    for field in ("category", "subcategory", "observed_failure",
                  "existing_capability", "owner"):
        if not str(record.get(field) or "").strip():
            problems.append(f"empty {field}")
    if not isinstance(record.get("target"), Mapping) or not str(
        (record.get("target") or {}).get("kind") or ""
    ).strip():
        problems.append("target must be an object with a kind")
    if record.get("severity") not in SEVERITIES:
        problems.append(f"invalid severity {record.get('severity')!r}")
    if record.get("status") not in GAP_STATUSES:
        problems.append(f"invalid status {record.get('status')!r}")
    refs = record.get("evidence_refs")
    if not isinstance(refs, list) or not refs or not all(
        isinstance(ref, str) and ref.strip() for ref in refs
    ):
        problems.append("evidence_refs must be a non-empty list of strings")
    plan = record.get("proposed_experiment")
    if not isinstance(plan, Mapping):
        problems.append("proposed_experiment must be an object")
    else:
        status = plan.get("status")
        if status not in EXPERIMENT_STATUSES:
            problems.append(f"invalid proposed_experiment status {status!r}")
        elif status == "proposed":
            if not str(plan.get("experiment_id") or "").strip():
                problems.append("proposed experiment missing experiment_id")
            steps = plan.get("steps")
            if not isinstance(steps, list) or not steps or not all(
                isinstance(step, str) and step.strip() for step in steps
            ):
                problems.append("proposed experiment needs non-empty steps")
        elif not str(plan.get("reason") or "").strip():
            problems.append("cannot_plan missing reason")
    if not REVIEW_DATE_RE.match(str(record.get("review_by") or "")):
        problems.append(f"invalid review_by {record.get('review_by')!r}")
    if not isinstance(record.get("verification_required"), bool):
        problems.append("verification_required must be a bool")
    if record.get("false_verified_risk") not in FALSE_VERIFIED_RISK:
        problems.append(
            f"invalid false_verified_risk {record.get('false_verified_risk')!r}"
        )
    return problems


# ---------------------------------------------------------------------------
# Claims non-goal migration (12 records, status=non_goal)
# ---------------------------------------------------------------------------


def from_claim_non_goal(
    non_goal: Mapping[str, Any],
    *,
    claims_path: str = "docs/status/claims.json",
    matrix_path: str = "artifacts/capability-gap-audit-2026-11-14/coverage-matrix.json",
) -> dict[str, Any]:
    """Migrate one claims.json non-goal into a unified GapRecord."""
    claim_id = str(non_goal.get("id") or "")
    if not claim_id:
        raise ValueError("claims non_goal without id")
    category = str(non_goal.get("category") or "non_goal")
    severity = _SEVERITY_BY_CATEGORY.get(category, "low")
    risk = _FALSE_RISK_BY_CATEGORY.get(category, "low")
    if category == "runtime_gap":
        plan = proposed_experiment(
            status="proposed",
            experiment_id="EXP-CLAIM-" + _slug(claim_id),
            steps=[
                "run the documented capability probe on a host/platform where the "
                "runtime path is expected to be available",
                "record the typed unavailable/available evidence and never mark a "
                "verified_patch without external-PoC/native evidence",
            ],
        )
    else:
        plan = cannot_plan(
            "explicit non-goal in docs/status/claims.json: no repair experiment "
            "is planned; only enforcement/regression verification applies"
        )
    return make_record(
        discovery_source="claims_non_goal",
        gap_id=deterministic_gap_id("claims_non_goal", claim_id),
        category=category,
        subcategory=claim_id,
        target={
            "kind": "claims_non_goal",
            "claim_id": claim_id,
            "applies_to": category,
        },
        observed_failure=str(non_goal.get("claim") or ""),
        existing_capability=str(non_goal.get("enforcement") or ""),
        severity=severity,
        status="non_goal",
        evidence_refs=[
            f"{claims_path}#non_goals[id={claim_id}]",
            f"{matrix_path}#universe.cells[claims_non_goal_id={claim_id}]",
        ],
        plan=plan,
        owner=str(non_goal.get("owner") or "lead"),
        review_by=str(non_goal.get("review_by") or "2027-05-14"),
        verification_required=True,
        false_verified_risk=risk,
    )


def from_mitigated_gap(
    audit_gap: Mapping[str, Any],
    *,
    matrix_path: str = "artifacts/capability-gap-audit-2026-11-14/coverage-matrix.json",
) -> dict[str, Any]:
    """Migrate one audited mitigated gap into a resolved GapRecord."""
    gap_id = str(audit_gap.get("gap_id") or "")
    if not gap_id:
        raise ValueError("audit gap without gap_id")
    return make_record(
        discovery_source="failure_driven",
        gap_id=deterministic_gap_id("failure_driven", gap_id),
        category=str(audit_gap.get("category") or "runtime_gap"),
        subcategory=gap_id,
        target={"kind": "audit_gap", "gap_id": gap_id},
        observed_failure=str(audit_gap.get("symptom") or ""),
        existing_capability=(
            "mitigated in the committed coverage audit: "
            + str(audit_gap.get("next_step") or "")
        ),
        severity="info",
        status="resolved",
        evidence_refs=[f"{matrix_path}#gaps[id={gap_id}]"],
        plan=proposed_experiment(
            status="proposed",
            experiment_id="EXP-MIT-RUNTIME-TIER-HOST-MATCH",
            steps=[
                "re-run the runtime capability probe on a host matching the cell "
                "architecture to obtain native-tier evidence",
                "if no matching host is available, keep reporting the mitigated "
                "platform-gated status and never fabricate native evidence",
            ],
        ),
        owner="runtime",
        review_by="2027-05-14",
        verification_required=True,
        false_verified_risk="high",
    )


def claim_records(claims: Mapping[str, Any]) -> list[dict[str, Any]]:
    non_goals = claims.get("non_goals")
    if not isinstance(non_goals, list) or len(non_goals) != 12:
        raise ValueError(
            f"claims non_goals={len(non_goals) if isinstance(non_goals, list) else 'missing'} "
            "(expected 12)"
        )
    return [from_claim_non_goal(item) for item in non_goals]


def mitigated_records(matrix: Mapping[str, Any]) -> list[dict[str, Any]]:
    gaps = matrix.get("gaps")
    if not isinstance(gaps, list):
        raise ValueError("coverage matrix has no gaps list")
    mitigated = [gap for gap in gaps if gap.get("status") == "mitigated"]
    if len(mitigated) != 1:
        raise ValueError(f"expected exactly 1 mitigated audit gap, found {len(mitigated)}")
    return [from_mitigated_gap(mitigated[0])]


# ---------------------------------------------------------------------------
# Discovery candidate construction (never promoted)
# ---------------------------------------------------------------------------


def make_candidate(
    *,
    discovery_source: str,
    key: str,
    category: str,
    subcategory: str,
    target: dict[str, Any],
    observed_failure: str,
    existing_capability: str,
    severity: str,
    evidence_refs: Iterable[str],
    plan: dict[str, Any],
    owner: str,
    review_by: str,
    false_verified_risk: str = "medium",
    verification_required: bool = True,
) -> dict[str, Any]:
    """Create one discovery candidate record (status is always ``candidate``)."""
    if discovery_source not in RUNNABLE_DISCOVERY_SOURCES:
        raise ValueError(f"{discovery_source!r} is not a runnable discovery source")
    return make_record(
        discovery_source=discovery_source,
        gap_id=deterministic_gap_id(discovery_source, key),
        category=category,
        subcategory=subcategory,
        target=target,
        observed_failure=observed_failure,
        existing_capability=existing_capability,
        severity=severity,
        status="candidate",
        evidence_refs=evidence_refs,
        plan=plan,
        owner=owner,
        review_by=review_by,
        verification_required=verification_required,
        false_verified_risk=false_verified_risk,
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_records(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Validate a full GapRecord registry; returns ``{"ok", "violations", ...}``."""
    record_list = list(records)
    violations: list[str] = []
    ids: list[str] = []
    for index, record in enumerate(record_list):
        problems = _record_problems(record)
        label = record.get("gap_id") if isinstance(record, Mapping) else f"record[{index}]"
        for problem in problems:
            violations.append(f"{label}: {problem}")
        if isinstance(record, Mapping):
            ids.append(str(record.get("gap_id") or ""))
            source = record.get("discovery_source")
            status = record.get("status")
            target_kind = str((record.get("target") or {}).get("kind") or "")
            migrated_mitigation = source == "failure_driven" and target_kind == "audit_gap"
            if (
                source in RUNNABLE_DISCOVERY_SOURCES
                and not migrated_mitigation
                and status != "candidate"
            ):
                violations.append(
                    f"{label}: discovery candidate status={status!r} "
                    "(auto-promotion is forbidden; candidates stay candidate)"
                )
            if source == "claims_non_goal" and status != "non_goal":
                violations.append(
                    f"{label}: claims_non_goal record status={status!r} (expected non_goal)"
                )
            if source == "failure_driven" and status not in {"resolved", "candidate"}:
                violations.append(
                    f"{label}: failure_driven baseline record status={status!r}"
                )
    duplicates = sorted({gap_id for gap_id in ids if ids.count(gap_id) > 1})
    if duplicates:
        violations.append(f"duplicate gap ids: {duplicates}")
    for gap_id in ids:
        if not GAP_ID_RE.match(gap_id):
            violations.append(f"invalid gap id: {gap_id!r}")
    sources = {str(record.get("discovery_source")) for record in record_list
               if isinstance(record, Mapping)}
    return {
        "ok": not violations,
        "violations": violations,
        "record_count": len(record_list),
        "unique_id_count": len(set(ids)),
        "sources": sorted(sources),
    }


def sort_records(records: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Deterministic ordering for artifacts."""
    return sorted((dict(record) for record in records),
                  key=lambda record: str(record.get("gap_id")))
