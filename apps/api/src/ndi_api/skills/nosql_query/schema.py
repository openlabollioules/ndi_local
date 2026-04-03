"""Input/output schemas for the NoSQL Query skill."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ndi_api.skills.base import SkillInput, SkillOutput


class NoSQLQueryInput(SkillInput):
    """Input for NoSQL query generation."""

    schema_context: str = Field("", description="Collection/field context")


class NoSQLQueryOutput(SkillOutput):
    """Output of the NoSQL query skill."""

    json_query: str = Field("", description="Generated JSON query (compact, single line)")
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    error: str | None = None
