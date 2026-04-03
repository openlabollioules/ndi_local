"""Input/output schemas for the KPI Dashboard skill."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ndi_api.skills.base import SkillInput, SkillOutput


class KPIDashboardInput(SkillInput):
    """Input for KPI dashboard generation."""

    table_name: str | None = None
    sample_data: list[dict[str, Any]] = Field(default_factory=list)
    schema_info: dict | None = None


class NumericKPI(SkillOutput):
    """KPI for a numeric column."""

    column: str = ""
    total: float = 0.0
    average: float = 0.0
    minimum: float = 0.0
    maximum: float = 0.0


class KPIDashboardOutput(SkillOutput):
    """Output of the KPI dashboard skill."""

    table_name: str = ""
    total_rows: int = 0
    total_columns: int = 0
    date_range: str | None = Field(None, description="min → max date if applicable")
    numeric_kpis: list[dict[str, Any]] = Field(default_factory=list)
    distributions: dict[str, dict[str, str]] = Field(
        default_factory=dict,
        description="Column → {value: percentage}",
    )
    top_items: list[dict[str, str]] = Field(default_factory=list)
    alerts: list[str] = Field(default_factory=list)
