from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import Callable, Iterable
from io import BytesIO
from pathlib import Path

import duckdb
import pandas as pd

from ndi_api.constants import (
    deduplicate_columns as _deduplicate_columns,
)
from ndi_api.constants import (
    normalize_column_name,
)
from ndi_api.services.file_reader import (
    detect_encoding as _detect_encoding,
)
from ndi_api.services.file_reader import (
    list_excel_sheets,
)
from ndi_api.services.file_reader import (  # noqa: F401 — re-exported
    read_dataframe as _read_dataframe,
)
from ndi_api.settings import settings

logger = logging.getLogger("ndi.ingestion")
from ndi_api.services.cache import invalidate_schema_cache, schema_cache
from ndi_api.services.metadata import batch_update_schema_map
from ndi_api.services.monitoring import log_ingestion_time

# ---------------------------------------------------------------------------
# Date column detection (pre-compiled regexes)
# ---------------------------------------------------------------------------
_DATE_NAME_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p)
    for p in (
        r"^date$",
        r"^dt$",
        r"_date$",
        r"_dt$",
        r"^created_",
        r"^updated_",
        r"^modified_",
        r"^timestamp_",
        r"^(year|month|day)$",
        r"^(annee|mois|jour)$",
        r"_at$",
        r"_on$",
        r"^date_",
        r"_date",
        r"^(livraison|echeance|debut|fin|naissance|embauche|depart|signature)",
        r"(livraison|echeance|debut|fin|naissance|embauche|depart|signature)$",
    )
]

_DATE_VALUE_RE = re.compile(r"^\d{1,4}[/\-\.]\d{1,2}[/\-\.]\d{1,4}$" r"|^\d{4}-\d{2}-\d{2}T")

_NUMERIC_CANDIDATE_THRESHOLD = 0.8
_DATE_VALID_THRESHOLD = 0.8


# ---------------------------------------------------------------------------
# Date detection (hybrid: name + value sampling)
# ---------------------------------------------------------------------------


def is_date_column(col_name: str) -> bool:
    """Check if column name suggests it contains date data."""
    col_lower = col_name.lower()
    return any(p.search(col_lower) for p in _DATE_NAME_PATTERNS)


def _looks_like_date_values(series: pd.Series, sample_size: int = 20) -> bool:
    """Peek at actual values to detect date-like strings."""
    sample = series.dropna().head(sample_size).astype(str)
    if len(sample) == 0:
        return False
    matches = sample.str.match(_DATE_VALUE_RE).sum()
    return (matches / len(sample)) >= 0.6


def _try_parse_dates(col_series: pd.Series) -> pd.Series | None:
    """Attempt to parse a column as datetime64.  Returns None on failure."""
    sample = col_series.dropna().head(20).astype(str)
    if len(sample) == 0:
        return None

    is_iso = sample.str.match(r"^\d{4}-\d{2}-\d{2}").any()
    has_tz = sample.str.match(r"^\d{4}-\d{2}-\d{2}T").any()

    if has_tz:
        parsed = pd.to_datetime(col_series, errors="coerce", utc=True)
    else:
        parsed = pd.to_datetime(col_series, errors="coerce", dayfirst=not is_iso)

    valid_ratio = parsed.notna().sum() / max(len(parsed), 1)
    if valid_ratio >= _DATE_VALID_THRESHOLD:
        return parsed
    return None


# ---------------------------------------------------------------------------
# Core normalisation pipeline
# ---------------------------------------------------------------------------


