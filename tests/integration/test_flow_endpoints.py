"""Contract tests for the T7.1 flow endpoints.

These pin the *shape* the agent console (M2) can build against, and they pin the
honesty rules: a job nobody screened reports ``not_provided``, a request is not a
result, and a comparison is rendered only from an artifact that really exists.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.controller_api import app
from app.db.connection import connect

FORM = {
    "defect": "strcpy in stack_buf does not check length; overlong input writes out of bounds",
    "valid_tests": "valid: hello",
    "environment": "Ubuntu x86-64 VM (test: execution disabled)",
    "valid_domain": "Input length 0-64 bytes",
    "forbidden": "Out-of-bounds write to the target buffer",
    "invalid_outcome": "Return error code 1 without out-of-bounds access",
    "assumptions": "Single process",
}


@pytest.fixture
def data_dir(tmp_path) -> Path:
    return tmp_path / "var"


@pytest.fixture
def client(data_dir, monkeypatch) -> TestClient:
    monkeypatch.setenv("BINARYREPAIR_DATA_DIR", str(data_dir))
    return TestClient(app, base_url="http://127.0.0.1")


def _create(client: TestClient) -> dict:
    response = client.post(
        "/api/jobs",
        data=FORM,
        files={"binary": ("sample.bin", b"\x7fELF flow bytes", "application/octet-stream")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _approve(client: TestClient, job_id: str) -> dict:
    contract = client.get(f"/api/jobs/{job_id}").json()["contract"]
    response = client.post(
        f"/api/jobs/{job_id}/approve",
        data={"expected_sha256": contract["sha256"], "reviewer_label": "test-reviewer"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _register(data_dir: Path, job_id: str, role: str, name: str, payload: bytes) -> str:
    """Simulate what M5's ingest adapter does: write bytes, insert the row."""
    artifact_id = uuid.uuid4().hex
    relative = f"analysis/{name}"
    target = data_dir / "jobs" / job_id / "artifacts" / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    connection = connect(data_dir)
    try:
        connection.execute(
            "INSERT INTO artifacts "
            "(id, job_id, attempt_id, relative_path, sha256, size_bytes, media_type, role, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                artifact_id,
                job_id,
                None,
                relative,
                hashlib.sha256(payload).hexdigest(),
                len(payload),
                "application/json",
                role,
                "2026-11-05T00:00:00+00:00",
            ),
        )
        connection.commit()
    finally:
        connection.close()
    return artifact_id


def test_snapshot_reports_the_agent_step_and_derived_execution(client: TestClient) -> None:
    job_id = _create(client)["id"]

    payload = client.get(f"/api/jobs/{job_id}").json()

    agent = payload["agent"]
    assert agent["current_step"] == "intake"
    assert agent["source"] == "controller-derived"
    assert [step["id"] for step in agent["steps"]] == [
        "intake",
        "contract",
        "screening",
        "repair",
        "verification",
        "done",
    ]
    assert agent["steps"][0]["state"] == "active"
    assert all(step["state"] == "pending" for step in agent["steps"][1:])

    execution = payload["execution"]
    assert execution["status"] == "not_started"
    assert execution["source"] == "controller-derived"
    # No sidecar exists in this build; the field stays explicit rather than absent.
    assert execution["sidecar"] is None
    assert payload["execution_phase"] == "not_started"


def test_agent_advances_to_contract_then_repair(client: TestClient) -> None:
    job_id = _create(client)["id"]
    approval = _approve(client, job_id)

    assert client.get(f"/api/jobs/{job_id}").json()["agent"]["current_step"] == "contract"

    started = client.post(
        f"/api/jobs/{job_id}/runs",
        json={
            "contract_revision": approval["contract_revision"],
            "manifest_sha256": approval["manifest_sha256"],
            "idempotency_key": "flow-1",
        },
    )
    assert started.status_code in {200, 202}, started.text

    payload = client.get(f"/api/jobs/{job_id}").json()
    assert payload["agent"]["current_step"] == "repair"
    assert payload["agent"]["steps"][3]["state"] == "active"
    assert payload["execution"]["status"] == "queued"
    assert payload["execution"]["run_id"]


def test_cancelled_job_reports_cancelled_execution(client: TestClient) -> None:
    job_id = _create(client)["id"]
    approval = _approve(client, job_id)
    client.post(
        f"/api/jobs/{job_id}/runs",
        json={
            "contract_revision": approval["contract_revision"],
            "manifest_sha256": approval["manifest_sha256"],
            "idempotency_key": "flow-cancel",
        },
    )

    assert client.post(f"/api/jobs/{job_id}/cancel").status_code in {200, 202}

    payload = client.get(f"/api/jobs/{job_id}").json()
    assert payload["execution"]["status"] == "cancelled"
    assert payload["agent"]["current_step"] == "done"


