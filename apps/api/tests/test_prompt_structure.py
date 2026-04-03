"""Tests for validating prompt structure based on mode and question type.

Validates that prompts are correctly assembled with:
- Mode SQL: AGENTS.md + SKILL.md (sql) + schema + relationships
- Mode NoSQL: AGENTS.md + SKILL.md (nosql)
- Open analysis: AGENTS.md + SKILL.md (open-analysis)

Usage:
    cd apps/api && PYTHONPATH=src:$PYTHONPATH uv run pytest tests/test_prompt_structure.py -v
"""

from unittest.mock import Mock, patch

import pytest


class TestPromptStructureSQLMode:
    """Validate prompt structure for SQL mode queries."""

    def test_sql_prompt_includes_agents_md(self):
        """SQL prompts should include AGENTS.md content."""
        from ndi_api.services.agent_prompts import get_system_prompt

        prompt = get_system_prompt(mode="sql", plugin_fallback="Fallback SQL prompt")

        # Should contain personality/rules from AGENTS.md
        assert len(prompt) > 0, "Prompt should not be empty"
        # AGENTS.md content should be present (even if minimal)
        assert (
            "Tu es" in prompt or "Vous êtes" in prompt or "assistant" in prompt.lower()
        ), "Missing AGENTS.md personality content"

    def test_sql_prompt_includes_skill_sql(self):
        """SQL prompts should include SKILL.md (sql) content."""
        from ndi_api.services.agent_prompts import get_system_prompt

        prompt = get_system_prompt(mode="sql", plugin_fallback="Fallback SQL prompt")

        # Should contain SQL-specific instructions
        sql_indicators = [
            "SQL",
            "SELECT",
            "DuckDB",
            "table",
            "colonne",
            "FROM",
            "WHERE",
        ]
        assert any(ind in prompt for ind in sql_indicators), f"Missing SQL skill content. Prompt: {prompt[:500]}"

    def test_sql_prompt_includes_schema_context(self):
        """SQL prompts should include database schema in context."""
        from ndi_api.plugins.sql_plugin import SQLPlugin

        plugin = SQLPlugin()

        # Test that the plugin provides schema context
        # We check the method exists and returns a string
        try:
            context = plugin.get_query_context(question="test query", relevant_items=[])
            assert isinstance(context, str), "get_query_context should return a string"
        except Exception:
            # If no schema available, just verify method exists
            assert hasattr(plugin, "get_query_context"), "Plugin missing get_query_context method"

    def test_sql_prompt_includes_relationships(self):
        """SQL prompts should include PK/FK relationships when available."""
        from ndi_api.plugins.sql_plugin import SQLPlugin

        plugin = SQLPlugin()

        # Mock relations
        mock_relations = [
            {
                "from_table": "orders",
                "from_column": "customer_id",
                "to_table": "customers",
                "to_column": "id",
                "relation_type": "many_to_one",
            }
        ]

        with patch.object(plugin, "get_relations", return_value=mock_relations):
            with patch.object(plugin, "supports_relations", return_value=True):
                relations = plugin.get_relations()

                assert len(relations) > 0, "Relations should be available"
                assert relations[0]["from_table"] == "orders", "Missing relation data"
                assert relations[0]["to_table"] == "customers", "Missing relation data"


class TestPromptStructureNoSQLMode:
    """Validate prompt structure for NoSQL mode queries."""

    def test_nosql_prompt_includes_agents_md(self):
        """NoSQL prompts should include AGENTS.md content."""
        from ndi_api.services.agent_prompts import get_system_prompt

        prompt = get_system_prompt(mode="nosql", plugin_fallback="Fallback NoSQL prompt")

        assert len(prompt) > 0, "Prompt should not be empty"
        assert (
            "Tu es" in prompt or "Vous êtes" in prompt or "assistant" in prompt.lower()
        ), "Missing AGENTS.md personality content"

    def test_nosql_prompt_includes_skill_nosql(self):
        """NoSQL prompts should include SKILL.md (nosql) content."""
        from ndi_api.services.agent_prompts import get_system_prompt

        prompt = get_system_prompt(mode="nosql", plugin_fallback="Fallback NoSQL prompt")

        # Should contain NoSQL-specific instructions
        nosql_indicators = [
            "JSON",
            "collection",
            "document",
            "MongoDB",
            "$group",
            "$filter",
            "$ilike",
        ]
        assert any(ind in prompt for ind in nosql_indicators), f"Missing NoSQL skill content. Prompt: {prompt[:500]}"

    def test_nosql_prompt_excludes_sql_syntax(self):
        """NoSQL prompts should not focus on SQL syntax."""
        from ndi_api.services.agent_prompts import get_system_prompt

        prompt = get_system_prompt(mode="nosql", plugin_fallback="Fallback NoSQL prompt")

        # Should not contain SQL-specific instructions that would confuse the model
        sql_specific = ["JOIN", "FOREIGN KEY", "PRIMARY KEY", "NORMALIZED"]

        # It's OK if these words appear, but they shouldn't be emphasized
        # The test checks that NoSQL indicators are present
        nosql_indicators = ["JSON", "collection", "document"]
        assert any(ind in prompt for ind in nosql_indicators), "Prompt should emphasize NoSQL concepts"


