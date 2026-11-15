"""Tests for the acceptance-model matcher, registry and audit matrix."""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for entry in (ROOT, SCRIPTS):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import audit_acceptance_models as audit  # noqa: E402
from app.services.acceptance_models import (  # noqa: E402
    ACCEPTANCE_DIMENSIONS,
    MISMATCH_BY_ID,
    MISMATCH_IDS,
    MISMATCH_RULES,
    AcceptanceModelMatcher,
)

ARTIFACT_DIR = ROOT / "artifacts" / "acceptance-model-audit-2026-11-16"


@pytest.fixture(scope="module")
def cases() -> list[dict]:
    return audit.build_cases()


@pytest.fixture(scope="module")
def report(cases: list[dict]) -> dict:
    return audit.evaluate_cases(cases)


def _match(case: dict) -> dict:
    return AcceptanceModelMatcher.match(case["task"], case["acceptance"])


def test_registry_dimensions_and_mismatch_classes_are_complete() -> None:
    dimension_ids = [dim["id"] for dim in ACCEPTANCE_DIMENSIONS]
    assert dimension_ids == ["A01", "A02", "A03", "A04", "A05", "A06", "A07",
                             "A08"]
    assert len(set(dimension_ids)) == len(dimension_ids) == 8
    mismatch_ids = [rule["id"] for rule in MISMATCH_RULES]
    assert mismatch_ids == [f"AM{index:02d}" for index in range(1, 29)]
    assert len(set(mismatch_ids)) == len(mismatch_ids) == 28
    mapped = {mismatch_id for dim in ACCEPTANCE_DIMENSIONS
              for mismatch_id in dim["mismatch_ids"]}
    assert mapped == set(MISMATCH_IDS)
    for rule in MISMATCH_RULES:
        assert rule["severity"] in {"critical", "high", "medium"}
        assert rule["required_actions"]
        assert rule["code"]
    for dimension in ACCEPTANCE_DIMENSIONS:
        assert dimension["title"]
        assert dimension["task_fields"]


def test_matrix_has_40_plus_cases_and_covers_every_am_class(
        cases: list[dict]) -> None:
    assert len(cases) >= 60
    assert len({case["case_id"] for case in cases}) == len(cases)
    covered = {mismatch_id for case in cases
               for mismatch_id in case["expected_mismatches"]}
    assert covered == set(MISMATCH_IDS)
    for case in cases:
        assert case["expected_mismatches"] == sorted(
            case["expected_mismatches"])
        expected = "verified" if not case["expected_mismatches"] else "rejected"
        assert case["expected_decision"] == expected


def test_audit_report_recall_precision_and_all_cases(cases: list[dict],
                                                     report: dict) -> None:
    assert len(cases) == report["case_count"]
    assert report["covered_am_classes"] == sorted(MISMATCH_IDS)
    assert report["recall"] == 1.0
    assert report["precision"] == 1.0
    assert report["false_positives"] == 0
    assert report["ok"] is True, report["failures"]
    assert len(report["cases"]) == len(cases)
    for case in report["cases"]:
        assert case["ok"] is True, case


def test_positive_cases_verify(cases: list[dict]) -> None:
    positives = [case for case in cases
                 if not case["expected_mismatches"]]
    assert len(positives) >= 4
    for case in positives:
        result = _match(case)
        assert result["verified"] is True, (case["case_id"], result)
        assert result["decision"] == "verified"
        assert result["mismatches"] == []
        assert result["residual_risk"] == "low"
    aliases = [case for case in positives
               if case["acceptance"]["model_identity"].get("status") == "alias"]
    assert aliases, "declared alias positive case missing"


def test_every_am_class_has_a_detected_negative_case(cases: list[dict]) -> None:
    detected_by_class: dict[str, list[str]] = {mismatch_id: []
                                               for mismatch_id in MISMATCH_IDS}
    for case in cases:
        if not case["expected_mismatches"]:
            continue
        result = _match(case)
        assert result["verified"] is False, case["case_id"]
        assert result["decision"] == "rejected"
        for mismatch_id in case["expected_mismatches"]:
            detected_by_class[mismatch_id].append(case["case_id"])
    missing = [mismatch_id for mismatch_id, case_ids in detected_by_class.items()
               if not case_ids]
    assert missing == []