def normalize_dataframe(
    df: pd.DataFrame,
    on_step: Callable[[str, str], None] | None = None,
    context: str = "",
) -> pd.DataFrame:
    df = df.copy()

    # --- 1. Column names --------------------------------------------------
    if on_step:
        on_step("normalize_columns", f"{context} Normalisation des noms de colonnes")
    raw_names = [normalize_column_name(str(c)) for c in df.columns]
    df.columns = _deduplicate_columns(raw_names)

    # --- 2. Numeric conversion (skip long-text columns) -------------------
    if on_step:
        on_step("normalize_values", f"{context} Normalisation des valeurs numériques")

    for col in df.columns:
        if not pd.api.types.is_object_dtype(df[col]):
            continue
        non_null = df[col].dropna()
        if len(non_null) == 0:
            continue
        avg_len = non_null.astype(str).str.len().mean()
        if avg_len > 30:
            continue

        series = df[col].astype("string")
        series = series.str.replace("\u00a0", "", regex=False)
        series = series.str.replace(" ", "", regex=False)
        series = series.str.replace(",", ".", regex=False)

        numeric = pd.to_numeric(series, errors="coerce")
        new_na = numeric.isna().sum()
        old_na = df[col].isna().sum()
        total = len(df[col])
        converted_ratio = (total - new_na) / max(total - old_na, 1)
        if converted_ratio >= _NUMERIC_CANDIDATE_THRESHOLD:
            df[col] = numeric

    # --- 3. Date conversion (hybrid: name + value detection) --------------
    if on_step:
        on_step("normalize_dates", f"{context} Conversion des colonnes date")

    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            continue
        if not (is_date_column(col) or _looks_like_date_values(df[col])):
            continue
        try:
            parsed = _try_parse_dates(df[col])
            if parsed is not None:
                df[col] = parsed
        except Exception:
            pass

    return df


def _get_existing_tables() -> set[str]:
    """Get set of existing table names in DuckDB."""
    db_path = get_duckdb_path()
    if not Path(db_path).exists():
        return set()

    try:
        with duckdb.connect(db_path) as con:
            tables = con.execute("SHOW TABLES").fetchall()
            return {t[0].lower() for t in tables}
    except Exception:
        return set()


def _safe_table_name(filename: str, existing_tables: set[str] | None = None) -> str:
    """Generate unique table name from filename, handling collisions."""
    stem = Path(filename).stem
    base_name = normalize_column_name(stem) or "table"

    if existing_tables is None:
        existing_tables = _get_existing_tables()

    # Check for collision (case-insensitive)
    name = base_name
    counter = 1
    original_name = name

    while name.lower() in existing_tables:
        # Add short hash of filename for uniqueness
        file_hash = hashlib.md5(filename.encode()).hexdigest()[:4]
        name = f"{base_name}_{file_hash}"
        if counter > 1:
            name = f"{name}_{counter}"
        counter += 1

        # Safety limit
        if counter > 100:
            name = f"table_{hashlib.md5(filename.encode()).hexdigest()[:8]}"
            break

    return name


def _detect_encoding(file_bytes: bytes) -> str:
    """Detect file encoding using chardet if available, fallback to utf-8."""
    try:
        import chardet

        result = chardet.detect(file_bytes[:10000])  # Sample first 10KB
        encoding = result.get("encoding", "utf-8")
        confidence = result.get("confidence", 0)
        if encoding and confidence > 0.5:
            logger.debug(f"Detected encoding: {encoding} (confidence: {confidence:.2f})")
            return encoding
    except ImportError:
        logger.debug("chardet not installed, using utf-8 fallback")
    except Exception as e:
        logger.warning(f"Encoding detection failed: {e}, using utf-8 fallback")
    return "utf-8"


