"""SkillBase — abstract base class for all NDI skills.

Each skill declares:
- Metadata (name, description, version, tags, triggers)
- Prompt loading (from SKILL.md or inline)
- Input/output schemas (Pydantic models)
- Optional tool definitions (callable by the LLM)
- Optional composition dependencies (e.g. chart_gen depends on sql_query)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class SkillInput(BaseModel):
    """Base input schema — every skill receives at least a question."""

    question: str
    context: str = ""
    conversation_id: str | None = None


class SkillOutput(BaseModel):
    """Base output schema — every skill produces at least an answer."""

    answer: str
    confidence: float = 1.0
    metadata: dict[str, Any] = {}


class ToolDefinition(BaseModel):
    """A tool that the LLM can invoke when this skill is active."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema


class SkillBase(ABC):
    """Abstract contract for every NDI skill."""

    # --- Metadata (override in subclasses) ------------------------------------

    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    tags: list[str] = []

    # Trigger keywords that help the router pick this skill
    triggers: list[str] = []

    # Skills this skill depends on (run *before* this one in a pipeline)
    depends_on: list[str] = []

    # Whether this skill is a post-processor (composes on top of another)
    is_post_processor: bool = False

    # --- Prompt ---------------------------------------------------------------

    def get_prompt(self) -> str:
        """Load skill instructions from the co-located SKILL.md.

        Falls back to ``_inline_prompt()`` if the file doesn't exist.
        """
        skill_md = self._skill_md_path()
        if skill_md and skill_md.exists():
            from ndi_api.services.agent_prompts import _parse_frontmatter

            raw = skill_md.read_text(encoding="utf-8")
            _, body = _parse_frontmatter(raw)
            return body
        return self._inline_prompt()

    def _inline_prompt(self) -> str:
        """Fallback prompt when SKILL.md is missing. Override per-skill."""
        return ""

    def _skill_md_path(self) -> Path | None:
        """Path to the SKILL.md that lives next to the skill module."""
        # agents/skills/<dir_name>/SKILL.md
        from ndi_api.services.agent_prompts import _get_agents_base_dir
        from ndi_api.settings import settings

        base = _get_agents_base_dir()
        if not base:
            return None

        skills_dir = settings.agents_skills_dir or "skills"
        dir_name = self.name.replace("_", "-")
        return base / skills_dir / dir_name / "SKILL.md"

    # --- Schemas --------------------------------------------------------------

    def get_input_schema(self) -> type[SkillInput]:
        """Pydantic model for this skill's input. Override for richer schemas."""
        return SkillInput

    def get_output_schema(self) -> type[SkillOutput]:
        """Pydantic model for this skill's output. Override for richer schemas."""
        return SkillOutput

    # --- Tools ----------------------------------------------------------------

    def get_tools(self) -> list[ToolDefinition]:
        """Tools the LLM can call when this skill is active. Default: none."""
        return []

    # --- Validation -----------------------------------------------------------

    def validate_output(self, raw: str) -> SkillOutput:
        """Parse and validate the raw LLM response into the output schema.

        Override for skills that need custom parsing (e.g. extracting SQL).
        """
        schema = self.get_output_schema()
        return schema(answer=raw)

    # --- Lifecycle ------------------------------------------------------------

    @abstractmethod
    def execute(self, inp: SkillInput, **kwargs: Any) -> SkillOutput:
        """Run the skill's main logic.

        For *prompt-only* skills this is a no-op — the prompt is injected into
        the LLM call by the pipeline.  Skills that wrap a service (e.g. chart
        suggestion) implement real logic here.
        """
        ...