def test_served_model_only_never_verifies() -> None:
    task, acceptance = audit._mutated(lambda task, acceptance: None)
    acceptance["model_identity"] = {
        "status": "served-model-only",
        "requested": "deepseek-chat",
        "served": "deepseek-chat",
    }
    result = AcceptanceModelMatcher.match(task, acceptance)
    assert result["verified"] is False
    assert "AM09" in result["mismatches"]
    assert "reject_served_model_identity" in result["required_actions"]


@pytest.mark.parametrize("field,value,mismatch_id", [
    ("target_sha", "f" * 64, "AM01"),
    ("tree_sha", "f" * 64, "AM02"),
    ("format", "pe", "AM03"),
    ("arch", "arm64", "AM04"),
])
def test_sha_format_arch_spoofs_fail_closed(field: str, value: str,
                                            mismatch_id: str) -> None:
    task, acceptance = audit._mutated(lambda task, acceptance: None)
    if field in {"target_sha", "tree_sha"}:
        acceptance["target"][{"target_sha": "sha256",
                              "tree_sha": "tree_sha"}[field]] = value
    else:
        acceptance["target"][field] = value
    result = AcceptanceModelMatcher.match(task, acceptance)
    assert result["verified"] is False
    assert mismatch_id in result["mismatches"]


def test_scope_static_dynamic_whole_program_fail_closed() -> None:
    task, acceptance = audit._mutated(lambda task, acceptance: None)
    acceptance["scope"] = "module"
    scope_result = AcceptanceModelMatcher.match(task, acceptance)
    assert scope_result["verified"] is False
    assert "AM05" in scope_result["mismatches"]

    task, acceptance = audit._mutated(lambda task, acceptance: None)
    acceptance["evidence"][1]["mode"] = "static"
    mode_result = AcceptanceModelMatcher.match(task, acceptance)
    assert mode_result["verified"] is False
    assert "AM06" in mode_result["mismatches"]

    task, acceptance = audit._mutated(lambda task, acceptance: None)
    task["scope"] = "whole_program"
    acceptance["scope"] = "whole_program"
    acceptance["claims"]["scope"] = "whole_program"
    whole_result = AcceptanceModelMatcher.match(task, acceptance)
    assert whole_result["verified"] is False
    assert "AM07" in whole_result["mismatches"]


def test_independence_and_claims_fail_closed() -> None:
    task, acceptance = audit._mutated(lambda task, acceptance: None)
    acceptance["independence"]["self_review"] = True
    independence = AcceptanceModelMatcher.match(task, acceptance)
    assert independence["verified"] is False
    assert "AM18" in independence["mismatches"]

    task, acceptance = audit._mutated(lambda task, acceptance: None)
    acceptance["claims"]["extra_claims"] = ["whole_repository_secure"]
    claims = AcceptanceModelMatcher.match(task, acceptance)
    assert claims["verified"] is False
    assert "AM19" in claims["mismatches"]


def test_matcher_is_pure_deterministic_and_json_serializable() -> None:
    task, acceptance = audit._mutated(lambda task, acceptance: None)
    task_before = copy.deepcopy(task)
    acceptance_before = copy.deepcopy(acceptance)
    first = AcceptanceModelMatcher.match(task, acceptance)
    second = AcceptanceModelMatcher.match(task, acceptance)
    assert first == second
    assert json.loads(json.dumps(first, sort_keys=True)) == json.loads(
        json.dumps(second, sort_keys=True))
    assert task == task_before
    assert acceptance == acceptance_before
    for key in ("decision", "mismatches", "required_actions", "verified",
                "residual_risk", "reasons"):
        assert key in first


def test_cli_json_matrix_report() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "audit_acceptance_models.py"),
         "--json"],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["case_count"] >= 60
    assert payload["recall"] == 1.0
    assert payload["precision"] == 1.0
    assert len(payload["covered_am_classes"]) == 28
    assert set(payload["mismatch_classes"]) == set(MISMATCH_IDS)


def test_committed_artifacts_check_ok() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "audit_acceptance_models.py"),
         "--check"],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "check OK" in result.stdout
    for name in ("cases.json", "report.json", "README.md", "SHA256SUMS"):
        assert (ARTIFACT_DIR / name).is_file(), name


