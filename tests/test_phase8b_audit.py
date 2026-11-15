"""Tests for the Phase-8B B1 verifier disagreement baseline audit."""
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

import audit_phase8b_verifier_semantics as audit  # noqa: E402

ARTIFACT = ROOT / "artifacts" / "phase8b-baseline-2026-11-16"
BASELINE_PATH = ARTIFACT / "phase8b-baseline-audit.json"
GAPS_PATH = ARTIFACT / "phase8b-verifier-gap-registry.json"
DOC_PATHS = (
    ROOT / "docs/acceptance/phase8b-disagreement-analysis.md",
    ROOT / "docs/operations/phase8b-implementation-plan.md",
    ROOT / "docs/operations/phase8b-test-plan.md",
)


@pytest.fixture(scope="module")
def baseline() -> dict:
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def gaps() -> dict:
    return json.loads(GAPS_PATH.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_committed_artifact_check_ok() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "audit_phase8b_verifier_semantics.py"),
         "--check"],
        cwd=ROOT, capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "check OK" in result.stdout


def test_baseline_structure_and_identity(baseline: dict) -> None:
    assert baseline["schema_version"] == 1
    assert baseline["kind"] == "phase8b_verifier_disagreement_baseline"
    assert len(baseline["base_sha"]) == 40
    assert baseline["capability_claims"] == []
    assert baseline["environment"]["network_used"] is False
    assert baseline["environment"]["ai_invoked"] is False
    sample_ids = [sample["sample_id"] for sample in baseline["samples"]]
    assert sample_ids == ["stack-strcpy-x86_64", "heap-capacity-x86_64"]
    assert baseline["manifest"]["path"] == "benchmark/phase8-v1/manifest.json"
    assert baseline["manifest"]["hidden_available"] is False
    assert baseline["benchmark_results"]["verification_disagreements"] >= 2
    assert baseline["summary"]["status"] == "ok"
    assert baseline["summary"]["gap_registry"]["total"] == 7


def test_two_samples_reproduce_expected_candidates(baseline: dict) -> None:
    expected = {
        "stack-strcpy-x86_64":
            "1bc66b2ee28e2370cca1fcea624378e72afcafeac02c1da4eead689cd64ff6f4",
        "heap-capacity-x86_64":
            "93e27f2fc543b2c9652efe638adafbf239ba58965b07b5beda3e516817b033a2",
    }
    for sample in baseline["samples"]:
        sid = sample["sample_id"]
        assert sample["status"] == "reproduced"
        assert sample["reproduction"]["candidate_sha256"] == expected[sid]
        assert sample["inputs"]["recorded_candidate_sha256"] == expected[sid]
        assert sample["status_flags"]["candidate_sha_matches_benchmark"] is True
        directory = ARTIFACT / f"disagreement-{sid}"
        assert (directory / "original.elf").is_file()
        assert (directory / "candidate.bin").is_file()
        assert _sha(directory / "original.elf") == (
            sample["inputs"]["original_sha256"])
        assert _sha(directory / "candidate.bin") == expected[sid]
        for name in ("outcome.json", "metadata.json", "verifier-report.json",
                     "reproduce.sh"):
            assert (directory / name).is_file(), (sid, name)


def test_candidate_bytes_are_evidence_only(baseline: dict) -> None:
    assert "evidence-only" in baseline["candidate_evidence_policy"]
    for sample in baseline["samples"]:
        assert sample["status_flags"]["generator_claim_not_copied"] is True
        assert sample["status_flags"]["independently_verified"] is False
        assert sample["classification"]["candidate_issue"] in {
            "none_observed", "candidate_defect"}
        assert "not verified" in sample["classification"]["candidate_correctness"]
        assert sample["candidate_file"]["provenance"]
        assert "evidence-only" in sample["candidate_file"]["provenance"]


def test_verifier_disagreement_and_oracle_facts(baseline: dict) -> None:
    for sample in baseline["samples"]:
        cli = sample["verifier"]["cli"]
        module_oracle = sample["verifier"]["module_api_with_oracle"]
        assert cli["decision"] == "rejected"
        cli_checks = {item["id"]: item["status"]
                      for item in cli["checks"]}
        module_checks = {item["id"]: item["status"]
                         for item in module_oracle["checks"]}
        assert cli_checks["runtime-oracle"] == "not_run"
        assert module_checks["runtime-oracle"] == "passed"
        assert sample["verifier"]["baseline_runner_path"].startswith("CLI")
        assert sample["status_flags"]["cli_oracle_not_run"] is True


