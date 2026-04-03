"""Tests for session skills — versioning, rollback, cleanup."""

import pytest

from ndi_api.services.session_skills import (
    clear_active_skill,
    clear_all_skills,
    get_active_skill,
    get_skill_history,
    rollback_skill,
    set_active_skill,
)


@pytest.fixture(autouse=True)
def _clean():
    """Ensure clean state between tests."""
    clear_all_skills()
    yield
    clear_all_skills()


class TestVersioning:
    def test_first_version_is_1(self):
        s = set_active_skill("s", "content", conversation_id="c1")
        assert s.version == 1

    def test_versions_increment(self):
        set_active_skill("s", "v1", conversation_id="c1")
        s2 = set_active_skill("s", "v2", source="refined", conversation_id="c1")
        assert s2.version == 2

    def test_active_is_latest(self):
        set_active_skill("s", "v1", conversation_id="c1")
        set_active_skill("s", "v2", conversation_id="c1")
        assert get_active_skill("c1").content == "v2"


class TestRollback:
    def test_rollback_returns_previous(self):
        set_active_skill("s", "v1", conversation_id="c1")
        set_active_skill("s", "v2", conversation_id="c1")
        prev = rollback_skill("c1")
        assert prev.version == 1
        assert prev.content == "v1"

    def test_rollback_on_single_version_returns_none(self):
        set_active_skill("s", "v1", conversation_id="c1")
        assert rollback_skill("c1") is None

    def test_rollback_on_empty_returns_none(self):
        assert rollback_skill("nonexistent") is None


class TestIsolation:
    def test_conversations_isolated(self):
        set_active_skill("a", "conv1", conversation_id="c1")
        set_active_skill("b", "conv2", conversation_id="c2")
        assert get_active_skill("c1").name == "a"
        assert get_active_skill("c2").name == "b"

    def test_clear_one_doesnt_affect_other(self):
        set_active_skill("a", "x", conversation_id="c1")
        set_active_skill("b", "y", conversation_id="c2")
        clear_active_skill("c1")
        assert get_active_skill("c1") is None
        assert get_active_skill("c2") is not None


class TestHistory:
    def test_history_length(self):
        set_active_skill("s", "v1", conversation_id="c1")
        set_active_skill("s", "v2", conversation_id="c1")
        set_active_skill("s", "v3", conversation_id="c1")
        h = get_skill_history("c1")
        assert len(h) == 3

    def test_history_empty(self):
        assert get_skill_history("nonexistent") == []


class TestCleanup:
    def test_global_default_key(self):
        s = set_active_skill("s", "content")
        assert s.version == 1
        assert get_active_skill() is not None

    def test_clear_all(self):
        set_active_skill("a", "x", conversation_id="c1")
        set_active_skill("b", "y", conversation_id="c2")
        count = clear_all_skills()
        assert count == 2
        assert get_active_skill("c1") is None
