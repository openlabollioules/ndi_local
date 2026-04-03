"""Input/output schemas for the Data Conformity skill."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ndi_api.skills.base import SkillInput, SkillOutput


class ConformityRule(BaseModel):
    """A single conformity rule to check."""

    description: str = Field(..., description="Rule in natural language")
    column: str | None = Field(None, description="Target column (None = cross-column)")
    rule_type: str = Field(
        "custom",
        description="enum | format | range | coherence | completeness | uniqueness | custom",
    )
    # Optional structured params for pre-filtering
    allowed_values: list[str] | None = None
    min_value: float | None = None
    max_value: float | None = None
    pattern: str | None = None  # regex
    required_if: str | None = None  # condition for completeness rules


class ConformityInput(SkillInput):
    """Input for conformity audit."""

    table_name: str | None = None
    rules: list[ConformityRule] = Field(default_factory=list)
    sample_data: list[dict[str, Any]] = Field(default_factory=list)


class Violation(BaseModel):
    """A single detected violation."""

    row_index: int
    column: str
    current_value: Any
    expected: str
    rule: str
    severity: str = Field("warning", description="error | warning | info")
    suggested_fix: Any | None = None


class RuleResult(BaseModel):
    """Result for a single rule check."""

    rule: str
    status: str = Field("ok", description="ok | violated")
    violation_count: int = 0
    examples: list[Violation] = Field(default_factory=list)


class ConformityOutput(SkillOutput):
    """Output of the conformity audit."""

    table_name: str = ""
    total_rows: int = 0
    rules_checked: int = 0
    total_violations: int = 0
    conformity_score: float = Field(0.0, description="0-100 percentage")
    rule_results: list[RuleResult] = Field(default_factory=list)
    corrections: list[Violation] = Field(default_factory=list, description="All violations with suggested fixes")
    corrected_file_available: bool = False
