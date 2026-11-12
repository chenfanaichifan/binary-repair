"""Strict wire contract for the read-only binary reviewer.

The model sees the same structured verification packet a human sees.  It may
only return a recommendation plus review notes; it never returns a verdict,
evidence, hashes or an acceptance decision.  ``extra="forbid"`` and
``guard_model_payload`` make that boundary explicit rather than advisory.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ReviewConcern(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_id: str = Field(min_length=1, max_length=64)
    why: str = Field(min_length=1, max_length=400)

    @field_validator("check_id", "why")
    @classmethod
    def _strip_nonempty(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("review text must not be blank")
        return text


class AIReviewPayload(BaseModel):
    """One model review.  ``reject`` is accepted as a synonym for ``hold``."""

    model_config = ConfigDict(extra="forbid")

    recommendation: Literal["accept", "hold", "reject", "needs_more_checks"]
    summary: str = Field(min_length=1, max_length=600)
    concerns: list[ReviewConcern] = Field(default_factory=list, max_length=8)
    missing_evidence: list[str] = Field(default_factory=list, max_length=8)
    further_checks: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("summary")
    @classmethod
    def _summary_nonempty(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("summary must not be blank")
        return text

    @field_validator("missing_evidence", "further_checks")
    @classmethod
    def _text_list(cls, values: list[str]) -> list[str]:
        out: list[str] = []
        for value in values:
            text = str(value).strip()
            if not text:
                raise ValueError("review list entries must not be blank")
            if len(text) > 400:
                raise ValueError("review list entries must be at most 400 characters")
            out.append(text)
        return out

    @property
    def normalized_recommendation(self) -> Literal["accept", "hold", "needs_more_checks"]:
        return "hold" if self.recommendation == "reject" else self.recommendation  # type: ignore[return-value]


def validate_check_references(payload: AIReviewPayload, allowed_check_ids: set[str]) -> list[str]:
    """Return unknown concern check IDs; an empty list means all references resolve.

    ``scope`` is a deliberate virtual check ID for a concern that is about the
    overall claim rather than one check.
    """
    allowed = set(allowed_check_ids) | {"scope"}
    return sorted(
        {
            concern.check_id
            for concern in payload.concerns
            if concern.check_id not in allowed
        }
    )


__all__ = [
    "AIReviewPayload",
    "ReviewConcern",
    "validate_check_references",
]
