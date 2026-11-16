"""Ollama local chat adapter."""
from __future__ import annotations

import json
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

DEFAULT_BASE_URL = "http://127.0.0.1:11434"


def _usage(data: Mapping[str, Any], latency_ms: int) -> dict[str, int]:
    result: dict[str, int] = {}
    prompt = data.get("prompt_eval_count")
    completion = data.get("eval_count")
    if isinstance(prompt, int) and not isinstance(prompt, bool) and prompt >= 0:
        result["prompt_tokens"] = prompt
    if isinstance(completion, int) and not isinstance(completion, bool) and completion >= 0:
        result["completion_tokens"] = completion
    if "prompt_tokens" in result and "completion_tokens" in result:
        result["total_tokens"] = result["prompt_tokens"] + result["completion_tokens"]
    result["latency_ms"] = max(0, int(latency_ms))
    return result


class OllamaProvider:
    name = "ollama"

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        model: str | None = None,
        timeout: float = 60.0,
        transport: Any | None = None,
        http_client: Any | None = None,
        keep_alive: str | None = None,
        include_raw: bool = False,
    ) -> None:
        self.base_url = str(base_url or DEFAULT_BASE_URL).rstrip("/")
        self.model = model
        self.timeout = float(timeout)
        self._transport = transport
        self._http_client = http_client
        self.keep_alive = keep_alive
        self.include_raw = bool(include_raw)

    def __repr__(self) -> str:
        return f"OllamaProvider(base_url={self.base_url!r}, model={self.model!r})"

    def _client(self) -> Any:
        if self._http_client is not None:
            return self._http_client
        return httpx.Client(timeout=self.timeout, transport=self._transport)

    def generate(self, request: GenerationRequest) -> GenerationResult:
        model = request.model or self.model
        if not model:
            raise GatewayError("configuration_error", "Ollama model is not configured",
                               provider=self.name)
        options: dict[str, Any] = {
            "num_predict": int(request.max_tokens),
        }
        if request.temperature is not None:
            options["temperature"] = float(request.temperature)
        payload: dict[str, Any] = {
            "model": model,
            "messages": request.normalized_messages(),
            "stream": False,
            "options": options,
        }
        if self.keep_alive:
            payload["keep_alive"] = self.keep_alive
        if request.response_format == "json":
            payload["format"] = "json"
        timeout = float(request.timeout or self.timeout)
        started = time.perf_counter()
        client = self._client()
        try:
            response = client.post(
                f"{self.base_url}/api/chat",
                json=payload, timeout=timeout,
            )
        except httpx.TimeoutException as exc:
            raise TimeoutError("Ollama request timed out", provider=self.name) from exc
        except httpx.HTTPError as exc:
            raise TransportError(f"Ollama transport error: {type(exc).__name__}",
                                 provider=self.name) from exc
        finally:
            if self._http_client is None and hasattr(client, "close"):
                client.close()
        latency_ms = int((time.perf_counter() - started) * 1000)
        if response.status_code >= 400:
            raise HTTPStatusError(
                f"Ollama returned HTTP {response.status_code}",
                provider=self.name, http_status=response.status_code,
                retryable=response.status_code >= 500,
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise GatewayError("response_error", "Ollama response was not JSON",
                               provider=self.name) from exc
        if not isinstance(data, Mapping):
            raise GatewayError("response_error", "Ollama response was not an object",
                               provider=self.name)
        message = data.get("message")
        value = message.get("content") if isinstance(message, Mapping) else None
        if not isinstance(value, str) or not value.strip():
            raise EmptyContentError(provider=self.name)
        return GenerationResult(
            content=value,
            provider=self.name,
            model=str(data.get("model") or model),
            request_id=str(data.get("created_at") or "") or None,
            usage=_usage(data, latency_ms),
            latency_ms=latency_ms,
            raw=dict(data) if self.include_raw else None,
        )

    def list_models(self) -> list[str]:
        client = self._client()
        try:
            response = client.get(f"{self.base_url}/api/tags", timeout=self.timeout)
        except httpx.HTTPError as exc:
            raise TransportError(f"Ollama transport error: {type(exc).__name__}",
                                 provider=self.name) from exc
        finally:
            if self._http_client is None and hasattr(client, "close"):
                client.close()
        if response.status_code >= 400:
            raise HTTPStatusError(f"Ollama returned HTTP {response.status_code}",
                                  provider=self.name,
                                  http_status=response.status_code)
        data = response.json()
        return [str(item.get("name")) for item in data.get("models", [])
                if isinstance(item, Mapping) and item.get("name")]


__all__ = ["OllamaProvider", "DEFAULT_BASE_URL"]
