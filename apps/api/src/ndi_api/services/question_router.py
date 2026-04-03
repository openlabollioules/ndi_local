"""Question routing - determines how to handle different types of questions.

Routes questions to:
- nl_to_query: Generate SQL/NoSQL query
- follow_up: Question about previous results
- open_analysis: Open-ended analysis of data
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from ndi_api.services.conversation_memory import ConversationSession

QuestionType = Literal["nl_to_query", "follow_up", "open_analysis", "explanation"]


@dataclass
class RoutingResult:
    """Result of question routing."""

    question_type: QuestionType
    confidence: float  # 0-1
    reasoning: str
    suggested_approach: str


class QuestionRouter:
    """Routes user questions to appropriate handlers."""

    # Keywords indicating different question types
    FOLLOW_UP_INDICATORS = [
        "et",
        "mais",
        "aussi",
        "également",
        "alors",
        "donc",
        "laquelle",
        "lesquelles",
        "lequel",
        "lesquels",
        "pourquoi",
        "comment ça",
        "explique",
        "plus",
        "moins",
        "autre",
        "encore",
        "celle",
        "celui",
        "ceux",
        "celles",
        "elle",
        "il",
        "ils",
        "elles",  # pronouns referring to previous
    ]

    OPEN_ANALYSIS_KEYWORDS = [
        # Analysis actions
        "évalue",
        "évaluer",
        "analyse",
        "analyser",
        "étudie",
        "étudier",
        "examine",
        "examiner",
        "compare",
        "comparer",
        "contraste",
        # Quality assessment
        "cohérence",
        "cohérent",
        "incohérence",
        "incohérent",
        "qualité",
        "fiabilité",
        "consistance",
        # Patterns
        "pattern",
        "patterns",
        "tendance",
        "tendances",
        "trend",
        "évolution",
        "changement",
        "variation",
        # Correlations
        "corrélation",
        "corréler",
        "lien",
        "relation",
        "dépend",
        "influence",
        "impact",
        # Insights
        "insight",
        "insights",
        "observation",
        "remarque",
        "qu'en penses-tu",
        "que penses-tu",
        "interprète",
        "que remarques-tu",
        "que vois-tu",
        "déduis",
        # Distribution
        "répartition",
        "distribution",
        "proportion",
        "fréquence",
        "fréquent",
        "rare",
    ]

    EXPLANATION_KEYWORDS = [
        "explique",
        "expliquer",
        "détaille",
        "détailler",
        "clarifie",
        "précise",
        "pourquoi",
        "comment",
        "qu'est-ce que",
        "définis",
        "c'est quoi",
    ]

    def __init__(self):
        self._follow_up_pattern = re.compile(r"\b(" + "|".join(self.FOLLOW_UP_INDICATORS) + r")\b", re.IGNORECASE)
        self._analysis_pattern = re.compile(r"\b(" + "|".join(self.OPEN_ANALYSIS_KEYWORDS) + r")\b", re.IGNORECASE)
        self._explanation_pattern = re.compile(r"\b(" + "|".join(self.EXPLANATION_KEYWORDS) + r")\b", re.IGNORECASE)

    def route(self, question: str, session: ConversationSession | None = None) -> RoutingResult:
        """
        Determine the type of question and how to handle it.

        Args:
            question: The user's question
            session: Optional conversation session for context

        Returns:
            RoutingResult with type and approach
        """
        question_lower = question.lower().strip()

        # Check for conversation context
        has_context = session is not None and len(session.messages) > 0
        last_was_query = False
        if has_context:
            last_result = session.get_last_query_result()
            last_was_query = last_result is not None

        # 1. Check for follow-up (needs context)
        if has_context and self._is_follow_up(question_lower, last_was_query):
            return RoutingResult(
                question_type="follow_up",
                confidence=0.85,
                reasoning="Question de suivi détectée (référence implicite aux résultats précédents)",
                suggested_approach="Utiliser le contexte de la dernière requête pour répondre",
            )

        # 2. Check for open analysis
        if self._is_open_analysis(question_lower):
            return RoutingResult(
                question_type="open_analysis",
                confidence=0.80,
                reasoning="Demande d'analyse ouverte détectée",
                suggested_approach="Extraire un échantillon et générer une analyse avec le LLM",
            )

        # 3. Check for explanation request
        if self._is_explanation(question_lower):
            return RoutingResult(
                question_type="explanation",
                confidence=0.75,
                reasoning="Demande d'explication détectée",
                suggested_approach="Expliquer les concepts ou résultats de manière pédagogique",
            )

        # 4. Default: nl_to_query
        return RoutingResult(
            question_type="nl_to_query",
            confidence=0.90,
            reasoning="Question directe sur les données",
            suggested_approach="Générer une requête SQL/NoSQL",
        )

    def _is_follow_up(self, question: str, has_query_context: bool) -> bool:
        """Detect if this is a follow-up question."""
        if not has_query_context:
            return False

        # Short questions with pronouns are often follow-ups
        if len(question) < 30:
            # Check for pronouns referring to previous context
            pronouns = ["elle", "il", "elles", "ils", "celle", "celui", "ceux"]
            if any(p in question.split() for p in pronouns):
                return True

        # Check for follow-up indicators at start
        first_words = " ".join(question.split()[:3])
        indicators = ["et", "mais", "aussi", "alors", "donc", "pourquoi", "comment"]
        if any(first_words.startswith(ind) for ind in indicators):
            return True

        # Check for comparative without explicit subject
        comparative_pattern = r"^(plus |moins |autre |encore |meilleur |pire )"
        if re.match(comparative_pattern, question):
            return True

        # Count follow-up keywords
        matches = len(self._follow_up_pattern.findall(question))
        return matches >= 1 and len(question) < 50

    def _is_open_analysis(self, question: str) -> bool:
        """Detect if this is an open analysis question."""
        matches = self._analysis_pattern.findall(question)

        # Strong indicator: explicit analysis keywords
        if len(matches) >= 1:
            # Check for compound patterns
            strong_indicators = [
                "cohérence entre",
                "corrélation entre",
                "comparer",
                "évalue la",
                "analyse la",
                "qu'en penses-tu",
            ]
            for indicator in strong_indicators:
                if indicator in question:
                    return True

            # Multiple analysis keywords = likely analysis
            if len(matches) >= 2:
                return True

        # Questions asking for opinion/interpretation
        opinion_patterns = [
            r"qu'en penses[- ]tu",
            r"que (?:penses?|trouves?|remarques?)-tu",
            r"donne[- ]moi (?:ton|votre) avis",
            r"quelle est (?:ton|votre) opinion",
        ]
        for pattern in opinion_patterns:
            if re.search(pattern, question):
                return True

        return False

    def _is_explanation(self, question: str) -> bool:
        """Detect if this is an explanation request."""
        matches = self._explanation_pattern.findall(question)

        if len(matches) >= 1:
            # But not if it's clearly a query
            if question.startswith("explique-moi les") or "données" in question:
                return False
            return True

        return False

    def get_context_instructions(self, question_type: QuestionType) -> str:
        """Get system instructions for handling this question type."""
        instructions = {
            "nl_to_query": (
                "Génère une requête SQL ou NoSQL pour répondre à la question. "
                "Retourne uniquement la requête dans le format approprié."
            ),
            "follow_up": (
                "Cette question fait référence aux résultats précédents. "
                "Utilise le contexte de la dernière requête pour répondre. "
                "Tu peux générer une nouvelle requête si nécessaire, ou analyser les résultats existants."
            ),
            "open_analysis": (
                "Cette question demande une analyse ouverte des données. "
                "Tu vas extraire un échantillon de données pertinent et fournir une analyse détaillée "
                "avec observations, patterns, et interprétations."
            ),
            "explanation": (
                "Explique les concepts ou résultats de manière claire et pédagogique. "
                "Utilise des exemples concrets si possible."
            ),
        }
        return instructions.get(question_type, instructions["nl_to_query"])


# Singleton instance
_question_router: QuestionRouter | None = None


def get_question_router() -> QuestionRouter:
    """Get or create the question router singleton."""
    global _question_router
    if _question_router is None:
        _question_router = QuestionRouter()
    return _question_router
