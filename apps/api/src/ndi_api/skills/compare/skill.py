"""Compare skill — compares periods, groups, or metrics with deltas and trends."""

from __future__ import annotations

from typing import Any

from ndi_api.skills import registry
from ndi_api.skills.base import SkillBase, SkillInput, ToolDefinition
from ndi_api.skills.compare.schema import CompareInput, CompareOutput


class CompareSkill(SkillBase):
    name = "compare"
    description = "Compare deux périodes, groupes ou métriques avec écarts et tendances."
    version = "1.0.0"
    tags = ["compare", "evolution", "trend", "difference", "variation"]
    triggers = [
        "compare",
        "comparer",
        "comparaison",
        "vs",
        "versus",
        "par rapport",
        "différence",
        "difference",
        "écart",
        "ecart",
        "évolution",
        "evolution",
        "tendance",
        "trend",
        "progression",
        "régression",
        "avant",
        "après",
        "apres",
        "augmentation",
        "diminution",
        "variation",
        "mois dernier",
        "année dernière",
        "trimestre",
    ]

    def get_input_schema(self) -> type[CompareInput]:
        return CompareInput

    def get_output_schema(self) -> type[CompareOutput]:
        return CompareOutput

    def get_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="query_period",
                description="Query data for a specific period to compare",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "SQL/NoSQL query for one period"},
                    },
                    "required": ["query"],
                },
            ),
        ]

    def _inline_prompt(self) -> str:
        return (
            "Tu es un analyste comparatif. Compare les deux sujets demandés.\n"
            "Donne les écarts en absolu ET en pourcentage.\n"
            "Identifie le sens : hausse ↑, baisse ↓, stable →.\n"
            "Ordonne par impact décroissant.\n"
        )

    def execute(self, inp: SkillInput, **kwargs: Any) -> CompareOutput:
        """Execution handled by the open_analysis engine with compare prompt."""
        return CompareOutput(answer="")


registry.register(CompareSkill())
