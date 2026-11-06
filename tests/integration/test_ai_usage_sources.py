from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.controller_api import app
from app.services import jobs
from app.services import model_calls


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
        files={"binary": ("s.elf", b"\x7fELF usage", "application/octet-stream")},
        data={"defect": "overflow"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _attempt(data: Path, job_id: str):
    job = jobs.get_job(job_id, data_dir=data)
    approval = jobs.approve_contract(
        job_id,
        contract_revision=1,
        reviewer_label="t",
        data_dir=data,
        input_sha256=job.original_sha256,
        manifest_sha256="1" * 64,
    )
    run = jobs.start_run(job_id, approval=approval, idempotency_key="usage", data_dir=data)
    return next(a for a in jobs.list_attempts(run.id, data_dir=data) if a.route == "route_a")


def _usage(client: TestClient, job_id: str):
    routes = client.get(f"/api/jobs/{job_id}").json()["routes"]
    return routes["A"]["ai_usage"]


def test_model_calls_win_over_the_plan(client: TestClient, data_dir: Path) -> None:
    job = _create(client)
    attempt = _attempt(data_dir, job["id"])
    model_calls.record_call(
        data_dir=data_dir,
        model_requested="m",
        status="ok",
        usage={"prompt_tokens": 12, "completion_tokens": 3},
        job_id=job["id"],
    )
    model_calls.record_call(
        data_dir=data_dir,
        model_requested="m",
        status="ok",
        usage={"prompt_tokens": 1, "completion_tokens": 1},
        attempt_id=attempt.id,
        route="route_a",
    )

    # Both bindings count: direct job_id rows and attempt-bound rows.
    assert _usage(client, job["id"]) == {
        "input_tokens": 13, "output_tokens": 4, "partial": False,
    }


def test_partial_model_call_is_marked_not_dropped(client: TestClient, data_dir: Path) -> None:
    job = _create(client)
    model_calls.record_call(
        data_dir=data_dir,
        model_requested="m",
        status="ok",
        usage={"prompt_tokens": 5, "completion_tokens": 7},
        job_id=job["id"],
    )
    model_calls.record_call(
        data_dir=data_dir,
        model_requested="m",
        status="failed",
        usage=None,
        job_id=job["id"],
    )

    # A NULL sibling does not erase real usage; it marks the aggregate partial.
    assert _usage(client, job["id"]) == {
        "input_tokens": 5, "output_tokens": 7, "partial": True,
    }


def test_all_null_model_calls_is_none_not_zero(client: TestClient, data_dir: Path) -> None:
    job = _create(client)
    model_calls.record_call(
        data_dir=data_dir,
        model_requested="m",
        status="failed",
        usage=None,
        job_id=job["id"],
    )
    assert _usage(client, job["id"]) is None


def test_plan_usage_is_only_a_complete_fallback(client: TestClient, data_dir: Path) -> None:
    from app.domain.assistant import deterministic_plan
    from app.services import assistant

    job = _create(client)
    plan = deterministic_plan("fix the reported binary vulnerability")
    assistant.save_plan(
        job["id"], plan, data_dir=data_dir,
        usage={"input_tokens": 3, "output_tokens": 4},
    )

    # No model_calls rows: the stored plan is the only real record, and it is
    # complete by construction.
    assert _usage(client, job["id"]) == {
        "input_tokens": 3, "output_tokens": 4, "partial": False,
    }


def test_no_usage_anywhere_is_none(client: TestClient) -> None:
    job = _create(client)
    assert _usage(client, job["id"]) is None


def test_aggregate_counts_job_and_attempt_bindings_once(data_dir: Path) -> None:
    """A route call carries attempt_id only; a plan call carries job_id only.

    Both belong to the same job, and a row that happens to carry both must
    still contribute its tokens once.
    """
    job = jobs.create_job(
        original_bytes=b"\x7fELF usage", filename="u.elf",
        defect_description="overflow", data_dir=data_dir,
    )
    attempt = _attempt(data_dir, job.id)

    model_calls.record_call(
        data_dir=data_dir, model_requested="m", status="ok",
        job_id=job.id, usage={"prompt_tokens": 2, "completion_tokens": 3},
    )
    model_calls.record_call(
        data_dir=data_dir, model_requested="m", status="ok",
        attempt_id=attempt.id, usage={"prompt_tokens": 4, "completion_tokens": 5},
    )
    model_calls.record_call(
        data_dir=data_dir, model_requested="m", status="ok",
        job_id=job.id, attempt_id=attempt.id,
        usage={"prompt_tokens": 1, "completion_tokens": 1},
    )

    assert model_calls.aggregate_job_usage(data_dir=data_dir, job_id=job.id) == {
        "input_tokens": 7,
        "output_tokens": 9,
        "partial": False,
    }


def test_aggregate_all_null_returns_none(data_dir: Path) -> None:
    """Every recorded call lacks usage: there is no real sum to report."""
    job = jobs.create_job(
        original_bytes=b"\x7fELF null", filename="n.elf",
        defect_description="overflow", data_dir=data_dir,
    )
    model_calls.record_call(
        data_dir=data_dir, model_requested="m", status="ok",
        job_id=job.id, usage=None,
    )
    model_calls.record_call(
        data_dir=data_dir, model_requested="m", status="ok",
        job_id=job.id, usage={"prompt_tokens": None, "completion_tokens": None},
    )
    assert model_calls.aggregate_job_usage(data_dir=data_dir, job_id=job.id) is None


def test_aggregate_partial_null_marks_partial(data_dir: Path) -> None:
    """Some rows carry usage, some do not: sum the real ones and say so."""
    job = jobs.create_job(
        original_bytes=b"\x7fELF partial", filename="p.elf",
        defect_description="overflow", data_dir=data_dir,
    )
    model_calls.record_call(
        data_dir=data_dir, model_requested="m", status="ok",
        job_id=job.id, usage={"prompt_tokens": 2, "completion_tokens": 3},
    )
    model_calls.record_call(
        data_dir=data_dir, model_requested="m", status="failed",
        job_id=job.id, usage=None,
    )
    assert model_calls.aggregate_job_usage(data_dir=data_dir, job_id=job.id) == {
        "input_tokens": 2,
        "output_tokens": 3,
        "partial": True,
    }


def test_aggregate_ignores_another_jobs_attempts(data_dir: Path) -> None:
    mine = jobs.create_job(
        original_bytes=b"\x7fELF mine", filename="a.elf",
        defect_description="overflow", data_dir=data_dir,
    )
    other = jobs.create_job(
        original_bytes=b"\x7fELF other", filename="b.elf",
        defect_description="overflow", data_dir=data_dir,
    )
    foreign = _attempt(data_dir, other.id)
    model_calls.record_call(
        data_dir=data_dir, model_requested="m", status="ok",
        attempt_id=foreign.id, usage={"prompt_tokens": 9, "completion_tokens": 9},
    )
    assert model_calls.aggregate_job_usage(data_dir=data_dir, job_id=mine.id) is None
