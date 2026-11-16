"""Transport-neutral request/result types for the LLM gateway.

This module owns only public data shapes and typed errors.  Providers implement
``generate()``; the gateway owns model-identity validation and result
annotation.  No credential is stored in a result, error, repr or log message.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable


class GatewayError(RuntimeError):
    """A provider-independent typed failure.

    ``code`` is stable and machine-readable; ``message`` never contains a key,
    Authorization header or raw provider body.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        provider: str | None = None,
        retryable: bool = False,
        http_status: int | None = None,
        request_id: str | None = None,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = str(code)
        self.provider = provider
        self.retryable = bool(retryable)
        self.http_status = http_status
        self.request_id = request_id
        self.detail = dict(detail or {})

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": str(self),
            "provider": self.provider,
            "retryable": self.retryable,
            "http_status": self.http_status,
            "request_id": self.request_id,
            "detail": dict(self.detail),
        }


class ConfigurationError(GatewayError):
    def __init__(self, message: str, *, provider: str | None = None) -> None:
        super().__init__("configuration_error", message, provider=provider)


class TransportError(GatewayError):
    def __init__(self, message: str, *, provider: str | None = None,
                 retryable: bool = True) -> None:
        super().__init__("transport_error", message, provider=provider,
                         retryable=retryable)


class TimeoutError(GatewayError):  # noqa: A001 - exported typed timeout
    def __init__(self, message: str = "provider request timed out", *,
                 provider: str | None = None) -> None:
        super().__init__("timeout", message, provider=provider, retryable=True)


class HTTPStatusError(GatewayError):
    def __init__(self, message: str, *, provider: str | None = None,
                 http_status: int | None = None, retryable: bool = False,
                 request_id: str | None = None) -> None:
        super().__init__("http_error", message, provider=provider,
                         retryable=retryable, http_status=http_status,
                         request_id=request_id)


class ResponseError(GatewayError):
    def __init__(self, message: str, *, provider: str | None = None,
                 detail: Mapping[str, Any] | None = None) -> None:
        super().__init__("response_error", message, provider=provider,
                         detail=detail)


class EmptyContentError(ResponseError):
    def __init__(self, *, provider: str | None = None) -> None:
        super().__init__("provider returned empty content", provider=provider)
        self.code = "empty_content"


class ModelIdentityError(GatewayError):
    def __init__(self, requested: str | None, returned: str | None, *,
                 provider: str | None = None) -> None:
        super().__init__(
            "model_identity_mismatch",
            f"model identity mismatch: requested={requested!r} returned={returned!r}",
            provider=provider,
        )
        self.requested = requested
        self.returned = returned

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update({"requested": self.requested, "returned": self.returned})
        return payload


# Backwards-friendly names used by callers/tests.
ProviderError = GatewayError
TimeoutGatewayError = TimeoutError


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass(frozen=True)
class GenerationRequest:
    messages: Sequence[ChatMessage | Mapping[str, str]]
    model: str
    max_tokens: int = 1024
    temperature: float = 0.0
    thinking: bool = False
    response_format: str = "text"  # text | json
    timeout: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def normalized_messages(self) -> list[dict[str, str]]:
        result: list[dict[str, str]] = []
        for message in self.messages:
            if isinstance(message, ChatMessage):
                result.append(message.to_dict())
            elif isinstance(message, Mapping):
                result.append({"role": str(message.get("role", "")),
                               "content": str(message.get("content", ""))})
            else:
                raise ConfigurationError(
                    f"unsupported message type: {type(message).__name__}"
                )
        return result


@dataclass(frozen=True)
class GenerationResult:
    content: str
    provider: str
    model_requested: str | None = None
    model: str | None = None
    request_id: str | None = None
    usage: Mapping[str, int] = field(default_factory=dict)
    latency_ms: int = 0
    identity_ok: bool | None = None
    raw: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "content": self.content,
            "provider": self.provider,
            "model_requested": self.model_requested,
            "model": self.model,
            "request_id": self.request_id,
            "usage": {str(k): int(v) for k, v in self.usage.items()},
            "latency_ms": self.latency_ms,
            "identity_ok": self.identity_ok,
        }
        if self.raw is not None:
            payload["raw"] = dict(self.raw)
        return payload

    def json_content(self) -> Any:
        return json.loads(self.content)


# Common aliases: callers may use Request/Response names without coupling to
# a provider implementation.
GatewayRequest = GenerationRequest
GatewayResponse = GenerationResult
GenerateRequest = GenerationRequest
GenerateResult = GenerationResult


def model_identity_ok(requested: str | None, returned: str | None) -> bool:
    """Exact identity comparison; no provider/model aliasing is assumed."""
    if not isinstance(requested, str) or not requested.strip():
        return False
    if not isinstance(returned, str) or not returned.strip():
        return False
    return requested.strip() == returned.strip()


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    def generate(self, request: GenerationRequest) -> GenerationResult: ...


def annotate_identity(result: GenerationResult, requested: str | None) -> GenerationResult:
    """Return a copy with identity fields filled from the actual response."""
    identity = model_identity_ok(requested, result.model)
    from dataclasses import replace
    return replace(result, model_requested=requested, identity_ok=identity)


__all__ = [
    "GatewayError", "ProviderError", "ConfigurationError", "TransportError",
    "TimeoutError", "TimeoutGatewayError", "HTTPStatusError", "ResponseError",
    "EmptyContentError", "ModelIdentityError", "ChatMessage",
    "GenerationRequest", "GenerationResult", "GenerateRequest", "GenerateResult",
    "GatewayRequest", "GatewayResponse", "LLMProvider", "model_identity_ok",
    "annotate_identity",
]
