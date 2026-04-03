"""Evaluation endpoints for testing retrieval improvements (re-ranker, etc.)."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from ndi_api.services.reranker import FakeReranker, LightweightReranker, get_reranker, rerank_documents
from ndi_api.services.vector_store import query_documents

router = APIRouter(prefix="/eval")


class RetrievalComparisonRequest(BaseModel):
    query: str
    top_k: int = 3
    reranker_k: int = 10


class RetrievalResult(BaseModel):
    method: str
    documents: list[str]
    scores: list[float] | None = None
    latency_ms: float
    metadata: dict[str, Any]


class ComparisonResponse(BaseModel):
    query: str
    baseline: RetrievalResult
    with_reranker: RetrievalResult
    improvement: dict[str, Any]


@router.post("/retrieval/compare", response_model=ComparisonResponse)
async def compare_retrieval_methods(
    request: RetrievalComparisonRequest,
) -> ComparisonResponse:
    """Compare retrieval with and without re-ranker.

    This endpoint helps evaluate the impact of the BGE re-ranker on retrieval quality.
    """
    query = request.query

    # 1. Baseline: Standard vector search (top-k)
    start = time.time()
    baseline_docs = query_documents(query, k=request.top_k)
    baseline_latency = (time.time() - start) * 1000

    baseline = RetrievalResult(
        method="baseline_vector_search",
        documents=baseline_docs,
        scores=None,
        latency_ms=baseline_latency,
        metadata={"k": request.top_k},
    )

    # 2. With re-ranker: Retrieve more, then re-rank
    start = time.time()

    # Retrieve more documents
    docs_to_rerank = query_documents(query, k=request.reranker_k)

    # Re-rank in a thread to avoid blocking the event loop
    reranked_docs, _, rerank_stats = await asyncio.to_thread(
        rerank_documents,
        query=query,
        documents=docs_to_rerank,
        top_k=request.top_k,
        use_reranker=True,
    )

    reranker_latency = (time.time() - start) * 1000

    with_reranker = RetrievalResult(
        method="vector_search_with_reranker",
        documents=reranked_docs,
        scores=rerank_stats.get("scores"),
        latency_ms=reranker_latency,
        metadata={
            "initial_k": request.reranker_k,
            "final_k": request.top_k,
            "reranker_method": rerank_stats.get("method", "unknown"),
        },
    )

    # Calculate improvement metrics
    overlap = len(set(baseline_docs) & set(reranked_docs))

    improvement = {
        "latency_overhead_ms": reranker_latency - baseline_latency,
        "latency_overhead_percent": (
            ((reranker_latency - baseline_latency) / baseline_latency * 100) if baseline_latency > 0 else 0
        ),
        "documents_overlap": overlap,
        "documents_overlap_percent": ((overlap / request.top_k * 100) if request.top_k > 0 else 0),
        "documents_changed": request.top_k - overlap,
    }

    return ComparisonResponse(
        query=query,
        baseline=baseline,
        with_reranker=with_reranker,
        improvement=improvement,
    )


@router.get("/retrieval/test")
async def test_retrieval(
    query: str = Query(..., description="Test query"),
    use_reranker: bool = Query(True, description="Whether to use re-ranker"),
    initial_k: int = Query(10, description="Number of documents to retrieve initially"),
    final_k: int = Query(3, description="Number of documents to return after re-ranking"),
) -> dict:
    """Test retrieval with optional re-ranker.

    Example:
        GET /api/eval/retrieval/test?query=ventes+par+region&use_reranker=true
    """
    start = time.time()

    # Retrieve documents
    docs = query_documents(query, k=initial_k)
    retrieve_time = (time.time() - start) * 1000

    if not use_reranker or len(docs) <= final_k:
        return {
            "query": query,
            "method": "baseline",
            "documents": docs[:final_k],
            "timings": {
                "retrieval_ms": retrieve_time,
                "reranking_ms": 0,
                "total_ms": retrieve_time,
            },
        }

    # Re-rank in a thread to avoid blocking the event loop
    rerank_start = time.time()
    reranked, _, stats = await asyncio.to_thread(
        rerank_documents,
        query=query,
        documents=docs,
        top_k=final_k,
        use_reranker=True,
    )
    rerank_time = (time.time() - rerank_start) * 1000
    total_time = (time.time() - start) * 1000

    return {
        "query": query,
        "method": "with_reranker",
        "documents": reranked,
        "reranker_stats": stats,
        "timings": {
            "retrieval_ms": retrieve_time,
            "reranking_ms": rerank_time,
            "total_ms": total_time,
        },
    }


@router.get("/reranker/status")
async def get_reranker_status() -> dict:
    """Get current re-ranker configuration and status."""
    import os

    reranker_type = os.getenv("NDI_RERANKER_TYPE", "lightweight").lower()
    reranker_model = os.getenv("NDI_RERANKER_MODEL", "bge-reranker-v2-m3")
    use_reranker = os.getenv("NDI_USE_RERANKER", "true").lower() == "true"

    # Get actual re-ranker instance
    reranker = get_reranker()

    return {
        "configured": {
            "type": reranker_type,
            "model": reranker_model,
            "enabled": use_reranker,
        },
        "actual": {
            "class": reranker.__class__.__name__,
            "is_fake": isinstance(reranker, FakeReranker),
            "is_lightweight": isinstance(reranker, LightweightReranker),
        },
        "environment_variables": {
            "NDI_RERANKER_TYPE": reranker_type,
            "NDI_RERANKER_MODEL": reranker_model,
            "NDI_USE_RERANKER": str(use_reranker),
            "NDI_RETRIEVAL_K": os.getenv("NDI_RETRIEVAL_K", "10"),
        },
    }


@router.post("/reranker/benchmark")
async def benchmark_reranker(
    queries: list[str],
    top_k: int = 3,
    reranker_k: int = 10,
) -> dict:
    """Benchmark re-ranker on multiple queries.

    This helps evaluate the average improvement across different question types.
    """
    results = []

    for query in queries:
        # Run comparison
        result = await compare_retrieval_methods(
            RetrievalComparisonRequest(
                query=query,
                top_k=top_k,
                reranker_k=reranker_k,
            )
        )
        results.append(
            {
                "query": query,
                "overlap_percent": result.improvement["documents_overlap_percent"],
                "latency_overhead_ms": result.improvement["latency_overhead_ms"],
            }
        )

    # Calculate averages
    avg_overlap = sum(r["overlap_percent"] for r in results) / len(results)
    avg_latency = sum(r["latency_overhead_ms"] for r in results) / len(results)

    return {
        "queries_tested": len(queries),
        "results": results,
        "summary": {
            "average_overlap_percent": avg_overlap,
            "average_latency_overhead_ms": avg_latency,
            "interpretation": (
                "High overlap (>70%) = re-ranker doesn't change much\n"
                "Low overlap (<50%) = re-ranker significantly reorders results\n"
                "Ideal: Low overlap + better SQL generation quality"
            ),
        },
    }
