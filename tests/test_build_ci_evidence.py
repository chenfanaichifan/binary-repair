"""Tests for portable GitHub-hosted CI evidence assembly (offline)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_ci_evidence.py"


def _pr_gate(ok: bool = True) -> dict:
    return {
        "schema_version": 1,
        "mode": "pr",
        "branch": "workbench-v3",
        "ok": ok,
        "checks": [
            {"id": "static-coverage-gate", "status": "passed", "required": True},
            {"id": "targeted-pytest", "status": "passed" if ok else "failed",
             "required": True},
        ],
        "violations": [] if ok else ["targeted pytest failed"],
    }


def _junit(path: Path, *, failures: int = 0, tests: int = 12) -> None:
    root = (
        f'<testsuites><testsuite name="pytest" tests="{tests}" '
        f'failures="{failures}" errors="0" skipped="1" time="1.0">'
        '</testsuite></testsuites>'
    )
    path.write_text(root, encoding="utf-8")


def _run(tmp_path: Path, *, pr_ok: bool = True, failures: int = 0,
         env: dict | None = None) -> subprocess.CompletedProcess:
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    gate = out_dir / "pr-gate.json"
    gate.write_text(json.dumps(_pr_gate(pr_ok)), encoding="utf-8")
    junit = out_dir / "pytest.xml"
    _junit(junit, failures=failures)
    out = out_dir / "ci-evidence.json"
    import os

    merged = dict(os.environ)
    merged.update(env or {})
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--out", str(out),
         "--pr-json", str(gate), "--pytest-junit", str(junit)],
        capture_output=True, text=True, timeout=60, env=merged,
    )


def test_green_ci_evidence_bundle(tmp_path: Path) -> None:
    env = {
        "GITHUB_ACTIONS": "true",
        "GITHUB_RUN_ID": "12345",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_WORKFLOW": "CI",
        "GITHUB_JOB": "release-gate-hosted",
        "GITHUB_SHA": "a" * 40,
        "GITHUB_REF": "refs/heads/workbench-v3",
        "GITHUB_REPOSITORY": "owner/repo",
    }
    result = _run(tmp_path, env=env)
    assert result.returncode == 0, result.stdout + result.stderr
    out = tmp_path / "out"
    evidence = json.loads((out / "ci-evidence.json").read_text())
    assert evidence["ok"] is True
    assert evidence["kind"] == "ci_portable_evidence"
    assert evidence["github"]["run_id"] == "12345"
    assert evidence["pytest"]["tests"] == 12
    assert evidence["pytest"]["skipped"] == 1
    assert evidence["pr_gate"]["ok"] is True
    assert "Lima nightly" in evidence["scope"]
    for name in ("README.md", "SHA256SUMS", "pr-gate.json", "pytest.xml"):
        assert (out / name).is_file()
    sums = (out / "SHA256SUMS").read_text()
    assert "ci-evidence.json" in sums
    assert "README.md" in sums


def test_failed_pytest_is_recorded_and_fails(tmp_path: Path) -> None:
    result = _run(tmp_path, failures=2)
    assert result.returncode == 1
    evidence = json.loads(
        (tmp_path / "out" / "ci-evidence.json").read_text())
    assert evidence["ok"] is False
    assert evidence["pytest"]["ok"] is False
    assert evidence["pytest"]["failures"] == 2


def test_failed_pr_gate_fails(tmp_path: Path) -> None:
    result = _run(tmp_path, pr_ok=False)
    assert result.returncode == 1
    assert "FAIL" in result.stdout


def test_missing_inputs_are_usage_errors(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--out", str(tmp_path / "x.json"),
         "--pr-json", str(tmp_path / "missing.json"),
         "--pytest-junit", str(tmp_path / "missing.xml")],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 2
