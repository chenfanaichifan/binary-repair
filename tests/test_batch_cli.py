"""Batch CLI over a mixed directory."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv" / "bin" / "python"
PE = ROOT / "fixtures" / "pe" / "vuln-strcpy-x64.exe"
I386 = ROOT / "fixtures" / "pe" / "i386-control.exe"


def test_batch_repairs_supported_and_reports_unsupported(tmp_path):
    if not PE.is_file() or not I386.is_file():
        pytest.skip("PE fixtures missing")
    source = tmp_path / "in"
    source.mkdir()
    shutil.copy(PE, source / "good.exe")
    shutil.copy(I386, source / "control.exe")
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
    assert summary == {"ok": 1, "unsupported": 1, "error": 0}
    assert (out / "good-fixed.exe").is_file()
    assert not (out / "control-fixed.exe").exists()
    good = next(item for item in records if item.get("output"))
    assert good["format"] == "pe"
    assert good["strategy"] == "guard"
    assert good["verification_tier"] == "emulated_run"
