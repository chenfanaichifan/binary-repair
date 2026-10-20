"""Contract tests for the controller HTTP API."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app.controller_api import app

FORM = {
    "defect": "strcpy in stack_buf does not check length; overlong input writes out of bounds",
    "valid_tests": "valid: hello\nboundary: 8 bytes",
    "environment": "Ubuntu x86-64 VM (test: execution disabled)",
    "valid_domain": "Input length 0-64 bytes",
    "forbidden": "Out-of-bounds write to the target buffer",
    "invalid_outcome": "Return error code 1 without out-of-bounds access",
    "assumptions": "Single process\nStack protector disabled",
}
CJK = re.compile(r"[\u2e80-\u2fff\u3000-\u303f\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef]")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("BINARYREPAIR_DATA_DIR", str(tmp_path / "var"))
    return TestClient(app, base_url="http://127.0.0.1")


def _create(client: TestClient) -> dict:
    response = client.post(
        "/api/jobs",
        data=FORM,
        files={"binary": ("sample.bin", b"\x7fELF demo bytes", "application/octet-stream")},
    )
    assert response.status_code == 201, response.text
    assert not CJK.search(response.text)
    return response.json()


def test_create_and_snapshot_contract(client: TestClient) -> None:
    created = _create(client)
    job_id = created["id"]
    assert len(created["original_sha256"]) == 64

    snapshot = client.get(f"/api/jobs/{job_id}")
    assert snapshot.status_code == 200
    payload = snapshot.json()
    for key in ("id", "phase", "routes", "contract", "original_sha256", "valid_tests"):
        assert key in payload
    assert set(payload["routes"]) == {"A", "B"}
    assert payload["phase"] == "draft"
    assert payload["demo"] is False
    assert not CJK.search(snapshot.text)


def test_start_is_idempotent(client: TestClient) -> None:
    job_id = _create(client)["id"]

    first = client.post(f"/api/jobs/{job_id}/start")
    second = client.post(f"/api/jobs/{job_id}/start")
    assert first.status_code == second.status_code == 202
    assert first.json()["id"] == second.json()["id"]

    snapshot = client.get(f"/api/jobs/{job_id}").json()
    assert snapshot["phase"] == "queued"
    assert snapshot["execution"] == "queued"


def test_obligations_and_artifacts(client: TestClient) -> None:
    created = _create(client)
    job_id = created["id"]

    obligations = client.get(f"/api/jobs/{job_id}/obligations")
    assert obligations.status_code == 200
    data = obligations.json()
    assert set(data) == {"A", "B"}
    assert data["A"][0]["id"] == "V0"
    assert data["A"][0]["result"] == "passed"
    assert data["A"][1]["result"] == "not_run"
    assert not CJK.search(obligations.text)

    artifacts = client.get(f"/api/jobs/{job_id}/artifacts")
    assert artifacts.status_code == 200
    assert artifacts.json()["A"][0]["sha256"] == created["original_sha256"]


def test_cancel_and_restart_state(client: TestClient, tmp_path, monkeypatch) -> None:
    job_id = _create(client)["id"]
    started = client.post(f"/api/jobs/{job_id}/start")
    assert started.status_code == 202

    cancelled = client.post(f"/api/jobs/{job_id}/cancel")
    assert cancelled.status_code == 202
    snapshot = client.get(f"/api/jobs/{job_id}").json()
    assert snapshot["phase"] == "cancelled"
    assert snapshot["cancelled"] is True

    blocked = client.post(f"/api/jobs/{job_id}/start")
    assert blocked.status_code == 409

    # A new client (new connections) sees the same persisted state.
    restarted = TestClient(app, base_url="http://127.0.0.1")
    assert restarted.get(f"/api/jobs/{job_id}").json()["phase"] == "cancelled"


def test_missing_job_returns_404(client: TestClient) -> None:
    response = client.get("/api/jobs/does-not-exist")
    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found."


def test_non_ascii_form_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/jobs",
        data={**FORM, "defect": "stack buffer overflow"},
        files={"binary": ("sample.bin", b"\x7fELF demo bytes", "application/octet-stream")},
    )
    assert response.status_code == 201

    response = client.post(
        "/api/jobs",
        data={**FORM, "defect": "越界写"},
        files={"binary": ("sample.bin", b"\x7fELF demo bytes", "application/octet-stream")},
    )
    assert response.status_code == 422


def test_host_check(client: TestClient) -> None:
    response = client.get("/healthz", headers={"host": "evil.example"})
    assert response.status_code == 403
