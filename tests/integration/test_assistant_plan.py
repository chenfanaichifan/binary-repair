from __future__ import annotations

from pathlib import Path

import pytest

from app.domain.assistant import AssistantPlan, AssistantQuestion, AssistantStep
from app.services import assistant, jobs


def _job(tmp_path: Path):
    data = tmp_path / "var"
    job = jobs.create_job(original_bytes=b"\x7fELF assistant", filename="s.elf",
                          defect_description="overflow", data_dir=data)
    return data, job


def test_deterministic_plan_contract(tmp_path: Path) -> None:
    data, job = _job(tmp_path)
    plan = assistant.generate_plan("fix the overflow", job_id=job.id, data_dir=data)
    assert isinstance(plan, AssistantPlan)
    assert plan.mode == "deterministic"
    assert plan.fallback is False
    assert 1 <= len(plan.steps) <= 6
    assert plan.steps[-1].kind == "review"
    assert len({step.id for step in plan.steps}) == len(plan.steps)
    assert all(step.prompt for step in plan.steps)
    for step in plan.steps:
        if step.kind == "question":
            assert step.questions
            assert len({q.key for q in step.questions}) == len(step.questions)
        for question in step.questions:
            assert question.default is None or question.default.isascii()
    found = assistant.get_plan(job.id, data_dir=data)
    assert found is not None
    assert found["plan"]["plan_id"] == plan.plan_id
    assert found["version"] == 1


def test_unknown_assistant_mode_fails_closed(tmp_path: Path) -> None:
    data, job = _job(tmp_path)
    with pytest.raises(ValueError, match="unknown assistant mode"):
        assistant.generate_plan("x", job_id=job.id, data_dir=data, mode="bogus")


def test_llm_seam_accepts_injected_planner(tmp_path: Path) -> None:
    data, job = _job(tmp_path)

    def planner(*, description, context=None, client=None):
        return AssistantPlan(
            plan_id="injected-plan", mode="llm", fallback=False,
            steps=[AssistantStep(id="r", kind="review", title="Review", prompt="Review.")],
            model="injected-model",
        )

    plan = assistant.generate_plan("x", job_id=job.id, data_dir=data, planner=planner)
    assert plan.mode == "llm"
    assert plan.model == "injected-model"
    found = assistant.get_plan(job.id, data_dir=data)
    assert found["plan"]["plan_id"] == "injected-plan"


def test_plan_versions_and_superseded(tmp_path: Path) -> None:
    data, job = _job(tmp_path)
    first = assistant.generate_plan("one", job_id=job.id, data_dir=data)
    second = assistant.generate_plan("two", job_id=job.id, data_dir=data)
    latest = assistant.get_plan(job.id, data_dir=data)
    assert latest["version"] == 2
    assert latest["plan"]["plan_id"] == second.plan_id
    assert latest["superseded_by"] is None
    # version 1 is retained and marked superseded by version 2.
    from app.db.connection import connect
    connection = connect(data)
    try:
        row = connection.execute(
            "SELECT superseded_by FROM assistant_plans WHERE id = ?", (first.plan_id,)
        ).fetchone()
    finally:
        connection.close()
    assert row["superseded_by"] == second.plan_id


def test_messages_and_model_call_link(tmp_path: Path) -> None:
    from app.services import model_calls
    data, job = _job(tmp_path)
    message = assistant.append_message(job.id, "user", "build a plan", data_dir=data)
    plan = assistant.generate_plan("plan", job_id=job.id, data_dir=data)
    assert [m["content"] for m in assistant.list_messages(job.id, data_dir=data)] == ["build a plan"]
    call_id = model_calls.record_call(
        data_dir=data, model_requested="m", status="ok",
        job_id=job.id, plan_id=plan.plan_id,
        usage={"prompt_tokens": 1, "completion_tokens": 2},
    )
    from app.db.connection import connect
    connection = connect(data)
    try:
        row = connection.execute(
            "SELECT job_id, plan_id FROM model_calls WHERE id = ?", (call_id,)
        ).fetchone()
    finally:
        connection.close()
    assert row["job_id"] == job.id
    assert row["plan_id"] == plan.plan_id


def test_generate_plan_context_contains_data_dir(tmp_path: Path) -> None:
    data, job = _job(tmp_path)
    seen = {}

    def planner(*, description, context=None, client=None):
        seen.update(context or {})
        return AssistantPlan(
            plan_id="ctx-plan", mode="llm",
            steps=[AssistantStep(id="r", kind="review", title="Review", prompt="Review.")],
        )

    assistant.generate_plan("x", job_id=job.id, data_dir=data, planner=planner)
    assert seen["data_dir"] == str(data)
    assert seen["job_id"] == job.id
