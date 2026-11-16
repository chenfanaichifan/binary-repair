"""OpenRouter chat-completions adapter (OpenAI-compatible wire shape)."""
from __future__ import annotations

import time
from typing import Any, Mapping

import httpx

from ..base import (
    EmptyContentError,
    GatewayError,
    GenerationRequest,
    GenerationResult,
    HTTPStatusError,
    TransportError,
    TimeoutError,
)

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


def _usage(raw: Any, latency_ms: int) -> dict[str, int]:
    usage = raw if isinstance(raw, Mapping) else {}
    result: dict[str, int] = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = usage.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            result[key] = value
    result["latency_ms"] = max(0, int(latency_ms))
    return result


def _content(raw: Any) -> str:
    choices = raw.get("choices") if isinstance(raw, Mapping) else None
    if not isinstance(choices, list) or not choices:
        raise GatewayError("response_error", "provider response contained no choices",
                           provider="openrouter")
    first = choices[0] if isinstance(choices[0], Mapping) else {}
    message = first.get("message") if isinstance(first, Mapping) else {}
    value = message.get("content") if isinstance(message, Mapping) else None
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = [str(item.get("text", "")) for item in value if isinstance(item, Mapping)]
        return "".join(parts)
    raise EmptyContentError(provider="openrouter")


class OpenRouterProvider:
    name = "openrouter"

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        model: str | None = None,
        timeout: float = 60.0,
        transport: Any | None = None,
        http_client: Any | None = None,
        http_referer: str | None = None,
        app_title: str | None = None,
        include_raw: bool = False,
    ) -> None:
        self._api_key = str(api_key or "")
        self.base_url = str(base_url or DEFAULT_BASE_URL).rstrip("/")
        self.model = model
        self.timeout = float(timeout)
        self._transport = transport
        self._http_client = http_client
        self._http_referer = http_referer
        self._app_title = app_title
        self.include_raw = bool(include_raw)

    def __repr__(self) -> str:  # never include the key
        return f"OpenRouterProvider(base_url={self.base_url!r}, model={self.model!r})"

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self._http_referer:
            headers["HTTP-Referer"] = self._http_referer
        if self._app_title:
            headers["X-Title"] = self._app_title
        return headers

    def _client(self) -> Any:
        if self._http_client is not None:
            return self._http_client
        return httpx.Client(timeout=self.timeout, transport=self._transport)

    def generate(self, request: GenerationRequest) -> GenerationResult:
        if not self._api_key:
            raise GatewayError("auth_error", "OpenRouter API key is not configured",
                               provider=self.name)
        model = request.model or self.model
        if not model:
            raise GatewayError("configuration_error", "OpenRouter model is not configured",
                               provider=self.name)
        payload: dict[str, Any] = {
            "model": model,
            "messages": request.normalized_messages(),
            "stream": False,
            "max_tokens": int(request.max_tokens),
        }
        if request.temperature is not None:
            payload["temperature"] = float(request.temperature)
        if request.response_format == "json":
            payload["response_format"] = {"type": "json_object"}
        timeout = float(request.timeout or self.timeout)
        started = time.perf_counter()
        client = self._client()
        try:
            response = client.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(), json=payload, timeout=timeout,
            )
        except httpx.TimeoutException as exc:
            raise TimeoutError("OpenRouter request timed out", provider=self.name) from exc
        except httpx.HTTPError as exc:
            raise TransportError(f"OpenRouter transport error: {type(exc).__name__}",
                                 provider=self.name) from exc
        finally:
            if self._http_client is None and hasattr(client, "close"):
                client.close()
        latency_ms = int((time.perf_counter() - started) * 1000)
        request_id = None
        try:
            request_id = response.headers.get("x-request-id")
        except Exception:  # noqa: BLE001
            request_id = None
        if response.status_code >= 400:
            retryable = response.status_code in (408, 429) or response.status_code >= 500
            raise HTTPStatusError(
                f"OpenRouter returned HTTP {response.status_code}",
                provider=self.name, http_status=response.status_code,
                retryable=retryable, request_id=request_id,
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise GatewayError("response_error", "OpenRouter response was not JSON",
                               provider=self.name) from exc
        content = _content(data)
        return GenerationResult(
            content=content,
            provider=self.name,
            model=str(data.get("model")) if isinstance(data, Mapping) and data.get("model") else model,
            request_id=request_id,
            usage=_usage(data.get("usage") if isinstance(data, Mapping) else None, latency_ms),
            latency_ms=latency_ms,
            raw=dict(data) if self.include_raw and isinstance(data, Mapping) else None,
        )


__all__ = ["OpenRouterProvider", "DEFAULT_BASE_URL"]
