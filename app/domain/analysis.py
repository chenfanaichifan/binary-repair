"""Schema for the analysis artifacts shown in the result report.

These are candidate-derived explanations, not acceptance evidence.  They are
stored as artifacts so the GUI/report can render exactly what was reviewed.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AnalysisArtifacts(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int = 1
    candidate_sha256: str = Field(min_length=64, max_length=64)
    expected_effects: list[str] = Field(min_length=1, max_length=32)
    assumptions: list[str] = Field(default_factory=list, max_length=32)
    uncertainties: list[str] = Field(default_factory=list, max_length=32)


ANALYSIS_ROLES = {
    "analysis_expected_effects": "expected_effects",
    "analysis_assumptions": "assumptions",
    "analysis_uncertainties": "uncertainties",
}


__all__ = ["ANALYSIS_ROLES", "AnalysisArtifacts"]
