"""Tests for the Phase-8C C13 public/hidden quality audit."""
from __future__ import annotations

import ast
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

import audit_phase8c_quality as quality  # noqa: E402

ARTIFACT = ROOT / "artifacts" / "phase8c-quality-2026-11-16"
ARTIFACT_JSON = ARTIFACT / "quality.json"


def test_committed_public_artifact_check_ok() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "audit_phase8c_quality.py"),
         "--check"], cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "check OK" in result.stdout


def test_public_checks_pass_on_current_tree() -> None:
    report = json.loads(ARTIFACT_JSON.read_text(encoding="utf-8"))
    assert report["kind"] == quality.KIND
    assert report["mode"] == "public_only"
    assert report["status"] == "ok_public_only"
    checks = {item["id"]: item["status"] for item in report["checks"]}
    for check_id in ("public-count", "public-core-count",
                     "public-runtime-analysis", "public-split-counts",
                     "v1-migration", "v2-contracts", "public-sums",
                     "contamination", "external", "hidden-leaks"):
        assert checks.get(check_id) == "pass", (check_id, checks)
    counts = report["counts"]
    assert counts["core_count"] == 28
    assert counts["runtime_count"] == 20
    assert counts["analysis_only_count"] == 8
    assert counts["sample_count"] == 32
    assert report["hidden_available"] is False
    assert report["v1_migration"]["migrated"] == 12
    assert report["v2_contracts"]["parsed"] == 4
    assert report["leaks"] == []


def test_full_mode_without_hidden_inputs_is_not_run() -> None:
    report = quality.audit(full=True, hidden_root=None)
    assert report["status"] == "not_run"
    checks = {item["id"]: item["status"] for item in report["checks"]}
    assert checks["hidden"] == "not_run"
    assert report["capability_claims"] == []


def test_full_mode_with_missing_root_is_not_run(tmp_path: Path) -> None:
    report = quality.audit(full=True, hidden_root=tmp_path / "missing")
    assert report["status"] == "not_run"
    checks = {item["id"]: item["status"] for item in report["checks"]}
    assert checks["hidden"] == "not_run"


def test_no_hidden_paths_in_public_artifact() -> None:
    report = json.loads(ARTIFACT_JSON.read_text(encoding="utf-8"))
    text = json.dumps(report)
    for pattern in quality.HIDDEN_LEAK_PATTERNS:
        assert pattern not in text


def test_no_network_ai_imports() -> None:
    source = (SCRIPTS / "audit_phase8c_quality.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    for name in imported:
        assert not any(token in name for token in (
            "requests", "httpx", "urllib", "openai", "app.services.provider"))


@pytest.mark.parametrize("tamper", ["json", "readme", "sums"])
def test_check_detects_tampering(tmp_path: Path, tamper: str) -> None:
    target = tmp_path / "artifact"
    shutil.copytree(ARTIFACT, target)
    if tamper == "json":
        path = target / "quality.json"
        report = json.loads(path.read_text(encoding="utf-8"))
        report["status"] = "ok"
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
    elif tamper == "readme":
        path = target / "README.md"
        path.write_text(path.read_text(encoding="utf-8") + "tamper\n",
                        encoding="utf-8")
    else:
        path = target / "SHA256SUMS"
        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text("0" * 64 + "  " + lines[0].split()[-1] + "\n"
                        + "\n".join(lines[1:]) + "\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "audit_phase8c_quality.py"),
         "--check", "--artifact-dir", str(target)],
        cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert result.returncode != 0
    assert "QUALITY-VIOLATION" in result.stdout


def _write(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    return path


def test_full_mode_with_synthetic_hidden_inputs_passes(tmp_path: Path) -> None:
    public_sha = quality._sha256_file(quality.PUBLIC_MANIFEST)
    commitment = {
        "schema_version": 1, "kind": "hidden_benchmark_commitment",
        "benchmark_id": "phase8c-v1", "hidden_version": "v1",
        "sample_count": 20, "runtime_count": 14,
        "analysis_only_count": 6,
        "commitment_sha256": "a" * 64,
        "public_manifest_sha256": public_sha,
        "created_at": "2026-11-16T00:00:00Z",
        "samples": [{"opaque_sample_id": f"{index:064x}",
                     "opaque_binary_sha256": f"{index + 1:064x}"}
                    for index in range(20)],
        "limitations": ["synthetic test"],
    }
    commitment_path = _write(tmp_path / "commitment.json", commitment)
    results = {
        "schema_version": 1, "kind": "benchmark_results_v2",
        "benchmark_id": "phase8c-v1",
        "manifest_sha256": public_sha,
        "generated_at": "2026-11-16T00:00:00Z",
        "samples": [{"sample_id": f"s{index}", "status": "executed"}
                    for index in range(48)],
        "aggregate": {"denominator": 48, "executed": 48,
                      "false_verified": 0},
        "hidden_aggregate": {"sample_count": 20, "runtime_count": 14,
                             "analysis_only_count": 6,
                             "false_verified": 0,
                             "per_sample_ids_included": False},
        "limitations": ["synthetic test"],
    }
    results_path = _write(tmp_path / "results.json", results)
    contamination = {"mode": "hidden", "status": "ok", "verdict": "clean"}
    contamination_path = _write(tmp_path / "contamination-hidden.json",
                                contamination)
    hidden_root = tmp_path / "hidden"
    hidden_root.mkdir()
    report = quality.audit(
        full=True, hidden_root=hidden_root,
        hidden_commitment=commitment_path, results_path=results_path,
        contamination_path=contamination_path)
    assert report["status"] == "ok", report["checks"]
    checks = {item["id"]: item["status"] for item in report["checks"]}
    assert checks["hidden-counts"] == "pass"
    assert checks["results-v2"] == "pass"
    assert checks["hidden-contamination"] == "pass"


def test_full_mode_false_verified_fails(tmp_path: Path) -> None:
    public_sha = quality._sha256_file(quality.PUBLIC_MANIFEST)
    commitment = {
        "schema_version": 1, "kind": "hidden_benchmark_commitment",
        "benchmark_id": "phase8c-v1", "hidden_version": "v1",
        "sample_count": 20, "runtime_count": 14,
        "analysis_only_count": 6,
        "commitment_sha256": "b" * 64,
        "public_manifest_sha256": public_sha,
        "created_at": "2026-11-16T00:00:00Z",
        "samples": [{"opaque_sample_id": f"{index:064x}",
                     "opaque_binary_sha256": f"{index + 2:064x}"}
                    for index in range(20)],
        "limitations": ["synthetic test"],
    }
    commitment_path = _write(tmp_path / "commitment.json", commitment)
    results = {
        "schema_version": 1, "kind": "benchmark_results_v2",
        "benchmark_id": "phase8c-v1", "manifest_sha256": public_sha,
        "generated_at": "2026-11-16T00:00:00Z", "samples": [],
        "aggregate": {"denominator": 48, "false_verified": 1},
        "hidden_aggregate": {"sample_count": 20, "false_verified": 0,
                             "per_sample_ids_included": False},
        "limitations": ["synthetic test"],
    }
    hidden_root = tmp_path / "hidden"
    hidden_root.mkdir()
    report = quality.audit(
        full=True, hidden_root=hidden_root,
        hidden_commitment=commitment_path,
        results_path=_write(tmp_path / "results.json", results),
        contamination_path=_write(tmp_path / "contamination-hidden.json",
                                  {"mode": "hidden", "status": "ok",
                                   "verdict": "clean"}))
    assert report["status"] == "fail"
    checks = {item["id"]: item["status"] for item in report["checks"]}
    assert checks["results-v2"] == "fail"