def test_root_cause_hypotheses_are_adjudicated(baseline: dict) -> None:
    statuses = {
        sample["sample_id"]: {
            cause["hypothesis_id"]: cause["status"]
            for cause in sample["root_cause_candidates"]}
        for sample in baseline["samples"]
    }
    stack = statuses["stack-strcpy-x86_64"]
    heap = statuses["heap-capacity-x86_64"]
    for hypothesis in ("V8B-01", "V8B-04", "V8B-05", "V8B-06", "V8B-07"):
        assert stack[hypothesis] == "confirmed"
        assert heap[hypothesis] == "confirmed"
    assert stack["V8B-02"] == "confirmed"
    assert stack["V8B-03"] == "confirmed"
    assert heap["V8B-03"] == "refuted_for_observed_sample"
    assert baseline["root_cause_conclusions"]["V8B-01"] == "confirmed"


def test_gap_registry_covers_v8b_01_to_07(gaps: dict) -> None:
    assert gaps["kind"] == "phase8b_verifier_gap_registry"
    ids = [item["id"] for item in gaps["items"]]
    assert ids == [f"V8B-{index:02d}" for index in range(1, 8)]
    for item in gaps["items"]:
        for field in ("title", "severity", "affected_modules", "hypothesis",
                      "evidence_refs", "required_fix", "acceptance"):
            assert item[field], (item["id"], field)
        assert item["severity"] in {"critical", "high"}
        assert item["acceptance"]
    assert gaps["summary"]["total"] == 7


def test_documentation_is_ascii_and_answers_questions() -> None:
    assert all(path.is_file() for path in DOC_PATHS)
    disagreement = DOC_PATHS[0].read_text(encoding="utf-8")
    implementation = DOC_PATHS[1].read_text(encoding="utf-8")
    test_plan = DOC_PATHS[2].read_text(encoding="utf-8")
    for text in (disagreement, implementation, test_plan):
        assert all(ord(character) < 127 for character in text)
    for marker in ("candidate", "verifier", "V8B-01", "confirmed",
                   "not verified"):
        assert marker in disagreement
    for marker in ("V8B-01", "acceptance", "phase"):
        assert marker in implementation
    for marker in ("test", "V8B-01"):
        assert marker in test_plan
    assert "rule may be loosened" in disagreement
    assert "not verified" in disagreement


def test_audit_script_uses_no_ai_or_network() -> None:
    source = (SCRIPTS / "audit_phase8b_verifier_semantics.py").read_text(
        encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden = ("openai", "requests", "httpx", "urllib", "http",
                 "app.services.provider", "app.services.ai_")
    for name in imported:
        assert not any(token in name for token in forbidden), name
    assert "repair_any" in source
    assert "run_poc" in source


def test_check_detects_tampered_candidate_and_report(tmp_path: Path) -> None:
    target = tmp_path / "phase8b"
    shutil.copytree(ARTIFACT, target)
    # Tamper candidate bytes: SHA256SUMS and the saved-evidence check must fail.
    candidate = target / "disagreement-stack-strcpy-x86_64" / "candidate.bin"
    candidate.write_bytes(candidate.read_bytes() + b"tamper")
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "audit_phase8b_verifier_semantics.py"),
         "--check", "--artifact-dir", str(target)],
        cwd=ROOT, capture_output=True, text=True, timeout=300,
    )
    assert result.returncode != 0
    assert "PHASE8B-VIOLATION" in result.stdout

    shutil.rmtree(target)
    shutil.copytree(ARTIFACT, target)
    baseline_path = target / "phase8b-baseline-audit.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline["samples"][0]["verifier"]["cli"]["decision"] = "verified"
    baseline["samples"][0]["status_flags"]["independently_verified"] = True
    baseline_path.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "audit_phase8b_verifier_semantics.py"),
         "--check", "--artifact-dir", str(target)],
        cwd=ROOT, capture_output=True, text=True, timeout=300,
    )
    assert result.returncode != 0
    assert "PHASE8B-VIOLATION" in result.stdout


def test_check_detects_missing_artifact_file(tmp_path: Path) -> None:
    target = tmp_path / "phase8b"
    shutil.copytree(ARTIFACT, target)
    (target / "disagreement-heap-capacity-x86_64" /
     "verifier-report.json").unlink()
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "audit_phase8b_verifier_semantics.py"),
         "--check", "--artifact-dir", str(target)],
        cwd=ROOT, capture_output=True, text=True, timeout=300,
    )
    assert result.returncode != 0
    assert "PHASE8B-VIOLATION" in result.stdout
