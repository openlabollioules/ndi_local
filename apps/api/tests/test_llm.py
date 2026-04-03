"""Tests for LLM service — strip_thinking and stream detection."""

from ndi_api.services.llm import strip_thinking


class TestStripThinking:
    def test_standard_think_tags(self):
        assert strip_thinking("<think>reasoning</think>SELECT 1") == "SELECT 1"

    def test_multiline_think(self):
        text = "<think>\n1. step one\n2. step two\n</think>\nSELECT * FROM t"
        assert strip_thinking(text) == "SELECT * FROM t"

    def test_thinking_process_colon(self):
        text = "Thinking Process:\n1. analyze\n2. decide\n</think>\nSELECT 1"
        assert strip_thinking(text) == "SELECT 1"

    def test_thinking_process_no_colon(self):
        text = "Thinking Process\nblah\n</think>\nHello"
        assert strip_thinking(text) == "Hello"

    def test_lowercase(self):
        text = "thinking process:\nblah\n</think>\nresult"
        assert strip_thinking(text) == "result"

    def test_no_thinking(self):
        assert strip_thinking("SELECT * FROM t LIMIT 10") == "SELECT * FROM t LIMIT 10"

    def test_empty(self):
        assert strip_thinking("") == ""

    def test_only_thinking(self):
        result = strip_thinking("<think>only reasoning</think>")
        assert result == ""

    def test_whitespace_after_close(self):
        text = "<think>x</think>   \n\n  SELECT 1"
        assert strip_thinking(text) == "SELECT 1"
