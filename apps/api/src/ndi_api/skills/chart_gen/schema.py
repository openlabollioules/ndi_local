"""Input/output schemas for the Chart Generation skill."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ndi_api.skills.base import SkillInput, SkillOutput


class ChartInput(SkillInput):
    """Input for chart suggestion."""

    rows: list[dict[str, Any]] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)


class ChartOutput(SkillOutput):
    """Output of the chart suggestion skill."""

    chart_type: str | None = Field(
        None,
        description="Suggested chart type: bar, line, pie, area, scatter, radar",
    )
    chart_config: dict[str, Any] | None = Field(None, description="Full chart configuration for the frontend")
    applicable: bool = Field(True, description="Whether a chart is appropriate")
