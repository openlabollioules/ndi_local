"""Image Agent - Natural language interaction with images.

Handles:
- Image upload and analysis requests
- Natural language commands for image processing
- Extraction of data tables from images
- OCR and description requests
- **Secure ingestion** of extracted tables (skill: image-ingest)
"""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import pandas as pd

from ndi_api.plugins.manager import get_plugin_manager
from ndi_api.services.image_analysis import (
    ImageAnalysisResult,
    get_image_analysis_service,
)

logger = logging.getLogger(__name__)

_IMG_PREFIX = "img_"
_MAX_ROWS = 10_000
_MAX_COLS = 100
_MAX_TABLE_NAME_LEN = 63


@dataclass
class ImageAgentResult:
    """Result from image agent processing."""

    success: bool
    answer: str
    action_taken: Literal["describe", "ocr", "extract_table", "ingest_table", "unknown"]
    data: dict | None = None
    table_name: str | None = None
    rows_ingested: int = 0


class ImageAgent:
    """Agent for handling natural language image requests."""

    # Keywords that indicate different intents
    DESCRIBE_KEYWORDS = [
        "décris",
        "décrire",
        "description",
        "que vois-tu",
        "que vois-je",
        "qu'est-ce que c'est",
        "qu'est ce que c'est",
        "montre",
        "analyse cette image",
        "analyser cette image",
        "qu'est-ce qu'il y a",
        "qu'est ce qu'il y a",
    ]

    OCR_KEYWORDS = [
        "ocr",
        "texte",
        "extraire le texte",
        "transcrire",
        "transcription",
        "lis ce document",
        "lire ce document",
        "qu'est-ce qui est écrit",
        "qu'est ce qui est écrit",
        "contenu du document",
        "texte du document",
    ]

    TABLE_KEYWORDS = [
        "tableau",
        "table",
        "données",
        "extraire les données",
        "extraire le tableau",
        "récupérer le tableau",
        "ingérer",
        "importer le tableau",
        "csv",
        "excel",
        "données du tableau",
        "tableau de données",
        "extraire ces données",
        "mettre dans la base",
        "sauvegarder",
        "stocker",
    ]

    CHART_KEYWORDS = [
        "graphique",
        "chart",
        "courbe",
        "histogramme",
        "tendance",
        "analyser ce graphique",
        "que montre ce graphique",
        "interprète ce graphique",
    ]

    def __init__(self):
        self.image_service = get_image_analysis_service()

    def detect_intent(
        self, message: str
    ) -> Literal["describe", "ocr", "extract_table", "ingest_table", "chart", "unknown"]:
        """Detect user's intent from natural language message."""
        message_lower = message.lower()

        # Check for table ingestion first (more specific - must be before extraction)
        ingestion_keywords = [
            "ingérer",
            "ingère",
            "importer",
            "mettre dans",
            "sauvegarder",
            "stocker",
            "base de données",
            "base",
        ]
        if any(kw in message_lower for kw in ingestion_keywords):
            return "ingest_table"

        # Check for table extraction (without ingestion)
        if any(kw in message_lower for kw in self.TABLE_KEYWORDS):
            return "extract_table"

        # Check for chart analysis
        if any(kw in message_lower for kw in self.CHART_KEYWORDS):
            return "chart"

        # Check for OCR
        if any(kw in message_lower for kw in self.OCR_KEYWORDS):
            return "ocr"

        # Check for description (default fallback)
        if any(kw in message_lower for kw in self.DESCRIBE_KEYWORDS):
            return "describe"

        # Default: if message is short, assume description
        if len(message.strip()) < 50:
            return "describe"

        return "unknown"

    async def process(
        self,
        image_bytes: bytes,
        filename: str,
        user_message: str,
        custom_table_name: str | None = None,
    ) -> ImageAgentResult:
        """
        Process an image based on user's natural language request.

        Args:
            image_bytes: Raw image data
            filename: Original filename
            user_message: User's request in natural language
            custom_table_name: Optional custom name for table ingestion

        Returns:
            ImageAgentResult with action taken and response
        """
        intent = self.detect_intent(user_message)
        logger.info(f"Image agent detected intent: {intent} for message: {user_message[:50]}...")

        try:
            if intent == "describe":
                return await self._handle_describe(image_bytes, filename)
            elif intent == "ocr":
                return await self._handle_ocr(image_bytes, filename)
            elif intent == "extract_table":
                return await self._handle_extract_table(image_bytes, filename, ingest=False)
            elif intent == "ingest_table":
                return await self._handle_extract_table(
                    image_bytes, filename, ingest=True, custom_table_name=custom_table_name
                )
            elif intent == "chart":
                return await self._handle_chart(image_bytes, filename)
            else:
                # Unknown intent - try to be helpful
                return await self._handle_describe(image_bytes, filename)

        except Exception as e:
            logger.exception("Image agent processing failed")
            return ImageAgentResult(
                success=False,
                answer=f"❌ Erreur lors du traitement de l'image: {str(e)}",
                action_taken="unknown",
            )

    async def _handle_describe(self, image_bytes: bytes, filename: str) -> ImageAgentResult:
        """Handle image description request."""
        result: ImageAnalysisResult = await self.image_service.analyze_image(
            image_bytes=image_bytes, filename=filename, analysis_type="general"
        )

        # Format a nice response
        answer = f"📷 **Analyse de l'image**\n\n{result.description}\n\n"

        if result.objects_detected:
            answer += f"🎯 **Éléments détectés**: {', '.join(result.objects_detected[:10])}\n\n"

        answer += f"_Confiance: {int(result.confidence * 100)}%_"

        return ImageAgentResult(
            success=True,
            answer=answer,
            action_taken="describe",
            data={"objects": result.objects_detected, "confidence": result.confidence},
        )

    async def _handle_ocr(self, image_bytes: bytes, filename: str) -> ImageAgentResult:
        """Handle OCR/text extraction request."""
        result: ImageAnalysisResult = await self.image_service.analyze_image(
            image_bytes=image_bytes, filename=filename, analysis_type="ocr"
        )

        answer = f"📝 **Texte extrait**\n\n```\n{result.description}\n```\n\n"
        answer += f"_Confiance: {int(result.confidence * 100)}%_"

        return ImageAgentResult(success=True, answer=answer, action_taken="ocr", data={"text": result.description})

    # ------------------------------------------------------------------
    # Safe ingestion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_img_table_name(
        raw: str,
        plugin,
    ) -> str:
        """Build a collision-free, prefixed table name.

        Rules (from image-ingest skill):
        - Prefix ``img_``
        - Only ``[a-z0-9_]``
        - Max 63 chars
        - If the name already exists, append ``_YYYYMMDD_HHmmss``
        """
        base = re.sub(r"[^a-z0-9_]", "_", raw.lower())
        base = re.sub(r"_+", "_", base).strip("_") or "image_data"

        if not base.startswith(_IMG_PREFIX):
            base = f"{_IMG_PREFIX}{base}"

        base = base[:_MAX_TABLE_NAME_LEN]

        if plugin.table_exists(base):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            candidate = f"{base}_{ts}"[:_MAX_TABLE_NAME_LEN]
            return candidate
        return base

    @staticmethod
    def _validate_dataframe(df: pd.DataFrame) -> str | None:
        """Return an error message if the DataFrame fails safety checks, else None."""
        if len(df) == 0:
            return "Le tableau extrait est vide (0 lignes)."
        if len(df) > _MAX_ROWS:
            return (
                f"Le tableau contient {len(df)} lignes, "
                f"ce qui dépasse la limite de sécurité ({_MAX_ROWS}). "
                f"Veuillez découper les données."
            )
        if len(df.columns) > _MAX_COLS:
            return (
                f"Le tableau contient {len(df.columns)} colonnes, "
                f"ce qui dépasse la limite de sécurité ({_MAX_COLS})."
            )
        if all(c.startswith("Unnamed") for c in df.columns):
            return "Aucun en-tête de colonne valide détecté."
        return None

    # ------------------------------------------------------------------
    # Table extraction + secure ingestion
    # ------------------------------------------------------------------

    async def _handle_extract_table(
        self,
        image_bytes: bytes,
        filename: str,
        ingest: bool = False,
        custom_table_name: str | None = None,
    ) -> ImageAgentResult:
        """Handle table extraction with optional **secure** ingestion."""
        result: ImageAnalysisResult = await self.image_service.analyze_image(
            image_bytes=image_bytes,
            filename=filename,
            analysis_type="data_table",
        )

        try:
            csv_content, columns = self._markdown_to_csv(result.description)
            df = pd.read_csv(io.StringIO(csv_content))
        except ValueError as e:
            return ImageAgentResult(
                success=False,
                answer=(
                    "Impossible d'extraire un tableau valide de cette image.\n\n"
                    "L'image pourrait ne pas contenir de tableau clair, ou la qualité "
                    f"est insuffisante.\n\nErreur: {e}"
                ),
                action_taken="extract_table",
            )

        rows = len(df)
        columns_list = list(df.columns)

        preview = df.head(5).to_markdown(index=False)

        answer = f"**Tableau extrait** ({rows} lignes, {len(columns_list)} colonnes)\n\n"
        answer += f"**Colonnes**: {', '.join(columns_list)}\n\n"
        answer += f"**Aperçu**:\n```\n{preview}\n```\n\n"

        if ingest and rows > 0:
            # --- Validation (skill image-ingest) -----------------------
            validation_err = self._validate_dataframe(df)
            if validation_err:
                answer += f"**Ingestion refusée** : {validation_err}"
                return ImageAgentResult(
                    success=False,
                    answer=answer,
                    action_taken="extract_table",
                    data={
                        "csv": csv_content,
                        "preview": df.head(10).to_dict("records"),
                        "columns": columns_list,
                    },
                )

            plugin = get_plugin_manager().get_plugin()

            # --- Safe table name (no overwrite) ------------------------
            raw_name = custom_table_name or (filename.rsplit(".", 1)[0] if "." in filename else filename)
            table_name = self._safe_img_table_name(raw_name, plugin)

            # Use CREATE TABLE (not REPLACE) via a dedicated path
            final_table_name = self._safe_ingest(plugin, df, table_name)

            logger.info(
                "Image ingest: table=%s rows=%d cols=%d source=%s",
                final_table_name,
                rows,
                len(columns_list),
                filename,
            )

            answer += f"**Données ingérées** dans la table `{final_table_name}`\n\n"
            answer += "Vous pouvez maintenant interroger ces données en langage naturel !"

            return ImageAgentResult(
                success=True,
                answer=answer,
                action_taken="ingest_table",
                data={"preview": df.head(10).to_dict("records")},
                table_name=final_table_name,
                rows_ingested=rows,
            )

        answer += "*Pour ingérer ces données, demandez : « Ingère ce tableau » ou « Sauvegarde dans la base »*"

        return ImageAgentResult(
            success=True,
            answer=answer,
            action_taken="extract_table",
            data={
                "csv": csv_content,
                "preview": df.head(10).to_dict("records"),
                "columns": columns_list,
            },
        )

    @staticmethod
    def _safe_ingest(plugin, df: pd.DataFrame, table_name: str) -> str:
        """Ingest into the plugin **without overwriting** existing tables.

        For SQL (DuckDB): uses CREATE TABLE (not CREATE OR REPLACE).
        For NoSQL: delegates to the plugin (collections are append-safe).
        """
        if plugin.mode == "sql":
            from ndi_api.plugins.sql_plugin import SQLPlugin

            assert isinstance(plugin, SQLPlugin)

            raw_names = [plugin.normalize_column_name(str(c)) for c in df.columns]
            df.columns = plugin._deduplicate_columns(raw_names)

            with plugin._get_connection() as con:
                con.register("_img_ingest_df", df)
                con.execute(f"CREATE TABLE IF NOT EXISTS {table_name} " f"AS SELECT * FROM _img_ingest_df")
                con.unregister("_img_ingest_df")

            plugin._existing_tables.add(table_name.lower())
            return table_name

        return plugin.ingest_dataframe(df, f"{table_name}.csv")

    async def _handle_chart(self, image_bytes: bytes, filename: str) -> ImageAgentResult:
        """Handle chart/graph analysis request."""
        result: ImageAnalysisResult = await self.image_service.analyze_image(
            image_bytes=image_bytes, filename=filename, analysis_type="chart"
        )

        answer = f"📈 **Analyse du graphique**\n\n{result.description}\n\n"
        answer += f"_Confiance: {int(result.confidence * 100)}%_"

        return ImageAgentResult(
            success=True,
            answer=answer,
            action_taken="chart",
        )

    def _markdown_to_csv(self, markdown_table: str) -> tuple[str, list[str]]:
        """Convert markdown table to CSV format."""
        lines = markdown_table.strip().split("\n")

        # Filter out separator lines
        data_lines = [line for line in lines if not re.match(r"^\|?[-:|\s]+\|?$", line.strip())]

        if not data_lines:
            raise ValueError("No valid table data found")

        # Parse rows
        rows = []
        for line in data_lines:
            cells = [cell.strip() for cell in line.split("|")]
            cells = [c for c in cells if c]  # Remove empty
            if cells:
                rows.append(cells)

        if len(rows) < 1:
            raise ValueError("Table must have at least a header row")

        # Convert to CSV
        csv_lines = [",".join(f'"{cell.replace("\"", "\"\"")}"' for cell in row) for row in rows]

        return "\n".join(csv_lines), rows[0] if rows else []


# Singleton instance
_image_agent: ImageAgent | None = None


def get_image_agent() -> ImageAgent:
    """Get or create the image agent singleton."""
    global _image_agent
    if _image_agent is None:
        _image_agent = ImageAgent()
    return _image_agent
