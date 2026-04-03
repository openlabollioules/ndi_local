"""NoSQL Plugin for NDI - MongoDB-style document storage.

Provides document-oriented database functionality using a local JSON-based store
(similar to MongoDB) for hierarchical/nested data without JOINs.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd

from ndi_api.plugins.base import (
    ColumnInfo,
    DataPlugin,
    QueryResult,
    SchemaInfo,
    TableSchema,
)
from ndi_api.settings import settings


class NoSQLPlugin(DataPlugin):
    """Document-oriented plugin for hierarchical/nested data.

    Uses a JSON-based storage (similaire à MongoDB) where each 'collection'
    is a directory containing JSON documents.
    """

    name = "nosql"
    mode = "nosql"

    # For date detection - patterns pour différents formats
    _DATE_PATTERNS = [
        # ISO: 2023-12-31, 2023-12-31T10:30:00
        (re.compile(r"^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?"), "%Y-%m-%d"),
        # FR: 31/12/2023, 31/12/23
        (re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4}"), "%d/%m/%Y"),
        # US: 12/31/2023
        (re.compile(r"^\d{1,2}/\d{1,2}/\d{4}"), "%m/%d/%Y"),
        # Dash: 31-12-2023
        (re.compile(r"^\d{1,2}-\d{1,2}-\d{4}"), "%d-%m-%Y"),
        # Point: 31.12.2023
        (re.compile(r"^\d{1,2}\.\d{1,2}\.\d{4}"), "%d.%m.%Y"),
    ]

    def __init__(self):
        self._data_dir: Path | None = None
        self._collections_dir: Path | None = None
        self._existing_collections: set[str] = set()

    # -----------------------------------------------------------------------
    # Connection & Lifecycle
    # -----------------------------------------------------------------------

    def initialize(self) -> None:
        """Initialize document storage directories."""
        self._data_dir = Path(settings.data_dir)
        self._collections_dir = self._data_dir / "collections"
        self._collections_dir.mkdir(parents=True, exist_ok=True)
        self._refresh_existing_collections()

    def close(self) -> None:
        """Close/cleanup (nothing for file-based)."""
        self._existing_collections.clear()

    def purge(self) -> bool:
        """Delete all collections."""
        import shutil

        if self._collections_dir and self._collections_dir.exists():
            shutil.rmtree(self._collections_dir)
            self._collections_dir.mkdir(parents=True, exist_ok=True)
        self._existing_collections.clear()
        return True

    def _refresh_existing_collections(self) -> None:
        """Refresh list of existing collections."""
        if self._collections_dir and self._collections_dir.exists():
            self._existing_collections = {d.name.lower() for d in self._collections_dir.iterdir() if d.is_dir()}
        else:
            self._existing_collections = set()

    def _get_collection_path(self, name: str) -> Path:
        """Get path to a collection directory."""
        if self._collections_dir is None:
            raise RuntimeError("Plugin not initialized")
        return self._collections_dir / name

    def _safe_collection_name(self, filename: str) -> str:
        """Generate unique collection name from filename."""
        stem = Path(filename).stem
        # Clean name: alphanumeric + underscore only
        name = re.sub(r"[^a-zA-Z0-9_]", "_", stem).lower()
        name = re.sub(r"_+", "_", name).strip("_")
        if not name:
            name = "collection"

        base_name = name
        counter = 1

        while name.lower() in self._existing_collections:
            file_hash = hashlib.md5(filename.encode()).hexdigest()[:4]
            name = f"{base_name}_{file_hash}"
            if counter > 1:
                name = f"{name}_{counter}"
            counter += 1

            if counter > 100:
                name = f"collection_{hashlib.md5(filename.encode()).hexdigest()[:8]}"
                break

        return name

    def _flatten_dict(self, d: dict, parent_key: str = "", sep: str = ".") -> dict:
        """Flatten nested dictionaries for schema detection."""
        items: list[tuple[str, Any]] = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep).items())
            else:
                items.append((new_key, v))
        return dict(items)

    def _try_parse_date(self, value: Any) -> datetime | None:
        """Try to parse a value as a date using multiple formats.

        Returns the datetime if successful, None otherwise.
        """
        if value is None:
            return None

        if isinstance(value, datetime):
            return value

        str_val = str(value).strip()

        # Fast path: ISO format (handles 2025-09-17, 2025-09-17T00:00:00, etc.)
        try:
            return datetime.fromisoformat(str_val)
        except (ValueError, TypeError):
            pass

        # Try patterns with specific formats (FR, US, dot-separated)
        for pattern, fmt in self._DATE_PATTERNS:
            if pattern.match(str_val):
                try:
                    if "%y" in fmt.lower() and len(str_val.split("/")[-1]) == 2:
                        return datetime.strptime(str_val, fmt)
                    return datetime.strptime(str_val, fmt)
                except ValueError:
                    continue

        # Fallback: manual parsing for common formats
        try:
            if "/" in str_val and str_val.count("/") == 2:
                parts = str_val.split("/")
                day, month = int(parts[0]), int(parts[1])
                year = int(parts[2])
                if year < 100:
                    year += 2000 if year < 50 else 1900
                return datetime(year, month, day)

            if "-" in str_val and str_val.count("-") == 2 and len(str_val) == 10:
                parts = str_val.split("-")
                if len(parts[0]) == 2:  # dd-mm-yyyy
                    day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                    return datetime(year, month, day)
        except (ValueError, IndexError):
            pass

        return None

    def _compare_values(self, doc_value: Any, query_value: Any, operator: str = "$eq") -> bool:
        """Compare two values with automatic date detection.

        This method tries to parse both values as dates and compare them chronologically
        if they both look like dates. Otherwise falls back to standard comparison.
        """
        # Try to parse both as dates
        doc_date = self._try_parse_date(doc_value)
        query_date = self._try_parse_date(query_value)

        # If both are dates, compare chronologically
        if doc_date is not None and query_date is not None:
            if operator == "$eq":
                return doc_date == query_date
            elif operator == "$ne":
                return doc_date != query_date
            elif operator == "$gt":
                return doc_date > query_date
            elif operator == "$gte":
                return doc_date >= query_date
            elif operator == "$lt":
                return doc_date < query_date
            elif operator == "$lte":
                return doc_date <= query_date

        # Fallback to standard comparison
        if operator == "$eq":
            return doc_value == query_value
        elif operator == "$ne":
            return doc_value != query_value
        elif operator == "$gt":
            return doc_value > query_value
        elif operator == "$gte":
            return doc_value >= query_value
        elif operator == "$lt":
            return doc_value < query_value
        elif operator == "$lte":
            return doc_value <= query_value

        return False

    def _infer_type(self, value: Any) -> str:
        """Infer type of a value for schema."""
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int):
            return "integer"
        if isinstance(value, float):
            return "float"
        if isinstance(value, datetime):
            return "datetime"
        if isinstance(value, list):
            return "array"
        if isinstance(value, dict):
            return "object"

        # String - check if looks like date
        str_val = str(value)
        for pattern, _ in self._DATE_PATTERNS:
            if pattern.match(str_val):
                return "datetime"
        return "string"

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

        if suffix == ".json":
            return pd.read_json(BytesIO(file_bytes))

        if suffix == ".jsonl":
            return pd.read_json(BytesIO(file_bytes), lines=True)

        raise ValueError(f"Format de fichier non supporté: {suffix}")

    def ingest_dataframe(
        self,
        df: pd.DataFrame,
        name: str,
        on_step: Callable[[str, str], None] | None = None,
    ) -> str:
        """Ingest a DataFrame as documents.

        Unlike SQL, we preserve the hierarchical structure if present.
        """
        if on_step:
            on_step("convert_documents", "Conversion en documents JSON")

        # Convert DataFrame to list of documents
        documents = df.to_dict("records")

        # Generate safe collection name
        collection_name = self._safe_collection_name(name)
        collection_path = self._get_collection_path(collection_name)
        collection_path.mkdir(parents=True, exist_ok=True)

        # Write documents as individual JSON files
        if on_step:
            on_step("write_documents", f"Écriture des documents ({len(documents)} docs)")

        for i, doc in enumerate(documents):
            # Clean NaN values
            doc = self._clean_document(doc)
            doc["_id"] = f"doc_{i:08d}"
            doc["_ingested_at"] = datetime.now().isoformat()

            doc_path = collection_path / f"{doc['_id']}.json"
            with open(doc_path, "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False, indent=2, default=str)

        # Write metadata
        metadata = {
            "name": collection_name,
            "original_name": name,
            "document_count": len(documents),
            "created_at": datetime.now().isoformat(),
            "columns": list(df.columns),
        }
        with open(collection_path / "_metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        self._existing_collections.add(collection_name.lower())
        return collection_name

    def _clean_document(self, doc: dict) -> dict:
        """Clean document values (remove NaN, etc.)."""
        cleaned = {}
        for k, v in doc.items():
            if pd.isna(v):
                cleaned[k] = None
            elif isinstance(v, pd.Timestamp):
                cleaned[k] = v.isoformat()
            else:
                cleaned[k] = v
        return cleaned

    # -----------------------------------------------------------------------
    # Schema & Metadata
    # -----------------------------------------------------------------------

    def list_tables(self) -> list[str]:
        """List all collections."""
        if not self._collections_dir or not self._collections_dir.exists():
            return []

        return [d.name for d in self._collections_dir.iterdir() if d.is_dir() and not d.name.startswith("_")]

    def get_schema(self) -> SchemaInfo:
        """Get schema for all collections."""
        tables = []

        for collection_name in self.list_tables():
            table_schema = self.get_table_schema(collection_name)
            if table_schema:
                tables.append(table_schema)

        return SchemaInfo(tables=tables, relations=[])

    def get_table_schema(self, name: str) -> TableSchema | None:
        """Get schema for a collection."""
        collection_path = self._get_collection_path(name)

        if not collection_path.exists():
            return None

        # Read metadata if available
        metadata_path = collection_path / "_metadata.json"
        if metadata_path.exists():
            try:
                with open(metadata_path, encoding="utf-8") as f:
                    metadata = json.load(f)
                columns = [ColumnInfo(name=col, type="unknown") for col in metadata.get("columns", [])]
                return TableSchema(name=name, columns=columns)
            except Exception:
                pass

        # Infer schema from sample documents
        sample_docs = self._read_collection_sample(name, limit=10)
        if not sample_docs:
            return TableSchema(name=name)

        # Build field info from samples
        all_fields: dict[str, set[str]] = {}
        for doc in sample_docs:
            flat_doc = self._flatten_dict(doc)
            for field, value in flat_doc.items():
                if field not in all_fields:
                    all_fields[field] = set()
                all_fields[field].add(self._infer_type(value))

        columns = [
            ColumnInfo(name=field, type=" | ".join(sorted(types)) if types else "unknown")
            for field, types in all_fields.items()
            if not field.startswith("_")
        ]

        return TableSchema(
            name=name,
            columns=columns,
            sample_fields=all_fields,
        )

    def table_exists(self, name: str) -> bool:
        """Check if a collection exists."""
        collection_path = self._get_collection_path(name)
        return collection_path.exists() and collection_path.is_dir()

    def _read_collection_sample(self, name: str, limit: int = 100, offset: int = 0) -> list[dict]:
        """Read documents from a collection."""
        collection_path = self._get_collection_path(name)

        if not collection_path.exists():
            return []

        # Get all JSON files (excluding metadata)
        json_files = sorted(
            [f for f in collection_path.iterdir() if f.suffix == ".json" and not f.name.startswith("_")]
        )

        # Apply offset and limit
        json_files = json_files[offset : offset + limit]

        documents = []
        for doc_path in json_files:
            try:
                with open(doc_path, encoding="utf-8") as f:
                    documents.append(json.load(f))
            except Exception:
                pass

        return documents

    def _read_collection_all(self, name: str) -> list[dict]:
        """Read all documents from a collection."""
        return self._read_collection_sample(name, limit=1000000)

    # -----------------------------------------------------------------------
    # Querying
    # -----------------------------------------------------------------------

    def execute_query(self, query: str, limit: int | None = None) -> QueryResult:
        """Execute a query expression.

        For NoSQL mode, the query is a simplified expression language:
        - "collection: {name}" - select from collection
        - "filter: {field} {op} {value}" - filter documents
        - "project: {fields}" - project fields

        Or JSON format:
        {"collection": "name", "filter": {...}, "project": [...]}
        """
        max_limit = settings.sql_result_limit
        if limit is None:
            limit = max_limit
        else:
            limit = min(limit, max_limit)

        try:
            # Fix common LLM JSON syntax errors before parsing
            fixed_query = self._fix_common_json_errors(query)
            # Try to parse as JSON
            query_obj = json.loads(fixed_query)
            return self._execute_json_query(query_obj, limit)
        except json.JSONDecodeError:
            # Try to parse as simple expression
            return self._execute_expression_query(query, limit)

    def _fix_common_json_errors(self, query: str) -> str:
        """Fix common JSON syntax errors made by LLMs."""
        import re

        # Fix 1: Wrong separator between filter and aggregate: "filter":{...}},{"aggregate":
        # Should be: "filter":{...},"aggregate":
        # Pattern: }},{ followed by {"aggregate" or similar
        pattern1 = r'("filter":\s*\{[^}]+\})\s*,\s*\{\s*"aggregate"'
        replacement1 = r'\1, "aggregate"'
        query = re.sub(pattern1, replacement1, query)

        # Fix 2: Multiple root objects: }{}
        # If we see "},{", it's likely a syntax error
        if '","aggregate"' not in query and '},{"aggregate"' in query:
            query = query.replace('},{"aggregate"', ',"aggregate"')

        return query

    def _execute_json_query(self, query: dict, limit: int) -> QueryResult:
        """Execute a JSON query with optional aggregation pipeline.

        Supported top-level keys:
          collection (str)          – required
          filter     (dict)         – MongoDB-style filter
          aggregate  (dict|list)    – aggregation operations (see below)
          sort       (dict)         – {"field": 1} ascending, {"field": -1} descending
          project    (list[str])    – fields to keep
          limit      (int)          – max documents returned
          distinct   (str)          – return unique values for this field

        Aggregate formats:
          {"$count": true}
          {"$count": "field"}                  – count non-null values
          {"$sum": "field"}
          {"$avg": "field"}
          {"$min": "field"}
          {"$max": "field"}
          {"$group": {"by": "field", "agg": {"$count": true}}}
          [{"$count": true}, {"$sum": "montant"}]  – multiple aggregations
        """
        collection = query.get("collection")
        if not collection:
            return QueryResult(error="No collection specified")

        if not self.table_exists(collection):
            return QueryResult(error=f"Collection '{collection}' not found")

        documents = self._read_collection_all(collection)

        # 1. Filter
        filter_spec = query.get("filter", {})
        if filter_spec:
            documents = self._apply_filter(documents, filter_spec)

        # 2. Aggregation (returns early if present)
        aggregate_spec = query.get("aggregate")
        if aggregate_spec is not None:
            return self._apply_aggregate(documents, aggregate_spec, query)

        # 3. Distinct
        distinct_field = query.get("distinct")
        if distinct_field:
            return self._apply_distinct(documents, distinct_field, query)

        # 4. Sort
        sort_spec = query.get("sort")
        if sort_spec:
            documents = self._apply_sort(documents, sort_spec)

        # 5. Projection
        project_fields = query.get("project")
        if project_fields:
            documents = self._apply_projection(documents, project_fields)

        # 6. Limit
        query_limit = query.get("limit")
        effective_limit = min(query_limit, limit) if query_limit else limit
        total_count = len(documents)
        documents = documents[:effective_limit]

        columns = list(documents[0].keys()) if documents else []

        return QueryResult(
            rows=documents,
            columns=columns,
            total_count=total_count,
            query_text=json.dumps(query, ensure_ascii=False),
        )

    # ------------------------------------------------------------------
    # Aggregation helpers
    # ------------------------------------------------------------------

    def _eval_expr(self, doc: dict, expr: Any) -> Any:
        """Evaluate a MongoDB-style expression against a document.

        Supports: "$field", numbers, {$dateToTime: "$field"}, {$subtract: [a,b]}, {$divide: [a,b]}, {$add: [...]}.
        """
        if expr is None:
            return None
        if isinstance(expr, (int, float, bool)):
            return expr
        if isinstance(expr, str):
            key = expr.lstrip("$")
            return self._get_nested_value(doc, key)
        if isinstance(expr, list):
            return [self._eval_expr(doc, e) for e in expr]
        if isinstance(expr, dict):
            if len(expr) != 1:
                return None
            op, arg = next(iter(expr.items()))
            if op == "$dateToTime":
                field = arg if isinstance(arg, str) else str(arg)
                key = field.lstrip("$")
                raw = self._get_nested_value(doc, key)
                dt = self._try_parse_date(raw)
                if dt is not None:
                    return int(dt.timestamp() * 1000)
                return None
            if op == "$subtract":
                args = arg if isinstance(arg, list) else [arg]
                if len(args) < 2:
                    return None
                a, b = self._eval_expr(doc, args[0]), self._eval_expr(doc, args[1])
                if a is None or b is None:
                    return None
                try:
                    return float(a) - float(b)
                except (TypeError, ValueError):
                    return None
            if op == "$divide":
                args = arg if isinstance(arg, list) else [arg]
                if len(args) < 2:
                    return None
                a, b = self._eval_expr(doc, args[0]), self._eval_expr(doc, args[1])
                if a is None or b is None or b == 0:
                    return None
                try:
                    return float(a) / float(b)
                except (TypeError, ValueError):
                    return None
            if op == "$add":
                args = arg if isinstance(arg, list) else [arg]
                vals = [self._eval_expr(doc, e) for e in args]
                if any(v is None for v in vals):
                    return None
                try:
                    return sum(float(v) for v in vals)
                except (TypeError, ValueError):
                    return None
            if op == "$multiply":
                args = arg if isinstance(arg, list) else [arg]
                vals = [self._eval_expr(doc, e) for e in args]
                if any(v is None for v in vals):
                    return None
                try:
                    acc = 1.0
                    for v in vals:
                        acc *= float(v)
                    return acc
                except (TypeError, ValueError):
                    return None
            # Date extractors: $year, $month, $day, etc.
            if op in self._DATE_EXTRACTORS:
                field = arg if isinstance(arg, str) else str(arg)
                key = field.lstrip("$")
                raw = self._get_nested_value(doc, key)
                dt = self._try_parse_date(raw)
                if dt is not None:
                    extractor = self._DATE_EXTRACTORS[op]
                    return extractor(dt)
                return None
        return None

    def _apply_project(self, documents: list[dict], project_spec: dict) -> list[dict]:
        """Apply $project: add computed fields to each document. Expressions can reference previously defined fields in the same spec."""
        result: list[dict] = []
        for doc in documents:
            ctx = dict(doc)
            for key, expr in project_spec.items():
                if key.startswith("$"):
                    continue
                ctx[key] = self._eval_expr(ctx, expr)
            result.append(ctx)
        return result

    def _apply_aggregate(
        self,
        documents: list[dict],
        spec: Any,
        raw_query: dict,
    ) -> QueryResult:
        """Run one or more aggregation operations on *documents*.

        Handles:
          - Pipeline list: [$project, $group, ...] — run in order (project adds computed fields, then group).
          - Single dict with $group or simple agg.
        """

        # Normalise to a list of operations
        if isinstance(spec, dict):
            ops: list[dict] = [spec]
        elif isinstance(spec, list):
            ops = spec
        else:
            return QueryResult(error=f"Invalid aggregate spec: {spec}")

        # Extract post-processing ($sort, $limit)
        post_sort: dict | None = None
        post_limit: int | None = None
        for op in ops:
            if "$sort" in op:
                post_sort = op["$sort"]
            if "$limit" in op:
                post_limit = int(op["$limit"])
        if post_sort is None:
            post_sort = raw_query.get("sort")
        if post_limit is None and "limit" in raw_query:
            post_limit = int(raw_query["limit"])

        # Run pipeline: $project stages first, then $group
        current_docs = documents
        for op in ops:
            if "$project" in op:
                current_docs = self._apply_project(current_docs, op["$project"])

        # Find and run $group on the current document set
        for op in ops:
            if "$group" in op:
                result = self._apply_group(current_docs, op["$group"], ops, raw_query)
                return self._post_process_result(result, post_sort, post_limit, raw_query)

        # No $group: simple aggregations on current_docs
        result_row: dict[str, Any] = {}
        for op in ops:
            for agg_op, agg_field in op.items():
                if agg_op in ("$sort", "$limit", "$project"):
                    continue
                label, value = self._compute_agg(current_docs, agg_op, agg_field)
                result_row[label] = value

        return QueryResult(
            rows=[result_row],
            columns=list(result_row.keys()),
            total_count=1,
            query_text=json.dumps(raw_query, ensure_ascii=False),
        )

    def _post_process_result(
        self,
        result: QueryResult,
        sort_spec: dict | None,
        limit: int | None,
        raw_query: dict,
    ) -> QueryResult:
        """Apply sort, limit and projection to an aggregation result."""
        rows = result.rows

        if sort_spec:
            rows = self._apply_sort(rows, sort_spec)

        project_fields = raw_query.get("project")
        if project_fields:
            rows = self._apply_projection(rows, project_fields)

        if limit and len(rows) > limit:
            rows = rows[:limit]

        columns = list(rows[0].keys()) if rows else result.columns
        return QueryResult(
            rows=rows,
            columns=columns,
            total_count=len(rows),
            query_text=result.query_text,
        )

    def _compute_agg(
        self,
        docs: list[dict],
        op: str,
        field: Any,
    ) -> tuple[str, Any]:
        """Compute a single aggregation and return (label, value).

        Handles MongoDB conventions:
          - {"$sum": 1}  → count (MongoDB accumulator shorthand)
          - {"$count": 1} → count
          - {"$sum": "field"} → sum of numeric field
        """

        # Treat numeric 1 / True as "count all" for any operator
        if field == 1 or field is True:
            if op in ("$sum", "$count"):
                return ("count", len(docs))

        if op == "$count":
            if field is True or field == "*" or field == 1:
                return ("count", len(docs))
            field = str(field).lstrip("$")
            values = [self._get_nested_value(d, field) for d in docs if self._get_nested_value(d, field) is not None]
            return (f"count_{field}", len(values))

        if op in ("$sum", "$avg", "$min", "$max"):
            field = str(field).lstrip("$")
            values = self._extract_numeric(docs, field)
            if not values:
                return (f"{op[1:]}_{field}", 0)
            if op == "$sum":
                return (f"sum_{field}", round(sum(values), 2))
            if op == "$avg":
                return (f"avg_{field}", round(sum(values) / len(values), 2))
            if op == "$min":
                return (f"min_{field}", min(values))
            if op == "$max":
                return (f"max_{field}", max(values))

        return (op, None)

    # Supported date-part extraction operators (MongoDB style)
    _DATE_EXTRACTORS: dict[str, Callable[[datetime], int]] = {
        "$year": lambda dt: dt.year,
        "$month": lambda dt: dt.month,
        "$dayOfMonth": lambda dt: dt.day,
        "$day": lambda dt: dt.day,
        "$hour": lambda dt: dt.hour,
        "$minute": lambda dt: dt.minute,
        "$week": lambda dt: dt.isocalendar()[1],
        "$quarter": lambda dt: (dt.month - 1) // 3 + 1,
    }

    def _resolve_group_value(self, doc: dict, by_item: Any) -> tuple[str, Any]:
        """Resolve a single group-by specification to (label, value).

        Handles:
          - "field_name" → direct field lookup
          - "$field_name" → field reference (MongoDB style)
          - {"$year": "$CDE_DATE_COMMANDE"} → date-part extraction from string date
          - {"$year": "$timestamp_field"} → date-part extraction from timestamp (ms)
        """
        if isinstance(by_item, str):
            # Handle MongoDB-style field reference like "$_id"
            field_name = by_item.lstrip("$")
            return (field_name, self._get_nested_value(doc, field_name))

        if isinstance(by_item, dict):
            for op, field_ref in by_item.items():
                extractor = self._DATE_EXTRACTORS.get(op)
                if extractor is None:
                    continue
                field_name = str(field_ref).lstrip("$")
                raw_value = self._get_nested_value(doc, field_name)

                # Try to parse as date string first
                parsed = self._try_parse_date(raw_value)
                if parsed is not None:
                    label = f"{op[1:]}_{field_name}"
                    return (label, extractor(parsed))

                # Try to interpret as timestamp (milliseconds since epoch)
                if isinstance(raw_value, (int, float)):
                    try:
                        # Assume milliseconds (from $dateToTime)
                        dt = datetime.fromtimestamp(raw_value / 1000.0)
                        label = f"{op[1:]}_{field_name}"
                        return (label, extractor(dt))
                    except (ValueError, OSError, OverflowError):
                        pass

                return (f"{op[1:]}_{field_name}", None)

        return (str(by_item), None)

    def _apply_group(
        self,
        documents: list[dict],
        group_spec: dict,
        all_ops: list[dict],
        raw_query: dict,
    ) -> QueryResult:
        """Group documents by one or more fields, then aggregate.

        Supports MongoDB-style syntax: {"_id": "$field", "agg_name": {"$avg": "$field"}}
        or simplified: {"by": "$field", "agg": {"$avg": "$field"}}

        Special case: _id = null or missing → global aggregation (single result).
        """
        # Check for MongoDB-style _id syntax
        by = group_spec.get("by")
        agg_spec = group_spec.get("agg", group_spec.get("aggregate", {}))

        # Handle MongoDB standard syntax with _id (or id as alias)
        group_key = None
        if "_id" in group_spec:
            group_key = "_id"
        elif "id" in group_spec:
            group_key = "id"  # Common LLM mistake

        if group_key:
            by = group_spec[group_key]
            # If _id is null/None, this means global aggregation (no grouping)
            if by is None:
                by = []  # Empty list = no grouping
            # Extract aggregations from other fields
            agg_fields = {k: v for k, v in group_spec.items() if k != group_key}
            if agg_fields:
                agg_spec = agg_fields

        # Global aggregation when by is empty/null
        if by is None or by == []:
            # Compute aggregations on all documents
            result_row: dict[str, Any] = {}
            if isinstance(agg_spec, dict):
                for agg_name, agg_def in agg_spec.items():
                    if isinstance(agg_def, dict):
                        # agg_def is like {"$avg": "$field"}
                        for agg_op, agg_field in agg_def.items():
                            label, value = self._compute_agg(documents, agg_op, agg_field)
                            # Use the provided name if it's not a generic label
                            if label.startswith(("avg_", "sum_", "min_", "max_", "count_")):
                                result_row[agg_name] = value
                            else:
                                result_row[label] = value
                    else:
                        # Direct value like {"count": {"$sum": 1}}
                        label, value = self._compute_agg(documents, agg_name, agg_def)
                        result_row[agg_name] = value

            return QueryResult(
                rows=[result_row],
                columns=list(result_row.keys()),
                total_count=1,
                query_text=json.dumps(raw_query, ensure_ascii=False),
            )

        # Normalise `by` to a list (can contain strings or dicts like {"$year": "$field"})
        if not isinstance(by, list):
            by = [by]

        # Normalise agg_spec to list
        agg_ops: list[dict] = [agg_spec] if isinstance(agg_spec, dict) else list(agg_spec)

        # Build groups
        groups: dict[tuple, list[dict]] = {}
        label_names: list[str] = []
        for doc in documents:
            resolved = [self._resolve_group_value(doc, b) for b in by]
            if not label_names:
                label_names = [r[0] for r in resolved]
            key = tuple(r[1] for r in resolved)
            groups.setdefault(key, []).append(doc)

        rows: list[dict] = []
        for key_values, group_docs in groups.items():
            row: dict[str, Any] = {lbl: v for lbl, v in zip(label_names, key_values, strict=False)}
            for op_dict in agg_ops:
                for key, val in op_dict.items():
                    if key in ("$group", "$sort", "$limit"):
                        continue
                    # Handle MongoDB-style: {"agg_name": {"$avg": "$field"}}
                    if isinstance(val, dict) and any(k.startswith("$") for k in val.keys()):
                        agg_name = key  # e.g., "avg_ecart_ms"
                        for agg_op, agg_field in val.items():
                            label, value = self._compute_agg(group_docs, agg_op, agg_field)
                            # Use the custom name if provided
                            if label.startswith(("avg_", "sum_", "min_", "max_", "count_")):
                                row[agg_name] = value
                            else:
                                row[label] = value
                    else:
                        # Simplified style: {"$avg": "$field"}
                        label, value = self._compute_agg(group_docs, key, val)
                        row[label] = value
            rows.append(row)

        # Special case: grouping by _id with single aggregation = compute global aggregate
        if label_names == ["_id"] and len(rows) > 1 and len(rows[0]) == 2:
            # Check if we have only one aggregation column
            agg_col = [k for k in rows[0].keys() if k != "_id"]
            if len(agg_col) == 1:
                agg_name = agg_col[0]
                all_values = [r[agg_name] for r in rows if r[agg_name] is not None]
                if all_values:
                    if agg_name.startswith("avg_"):
                        global_avg = sum(all_values) / len(all_values)
                        rows = [{agg_name: round(global_avg, 2)}]
                    elif agg_name.startswith("sum_"):
                        global_sum = sum(all_values)
                        rows = [{agg_name: round(global_sum, 2)}]
                    elif agg_name.startswith(("min_", "max_")):
                        if "min_" in agg_name:
                            rows = [{agg_name: min(all_values)}]
                        else:
                            rows = [{agg_name: max(all_values)}]

        # Default sort: by group key ascending (e.g. year ascending)
        agg_keys = [k for k in rows[0].keys() if k not in label_names] if rows else []
        if label_names:
            rows.sort(key=lambda r: (r.get(label_names[0]) is None, r.get(label_names[0], "")))

        columns = list(rows[0].keys()) if rows else label_names
        return QueryResult(
            rows=rows,
            columns=columns,
            total_count=len(rows),
            query_text=json.dumps(raw_query, ensure_ascii=False),
        )

    def _extract_numeric(self, docs: list[dict], field: str) -> list[float]:
        """Extract numeric values for a field, coercing when possible."""
        values: list[float] = []
        for doc in docs:
            v = self._get_nested_value(doc, field)
            if v is None:
                continue
            if isinstance(v, (int, float)):
                values.append(float(v))
                continue
            try:
                cleaned = str(v).replace(" ", "").replace(",", ".").replace("\u00a0", "")
                values.append(float(cleaned))
            except (ValueError, TypeError):
                continue
        return values

    def _apply_distinct(
        self,
        documents: list[dict],
        field: str,
        raw_query: dict,
    ) -> QueryResult:
        """Return unique values for a field."""
        seen: set = set()
        rows: list[dict] = []
        for doc in documents:
            v = self._get_nested_value(doc, field)
            key = str(v)
            if key not in seen:
                seen.add(key)
                rows.append({field: v})
        rows.sort(key=lambda r: str(r.get(field, "")))
        return QueryResult(
            rows=rows,
            columns=[field],
            total_count=len(rows),
            query_text=json.dumps(raw_query, ensure_ascii=False),
        )

    def _apply_sort(self, documents: list[dict], sort_spec: dict) -> list[dict]:
        """Sort documents.  sort_spec: {"field": 1} or {"field": -1}.

        Also accepts virtual keys like "_id" which maps to the first
        aggregation column (MongoDB convention).
        """
        if not documents:
            return documents

        doc_keys = list(documents[0].keys())

        for field, direction in reversed(list(sort_spec.items())):
            reverse = direction == -1 or direction == "-1" or direction == -1.0

            # MongoDB's "_id" after $group → sort by first agg column
            actual_field = field
            if field == "_id" and field not in documents[0]:
                agg_cols = [k for k in doc_keys if k.startswith(("count", "sum_", "avg_", "min_", "max_"))]
                if agg_cols:
                    actual_field = agg_cols[0]
                elif doc_keys:
                    actual_field = doc_keys[0]

            def _sort_key(d: dict, f: str = actual_field) -> tuple:
                v = self._get_nested_value(d, f) if "." in f else d.get(f)
                return (v is None, v if v is not None else "")

            documents = sorted(documents, key=_sort_key, reverse=reverse)
        return documents

    def _execute_expression_query(self, query: str, limit: int) -> QueryResult:
        """Execute a simple expression query."""
        # Simple parser for: "from {collection} where {condition}"
        # This is a basic implementation - can be extended

        lines = query.strip().split("\n")
        collection = None
        filters = {}

        for line in lines:
            line = line.strip()
            if line.lower().startswith("collection:"):
                collection = line.split(":", 1)[1].strip()
            elif line.lower().startswith("from "):
                collection = line[5:].strip()

        if not collection:
            return QueryResult(error="No collection specified")

        if not self.table_exists(collection):
            return QueryResult(error=f"Collection '{collection}' not found")

        documents = self._read_collection_sample(collection, limit=limit)

        columns = list(documents[0].keys()) if documents else []

        return QueryResult(
            rows=documents,
            columns=columns,
            total_count=len(documents),
            query_text=query,
        )

    def _apply_filter(self, documents: list[dict], filter_spec: dict) -> list[dict]:
        """Apply filter to documents with automatic date handling."""
        result = documents

        for field, condition in filter_spec.items():
            if isinstance(condition, dict):
                # Complex condition: {"$gt": 10, "$lt": 100}
                for op, value in condition.items():
                    result = self._apply_operator(result, field, op, value)
            else:
                # Simple equality: {"field": "value"}
                # Use smart comparison to handle dates
                result = [d for d in result if self._compare_values(self._get_nested_value(d, field), condition, "$eq")]

        return result

    def _apply_operator(self, documents: list[dict], field: str, op: str, value: Any) -> list[dict]:
        """Apply a comparison operator with automatic date handling."""
        # Use smart comparison for comparison operators
        if op in ("$eq", "$ne", "$gt", "$gte", "$lt", "$lte"):
            return [d for d in documents if self._compare_values(self._get_nested_value(d, field), value, op)]
        elif op == "$in":
            # For $in, check if any value in the list matches
            return [
                d
                for d in documents
                if any(self._compare_values(self._get_nested_value(d, field), v, "$eq") for v in value)
            ]
        elif op == "$exists":
            return [d for d in documents if (self._get_nested_value(d, field) is not None) == value]
        elif op == "$regex":
            # Regex matching
            try:
                pattern = re.compile(value)
                return [d for d in documents if pattern.search(str(self._get_nested_value(d, field) or ""))]
            except re.error:
                return documents
        elif op == "$ilike":
            # Case-insensitive pattern matching (SQL ILIKE behavior)
            # Convert value to pattern: %text% → .*text.*
            pattern_str = str(value).lower()
            # Escape regex special chars except % and _
            for char in [".", "^", "$", "+", "{", "}", "[", "]", "|", "\\"]:
                pattern_str = pattern_str.replace(char, "\\" + char)
            # Convert SQL wildcards to regex
            pattern_str = pattern_str.replace("%", ".*").replace("_", ".")
            pattern_str = f"^{pattern_str}$"
            try:
                pattern = re.compile(pattern_str, re.IGNORECASE)
                return [d for d in documents if pattern.match(str(self._get_nested_value(d, field) or ""))]
            except re.error:
                return documents
        return documents

    def _get_nested_value(self, doc: dict, path: str) -> Any:
        """Get a value from a document using dot notation."""
        parts = path.split(".")
        current = doc

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None

        return current

    def _apply_projection(self, documents: list[dict], fields: list[str]) -> list[dict]:
        """Project only specified fields."""
        result = []
        for doc in documents:
            projected = {}
            for field in fields:
                projected[field] = self._get_nested_value(doc, field)
            result.append(projected)
        return result

    def preview_table(self, name: str, limit: int = 50, offset: int = 0) -> QueryResult:
        """Get a preview of a collection."""
        if not self.table_exists(name):
            return QueryResult(error=f"Collection '{name}' not found")

        documents = self._read_collection_sample(name, limit=limit, offset=offset)

        # Get total count
        collection_path = self._get_collection_path(name)
        json_files = [f for f in collection_path.iterdir() if f.suffix == ".json" and not f.name.startswith("_")]
        total_count = len(json_files)

        columns = list(documents[0].keys()) if documents else []

        return QueryResult(
            rows=documents,
            columns=columns,
            total_count=total_count,
            query_text=f"preview collection: {name}",
        )

    # -----------------------------------------------------------------------
    # NL-to-Query specific
    # -----------------------------------------------------------------------

    def validate_query(self, query: str) -> tuple[bool, str]:
        """Validate a query for safety."""
        if not query or not query.strip():
            return False, "Requête vide."

        try:
            # Try to parse as JSON
            json.loads(query)
            return True, ""
        except json.JSONDecodeError:
            # Simple expression - check for suspicious patterns
            forbidden = ["__import__", "eval", "exec", "os.", "sys."]
            for pattern in forbidden:
                if pattern in query:
                    return False, f"Pattern interdit détecté: {pattern}"
            return True, ""

    def get_system_prompt(self) -> str:
        """Get query prompt for NoSQL document database."""
        return (
            "Tu es un assistant pour base de données document (NoSQL). Règles STRICTES:\n"
            "1. Les données sont stockées comme des documents JSON (style MongoDB).\n"
            "2. Chaque 'table' est en fait une collection de documents.\n"
            "3. Les documents peuvent avoir des champs imbriqués (ex: client.adresse.ville).\n"
            "4. PAS de JOINs - les données liées sont imbriquées dans les documents.\n"
            "5. Retourne UNIQUEMENT un objet JSON de requête, rien d'autre.\n\n"
            "FORMAT DE REQUÊTE JSON:\n"
            "{\n"
            '  "collection": "nom_collection",\n'
            '  "filter":    {...},           // optionnel – filtre les documents\n'
            '  "aggregate": {...} ou [...],  // optionnel – agrégation (count, sum, avg…)\n'
            '  "sort":      {"champ": 1},    // optionnel – 1=asc, -1=desc\n'
            '  "project":   ["champ1"],      // optionnel – champs à garder\n'
            '  "distinct":  "champ",         // optionnel – valeurs uniques\n'
            '  "limit":     10               // optionnel – nombre max de docs\n'
            "}\n\n"
            "OPÉRATEURS DE FILTRE:\n"
            "  $eq, $ne, $gt, $gte, $lt, $lte, $in, $exists, $regex\n\n"
            "DATES (détection automatique des formats ISO/FR/US):\n"
            '  Année:   {"champ_date": {"$gte": "2023-01-01", "$lte": "2023-12-31"}}\n'
            '  Période: {"champ_date": {"$gte": "date_debut", "$lte": "date_fin"}}\n\n'
            'AGRÉGATION (clé "aggregate"):\n'
            '  Compter:      {"$count": true}               → {"count": N}\n'
            '  Compter non-null: {"$count": "champ"}        → {"count_champ": N}\n'
            '  Somme:        {"$sum": "champ_numerique"}     → {"sum_champ": X}\n'
            '  Moyenne:      {"$avg": "champ_numerique"}     → {"avg_champ": X}\n'
            '  Min/Max:      {"$min": "champ"}, {"$max": "champ"}\n'
            "\n"
            "CALCUL D'ÉCART ENTRE DATES (pipeline avancé):\n"
            "  Ex: écart moyen entre date_commande et date_livraison:\n"
            "  {\n"
            '    "collection": "commandes",\n'
            '    "aggregate": [\n'
            '      {"$project": {\n'
            '         "ecart_jours": {\n'
            '           "$divide": [\n'
            '             {"$subtract": [{"$dateToTime": "$date_livraison"}, {"$dateToTime": "$date_commande"}]},\n'
            "             86400000\n"
            "           ]\n"
            "         }\n"
            "      }},\n"
            '      {"$group": {"_id": null, "avg_ecart_jours": {"$avg": "$ecart_jours"}}}\n'
            "    ]\n"
            "  }\n"
            '  IMPORTANT: "_id": null pour agrégation globale\n'
            "  $dateToTime convertit en timestamp (ms), $subtract soustrait, $divide divise\n"
            "  86400000 = ms par jour (1000 * 60 * 60 * 24)\n"
            '  Plusieurs:    [{"$count": true}, {"$sum": "montant"}]\n\n'
            "PIPELINE (aggregate comme liste):\n"
            "  Pour calculer des champs dérivés puis grouper, utilise une liste de stages.\n"
            "  $project ajoute des champs calculés (dates en ms, différences, etc.) puis $group les utilise.\n"
            "  Opérateurs dans $project: $dateToTime (champ date → ms), $subtract [a,b], $divide [a,b], $add, $multiply.\n"
            "  Exemple écart moyen en jours entre 2 dates par année:\n"
            '  "aggregate": [{"$project": {"d1": {"$dateToTime": "$date1"}, "d2": {"$dateToTime": "$date2"}, "ecart_jours": {"$divide": [{"$subtract": ["$d2","$d1"]}, 86400000]}}}, {"$group": {"by": {"$year": "$date1"}, "agg": [{"$avg": "$ecart_jours"}]}}]\n\n'
            "GROUPEMENT (dans aggregate):\n"
            '  {"$group": {"by": "champ", "agg": {"$count": true}}}\n'
            '  {"$group": {"by": ["champ1","champ2"], "agg": [{"$count": true}, {"$sum": "montant"}]}}\n\n'
            "EXTRACTION DE DATE (dans $group.by):\n"
            "  Quand tu dois grouper par année, mois, jour, etc., utilise un opérateur de date:\n"
            "  $year, $month, $day, $hour, $quarter, $week\n"
            '  Syntaxe: {"$year": "$champ_date"} (préfixe $ devant le nom du champ)\n'
            "  Exemples:\n"
            '    Par année:    {"$group": {"by": {"$year": "$date_commande"}, "agg": {"$count": true}}}\n'
            '    Par mois:     {"$group": {"by": {"$month": "$date_commande"}, "agg": {"$sum": "montant"}}}\n'
            '    Par trimestre:{"$group": {"by": {"$quarter": "$date_commande"}, "agg": {"$count": true}}}\n'
            '    Multi-clés:   {"$group": {"by": [{"$year": "$date"}, "$statut"], "agg": {"$count": true}}}\n\n'
            "EXEMPLES:\n"
            "Q: nombre de commandes en 2023\n"
            'R: {"collection":"commandes","filter":{"date":{"$gte":"2023-01-01","$lte":"2023-12-31"}},"aggregate":{"$count":true}}\n\n'
            "Q: nombre de commandes par année\n"
            'R: {"collection":"commandes","aggregate":{"$group":{"by":{"$year":"$date"},"agg":{"$count":true}}}}\n\n'
            "Q: chiffre d'affaires par mois en 2024\n"
            'R: {"collection":"ventes","filter":{"date":{"$gte":"2024-01-01","$lte":"2024-12-31"}},"aggregate":{"$group":{"by":{"$month":"$date"},"agg":{"$sum":"montant"}}}}\n\n'
            "Q: montant total des ventes par client\n"
            'R: {"collection":"ventes","aggregate":{"$group":{"by":"client","agg":{"$sum":"montant"}}}}\n\n'
            "Q: top 5 produits les plus chers\n"
            'R: {"collection":"produits","sort":{"prix":-1},"limit":5}\n\n'
            "Q: clients de Paris avec âge > 30\n"
            'R: {"collection":"clients","filter":{"ville":"Paris","age":{"$gt":30}}}\n\n'
            "Q: nombre de commandes par statut en 2024\n"
            'R: {"collection":"commandes","filter":{"date":{"$gte":"2024-01-01","$lte":"2024-12-31"}},"aggregate":{"$group":{"by":"statut","agg":{"$count":true}}}}\n\n'
            "Q: chiffre d'affaires moyen par mois\n"
            'R: {"collection":"ventes","aggregate":{"$group":{"by":{"$month":"$date"},"agg":{"$avg":"montant"}}}}\n\n'
            "Q: liste des catégories distinctes\n"
            'R: {"collection":"produits","distinct":"categorie"}\n\n'
            "RÈGLE IMPORTANTE: quand la question demande un NOMBRE, un TOTAL, une MOYENNE,\n"
            'un MINIMUM ou un MAXIMUM, tu DOIS utiliser "aggregate". Ne retourne JAMAIS\n'
            "tous les documents bruts quand une agrégation répond à la question."
        )

    def get_query_context(self, question: str, relevant_items: list[str]) -> str:
        """Build query context for NL-to-Query."""
        schema_info = self.get_schema()

        context_lines: list[str] = []

        for table in schema_info.tables[:5]:
            date_fields = [c.name for c in table.columns if c.type == "datetime"]
            numeric_fields = [c.name for c in table.columns if c.type in ("integer", "float")]
            other_fields = [
                f"{c.name} ({c.type})" for c in table.columns[:20] if c.type not in ("datetime", "integer", "float")
            ]

            parts: list[str] = other_fields.copy()
            if numeric_fields:
                parts.append(f"NUMÉRIQUES (agrégables $sum/$avg/$min/$max): {', '.join(numeric_fields)}")
            if date_fields:
                parts.append(f"DATES (filtrables $gte/$lte): {', '.join(date_fields)}")

            context_lines.append(f"Collection {table.name} champs: {', '.join(parts)}")

        if relevant_items:
            context_lines.extend(["\nInformations pertinentes:"] + relevant_items)

        context_lines.append(
            "\nRappels:\n"
            '- Pour compter: "aggregate": {"$count": true}\n'
            '- Pour sommer/moyenner un champ numérique: {"$sum": "champ"}, {"$avg": "champ"}\n'
            '- Pour grouper: {"$group": {"by": "champ", "agg": {"$count": true}}}\n'
            '- Grouper par partie de date: {"$group": {"by": {"$year": "$champ_date"}, "agg": ...}}\n'
            "  Opérateurs: $year, $month, $day, $quarter, $week, $hour\n"
            '- Écart entre 2 dates (en jours): utiliser "aggregate" en liste avec $project (dateToTime, subtract, divide par 86400000) puis $group avec $avg\n'
            '- Dates: {"$gte": "2023-01-01", "$lte": "2023-12-31"}\n'
            "- Champs imbriqués: client.nom"
        )

        return "\n".join(context_lines)

    # -----------------------------------------------------------------------
    # Relations (NoSQL doesn't support relations the same way)
    # -----------------------------------------------------------------------

    def supports_relations(self) -> bool:
        """NoSQL mode doesn't use traditional relations."""
        return False

    # -----------------------------------------------------------------------
    # Stats & Sampling
    # -----------------------------------------------------------------------

    def get_table_stats(self, name: str) -> dict[str, Any]:
        """Get statistics about a collection."""
        collection_path = self._get_collection_path(name)

        if not collection_path.exists():
            return {"error": f"Collection '{name}' not found"}

        # Count documents
        json_files = [f for f in collection_path.iterdir() if f.suffix == ".json" and not f.name.startswith("_")]
        doc_count = len(json_files)

        # Read metadata
        metadata_path = collection_path / "_metadata.json"
        metadata = {}
        if metadata_path.exists():
            try:
                with open(metadata_path, encoding="utf-8") as f:
                    metadata = json.load(f)
            except Exception:
                pass

        return {
            "document_count": doc_count,
            "metadata": metadata,
        }

    def get_sample_data(self, name: str, limit: int = 100) -> list[dict]:
        """Get sample documents from a collection."""
        return self._read_collection_sample(name, limit=limit)
