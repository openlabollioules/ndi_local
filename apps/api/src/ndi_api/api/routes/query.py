import asyncio
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Request

from ndi_api.schemas.query import QueryRequest, QueryResponse
from ndi_api.services.nl_sql import run_nl_sql
from ndi_api.services.rate_limiter import QUERY_LIMIT, limiter

router = APIRouter(prefix="/query")

# Pool d'exécution pour les appels synchrones bloquants
_query_executor = ThreadPoolExecutor(max_workers=4)


@router.post("", response_model=QueryResponse)
@limiter.limit(QUERY_LIMIT)
async def run_query(request: Request, payload: QueryRequest) -> QueryResponse:
    # Exécuter run_nl_sql dans un thread pour ne pas bloquer la boucle async
    result = await asyncio.get_event_loop().run_in_executor(_query_executor, run_nl_sql, payload.question)
    return QueryResponse(
        answer=result["answer"],
        sql=result["sql"],
        rows=result["rows"],
    )
