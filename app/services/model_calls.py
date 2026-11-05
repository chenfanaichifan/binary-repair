"""Persist and aggregate model-call records.

The provider adapter may fail before a candidate exists; these records are
audit/cost data, never evidence of correctness.  ``ai_usage`` is either the
real token counts or ``None``; it is never a fabricated string.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.db.connection import connect


def record_call(
    *,
    data_dir: str | Path,
    model_requested: str,
    status: str,
    attempt_id: str | None = None,
    route: str | None = None,
    model_returned: str | None = None,
    usage: dict[str, Any] | None = None,
    latency_ms: int | None = None,
    request_id: str | None = None,
    assistant_plan_id: str | None = None,
) -> str:
    usage = usage or {}
    prompt = usage.get("prompt_tokens")
    completion = usage.get("completion_tokens")
    total = usage.get("total_tokens")
    if total is None and prompt is not None and completion is not None:
        total = int(prompt) + int(completion)
    call_id = uuid.uuid4().hex
    connection = connect(data_dir)
    try:
        with connection:
            connection.execute(
                "INSERT INTO model_calls "
                "(id, attempt_id, route, model_requested, model_returned, status, "
                "prompt_tokens, completion_tokens, total_tokens, estimated_cost_usd, "
                "latency_ms, request_id, usage_json, assistant_plan_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    call_id, attempt_id, route, model_requested, model_returned, status,
                    int(prompt) if prompt is not None else None,
                    int(completion) if completion is not None else None,
                    int(total) if total is not None else None,
                    usage.get("estimated_cost_usd"),
                    latency_ms, request_id,
                    json.dumps(usage, sort_keys=True) if usage else None,
                    assistant_plan_id,
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                ),
            )
    finally:
        connection.close()
    return call_id


def aggregate_usage(
    *, data_dir: str | Path, attempt_id: str | None = None, route: str | None = None
) -> dict[str, int] | None:
    where = []
    params: list[Any] = []
    if attempt_id is not None:
        where.append("attempt_id = ?")
        params.append(attempt_id)
    if route is not None:
        where.append("route = ?")
        params.append(route)
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    connection = connect(data_dir)
    try:
        rows = connection.execute(
            "SELECT prompt_tokens, completion_tokens, total_tokens FROM model_calls" + clause,
            params,
        ).fetchall()
    finally:
        connection.close()
    if not rows:
        return None
    # Missing token fields are unavailable; do not turn them into zero.
    if any(row["prompt_tokens"] is None or row["completion_tokens"] is None for row in rows):
        return None
    return {
        "input_tokens": sum(int(row["prompt_tokens"]) for row in rows),
        "output_tokens": sum(int(row["completion_tokens"]) for row in rows),
    }


__all__ = ["aggregate_usage", "record_call", "record_provider_result"]


def record_provider_result(
    *, data_dir: str | Path, result: Any, route: str,
    attempt_id: str | None = None,
) -> str | None:
    """Record a DeepSeekProvider result (success or typed failure).

    The provider result's ``record`` carries model/usage/latency/request id;
    its own words never become a verdict.
    """
    record = getattr(result, "record", None)
    if record is None:
        return None
    usage = getattr(record, "usage", None)
    return record_call(
        data_dir=data_dir,
        attempt_id=attempt_id,
        route=route,
        model_requested=str(getattr(record, "model", "") or "unknown"),
        model_returned=getattr(record, "model_returned", None),
        status=str(getattr(record, "status", "unknown")),
        usage=usage,
        latency_ms=getattr(record, "latency_ms", None),
        request_id=getattr(record, "request_id", None),
    )
