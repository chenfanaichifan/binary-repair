"""T8.2 LLM planner: fake transport, schema fallback, and usage audit.

Owner: M2.  The seam under test is ``app/services/assistant.py``:
``generate_plan(..., client=..., planner=...)``.  The LLM branch must return an
``AssistantPlan`` even when the model fails, and each attempt must leave one
``model_calls`` row whose token fields are real counts or NULL.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.db.connection import connect
from app.domain.assistant import AssistantPlan
from app.services import assistant, jobs, model_calls
from app.services import assistant_llm
from app.services.assistant_llm import (
    FallbackReason,
    assistant_status,
    build_messages,
    generate_plan,
    validate_plan,
)


def _payload() -> dict:
    return {
        "plan_id": "plan-fake",
        "mode": "llm",
        "fallback": False,
        "fallback_reason": None,
        "model": None,
        "tokens": None,
        "steps": [
            {"id": "sample", "kind": "upload", "title": "Step 1", "prompt": "Upload."},
            {"id": "defect", "kind": "question", "title": "Step 2", "prompt": "Describe.",
             "questions": [{"key": "defect", "label": "Defect", "input": "textarea",
                            "required": True, "ascii": True, "default": "ok"}]},
            {"id": "review", "kind": "review", "title": "Review", "prompt": "Review."},
        ],
    }


class FakeTransport:
    """M5 provider shape: ``chat_json`` returning an object with content/model/usage."""

    def __init__(self, content, *, model="fake-model", usage=None, error=None):
        self.content = content
        self.model = model
        self.usage = usage
        self.error = error
        self.calls: list = []

    def chat_json(self, messages, *, max_tokens=0, thinking=False):
        self.calls.append({"messages": messages, "max_tokens": max_tokens, "thinking": thinking})
        if self.error is not None:
            raise self.error
        return SimpleNamespace(content=self.content, model=self.model, usage=self.usage)


class LegacyTransport:
    """The draft's ``complete`` protocol; kept so neither adapter is lost."""

    def __init__(self, content, *, usage=None):
        self.content = content
        self.usage = usage
        self.calls: list = []

    def complete(self, messages, *, model):
        self.calls.append({"messages": messages, "model": model})
        return {"content": self.content, "model": "legacy-model", "usage": self.usage}


def _rows(data_dir: Path) -> list[dict]:
    connection = connect(data_dir)
    try:
        rows = connection.execute(
            "SELECT status, route, model_requested, model_returned, prompt_tokens, "
            "completion_tokens, total_tokens, latency_ms, plan_id, job_id, usage_json "
            "FROM model_calls ORDER BY rowid"
        ).fetchall()
    finally:
        connection.close()
    return [dict(row) for row in rows]


def _job(tmp_path: Path):
    data = tmp_path / "var"
    job = jobs.create_job(original_bytes=b"\x7fELF assistant", filename="s.elf",
                          defect_description="overflow", data_dir=data)
    return data, job


# --- happy path -------------------------------------------------------------

def test_fake_transport_returns_a_validated_plan():
    transport = FakeTransport(_payload(), usage={"prompt_tokens": 11, "completion_tokens": 4,
                                                 "total_tokens": 15})
    plan = generate_plan("fix it", client=transport)
    assert isinstance(plan, AssistantPlan)
    assert plan.mode == "llm"
    assert plan.fallback is False
    assert plan.plan_id == "plan-fake"
    assert plan.model == "fake-model"
    assert plan.tokens == {"prompt": 11, "completion": 4}
    assert plan.steps[-1].kind == "review"
    assert transport.calls[0]["thinking"] is True


def test_legacy_complete_transport_still_works():
    plan = generate_plan("fix it", client=LegacyTransport(_payload()))
    assert plan.model == "legacy-model"
    assert plan.fallback is False


def test_missing_plan_id_is_filled_server_side():
    payload = _payload()
    del payload["plan_id"]
    plan = generate_plan("fix it", client=FakeTransport(payload))
    assert plan.plan_id
    assert plan.fallback is False