def _read_dataframe(
    file_bytes: bytes, filename: str, sheet_name: str | int | list | None = None
) -> pd.DataFrame | dict[str, pd.DataFrame]:
    """Read dataframe from file with encoding detection for CSV.

    Args:
        file_bytes: Raw file content
        filename: Original filename
        sheet_name: For Excel files: sheet name, index, list of sheets, or None for first sheet
                   If "all", returns a dict of all sheets

    Returns:
        DataFrame or dict of DataFrames if sheet_name="all" or multiple sheets
    """
    suffix = Path(filename).suffix.lower()

    if suffix == ".csv":
        bio = BytesIO(file_bytes)
        encoding = _detect_encoding(file_bytes)

        try:
            if len(file_bytes) > 50 * 1024 * 1024:
                chunks = pd.read_csv(bio, chunksize=10_000, low_memory=False, encoding=encoding)
                return pd.concat(chunks, ignore_index=True)
            return pd.read_csv(bio, low_memory=False, encoding=encoding)
        except UnicodeDecodeError:
            # Fallback to latin-1 if detection failed
            bio.seek(0)
            logger.warning(f"Failed to read {filename} with {encoding}, trying latin-1")
            if len(file_bytes) > 50 * 1024 * 1024:
                chunks = pd.read_csv(bio, chunksize=10_000, low_memory=False, encoding="latin-1")
                return pd.concat(chunks, ignore_index=True)
            return pd.read_csv(bio, low_memory=False, encoding="latin-1")

    if suffix in {".xls", ".xlsx"}:
        bio = BytesIO(file_bytes)
        if sheet_name == "all":
            # Return all sheets as a dict
            return pd.read_excel(bio, sheet_name=None)
        elif sheet_name is not None:
            # Read specific sheet(s)
            return pd.read_excel(bio, sheet_name=sheet_name)
        else:
            # Default: read first sheet
            return pd.read_excel(bio)

    if suffix == ".parquet":
        return pd.read_parquet(BytesIO(file_bytes))

    raise ValueError(f"Format de fichier non supporté: {suffix}")


def list_excel_sheets(file_bytes: bytes, filename: str) -> list[dict]:
    """List all sheets in an Excel file with preview info.

    Returns:
        List of sheet info dicts with name, index, row_count, column_count, columns
    """
    suffix = Path(filename).suffix.lower()
    if suffix not in {".xls", ".xlsx"}:
        raise ValueError(f"Not an Excel file: {suffix}")

    logger.info(f"Reading Excel sheets from: {filename} ({len(file_bytes)} bytes)")

    # Use the bytes directly with pd.ExcelFile
    xl = pd.ExcelFile(BytesIO(file_bytes))

    logger.info(f"Found {len(xl.sheet_names)} sheets: {list(xl.sheet_names)}")

    sheets_info = []
    for idx, sheet_name in enumerate(xl.sheet_names):
        try:
            # Create a new BytesIO for each sheet read to avoid position issues
            # Read preview (first 5 rows)
            df_preview = pd.read_excel(BytesIO(file_bytes), sheet_name=sheet_name, nrows=5)

            # Read full sheet for row count
            df_full = pd.read_excel(BytesIO(file_bytes), sheet_name=sheet_name)
            row_count = len(df_full)

            logger.info(f"Sheet '{sheet_name}': {row_count} rows, {len(df_preview.columns)} columns")

            sheets_info.append(
                {
                    "index": idx,
                    "name": sheet_name,
                    "row_count": row_count,
                    "column_count": len(df_preview.columns),
                    "columns": [str(c) for c in df_preview.columns.tolist()],
                    "preview_rows": df_preview.head(3).to_dict("records") if len(df_preview) > 0 else [],
                }
            )
        except Exception as e:
            logger.warning(f"Failed to read sheet {sheet_name}: {e}")
            sheets_info.append(
                {
                    "index": idx,
                    "name": sheet_name,
                    "row_count": 0,
                    "column_count": 0,
                    "columns": [],
                    "preview_rows": [],
                    "error": str(e),
                }
            )

    logger.info(f"Returning {len(sheets_info)} sheet(s)")
    return sheets_info


