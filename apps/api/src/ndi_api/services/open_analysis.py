"""Open analysis engine for complex, open-ended questions about data.

Provides capabilities for:
- Coherence analysis between columns
- Pattern detection
- Trend analysis
- Correlation detection
- Data quality assessment
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import dataclass
from typing import Any, Literal

logger = logging.getLogger(__name__)

from ndi_api.plugins.base import DataPlugin
from ndi_api.services.agent_prompts import get_system_prompt as get_agent_system_prompt
from ndi_api.services.conversation_memory import ConversationSession
from ndi_api.services.llm import get_llm

AnalysisType = Literal[
    "coherence",  # Coherence between columns
    "pattern",  # Pattern detection
    "trend",  # Trend analysis
    "correlation",  # Correlation between variables
    "distribution",  # Data distribution
    "quality",  # Data quality assessment
    "anomaly",  # Anomaly detection
    "custom",  # Custom analysis
]


@dataclass
class AnalysisResult:
    """Result of an open analysis."""

    answer: str
    analysis_type: AnalysisType
    confidence: float
    supporting_data: dict | None = None
    sample_size: int = 0
    query_used: str | None = None


class DataAnalysisTools:
    """Tools for analyzing data samples."""

    @staticmethod
    def analyze_coherence(data: list[dict], col1: str, col2: str) -> dict:
        """
        Analyze coherence between two columns.
        Returns metrics on how well the columns align.
        """
        if not data:
            return {"error": "No data provided"}

        total = len(data)
        both_present = 0
        both_empty = 0
        one_empty = 0

        # Simple coherence: both have values or both are empty
        for row in data:
            v1 = row.get(col1)
            v2 = row.get(col2)

            has_v1 = v1 is not None and str(v1).strip() != ""
            has_v2 = v2 is not None and str(v2).strip() != ""

            if has_v1 and has_v2:
                both_present += 1
            elif not has_v1 and not has_v2:
                both_empty += 1
            else:
                one_empty += 1

        coherence_rate = (both_present + both_empty) / total if total > 0 else 0

        return {
            "total_rows": total,
            "both_present": both_present,
            "both_empty": both_empty,
            "one_empty": one_empty,
            "coherence_rate": round(coherence_rate * 100, 2),
            "data_completeness": round(both_present / total * 100, 2) if total > 0 else 0,
        }

    @staticmethod
    def analyze_text_similarity(data: list[dict], col1: str, col2: str) -> dict:
        """
        Analyze text similarity between two columns.
        Useful for comparing 'Motif' vs 'Commentaires'.
        """
        import difflib

        similarities = []
        examples_high = []
        examples_low = []

        for row in data:
            text1 = str(row.get(col1, "")).lower()
            text2 = str(row.get(col2, "")).lower()

            if text1 and text2:
                # Simple similarity ratio
                similarity = difflib.SequenceMatcher(None, text1, text2).ratio()
                similarities.append(similarity)

                # Keep examples
                if len(examples_high) < 2 and similarity > 0.7:
                    examples_high.append({col1: row.get(col1), col2: row.get(col2), "similarity": round(similarity, 2)})
                elif len(examples_low) < 2 and similarity < 0.3:
                    examples_low.append({col1: row.get(col1), col2: row.get(col2), "similarity": round(similarity, 2)})

        if not similarities:
            return {"error": "No comparable data found"}

        avg_similarity = sum(similarities) / len(similarities)

        return {
            "average_similarity": round(avg_similarity * 100, 2),
            "high_similarity_count": sum(1 for s in similarities if s > 0.7),
            "low_similarity_count": sum(1 for s in similarities if s < 0.3),
            "examples_high": examples_high,
            "examples_low": examples_low,
        }

    @staticmethod
    def detect_patterns(data: list[dict], column: str) -> dict:
        """Detect patterns in a column."""
        values = [str(row.get(column, "")) for row in data if row.get(column)]

        if not values:
            return {"error": f"No data in column {column}"}

        # Frequency distribution
        counter = Counter(values)
        most_common = counter.most_common(10)

        # Unique ratio
        unique_count = len(counter)
        total_count = len(values)
        unique_ratio = unique_count / total_count if total_count > 0 else 0

        # Pattern detection (simple)
        patterns = {
            "numeric_only": sum(1 for v in values if v.replace(".", "").replace("-", "").isdigit()),
            "date_like": sum(1 for v in values if "/" in v or "-" in v),
            "email_like": sum(1 for v in values if "@" in v),
        }

        return {
            "total_values": total_count,
            "unique_values": unique_count,
            "unique_ratio": round(unique_ratio, 3),
            "most_common": most_common,
            "patterns": patterns,
        }

    @staticmethod
    def analyze_distribution(data: list[dict], column: str) -> dict:
        """Analyze distribution of values in a column."""
        values = [row.get(column) for row in data if row.get(column) is not None]

        if not values:
            return {"error": f"No data in column {column}"}

        # Try numeric analysis
        numeric_values = []
        for v in values:
            try:
                numeric_values.append(float(v))
            except (ValueError, TypeError):
                pass

        if numeric_values:
            return {
                "type": "numeric",
                "count": len(numeric_values),
                "min": min(numeric_values),
                "max": max(numeric_values),
                "mean": round(sum(numeric_values) / len(numeric_values), 2),
            }

        # Categorical analysis
        counter = Counter(str(v) for v in values)
        return {
            "type": "categorical",
            "count": len(values),
            "categories": len(counter),
            "distribution": counter.most_common(5),
        }


class OpenAnalysisEngine:
    """Engine for performing open-ended data analysis."""

    def __init__(self):
        self.tools = DataAnalysisTools()
        self.llm = None

    async def analyze(
        self,
        question: str,
        plugin: DataPlugin,
        session: ConversationSession | None = None,
    ) -> AnalysisResult:
        """
        Perform open analysis on data based on the question.

        Args:
            question: The user's question
            plugin: The data plugin to query
            session: Optional conversation session for context

        Returns:
            AnalysisResult with answer and metadata
        """
        if self.llm is None:
            self.llm = get_llm()

        # 1. Detect analysis type
        analysis_type = self._detect_analysis_type(question)

        # 2. Extract relevant data sample
        schema = plugin.get_schema()
        sample_data = await self._extract_sample_data(question, schema, plugin)

        if not sample_data:
            return AnalysisResult(
                answer="Je n'ai pas pu extraire de données pertinentes pour cette analyse.",
                analysis_type=analysis_type,
                confidence=0.0,
            )

        # 3. Perform specific analysis based on type
        analysis_data = self._perform_analysis(analysis_type, sample_data, question)

        # 4. Generate natural language response
        answer = await self._generate_analysis_response(
            question=question,
            analysis_type=analysis_type,
            analysis_data=analysis_data,
            sample_data=sample_data,
            schema=schema,
        )

        return AnalysisResult(
            answer=answer,
            analysis_type=analysis_type,
            confidence=0.85,
            supporting_data=analysis_data,
            sample_size=len(sample_data),
        )

    def _detect_analysis_type(self, question: str) -> AnalysisType:
        """Detect what type of analysis is requested."""
        question_lower = question.lower()

        if any(kw in question_lower for kw in ["cohérence", "cohérent", "correspond"]):
            return "coherence"
        elif any(kw in question_lower for kw in ["pattern", "tendance", "trend", "évolution"]):
            return "pattern"
        elif any(kw in question_lower for kw in ["corrélation", "lien", "relation", "dépend"]):
            return "correlation"
        elif any(kw in question_lower for kw in ["répartition", "distribution", "proportion"]):
            return "distribution"
        elif any(kw in question_lower for kw in ["qualité", "fiabilité", "manquante"]):
            return "quality"
        elif any(kw in question_lower for kw in ["anomalie", "outlier", "aberrant"]):
            return "anomaly"

        return "custom"

    async def _extract_sample_data(
        self,
        question: str,
        schema: Any,
        plugin: DataPlugin,
    ) -> list[dict]:
        """Extract a sample of relevant data for analysis."""
        from ndi_api.settings import settings

        # Check if user wants complete analysis
        question_lower = question.lower()
        wants_complete = any(
            kw in question_lower
            for kw in [
                "toutes les lignes",
                "complet",
                "intégral",
                "totalité",
                "all rows",
                "complete analysis",
                "full dataset",
            ]
        )

        # No row limit — analyse sur l'ensemble des données
        max_rows = getattr(settings, "analysis_max_rows", 0) or 0

        # Get all tables/collections
        tables = schema.tables if hasattr(schema, "tables") else []

        if not tables:
            return []

        # For now, use the first table or largest table
        target_table = tables[0].name

        # Query for all data (max_rows=0 means unlimited)
        try:
            fetch_limit = max_rows if max_rows > 0 else 999_999_999
            result = plugin.preview_table(target_table, limit=fetch_limit, offset=0)
            rows = result.rows if hasattr(result, "rows") else []
            return rows
        except Exception:
            return []

    def _perform_analysis(
        self,
        analysis_type: AnalysisType,
        data: list[dict],
        question: str,
    ) -> dict:
        """Perform the specific analysis based on type."""
        if not data:
            return {}

        # Extract column names mentioned in question
        columns = list(data[0].keys()) if data else []

        if analysis_type == "coherence":
            # Try to find two columns to compare
            if len(columns) >= 2:
                # Look for column pairs in question
                col1, col2 = self._find_column_pair(question, columns)
                if col1 and col2:
                    result = self.tools.analyze_coherence(data, col1, col2)
                    result["columns"] = [col1, col2]

                    # Also do text similarity if text columns
                    text_result = self.tools.analyze_text_similarity(data, col1, col2)
                    result["text_similarity"] = text_result

                    return result

            # Fallback: analyze coherence of first two columns
            return self.tools.analyze_coherence(data, columns[0], columns[1] if len(columns) > 1 else columns[0])

        elif analysis_type == "pattern":
            # Analyze first column with data
            for col in columns:
                result = self.tools.detect_patterns(data, col)
                if "error" not in result:
                    return result
            return {}

        elif analysis_type == "distribution":
            for col in columns:
                result = self.tools.analyze_distribution(data, col)
                if "error" not in result:
                    return result
            return {}

        elif analysis_type == "custom":
            # General analysis: basic stats on all columns
            results = {}
            for col in columns[:5]:  # Limit to first 5 columns
                result = self.tools.analyze_distribution(data, col)
                if "error" not in result:
                    results[col] = result
            return results

        return {}

    def _find_column_pair(self, question: str, columns: list[str]) -> tuple[str | None, str | None]:
        """Find two columns mentioned in the question."""
        question_lower = question.lower()
        found = []

        for col in columns:
            if col.lower() in question_lower:
                found.append(col)

        if len(found) >= 2:
            return found[0], found[1]

        # Look for "entre X et Y" pattern
        import re

        match = re.search(r"entre\s+(\w+)\s+et\s+(\w+)", question_lower)
        if match:
            col1, col2 = match.groups()
            # Find matching columns (case insensitive)
            for col in columns:
                if col.lower() == col1:
                    col1 = col
                if col.lower() == col2:
                    col2 = col
            return col1, col2

        return None, None

    async def _generate_analysis_response(
        self,
        question: str,
        analysis_type: AnalysisType,
        analysis_data: dict,
        sample_data: list[dict],
        schema: Any,
    ) -> str:
        """Generate a natural language response from analysis results."""

        # Build prompt for LLM
        prompt = self._build_analysis_prompt(question, analysis_type, analysis_data, sample_data, schema)

        # Log the prompt for debugging/monitoring
        logger.debug(f"Open Analysis Prompt ({analysis_type}):\n{prompt[:2000]}...")

        try:
            from ndi_api.services.llm import strip_thinking

            response = await self.llm.ainvoke(prompt)
            text = str(response.content if hasattr(response, "content") else response)
            return strip_thinking(text)
        except Exception:
            # Fallback: return raw analysis data
            return f"Analyse effectuée, mais je n'ai pas pu formuler la réponse. Données brutes:\n{json.dumps(analysis_data, indent=2, ensure_ascii=False)[:500]}"

    def _build_analysis_prompt(
        self,
        question: str,
        analysis_type: AnalysisType,
        analysis_data: dict,
        sample_data: list[dict],
        schema: Any,
    ) -> str:
        """Build the prompt for the LLM to generate analysis response."""

        type_instructions = {
            "coherence": """
