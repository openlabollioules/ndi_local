"""Input/output schemas for the SQL Query skill."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ndi_api.skills.base import SkillInput, SkillOutput


class SQLQueryInput(SkillInput):
    """Input for SQL query generation."""

    schema_context: str = Field("", description="Schema + relation context injected by the pipeline")
    max_rows: int = Field(50, description="Default LIMIT for generated queries")


class SQLQueryOutput(SkillOutput):
    """Output of the SQL query skill."""

    query: str = Field("", description="Generated SQL query")
    rows: list[dict[str, Any]] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)
    row_count: int = 0
    error: str | None = None
