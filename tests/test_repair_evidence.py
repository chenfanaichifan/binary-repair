"""Repair evidence bundle build/check."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.repair_evidence import build, check


def test_build_and_check(tmp_path):
    run = tmp_path / "run"
    (run / "candidates").mkdir(parents=True)
    cand = run / "candidates" / "c.bin"
    cand.write_bytes(b"candidate")
    summary = {
        "provider": "fake", "funnel": {"VERIFIED": 1}, "ai_verified": 1,
        "cases": [{
            "case": {"id": "c"}, "input_sha256": "a" * 64,
            "candidate": {"gate": "pass", "repair_status": "VERIFIED",
                          "candidate_sha256": "b" * 64,
                          "candidate_artifact": str(cand)},
            "ai_attempts": [{"plan_status": "valid"}],
        }],
    }
    (run / "summary.json").write_text(json.dumps(summary))
    (run / "run-manifest.json").write_text(json.dumps({"schema_version": 1}))
    out = tmp_path / "bundle"
    metadata = build(run, out)
    assert metadata["schema_version"] == 2
    assert metadata["cases"][0]["repair_status"] == "VERIFIED"
    assert (out / "candidates" / "c.bin").is_file()
    assert check(out) == []


def test_check_detects_tamper(tmp_path):
    run = tmp_path / "run"; run.mkdir()
    (run / "summary.json").write_text(json.dumps({"cases": []}))
    out = tmp_path / "bundle"
    build(run, out)
    (out / "metadata.json").write_text("{}")
    assert check(out)
