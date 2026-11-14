"""Compliant multi-provider selection and model-identity checks."""
from __future__ import annotations

from types import SimpleNamespace

from app.services.assistant_llm import (
    client_from_env,
    model_identity_ok,
    provider_config,
)
from app.services.ai_binary_repair import _call_model


def test_siliconflow_profile_is_selected_by_its_key():
    env = {
        "SILICONFLOW_API_KEY": "sk-test-silicon",
        "SILICONFLOW_MODEL": "deepseek-ai/DeepSeek-V4-Flash",
    }
    cfg = provider_config(env)
    assert cfg["provider"] == "siliconflow"
    assert cfg["base_url"] == "https://api.siliconflow.cn/v1"
    assert cfg["model"] == "deepseek-ai/DeepSeek-V4-Flash"
    assert cfg["configured"] is True
    client = client_from_env(env)
    assert client is not None
    assert client.provider_name == "siliconflow"
    assert client.model == "deepseek-ai/DeepSeek-V4-Flash"


def test_dashscope_profile_is_selected_by_its_key():
    env = {
        "DASHSCOPE_API_KEY": "sk-test-dashscope",
        "DASHSCOPE_MODEL": "qwen-plus",
    }
    cfg = provider_config(env)
    assert cfg["provider"] == "dashscope"
    assert cfg["base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert cfg["configured"] is True
    client = client_from_env(env)
    assert client is not None
    assert client.provider_name == "dashscope"


def test_missing_provider_model_or_key_is_not_configured():
    cfg = provider_config({"SILICONFLOW_API_KEY": "sk-test-only"})
    assert cfg["configured"] is False
    assert any("model" in item for item in cfg["errors"])
    assert client_from_env({"SILICONFLOW_API_KEY": "sk-test-only"}) is None


def test_explicit_provider_requires_provider_key():
    cfg = provider_config({"BINARYREPAIR_PROVIDER": "siliconflow"})
    assert cfg["provider"] == "siliconflow"
    assert cfg["configured"] is False
    assert any("API key" in item for item in cfg["errors"])


def test_model_identity_is_exact():
    assert model_identity_ok("deepseek-chat", "deepseek-chat") is True
    assert model_identity_ok("deepseek-chat", "deepseek-flash") is False
    assert model_identity_ok(None, "x") is False


def test_strict_identity_rejects_provider_swap(monkeypatch):
    class FakeClient:
        model = "deepseek-chat"

        def chat_json(self, messages, **kwargs):
            return SimpleNamespace(
                content='{"schema_version":1,"assembly":".intel_syntax noprefix\\n.text\\nret\\n"}',
                model="deepseek-flash", usage={}, request_id="r",
            )

    monkeypatch.setenv("BINARYREPAIR_STRICT_MODEL_IDENTITY", "1")
    ai: dict = {}
    parsed, error = _call_model(
        FakeClient(), system_prompt="sys", packet={}, max_tokens=10, ai=ai,
    )
    assert parsed is None
    assert ai["status"] == "identity_mismatch"
    assert ai["model_identity_ok"] is False
    assert "requested" in (error or "")


def test_siliconflow_uses_generic_assistant_model_override():
    env = {
        "SILICONFLOW_API_KEY": "sk-test-silicon",
        "BINARYREPAIR_ASSISTANT_MODEL": "Qwen/Qwen3.8-27B",
    }
    cfg = provider_config(env)
    assert cfg["provider"] == "siliconflow"
    assert cfg["model"] == "Qwen/Qwen3.8-27B"
    assert cfg["configured"] is True