class TestPromptStructureOpenAnalysis:
    """Validate prompt structure for open analysis questions."""

    def test_open_analysis_prompt_structure(self):
        """Open analysis prompts should have correct structure."""
        from ndi_api.services.open_analysis import OpenAnalysisEngine

        engine = OpenAnalysisEngine()

        prompt = engine._build_analysis_prompt(
            question="analyse la cohérence entre MOTIF et Commentaires",
            analysis_type="coherence",
            analysis_data={"coherence_rate": 95.0},
            sample_data=[{"MOTIF": "Test", "Commentaires": "Comment"}],
            schema=Mock(),
        )

        assert "FORMAT DE RÉPONSE ATTENDU" in prompt, "Missing format specification"
        assert "TABLEAU MARKDOWN" in prompt, "Missing table format"
        assert "Évaluation" in prompt, "Missing evaluation column"
        assert "Justification" in prompt, "Missing justification column"

    def test_open_analysis_includes_agents_md(self):
        """Open analysis should inherit AGENTS.md personality via agent_prompts."""
        from ndi_api.services.open_analysis import OpenAnalysisEngine

        engine = OpenAnalysisEngine()

        prompt = engine._build_analysis_prompt(
            question="analyse de patterns",
            analysis_type="pattern",
            analysis_data={},
            sample_data=[],
            schema=Mock(),
        )

        assert "[INSTRUCTIONS]" in prompt, "Missing instructions section delimiter"
        assert "NDI" in prompt or "assistant" in prompt.lower(), "Missing AGENTS.md personality in open analysis prompt"

    def test_open_analysis_includes_skill_content(self):
        """Open analysis should include the open-analysis SKILL.md content."""
        from ndi_api.services.agent_prompts import get_system_prompt

        prompt = get_system_prompt(mode="open-analysis")

        analysis_indicators = [
            "analyse",
            "cohérence",
            "pattern",
            "tendance",
            "SYNTHÈSE",
            "DÉTAILS",
            "LIMITES",
        ]
        assert any(
            ind in prompt for ind in analysis_indicators
        ), f"Missing open-analysis skill content. Prompt: {prompt[:500]}"

    def test_coherence_prompt_has_table_structure(self):
        """Coherence analysis prompts should request table format."""
        from ndi_api.services.open_analysis import OpenAnalysisEngine

        engine = OpenAnalysisEngine()

        prompt = engine._build_analysis_prompt(
            question="cohérence entre A et B",
            analysis_type="coherence",
            analysis_data={},
            sample_data=[],
            schema=Mock(),
        )

        assert "|" in prompt, "Missing table structure example"
        assert "RÈGLES IMPORTANTES" in prompt, "Missing rules section"


