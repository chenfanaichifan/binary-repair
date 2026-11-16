from __future__ import annotations

import pytest

from app.services.llm_gateway.credentials import (
    CredentialResolver,
    available_providers,
    mask_key,
    resolve_credential,
)
from app.services.llm_gateway.errors import (
    AuthenticationError,
    CredentialError,
    IdentityMismatchError,
    LLMGatewayError,
    ProviderError,
    ResponseError,
    error_payload,
    safe_text,
)
from app.services.llm_gateway.usage import (
    ModelIdentity,
    RequestRecord,
    TokenUsage,
    UsageRecorder,
    coerce_usage,
    measure_latency,
    merge_usage,
)


def test_openrouter_key_precedence_and_redaction() -> None:
    env = {
        "BINARYREPAIR_LLM_PROVIDER": "openrouter",
        "BINARYREPAIR_OPENROUTER_API_KEY": "sk-or-primary-1234567890",
        "OPENROUTER_API_KEY": "sk-or-fallback-1234567890",
        "OPENROUTER_MODEL": "openrouter/model-a",
    }
    credential = resolve_credential(env=env)
    assert credential.provider == "openrouter"
    assert credential.api_key == "sk-or-primary-1234567890"
    assert credential.base_url == "https://openrouter.ai/api/v1"
    assert credential.model == "openrouter/model-a"
    assert credential.requires_api_key is True
    assert credential.source == "BINARYREPAIR_OPENROUTER_API_KEY"
    assert "sk-or-primary" not in repr(credential)
    redacted = credential.redacted()
    assert "sk-or-primary" not in str(redacted)
    assert "api_key" not in redacted
    assert redacted["api_key_masked"].startswith("sk-o")
    assert credential.headers()["Authorization"].startswith("Bearer ")


def test_openrouter_missing_key_is_typed_and_safe() -> None:
    with pytest.raises(CredentialError) as caught:
        resolve_credential("openrouter", env={})
    error = caught.value
    assert error.code == "missing_credential"
    assert "API key" in error.message
    assert "sk-" not in str(error)


def test_openrouter_invalid_key_never_echoes_value() -> None:
    secret = "sk-or-bad key"
    with pytest.raises(CredentialError) as caught:
        resolve_credential("openrouter", env={"OPENROUTER_API_KEY": secret})
    assert secret not in str(caught.value)
    assert secret not in str(caught.value.to_dict())


def test_key_loader_fallback_and_failure_are_typed() -> None:
    seen: list[str] = []

    def loader(provider: str) -> str:
        seen.append(provider)
        return "sk-or-loaded-123456"

    credential = resolve_credential("openrouter", env={}, key_loader=loader)
    assert credential.api_key == "sk-or-loaded-123456"
    assert credential.source == "key_store"
    assert seen == ["openrouter"]

    def failing(_provider: str) -> str:
        raise RuntimeError("do not leak this detail")

    with pytest.raises(CredentialError) as caught:
        resolve_credential("openrouter", env={}, key_loader=failing)
    assert "do not leak" not in str(caught.value)
    assert "RuntimeError" in caught.value.details.get("loader", "")


def test_ollama_needs_no_key_and_normalizes_host() -> None:
    env = {"OLLAMA_HOST": "127.0.0.1:11434", "OLLAMA_MODEL": "qwen-local"}
    credential = resolve_credential("ollama", env=env)
    assert credential.provider == "ollama"
    assert credential.base_url == "http://127.0.0.1:11434/v1"
    assert credential.model == "qwen-local"
    assert credential.requires_api_key is False
    assert credential.api_key is None
    assert credential.headers() == {}
    assert credential.redacted()["configured"] is True


def test_mock_provider_is_offline_without_credentials() -> None:
    credential = resolve_credential("mock", env={})
    assert credential.provider == "mock"
    assert credential.base_url == "mock://local"
    assert credential.api_key is None
    assert credential.redacted()["configured"] is True


