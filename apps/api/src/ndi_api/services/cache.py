"""Simple TTL cache for expensive operations."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from functools import wraps
from typing import TypeVar

T = TypeVar("T")


class TTLCache:
    """Simple in-memory cache with time-to-live."""

    def __init__(self, default_ttl: int = 3600) -> None:
        """
        Initialize cache.

        Args:
            default_ttl: Default time-to-live in seconds (default: 1 hour)
        """
        self._cache: dict[str, tuple[T, float]] = {}
        self._default_ttl = default_ttl

    def get(self, key: str) -> T | None:
        """Get value from cache if not expired."""
        if key not in self._cache:
            return None

        value, expiry = self._cache[key]
        if time.time() > expiry:
            del self._cache[key]
            return None

        return value

    def set(self, key: str, value: T, ttl: int | None = None) -> None:
        """Set value in cache with TTL."""
        expiry = time.time() + (ttl if ttl is not None else self._default_ttl)
        self._cache[key] = (value, expiry)

    def delete(self, key: str) -> None:
        """Delete key from cache."""
        self._cache.pop(key, None)

    def clear(self) -> None:
        """Clear all cache."""
        self._cache.clear()

    def keys(self) -> list[str]:
        """Get all non-expired keys."""
        now = time.time()
        valid_keys = []
        expired = []

        for key, (_, expiry) in self._cache.items():
            if now > expiry:
                expired.append(key)
            else:
                valid_keys.append(key)

        # Clean expired
        for key in expired:
            del self._cache[key]

        return valid_keys


# Global cache instances — TTLs configurable via NDI_CACHE_TTL_* env vars
from ndi_api.settings import settings as _settings

nl_sql_cache = TTLCache(default_ttl=_settings.cache_ttl_query)
schema_cache = TTLCache(default_ttl=_settings.cache_ttl_schema)
embedding_cache = TTLCache(default_ttl=_settings.cache_ttl_embedding)


def hash_question(question: str, schema_hash: str = "") -> str:
    """Create a hash for a question + schema context."""
    content = f"{question.lower().strip()}:{schema_hash}"
    return hashlib.sha256(content.encode()).hexdigest()[:32]


def hash_schema(schema: list[dict]) -> str:
    """Create a hash for schema structure."""
    # Normalize and hash schema
    schema_str = json.dumps(schema, sort_keys=True)
    return hashlib.sha256(schema_str.encode()).hexdigest()[:16]


def cached_nl_sql(ttl: int = 3600):
    """Decorator to cache NL-SQL results."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(question: str, *args, **kwargs) -> dict:
            # Generate cache key from question
            cache_key = hash_question(question)

            # Try cache
            cached = nl_sql_cache.get(cache_key)
            if cached is not None:
                # Add cache hit indicator
                cached["_cache_hit"] = True
                return cached

            # Execute and cache
            result = func(question, *args, **kwargs)

            # Only cache successful results
            if result.get("sql") and not result.get("error"):
                nl_sql_cache.set(cache_key, result.copy(), ttl)

            result["_cache_hit"] = False
            return result

        return wrapper

    return decorator


def invalidate_schema_cache() -> None:
    """Invalidate schema cache when data changes."""
    schema_cache.clear()
    # Also invalidate NL-SQL cache since schema changed
    nl_sql_cache.clear()


def get_cache_stats() -> dict:
    """Get cache statistics."""
    return {
        "nl_sql": {
            "keys": len(nl_sql_cache.keys()),
            "ttl_default": nl_sql_cache._default_ttl,
        },
        "schema": {
            "keys": len(schema_cache.keys()),
            "ttl_default": schema_cache._default_ttl,
        },
        "embedding": {
            "keys": len(embedding_cache.keys()),
            "ttl_default": embedding_cache._default_ttl,
        },
    }
