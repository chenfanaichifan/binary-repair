"""T8.2 LLM planner implementation (owner: M2).

M5 owns the stable seam and persistence.  M2 owns this module; it must return
an AssistantPlan matching app/domain/assistant.py.
"""

from __future__ import annotations

import json
from typing import Any

from app.domain.assistant import AssistantPlan
from app.services import model_calls


def _llm_plan(description: str, *, context: dict | None, client: Any) -> tuple[AssistantPlan, dict | None, str | None]:
    messages = [
        {"role": "system", "content": (
            "You are a BinaryRepair assistant. Return JSON only matching the "
            "AssistantPlan schema: plan_id, mode=llm, fallback=false, "
            "fallback_reason, model, tokens, steps 1..6 with id/kind "
            "(upload|question|review)/title/prompt/questions; review must be last. "
            "You must not approve contracts, start runs, or claim a verdict."
        )},
        {"role": "user", "content": json.dumps({
            "description": description, "context": context or {},
        }, sort_keys=True)},
    ]
    response = client.chat_json(messages, max_tokens=1200, thinking=False)
    payload = json.loads(getattr(response, "content", ""))
    plan = AssistantPlan.model_validate(payload)
    plan.mode = "llm"
    plan.fallback = False
    plan.fallback_reason = None
    plan.model = getattr(response, "model", None)
    usage = getattr(response, "usage", None)
    if usage:
        plan.tokens = {
            "prompt": int(usage.get("prompt_tokens", 0)),
            "completion": int(usage.get("completion_tokens", 0)),
        }
    return plan, usage, plan.model


def generate_plan(description: str, *, context: dict | None = None,
                  client: Any | None = None, mode: str = "llm") -> AssistantPlan:
    if client is None:
        raise ValueError("llm client is required")
    plan, usage, model = _llm_plan(description, context=context, client=client)
    model_calls.record_call(
        data_dir=context.get("data_dir") if context else "var",
        model_requested=model or "unknown", model_returned=model,
        status="accepted_for_assistant", route="assistant",
        usage=usage, job_id=(context or {}).get("job_id"),
        plan_id=plan.plan_id,
    )
    return plan


__all__ = ["generate_plan"]
