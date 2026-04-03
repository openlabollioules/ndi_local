"""Agent prompts loader - Load memory (AGENTS.md) and skills (SKILL.md) from filesystem.

Architecture:
- AGENTS.md: Global memory / persona (always loaded)
- SKILL.md: Mode-specific skills (dynamically loaded based on SQL/NoSQL mode)
- ndi_api.skills.*: Structured skill modules with schemas, tools, and routing
- Fallback chain: SKILL.md → SkillBase._inline_prompt() → plugin_fallback
"""

from __future__ import annotations

import functools
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ndi_api.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class Skill:
    """Parsed skill with frontmatter metadata."""

    name: str
    description: str
    version: str | None
    content: str  # Without frontmatter


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from markdown content.

    Returns:
        (metadata_dict, body_without_frontmatter)
    """
    metadata = {}

    if not content.startswith("---"):
        return metadata, content

    # Find the end of frontmatter
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)", content, re.DOTALL)
    if not match:
        return metadata, content

    frontmatter = match.group(1)
    body = match.group(2).strip()

    # Simple YAML parsing (key: value)
    for line in frontmatter.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip().strip("\"'")  # Remove quotes if present
            metadata[key] = value

    return metadata, body


def _get_agents_base_dir() -> Path | None:
    """Get the base directory for agent files.

    Returns None if not configured or doesn't exist.
    """
    if not settings.agents_base_dir:
        return None

    path = Path(settings.agents_base_dir)
    if not path.is_absolute():
        # Relative to api directory (apps/api/)
        # __file__ is in apps/api/src/ndi_api/services/, so go up 3 levels to apps/api/
        api_dir = Path(__file__).parent.parent.parent.parent
        path = api_dir / path

    if not path.exists():
        return None

    return path


@functools.lru_cache(maxsize=1)
def load_memory() -> str:
    """Load global memory from AGENTS.md.

    Returns:
        Content of AGENTS.md or empty string if not found.
    """
    base_dir = _get_agents_base_dir()
    if not base_dir:
        return ""

    memory_file = settings.agents_memory_file or "AGENTS.md"
    memory_path = base_dir / memory_file

    try:
        return memory_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    except Exception as e:
        # Log error but don't crash - fallback to empty
        import logging

        logging.getLogger(__name__).warning(f"Failed to load AGENTS.md: {e}")
        return ""


SkillMode = Literal[
    "sql",
    "nosql",
    "open-analysis",
    "chart-gen",
    "image-ingest",
    "data-quality",
    "query-explain",
    "compare",
    "summarize",
    "kpi-dashboard",
]

_SKILL_DIR_MAP: dict[str, str] = {
    "sql": "sql-query",
    "nosql": "nosql-query",
    "open-analysis": "open-analysis",
    "chart-gen": "chart-gen",
    "image-ingest": "image-ingest",
    "data-quality": "data-quality",
    "query-explain": "query-explain",
    "compare": "compare",
    "summarize": "summarize",
    "kpi-dashboard": "kpi-dashboard",
    "data-conformity": "data-conformity",
}


@functools.lru_cache(maxsize=8)
def load_skill(mode: SkillMode) -> Skill:
    """Load skill for given mode from SKILL.md.

    Args:
        mode: "sql", "nosql", or "open-analysis"

    Returns:
        Skill object with metadata and content (empty skill if not found)
    """
    skill_name = _SKILL_DIR_MAP.get(mode, f"{mode}-query")

    base_dir = _get_agents_base_dir()
    if not base_dir:
        return Skill(name=skill_name, description="", version=None, content="")

    skills_dir = settings.agents_skills_dir or "skills"
    skill_path = base_dir / skills_dir / skill_name / "SKILL.md"

    try:
        content = skill_path.read_text(encoding="utf-8")
        metadata, body = _parse_frontmatter(content)

        return Skill(
            name=metadata.get("name", skill_name),
            description=metadata.get("description", ""),
            version=metadata.get("version"),
            content=body,
        )
    except FileNotFoundError:
        return Skill(name=skill_name, description="", version=None, content="")
    except Exception as e:
        import logging

        logging.getLogger(__name__).warning(f"Failed to load skill for {mode}: {e}")
        return Skill(name=skill_name, description="", version=None, content="")


def invalidate_cache():
    """Invalidate all cached prompts. Call when files are modified."""
    load_memory.cache_clear()
    load_skill.cache_clear()


def get_system_prompt(
    mode: SkillMode,
    plugin_fallback: str = "",
    conversation_id: str | None = None,
    question: str | None = None,
) -> str:
    """Build complete system prompt from memory + skill + session skill.

    Args:
        mode: "sql", "nosql", or "open-analysis"
        plugin_fallback: Fallback prompt from plugin if skill file not found
        conversation_id: Optional conversation ID to look up per-conversation session skill
        question: Current user question — used to check if session skill is relevant

    Returns:
        Complete system prompt combining memory, skill, and session skill
    """
    parts = []

    # 1. Load memory (AGENTS.md)
    memory = load_memory()
    if memory:
        parts.append(memory)

    # 2. Load skill — priority: SKILL.md → registry inline prompt → plugin fallback
    skill = load_skill(mode)
    if skill.content:
        parts.append(skill.content)
    else:
        # Try to get inline prompt from skill registry
        skill_name = _SKILL_DIR_MAP.get(mode, f"{mode}-query")
        from ndi_api.skills import registry

        registered = registry.get(skill_name)
        inline = registered.get_prompt() if registered else ""
        parts.append(inline or plugin_fallback)

    # 3. Inject ephemeral session skill ONLY if relevant to the question
    from ndi_api.services.session_skills import get_active_skill

    session_skill = get_active_skill(conversation_id)
    if session_skill:
        if question and not session_skill.is_relevant(question):
            logger.debug(
                "Session skill '%s' skipped (not relevant to: %s)",
                session_skill.name,
                question[:60],
            )
        else:
            parts.append(f"[SKILL COMPLÉMENTAIRE : {session_skill.name}]\n{session_skill.content}")

    full = "\n\n---\n\n".join(parts)

    # Warn if prompt is using a large fraction of the context window
    estimated_tokens = len(full) // 4  # rough estimate: 1 token ≈ 4 chars
    ctx = settings.llm_context_length
    if ctx and estimated_tokens > ctx * 0.5:
        logger.warning(
            "System prompt is ~%d tokens (%.0f%% of %d context window)",
            estimated_tokens,
            estimated_tokens / ctx * 100,
            ctx,
        )

    return full


def get_skill_info(mode: SkillMode) -> dict:
    """Get skill metadata for debugging/UI purposes.

    Returns:
        Dict with name, description, version, has_content
    """
    skill = load_skill(mode)
    return {
        "name": skill.name,
        "description": skill.description,
        "version": skill.version,
        "has_content": bool(skill.content),
    }


def get_all_skills_info() -> list[dict]:
    """List all registered skills with metadata (for UI / debug)."""
    from ndi_api.skills import registry

    result = []
    for name, skill in registry.all_skills().items():
        result.append(
            {
                "name": skill.name,
                "description": skill.description,
                "version": skill.version,
                "tags": skill.tags,
                "triggers": skill.triggers,
                "depends_on": skill.depends_on,
                "is_post_processor": skill.is_post_processor,
                "has_tools": len(skill.get_tools()) > 0,
                "tools": [t.name for t in skill.get_tools()],
            }
        )
    return result


def get_memory_info() -> dict:
    """Get memory file info for debugging/UI purposes.

    Returns:
        Dict with has_content, file_path
    """
    base_dir = _get_agents_base_dir()
    memory_file = settings.agents_memory_file or "AGENTS.md"

    file_path = None
    if base_dir:
        file_path = str(base_dir / memory_file)

    return {
        "has_content": bool(load_memory()),
        "file_path": file_path,
        "base_dir_configured": bool(settings.agents_base_dir),
    }
