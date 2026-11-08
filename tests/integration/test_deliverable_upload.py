"""Operator deliverable upload: storage/download only, never acceptance evidence."""

from __future__ import annotations

import hashlib

import pytest
from fastapi.testclient import TestClient

from app.controller_api import app

FORM = {
    "defect": "strcpy in stack_buf does not check length; overlong input writes out of bounds",
    "valid_tests": "valid: hello",
    "environment": "Ubuntu x86-64 VM (test: execution disabled)",
    "valid_domain": "Input length 0-64 bytes",
    "forbidden": "Out-of-bounds write",
    "invalid_outcome": "Return error code 1",
    "assumptions": "Single process",
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("BINARYREPAIR_DATA_DIR", str(tmp_path / "var"))
    return TestClient(app, base_url="http://127.0.0.1")


def _create(client: TestClient) -> str:
    response = client.post(
        "/api/jobs",
        data=FORM,
        files={"binary": ("sample.bin", b"\x7fELF demo bytes", "application/octet-stream")},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_deliverable_is_registered_and_downloadable(client: TestClient) -> None:
    job_id = _create(client)
    payload = b"\x7fELF" + b"repaired" * 32
    response = client.post(
        f"/api/jobs/{job_id}/deliverables",
        files={"file": ("repaired.elf", payload, "application/x-elf")},
    )
    assert response.status_code == 201, response.text
    artifact = response.json()["artifact"]
    assert artifact["role"] == "operator_deliverable"
    assert artifact["sha256"] == hashlib.sha256(payload).hexdigest()
    assert artifact["available"] is True

    download = client.get(f"/api/jobs/{job_id}/artifacts/{artifact['id']}/download")
    assert download.status_code == 200
    assert download.content == payload

    # No run/attempt/verdict is created by a deliverable upload.
    snapshot = client.get(f"/api/jobs/{job_id}").json()
    assert snapshot["phase"] == "draft"
    assert snapshot["verdict"] is None


def test_deliverable_rejects_non_elf(client: TestClient) -> None:
    job_id = _create(client)
    response = client.post(
        f"/api/jobs/{job_id}/deliverables",
        files={"file": ("notes.txt", b"not an elf", "text/plain")},
    )
    assert response.status_code == 400
