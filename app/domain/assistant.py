"""Assistant plan schema and deterministic v1 planner.

The assistant is guidance only: it cannot approve, start a run, or write a
verdict.  Plans are persisted as data so the controller/UI can render exactly
what was proposed, with the mode and model metadata visible.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AssistantStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=64)
    kind: Literal["input", "action", "review"] = "action"
    title: str = Field(min_length=1, max_length=200)
    detail: str = Field(min_length=1, max_length=2000)
    state: Literal["next", "waiting", "done", "blocked"] = "next"


class AssistantQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=64)
    prompt: str = Field(min_length=1, max_length=1000)
    options: list[str] = Field(default_factory=list, max_length=8)
    required: bool = True
    allow_free_text: bool = False


class AssistantPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    job_id: str = Field(min_length=1, max_length=64)
    mode: Literal["scripted", "llm"]
    summary: str = Field(min_length=1, max_length=2000)
    steps: list[AssistantStep] = Field(min_length=1, max_length=6)
    questions: list[AssistantQuestion] = Field(default_factory=list, max_length=8)
    model: str | None = Field(default=None, max_length=200)
    fallback_reason: str | None = Field(default=None, max_length=500)


def deterministic_plan(job: dict) -> AssistantPlan:
    """A stable plan derived only from job state; never from a model."""
    job_id = str(job.get("id") or "")
    phase = str(job.get("phase") or "draft")
    approved = bool((job.get("contract") or {}).get("approved"))
    steps = [
        AssistantStep(id="input", kind="input", title="Confirm sample and inputs",
                      detail="Check the original ELF, defect description, reproducer, and valid input tests.",
                      state="done"),
        AssistantStep(id="contract", kind="action", title="Review safety contract",
                      detail="Confirm valid input domain, forbidden behavior, and invalid-input result; do not start before approval.",
                      state="done" if approved else "blocked"),
        AssistantStep(id="route_a", kind="action", title="Route A instruction repair",
                      detail="Generate and inspect the instruction-level candidate; record unsupported when placement is unsafe.",
                      state="next" if approved else "waiting"),
        AssistantStep(id="route_b", kind="action", title="Route B recovered-C repair",
                      detail="Run the unchanged round trip first, then apply the safety edit and reintegrate.",
                      state="waiting"),
        AssistantStep(id="acceptance", kind="action", title="Shared V0-V5 acceptance",
                      detail="Both routes use the same tests and contract; a required miss must not be written as success.",
                      state="waiting"),
        AssistantStep(id="review", kind="review", title="Review evidence and limits",
                      detail="Review both routes, V4 scope, and residual unknowns before any human approval.",
                      state="waiting"),
    ]
    if phase in {"finished", "cancelled"}:
        steps[-1].state = "done" if phase == "finished" else "blocked"
    return AssistantPlan(
        job_id=job_id,
        mode="scripted",
        summary="Proceed input -> contract -> both routes -> shared acceptance -> review; guidance only, never a verdict.",
        steps=steps,
        questions=[],
    )


__all__ = ["AssistantPlan", "AssistantQuestion", "AssistantStep", "deterministic_plan"]
