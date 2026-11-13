"""Native/guest PoC and regression execution evidence."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from app.services.binary_pipeline import repair_any
from app.services.poc_runner import load_manifest, run_poc

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "elf" / "vuln-strcpy-x86_64.elf"
MANIFEST = ROOT / "fixtures" / "poc" / "elf-x86_64-strcpy.json"
LINUX_X64 = sys.platform.startswith("linux") and __import__("platform").machine() in {"x86_64", "amd64"}


def test_manifest_validation_and_hash_binding():
    data = load_manifest(MANIFEST)
    assert data["format"] == "elf"
    assert data["arch"] == "x86_64"
    assert data["poc"] and data["regression"]
    with pytest.raises(ValueError):
        load_manifest({"schema_version": 1})


def test_poc_runner_is_explicit_when_unavailable_or_wrong_hash(tmp_path: Path):
    manifest = json.loads(MANIFEST.read_text())
    original = b"not the fixture"
    evidence = run_poc(original, original, manifest)
    assert evidence.status == "fail"
    assert any("fixture_sha256" in item for item in evidence.limitations)


@pytest.mark.skipif(not LINUX_X64, reason="native ELF x86-64 PoC requires Linux x86-64")
def test_real_poc_and_regression_pass_for_verified_candidate():
    original = FIXTURE.read_bytes()
    manifest = json.loads(MANIFEST.read_text())
    outcome = repair_any(original, poc_manifest=manifest)
    assert outcome.verified is True, outcome.report.to_dict()
    assert outcome.report.poc["status"] == "pass"
    checks = {
        check["id"]: check["status"]
        for check in outcome.report.verification["packet"]["checks"]
    }
    assert checks["poc.native.available"] == "passed"
    assert checks["poc.native.original_failure"] == "passed"
    assert checks["poc.native.candidate_pass"] == "passed"
    assert checks["poc.native.regression"] == "passed"


@pytest.mark.skipif(not LINUX_X64, reason="native ELF x86-64 PoC requires Linux x86-64")
def test_noop_candidate_fails_poc_gate():
    original = FIXTURE.read_bytes()
    manifest = json.loads(MANIFEST.read_text())
    # Candidate identical to the vulnerable original: PoC original expectation
    # passes, but the candidate must also fail, so the gate rejects.
    evidence = run_poc(original, original, manifest)
    assert evidence.status == "fail"
