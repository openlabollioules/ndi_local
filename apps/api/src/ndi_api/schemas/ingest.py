from pydantic import BaseModel


class IngestSummary(BaseModel):
    files_received: int
    tables_created: int
    message: str
    job_id: str | None = None
    status: str = "completed"


class PurgeResponse(BaseModel):
    duckdb_cleared: bool
    chroma_cleared: bool  # kept for backward compat — actually tracks qdrant now
    message: str


class ExcelSheetInfo(BaseModel):
    """Information about a single Excel sheet."""

    index: int
    name: str
    row_count: int
    column_count: int
    columns: list[str]
    preview_rows: list[dict]
    error: str | None = None


class ExcelSheetsResponse(BaseModel):
    """Response for Excel sheet preview endpoint."""

    filename: str
    sheets: list[ExcelSheetInfo]
    total_sheets: int


class SheetSelection(BaseModel):
    """Selection of sheets to ingest from a file."""

    filename: str
    sheet_names: list[str]  # Names of sheets to ingest
    sheet_indices: list[int] | None = None  # Alternative: indices of sheets


class ExcelIngestRequest(BaseModel):
    """Request to ingest Excel files with sheet selection."""

    selections: list[SheetSelection]  # Per-file sheet selections
