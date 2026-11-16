"""Credential resolution for cloud and local LLM providers.

Precedence and provider selection are explicit.  Resolved credentials are
immutable and redaction-safe: ``repr()`` and ``redacted()`` never contain the
key.  This module performs no network I/O.

Compatible environment variables
--------------------------------
Provider selection:
  BINARYREPAIR_LLM_PROVIDER=openrouter|ollama|mock

OpenRouter:
  BINARYREPAIR_OPENROUTER_API_KEY, OPENROUTER_API_KEY
  BINARYREPAIR_OPENROUTER_BASE_URL, OPENROUTER_BASE_URL
  BINARYREPAIR_OPENROUTER_MODEL, OPENROUTER_MODEL

Ollama:
  BINARYREPAIR_OLLAMA_BASE_URL, OLLAMA_HOST
  BINARYREPAIR_OLLAMA_MODEL, OLLAMA_MODEL

Mock is offline and needs no credential.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from app.services.llm_gateway.errors import (
    CredentialError,
    INVALID_CREDENTIAL,
    MISSING_CREDENTIAL,
)

__all__ = [
    "PROVIDER_ENV",
    "OPENROUTER_DEFAULT_BASE",
    "OLLAMA_DEFAULT_BASE",
    "Credential",
    "CredentialResolver",
    "resolve_credential",
    "available_providers",
    "mask_key",
    "normalize_provider",
]

PROVIDER_ENV = "BINARYREPAIR_LLM_PROVIDER"
OPENROUTER_DEFAULT_BASE = "https://openrouter.ai/api/v1"
OLLAMA_DEFAULT_BASE = "http://127.0.0.1:11434/v1"

_OPENROUTER_KEYS = ("BINARYREPAIR_OPENROUTER_API_KEY", "OPENROUTER_API_KEY")
_OPENROUTER_BASES = ("BINARYREPAIR_OPENROUTER_BASE_URL", "OPENROUTER_BASE_URL")
_OPENROUTER_MODELS = ("BINARYREPAIR_OPENROUTER_MODEL", "OPENROUTER_MODEL")
_OLLAMA_BASES = ("BINARYREPAIR_OLLAMA_BASE_URL", "OLLAMA_HOST")
_OLLAMA_MODELS = ("BINARYREPAIR_OLLAMA_MODEL", "OLLAMA_MODEL")
_ALIASES = {
    "openrouter": "openrouter",
    "open-router": "openrouter",
    "cloud": "openrouter",
    "ollama": "ollama",
    "local": "ollama",
    "mock": "mock",
    "offline": "mock",
}
_KEY_RE = re.compile(r"^[^\s\x00-\x1f\x7f]+$")


def normalize_provider(value: str | None) -> str:
    raw = (value or "").strip().lower()
    return _ALIASES.get(raw, raw)


def mask_key(key: str) -> str:
    """Return a safe display form; short keys are fully hidden."""
    key = key or ""
    if not key:
        return ""
    if len(key) <= 12:
        return "*" * len(key)
    return f"{key[:4]}...{key[-4:]}"


def _first(env: Mapping[str, str], names: tuple[str, ...]) -> tuple[str, str | None]:
    for name in names:
        value = (env.get(name) or "").strip()
        if value:
            return name, value
    return "", None


def _normalize_base(value: str | None, default: str) -> str:
    base = (value or "").strip().rstrip("/")
    if not base:
        return default
    if not base.startswith(("http://", "https://")):
        base = "http://" + base
    return base


def _validate_key(key: str) -> str:
    if not _KEY_RE.match(key):
        raise CredentialError(
            "credential contains whitespace or control characters",
            code=INVALID_CREDENTIAL,
        )
    return key


@dataclass(frozen=True)
class Credential:
    provider: str
    base_url: str
    model: str | None = None
    api_key: str | None = None
    source: str = "env"
    requires_api_key: bool = False

    def __repr__(self) -> str:
        return (
            f"Credential(provider={self.provider!r}, base_url={self.base_url!r}, "
            f"model={self.model!r}, api_key={mask_key(self.api_key or '')!r}, "
            f"source={self.source!r})"
        )

    def headers(self) -> dict[str, str]:
        if self.api_key:
            return {"Authorization": f"Bearer {self.api_key}"}
        return {}

    def redacted(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "base_url": self.base_url,
            "model": self.model,
            "configured": bool(self.api_key) or not self.requires_api_key,
            "source": self.source,
            "api_key_masked": mask_key(self.api_key or ""),
        }


class CredentialResolver:
    """Resolve one provider credential from env or an explicit key loader."""

    def __init__(self, env: Mapping[str, str] | None = None,
                 key_loader: Callable[[str], str] | None = None) -> None:
        self._env = env if env is not None else os.environ
        self._key_loader = key_loader

    def default_provider(self) -> str:
        explicit = normalize_provider(self._env.get(PROVIDER_ENV))
        if explicit:
            return explicit
        if _first(self._env, _OPENROUTER_KEYS)[1]:
            return "openrouter"
        if _first(self._env, _OLLAMA_BASES)[1]:
            return "ollama"
        return "mock"

    def resolve(self, provider: str | None = None,
                model: str | None = None) -> Credential:
        name = normalize_provider(provider) or self.default_provider()
        if name == "openrouter":
            return self._openrouter(model)
        if name == "ollama":
            return self._ollama(model)
        if name == "mock":
            return Credential(provider="mock", base_url="mock://local",
                              model=model or "mock-model", source="mock")
        raise CredentialError(
            f"unknown LLM provider: {name}", code=MISSING_CREDENTIAL,
            details={"provider": name},
        )

    def _openrouter(self, model: str | None) -> Credential:
        source, key = _first(self._env, _OPENROUTER_KEYS)
        if not key and self._key_loader is not None:
            try:
                loaded = (self._key_loader("openrouter") or "").strip()
            except Exception as exc:  # noqa: BLE001 - never leak loader detail
                raise CredentialError(
                    "credential loader failed",
                    details={"loader": type(exc).__name__},
                ) from None
            if loaded:
                key, source = loaded, "key_store"
        if not key:
            raise CredentialError(
                "OpenRouter API key is not configured; set "
                "BINARYREPAIR_OPENROUTER_API_KEY or OPENROUTER_API_KEY",
                details={"provider": "openrouter"},
            )
        key = _validate_key(key)
        base = _normalize_base(
            _first(self._env, _OPENROUTER_BASES)[1], OPENROUTER_DEFAULT_BASE)
        resolved_model = model or _first(self._env, _OPENROUTER_MODELS)[1]
        return Credential(provider="openrouter", base_url=base,
                          model=resolved_model, api_key=key,
                          source=source or "env", requires_api_key=True)

    def _ollama(self, model: str | None) -> Credential:
        base = _normalize_base(
            _first(self._env, _OLLAMA_BASES)[1], OLLAMA_DEFAULT_BASE)
        if not base.endswith("/v1"):
            base = base.rstrip("/") + "/v1"
        resolved_model = model or _first(self._env, _OLLAMA_MODELS)[1]
        return Credential(provider="ollama", base_url=base,
                          model=resolved_model, api_key=None,
                          source="env", requires_api_key=False)


def resolve_credential(provider: str | None = None, *,
                       model: str | None = None,
                       env: Mapping[str, str] | None = None,
                       key_loader: Callable[[str], str] | None = None) -> Credential:
    return CredentialResolver(env=env, key_loader=key_loader).resolve(provider, model)


def available_providers(env: Mapping[str, str] | None = None) -> list[str]:
    environment = env if env is not None else os.environ
    providers = ["mock", "ollama"]
    if _first(environment, _OPENROUTER_KEYS)[1]:
        providers.append("openrouter")
    return providers
