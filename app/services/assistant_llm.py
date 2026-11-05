"""T8.2 LLM planner implementation (owner: M2).

M5 owns the stable seam (``app/services/assistant.py``) and persistence
(``assistant_plans``).  This module only fills the ``client`` branch and must
return an object that validates as :class:`app.domain.assistant.AssistantPlan`
— the wire shape the GUI consumes.

Rules kept from the M2 draft:

* a model/schema/transport failure never raises and never returns half a plan;
  it returns the deterministic guide marked ``mode="llm"``, ``fallback=True``
  and a stable ``fallback_reason``;
* ``plan_id`` is always present (the model may omit it, the schema requires it);
* ``model`` / ``tokens`` are filled from the real response, never from what the
  model claims; missing usage stays ``None`` (never ``0``);
* ``model_calls`` gets one row per attempt, including fallbacks; no prompt,
  raw content or key is written to the row or to logs.

Not in scope: persistence, the deterministic planner, the HTTP surface, and the
``POST /api/assistant/plan`` endpoint (M1).
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from app.domain.assistant import AssistantPlan, deterministic_plan
from app.services import model_calls

__all__ = [
    "ASSISTANT_MODE_ENV",
    "DEFAULT_MODEL",
    "FallbackReason",
    "assistant_status",
    "build_messages",
    "generate_plan",
    "resolve_mode",
    "resolve_model",
    "validate_plan",
]

ASSISTANT_MODE_ENV = "BINARYREPAIR_ASSISTANT_MODE"
ASSISTANT_MODEL_ENV = "BINARYREPAIR_ASSISTANT_MODEL"
DEFAULT_MODEL = "deepseek-chat"
MAX_OUTPUT_TOKENS = 1200

MODES = ("llm", "deterministic", "fixture")

#: ``model_calls.status`` values.  A fallback is recorded as a fallback; it is
#: never stored as an accepted plan.
STATUS_OK = "accepted_for_assistant"
STATUS_FALLBACK = "fallback"


class FallbackReason:
    """Stable reason codes; the GUI translates them, it never infers them."""

    NO_CLIENT = "llm_client_not_configured"
    DISABLED = "assistant_mode_not_llm"
    TIMEOUT = "llm_timeout"
    NETWORK = "llm_network_error"
    EMPTY = "llm_empty_content"
    MALFORMED = "llm_invalid_json"
    SCHEMA = "llm_plan_schema_invalid"
    UNKNOWN = "llm_unknown_error"


class _TransportMissing(TypeError):
    """The injected client exposes neither ``chat_json`` nor ``complete``."""


@dataclass(frozen=True)
class _Response:
    content: Any
    model: str | None
    usage: dict[str, Any]
    request_id: str | None


def resolve_mode(value: str | None = None) -> str:
    """Read the assistant mode; unknown values are deterministic, never llm."""
    raw = (value if value is not None else os.environ.get(ASSISTANT_MODE_ENV, "")).strip().lower()
    return raw if raw in MODES else "deterministic"


def resolve_model(value: str | None = None) -> str:
    return (value or os.environ.get(ASSISTANT_MODEL_ENV, "")).strip() or DEFAULT_MODEL


def assistant_status(*, mode: str | None = None, client_configured: bool | None = None) -> dict[str, Any]:
    """Mode badge for the workbench.

    ``available`` is true only in llm mode with an injected client.  Without an
    explicit signal the page says "not wired", never "enabled".
    """
    resolved = resolve_mode(mode)
    if client_configured is None:
        client_configured = False
    return {
        "mode": resolved,
        "model": resolve_model() if resolved == "llm" else None,
        "available": resolved == "llm" and bool(client_configured),
        "fallback_reason": None if resolved != "llm" or client_configured else FallbackReason.NO_CLIENT,
    }


def _fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def build_messages(description: str, *, context: Mapping[str, Any] | None = None) -> list[dict[str, str]]:
    """Build the planning messages.

    The prompt contains only the user description and structured context.  It
    asks for one JSON object; the caller validates it, so a half-written answer
    falls back instead of being rendered.
    """
    system = (
        "You are the planning assistant of a binary-repair workbench.\n"
        "Return ONLY a JSON object matching this shape:\n"
        '{"plan_id":"string","mode":"llm","fallback":false,"fallback_reason":null,'
        '"model":null,"tokens":null,"steps":[{"id":"string","kind":"upload|question|review",'
        '"title":"string","prompt":"string","questions":[{"key":"string","label":"string",'
        '"input":"text|textarea","required":true,"ascii":true,"default":"string"}]}]}\n'
        "Rules:\n"
        "- Every step needs a non-empty id, title and prompt; ids are unique.\n"
        "- kind is upload, question or review; a question step needs >= 1 question.\n"
        "- questions are only allowed on question steps; keys are unique per step.\n"
        "- The last step must be kind=review.\n"
        "- 1 to 6 steps, in the order the user should follow.\n"
        "- Do not add fields outside this shape.\n"
        "- You guide the user; you never create jobs, start runs or judge repairs.\n"
        "- Never invent hashes, verdicts, evidence or token counts; model and tokens are filled by the caller.\n"
        "- Use ASCII English for any value that will be submitted to the backend.\n"
        "- No markdown fences, no commentary."
    )
    payload: dict[str, Any] = {"description": description}
    if context:
        # data_dir and job_id are routing hints, not prompt material.
        safe = {k: v for k, v in dict(context).items() if k not in ("data_dir",)}
        if safe:
            payload["context"] = safe
    user = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _errors_of(payload: Any) -> list[str]:
    """Schema errors without echoing model output.

    ``include_input=False`` matters: pydantic's default errors carry the offending
    value, which would put model text (and possibly user data) into a response.
    """
    if isinstance(payload, AssistantPlan):
        return []
    try:
        AssistantPlan.model_validate(payload)
    except Exception as exc:  # noqa: BLE001 - ValidationError and its subclasses
        errors = getattr(exc, "errors", None)
        if callable(errors):
            try:
                details = errors(include_input=False)
            except TypeError:  # pragma: no cover - older pydantic
                details = []
            result: list[str] = []
            for item in details[:20]:
                loc = ".".join(str(part) for part in item.get("loc", ())) or "plan"
                result.append(f"{loc}: {item.get('msg', 'invalid')}")
            return result or ["plan does not match AssistantPlan v1"]
        return ["plan does not match AssistantPlan v1"]
    return []


def validate_plan(plan: Any) -> list[str]:
    """Validate against AssistantPlan v1; ``[]`` means the GUI can render it."""
    return _errors_of(plan)


def _field(response: Any, name: str) -> Any:
    if isinstance(response, Mapping):
        return response.get(name)
    return getattr(response, name, None)


def _usage_of(response: Any) -> dict[str, Any]:
    usage = _field(response, "usage")
    if not isinstance(usage, Mapping):
        return {}
    result: dict[str, Any] = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens", "latency_ms"):
        value = usage.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            result[key] = value
    return result


def _tokens_of(usage: Mapping[str, Any]) -> dict[str, int] | None:
    prompt = usage.get("prompt_tokens")
    completion = usage.get("completion_tokens")
    if not isinstance(prompt, int) or not isinstance(completion, int):
        return None
    if prompt < 0 or completion < 0:
        return None
    return {"prompt": prompt, "completion": completion}


def _invoke(client: Any, messages: Sequence[Mapping[str, str]], model: str) -> Any:
    chat_json = getattr(client, "chat_json", None)
    if callable(chat_json):
        # The provider adapter used by M5: returns content/model/usage.
        return chat_json(messages, max_tokens=MAX_OUTPUT_TOKENS, thinking=False)
    complete = getattr(client, "complete", None)
    if callable(complete):
        return complete(messages, model=model)
    raise _TransportMissing("client exposes neither chat_json nor complete")


def _response_of(raw: Any) -> _Response:
    content = _field(raw, "content")
    model = _field(raw, "model")
    request_id = _field(raw, "request_id")
    return _Response(
        content=content,
        model=model if isinstance(model, str) and model else None,
        usage=_usage_of(raw),
        request_id=request_id if isinstance(request_id, str) and request_id else None,
    )


def _parse_content(content: Any) -> tuple[Any | None, str | None]:
    if isinstance(content, Mapping):
        return dict(content), None
    if not isinstance(content, str) or not content.strip():
        return None, FallbackReason.EMPTY
    text = content.strip()
    if text.startswith("```"):
        lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None, FallbackReason.MALFORMED
    if not isinstance(parsed, dict):
        return None, FallbackReason.SCHEMA
    return parsed, None


def _fallback(
    description: str,
    context: Mapping[str, Any] | None,
    *,
    reason: str,
    requested: str,
    returned: str | None = None,
    usage: Mapping[str, Any] | None = None,
) -> AssistantPlan:
    base = deterministic_plan(description, dict(context) if context else None)
    return base.model_copy(update={
        "mode": "llm",
        "fallback": True,
        "fallback_reason": reason,
        "model": returned,
        "tokens": _tokens_of(usage or {}),
    })


def _record(
    plan: AssistantPlan,
    *,
    context: Mapping[str, Any] | None,
    requested: str,
    returned: str | None,
    usage: Mapping[str, Any],
    request_id: str | None,
    status: str,
) -> None:
    data_dir = context.get("data_dir") if isinstance(context, Mapping) else None
    job_id = context.get("job_id") if isinstance(context, Mapping) else None
    try:
        model_calls.record_call(
            data_dir=data_dir or "var",
            model_requested=requested,
            model_returned=returned,
            status=status,
            route="assistant",
            usage=dict(usage) if usage else None,
            request_id=request_id,
            job_id=job_id,
            plan_id=plan.plan_id,
        )
    except Exception:  # noqa: BLE001 - audit failure must not break planning
        # A missing audit row is reported by ai_usage being unavailable; it is
        # never replaced by a fabricated zero.
        pass


def generate_plan(
    description: str,
    *,
    context: Mapping[str, Any] | None = None,
    client: Any | None = None,
    mode: str | None = "llm",
) -> AssistantPlan:
    """Return a plan for the ``client`` branch of the M5 seam.

    Called as ``assistant_llm.generate_plan(description, context=..., client=...,
    mode="llm")`` from ``app/services/assistant.py``.  Never raises on model
    failure; the caller persists whatever comes back.
    """
    resolved = resolve_mode(mode)
    requested = resolve_model()

    if resolved != "llm":
        # Defensive: the seam only routes here in llm mode.
        return deterministic_plan(description, dict(context) if context else None)
    if client is None:
        plan = _fallback(description, context, reason=FallbackReason.NO_CLIENT,
                         requested=requested)
        _record(plan, context=context, requested=requested, returned=None,
                usage={}, request_id=None, status=STATUS_FALLBACK)
        return plan

    messages = build_messages(description, context=context)
    try:
        raw = _invoke(client, messages, requested)
    except TimeoutError:
        plan = _fallback(description, context, reason=FallbackReason.TIMEOUT,
                         requested=requested)
        _record(plan, context=context, requested=requested, returned=None,
                usage={}, request_id=None, status=STATUS_FALLBACK)
        return plan
    except ConnectionError:
        plan = _fallback(description, context, reason=FallbackReason.NETWORK,
                         requested=requested)
        _record(plan, context=context, requested=requested, returned=None,
                usage={}, request_id=None, status=STATUS_FALLBACK)
        return plan
    except _TransportMissing:
        plan = _fallback(description, context, reason=FallbackReason.NO_CLIENT,
                         requested=requested)
        _record(plan, context=context, requested=requested, returned=None,
                usage={}, request_id=None, status=STATUS_FALLBACK)
        return plan
    except Exception:  # noqa: BLE001 - transport failures downgrade, never leak
        plan = _fallback(description, context, reason=FallbackReason.UNKNOWN,
                         requested=requested)
        _record(plan, context=context, requested=requested, returned=None,
                usage={}, request_id=None, status=STATUS_FALLBACK)
        return plan

    response = _response_of(raw)
    payload, parse_reason = _parse_content(response.content)
    if payload is None:
        plan = _fallback(description, context, reason=parse_reason or FallbackReason.EMPTY,
                         requested=requested, returned=response.model,
                         usage=response.usage)
        _record(plan, context=context, requested=requested, returned=response.model,
                usage=response.usage, request_id=response.request_id,
                status=STATUS_FALLBACK)
        return plan

    payload = dict(payload)
    # Identity and accounting are server-side facts; do not trust the model's.
    payload.setdefault("plan_id", uuid.uuid4().hex)
    payload["mode"] = "llm"
    payload["fallback"] = False
    payload["fallback_reason"] = None
    payload["model"] = response.model
    payload["tokens"] = _tokens_of(response.usage)

    errors = _errors_of(payload)
    if errors:
        plan = _fallback(description, context, reason=FallbackReason.SCHEMA,
                         requested=requested, returned=response.model,
                         usage=response.usage)
        _record(plan, context=context, requested=requested, returned=response.model,
                usage=response.usage, request_id=response.request_id,
                status=STATUS_FALLBACK)
        return plan

    plan = AssistantPlan.model_validate(payload)
    _record(plan, context=context, requested=requested, returned=response.model,
            usage=response.usage, request_id=response.request_id, status=STATUS_OK)
    return plan
