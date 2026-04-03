"""Vector store service — Qdrant implementation.

Replaces the previous ChromaDB backend with Qdrant for better concurrency,
no schema migration issues, and proper client/server architecture.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Iterable

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams,
)

from ndi_api.services.llm import get_embeddings
from ndi_api.settings import settings

logger = logging.getLogger("ndi.vector_store")

# ── Client singleton with health check ────────────────────────────────

_client: QdrantClient | None = None
_client_created_at: float = 0.0
_HEALTH_CHECK_INTERVAL = 300.0  # 5 minutes
_VECTOR_SIZE: int | None = None  # detected on first upsert


def _create_client() -> QdrantClient:
    return QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        timeout=30,
    )


def get_client() -> QdrantClient:
    """Get or create Qdrant client with periodic health check."""
    global _client, _client_created_at

    now = time.monotonic()

    if _client is not None:
        if (now - _client_created_at) > _HEALTH_CHECK_INTERVAL:
            try:
                _client.get_collections()
                _client_created_at = now
            except Exception:
                logger.warning("Qdrant health check failed — reconnecting")
                _client = None

    if _client is None:
        _client = _create_client()
        _client_created_at = now
        logger.info("Qdrant client connected to %s", settings.qdrant_url)

    return _client


def reset_client() -> None:
    """Reset the Qdrant client (useful after purge or config change)."""
    global _client, _client_created_at
    if _client is not None:
        _client.close()
    _client = None
    _client_created_at = 0.0
    logger.info("Qdrant client reset")


# Keep backward-compatible name used by other modules
reset_chroma_client = reset_client


# ── Collection management ─────────────────────────────────────────────


def _ensure_collection(name: str | None = None, vector_size: int = 1024) -> str:
    """Ensure the collection exists, create if missing."""
    coll_name = name or settings.qdrant_collection
    client = get_client()

    existing = [c.name for c in client.get_collections().collections]
    if coll_name not in existing:
        client.create_collection(
            collection_name=coll_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
        logger.info("Created Qdrant collection '%s' (dim=%d)", coll_name, vector_size)

    return coll_name


def get_collection(name: str | None = None):
    """Get collection info. Creates if missing."""
    coll_name = _ensure_collection(name)
    client = get_client()
    return client.get_collection(coll_name)


# ── Core operations ───────────────────────────────────────────────────


def upsert_documents(
    documents: Iterable[str],
    ids: Iterable[str],
    metadatas: Iterable[dict] | None = None,
) -> int:
    """Upsert documents with embeddings into Qdrant."""
    global _VECTOR_SIZE

    docs = list(documents)
    ids_list = list(ids)
    metas = list(metadatas) if metadatas is not None else [{}] * len(docs)

    embeddings = get_embeddings().embed_documents(docs)

    if not embeddings:
        return 0

    # Detect vector size from first embedding
    if _VECTOR_SIZE is None:
        _VECTOR_SIZE = len(embeddings[0])

    coll_name = _ensure_collection(vector_size=_VECTOR_SIZE)
    client = get_client()

    points = []
    for doc_id, doc, emb, meta in zip(ids_list, docs, embeddings, metas, strict=False):
        # Qdrant needs UUID or int IDs — hash string IDs
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, doc_id))
        payload = {
            "document": doc,
            "original_id": doc_id,
            **(meta or {}),
        }
        points.append(PointStruct(id=point_id, vector=emb, payload=payload))

    # Qdrant supports batch upsert
    BATCH = 100
    for i in range(0, len(points), BATCH):
        client.upsert(collection_name=coll_name, points=points[i : i + BATCH])

    return len(points)


def query_documents(query: str, k: int) -> list[str]:
    """Query documents by semantic similarity. Returns document texts."""
    try:
        coll_name = settings.qdrant_collection
        client = get_client()

        # Check collection exists
        existing = [c.name for c in client.get_collections().collections]
        if coll_name not in existing:
            return []

        query_embedding = get_embeddings().embed_query(query)

        results = client.query_points(
            collection_name=coll_name,
            query=query_embedding,
            limit=k,
            with_payload=True,
        )

        return [
            hit.payload.get("document", "") for hit in results.points if hit.payload and hit.payload.get("document")
        ]
    except Exception:
        logger.warning("Vector store query failed — falling back to empty results", exc_info=True)
        return []


def get_index_count() -> int:
    """Get total number of indexed vectors."""
    try:
        coll_name = settings.qdrant_collection
        client = get_client()

        existing = [c.name for c in client.get_collections().collections]
        if coll_name not in existing:
            return 0

        info = client.get_collection(coll_name)
        return info.points_count or 0
    except Exception:
        logger.warning("Failed to get index count", exc_info=True)
        return 0
