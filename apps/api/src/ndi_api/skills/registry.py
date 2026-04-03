"""Skill registry — auto-discovers and stores all available skills."""

from __future__ import annotations

import importlib
import logging
import pkgutil

from ndi_api.skills.base import SkillBase

logger = logging.getLogger(__name__)

# Global registry  (skill.name -> instance)
_registry: dict[str, SkillBase] = {}
_discovered = False


def register(skill: SkillBase) -> None:
    """Register a single skill instance."""
    if skill.name in _registry:
        logger.debug("Replacing skill %s", skill.name)
    _registry[skill.name] = skill


def get(name: str) -> SkillBase | None:
    """Lookup a skill by name. Triggers auto-discovery on first call."""
    _ensure_discovered()
    return _registry.get(name)


def all_skills() -> dict[str, SkillBase]:
    """Return a *copy* of the full registry."""
    _ensure_discovered()
    return dict(_registry)


def names() -> list[str]:
    """Return registered skill names."""
    _ensure_discovered()
    return list(_registry.keys())


def find_by_trigger(keyword: str) -> list[SkillBase]:
    """Return skills whose trigger list matches *keyword*."""
    _ensure_discovered()
    kw = keyword.lower()
    return [s for s in _registry.values() if any(kw in t.lower() for t in s.triggers)]


# ---------------------------------------------------------------------------
# Auto-discovery
# ---------------------------------------------------------------------------


def _ensure_discovered() -> None:
    global _discovered
    if _discovered:
        return
    _discover_builtin_skills()
    _discovered = True


def _discover_builtin_skills() -> None:
    """Walk ``ndi_api.skills.*`` sub-packages and import their ``skill`` module.

    Each ``skill.py`` is expected to call ``register()`` at import time
    (via a module-level ``register(SkillInstance)`` call in its ``__init__``
    or directly at the bottom of ``skill.py``).
    """
    import ndi_api.skills as skills_pkg

    for info in pkgutil.iter_modules(skills_pkg.__path__):
        if not info.ispkg:
            continue
        module_name = f"ndi_api.skills.{info.name}.skill"
        try:
            importlib.import_module(module_name)
            logger.debug("Discovered skill: %s", info.name)
        except ModuleNotFoundError:
            # Sub-package exists but has no skill.py — skip silently
            pass
        except Exception:
            logger.warning("Failed to load skill %s", module_name, exc_info=True)


def reset() -> None:
    """Clear the registry (useful in tests)."""
    global _discovered
    _registry.clear()
    _discovered = False
