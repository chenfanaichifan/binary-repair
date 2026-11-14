#!/usr/bin/env python3
"""Meta-audit: measure the coverage audit's own detector recall and precision.

The audit is only trustworthy if its detectors detect real regressions and do
not invent gaps.  This tool builds the real static census, then:

* **recall scenarios** inject a known synthetic defect into a census fixture
  (dead sink class, removed gate check, unexercised strategy, manifest-route
  signature-token regression) and require the matching detector to report it;
* **precision scenarios** inject fabricated gap records into a synthetic audit
  document and require the coverage regression gate to reject them, and mutate
  semantically-irrelevant census fields to require that no *new* open gap
  appears (no false positives).

Output (deterministic, no network, reused by ``verify_coverage_gate.py``)::

    {"ok": bool, "passed": bool, "recall": float, "precision": float,
     "thresholds": {...}, "scenario_count": int, "violations": [...],
     "scenarios": [{"id", "kind", "expected_detected", "detected", "detail"}]}
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / "scripts"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

MIN_RECALL = 0.8
MIN_PRECISION = 1.0
MIN_SCENARIOS = 7


def _import_audit() -> Any:
    from app.services import coverage_audit
    return coverage_audit


def _run_detector(audit_module: Any, name: str,
                  ctx: dict[str, Any]) -> list[dict[str, Any]]:
    detectors = dict(audit_module.DETECTORS)
    detector = detectors.get(name)
    if detector is None:
        return []
    try:
        return detector(ctx)
    except Exception as exc:  # noqa: BLE001 - recorded as a meta-audit failure
        return [{
            "gap_id": f"GM-meta-detector-error::{name}",
            "status": "open",
            "category": "gate_mismatch",
            "severity": "medium",
            "symptom": f"{type(exc).__name__}: {exc}",
            "evidence": [],
        }]


def _run_all_detectors(audit_module: Any,
                       ctx: dict[str, Any]) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    for name, _detector in audit_module.DETECTORS:
        gaps.extend(_run_detector(audit_module, name, ctx))
    return audit_module._merge_gaps(gaps)


def _gap_map(gaps: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(gap.get("gap_id")): gap for gap in gaps}


def _scenario(scenario_id: str, kind: str, expected: bool, detected: bool,
              detail: str) -> dict[str, Any]:
    return {
        "id": scenario_id,
        "kind": kind,
        "expected_detected": expected,
        "detected": detected,
        "detail": detail,
    }


def _recall_dead_sink(audit_module: Any,
                      ctx: dict[str, Any]) -> dict[str, Any]:
    mutated = copy.deepcopy(ctx)
    fake_kind = "audit_probe_fake_dead_sink"
    mutated["matrix"]["sink_classes"][fake_kind] = {"strategy": "guard"}
    cells = mutated["matrix"]["cells"]
    if cells:
        cells[0].setdefault("sink_classes", []).append(fake_kind)
    gaps = _run_detector(audit_module, "engine_sink_classes", mutated)
    expected_id = f"EG-sink-class-dead::{fake_kind}"
    detected = expected_id in _gap_map(gaps) and _gap_map(gaps)[expected_id]["status"] == "open"
    return _scenario("dead_sink_class", "recall", True, detected,
                     f"expected open {expected_id}")


def _recall_gate_mismatch(audit_module: Any,
                          ctx: dict[str, Any]) -> dict[str, Any]:
    mutated = copy.deepcopy(ctx)
    scenarios = _as_dict(_as_dict(mutated.get("gates")).get("unified")).get(
        "scenarios") or {}
    rewritten = dict(scenarios)
    tampered = copy.deepcopy(_as_dict(rewritten.get("rewrite_tampered")))
    tampered["checks"] = [
        check for check in _as_list(tampered.get("checks"))
        if not str(_as_dict(check).get("id", "")).startswith(
            ("patch.rewrite", "patch.capacity"))
    ]
    rewritten["rewrite_tampered"] = tampered
    _as_dict(mutated["gates"]["unified"])["scenarios"] = rewritten
    gaps = _run_detector(audit_module, "gate_rewrite", mutated)
    gap = _gap_map(gaps).get("GM-gate-rewrite", {})
    detected = gap.get("status") == "open"
    return _scenario("gate_mismatch_rewrite_check_removed", "recall", True,
                     detected,
                     "removed the failed patch.rewrite check from the tampered "
                     "scenario; GM-gate-rewrite must reopen")


def _recall_unexercised_strategy(audit_module: Any,
                                 ctx: dict[str, Any]) -> dict[str, Any]:
    mutated = copy.deepcopy(ctx)
    fake_strategy = "audit_probe_fake_strategy"
    mutated["matrix"].setdefault("strategies", []).append(fake_strategy)
    mutated["_include_probes"] = True
    mutated["probes"] = {"fixtures": [], "analysis": [], "strategies": [],
                         "capacity": [], "targets": [], "safe_default": [],
                         "skipped_budget": 0}
    gaps = _run_detector(audit_module, "matrix_coverage", mutated)
    expected_id = f"MM-strategy-unexercised::{fake_strategy}"
    gap = _gap_map(gaps).get(expected_id, {})
    detected = gap.get("status") == "open"
    return _scenario("unexercised_strategy", "recall", True, detected,
                     f"expected open {expected_id}")


def _manifest_route_scenarios(audit_module: Any) -> list[dict[str, Any]]:
    signature_only = """
