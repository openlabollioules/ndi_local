"""Tests for monitoring prompts sent to LLM in open analysis.

Usage:
    cd apps/api && uv run pytest tests/test_prompt_monitoring.py -v

To see prompts in real-time:
    uv run pytest tests/test_prompt_monitoring.py -v -s --log-cli-level=DEBUG
"""

import json
import logging
from unittest.mock import Mock

import pytest

# Configure logging to see prompts
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s | %(name)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


class TestPromptMonitoring:
    """Monitor and validate prompts sent to LLM."""

    def test_coherence_prompt_structure(self):
        """Test that coherence analysis prompts have correct structure."""
        from ndi_api.services.open_analysis import OpenAnalysisEngine

        engine = OpenAnalysisEngine()

        # Mock data
        sample_data = [
            {"MOTIF": "Main d'Oeuvre", "Commentaires": "attente consignation"},
            {"MOTIF": "Matière", "Commentaires": "manque appro"},
        ]
        analysis_data = {
            "coherence_rate": 95.0,
            "total_rows": 100,
        }
        schema = Mock()
        schema.tables = []

        # Build prompt
        prompt = engine._build_analysis_prompt(
            question="analyse la cohérence entre MOTIF et Commentaires",
            analysis_type="coherence",
            analysis_data=analysis_data,
            sample_data=sample_data,
            schema=schema,
        )

        # Log the full prompt
        logger.info("=" * 80)
        logger.info("COHERENCE ANALYSIS PROMPT:")
        logger.info("=" * 80)
        logger.info(prompt)
        logger.info("=" * 80)

        # Assertions
        assert "Tu es un analyste de données expert" in prompt
        assert "FORMAT DE RÉPONSE ATTENDU" in prompt
        assert "analyse de cohérence" in prompt
        assert "MOTIF" in prompt
        assert "Commentaires" in prompt
        assert "coherence_rate" in prompt
        assert "Main d'Oeuvre" in prompt

    def test_prompt_length_limits(self):
        """Ensure prompts don't exceed token limits."""
        from ndi_api.services.open_analysis import OpenAnalysisEngine

        engine = OpenAnalysisEngine()

        # Large sample data
        sample_data = [{f"col_{i}": f"value_{i}" * 100} for i in range(100)]
        analysis_data = {"test": "data"}
        schema = Mock()
        schema.tables = []

        prompt = engine._build_analysis_prompt(
            question="test analysis",
            analysis_type="coherence",
            analysis_data=analysis_data,
            sample_data=sample_data,
            schema=schema,
        )

        # Log prompt size
        logger.info(f"Prompt size: {len(prompt)} characters")
        logger.info(f"Approximate tokens: {len(prompt) // 4}")  # Rough estimate

        # Check that it's under reasonable limits (32k context ~ 24k for prompt)
        assert len(prompt) < 100000, "Prompt too large, risk of exceeding context window"

    def test_coherence_prompt_format_specifications(self):
        """Verify coherence prompts contain all format specifications."""
        from ndi_api.services.open_analysis import OpenAnalysisEngine

        engine = OpenAnalysisEngine()

        prompt = engine._build_analysis_prompt(
            question="analyse la cohérence",
            analysis_type="coherence",
            analysis_data={},
            sample_data=[],
            schema=Mock(),
        )

        required_elements = [
            "FORMAT DE RÉPONSE ATTENDU",
            "RÈGLES IMPORTANTES",
            "Évaluation",
            "Justification",
            "TABLEAU MARKDOWN",
            "résumé",  # minuscule dans le prompt
        ]

        for element in required_elements:
            assert element in prompt, f"Missing required element: {element}"
            logger.info(f"✓ Found: {element}")

    def test_sample_data_in_prompt(self):
        """Verify sample data is correctly included in prompt."""
        from ndi_api.services.open_analysis import OpenAnalysisEngine

        engine = OpenAnalysisEngine()

        sample_data = [
            {"MOTIF": "Test1", "Commentaires": "Comment1"},
            {"MOTIF": "Test2", "Commentaires": "Comment2"},
        ]

        prompt = engine._build_analysis_prompt(
            question="test",
            analysis_type="coherence",
            analysis_data={},
            sample_data=sample_data,
            schema=Mock(),
        )

        # Log sample data portion
        logger.info("Sample data included in prompt:")
        logger.info(json.dumps(sample_data, indent=2, ensure_ascii=False))

        assert "Test1" in prompt
        assert "Comment1" in prompt
        assert "Échantillon de données" in prompt


class TestPromptOutputCapture:
    """Capture and display actual prompts that would be sent."""

    @pytest.mark.skip(reason="Run manually to see actual prompts: pytest -v -s -k test_display")
    def test_display_actual_coherence_prompt(self):
        """Display the actual prompt for coherence analysis."""
        from ndi_api.services.open_analysis import OpenAnalysisEngine

        engine = OpenAnalysisEngine()

        # Realistic sample
        sample_data = [
            {"MOTIF": "Main d'Oeuvre", "Commentaires Aléas": "attente accord CN"},
            {"MOTIF": "Matière", "Commentaires Aléas": "manque appro"},
            {"MOTIF": "Management", "Commentaires Aléas": "réunion planning"},
        ]

        analysis_data = {
            "total_rows": 240,
            "coherence_rate": 100.0,
            "both_present": 240,
            "text_similarity": {"average": 21.5},
        }

        prompt = engine._build_analysis_prompt(
            question="analyse la cohérence entre MOTIF et Commentaires Aléas",
            analysis_type="coherence",
            analysis_data=analysis_data,
            sample_data=sample_data,
            schema=Mock(),
        )

        print("\n" + "=" * 80)
        print("FULL PROMPT SENT TO LLM:")
        print("=" * 80)
        print(prompt)
        print("=" * 80)
        print(f"Total length: {len(prompt)} chars")
        print(f"Estimated tokens: ~{len(prompt) // 4}")


def run_manual_prompt_inspection():
    """Run this directly to see prompts: python test_prompt_monitoring.py"""
    import sys

    # Configure detailed logging
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(levelname)s: %(message)s")
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(handler)

    print("\n" + "=" * 80)
    print("PROMPT MONITORING TEST")
    print("=" * 80 + "\n")

    from ndi_api.services.open_analysis import OpenAnalysisEngine

    engine = OpenAnalysisEngine()

    # Test coherence prompt
    sample_data = [
        {"MOTIF": "Main d'Oeuvre", "Commentaires Aléas": "attente consignation"},
        {"MOTIF": "Matière", "Commentaires Aléas": "manque appro fournisseur"},
    ]

    prompt = engine._build_analysis_prompt(
        question="analyse la cohérence entre MOTIF et Commentaires Aléas",
        analysis_type="coherence",
        analysis_data={"test": "data"},
        sample_data=sample_data,
        schema=Mock(),
    )

    print("\n" + "=" * 80)
    print("COMPLETE PROMPT:")
    print("=" * 80)
    print(prompt)
    print("=" * 80)


if __name__ == "__main__":
    run_manual_prompt_inspection()
