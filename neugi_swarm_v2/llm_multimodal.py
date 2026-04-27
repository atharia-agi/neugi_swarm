"""
Multi-modal LLM Support for NEUGI v2
======================================
Vision model integration for Computer Use, image understanding,
and screenshot-based automation.

Features:
    - Image input for Ollama (llava, bakllava, etc.)
    - Image input for OpenAI (GPT-4V)
    - Image input for Anthropic (Claude 3)
    - Base64 encoding helpers
    - Screenshot → LLM prompt conversion

Usage:
    from llm_multimodal import MultimodalProvider, ImageMessage
    
    provider = MultimodalProvider.from_provider(ollama_provider)
    response = provider.chat_with_image(
        messages=[{"role": "user", "content": "What's in this screenshot?"}],
        image_b64=screenshot_b64
    )
"""

from __future__ import annotations

import base64
import io
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from llm_provider import LLMProvider, LLMResponse, ProviderConfig, ProviderType

logger = logging.getLogger(__name__)


@dataclass
class ImageMessage:
    """A message containing both text and image."""
    text: str
    image_b64: str = ""
    image_path: str = ""
    image_url: str = ""
    
    def to_ollama_format(self) -> Dict[str, Any]:
        """Convert to Ollama API format."""
        message = {"role": "user", "content": self.text}
        if self.image_b64:
            message["images"] = [self.image_b64]
        elif self.image_path:
            with open(self.image_path, "rb") as f:
                message["images"] = [base64.b64encode(f.read()).decode()]
        return message
    
    def to_openai_format(self) -> Dict[str, Any]:
        """Convert to OpenAI API format."""
        content = [{"type": "text", "text": self.text}]
        
        if self.image_b64:
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{self.image_b64}"}
            })
        elif self.image_url:
            content.append({
                "type": "image_url",
                "image_url": {"url": self.image_url}
            })
        elif self.image_path:
            with open(self.image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}"}
                })
        
        return {"role": "user", "content": content}
    
    def to_anthropic_format(self) -> Dict[str, Any]:
        """Convert to Anthropic API format."""
        content = [{"type": "text", "text": self.text}]
        
        if self.image_b64:
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": self.image_b64,
                }
            })
        elif self.image_path:
            with open(self.image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": b64,
                    }
                })
        
        return {"role": "user", "content": content}


class MultimodalProvider:
    """Wrapper that adds image/vision capabilities to any LLMProvider."""
    
    def __init__(self, provider: LLMProvider):
        self.provider = provider
        self.provider_type = self._detect_provider_type(provider)
    
    def _detect_provider_type(self, provider: LLMProvider) -> ProviderType:
        """Detect the underlying provider type."""
        class_name = provider.__class__.__name__
        if "Ollama" in class_name:
            return ProviderType.OLLAMA
        elif "Anthropic" in class_name:
            return ProviderType.ANTHROPIC_COMPATIBLE
        else:
            return ProviderType.OPENAI_COMPATIBLE
    
    def chat_with_image(
        self,
        messages: List[Dict[str, Any]],
        image_b64: str,
        text: str = "Describe what you see in this image.",
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """
        Send a chat message with an image.
        
        Args:
            messages: Previous message history
            image_b64: Base64-encoded image (PNG/JPEG)
            text: Question about the image
            model: Model override
            temperature: Sampling temperature
            max_tokens: Max output tokens
            
        Returns:
            LLMResponse with description/analysis
        """
        # Build message with image based on provider type
        if self.provider_type == ProviderType.OLLAMA:
            image_message = ImageMessage(text=text, image_b64=image_b64)
            multimodal_msg = image_message.to_ollama_format()
        elif self.provider_type == ProviderType.ANTHROPIC_COMPATIBLE:
            image_message = ImageMessage(text=text, image_b64=image_b64)
            multimodal_msg = image_message.to_anthropic_format()
        else:
            # OpenAI compatible
            image_message = ImageMessage(text=text, image_b64=image_b64)
            multimodal_msg = image_message.to_openai_format()
        
        # Add to message history
        all_messages = list(messages) + [multimodal_msg]
        
        return self.provider.chat(
            messages=all_messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    
    def analyze_screenshot(
        self,
        screenshot_b64: str,
        task: str = "Describe the current state of the screen and list all interactive elements.",
        model: str = "",
    ) -> LLMResponse:
        """
        Analyze a screenshot for Computer Use.
        
        Args:
            screenshot_b64: Base64 screenshot
            task: What to analyze
            model: Vision model override
            
        Returns:
            LLMResponse with structured analysis
        """
        system_prompt = """You are a computer automation assistant. Analyze screenshots and determine the next action.

Respond with a JSON object in this format:
{
    "action": "click|fill|scroll|navigate|terminate",
    "selector": "css selector or element identifier",
    "text": "text to type (for fill actions)",
    "url": "url to navigate to (for navigate actions)",
    "reason": "explanation of why this action was chosen"
}

Rules:
- Only suggest safe, non-destructive actions
- Prefer specific selectors over generic ones
- If task is complete, use action: "terminate"
- If unsure, use action: "screenshot" to get more context
"""
        
        messages = [{"role": "system", "content": system_prompt}]
        
        return self.chat_with_image(
            messages=messages,
            image_b64=screenshot_b64,
            text=task,
            model=model,
            temperature=0.2,  # Lower temp for deterministic actions
            max_tokens=2048,
        )
    
    def compare_screenshots(
        self,
        before_b64: str,
        after_b64: str,
        model: str = "",
    ) -> LLMResponse:
        """Compare two screenshots and describe changes."""
        
        if self.provider_type == ProviderType.OLLAMA:
            # Ollama doesn't support multiple images well, send sequentially
            messages = [
                {"role": "user", "content": "I will show you two screenshots. Describe what changed."},
                ImageMessage(text="First screenshot:", image_b64=before_b64).to_ollama_format(),
                ImageMessage(text="Second screenshot:", image_b64=after_b64).to_ollama_format(),
                {"role": "user", "content": "What changed between these two screenshots?"},
            ]
        elif self.provider_type == ProviderType.ANTHROPIC_COMPATIBLE:
            # Anthropic supports multiple images in one message
            content = [
                {"type": "text", "text": "Compare these two screenshots and describe what changed:"},
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": before_b64,
                    }
                },
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": after_b64,
                    }
                },
            ]
            messages = [{"role": "user", "content": content}]
        else:
            # OpenAI
            content = [
                {"type": "text", "text": "Compare these two screenshots and describe what changed:"},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{before_b64}"}
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{after_b64}"}
                },
            ]
            messages = [{"role": "user", "content": content}]
        
        return self.provider.chat(
            messages=messages,
            model=model,
            temperature=0.3,
            max_tokens=2048,
        )
    
    @staticmethod
    def encode_image(path: str) -> str:
        """Encode an image file to base64."""
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    
    @staticmethod
    def encode_image_bytes(data: bytes) -> str:
        """Encode image bytes to base64."""
        return base64.b64encode(data).decode()
    
    @classmethod
    def from_provider(cls, provider: LLMProvider) -> "MultimodalProvider":
        """Create MultimodalProvider from existing LLMProvider."""
        return cls(provider)


