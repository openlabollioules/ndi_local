from fastapi import APIRouter, Depends

from ndi_api.api.routes.conformity import router as conformity_router
from ndi_api.api.routes.conversation import router as conversation_router
from ndi_api.api.routes.data import router as data_router
from ndi_api.api.routes.eval import router as eval_router
from ndi_api.api.routes.export import router as export_router
from ndi_api.api.routes.health import admin_router as health_admin_router
from ndi_api.api.routes.health import router as health_router
from ndi_api.api.routes.images import router as images_router
from ndi_api.api.routes.index import router as index_router
from ndi_api.api.routes.ingest import router as ingest_router
from ndi_api.api.routes.query import router as query_router
from ndi_api.api.routes.relations import router as relations_router
from ndi_api.api.routes.schema import router as schema_router
from ndi_api.api.routes.skills import router as skills_router
from ndi_api.api.routes.vectorstore import router as vectorstore_router
from ndi_api.services.auth import verify_api_key

api_router = APIRouter()

# Health check remains public (no auth) — only GET /health/health
api_router.include_router(health_router, tags=["health"])

# Health admin (config, performance, cache, model switching) — requires auth
api_router.include_router(health_admin_router, tags=["health-admin"], dependencies=[Depends(verify_api_key)])

# Protected routes (require API key when auth is enabled)
api_router.include_router(ingest_router, tags=["ingest"], dependencies=[Depends(verify_api_key)])
api_router.include_router(index_router, tags=["index"], dependencies=[Depends(verify_api_key)])
api_router.include_router(query_router, tags=["query"], dependencies=[Depends(verify_api_key)])
api_router.include_router(schema_router, tags=["schema"], dependencies=[Depends(verify_api_key)])
api_router.include_router(relations_router, tags=["relations"], dependencies=[Depends(verify_api_key)])
api_router.include_router(data_router, tags=["data"], dependencies=[Depends(verify_api_key)])
api_router.include_router(export_router, tags=["export"], dependencies=[Depends(verify_api_key)])
api_router.include_router(vectorstore_router, tags=["vectorstore"], dependencies=[Depends(verify_api_key)])
api_router.include_router(eval_router, tags=["evaluation"], dependencies=[Depends(verify_api_key)])
api_router.include_router(conversation_router, tags=["conversation"], dependencies=[Depends(verify_api_key)])
api_router.include_router(skills_router, tags=["skills"], dependencies=[Depends(verify_api_key)])
api_router.include_router(images_router, tags=["images"], dependencies=[Depends(verify_api_key)])
api_router.include_router(conformity_router, tags=["conformity"], dependencies=[Depends(verify_api_key)])
