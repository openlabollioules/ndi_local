"""Conversation memory management for contextual follow-up questions.

This module provides short-term memory for conversational AI,
allowing users to ask follow-up questions about previous results.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


@dataclass
class ConversationMessage:
    """A single message in the conversation."""

    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    thinking: str | None = None
    # Optional metadata
    query: str | None = None  # SQL/NoSQL generated
    query_type: Literal["sql", "nosql"] | None = None
    results_summary: str | None = None  # Truncated results summary
    results_count: int | None = None
    analysis: str | None = None  # Analysis performed
    intent: str | None = None  # detected intent: query, follow_up, analysis


@dataclass
class PendingTableData:
    """Table data extracted from an image, waiting for user confirmation to ingest."""

    csv_content: str
    columns: list[str]
    row_count: int
    source_filename: str
    extracted_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ConversationSession:
    """A conversation session with history."""

    id: str
    messages: list[ConversationMessage] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)
    pending_table: PendingTableData | None = None

    def add_message(self, message: ConversationMessage) -> None:
        """Add a message and update activity timestamp."""
        self.messages.append(message)
        self.last_activity = datetime.utcnow()

    def get_recent_context(self, last_n: int = 3) -> list[ConversationMessage]:
        """Get the N most recent messages."""
        return self.messages[-last_n:] if len(self.messages) <= last_n else self.messages[-last_n:]

    def get_last_query_result(self) -> dict | None:
        """Get the last query result for follow-up questions."""
        for msg in reversed(self.messages):
            if msg.role == "assistant" and msg.query:
                return {
                    "query": msg.query,
                    "query_type": msg.query_type,
                    "results_summary": msg.results_summary,
                    "results_count": msg.results_count,
                }
        return None

    def get_last_results_context(self, max_chars: int = 2000) -> str:
        """Get formatted context of last results for the LLM."""
        last_result = self.get_last_query_result()
        if not last_result:
            return ""

        context_parts = [
            f"Dernière requête ({last_result['query_type']}):",
            f"```\n{last_result['query']}\n```",
        ]

        if last_result["results_summary"]:
            summary = last_result["results_summary"]
            if len(summary) > max_chars:
                summary = summary[:max_chars] + "...\n[Données tronquées]"
            context_parts.append(f"Résultats ({last_result['results_count']} lignes):\n{summary}")

        return "\n\n".join(context_parts)

    def format_for_prompt(self, last_n: int = 3) -> str:
        """Format recent messages for inclusion in LLM prompt."""
        recent = self.get_recent_context(last_n)
        lines = []
        for msg in recent:
            prefix = "Utilisateur" if msg.role == "user" else "Assistant"
            lines.append(f"{prefix}: {msg.content}")
        return "\n".join(lines)

    def should_summarize(self, max_messages: int = 10) -> bool:
        """Check if old messages should be summarized."""
        return len(self.messages) > max_messages

    def summarize_old_messages(self) -> None:
        """Summarize older messages to save context space."""
        # Keep last 5 messages, summarize the rest
        if len(self.messages) <= 5:
            return

        to_summarize = self.messages[:-5]
        keep = self.messages[-5:]

        # Create summary of older conversation
        summary_content = f"[Résumé des {len(to_summarize)} messages précédents: "

        # Extract key queries and analyses
        queries = [m for m in to_summarize if m.query]
        analyses = [m for m in to_summarize if m.analysis]

        if queries:
            summary_content += f"{len(queries)} requêtes effectuées. "
        if analyses:
            summary_content += f"{len(analyses)} analyses réalisées."

        summary_content += "]"

        summary_msg = ConversationMessage(role="system", content=summary_content, intent="summary")

        self.messages = [summary_msg] + keep


class ConversationMemoryStore:
    """In-memory store for conversation sessions."""

    def __init__(self, max_sessions: int = 100, ttl_hours: int = 24):
        self._sessions: dict[str, ConversationSession] = {}
        self.max_sessions = max_sessions
        self.ttl_hours = ttl_hours

    # ── public API ────────────────────────────────────────────────────

    def create_session(self, session_id: str | None = None) -> ConversationSession:
        """Create a new conversation session."""
        if session_id is None:
            session_id = str(uuid.uuid4())[:8]

        session = ConversationSession(id=session_id)
        self._sessions[session_id] = session
        self._cleanup()
        return session

    def get_session(self, session_id: str) -> ConversationSession | None:
        """Get an existing session or None."""
        session = self._sessions.get(session_id)
        if session:
            age = datetime.utcnow() - session.last_activity
            if age.total_seconds() > self.ttl_hours * 3600:
                del self._sessions[session_id]
                return None
        return session

    def get_or_create(self, session_id: str | None) -> tuple[ConversationSession, bool]:
        """Get existing session or create new one. Returns (session, is_new)."""
        self._purge_expired()
        if session_id:
            session = self.get_session(session_id)
            if session:
                return session, False
        return self.create_session(session_id), True

    def delete_session(self, session_id: str) -> bool:
        """Delete a session. Returns True if existed."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def list_sessions(self) -> list[dict]:
        """List all active sessions with metadata."""
        self._purge_expired()
        return [
            {
                "id": s.id,
                "message_count": len(s.messages),
                "created_at": s.created_at.isoformat(),
                "last_activity": s.last_activity.isoformat(),
            }
            for s in self._sessions.values()
        ]

    def clear_all(self) -> int:
        """Clear all sessions. Returns count cleared."""
        count = len(self._sessions)
        self._sessions.clear()
        return count

    # ── internal cleanup ──────────────────────────────────────────────

    def _purge_expired(self) -> int:
        """Remove all sessions whose last_activity exceeds the TTL.

        Called opportunistically on ``get_or_create`` and ``list_sessions``.
        Returns the number of sessions purged.
        """
        now = datetime.utcnow()
        ttl_seconds = self.ttl_hours * 3600
        expired = [sid for sid, s in self._sessions.items() if (now - s.last_activity).total_seconds() > ttl_seconds]
        for sid in expired:
            del self._sessions[sid]
        return len(expired)

    def _cleanup(self) -> None:
        """Evict oldest sessions when max_sessions is exceeded."""
        self._purge_expired()
        if len(self._sessions) <= self.max_sessions:
            return
        sorted_sessions = sorted(
            self._sessions.values(),
            key=lambda s: s.last_activity,
        )
        to_remove = len(sorted_sessions) - self.max_sessions
        for session in sorted_sessions[:to_remove]:
            del self._sessions[session.id]


# Global store instance
conversation_store = ConversationMemoryStore()


def get_conversation_store() -> ConversationMemoryStore:
    """Get the global conversation store."""
    return conversation_store
