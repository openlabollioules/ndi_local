#!/usr/bin/env python3
"""Utility script to manage agent skills and memory.

Usage:
    python manage_skills.py validate    # Validate all skill files
    python manage_skills.py info        # Show current configuration
    python manage_skills.py create-skill <name>  # Create a new skill template
    python manage_skills.py reload      # Invalidate cache (for hot reload)
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ndi_api.services import agent_prompts
from ndi_api.settings import settings


def validate():
    """Validate all skill files."""
    print("🔍 Validating agent prompts configuration...\n")

    # Check memory
    memory_info = agent_prompts.get_memory_info()
    print("📄 AGENTS.md:")
    print(f"   Configured: {'✅' if memory_info['base_dir_configured'] else '❌'}")
    print(f"   File exists: {'✅' if memory_info['has_content'] else '❌'}")
    if memory_info["file_path"]:
        print(f"   Path: {memory_info['file_path']}")
    print()

    # Check skills
    for mode in ["sql", "nosql"]:
        info = agent_prompts.get_skill_info(mode)
        print(f"🔧 {mode.upper()} Skill:")
        print(f"   Name: {info['name']}")
        print(f"   Description: {info['description'] or '(none)'}")
        print(f"   Version: {info['version'] or '(none)'}")
        print(f"   Has content: {'✅' if info['has_content'] else '❌ (will use fallback)'}")
        print()

    # Show combined prompt preview
    print("📝 Prompt Preview (first 500 chars):")
    print("-" * 50)
    from ndi_api.plugins.manager import get_plugin_manager

    plugin = get_plugin_manager().get_plugin()
    prompt = agent_prompts.get_system_prompt(plugin.mode, plugin.get_system_prompt())
    print(prompt[:500] + "..." if len(prompt) > 500 else prompt)


def info():
    """Show current configuration."""
    print("ℹ️  Agent Prompts Configuration\n")
    print(f"agents_base_dir: {settings.agents_base_dir or '(not set)'}")
    print(f"agents_memory_file: {settings.agents_memory_file}")
    print(f"agents_agents_skills_dir: {settings.agents_skills_dir}")
    print()

    base_dir = agent_prompts._get_agents_base_dir()
    if base_dir:
        print(f"Resolved base dir: {base_dir}")
        print("\nDirectory structure:")
        for path in sorted(base_dir.rglob("*.md")):
            rel_path = path.relative_to(base_dir)
            print(f"  📄 {rel_path}")
    else:
        print("⚠️  Base directory not configured or doesn't exist.")
        print("   Using fallback prompts from plugins.")


def create_skill(name: str):
    """Create a new skill template."""
    base_dir = agent_prompts._get_agents_base_dir()
    if not base_dir:
        print("❌ Error: agents_base_dir not configured")
        sys.exit(1)

    skill_dir = base_dir / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)

    skill_file = skill_dir / "SKILL.md"
    if skill_file.exists():
        print(f"⚠️  Skill '{name}' already exists at {skill_file}")
        return

    template = f"""---
name: {name}
description: Description of what this skill does
version: 1.0.0
tags: []
---

# Skill: {name}

## Description

Add your skill instructions here.

## Rules

1. Rule one
2. Rule two

## Examples

**Q:** Example question?
**A:** Example answer.
"""

    skill_file.write_text(template)
    print(f"✅ Created skill template at {skill_file}")


def reload():
    """Invalidate cache to reload files."""
    agent_prompts.invalidate_cache()
    print("🔄 Cache invalidated. Files will be reloaded on next request.")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "validate":
        validate()
    elif command == "info":
        info()
    elif command == "create-skill":
        if len(sys.argv) < 3:
            print("Usage: python manage_skills.py create-skill <name>")
            sys.exit(1)
        create_skill(sys.argv[2])
    elif command == "reload":
        reload()
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
