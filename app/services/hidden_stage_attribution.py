"""D05: private stage attribution for hidden no-candidate outcomes.

The Phase-8C hidden lane records only aggregate counts.  That is honest but
leaves a gap: a hidden runtime sample with no candidate is not attributed to a
pipeline stage.  This module derives a deterministic, private diagnostic from
the already-executed ``repair_any`` report; it never re-runs the engine, never
uses the network/AI, and never puts opaque sample ids, paths, bytes or raw
report strings into the public aggregate.

The taxonomy and stage list are intentionally finite.  A signal that is not
observable is ``unknown``; a stage downstream of a failed stage is
``not_reached``.  We do not infer a stage from a name or fabricate a pass.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any, Mapping

STAGES = (
    "parsing",
    "function_cfg_recovery",
    "detection",
    "root_cause",
    "localization",
    "repairability",
    "strategy_selection",
    "plan_validation",
    "candidate_generation",
    "pre_verification",
)

#: Closed taxonomy for a runtime sample that produced no candidate.  The
#: private diagnostics may use ``analysis_only`` for an analysis-only sample,
#: but that value is never included in the public runtime no-candidate counts.
NO_CANDIDATE_REASONS = (
    "not_vulnerable",
    "unsupported_binary_format",
    "unsupported_architecture",
    "decode_incomplete",
    "function_boundary_unknown",
    "control_flow_unknown",
    "detection_missed",
    "root_cause_unknown",
    "localization_incomplete",
    "alias_unknown",
    "path_condition_unresolved",
    "no_repair_strategy",
    "repair_plan_rejected",
    "abi_unknown",
    "no_safe_code_space",
    "relocation_unsupported",
    "patch_generation_failed",
    "resource_budget_exhausted",
    "environment_unavailable",
    "other",
    "inconclusive",
)

PUBLIC_STAGE_STATUSES = (
    "observed",
    "not_observed",
    "not_reached",
    "not_applicable",
    "unknown",
    "failed",
)

_PRIVATE_ONLY_REASON = "analysis_only"

_SAFE_DETAIL_RE = re.compile(r"^[a-z0-9_.:-]{0,80}$")


def _field(report: Any, name: str, default: Any = None) -> Any:
    if report is None:
        return default
    if isinstance(report, Mapping):
        return report.get(name, default)
    return getattr(report, name, default)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_int(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _safe_detail(value: Any, default: str = "unavailable") -> str:
    """Keep private details short and free of paths/bytes/identifiers."""

    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9_.:-]+", "_", text).strip("_")
    if not text or len(text) > 80 or not _SAFE_DETAIL_RE.match(text):
        return default
    return text


def _report_limitations(report: Any) -> list[str]:
    values = _field(report, "limitations", [])
    if not isinstance(values, list):
        return []
    return [str(item).lower() for item in values if str(item).strip()]


def _signal_from_limitations(report: Any) -> str | None:
    """Map measured engine limitations to a specific taxonomy reason."""

    text = " ".join(_report_limitations(report)).lower()
    if not text:
        return None
    if "timeout" in text or "resource budget" in text or "budget exhausted" in text:
        return "resource_budget_exhausted"
    if "relocation" in text:
        return "relocation_unsupported"
    if "code cave" in text or "no safe code space" in text or "no patchable sink" in text:
        return "no_safe_code_space"
    if "alias" in text or "points-to" in text:
        return "alias_unknown"
    if "path condition" in text or "path-sensitive" in text:
        return "path_condition_unresolved"
    if "abi" in text:
        return "abi_unknown"
    if "decode" in text or "disassembly" in text or "instruction boundary" in text:
        return "decode_incomplete"
    return None


def _stage(
    name: str,
    status: str,
    detail: str,
    *,
    signal: bool | None = None,
    count: int | None = None,
) -> dict[str, Any]:
    if status not in PUBLIC_STAGE_STATUSES:
        status = "unknown"
    payload: dict[str, Any] = {
        "stage": name,
        "status": status,
        "detail": _safe_detail(detail, "unavailable"),
    }
    if signal is not None:
        payload["signal"] = bool(signal)
    if count is not None:
        payload["count"] = int(count)
    return payload


def _base_stages() -> dict[str, dict[str, Any]]:
    return {
        name: _stage(name, "not_reached", "prior_stage_blocked")
        for name in STAGES
    }


def attribute_hidden_execution(sample: Mapping[str, Any],
                               execution: Mapping[str, Any]) -> dict[str, Any]:
    """Return one private stage diagnostic for an executed hidden sample.

    ``execution`` is exactly what ``execute_sample`` returns, including the
    classified ``repair.report`` object.  The function never reads binary
    bytes or invokes the engine.
    """

    result = execution.get("result") or {}
    report = (result.get("repair") or {}).get("report") if isinstance(
        result.get("repair"), Mapping) else None
    container = _mapping(_field(report, "container", {}))
    matrix = _mapping(_field(report, "matrix", {}))
    universal = _mapping(_field(report, "universal", {}))
    findings = _field(report, "findings", []) or []
    actions = _field(report, "actions", []) or []
    patch_plan = _field(report, "patch_plan")
    verification = _mapping(_field(report, "verification", {}))
    strategy = result.get("strategy") or _field(report, "strategy")
    candidate = result.get("candidate")
    analysis_only = str(sample.get("expected_scope")) == "analysis_only" or (
        str(sample.get("target", {}).get("kind")) == "analysis_only"
    )
    stages = _base_stages()
    evidence: dict[str, Any] = {
        "finding_count": len(findings) if isinstance(findings, list) else None,
        "action_count": len(actions) if isinstance(actions, list) else None,
        "has_patch_plan": isinstance(patch_plan, Mapping),
        "has_verification": bool(verification),
        "engine_reports_detected": universal.get("detected"),
        "engine_reports_repairable": universal.get("repairable"),
        "target_scope_present": bool(universal.get("target_scope")),
    }

    # 1. Parsing.
    if container.get("format") and container.get("arch") and matrix.get("cell"):
        stages["parsing"] = _stage(
            "parsing", "observed", "container_and_matrix_present", signal=True)
    elif report is not None:
        stages["parsing"] = _stage(
            "parsing", "not_observed", "container_or_matrix_missing", signal=False)
    else:
        stages["parsing"] = _stage(
            "parsing", "unknown", "no_report_available", signal=None)

    # 2. Function/CFG recovery.
    target_scope = universal.get("target_scope")
    if analysis_only:
        stages["function_cfg_recovery"] = _stage(
            "function_cfg_recovery", "not_applicable",
            "analysis_only_no_target_scope")
    elif isinstance(target_scope, Mapping) and target_scope.get("va") is not None:
        stages["function_cfg_recovery"] = _stage(
            "function_cfg_recovery", "observed", "target_scope_present",
            signal=True)
    elif report is not None:
        stages["function_cfg_recovery"] = _stage(
            "function_cfg_recovery", "not_observed", "target_scope_missing",
            signal=False)
    else:
        stages["function_cfg_recovery"] = _stage(
            "function_cfg_recovery", "unknown", "no_report_available")

    # 3. Detection.  ``universal.detected`` is an engine claim, not a finding;
    # only a finding or candidate is observed detection evidence.
    detected = result.get("detection") is True
    if analysis_only:
        stages["detection"] = _stage(
            "detection", "not_applicable", "analysis_only_no_runtime_detection")
    elif detected:
        stages["detection"] = _stage(
            "detection", "observed", "finding_or_candidate_present", signal=True)
    elif report is not None:
        stages["detection"] = _stage(
            "detection", "not_observed", "no_finding_or_candidate", signal=False)
    else:
        stages["detection"] = _stage(
            "detection", "unknown", "no_report_available")

    # 4. Root cause.
    if analysis_only:
        stages["root_cause"] = _stage(
            "root_cause", "not_applicable", "analysis_only_no_root_cause")
    elif result.get("root_cause") is True:
        stages["root_cause"] = _stage(
            "root_cause", "observed", "root_cause_matched", signal=True)
    elif result.get("root_cause") is False:
        stages["root_cause"] = _stage(
            "root_cause", "not_observed", "root_cause_not_matched", signal=False)
    else:
        stages["root_cause"] = _stage(
            "root_cause", "unknown", "root_cause_not_measured")

    # 5. Localization.
    if analysis_only:
        stages["localization"] = _stage(
            "localization", "not_applicable", "analysis_only_no_localization")
    elif result.get("localization") is True:
        stages["localization"] = _stage(
            "localization", "observed", "actions_within_target_scope", signal=True)
    elif result.get("localization") is False:
        stages["localization"] = _stage(
            "localization", "not_observed", "no_localized_action", signal=False)
    else:
        stages["localization"] = _stage(
            "localization", "unknown", "localization_not_measured")

    # 6. Repairability.  This is an engine claim; no candidate means we can
    # only observe the claim, not a successful repair.
    if analysis_only:
        stages["repairability"] = _stage(
            "repairability", "not_applicable", "analysis_only_no_repair")
    elif candidate is not None:
        stages["repairability"] = _stage(
            "repairability", "observed", "candidate_available", signal=True)
    elif universal.get("repairable") is True:
        stages["repairability"] = _stage(
            "repairability", "not_observed", "engine_claims_repairable_no_candidate",
            signal=False)
    elif universal.get("repairable") is False:
        stages["repairability"] = _stage(
            "repairability", "failed", "engine_reports_not_repairable", signal=False)
    else:
        stages["repairability"] = _stage(
            "repairability", "unknown", "repairability_not_measured")

    # 7. Strategy selection.
    strategy_text = str(strategy or "").strip().lower()
    if analysis_only:
        stages["strategy_selection"] = _stage(
            "strategy_selection", "not_applicable", "analysis_only_no_strategy")
    elif strategy_text and strategy_text not in {"none", "unsupported", "analysis_only"}:
        stages["strategy_selection"] = _stage(
            "strategy_selection", "observed", "strategy_selected", signal=True)
    elif report is not None:
        stages["strategy_selection"] = _stage(
            "strategy_selection", "not_observed", "no_strategy_selected",
            signal=False)
    else:
        stages["strategy_selection"] = _stage(
            "strategy_selection", "unknown", "no_report_available")

    # 8. Plan validation.
    if analysis_only:
        stages["plan_validation"] = _stage(
            "plan_validation", "not_applicable", "analysis_only_no_plan")
    elif isinstance(patch_plan, Mapping):
        stages["plan_validation"] = _stage(
            "plan_validation", "observed", "patch_plan_present", signal=True)
    elif verification:
        stages["plan_validation"] = _stage(
            "plan_validation", "failed", "verification_present_without_plan",
            signal=False)
    else:
        stages["plan_validation"] = _stage(
            "plan_validation", "not_reached", "strategy_not_selected")

    # 9. Candidate generation.
    if candidate is not None:
        stages["candidate_generation"] = _stage(
            "candidate_generation", "observed", "candidate_bytes_present",
            signal=True, count=1)
    elif analysis_only:
        stages["candidate_generation"] = _stage(
            "candidate_generation", "not_applicable",
            "analysis_only_no_candidate_expected")
    else:
        stages["candidate_generation"] = _stage(
            "candidate_generation", "not_observed", "candidate_absent",
            signal=False)

    # 10. Pre-verification / independent verification hook.
    if candidate is None:
        stages["pre_verification"] = _stage(
            "pre_verification", "not_reached", "candidate_absent")
    elif verification:
        stages["pre_verification"] = _stage(
            "pre_verification", "observed", "verification_evidence_present",
            signal=True)
    else:
        stages["pre_verification"] = _stage(
            "pre_verification", "not_observed", "verification_absent",
            signal=False)

    if not analysis_only:
        # A stage after the first unobserved/failed stage was never reached;
        # do not report a downstream "not observed" as if it were measured.
        blocked = False
        for name in STAGES:
            stage = stages[name]
            if blocked and stage["status"] not in {"not_applicable"}:
                stages[name] = _stage(name, "not_reached", "prior_stage_blocked")
                continue
            if stage["status"] in {"failed", "not_observed", "unknown"}:
                blocked = True

    first_stage, reason = _first_blocking_stage(
        sample, execution, stages, report, candidate, analysis_only)
    return {
        "opaque_sample_id": str(sample.get("sample_id") or ""),
        "expected_scope": str(sample.get("expected_scope") or ""),
        "format": str(sample.get("format") or ""),
        "arch": str(sample.get("arch") or ""),
        "candidate_produced": candidate is not None,
        "no_candidate_expected": analysis_only,
        "first_blocking_stage": first_stage,
        "no_candidate_reason": reason,
        "stages": stages,
        "evidence": evidence,
        "limitations": [
            "stage attribution is derived from the deterministic report only; "
            "it is not a proof of the missing semantic capability",
            "a not_reached stage does not prove the stage would fail if reached",
        ],
    }


def _first_blocking_stage(
    sample: Mapping[str, Any],
    execution: Mapping[str, Any],
    stages: Mapping[str, Mapping[str, Any]],
    report: Any,
    candidate: Any,
    analysis_only: bool,
) -> tuple[str, str]:
    if analysis_only:
        return "analysis_only", _PRIVATE_ONLY_REASON
    status = str((execution.get("result") or {}).get("status") or "")
    if status == "invalid":
        fmt = str(sample.get("format") or "").lower()
        if fmt not in {"elf", "macho", "pe"}:
            return "parsing", "unsupported_binary_format"
        if str(sample.get("arch") or "") not in {"x86_64", "i386", "arm64"}:
            return "parsing", "unsupported_architecture"
        return "parsing", "decode_incomplete"
    if status in {"blocked", "not_run"}:
        return "pre_verification", "environment_unavailable"
    if stages["parsing"]["status"] in {"failed", "not_observed"}:
        return "parsing", "decode_incomplete"
    if stages["function_cfg_recovery"]["status"] == "not_observed":
        target = sample.get("target") or {}
        if target.get("kind") in {"function", "symbol"}:
            return "function_cfg_recovery", "function_boundary_unknown"
        return "function_cfg_recovery", "control_flow_unknown"
    if stages["detection"]["status"] == "not_observed":
        return "detection", "detection_missed"
    if stages["root_cause"]["status"] == "not_observed":
        return "root_cause", "root_cause_unknown"
    if stages["localization"]["status"] == "not_observed":
        return "localization", "localization_incomplete"
    if stages["strategy_selection"]["status"] == "not_observed":
        limitation_reason = _signal_from_limitations(report)
        if limitation_reason:
            return "strategy_selection", limitation_reason
        return "strategy_selection", "no_repair_strategy"
    if stages["plan_validation"]["status"] in {"failed", "not_observed"}:
        limitation_reason = _signal_from_limitations(report)
        return "plan_validation", limitation_reason or "repair_plan_rejected"
    if candidate is None:
        limitation_reason = _signal_from_limitations(report)
        return "candidate_generation", (
            limitation_reason or "patch_generation_failed")
    if stages["pre_verification"]["status"] in {"not_observed", "not_reached"}:
        return "pre_verification", "inconclusive"
    return "other", "inconclusive"


def aggregate_stage_attribution(
    diagnostics: list[Mapping[str, Any]],
    *,
    sample_count: int | None = None,
    runtime_count: int | None = None,
    analysis_only_count: int | None = None,
) -> dict[str, Any]:
    """Build the public counts-only stage distribution (no sample identifiers)."""

    runtime = [
        item for item in diagnostics
        if item.get("no_candidate_expected") is not True
    ]
    analysis = [
        item for item in diagnostics
        if item.get("no_candidate_expected") is True
    ]
    no_candidate = [item for item in runtime if item.get("candidate_produced") is not True]
    candidate_count = len(runtime) - len(no_candidate)
    reason_counts: Counter[str] = Counter(
        str(item.get("no_candidate_reason") or "inconclusive")
        for item in no_candidate
    )
    stage_counts: Counter[str] = Counter(
        str(item.get("first_blocking_stage") or "other")
        for item in no_candidate
        if str(item.get("first_blocking_stage") or "") != "analysis_only"
    )
    stage_status_counts: dict[str, dict[str, int]] = {}
    for name in STAGES:
        counts: Counter[str] = Counter()
        for item in runtime:
            stage = (item.get("stages") or {}).get(name) or {}
            counts[str(stage.get("status") or "unknown")] += 1
        stage_status_counts[name] = dict(sorted(counts.items()))
    return {
        "sample_count": sample_count if sample_count is not None else len(diagnostics),
        "runtime_count": runtime_count if runtime_count is not None else len(runtime),
        "analysis_only_count": (
            analysis_only_count if analysis_only_count is not None else len(analysis)
        ),
        "runtime_no_candidate_count": len(no_candidate),
        "runtime_candidate_count": candidate_count,
        "no_candidate_reason_counts": dict(sorted(reason_counts.items())),
        "first_blocking_stage_counts": dict(sorted(stage_counts.items())),
        "stage_status_counts": stage_status_counts,
        "analysis_only_no_candidate_expected": len(analysis),
        "limitations": [
            "public stage attribution contains counts and distribution only: no "
            "hidden sample ids, paths, bytes, hashes or raw report strings",
            "stage attribution is derived from deterministic engine reports; "
            "not_reached stages are not proof that the stage would fail",
            "analysis-only samples are excluded from the runtime no-candidate "
            "reason distribution and reported by count only",
        ],
    }


def build_private_report(
    diagnostics: list[Mapping[str, Any]],
    *,
    benchmark_id: str,
    commitment_sha256: str,
    public_manifest_sha256: str,
    hidden_manifest_sha256: str,
    generated_at: str,
) -> dict[str, Any]:
    """Private detailed report; never written to the public artifact path."""

    return {
        "schema_version": 1,
        "kind": "phase8d_hidden_stage_attribution_private",
        "benchmark_id": benchmark_id,
        "commitment_sha256": commitment_sha256,
        "public_manifest_sha256": public_manifest_sha256,
        "hidden_manifest_sha256": hidden_manifest_sha256,
        "generated_at": generated_at,
        "sample_count": len(diagnostics),
        "runtime_count": sum(
            1 for item in diagnostics
            if item.get("no_candidate_expected") is not True),
        "analysis_only_count": sum(
            1 for item in diagnostics
            if item.get("no_candidate_expected") is True),
        "diagnostics": [dict(item) for item in diagnostics],
        "limitations": [
            "private detailed diagnostics contain opaque sample ids but no "
            "binary bytes or case paths; retain privately",
            "attribution is derived from deterministic reports and is not a "
            "capability proof",
        ],
    }
