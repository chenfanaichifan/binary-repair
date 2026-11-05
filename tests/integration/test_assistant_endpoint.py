"""T8.1 contract tests: the assistant endpoint is advice, not a decision.

The plan is stored data the UI renders. Generating one must not approve the
contract, start a run, or create an obligation, and the response must be the
AssistantPlan shape M2 builds against.
"""

from __future__ import annotations

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
    monkeypatch.delenv("BINARYREPAIR_ASSISTANT_MODE", raising=False)
    return TestClient(app, base_url="http://127.0.0.1")


def _create(client: TestClient) -> dict:
    response = client.post(
        "/api/jobs",
        data=FORM,
        files={"binary": ("sample.bin", b"\x7fELF assistant bytes", "application/octet-stream")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _count(data_dir: Path, table: str) -> int:
    connection = connect(data_dir)
    try:
        return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    finally:
        connection.close()


def test_plan_is_absent_before_it_is_generated(client: TestClient) -> None:
    job = _create(client)
    response = client.get(f"/api/jobs/{job['id']}/assistant")
    assert response.status_code == 404


def test_post_returns_an_assistant_plan(client: TestClient) -> None:
    job = _create(client)
    response = client.post(f"/api/jobs/{job['id']}/assistant", json={})
    assert response.status_code == 200, response.text
    body = response.json()

    plan = body["plan"]
    assert body["mode"] == "scripted"
    assert plan["schema_version"] == 1
    assert plan["job_id"] == job["id"]
    assert plan["mode"] == "scripted"
    assert plan["steps"], "a plan with no steps is not actionable"
    for step in plan["steps"]:
        assert {"id", "title", "detail", "state"} <= set(step)
        assert step["state"] in {"next", "waiting", "done", "blocked"}

    again = client.get(f"/api/jobs/{job['id']}/assistant").json()
    assert again["id"] == body["id"]
    assert again["plan"] == plan


def test_plan_does_not_change_job_state_or_create_runs(
    client: TestClient, data_dir: Path
) -> None:
    job = _create(client)
    before = client.get(f"/api/jobs/{job['id']}").json()

    assert client.post(f"/api/jobs/{job['id']}/assistant", json={}).status_code == 200

    after = client.get(f"/api/jobs/{job['id']}").json()
    assert after["phase"] == before["phase"] == "draft"
    assert after["contract"] == before["contract"]
    assert after["contract"]["approved"] is False
    assert after["run"] is None
    assert after["verdict"] is None
    assert _count(data_dir, "runs") == 0
    assert _count(data_dir, "obligations") == 0


def test_each_post_appends_and_get_shows_the_latest(
    client: TestClient, data_dir: Path
) -> None:
    job = _create(client)
    first = client.post(f"/api/jobs/{job['id']}/assistant", json={}).json()["id"]
    second = client.post(f"/api/jobs/{job['id']}/assistant", json={}).json()["id"]

    assert first != second
    assert _count(data_dir, "assistant_plans") == 2
    assert client.get(f"/api/jobs/{job['id']}/assistant").json()["id"] == second


def test_unknown_mode_is_rejected(client: TestClient) -> None:
    job = _create(client)
    response = client.post(f"/api/jobs/{job['id']}/assistant", json={"mode": "creative"})
    assert response.status_code == 422


def test_unknown_job_is_404(client: TestClient) -> None:
    assert client.get("/api/jobs/does-not-exist/assistant").status_code == 404
    assert client.post("/api/jobs/does-not-exist/assistant", json={}).status_code == 404

def test_plan_does_not_touch_a_running_job(
    client: TestClient, data_dir: Path
) -> None:
    """With a real run in place, generation may only append assistant_plans."""
    job = _create(client)
    contract = client.get(f"/api/jobs/{job['id']}").json()["contract"]
    approval = client.post(
        f"/api/jobs/{job['id']}/approve",
        data={"expected_sha256": contract["sha256"], "reviewer_label": "t"},
    ).json()
    started = client.post(
        f"/api/jobs/{job['id']}/runs",
        json={
            "contract_revision": approval["contract_revision"],
            "manifest_sha256": approval["manifest_sha256"],
            "idempotency_key": "assistant-only",
        },
    )
    assert started.status_code in {200, 202}, started.text

    tables = ("contracts", "runs", "attempts", "obligations", "assistant_plans")
    before = {name: _count(data_dir, name) for name in tables}
    snapshot_before = client.get(f"/api/jobs/{job['id']}").json()

    assert client.post(f"/api/jobs/{job['id']}/assistant", json={}).status_code == 200

    after = {name: _count(data_dir, name) for name in tables}
    assert after["assistant_plans"] == before["assistant_plans"] + 1
    for name in ("contracts", "runs", "attempts", "obligations"):
        assert after[name] == before[name], name

    snapshot_after = client.get(f"/api/jobs/{job['id']}").json()
    assert snapshot_after["phase"] == snapshot_before["phase"]
    assert snapshot_after["contract"] == snapshot_before["contract"]
    assert snapshot_after["run"] == snapshot_before["run"]
    assert snapshot_after["verdict"] == snapshot_before["verdict"]
