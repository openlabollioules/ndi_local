import io

import pandas as pd
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ndi_api.services.rate_limiter import EXPORT_LIMIT, limiter

router = APIRouter(prefix="/export")


class ExportRequest(BaseModel):
    data: list[dict]
    filename: str = "export"


@router.post("/parquet")
@limiter.limit(EXPORT_LIMIT)
async def export_parquet(request: Request, payload: ExportRequest) -> StreamingResponse:
    """Exporte des données en format Parquet."""
    if not payload.data:
        return StreamingResponse(
            io.BytesIO(),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename={payload.filename}.parquet"},
        )

    # Convertir en DataFrame
    df = pd.DataFrame(payload.data)

    # Écrire en Parquet dans un buffer
    buffer = io.BytesIO()
    df.to_parquet(buffer, index=False, engine="pyarrow")
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={payload.filename}.parquet"},
    )


@router.post("/csv")
@limiter.limit(EXPORT_LIMIT)
async def export_csv(request: Request, payload: ExportRequest) -> StreamingResponse:
    """Exporte des données en format CSV."""
    if not payload.data:
        return StreamingResponse(
            io.BytesIO(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={payload.filename}.csv"},
        )

    # Convertir en DataFrame
    df = pd.DataFrame(payload.data)

    # Écrire en CSV dans un buffer
    buffer = io.BytesIO()
    df.to_csv(buffer, index=False, sep=";", encoding="utf-8-sig")
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={payload.filename}.csv"},
    )


@router.post("/xlsx")
@limiter.limit(EXPORT_LIMIT)
async def export_xlsx(request: Request, payload: ExportRequest) -> StreamingResponse:
    """Exporte des données en format Excel XLSX."""
    if not payload.data:
        return StreamingResponse(
            io.BytesIO(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={payload.filename}.xlsx"},
        )

    # Convertir en DataFrame
    df = pd.DataFrame(payload.data)

    # Écrire en Excel dans un buffer
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Résultats")
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={payload.filename}.xlsx"},
    )
