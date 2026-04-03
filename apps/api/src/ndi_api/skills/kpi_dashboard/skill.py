"""KPI Dashboard skill — generates a metrics overview for a table/collection."""

from __future__ import annotations

from typing import Any

from ndi_api.skills import registry
from ndi_api.skills.base import SkillBase, SkillInput, ToolDefinition
from ndi_api.skills.kpi_dashboard.schema import KPIDashboardInput, KPIDashboardOutput


class KPIDashboardSkill(SkillBase):
    name = "kpi-dashboard"
    description = "Génère un tableau de bord KPI — métriques, répartitions, top N."
    version = "1.0.0"
    tags = ["kpi", "dashboard", "indicators", "metrics", "overview"]
    triggers = [
        "kpi",
        "indicateur",
        "indicateurs",
        "tableau de bord",
        "dashboard",
        "métriques",
        "metriques",
        "metrics",
        "vue d'ensemble",
        "état des lieux",
        "etat des lieux",
        "bilan",
        "point sur",
        "statistiques",
        "chiffres clés",
        "chiffres cles",
    ]

    def get_input_schema(self) -> type[KPIDashboardInput]:
        return KPIDashboardInput

    def get_output_schema(self) -> type[KPIDashboardOutput]:
        return KPIDashboardOutput

    def get_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="get_table_stats",
                description="Get row count and column statistics for a table",
                parameters={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string"},
                    },
                    "required": ["table_name"],
                },
            ),
            ToolDefinition(
                name="get_column_distribution",
                description="Get value distribution for a categorical column",
                parameters={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string"},
                        "column": {"type": "string"},
                        "top_n": {"type": "integer", "default": 5},
                    },
                    "required": ["table_name", "column"],
                },
            ),
            ToolDefinition(
                name="get_numeric_aggregates",
                description="Get SUM, AVG, MIN, MAX for a numeric column",
                parameters={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string"},
                        "column": {"type": "string"},
                    },
                    "required": ["table_name", "column"],
                },
            ),
        ]

    def _inline_prompt(self) -> str:
        return (
            "Tu génères un tableau de bord KPI pour une table de données.\n"
            "Inclus : volumétrie, métriques numériques (total/avg/min/max),\n"
            "répartitions catégorielles (top 5), plage temporelle, alertes.\n"
            "Formate les nombres avec espaces comme séparateurs de milliers.\n"
        )

    def execute(self, inp: SkillInput, **kwargs: Any) -> KPIDashboardOutput:
        """Execution handled by the open_analysis engine with KPI prompt."""
        return KPIDashboardOutput(answer="")


registry.register(KPIDashboardSkill())