def test_check_detects_tampered_cases_and_report(tmp_path: Path) -> None:
    target = tmp_path / "audit"
    shutil.copytree(ARTIFACT_DIR, target)
    cases_path = target / "cases.json"
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    cases["cases"][0]["expected_mismatches"] = ["AM99"]
    cases_path.write_text(json.dumps(cases, indent=2, sort_keys=True) + "\n",
                          encoding="utf-8")
    tampered = subprocess.run(
        [sys.executable, str(SCRIPTS / "audit_acceptance_models.py"),
         "--check", "--artifact-dir", str(target)],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    assert tampered.returncode != 0
    assert "AUDIT-VIOLATION" in tampered.stdout

    shutil.rmtree(target)
    shutil.copytree(ARTIFACT_DIR, target)
    report_path = target / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["recall"] = 0.5
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    tampered_report = subprocess.run(
        [sys.executable, str(SCRIPTS / "audit_acceptance_models.py"),
         "--check", "--artifact-dir", str(target)],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    assert tampered_report.returncode != 0
    assert "report.json" in tampered_report.stdout


def test_cli_write_and_check_roundtrip(tmp_path: Path) -> None:
    target = tmp_path / "generated"
    write = subprocess.run(
        [sys.executable, str(SCRIPTS / "audit_acceptance_models.py"),
         "--write", "--artifact-dir", str(target)],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    assert write.returncode == 0, write.stdout + write.stderr
    check = subprocess.run(
        [sys.executable, str(SCRIPTS / "audit_acceptance_models.py"),
         "--check", "--artifact-dir", str(target)],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    assert check.returncode == 0, check.stdout + check.stderr
    assert audit.check_artifacts(target) == []


# ---------------------------------------------------------------------------
# Phase-8 additive classes AM21-AM24
# ---------------------------------------------------------------------------

def _phase8_negative(case_id: str) -> dict:
    case = next(case for case in audit.build_cases()
                if case["case_id"] == case_id)
    result = AcceptanceModelMatcher.match(case["task"], case["acceptance"])
    expected = case["expected_mismatches"]
    assert result["verified"] is False
    assert result["mismatches"] == expected, (case_id, result["mismatches"])
    return result


def test_am21_repair_scope_escape_is_rejected() -> None:
    result = _phase8_negative("negative-am21-repair-scope-escape")
    assert "reject_repair_scope_mismatch" in result["required_actions"]


def test_am21_out_of_target_function_and_range_is_rejected() -> None:
    task, acceptance = audit._mutated(lambda task, acceptance: None)
    task["target_scope"] = {"policy": "target_scoped", "name": "vuln_copy",
                            "va": 4096, "end": 8192}
    acceptance["repair_scope"] = {
        "policy": "target_scoped",
        "modified_functions": ["vuln_copy", "helper"],
        "actions": [{"va": 9000}],
    }
    result = AcceptanceModelMatcher.match(task, acceptance)
    assert result["verified"] is False
    assert result["mismatches"] == ["AM21"]


def test_am22_partial_semantic_scope_is_rejected() -> None:
    result = _phase8_negative("negative-am22-semantic-scope-partial")
    assert "collect_semantic_scope_evidence" in result["required_actions"]


def test_am23_generator_self_report_is_not_an_oracle() -> None:
    result = _phase8_negative("negative-am23-oracle-self-report")
    assert "require_independent_oracle" in result["required_actions"]


def test_am23_missing_required_oracle_is_rejected() -> None:
    task, acceptance = audit._mutated(lambda task, acceptance: None)
    task["requires_independent_oracle"] = True
    result = AcceptanceModelMatcher.match(task, acceptance)
    assert result["verified"] is False
    assert "AM23" in result["mismatches"]


def test_am24_benchmark_version_mismatch_is_rejected() -> None:
    result = _phase8_negative("negative-am24-benchmark-version-mismatch")
    assert "reject_benchmark_version_mismatch" in result["required_actions"]


def test_am24_missing_benchmark_record_is_rejected() -> None:
    task, acceptance = audit._mutated(lambda task, acceptance: None)
    task["benchmark"] = {"version": "phase8-v1", "sample_set_sha256": "a" * 64}
    result = AcceptanceModelMatcher.match(task, acceptance)
    assert result["verified"] is False
    assert "AM24" in result["mismatches"]


def test_am21_am24_positive_cases_verify() -> None:
    positives = [case for case in audit.build_cases()
                 if not case["expected_mismatches"]
                 and any(key in case["task"] or key in case["acceptance"]
                         for key in ("target_scope", "semantic_scope",
                                     "requires_independent_oracle",
                                     "benchmark"))]
    assert len(positives) >= 5
    for case in positives:
        result = AcceptanceModelMatcher.match(case["task"],
                                              case["acceptance"])
        assert result["verified"] is True, (case["case_id"], result)


# ---------------------------------------------------------------------------
# Phase-8B additive classes AM25-AM28
# ---------------------------------------------------------------------------

def _phase8b_case(case_id: str) -> dict:
    case = next(case for case in audit.build_cases()
                if case["case_id"] == case_id)
    result = AcceptanceModelMatcher.match(case["task"], case["acceptance"])
    assert result["mismatches"] == case["expected_mismatches"], (
        case_id, result["mismatches"])
    return result


def test_am25_candidate_layout_mismatch_rejected() -> None:
    result = _phase8b_case("negative-am25-layout-missing")
    assert result["verified"] is False
    assert "reject_candidate_layout_mismatch" in result["required_actions"]
    operation = _phase8b_case("negative-am25-operation-mismatch")
    assert "AM25" in operation["mismatches"]


def test_am25_layout_cave_and_relocation_consistency() -> None:
    task, acceptance = audit._mutated(lambda task, acceptance: None)
    task["patch_plan"] = {
        "plan_sha256": "a" * 64,
        "candidate_sha256": "c" * 64,
        "operations": [{
            "kind": "insert",
            "original_offset": 8409,
            "candidate_offset": 4915238,
            "size": 16,
            "before_hex": "",
            "after_hex": "90" * 16,
            "site_va": 16956099,
            "reason": "guard_cave",
            "authorization_ref": None,
        }],
        "cave": {"va": 4915200, "size": 64, "executable": True,
                 "method": "append"},
        "relocations": [],
    }
    acceptance["candidate_sha256"] = "c" * 64
    acceptance["layout_evidence"] = {
        "patch_plan_sha256": "a" * 64,
        "replay_ok": True,
        "changed_ranges": [{"original_offset": 8409,
                            "candidate_offset": 4915238,
                            "size": 16, "kind": "insert"}],
        "cave": {"va": 4915200, "size": 64, "executable": True,
                 "method": "append"},
        "relocations": [],
        "abi_blocks": [{"function": "main", "va": 16956084, "size": 16,
                        "arch": "x86_64"}],
    }
    result = AcceptanceModelMatcher.match(task, acceptance)
    assert result["verified"] is True, result


def test_am26_associated_change_authorization() -> None:
    result = _phase8b_case("negative-am26-unauthorized-associated")
    assert "reject_unauthorized_associated_change" in result["required_actions"]
    out_of_range = _phase8b_case("negative-am26-associated-out-of-range")
    assert "AM26" in out_of_range["mismatches"]


def test_am27_abi_evidence_requirement() -> None:
    result = _phase8b_case("negative-am27-abi-missing")
    assert "collect_derived_abi_evidence" in result["required_actions"]
    task, acceptance = audit._mutated(lambda task, acceptance: None)
    task["requires_abi_evidence"] = True
    acceptance["abi_blocks"] = [{"function": "main", "va": 4202713,
                                 "size": 16, "arch": "x86_64"}]
    assert AcceptanceModelMatcher.match(task, acceptance)["verified"] is True


def test_am28_oracle_metadata_requirement() -> None:
    result = _phase8b_case("negative-am28-oracle-metadata")
    assert "collect_oracle_metadata" in result["required_actions"]
    task, acceptance = audit._mutated(lambda task, acceptance: None)
    acceptance["oracle_evidence"] = {
        "manifest_sha256": "a" * 64,
        "runner": "lima-guest",
        "tier": "emulated_run",
        "status": "executed",
        "evidence_sha256": "b" * 64,
        "expected": {"expected_original": "triggers",
                     "expected_candidate": "rejected"},
    }
    assert AcceptanceModelMatcher.match(task, acceptance)["verified"] is True


def test_am25_am28_phase8b_positive_cases_verify() -> None:
    positives = [case for case in audit.build_cases()
                 if not case["expected_mismatches"]
                 and any(key in case["task"] or key in case["acceptance"]
                         for key in ("patch_plan", "authority",
                                     "requires_abi_evidence",
                                     "oracle_evidence", "abi_blocks"))]
    assert len(positives) >= 4
    for case in positives:
        result = AcceptanceModelMatcher.match(case["task"],
                                              case["acceptance"])
        assert result["verified"] is True, (case["case_id"], result)
