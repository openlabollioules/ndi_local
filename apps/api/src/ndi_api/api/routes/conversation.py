"""Conversation API routes with memory and open analysis support.

Provides endpoints for:
- Query with conversation context
- Conversation history management
- Open-ended data analysis
- Image upload and analysis via chat
"""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

logger = logging.getLogger(__name__)
from pydantic import BaseModel, Field

from ndi_api.plugins.manager import get_plugin_manager  # kept for internal helpers
from ndi_api.services.agent_prompts import load_skill
from ndi_api.services.chart_suggest import suggest_chart
from ndi_api.services.conversation_memory import (
    ConversationMessage,
    PendingTableData,
    get_conversation_store,
)
from ndi_api.services.image_agent import ImageAgent, ImageAgentResult, get_image_agent
from ndi_api.services.indexing import index_schema
from ndi_api.services.nl_sql import run_nl_sql, run_nl_sql_stream
from ndi_api.services.open_analysis import get_open_analysis_engine
from ndi_api.services.question_router import get_question_router
from ndi_api.settings import settings

router = APIRouter(prefix="/conversation")


def _infer_query_type(query: str | None) -> str | None:
    if not query:
        return None
    return "nosql" if query.lstrip().startswith("{") else "sql"


class QueryRequest(BaseModel):
    """Request for a conversational query."""

    question: str = Field(..., description="The user's question")
    conversation_id: str | None = Field(
        None, description="Conversation ID for context (optional, creates new if not provided)"
    )


class QueryResponse(BaseModel):
    """Response from a conversational query."""

    answer: str = Field(..., description="The answer to the question")
    conversation_id: str = Field(..., description="Conversation ID for follow-up")
    question_type: str = Field(..., description="Type of question: query, follow_up, analysis")
    confidence: float = Field(..., description="Confidence in the routing")

    # For nl_to_query type
    query: str | None = Field(None, description="Generated SQL/NoSQL query if applicable")
    query_type: str | None = Field(None, description="Type of query: sql or nosql")
    rows: list[dict] | None = Field(None, description="Query results if applicable")
    row_count: int | None = Field(None, description="Number of rows returned")

    # For analysis type
    analysis_type: str | None = Field(None, description="Type of analysis performed")
    sample_size: int | None = Field(None, description="Sample size for analysis")

    # Chart suggestion
    chart_suggestion: dict | None = Field(None, description="Suggested chart configuration")


class ConversationHistoryResponse(BaseModel):
    """Response containing conversation history."""

    conversation_id: str
    messages: list[dict]
    message_count: int


class ImageChatResponse(BaseModel):
    """Response from an image chat request."""

    answer: str = Field(..., description="The assistant's response")
    conversation_id: str = Field(..., description="Conversation ID")
    action_taken: str = Field(..., description="Action performed: describe, ocr, extract_table, ingest_table, chart")
    success: bool = Field(..., description="Whether the operation succeeded")

    # For table extraction/ingestion
    table_name: str | None = Field(None, description="Name of ingested table if applicable")
    rows_ingested: int = Field(0, description="Number of rows ingested if applicable")
    columns: list[str] | None = Field(None, description="Column names if table extracted")

    # Data preview
    data_preview: list[dict] | None = Field(None, description="Preview of extracted data")


_INGEST_KEYWORDS = [
    "ingère",
    "ingérer",
    "sauvegarde",
    "sauvegarder",
    "importe",
    "importer",
    "stocke",
    "stocker",
    "mettre dans la base",
    "enregistre",
    "enregistrer",
    "sauvegarde dans la base",
    "dans la base",
]


_QUALITY_RE = re.compile(
    r"\b(qualité|qualite|quality|manquant|null|vide|doublon|duplicate|"
    r"outlier|aberrant|anomalie|complétude|audit|propreté)\b",
    re.IGNORECASE,
)


def _is_quality_intent(question: str) -> bool:
    """Detect whether the user wants a data quality audit."""
    return bool(_QUALITY_RE.search(question))


def _is_ingest_intent(question: str) -> bool:
    """Detect whether the user wants to ingest previously extracted data."""
    q = question.lower()
    return any(kw in q for kw in _INGEST_KEYWORDS)


