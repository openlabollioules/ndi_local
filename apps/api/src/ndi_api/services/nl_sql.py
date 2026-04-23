from __future__ import annotations

import json
import os
import re
import time
from typing import Literal

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from ndi_api.plugins.manager import get_plugin_manager
from ndi_api.services.agent_prompts import get_system_prompt as get_agent_system_prompt
from ndi_api.services.agent_prompts import load_memory
from ndi_api.services.cache import (
    hash_question,
    hash_schema,
    nl_sql_cache,
    schema_cache,
)
from ndi_api.services.llm import extract_sql, get_llm, stream_llm_call, strip_thinking
from ndi_api.services.monitoring import (
    QueryLogEntry,
    log_query_complete,
    log_user_input,
    monitor,
    reasoning_logger,
)
from ndi_api.services.reranker import rerank_documents
from ndi_api.services.vector_store import query_documents
from ndi_api.settings import settings


class NLState(TypedDict):
    question: str
    route: str
    schema_context: str
    sql: str
    error: str
    rows: list[dict]
    answer: str
    attempts: int
    _timings: dict[str, float]


def _route(state: NLState) -> dict:
    return {"route": "sql"}


def _route_next(state: NLState) -> Literal["schema_context"]:
    return "schema_context"


def _extract_question_keywords(question: str) -> set[str]:
    """Extract relevant keywords from question for table matching."""
    # Common words to ignore
    stopwords = {
        "le",
        "la",
        "les",
        "de",
        "des",
        "du",
        "un",
        "une",
        "et",
        "ou",
        "en",
        "dans",
        "par",
        "pour",
        "sur",
        "avec",
        "sans",
        "sous",
        "comment",
        "quelle",
        "quel",
        "combien",
        "liste",
        "montre",
        "donne",
        "trouve",
        "chercher",
        "trouver",
        "the",
        "a",
        "an",
        "and",
        "or",
        "in",
        "on",
        "with",
        "for",
        "to",
        "of",
        "show",
        "list",
        "find",
        "get",
        "what",
        "how",
        "many",
        "much",
    }

    words = re.findall(r"\b[a-zA-Z_]+\b", question.lower())
    return {w for w in words if len(w) > 2 and w not in stopwords}


def _score_table_relevance(table: dict, keywords: set[str]) -> float:
    """Score table relevance based on keyword matching."""
    score = 0.0
    table_name = table["name"].lower()

    # Direct table name match
    for kw in keywords:
        if kw in table_name:
            score += 3.0  # High weight for table name match
        if table_name in kw:
            score += 2.0

    # Column name matches
    for col in table["columns"]:
        col_name = col["name"].lower()
        for kw in keywords:
            if kw in col_name:
                score += 1.0
            if col_name in kw:
                score += 0.5

    return score


