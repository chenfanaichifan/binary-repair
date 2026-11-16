"""Gateway orchestration: provider selection, identity checks and results."""
from __future__ import annotations

import os
from dataclasses import replace
from typing import Any, Mapping

from .base import (
    ConfigurationError,
    GatewayError,
    GenerationRequest,
    GenerationResult,
    LLMProvider,
    ModelIdentityError,
    annotate_identity,
)
from .providers import MockProvider, OllamaProvider, OpenRouterProvider

DEFAULT_PROVIDER = "openrouter"


class LLMGateway:
    """Select a provider for one ``generate()`` call and own identity checks.

    The gateway never reads a generator verdict and never changes an
    independent verification decision.  It only returns a typed model response
    or a typed error.
    """

    def __init__(
        self,
        providers: Mapping[str, LLMProvider] | None = None,
        *,
        default_provider: str | None = None,
        strict_identity: bool = True,
    ) -> None:
        self._providers: dict[str, LLMProvider] = dict(providers or {})
        self.default_provider = default_provider or next(iter(self._providers), None)
        self.strict_identity = bool(strict_identity)

    def __repr__(self) -> str:
        return (f"LLMGateway(providers={sorted(self._providers)!r}, "
                f"default={self.default_provider!r}, strict_identity={self.strict_identity})")

    @property
    def providers(self) -> tuple[str, ...]:
        return tuple(sorted(self._providers))

    def register(self, provider: LLMProvider, *, name: str | None = None) -> "LLMGateway":
        key = (name or getattr(provider, "name", "") or "").strip()
        if not key:
            raise ConfigurationError("provider name is required")
        self._providers[key] = provider
        if self.default_provider is None:
            self.default_provider = key
        return self

    def provider(self, name: str | None = None) -> LLMProvider:
        key = (name or self.default_provider or "").strip()
        if not key:
            raise ConfigurationError("no LLM provider selected")
        try:
            return self._providers[key]
        except KeyError as exc:
            raise ConfigurationError(f"unknown LLM provider: {key}") from exc

    def generate(
        self,
        request: GenerationRequest,
        *,
        provider: str | None = None,
        strict_identity: bool | None = None,
    ) -> GenerationResult:
        adapter = self.provider(provider)
        result = adapter.generate(request)
        requested = request.model or getattr(adapter, "model", None)
        annotated = annotate_identity(result, requested)
        strict = self.strict_identity if strict_identity is None else bool(strict_identity)
        if strict and annotated.identity_ok is not True:
            raise ModelIdentityError(requested, annotated.model,
                                     provider=annotated.provider)
        return annotated

    def generate_text(self, prompt: str, *, model: str,
                      provider: str | None = None,
                      **kwargs: Any) -> GenerationResult:
        request = GenerationRequest(
            messages=[{"role": "user", "content": prompt}],
            model=model,
            **kwargs,
        )
        return self.generate(request, provider=provider)


def _env(env: Mapping[str, str], *names: str) -> str:
    for name in names:
        value = (env.get(name) or "").strip()
        if value:
            return value
    return ""


def gateway_from_env(
    environ: Mapping[str, str] | None = None,
    *,
    provider: str | None = None,
) -> LLMGateway:
    """Build one gateway from env without making a network call.

    Only the selected adapter is constructed.  Missing credentials raise
    ``ConfigurationError``; a gateway is never fabricated with a placeholder
    key.
    """
    env = os.environ if environ is None else environ
    selected = (provider or _env(env, "BINARYREPAIR_LLM_PROVIDER",
                                 "BINARYREPAIR_PROVIDER") or DEFAULT_PROVIDER).lower()
    model = _env(env, "BINARYREPAIR_ASSISTANT_MODEL", "OPENROUTER_MODEL",
                 "OLLAMA_MODEL")
    strict = (env.get("BINARYREPAIR_STRICT_MODEL_IDENTITY", "1").strip().lower()
              not in {"0", "false", "no", "off"})
    if selected == "openrouter":
        key = _env(env, "OPENROUTER_API_KEY", "BINARYREPAIR_OPENROUTER_API_KEY")
        if not key:
            raise ConfigurationError("OpenRouter API key is not configured",
                                     provider="openrouter")
        base = _env(env, "OPENROUTER_BASE_URL", "BINARYREPAIR_OPENROUTER_BASE_URL") or \
            "https://openrouter.ai/api/v1"
        timeout = float(_env(env, "OPENROUTER_TIMEOUT", "BINARYREPAIR_LLM_TIMEOUT") or 60)
        adapter = OpenRouterProvider(
            key, base_url=base, model=model or None, timeout=timeout,
            http_referer=_env(env, "OPENROUTER_HTTP_REFERER") or None,
            app_title=_env(env, "OPENROUTER_APP_TITLE") or None,
        )
        return LLMGateway({"openrouter": adapter}, default_provider="openrouter",
                          strict_identity=strict)
    if selected == "ollama":
        base = _env(env, "OLLAMA_BASE_URL", "BINARYREPAIR_OLLAMA_BASE_URL") or \
            "http://127.0.0.1:11434"
        timeout = float(_env(env, "OLLAMA_TIMEOUT", "BINARYREPAIR_LLM_TIMEOUT") or 60)
        adapter = OllamaProvider(base_url=base, model=model or None, timeout=timeout)
        return LLMGateway({"ollama": adapter}, default_provider="ollama",
                          strict_identity=strict)
    if selected == "mock":
        adapter = MockProvider()
        return LLMGateway({"mock": adapter}, default_provider="mock",
                          strict_identity=False)
    raise ConfigurationError(f"unknown LLM provider: {selected}")


# Convenience aliases used by integration callers.
Gateway = LLMGateway
LLMClient = LLMGateway
create_gateway = gateway_from_env


__all__ = ["LLMGateway", "Gateway", "LLMClient", "gateway_from_env",
           "create_gateway", "DEFAULT_PROVIDER"]
