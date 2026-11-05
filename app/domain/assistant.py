"""Assistant plan contract (T8.1) and the deterministic planner.

The plan is guidance only. It cannot approve a contract, start a run, or write
a verdict.  The wire shape below is the exact shape consumed by the GUI.
"""

from __future__ import annotations

import re
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_ASCII = re.compile(r"^[\x00-\x7f]*$")


class AssistantQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=200)
    input: Literal["text", "textarea"]
    required: bool
    ascii: bool
    default: str | None = Field(default=None, max_length=2000)

    @field_validator("default")
    @classmethod
    def _ascii_default(cls, value: str | None) -> str | None:
        if value is not None and not _ASCII.match(value):
            raise ValueError("question default must be ASCII")
        return value


class AssistantStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=64)
    kind: Literal["upload", "question", "review"]
    title: str = Field(min_length=1, max_length=200)
    prompt: str = Field(min_length=1, max_length=2000)
    questions: list[AssistantQuestion] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def _check_step(self) -> "AssistantStep":
        if self.kind == "question" and not self.questions:
            raise ValueError("question step must contain at least one question")
        if self.kind != "question" and self.questions:
            raise ValueError("only question steps may contain questions")
        keys = [q.key for q in self.questions]
        if len(keys) != len(set(keys)):
            raise ValueError("question keys must be unique within a step")
        return self


class AssistantPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_id: str = Field(min_length=1, max_length=64)
    mode: Literal["deterministic", "llm"]
    fallback: bool = False
    fallback_reason: str | None = Field(default=None, max_length=500)
    model: str | None = Field(default=None, max_length=200)
    tokens: dict[str, int] | None = None
    steps: list[AssistantStep] = Field(min_length=1, max_length=6)

    @model_validator(mode="after")
    def _check_plan(self) -> "AssistantPlan":
        if self.steps[-1].kind != "review":
            raise ValueError("review must be the last step")
        ids = [step.id for step in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("step ids must be unique")
        if self.fallback and not self.fallback_reason:
            raise ValueError("fallback=true requires fallback_reason")
        if self.tokens is not None:
            prompt = self.tokens.get("prompt")
            completion = self.tokens.get("completion")
            if not isinstance(prompt, int) or not isinstance(completion, int):
                raise ValueError("tokens must contain integer prompt/completion")
            if prompt < 0 or completion < 0:
                raise ValueError("tokens must be non-negative")
        return self


def deterministic_plan(description: str, context: dict | None = None) -> AssistantPlan:
    """Pure deterministic planner; no env, no DB, no network."""
    text = " ".join(str(description or "").split())
    if not text:
        text = "Repair the reported binary vulnerability."
    # Keep the default contract-safe: descriptions may contain non-ASCII.
    safe_default = "fix the reported binary vulnerability"
    return AssistantPlan(
        plan_id=uuid.uuid4().hex,
        mode="deterministic",
        fallback=False,
        fallback_reason=None,
        model=None,
        tokens=None,
        steps=[
            AssistantStep(
                id="sample", kind="upload", title="Step 1 - Sample",
                prompt="Upload the binary to repair.",
            ),
            AssistantStep(
                id="defect", kind="question", title="Step 2 - Defect",
                prompt="Describe the defect in one sentence.",
                questions=[AssistantQuestion(
                    key="defect", label="Defect (ASCII)", input="textarea",
                    required=True, ascii=True, default=safe_default,
                )],
            ),
            AssistantStep(
                id="valid", kind="question", title="Step 3 - Valid inputs",
                prompt="List the valid inputs and expected behavior.",
                questions=[AssistantQuestion(
                    key="valid_tests", label="Valid tests (ASCII)", input="textarea",
                    required=True, ascii=True, default="valid: hello",
                )],
            ),
            AssistantStep(
                id="environment", kind="question", title="Step 4 - Environment",
                prompt="State the execution environment and constraints.",
                questions=[AssistantQuestion(
                    key="environment", label="Environment (ASCII)", input="text",
                    required=True, ascii=True, default="Ubuntu x86-64 guest",
                )],
            ),
            AssistantStep(
                id="review", kind="review", title="Step 5 - Review and create",
                prompt="Review the order and click Create task when ready.",
            ),
        ],
    )


# Compatibility alias for callers that used the older name.
plan = deterministic_plan

__all__ = ["AssistantPlan", "AssistantQuestion", "AssistantStep", "deterministic_plan", "plan"]
