"""Contract tests for the controller-only HTTP API."""

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


def test_create_and_snapshot(client: TestClient) -> None:
    created = _create(client)
    snapshot = client.get(f"/api/jobs/{created['id']}")
    assert snapshot.status_code == 200
    payload = snapshot.json()
    assert payload["phase"] == "draft"
    assert set(payload["routes"]) == {"A", "B"}
    assert payload["original_sha256"] == created["original_sha256"]
    assert payload["valid_tests"] == ["valid: hello", "boundary: 8 bytes"]
    assert not CJK.search(snapshot.text)


def test_start_alias_is_idempotent(client: TestClient) -> None:
    job_id = _create(client)["id"]
    first = client.post(f"/api/jobs/{job_id}/start")
    second = client.post(f"/api/jobs/{job_id}/start")
    assert first.status_code == second.status_code == 202
    assert first.json()["id"] == second.json()["id"]
    assert client.get(f"/api/jobs/{job_id}").json()["phase"] == "queued"


def test_canonical_approve_and_runs(client: TestClient) -> None:
    created = _create(client)
    job_id = created["id"]
    approve = client.post(
        f"/api/jobs/{job_id}/approve",
        json={
            "input_sha256": created["original_sha256"],
            "contract_revision": 1,
            "manifest_sha256": "1" * 64,
            "scope_sha256": "2" * 64,
            "reviewer_label": "test",
        },
    )
    assert approve.status_code == 200, approve.text
    run = client.post(
        f"/api/jobs/{job_id}/runs",
        json={"contract_revision": 1, "idempotency_key": "canonical-1"},
    )
    assert run.status_code == 202, run.text
    assert run.json()["phase"] == "queued"


def test_runs_requires_approval(client: TestClient) -> None:
    job_id = _create(client)["id"]
    response = client.post(
        f"/api/jobs/{job_id}/runs",
        json={"contract_revision": 1, "idempotency_key": "missing-approval"},
    )
    assert response.status_code == 409


def test_obligations_artifacts_and_attempt_404(client: TestClient) -> None:
    created = _create(client)
    job_id = created["id"]
    obligations = client.get(f"/api/jobs/{job_id}/obligations")
    assert obligations.status_code == 200
    assert obligations.json()["A"][0]["id"] == "V0"
    assert obligations.json()["A"][1]["result"] == "not_run"

    artifacts = client.get(f"/api/jobs/{job_id}/artifacts")
    assert artifacts.status_code == 200
    assert artifacts.json()["A"][0]["sha256"] == created["original_sha256"]

    attempt = client.get("/api/attempts/does-not-exist/evidence")
    assert attempt.status_code == 404


def test_cancel_blocks_start(client: TestClient) -> None:
    job_id = _create(client)["id"]
    assert client.post(f"/api/jobs/{job_id}/cancel").status_code == 202
    snapshot = client.get(f"/api/jobs/{job_id}").json()
    assert snapshot["phase"] == "cancelled"
    assert snapshot["cancelled"] is True
    assert client.post(f"/api/jobs/{job_id}/start").status_code == 409


def test_non_ascii_and_host_check(client: TestClient) -> None:
    response = client.post(
        "/api/jobs",
        data={**FORM, "defect": "越界写"},
        files={"binary": ("sample.bin", b"\x7fELF demo bytes", "application/octet-stream")},
    )
    assert response.status_code == 422
    assert client.get("/healthz", headers={"host": "evil.example"}).status_code == 403
