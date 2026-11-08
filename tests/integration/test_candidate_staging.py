"""T6.6: a provider proposal is staged input, never a repair result.

These tests pin the boundary: staging writes a file and nothing else. No run, no
attempt, no obligation, and no verdict may appear, and the record says
``candidate: false`` so nobody can read it as evaluated.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.controller_api import app
from app.db.connection import connect
from app.services import candidate_staging

FORM = {
    "defect": "strcpy in stack_buf does not check length; overlong input writes out of bounds",
    "valid_tests": "valid: hello",
    "environment": "Ubuntu x86-64 VM (test: execution disabled)",
    "valid_domain": "Input length 0-64 bytes",
    "forbidden": "Out-of-bounds write to the target buffer",
    "invalid_outcome": "Return error code 1 without out-of-bounds access",
    "assumptions": "Single process",
}

PROPOSAL = "--- a/stack.c\n+++ b/stack.c\n@@\n-  strcpy(buf, input);\n+  snprintf(buf, sizeof buf, \"%s\", input);\n"


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
        files={"binary": ("sample.bin", b"\x7fELF staging bytes", "application/octet-stream")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _count(data_dir: Path, table: str) -> int:
    connection = connect(data_dir)
    try:
        return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    finally:
        connection.close()


def test_staging_records_input_not_a_result(client: TestClient) -> None:
    job = _create(client)
    response = client.post(
        f"/api/jobs/{job['id']}/proposals",
        json={"text": PROPOSAL, "source": "provider", "model": "demo-model"},
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["status"] == "staged"
    assert body["candidate"] is False
    assert body["verdict"] is None
    assert body["obligations_evaluated"] == 0
    assert body["bytes"] == len(PROPOSAL.encode("utf-8"))
    assert body["model"] == "demo-model"
    assert body["deduplicated"] is False


def test_staging_creates_no_run_attempt_or_verdict(
    client: TestClient, data_dir: Path
) -> None:
    job = _create(client)
    before = client.get(f"/api/jobs/{job['id']}").json()

    assert client.post(
        f"/api/jobs/{job['id']}/proposals", json={"text": PROPOSAL}
    ).status_code == 200

    after = client.get(f"/api/jobs/{job['id']}").json()
    assert after["phase"] == before["phase"] == "draft"
    assert after["verdict"] is None
    assert after["run"] is None
    assert _count(data_dir, "runs") == 0
    assert _count(data_dir, "attempts") == 0
    assert _count(data_dir, "obligations") == 0


def test_same_text_is_deduplicated(client: TestClient, data_dir: Path) -> None:
    job = _create(client)
    first = client.post(f"/api/jobs/{job['id']}/proposals", json={"text": PROPOSAL}).json()
    second = client.post(f"/api/jobs/{job['id']}/proposals", json={"text": PROPOSAL}).json()

    assert first["id"] == second["id"]
    assert second["deduplicated"] is True
    stored = list(candidate_staging.proposals_dir(data_dir, job["id"]).glob("*.json"))
    assert len(stored) == 1


def test_proposals_are_listed_newest_first(client: TestClient) -> None:
    job = _create(client)
    client.post(f"/api/jobs/{job['id']}/proposals", json={"text": PROPOSAL})
    client.post(f"/api/jobs/{job['id']}/proposals", json={"text": PROPOSAL + "/* two */\n"})

    listed = client.get(f"/api/jobs/{job['id']}/proposals").json()["proposals"]
    assert len(listed) == 2
    assert listed[0]["created_at"] >= listed[1]["created_at"]


def test_empty_proposal_is_rejected(client: TestClient) -> None:
    job = _create(client)
    assert client.post(f"/api/jobs/{job['id']}/proposals", json={"text": ""}).status_code == 422
    assert client.post(f"/api/jobs/{job['id']}/proposals", json={"text": "   "}).status_code == 400


def test_oversized_proposal_is_rejected(client: TestClient) -> None:
    job = _create(client)
    too_big = "x" * (candidate_staging.MAX_PROPOSAL_BYTES + 1)
    assert client.post(f"/api/jobs/{job['id']}/proposals", json={"text": too_big}).status_code == 400


def test_unknown_job_is_404(client: TestClient) -> None:
    assert client.get("/api/jobs/nope/proposals").status_code == 404
    assert client.post("/api/jobs/nope/proposals", json={"text": PROPOSAL}).status_code == 404


def test_proposal_id_cannot_escape_the_staging_directory(data_dir: Path) -> None:
    with pytest.raises(ValueError):
        candidate_staging.get_proposal("job", "../escape", data_dir=data_dir)
