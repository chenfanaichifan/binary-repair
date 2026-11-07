"""Upload and state-change guards.

The controller is loopback-only, but a browser page served from anywhere can
still issue a POST to 127.0.0.1. These tests pin the two defences: a cross-origin
state change is rejected, and an operator can require a token for every write.
Reads stay open so the GUI's http adapter keeps working.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.controller_api import app

FORM = {
    "defect": "strcpy in stack_buf does not check length",
    "valid_tests": "valid: hello",
    "environment": "Ubuntu x86-64 VM",
    "valid_domain": "Input length 0-64 bytes",
    "forbidden": "Out-of-bounds write to the target buffer",
    "invalid_outcome": "Return error code 1 without out-of-bounds access",
    "assumptions": "Single process",
}


@pytest.fixture
def client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.delenv("BINARYREPAIR_CONTROLLER_TOKEN", raising=False)
    monkeypatch.setenv("BINARYREPAIR_DATA_DIR", str(tmp_path / "var"))
    return TestClient(app, base_url="http://127.0.0.1")


def _create(client: TestClient, headers: dict[str, str] | None = None):
    return client.post(
        "/api/jobs",
        data=FORM,
        files={"binary": ("s.bin", b"\x7fELF auth", "application/octet-stream")},
        headers=headers or {},
    )


def test_cross_origin_upload_is_rejected(client: TestClient) -> None:
    response = _create(client, {"Origin": "http://evil.example"})
    assert response.status_code == 403
    assert "cross-origin" in response.json()["detail"]


def test_loopback_origin_upload_is_accepted(client: TestClient) -> None:
    response = _create(client, {"Origin": "http://127.0.0.1:8000"})
    assert response.status_code == 201, response.text


def test_cross_site_fetch_metadata_is_rejected(client: TestClient) -> None:
    response = _create(client, {"Sec-Fetch-Site": "cross-site"})
    assert response.status_code == 403


def test_token_is_required_for_writes_when_configured(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setenv("BINARYREPAIR_CONTROLLER_TOKEN", "s3cret")

    assert _create(client).status_code == 401
    assert _create(client, {"X-BinaryRepair-Token": "wrong"}).status_code == 401
    assert _create(client, {"X-BinaryRepair-Token": "s3cret"}).status_code == 201
    assert _create(client, {"Authorization": "Bearer s3cret"}).status_code == 201


def test_reads_do_not_require_the_token(client: TestClient, monkeypatch) -> None:
    job_id = _create(client).json()["id"]
    monkeypatch.setenv("BINARYREPAIR_CONTROLLER_TOKEN", "s3cret")

    assert client.get(f"/api/jobs/{job_id}").status_code == 200
    assert client.get("/healthz").status_code == 200


def test_state_change_endpoints_are_all_guarded(client: TestClient) -> None:
    job_id = _create(client).json()["id"]

    for path in (
        f"/api/jobs/{job_id}/approve",
        f"/api/jobs/{job_id}/runs",
        f"/api/jobs/{job_id}/start",
        f"/api/jobs/{job_id}/cancel",
        f"/api/jobs/{job_id}/analysis",
    ):
        response = client.post(path, headers={"Origin": "http://evil.example"})
        assert response.status_code == 403, (path, response.status_code, response.text)

def test_retry_is_guarded_before_any_lookup(client: TestClient) -> None:
    """The retry route is a state change even when the run id is unknown."""
    response = client.post(
        "/api/runs/does-not-exist/attempts/retry",
        json={"route": "route_a"},
        headers={"Origin": "http://evil.example"},
    )
    assert response.status_code == 403

def test_non_elf_upload_is_rejected(client: TestClient) -> None:
    """A script or archive is not a repair target; reject before it is stored."""
    response = client.post(
        "/api/jobs",
        data=FORM,
        files={"binary": ("payload.sh", b"#!/bin/sh\necho hi\n", "text/x-shellscript")},
    )
    assert response.status_code == 400
    assert "ELF" in response.json()["detail"]


def test_path_traversal_filename_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/jobs",
        data=FORM,
        files={"binary": ("../../evil.elf", b"\x7fELF traversal", "application/octet-stream")},
    )
    assert response.status_code == 400
    assert "path traversal" in response.json()["detail"]
