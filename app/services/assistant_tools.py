"""Agent-facing tool registry over the M5 Gate 2b adapters (contracts v2).

The agent never talks to the runners or the controller directly.  It calls
``call_tool(name, arguments)`` with a v2 request envelope and receives the v2
response envelope.  ``tool_specs()`` exposes the same three tools as JSON
schemas so a planner can advertise them to the model.

Boundary: this module adds no executor and no gate.  Every call delegates to
``tools.mcp_tool_adapters``; an adapter ``ToolError`` becomes a stable status
envelope instead of an exception leaking into the runtime.
"""

from __future__ import annotations

from typing import Any, Callable

from tools import mcp_tool_adapters

SCHEMA_VERSION = 2

_RUN_CASE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["schema_version", "binary_path", "tests_dir", "input_mode"],
    "properties": {
        "schema_version": {"const": SCHEMA_VERSION},
        "case_id": {"type": "string"},
        "binary_path": {"type": "string"},
        "contract_path": {"type": "string"},
        "tests_dir": {"type": "string"},
        "original_path": {"type": "string"},
        "input_mode": {"enum": ["none", "argv"]},
        "timeout_ms": {"type": "integer", "minimum": 1},
        "evidence_path": {"type": "string"},
        "idempotency_key": {"type": "string"},
    },
}

_READ_EVIDENCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["schema_version", "attempt_id"],
    "properties": {
        "schema_version": {"const": SCHEMA_VERSION},
        "job_id": {"type": "string"},
        "attempt_id": {"type": "string"},
        "base_url": {"type": "string"},
        "timeout_ms": {"type": "integer", "minimum": 1},
    },
}

_APPLY_CANDIDATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["schema_version", "job_id", "bundle_path", "candidate_sha256"],
    "properties": {
        "schema_version": {"const": SCHEMA_VERSION},
        "job_id": {"type": "string"},
        "run_id": {"type": ["string", "null"]},
        "attempt_id": {"type": ["string", "null"]},
        "route": {"type": "string"},
        "candidate_path": {"type": "string"},
        "candidate_sha256": {"type": "string", "minLength": 64, "maxLength": 64},
        "contract_revision": {"type": "integer"},
        "manifest_sha256": {"type": "string"},
        "bundle_path": {"type": "string"},
        "data_dir": {"type": "string"},
        "no_trigger": {"type": "boolean"},
        "dry_run": {"type": "boolean"},
        "idempotency_key": {"type": "string"},
    },
}

_ADAPTERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "run_case": mcp_tool_adapters.run_case,
    "read_evidence": mcp_tool_adapters.read_evidence,
    "apply_candidate": mcp_tool_adapters.apply_candidate,
}

_SCHEMAS: dict[str, dict[str, Any]] = {
    "run_case": _RUN_CASE_SCHEMA,
    "read_evidence": _READ_EVIDENCE_SCHEMA,
    "apply_candidate": _APPLY_CANDIDATE_SCHEMA,
}

_DESCRIPTIONS = {
    "run_case": (
        "Run one repair case through the Route B runner. Dispatch is chosen by "
        "input_mode: none + original_path compares bytes, none alone uses the "
        "native no-input path, argv uses valid.json/invalid.json. stdin and a "
        "raw argv list are rejected."
    ),
    "read_evidence": (
        "Read the persisted evidence for one attempt, including gates and the "
        "v3 summary. input_mode is authoritative for invalid applicability."
    ),
    "apply_candidate": (
        "Create or reuse the run/attempt metadata, assert the candidate hash, "
        "and delegate the bundle to the existing ingest writer. Never builds or "
        "executes a candidate."
    ),
}

_REJECTED_REASONS = {"candidate_hash_mismatch", "bundle_invalid"}
_INVALID_REASONS = {"invalid_request", "pre_layer_required", "binary_not_found"}


class ToolCallError(ValueError):
    """The agent asked for an unknown tool or a malformed envelope."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(detail or reason)
        self.reason = reason
        self.detail = detail or reason


def tool_names() -> list[str]:
    return list(_ADAPTERS)


def tool_specs() -> list[dict[str, Any]]:
    """OpenAI-style function specs for the three v2 tools."""

    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": _DESCRIPTIONS[name],
                "parameters": _SCHEMAS[name],
            },
        }
        for name in _ADAPTERS
    ]


def _check_envelope(name: str, arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise ToolCallError("invalid_request", "arguments must be an object")
    if arguments.get("schema_version") != SCHEMA_VERSION:
        raise ToolCallError("invalid_request", "schema_version must be 2")
    required = _SCHEMAS[name].get("required", [])
    missing = [key for key in required if arguments.get(key) in (None, "")]
    if missing:
        raise ToolCallError("invalid_request", f"missing: {', '.join(missing)}")
    return arguments


def _status_for(name: str, reason: str) -> str:
    if name == "apply_candidate" and reason in _REJECTED_REASONS:
        return "rejected"
    if reason in _INVALID_REASONS:
        return "invalid_request"
    return "error"


def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Call one v2 tool and always return a status envelope.

    Unknown tools and malformed envelopes raise ``ToolCallError`` because they
    are runtime bugs; adapter-level failures become ``status`` values because
    the agent must be able to observe and retry them.
    """

    adapter = _ADAPTERS.get(name)
    if adapter is None:
        raise ToolCallError("unknown_tool", f"unknown tool: {name!r}")
    request = _check_envelope(name, arguments)
    try:
        return adapter(dict(request))
    except mcp_tool_adapters.ToolError as exc:
        envelope: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "tool": name,
            "status": _status_for(name, exc.reason),
            "reason": exc.reason,
            "detail": exc.detail,
        }
        if name == "apply_candidate":
            envelope["rejected_reason"] = exc.reason
        return envelope


__all__ = [
    "SCHEMA_VERSION",
    "ToolCallError",
    "call_tool",
    "tool_names",
    "tool_specs",
]
