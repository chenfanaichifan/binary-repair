"""T8.2 assistant LLM seam: valid plan, fallback, no key leak."""

from __future__ import annotations

import json
from pathlib import Path

from app.domain.assistant import AssistantPlan, deterministic_plan
from app.services import assistant_llm


class Response:
    content: str
    model = "fake-model"
    usage = {"prompt_tokens": 7, "completion_tokens": 3}


class Client:
    def __init__(self, payload: dict | str) -> None:
        self.payload = payload

    def chat_json(self, messages, *, max_tokens, thinking=False):
        response = Response()
        response.content = self.payload if isinstance(self.payload, str) else json.dumps(self.payload)
        return response


def _payload() -> dict:
    plan = deterministic_plan("repair")
    data = plan.model_dump()
    data["mode"] = "llm"
    data["fallback"] = False
    data["fallback_reason"] = None
    return data


def test_no_client_falls_back_to_deterministic() -> None:
    plan = assistant_llm.generate_plan("repair", context={})
    assert isinstance(plan, AssistantPlan)
    assert plan.mode == "deterministic"
    assert plan.fallback is True
    assert "no LLM client" in (plan.fallback_reason or "")


def test_invalid_llm_output_falls_back_without_secret() -> None:
    plan = assistant_llm.generate_plan("repair", context={}, client=Client("not-json"))
    assert plan.fallback is True
    assert "JSONDecodeError" in (plan.fallback_reason or "")
    assert "sk-" not in json.dumps(plan.model_dump())


def test_valid_llm_plan_and_tokens(monkeypatch, tmp_path: Path) -> None:
    calls: list[dict] = []
    monkeypatch.setattr(
        assistant_llm.model_calls,
        "record_call",
        lambda **kwargs: calls.append(kwargs) or "call-id",
    )
    plan = assistant_llm.generate_plan(
        "repair",
        context={"data_dir": str(tmp_path), "job_id": "j1"},
        client=Client(_payload()),
    )
    assert plan.mode == "llm"
    assert plan.fallback is False
    assert plan.tokens == {"prompt": 7, "completion": 3}
    assert plan.model == "fake-model"
    assert calls and calls[0]["job_id"] == "j1"
