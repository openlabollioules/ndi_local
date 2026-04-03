"""Data Conformity skill — audits data against business rules,
detects violations, proposes corrections, and generates corrected files.
"""

from __future__ import annotations

from typing import Any

from ndi_api.skills import registry
from ndi_api.skills.base import SkillBase, SkillInput, ToolDefinition
from ndi_api.skills.data_conformity.schema import ConformityInput, ConformityOutput


class DataConformitySkill(SkillBase):
    name = "data-conformity"
    description = "Audit de conformité aux règles métier — détecte les violations, propose des corrections, génère un fichier corrigé."
    version = "1.0.0"
    tags = ["conformity", "rules", "validation", "correction", "audit", "compliance"]
    triggers = [
        "conformité",
        "conformite",
        "conforme",
        "règle",
        "regle",
        "règles",
        "regles",
        "valider",
        "validation",
        "vérifier",
        "verifier",
        "correction",
        "corriger",
        "corrige",
        "autorisé",
        "interdit",
        "doit contenir",
        "format attendu",
        "valeurs attendues",
        "non-conforme",
        "violation",
        "fichier corrigé",
        "export corrigé",
    ]

    def get_input_schema(self) -> type[ConformityInput]:
        return ConformityInput

    def get_output_schema(self) -> type[ConformityOutput]:
        return ConformityOutput

    def get_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="check_enum_values",
                description="Check that a column only contains allowed values",
                parameters={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string"},
                        "column": {"type": "string"},
                        "allowed_values": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["table_name", "column", "allowed_values"],
                },
            ),
            ToolDefinition(
                name="check_format",
                description="Check that a column matches a regex pattern",
                parameters={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string"},
                        "column": {"type": "string"},
                        "pattern": {"type": "string"},
                    },
                    "required": ["table_name", "column", "pattern"],
                },
            ),
            ToolDefinition(
                name="check_range",
                description="Check that a numeric column is within bounds",
                parameters={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string"},
                        "column": {"type": "string"},
                        "min_value": {"type": "number"},
                        "max_value": {"type": "number"},
                    },
                    "required": ["table_name", "column"],
                },
            ),
            ToolDefinition(
                name="check_uniqueness",
                description="Check that a column has no duplicate values",
                parameters={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string"},
                        "column": {"type": "string"},
                    },
                    "required": ["table_name", "column"],
                },
            ),
            ToolDefinition(
                name="export_corrected_file",
                description="Generate a corrected CSV/XLSX with fixes applied",
                parameters={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string"},
                        "corrections": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "row_index": {"type": "integer"},
                                    "column": {"type": "string"},
                                    "new_value": {"type": "string"},
                                },
                            },
                        },
                    },
                    "required": ["table_name", "corrections"],
                },
            ),
        ]

    def _inline_prompt(self) -> str:
        return (
            "Tu audites la conformité des données par rapport à des règles métier.\n"
            "1. Vérifie chaque règle sur l'ensemble des données\n"
            "2. Liste les violations avec ligne, colonne, valeur actuelle, attendue\n"
            "3. Propose une correction pour chaque violation\n"
            "4. Calcule un score de conformité global (0-100%)\n"
        )

    def execute(self, inp: SkillInput, **kwargs: Any) -> ConformityOutput:
        """Execution handled by the conformity analysis service."""
        return ConformityOutput(answer="")


registry.register(DataConformitySkill())
