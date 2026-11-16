"""Token usage, latency and request/response identity records.

Usage values are never invented: absent provider fields stay ``None``.  A
strict identity check compares the model that was requested with the model the
provider actually reports; a mismatch is a typed error and is also retained as
a record for audit.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Mapping

from app.services.llm_gateway.errors import IdentityMismatchError, UsageError

__all__ = [
    "TokenUsage",
    "ModelIdentity",
    "RequestRecord",
    "UsageRecorder",
    "coerce_usage",
    "merge_usage",
    "measure_latency",
]


def _int_or_none(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


@dataclass(frozen=True)
class TokenUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None

    def to_dict(self) -> dict[str, int | None]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }

    @property
    def complete(self) -> bool:
        return None not in (self.prompt_tokens, self.completion_tokens,
                            self.total_tokens)

    def merged(self, other: "TokenUsage | None") -> "TokenUsage":
        if other is None:
            return self

        def add(a: int | None, b: int | None) -> int | None:
            # Aggregation sums available counters; a missing counter is not a
            # fabricated zero, but it also must not erase a known counter.
            if a is None:
                return b
            if b is None:
                return a
            return a + b

        return TokenUsage(add(self.prompt_tokens, other.prompt_tokens),
                          add(self.completion_tokens, other.completion_tokens),
                          add(self.total_tokens, other.total_tokens))


def coerce_usage(value: Any) -> TokenUsage | None:
    """Parse an OpenAI-compatible usage object without inventing fields."""
    if value is None:
        return None
    if isinstance(value, TokenUsage):
        return value
    if not isinstance(value, Mapping):
        raise UsageError("usage must be a mapping or TokenUsage")
    prompt = _int_or_none(value.get("prompt_tokens"))
    completion = _int_or_none(value.get("completion_tokens"))
    total = _int_or_none(value.get("total_tokens"))
    if prompt is None and completion is None and total is None:
        return None
    return TokenUsage(prompt, completion, total)


def merge_usage(records: list[TokenUsage | None]) -> TokenUsage:
    result = TokenUsage()
    for item in records:
        result = result.merged(item)
    return result


@dataclass(frozen=True)
class ModelIdentity:
    requested_model: str | None
    response_model: str | None
    provider: str
    request_id: str | None = None

    @property
    def matched(self) -> bool:
        if not self.requested_model or not self.response_model:
            return False
        return self.requested_model == self.response_model

    def require_match(self) -> "ModelIdentity":
        if not self.matched:
            raise IdentityMismatchError(
                "provider response model does not match the requested model",
                requested=self.requested_model,
                observed=self.response_model,
                provider=self.provider,
                details={"request_id": self.request_id or ""},
            )
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested_model": self.requested_model,
            "response_model": self.response_model,
            "matched": self.matched,
            "provider": self.provider,
            "request_id": self.request_id,
        }


@dataclass(frozen=True)
class RequestRecord:
    provider: str
    identity: ModelIdentity
    usage: TokenUsage | None
    latency_ms: int | None
    attempts: int = 1
    status: str = "ok"
    error_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "identity": self.identity.to_dict(),
            "usage": self.usage.to_dict() if self.usage else None,
            "latency_ms": self.latency_ms,
            "attempts": self.attempts,
            "status": self.status,
            "error_code": self.error_code,
        }


class UsageRecorder:
    """Bounded, thread-safe in-memory record of gateway calls."""

    def __init__(self, max_records: int = 1000) -> None:
        self._max = max(1, int(max_records))
        self._records: list[RequestRecord] = []
        self._lock = threading.Lock()

    def record(self, record: RequestRecord) -> None:
        with self._lock:
            self._records.append(record)
            if len(self._records) > self._max:
                del self._records[: len(self._records) - self._max]

    def records(self) -> list[RequestRecord]:
        with self._lock:
            return list(self._records)

    def summary(self) -> dict[str, Any]:
        records = self.records()
        usage = merge_usage([item.usage for item in records])
        latencies = [item.latency_ms for item in records
                     if item.latency_ms is not None]
        return {
            "calls": len(records),
            "ok": sum(1 for item in records if item.status == "ok"),
            "errors": sum(1 for item in records if item.status != "ok"),
            "identity_mismatches": sum(
                1 for item in records if not item.identity.matched),
            "usage": usage.to_dict(),
            "latency_ms_total": sum(latencies) if latencies else None,
            "latency_ms_avg": (
                round(sum(latencies) / len(latencies), 3) if latencies else None
            ),
        }


class measure_latency:
    """Context manager returning elapsed monotonic milliseconds."""

    def __init__(self) -> None:
        self.elapsed_ms: int | None = None
        self._start = 0.0

    def __enter__(self) -> "measure_latency":
        self._start = time.monotonic()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.elapsed_ms = int((time.monotonic() - self._start) * 1000)
