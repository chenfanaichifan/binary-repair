"""Offline CI evidence/claims consistency; online check is opt-in."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ci_claims_are_offline_consistent():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_ci_evidence.py")],
        cwd=ROOT, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "claims=ok" in result.stdout


def test_claims_do_not_claim_universal_repair():
    claims = json.loads((ROOT / "docs" / "status" / "claims.json").read_text())
    assert claims["product_paths"] == ["asm_roundtrip", "binary_direct"]
    assert "not universal repair" in claims["scope"]
    assert any("paradigm A" in item for item in claims["explicitly_unimplemented"])
