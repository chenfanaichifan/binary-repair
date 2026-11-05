"""T8.2 LLM planner seam：传输层可注入，任何失败都明确回退。"""

from __future__ import annotations

import json

import pytest

from app.services import assistant_llm


VALID_PLAN = {
    "mode": "llm",
    "steps": [
        {
            "id": "sample",
            "title": "样本",
            "kind": "upload",
            "prompt": "上传待修复的 ELF 样本。",
            "questions": [],
        },
        {
            "id": "defect",
            "title": "缺陷",
            "kind": "question",
            "prompt": "描述该二进制当前的缺陷。",
            "questions": [
                {"key": "defect", "label": "缺陷描述", "required": True, "ascii": True},
                {"key": "valid_tests", "label": "合法输入", "required": True, "ascii": True,
                 "input": "textarea"},
            ],
        },
        {"id": "review", "title": "复核", "kind": "review", "prompt": "确认后由你点击创建。"},
    ],
}


class FakeClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def complete(self, messages, *, model):
        self.calls.append({"messages": messages, "model": model})
        if self.error is not None:
            raise self.error
        return self.response


def _ok(plan):
    return {
        "content": json.dumps(plan),
        "model": "deepseek-chat",
        "usage": {"prompt_tokens": 11, "completion_tokens": 22, "total_tokens": 33,
                  "latency_ms": 480},
        "request_id": "req-1",
    }


def test_non_llm_mode_never_calls_the_client():
    client = FakeClient(_ok(VALID_PLAN))
    outcome = assistant_llm.generate_plan("fix it", client=client, mode="deterministic")
    assert outcome.mode == "deterministic"
    assert outcome.plan is None
    assert outcome.fallback is False
    assert client.calls == []


def test_llm_mode_without_client_falls_back_and_says_why():
    outcome = assistant_llm.generate_plan("fix it", mode="llm")
    assert outcome.mode == "llm"
    assert outcome.plan is None
    assert outcome.fallback is True
    assert outcome.fallback_reason == assistant_llm.FallbackReason.NO_CLIENT


def test_unknown_mode_is_treated_as_deterministic():
    assert assistant_llm.resolve_mode("totally-new-mode") == "deterministic"
    assert assistant_llm.resolve_mode("LLM") == "llm"


def test_successful_plan_passes_validation_and_records_usage():
    client = FakeClient(_ok(VALID_PLAN))
    outcome = assistant_llm.generate_plan("fix it", client=client, mode="llm")

    assert outcome.fallback is False
    assert outcome.plan is not None
    assert outcome.plan["mode"] == "llm"
    assert outcome.usage["prompt_tokens"] == 11
    assert outcome.usage["total_tokens"] == 33
    assert outcome.model_returned == "deepseek-chat"
    assert outcome.request_id == "req-1"

    row = outcome.as_model_call_row(call_id="c1", created_at="2026-11-05T00:00:00Z")
    assert row["status"] == "ok"
    assert row["model_requested"] == "deepseek-chat"
    assert row["total_tokens"] == 33
    assert json.loads(row["usage_json"])["prompt_chars"] > 0
    # 记录里不能出现 prompt 原文，更不能出现凭据。
    assert "fix it" not in row["usage_json"]
    assert "sk-" not in json.dumps(row)


def test_fenced_json_is_accepted_but_still_parsed():
    client = FakeClient({
        "content": "```json\n" + json.dumps(VALID_PLAN) + "\n```",
        "model": "deepseek-chat",
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    })
    outcome = assistant_llm.generate_plan("fix it", client=client, mode="llm")
    assert outcome.fallback is False
    assert outcome.plan["steps"][0]["id"] == "sample"


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        ({"content": ""}, assistant_llm.FallbackReason.EMPTY),
        ({"content": "{not json"}, assistant_llm.FallbackReason.MALFORMED),
        ({"content": "[1,2,3]"}, assistant_llm.FallbackReason.SCHEMA),
        ({"content": json.dumps({"steps": []})}, assistant_llm.FallbackReason.SCHEMA),
        ({"content": "plain text"}, assistant_llm.FallbackReason.MALFORMED),
    ],
)
def test_bad_content_always_falls_back(response, reason):
    outcome = assistant_llm.generate_plan("fix it", client=FakeClient(response), mode="llm")
    assert outcome.fallback is True
    assert outcome.plan is None
    assert outcome.fallback_reason == reason


def test_transport_errors_are_typed_and_contain_no_raw_text():
    timeout = assistant_llm.generate_plan(
        "fix it", client=FakeClient(error=TimeoutError("boom")), mode="llm"
    )
    assert timeout.fallback_reason == assistant_llm.FallbackReason.TIMEOUT

    network = assistant_llm.generate_plan(
        "fix it", client=FakeClient(error=ConnectionError("dns")), mode="llm"
    )
    assert network.fallback_reason == assistant_llm.FallbackReason.NETWORK

    unknown = assistant_llm.generate_plan(
        "fix it", client=FakeClient(error=RuntimeError("sk-leaked")), mode="llm"
    )
    assert unknown.fallback_reason == assistant_llm.FallbackReason.UNKNOWN
    assert "sk-leaked" not in json.dumps(
        unknown.as_model_call_row(call_id="c", created_at="t")
    )


def test_plan_with_unknown_step_kind_is_rejected_not_guessed():
    plan = {
        "steps": [{"id": "x", "title": "x", "kind": "magic", "prompt": "?"}],
    }
    errors = assistant_llm.validate_plan(plan)
    assert any("kind" in error for error in errors)

    outcome = assistant_llm.generate_plan(
        "fix it", client=FakeClient({"content": json.dumps(plan)}), mode="llm"
    )
    assert outcome.fallback is True
    assert outcome.fallback_reason == assistant_llm.FallbackReason.SCHEMA


def test_duplicate_step_ids_and_missing_prompt_are_rejected():
    plan = {
        "steps": [
            {"id": "a", "title": "A", "kind": "upload", "prompt": "p"},
            {"id": "a", "title": "B", "kind": "upload", "prompt": ""},
        ]
    }
    errors = assistant_llm.validate_plan(plan)
    assert any("duplicated" in error for error in errors)
    assert any("prompt" in error for error in errors)


def test_prompt_carries_no_credential_and_states_the_boundary():
    messages = assistant_llm.build_messages("fix it", context={"job_id": "j1"})
    system = messages[0]["content"]
    assert "never create jobs" in system
    assert "never judge repairs" in system
    assert "sk-" not in system
    assert messages[1]["role"] == "user"


def test_assistant_status_is_honest_about_not_being_wired():
    status = assistant_llm.assistant_status(mode="llm", client_configured=False)
    assert status["mode"] == "llm"
    assert status["available"] is False
    assert status["fallback_reason"] == assistant_llm.FallbackReason.NO_CLIENT

    ready = assistant_llm.assistant_status(mode="llm", client_configured=True)
    assert ready["available"] is True
    assert ready["fallback_reason"] is None
