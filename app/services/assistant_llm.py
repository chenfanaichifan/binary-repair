"""T8.2 LLM planner implementation (owner: M2).

M5 owns the stable seam in ``app.services.assistant``: schema, persistence,
deterministic planner, and the injectable ``planner``/``client`` call.  M2 owns
this module: prompt, provider call, usage recording, and fake-transport tests.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.domain.assistant import AssistantPlan
from app.services import jobs, model_calls
from app.services.assistant import assistant_context, save_plan
from binaryrepair_ai.client import DeepSeekClient
from binaryrepair_ai.settings import Settings


def _llm_plan(
    job: Any, *, data_dir: str | Path, client: Any
) -> tuple[AssistantPlan, dict | None, str | None]:
    context = assistant_context(job, data_dir=data_dir)
    messages = [
        {"role": "system", "content": (
            "You are a BinaryRepair assistant. Return JSON only, matching the "
            "AssistantPlan schema: schema_version, job_id, mode, summary, steps "
            "(id/title/detail/state), questions (id/prompt/options). "
            "You must not approve contracts, start runs, or claim a verdict."
        )},
        {"role": "user", "content": json.dumps(context, sort_keys=True)},
    ]
    response = client.chat_json(messages, max_tokens=1200, thinking=False)
    payload = json.loads(getattr(response, "content", ""))
    plan = AssistantPlan.model_validate(payload)
    if plan.job_id != job.id:
        raise ValueError("LLM plan job_id does not match job")
    plan.mode = "llm"
    plan.model = getattr(response, "model", None)
    plan.fallback_reason = None
    return plan, getattr(response, "usage", None), plan.model


def generate_llm_plan(
    *, job_id: str, data_dir: str | Path, client: Any | None = None
) -> dict[str, Any]:
    """Call the model, validate the plan, record usage, then persist."""
    job = jobs.get_job(job_id, data_dir=data_dir)
    if job is None:
        raise ValueError("job not found")
    if client is None:
        client = DeepSeekClient(Settings.from_env())
    plan, usage, model = _llm_plan(job, data_dir=data_dir, client=client)
    call_id = model_calls.record_call(
        data_dir=data_dir, model_requested=model or "unknown",
        model_returned=model, status="accepted_for_assistant",
        route="assistant", usage=usage,
    )
    stored_usage = dict(usage or {})
    stored_usage["model_call_id"] = call_id
    return save_plan(job.id, plan, data_dir=data_dir, model=model, usage=stored_usage)


__all__ = ["generate_llm_plan"]
