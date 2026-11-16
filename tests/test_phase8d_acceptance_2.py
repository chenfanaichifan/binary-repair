"""Tests for additive Acceptance 2.0 L0-L7 and mutation audit."""
from __future__ import annotations

import copy
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for entry in (ROOT, SCRIPTS):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import audit_acceptance_2 as audit  # noqa: E402
from app.services import acceptance_2 as a2  # noqa: E402

ARTIFACT = ROOT / "artifacts" / "phase8d-acceptance-2-2026-11-17"


@pytest.fixture(scope="module")
def report() -> dict:
    return audit.build_artifact()


@pytest.fixture(scope="module")
def cases() -> list[dict]:
    return audit.build_cases()


def test_registry_has_eight_layers_and_versioned_rules() -> None:
    assert [layer["id"] for layer in a2.LAYER_SPECS] == [
        f"L{index}" for index in range(8)
    ]
    assert a2.REGISTRY_VERSION == "2.0.0"
    assert len(a2.RULE_SPECS) >= 24
    assert len({rule["id"] for rule in a2.RULE_SPECS}) == len(a2.RULE_SPECS)
    assert a2.registry_digest() == a2.CANONICAL_REGISTRY_SHA256
    registry = a2.build_registry()
    assert registry["digest"] == a2.CANONICAL_REGISTRY_SHA256
    assert len(registry["layers"]) == 8


def test_all_declared_cases_match_and_no_false_accept_or_reject(
        cases: list[dict], report: dict) -> None:
    assert len(cases) >= 18
    assert report["case_count"] == len(cases)
    assert report["matched"] == len(cases)
    assert report["false_accept_cases"] == []
    assert report["false_reject_cases"] == []
    assert report["summary"]["ok"] is True


def test_positive_new_layout_candidates_are_verified(cases: list[dict]) -> None:
    positives = [case for case in cases if case["expected_decision"] == "verified"]
    assert any(case["case_id"] == "positive-new-layout" for case in positives)
    assert any(case["case_id"] == "positive-new-layout-cave" for case in positives)
    for case in positives:
        result = a2.evaluate(case)
        assert result["verified"] is True, (case["case_id"], result["reasons"])
        assert all(row["status"] == "passed" for row in result["rules"])
        assert len(result["layers"]) == 8


def test_not_run_inconclusive_and_analysis_only_are_never_promoted(
        cases: list[dict]) -> None:
    by_id = {case["case_id"]: case for case in cases}
    for case_id, expected in (
        ("analysis-only-no-candidate", "analysis_only"),
        ("not-run-oracle-unknown", "not_run"),
        ("inconclusive-conflicting-evidence", "inconclusive"),
    ):
        result = a2.evaluate(by_id[case_id])
        assert result["decision"] == expected, result
        assert result["verified"] is False


def test_invalid_plausible_candidates_are_rejected(cases: list[dict]) -> None:
    by_id = {case["case_id"]: case for case in cases}
    invalid = [case for case in cases if case["expected_decision"] == "rejected"]
    assert len(invalid) >= 8
    for case in invalid:
        result = a2.evaluate(case)
        assert result["verified"] is False, (case["case_id"], result)
        assert result["failed_rules"], case["case_id"]
    assert "L2.patch_plan" in a2.evaluate(by_id["invalid-no-plan"])["failed_rules"]
    assert "L1.scope_policy" in a2.evaluate(
        by_id["invalid-scope-inflation"])["failed_rules"]
    assert "L4.independent_oracle" in a2.evaluate(
        by_id["invalid-generator-verdict"])["failed_rules"]
    assert "L3.abi_blocks" in a2.evaluate(
        by_id["invalid-abi-missing"])["failed_rules"]
    assert "L7.no_state_promotion" in a2.evaluate(
        by_id["invalid-not-run-verified"])["failed_rules"]
    assert "L7.no_state_promotion" in a2.evaluate(
        by_id["invalid-analysis-only-verified"])["failed_rules"]