def test_blank_plan_id_is_replaced():
    payload = _payload()
    payload["plan_id"] = "   "
    plan = generate_plan("fix it", client=FakeTransport(payload))
    assert plan.plan_id.strip()
    assert plan.fallback is False


def test_model_claimed_accounting_is_overwritten():
    payload = _payload()
    payload["tokens"] = {"prompt": 999, "completion": 999}
    payload["model"] = "model-says-this"
    transport = FakeTransport(payload, model="real-model",
                              usage={"prompt_tokens": 7, "completion_tokens": 3})
    plan = generate_plan("fix it", client=transport)
    assert plan.model == "real-model"
    assert plan.tokens == {"prompt": 7, "completion": 3}


def test_model_cannot_claim_a_fallback():
    payload = _payload()
    payload["fallback"] = True
    payload["fallback_reason"] = "model self-report"
    plan = generate_plan("fix it", client=FakeTransport(payload))
    assert plan.fallback is False
    assert plan.fallback_reason is None


# --- fallback paths ---------------------------------------------------------

@pytest.mark.parametrize("content,reason", [
    ("", FallbackReason.EMPTY),
    ("not json", FallbackReason.MALFORMED),
    ("[1,2,3]", FallbackReason.SCHEMA),
])
def test_bad_content_falls_back(content, reason):
    plan = generate_plan("fix it", client=FakeTransport(content))
    assert isinstance(plan, AssistantPlan)
    assert plan.mode == "llm"
    assert plan.fallback is True
    assert plan.fallback_reason == reason
    assert plan.steps[-1].kind == "review"


def test_review_must_be_last():
    payload = _payload()
    payload["steps"] = [payload["steps"][2], payload["steps"][0]]
    plan = generate_plan("fix it", client=FakeTransport(payload))
    assert plan.fallback is True
    assert plan.fallback_reason == FallbackReason.SCHEMA


def test_unknown_kind_falls_back():
    payload = _payload()
    payload["steps"][0]["kind"] = "guess"
    plan = generate_plan("fix it", client=FakeTransport(payload))
    assert plan.fallback is True
    assert plan.fallback_reason == FallbackReason.SCHEMA


def test_fenced_json_is_accepted():
    transport = FakeTransport("```json\n" + __import__("json").dumps(_payload()) + "\n```")
    plan = generate_plan("fix it", client=transport)
    assert plan.fallback is False


@pytest.mark.parametrize("error,reason", [
    (TimeoutError("slow"), FallbackReason.TIMEOUT),
    (ConnectionError("down"), FallbackReason.NETWORK),
    (RuntimeError("boom"), FallbackReason.UNKNOWN),
])
def test_transport_errors_become_stable_reasons(error, reason):
    plan = generate_plan("fix it", client=FakeTransport("", error=error))
    assert plan.fallback is True
    assert plan.fallback_reason == reason


def test_client_without_a_transport_is_not_configured():
    plan = generate_plan("fix it", client=object())
    assert plan.fallback is True
    assert plan.fallback_reason == FallbackReason.NO_CLIENT


def test_no_client_falls_back_without_throwing():
    plan = generate_plan("fix it", client=None)
    assert plan.fallback is True
    assert plan.fallback_reason == FallbackReason.NO_CLIENT


def test_deterministic_mode_never_calls_the_model():
    transport = FakeTransport(_payload())
    plan = generate_plan("fix it", client=transport, mode="deterministic")
    assert plan.mode == "deterministic"
    assert plan.fallback is False
    assert transport.calls == []


# --- model_calls audit ------------------------------------------------------

