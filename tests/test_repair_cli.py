"""The direct binary repair CLI works from the repository root."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VULN = ROOT / "artifacts" / "vuln-elf" / "vuln.elf"


def test_cli_returns_strict_patched_elf(tmp_path):
    out = tmp_path / "out.elf"
    report = tmp_path / "report.json"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "repair_binary.py"),
         str(VULN), str(out), "--report", str(report)],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    assert out.read_bytes()[:4] == b"\x7fELF"
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["mode"] == "strict"
    assert payload["capacity"] == 16
