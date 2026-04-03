"""Ephemeral session skill store — per-conversation, with versioning.

Skills generated or imported by the user are stored in memory, keyed by
conversation_id.  Each conversation keeps a *version stack* so the user
can rollback after a refinement.

Improvements over v1:
- **Triggers**: extracted from frontmatter/content, used for conditional injection
- **Relevance check**: `is_relevant(question)` avoids injecting noise
- **Full export**: `promote_to_module()` generates a complete SkillBase module
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# Trigger extraction
# ═══════════════════════════════════════════════════════════════════════

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
_TAGS_RE = re.compile(r"tags:\s*\[([^\]]*)\]")
_NAME_RE = re.compile(r"^name:\s*(.+)$", re.MULTILINE)
_DESC_RE = re.compile(r"^description:\s*(.+)$", re.MULTILINE)

# Sections that often contain domain keywords
_KEYWORD_SECTIONS = re.compile(
    r"##\s+(?:Vocabulaire|Règles|Mappings|Contexte)[^\n]*\n(.*?)(?=\n##|\Z)",
    re.DOTALL | re.IGNORECASE,
)
# Bold terms in markdown
_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")


def extract_triggers(content: str) -> list[str]:
    """Extract trigger keywords from a skill's markdown content.

    Sources (in priority order):
    1. ``tags: [...]`` from YAML frontmatter
    2. Bold terms (``**term**``) from Vocabulaire/Règles/Mappings sections
    3. The skill name itself
    """
    triggers: list[str] = []

    # 1. Tags from frontmatter
    fm = _FRONTMATTER_RE.match(content)
    if fm:
        tags_match = _TAGS_RE.search(fm.group(1))
        if tags_match:
            raw_tags = tags_match.group(1)
            triggers.extend(t.strip().strip("\"'") for t in raw_tags.split(",") if t.strip())

    # 2. Bold terms from relevant sections
    for section_match in _KEYWORD_SECTIONS.finditer(content):
        section_text = section_match.group(1)
        for bold in _BOLD_RE.findall(section_text):
            term = bold.strip().lower()
            if 1 < len(term) < 40:
                triggers.append(term)

    # 3. Skill name
    name_match = _NAME_RE.search(content)
    if name_match:
        name = name_match.group(1).strip().strip("\"'")
        triggers.extend(name.replace("-", " ").split())

    # Deduplicate preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for t in triggers:
        t_lower = t.lower()
        if t_lower not in seen:
            seen.add(t_lower)
            unique.append(t_lower)

    return unique


def extract_description(content: str) -> str:
    """Extract description from frontmatter."""
    match = _DESC_RE.search(content)
    return match.group(1).strip().strip("\"'") if match else ""


# ═══════════════════════════════════════════════════════════════════════
# Data model
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class SessionSkill:
    """A single version of a session skill."""

    name: str
    content: str
    created_at: float = field(default_factory=time.time)
    source: str = "generated"
    version: int = 1
    parent_version: int | None = None
    triggers: list[str] = field(default_factory=list)
    description: str = ""

    def is_relevant(self, question: str) -> bool:
        """Check if this skill is relevant to the given question.

        Returns True if any trigger keyword appears in the question,
        or if there are no triggers (= always relevant, legacy behavior).
        """
        if not self.triggers:
            return True  # No triggers = always inject (backward compat)
        q_lower = question.lower()
        return any(t in q_lower for t in self.triggers)


@dataclass
class SkillStack:
    """Per-conversation skill history (ordered oldest → newest)."""

    versions: list[SessionSkill] = field(default_factory=list)

    @property
    def active(self) -> SessionSkill | None:
        return self.versions[-1] if self.versions else None

    @property
    def current_version(self) -> int:
        return self.active.version if self.active else 0

    def push(
        self,
        name: str,
        content: str,
        source: str = "generated",
    ) -> SessionSkill:
        ver = self.current_version + 1
        parent = self.current_version if self.versions else None
        triggers = extract_triggers(content)
        desc = extract_description(content)
        skill = SessionSkill(
            name=name,
            content=content,
            source=source,
            version=ver,
            parent_version=parent,
            triggers=triggers,
            description=desc,
        )
        self.versions.append(skill)
        if len(self.versions) > 10:
            self.versions = self.versions[-10:]
        logger.debug(
            "Skill v%d pushed: %s (%d triggers: %s)",
            ver,
            name,
            len(triggers),
            triggers[:5],
        )
        return skill

    def rollback(self) -> SessionSkill | None:
        if len(self.versions) <= 1:
            return None
        self.versions.pop()
        return self.active

    def clear(self) -> bool:
        had = bool(self.versions)
        self.versions.clear()
        return had

    def history(self) -> list[dict]:
        return [
            {
                "version": s.version,
                "name": s.name,
                "source": s.source,
                "created_at": s.created_at,
                "content_length": len(s.content),
                "triggers_count": len(s.triggers),
            }
            for s in self.versions
        ]


# ═══════════════════════════════════════════════════════════════════════
# Global store
# ═══════════════════════════════════════════════════════════════════════

_stacks: dict[str, SkillStack] = {}
_DEFAULT_KEY = "__global__"
_MAX_CONVERSATIONS = 200


def _key(conversation_id: str | None) -> str:
    return conversation_id or _DEFAULT_KEY


def _cleanup_if_needed() -> None:
    if len(_stacks) <= _MAX_CONVERSATIONS:
        return
    sorted_keys = sorted(
        _stacks,
        key=lambda k: (_stacks[k].active.created_at if _stacks[k].active else 0),
    )
    for key in sorted_keys[: len(_stacks) - _MAX_CONVERSATIONS]:
        del _stacks[key]


def _get_stack(conversation_id: str | None) -> SkillStack:
    key = _key(conversation_id)
    if key not in _stacks:
        _stacks[key] = SkillStack()
    return _stacks[key]


# ═══════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════


def get_active_skill(conversation_id: str | None = None) -> SessionSkill | None:
    stack = _stacks.get(_key(conversation_id))
    return stack.active if stack else None


def set_active_skill(
    name: str,
    content: str,
    source: str = "generated",
    conversation_id: str | None = None,
) -> SessionSkill:
    stack = _get_stack(conversation_id)
    skill = stack.push(name, content, source)
    _cleanup_if_needed()
    return skill


def rollback_skill(conversation_id: str | None = None) -> SessionSkill | None:
    stack = _stacks.get(_key(conversation_id))
    if not stack:
        return None
    result = stack.rollback()
    logger.debug("Skill rollback for %s → v%s", _key(conversation_id), result.version if result else "none")
    return result


def clear_active_skill(conversation_id: str | None = None) -> bool:
    key = _key(conversation_id)
    stack = _stacks.get(key)
    if not stack:
        return False
    had = stack.clear()
    del _stacks[key]
    return had


def get_skill_history(conversation_id: str | None = None) -> list[dict]:
    stack = _stacks.get(_key(conversation_id))
    return stack.history() if stack else []


def clear_all_skills() -> int:
    count = len(_stacks)
    _stacks.clear()
    return count


# ═══════════════════════════════════════════════════════════════════════
# Export & Promotion
# ═══════════════════════════════════════════════════════════════════════


def export_skill_to_file(
    conversation_id: str | None = None,
    *,
    directory: str | Path | None = None,
) -> Path | None:
    """Write the active skill to disk as a ``SKILL.md`` file."""
    skill = get_active_skill(conversation_id)
    if not skill:
        return None

    if directory is None:
        from ndi_api.services.agent_prompts import _get_agents_base_dir
        from ndi_api.settings import settings

        base = _get_agents_base_dir()
        if not base:
            base = Path(__file__).parent.parent.parent.parent / "agents"
        skills_dir = settings.agents_skills_dir or "skills"
        directory = base / skills_dir / skill.name

    out_dir = Path(directory)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "SKILL.md"
    out_path.write_text(skill.content, encoding="utf-8")
    logger.info("Skill SKILL.md exported to %s", out_path)
    return out_path


def promote_to_module(
    conversation_id: str | None = None,
) -> dict | None:
    """Generate a full SkillBase module (skill.py + schema.py) from the active
    session skill, write it to ``src/ndi_api/skills/<name>/``, and register it.

    Returns metadata dict or None if no active skill.
    """
    skill = get_active_skill(conversation_id)
    if not skill:
        return None

    # Sanitize name for Python identifiers
    py_name = skill.name.replace("-", "_").replace(" ", "_").lower()
    py_name = re.sub(r"[^a-z0-9_]", "", py_name)
    class_name = "".join(w.capitalize() for w in py_name.split("_")) + "Skill"

    # Determine paths
    skills_pkg = Path(__file__).parent.parent / "skills" / py_name
    skills_pkg.mkdir(parents=True, exist_ok=True)

    # Also export SKILL.md to agents/skills/<name>/
    export_skill_to_file(conversation_id)

    # ── __init__.py ────────────────────────────────────────────────
    (skills_pkg / "__init__.py").write_text("", encoding="utf-8")

    # ── schema.py ──────────────────────────────────────────────────
    schema_content = f'''"""Input/output schemas for the {skill.name} skill (auto-generated)."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ndi_api.skills.base import SkillInput, SkillOutput


