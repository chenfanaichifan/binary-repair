from __future__ import annotations

import copy
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_phase8d_experiment_bundle as bundle  # noqa: E402


def test_bundle_is_deterministic_and_has_no_promotion():
    payload = bundle.build_bundle()
    assert payload["summary"] == {
        "experiment_count": 10,
        "verified_true_count": 0,
        "capability_promotion": False,
        "false_verified_observed": 0,
        "not_run_count": 0,
    }
    assert len(payload["experiments"]) == 10
    assert all(item["promotion_effect"] == "none" for item in payload["experiments"])
    assert len({item["experiment_id"] for item in payload["experiments"]}) == 10


def test_committed_bundle_check_and_hashes():
    ok, problems = bundle.check_bundle()
    assert ok is True, problems
    assert bundle.check_bundle() == (True, [])


def test_bundle_tamper_is_rejected(tmp_path, monkeypatch):
    source = ROOT / "artifacts" / "phase8d-experiments-2026-11-17" / "experiments.json"
    shutil.copyfile(source, tmp_path / "experiments.json")
    payload = json.loads((tmp_path / "experiments.json").read_text())
    payload["experiments"][0]["evidence"][0]["sha256"] = "0" * 64
    (tmp_path / "experiments.json").write_text(json.dumps(payload, indent=2))
    monkeypatch.setattr(bundle, "OUT", tmp_path)
    ok, problems = bundle.check_bundle()
    assert ok is False
    assert any("differs" in problem or "digest mismatch" in problem for problem in problems)


def test_bundle_contains_all_phase8d_workstreams():
    payload = bundle.build_bundle()
    ids = {item["experiment_id"] for item in payload["experiments"]}
    expected = {f"EXP-8D-D{i:02d}" for i in range(11)} - {"EXP-8D-D08"}
    assert ids == expected
    # D08 is the bundle itself; the ten bound experiments cover D00-D07 and D09-D10.
