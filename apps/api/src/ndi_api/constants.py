"""Shared constants and utilities — single source of truth.

Centralises values that were previously duplicated across
``plugins/sql_plugin.py``, ``services/nl_sql.py``, and ``services/ingestion.py``.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# SQL validation keyword sets  (read-only enforcement)
# ---------------------------------------------------------------------------

ALLOWED_SQL_KEYWORDS: frozenset[str] = frozenset(
    {
        "SELECT",
        "FROM",
        "WHERE",
        "JOIN",
        "INNER",
        "LEFT",
        "RIGHT",
        "OUTER",
        "ON",
        "AND",
        "OR",
        "NOT",
        "NULL",
        "IS",
        "IN",
        "EXISTS",
        "BETWEEN",
        "LIKE",
        "ESCAPE",
        "GROUP",
        "BY",
        "ORDER",
        "HAVING",
        "LIMIT",
        "OFFSET",
        "UNION",
        "ALL",
        "DISTINCT",
        "AS",
        "CASE",
        "WHEN",
        "THEN",
        "ELSE",
        "END",
        "CAST",
        "COALESCE",
        "IFNULL",
        "NULLIF",
        "COUNT",
        "SUM",
        "AVG",
        "MIN",
        "MAX",
        "ROUND",
        "ABS",
        "UPPER",
        "LOWER",
        "TRIM",
        "SUBSTRING",
        "LENGTH",
        "REPLACE",
        "CONCAT",
        "DATE",
        "EXTRACT",
        "YEAR",
        "MONTH",
        "DAY",
        "STRFTIME",
        "WITH",
        "OVER",
        "PARTITION",
        "ROW_NUMBER",
        "RANK",
        "DENSE_RANK",
    }
)

FORBIDDEN_SQL_KEYWORDS: frozenset[str] = frozenset(
    {
        "DROP",
        "DELETE",
        "UPDATE",
        "INSERT",
        "ALTER",
        "CREATE",
        "TRUNCATE",
        "UPSERT",
        "MERGE",
        "GRANT",
        "REVOKE",
        "COMMIT",
        "ROLLBACK",
        "VACUUM",
        "ATTACH",
        "DETACH",
        "PRAGMA",
        "LOAD_EXTENSION",
        # Note: REPLACE (the text function) is in ALLOWED.
        # REPLACE INTO is blocked by the SELECT/WITH first-token check.
    }
)

# ---------------------------------------------------------------------------
# Column name normalization  (shared between sql_plugin and ingestion)
# ---------------------------------------------------------------------------

_NON_ALNUM_RE = re.compile(r"[^0-9a-zA-Z]+")
_MULTI_UNDERSCORE = re.compile(r"_+")
_STRIP_PREFIXES: frozenset[str] = frozenset(
    {
        "col",
        "field",
        "fld",
        "column",
        "champ",
    }
)


def to_snake(value: str) -> str:
    """Convert an arbitrary string to a safe snake_case identifier."""
    cleaned = _NON_ALNUM_RE.sub("_", value.strip())
    cleaned = _MULTI_UNDERSCORE.sub("_", cleaned).strip("_")
    return cleaned.lower()


def strip_meaningless_prefix(parts: list[str]) -> list[str]:
    """Remove well-known meaningless prefixes (col_, field_, etc.)."""
    if len(parts) <= 1:
        return parts
    if parts[0] in _STRIP_PREFIXES:
        return parts[1:]
    return parts


def normalize_column_name(name: str) -> str:
    """Normalize a raw column name to a safe snake_case identifier."""
    snake = to_snake(name)
    parts = snake.split("_")
    parts = strip_meaningless_prefix(parts)
    return "_".join(parts) or snake


def deduplicate_columns(columns: list[str]) -> list[str]:
    """Append ``_2``, ``_3``… suffixes when normalisation produces duplicates."""
    seen: dict[str, int] = {}
    result: list[str] = []
    for col in columns:
        if col not in seen:
            seen[col] = 1
            result.append(col)
        else:
            seen[col] += 1
            result.append(f"{col}_{seen[col]}")
    return result
