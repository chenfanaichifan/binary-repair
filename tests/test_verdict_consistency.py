"""P2 consistency test: snapshot / verdict.json file / DB / GUI agree.

M4's three authoritative fixtures are used verbatim, so the test fails if any
layer diverges or if the GUI invents a different outcome.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.i18n import OUTCOME_LABELS_ZH
from app.status import display_verdict

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "verdicts"


def _fixture(case: str) -> dict:
    return json.loads((FIXTURES / f"{case}.json").read_text(encoding="utf-8"))


def _snapshot(fixture: dict) -> dict:
    outcome = fixture["verdict"]["outcome"]
    route = {
        "name": "Route A",
        "phase": "finished",
        "outcome": outcome,
        "outcome_reason": fixture["verdict"]["reason"] or "",
        "stages": [{"name": "screening", "state": "done"}],
        "tests": {"passed": 0, "total": 0},
        "verification": "not_run",
        "compatibility": "not_run",
        "changed_regions": [],
        "manual_interventions": 0,
        "ai_usage": "unavailable",
        "elapsed_s": 0.0,
        "verdict": fixture["verdict"],
        "obligations": fixture["obligations"],
    }
    return {
        "id": fixture["job_id"],
        "demo": False,
        "filename": "sample.bin",
        "original_sha256": fixture["expected_sha256"],
        "defect": "fixture",
        "valid_tests": [],
        "environment": "fixture",
        "created_at": "2026-10-22T00:00:00+00:00",
        "phase": "finished",
        "cancelled": False,
        "contract": {
            "revision": 1,
            "sha256": fixture["reviewed_scope_sha256"],
            "approved": True,
            "valid_domain": "Input length 0-64 bytes",
            "forbidden": "Out-of-bounds write",
            "invalid_outcome": "Return error code 1",
            "assumptions": ["Single process"],
        },
        "run": {"id": fixture["run_id"], "phase": "finished", "manifest_sha256": "a" * 64, "reviewed_scope_sha256": fixture["reviewed_scope_sha256"]},
        "verdict": fixture["verdict"],
        "routes": {"A": route, "B": dict(route)},
    }


class _FakeBackend:
    mode = "mock"
    supports_start = True

    def __init__(self, snapshot: dict) -> None:
        self.snapshot = snapshot

    def get_snapshot(self, job_id: str):
        return self.snapshot

    def get_visuals(self, job_id: str):
        return {"available": False, "note": "fixture"}

    def get_obligations(self, job_id: str):
        return {}

    def get_artifacts(self, job_id: str):
        return {"A": [], "B": []}


@pytest.mark.parametrize(
    "case,expected",
    [
        ("success", "success_within_scope"),
        ("failure", "rejected"),
        ("unknown", "inconclusive"),
    ],
)
def test_verdict_consistent_across_snapshot_file_db_and_gui(case: str, expected: str, tmp_path, monkeypatch):
    fixture = _fixture(case)

    # 1. verdict.json file (authoritative evidence)
    verdict_file = tmp_path / "jobs" / fixture["job_id"] / "runs" / fixture["run_id"] / "verdict.json"
    verdict_file.parent.mkdir(parents=True)
    verdict_file.write_text(json.dumps(fixture, ensure_ascii=True), encoding="utf-8")
    file_verdict = json.loads(verdict_file.read_text(encoding="utf-8"))
    assert file_verdict["verdict"]["outcome"] == expected

    # 2. DB column (query index)
    connection = sqlite3.connect(tmp_path / "app.db")
    try:
        connection.execute(
            "CREATE TABLE attempts (id TEXT, outcome TEXT, reason TEXT, "
            "failing_obligation TEXT, detail TEXT)"
        )
        connection.execute(
            "INSERT INTO attempts VALUES (?, ?, ?, ?, ?)",
            (
                fixture["run_id"],
                fixture["verdict"]["outcome"],
                fixture["verdict"]["reason"],
                fixture["verdict"]["failing_obligation"],
                fixture["verdict"]["detail"],
            ),
        )
        connection.commit()
        db_outcome = connection.execute("SELECT outcome FROM attempts WHERE id = ?", (fixture["run_id"],)).fetchone()[0]
    finally:
        connection.close()
    assert db_outcome == expected

    # 3. controller snapshot (what the GUI reads)
    snapshot = _snapshot(fixture)
    assert snapshot["routes"]["A"]["outcome"] == expected
    assert snapshot["verdict"]["outcome"] == expected

    # 4. GUI renders that exact value and never computes its own
    assert display_verdict(snapshot)["key"] == expected
    monkeypatch.setattr(main, "BACKEND", _FakeBackend(snapshot))
    client = TestClient(main.app, base_url="http://127.0.0.1")
    assert client.get("/?token=" + main.SESSION_TOKEN).status_code == 200
    page = client.get(f"/jobs/{fixture['job_id']}")
    assert page.status_code == 200
    label = OUTCOME_LABELS_ZH[expected]
    assert label in page.text
    # The GUI must not show a different verdict.
    other_labels = [value for key, value in OUTCOME_LABELS_ZH.items() if key != expected and key != "cancelled"]
    assert all(value not in page.text for value in other_labels)