def repair_any(
    data: bytes,
    *,
    poc_manifest: dict[str, Any] | None = None,
    verify: bool = True,
) -> RepairOutcome:
    container = detect_container(data)
    from app.services.binary_repair_engine import repair_elf
    patched, raw = repair_elf(data)
    report = _from_elf_legacy(container, data, patched, raw, verify=verify,
                              external_poc=poc_manifest)
    return report


def _from_elf_legacy(container, data, patched, raw, *, verify,
                     external_poc=None):
    if external_poc is not None:
        report.limitations.append("cannot consume it")
    return report


def _select_runtime(data, container, sink):
    return None
"""
    guarded = signature_only.replace(
        "    from app.services.binary_repair_engine import repair_elf",
        "    if poc_manifest is not None:\n"
        "        return _attempt_capacity(data, container,\n"
        "                                 poc_manifest=poc_manifest)\n"
        "    from app.services.binary_repair_engine import repair_elf",
    )
    signature_evidence = audit_module._manifest_route_evidence(signature_only)
    guarded_evidence = audit_module._manifest_route_evidence(guarded)
    return [
        _scenario(
            "manifest_route_signature_token_is_not_a_route", "recall", True,
            signature_evidence["routed"] is False,
            f"signature-only source routed={signature_evidence['routed']}; "
            "a parameter declaration must not count as a manifest guard",
        ),
        _scenario(
            "manifest_route_real_guard_is_measured", "recall", True,
            guarded_evidence["routed"] is True,
            f"guarded source routed={guarded_evidence['routed']} helpers="
            f"{guarded_evidence['route_helpers']}",
        ),
    ]


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _gate_fake_gap_scenarios(audit_module: Any,
                             ctx: dict[str, Any]) -> list[dict[str, Any]]:
    from verify_coverage_gate import evaluate, load_claims

    claims, _claim_errors = load_claims()
    doc_text = (ROOT / "docs" / "acceptance"
                / "non-goals-2026-11-14.md").read_text(encoding="utf-8")
    baseline_gaps = _run_all_detectors(audit_module, ctx)
    baseline_open = sorted(
        str(gap.get("gap_id")) for gap in baseline_gaps
        if gap.get("status") == "open")
    fake_open = baseline_gaps + [{
        "gap_id": "EG-audit_fake_open_gap",
        "category": "engine_gap",
        "severity": "medium",
        "status": "open",
        "symptom": "fabricated",
        "evidence": [],
    }]
    open_result = evaluate(
        {"gaps": fake_open, "mode": "static"}, claims, doc_text,
        allowed_open=(), local=False)
    fake_open_rejected = any(
        "ALLOWED_OPEN" in violation
        for violation in open_result.get("violations", []))
    fake_non_goal = baseline_gaps + [{
        "gap_id": "NG-audit_fake_non_goal",
        "category": "non_goal",
        "severity": "info",
        "status": "non_goal",
        "symptom": "fabricated",
        "evidence": [],
    }]
    non_goal_result = evaluate(
        {"gaps": fake_non_goal, "mode": "static"}, claims, doc_text,
        allowed_open=(), local=False)
    fake_non_goal_rejected = any(
        "not mapped" in violation
        for violation in non_goal_result.get("violations", []))
    return [
        _scenario("gate_rejects_fabricated_open_gap", "precision", True,
                  fake_open_rejected,
                  "a fabricated open gap id cannot pass the coverage gate"),
        _scenario("gate_rejects_unmapped_fake_non_goal", "precision", True,
                  fake_non_goal_rejected,
                  "a fabricated non_goal id cannot pass without a claims/doc "
                  "mapping"),
    ]


def _precision_benign_mutations(audit_module: Any,
                                ctx: dict[str, Any]) -> dict[str, Any]:
    baseline = _run_all_detectors(audit_module, ctx)
    baseline_open = {str(gap.get("gap_id")) for gap in baseline
                     if gap.get("status") == "open"}
    mutated = copy.deepcopy(ctx)
    mutated["matrix"]["cells"] = list(reversed(mutated["matrix"]["cells"]))
    mutated["matrix"]["fixtures"] = list(reversed(
        _as_list(mutated["matrix"].get("fixtures"))))
    mutated["docs"]["README.md"] = str(mutated["docs"].get("README.md", "")) + " "
    mutated_gaps = _run_all_detectors(audit_module, mutated)
    mutated_open = {str(gap.get("gap_id")) for gap in mutated_gaps
                    if gap.get("status") == "open"}
    spurious = sorted(mutated_open - baseline_open)
    return _scenario(
        "benign_census_mutation_has_no_new_open_gap", "precision", True,
        not spurious,
        f"spurious new open gaps={spurious}" if spurious else "no new open gaps",
    )


def _precision_no_detector_errors(audit_module: Any,
                                  ctx: dict[str, Any]) -> dict[str, Any]:
    gaps = _run_all_detectors(audit_module, ctx)
    errors = sorted(str(gap.get("gap_id")) for gap in gaps
                    if str(gap.get("gap_id")).startswith("GM-detector-error::"))
    return _scenario("no_detector_errors_on_clean_census", "precision", True,
                     not errors, f"detector errors={errors}")


def run_meta_audit(*, include_probes: bool = False) -> dict[str, Any]:
    """Run the meta-audit and return the deterministic report dict."""
    audit_module = _import_audit()
    ctx = audit_module.build_census_context(include_probes=include_probes)
    scenarios: list[dict[str, Any]] = []
    scenarios.append(_recall_dead_sink(audit_module, ctx))
    scenarios.append(_recall_gate_mismatch(audit_module, ctx))
    scenarios.append(_recall_unexercised_strategy(audit_module, ctx))
    scenarios.extend(_manifest_route_scenarios(audit_module))
    scenarios.extend(_gate_fake_gap_scenarios(audit_module, ctx))
    scenarios.append(_precision_benign_mutations(audit_module, ctx))
    scenarios.append(_precision_no_detector_errors(audit_module, ctx))
    recall_scenarios = [item for item in scenarios if item["kind"] == "recall"]
    precision_scenarios = [item for item in scenarios if item["kind"] == "precision"]
    recall = (sum(1 for item in recall_scenarios if item["detected"])
              / len(recall_scenarios)) if recall_scenarios else 0.0
    precision = (sum(1 for item in precision_scenarios if item["detected"])
                 / len(precision_scenarios)) if precision_scenarios else 0.0
    violations = [
        f"{item['id']}: expected_detected={item['expected_detected']} "
        f"detected={item['detected']} ({item['detail']})"
        for item in scenarios
        if item["detected"] != item["expected_detected"]
    ]
    if recall < MIN_RECALL:
        violations.append(
            f"recall {recall:.2f} below threshold {MIN_RECALL:.2f}")
    if precision < MIN_PRECISION:
        violations.append(
            f"precision {precision:.2f} below threshold {MIN_PRECISION:.2f}")
    if len(scenarios) < MIN_SCENARIOS:
        violations.append(
            f"only {len(scenarios)} meta-audit scenarios (< {MIN_SCENARIOS})")
    return {
        "schema_version": 1,
        "ok": not violations,
        "passed": not violations,
        "violations": violations,
        "recall": round(recall, 4),
        "precision": round(precision, 4),
        "thresholds": {"min_recall": MIN_RECALL,
                       "min_precision": MIN_PRECISION,
                       "min_scenarios": MIN_SCENARIOS},
        "scenario_count": len(scenarios),
        "scenarios": scenarios,
        "mode": "full" if include_probes else "static",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="meta-audit: measure detector recall/precision")
    parser.add_argument("--json", action="store_true",
                        help="print the report as JSON")
    parser.add_argument("--out", type=Path, default=None,
                        help="write the JSON report to this path")
    parser.add_argument("--probes", action="store_true",
                        help="include dynamic probes in the census context")
    args = parser.parse_args(argv)
    report = run_meta_audit(include_probes=bool(args.probes))
    if args.out is not None:
        args.out.write_text(
            json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False)
            + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(
            "meta-audit: ok={ok} recall={recall} precision={precision} "
            "scenarios={count} violations={violations}".format(
                ok=report["ok"], recall=report["recall"],
                precision=report["precision"], count=report["scenario_count"],
                violations=len(report["violations"]),
            )
        )
        for violation in report["violations"]:
            print(f"META-VIOLATION: {violation}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