def test_analysis_starts_as_not_provided(client: TestClient) -> None:
    job_id = _create(client)["id"]

    response = client.get(f"/api/jobs/{job_id}/analysis")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "not_provided"
    assert payload["purpose"] == "screening"
    assert payload["artifacts"] == []
    assert payload["screening"] is None


def test_analysis_request_needs_an_approved_contract(client: TestClient) -> None:
    job_id = _create(client)["id"]

    response = client.post(f"/api/jobs/{job_id}/analysis")

    assert response.status_code == 409
    assert "approve" in response.json()["detail"].lower()


def test_analysis_request_is_recorded_and_idempotent(client: TestClient) -> None:
    job_id = _create(client)["id"]
    _approve(client, job_id)

    first = client.post(f"/api/jobs/{job_id}/analysis")
    assert first.status_code == 202, first.text
    assert first.json()["status"] == "requested"
    requested_at = first.json()["requested_at"]
    assert requested_at

    second = client.post(f"/api/jobs/{job_id}/analysis")
    assert second.status_code == 200
    assert second.json()["requested_at"] == requested_at

    # A request is not a result.
    fetched = client.get(f"/api/jobs/{job_id}/analysis").json()
    assert fetched["status"] == "requested"
    assert fetched["artifacts"] == []
    assert client.get(f"/api/jobs/{job_id}").json()["agent"]["current_step"] == "screening"


def test_analysis_becomes_available_only_with_artifacts(
    client: TestClient, data_dir: Path
) -> None:
    job_id = _create(client)["id"]
    _approve(client, job_id)
    client.post(f"/api/jobs/{job_id}/analysis")

    artifact_id = _register(
        data_dir,
        job_id,
        "analysis_expected_effects",
        "screening.json",
        json.dumps({"expected_effects": 3}).encode("utf-8"),
    )

    payload = client.get(f"/api/jobs/{job_id}/analysis").json()
    assert payload["status"] == "available"
    assert [item["id"] for item in payload["artifacts"]] == [artifact_id]
    assert payload["artifacts"][0]["available"] is True
    # The producer's summary is not invented by the controller.
    assert payload["screening"] is None


def test_comparison_is_not_provided_without_an_artifact(client: TestClient) -> None:
    job_id = _create(client)["id"]

    payload = client.get(f"/api/jobs/{job_id}/comparison").json()

    assert payload["status"] == "not_provided"
    assert payload["comparison"] is None
    assert payload["artifacts"] == []


def test_comparison_renders_an_ingested_artifact(
    client: TestClient, data_dir: Path
) -> None:
    job_id = _create(client)["id"]
    body = {"cases": [{"name": "valid", "original": "pass", "candidate": "pass"}]}
    _register(
        data_dir,
        job_id,
        "behavior_comparison",
        "behavior-comparison.json",
        json.dumps(body).encode("utf-8"),
    )

    payload = client.get(f"/api/jobs/{job_id}/comparison").json()

    assert payload["status"] == "available"
    assert payload["comparison"] == body
    assert len(payload["artifacts"]) == 1


def test_comparison_reports_unreadable_json_instead_of_failing(
    client: TestClient, data_dir: Path
) -> None:
    job_id = _create(client)["id"]
    _register(
        data_dir,
        job_id,
        "behavior_comparison",
        "broken.json",
        b"{not json",
    )

    payload = client.get(f"/api/jobs/{job_id}/comparison").json()

    assert payload["status"] == "available"
    assert payload["comparison"] is None
    assert "not readable JSON" in payload["detail"]


def test_analysis_is_scoped_to_its_own_job(client: TestClient, data_dir: Path) -> None:
    first = _create(client)["id"]
    second = _create(client)["id"]
    _register(
        data_dir,
        first,
        "analysis_assumptions",
        "only-first.json",
        b'{"assumptions": []}',
    )

    assert client.get(f"/api/jobs/{first}/analysis").json()["status"] == "available"
    assert client.get(f"/api/jobs/{second}/analysis").json()["status"] == "not_provided"
    assert client.get(f"/api/jobs/{second}/comparison").json()["status"] == "not_provided"


def test_unknown_job_is_404_on_every_flow_endpoint(client: TestClient) -> None:
    for method, path in (
        ("get", "/api/jobs/does-not-exist/analysis"),
        ("post", "/api/jobs/does-not-exist/analysis"),
        ("get", "/api/jobs/does-not-exist/comparison"),
    ):
        response = getattr(client, method)(path)
        assert response.status_code == 404, (method, path, response.text)
