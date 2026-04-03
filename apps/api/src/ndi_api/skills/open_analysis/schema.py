"""Input/output schemas for the Open Analysis skill."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ndi_api.skills.base import SkillInput, SkillOutput


class AnalysisInput(SkillInput):
    """Input for open-ended analysis."""

    sample_data: list[dict[str, Any]] = Field(default_factory=list)
    analysis_type: str = Field("general", description="coherence, patterns, distribution, etc.")
    schema_info: dict | None = None


class AnalysisOutput(SkillOutput):
    """Output of the open analysis skill."""

    analysis_type: str = "general"
    sample_size: int = 0
    sections: dict[str, str] = Field(
        default_factory=dict,
        description="Parsed sections: ANALYSE, SYNTHESE, DETAILS, etc.",
    )
