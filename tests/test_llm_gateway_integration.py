"""Offline integration contract for the P31-P34 unified LLM gateway.

No real network call is made: HTTP adapters are exercised with an httpx
MockTransport and the mock adapter is fully local.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.llm_gateway import (  # noqa: E402
    ConfigurationError,
    GenerationRequest,
    GenerationResult,
    LLMGateway,
    MockProvider,
    ModelIdentityError,
    OpenRouterProvider,
    OllamaProvider,
    model_identity_ok,
)
from app.services.llm_gateway.client import gateway_from_env  # noqa: E402


def _request(model: str = "mock-model") -> GenerationRequest:
    return GenerationRequest(messages=[{"role": "user", "content": "hi"}],
                             model=model)


def test_mock_provider_and_gateway_are_offline_and_deterministic() -> None:
    provider = MockProvider(["fixed response"], model="mock-model")
    gateway = LLMGateway({"mock": provider}, default_provider="mock")
    result = gateway.generate(_request())
    assert isinstance(result, GenerationResult)
    assert result.content == "fixed response"
    assert result.provider == "mock"
    assert result.identity_ok is True
    assert provider.requests and provider.requests[0].model == "mock-model"


def test_gateway_rejects_mock_identity_mismatch() -> None:
    class WrongModel:
        name = "wrong"
        def generate(self, request: GenerationRequest) -> GenerationResult:
            return GenerationResult(content="x", provider="wrong",
                                    model="different-model")

    gateway = LLMGateway({"wrong": WrongModel()}, default_provider="wrong")
    with pytest.raises(ModelIdentityError) as excinfo:
        gateway.generate(_request("requested-model"))
    assert excinfo.value.code == "model_identity_mismatch"
    assert excinfo.value.returned == "different-model"
    assert "different-model" in str(excinfo.value)


def test_identity_helper_is_exact_not_alias() -> None:
    assert model_identity_ok("deepseek-chat", "deepseek-chat") is True
    assert model_identity_ok("deepseek-chat", "deepseek-chat-v2") is False
    assert model_identity_ok("", "") is False


def test_openrouter_adapter_uses_injected_transport_without_network() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["model"] == "openrouter/test-model"
        return httpx.Response(
            200,
            headers={"x-request-id": "req-123"},
            json={
                "model": "openrouter/test-model",
                "choices": [{"message": {"content": "cloud answer"}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2,
                          "total_tokens": 5},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenRouterProvider("secret-key", http_client=client,
                                  model="openrouter/test-model")
    result = provider.generate(_request("openrouter/test-model"))
    assert result.content == "cloud answer"
    assert result.provider == "openrouter"
    assert result.request_id == "req-123"
    assert result.usage["total_tokens"] == 5
    assert "secret-key" not in repr(provider)
    client.close()


def test_openrouter_missing_key_is_typed_and_redacted() -> None:
    provider = OpenRouterProvider("", model="openrouter/test-model")
    with pytest.raises(Exception) as excinfo:
        provider.generate(_request("openrouter/test-model"))
    assert getattr(excinfo.value, "code", None) == "auth_error"
    assert "secret" not in str(excinfo.value).lower()


def test_ollama_adapter_uses_injected_transport_without_network() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["model"] == "llama-test"
        return httpx.Response(
            200,
            json={
                "model": "llama-test",
                "message": {"content": "local answer"},
                "prompt_eval_count": 4,
                "eval_count": 2,
                "created_at": "2026-11-16T00:00:00Z",
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OllamaProvider(http_client=client, model="llama-test")
    result = provider.generate(_request("llama-test"))
    assert result.content == "local answer"
    assert result.provider == "ollama"
    assert result.usage["total_tokens"] == 6
    client.close()


def test_env_missing_credential_does_not_create_provider() -> None:
    with pytest.raises(ConfigurationError) as excinfo:
        gateway_from_env({}, provider="openrouter")
    assert excinfo.value.code == "configuration_error"
    assert "api key" in str(excinfo.value).lower()


def test_env_mock_provider_requires_no_credential() -> None:
    gateway = gateway_from_env({"BINARYREPAIR_PROVIDER": "mock"}, provider="mock")
    assert gateway.providers == ("mock",)
    assert gateway.default_provider == "mock"


def test_stability_aggregate_separates_statuses() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import run_stability_matrix  # noqa: E402

    records = [
        {"status": "completed", "verified": True,
         "verification_status": "verified", "spec": "m", "case_id": "a"},
        {"status": "completed", "verified": False,
         "verification_status": "PLAN_INVALID", "spec": "m", "case_id": "b"},
        {"status": "completed", "verified": False,
         "verification_status": "ARTIFACT_MISSING", "spec": "m", "case_id": "c"},
        {"status": "timeout", "verified": False,
         "verification_status": "TIMEOUT", "spec": "m", "case_id": "d"},
    ]
    report = run_stability_matrix.aggregate(records)
    assert report["eligible_runs"] == 3
    assert report["verified_runs"] == 1
    assert report["status_counts"]["PLAN_INVALID"] == 1
    assert report["status_counts"]["ARTIFACT_MISSING"] == 1
    assert report["status_counts"]["TIMEOUT"] == 1
