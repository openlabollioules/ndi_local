import asyncio
import json
import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse

from ndi_api.api.dependencies import PluginDep
from ndi_api.schemas.ingest import ExcelSheetsResponse, IngestSummary, PurgeResponse
from ndi_api.services.agent_prompts import invalidate_cache as invalidate_agent_prompts_cache
from ndi_api.services.cache import invalidate_schema_cache
from ndi_api.services.indexing import index_schema
from ndi_api.services.ingestion import list_excel_sheets
from ndi_api.services.progress import progress_store
from ndi_api.services.rate_limiter import PURGE_LIMIT, UPLOAD_LIMIT, limiter
from ndi_api.services.vector_store import reset_client as reset_vector_client
from ndi_api.settings import settings

router = APIRouter(prefix="/ingest")
logger = logging.getLogger(__name__)

# Configuration validation uploads
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 Mo
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".parquet"}
ALLOWED_MIME_TYPES = {
    "text/csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "application/octet-stream",  # Parquet often uses this
}


def _validate_file_content(filename: str, content: bytes) -> tuple[bool, str]:
    """Valide le type de fichier par extension et magic bytes.

    Returns:
        (is_valid, error_message)
    """
    ext = Path(filename).suffix.lower()

    # Vérifier extension
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"Extension non autorisée: {ext}. Types acceptés: {', '.join(ALLOWED_EXTENSIONS)}"

    # Vérifier magic bytes
    if ext == ".parquet":
        # Parquet magic: 'PAR1' au début ou à la fin
        if not (content[:4] == b"PAR1" or content[-4:] == b"PAR1"):
            return False, "Fichier Parquet invalide (magic bytes incorrects)"
    elif ext in (".xlsx", ".xls"):
        # Excel modern (xlsx) est un ZIP
        if ext == ".xlsx" and content[:4] != b"PK\x03\x04":
            return False, "Fichier Excel (.xlsx) invalide (format ZIP attendu)"
    elif ext == ".csv":
        # CSV: vérifier que c'est du texte lisible (pas binaire)
        # On accepte tous les encodages - la détection se fera à la lecture
        # On vérifie juste que ce n'est pas un fichier binaire pur
        null_bytes = content[:8192].count(b"\x00")
        if null_bytes > 10:
            return False, "Fichier CSV invalide (contenu binaire détecté)"

    return True, ""


