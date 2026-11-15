from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import freeze_experiment  # noqa: E402


def test_freezer_reads_test_counts_and_hashes(tmp_path: Path) -> None:
    xml = tmp_path / "junit.xml"
    xml.write_text(
        '<testsuite tests="7" failures="0" errors="0" skipped="1" time="1.0" />',
        encoding="utf-8",
    )
    assert freeze_experiment._test_count(xml)["tests"] == "7"
    assert freeze_experiment._test_count(tmp_path / "missing.xml")["status"] == "unavailable"


def test_profile_artifact_is_hashed() -> None:
    path = ROOT / "experiments/p21-p16r3-658ff8c/profile.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["verifier_profile"] == "P16R3_PLAN_AWARE"
    assert data["authorization_profile"] == "STATIC_REFERENCE_ONLY"
    assert data["source_commit"]
