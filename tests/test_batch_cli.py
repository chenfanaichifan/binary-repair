"""Batch CLI over a mixed directory."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(sys.executable)
PE = ROOT / "fixtures" / "pe" / "vuln-strcpy-x64.exe"
NEGATIVE = ROOT / "fixtures" / "pe" / "cli-64.exe"


def test_batch_repairs_supported_and_reports_unsupported(tmp_path):
    if not PE.is_file() or not NEGATIVE.is_file():
        pytest.skip("PE fixtures missing")
    source = tmp_path / "in"
    source.mkdir()
    shutil.copy(PE, source / "good.exe")
    shutil.copy(NEGATIVE, source / "control.exe")
    out = tmp_path / "out"
    proc = subprocess.run(
        [str(PYTHON), str(ROOT / "scripts" / "repair_binary.py"),
         "--batch", str(source), "--out", str(out), "--json"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=180,
    )
    assert proc.returncode == 0, proc.stderr
    records = [json.loads(line) for line in proc.stdout.splitlines() if line.startswith("{")]
    assert records
    summary = records[-1]["summary"]
    assert summary["verified"] == 1
    assert summary["analysis_only"] == 1
    assert summary["error"] == 0
    assert summary["ok"] == 1
    assert (out / "good-fixed.exe").is_file()
    assert not (out / "control-fixed.exe").exists()
    good = next(item for item in records if item.get("output"))
    assert good["format"] == "pe"
    assert good["strategy"] == "guard"
    assert good["disposition"] == "verified_patch"
    assert good["verification_tier"] == "emulated_run"