def test_rule_mutation_is_detected_by_registry_integrity(cases: list[dict]) -> None:
    base = next(case for case in cases
                if case["case_id"] == "positive-new-layout")
    mutated = [copy.deepcopy(dict(rule)) for rule in a2.RULE_SPECS]
    next(rule for rule in mutated if rule["id"] == "L2.patch_plan")[
        "required"] = False
    result = a2.evaluate(base, registry=mutated)
    assert result["verified"] is False
    assert result["decision"] == "rejected"
    assert "L7.registry_integrity" in result["failed_rules"]
    assert a2.registry_digest(mutated) != a2.CANONICAL_REGISTRY_SHA256


def test_mutation_campaign_detects_every_family_without_false_accept(
        cases: list[dict]) -> None:
    base = next(case for case in cases
                if case["case_id"] == "positive-new-layout")
    mutation = a2.run_mutations(base)
    assert mutation["total"] == len(a2.MUTATION_SPECS) == 14
    assert mutation["detected"] == mutation["total"]
    assert mutation["detection_rate"] == 1.0
    assert mutation["false_accepts"] == 0
    assert set(mutation["by_family"]) == {
        "rule", "evidence", "scope", "oracle", "layout", "regression", "state",
    }
    for row in mutation["mutations"]:
        assert row["detected"] is True, row
        assert row["false_accept"] is False, row
        assert row["expected_rule"] in row["detected_rules"], row


def test_specific_mutations_fail_closed(cases: list[dict]) -> None:
    base = next(case for case in cases
                if case["case_id"] == "positive-new-layout")
    cases_by_mutation = {
        "M-evidence-refs-missing": "L7.evidence_refs",
        "M-evidence-hash-tampered": "L7.evidence_refs",
        "M-scope-inflation": "L1.scope_policy",
        "M-oracle-not-run": "L4.oracle_executed",
        "M-oracle-self-verdict": "L4.independent_oracle",
        "M-not-run-verified": "L7.no_state_promotion",
        "M-analysis-only-verified": "L7.no_state_promotion",
        "M-layout-no-plan": "L2.patch_plan",
        "M-abi-missing": "L3.abi_blocks",
    }
    for mutation_id, expected_rule in cases_by_mutation.items():
        spec = next(item for item in a2.MUTATION_SPECS
                    if item["id"] == mutation_id)
        assert spec["expected_rule"] == expected_rule
    for row in a2.run_mutations(base)["mutations"]:
        result = row["decision"]
        assert result != "verified", row
        if row["mutation_id"] in cases_by_mutation:
            assert row["detected"] is True, row


def test_historical_replay_is_not_upgraded(cases: list[dict]) -> None:
    base = next(case for case in cases
                if case["case_id"] == "positive-new-layout")
    replay = a2.replay_historical(base, registry_version="1.0.0")
    assert replay["decision"] in {"not_run", "rejected"}
    assert replay["verified"] is False
    assert replay["upgraded"] is False
    assert "historical" in replay["historical_note"]
    assert replay["reasons"]


def test_report_contains_honest_false_reject_gaps(report: dict) -> None:
    gaps = report["false_reject_gaps"]
    assert len(gaps) >= 2
    assert any("ABI" in gap["reason"] for gap in gaps)
    for gap in gaps:
        assert gap["observed"] != "verified"
    assert report["summary"]["false_rejects"] == 0
    assert report["summary"]["no_false_promotion"] is True


def test_artifact_is_deterministic_and_schema_valid(report: dict) -> None:
    second = audit.build_artifact()
    assert report == second
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(
        (ROOT / "contracts" / "acceptance-2.schema.json").read_text())
    jsonschema.validate(report, schema)
    assert audit.check_files() == []


def test_artifact_tamper_is_detected(tmp_path: Path) -> None:
    target = tmp_path / "artifact"
    shutil.copytree(ARTIFACT, target)
    report = json.loads((target / "report.json").read_text())
    report["summary"]["false_accepts"] = 7
    (target / "report.json").write_text(json.dumps(report) + "\n")
    assert audit.check_files(target)


def test_audit_script_is_offline_and_additive() -> None:
    service = (ROOT / "app/services/acceptance_2.py").read_text().lower()
    script = (ROOT / "scripts/audit_acceptance_2.py").read_text().lower()
    for text in (service, script):
        assert "requests" not in text
        assert "openai" not in text
        assert "anthropic" not in text
        assert "urllib" not in text
    assert "am01-am28" in service
    assert "do not" in service or "does not" in service
