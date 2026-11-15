"""Tests for the Phase-8C C1 baseline/hidden readiness audit."""
from __future__ import annotations

import ast
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import audit_phase8c_readiness as audit  # noqa: E402

ARTIFACT = ROOT / "artifacts" / "phase8c-baseline-2026-11-16"
BASELINE_PATH = ARTIFACT / "phase8c-baseline-audit.json"
BREAKDOWN_PATH = ARTIFACT / "phase8c-work-breakdown.json"
DOC = ROOT / "docs/acceptance/phase8c-baseline-audit.md"
PHASE8B_RESULTS = ROOT / "artifacts/phase8b-benchmark-2026-11-16/results.json"


@pytest.fixture(scope="module")
def baseline() -> dict:
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def breakdown() -> dict:
    return json.loads(BREAKDOWN_PATH.read_text(encoding="utf-8"))


def test_committed_artifact_check_ok() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "audit_phase8c_readiness.py"),
         "--check"],
        cwd=ROOT, capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "check OK" in result.stdout


def test_baseline_structure_and_ten_questions(baseline: dict) -> None:
    assert baseline["schema_version"] == 1
    assert baseline["kind"] == "phase8c_readiness_audit"
    assert baseline["base_sha"] == audit.EXPECTED_BASE_SHA
    assert baseline["expected_base_sha"] == audit.EXPECTED_BASE_SHA
    assert baseline["capability_claims"] == []
    assert baseline["no_new_repair_capability"] is True
    assert baseline["no_verified_upgrade"] is True
    assert baseline["environment"]["network_used"] is False
    assert baseline["environment"]["ai_invoked"] is False
    questions = baseline["ten_questions"]
    assert [item["id"] for item in questions] == list(audit.QUESTION_IDS)
    assert len(questions) == 10
    for item in questions:
        assert item["status"] in {"answered", "reproduced", "not_run"}
        assert item["answer"].strip()


def test_v1_migration_matrix_is_lossless(baseline: dict) -> None:
    migration = baseline["q2_v1_migration"]
    matrix = migration["matrix"]
    assert len(matrix) == 12
    summary = migration["summary"]
    assert summary["lossless"] == 12
    assert summary["all_required_fields_present"] is True
    assert summary["hidden_false"] is True
    assert summary["v2_gap_count"] >= 1
    for row in matrix:
        assert row["binary_sha_matches"] is True
        assert row["source_refs_resolvable"] is True
        assert row["evidence_refs_resolvable"] is True
        assert row["required_schema_fields_missing"] == []
        assert row["lossless_v1_sample"] is True


def test_reproduction_is_truthful_and_matches_phase8b(baseline: dict) -> None:
    reproduction = baseline["q3_reproduction"]
    status = reproduction["status"]
    if status == "not_run":
        assert reproduction.get("reason")
        return
    assert status == "reproduced"
    assert reproduction["not_overwritten_committed_evidence"] is True
    committed = json.loads(PHASE8B_RESULTS.read_text(encoding="utf-8"))
    committed_candidates = {
        row["sample_id"]: row.get("candidate_sha256")
        for row in committed["results"]
    }
    samples = reproduction["samples"]
    assert len(samples) == 2
    for sample in samples:
        assert sample["sample_id"] in sorted(committed_candidates)
        assert sample["candidate_sha_matches_phase8b"] is True
        assert sample["candidate_sha256"] == committed_candidates[
            sample["sample_id"]]
        assert sample["independently_verified"] is True
        assert sample["verifier_decision"] == "verified"
        assert sample["oracle_status"] == "pass"
        assert sample["layout_status"] == "passed"
        assert sample["false_verified"] is False
    assert reproduction["summary"]["false_verified"] == 0


def test_hidden_facts_are_isolation_only_and_not_read(baseline: dict) -> None:
    hidden = baseline["q5_hidden_isolation"]["facts"]
    assert hidden["hidden_corpus_created"] is False
    assert hidden["hidden_corpus_read"] is False
    assert hidden["isolation_is_operational_not_cryptographic"] is True
    assert hidden["hidden_available_manifest"] is False
    assert hidden["hidden_commitment_sha256_manifest"] is None
    assert hidden["private_root_env"] == "PHASE8C_HIDDEN_ROOT"
    assert "phase8c-hidden" in hidden["private_root_default"]
    plan = (ARTIFACT / "phase8c-hidden-isolation-plan.md").read_text(
        encoding="utf-8")
    for marker in ("0700", "operational", "aggregate", "commitment",
                   "not cryptography"):
        assert marker.lower() in plan.lower()