def test_successful_call_records_real_tokens(tmp_path: Path):
    data, job = _job(tmp_path)
    transport = FakeTransport(_payload(), usage={"prompt_tokens": 21, "completion_tokens": 5,
                                                 "total_tokens": 26})
    plan = generate_plan("fix it", client=transport,
                         context={"data_dir": str(data), "job_id": job.id})
    rows = _rows(data)
    assert len(rows) == 1
    row = rows[0]
    assert row["status"] == assistant_llm.STATUS_OK
    assert row["route"] == "assistant"
    assert row["model_requested"]
    assert row["model_returned"] == "fake-model"
    assert row["prompt_tokens"] == 21
    assert row["completion_tokens"] == 5
    assert row["total_tokens"] == 26
    assert row["plan_id"] == plan.plan_id
    assert row["job_id"] == job.id


def test_missing_usage_is_null_not_zero(tmp_path: Path):
    data, job = _job(tmp_path)
    plan = generate_plan("fix it", client=FakeTransport(_payload()),
                         context={"data_dir": str(data), "job_id": job.id})
    assert plan.tokens is None
    row = _rows(data)[0]
    assert row["prompt_tokens"] is None
    assert row["completion_tokens"] is None
    assert row["total_tokens"] is None


def test_total_only_usage_does_not_become_a_token_pair(tmp_path: Path):
    data, job = _job(tmp_path)
    plan = generate_plan("fix it", client=FakeTransport(_payload(), usage={"total_tokens": 9}),
                         context={"data_dir": str(data), "job_id": job.id})
    assert plan.tokens is None
    row = _rows(data)[0]
    assert row["prompt_tokens"] is None
    assert row["completion_tokens"] is None
    assert row["total_tokens"] == 9


def test_one_sided_usage_is_kept_but_never_completed(tmp_path: Path):
    # A half-reported usage row must stay half-reported: it feeds the job-level
    # "partial" flag instead of being completed with zeros.
    data, job = _job(tmp_path)
    plan = generate_plan("fix it", client=FakeTransport(_payload(), usage={"prompt_tokens": 11}),
                         context={"data_dir": str(data), "job_id": job.id})
    assert plan.tokens is None
    row = _rows(data)[0]
    assert row["prompt_tokens"] == 11
    assert row["completion_tokens"] is None
    assert row["total_tokens"] is None
    assert json.loads(row["usage_json"]) == {"prompt_tokens": 11}


def test_aggregate_marks_partial_when_a_sibling_row_has_no_usage(tmp_path: Path):
    # T8.2 seam + canonical d1ce352 aggregate: one row has real tokens, one is
    # NULL. The sum must survive and be marked partial, never completed with 0.
    data, job = _job(tmp_path)
    generate_plan("fix it",
                  client=FakeTransport(_payload(), usage={"prompt_tokens": 21,
                                                          "completion_tokens": 5}),
                  context={"data_dir": str(data), "job_id": job.id})
    generate_plan("fix it", client=FakeTransport(_payload()),
                  context={"data_dir": str(data), "job_id": job.id})
    assert model_calls.aggregate_job_usage(data_dir=data, job_id=job.id) == {
        "input_tokens": 21, "output_tokens": 5, "partial": True,
    }


def test_aggregate_is_null_when_every_row_lacks_usage(tmp_path: Path):
    # "未提供" is null, not 0: a job with only missing usage has no sum.
    data, job = _job(tmp_path)
    generate_plan("fix it", client=FakeTransport(_payload()),
                  context={"data_dir": str(data), "job_id": job.id})
    assert model_calls.aggregate_job_usage(data_dir=data, job_id=job.id) is None


def test_aggregate_is_complete_when_every_row_has_usage(tmp_path: Path):
    data, job = _job(tmp_path)
    for _ in range(2):
        generate_plan("fix it",
                      client=FakeTransport(_payload(), usage={"prompt_tokens": 3,
                                                              "completion_tokens": 2}),
                      context={"data_dir": str(data), "job_id": job.id})
    assert model_calls.aggregate_job_usage(data_dir=data, job_id=job.id) == {
        "input_tokens": 6, "output_tokens": 4, "partial": False,
    }


def test_latency_goes_to_its_own_column(tmp_path: Path):
    data, job = _job(tmp_path)
    plan = generate_plan("fix it", client=FakeTransport(_payload(), usage={"latency_ms": 42}),
                         context={"data_dir": str(data), "job_id": job.id})
    assert plan.tokens is None
    row = _rows(data)[0]
    assert row["latency_ms"] == 42
    assert row["usage_json"] is None


