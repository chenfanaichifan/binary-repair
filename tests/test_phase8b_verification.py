"""Tests for the committed Phase-8B real-verification evidence checker."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_phase8b_verification.py"
RESULTS = ROOT / "artifacts" / "phase8b-benchmark-2026-11-16" / "results.json"


def _run(path: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--results", str(path), "--json", *args],
        cwd=ROOT, capture_output=True, text=True, timeout=60,
    )


def test_committed_artifact_has_real_verification_zero_false() -> None:
    result = _run(RESULTS)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["ok"] is True
    assert report["false_verified"] == 0
    assert report["real_verification_count"] >= 1
    assert report["verified_samples"]


def test_false_verified_tamper_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "results.json"
    payload = json.loads(RESULTS.read_text())
    payload["summary"]["false_verified"] = 2
    target.write_text(json.dumps(payload))
    result = _run(target)
    assert result.returncode == 1
    assert json.loads(result.stdout)["false_verified"] == 2


def test_verified_row_without_evidence_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "results.json"
    payload = json.loads(RESULTS.read_text())
    for row in payload["results"]:
        if row.get("independently_verified"):
            row["verifier_decision"] = "rejected"
            break
    target.write_text(json.dumps(payload))
    result = _run(target)
    assert result.returncode == 1
    assert "verifier_decision" in result.stdout


def test_missing_results_is_not_run(tmp_path: Path) -> None:
    result = _run(tmp_path / "absent.json")
    assert result.returncode == 2
    assert json.loads(result.stdout)["not_run"]
