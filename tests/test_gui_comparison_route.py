"""GUI JSON comparison route: 200/not_provided, 200/invalid, 404 only for unknown job."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import main
from app.backend import BackendError
from app.main import SESSION_TOKEN, app


class FakeBackend:
    mode = "mock"
    supports_start = False

    def __init__(self, *, row: dict[str, Any] | None = None, content: bytes = b"",
                 missing_job: bool = False) -> None:
        self.row = row
        self.content = content
        self.missing_job = missing_job

    def get_snapshot(self, job_id: str) -> dict[str, Any]:
        if self.missing_job:
            raise BackendError(404, "job not found")
        return {"id": job_id, "demo": False}

    def get_artifacts(self, job_id: str) -> dict[str, list[dict[str, Any]]]:
        return {"A": [self.row] if self.row else [], "B": []}

    def get_artifact_bytes(self, artifact_id: str):
        return self.content, "application/json", "behavior-comparison.json"


def _payload() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "original_sha256": "a" * 64,
        "candidate_sha256": "b" * 64,
        "scope": "behavior_only",
        "cases": [
            {
                "id": "case-1",
                "kind": "known_good",
                "input_sha256": None,
                "original": {
                    "returncode": 0,
                    "stdout_sha256": "c" * 64,
                    "stderr_sha256": "d" * 64,
                    "timed_out": False,
                },
                "candidate": {
                    "returncode": 0,
                    "stdout_sha256": "c" * 64,
                    "stderr_sha256": "d" * 64,
                    "timed_out": False,
                },
                "verdict": "same",
                "detail": "",
            }
        ],
        "summary": {"total": 1, "same": 1, "different": 0, "not_run": 0, "unknown": 0},
        "not_claimed": ["not a repair verdict", "same is not acceptance evidence"],
    }


def _row(content: bytes) -> dict[str, Any]:
    return {
        "id": "artifact-1",
        "role": "behavior_comparison",
        "available": True,
        "sha256": hashlib.sha256(content).hexdigest(),
        "name": "behavior-comparison.json",
    }


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("BINARYREPAIR_SESSION_TOKEN", SESSION_TOKEN)
    c = TestClient(app, base_url="http://127.0.0.1")
    c.cookies.set("br_session", SESSION_TOKEN)
    return c


def _set_backend(monkeypatch, backend: FakeBackend) -> None:
    monkeypatch.setattr(main, "BACKEND", backend)


def test_missing_artifact_is_200_not_provided(client, monkeypatch) -> None:
    _set_backend(monkeypatch, FakeBackend())
    response = client.get("/api/jobs/job-1/comparison")
    assert response.status_code == 200
    assert response.json()["status"] == "not_provided"
    assert response.json()["comparison"] is None


def test_valid_artifact_is_available(client, monkeypatch) -> None:
    content = json.dumps(_payload()).encode()
    _set_backend(monkeypatch, FakeBackend(row=_row(content), content=content))
    response = client.get("/api/jobs/job-1/comparison")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "available"
    assert body["comparison"]["cases"]
    assert body["comparison"]["summary"]["total"] == 1


def test_hash_mismatch_is_invalid(client, monkeypatch) -> None:
    content = json.dumps(_payload()).encode()
    _set_backend(monkeypatch, FakeBackend(row=_row(content), content=content + b" "))
    response = client.get("/api/jobs/job-1/comparison")
    assert response.status_code == 200
    assert response.json()["status"] == "invalid"
    assert response.json()["comparison"] is None


def test_bad_json_is_invalid(client, monkeypatch) -> None:
    content = b"not-json"
    _set_backend(monkeypatch, FakeBackend(row=_row(content), content=content))
    response = client.get("/api/jobs/job-1/comparison")
    assert response.status_code == 200
    assert response.json()["status"] == "invalid"


def test_unknown_job_is_404(client, monkeypatch) -> None:
    _set_backend(monkeypatch, FakeBackend(missing_job=True))
    response = client.get("/api/jobs/nope/comparison")
    assert response.status_code == 404


def test_no_session_is_401(monkeypatch) -> None:
    _set_backend(monkeypatch, FakeBackend())
    c = TestClient(app, base_url="http://127.0.0.1")
    response = c.get("/api/jobs/job-1/comparison")
    assert response.status_code == 401
