"""Tests for TTL cache."""

import time

from ndi_api.services.cache import TTLCache, hash_question, hash_schema


class TestTTLCache:
    def test_set_and_get(self):
        c = TTLCache(default_ttl=60)
        c.set("k", "v")
        assert c.get("k") == "v"

    def test_expired(self):
        c = TTLCache(default_ttl=0)  # immediate expiry
        c.set("k", "v", ttl=0)
        time.sleep(0.01)
        assert c.get("k") is None

    def test_custom_ttl(self):
        c = TTLCache(default_ttl=0)
        c.set("k", "v", ttl=60)
        assert c.get("k") == "v"

    def test_delete(self):
        c = TTLCache()
        c.set("k", "v")
        c.delete("k")
        assert c.get("k") is None

    def test_clear(self):
        c = TTLCache()
        c.set("a", 1)
        c.set("b", 2)
        c.clear()
        assert c.get("a") is None
        assert c.get("b") is None

    def test_keys_excludes_expired(self):
        c = TTLCache(default_ttl=0)
        c.set("old", "x", ttl=0)
        time.sleep(0.01)
        c.set("new", "y", ttl=60)
        assert "new" in c.keys()
        assert "old" not in c.keys()


class TestHashing:
    def test_same_question_same_hash(self):
        h1 = hash_question("test", "schema1")
        h2 = hash_question("test", "schema1")
        assert h1 == h2

    def test_different_questions(self):
        h1 = hash_question("a", "s")
        h2 = hash_question("b", "s")
        assert h1 != h2

    def test_schema_hash_deterministic(self):
        schema = [{"name": "t", "columns": [{"name": "c", "type": "int"}]}]
        h1 = hash_schema(schema)
        h2 = hash_schema(schema)
        assert h1 == h2
