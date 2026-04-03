"""Tests for agent prompts loader (AGENTS.md + SKILL.md)."""

from unittest.mock import patch

import pytest

from ndi_api.services import agent_prompts


class TestAgentPrompts:
    """Test suite for agent prompts loader."""

    def test_parse_frontmatter_with_yaml(self):
        """Test parsing of frontmatter with YAML metadata."""
        content = """---
name: test-skill
description: A test skill
version: 1.0.0
---

# Skill Content

This is the body.
"""
        metadata, body = agent_prompts._parse_frontmatter(content)

        assert metadata["name"] == "test-skill"
        assert metadata["description"] == "A test skill"
        assert metadata["version"] == "1.0.0"
        assert "# Skill Content" in body
        assert "This is the body." in body

    def test_parse_frontmatter_without_yaml(self):
        """Test parsing of content without frontmatter."""
        content = "# Just markdown\n\nNo frontmatter here."
        metadata, body = agent_prompts._parse_frontmatter(content)

        assert metadata == {}
        assert body == content

    def test_parse_frontmatter_empty(self):
        """Test parsing of empty content."""
        metadata, body = agent_prompts._parse_frontmatter("")
        assert metadata == {}
        assert body == ""

    def test_load_memory_no_config(self):
        """Test load_memory when agents_base_dir is not configured."""
        with patch.object(agent_prompts.settings, "agents_base_dir", None):
            agent_prompts.load_memory.cache_clear()
            result = agent_prompts.load_memory()
            assert result == ""

    def test_load_memory_file_not_found(self):
        """Test load_memory when AGENTS.md doesn't exist."""
        with patch.object(agent_prompts.settings, "agents_base_dir", "/nonexistent"):
            agent_prompts.load_memory.cache_clear()
            result = agent_prompts.load_memory()
            assert result == ""

    def test_load_skill_no_config(self):
        """Test load_skill when agents_base_dir is not configured."""
        with patch.object(agent_prompts.settings, "agents_base_dir", None):
            agent_prompts.load_skill.cache_clear()
            skill = agent_prompts.load_skill("sql")
            assert skill.content == ""
            assert skill.name == "sql-query"

    def test_load_skill_open_analysis(self):
        """Test load_skill for open-analysis mode."""
        with patch.object(agent_prompts.settings, "agents_base_dir", None):
            agent_prompts.load_skill.cache_clear()
            skill = agent_prompts.load_skill("open-analysis")
            assert skill.name == "open-analysis"

    def test_load_skill_file_not_found(self):
        """Test load_skill when SKILL.md doesn't exist."""
        with patch.object(agent_prompts.settings, "agents_base_dir", "/nonexistent"):
            agent_prompts.load_skill.cache_clear()
            skill = agent_prompts.load_skill("sql")
            assert skill.content == ""

    def test_get_system_prompt_with_files(self, tmp_path):
        """Test get_system_prompt with actual files."""
        # Create directory structure
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        skills_dir = agents_dir / "skills" / "sql-query"
        skills_dir.mkdir(parents=True)

        # Create AGENTS.md
        (agents_dir / "AGENTS.md").write_text("# Memory\n\nGlobal instructions.")

        # Create SKILL.md
        (skills_dir / "SKILL.md").write_text("""---
name: sql-query
description: SQL generation
---

# SQL Skill

Generate SQL queries.
""")

        with patch.object(agent_prompts.settings, "agents_base_dir", str(agents_dir)):
            agent_prompts.invalidate_cache()
            result = agent_prompts.get_system_prompt("sql", "FALLBACK")

            assert "Global instructions" in result
            assert "SQL Skill" in result
            assert "FALLBACK" not in result
            assert "---" in result  # Separator

    def test_get_system_prompt_fallback(self, tmp_path):
        """Test get_system_prompt falls back to plugin when files missing."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()

        with patch.object(agent_prompts.settings, "agents_base_dir", str(agents_dir)):
            agent_prompts.invalidate_cache()
            result = agent_prompts.get_system_prompt("sql", "PLUGIN_FALLBACK")

            assert "PLUGIN_FALLBACK" in result

    def test_get_system_prompt_partial(self, tmp_path):
        """Test get_system_prompt with only memory file."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "AGENTS.md").write_text("# Memory")

        with patch.object(agent_prompts.settings, "agents_base_dir", str(agents_dir)):
            agent_prompts.invalidate_cache()
            result = agent_prompts.get_system_prompt("sql", "FALLBACK")

            assert "# Memory" in result
            assert "FALLBACK" in result  # Skill falls back

    def test_skill_info(self, tmp_path):
        """Test get_skill_info returns correct metadata."""
        agents_dir = tmp_path / "agents"
        skills_dir = agents_dir / "skills" / "nosql-query"
        skills_dir.mkdir(parents=True)

        (skills_dir / "SKILL.md").write_text("""---
name: nosql-query
description: NoSQL queries
version: 2.0.0
---

Content here.
""")

        with patch.object(agent_prompts.settings, "agents_base_dir", str(agents_dir)):
            agent_prompts.invalidate_cache()
            info = agent_prompts.get_skill_info("nosql")

            assert info["name"] == "nosql-query"
            assert info["description"] == "NoSQL queries"
            assert info["version"] == "2.0.0"
            assert info["has_content"] is True

    def test_memory_info(self, tmp_path):
        """Test get_memory_info returns correct info."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "AGENTS.md").write_text("# Memory")

        with patch.object(agent_prompts.settings, "agents_base_dir", str(agents_dir)):
            agent_prompts.invalidate_cache()
            info = agent_prompts.get_memory_info()

            assert info["has_content"] is True
            assert info["base_dir_configured"] is True
            assert str(agents_dir) in info["file_path"]

    def test_invalidate_cache(self):
        """Test that invalidate_cache clears the cache."""
        # Just verify it doesn't crash
        agent_prompts.invalidate_cache()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