def test_default_provider_selection() -> None:
    assert CredentialResolver(env={}).default_provider() == "mock"
    assert CredentialResolver(env={"OLLAMA_HOST": "x"}).default_provider() == "ollama"
    assert CredentialResolver(env={"OPENROUTER_API_KEY": "k"}).default_provider() == "openrouter"
    assert CredentialResolver(env={"BINARYREPAIR_LLM_PROVIDER": "local"}).default_provider() == "ollama"


def test_available_providers_and_mask_key() -> None:
    assert available_providers(env={}) == ["mock", "ollama"]
    assert available_providers(env={"OPENROUTER_API_KEY": "k"}) == ["mock", "ollama", "openrouter"]
    assert mask_key("") == ""
    assert mask_key("short") == "*****"
    assert mask_key("sk-or-1234567890") == "sk-o...7890"


def test_unknown_provider_is_typed() -> None:
    with pytest.raises(CredentialError):
        resolve_credential("not-a-provider", env={})


def test_error_hierarchy_payload_and_redaction() -> None:
    error = ProviderError("upstream failed", code="provider_error",
                          retryable=True, provider="openrouter", status=503,
                          details={"body": "x" * 500})
    assert isinstance(error, LLMGatewayError)
    assert error.retryable is True
    assert error.to_dict()["provider"] == "openrouter"
    assert len(error.details["body"]) <= 300
    auth = AuthenticationError()
    assert auth.code == "authentication_failed"
    assert auth.retryable is False
    response = ResponseError("bad json")
    assert response.code == "malformed_response"
    unrelated = ValueError("plain")
    payload = error_payload(unrelated)
    assert payload["code"] == "unknown_error"
    assert payload["message"] == "ValueError"
    assert safe_text("a\x00b\nc") == "a b c"


def test_usage_parse_merge_and_missing_values() -> None:
    usage = coerce_usage({"prompt_tokens": 3, "completion_tokens": 4,
                          "total_tokens": 7})
    assert usage == TokenUsage(3, 4, 7)
    assert usage.complete
    assert coerce_usage({}) is None
    assert coerce_usage(None) is None
    combined = merge_usage([usage, TokenUsage(1, 2, 3), None])
    assert combined == TokenUsage(4, 6, 10)
    partial = merge_usage([TokenUsage(3, None, None), TokenUsage(1, 2, 3)])
    assert partial.prompt_tokens == 4
    assert partial.completion_tokens == 2
    assert partial.complete is True


def test_usage_rejects_non_mapping() -> None:
    with pytest.raises(Exception):
        coerce_usage("not-a-mapping")


def test_identity_requires_exact_model_and_typed_mismatch() -> None:
    identity = ModelIdentity("model-a", "model-a", "openrouter", "req-1")
    assert identity.matched is True
    assert identity.require_match() is identity
    mismatch = ModelIdentity("model-a", "model-b", "openrouter")
    assert mismatch.matched is False
    with pytest.raises(IdentityMismatchError) as caught:
        mismatch.require_match()
    assert caught.value.code == "model_identity_mismatch"
    assert caught.value.details["requested"] == "model-a"
    assert caught.value.details["observed"] == "model-b"


def test_usage_recorder_summary_is_safe_and_aggregates() -> None:
    recorder = UsageRecorder(max_records=3)
    identity = ModelIdentity("m", "m", "mock", "r1")
    recorder.record(RequestRecord("mock", identity, TokenUsage(1, 2, 3), 10))
    recorder.record(RequestRecord("mock", ModelIdentity("m", "other", "mock"),
                                  None, 30, status="error", error_code="timeout"))
    recorder.record(RequestRecord("mock", identity, TokenUsage(2, 3, 5), 20))
    summary = recorder.summary()
    assert summary["calls"] == 3
    assert summary["ok"] == 2
    assert summary["errors"] == 1
    assert summary["identity_mismatches"] == 1
    assert summary["usage"]["total_tokens"] == 8
    assert summary["latency_ms_total"] == 60
    assert "api_key" not in str(summary)


def test_measure_latency_reports_number() -> None:
    with measure_latency() as elapsed:
        pass
    assert isinstance(elapsed.elapsed_ms, int)
    assert elapsed.elapsed_ms >= 0
