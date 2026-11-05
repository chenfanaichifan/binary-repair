from __future__ import annotations

import json
from pathlib import Path

from app.services import assistant_llm, jobs

_PLAN = {
    "plan_id": "llm-plan", "mode": "llm", "fallback": False,
    "fallback_reason": None, "model": "fake-model",
    "tokens": None,
    "steps": [
        {"id": "sample", "kind": "upload", "title": "Sample", "prompt": "Upload."},
        {"id": "review", "kind": "review", "title": "Review", "prompt": "Review."},
    ],
}


class _FakeResponse:
    content = json.dumps(_PLAN)
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


def test_llm_plan_is_validated_and_has_tokens(tmp_path: Path) -> None:
    data, job = _job(tmp_path)
    plan = assistant_llm.generate_plan(
        "fix", context={"job_id": job.id, "data_dir": str(data)}, client=_FakeClient()
    )
    assert plan.mode == "llm"
    assert plan.model == "fake-model"
    assert plan.tokens == {"prompt": 10, "completion": 5}


def test_llm_call_is_recorded_for_usage(tmp_path: Path) -> None:
    data, job = _job(tmp_path)
    plan = assistant_llm.generate_plan(
        "fix", context={"job_id": job.id, "data_dir": str(data)}, client=_FakeClient()
    )
    from app.db.connection import connect
    connection = connect(data)
    try:
        row = connection.execute(
            "SELECT job_id, plan_id FROM model_calls WHERE route = 'assistant'"
        ).fetchone()
    finally:
        connection.close()
    assert row["job_id"] == job.id
    assert row["plan_id"] == plan.plan_id
