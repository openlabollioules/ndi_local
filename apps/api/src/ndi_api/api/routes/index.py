import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ndi_api.schemas.status import IndexStatus
from ndi_api.services.indexing import index_schema
from ndi_api.services.vector_store import get_index_count

router = APIRouter(prefix="/index")


@router.get("/status", response_model=IndexStatus)
async def index_status() -> IndexStatus:
    return IndexStatus(indexed=get_index_count())


@router.post("/reindex")
async def reindex_schema() -> dict:
    """Relance la génération du dictionnaire de données et la vectorisation."""
    try:
        count = index_schema()
        return {
            "success": True,
            "indexed": count,
            "message": f"Indexation terminée : {count} documents indexés.",
        }
    except Exception as e:
        return {
            "success": False,
            "indexed": 0,
            "message": f"Erreur lors de l'indexation : {str(e)}",
        }


@router.get("/reindex/stream")
async def reindex_schema_stream():
    """Relance l'indexation avec streaming de la progression."""

    async def event_generator():
        progress_events = []

        def on_progress(step: str, message: str):
            progress_events.append({"step": step, "message": message})

        # Lancer l'indexation dans un thread séparé
        loop = asyncio.get_event_loop()

        async def run_indexing():
            return await loop.run_in_executor(None, lambda: index_schema(on_progress=on_progress))

        # Démarrer l'indexation
        task = asyncio.create_task(run_indexing())

        sent_count = 0
        while not task.done():
            # Envoyer les nouveaux événements
            while sent_count < len(progress_events):
                event = progress_events[sent_count]
                yield f"data: {json.dumps(event)}\n\n"
                sent_count += 1
            await asyncio.sleep(0.1)

        # Envoyer les événements restants
        while sent_count < len(progress_events):
            event = progress_events[sent_count]
            yield f"data: {json.dumps(event)}\n\n"
            sent_count += 1

        # Résultat final
        try:
            count = task.result()
            yield f"data: {json.dumps({'step': 'complete', 'message': f'Indexation terminée : {count} documents', 'count': count})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'step': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
