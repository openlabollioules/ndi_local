"""Skill: maintenance-navale (auto-generated from session skill)."""

from __future__ import annotations

from typing import Any

from ndi_api.skills import registry
from ndi_api.skills.base import SkillBase, SkillInput
from ndi_api.skills.maintenance_navale.schema import MaintenanceNavaleSkillInput, MaintenanceNavaleSkillOutput


class MaintenanceNavaleSkill(SkillBase):
    name = "maintenance-navale"
    description = "Skill pour la maintenance navale et les aléas"
    version = "1.0.0"
    tags = ["maintenance", "naval", "aléas", "ot", "mo"]
    triggers = ["maintenance", "naval", "aléas", "ot", "mo", "motifs", "navale"]

    def get_input_schema(self) -> type[MaintenanceNavaleSkillInput]:
        return MaintenanceNavaleSkillInput

    def get_output_schema(self) -> type[MaintenanceNavaleSkillOutput]:
        return MaintenanceNavaleSkillOutput

    def _inline_prompt(self) -> str:
        return ""  # Loaded from SKILL.md via get_prompt()

    def execute(self, inp: SkillInput, **kwargs: Any) -> MaintenanceNavaleSkillOutput:
        return MaintenanceNavaleSkillOutput(answer="")


registry.register(MaintenanceNavaleSkill())
