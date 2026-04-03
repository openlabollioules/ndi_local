"""Skills API — generate, refine, inject, manage, and export session skills.

Improvements over v1:
- Schema-aware generation (injects current DB schema + mode into the prompt)
- Structural validation of generated skills (frontmatter, required sections)
- conversation_id propagation (per-conversation skill isolation)
- Versioning with rollback support
- Server-side export to agents/skills/<name>/SKILL.md
"""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ndi_api.plugins.manager import get_plugin_manager
from ndi_api.services.llm import get_indexing_llm, strip_thinking
from ndi_api.services.session_skills import (
    clear_active_skill,
    export_skill_to_file,
    get_active_skill,
    get_skill_history,
    promote_to_module,
    rollback_skill,
    set_active_skill,
)

router = APIRouter(prefix="/skills")
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════
# Prompt templates
# ═══════════════════════════════════════════════════════════════════════

_GENERATE_PROMPT = """\
Tu es un expert en prompt-engineering et ingénierie de connaissances
pour le système NDI (Naval Data Intelligence).

NDI convertit des questions en langage naturel en requêtes {mode_label}.
L'utilisateur te fournit un contexte métier brut (règles, vocabulaire,
contraintes, données).

**Ton objectif** : transformer ce contexte en un **Skill** structuré que
NDI injectera dans le prompt LLM pour améliorer la qualité des requêtes.

## Schéma actuel de la base

{schema_block}

## Modèle de skill attendu

Le skill DOIT respecter exactement cette structure :

```markdown
---
name: <nom-court-kebab-case>
description: <description en une phrase>
version: 1.0.0
tags: [<tag1>, <tag2>]
---

# Skill: <Titre du skill>

## Contexte métier
<résumé du domaine, 2-3 phrases>

## Vocabulaire clé
- **<terme>** : <définition courte>

## Règles spécifiques
1. <règle métier 1>
2. <règle métier 2>

## Mappings colonnes
<correspondance entre les termes métier et les colonnes réelles du schéma>
- « <terme métier> » → colonne `<nom_colonne>` (table `<nom_table>`)

## Exemples
**Q:** <question type en langage naturel>
**{query_label}:** <requête {mode_label} attendue utilisant les vraies colonnes>

## Contraintes
- <contrainte 1>
- <contrainte 2>
```

## Règles de génération

1. Le frontmatter YAML (entre `---`) est OBLIGATOIRE
2. Le nom doit être en kebab-case (ex: `maintenance-navale`)
3. La section **Mappings colonnes** est OBLIGATOIRE — elle lie les termes
   métier de l'utilisateur aux colonnes réelles du schéma ci-dessus
4. Les exemples Q/R DOIVENT utiliser les vrais noms de colonnes/tables
5. Sois concis : max 150 lignes
6. Réponds en français sauf pour les termes techniques
7. Retourne UNIQUEMENT le Markdown, sans texte avant/après
8. Ne mets PAS de backticks markdown (```) autour du skill entier

## Contexte métier fourni par l'utilisateur

{user_input}

SKILL GÉNÉRÉ :"""


_REFINE_PROMPT = """\
Tu es un expert en ingénierie de connaissances pour NDI.

Voici un skill généré automatiquement à partir d'un contexte métier :

--- DÉBUT DU SKILL ---
{skill_content}
--- FIN DU SKILL ---

{schema_hint}

Analyse ce skill et identifie ce qui MANQUE ou pourrait être amélioré.
Pose exactement 3 questions courtes et ciblées à l'utilisateur.

Chaque question doit porter sur un aspect DIFFÉRENT parmi :
- Termes métier ou acronymes non définis
- Mappings colonnes manquants (termes métier → colonnes réelles)
- Cas limites, exceptions, ou règles implicites non capturées
- Exemples concrets Q/R supplémentaires
- Contraintes de format, filtres par défaut, ou périodes temporelles

Réponds UNIQUEMENT avec les 3 questions, une par ligne, numérotées 1. 2. 3.
Pas d'introduction ni de conclusion."""


