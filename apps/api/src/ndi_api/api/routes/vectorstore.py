"""Vector store (Qdrant) management routes."""

import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ndi_api.services.cache import invalidate_schema_cache
from ndi_api.services.llm import get_embeddings
from ndi_api.services.vector_store import get_client
from ndi_api.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vectorstore")


class QueryRequest(BaseModel):
    query: str
    collection_name: str
    n_results: int = 5


class CollectionInfo(BaseModel):
    name: str
    count: int
    metadata: dict | None


class DocumentResult(BaseModel):
    id: str
    document: str | None
    metadata: dict | None
    distance: float | None


@router.get("/collections")
async def list_collections(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """Liste toutes les collections Qdrant avec leurs statistiques."""
    try:
        client = get_client()
        collections = client.get_collections().collections
        total = len(collections)
        page = collections[offset : offset + limit]

        result = []
        for col in page:
            try:
                info = client.get_collection(col.name)
                count = info.points_count or 0
            except Exception:
                count = 0
            result.append(
                CollectionInfo(
                    name=col.name,
                    count=count,
                    metadata=None,
                )
            )

        return {
            "collections": result,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_next": (offset + limit) < total,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")


@router.get("/collections/{collection_name}")
async def get_collection_info(collection_name: str) -> CollectionInfo:
    """Récupère les informations d'une collection spécifique."""
    try:
        client = get_client()
        info = client.get_collection(collection_name)
        return CollectionInfo(
            name=collection_name,
            count=info.points_count or 0,
            metadata=None,
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Collection non trouvée: {str(e)}")


@router.get("/collections/{collection_name}/peek")
async def peek_collection(
    collection_name: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """Récupère les premiers éléments d'une collection (sans recherche vectorielle)."""
    try:
        client = get_client()
        info = client.get_collection(collection_name)
        total = info.points_count or 0

        # Scroll through points
        results, _next = client.scroll(
            collection_name=collection_name,
            limit=limit,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        documents = []
        for point in results:
            payload = point.payload or {}
            documents.append(
                {
                    "id": payload.get("original_id", str(point.id)),
                    "document": payload.get("document"),
                    "metadata": {k: v for k, v in payload.items() if k not in ("document", "original_id")},
                }
            )

        return {
            "documents": documents,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_next": (offset + limit) < total,
            "has_previous": offset > 0,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")


@router.post("/query")
async def query_collection(request: QueryRequest) -> dict:
    """Effectue une recherche vectorielle dans une collection."""
    try:
        client = get_client()
        query_embedding = get_embeddings().embed_query(request.query)

        results = client.query_points(
            collection_name=request.collection_name,
            query=query_embedding,
            limit=request.n_results,
            with_payload=True,
        )

        documents = []
        for hit in results.points:
            payload = hit.payload or {}
            documents.append(
                DocumentResult(
                    id=payload.get("original_id", str(hit.id)),
                    document=payload.get("document"),
                    metadata={k: v for k, v in payload.items() if k not in ("document", "original_id")},
                    distance=hit.score,
                )
            )

        return {
            "query": request.query,
            "results": [doc.model_dump() for doc in documents],
            "collection": request.collection_name,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")


@router.get("/health")
async def health_check() -> dict:
    """Vérifie la santé du vector store et retourne les statistiques globales."""
    try:
        client = get_client()
        collections = client.get_collections().collections

        stats = {
            "status": "ok",
            "backend": "qdrant",
            "url": settings.qdrant_url,
            "total_collections": len(collections),
            "total_vectors": 0,
            "collections": [],
        }

        for col in collections:
            try:
                info = client.get_collection(col.name)
                count = info.points_count or 0
            except Exception:
                count = 0
            stats["total_vectors"] += count
            stats["collections"].append({"name": col.name, "count": count})

        return stats
    except Exception as e:
        return {
            "status": "error",
            "backend": "qdrant",
            "error": str(e),
            "total_collections": 0,
            "total_vectors": 0,
            "collections": [],
        }


@router.post("/purge")
async def purge_vectorstore() -> dict:
    """Purge le vector store Qdrant — supprime toutes les collections."""
    deleted_collections: list[str] = []

    try:
        client = get_client()
        for col in client.get_collections().collections:
            deleted_collections.append(col.name)
            client.delete_collection(col.name)
    except Exception as e:
        logger.warning("Impossible de lister/supprimer les collections: %s", e)

    invalidate_schema_cache()

    logger.info("Vector store purgé: %d collections supprimées", len(deleted_collections))

    return {
        "message": "Vector store purgé avec succès",
        "collections_deleted": deleted_collections,
    }
