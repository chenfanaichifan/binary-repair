"""M1 handoff (97-m1-review-closeout): persisted scope and attempt history.

Two GUI-side contracts are pinned here:

* ``obligations.scope`` from migration 005 wins over the GUI's kind table, and the
  page says which one it used;
* ``GET /api/jobs/{id}/attempts`` is consumed as-is, and an absent endpoint is
  reported as "not available", never as "zero attempts".
"""

from __future__ import annotations

from fastapi.testclient import TestClient

import app.main as main_module
from app.backend import build_export_bundle
from app.evidence_domains import scope_display
from app.main import SESSION_TOKEN, app

OBLIGATIONS = [
    {"id": "V1", "kind": "structure", "required": True, "result": "passed",
     "scope": "binary", "evidence_artifact_id": "artifact-v1", "detail": "V1 structure"},
    {"id": "V3", "kind": "behaviour", "required": True, "result": "failed",
     "scope": "replay", "evidence_artifact_id": "artifact-v3", "detail": "V3 behaviour"},
    {"id": "V4", "kind": "symbolic", "required": True, "result": "not_run",
     "scope": "model", "evidence_artifact_id": None, "detail": "V4 symbolic"},
]

SNAPSHOT = {
    "id": "job-handoff",
    "demo": True,
    "filename": "sample.bin",
    "original_sha256": "a" * 64,
    "phase": "finished",
    "cancelled": False,
    "created_at": "2026-11-05T00:00:00+00:00",
    "contract": {"revision": 1, "sha256": "b" * 64, "approved": True},
    "routes": {
        "A": {"name": "route_a", "outcome": "inconclusive", "tests": {"passed": 0, "total": 8},
              "stages": [], "obligations": OBLIGATIONS,
              "ai_usage": {"input_tokens": 120, "output_tokens": 45}},
        "B": {"name": "route_b", "outcome": "inconclusive", "tests": {"passed": 0, "total": 8},
              "stages": [], "obligations": OBLIGATIONS, "ai_usage": None},
    },
    "verdict": {"outcome": "inconclusive", "reason": "required_check_not_run"},
}

ATTEMPTS = {
    "available": True,
    "run_id": "run-1",
    "attempts": [
        {"attempt_id": "att-1", "attempt_no": 1, "route": "route_a",
         "status": "finished", "outcome": "success_within_scope", "reason": None},
        {"attempt_id": "att-2", "attempt_no": 2, "route": "route_b",
         "status": "finished", "outcome": "inconclusive", "reason": "provider_timeout"},
    ],
}


class _HandoffBackend:
    mode = "mock"
    base_url = ""

    def get_snapshot(self, job_id: str) -> dict:
        return SNAPSHOT

    def get_obligations(self, job_id: str) -> dict:
        return {"A": OBLIGATIONS, "B": OBLIGATIONS}

    def get_attempts(self, job_id: str) -> dict:
        return ATTEMPTS

    def get_artifacts(self, job_id: str) -> dict:
        return {"A": [], "B": []}

    def export_bundle(self, job_id: str) -> dict:
        return build_export_bundle(
            SNAPSHOT, {"A": OBLIGATIONS, "B": OBLIGATIONS}, {"A": [], "B": []}, demo=True
        )


class _NoAttemptsBackend(_HandoffBackend):
    def get_attempts(self, job_id: str):
        return None


def _client(monkeypatch, backend=None) -> TestClient:
    monkeypatch.setattr(main_module, "BACKEND", backend or _HandoffBackend())
    client = TestClient(app, base_url="http://127.0.0.1")
    assert client.get("/?token=" + SESSION_TOKEN).status_code == 200
    return client


def test_persisted_scope_wins_over_the_kind_table():
    # structure is "binary" in the persisted row even though the GUI's kind table
    # would have described it as a static check.
    assert scope_display({"kind": "structure", "scope": "binary"}) == {
        "key": "binary", "zh": "二进制制品", "en": "Binary artifact", "source": "persisted"
    }
    # Without a persisted scope the fallback is labelled as such.
    assert scope_display({"kind": "structure"})["source"] == "kind"


def test_evidence_page_marks_persisted_scope_and_its_source(monkeypatch):
    page = _client(monkeypatch).get("/jobs/job-handoff/evidence")
    assert page.status_code == 200
    body = page.text
    assert 'data-evidence-scope="binary"' in body
    assert 'data-evidence-scope="replay"' in body
    assert 'data-evidence-scope="model"' in body
    assert 'data-evidence-scope-source="persisted"' in body


def test_report_page_shows_persisted_scope(monkeypatch):
    page = _client(monkeypatch).get("/jobs/job-handoff/report")
    assert page.status_code == 200
    body = page.text
    assert "Binary artifact" in body
    assert "Replay / execution" in body
    assert "Symbolic model" in body
    assert 'data-evidence-scope-source="persisted"' in body


def test_report_lists_attempts_with_stable_field_names(monkeypatch):
    page = _client(monkeypatch).get("/jobs/job-handoff/report")
    assert page.status_code == 200
    body = page.text
    assert "Attempt no." in body
    assert "att-1" in body and "att-2" in body
    assert "success_within_scope" in body
    assert "provider_timeout" in body


def test_attempts_proxy_returns_available_true(monkeypatch):
    payload = _client(monkeypatch).get("/api/jobs/job-handoff/attempts").json()
    assert payload["available"] is True
    assert payload["attempts"][0]["attempt_no"] == 1


def test_absent_attempts_endpoint_is_not_zero_attempts(monkeypatch):
    client = _client(monkeypatch, _NoAttemptsBackend())
    payload = client.get("/api/jobs/job-handoff/attempts").json()
    assert payload["available"] is False
    assert payload["attempts"] == []

    page = client.get("/jobs/job-handoff/report")
    assert page.status_code == 200
    assert "not_available" in page.text
    assert "not the same as zero attempts" in page.text or "zero attempts" in page.text