@router.post("/upload", response_model=IngestSummary)
@limiter.limit(UPLOAD_LIMIT)
async def upload_files(
    request: Request,
    plugin: PluginDep,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    async_process: bool = Query(False),
) -> IngestSummary:
    try:
        payload = []
        for file in files:
            content = await file.read()

            # Validation taille
            if len(content) > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail=f"Fichier trop volumineux: {file.filename} ({len(content)} bytes). Max: {MAX_FILE_SIZE // (1024*1024)} Mo",
                )

            # Validation type
            is_valid, error_msg = _validate_file_content(file.filename or "upload", content)
            if not is_valid:
                raise HTTPException(status_code=400, detail=error_msg)

            payload.append((file.filename or "upload", content))

        # Plugin injected via Depends
        plugin_name = plugin.name
        logger.info("Ingestion avec plugin %s (mode=%s)", plugin_name, plugin.mode)

        if async_process:
            job_id = progress_store.create_job()

            def _progress(step: str, message: str) -> None:
                progress_store.add_event(job_id, step, message)

            def _run_job() -> None:
                from ndi_api.services.ingestion import normalize_dataframe

                try:
                    _progress("start", f"Démarrage ingestion ({plugin_name} mode) — {len(payload)} fichier(s)")
                    tables_created = 0
                    for i, (filename, content) in enumerate(payload, 1):
                        label = f"[{i}/{len(payload)} {filename}]"
                        _progress("read_file", f"{label} Lecture du fichier")
                        df = plugin.read_file(content, filename)
                        _progress(
                            "normalize_columns", f"{label} Normalisation ({len(df)} lignes, {len(df.columns)} colonnes)"
                        )
                        df = normalize_dataframe(df, on_step=_progress, context=label)
                        _progress("write_duckdb", f"{label} Écriture en base")
                        table_name = plugin.ingest_dataframe(df, filename, on_step=_progress)
                        tables_created += 1
                        _progress("table_created", f"{label} Table créée : {table_name}")
                    _progress("indexing", f"Indexation sémantique de {tables_created} table(s)…")
                    if settings.indexing_enabled:
                        index_schema(on_progress=_progress)
                    _progress("done", f"Ingestion terminée — {tables_created} table(s) créée(s)")
                finally:
                    progress_store.complete(job_id)

            background_tasks.add_task(_run_job)
            return IngestSummary(
                files_received=len(files),
                tables_created=0,
                message=f"Ingestion en cours ({plugin_name} mode).",
                job_id=job_id,
                status="processing",
            )

        logger.info("Ingestion démarrée: %s fichiers (mode: %s)", len(payload), plugin_name)
        tables_created = 0
        for filename, content in payload:
            df = plugin.read_file(content, filename)
            table_name = plugin.ingest_dataframe(df, filename)
            tables_created += 1
            logger.info("Table/collection créée: %s", table_name)
        logger.info("Ingestion terminée: %s tables/collections", tables_created)

        if settings.indexing_enabled:
            background_tasks.add_task(index_schema)
            message = f"Ingestion terminée ({plugin_name} mode). Indexation en arrière-plan."
        else:
            message = f"Ingestion terminée ({plugin_name} mode)."
        return IngestSummary(
            files_received=len(files),
            tables_created=tables_created,
            message=message,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - fallback
        raise HTTPException(status_code=500, detail="Erreur ingestion.") from exc


@router.post("/purge", response_model=PurgeResponse)
@limiter.limit(PURGE_LIMIT)
async def purge_ingestion(request: Request, plugin: PluginDep) -> PurgeResponse:
    # Purge plugin data (DuckDB or JSON collections)
    plugin_cleared = plugin.purge()

    # Purge Qdrant collections
    qdrant_cleared = False
    try:
        from ndi_api.services.vector_store import get_client

        client = get_client()
        for col in client.get_collections().collections:
            client.delete_collection(col.name)
        qdrant_cleared = True
    except Exception as e:
        logger.warning("Failed to purge Qdrant: %s", e)

    reset_vector_client()
    invalidate_schema_cache()
    invalidate_agent_prompts_cache()

    logger.info("Purge completed: plugin=%s, qdrant=%s", plugin.name, qdrant_cleared)

    message = f"Données purgées ({plugin.name} mode)."
    return PurgeResponse(
        duckdb_cleared=plugin_cleared if plugin.name == "sql" else False,
        chroma_cleared=qdrant_cleared,
        message=message,
    )


@router.get("/stream")
async def stream_progress(
    job_id: str,
    cursor: int = 0,
    api_key: str | None = Query(None, description="API key (for EventSource which can't send headers)"),
) -> StreamingResponse:
    async def event_generator():
        current = cursor
        while True:
            events, done = progress_store.get_events(job_id, current)
            for event in events:
                current += 1
                yield f"event: progress\ndata: {json.dumps(event)}\n\n"
            if done:
                yield "event: done\ndata: {}\n\n"
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# =============================================================================
# Excel Sheet Preview and Selective Ingestion
# =============================================================================


@router.post("/excel/sheets", response_model=ExcelSheetsResponse)
@limiter.limit(UPLOAD_LIMIT)
async def preview_excel_sheets(
    request: Request,
    file: UploadFile = File(...),
) -> ExcelSheetsResponse:
    """Preview all sheets in an Excel file before ingestion.

    Returns sheet names, row counts, column info, and preview data.
    """
    logger.info(f"Excel sheet preview request for: {file.filename}")
    try:
        content = await file.read()
        logger.info(f"File read: {len(content)} bytes")

        # Validation taille
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"Fichier trop volumineux: {file.filename} ({len(content)} bytes). Max: {MAX_FILE_SIZE // (1024*1024)} Mo",
            )

        # Validation type
        is_valid, error_msg = _validate_file_content(file.filename or "upload", content)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)

        # Check it's an Excel file
        ext = Path(file.filename or "").suffix.lower()
        if ext not in {".xls", ".xlsx"}:
            raise HTTPException(status_code=400, detail="Seuls les fichiers Excel (.xlsx, .xls) sont supportés")

        sheets = list_excel_sheets(content, file.filename or "upload")
        logger.info(f"Returning {len(sheets)} sheets for {file.filename}")

        return ExcelSheetsResponse(filename=file.filename or "upload", sheets=sheets, total_sheets=len(sheets))

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to preview Excel sheets")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la prévisualisation: {str(e)}")


