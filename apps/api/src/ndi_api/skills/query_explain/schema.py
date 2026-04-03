"""Input/output schemas for the Query Explain skill."""

from __future__ import annotations

from pydantic import Field

from ndi_api.skills.base import SkillInput, SkillOutput


class QueryExplainInput(SkillInput):
    """Input for query explanation."""

    query: str = Field("", description="The SQL/NoSQL query to explain")
    query_type: str = Field("sql", description="sql or nosql")


class QueryExplainOutput(SkillOutput):
    """Output of the query explanation skill."""

    explanation: str = Field("", description="Plain-language explanation")
    steps: list[str] = Field(default_factory=list, description="Step-by-step breakdown")
    columns_used: dict[str, str] = Field(default_factory=dict, description="Column → role")
