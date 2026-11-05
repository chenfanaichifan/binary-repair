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