def _schema_context(state: NLState) -> dict:
    question = state["question"]
    keywords = _extract_question_keywords(question)
    timings = state.get("_timings", {})

    initial_k = int(os.getenv("NDI_RETRIEVAL_K", "20"))
    final_k = int(os.getenv("NDI_RERANKER_FINAL_K", "8"))
    use_reranker = os.getenv("NDI_USE_RERANKER", "true").lower() == "true"

    # Get plugin for relations and schema context
    plugin = get_plugin_manager().get_plugin()
    current_mode = plugin.mode  # "sql" or "nosql"

    t0 = time.perf_counter()
    docs = query_documents(question, k=initial_k)
    timings["retrieval_ms"] = round((time.perf_counter() - t0) * 1000, 1)

    # Filter vector results to only include docs matching the current mode
    if current_mode == "nosql":
        docs = [d for d in docs if "Collection " in d]
    elif current_mode == "sql":
        docs = [d for d in docs if "Collection " not in d or "Table " in d]

    rerank_stats = {}
    if use_reranker and len(docs) > final_k:
        t0 = time.perf_counter()
        docs, _, rerank_stats = rerank_documents(
            query=question,
            documents=docs,
            top_k=final_k,
            use_reranker=True,
        )
        timings["reranking_ms"] = round((time.perf_counter() - t0) * 1000, 1)

    relation_lines = []
    relevant_tables = set()

    # Extract table/collection names from vector results
    for doc in docs:
        for match in re.finditer(r"[Tt]able\s+(\w+)|[Cc]ollection\s+(\w+)", doc):
            table_name = match.group(1) or match.group(2)
            if table_name:
                relevant_tables.add(table_name.lower())

    # Build relation block only for SQL mode
    if plugin.supports_relations():
        relations = plugin.get_relations()
        for rel in relations:
            from_table = rel["from_table"]
            from_column = rel["from_column"]
            to_table = rel["to_table"]
            to_column = rel["to_column"]
            relation_type = rel.get("relation_type", "foreign_key")

            # Include relation if either table is relevant
            if (
                relevant_tables
                and from_table.lower() not in relevant_tables
                and to_table.lower() not in relevant_tables
            ):
                continue

            join_example = f"JOIN {to_table} ON {from_table}.{from_column} = {to_table}.{to_column}"
            relation_lines.append(
                f"Relation: {from_table}.{from_column} -> {to_table}.{to_column} ({relation_type})\n"
                f"  Syntaxe JOIN: {join_example}"
            )

        relation_block = (
            "Relations déclarées (utilisez UNIQUEMENT celles-ci pour les JOINs):\n" + "\n\n".join(relation_lines)
            if relation_lines
            else "Aucune relation déclarée. Ne faites PAS de JOINs."
        )
    else:
        # NoSQL mode: no relations
        relation_block = "Mode NoSQL: PAS de JOINs. Les données liées sont imbriquées dans les documents."

    # En mode SQL : ne jamais utiliser les docs du vector store comme contexte (ils peuvent
    # contenir "Collection" et faire générer du NoSQL). Toujours utiliser le schéma du plugin (tables).
    if docs and current_mode != "sql":
        combined = "\n".join(docs)
        if relation_block:
            combined = f"{combined}\n\n{relation_block}"
        state["_retrieval_info"] = {
            "initial_k": initial_k,
            "final_k": len(docs),
            "reranker": rerank_stats,
        }
        return {"schema_context": combined}

    # 2. Fallback ou mode SQL : schéma issu du plugin uniquement (tables en SQL, collections en NoSQL)
    plugin = get_plugin_manager().get_plugin()
    schema_info = plugin.get_schema()
    schema = [
        {"name": t.name, "columns": [{"name": c.name, "type": c.type} for c in t.columns]} for t in schema_info.tables
    ]

    if not schema:
        return {"schema_context": "Aucune table/collection disponible."}

    # Score and rank tables by relevance to question
    scored_tables = [(_score_table_relevance(table, keywords), table) for table in schema]
    scored_tables.sort(reverse=True, key=lambda x: x[0])

    # Take top 3 most relevant tables (or all if less than 3)
    top_tables = scored_tables[:3]

    # Build context with only relevant tables
    context_lines = []
    for score, table in top_tables:
        table_name = table["name"]
        columns = table["columns"]
        # Include all columns for relevant tables
        col_descriptions = [f"{c['name']} ({c['type']})" for c in columns]
        context_lines.append(f"Table {table_name} colonnes: {', '.join(col_descriptions)}")

    # If no good matches, include at least one table
    if not top_tables or top_tables[0][0] == 0:
        # Include first table with all columns
        table = schema[0]
        col_descriptions = [f"{c['name']} ({c['type']})" for c in table["columns"]]
        context_lines = [f"Table {table['name']} colonnes: {', '.join(col_descriptions)}"]

    context = "\n".join(context_lines)
    if relation_block:
        context = f"{context}\n\n{relation_block}"

    return {"schema_context": context}


def _get_system_prompt() -> str:
    """Get the appropriate system prompt based on current database mode.

    Uses AGENTS.md + SKILL.md if configured, otherwise falls back to plugin prompt.
    """
    plugin = get_plugin_manager().get_plugin()
    fallback = plugin.get_system_prompt()
    return get_agent_system_prompt(mode=plugin.mode, plugin_fallback=fallback)


