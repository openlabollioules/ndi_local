"""SkillRouter — resolves user intent + mode into an ordered list of skills.

Replaces the hardcoded ``_SKILL_DIR_MAP`` with metadata-driven routing.
Supports skill composition: e.g. a chart question yields
``[sql_query, chart_gen]``.
"""

from __future__ import annotations

import logging
import re

from ndi_api.skills.base import SkillBase

logger = logging.getLogger(__name__)


class SkillRouter:
    """Resolve which skill(s) should handle a request."""

    # Post-processor detection patterns
    _CHART_RE = re.compile(
        r"\b(graphique|diagramme|chart|graph|courbe|histogramme|camembert|"
        r"pie|bar|line|scatter|radar|visualis|affiche.*(graph|chart))\b",
        re.IGNORECASE,
    )
    _EXPLAIN_RE = re.compile(
        r"\b(explique|explication|comment ça marche|que fait|décompose|détaille)\b",
        re.IGNORECASE,
    )
    _SUMMARIZE_RE = re.compile(
        r"\b(résumé|résume|synthèse|en bref|l'essentiel|récapitulatif|overview|digest)\b",
        re.IGNORECASE,
    )
    _QUALITY_RE = re.compile(
        r"\b(qualité|qualite|quality|manquant|null|vide|doublon|duplicate|"
        r"outlier|aberrant|anomalie|complétude|audit|propreté)\b",
        re.IGNORECASE,
    )
    _CONFORMITY_RE = re.compile(
        r"\b(conformité|conformite|conforme|non.conforme|règle[s]?|regle[s]?|"
        r"validation|valider|vérifier|corriger|correction|corrige[rz]?|"
        r"fichier corrigé|valeurs autorisées|valeurs? non.conforme|"
        r"interdit|doit contenir|format attendu)\b",
        re.IGNORECASE,
    )
    _COMPARE_RE = re.compile(
        r"\b(compare[rz]?|comparaison|vs|versus|par rapport|différence entre|"
        r"écart entre|évolution|tendance|progression|régression|avant.+après|"
        r"augmentation|diminution|variation)\b",
        re.IGNORECASE,
    )
    _KPI_RE = re.compile(
        r"\b(kpi|indicateur|tableau de bord|dashboard|métriques|metriques|"
        r"vue d'ensemble|état des lieux|bilan|point sur|statistiques|"
        r"chiffres clés|chiffres cles)\b",
        re.IGNORECASE,
    )

    def resolve(
        self,
        question: str,
        mode: str,
        *,
        question_type: str = "nl_to_query",
        context: dict | None = None,
    ) -> list[SkillBase]:
        """Return an ordered list of skills to execute.

        Priority: dedicated skills (quality, compare, kpi) override the default
        primary skill.  Post-processors (chart, explain, summarize) stack on top.
        """
        from ndi_api.skills import registry

        skills: list[SkillBase] = []

        # 1. Check for dedicated analysis skills (override primary)
        primary = self._resolve_primary(question, question_type, mode)
        if primary:
            skills.append(primary)

        # 2. Stack post-processors
        for check, name in [
            (self._wants_chart, "chart-gen"),
            (self._wants_explain, "query-explain"),
            (self._wants_summarize, "summarize"),
        ]:
            if check(question):
                skill = registry.get(name)
                if skill and skill not in skills:
                    skills.append(skill)

        if not skills:
            logger.warning(
                "No skill resolved for mode=%s type=%s",
                mode,
                question_type,
            )

        return skills

    # ------------------------------------------------------------------
    # Primary resolution
    # ------------------------------------------------------------------

    def _resolve_primary(
        self,
        question: str,
        question_type: str,
        mode: str,
    ) -> SkillBase | None:
        from ndi_api.skills import registry

        # Dedicated skills take priority over generic query
        # Conformity before quality (more specific)
        if self._CONFORMITY_RE.search(question):
            return registry.get("data-conformity")
        if self._QUALITY_RE.search(question):
            return registry.get("data-quality")
        if self._COMPARE_RE.search(question):
            return registry.get("compare")
        if self._KPI_RE.search(question):
            return registry.get("kpi-dashboard")

        if question_type in ("open_analysis", "explanation"):
            return registry.get("open-analysis")
        if question_type == "image_ingest":
            return registry.get("image-ingest")

        # Default: mode-dependent query skill
        if mode == "nosql":
            return registry.get("nosql-query")
        return registry.get("sql-query")

    # ------------------------------------------------------------------
    # Post-processor checks
    # ------------------------------------------------------------------

    def _wants_chart(self, question: str) -> bool:
        return bool(self._CHART_RE.search(question))

    def _wants_explain(self, question: str) -> bool:
        return bool(self._EXPLAIN_RE.search(question))

    def _wants_summarize(self, question: str) -> bool:
        return bool(self._SUMMARIZE_RE.search(question))


# Singleton
_router: SkillRouter | None = None


def get_skill_router() -> SkillRouter:
    global _router
    if _router is None:
        _router = SkillRouter()
    return _router