@router.post("/excel/upload", response_model=IngestSummary)
@limiter.limit(UPLOAD_LIMIT)
async def upload_excel_with_sheet_selection(
    request: Request,
    plugin: PluginDep,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    selections: str = Form(...),  # JSON string of sheet selections
    async_process: bool = Query(False),
) -> IngestSummary:
    """Upload Excel files with specific sheet selection.

    The 'selections' parameter is a JSON string mapping filenames to selected sheet names.
    Example: {"file.xlsx": ["Sheet1", "Sheet2"], "file2.xlsx": ["Data"]}
    """
    try:
        import json

        sheet_selections: dict[str, list[str]] = json.loads(selections)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid selections JSON: {str(e)}")

    try:
        payload = []
        for file in files:
            content = await file.read()
            filename = file.filename or "upload"

            # Validation taille
            if len(content) > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail=f"Fichier trop volumineux: {filename} ({len(content)} bytes). Max: {MAX_FILE_SIZE // (1024*1024)} Mo",
                )

            # Validation type
            is_valid, error_msg = _validate_file_content(filename, content)
            if not is_valid:
                raise HTTPException(status_code=400, detail=error_msg)

            # Get selected sheets for this file
            selected_sheets = sheet_selections.get(filename, [])
            if not selected_sheets:
                logger.warning(f"No sheets selected for {filename}, skipping")
                continue

            payload.append((filename, content, selected_sheets))

        if not payload:
            raise HTTPException(status_code=400, detail="Aucun fichier à ingérer (aucune feuille sélectionnée)")

        # Plugin injected via Depends
        plugin_name = plugin.name
        logger.info(f"Ingestion Excel avec sélection: {len(payload)} fichiers (mode={plugin.mode})")

        if async_process:
            job_id = progress_store.create_job()

            def _progress(step: str, message: str) -> None:
                progress_store.add_event(job_id, step, message)

            def _run_job() -> None:
                try:
                    _progress("start", f"Démarrage ingestion Excel ({plugin_name} mode)")
                    tables_created = 0
                    for filename, content, selected_sheets in payload:
                        # Read and ingest each selected sheet
                        from ndi_api.services.ingestion import _read_dataframe

                        sheets_data = _read_dataframe(content, filename, sheet_name="all")

                        if isinstance(sheets_data, dict):
                            for sheet_name, df in sheets_data.items():
                                if sheet_name in selected_sheets:
                                    # Create unique table name including sheet name
                                    sheet_filename = f"{filename}_{sheet_name}"
                                    table_name = plugin.ingest_dataframe(df, sheet_filename, on_step=_progress)
                                    tables_created += 1
                                    _progress(
                                        "table_created", f"Table/collection créée: {table_name} (feuille: {sheet_name})"
                                    )
                        else:
                            # Single sheet (shouldn't happen with "all" but handle it)
                            table_name = plugin.ingest_dataframe(sheets_data, filename, on_step=_progress)
                            tables_created += 1
                            _progress("table_created", f"Table/collection créée: {table_name}")

                    _progress("done", f"Ingestion terminée ({tables_created} tables/collections)")
                    if settings.indexing_enabled:
                        index_schema(on_progress=_progress)
                finally:
                    progress_store.complete(job_id)

            background_tasks.add_task(_run_job)
            return IngestSummary(
                files_received=len(files),
                tables_created=0,
                message=f"Ingestion en cours ({plugin_name} mode).",
                job_id=job_id,
                status="processing",
            )

        # Synchronous processing
        tables_created = 0
        for filename, content, selected_sheets in payload:
            from ndi_api.services.ingestion import _read_dataframe

            sheets_data = _read_dataframe(content, filename, sheet_name="all")

            if isinstance(sheets_data, dict):
                for sheet_name, df in sheets_data.items():
                    if sheet_name in selected_sheets:
                        sheet_filename = f"{filename}_{sheet_name}"
                        table_name = plugin.ingest_dataframe(df, sheet_filename)
                        tables_created += 1
                        logger.info(f"Table/collection créée: {table_name} (feuille: {sheet_name})")
            else:
                table_name = plugin.ingest_dataframe(sheets_data, filename)
                tables_created += 1
                logger.info(f"Table/collection créée: {table_name}")

        if settings.indexing_enabled:
            background_tasks.add_task(index_schema)
            message = f"Ingestion terminée ({plugin_name} mode). Indexation en arrière-plan."
        else:
            message = f"Ingestion terminée ({plugin_name} mode)."

        return IngestSummary(
            files_received=len(files),
            tables_created=tables_created,
            message=message,
        )

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Excel ingestion with sheet selection failed")
        raise HTTPException(status_code=500, detail=f"Erreur ingestion: {str(exc)}") from exc
