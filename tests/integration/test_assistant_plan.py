from __future__ import annotations

from pathlib import Path

import pytest

from app.services import assistant, jobs


def test_scripted_plan_persists(tmp_path: Path) -> None:
    data = tmp_path / "var"
    job = jobs.create_job(original_bytes=b"\x7fELF assistant", filename="s.elf",
                          defect_description="overflow", data_dir=data)
    result = assistant.generate_plan(job.id, data_dir=data)
    assert result["mode"] == "scripted"
    assert result["plan"]["job_id"] == job.id
    assert result["plan"]["steps"]
    found = assistant.get_plan(job.id, data_dir=data)
    assert found is not None
    assert found["plan"]["summary"] == result["plan"]["summary"]


def test_unknown_assistant_mode_fails_closed(tmp_path: Path) -> None:
    data = tmp_path / "var"
    job = jobs.create_job(original_bytes=b"\x7fELF assistant", filename="s.elf",
                          defect_description="overflow", data_dir=data)
    with pytest.raises(ValueError, match="unknown assistant mode"):
        assistant.generate_plan(job.id, data_dir=data, mode="bogus")


def test_llm_seam_accepts_injected_planner(tmp_path: Path) -> None:
    from app.domain.assistant import AssistantPlan, AssistantStep
    data = tmp_path / "var"
    job = jobs.create_job(original_bytes=b"\x7fELF assistant", filename="s.elf",
                          defect_description="overflow", data_dir=data)

    def planner(*, job_id: str, data_dir, client=None):
        return assistant.save_plan(job_id, AssistantPlan(
            job_id=job_id, mode="llm", summary="injected",
            steps=[AssistantStep(id="s", title="step", detail="detail")],
        ), data_dir=data_dir, model="injected-model")

    result = assistant.generate_plan(job.id, data_dir=data, mode="llm", planner=planner)
    assert result["mode"] == "llm"
    assert result["model"] == "injected-model"


def test_get_plan_returns_latest_same_second(tmp_path: Path) -> None:
    from app.domain.assistant import AssistantPlan, AssistantStep
    data = tmp_path / "var"
    job = jobs.create_job(original_bytes=b"\x7fELF assistant", filename="s.elf",
                          defect_description="overflow", data_dir=data)

    def plan(summary: str):
        return AssistantPlan(job_id=job.id, mode="scripted", summary=summary,
                             steps=[AssistantStep(id="s", title="t", detail="d")])

    first = assistant.save_plan(job.id, plan("first"), data_dir=data)
    second = assistant.save_plan(job.id, plan("second"), data_dir=data)
    latest = assistant.get_plan(job.id, data_dir=data)
    assert first["id"] != second["id"]
    assert latest is not None
    assert latest["id"] == second["id"]
    assert latest["plan"]["summary"] == "second"


def test_messages_versions_and_model_call_link(tmp_path: Path) -> None:
    from app.domain.assistant import AssistantPlan, AssistantStep
    from app.services import model_calls
    data = tmp_path / "var"
    job = jobs.create_job(original_bytes=b"\x7fELF assistant", filename="s.elf",
                          defect_description="overflow", data_dir=data)
    message = assistant.append_message(job.id, "user", "build a plan", data_dir=data)
    plan = AssistantPlan(job_id=job.id, mode="scripted", summary="one",
                         steps=[AssistantStep(id="s", title="t", detail="d")])
    first = assistant.save_plan(job.id, plan, data_dir=data, message_id=message["id"])
    second = assistant.save_plan(job.id, plan, data_dir=data)
    assert first["version"] == 1
    assert second["version"] == 2
    assert [m["content"] for m in assistant.list_messages(job.id, data_dir=data)] == ["build a plan"]
    call_id = model_calls.record_call(
        data_dir=data, model_requested="m", status="ok",
        assistant_plan_id=first["id"], usage={"prompt_tokens": 1, "completion_tokens": 2},
    )
    from app.db.connection import connect
    connection = connect(data)
    try:
        row = connection.execute("SELECT assistant_plan_id FROM model_calls WHERE id = ?", (call_id,)).fetchone()
    finally:
        connection.close()
    assert row["assistant_plan_id"] == first["id"]
