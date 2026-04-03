"""NoSQL Query skill — generates MongoDB-style JSON queries."""

from __future__ import annotations

from typing import Any

from ndi_api.skills import registry
from ndi_api.skills.base import SkillBase, SkillInput, ToolDefinition
from ndi_api.skills.nosql_query.schema import NoSQLQueryInput, NoSQLQueryOutput


class NoSQLQuerySkill(SkillBase):
    name = "nosql-query"
    description = "Génère des requêtes JSON (style MongoDB) pour la base documentaire."
    version = "1.1.0"
    tags = ["nosql", "json", "mongodb", "query-generation"]
    triggers = [
        "nosql",
        "json",
        "document",
        "collection",
        "liste",
        "montre",
        "affiche",
        "combien",
        "total",
        "somme",
        "moyenne",
    ]

    def get_input_schema(self) -> type[NoSQLQueryInput]:
        return NoSQLQueryInput

    def get_output_schema(self) -> type[NoSQLQueryOutput]:
        return NoSQLQueryOutput

    def get_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="execute_nosql",
                description="Execute a JSON query against the document store",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "JSON query string"},
                    },
                    "required": ["query"],
                },
            ),
        ]

    def _inline_prompt(self) -> str:
        return (
            "Tu es un assistant NoSQL expert. Règles STRICTES:\n"
            "1. Retourne UNIQUEMENT un objet JSON compact sur une seule ligne.\n"
            "2. Utilise $ilike pour les recherches textuelles, jamais $eq.\n"
            "3. Pour les groupements, utilise {by: ..., agg: {...}}.\n"
        )

    def validate_output(self, raw: str) -> NoSQLQueryOutput:
        """Extract JSON query from raw LLM response."""
        import json

        query = raw.strip()
        if query.startswith("```"):
            lines = query.split("\n")
            query = "\n".join(l for l in lines if not l.strip().startswith("```")).strip()

        # Validate it's parseable JSON
        try:
            json.loads(query)
        except json.JSONDecodeError:
            return NoSQLQueryOutput(answer=raw, json_query=query, error="Invalid JSON output")

        return NoSQLQueryOutput(answer=raw, json_query=query)

    def execute(self, inp: SkillInput, **kwargs: Any) -> NoSQLQueryOutput:
        """Prompt-only skill — execution is handled by the nl_sql pipeline."""
        return NoSQLQueryOutput(answer="", json_query="")


registry.register(NoSQLQuerySkill())