def test_fallback_is_recorded_as_fallback(tmp_path: Path):
    data, job = _job(tmp_path)
    plan = generate_plan("fix it", client=FakeTransport("", error=TimeoutError()),
                         context={"data_dir": str(data), "job_id": job.id})
    row = _rows(data)[0]
    assert row["status"] == assistant_llm.STATUS_FALLBACK
    assert row["plan_id"] == plan.plan_id
    assert row["prompt_tokens"] is None
    assert row["usage_json"] is None


# --- the M5 seam ------------------------------------------------------------

def test_seam_persists_the_llm_plan(tmp_path: Path):
    data, job = _job(tmp_path)
    transport = FakeTransport(_payload())
    # No explicit context: M5's seam (c50ca04) fills data_dir/job_id itself.
    plan = assistant.generate_plan(
        "fix the overflow", job_id=job.id, data_dir=data, client=transport,
    )
    assert plan.mode == "llm"
    assert plan.fallback is False
    found = assistant.get_plan(job.id, data_dir=data)
    assert found is not None
    assert found["plan"]["plan_id"] == "plan-fake"
    assert found["model"] == "fake-model"


def test_seam_context_carries_the_audit_target(tmp_path: Path):
    data, job = _job(tmp_path)
    context = assistant.assistant_context(job, data_dir=data)
    assert context["job_id"] == job.id
    assert context["data_dir"] == str(data)


def test_seam_records_usage_against_the_job_without_an_explicit_context(tmp_path: Path):
    data, job = _job(tmp_path)
    transport = FakeTransport(_payload(), usage={"prompt_tokens": 3, "completion_tokens": 2})
    plan = assistant.generate_plan("fix it", job_id=job.id, data_dir=data,
                                   client=transport)
    row = _rows(data)[0]
    assert row["plan_id"] == plan.plan_id
    assert row["job_id"] == job.id
    assert row["prompt_tokens"] == 3
    assert row["completion_tokens"] == 2


def test_seam_prefers_an_injected_planner(tmp_path: Path):
    data, job = _job(tmp_path)
    transport = FakeTransport(_payload())

    def planner(*, description, context=None, client=None):
        return AssistantPlan(
            plan_id="injected", mode="llm", fallback=False,
            steps=[{"id": "r", "kind": "review", "title": "Review", "prompt": "Review."}],
        )

    plan = assistant.generate_plan("x", job_id=job.id, data_dir=data,
                                   planner=planner, client=transport)
    assert plan.plan_id == "injected"
    assert transport.calls == []


# --- validator and status ---------------------------------------------------

def test_validate_plan_accepts_the_contract_shape():
    assert validate_plan(_payload()) == []
    assert validate_plan(AssistantPlan.model_validate(_payload())) == []


def test_validate_plan_does_not_echo_model_text():
    payload = _payload()
    payload["steps"][1]["questions"][0]["default"] = "秘密中文"
    errors = validate_plan(payload)
    assert errors
    assert all("秘密" not in item for item in errors)


def test_status_badge_is_never_enabled_by_default():
    status = assistant_status()
    assert status["mode"] == "deterministic"
    assert status["available"] is False
    assert status["model"] is None
    assert status["fallback_reason"] is None


def test_status_badge_reports_an_unwired_llm():
    status = assistant_status(mode="llm", client_configured=False)
    assert status["available"] is False
    assert status["fallback_reason"] == FallbackReason.NO_CLIENT


def test_messages_keep_routing_ids_out_of_the_prompt():
    messages = build_messages("fix the overflow",
                              context={"job_id": "j1", "data_dir": "C:/secret",
                                       "defect": "heap overflow"})
    payload = json.loads(messages[-1]["content"])
    assert payload["description"] == "fix the overflow"
    assert payload["context"] == {"defect": "heap overflow"}
    assert "j1" not in messages[-1]["content"]
    assert "C:/secret" not in messages[-1]["content"]