def _sql_generate(state: NLState) -> dict:
    timings = state.get("_timings", {})
    prompt = (
        f"[INSTRUCTIONS]\n{_get_system_prompt()}\n\n"
        f"[SCHEMA]\n{state['schema_context']}\n\n"
        f"[QUESTION]\n{state['question']}\n\n"
        f"[QUERY]"
    )

    reasoning_logger.info(
        "SQL Generation Prompt",
        extra={
            "extra_data": {
                "question": state["question"],
                "prompt": prompt,
                "schema_context": state["schema_context"],
                "step": "sql_generate",
            }
        },
    )

    t0 = time.perf_counter()
    raw = get_llm().invoke(prompt).content
    sql = extract_sql(raw)
    timings["sql_generate_ms"] = round((time.perf_counter() - t0) * 1000, 1)

    # En mode SQL : si le LLM a renvoyé du JSON, on le garde pour que la validation échoue puis _sql_correct donne un hint clair
    plugin = get_plugin_manager().get_plugin()
    if plugin.mode == "sql" and sql.lstrip().startswith("{"):
        reasoning_logger.info(
            "SQL Generation Rejected (JSON in SQL mode)",
            extra={"extra_data": {"question": state["question"], "raw_preview": sql[:200]}},
        )

    reasoning_logger.info(
        "SQL Generation Response",
        extra={"extra_data": {"question": state["question"], "sql_generated": sql, "step": "sql_generate_response"}},
    )

    return {"sql": sql}