class {class_name}Input(SkillInput):
    """Input for {skill.name}."""
    sample_data: list[dict[str, Any]] = Field(default_factory=list)


class {class_name}Output(SkillOutput):
    """Output of {skill.name}."""
    sections: dict[str, str] = Field(default_factory=dict)
'''
    (skills_pkg / "schema.py").write_text(schema_content, encoding="utf-8")

    # ── skill.py ───────────────────────────────────────────────────
    triggers_repr = repr(skill.triggers[:15])
    desc_repr = repr(skill.description[:100] or f"Skill {skill.name}")

    skill_content = f'''"""Skill: {skill.name} (auto-generated from session skill)."""

from __future__ import annotations

from typing import Any

from ndi_api.skills.base import SkillBase, SkillInput, SkillOutput
from ndi_api.skills.{py_name}.schema import {class_name}Input, {class_name}Output
from ndi_api.skills import registry


class {class_name}(SkillBase):
    name = {repr(skill.name)}
    description = {desc_repr}
    version = "1.0.0"
    tags = {repr([t for t in skill.triggers[:5]])}
    triggers = {triggers_repr}

    def get_input_schema(self) -> type[{class_name}Input]:
        return {class_name}Input

    def get_output_schema(self) -> type[{class_name}Output]:
        return {class_name}Output

    def _inline_prompt(self) -> str:
        return ""  # Loaded from SKILL.md via get_prompt()

    def execute(self, inp: SkillInput, **kwargs: Any) -> {class_name}Output:
        return {class_name}Output(answer="")


registry.register({class_name}())
'''
    (skills_pkg / "skill.py").write_text(skill_content, encoding="utf-8")

    # ── Register at runtime ────────────────────────────────────────
    import importlib

    module_name = f"ndi_api.skills.{py_name}.skill"
    try:
        importlib.import_module(module_name)
        logger.info("Skill %s promoted and registered from %s", skill.name, skills_pkg)
    except Exception:
        logger.warning("Skill %s promoted to %s but import failed", skill.name, skills_pkg, exc_info=True)

    return {
        "name": skill.name,
        "python_name": py_name,
        "class_name": class_name,
        "module_path": str(skills_pkg),
        "files": ["__init__.py", "schema.py", "skill.py"],
        "triggers": skill.triggers[:15],
    }
