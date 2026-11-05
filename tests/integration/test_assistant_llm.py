from __future__ import annotations

from pathlib import Path

from app.services import assistant_llm, jobs

_PLAN_TEMPLATE = '{"schema_version":1,"job_id":"__JOB__","mode":"llm","summary":"llm plan","steps":[{"id":"s","title":"step","detail":"do it","state":"next"}],"questions":[]}'


class _FakeResponse:
    content = _PLAN_TEMPLATE
    model = "fake-model"
    usage = {"prompt_tokens": 10, "completion_tokens": 5}


class _FakeClient:
    def chat_json(self, messages, **kwargs):
        return _FakeResponse


def _job(tmp_path: Path):
    data = tmp_path / "var"
    job = jobs.create_job(original_bytes=b"\x7fELF assistant", filename="s.elf",
                          defect_description="overflow", data_dir=data)
    return data, job


def test_llm_plan_is_saved_with_usage(tmp_path: Path) -> None:
    data, job = _job(tmp_path)
    _FakeResponse.content = _PLAN_TEMPLATE.replace("__JOB__", job.id)
    result = assistant_llm.generate_llm_plan(job_id=job.id, data_dir=data, client=_FakeClient())
    assert result["mode"] == "llm"
    assert result["model"] == "fake-model"
    assert result["usage"]["prompt_tokens"] == 10


def test_llm_call_is_recorded_for_usage(tmp_path: Path) -> None:
    data, job = _job(tmp_path)
    _FakeResponse.content = _PLAN_TEMPLATE.replace("__JOB__", job.id)
    result = assistant_llm.generate_llm_plan(job_id=job.id, data_dir=data, client=_FakeClient())
    from app.services import model_calls
    usage = model_calls.aggregate_usage(data_dir=data, route="assistant")
    assert usage == {"input_tokens": 10, "output_tokens": 5}
    assert result["usage"]["model_call_id"]
