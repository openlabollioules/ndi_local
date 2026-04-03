"""Query Explain skill — explains SQL/NoSQL queries in plain French.

Post-processor: runs after a query skill to enrich the response.
"""

from __future__ import annotations

from typing import Any

from ndi_api.skills import registry
from ndi_api.skills.base import SkillBase, SkillInput
from ndi_api.skills.query_explain.schema import QueryExplainInput, QueryExplainOutput


class QueryExplainSkill(SkillBase):
    name = "query-explain"
    description = "Explique en français ce que fait une requête SQL/NoSQL générée."
    version = "1.0.0"
    tags = ["explain", "pedagogy", "sql", "nosql"]
    triggers = [
        "explique",
        "expliquer",
        "explication",
        "comment ça marche",
        "c'est quoi",
        "que fait",
        "signifie",
        "comprendre",
        "détaille",
        "décompose",
    ]
    depends_on = ["sql-query", "nosql-query"]
    is_post_processor = True

    def get_input_schema(self) -> type[QueryExplainInput]:
        return QueryExplainInput

    def get_output_schema(self) -> type[QueryExplainOutput]:
        return QueryExplainOutput

    def _inline_prompt(self) -> str:
        return (
            "Tu expliques des requêtes SQL/NoSQL en français simple.\n"
            "Traduis chaque opération : GROUP BY → 'regroupe par', "
            "WHERE → 'filtre sur', JOIN → 'croise avec'.\n"
            "Sois concis — max 10 lignes.\n"
        )

    def execute(self, inp: SkillInput, **kwargs: Any) -> QueryExplainOutput:
        """Prompt-only post-processor — injected after query generation."""
        return QueryExplainOutput(answer="")


registry.register(QueryExplainSkill())
