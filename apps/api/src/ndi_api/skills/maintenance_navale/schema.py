"""Input/output schemas for the maintenance-navale skill (auto-generated)."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ndi_api.skills.base import SkillInput, SkillOutput


class MaintenanceNavaleSkillInput(SkillInput):
    """Input for maintenance-navale."""

    sample_data: list[dict[str, Any]] = Field(default_factory=list)


class MaintenanceNavaleSkillOutput(SkillOutput):
    """Output of maintenance-navale."""

    sections: dict[str, str] = Field(default_factory=dict)
