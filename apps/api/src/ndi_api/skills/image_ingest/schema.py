"""Input/output schemas for the Image Ingest skill."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ndi_api.skills.base import SkillInput, SkillOutput


class ImageIngestInput(SkillInput):
    """Input for image-based data ingestion."""

    image_bytes: bytes = b""
    filename: str = ""
    custom_table_name: str | None = None


class ImageIngestOutput(SkillOutput):
    """Output of the image ingest skill."""

    action_taken: str = Field("", description="describe, ocr, extract_table, ingest_table, chart")
    success: bool = True
    table_name: str | None = None
    rows_ingested: int = 0
    columns: list[str] = Field(default_factory=list)
    data_preview: list[dict[str, Any]] | None = None
