"""NDI Skills package — structured skill architecture.

Usage::

    from ndi_api.skills import registry, get_skill_router

    # Get a specific skill
    sql_skill = registry.get("sql-query")

    # Resolve skills for a question
    router = get_skill_router()
    skills = router.resolve("montre les ventes en graphique", mode="sql")
    # -> [SQLQuerySkill, ChartGenSkill]
"""

from ndi_api.skills.registry import (  # noqa: F401
    all_skills,
    find_by_trigger,
    get,
    names,
    register,
    reset,
)
from ndi_api.skills.router import get_skill_router  # noqa: F401
