"""Tests for the meta-audit (detector recall/precision) tool."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import meta_audit  # noqa: E402


def _report() -> dict:
    return meta_audit.run_meta_audit(include_probes=False)


def test_meta_audit_passes_with_expected_thresholds() -> None:
    report = _report()
    assert report["ok"], report["violations"]
    assert report["recall"] >= report["thresholds"]["min_recall"]
    assert report["precision"] >= report["thresholds"]["min_precision"]
    assert report["scenario_count"] >= report["thresholds"]["min_scenarios"]
    assert report["violations"] == []


def test_meta_audit_scenarios_cover_recall_and_precision() -> None:
    report = _report()
    scenarios = {item["id"]: item for item in report["scenarios"]}
    recall_ids = {
        "dead_sink_class",
        "gate_mismatch_rewrite_check_removed",
        "target_scope_gate_check_removed",
        "rewrite_actions_not_rederived",
        "provider_identity_mismatch_recorded_non_verified",
        "stale_committed_audit_artifacts",
        "invariant_download_on_inconclusive",
        "fabricated_capability_without_reason",
        "unexercised_strategy",
        "release_evidence_sha_or_check_mismatch",
        "evidence_provenance_missing",
        "local_gate_claimed_as_ci_evidence",
        "unregistered_sink_detected_by_methodology",
        "unregistered_strategy_detected_by_methodology",
        "unregistered_platform_detected_by_methodology",
        "ci_evidence_missing_or_misclaimed",
        "provenance_incomplete",
        "evidence_branch_drift",
        "acceptance_served_model_only_masquerade",
        "acceptance_whole_program_masquerade",
        "acceptance_oracle_self_report_masquerade",
        "benchmark_version_mismatch",
    }
    precision_ids = {
        "gate_rejects_fabricated_open_gap",
        "gate_rejects_unmapped_fake_non_goal",
        "benign_census_mutation_has_no_new_open_gap",
        "no_detector_errors_on_clean_census",
    }
    for scenario_id in recall_ids | precision_ids:
        assert scenario_id in scenarios, scenario_id
        assert scenarios[scenario_id]["detected"] is True, scenarios[scenario_id]
    assert scenarios["dead_sink_class"]["expected_detected"] is True


def test_manifest_route_signature_token_regression_is_covered() -> None:
    report = _report()
    scenarios = {item["id"]: item for item in report["scenarios"]}
    signature = scenarios["manifest_route_signature_token_is_not_a_route"]
    guarded = scenarios["manifest_route_real_guard_is_measured"]
    assert signature["detected"] is True
    assert guarded["detected"] is True
    assert "routed=False" in signature["detail"]
    assert "routed=True" in guarded["detail"]


def test_meta_audit_is_deterministic() -> None:
    first = _report()
    second = _report()
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_meta_audit_cli_json_contract(tmp_path: Path) -> None:
    out_path = tmp_path / "meta.json"
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "meta_audit.py"), "--json",
         "--out", str(out_path)],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["passed"] is True
    assert isinstance(payload["recall"], float)
    assert isinstance(payload["precision"], float)
    assert out_path.is_file()
    assert json.loads(out_path.read_text(encoding="utf-8"))["ok"] is True


def test_meta_audit_has_at_least_twelve_injected_scenarios() -> None:
    report = _report()
    assert report["scenario_count"] >= 26
    assert report["thresholds"]["min_scenarios"] >= 26
    scenario_ids = {item["id"] for item in report["scenarios"]}
    for required in (
        "target_scope_gate_check_removed",
        "rewrite_actions_not_rederived",
        "provider_identity_mismatch_recorded_non_verified",
        "stale_committed_audit_artifacts",
        "invariant_download_on_inconclusive",
        "fabricated_capability_without_reason",
        "release_evidence_sha_or_check_mismatch",
        "evidence_provenance_missing",
        "local_gate_claimed_as_ci_evidence",
        "unregistered_sink_detected_by_methodology",
        "unregistered_strategy_detected_by_methodology",
        "unregistered_platform_detected_by_methodology",
        "ci_evidence_missing_or_misclaimed",
        "provenance_incomplete",
        "evidence_branch_drift",
        "acceptance_served_model_only_masquerade",
        "acceptance_whole_program_masquerade",
    ):
        assert required in scenario_ids, required


def test_meta_audit_cli_reports_full_scenario_count() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "meta_audit.py"), "--json"],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["scenario_count"] >= 26
    assert payload["ok"] is True
    assert payload["recall"] == 1.0
    assert payload["precision"] == 1.0