_REGENERATE_PROMPT = """\
Tu es un expert en prompt-engineering et ingénierie de connaissances pour NDI.

L'utilisateur a d'abord fourni ce contexte métier brut :
--- CONTEXTE ORIGINAL ---
{original_input}
--- FIN CONTEXTE ---

Un premier skill a été généré :
--- SKILL EXISTANT ---
{skill_content}
--- FIN SKILL ---

L'utilisateur a ensuite répondu à des questions de raffinement :
--- RAFFINEMENTS ---
{refinements}
--- FIN RAFFINEMENTS ---

{schema_hint}

Régénère le skill en intégrant TOUTES les informations ci-dessus.
Conserve la même structure Markdown (frontmatter YAML, sections Contexte/
Vocabulaire/Règles/Mappings/Exemples/Contraintes).

IMPORTANT :
- Enrichis les sections existantes avec les nouvelles informations
- Mets à jour la section Mappings colonnes si de nouveaux termes métier
  ont été mentionnés
- Les exemples Q/R DOIVENT utiliser les vrais noms de colonnes du schéma
- Ne supprime rien de pertinent du skill existant
- Incrémente la version (ex: 1.0.0 → 1.1.0)
- Retourne UNIQUEMENT le Markdown, sans texte avant/après"""


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

_REQUIRED_SECTIONS = {"contexte", "règles", "exemples"}

_SECTION_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)


def _get_schema_block() -> str:
    """Build a compact schema summary from the current plugin."""
    try:
        plugin = get_plugin_manager().get_plugin()
        schema = plugin.get_schema()
        if not schema.tables:
            return "(aucune table disponible)"
        lines = []
        for table in schema.tables:
            cols = ", ".join(f"{c.name} ({c.type})" for c in table.columns)
            lines.append(f"- Table `{table.name}` : {cols}")
        return "\n".join(lines)
    except Exception:
        return "(schéma non disponible)"


def _get_schema_hint() -> str:
    """Short schema reminder for refine/regenerate prompts."""
    block = _get_schema_block()
    if block.startswith("("):
        return ""
    return f"Rappel — schéma actuel de la base :\n{block}\n"


def _get_mode_info() -> tuple[str, str]:
    """Return (mode_label, query_label) based on active plugin."""
    try:
        mode = get_plugin_manager().get_current_mode()
    except Exception:
        mode = "sql"
    if mode == "nosql":
        return "NoSQL (JSON / MongoDB-style)", "JSON"
    return "SQL (DuckDB)", "SQL"


def _validate_skill_structure(content: str) -> list[str]:
    """Validate that a generated skill has the expected structure.

    Returns a list of warnings (empty = valid).
    """
    warnings: list[str] = []

    # Check frontmatter
    if not content.strip().startswith("---"):
        warnings.append("Frontmatter YAML manquant (doit commencer par ---)")
    else:
        fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
        if fm_match:
            fm = fm_match.group(1)
            if "name:" not in fm:
                warnings.append("Champ 'name' manquant dans le frontmatter")
            if "description:" not in fm:
                warnings.append("Champ 'description' manquant dans le frontmatter")
        else:
            warnings.append("Frontmatter mal formé (--- de fermeture manquant)")

    # Check required sections
    found_sections = {m.group(1).strip().lower() for m in _SECTION_RE.finditer(content)}
    for required in _REQUIRED_SECTIONS:
        if not any(required in s for s in found_sections):
            warnings.append(f"Section '## {required.title()}' manquante ou mal nommée")

    return warnings


def _extract_name(md: str) -> str | None:
    """Try to extract skill name from frontmatter."""
    match = re.search(r"^name:\s*(.+)$", md, re.MULTILINE)
    if match:
        return match.group(1).strip().strip("\"'")
    return None


def _parse_questions(raw: str) -> list[str]:
    """Parse numbered questions from LLM output."""
    lines = raw.strip().splitlines()
    questions: list[str] = []
    for line in lines:
        cleaned = re.sub(r"^\s*\d+[\.\)]\s*", "", line).strip()
        if cleaned and len(cleaned) > 10:
            questions.append(cleaned)
    return questions


# ═══════════════════════════════════════════════════════════════════════
# Request / Response models
# ═══════════════════════════════════════════════════════════════════════


class GenerateRequest(BaseModel):
    input: str = Field(..., min_length=10, description="Contexte métier brut")
    name: str | None = Field(None, description="Nom souhaité (optionnel)")
    conversation_id: str | None = Field(None, description="Conversation pour isoler le skill")


