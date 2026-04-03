"""Data Quality skill — audit completeness, duplicates, outliers, type issues."""

from __future__ import annotations

from typing import Any

from ndi_api.skills import registry
from ndi_api.skills.base import SkillBase, SkillInput, ToolDefinition
from ndi_api.skills.data_quality.schema import DataQualityInput, DataQualityOutput


class DataQualitySkill(SkillBase):
    name = "data-quality"
    description = "Audit de qualité des données — valeurs manquantes, doublons, outliers, types."
    version = "1.0.0"
    tags = ["quality", "audit", "completeness", "duplicates", "outliers"]
    triggers = [
        "qualité",
        "qualite",
        "quality",
        "manquant",
        "manquante",
        "null",
        "vide",
        "doublon",
        "doublons",
        "duplicate",
        "outlier",
        "aberrant",
        "anomalie",
        "complétude",
        "completude",
        "propreté",
        "proprete",
        "audit",
        "vérifier",
        "verifier",
        "contrôle",
    ]

    def get_input_schema(self) -> type[DataQualityInput]:
        return DataQualityInput

    def get_output_schema(self) -> type[DataQualityOutput]:
        return DataQualityOutput

    def get_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="count_nulls",
                description="Count null values per column for a table",
                parameters={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string"},
                    },
                    "required": ["table_name"],
                },
            ),
            ToolDefinition(
                name="find_duplicates",
                description="Find duplicate rows based on key columns",
                parameters={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string"},
                        "columns": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["table_name"],
                },
            ),
            ToolDefinition(
                name="detect_outliers",
                description="Detect outlier values in numeric columns using IQR method",
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
            "Tu es un auditeur de qualité de données. Analyse l'échantillon fourni et retourne :\n"
            "- COMPLÉTUDE : % de valeurs remplies par colonne\n"
            "- DOUBLONS : lignes potentiellement dupliquées\n"
            "- OUTLIERS : valeurs aberrantes dans les colonnes numériques\n"
            "- SCORE GLOBAL : note sur 10\n"
            "- RECOMMANDATIONS : actions correctives\n"
        )

    def execute(self, inp: SkillInput, **kwargs: Any) -> DataQualityOutput:
        """Execution handled by the open_analysis engine with data-quality prompt."""
        return DataQualityOutput(answer="")


registry.register(DataQualitySkill())
