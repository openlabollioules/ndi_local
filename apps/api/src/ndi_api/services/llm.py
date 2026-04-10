"""LLM service — OpenAI-compatible client (vLLM, etc.)

Replaces the previous Ollama-specific implementation with the standard
OpenAI client via ``langchain-openai``.  Any server exposing
``/v1/chat/completions``, ``/v1/completions``, and ``/v1/embeddings``
is supported (vLLM, TGI, LiteLLM, OpenAI, …).
"""

from __future__ import annotations

import logging
import re

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from ndi_api.settings import settings

logger = logging.getLogger(__name__)

# Strip reasoning/thinking blocks emitted by reasoning models (Qwen3, DeepSeek, etc.)
# Pattern 1: <think>…</think> or Thinking Process:…</think>
_THINK_RE = re.compile(
    r"(?:<think>|[Tt]hinking\s*[Pp]rocess\s*:?).*?</think>\s*",
    re.DOTALL,
)

# Dangerous HTML tags that should never appear in LLM output
_DANGEROUS_HTML_RE = re.compile(
    r"<\s*/?\s*(?:iframe|script|object|embed|form|input|link|meta|style|base|applet)\b[^>]*>",
    re.IGNORECASE,
)


def strip_dangerous_html(text: str) -> str:
    """Remove dangerous HTML tags (iframe, script, etc.) from LLM output."""
    cleaned = _DANGEROUS_HTML_RE.sub("", text)
    if cleaned != text:
        logger.warning("Stripped dangerous HTML from LLM output")
    return cleaned


def strip_thinking(text: str) -> str:
    """Remove chain-of-thought / thinking blocks from LLM output.

    Handles multiple formats:
    - ``<think>…</think>``
    - ``Thinking Process:…</think>``
    - No opening tag but ``</think>`` present → everything before it is reasoning
    """
    # Standard tagged blocks
    cleaned = _THINK_RE.sub("", text)

    # Fallback: </think> without opening tag — strip everything before it
    if "</think>" in cleaned:
        cleaned = cleaned.split("</think>")[-1]

    # Always strip dangerous HTML from LLM output
    cleaned = strip_dangerous_html(cleaned)

    return cleaned.strip()


_SQL_KEYWORDS = {
    "select", "from", "where", "group", "order", "having", "limit",
    "join", "left", "right", "inner", "outer", "on", "and", "or",
    "as", "by", "in", "is", "not", "null", "between", "like", "ilike",
    "case", "when", "then", "else", "end", "with", "union", "distinct",
    "count", "sum", "avg", "min", "max", "over", "partition",
}


def _fix_sql_aliases(sql: str) -> str:
    """Fix SQL aliases that contain spaces (e.g. 'as null values' → 'as null_values').

    Only joins words that are NOT SQL keywords, to avoid merging
    'as colonne FROM table' into 'as colonne_FROM_table'.
    """
    def _replace_alias(m: re.Match) -> str:
        word1 = m.group(1)
        word2 = m.group(2)
        # Don't merge if the second word is a SQL keyword
        if word2.lower() in _SQL_KEYWORDS:
            return m.group(0)  # leave unchanged
        return f" as {word1}_{word2}"

    # Match: AS <word> <word> — exactly two non-keyword words
    return re.sub(
        r"\bas\s+([a-zA-Z_]\w*)\s+([a-zA-Z_]\w*)(?=\s*(?:,|\bFROM\b|\bGROUP\b|\bORDER\b|\bHAVING\b|\bWHERE\b|\bLIMIT\b|\)|$))",
        _replace_alias,
        sql,
        flags=re.IGNORECASE,
    )


def extract_sql(text: str) -> str:
    """Extract SQL from LLM response that may contain reasoning/explanation.

    Handles cases where the model outputs natural language before/after the SQL.
    Falls back to the full text if no SQL is found.
    """
    cleaned = strip_thinking(text)

    # 1. Try markdown code block (```sql ... ``` or ``` ... ```)
    code_match = re.search(r"```(?:sql)?\s*\n?(.*?)```", cleaned, re.DOTALL | re.IGNORECASE)
    if code_match:
        return _fix_sql_aliases(code_match.group(1).strip())

    # 2. Try to find SELECT/WITH statement in the text
    sql_match = re.search(
        r"((?:WITH\s+\w+\s+AS\s*\(|SELECT\s+).*?)(?:\n\n|\Z)",
        cleaned,
        re.DOTALL | re.IGNORECASE,
    )
    if sql_match:
        return _fix_sql_aliases(sql_match.group(1).strip().rstrip(";").strip())

    # 3. Try JSON object (for NoSQL mode)
    json_match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
    if json_match:
        return json_match.group(1).strip()

    # 4. Fallback: return cleaned text as-is
    return cleaned


