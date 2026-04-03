"""Input/output schemas for the Compare skill."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ndi_api.skills.base import SkillInput, SkillOutput


class CompareInput(SkillInput):
    """Input for comparison analysis."""

    subject_a: str = Field("", description="First subject (period, group, etc.)")
    subject_b: str = Field("", description="Second subject")
    metric: str = Field("", description="Metric to compare on")
    sample_data: list[dict[str, Any]] = Field(default_factory=list)


class ComparisonRow(SkillOutput):
    """A single row in the comparison table."""

    metric: str = ""
    value_a: str = ""
    value_b: str = ""
    delta: str = ""
    variation_pct: str = ""


class CompareOutput(SkillOutput):
    """Output of the comparison skill."""

    subject_a: str = ""
    subject_b: str = ""
    summary: str = Field("", description="Key takeaway in 1-2 sentences")
    details: list[dict[str, str]] = Field(default_factory=list, description="Comparison rows")
    trends: list[str] = Field(default_factory=list)
    alerts: list[str] = Field(default_factory=list, description="Notable points of attention")
