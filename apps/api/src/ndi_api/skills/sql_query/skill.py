"""SQL Query skill — generates DuckDB SQL from natural language."""

from __future__ import annotations

from typing import Any

from ndi_api.skills import registry
from ndi_api.skills.base import SkillBase, SkillInput, ToolDefinition
from ndi_api.skills.sql_query.schema import SQLQueryInput, SQLQueryOutput


class SQLQuerySkill(SkillBase):
    name = "sql-query"
    description = "Génère des requêtes SQL DuckDB à partir de questions en français."
    version = "1.1.0"
    tags = ["sql", "duckdb", "query-generation"]
    triggers = [
        "sql",
        "select",
        "requête",
        "query",
        "liste",
        "montre",
        "affiche",
        "combien",
        "total",
        "somme",
        "moyenne",
    ]

    def get_input_schema(self) -> type[SQLQueryInput]:
        return SQLQueryInput

    def get_output_schema(self) -> type[SQLQueryOutput]:
        return SQLQueryOutput

    def get_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="execute_sql",
                description="Execute a read-only SQL query against DuckDB",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "SQL SELECT query"},
                    },
                    "required": ["query"],
                },
            ),
            ToolDefinition(
                name="validate_sql",
                description="Validate that a SQL query is read-only and safe",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                    },
                    "required": ["query"],
                },
            ),
        ]

    def _inline_prompt(self) -> str:
        return (
            "Tu es un assistant SQL DuckDB expert. Règles STRICTES:\n"
            "1. Utilise UNIQUEMENT les noms de colonnes listés dans le schéma.\n"
            "2. N'invente JAMAIS de colonnes qui n'apparaissent pas dans le schéma.\n"
            "3. N'effectue des JOINs QUE si une relation est déclarée.\n"
            "4. Retourne UNIQUEMENT la requête SQL, sans explication, sans markdown.\n"
            "5. Ne PAS ajouter de LIMIT sauf demande explicite de l'utilisateur.\n"
        )

    def validate_output(self, raw: str) -> SQLQueryOutput:
        """Extract SQL from raw LLM response."""
        sql = raw.strip()
        # Remove markdown code fences if present
        if sql.startswith("```"):
            lines = sql.split("\n")
            sql = "\n".join(l for l in lines if not l.strip().startswith("```")).strip()
        return SQLQueryOutput(answer=raw, query=sql)

    def execute(self, inp: SkillInput, **kwargs: Any) -> SQLQueryOutput:
        """Prompt-only skill — execution is handled by the nl_sql pipeline."""
        return SQLQueryOutput(answer="", query="")


# Auto-register on import
registry.register(SQLQuerySkill())
