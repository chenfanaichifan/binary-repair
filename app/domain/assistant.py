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
    title: str = Field(min_length=1, max_length=200)
    detail: str = Field(min_length=1, max_length=2000)
    state: Literal["next", "waiting", "done", "blocked"] = "next"


class AssistantQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=64)
    prompt: str = Field(min_length=1, max_length=1000)
    options: list[str] = Field(default_factory=list, max_length=8)


class AssistantPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    job_id: str = Field(min_length=1, max_length=64)
    mode: Literal["scripted", "llm"]
    summary: str = Field(min_length=1, max_length=2000)
    steps: list[AssistantStep] = Field(min_length=1, max_length=16)
    questions: list[AssistantQuestion] = Field(default_factory=list, max_length=8)
    model: str | None = Field(default=None, max_length=200)
    fallback_reason: str | None = Field(default=None, max_length=500)


def deterministic_plan(job: dict) -> AssistantPlan:
    """A stable plan derived only from job state; never from a model."""
    job_id = str(job.get("id") or "")
    phase = str(job.get("phase") or "draft")
    approved = bool((job.get("contract") or {}).get("approved"))
    steps = [
        AssistantStep(id="input", title="确认样本与输入",
                      detail="检查原始 ELF、缺陷描述、复现输入和有效输入测试。",
                      state="done"),
        AssistantStep(id="contract", title="复核安全契约",
                      detail="确认有效输入域、禁止行为与 invalid 输入结果；批准前不能启动。",
                      state="done" if approved else "blocked"),
        AssistantStep(id="route_a", title="Route A 指令修复",
                      detail="生成/检查指令级候选；无法安全放置时记录 unsupported。",
                      state="next" if approved else "waiting"),
        AssistantStep(id="route_b", title="Route B recovered-C 修复",
                      detail="先做 unchanged round-trip，再做安全编辑和回填。",
                      state="waiting"),
        AssistantStep(id="acceptance", title="V0–V5 共享验收",
                      detail="两路线使用同一测试和契约；required 未通过不得写 success。",
                      state="waiting"),
    ]
    if phase in {"finished", "cancelled"}:
        steps[-1].state = "done" if phase == "finished" else "blocked"
    return AssistantPlan(
        job_id=job_id,
        mode="scripted",
        summary="按输入 → 契约 → 双路线 → 共享验收推进；助手只给建议，不改变 verdict。",
        steps=steps,
        questions=[],
    )


__all__ = ["AssistantPlan", "AssistantQuestion", "AssistantStep", "deterministic_plan"]
