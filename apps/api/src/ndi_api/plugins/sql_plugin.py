"""SQL Plugin for NDI - DuckDB implementation.

Provides relational database functionality using DuckDB.
Supports JOINs, complex queries, and table relations.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from io import BytesIO
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import sqlparse
from sqlparse import tokens as T

from ndi_api.constants import (
    FORBIDDEN_SQL_KEYWORDS,
)
from ndi_api.constants import (
    deduplicate_columns as _shared_deduplicate,
)
from ndi_api.constants import (
    normalize_column_name as _shared_normalize,
)
from ndi_api.plugins.base import (
    ColumnInfo,
    DataPlugin,
    QueryResult,
    SchemaInfo,
    TableSchema,
)
from ndi_api.services.relations import load_relations
from ndi_api.settings import settings


class SQLPlugin(DataPlugin):
    """DuckDB-based SQL plugin for relational data."""

    name = "sql"
    mode = "sql"

    # Column name normalization patterns
    _NON_ALNUM_RE = re.compile(r"[^0-9a-zA-Z]+")
    _MULTI_UNDERSCORE = re.compile(r"_+")
    _STRIP_PREFIXES = frozenset({"col", "field", "fld", "column", "champ"})

    def __init__(self):
        self._db_path: Path | None = None
        self._existing_tables: set[str] = set()

    # -----------------------------------------------------------------------
    # Connection & Lifecycle
    # -----------------------------------------------------------------------

    def initialize(self) -> None:
        """Initialize DuckDB connection and ensure data directory exists."""
        data_dir = Path(settings.data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = data_dir / settings.duckdb_filename

        # Ensure database file exists
        if not self._db_path.exists():
            with duckdb.connect(str(self._db_path)) as con:
                pass  # Just create the file

        self._refresh_existing_tables()

    def close(self) -> None:
        """Close DuckDB connection (nothing to do for file-based)."""
        self._existing_tables.clear()

    def purge(self) -> bool:
        """Delete DuckDB file and reset state."""
        if self._db_path and self._db_path.exists():
            self._db_path.unlink()
        self._existing_tables.clear()
        return True

    def _refresh_existing_tables(self) -> None:
        """Refresh the set of existing tables."""
        self._existing_tables = {t.lower() for t in self.list_tables()}

    def _get_connection(self):
        """Get a DuckDB connection."""
        if self._db_path is None:
            raise RuntimeError("Plugin not initialized")
        return duckdb.connect(str(self._db_path))

    # -----------------------------------------------------------------------
    # Column Name Normalization
    # -----------------------------------------------------------------------

    def _to_snake(self, value: str) -> str:
        """Convert to snake_case."""
        cleaned = self._NON_ALNUM_RE.sub("_", value.strip())
        cleaned = self._MULTI_UNDERSCORE.sub("_", cleaned).strip("_")
        return cleaned.lower()

    def _strip_prefix(self, tokenized: list[str]) -> list[str]:
        """Remove well-known meaningless prefixes."""
        if len(tokenized) <= 1:
            return tokenized
        if tokenized[0] in self._STRIP_PREFIXES:
            return tokenized[1:]
        return tokenized

    def normalize_column_name(self, name: str) -> str:
        """Normalize column name to snake_case."""
        return _shared_normalize(name)

    def _deduplicate_columns(self, columns: list[str]) -> list[str]:
        """Append _2, _3… suffixes when normalisation produces duplicates."""
        return _shared_deduplicate(columns)

    def _safe_table_name(self, filename: str) -> str:
        """Generate unique table name from filename."""
        stem = Path(filename).stem
        base_name = self.normalize_column_name(stem) or "table"

        name = base_name
        counter = 1

        while name.lower() in self._existing_tables:
            file_hash = hashlib.md5(filename.encode()).hexdigest()[:4]
            name = f"{base_name}_{file_hash}"
            if counter > 1:
                name = f"{name}_{counter}"
            counter += 1

            if counter > 100:
                name = f"table_{hashlib.md5(filename.encode()).hexdigest()[:8]}"
                break

        return name

    # -----------------------------------------------------------------------
    # Ingestion
    # -----------------------------------------------------------------------

    def read_file(self, file_bytes: bytes, filename: str, sheet_name: str | int | None = None) -> pd.DataFrame:
        """Read a file into a DataFrame with encoding detection for CSV."""
        suffix = Path(filename).suffix.lower()

        if suffix == ".csv":
            bio = BytesIO(file_bytes)
            # Try to detect encoding
            encoding = "utf-8"
            try:
                import chardet

                result = chardet.detect(file_bytes[:10000])
                detected = result.get("encoding", "utf-8")
                confidence = result.get("confidence", 0)
                if detected and confidence > 0.5:
                    encoding = detected
            except ImportError:
                pass  # chardet not installed, use utf-8
            except Exception:
                pass  # detection failed, use utf-8

            try:
                if len(file_bytes) > 50 * 1024 * 1024:
                    chunks = pd.read_csv(bio, chunksize=10_000, low_memory=False, encoding=encoding)
                    return pd.concat(chunks, ignore_index=True)
                return pd.read_csv(bio, low_memory=False, encoding=encoding)
            except UnicodeDecodeError:
                # Fallback to latin-1
                bio.seek(0)
                if len(file_bytes) > 50 * 1024 * 1024:
                    chunks = pd.read_csv(bio, chunksize=10_000, low_memory=False, encoding="latin-1")
                    return pd.concat(chunks, ignore_index=True)
                return pd.read_csv(bio, low_memory=False, encoding="latin-1")

        if suffix in {".xls", ".xlsx"}:
            if sheet_name is not None:
                return pd.read_excel(BytesIO(file_bytes), sheet_name=sheet_name)
            return pd.read_excel(BytesIO(file_bytes))

        if suffix == ".parquet":
            return pd.read_parquet(BytesIO(file_bytes))

        raise ValueError(f"Format de fichier non supporté: {suffix}")

    def ingest_dataframe(
        self,
        df: pd.DataFrame,
        name: str,
        on_step: Callable[[str, str], None] | None = None,
    ) -> str:
        """Ingest a DataFrame into DuckDB."""
        # Validate table name before using it in SQL
        self._validate_sql_identifier(name)

        # Normalize column names
        if on_step:
            on_step("normalize_columns", "Normalisation des noms de colonnes")

        raw_names = [self.normalize_column_name(str(c)) for c in df.columns]
        df.columns = self._deduplicate_columns(raw_names)

        # Generate safe table name
        table_name = self._safe_table_name(name)

        # Write to DuckDB
        if on_step:
            on_step("write_duckdb", f"Écriture dans DuckDB (table: {table_name})")

        with self._get_connection() as con:
            con.register("ingest_df", df)
            con.execute(f'CREATE OR REPLACE TABLE "{table_name}" AS SELECT * FROM ingest_df')
            con.unregister("ingest_df")

        self._existing_tables.add(table_name.lower())
        return table_name

    # -----------------------------------------------------------------------
    # Schema & Metadata
    # -----------------------------------------------------------------------

    def list_tables(self) -> list[str]:
        """List all tables in the database."""
        if not self._db_path or not self._db_path.exists():
            return []

        try:
            with self._get_connection() as con:
                tables = con.execute("SHOW TABLES").fetchall()
                return [t[0] for t in tables]
        except Exception:
            return []

    def get_schema(self) -> SchemaInfo:
        """Get complete schema information."""
        tables = []

        for table_name in self.list_tables():
            table_schema = self.get_table_schema(table_name)
            if table_schema:
                tables.append(table_schema)

        relations = load_relations()
        return SchemaInfo(tables=tables, relations=relations)

    def get_table_schema(self, name: str) -> TableSchema | None:
        """Get schema for a specific table."""
        if not self.table_exists(name):
            return None

        try:
            with self._get_connection() as con:
                cols = con.execute(f"PRAGMA table_info('{name}')").fetchall()
                columns = [ColumnInfo(name=col[1], type=col[2], nullable=not col[3]) for col in cols]
                return TableSchema(name=name, columns=columns)
        except Exception:
            return None

    def table_exists(self, name: str) -> bool:
        """Check if a table exists."""
        if not self._db_path or not self._db_path.exists():
            return False

        try:
            with self._get_connection() as con:
                tables = con.execute("SHOW TABLES").fetchall()
                return any(t[0].lower() == name.lower() for t in tables)
        except Exception:
            return False

    # -----------------------------------------------------------------------
    # Querying
    # -----------------------------------------------------------------------

    def _validate_sql_identifier(self, name: str) -> str:
        """Validate SQL identifier."""
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name):
            raise ValueError(f"Nom de table invalide: {name}")
        return name

    def execute_query(self, query: str, limit: int | None = None) -> QueryResult:
        """Execute a SQL query."""
        if not self._db_path or not self._db_path.exists():
            return QueryResult(error="Database not found")

        # Apply limit only if explicitly set and > 0
        max_limit = settings.sql_result_limit
        if limit is None and max_limit:
            limit = max_limit
        elif limit and max_limit:
            limit = min(limit, max_limit)

        try:
            with self._get_connection() as con:
                result = con.execute(query).fetchdf()

            if limit and limit > 0 and len(result) > limit:
                result = result.head(limit)

            rows = json.loads(result.to_json(orient="records"))
            return QueryResult(
                rows=rows,
                columns=list(result.columns),
                total_count=len(rows),
                query_text=query,
            )
        except Exception as e:
            return QueryResult(error=str(e), query_text=query)

    def preview_table(self, name: str, limit: int = 50, offset: int = 0) -> QueryResult:
        """Get a preview of a table with pagination."""
        if not self.table_exists(name):
            return QueryResult(error=f"Table '{name}' not found")

        if not self._db_path or not self._db_path.exists():
            return QueryResult(error="Database not found")

        try:
            safe_table = self._validate_sql_identifier(name)
            safe_limit = max(1, int(limit))
            safe_offset = max(0, int(offset))

            with self._get_connection() as con:
                # Get total count
                count_result = con.execute(f'SELECT COUNT(*) as total FROM "{safe_table}"').fetchone()
                total_count = int(count_result[0]) if count_result else 0

                # Get paginated data
                df = con.execute(f'SELECT * FROM "{safe_table}" LIMIT ? OFFSET ?', [safe_limit, safe_offset]).fetchdf()

            rows = json.loads(df.to_json(orient="records"))
            return QueryResult(
                rows=rows,
                columns=list(df.columns),
                total_count=total_count,
                query_text=f"SELECT * FROM {safe_table} LIMIT {safe_limit} OFFSET {safe_offset}",
            )
        except Exception as e:
            return QueryResult(error=str(e))

    # -----------------------------------------------------------------------
    # NL-to-Query specific
    # -----------------------------------------------------------------------

    def validate_query(self, query: str) -> tuple[bool, str]:
        """Validate SQL for read-only safety."""
        if not query or not query.strip():
            return False, "Requête SQL vide."

        sql_clean = query.strip().upper()

        # Check forbidden keywords
        for keyword in FORBIDDEN_SQL_KEYWORDS:
            pattern = r"\b" + keyword + r"\b"
            if re.search(pattern, sql_clean):
                return False, f"Opération '{keyword}' non autorisée."

        # Parse SQL
        try:
            parsed = sqlparse.parse(query)
            if not parsed:
                return False, "Impossible de parser la requête SQL."

            first_statement = parsed[0]
            first_token = None

            for token in first_statement.tokens:
                if token.ttype not in (T.Whitespace, T.Comment.Single, T.Comment.Multiline):
                    if token.ttype in (T.Keyword.DML, T.Keyword.CTE):
                        first_token = token.value.upper()
                    elif hasattr(token, "ttype") and token.ttype:
                        first_token = str(token).upper()
                    break

            if first_token not in ("SELECT", "WITH"):
                return False, "Requête doit commencer par SELECT ou WITH."

        except Exception:
            if not re.match(r"^\s*(SELECT|WITH)\s+", sql_clean):
                return False, "Requête doit commencer par SELECT ou WITH."

        return True, ""

    def get_system_prompt(self) -> str:
        """Get system prompt for NL-to-SQL generation."""
        return (
            "Tu es un assistant SQL DuckDB expert. Règles STRICTES:\n"
            "1. Utilise UNIQUEMENT les noms de colonnes listés dans le schéma.\n"
            "2. Chaque colonne est au format 'nom (type)' — utilise EXACTEMENT le nom indiqué.\n"
            "3. N'invente JAMAIS de colonnes qui n'apparaissent pas dans le schéma.\n"
            "4. N'effectue des JOINs QUE si une relation est déclarée.\n"
            "5. Retourne UNIQUEMENT la requête SQL, sans explication, sans markdown.\n\n"
            "Fonctions DuckDB utiles:\n"
            "- Dates: YEAR(col), MONTH(col), DAY(col), EXTRACT(YEAR FROM col)\n"
            "- Texte: LOWER(col), UPPER(col), CONTAINS(col, 'x'), col ILIKE '%x%'\n"
            "- Agrégation: COUNT(*), SUM(col), AVG(col), MIN(col), MAX(col)\n"
            "- Fenêtrage: ROW_NUMBER() OVER (PARTITION BY col ORDER BY col2)\n\n"
            "Exemple:\n"
            "Q: liste des commandes de 2025\n"
            "SQL: SELECT * FROM commandes WHERE YEAR(date_commande) = 2025"
        )

    def get_query_context(self, question: str, relevant_items: list[str]) -> str:
        """Build query context for NL-to-SQL."""
        # Get schema
        schema_info = self.get_schema()

        # Build relation block
        relation_lines = []
        relevant_tables = set()

        # Extract table names from vector results
        for doc in relevant_items:
            for match in re.finditer(r"[Tt]able\s+(\w+)", doc):
                relevant_tables.add(match.group(1).lower())

        # Filter relations
        for rel in schema_info.relations:
            from_table = rel.get("from_table", "").lower()
            to_table = rel.get("to_table", "").lower()

            if relevant_tables and from_table not in relevant_tables and to_table not in relevant_tables:
                continue

            join_example = f"JOIN {rel['to_table']} ON {rel['from_table']}.{rel['from_column']} = {rel['to_table']}.{rel['to_column']}"
            relation_lines.append(
                f"Relation: {rel['from_table']}.{rel['from_column']} -> {rel['to_table']}.{rel['to_column']}\n"
                f"  Syntaxe JOIN: {join_example}"
            )

        relation_block = (
            "Relations déclarées (utilisez UNIQUEMENT celles-ci pour les JOINs):\n" + "\n\n".join(relation_lines)
            if relation_lines
            else "Aucune relation déclarée. Ne faites PAS de JOINs."
        )

        # Build context from relevant items
        if relevant_items:
            combined = "\n".join(relevant_items)
            return f"{combined}\n\n{relation_block}"

        # Fallback: include top 3 tables
        schema = self.get_schema()
        if not schema.tables:
            return "Aucune table disponible."

        # Score tables by keyword matching
        from ndi_api.services.nl_sql import _extract_question_keywords, _score_table_relevance

        keywords = _extract_question_keywords(question)
        scored = [
            (_score_table_relevance({"name": t.name, "columns": [{"name": c.name} for c in t.columns]}, keywords), t)
            for t in schema.tables
        ]
        scored.sort(reverse=True, key=lambda x: x[0])

        context_lines = []
        for _, table in scored[:3]:
            col_descriptions = [f"{c.name} ({c.type})" for c in table.columns]
            context_lines.append(f"Table {table.name} colonnes: {', '.join(col_descriptions)}")

        context = "\n".join(context_lines) if context_lines else ""
        return f"{context}\n\n{relation_block}" if context else relation_block

    # -----------------------------------------------------------------------
    # Relations
    # -----------------------------------------------------------------------

    def supports_relations(self) -> bool:
        """SQL mode supports relations."""
        return True

    def get_relations(self) -> list[dict]:
        """Get declared relations."""
        return load_relations()

    def save_relation(self, relation: dict) -> bool:
        """Save a relation."""
        from ndi_api.services.relations import upsert_relation

        upsert_relation(relation)
        return True

    # -----------------------------------------------------------------------
    # Stats & Sampling
    # -----------------------------------------------------------------------

    def get_table_stats(self, name: str) -> dict[str, Any]:
        """Get statistics about a table."""
        if not self.table_exists(name):
            return {"error": f"Table '{name}' not found"}

        try:
            with self._get_connection() as con:
                # Row count
                count_result = con.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()
                row_count = count_result[0] if count_result else 0

                # Column stats
                schema = self.get_table_schema(name)
                column_stats = {}

                if schema:
                    for col in schema.columns:
                        try:
                            stats = con.execute(f"""
                                SELECT 
                                    COUNT("{col.name}") as non_null,
                                    COUNT(DISTINCT "{col.name}") as unique_vals
                                FROM "{name}"
                            """).fetchone()
                            column_stats[col.name] = {
                                "non_null": stats[0],
                                "unique_values": stats[1],
                            }
                        except Exception:
                            pass

                return {
                    "row_count": row_count,
                    "column_stats": column_stats,
                }
        except Exception as e:
            return {"error": str(e)}

    def get_sample_data(self, name: str, limit: int = 100) -> list[dict]:
        """Get sample data from a table."""
        result = self.preview_table(name, limit=limit, offset=0)
        return result.rows
