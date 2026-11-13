"""Fixture/evidence SHA-256 verification is reproducible and machine-checkable."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_verify_evidence_passes_for_committed_tree() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_evidence.py"), "--json"],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["hash_algorithm"] == "sha256"
    assert payload["fixtures_ok"] is True
    assert payload["fixture_count"] >= 11
    assert all(bundle["ok"] for bundle in payload["bundles"])
    assert "git blob" in payload["note"]
