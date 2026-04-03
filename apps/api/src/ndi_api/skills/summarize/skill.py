"""Summarize skill — digests large result sets into key insights.

Post-processor: runs after a query skill when results exceed a threshold.
"""

from __future__ import annotations

from typing import Any

from ndi_api.skills import registry
from ndi_api.skills.base import SkillBase, SkillInput
from ndi_api.skills.summarize.schema import SummarizeInput, SummarizeOutput

# Threshold: only summarize if the result set has more than this many rows
SUMMARIZE_THRESHOLD = 20


class SummarizeSkill(SkillBase):
    name = "summarize"
    description = "Résume un jeu de résultats volumineux en points clés."
    version = "1.0.0"
    tags = ["summarize", "synthesis", "digest", "overview"]
    triggers = [
        "résumé",
        "resume",
        "résume",
        "synthèse",
        "synthese",
        "en bref",
        "l'essentiel",
        "overview",
        "digest",
        "récapitulatif",
        "recapitulatif",
    ]
    depends_on = ["sql-query", "nosql-query"]
    is_post_processor = True

    def get_input_schema(self) -> type[SummarizeInput]:
        return SummarizeInput

    def get_output_schema(self) -> type[SummarizeOutput]:
        return SummarizeOutput

    def _inline_prompt(self) -> str:
        return (
            "Tu résumes un jeu de résultats en points clés.\n"
            "Donne : chiffres clés (total, moyenne), top 3, bottom 3, distribution.\n"
            "Max 15 lignes. Arrondis les chiffres. Conclus en 1-2 phrases.\n"
        )

    def execute(self, inp: SkillInput, **kwargs: Any) -> SummarizeOutput:
        """Prompt-only post-processor."""
        return SummarizeOutput(answer="")


registry.register(SummarizeSkill())