def test_messages_drop_values_json_cannot_carry():
    messages = build_messages("fix it", context={"defect": "overflow", "blob": object(),
                                                 "when": {1, 2}})
    payload = json.loads(messages[-1]["content"])
    assert payload["context"] == {"defect": "overflow"}
    assert "object at" not in messages[-1]["content"]


def test_messages_carry_read_evidence_context_verbatim():
    # The M5 read_evidence payload is the planner's input. The seam must pass
    # it through unchanged apart from the routing ids, including input_mode so
    # a no-input attempt is not re-derived as "invalid unknown".
    evidence = {
        "attempt_id": "attempt-1",
        "evidence": "persisted",
        "gates": [{"gate": "V3", "kind": "behaviour", "result": "passed"}],
        "v3": {
            "gate": "V3", "kind": "behaviour", "result": "passed",
            "input_mode": "none",
            "valid": {"passed": 1, "total": 1},
            "invalid": {"passed": 0, "total": 0},
            "invalid_applicable": False,
        },
        "obligations": {"A": [], "B": []},
    }
    messages = build_messages("fix the crash", context={
        "data_dir": "C:/secret", "job_id": "j1", "evidence": evidence,
    })
    payload = json.loads(messages[-1]["content"])
    assert payload["context"]["evidence"] == evidence
    assert "C:/secret" not in messages[-1]["content"]
    assert "j1" not in messages[-1]["content"]


def test_messages_drop_evidence_that_json_cannot_carry():
    messages = build_messages("fix it", context={"evidence": {"blob": object()}})
    payload = json.loads(messages[-1]["content"])
    assert "evidence" not in payload.get("context", {})


def test_messages_carry_the_agent_tool_specs_as_plain_json():
    # The runtime hands the planner the same three v2 tools it can call later.
    # Specs must be JSON-only (no callables) so build_messages can serialise them.
    from app.services import assistant_tools

    specs = assistant_tools.tool_specs()
    messages = build_messages("fix it", context={"tools": specs})
    payload = json.loads(messages[-1]["content"])
    assert payload["context"]["tools"] == specs
    assert {spec["function"]["name"] for spec in specs} == {
        "run_case", "read_evidence", "apply_candidate",
    }


def test_build_failure_downgrades_instead_of_raising(monkeypatch):
    def boom(*args, **kwargs):
        raise TypeError("context is not serialisable")

    monkeypatch.setattr(assistant_llm, "build_messages", boom)
    plan = generate_plan("fix it", client=FakeTransport(_payload()))
    assert plan.fallback is True
    assert plan.fallback_reason == FallbackReason.UNKNOWN


def _plan_body() -> dict:
    return {
        "choices": [{"message": {"content": json.dumps(_payload())}}],
        "model": "model-x",
        "usage": {"prompt_tokens": 11, "completion_tokens": 22},
    }


def test_client_from_env_without_key_is_none():
    assert assistant_llm.client_from_env({}) is None
    assert assistant_llm.client_from_env({assistant_llm.PROVIDER_KEY_ENV: "   "}) is None


def test_client_from_env_falls_back_on_a_blank_base():
    client = assistant_llm.client_from_env({
        assistant_llm.PROVIDER_KEY_ENV: "sk-test",
        assistant_llm.PROVIDER_BASE_ENV: "   ",
    })
    assert client is not None
    assert client.base_url == assistant_llm.DEFAULT_PROVIDER_BASE


def test_client_from_env_ignores_a_bad_timeout():
    for raw in ("nope", "0", "-1"):
        client = assistant_llm.client_from_env({
            assistant_llm.PROVIDER_KEY_ENV: "sk-test",
            assistant_llm.PROVIDER_TIMEOUT_ENV: raw,
        })
        assert client is not None
        assert client._timeout == 30.0


