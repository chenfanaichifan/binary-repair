"""Hard-case benchmark harness: baseline must fail, reference fix must gate."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LINUX_X64 = sys.platform.startswith("linux") and __import__("platform").machine() in {"x86_64", "amd64"}


def test_hard_cases_are_well_formed_and_baseline_fails():
    cases = json.loads((ROOT / "fixtures" / "hard-cases" / "cases.json").read_text())
    assert len(cases["cases"]) >= 2
    for case in cases["cases"]:
        assert (ROOT / case["binary"]).is_file()
        assert (ROOT / case["poc"]).is_file()
        assert (ROOT / case["reference_fix"]).is_file()
        assert case["baseline_expected"] in {"analysis_only", "rejected", "unsupported"}


@pytest.mark.skipif(not LINUX_X64, reason="native PoC gate requires Linux x86-64")
def test_reference_assembly_case_passes_native_poc_gate(tmp_path: Path):
    out = tmp_path / "bench"
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_hard_benchmark.py"),
         "--out", str(out), "--client", "reference", "--case", "inline-byte-loop"],
        cwd=ROOT, capture_output=True, text=True, timeout=240,
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads((out / "summary.json").read_text())
    assert summary["baseline_verified"] == 0
    assert summary["ai_verified"] == 1
    assert summary["ai_increment"] == 1
