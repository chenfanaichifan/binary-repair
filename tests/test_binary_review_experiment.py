"""The reproducible review experiment keeps its three-case contract."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "demo_binary_ai_review.py"


def test_scripted_experiment_has_the_three_required_outcomes(tmp_path: Path):
    out = tmp_path / "review"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--provider", "scripted", "--out", str(out)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert payload["provider"]["mode"] == "scripted"
    assert payload["provider"]["called"] is False
    cases = {item["case_id"]: item for item in payload["cases"]}
    assert set(cases) == {"strict_ok", "unsupported", "missing_evidence"}

    strict = cases["strict_ok"]
    assert strict["baseline"]["decision"]["success"] is True
    assert strict["with_review"]["decision"]["success"] is True
    assert strict["hold_control"]["decision"]["success"] is False
    assert strict["hold_control"]["decision"]["authority"] == "scripted_veto"

    for case_id in ("unsupported", "missing_evidence"):
        case = cases[case_id]
        assert case["baseline"]["decision"]["success"] is False
        assert case["with_review"]["decision"]["success"] is False
        assert case["accept_control"]["decision"]["success"] is False
        assert case["accept_control"]["decision"]["reason"] == "review_accept_cannot_promote_gate"

    sums = (out / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    assert len(sums) == 3
    for line in sums:
        digest, name = line.split(None, 1)
        import hashlib

        assert hashlib.sha256((out / name.strip()).read_bytes()).hexdigest() == digest