FORMAT DE RÉPONSE ATTENDU (analyse de cohérence):
Présente les résultats sous forme de TABLEAU MARKDOWN avec les VRAIS noms des colonnes analysées:

| MOTIF | Commentaires Aléas | Évaluation | Justification |
|-------|-------------------|------------|---------------|
| Main d'Oeuvre | attente accord CN | ✅ | Motif = ressource, Commentaire = cause |
| Management | réunion planning | ✅ | Correspondance logique métier |

RÈGLES IMPORTANTES:
- Utilise les VRAIS noms des colonnes dans l'en-tête (pas "Colonne 1/2")
- Évaluation: ✅ = cohérent (fonction différente mais complémentaire), ❌ = contradiction
- Justification: 8-12 mots expliquant POURQUOI c'est cohérent ou non
- Montre 8-10 exemples VARIÉS (sauter des lignes pour avoir de la diversité)
- Si plusieurs motifs existent, montre au moins un exemple par motif
- Ajoute un résumé en 2 phrases max après le tableau
""",
            "pattern": """
FORMAT DE RÉPONSE ATTENDU (détection de patterns):
1. Pattern principal identifié
2. 3-5 exemples concrets
3. Fréquence/occurrence
""",
            "distribution": """
FORMAT DE RÉPONSE ATTENDU (distribution):
1. Tableau des valeurs principales + fréquences
2. Visualisation textuelle simple (barres ASCII si pertinent)
3. Observation clé en 1-2 phrases
""",
        }

        specific_instruction = type_instructions.get(analysis_type, "")

        system_prompt = get_agent_system_prompt(mode="open-analysis")

        prompt_parts = [
            f"[INSTRUCTIONS]\n{system_prompt}",
            "",
            f"[ANALYSE]\nQuestion: {question}",
            f"Type d'analyse: {analysis_type}",
            specific_instruction,
            "",
            "[DONNÉES]",
            json.dumps(analysis_data, indent=2, ensure_ascii=False),
            "",
            f"[ÉCHANTILLON] ({len(sample_data)} lignes) - 10 exemples variés:",
            json.dumps(sample_data[:: max(1, len(sample_data) // 10)][:10], indent=2, ensure_ascii=False),
            "",
            "[RÉPONSE]",
        ]

        return "\n".join(prompt_parts)


# Singleton instance
_analysis_engine: OpenAnalysisEngine | None = None


def get_open_analysis_engine() -> OpenAnalysisEngine:
    """Get or create the open analysis engine singleton."""
    global _analysis_engine
    if _analysis_engine is None:
        _analysis_engine = OpenAnalysisEngine()
    return _analysis_engine
