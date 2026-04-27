"""
NEUGI v2 Structured Response Format
======================================
Rich, structured agent responses with metadata.

Features:
    - Markdown rendering with code block detection
    - Response metadata (model, tokens, confidence, timing)
    - Thinking/reasoning extraction
    - Tool call history
    - Citations and sources
    - Structured sections (summary, details, actions)

Usage:
    from response_format import StructuredResponse, ResponseFormatter
    
    formatter = ResponseFormatter()
    response = formatter.format(
        text=llm_response.content,
        tool_calls=llm_response.tool_calls,
        model="qwen2.5-coder:7b",
        metadata={"thinking": "...", "confidence": 0.95}
    )
    
    # Render for different channels
    text_output = response.to_text()
    html_output = response.to_html()
    markdown_output = response.to_markdown()
    telegram_output = response.to_telegram()
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CodeBlock:
    """A code block extracted from response."""
    language: str
    code: str
    line_count: int = 0
    
    def __post_init__(self):
        self.line_count = len(self.code.splitlines())


@dataclass
class Citation:
    """A citation/source reference."""
    source: str
    url: str = ""
    snippet: str = ""
    confidence: float = 1.0


@dataclass
class ThinkingBlock:
    """Extracted thinking/reasoning block."""
    content: str
    is_visible: bool = False  # Whether to show thinking to user


@dataclass
class ResponseSection:
    """A section of the response."""
    title: str
    content: str
    section_type: str = "text"  # text, warning, info, code, action


@dataclass
class ResponseMetadata:
    """Metadata about the response generation."""
    model: str = ""
    provider: str = ""
    tokens_used: int = 0
    tokens_input: int = 0
    tokens_output: int = 0
    generation_time_seconds: float = 0.0
    finish_reason: str = ""
    confidence: float = 0.0
    tool_calls_count: int = 0
    memory_recalls: int = 0
    skills_used: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


@dataclass
class StructuredResponse:
    """
    A fully structured agent response.
    
    Contains:
        - text: Main response text
        - sections: Named sections
        - code_blocks: Extracted code
        - thinking: Reasoning process
        - citations: Sources
        - actions: Suggested actions
        - metadata: Generation info
    """
    text: str = ""
    sections: List[ResponseSection] = field(default_factory=list)
    code_blocks: List[CodeBlock] = field(default_factory=list)
    thinking: Optional[ThinkingBlock] = None
    citations: List[Citation] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    metadata: ResponseMetadata = field(default_factory=ResponseMetadata)
    raw_response: str = ""  # Original LLM output
    
    # ==================== FORMATTERS ====================
    
    def to_text(self, include_metadata: bool = False) -> str:
        """Format as plain text."""
        parts = [self.text]
        
        if self.actions:
            parts.append("\nSuggested actions:")
            for i, action in enumerate(self.actions, 1):
                parts.append(f"  {i}. {action}")
        
        if include_metadata and self.metadata.model:
            parts.append(f"\n---\nModel: {self.metadata.model} | "
                        f"Tokens: {self.metadata.tokens_used} | "
                        f"Time: {self.metadata.generation_time_seconds:.2f}s")
        
        return "\n".join(parts)
    
    def to_markdown(self, include_metadata: bool = False) -> str:
        """Format as markdown."""
        parts = []
        
        # Main text
        parts.append(self.text)
        
        # Thinking (if visible)
        if self.thinking and self.thinking.is_visible:
            parts.append(f"\n<details>\n<summary>Thinking</summary>\n\n{self.thinking.content}\n</details>")
        
        # Actions
        if self.actions:
            parts.append("\n### Suggested Actions")
            for action in self.actions:
                parts.append(f"- {action}")
        
        # Citations
        if self.citations:
            parts.append("\n### Sources")
            for cite in self.citations:
                if cite.url:
                    parts.append(f"- [{cite.source}]({cite.url})")
                else:
                    parts.append(f"- {cite.source}")
        
        # Metadata
        if include_metadata and self.metadata.model:
            parts.append(f"\n---\n*Model: `{self.metadata.model}` | "
                        f"Tokens: {self.metadata.tokens_used} | "
                        f"Time: {self.metadata.generation_time_seconds:.2f}s*")
        
        return "\n".join(parts)
    
    def to_html(self, include_metadata: bool = False) -> str:
        """Format as HTML."""
        parts = ["<div class=\"neugi-response\">"]
        
        # Main text (convert markdown-like to HTML)
        text_html = self._markdown_to_html(self.text)
        parts.append(f"<div class=\"response-text\">{text_html}</div>")
        
        # Code blocks
        for block in self.code_blocks:
            lang = block.language or "text"
            parts.append(f'<pre class=\"code-block\" data-language=\"{lang}\">')
            parts.append(f'<code class=\"language-{lang}\">{self._escape_html(block.code)}</code>')
            parts.append('</pre>')
        
        # Actions
        if self.actions:
            parts.append('<div class=\"suggested-actions\"><h4>Actions</h4><ul>')
            for action in self.actions:
                parts.append(f"<li>{self._escape_html(action)}</li>")
            parts.append('</ul></div>')
        
        # Metadata
        if include_metadata and self.metadata.model:
            parts.append('<div class=\"response-meta\">')
            parts.append(f'<span class=\"model\">{self._escape_html(self.metadata.model)}</span>')
            parts.append(f'<span class=\"tokens\">{self.metadata.tokens_used} tokens</span>')
            parts.append(f'<span class=\"time\">{self.metadata.generation_time_seconds:.2f}s</span>')
            parts.append('</div>')
        
        parts.append("</div>")
        return "\n".join(parts)
    
    def to_telegram(self, max_length: int = 4000) -> str:
        """Format for Telegram (HTML parse mode)."""
        text = self.text
        
        # Truncate if too long
        if len(text) > max_length:
            text = text[:max_length - 100] + "\n\n[...message truncated]"
        
        # Escape HTML special chars in text (Telegram HTML mode)
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        
        # Convert markdown code blocks to Telegram HTML
        text = self._markdown_to_telegram_html(text)
        
        # Add actions
        if self.actions:
            text += "\n\n<b>Actions:</b>\n"
            for action in self.actions[:3]:  # Limit actions
                text += f"  {action}\n"
        
        return text
    
    def to_json(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "text": self.text,
            "sections": [
                {"title": s.title, "content": s.content, "type": s.section_type}
                for s in self.sections
            ],
            "code_blocks": [
                {"language": cb.language, "code": cb.code, "lines": cb.line_count}
                for cb in self.code_blocks
            ],
            "thinking": {
                "content": self.thinking.content if self.thinking else "",
                "visible": self.thinking.is_visible if self.thinking else False,
            },
            "citations": [
                {"source": c.source, "url": c.url, "confidence": c.confidence}
                for c in self.citations
            ],
            "actions": self.actions,
            "metadata": {
                "model": self.metadata.model,
                "provider": self.metadata.provider,
                "tokens_used": self.metadata.tokens_used,
                "generation_time_seconds": self.metadata.generation_time_seconds,
                "finish_reason": self.metadata.finish_reason,
                "timestamp": self.metadata.timestamp,
            },
        }
    
    # ==================== HELPERS ====================
    
    @staticmethod
    def _markdown_to_html(text: str) -> str:
        """Simple markdown to HTML conversion."""
        # Bold
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        # Italic
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        # Code inline
        text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
        # Headers
        text = re.sub(r'^### (.+)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
        text = re.sub(r'^## (.+)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)
        text = re.sub(r'^# (.+)$', r'<h1>\1</h1>', text, flags=re.MULTILINE)
        # Line breaks
        text = text.replace("\n", "<br>")
        return text
    
    @staticmethod
    def _markdown_to_telegram_html(text: str) -> str:
        """Convert markdown to Telegram HTML."""
        # Bold
        text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
        # Italic
        text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
        # Code inline
        text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
        # Code blocks (simplified)
        text = re.sub(r'```(\w+)?\n(.+?)```', r'<pre><code>\2</code></pre>', text, flags=re.DOTALL)
        return text
    
    @staticmethod
    def _escape_html(text: str) -> str:
        """Escape HTML special characters."""
        return (text
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;"))


class ResponseFormatter:
    """
    Format raw LLM responses into StructuredResponse.
    """
    
    def __init__(self):
        self.thinking_pattern = re.compile(
            r'<think>(.+?)</think>|'
            r'(?:Thinking:|Reasoning:|Let me think[.:\s])(.+?)(?:\n\n|\Z)',
            re.DOTALL | re.IGNORECASE
        )
        self.code_pattern = re.compile(r'```(\w+)?\n(.+?)```', re.DOTALL)
        self.action_pattern = re.compile(
            r'(?:Action:|Next step:|You should:|Try:)(.+?)(?:\n|$)',
            re.IGNORECASE
        )
    
    def format(
        self,
        text: str,
        tool_calls: Optional[List[Any]] = None,
        model: str = "",
        provider: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> StructuredResponse:
        """
        Format raw LLM text into StructuredResponse.
        
        Args:
            text: Raw LLM response text
            tool_calls: Tool calls made during generation
            model: Model name
            provider: Provider name
            metadata: Extra metadata (tokens, timing, etc.)
            
        Returns:
            StructuredResponse
        """
        metadata = metadata or {}
        
        # Extract thinking
        thinking = self._extract_thinking(text)
        
        # Extract code blocks
        code_blocks = self._extract_code_blocks(text)
        
        # Extract actions
        actions = self._extract_actions(text)
        
        # Build response metadata
        resp_meta = ResponseMetadata(
            model=model,
            provider=provider,
            tokens_used=metadata.get("tokens_used", 0),
            tokens_input=metadata.get("tokens_input", 0),
            tokens_output=metadata.get("tokens_output", 0),
            generation_time_seconds=metadata.get("generation_time", 0.0),
            finish_reason=metadata.get("finish_reason", ""),
            confidence=metadata.get("confidence", 0.0),
            tool_calls_count=len(tool_calls) if tool_calls else 0,
            skills_used=metadata.get("skills_used", []),
        )
        
        return StructuredResponse(
            text=text,
            code_blocks=code_blocks,
            thinking=thinking,
            actions=actions,
            metadata=resp_meta,
            raw_response=text,
        )
    
    def _extract_thinking(self, text: str) -> Optional[ThinkingBlock]:
        """Extract thinking/reasoning blocks."""
        match = self.thinking_pattern.search(text)
        if match:
            content = match.group(1) or match.group(2) or ""
            return ThinkingBlock(
                content=content.strip(),
                is_visible=False,  # Hidden by default
            )
        return None
    
    def _extract_code_blocks(self, text: str) -> List[CodeBlock]:
        """Extract code blocks from markdown."""
        blocks = []
        for match in self.code_pattern.finditer(text):
            language = match.group(1) or "text"
            code = match.group(2).strip()
            blocks.append(CodeBlock(language=language, code=code))
        return blocks
    
    def _extract_actions(self, text: str) -> List[str]:
        """Extract suggested actions."""
        actions = []
        for match in self.action_pattern.finditer(text):
            action = match.group(1).strip()
            if action and len(action) > 5:
                actions.append(action)
        return actions[:5]  # Limit to 5 actions


__all__ = [
    "CodeBlock",
    "Citation",
    "ResponseFormatter",
    "ResponseMetadata",
    "ResponseSection",
    "StructuredResponse",
    "ThinkingBlock",
]
