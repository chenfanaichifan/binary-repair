"""Synthetic aggregation tests for the stability matrix."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "stability", ROOT / "scripts" / "run_stability_matrix.py")
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def test_aggregate_counts_and_failures():
    records = [
        {"spec": "m", "case_id": "a", "status": "completed", "verified": True,
         "repair_status": "VERIFIED"},
        {"spec": "m", "case_id": "a", "status": "completed", "verified": False,
         "repair_status": "SECURITY_FAILED"},
        {"spec": "m", "case_id": "b", "status": "error"},
    ]
    report = mod.aggregate(records)
    assert report["runs"] == 3
    assert report["eligible_runs"] == 2
    assert report["verified_runs"] == 1
    assert report["R_verified"] == 0.5
    assert report["per_model"]["m"]["failures"] == {"SECURITY_FAILED": 1}
    assert report["per_case"]["a"] == {"runs": 2, "verified": 1}
