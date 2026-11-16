from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_stability_matrix as stability  # noqa: E402


def _record(spec: str = "deepseek:flash", case: str = "case-a",
            run: int = 1, status: str = "verified", *,
            completed: bool = True) -> dict:
    record = {"spec": spec, "case_id": case, "run": run, "started": True}
    return stability._finalize(record, status, completed=completed)


def test_classification_keeps_plan_and_artifact_failures_separate() -> None:
    assert stability._verification_status(
        {"gate": "plan_invalid"}, {}, None, Path(".")) == ("PLAN_INVALID", None)
    assert stability._verification_status(
        {"gate": "no_candidate"}, {}, None, Path(".")) == ("NO_CANDIDATE", None)
    assert stability._verification_status(
        {"gate": "pass"}, {}, None, Path(".")) == ("ARTIFACT_MISSING", None)


def test_finalize_counts_only_independent_verified() -> None:
    verified = _record(status="verified")
    plan = _record(status="PLAN_INVALID")
    missing = _record(status="ARTIFACT_MISSING")
    assert verified["verified"] is True and verified["eligible"] is True
    assert plan["verified"] is False and plan["eligible"] is True
    assert missing["verified"] is False and missing["eligible"] is False


def test_timeout_record_is_not_eligible() -> None:
    args = argparse.Namespace(experiment_id="exp", timeout=10)
    record = stability._timeout_record(
        "deepseek:flash", "deepseek", "flash", "case-a", 1, args,
        subprocess.TimeoutExpired("cmd", 10),
    )
    assert record["status"] == "timeout"
    assert record["completed"] is False
    assert record["eligible"] is False
    assert record["verification_status"] == "TIMEOUT"


def test_aggregate_reports_expected_started_completed_eligible() -> None:
    records = [
        _record(status="verified"),
        _record(case="case-b", status="PLAN_INVALID"),
        _record(case="case-c", status="ARTIFACT_MISSING"),
        _record(case="case-d", status="TIMEOUT", completed=False),
    ]
    report = stability.aggregate(records, expected_runs=4)
    assert report["expected_runs"] == 4
    assert report["started_runs"] == 4
    assert report["completed_runs"] == 3
    assert report["eligible_runs"] == 2
    assert report["verified_runs"] == 1
    assert report["status_counts"]["PLAN_INVALID"] == 1
    assert report["status_counts"]["ARTIFACT_MISSING"] == 1
    assert report["status_counts"]["TIMEOUT"] == 1
    assert report["R_verified"] == 1 / 2


def test_checkpoint_roundtrip_and_completed_keys(tmp_path: Path) -> None:
    records = [_record(status="verified")]
    stability._write_checkpoint(tmp_path, "exp", 4, records)
    expected, loaded = stability._load_checkpoint(tmp_path, "exp")
    assert expected == 4
    assert stability._record_key(loaded[0]) == ("deepseek:flash", "case-a", 1)
    assert stability._load_checkpoint(tmp_path, "other-exp") == (None, [])


def test_run_one_timeout_is_captured(tmp_path: Path, monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired("run_hard_benchmark", 3)

    monkeypatch.setattr(stability.subprocess, "run", fake_run)
    args = argparse.Namespace(
        out=tmp_path, cases=Path("cases.json"), timeout=3,
        max_repair_rounds=1, experiment_id="exp", profile=None,
        expected_runs=1,
    )
    record = stability._run_one("deepseek:flash", "case-a", 1, args)
    assert record["status"] == "timeout"
    assert record["verification_status"] == "TIMEOUT"
    assert record["completed"] is False
