"""Chart Generation skill — suggests visualizations for query results.

This is a **post-processor** skill: it runs *after* a query skill and
enriches the response with a chart suggestion.
"""

from __future__ import annotations

from typing import Any

from ndi_api.skills import registry
from ndi_api.skills.base import SkillBase, SkillInput
from ndi_api.skills.chart_gen.schema import ChartInput, ChartOutput


class ChartGenSkill(SkillBase):
    name = "chart-gen"
    description = "Suggère une visualisation graphique adaptée aux résultats de requêtes."
    version = "1.0.0"
    tags = ["chart", "visualization", "graphique"]
    triggers = [
        "graphique",
        "diagramme",
        "chart",
        "graph",
        "courbe",
        "histogramme",
        "camembert",
        "pie",
        "visualisation",
        "visualise",
    ]
    depends_on = ["sql-query", "nosql-query"]
    is_post_processor = True

    def get_input_schema(self) -> type[ChartInput]:
        return ChartInput

    def get_output_schema(self) -> type[ChartOutput]:
        return ChartOutput

    def execute(self, inp: SkillInput, **kwargs: Any) -> ChartOutput:
        """Delegate to the existing chart_suggest service."""
        from ndi_api.services.chart_suggest import suggest_chart

        rows = kwargs.get("rows", [])
        question = inp.question if isinstance(inp, SkillInput) else ""
        suggestion = suggest_chart(rows, question)

        if suggestion:
            return ChartOutput(
                answer="Suggestion de graphique générée.",
                chart_type=suggestion.get("type"),
                chart_config=suggestion,
            )
        return ChartOutput(answer="", applicable=False)


registry.register(ChartGenSkill())
