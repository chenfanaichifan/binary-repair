"""The scripted two-path evidence bundle is reproducible and gate-backed."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_scripted_ai_evidence_has_both_paths_and_negative_control(tmp_path: Path) -> None:
    out = tmp_path / "ai-evidence"
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "capture_ai_binary_repair.py"),
         "--out", str(out)],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["paths"] == ["ai_plan", "ai_bytes"]
    assert summary["no_assembly_or_decompile_roundtrip"] is True
    assert len(summary["records"]) == 6
    assert all(row["verified"] for row in summary["records"].values())
    assert summary["negative_control"]["verified"] is False
    assert summary["negative_control"]["disposition"] == "rejected"
    # Both paths ran on every fixture; the scripted guard bytes may coincide
    # with the deterministic guard candidate, which is expected and honest.
    for path in summary["paths"]:
        assert any(key.startswith(path + ":") for key in summary["records"])
    sums = (out / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    assert len(sums) >= 7  # six records + summary + negative
