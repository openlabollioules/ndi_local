"""Input/output schemas for the Data Quality skill."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ndi_api.skills.base import SkillInput, SkillOutput


class DataQualityInput(SkillInput):
    """Input for data quality audit."""

    table_name: str | None = None
    sample_data: list[dict[str, Any]] = Field(default_factory=list)
    schema_info: dict | None = None


class ColumnQuality(SkillOutput):
    """Quality metrics for a single column."""

    column: str = ""
    completeness_pct: float = 0.0
    null_count: int = 0
    unique_count: int = 0
    type_issues: list[str] = Field(default_factory=list)


class DataQualityOutput(SkillOutput):
    """Output of the data quality audit."""

    table_name: str = ""
    total_rows: int = 0
    score: float = Field(0.0, description="Quality score 0-10")
    completeness: dict[str, float] = Field(default_factory=dict, description="Column → % filled")
    duplicate_count: int = 0
    outlier_columns: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
