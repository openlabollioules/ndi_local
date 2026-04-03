"""Open Analysis skill — interprets and comments on data beyond simple queries."""

from __future__ import annotations

from typing import Any

from ndi_api.skills import registry
from ndi_api.skills.base import SkillBase, SkillInput
from ndi_api.skills.open_analysis.schema import AnalysisInput, AnalysisOutput


class OpenAnalysisSkill(SkillBase):
    name = "open-analysis"
    description = "Analyser, interpréter et commenter les données au-delà des requêtes simples."
    version = "1.0.0"
    tags = ["analysis", "interpretation", "coherence", "patterns", "insights"]
    triggers = [
        "analyse",
        "analyser",
        "évalue",
        "évaluer",
        "cohérence",
        "pattern",
        "tendance",
        "compare",
        "interprète",
        "distribution",
        "répartition",
        "qu'en penses-tu",
        "que remarques-tu",
    ]

    def get_input_schema(self) -> type[AnalysisInput]:
        return AnalysisInput

    def get_output_schema(self) -> type[AnalysisOutput]:
        return AnalysisOutput

    def _inline_prompt(self) -> str:
        return (
            "Tu es un analyste de données expert. "
            "Fournis une réponse structurée avec ANALYSE, SYNTHÈSE, DÉTAILS, "
            "EXEMPLES, HYPOTHÈSES et LIMITES. "
            "Toujours donner des chiffres et citer des exemples concrets."
        )

    def validate_output(self, raw: str) -> AnalysisOutput:
        """Parse structured analysis sections from the LLM response."""
        import re

        sections: dict[str, str] = {}
        current = None
        lines: list[str] = []

        for line in raw.split("\n"):
            header_match = re.match(
                r"^(ANALYSE|SYNTHÈSE|DÉTAILS|EXEMPLES|HYPOTHÈSES|LIMITES|PATTERNS)\s*:?\s*",
                line,
                re.IGNORECASE,
            )
            if header_match:
                if current and lines:
                    sections[current] = "\n".join(lines).strip()
                current = header_match.group(1).upper()
                rest = line[header_match.end() :].strip()
                lines = [rest] if rest else []
            else:
                lines.append(line)

        if current and lines:
            sections[current] = "\n".join(lines).strip()

        return AnalysisOutput(answer=raw, sections=sections)

    def execute(self, inp: SkillInput, **kwargs: Any) -> AnalysisOutput:
        """Execution handled by the open_analysis engine."""
        return AnalysisOutput(answer="")


registry.register(OpenAnalysisSkill())
