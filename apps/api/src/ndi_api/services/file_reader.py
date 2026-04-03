"""File reader — CSV, Excel, Parquet with encoding detection.

Extracted from ingestion.py for reuse and testability.
"""

from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path

import pandas as pd

logger = logging.getLogger("ndi.ingestion")


def detect_encoding(file_bytes: bytes) -> str:
    """Detect file encoding using chardet if available, fallback to utf-8."""
    try:
        import chardet

        result = chardet.detect(file_bytes[:10000])
        encoding = result.get("encoding", "utf-8")
        confidence = result.get("confidence", 0)
        if encoding and confidence > 0.5:
            logger.debug("Detected encoding: %s (confidence: %.2f)", encoding, confidence)
            return encoding
    except ImportError:
        logger.debug("chardet not installed, using utf-8 fallback")
    except Exception as e:
        logger.warning("Encoding detection failed: %s, using utf-8 fallback", e)
    return "utf-8"


def read_dataframe(
    file_bytes: bytes,
    filename: str,
    sheet_name: str | int | list | None = None,
) -> pd.DataFrame | dict[str, pd.DataFrame]:
    """Read a file into a DataFrame with encoding detection for CSV.

    Args:
        file_bytes: Raw file content
        filename: Original filename
        sheet_name: For Excel files: sheet name, index, list, or None for first sheet.
                    If ``"all"``, returns a dict of all sheets.

    Returns:
        DataFrame or dict of DataFrames if sheet_name="all" or multiple sheets
    """
    suffix = Path(filename).suffix.lower()

    if suffix == ".csv":
        bio = BytesIO(file_bytes)
        encoding = detect_encoding(file_bytes)

        try:
            if len(file_bytes) > 50 * 1024 * 1024:
                chunks = pd.read_csv(bio, chunksize=10_000, low_memory=False, encoding=encoding)
                return pd.concat(chunks, ignore_index=True)
            return pd.read_csv(bio, low_memory=False, encoding=encoding)
        except UnicodeDecodeError:
            bio.seek(0)
            logger.warning("Failed to read %s with %s, trying latin-1", filename, encoding)
            if len(file_bytes) > 50 * 1024 * 1024:
                chunks = pd.read_csv(bio, chunksize=10_000, low_memory=False, encoding="latin-1")
                return pd.concat(chunks, ignore_index=True)
            return pd.read_csv(bio, low_memory=False, encoding="latin-1")

    if suffix in {".xls", ".xlsx"}:
        bio = BytesIO(file_bytes)
        if sheet_name == "all":
            return pd.read_excel(bio, sheet_name=None)
        elif sheet_name is not None:
            return pd.read_excel(bio, sheet_name=sheet_name)
        else:
            return pd.read_excel(bio)

    if suffix == ".parquet":
        return pd.read_parquet(BytesIO(file_bytes))

    raise ValueError(f"Format de fichier non supporté: {suffix}")


def list_excel_sheets(file_bytes: bytes, filename: str) -> list[dict]:
    """List all sheets in an Excel file with preview info."""
    suffix = Path(filename).suffix.lower()
    if suffix not in {".xls", ".xlsx"}:
        raise ValueError(f"Not an Excel file: {suffix}")

    logger.info("Reading Excel sheets from: %s (%d bytes)", filename, len(file_bytes))

    xl = pd.ExcelFile(BytesIO(file_bytes))
    logger.info("Found %d sheets: %s", len(xl.sheet_names), list(xl.sheet_names))

    sheets_info = []
    for idx, sname in enumerate(xl.sheet_names):
        try:
            df_preview = pd.read_excel(BytesIO(file_bytes), sheet_name=sname, nrows=5)
            df_full = pd.read_excel(BytesIO(file_bytes), sheet_name=sname)
            row_count = len(df_full)
            logger.info("Sheet '%s': %d rows, %d columns", sname, row_count, len(df_preview.columns))
            sheets_info.append(
                {
                    "index": idx,
                    "name": sname,
                    "row_count": row_count,
                    "column_count": len(df_preview.columns),
                    "columns": [str(c) for c in df_preview.columns.tolist()],
                    "preview_rows": df_preview.head(3).to_dict("records") if len(df_preview) > 0 else [],
                }
            )
        except Exception as e:
            logger.warning("Failed to read sheet %s: %s", sname, e)
            sheets_info.append(
                {
                    "index": idx,
                    "name": sname,
                    "row_count": 0,
                    "column_count": 0,
                    "columns": [],
                    "preview_rows": [],
                    "error": str(e),
                }
            )

    logger.info("Returning %d sheet(s)", len(sheets_info))
    return sheets_info
