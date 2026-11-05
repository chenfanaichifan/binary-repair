"""Direct tests for the controller's ``_ai_usage_for_job`` helper.

The helper is the single place that turns stored records into the ``ai_usage``
block, so its four outcomes and its two row bindings are pinned here rather
than inferred from the rendered GUI route.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.controller_api import _ai_usage_for_job
from app.domain.assistant import deterministic_plan
from app.services import jobs, model_calls
from app.services.assistant import save_plan


@pytest.fixture
def data_dir(tmp_path, monkeypatch) -> Path:
    path = tmp_path / "var"
    monkeypatch.setenv("BINARYREPAIR_DATA_DIR", str(path))
    monkeypatch.delenv("BINARYREPAIR_ASSISTANT_MODE", raising=False)
    return path


def _job(data_dir: Path):
    return jobs.create_job(
        original_bytes=b"\x7fELF usage helper",
        filename="u.elf",
        defect_description="overflow",
        data_dir=data_dir,
    )


def _attempt(data_dir: Path, job) -> object:
    approval = jobs.approve_contract(
        job.id,
        contract_revision=1,
        reviewer_label="t",
        data_dir=data_dir,
        input_sha256=job.original_sha256,
        manifest_sha256="1" * 64,
    )
    run = jobs.start_run(
        job.id, approval=approval, idempotency_key="usage-helper", data_dir=data_dir
    )
    return next(a for a in jobs.list_attempts(run.id, data_dir=data_dir) if a.route == "route_a")


def test_complete_rows_are_summed_and_not_partial(data_dir: Path) -> None:
    job = _job(data_dir)
    model_calls.record_call(
        data_dir=data_dir, model_requested="m", status="ok", job_id=job.id,
        usage={"prompt_tokens": 10, "completion_tokens": 4},
    )
    model_calls.record_call(
        data_dir=data_dir, model_requested="m", status="ok", job_id=job.id,
        usage={"prompt_tokens": 2, "completion_tokens": 1},
    )

    assert _ai_usage_for_job(job.id) == {
        "input_tokens": 12,
        "output_tokens": 5,
        "partial": False,
    }


def test_a_null_row_keeps_the_real_sum_and_passes_partial_through(data_dir: Path) -> None:
    job = _job(data_dir)
    model_calls.record_call(
        data_dir=data_dir, model_requested="m", status="ok", job_id=job.id,
        usage={"prompt_tokens": 9, "completion_tokens": 3},
    )
    model_calls.record_call(
        data_dir=data_dir, model_requested="m", status="ok", job_id=job.id,
        usage={"prompt_tokens": 5},
    )

    # The NULL row is not zero and does not erase the sibling; it only marks
    # the sum incomplete.
    assert _ai_usage_for_job(job.id) == {
        "input_tokens": 9,
        "output_tokens": 3,
        "partial": True,
    }


def test_all_rows_null_is_none(data_dir: Path) -> None:
    job = _job(data_dir)
    model_calls.record_call(
        data_dir=data_dir, model_requested="m", status="ok", job_id=job.id,
        usage={"prompt_tokens": 5},
    )
    model_calls.record_call(
        data_dir=data_dir, model_requested="m", status="ok", job_id=job.id,
        usage={},
    )

    assert _ai_usage_for_job(job.id) is None


def test_attempt_bound_rows_are_counted(data_dir: Path) -> None:
    job = _job(data_dir)
    attempt = _attempt(data_dir, job)
    model_calls.record_call(
        data_dir=data_dir, model_requested="m", status="ok",
        attempt_id=attempt.id, route="route_a",
        usage={"prompt_tokens": 6, "completion_tokens": 2},
    )

    assert _ai_usage_for_job(job.id) == {
        "input_tokens": 6,
        "output_tokens": 2,
        "partial": False,
    }


def test_assistant_rows_bound_by_job_id_are_counted(data_dir: Path) -> None:
    job = _job(data_dir)
    plan = deterministic_plan("overflow")
    stored = save_plan(job.id, plan, data_dir=data_dir)
    model_calls.record_call(
        data_dir=data_dir, model_requested="m", status="ok",
        job_id=job.id, assistant_plan_id=stored["id"],
        usage={"prompt_tokens": 8, "completion_tokens": 3},
    )

    assert _ai_usage_for_job(job.id) == {
        "input_tokens": 8,
        "output_tokens": 3,
        "partial": False,
    }


def test_plan_fallback_reports_not_partial(data_dir: Path) -> None:
    job = _job(data_dir)
    save_plan(
        job.id, deterministic_plan("overflow"), data_dir=data_dir,
        usage={"input_tokens": 7, "output_tokens": 2},
    )

    # No model_calls rows: one stored plan record, so nothing can be missing.
    assert _ai_usage_for_job(job.id) == {
        "input_tokens": 7,
        "output_tokens": 2,
        "partial": False,
    }