class VisionComputerUse:
    """
    Computer Use with real vision model integration.
    Replaces rule-based action selection with LLM vision analysis.
    """
    
    def __init__(
        self,
        multimodal_provider: MultimodalProvider,
        max_steps: int = 20,
    ):
        self.vision = multimodal_provider
        self.max_steps = max_steps
        self.action_history: List[Dict[str, Any]] = []
    
    def determine_action(
        self,
        task: str,
        screenshot_b64: str,
        dom_state: List[Dict],
        previous_actions: List[Dict],
    ) -> Dict[str, Any]:
        """
        Use vision model to determine next action.
        
        Returns:
            Dict with action, selector, text, url, reason
        """
        # Build context from DOM state and history
        dom_summary = self._summarize_dom(dom_state)
        history_summary = self._summarize_history(previous_actions)
        
        prompt = f"""Task: {task}

Previous actions: {history_summary}

Interactive elements on page:
{dom_summary}

Based on the screenshot and page state, what is the next action to take?
Respond ONLY with valid JSON."""
        
        try:
            response = self.vision.analyze_screenshot(
                screenshot_b64=screenshot_b64,
                task=prompt,
            )
            
            # Parse JSON from response
            import json
            content = response.content.strip()
            
            # Extract JSON if wrapped in markdown
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            action = json.loads(content)
            
            # Validate required fields
            if "action" not in action:
                return {"action": "screenshot", "reason": "Invalid response from vision model"}
            
            return action
            
        except Exception as e:
            logger.error(f"Vision model failed: {e}")
            return {"action": "screenshot", "reason": f"Vision error: {e}"}
    
    def _summarize_dom(self, dom_state: List[Dict]) -> str:
        """Summarize DOM state for the vision model."""
        lines = []
        for el in dom_state[:20]:  # Limit to 20 elements
            tag = el.get("tag", "")
            text = el.get("text", "")[:50]
            selector = el.get("selector", "")
            clickable = "[clickable]" if el.get("clickable") else ""
            lines.append(f"- {tag} {clickable}: {text} ({selector})")
        return "\n".join(lines) if lines else "No interactive elements found."
    
    def _summarize_history(self, actions: List[Dict]) -> str:
        """Summarize action history."""
        if not actions:
            return "None"
        lines = []
        for a in actions[-5:]:  # Last 5 actions
            lines.append(f"- {a.get('action', '?')}: {a.get('reason', '')}")
        return "\n".join(lines)


__all__ = [
    "ImageMessage",
    "MultimodalProvider",
    "VisionComputerUse",
]
