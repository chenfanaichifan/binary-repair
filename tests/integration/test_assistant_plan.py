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


class _FakeResponse:
    content = '{"schema_version":1,"job_id":"__JOB__","mode":"llm","summary":"llm plan","steps":[{"id":"s","title":"step","detail":"do it","state":"next"}],"questions":[]}'
    model = "fake-model"
    usage = {"prompt_tokens": 10, "completion_tokens": 5}


class _FakeClient:
    def chat_json(self, messages, **kwargs):
        return _FakeResponse


def test_llm_plan_is_saved_with_usage(tmp_path: Path) -> None:
    data = tmp_path / "var"
    job = jobs.create_job(original_bytes=b"\x7fELF assistant", filename="s.elf",
                          defect_description="overflow", data_dir=data)
    _FakeResponse.content = _FakeResponse.content.replace("__JOB__", job.id)
    result = assistant.generate_plan(job.id, data_dir=data, mode="llm", client=_FakeClient())
    assert result["mode"] == "llm"
    assert result["model"] == "fake-model"
    assert result["usage"]["prompt_tokens"] == 10
