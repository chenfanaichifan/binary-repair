"""``POST /api/assistant/plan``: a plan from text, with or without a job.

The response is the shape M2 renders: the ``AssistantPlan`` body plus an
``agent`` block explaining how it was produced. Persisting is the only side
effect, and only when a job id exists.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.controller_api import app
from app.db.connection import connect

DESCRIPTION = "strcpy writes past stack_buf when the input exceeds 64 bytes"


@pytest.fixture
def data_dir(tmp_path) -> Path:
    return tmp_path / "var"


@pytest.fixture
def client(data_dir, monkeypatch) -> TestClient:
    monkeypatch.setenv("BINARYREPAIR_DATA_DIR", str(data_dir))
    monkeypatch.delenv("BINARYREPAIR_ASSISTANT_MODE", raising=False)
    return TestClient(app, base_url="http://127.0.0.1")


def _count(data_dir: Path, table: str) -> int:
    connection = connect(data_dir)
    try:
        return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        connection.close()


def _create(client: TestClient) -> dict:
    response = client.post(
        "/api/jobs",
        files={
            "binary": ("target.elf", b"\x7fELF" + b"\x00" * 60, "application/octet-stream")
        },
        data={"defect": DESCRIPTION},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_plan_without_a_job_is_a_preview(client: TestClient, data_dir: Path) -> None:
    response = client.post("/api/assistant/plan", json={"description": DESCRIPTION})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["job_id"] is None
    assert body["persisted"] is False
    assert body["plan"]["steps"][-1]["kind"] == "review"
    assert set(body["agent"]) == {
        "mode",
        "fallback",
        "fallback_reason",
        "model",
        "tokens",
    }
    assert body["agent"]["mode"] == "deterministic"
    assert body["agent"]["fallback"] is False
    assert _count(data_dir, "assistant_plans") == 0


def test_plan_without_input_is_rejected(client: TestClient) -> None:
    assert client.post("/api/assistant/plan", json={}).status_code == 422
    assert (
        client.post("/api/assistant/plan", json={"description": "   "}).status_code
        == 422
    )


def test_plan_with_a_job_is_stored_once(
    client: TestClient, data_dir: Path
) -> None:
    job = _create(client)
    before = {name: _count(data_dir, name) for name in ("contracts", "runs", "obligations")}

    response = client.post(
        "/api/assistant/plan", json={"job_id": job["id"], "description": DESCRIPTION}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["job_id"] == job["id"]
    assert body["persisted"] is True
    assert _count(data_dir, "assistant_plans") == 1
    for name, count in before.items():
        assert _count(data_dir, name) == count, name
    assert client.get(f"/api/jobs/{job['id']}").json()["verdict"] is None


def test_plan_with_a_job_uses_the_job_description(client: TestClient) -> None:
    job = _create(client)
    response = client.post("/api/assistant/plan", json={"job_id": job["id"]})
    assert response.status_code == 200, response.text
    assert response.json()["plan"]["steps"]


def test_llm_mode_without_a_client_is_503(
    client: TestClient, data_dir: Path
) -> None:
    response = client.post(
        "/api/assistant/plan", json={"description": DESCRIPTION, "mode": "llm"}
    )

    # No client is configured, so there is no LLM plan. Returning a
    # deterministic one with a fallback flag would let the caller believe the
    # LLM path ran.
    assert response.status_code == 503, response.text
    assert response.json() == {
        "plan": None,
        "error": "assistant_unavailable",
        "fallback_reason": "no LLM client is configured on this host",
    }
    assert _count(data_dir, "assistant_plans") == 0


def test_llm_mode_with_a_job_is_also_503(
    client: TestClient, data_dir: Path
) -> None:
    job = _create(client)
    response = client.post(
        "/api/assistant/plan",
        json={"job_id": job["id"], "description": DESCRIPTION, "mode": "llm"},
    )

    assert response.status_code == 503, response.text
    assert response.json()["error"] == "assistant_unavailable"
    assert _count(data_dir, "assistant_plans") == 0


def test_the_contract_context_field_is_accepted(client: TestClient) -> None:
    response = client.post(
        "/api/assistant/plan",
        json={"description": DESCRIPTION, "context": {"stage": "defect", "n": 2}},
    )

    assert response.status_code == 200, response.text
    assert response.json()["plan"]["steps"]


def test_scripted_label_maps_to_deterministic(client: TestClient) -> None:
    response = client.post(
        "/api/assistant/plan", json={"description": DESCRIPTION, "mode": "scripted"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["agent"]["mode"] == "deterministic"


def test_unknown_mode_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/assistant/plan", json={"description": DESCRIPTION, "mode": "creative"}
    )
    assert response.status_code == 422


def test_unknown_job_is_404(client: TestClient) -> None:
    response = client.post(
        "/api/assistant/plan", json={"job_id": "does-not-exist", "description": DESCRIPTION}
    )
    assert response.status_code == 404
