"""Tests for response_format module."""
import pytest
from response_format import (
    CodeBlock,
    ResponseFormatter,
    ResponseMetadata,
    StructuredResponse,
    ThinkingBlock,
)


class TestCodeBlock:
    def test_code_block_creation(self):
        cb = CodeBlock(language="python", code="print('hello')")
        assert cb.language == "python"
        assert cb.code == "print('hello')"
        assert cb.line_count == 1

    def test_code_block_multiline(self):
        cb = CodeBlock(language="js", code="line1\nline2\nline3")
        assert cb.line_count == 3


class TestThinkingBlock:
    def test_thinking_block(self):
        tb = ThinkingBlock(content="Let me think...", is_visible=True)
        assert tb.content == "Let me think..."
        assert tb.is_visible is True


class TestResponseMetadata:
    def test_default_values(self):
        meta = ResponseMetadata()
        assert meta.model == ""
        assert meta.tokens_used == 0
        assert meta.confidence == 0.0

    def test_custom_values(self):
        meta = ResponseMetadata(
            model="qwen2.5-coder:7b",
            tokens_used=150,
            confidence=0.95,
        )
        assert meta.model == "qwen2.5-coder:7b"
        assert meta.tokens_used == 150
        assert meta.confidence == 0.95


class TestStructuredResponse:
    def test_plain_text_formatting(self):
        resp = StructuredResponse(text="Hello world")
        assert resp.to_text() == "Hello world"

    def test_text_with_actions(self):
        resp = StructuredResponse(
            text="Here is the result",
            actions=["Run tests", "Deploy"],
        )
        text = resp.to_text()
        assert "Run tests" in text
        assert "Deploy" in text

    def test_markdown_formatting(self):
        resp = StructuredResponse(text="**Bold** text")
        md = resp.to_markdown()
        assert "**Bold** text" in md

    def test_telegram_formatting(self):
        resp = StructuredResponse(text="Hello <world>")
        tg = resp.to_telegram()
        assert "&lt;world&gt;" in tg  # HTML escaped

    def test_json_serialization(self):
        resp = StructuredResponse(
            text="Test",
            metadata=ResponseMetadata(model="test-model"),
        )
        data = resp.to_json()
        assert data["text"] == "Test"
        assert data["metadata"]["model"] == "test-model"


class TestResponseFormatter:
    def test_extract_code_blocks(self):
        formatter = ResponseFormatter()
        text = "```python\nprint('hi')\n```"
        result = formatter.format(text=text, model="test")
        assert len(result.code_blocks) == 1
        assert result.code_blocks[0].language == "python"

    def test_extract_thinking(self):
        formatter = ResponseFormatter()
        text = "<think>Let me analyze...</think>Answer is 42"
        result = formatter.format(text=text, model="test")
        assert result.thinking is not None
        assert "analyze" in result.thinking.content

    def test_extract_actions(self):
        formatter = ResponseFormatter()
        text = "You should: Run the tests first. Then deploy."
        result = formatter.format(text=text, model="test")
        assert len(result.actions) >= 1

    def test_metadata_passed_through(self):
        formatter = ResponseFormatter()
        result = formatter.format(
            text="Hello",
            model="qwen2.5-coder:7b",
            provider="ollama",
            metadata={"tokens_used": 100, "confidence": 0.9},
        )
        assert result.metadata.model == "qwen2.5-coder:7b"
        assert result.metadata.provider == "ollama"
        assert result.metadata.tokens_used == 100
        assert result.metadata.confidence == 0.9

    def test_tool_calls_count(self):
        formatter = ResponseFormatter()
        fake_tools = [{"name": "search"}, {"name": "read"}]
        result = formatter.format(text="Done", tool_calls=fake_tools, model="test")
        assert result.metadata.tool_calls_count == 2
