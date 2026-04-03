"""Conformity audit routes — check data against business rules."""

from __future__ import annotations

import io
import logging

import pandas as pd
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ndi_api.api.dependencies import PluginDep
from ndi_api.services.conformity import apply_corrections, run_conformity_audit
from ndi_api.services.rate_limiter import EXPORT_LIMIT, limiter

router = APIRouter(prefix="/conformity")
logger = logging.getLogger(__name__)


class ConformityRequest(BaseModel):
    """Request for a conformity audit."""

    table_name: str | None = Field(None, description="Table to audit (None = first/largest)")
    rules: str = Field(..., min_length=5, description="Rules in natural language, one per line")
    columns: list[str] | None = Field(None, description="Only check these columns (None = all)")
    max_rows: int = Field(0, description="Max rows to check (0 = all)")


class CorrectedExportRequest(BaseModel):
    """Request to export corrected data."""

    table_name: str | None = None
    corrections: list[dict] = Field(..., description="Corrections from a previous audit")
    format: str = Field("xlsx", description="csv | xlsx")


@router.post("/audit")
async def audit_conformity(request: ConformityRequest, plugin: PluginDep) -> dict:
    """Run a conformity audit on a table against user-defined rules.

    The rules are written in **natural language**, one per line. Examples:

    - "La colonne Motif ne doit contenir que : MO, Matériel, Management"
    - "Si État = Actif, alors Responsable doit être rempli"
    - "Le nombre d'heures ne peut pas dépasser 24"

    The service pre-filters with Python for simple rules, then uses the LLM
    for semantic/coherence checks.
    """
    # Get data
    schema = plugin.get_schema()
    tables = schema.tables if hasattr(schema, "tables") else []
    if not tables:
        raise HTTPException(status_code=404, detail="Aucune table disponible.")

    # Find target table
    if request.table_name:
        target = next((t for t in tables if t.name == request.table_name), None)
        if not target:
            raise HTTPException(status_code=404, detail=f"Table '{request.table_name}' non trouvée.")
        table_name = target.name
    else:
        table_name = tables[0].name

    # Fetch data
    limit = request.max_rows if request.max_rows > 0 else 999_999_999
    result = plugin.preview_table(table_name, limit=limit, offset=0)
    rows = result.rows if hasattr(result, "rows") else []

    if not rows:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' est vide.")

    # Filter columns if specified
    if request.columns:
        rows = [{k: v for k, v in row.items() if k in request.columns} for row in rows]

    logger.info("Conformity audit: table=%s, rows=%d, rules=%d chars", table_name, len(rows), len(request.rules))

    # Run audit
    report = run_conformity_audit(rows, request.rules, table_name)

    return report


@router.post("/export-corrected")
@limiter.limit(EXPORT_LIMIT)
async def export_corrected(
    request_obj: Request, request: CorrectedExportRequest, plugin: PluginDep
) -> StreamingResponse:
    """Export a corrected version of the data with fixes applied.

    Pass the ``corrections`` array from a previous ``/audit`` response.
    """
    # Get original data
    schema = plugin.get_schema()
    tables = schema.tables if hasattr(schema, "tables") else []
    if not tables:
        raise HTTPException(status_code=404, detail="Aucune table.")

    table_name = request.table_name or tables[0].name
    result = plugin.preview_table(table_name, limit=999_999_999, offset=0)
    rows = result.rows if hasattr(result, "rows") else []

    if not rows:
        raise HTTPException(status_code=404, detail="Table vide.")

    # Apply corrections
    corrected = apply_corrections(rows, request.corrections)
    df = pd.DataFrame(corrected)

    filename = f"{table_name}_corrige"
    buffer = io.BytesIO()

    if request.format == "csv":
        df.to_csv(buffer, index=False, sep=";", encoding="utf-8-sig")
        buffer.seek(0)
        return StreamingResponse(
            buffer,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}.csv"},
        )

    # Default: XLSX
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Données corrigées")
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}.xlsx"},
    )
