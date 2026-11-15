from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import summarize_stability  # noqa: E402


def test_summary_separates_artifact_missing_from_verified() -> None:
    data = {"records": [
        {"spec": "m", "case_id": "a", "status": "completed",
         "verified": True, "verification_status": "verified"},
        {"spec": "m", "case_id": "b", "status": "completed",
         "verified": False, "verification_status": "ARTIFACT_MISSING"},
        {"spec": "m", "case_id": "c", "status": "completed",
         "verified": False, "verification_status": "PLAN_INVALID"},
    ]}
    summary = summarize_stability.summarize(data)
    assert summary["planned_runs"] == 3
    assert summary["eligible_runs"] == 3
    assert summary["verified_runs"] == 1
    assert summary["status_counts"]["ARTIFACT_MISSING"] == 1
    assert summary["R_verified"] == 1 / 3
