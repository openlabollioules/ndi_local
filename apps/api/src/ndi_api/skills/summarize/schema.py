"""Input/output schemas for the Summarize skill."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ndi_api.skills.base import SkillInput, SkillOutput


class SummarizeInput(SkillInput):
    """Input for result summarization."""

    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    query: str = ""


class SummarizeOutput(SkillOutput):
    """Output of the summarize skill."""

    key_figures: dict[str, str] = Field(default_factory=dict, description="Metric → value")
    top_items: list[dict[str, str]] = Field(default_factory=list, description="Top N items")
    bottom_items: list[dict[str, str]] = Field(default_factory=list, description="Bottom N items")
    distribution: dict[str, str] = Field(default_factory=dict, description="Category → percentage")
    brief: str = Field("", description="1-2 sentence conclusion")
