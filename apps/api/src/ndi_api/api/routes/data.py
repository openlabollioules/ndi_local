from fastapi import APIRouter, HTTPException, Query

from ndi_api.api.dependencies import PluginDep
from ndi_api.schemas.data import PreviewResponse

router = APIRouter(prefix="/data")


@router.get("/preview", response_model=PreviewResponse)
async def preview_data(
    plugin: PluginDep,
    table: str = Query(...),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> PreviewResponse:
    try:
        result = plugin.preview_table(table, limit, offset)

        if result.error:
            raise HTTPException(status_code=404, detail=result.error)

        has_next = offset + limit < result.total_count
        has_previous = offset > 0
        return PreviewResponse(
            columns=result.columns,
            rows=result.rows,
            total_count=result.total_count,
            limit=limit,
            offset=offset,
            has_next=has_next,
            has_previous=has_previous,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
