"""Reproducible gate blind-spot experiment (scripted candidates, no network)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(
    __import__("shutil").which("clang") is None,
    reason="assembly blind-spot cases need host clang",
)
def test_gate_blind_spot_experiment_reports_caught_and_missed(tmp_path: Path) -> None:
    out = tmp_path / "blind-spots"
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "gate_blind_spot_experiment.py"),
         "--out", str(out)],
        cwd=ROOT, capture_output=True, text=True, timeout=240,
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    cases = {row["case"]: row for row in summary["cases"]}
    assert "asm_noop_ret" in cases
    assert "asm_wrong_destination" in cases
    assert "direct_extra_unrelated_executable_edit" in cases
    # These must be caught after the gate hardening in this round.
    assert cases["asm_noop_ret"]["gate_caught"] is True
    assert cases["asm_wrong_destination"]["gate_caught"] is True
    assert cases["asm_copy_without_terminator"]["gate_caught"] is True
    assert cases["direct_extra_unrelated_executable_edit"]["gate_caught"] is True
    # Known residual blind spot: the runtime oracle does not compare stdout/puts
    # side effects; a leaf assembly block that omits the original puts call can
    # still be memory-safe.  The experiment records it rather than hiding it.
    assert cases["asm_correct_copy_without_puts_side_effect"]["blind_spot"] is True
    assert summary["caught"] >= 4
    assert summary["blind_spots"] >= 1
    assert (out / "SHA256SUMS").is_file()
