"""Routes for image analysis using vision-capable LLM."""

from __future__ import annotations

import io
import logging
import re

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ndi_api.plugins.manager import get_plugin_manager
from ndi_api.services.image_analysis import (
    ImageAnalysisResult,
    get_image_analysis_service,
)
from ndi_api.services.indexing import index_schema
from ndi_api.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/images")


class ImageAnalysisResponse(BaseModel):
    """Response model for image analysis."""

    description: str
    confidence: float
    objects_detected: list[str]
    analysis_type: str


@router.post("/analyze", response_model=ImageAnalysisResponse)
async def analyze_image(
    file: UploadFile = File(..., description="Image file to analyze"),
    prompt: str | None = Form(None, description="Custom analysis prompt"),
    analysis_type: str = Form("general", description="Type of analysis: general, ocr, objects, chart, data_table"),
):
    """
    Analyze an uploaded image using a vision-capable LLM.

    Supports formats: JPG, PNG, GIF, WebP, BMP (max 10MB)

    Analysis types:
    - **general**: General description of the image
    - **ocr**: Extract text from the image
    - **objects**: List objects in the image
    - **chart**: Analyze charts/graphs
    - **data_table**: Extract data tables

    Requires a vision-capable model configured via NDI_VISION_MODEL.
    """
    try:
        # Read image bytes
        image_bytes = await file.read()

        # Get service and analyze
        service = get_image_analysis_service()
        result: ImageAnalysisResult = await service.analyze_image(
            image_bytes=image_bytes, filename=file.filename, prompt=prompt, analysis_type=analysis_type
        )

        return ImageAnalysisResponse(
            description=result.description,
            confidence=result.confidence,
            objects_detected=result.objects_detected,
            analysis_type=result.analysis_type,
        )

    except ValueError as e:
        logger.warning(f"Invalid image upload: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.error(f"Image analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error in image analysis")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/supported-formats")
async def get_supported_formats():
    """Get list of supported image formats."""
    service = get_image_analysis_service()
    return {
        "formats": list(service.SUPPORTED_FORMATS),
        "max_size_mb": service.MAX_IMAGE_SIZE / (1024 * 1024),
        "max_dimension": service.MAX_DIMENSION,
    }


class ImageIngestResponse(BaseModel):
    """Response model for image data ingestion."""

    success: bool
    table_name: str | None
    rows_ingested: int
    columns: list[str]
    analysis_preview: str
    message: str


def _markdown_to_csv(markdown_table: str) -> tuple[str, list[str]]:
    """Convert markdown table to CSV format.

    Returns:
        (csv_content, column_names)
    """
    lines = markdown_table.strip().split("\n")

    # Filter out separator lines (|---|---|...)
    data_lines = [line for line in lines if not re.match(r"^\|?[-:|\s]+\|?$", line.strip())]

    if not data_lines:
        raise ValueError("No valid table data found in markdown")

    # Parse rows
    rows = []
    for line in data_lines:
        # Split by | and clean
        cells = [cell.strip() for cell in line.split("|")]
        # Remove empty cells from start/end
        cells = [c for c in cells if c]
        if cells:
            rows.append(cells)

    if len(rows) < 1:
        raise ValueError("Table must have at least a header row")

    # Convert to CSV
    csv_lines = [",".join(f'"{cell.replace("\"", "\"\"")}"' for cell in row) for row in rows]

    return "\n".join(csv_lines), rows[0] if rows else []


@router.post("/ingest", response_model=ImageIngestResponse)
async def ingest_image_data(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Image containing a data table"),
    table_name: str | None = Form(None, description="Custom table name (default: auto-generated from filename)"),
):
    """
    Extract data table from an image and ingest it directly.

    This endpoint combines image analysis with data ingestion:
    1. Analyzes the image to extract tabular data
    2. Converts the markdown table to CSV format
    3. Ingests the data into the database
    4. Triggers schema indexing (if enabled)

    Best for:
    - Screenshots of spreadsheets
    - Scanned documents with tables
    - Photos of paper forms
    - Charts with data tables

    The image should clearly show a table with headers and rows.
    """
    try:
        # Step 1: Analyze image to extract table
        image_bytes = await file.read()
        service = get_image_analysis_service()

        result: ImageAnalysisResult = await service.analyze_image(
            image_bytes=image_bytes, filename=file.filename, analysis_type="data_table"
        )

        # Step 2: Convert markdown table to CSV
        try:
            csv_content, columns = _markdown_to_csv(result.description)
        except ValueError as e:
            logger.warning(f"Failed to parse table from image: {e}")
            return ImageIngestResponse(
                success=False,
                table_name=None,
                rows_ingested=0,
                columns=[],
                analysis_preview=result.description[:500],
                message=f"Could not extract valid table data. The image might not contain a clear table. Error: {e}",
            )

        # Step 3: Determine table name
        if not table_name:
            # Generate from filename
            base_name = file.filename.rsplit(".", 1)[0] if "." in file.filename else file.filename
            table_name = re.sub(r"[^a-zA-Z0-9_]", "_", base_name).lower()
            table_name = re.sub(r"_+", "_", table_name).strip("_")
            if not table_name:
                table_name = "image_data"

        # Step 4: Get plugin and ingest
        plugin = get_plugin_manager().get_plugin()

        # Read CSV content into DataFrame
        import pandas as pd

        df = pd.read_csv(io.StringIO(csv_content))

        # Ingest using plugin
        final_table_name = plugin.ingest_dataframe(df, f"{table_name}.csv")

        # Step 5: Trigger indexing in background
        if settings.indexing_enabled:
            background_tasks.add_task(index_schema)

        return ImageIngestResponse(
            success=True,
            table_name=final_table_name,
            rows_ingested=len(df),
            columns=list(df.columns),
            analysis_preview=result.description[:300],
            message=f"Successfully extracted and ingested {len(df)} rows into '{final_table_name}'",
        )

    except ValueError as e:
        logger.warning(f"Invalid image upload: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.error(f"Image analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error in image ingestion")
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")