_current_model: str | None = None
_llm_instance: ChatOpenAI | None = None
_llm_model_key: str | None = None
_embeddings_instance: OpenAIEmbeddings | None = None


def _release_llm(instance: ChatOpenAI | None) -> None:
    """Best-effort cleanup of an old LLM instance."""
    if instance is None:
        return
    try:
        if hasattr(instance, "client") and hasattr(instance.client, "close"):
            instance.client.close()
    except Exception:
        pass
    del instance


# Regex to detect the opening of a thinking block
_THINK_OPEN_RE = re.compile(r"(?:<think>|[Tt]hinking\s*[Pp]rocess\s*:?)")
_THINK_CLOSE = "</think>"

# Regex to detect start of actual content (SQL, JSON, or markdown table)
_CONTENT_START_RE = re.compile(r"^\s*(?:SELECT\b|WITH\b|\{|\|)", re.IGNORECASE)

# Maximum bytes to buffer before deciding if this is thinking or content.
_DETECT_WINDOW = 30

from collections.abc import Generator
from typing import Literal

StreamEventType = Literal["thinking", "content"]
StreamEvent = tuple[StreamEventType, str]


def stream_llm_call(prompt: str, llm: ChatOpenAI | None = None) -> Generator[StreamEvent, None, str]:
    """Stream an LLM call, separating thinking blocks from content.

    Yields ``("thinking", chunk)`` while inside a ``<think>`` block,
    then ``("content", chunk)`` for the actual answer.
    """
    if llm is None:
        llm = get_llm()

    # Phase 1: accumulate tokens until we can decide thinking vs content
    detect_buf = ""
    detected = False
    in_thinking = False
    content_parts: list[str] = []

    token_iter = iter(llm.stream(prompt))

    # --- detection phase: buffer up to _DETECT_WINDOW chars ----------------
    for chunk in token_iter:
        token = chunk.content if hasattr(chunk, "content") else str(chunk)
        if not token:
            continue
        detect_buf += token

        # Can we decide yet?
        if _THINK_OPEN_RE.search(detect_buf):
            # It's a thinking block — strip the opening tag and enter thinking mode
            in_thinking = True
            detected = True
            leftover = _THINK_OPEN_RE.sub("", detect_buf, count=1)
            if leftover.strip():
                yield ("thinking", leftover)
            break

        if len(detect_buf) >= _DETECT_WINDOW:
            detected = True
            if _CONTENT_START_RE.match(detect_buf):
                # Starts with SQL/JSON/table — it's content
                content_parts.append(detect_buf)
                yield ("content", detect_buf)
            else:
                # Starts with natural language — treat as thinking without opening tag
                # (model will hopefully emit </think> later)
                in_thinking = True
                yield ("thinking", detect_buf)
            break

    # If stream ended during detection and we never decided:
    if not detected:
        if _THINK_OPEN_RE.search(detect_buf):
            in_thinking = True
            leftover = _THINK_OPEN_RE.sub("", detect_buf, count=1)
            if leftover.strip():
                yield ("thinking", leftover)
        elif detect_buf:
            if _CONTENT_START_RE.match(detect_buf):
                content_parts.append(detect_buf)
                yield ("content", detect_buf)
            else:
                # Short response, no SQL — treat as thinking
                yield ("thinking", detect_buf)
            yield ("content", detect_buf)
        return "".join(content_parts).strip()

    # --- streaming phase: we know whether we're in thinking or content -----
    buf = ""
    for chunk in token_iter:
        token = chunk.content if hasattr(chunk, "content") else str(chunk)
        if not token:
            continue

        if in_thinking:
            buf += token
            # Check for closing tag
            close_idx = buf.find(_THINK_CLOSE)
            if close_idx >= 0:
                # Yield thinking before </think>
                thinking_part = buf[:close_idx]
                if thinking_part:
                    yield ("thinking", thinking_part)
                # Switch to content
                in_thinking = False
                remaining = buf[close_idx + len(_THINK_CLOSE) :]
                buf = ""
                if remaining.strip():
                    content_parts.append(remaining)
                    yield ("content", remaining)
            elif _CONTENT_START_RE.search(buf):
                # No </think> but we see SQL/JSON — model doesn't use closing tags.
                # Split: everything before the SQL keyword is thinking, rest is content.
                sql_match = re.search(r"(?:SELECT\b|WITH\b|\{|\|)", buf, re.IGNORECASE)
                if sql_match:
                    thinking_part = buf[: sql_match.start()]
                    if thinking_part.strip():
                        yield ("thinking", thinking_part)
                    content_start = buf[sql_match.start() :]
                    content_parts.append(content_start)
                    yield ("content", content_start)
                    in_thinking = False
                    buf = ""
            else:
                # Yield thinking as it arrives (but keep last few chars in case
                # "</think>" is split across chunks)
                safe = len(buf) - len(_THINK_CLOSE)
                if safe > 0:
                    yield ("thinking", buf[:safe])
                    buf = buf[safe:]
        else:
            # Pure content — yield immediately
            content_parts.append(token)
            yield ("content", token)

    # Flush anything remaining
    if buf:
        if in_thinking:
            # Thinking never closed — check if there's SQL content in the buffer
            sql_match = re.search(r"(SELECT\b|WITH\b\s+\w+\s+AS)", buf, re.IGNORECASE)
            if sql_match:
                thinking_part = buf[: sql_match.start()]
                if thinking_part.strip():
                    yield ("thinking", thinking_part)
                content_part = buf[sql_match.start() :]
                content_parts.append(content_part)
                yield ("content", content_part)
            else:
                cleaned = buf.replace("</think>", "").replace("</thin", "").replace("</thi", "")
                if cleaned.strip():
                    yield ("thinking", cleaned)
        else:
            content_parts.append(buf)
            yield ("content", buf)

    return "".join(content_parts).strip()