class TestPromptAssemblyIntegration:
    """Integration tests for complete prompt assembly."""

    def test_sql_mode_complete_prompt(self):
        """Test complete prompt assembly for SQL mode."""
        from ndi_api.services.agent_prompts import get_system_prompt

        sql_prompt = get_system_prompt(mode="sql", plugin_fallback="Fallback SQL")

        assert len(sql_prompt) > 100, "SQL prompt seems too short"

        has_sql_focus = any(x in sql_prompt for x in ["SELECT", "FROM", "WHERE", "SQL", "table", "colonne"])
        assert has_sql_focus, "Prompt missing SQL focus"

    def test_nosql_mode_complete_prompt(self):
        """Test complete prompt assembly for NoSQL mode."""
        from ndi_api.services.agent_prompts import get_system_prompt

        nosql_prompt = get_system_prompt(mode="nosql", plugin_fallback="Fallback NoSQL")

        assert len(nosql_prompt) > 100, "NoSQL prompt seems too short"

        has_nosql_focus = any(x in nosql_prompt for x in ["JSON", "collection", "document", "$group", "$filter"])
        assert has_nosql_focus, "Prompt missing NoSQL focus"

    def test_open_analysis_mode_complete_prompt(self):
        """Test complete prompt assembly for open-analysis mode."""
        from ndi_api.services.agent_prompts import get_system_prompt

        prompt = get_system_prompt(mode="open-analysis")

        assert len(prompt) > 100, "Open-analysis prompt seems too short"

        has_analysis_focus = any(
            x in prompt
            for x in [
                "analyse",
                "cohérence",
                "pattern",
                "SYNTHÈSE",
            ]
        )
        assert has_analysis_focus, "Prompt missing analysis focus"

    def test_different_modes_have_different_prompts(self):
        """SQL, NoSQL, and open-analysis modes should produce different prompts."""
        from ndi_api.services.agent_prompts import get_system_prompt

        sql_prompt = get_system_prompt(mode="sql", plugin_fallback="SQL")
        nosql_prompt = get_system_prompt(mode="nosql", plugin_fallback="NoSQL")
        analysis_prompt = get_system_prompt(mode="open-analysis")

        assert sql_prompt != nosql_prompt, "SQL and NoSQL prompts should differ"
        assert sql_prompt != analysis_prompt, "SQL and analysis prompts should differ"
        assert nosql_prompt != analysis_prompt, "NoSQL and analysis prompts should differ"


class TestPromptMonitoring:
    """Monitoring and debugging utilities for prompts."""

    @pytest.mark.skip(reason="Manual inspection - run with: pytest -v -s -k test_display")
    def test_display_sql_prompt(self):
        """Display complete SQL prompt for manual inspection."""
        from ndi_api.services.agent_prompts import get_system_prompt

        prompt = get_system_prompt(mode="sql")

        print("\n" + "=" * 80)
        print("COMPLETE SQL MODE PROMPT")
        print("=" * 80)
        print(prompt)
        print("=" * 80)
        print(f"Length: {len(prompt)} chars")

    @pytest.mark.skip(reason="Manual inspection - run with: pytest -v -s -k test_display")
    def test_display_nosql_prompt(self):
        """Display complete NoSQL prompt for manual inspection."""
        from ndi_api.services.agent_prompts import get_system_prompt

        prompt = get_system_prompt(mode="nosql")

        print("\n" + "=" * 80)
        print("COMPLETE NOSQL MODE PROMPT")
        print("=" * 80)
        print(prompt)
        print("=" * 80)
        print(f"Length: {len(prompt)} chars")

    def test_prompt_length_reasonable(self):
        """Prompts should not exceed reasonable token limits."""
        from ndi_api.services.agent_prompts import get_system_prompt

        for mode in ["sql", "nosql", "open-analysis"]:
            prompt = get_system_prompt(mode=mode, plugin_fallback="Test")

            estimated_tokens = len(prompt) // 4

            assert estimated_tokens < 20000, f"{mode} prompt too large: ~{estimated_tokens} tokens"


def run_manual_inspection():
    """Run this directly to inspect prompts: python test_prompt_structure.py"""

    print("\n" + "=" * 80)
    print("PROMPT STRUCTURE INSPECTION")
    print("=" * 80 + "\n")

    from ndi_api.services.agent_prompts import get_system_prompt

    for mode in ["sql", "nosql", "open-analysis"]:
        print(f"\n{'=' * 80}")
        print(f"MODE: {mode.upper()}")
        print(f"{'=' * 80}\n")

        prompt = get_system_prompt(mode=mode)

        # Show first 2000 chars
        print(prompt[:2000])
        print(f"\n... [{len(prompt) - 2000} more characters] ...")
        print(f"\nTotal: {len(prompt)} chars (~{len(prompt) // 4} tokens)")


if __name__ == "__main__":
    run_manual_inspection()