class SkillResponse(BaseModel):
    name: str
    content: str
    source: str
    active: bool
    version: int = 1
    warnings: list[str] = Field(default_factory=list, description="Problèmes de structure détectés")
    triggers: list[str] = Field(default_factory=list, description="Keywords extracted for conditional injection")


class InjectRequest(BaseModel):
    name: str = Field(..., min_length=1)
    content: str = Field(..., min_length=10)
    conversation_id: str | None = None


class RefineRequest(BaseModel):
    content: str = Field(..., min_length=20, description="Skill généré à analyser")


class RefineResponse(BaseModel):
    questions: list[str]


class Refinement(BaseModel):
    question: str
    answer: str


class RegenerateRequest(BaseModel):
    original_input: str = Field(..., min_length=10)
    skill_content: str = Field(..., min_length=20)
    refinements: list[Refinement]
    name: str | None = None
    conversation_id: str | None = None


class ExportRequest(BaseModel):
    conversation_id: str | None = None
    directory: str | None = Field(None, description="Répertoire cible (optionnel)")


class HistoryEntry(BaseModel):
    version: int
    name: str
    source: str
    created_at: float
    content_length: int


# ═══════════════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════════════


@router.post("/generate", response_model=SkillResponse)
async def generate_skill(request: GenerateRequest) -> SkillResponse:
    """Generate a structured skill from raw business context.

    The prompt is enriched with the current database schema so the generated
    skill references real column names.
    """
    mode_label, query_label = _get_mode_info()
    schema_block = _get_schema_block()

    prompt = (
        _GENERATE_PROMPT.replace("{user_input}", request.input)
        .replace("{mode_label}", mode_label)
        .replace("{query_label}", query_label)
        .replace("{schema_block}", schema_block)
    )

    try:
        llm = get_indexing_llm()
        raw = strip_thinking(llm.invoke(prompt).content)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erreur LLM : {e}")

    # Validate structure
    warnings = _validate_skill_structure(raw)

    name = request.name or _extract_name(raw) or "skill-custom"
    skill = set_active_skill(
        name=name,
        content=raw,
        source="generated",
        conversation_id=request.conversation_id,
    )

    return SkillResponse(
        name=skill.name,
        content=skill.content,
        source=skill.source,
        active=True,
        version=skill.version,
        warnings=warnings,
        triggers=skill.triggers,
    )


@router.post("/refine", response_model=RefineResponse)
async def refine_skill(request: RefineRequest) -> RefineResponse:
    """Analyze a generated skill and return targeted questions to improve it."""
    schema_hint = _get_schema_hint()
    prompt = _REFINE_PROMPT.replace("{skill_content}", request.content).replace("{schema_hint}", schema_hint)

    try:
        llm = get_indexing_llm()
        raw = strip_thinking(llm.invoke(prompt).content)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erreur LLM : {e}")

    questions = _parse_questions(raw)
    if not questions:
        questions = [
            "Quels termes ou acronymes spécifiques à votre domaine devraient être définis ?",
            "Y a-t-il des cas limites ou exceptions aux règles décrites ?",
            "Pouvez-vous donner un exemple concret de question/réponse attendue ?",
        ]

    return RefineResponse(questions=questions[:3])


@router.post("/regenerate", response_model=SkillResponse)
async def regenerate_skill(request: RegenerateRequest) -> SkillResponse:
    """Regenerate a skill enriched with user answers to refinement questions."""
    refinements_text = "\n".join(f"Q: {r.question}\nR: {r.answer}" for r in request.refinements)
    schema_hint = _get_schema_hint()

    prompt = (
        _REGENERATE_PROMPT.replace("{original_input}", request.original_input)
        .replace("{skill_content}", request.skill_content)
        .replace("{refinements}", refinements_text)
        .replace("{schema_hint}", schema_hint)
    )

    try:
        llm = get_indexing_llm()
        raw = strip_thinking(llm.invoke(prompt).content)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erreur LLM : {e}")

    warnings = _validate_skill_structure(raw)
    name = request.name or _extract_name(raw) or _extract_name(request.skill_content) or "skill-custom"

    skill = set_active_skill(
        name=name,
        content=raw,
        source="refined",
        conversation_id=request.conversation_id,
    )

    return SkillResponse(
        name=skill.name,
        content=skill.content,
        source=skill.source,
        active=True,
        version=skill.version,
        warnings=warnings,
        triggers=skill.triggers,
    )