# ── Model selection ──────────────────────────────────────────────────


def get_current_model() -> str:
    return _current_model if _current_model else settings.llm_model


def set_current_model(model: str) -> None:
    global _current_model, _llm_instance, _llm_model_key
    old = _llm_instance
    _current_model = model
    _llm_instance = None
    _llm_model_key = None
    _release_llm(old)
    logger.info("LLM model switched to %s", model)


def reset_current_model() -> None:
    global _current_model, _llm_instance, _llm_model_key
    old = _llm_instance
    _current_model = None
    _llm_instance = None
    _llm_model_key = None
    _release_llm(old)
    logger.info("LLM model reset to default (%s)", settings.llm_model)


# ── LLM instances ───────────────────────────────────────────────────


def get_llm() -> ChatOpenAI:
    """Primary LLM for query generation (chat completions)."""
    global _llm_instance, _llm_model_key
    model = get_current_model()
    if _llm_instance is None or _llm_model_key != model:
        old = _llm_instance
        _llm_instance = ChatOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=model,
            max_tokens=None,  # let the server decide based on context
            default_headers={"Accept": "application/json"},
        )
        _llm_model_key = model
        _release_llm(old)
    return _llm_instance


_indexing_llm_instance: ChatOpenAI | None = None


def get_indexing_llm() -> ChatOpenAI:
    """LLM dédié à l'indexation (descriptions de colonnes).

    Utilise ``NDI_INDEXING_LLM_MODEL`` si défini, sinon le modèle principal.
    """
    global _indexing_llm_instance
    model = settings.indexing_llm_model or settings.llm_model
    if _indexing_llm_instance is None or _indexing_llm_instance.model_name != model:
        old = _indexing_llm_instance
        _indexing_llm_instance = ChatOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=model,
            max_tokens=None,  # let the server decide based on context
            default_headers={"Accept": "application/json"},
        )
        _release_llm(old)
    return _indexing_llm_instance


# ── Embeddings ───────────────────────────────────────────────────────


def get_embeddings() -> OpenAIEmbeddings:
    """Embeddings via OpenAI-compatible ``/v1/embeddings`` endpoint."""
    global _embeddings_instance
    if _embeddings_instance is None:
        _embeddings_instance = OpenAIEmbeddings(
            base_url=settings.effective_embedding_base_url,
            api_key=settings.effective_embedding_api_key,
            model=settings.embedding_model,
            check_embedding_ctx_length=False,  # skip tiktoken download
            default_headers={"Accept": "application/json"},
        )
    return _embeddings_instance


# ── Vision LLM ───────────────────────────────────────────────────────

_vision_llm_instance: ChatOpenAI | None = None


def get_vision_llm() -> ChatOpenAI:
    """LLM dédié à l'analyse d'images (vision).

    Utilise ``NDI_VISION_MODEL`` si défini, sinon le modèle principal.
    Compatible avec tout serveur exposant ``/v1/chat/completions`` avec
    support des messages multimodaux (image_url).
    """
    global _vision_llm_instance
    model = settings.vision_model or settings.llm_model
    if _vision_llm_instance is None or _vision_llm_instance.model_name != model:
        old = _vision_llm_instance
        _vision_llm_instance = ChatOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=model,
            max_tokens=None,  # let the server decide based on context
            default_headers={"Accept": "application/json"},
        )
        _release_llm(old)
    return _vision_llm_instance