def ensure_data_dir() -> Path:
    data_dir = Path(settings.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_duckdb_path() -> str:
    data_dir = ensure_data_dir()
    return str(data_dir / settings.duckdb_filename)


def ingest_files(files: Iterable[tuple[str, bytes]]) -> int:
    import time

    db_path = get_duckdb_path()
    tables_created = 0
    total_rows = 0
    schema_updates: dict[str, tuple[list[str], list[str]]] = {}

    existing_tables = _get_existing_tables()

    with duckdb.connect(db_path) as con:
        for filename, file_bytes in files:
            file_type = Path(filename).suffix.lower()
            file_size = len(file_bytes)

            with log_ingestion_time(filename, file_size, file_type) as log_entry:
                start_time = time.time()
                df = _read_dataframe(file_bytes, filename)
                original_columns = [str(col) for col in df.columns]
                df = normalize_dataframe(df)
                table_name = _safe_table_name(filename, existing_tables)
                existing_tables.add(table_name.lower())
                schema_updates[table_name] = (original_columns, list(df.columns))
                con.register("ingest_df", df)
                con.execute(f'CREATE OR REPLACE TABLE "{table_name}" AS SELECT * FROM ingest_df')
                con.unregister("ingest_df")
                tables_created += 1
                total_rows += len(df)

                log_entry["rows_processed"] = len(df)
                log_entry["columns_count"] = len(df.columns)
                log_entry["table_name"] = table_name

    if schema_updates:
        batch_update_schema_map(schema_updates)
        invalidate_schema_cache()

    return tables_created


def ingest_files_with_progress(
    files: Iterable[tuple[str, bytes]],
    on_step: Callable[[str, str], None] | None = None,
) -> int:
    db_path = get_duckdb_path()
    tables_created = 0
    schema_updates: dict[str, tuple[list[str], list[str]]] = {}

    existing_tables = _get_existing_tables()

    with duckdb.connect(db_path) as con:
        for filename, file_bytes in files:
            label = f"[{filename}]"
            if on_step:
                on_step("read_file", f"{label} Lecture du fichier")
            df = _read_dataframe(file_bytes, filename)
            original_columns = [str(col) for col in df.columns]
            df = normalize_dataframe(df, on_step=on_step, context=label)
            table_name = _safe_table_name(filename, existing_tables)
            existing_tables.add(table_name.lower())
            schema_updates[table_name] = (original_columns, list(df.columns))
            if on_step:
                on_step("write_duckdb", f"{label} Écriture dans DuckDB (table: {table_name})")
            con.register("ingest_df", df)
            con.execute(f'CREATE OR REPLACE TABLE "{table_name}" AS SELECT * FROM ingest_df')
            con.unregister("ingest_df")
            tables_created += 1

    if schema_updates:
        batch_update_schema_map(schema_updates)
        invalidate_schema_cache()

    return tables_created


def _list_schema_raw() -> list[dict]:
    """Raw schema listing without cache."""
    db_path = get_duckdb_path()
    if not Path(db_path).exists():
        return []

    schema: list[dict] = []
    with duckdb.connect(db_path) as con:
        tables = con.execute("SHOW TABLES").fetchall()
        for (table_name,) in tables:
            cols = con.execute("PRAGMA table_info(?)", [table_name]).fetchall()
            # col[1] = name, col[2] = type
            columns = [{"name": col[1], "type": col[2]} for col in cols]
            schema.append({"name": table_name, "columns": columns})

    return schema


def list_schema(use_cache: bool = True) -> list[dict]:
    """List schema with caching.

    Args:
        use_cache: Whether to use cache (default: True)

    Returns:
        List of table definitions
    """
    if not use_cache:
        return _list_schema_raw()

    # Try cache
    cached = schema_cache.get("schema")
    if cached is not None:
        return cached

    # Fetch and cache
    schema = _list_schema_raw()
    schema_cache.set("schema", schema)
    return schema


def purge_data() -> tuple[bool, bool]:
    duckdb_path = Path(get_duckdb_path())
    duckdb_deleted = False
    if duckdb_path.exists():
        duckdb_path.unlink()
        duckdb_deleted = True

    # Purge Qdrant collections
    qdrant_deleted = False
    try:
        from ndi_api.services.vector_store import get_client

        client = get_client()
        for col in client.get_collections().collections:
            client.delete_collection(col.name)
        qdrant_deleted = True
    except Exception:
        pass

    # Invalidate all caches when data is purged
    invalidate_schema_cache()

    return duckdb_deleted, qdrant_deleted