def test_client_from_env_reads_base_model_and_timeout():
    client = assistant_llm.client_from_env({
        assistant_llm.PROVIDER_KEY_ENV: "sk-test",
        assistant_llm.PROVIDER_BASE_ENV: "https://example.test/v1/",
        assistant_llm.ASSISTANT_MODEL_ENV: "model-x",
        assistant_llm.PROVIDER_TIMEOUT_ENV: "7.5",
    })
    assert client is not None
    assert client.base_url == "https://example.test/v1"
    assert client.model == "model-x"


def test_client_from_env_accepts_the_documented_deepseek_aliases():
    client = assistant_llm.client_from_env({
        "DEEPSEEK_API_KEY": "sk-legacy",
        "DEEPSEEK_BASE_URL": "https://api.deepseek.com/v1/",
        "DEEPSEEK_MODEL": "deepseek-chat",
        "DEEPSEEK_TIMEOUT_S": "12",
    })
    assert client is not None
    assert client.base_url == "https://api.deepseek.com/v1"
    assert client.model == "deepseek-chat"
    assert client._timeout == 12.0


def test_canonical_names_win_over_the_documented_aliases():
    client = assistant_llm.client_from_env({
        assistant_llm.PROVIDER_KEY_ENV: "sk-canonical",
        "DEEPSEEK_API_KEY": "sk-legacy",
        assistant_llm.ASSISTANT_MODEL_ENV: "canonical-model",
        "DEEPSEEK_MODEL": "legacy-model",
    })
    assert client is not None
    assert client.model == "canonical-model"


def test_load_env_file_fills_missing_names_and_keeps_existing(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "# comment\n"
        "export BINARYREPAIR_ASSISTANT_PROVIDER_KEY=sk-from-file\n"
        "DEEPSEEK_MODEL='deepseek-chat'\n"
        "ALREADY_SET=file-value\n"
        "  \n"
        "not a pair\n",
        encoding="utf-8",
    )
    env = {"ALREADY_SET": "keep-me"}
    loaded = assistant_llm.load_env_file(env_path, environ=env)
    assert loaded == {
        "BINARYREPAIR_ASSISTANT_PROVIDER_KEY": "sk-from-file",
        "DEEPSEEK_MODEL": "deepseek-chat",
    }
    assert env["ALREADY_SET"] == "keep-me"


def test_load_env_file_missing_is_empty(tmp_path):
    assert assistant_llm.load_env_file(tmp_path / "nope.env", environ={}) == {}


def test_ensure_env_loaded_reads_a_dotenv_once(monkeypatch, tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "BINARYREPAIR_ASSISTANT_MODEL=from-dotenv\n", encoding="utf-8")
    monkeypatch.setattr(assistant_llm, "_ENV_FILE_LOADED", False)
    monkeypatch.delenv("BINARYREPAIR_ASSISTANT_MODEL", raising=False)
    try:
        loaded = assistant_llm.ensure_env_loaded(env_path)
        assert loaded["BINARYREPAIR_ASSISTANT_MODEL"] == "from-dotenv"
        assert os.environ["BINARYREPAIR_ASSISTANT_MODEL"] == "from-dotenv"
        assert assistant_llm.ensure_env_loaded(env_path) == {}
    finally:
        monkeypatch.delenv("BINARYREPAIR_ASSISTANT_MODEL", raising=False)


def test_unknown_tool_field_falls_back_and_never_echoes_the_model_text():
    # Plans are display-only; a model that tries to smuggle a tool call into a
    # step must hit the schema fallback, and the offending text must not be
    # echoed back (include_input=False).
    payload = _payload()
    payload["steps"][0]["tool"] = "run_case"
    plan = generate_plan("fix it", client=FakeTransport(json.dumps(payload)))
    assert plan.fallback is True
    assert plan.fallback_reason == FallbackReason.SCHEMA
    assert "run_case" not in plan.model_dump_json()


