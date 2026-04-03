"""BGE Re-ranker service for improved retrieval quality."""

from __future__ import annotations

from typing import Protocol

import httpx
import numpy as np
from pydantic import BaseModel

from ndi_api.settings import settings


class RankResult(BaseModel):
    """Result of re-ranking."""

    index: int  # Original index in input list
    document: str
    score: float  # Re-ranker score (higher = more relevant)
    metadata: dict | None = None


class RerankerClient(Protocol):
    """Protocol for re-ranker implementations."""

    def rerank(self, query: str, documents: list[str], top_k: int = 5) -> list[RankResult]:
        """Re-rank documents by relevance to query."""
        ...


class EmbeddingReranker:
    """Re-ranker using OpenAI-compatible /v1/embeddings endpoint.

    Sends query + all documents in a single batch call, then ranks by
    cosine similarity between the query embedding and each document embedding.
    """

    def __init__(
        self, model: str = "bge-reranker-v2-m3", base_url: str | None = None, api_key: str | None = None
    ) -> None:
        self.model = model
        self.base_url = base_url or settings.effective_embedding_base_url
        self.api_key = api_key or settings.effective_embedding_api_key

    def _batch_embed(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts via OpenAI-compatible /v1/embeddings."""
        headers = {"Content-Type": "application/json"}
        if self.api_key and self.api_key != "EMPTY":
            headers["Authorization"] = f"Bearer {self.api_key}"

        resp = httpx.post(
            f"{self.base_url}/embeddings",
            headers=headers,
            json={"model": self.model, "input": texts},
            timeout=60.0,
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        # Sort by index to preserve order
        data.sort(key=lambda x: x["index"])
        return [d["embedding"] for d in data]

    def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int = 5,
    ) -> list[RankResult]:
        try:
            all_texts = [query] + documents
            embeddings = self._batch_embed(all_texts)
            query_vec = np.array(embeddings[0])
            query_vec = query_vec / (np.linalg.norm(query_vec) + 1e-8)

            scored: list[RankResult] = []
            for i, doc in enumerate(documents):
                doc_vec = np.array(embeddings[i + 1])
                doc_vec = doc_vec / (np.linalg.norm(doc_vec) + 1e-8)
                cos_sim = float(np.dot(query_vec, doc_vec))
                scored.append(
                    RankResult(
                        index=i,
                        document=doc,
                        score=cos_sim,
                        metadata={"method": "embedding_reranker", "model": self.model},
                    )
                )

            scored.sort(key=lambda r: r.score, reverse=True)
            return scored[:top_k]
        except Exception:
            import logging

            logging.getLogger("ndi.reranker").warning(
                "Embedding reranker failed, falling back to lightweight",
                exc_info=True,
            )
            return LightweightReranker().rerank(query, documents, top_k)


class FakeReranker:
    """Fake re-ranker for testing (returns input order)."""

    def rerank(self, query: str, documents: list[str], top_k: int = 5) -> list[RankResult]:
        """Return documents unchanged (for A/B testing)."""
        return [
            RankResult(index=i, document=doc, score=1.0, metadata={"method": "none"})
            for i, doc in enumerate(documents[:top_k])
        ]


class LightweightReranker:
    """Lightweight re-ranker using existing embeddings + keyword scoring.

    No additional model loaded - reuses the embedding model already in memory.
    Uses cosine similarity + keyword matching for better relevance.
    """

    _CACHE_MAX_SIZE = 512  # bound to prevent memory leaks

    def __init__(self) -> None:
        self._embedding_cache: dict[str, list[float]] = {}

    def _evict_cache(self) -> None:
        """Evict oldest entries when cache exceeds max size."""
        if len(self._embedding_cache) <= self._CACHE_MAX_SIZE:
            return
        # Remove first (oldest) entries — dict preserves insertion order
        excess = len(self._embedding_cache) - self._CACHE_MAX_SIZE
        keys_to_remove = list(self._embedding_cache.keys())[:excess]
        for key in keys_to_remove:
            del self._embedding_cache[key]

    def _embed(self, texts: list[str]) -> list[list[float]]:
        """Get embeddings using existing LLM service."""
        from ndi_api.services.llm import get_embeddings

        embedder = get_embeddings()
        # Check cache first
        uncached = []
        uncached_indices = []
        results = [[] for _ in texts]

        for i, text in enumerate(texts):
            if text in self._embedding_cache:
                results[i] = self._embedding_cache[text]
            else:
                uncached.append(text)
                uncached_indices.append(i)

        # Embed uncached texts
        if uncached:
            new_embeddings = embedder.embed_documents(uncached)
            for idx, text, emb in zip(uncached_indices, uncached, new_embeddings, strict=False):
                self._embedding_cache[text] = emb
                results[idx] = emb
            self._evict_cache()

        return results

    def _extract_keywords(self, text: str) -> set[str]:
        """Extract important keywords from text."""
        # Simple keyword extraction
        words = text.lower().split()
        # Remove common stop words
        stop_words = {
            "le",
            "la",
            "les",
            "de",
            "des",
            "du",
            "un",
            "une",
            "et",
            "ou",
            "en",
            "par",
            "pour",
            "dans",
            "sur",
            "avec",
            "the",
            "a",
            "an",
            "and",
            "or",
            "in",
            "on",
            "at",
            "to",
            "for",
            "with",
            "by",
        }
        keywords = {w.strip(".,;:()[]{}") for w in words if len(w) > 2 and w not in stop_words}
        return keywords

    def _keyword_score(self, query: str, document: str) -> float:
        """Calculate keyword overlap score."""
        query_kw = self._extract_keywords(query)
        doc_kw = self._extract_keywords(document)

        if not query_kw:
            return 0.0

        matches = len(query_kw & doc_kw)
        return matches / len(query_kw)

    def _table_name_score(self, query: str, document: str) -> float:
        """Bonus if table name appears in query."""
        import re

        # Extract table name from document (e.g., "Table ventes colonnes...")
        table_match = re.search(r"[Tt]able\s+(\w+)", document)
        if not table_match:
            return 0.0

        table_name = table_match.group(1).lower()
        query_lower = query.lower()

        # Direct match
        if table_name in query_lower:
            return 1.0

        # Plural/singular variants (simple heuristic)
        if table_name.endswith("s") and table_name[:-1] in query_lower:
            return 0.8
        if not table_name.endswith("s") and (table_name + "s") in query_lower:
            return 0.8

        return 0.0

    def rerank(self, query: str, documents: list[str], top_k: int = 5) -> list[RankResult]:
        """Re-rank documents using embedding similarity + keyword matching."""
        if not documents:
            return []

        # Get embeddings
        query_emb = self._embed([query])[0]
        doc_embs = self._embed(documents)

        # Calculate cosine similarities
        query_norm = np.array(query_emb)
        query_norm = query_norm / (np.linalg.norm(query_norm) + 1e-8)

        scores = []
        for i, (doc, doc_emb) in enumerate(zip(documents, doc_embs, strict=False)):
            # Cosine similarity (0-1 range)
            doc_norm = np.array(doc_emb)
            doc_norm = doc_norm / (np.linalg.norm(doc_norm) + 1e-8)
            cos_sim = float(np.dot(query_norm, doc_norm))

            # Keyword overlap score (0-1 range)
            kw_score = self._keyword_score(query, doc)

            # Table name match bonus (0 or 1)
            table_bonus = self._table_name_score(query, doc) * 0.3

            # Combined score (weighted)
            # 60% embedding similarity, 30% keyword match, 10% table name
            final_score = (cos_sim * 0.6) + (kw_score * 0.3) + table_bonus

            scores.append(
                {
                    "index": i,
                    "document": doc,
                    "score": final_score,
                    "components": {
                        "cosine": round(cos_sim, 3),
                        "keyword": round(kw_score, 3),
                        "table_match": round(table_bonus, 3),
                    },
                }
            )

        # Sort by score descending
        scores.sort(key=lambda x: x["score"], reverse=True)

        # Return top-k
        return [
            RankResult(
                index=s["index"],
                document=s["document"],
                score=s["score"],
                metadata={"method": "lightweight", "components": s["components"]},
            )
            for s in scores[:top_k]
        ]


# Global re-ranker instance
_reranker: RerankerClient | None = None


def get_reranker() -> RerankerClient:
    """Get or initialize re-ranker client."""
    global _reranker
    if _reranker is None:
        reranker_type = settings.reranker_type.lower()

        if reranker_type == "embedding":
            _reranker = EmbeddingReranker(model=settings.reranker_model)
        elif reranker_type == "lightweight":
            _reranker = LightweightReranker()
        else:
            _reranker = FakeReranker()

    return _reranker


def set_reranker(client: RerankerClient) -> None:
    """Set global re-ranker (for testing)."""
    global _reranker
    _reranker = client


def rerank_documents(
    query: str,
    documents: list[str],
    metadatas: list[dict] | None = None,
    top_k: int = 5,
    use_reranker: bool = True,
) -> tuple[list[str], list[dict] | None, dict]:
    """Re-rank documents by relevance (SYNCHRONOUS VERSION).

    Args:
        query: User question
        documents: List of documents to re-rank
        metadatas: Optional metadata for each document
        top_k: Number of top documents to return
        use_reranker: Whether to use re-ranking (False = passthrough)

    Returns:
        Tuple of (filtered_documents, filtered_metadatas, stats)
    """
    if not documents:
        return [], None, {"method": "none", "input_count": 0, "output_count": 0}

    if not use_reranker or len(documents) <= top_k:
        # No re-ranking needed
        return (
            documents[:top_k],
            metadatas[:top_k] if metadatas else None,
            {
                "method": "passthrough",
                "input_count": len(documents),
                "output_count": min(len(documents), top_k),
            },
        )

    # Re-rank (SYNCHRONOUS)
    reranker = get_reranker()
    results = reranker.rerank(query, documents, top_k)

    # Extract top-k indices
    top_indices = [r.index for r in results[:top_k]]

    # Filter documents and metadatas
    filtered_docs = [documents[i] for i in top_indices]
    filtered_meta = [metadatas[i] for i in top_indices] if metadatas else None

    stats = {
        "method": "reranker",
        "input_count": len(documents),
        "output_count": len(filtered_docs),
        "scores": [r.score for r in results[:top_k]],
    }

    return filtered_docs, filtered_meta, stats