def test_schema_contracts_and_gate_facts(baseline: dict) -> None:
    contracts = baseline["facts"]["contracts"]
    assert contracts["count"] == 13
    assert contracts["has_hidden_fields"] is True
    assert contracts["has_authority_block"] is True
    assert contracts["has_patch_plan_contract"] is True
    assert contracts["checker"]["exit_code"] == 0
    assert contracts["has_manifest_wrapper_contract"] is False
    assert contracts["has_hidden_commitment_contract"] is False
    assert contracts["has_results_contract"] is False
    gate = baseline["q8_gate_ci"]
    assert gate["phase8c_checks_gating"] == "shadow_not_gating"
    assert gate["release_gate"]["modes"]["pr"] == 4
    assert gate["release_gate"]["modes"]["release"] == 12
    assert gate["release_gate"]["modes"]["nightly"] == 13
    assert gate["readiness_g29"]["measured_status"] == "not_run"


def test_work_breakdown_covers_c1_to_c14(breakdown: dict) -> None:
    assert breakdown["kind"] == "phase8c_work_breakdown"
    tasks = breakdown["tasks"]
    assert [task["id"] for task in tasks] == list(audit.TASK_IDS)
    known = {task["id"] for task in tasks}
    for task in tasks:
        assert task["title"]
        assert task["write_scopes"]
        assert task["acceptance"]
        for dependency in task["dependencies"]:
            assert dependency in known, (task["id"], dependency)
    assert breakdown["parallel_groups"]["G1"]
    assert breakdown["blockers"]
    assert any(item["id"] == "B-HIDDEN-ROOT"
               for item in breakdown["blockers"])


def test_documentation_is_ascii_and_answers_ten_questions() -> None:
    assert DOC.is_file()
    text = DOC.read_text(encoding="utf-8")
    assert all(ord(character) < 127 for character in text)
    for index in range(1, 11):
        assert f"Q{index:02d}" in text
    for marker in ("hidden", "Lima", "v1", "v2", "blocker"):
        assert marker.lower() in text.lower()


def test_audit_script_uses_no_ai_network_or_git_commands() -> None:
    source = (SCRIPTS / "audit_phase8c_readiness.py").read_text(
        encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    for name in imported:
        assert not any(token in name for token in (
            "openai", "requests", "httpx", "urllib", "http",
            "app.services.provider")), name
    assert '["git"' not in source
    assert "git rev-parse" not in source
    assert '"hidden_corpus_created": False' in source
    assert '"hidden_corpus_read": False' in source


def test_cli_json_summary() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "audit_phase8c_readiness.py"), "--json"],
        cwd=ROOT, capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["base_sha"] == audit.EXPECTED_BASE_SHA
    assert len(payload["ten_questions"]) == 10
    assert payload["v1_migration"]["lossless"] == 12
    assert payload["hidden"]["hidden_available"] is False
    assert payload["contracts"]["count"] == 13


def test_check_detects_tampered_baseline_and_breakdown(
        tmp_path: Path) -> None:
    target = tmp_path / "phase8c"
    shutil.copytree(ARTIFACT, target)
    baseline_path = target / "phase8c-baseline-audit.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline["q2_v1_migration"]["summary"]["lossless"] = 11
    baseline["q5_hidden_isolation"]["facts"]["hidden_corpus_read"] = True
    baseline_path.write_text(
        json.dumps(baseline, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "audit_phase8c_readiness.py"),
         "--check", "--artifact-dir", str(target)],
        cwd=ROOT, capture_output=True, text=True, timeout=300,
    )
    assert result.returncode != 0
    assert "PHASE8C-VIOLATION" in result.stdout
    shutil.rmtree(target)
    shutil.copytree(ARTIFACT, target)
    baseline_path = target / "phase8c-baseline-audit.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline["ten_questions"] = baseline["ten_questions"][:9]
    baseline_path.write_text(
        json.dumps(baseline, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "audit_phase8c_readiness.py"),
         "--check", "--artifact-dir", str(target)],
        cwd=ROOT, capture_output=True, text=True, timeout=300,
    )
    assert result.returncode != 0
    assert "PHASE8C-VIOLATION" in result.stdout


def test_check_detects_tampered_sums_and_missing_file(tmp_path: Path) -> None:
    target = tmp_path / "phase8c"
    shutil.copytree(ARTIFACT, target)
    sums = target / "SHA256SUMS"
    lines = sums.read_text(encoding="utf-8").splitlines()
    lines[0] = "0" * 64 + "  " + lines[0].split()[-1]
    sums.write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "audit_phase8c_readiness.py"),
         "--check", "--artifact-dir", str(target)],
        cwd=ROOT, capture_output=True, text=True, timeout=300,
    )
    assert result.returncode != 0
    shutil.rmtree(target)
    shutil.copytree(ARTIFACT, target)
    (target / "phase8c-work-breakdown.json").unlink()
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "audit_phase8c_readiness.py"),
         "--check", "--artifact-dir", str(target)],
        cwd=ROOT, capture_output=True, text=True, timeout=300,
    )
    assert result.returncode != 0
    assert "PHASE8C-VIOLATION" in result.stdout
