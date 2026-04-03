"""Image Ingest skill — secure ingestion of data extracted from images."""

from __future__ import annotations

from typing import Any

from ndi_api.skills import registry
from ndi_api.skills.base import SkillBase, SkillInput, ToolDefinition
from ndi_api.skills.image_ingest.schema import ImageIngestInput, ImageIngestOutput


class ImageIngestSkill(SkillBase):
    name = "image-ingest"
    description = "Ingestion sécurisée de données extraites d'images (tableaux, OCR)."
    version = "1.0.0"
    tags = ["ingestion", "image", "table-extraction", "sécurité", "write"]
    triggers = [
        "image",
        "photo",
        "capture",
        "screenshot",
        "ingère",
        "importe",
        "extraire",
        "tableau",
        "ocr",
        "scanner",
    ]

    def get_input_schema(self) -> type[ImageIngestInput]:
        return ImageIngestInput

    def get_output_schema(self) -> type[ImageIngestOutput]:
        return ImageIngestOutput

    def get_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="extract_table_from_image",
                description="Extract tabular data from an image via VLM",
                parameters={
                    "type": "object",
                    "properties": {
                        "image_bytes": {"type": "string", "description": "Base64 encoded image"},
                    },
                    "required": ["image_bytes"],
                },
            ),
            ToolDefinition(
                name="ingest_dataframe",
                description="Safely ingest a DataFrame into the database with img_ prefix",
                parameters={
                    "type": "object",
                    "properties": {
                        "csv_content": {"type": "string"},
                        "table_name": {"type": "string"},
                    },
                    "required": ["csv_content"],
                },
            ),
        ]

    def _inline_prompt(self) -> str:
        return (
            "Tu gères l'ingestion sécurisée de données extraites d'images.\n"
            "- NE JAMAIS écraser une table existante.\n"
            "- Préfixe obligatoire: img_\n"
            "- Max 10 000 lignes, max 100 colonnes.\n"
            "- Ingestion uniquement sur demande explicite de l'utilisateur.\n"
        )

    def execute(self, inp: SkillInput, **kwargs: Any) -> ImageIngestOutput:
        """Execution handled by the image_agent service."""
        return ImageIngestOutput(answer="")


registry.register(ImageIngestSkill())
