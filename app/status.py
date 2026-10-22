"""Honest overall-result derivation shared by the server-rendered page.

Rules (mirror of ``static/js/poll.js``):

- not finished (and not cancelled) -> "—"
- any route cancelled            -> "已取消"
- any route error                -> "失败（执行错误）"
- every route success_within_scope -> "成功（声明范围内）"
- otherwise                      -> "未达成（需两条路线各自成功）"

The overall result must never claim success unless *both* routes succeeded
within their declared scope. "finished" is a phase, not a verdict.
"""

from __future__ import annotations

from typing import Any


def overall_result(snapshot: dict[str, Any]) -> dict[str, str]:
    """Return ``{"key": ..., "label_zh": ...}`` for the job header badge."""

    routes = snapshot.get("routes") or {}
    outcomes = [route.get("outcome") for route in routes.values()]
    finished = snapshot.get("phase") == "finished" or bool(snapshot.get("cancelled"))

    if not finished:
        return {"key": "none", "label_zh": "—"}
    if any(outcome == "cancelled" for outcome in outcomes):
        return {"key": "cancelled", "label_zh": "已取消"}
    if any(outcome == "error" for outcome in outcomes):
        return {"key": "error", "label_zh": "失败（执行错误）"}
    if outcomes and all(outcome == "success_within_scope" for outcome in outcomes):
        return {"key": "success_within_scope", "label_zh": "成功（声明范围内）"}
    return {"key": "rejected", "label_zh": "未达成（需两条路线各自成功）"}