@router.post("/inject", response_model=SkillResponse)
async def inject_skill(request: InjectRequest) -> SkillResponse:
    """Inject (import) a skill into the current session."""
    warnings = _validate_skill_structure(request.content)

    skill = set_active_skill(
        name=request.name,
        content=request.content,
        source="imported",
        conversation_id=request.conversation_id,
    )

    return SkillResponse(
        name=skill.name,
        content=skill.content,
        source=skill.source,
        active=True,
        version=skill.version,
        warnings=warnings,
        triggers=skill.triggers,
    )


@router.get("/active")
async def get_active(
    conversation_id: str | None = Query(None),
) -> dict:
    """Get the currently active session skill for a conversation."""
    skill = get_active_skill(conversation_id)
    if not skill:
        return {"active": False, "skill": None}
    return {
        "active": True,
        "skill": {
            "name": skill.name,
            "content": skill.content,
            "source": skill.source,
            "version": skill.version,
            "created_at": skill.created_at,
            "triggers": skill.triggers,
            "description": skill.description,
        },
    }


@router.delete("/active")
async def deactivate_skill(
    conversation_id: str | None = Query(None),
) -> dict:
    """Remove all skill versions for a conversation."""
    removed = clear_active_skill(conversation_id)
    return {
        "removed": removed,
        "message": "Skill désactivé" if removed else "Aucun skill actif",
    }


@router.post("/rollback")
async def rollback_to_previous(
    conversation_id: str | None = Query(None),
) -> dict:
    """Rollback to the previous skill version."""
    previous = rollback_skill(conversation_id)
    if previous is None:
        raise HTTPException(
            status_code=400,
            detail="Impossible de revenir en arrière (version initiale ou aucun skill).",
        )
    return {
        "message": f"Retour à la version {previous.version}",
        "skill": {
            "name": previous.name,
            "content": previous.content,
            "source": previous.source,
            "version": previous.version,
        },
    }


@router.get("/history", response_model=list[HistoryEntry])
async def skill_history(
    conversation_id: str | None = Query(None),
) -> list[HistoryEntry]:
    """Get the version history of session skills for a conversation."""
    entries = get_skill_history(conversation_id)
    return [HistoryEntry(**e) for e in entries]


@router.post("/export")
async def export_to_disk(request: ExportRequest) -> dict:
    """Export the active session skill to the agents/ filesystem.

    This makes the skill permanent — it will be loaded automatically by
    ``agent_prompts.py`` on subsequent requests.
    """
    path = export_skill_to_file(
        conversation_id=request.conversation_id,
        directory=request.directory,
    )
    if path is None:
        raise HTTPException(status_code=404, detail="Aucun skill actif à exporter.")

    # Invalidate prompt cache so the new file is picked up
    from ndi_api.services.agent_prompts import invalidate_cache

    invalidate_cache()

    return {
        "message": f"Skill exporté vers {path}",
        "path": str(path),
    }


class PromoteRequest(BaseModel):
    conversation_id: str | None = None


@router.post("/promote")
async def promote_skill(request: PromoteRequest) -> dict:
    """Promote the active session skill to a permanent SkillBase module.

    This generates ``skill.py``, ``schema.py``, and ``__init__.py`` in
    ``src/ndi_api/skills/<name>/``, writes the ``SKILL.md`` to
    ``agents/skills/<name>/``, and registers the skill in the registry
    at runtime.

    After promotion, the skill appears in ``/skills/registry`` and is
    routed automatically based on its triggers.
    """
    result = promote_to_module(conversation_id=request.conversation_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Aucun skill actif à promouvoir.")

    from ndi_api.services.agent_prompts import invalidate_cache

    invalidate_cache()

    return {
        "message": f"Skill '{result['name']}' promu en module permanent",
        **result,
    }


@router.get("/registry")
async def list_registered_skills() -> dict:
    """List all skills registered in the SkillBase registry (permanent + promoted)."""
    from ndi_api.services.agent_prompts import get_all_skills_info

    skills = get_all_skills_info()
    return {"skills": skills, "count": len(skills)}
