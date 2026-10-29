"""UI tests for provisional/superseded evidence and artifact-id usage."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

import app.main as main


def _snapshot(provisional_source: bool = True, verdict: dict | None = None) -> dict:
    obligations = [
        {"id": "V0", "kind": "identity", "result": "passed", "description": "identity"},
        {"id": "V1", "kind": "structure", "result": "passed", "description": "structure"},
        {"id": "V2", "kind": "interface", "result": "not_run", "description": "interface"},
        {"id": "V3", "kind": "behaviour", "result": "passed", "description": "behaviour"},
        {"id": "V4", "kind": "symbolic", "result": "not_run", "description": "symbolic"},
        {"id": "V5", "kind": "reproducibility", "result": "not_run", "description": "reproducibility"},
    ]
    obligations[1]["evidence_artifact_id"] = "abc123def456"
    obligations[2]["evidence_path"] = "route_a/audit.json"
    route_a = {
        "name": "Route A",
        "phase": "finished",
        "outcome": "inconclusive",
        "outcome_reason": "required_check_not_run",
        "stages": [],
        "tests": {"passed": 0, "total": 0},
        "verification": "not_run",
        "compatibility": "not_run",
        "changed_regions": [],
        "manual_interventions": 0,
        "ai_usage": "unavailable",
        "elapsed_s": 0.0,
        "verdict": verdict
        or {
            "outcome": "inconclusive",
            "reason": "required_check_not_run",
            "failing_obligation": "interface",
            "detail": "V2 interface: not_run",
        },
        "obligations": obligations,
    }
    snapshot = {
        "id": "job-ui-test",
        "demo": False,
        "filename": "sample.bin",
        "original_sha256": "a" * 64,
        "defect": "fixture",
        "valid_tests": [],
        "environment": "test",
        "created_at": "2026-10-22T00:00:00+00:00",
        "phase": "finished" if verdict else "running",
        "cancelled": False,
        "contract": {
            "revision": 1,
            "sha256": "b" * 64,
            "approved": True,
            "valid_domain": "d",
            "forbidden": "f",
            "invalid_outcome": "i",
            "assumptions": [],
        },
        "run": {"id": "run-1", "phase": "finished", "manifest_sha256": "c" * 64, "reviewed_scope_sha256": "d" * 64},
        "verdict": verdict,
        "routes": {"A": route_a, "B": dict(route_a)},
    }
    if provisional_source:
        snapshot["source_sha256"] = "8256c8501afd95c02b371a99a507c436e5e431f49bdc5e4641b9a3bab2cbe64f"
    return snapshot


class _FakeBackend:
    mode = "mock"
    supports_start = True

    def __init__(self, snapshot: dict) -> None:
        self.snapshot = snapshot

    def get_snapshot(self, job_id: str):
        return self.snapshot

    def get_visuals(self, job_id: str):
        return {"available": False, "note": "test"}

    def get_obligations(self, job_id: str):
        return {}

    def get_artifacts(self, job_id: str):
        return {"A": [], "B": []}

    def get_artifact(self, artifact_id: str):
        return {
            "id": artifact_id,
            "name": "audit.json",
            "role": "route_a_audit",
            "sha256": "e" * 64,
            "size_bytes": 123,
        }


def _client() -> TestClient:
    client = TestClient(main.app, base_url="http://127.0.0.1")
    assert client.get("/?token=" + main.SESSION_TOKEN).status_code == 200
    return client


def test_not_run_is_not_rendered_as_pass_and_no_success(monkeypatch):
    monkeypatch.setattr(main, "BACKEND", _FakeBackend(_snapshot()))
    text = _client().get("/jobs/job-ui-test/evidence").text
    assert "result-not_run" in text
    assert "V2" in text and "not_run" in text
    assert "成功（声明范围内）" not in text
    assert "success_within_scope" not in text


def test_no_decision_renders_pending(monkeypatch):
    snapshot = _snapshot(verdict=None)
    monkeypatch.setattr(main, "BACKEND", _FakeBackend(snapshot))
    text = _client().get("/jobs/job-ui-test").text
    assert "尚无 verdict" in text
    assert "成功（声明范围内）" not in text


def test_superseded_source_shows_provisional_warning(monkeypatch):
    monkeypatch.setattr(main, "BACKEND", _FakeBackend(_snapshot()))
    text = _client().get("/jobs/job-ui-test/evidence").text
    assert "PROVISIONAL" in text
    assert "8256c850" in text
    assert "不覆盖 Gate 3 approved" in text
    assert "P3A checker PASS" in text


def test_artifact_id_is_the_view_key_and_paths_are_display_only(monkeypatch):
    monkeypatch.setattr(main, "BACKEND", _FakeBackend(_snapshot()))
    text = _client().get("/jobs/job-ui-test/evidence").text
    assert 'href="/artifacts/abc123def456"' in text
    assert "route_a/audit.json" in text
    # The path must not become a link key or an artifact id.
    assert 'href="/artifacts/route_a/audit.json"' not in text
    assert not re.search(r"artifact-link-[^\\n]*route_a/audit\\.json", text)


def test_artifact_view_uses_artifact_id(monkeypatch):
    monkeypatch.setattr(main, "BACKEND", _FakeBackend(_snapshot()))
    page = _client().get("/artifacts/abc123def456")
    assert page.status_code == 200
    assert "abc123def456" in page.text
    assert "audit.json" in page.text
    assert "route_a/audit.json" not in page.text
