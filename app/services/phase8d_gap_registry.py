"""Phase-8D additive gap registry.

This module extends, but never rewrites, the Phase-7 ``gap_registry`` artifact.
It turns the eight Phase-8D audit findings (``AUDIT-8D-01`` .. ``AUDIT-8D-08``)
into reviewable records with:

* the existing GapRecord core fields where meaningful;
* explicit reproduction status/confidence/dependencies;
* lineage links to existing historical gap ids (validated against the
  committed Phase-7 registry);
* capability-dimension refs (D01-D20) and a concrete proposed experiment;
* an explicit ``capability_promotion=false`` policy.

The module is stdlib-only and does no I/O.  The builder script owns artifact
provenance and verifies that the historical registry bytes are unchanged.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping

SCHEMA_VERSION = 1
KIND = "phase8d_gap_registry"
RECORD_KIND = "phase8d_gap_record"
GENERATED_AT = "2026-11-17T00:00:00Z"
HISTORICAL_REGISTRY = "artifacts/gap-registry-2026-11-16/gaps.json"
HISTORICAL_REGISTRY_KIND = "gap_registry"
HISTORICAL_RECORD_COUNT = 64

AUDIT_IDS: tuple[str, ...] = tuple(f"AUDIT-8D-{n:02d}" for n in range(1, 9))
CATEGORIES: tuple[str, ...] = (
    "hidden_evidence_gap",
    "verifier_root_cause_gap",
    "discovery_gap",
    "acceptance_gap",
    "reflection_gap",
    "governance_gap",
    "isolation_gap",
)
REPRODUCTION_STATUSES: tuple[str, ...] = (
    "reproduced",
    "partially_reproduced",
    "not_reproduced",
    "not_run",
    "blocked",
)
CONFIDENCES: tuple[str, ...] = ("high", "medium", "low")
STATUSES: tuple[str, ...] = ("open", "blocked", "not_run", "candidate")
SEVERITIES: tuple[str, ...] = ("critical", "high", "medium", "low", "info")
LINEAGE_RELATIONS: tuple[str, ...] = (
    "derived_from",
    "supersedes",
    "related_to",
    "blocks",
    "extends",
)
DIMENSIONS: tuple[str, ...] = tuple(f"D{n:02d}" for n in range(1, 21))
EXPERIMENT_STATUSES: tuple[str, ...] = ("proposed", "cannot_plan")

REQUIRED_FIELDS: tuple[str, ...] = (
    "schema_version",
    "kind",
    "gap_id",
    "audit_id",
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
    "reproduction_status",
    "confidence",
    "dependencies",
    "lineage",
    "capability_dimensions",
    "limitations",
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def proposed_experiment(
    *,
    status: str,
    experiment_id: str | None = None,
    steps: Iterable[str] | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    if status not in EXPERIMENT_STATUSES:
        raise ValueError(f"invalid proposed_experiment status: {status!r}")
    if status == "proposed":
        step_list = [str(step).strip() for step in (steps or []) if str(step).strip()]
        if not experiment_id or not step_list:
            raise ValueError("proposed experiment needs experiment_id and steps")
        return {"status": "proposed", "experiment_id": experiment_id, "steps": step_list}
    if not reason or not str(reason).strip():
        raise ValueError("cannot_plan needs a reason")
    return {"status": "cannot_plan", "reason": str(reason)}


def _spec(
    *,
    audit_id: str,
    subcategory: str,
    category: str,
    target: dict[str, Any],
    observed_failure: str,
    existing_capability: str,
    severity: str,
    status: str,
    evidence_refs: Iterable[str],
    experiment_id: str,
    steps: Iterable[str],
    owner: str,
    review_by: str,
    false_verified_risk: str,
    reproduction_status: str,
    confidence: str,
    dependencies: Iterable[str],
    parents: Iterable[str],
    dimensions: Iterable[str],
    limitations: Iterable[str],
) -> dict[str, Any]:
    return {
        "audit_id": audit_id,
        "gap_id": "GAP-8D-" + audit_id.replace("AUDIT-8D-", "AUDIT-"),
        "category": category,
        "subcategory": subcategory,
        "target": dict(target),
        "observed_failure": observed_failure,
        "existing_capability": existing_capability,
        "severity": severity,
        "status": status,
        "evidence_refs": [str(ref) for ref in evidence_refs],
        "proposed_experiment": proposed_experiment(
            status="proposed", experiment_id=experiment_id, steps=steps
        ),
        "owner": owner,
        "review_by": review_by,
        "verification_required": True,
        "false_verified_risk": false_verified_risk,
        "reproduction_status": reproduction_status,
        "confidence": confidence,
        "dependencies": [str(dep) for dep in dependencies],
        "lineage": {
            "derived_from": [str(parent) for parent in parents],
            "supersedes": [],
            "related_to": [],
            "blocks": [],
            "extends": [],
        },
        "capability_dimensions": [str(dim) for dim in dimensions],
        "limitations": [str(item) for item in limitations],
    }


# ---------------------------------------------------------------------------
# The eight Phase-8D audit findings
# ---------------------------------------------------------------------------

AUDIT_SPECS: tuple[dict[str, Any], ...] = (
    _spec(
        audit_id="AUDIT-8D-01",
        subcategory="hidden-zero-candidates-stage-unattributed",
        category="hidden_evidence_gap",
        target={"kind": "hidden_benchmark_aggregate", "benchmark_id": "phase8c-hidden"},
        observed_failure=(
            "The final hidden lane executed 8 samples (6 runtime, 2 analysis-only) "
            "but produced 0 candidates and 0 independent verifications. The public "
            "aggregate has only final status counts/rates; it cannot attribute the "
            "zero-candidate outcome to detection, root-cause, localization, strategy, "
            "candidate generation or verification. A zero result without stage "
            "attribution is an evaluation gap, not evidence of capability."
        ),
        existing_capability=(
            "Phase-8C emits per-public-sample stage metrics and hidden aggregate-only "
            "counts; hidden per-stage attribution is not implemented and hidden "
            "per-sample identifiers must stay private."
        ),
        severity="high",
        status="open",
        evidence_refs=[
            "artifacts/phase8c-hidden-2026-11-16/aggregate.json#aggregate.denominator",
            "artifacts/phase8c-hidden-2026-11-16/aggregate.json#by_arch.x86_64",
            "benchmark/phase8c/hidden-commitment.json#samples",
            "artifacts/phase8c-quality-2026-11-16/full/quality.json#checks[id=hidden-aggregate]",
        ],
        experiment_id="EXP-8D-HIDDEN-STAGE-ATTRIBUTION",
        steps=[
            "extend the hidden aggregate with private-stage counters for detection, root cause, localization, strategy and candidate generation, and publish only the aggregate counts",
            "replay the final hidden lane with D00/D01 instrumentation and verify the counters sum to the 8 executed samples without exposing per-sample ids",
            "record stage attribution as evidence; do not promote any capability from the hidden result",
        ],
        owner="benchmark",
        review_by="2027-02-28",
        false_verified_risk="high",
        reproduction_status="reproduced",
        confidence="high",
        dependencies=[],
        parents=[
            "GAP-FAIL-META-GATE-MISMATCH-GATE-SCENARIO-EXECUTION",
            "GAP-KNOW-4E20E505D6BE",
        ],
        dimensions=["D02", "D19"],
        limitations=[
            "hidden stage attribution must remain aggregate-only; private sample ids/paths cannot be public",
            "a zero-candidate result is a measured coverage gap, not a capability success",
        ],
    ),
    _spec(
        audit_id="AUDIT-8D-02",
        subcategory="heap-malloc-abi-rejection-unclassified",
        category="verifier_root_cause_gap",
        target={
            "kind": "benchmark_sample",
            "sample_id": "heap-malloc",
            "public_results": "benchmark/phase8c/results.json",
        },
        observed_failure=(
            "The public heap-malloc candidate was claimed deterministic-verified, then "
            "independently rejected by the ABI check with branch_target_unknown, "
            "call_target_not_allowed and no_ret. The disagreement is preserved, but no "
            "root-cause classification exists yet, so it is unclear whether the engine's "
            "plan omitted ABI evidence, the verifier required evidence the sample cannot "
            "supply, or both."
        ),
        existing_capability=(
            "Phase-8B/C verifier fails closed and the benchmark runner withdraws the "
            "deterministic claim; no root-cause probe classifies the ABI rejection."
        ),
        severity="high",
        status="open",
        evidence_refs=[
            "benchmark/phase8c/results.json#samples[id=heap-malloc]",
            "artifacts/phase8c-benchmark-2026-11-16/disagreements.json#0",
            "app/services/independent_verifier.py#abi_blocks",
            "app/services/benchmark_runner.py#disagreements",
        ],
        experiment_id="EXP-8D-HEAP-MALLOC-ABI-ROOT-CAUSE",
        steps=[
            "replay the exact heap-malloc candidate/plan/verifier metadata without changing verifier acceptance rules",
            "classify the rejection as engine-plan omission, verifier-evidence limitation or sample limitation using provenance evidence",
            "add the classification to the finding and rerun the benchmark; keep published false_verified=0 and the withdrawal intact",
        ],
        owner="verifier",
        review_by="2027-02-28",
        false_verified_risk="critical",
        reproduction_status="reproduced",
        confidence="high",
        dependencies=["AUDIT-8D-01"],
        parents=[
            "GAP-FAIL-META-GATE-MISMATCH-GATE-REWRITE",
            "GAP-KNOW-2449225E53BC",
            "GAP-KNOW-0046331D4CF9",
        ],
        dimensions=["D03", "D09", "D10"],
        limitations=[
            "no verifier loosening is permitted; a root-cause explanation does not verify the candidate",
            "ABI evidence unavailable must remain not_run, never pass",
        ],
    ),
    _spec(
        audit_id="AUDIT-8D-03",
        subcategory="four-of-seven-discovery-mechanisms-not-run",
        category="discovery_gap",
        target={"kind": "gap_registry_mechanisms", "registry": "artifacts/gap-registry-2026-11-16"},
        observed_failure=(
            "The historical discovery report runs only knowledge, failure_driven and "
            "differential (3/7). Mutation, metamorphic, sample_based and "
            "knowledge_source_scan are explicit not_run with no engine/corpus; the "
            "absence of four mechanisms means the capability space is only partially "
            "searched."
        ),
        existing_capability=(
            "Three deterministic mechanisms produce 64 records; four mechanisms are "
            "not_run and must not be counted as zero-gap evidence."
        ),
        severity="high",
        status="open",
        evidence_refs=[
            "artifacts/gap-registry-2026-11-16/README.md#mechanism-runs",
            "artifacts/gap-registry-2026-11-16/gaps.json#validation",
            "scripts/discover_capability_gaps.py#mechanisms",
        ],
        experiment_id="EXP-8D-DISCOVERY-ADAPTERS",
        steps=[
            "implement one deterministic mutation/metamorphic adapter with a versioned local corpus and provenance",
            "implement sample_based/knowledge_source_scan only when a local, licensed corpus/feed is provisioned; otherwise keep explicit not_run",
            "run all mechanisms together and compare newly discovered gaps against the historical registry without rewriting it",
        ],
        owner="discovery",
        review_by="2027-03-31",
        false_verified_risk="high",
        reproduction_status="reproduced",
        confidence="high",
        dependencies=[],
        parents=["GAP-KNOW-8CFA10A33EE8", "GAP-KNOW-E9D869738D70"],
        dimensions=["D09", "D14", "D20"],
        limitations=[
            "no fabricated mutation/metamorphic corpus; absent corpora remain not_run",
            "discovery candidates are never capability promotion evidence",
        ],
    ),
    _spec(
        audit_id="AUDIT-8D-04",
        subcategory="acceptance-false-reject-coverage-absent",
        category="acceptance_gap",
        target={"kind": "acceptance_model", "report": "artifacts/acceptance-model-audit-2026-11-16/report.json"},
        observed_failure=(
            "The acceptance audit covers 62 positive/negative cases across AM01-AM28 "
            "with precision/recall 1.0, but it has no systematic False Reject set: "
            "valid repairs that a correct rule must accept are not independently "
            "tested as a class. A rule set can reject all repairs and still pass the "
            "current negative-heavy matrix."
        ),
        existing_capability=(
            "13 positive and 49 negative cases exist; there is no measured "
            "valid-repair-acceptance suite or False Reject rate."
        ),
        severity="high",
        status="open",
        evidence_refs=[
            "artifacts/acceptance-model-audit-2026-11-16/report.json#positive_case_count",
            "artifacts/acceptance-model-audit-2026-11-16/report.json#negative_case_count",
            "app/services/acceptance_models.py#AM01-AM28",
        ],
        experiment_id="EXP-8D-FALSE-REJECT-SUITE",
        steps=[
            "construct independently reviewed valid-repair fixtures whose acceptance is required for each affected AM class",
            "add a false-reject metric and a differential valid-vs-invalid decision table; never pass by rejecting all inputs",
            "run the suite and publish false_reject_count/rate with failures counted, not hidden",
        ],
        owner="acceptance",
        review_by="2027-03-31",
        false_verified_risk="critical",
        reproduction_status="reproduced",
        confidence="high",
        dependencies=[],
        parents=[
            "GAP-FAIL-META-GATE-MISMATCH-SAFE-DEFAULT",
            "GAP-FAIL-META-GATE-MISMATCH-GATE-PROFILE-ENFORCEMENT",
        ],
        dimensions=["D19"],
        limitations=[
            "a valid-repair fixture needs independent review; generator-only self-acceptance is not evidence",
            "false-reject coverage is not a capability promotion",
        ],
    ),
    _spec(
        audit_id="AUDIT-8D-05",
        subcategory="acceptance-rule-mutation-absent",
        category="acceptance_gap",
        target={"kind": "acceptance_model", "report": "artifacts/acceptance-model-audit-2026-11-16/report.json"},
        observed_failure=(
            "The acceptance model has no systematic rule-mutation suite: thresholds, "
            "scope rules and required-evidence gates are not deliberately weakened/"
            "altered to prove the audit still rejects invalid candidates. The current "
            "audit tests known invalid fixtures, not the audit's own rules."
        ),
        existing_capability=(
            "62 static cases; no acceptance mutation harness, no threshold/scope "
            "mutation results, no negative test of the acceptance rule engine."
        ),
        severity="high",
        status="open",
        evidence_refs=[
            "artifacts/acceptance-model-audit-2026-11-16/report.json#case_count",
            "scripts/audit_acceptance_models.py#cases",
            "app/services/acceptance_models.py#thresholds",
        ],
        experiment_id="EXP-8D-ACCEPTANCE-MUTATION",
        steps=[
            "inject bounded mutations into thresholds, scope checks and required-evidence rules in a test-only copy",
            "verify the audit detects every mutation that would admit an invalid candidate and that legal-rule changes are review-gated",
            "record mutation survival counts and never mutate the production acceptance model",
        ],
        owner="acceptance",
        review_by="2027-03-31",
        false_verified_risk="critical",
        reproduction_status="reproduced",
        confidence="high",
        dependencies=["AUDIT-8D-04"],
        parents=["GAP-FAIL-META-GATE-MISMATCH-GATE-SATISFIABILITY"],
        dimensions=["D19"],
        limitations=[
            "rule mutation is a test of the acceptance model, not a license to change production thresholds",
            "mutation survival=0 is required before any promotion evidence is trusted",
        ],
    ),
    _spec(
        audit_id="AUDIT-8D-06",
        subcategory="reflection-plans-without-execution",
        category="reflection_gap",
        target={"kind": "reflection_artifact", "artifact": "artifacts/autonomous-reflection-2026-11-16/reflection.json"},
        observed_failure=(
            "The reflection artifact contains 101 records and 12 candidate decisions "
            "with proposed experiments, but there is no execution runner/result "
            "artifact: plans are not executed, falsification conditions are not "
            "evaluated, and no regression/promotion decision follows from them."
        ),
        existing_capability=(
            "Reflection produces analysis-only records; verified is always false and "
            "no experiment execution or result analyzer exists."
        ),
        severity="high",
        status="open",
        evidence_refs=[
            "artifacts/autonomous-reflection-2026-11-16/reflection.json#summary",
            "artifacts/autonomous-reflection-2026-11-16/reflection.json#contract.capability_decisions",
            "app/services/reflection_engine.py",
        ],
        experiment_id="EXP-8D-REFLECTION-EXECUTION",
        steps=[
            "select one bounded proposed experiment with a falsification condition and an isolated fixture",
            "execute it in a sandboxed runner and persist input/output/exit/oracle evidence under a new artifact directory",
            "feed the result back into reflection only as an analysis input; any capability change still needs the promotion gate",
        ],
        owner="reflection",
        review_by="2027-03-31",
        false_verified_risk="high",
        reproduction_status="reproduced",
        confidence="high",
        dependencies=[],
        parents=["GAP-KNOW-E9D869738D70"],
        dimensions=["D20"],
        limitations=[
            "executing a reflection experiment does not promote a capability",
            "untrusted experiment output must not be treated as verification without an independent verifier",
        ],
    ),
    _spec(
        audit_id="AUDIT-8D-07",
        subcategory="no-promotion-state-machine",
        category="governance_gap",
        target={"kind": "capability_promotion", "policy": "missing"},
        observed_failure=(
            "No promotion gate enforces discovered -> analysis_only -> "
            "candidate_generated -> independently_verified -> generalized -> promoted. "
            "There is no legal-transition checker, no evidence requirements per level, "
            "no hidden/holdout and regression requirements, and no independent/human "
            "approval for promotion. A record can therefore be described as a "
            "capability without a verifiable state history."
        ),
        existing_capability=(
            "Phase-8B/C evidence records verified/rejected/not_run but there is no "
            "promotion state machine, no auto-promotion ban, and no independent "
            "approval contract."
        ),
        severity="critical",
        status="open",
        evidence_refs=[
            "docs/status/claims.json#phase8c_ground_truth.status",
            "docs/acceptance/LIMITATIONS.md#phase-8c",
            "scripts/audit_repair_readiness.py#G30",
        ],
        experiment_id="EXP-8D-PROMOTION-GATE",
        steps=[
            "implement the additive promotion_gate service with legal transitions, per-level evidence requirements and an independent-approval field",
            "evaluate the Phase-8C public/hidden evidence: independently_verified may be reached only by public fixture evidence; generalized must fail while hidden verified=0; promoted must fail without independent approval",
            "publish denied/allowed decisions; never auto-promote and never treat not_run as pass",
        ],
        owner="governance",
        review_by="2027-02-28",
        false_verified_risk="critical",
        reproduction_status="reproduced",
        confidence="high",
        dependencies=["AUDIT-8D-01", "AUDIT-8D-02"],
        parents=[
            "GAP-FAIL-META-GATE-MISMATCH-GATE-PROFILE-ENFORCEMENT",
            "GAP-FAIL-META-GATE-MISMATCH-GATE-PROFILE-CHECKS",
        ],
        dimensions=["D19", "D20"],
        limitations=[
            "a gate decision is not a capability claim; promoted remains false until independent approval",
            "hidden evidence cannot be exposed per sample just to satisfy generalization",
        ],
    ),
    _spec(
        audit_id="AUDIT-8D-08",
        subcategory="hidden-isolation-operational-not-cryptographic",
        category="isolation_gap",
        target={"kind": "hidden_corpus", "root": "private", "commitment": "benchmark/phase8c/hidden-commitment.json"},
        observed_failure=(
            "The hidden corpus root is 0700 and commitment-only publicly, but isolation "
            "is operational: same-UID/root readers can inspect it, and no automated "
            "audit checks root permissions, commitment/aggregate consistency, public "
            "leakage and material integrity together. A clean hidden contamination "
            "result is not a cryptographic isolation proof."
        ),
        existing_capability=(
            "C4/C5 enforce 0700, public commitment and contamination checks at build "
            "time; no independent Phase-8D isolation audit artifact exists."
        ),
        severity="critical",
        status="open",
        evidence_refs=[
            "docs/operations/phase8c-hidden-corpus.md#isolation-is-operational-not-cryptographic",
            "benchmark/phase8c/hidden-commitment.json#limitations",
            "artifacts/phase8c-hidden-2026-11-16/aggregate.json#aggregate",
            "artifacts/phase8c-contamination-2026-11-16/hidden/contamination.json#verdict",
        ],
        experiment_id="EXP-8D-HIDDEN-ISOLATION-AUDIT",
        steps=[
            "implement a read-only audit for root mode, commitment/aggregate consistency, private material integrity and public leak scanning",
            "fail closed on 0700 violation, tamper, missing commitment or hidden id/path leakage; record operational-not-cryptographic limitation explicitly",
            "run it against the real private root read-only and publish only the audit summary/hashes",
        ],
        owner="security",
        review_by="2027-02-28",
        false_verified_risk="critical",
        reproduction_status="reproduced",
        confidence="high",
        dependencies=[],
        parents=[
            "GAP-CLAIM-RG-EXTERNAL-POC-DOC-MACHO-X86-64",
            "GAP-FAIL-META-GATE-MISMATCH-GATE-POC-UNAVAILABLE",
        ],
        dimensions=["D02", "D13", "D19"],
        limitations=[
            "operational isolation is not cryptographic; same-UID/root readers remain a limitation",
            "the audit must not copy hidden bytes, sample ids or private paths into public artifacts",
        ],
    ),
)


def make_records() -> list[dict[str, Any]]:
    """Build the eight additive records without reading/writing the old registry."""
    records: list[dict[str, Any]] = []
    for spec in AUDIT_SPECS:
        record = {
            "schema_version": SCHEMA_VERSION,
            "kind": RECORD_KIND,
            "discovery_source": "phase8d_audit",
            **spec,
        }
        problems = validate_record(record, historical_ids=None)
        if problems:
            raise ValueError(f"invalid built record {record['audit_id']}: {problems}")
        records.append(record)
    return records


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_record(
    record: Mapping[str, Any], *, historical_ids: set[str] | None = None
) -> list[str]:
    """Validate one additive Phase-8D record (no historical rewrite)."""
    problems: list[str] = []
    if not isinstance(record, Mapping):
        return ["record is not an object"]
    missing = [field for field in REQUIRED_FIELDS if field not in record]
    if missing:
        return [f"missing fields {missing}"]
    if record.get("schema_version") != SCHEMA_VERSION:
        problems.append("schema_version mismatch")
    if record.get("kind") != RECORD_KIND:
        problems.append("kind mismatch")
    if record.get("discovery_source") != "phase8d_audit":
        problems.append("discovery_source must be phase8d_audit")
    audit_id = str(record.get("audit_id") or "")
    if audit_id not in AUDIT_IDS:
        problems.append(f"invalid audit_id {audit_id!r}")
    expected_gap_id = "GAP-8D-" + audit_id.replace("AUDIT-8D-", "AUDIT-")
    if record.get("gap_id") != expected_gap_id:
        problems.append(f"gap_id must be {expected_gap_id!r}")
    if record.get("category") not in CATEGORIES:
        problems.append(f"invalid category {record.get('category')!r}")
    for field in ("subcategory", "observed_failure", "existing_capability", "owner"):
        if not _nonempty(record.get(field)):
            problems.append(f"empty {field}")
    target = record.get("target")
    if not isinstance(target, Mapping) or not _nonempty(target.get("kind")):
        problems.append("target must be an object with kind")
    if record.get("severity") not in SEVERITIES:
        problems.append("invalid severity")
    if record.get("status") not in STATUSES:
        problems.append("invalid status")
    refs = record.get("evidence_refs")
    if not isinstance(refs, list) or not refs or not all(_nonempty(ref) for ref in refs):
        problems.append("evidence_refs must be non-empty strings")
    plan = record.get("proposed_experiment")
    if not isinstance(plan, Mapping) or plan.get("status") not in EXPERIMENT_STATUSES:
        problems.append("invalid proposed_experiment")
    elif plan.get("status") == "proposed":
        if not _nonempty(plan.get("experiment_id")):
            problems.append("proposed experiment missing id")
        steps = plan.get("steps")
        if not isinstance(steps, list) or not steps or not all(_nonempty(s) for s in steps):
            problems.append("proposed experiment missing steps")
    if not _nonempty(record.get("review_by")):
        problems.append("missing review_by")
    if record.get("verification_required") is not True:
        problems.append("verification_required must be true")
    if record.get("false_verified_risk") not in ("none", "low", "medium", "high", "critical"):
        problems.append("invalid false_verified_risk")
    if record.get("reproduction_status") not in REPRODUCTION_STATUSES:
        problems.append("invalid reproduction_status")
    if record.get("confidence") not in CONFIDENCES:
        problems.append("invalid confidence")
    deps = record.get("dependencies")
    if not isinstance(deps, list) or not all(_nonempty(dep) for dep in deps):
        problems.append("dependencies must be strings")
    lineage = record.get("lineage")
    if not isinstance(lineage, Mapping):
        problems.append("lineage must be an object")
    else:
        parents = lineage.get("derived_from")
        if not isinstance(parents, list) or not parents or not all(_nonempty(p) for p in parents):
            problems.append("lineage.derived_from must be non-empty")
        elif historical_ids is not None:
            missing_parents = sorted(set(parents) - historical_ids)
            if missing_parents:
                problems.append(f"unknown historical lineage parents {missing_parents}")
        extra = set(lineage) - set(LINEAGE_RELATIONS)
        if extra:
            problems.append(f"unknown lineage relations {sorted(extra)}")
    dims = record.get("capability_dimensions")
    if not isinstance(dims, list) or not dims or not all(dim in DIMENSIONS for dim in dims):
        problems.append("capability_dimensions must be valid D01-D20 refs")
    limitations = record.get("limitations")
    if not isinstance(limitations, list) or not all(_nonempty(item) for item in limitations):
        problems.append("limitations must be non-empty strings")
    return problems


def validate_registry(
    records: Iterable[Mapping[str, Any]],
    *,
    historical_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    record_list = list(records)
    ids = [str(record.get("gap_id") or "") for record in record_list]
    historical = set(historical_ids or [])
    violations: list[str] = []
    for record in record_list:
        violations.extend(
            f"{record.get('gap_id')}: {problem}"
            for problem in validate_record(record, historical_ids=historical or None)
        )
    if len(record_list) != 8:
        violations.append(f"expected 8 records, got {len(record_list)}")
    missing_audits = sorted(set(AUDIT_IDS) - {str(r.get("audit_id")) for r in record_list})
    if missing_audits:
        violations.append(f"missing audit ids {missing_audits}")
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    if duplicates:
        violations.append(f"duplicate gap ids {duplicates}")
    if any(str(record.get("status")) in {"candidate"} for record in record_list):
        violations.append("a Phase-8D audit finding cannot claim candidate/verified status")
    dimensions = sorted({dim for record in record_list
                        for dim in record.get("capability_dimensions") or []})
    missing_8d_dims = sorted({"D02", "D09", "D10"} - set(dimensions))
    if missing_8d_dims:
        violations.append(f"registry does not cover Phase-8D dimensions {missing_8d_dims}")
    return {
        "ok": not violations,
        "violations": violations,
        "record_count": len(record_list),
        "audit_ids": [str(record.get("audit_id")) for record in record_list],
        "unique_gap_ids": len(set(ids)),
        "dimensions": dimensions,
        "historical_ids_checked": len(historical),
        "auto_promotion": False,
        "historical_registry_rewritten": False,
    }


def historical_lineage_ids(records: Iterable[Mapping[str, Any]]) -> list[str]:
    """Return sorted parent ids used by the additive records (for validation)."""
    parents: set[str] = set()
    for record in records:
        lineage = record.get("lineage") or {}
        parents.update(str(item) for item in (lineage.get("derived_from") or []))
    return sorted(parents)