def test_provider_key_never_reaches_the_prompt_or_the_client_repr(monkeypatch):
    key = "sk-SENTINEL-DO-NOT-LEAK"
    monkeypatch.setenv(assistant_llm.PROVIDER_KEY_ENV, key)
    messages = build_messages("fix it", context={"gates": [], "v3": None})
    assert key not in json.dumps(messages)
    client = assistant_llm.client_from_env()
    assert client is not None
    assert key not in repr(client)


def test_http_client_sends_the_openai_shape():
    import httpx

    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_plan_body(), request=request)

    client = assistant_llm.HttpJsonClient(
        api_key="sk-test", base_url="https://example.test/v1", model="model-x",
        transport=httpx.MockTransport(handler),
    )
    result = client.chat_json([{"role": "user", "content": "hi"}], max_tokens=99)
    assert seen["url"] == "https://example.test/v1/chat/completions"
    assert seen["auth"] == "Bearer sk-test"
    assert seen["body"]["max_tokens"] == 99
    assert seen["body"]["response_format"] == {"type": "json_object"}
    assert result.content == _plan_body()["choices"][0]["message"]["content"]
    assert result.usage["prompt_tokens"] == 11
    assert result.usage["completion_tokens"] == 22
    assert isinstance(result.usage["latency_ms"], int)


def test_http_client_hides_the_key_in_repr():
    client = assistant_llm.HttpJsonClient(api_key="sk-secret", base_url="https://x", model="m")
    assert "sk-secret" not in repr(client)


def test_http_client_maps_timeout_to_timeout_error():
    import httpx

    def handler(request):
        raise httpx.ConnectTimeout("slow", request=request)

    client = assistant_llm.HttpJsonClient(
        api_key="sk", base_url="https://x", model="m",
        transport=httpx.MockTransport(handler),
    )
    try:
        client.chat_json([{"role": "user", "content": "hi"}])
    except TimeoutError:
        pass
    else:  # pragma: no cover
        raise AssertionError("timeout must surface as TimeoutError")


def test_http_client_maps_http_error():
    import httpx

    def handler(request):
        return httpx.Response(500, json={"error": "boom"}, request=request)

    client = assistant_llm.HttpJsonClient(
        api_key="sk", base_url="https://x", model="m",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(assistant_llm._ProviderHTTPError) as caught:
        client.chat_json([{"role": "user", "content": "hi"}])
    assert caught.value.status == 500
    assert "boom" not in str(caught.value)


def test_generate_plan_uses_the_env_client(monkeypatch, tmp_path):
    import httpx

    def handler(request):
        return httpx.Response(200, json=_plan_body(), request=request)

    client = assistant_llm.HttpJsonClient(
        api_key="sk", base_url="https://x/v1", model="model-x",
        transport=httpx.MockTransport(handler),
    )
    monkeypatch.setattr(assistant_llm, "client_from_env", lambda environ=None: client)
    plan = generate_plan("fix it", context={"data_dir": str(tmp_path)}, mode="llm")
    assert plan.mode == "llm"
    assert plan.fallback is False
    assert plan.model == "model-x"
    assert plan.tokens == {"prompt": 11, "completion": 22}


def test_generate_plan_records_http_failure_as_fallback(monkeypatch, tmp_path):
    import httpx

    def handler(request):
        return httpx.Response(503, json={}, request=request)

    client = assistant_llm.HttpJsonClient(
        api_key="sk", base_url="https://x/v1", model="model-x",
        transport=httpx.MockTransport(handler),
    )
    monkeypatch.setattr(assistant_llm, "client_from_env", lambda environ=None: client)
    plan = generate_plan("fix it", context={"data_dir": str(tmp_path)}, mode="llm")
    assert plan.fallback is True
    assert plan.fallback_reason == FallbackReason.HTTP


def test_status_badge_reports_the_env_client(monkeypatch):
    monkeypatch.setenv(assistant_llm.PROVIDER_KEY_ENV, "sk-test")
    assert assistant_status(mode="llm")["available"] is True
    monkeypatch.delenv(assistant_llm.PROVIDER_KEY_ENV, raising=False)
    assert assistant_status(mode="llm")["available"] is False