def _sql_execute(state: NLState) -> dict:
    timings = state.get("_timings", {})
    sql = state["sql"]

    plugin = get_plugin_manager().get_plugin()
    is_valid, error_msg = plugin.validate_query(sql)
    if not is_valid:
        return {
            "rows": [],
            "error": f"[VALIDATION] {error_msg}",
            "attempts": state["attempts"] + 1,
        }

    try:
        t0 = time.perf_counter()
        plugin = get_plugin_manager().get_plugin()
        result = plugin.execute_query(sql)
        timings["sql_execute_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        if result.error:
            return {"rows": [], "error": result.error, "attempts": state["attempts"] + 1}
        return {"rows": result.rows, "error": ""}
    except Exception as exc:
        return {"rows": [], "error": str(exc), "attempts": state["attempts"] + 1}


def _categorize_error(error: str) -> str:
    """Categorize SQL error to provide targeted hints."""
    error_lower = error.lower()

    if "[validation]" in error_lower:
        return "La requête contient des opérations non autorisées. Utilise uniquement SELECT."
    elif "no such column" in error_lower:
        return "Vérifie que les noms de colonnes existent EXACTEMENT dans le schéma (respecte la casse snake_case)."
    elif "no such table" in error_lower:
        return "Vérifie que le nom de table existe dans le schéma."
    elif "parser error" in error_lower or "syntax error" in error_lower:
        return ("Erreur de syntaxe SQL. Causes fréquentes : "
                "1) Nom de colonne qui est un mot réservé SQL (at, order, group, date, type, key, value…) → encadre-le avec des guillemets doubles : \"at\", \"order\", \"type\". "
                "2) Alias avec espaces → utilise des underscores : `as nb_nulls` et non `as null values`. "
                "3) Virgules manquantes ou parenthèses non fermées. "
                "Corrige et retourne UNIQUEMENT la requête SQL.")
    elif "ambiguous column" in error_lower:
        return "Précise la table pour cette colonne (format: table.colonne)."
    elif "mismatched columns" in error_lower or "subquery" in error_lower:
        return "Vérifie que les sous-requêtes ont le même nombre de colonnes."
    elif "group by" in error_lower or "must appear in the group by" in error_lower or "aggregate function" in error_lower:
        return "ERREUR GROUP BY : chaque colonne du SELECT qui n'est PAS dans une fonction d'agrégation (SUM, COUNT, AVG, MIN, MAX) DOIT figurer dans la clause GROUP BY. Ajoute les colonnes manquantes au GROUP BY."
    else:
        return "Analyse l'erreur et corrige la requête en respectant strictement le schéma fourni."


def _sql_correct(state: NLState) -> dict:
    if not state["error"]:
        return {}

    timings = state.get("_timings", {})
    plugin = get_plugin_manager().get_plugin()
    if plugin.mode == "sql" and (state.get("sql") or "").strip().startswith("{"):
        hint = "En mode SQL tu dois générer UNIQUEMENT une requête SQL (SELECT ... FROM table ...). Pas de JSON, pas d'agrégation style MongoDB ($group, collection, etc.)."
    else:
        hint = _categorize_error(state["error"])

    prompt = (
        f"[INSTRUCTIONS]\n{_get_system_prompt()}\n\n"
        f"[CORRECTION]\n{hint}\n\n"
        f"[SCHEMA]\n{state['schema_context']}\n\n"
        f"[QUERY ERRONÉE]\n{state['sql']}\n\n"
        f"[ERREUR]\n{state['error']}\n\n"
        f"[QUERY CORRIGÉE]"
    )
    t0 = time.perf_counter()
    raw = get_llm().invoke(prompt).content
    sql = extract_sql(raw)
    timings["sql_correct_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return {"sql": sql}


_LLM_ROW_LIMIT = 20
_LLM_COL_LIMIT = 12


def _trim_rows_for_llm(rows: list[dict]) -> list[dict]:
    """Limit both rows and columns sent to the LLM to keep the prompt small."""
    if not rows:
        return rows
    preview = rows[:_LLM_ROW_LIMIT]
    keys = list(preview[0].keys())
    if len(keys) <= _LLM_COL_LIMIT:
        return preview
    kept = keys[:_LLM_COL_LIMIT]
    return [{k: row[k] for k in kept} for row in preview]


def _is_scalar_result(rows: list[dict]) -> bool:
    """Detect aggregation results (single row with count/sum/avg/min/max keys)."""
    if len(rows) != 1:
        return False
    keys = set(rows[0].keys())
    agg_prefixes = ("count", "sum_", "avg_", "min_", "max_")
    return all(any(k.startswith(p) or k == p for p in agg_prefixes) for k in keys)


def _format_scalar_answer(rows: list[dict], question: str) -> str:
    """Format a simple aggregation result without calling the LLM."""

    row = rows[0]

    def format_value(value):
        if isinstance(value, float) and value == int(value):
            value = int(value)
        if isinstance(value, (int, float)):
            return f"{value:,}".replace(",", " ")
        return str(value)

    def clean_label(key):
        # Clean up aggregation prefixes and make readable
        label = key.replace("_", " ")
        # Remove aggregation prefixes like "sum_", "avg_", "count_", "min_", "max_"
        for prefix in ["sum ", "avg ", "count ", "min ", "max "]:
            if label.lower().startswith(prefix):
                label = label[len(prefix) :]
                break
        return label.strip()

    if len(row) == 1:
        key, value = next(iter(row.items()))
        formatted = format_value(value)
        label = clean_label(key)

        # Format as a nice sentence
        if "total" in question.lower() or "somme" in question.lower() or "sum" in key.lower():
            return f"**{formatted}** {label} (total)"
        elif "moyenne" in question.lower() or "avg" in key.lower():
            return f"**{formatted}** {label} (moyenne)"
        elif "nombre" in question.lower() or "count" in key.lower():
            return f"**{formatted}** {label}"
        else:
            return f"**{formatted}** {label}"

    # Multiple values - format as a nice list
    parts = []
    for key, value in row.items():
        formatted = format_value(value)
        label = clean_label(key)
        parts.append(f"- **{label}** : {formatted}")
    return "\n".join(parts)


def _response(state: NLState) -> dict:
    rows = state["rows"]
    if not rows:
        return {
            "answer": (
                "Aucun résultat trouvé pour votre question. "
                "Vérifiez qu'il existe des données correspondantes ou ajustez les filtres."
            )
        }

    timings = state.get("_timings", {})

    # Fast path: scalar aggregation results (count, sum…) → no LLM call needed
    if _is_scalar_result(rows):
        t0 = time.perf_counter()
        answer = _format_scalar_answer(rows, state["question"])
        timings["response_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return {"answer": answer}

    total_rows = len(rows)
    total_cols = len(rows[0]) if rows else 0
    preview = _trim_rows_for_llm(rows)
    preview_cols = len(preview[0]) if preview else 0

    notes: list[str] = []
    if total_rows > _LLM_ROW_LIMIT:
        notes.append(f"{total_rows} résultats au total, seuls les {_LLM_ROW_LIMIT} premiers sont montrés")
    if total_cols > _LLM_COL_LIMIT:
        notes.append(f"{total_cols} colonnes au total, seules les {preview_cols} plus pertinentes sont montrées")
    truncation_note = ("\nNote: " + ". ".join(notes) + ".") if notes else ""

    memory = load_memory()
    personality = f"{memory}\n\n" if memory else ""

    if total_rows <= 3 and total_cols <= 2:
        prompt = (
            f"{personality}"
            "Réponds en français à partir des résultats.\n"
            "Pour ce résultat simple, donne une réponse concise en UNE PHRASE.\n"
            "Ne mets PAS de tableau markdown. Formate les nombres avec espaces.\n"
            "Exemple: 'Le total est de **1 234** heures.' ou 'Il y a **56** résultats.'\n"
            f"{truncation_note}\n\n"
            f"Question: {state['question']}\n"
            f"Résultats (JSON): {json.dumps(preview, ensure_ascii=False)}\n"
            "Réponse (une phrase, avec le nombre en gras):"
        )
    else:
        prompt = (
            f"{personality}"
            "Réponds en français à partir des résultats.\n"
            "Présente les résultats sous forme de TABLEAU MARKDOWN PROFESSIONNEL.\n\n"
            "RÈGLES STRICTES DE FORMATAGE:\n\n"
            "1. **NOMS DE COLONNES (TRADUCTION OBLIGATOIRE):**\n"
            "   - sum_ → 'Total' ou 'Total [champ]'\n"
            "   - avg_ → 'Moyenne' ou 'Moyenne [champ]'\n"
            "   - count_ → 'Nombre' ou 'Nb [champ]'\n"
            "   - min_ → 'Min'\n"
            "   - max_ → 'Max'\n"
            "   - underscore_ → espace\n"
            "   - Exemple: 'sum_Nombre d'heures' → 'Total heures'\n\n"
            "2. **FORMAT DES NOMBRES:**\n"
            "   - Espaces comme séparateurs de milliers: 2 950 379\n"
            "   - Virgule pour les décimales: 75,00\n"
            "   - Aligner à droite dans les cellules\n\n"
            "3. **PAS DE TIRETS ENTRE LES VALEURS:**\n"
            "   - Utilise uniquement des espaces comme séparateurs\n"
            "   - Jamais de underscore (_) dans l'affichage\n\n"
            "EXEMPLE CORRECT:\n"
            "| OT        | Total heures |\n"
            "|-----------|-------------:|\n"
            "| 2 950 379 |        75,00 |\n\n"
            f"{truncation_note}\n\n"
            f"Question: {state['question']}\n"
            f"Résultats (JSON): {json.dumps(preview, ensure_ascii=False)}\n"
            "Réponse (tableau propre, sans underscores, noms traduits):"
        )
    t0 = time.perf_counter()
    answer = strip_thinking(get_llm().invoke(prompt).content)
    timings["response_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return {"answer": answer}


def build_graph():
    builder = StateGraph(NLState)
    builder.add_node("route", _route)
    builder.add_node("schema_context", _schema_context)
    builder.add_node("sql_generate", _sql_generate)
    builder.add_node("sql_execute", _sql_execute)
    builder.add_node("sql_correct", _sql_correct)
    builder.add_node("response", _response)

    builder.add_edge(START, "route")
    builder.add_conditional_edges("route", _route_next)
    builder.add_edge("schema_context", "sql_generate")
    builder.add_edge("sql_generate", "sql_execute")

    def _next_after_execute(state: NLState) -> Literal["sql_correct", "response"]:
        if state["error"] and state["attempts"] < 2:
            return "sql_correct"
        return "response"

    builder.add_conditional_edges("sql_execute", _next_after_execute)
    builder.add_edge("sql_correct", "sql_execute")
    builder.add_edge("response", END)

    return builder.compile()


_compiled_graph = build_graph()


def _run_nl_sql_internal(question: str) -> dict:
    """Internal function to run NL-SQL without caching."""
    timings: dict[str, float] = {}
    result = _compiled_graph.invoke(
        {
            "question": question,
            "route": "",
            "schema_context": "",
            "sql": "",
            "error": "",
            "rows": [],
            "answer": "",
            "attempts": 0,
            "_timings": timings,
        }
    )
    return {
        "answer": result["answer"],
        "sql": result["sql"],
        "rows": result["rows"],
        "_timings": timings,
    }


def run_nl_sql(question: str, use_cache: bool = True) -> dict:
    """Run NL-SQL query with optional caching.

    Args:
        question: Natural language question
        use_cache: Whether to use cache (default: True)

    Returns:
        dict with answer, sql, rows, and _cache_hit indicator
    """
    start_time = time.time()

    # Log user input
    log_user_input(question)

    if not use_cache:
        result = _run_nl_sql_internal(question)
        result["_cache_hit"] = False
        # Log performance
        total_time = (time.time() - start_time) * 1000
        monitor.record("query", total_time)
        return result

    # Use cached schema hash to avoid re-serializing on every call
    cached_hash = schema_cache.get("_schema_hash")
    if cached_hash is None:
        plugin = get_plugin_manager().get_plugin()
        schema_info = plugin.get_schema()
        schema = [
            {"name": t.name, "columns": [{"name": c.name, "type": c.type} for c in t.columns]}
            for t in schema_info.tables
        ]
        cached_hash = hash_schema(schema)
        schema_cache.set("_schema_hash", cached_hash)
    cache_key = hash_question(question, cached_hash)

    # Try cache
    cached = nl_sql_cache.get(cache_key)
    if cached is not None:
        cached["_cache_hit"] = True
        total_time = (time.time() - start_time) * 1000
        monitor.record("query", total_time)
        log_user_input(f"[CACHE HIT] {question}")
        return cached

    result = _run_nl_sql_internal(question)
    total_time = (time.time() - start_time) * 1000
    step_timings = result.get("_timings", {})

    if result.get("sql") and not result.get("error"):
        result_copy = result.copy()
        result_copy.pop("_timings", None)
        result_copy["_cached_at"] = json.dumps({"schema_hash": cached_hash})
        nl_sql_cache.set(cache_key, result_copy)

    result["_cache_hit"] = False

    monitor.record("query", total_time)
    for step_name, step_ms in step_timings.items():
        monitor.record(step_name, step_ms)

    log_entry = QueryLogEntry(
        timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
        user_input=question,
        schema_context="",
        sql_generated=result.get("sql", ""),
        sql_valid=not bool(result.get("error")),
        execution_time_ms=total_time,
        total_time_ms=total_time,
        rows_count=len(result.get("rows", [])),
        cache_hit=False,
        error=result.get("error") if result.get("error") else None,
        retrieval_info=step_timings,
    )
    log_query_complete(log_entry)

    return result


# ═══════════════════════════════════════════════════════════════════════
# Streaming version — yields SSE events with thinking + pipeline status
# ═══════════════════════════════════════════════════════════════════════

from collections.abc import Generator as Gen


def run_nl_sql_stream(question: str) -> Gen[dict, None, None]:
    """Streaming NL-SQL pipeline.  Yields dicts suitable for SSE encoding:

    ``{"event": "status",   "data": "Recherche du contexte…"}``
    ``{"event": "thinking", "data": "token de raisonnement"}``
    ``{"event": "content",  "data": "token de réponse brute"}``
    ``{"event": "answer",   "data": {… QueryResponse final …}}``
    ``{"event": "error",    "data": "message d'erreur"}``
    """
    log_user_input(question)
    t_start = time.time()
    timings: dict[str, float] = {}

    try:
        streamed_thinking_parts: list[str] = []
        used_correction = False
        retrieved_doc_count = 0

        # 1. Route
        yield {"event": "status", "data": "Analyse de la question…"}
        plugin = get_plugin_manager().get_plugin()
        route = plugin.mode  # sql or nosql

        # 2. Schema context
        yield {"event": "status", "data": "Recherche du contexte schéma…"}
        t0 = time.perf_counter()
        initial_k = int(os.getenv("NDI_RETRIEVAL_K", "10"))
        docs = query_documents(question, k=initial_k)

        if docs:
            reranked, _, rerank_stats = rerank_documents(
                query=question,
                documents=docs,
                top_k=settings.retrieval_top_k,
                use_reranker=settings.use_reranker,
            )
            timings["retrieval_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        else:
            reranked = []
            timings["retrieval_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        retrieved_doc_count = len(reranked)

        schema_context = plugin.get_query_context(question, reranked)

        # 3. SQL/NoSQL generation — STREAM this step
        yield {"event": "status", "data": "Génération de la requête…"}
        prompt = (
            f"[INSTRUCTIONS]\n{_get_system_prompt()}\n\n"
            f"[SCHEMA]\n{schema_context}\n\n"
            f"[QUESTION]\n{question}\n\n"
            f"[QUERY]"
        )

        t0 = time.perf_counter()
        content_parts: list[str] = []
        for event_type, chunk in stream_llm_call(prompt):
            yield {"event": event_type, "data": chunk}
            if event_type == "thinking":
                streamed_thinking_parts.append(chunk)
            if event_type == "content":
                content_parts.append(chunk)

        raw_sql = extract_sql("".join(content_parts))
        timings["sql_generate_ms"] = round((time.perf_counter() - t0) * 1000, 1)

        # 4. Validate
        yield {"event": "status", "data": "Validation de la requête…"}
        is_valid, validation_error = plugin.validate_query(raw_sql)

        # 5. Correction if needed
        if not is_valid:
            used_correction = True
            yield {"event": "status", "data": "Correction de la requête…"}
            correction_prompt = (
                f"[INSTRUCTIONS]\n{_get_system_prompt()}\n\n"
                f"[SCHEMA]\n{schema_context}\n\n"
                f"[QUESTION]\n{question}\n\n"
                f"[ERREUR]\n{validation_error}\n\n"
                f"[QUERY CORRIGÉE]"
            )
            t0 = time.perf_counter()
            corrected_parts: list[str] = []
            for event_type, chunk in stream_llm_call(correction_prompt):
                yield {"event": event_type, "data": chunk}
                if event_type == "thinking":
                    streamed_thinking_parts.append(chunk)
                if event_type == "content":
                    corrected_parts.append(chunk)
            raw_sql = extract_sql("".join(corrected_parts))
            timings["sql_correct_ms"] = round((time.perf_counter() - t0) * 1000, 1)

            is_valid, validation_error = plugin.validate_query(raw_sql)
            if not is_valid:
                yield {
                    "event": "answer",
                    "data": {
                        "answer": (
                            "Je n'ai pas pu transformer votre message en requête exploitable. "
                            "Posez directement une question sur les données, par exemple : "
                            "\"combien de lignes\", \"montre les 10 premières lignes\" ou "
                            "\"quelles sont les valeurs distinctes de la colonne statut ?\""
                        ),
                        "query": raw_sql,
                        "query_type": "sql" if plugin.mode == "sql" else "nosql",
                        "rows": [],
                        "row_count": 0,
                        "question_type": "explanation",
                        "confidence": 1.0,
                        "thinking": (
                            "".join(streamed_thinking_parts).strip()
                            or (
                                f"Mode: {route.upper()}\n"
                                f"Contexte schéma consulté: {retrieved_doc_count} document(s)\n"
                                "La requête générée est restée invalide après tentative de correction."
                            )
                        ),
                        "_timings": timings,
                    },
                }
                return

        # 6. Execute
        yield {"event": "status", "data": "Exécution de la requête…"}
        t0 = time.perf_counter()
        exec_result = plugin.execute_query(raw_sql)
        timings["sql_execute_ms"] = round((time.perf_counter() - t0) * 1000, 1)

        rows = exec_result.rows or []
        error = exec_result.error

        # 7. Response formatting — STREAM this step
        if rows and not error:
            yield {"event": "status", "data": "Mise en forme de la réponse…"}
            preview = rows[:20]
            resp_prompt = (
                f"Question: {question}\n"
                f"Résultats (JSON): {json.dumps(preview, ensure_ascii=False)}\n"
                "Réponse (tableau propre, sans underscores, noms traduits):"
            )
            t0 = time.perf_counter()
            answer_parts: list[str] = []
            for event_type, chunk in stream_llm_call(resp_prompt):
                yield {"event": event_type, "data": chunk}
                if event_type == "thinking":
                    streamed_thinking_parts.append(chunk)
                if event_type == "content":
                    answer_parts.append(chunk)
            answer = "".join(answer_parts).strip()
            timings["response_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        elif error:
            answer = f"Erreur lors de l'exécution : {error}"
        else:
            answer = "La requête n'a retourné aucun résultat."

        fallback_thinking = (
            f"Mode: {route.upper()}\n"
            f"Contexte schéma consulté: {retrieved_doc_count} document(s)\n"
            f"Validation: {'requête corrigée avant exécution' if used_correction else 'requête valide du premier coup'}\n"
            f"Résultat: {'erreur d’exécution' if error else f'{len(rows)} ligne(s) retournée(s)'}"
        )

        total_ms = round((time.time() - t_start) * 1000, 1)
        monitor.record("query", total_ms)

        # 8. Final answer
        yield {
            "event": "answer",
            "data": {
                "answer": answer,
                "sql": raw_sql,
                "query": raw_sql,
                "query_type": "sql" if plugin.mode == "sql" else "nosql",
                "rows": rows,
                "row_count": len(rows),
                "question_type": "query",
                "confidence": 1.0,
                "thinking": "".join(streamed_thinking_parts).strip() or fallback_thinking,
                "_timings": timings,
            },
        }

    except Exception as e:
        yield {"event": "error", "data": str(e)}
