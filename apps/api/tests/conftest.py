"""Shared test fixtures.

Sets required env vars BEFORE any ndi_api module is imported,
then provides reusable mock objects.
"""

from __future__ import annotations

import os

# Set required env vars before importing ndi_api (settings validates on import)
os.environ.setdefault("NDI_LLM_BASE_URL", "http://localhost:9999/v1")
os.environ.setdefault("NDI_LLM_API_KEY", "test-key")
os.environ.setdefault("NDI_LLM_MODEL", "test-model")
os.environ.setdefault("NDI_EMBEDDING_MODEL", "test-embed")
os.environ.setdefault("NDI_AUTH_ENABLED", "false")

import pytest


@pytest.fixture()
def mock_llm_response(monkeypatch):
    """Patch get_llm().invoke() to return a fake AIMessage."""

    class FakeMessage:
        def __init__(self, content: str = "SELECT 1"):
            self.content = content

    class FakeLLM:
        def invoke(self, prompt, **kw):
            return FakeMessage()

        def stream(self, prompt, **kw):
            yield FakeMessage("SELECT 1")

    from ndi_api.services import llm

    monkeypatch.setattr(llm, "_llm_instance", FakeLLM())
    monkeypatch.setattr(llm, "_llm_model_key", "test-model")
    return FakeLLM