@router.post("/query", response_model=QueryResponse)
async def conversational_query(request: QueryRequest) -> QueryResponse:
    """
    Process a question with conversation context and memory.

    This endpoint handles:
    - Standard NL-to-Query questions
    - Follow-up questions about previous results
    - Open-ended analysis questions
    - **Pending table ingestion** from a previous image extraction

    The conversation_id allows maintaining context across multiple questions.
    """
    store = get_conversation_store()
    session, is_new = store.get_or_create(request.conversation_id)

    session.add_message(
        ConversationMessage(
            role="user",
            content=request.question,
        )
    )

    try:
        # --- Priority: ingest pending table data from image extraction ---
        if session.pending_table and _is_ingest_intent(request.question):
            result = await _handle_pending_ingest(session, request.question)
            question_type = "image_ingest"
        elif _is_quality_intent(request.question):
            # Quality audit takes priority — route directly to open_analysis
            # so the SkillRouter can resolve the data-quality skill.
            question_type = "open_analysis"
            result = await _handle_open_analysis(request.question, session)
        else:
            router_instance = get_question_router()
            routing = router_instance.route(request.question, session)
            question_type = routing.question_type

            if routing.question_type == "nl_to_query":
                result = _handle_nl_to_query(request.question, session)
            elif routing.question_type == "follow_up":
                result = await _handle_follow_up(request.question, session)
            elif routing.question_type in ("open_analysis", "explanation"):
                result = await _handle_open_analysis(request.question, session)
            else:
                result = _handle_nl_to_query(request.question, session)

        session.add_message(
            ConversationMessage(
                role="assistant",
                content=result["answer"],
                query=result.get("query"),
                query_type=result.get("query_type"),
                results_count=result.get("row_count"),
                analysis=result.get("analysis_type"),
                intent=question_type,
            )
        )

        if session.should_summarize():
            session.summarize_old_messages()

        return QueryResponse(
            answer=result["answer"],
            conversation_id=session.id,
            question_type=question_type,
            confidence=result.get("confidence", 1.0),
            query=result.get("query"),
            query_type=result.get("query_type"),
            rows=result.get("rows"),
            row_count=result.get("row_count"),
            analysis_type=result.get("analysis_type"),
            sample_size=result.get("sample_size"),
            chart_suggestion=result.get("chart_suggestion"),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors du traitement: {str(e)}")


@router.post("/query/stream")
async def conversational_query_stream(request: QueryRequest):
    """SSE streaming version of the conversational query endpoint.

    Streams events:
    - ``event: status``   — pipeline stage updates
    - ``event: thinking`` — reasoning tokens (chain-of-thought)
    - ``event: content``  — answer content tokens
    - ``event: answer``   — final JSON result
    - ``event: error``    — error message
    """
    import json as _json

    from fastapi.responses import StreamingResponse

    question = request.question
    store = get_conversation_store()
    session, _is_new = store.get_or_create(request.conversation_id)

    def event_generator():
        session.add_message(
            ConversationMessage(
                role="user",
                content=question,
            )
        )

        thinking_parts: list[str] = []
        final_answer: dict | None = None

        for event in run_nl_sql_stream(question):
            etype = event["event"]
            data = event["data"]

            if etype == "thinking" and isinstance(data, str):
                thinking_parts.append(data)
            elif etype == "answer" and isinstance(data, dict):
                query = data.get("query") or data.get("sql")
                data = {
                    **data,
                    "conversation_id": session.id,
                    "query": query,
                    "query_type": data.get("query_type") or _infer_query_type(query),
                    "question_type": data.get("question_type", "query"),
                    "confidence": data.get("confidence", 1.0),
                }
                final_answer = data

            if isinstance(data, dict):
                payload = _json.dumps(data, ensure_ascii=False)
            else:
                # Escape newlines for SSE (each line must be prefixed with data:)
                payload = str(data).replace("\n", "\\n")
            yield f"event: {etype}\ndata: {payload}\n\n"

        if final_answer:
            session.add_message(
                ConversationMessage(
                    role="assistant",
                    content=final_answer.get("answer", ""),
                    thinking=final_answer.get("thinking") or "".join(thinking_parts).strip() or None,
                    query=final_answer.get("query"),
                    query_type=final_answer.get("query_type"),
                    results_count=final_answer.get("row_count"),
                    analysis=final_answer.get("analysis_type"),
                    intent=final_answer.get("question_type"),
                )
            )

            if session.should_summarize():
                session.summarize_old_messages()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _handle_nl_to_query(question: str, session) -> dict:
    """Handle standard NL-to-Query questions."""
    result = run_nl_sql(question)
    rows = result.get("rows", [])

    return {
        "answer": result.get("answer", ""),
        "query": result.get("sql") or result.get("json_query"),
        "query_type": "sql" if result.get("sql") else "nosql",
        "rows": rows,
        "row_count": len(rows),
        "chart_suggestion": suggest_chart(rows, question),
    }


async def _handle_follow_up(question: str, session) -> dict:
    """Handle follow-up questions about previous results."""
    # Get context from previous query
    last_result = session.get_last_query_result()

    if not last_result:
        # No previous context, treat as normal query
        return _handle_nl_to_query(question, session)

    # Build enhanced prompt with context
    context = session.get_last_results_context(max_chars=1500)

    # For simple follow-ups, we might just analyze previous results
    # For complex ones, generate a new query

    # Check if we need a new query or just analysis
    if _needs_new_query(question):
        # Generate new query with context
        enhanced_question = f"Contexte précédent:\n{context}\n\nQuestion de suivi: {question}"
        return _handle_nl_to_query(enhanced_question, session)
    else:
        # Analyze previous results
        plugin = get_plugin_manager().get_plugin()
        engine = get_open_analysis_engine()

        analysis_result = await engine.analyze(
            question=f"Basé sur ces résultats précédents, réponds à: {question}\n\n{context}",
            plugin=plugin,
            session=session,
        )

        return {
            "answer": analysis_result.answer,
            "analysis_type": analysis_result.analysis_type,
            "sample_size": analysis_result.sample_size,
        }


async def _handle_open_analysis(question: str, session) -> dict:
    """Handle open-ended analysis questions."""
    plugin = get_plugin_manager().get_plugin()
    engine = get_open_analysis_engine()

    result = await engine.analyze(
        question=question,
        plugin=plugin,
        session=session,
    )

    return {
        "answer": result.answer,
        "analysis_type": result.analysis_type,
        "sample_size": result.sample_size,
        "confidence": result.confidence,
    }


async def _handle_pending_ingest(session, question: str) -> dict:
    """Ingest pending table data extracted from a previous image.

    Uses the same safe-ingestion logic as the image agent (no overwrite,
    prefixed table names, validation).
    """
    import io

    import pandas as pd

    pending = session.pending_table
    csv_content = pending.csv_content
    source = pending.source_filename

    df = pd.read_csv(io.StringIO(csv_content))

    validation_err = ImageAgent._validate_dataframe(df)
    if validation_err:
        return {
            "answer": f"**Ingestion refusée** : {validation_err}",
            "confidence": 1.0,
        }

    plugin = get_plugin_manager().get_plugin()
    raw_name = source.rsplit(".", 1)[0] if "." in source else source
    table_name = ImageAgent._safe_img_table_name(raw_name, plugin)
    final_table_name = ImageAgent._safe_ingest(plugin, df, table_name)

    rows = len(df)
    cols = list(df.columns)
    logger.info(
        "Pending ingest: table=%s rows=%d cols=%d source=%s session=%s",
        final_table_name,
        rows,
        len(cols),
        source,
        session.id,
    )

    session.pending_table = None

    if settings.indexing_enabled:
        import asyncio

        asyncio.create_task(_trigger_indexing_async())

    answer = (
        f"**Données ingérées** dans la table `{final_table_name}` "
        f"({rows} lignes, {len(cols)} colonnes)\n\n"
        f"Vous pouvez maintenant interroger ces données en langage naturel !"
    )
    return {"answer": answer, "confidence": 1.0}


def _needs_new_query(question: str) -> bool:
    """Determine if follow-up requires a new database query."""
    # Keywords that suggest we need new data
    new_query_indicators = [
        "autre",
        "autres",
        "différent",
        "différents",
        "plus",
        "moins",
        "supérieur",
        "inférieur",
        "tous",
        "toutes",
        "ensemble",
        "total",
        "2023",
        "2024",
        "2025",
        "année",
        "mois",
    ]

    question_lower = question.lower()
    return any(ind in question_lower for ind in new_query_indicators)


@router.get("/{conversation_id}/history", response_model=ConversationHistoryResponse)
async def get_conversation_history(conversation_id: str) -> ConversationHistoryResponse:
    """Get the history of a conversation."""
    store = get_conversation_store()
    session = store.get_session(conversation_id)

    if not session:
        raise HTTPException(status_code=404, detail="Conversation non trouvée")

    messages = [
        {
            "role": msg.role,
            "content": msg.content,
            "thinking": msg.thinking,
            "timestamp": msg.timestamp.isoformat(),
            "query": msg.query,
            "query_type": msg.query_type,
            "results_count": msg.results_count,
            "analysis": msg.analysis,
            "intent": msg.intent,
        }
        for msg in session.messages
    ]

    return ConversationHistoryResponse(
        conversation_id=conversation_id,
        messages=messages,
        message_count=len(messages),
    )


@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: str) -> dict:
    """Delete a conversation and its history."""
    store = get_conversation_store()
    deleted = store.delete_session(conversation_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation non trouvée")

    return {"message": "Conversation supprimée", "conversation_id": conversation_id}


@router.get("/list")
async def list_conversations(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """List active conversations with pagination (admin/debug)."""
    store = get_conversation_store()
    sessions = store.list_sessions()
    total = len(sessions)
    page = sessions[offset : offset + limit]
    return {
        "conversations": page,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_next": (offset + limit) < total,
    }


@router.post("/debug/analyze-prompt")
async def debug_analysis_prompt(request: dict) -> dict:
    """Debug endpoint to see the prompt that would be sent for analysis.

    Request body:
    {
        "question": "analyse la cohérence entre MOTIF et Commentaires",
        "analysis_type": "coherence",
        "sample_data": [...],
        "analysis_data": {...}
    }
    """
    from ndi_api.services.open_analysis import OpenAnalysisEngine

    engine = OpenAnalysisEngine()

    question = request.get("question", "")
    analysis_type = request.get("analysis_type", "coherence")
    sample_data = request.get("sample_data", [])
    analysis_data = request.get("analysis_data", {})

    # Build prompt
    prompt = engine._build_analysis_prompt(
        question=question,
        analysis_type=analysis_type,
        analysis_data=analysis_data,
        sample_data=sample_data,
        schema=None,
    )

    return {
        "prompt": prompt,
        "length": len(prompt),
        "estimated_tokens": len(prompt) // 4,
        "analysis_type": analysis_type,
        "sample_size": len(sample_data),
    }


# =============================================================================
# Image Chat Endpoint
# =============================================================================


@router.post("/image-chat", response_model=ImageChatResponse)
async def image_chat(
    file: UploadFile = File(..., description="Image file to analyze"),
    message: str = Form("", description="User's message/request about the image"),
    conversation_id: str | None = Form(None, description="Conversation ID for context"),
    table_name: str | None = Form(None, description="Custom table name for data ingestion"),
) -> ImageChatResponse:
    """
    Chat with an image - upload and analyze via natural language.

    This endpoint allows users to:
    - Upload an image
    - Describe what they want in natural language
    - Get intelligent processing based on intent

    **Examples of messages:**
    - "Décris cette image" → General description
    - "Extraire le texte" → OCR
    - "Extraire le tableau" → Table extraction (preview only)
    - "Ingère ces données" → Extract AND save to database
    - "Analyse ce graphique" → Chart analysis

    If no message is provided, defaults to image description.
    """
    # Get or create conversation session
    store = get_conversation_store()
    session, is_new = store.get_or_create(conversation_id)

    try:
        image_bytes = await file.read()

        skill = load_skill("image-ingest")
        if skill.content:
            logger.debug("Skill image-ingest v%s chargé", skill.version)

        agent = get_image_agent()
        result: ImageAgentResult = await agent.process(
            image_bytes=image_bytes,
            filename=file.filename,
            user_message=message,
            custom_table_name=table_name,
        )

        # Add to conversation history
        user_content = message if message else f"[Image upload: {file.filename}]"
        session.add_message(
            ConversationMessage(
                role="user",
                content=user_content,
                intent="image_upload",
            )
        )

        session.add_message(
            ConversationMessage(
                role="assistant",
                content=result.answer,
                intent=f"image_{result.action_taken}",
                results_count=result.rows_ingested if result.rows_ingested > 0 else None,
            )
        )

        # Store pending table data for follow-up ingestion via text message
        if result.action_taken == "extract_table" and result.success and result.data and result.data.get("csv"):
            csv_lines = result.data["csv"].strip().splitlines()
            actual_row_count = max(len(csv_lines) - 1, 0)  # minus header
            session.pending_table = PendingTableData(
                csv_content=result.data["csv"],
                columns=result.data.get("columns", []),
                row_count=actual_row_count,
                source_filename=file.filename or "image",
            )
            logger.info(
                "Pending table stored in session %s (%d cols, source=%s)",
                session.id,
                len(result.data.get("columns", [])),
                file.filename,
            )
        elif result.action_taken == "ingest_table":
            session.pending_table = None

        # Trigger indexing if data was ingested
        if result.action_taken == "ingest_table" and result.rows_ingested > 0:
            if settings.indexing_enabled:
                # Run indexing in background (fire and forget)
                import asyncio

                asyncio.create_task(_trigger_indexing_async())

        return ImageChatResponse(
            answer=result.answer,
            conversation_id=session.id,
            action_taken=result.action_taken,
            success=result.success,
            table_name=result.table_name,
            rows_ingested=result.rows_ingested,
            columns=list(result.data.keys())
            if result.data and isinstance(result.data, dict) and "csv" not in result.data
            else None,
            data_preview=result.data.get("preview") if result.data else None,
        )

    except Exception as e:
        logger.exception("Image chat failed")
        raise HTTPException(status_code=500, detail=f"Erreur lors du traitement de l'image: {str(e)}")


async def _trigger_indexing_async():
    """Trigger schema indexing asynchronously."""
    try:
        index_schema()
        logger.info("Schema indexing triggered after image ingestion")
    except Exception as e:
        logger.warning(f"Schema indexing failed after image ingestion: {e}")
