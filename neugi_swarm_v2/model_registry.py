"""
NEUGI Model Capability Detector
================================
Dynamic model capability detection. Not a whitelist — NEUGI works
with ANY model you have installed. This module detects what your
model can actually do (tools, vision, JSON mode) via probing.

Usage:
    from model_registry import ModelCapabilityDetector
    
    detector = ModelCapabilityDetector(ollama_url="http://localhost:11434")
    
    # Detect capabilities of installed model
    caps = detector.detect("qwen3.5:cloud")
    print(caps.supports_tools)  # True/False based on probing
    
    # List installed Ollama models
    models = detector.list_installed()
    
    # Check if a model likely supports a feature
    if detector.likely_supports_tools("qwen3.5:cloud"):
        ...
"""

from __future__ import annotations

import json
import logging
import urllib.request
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ModelCapabilities:
    """Detected capabilities of a model."""
    name: str = ""
    provider: str = ""
    supports_tools: bool = False
    supports_vision: bool = False
    supports_json_mode: bool = False
    context_length: int = 4096
    detected_via: str = ""  # "probe", "registry", "fallback"

    @property
    def is_chat_model(self) -> bool:
        return True  # All models we use are chat models


class ModelCapabilityDetector:
    """
    Detects what a model can do by probing or heuristic matching.
    
    NEVER blocks a model — if unknown, assumes basic chat capabilities
    and logs a warning so the user knows features might not work.
    """

    # Known model families and their typical capabilities
    # These are HINTS, not hard rules. Actual detection via probing preferred.
    # Updated April 2026 — includes latest releases
    _FAMILY_HINTS = {
        # Qwen family (Alibaba, very strong tool use)
        "qwen": {"tools": True, "vision": False, "json": True, "ctx": 32768},
        "qwen3": {"tools": True, "vision": True, "json": True, "ctx": 131072},
        "qwen2.5": {"tools": True, "vision": False, "json": True, "ctx": 32768},
        "qwen2.5-coder": {"tools": True, "vision": False, "json": True, "ctx": 32768},
        "qwq": {"tools": True, "vision": False, "json": True, "ctx": 32768},
        # Llama family (Meta)
        "llama": {"tools": True, "vision": False, "json": True, "ctx": 131072},
        "llama3": {"tools": True, "vision": False, "json": True, "ctx": 131072},
        "llama3.1": {"tools": True, "vision": False, "json": True, "ctx": 131072},
        "llama3.2": {"tools": True, "vision": False, "json": True, "ctx": 131072},
        "llama3.3": {"tools": True, "vision": False, "json": True, "ctx": 131072},
        "llama4": {"tools": True, "vision": True, "json": True, "ctx": 256000},
        # DeepSeek (reasoning specialist)
        "deepseek": {"tools": True, "vision": False, "json": True, "ctx": 131072},
        "deepseek-r1": {"tools": True, "vision": False, "json": True, "ctx": 131072},
        "deepseek-v3": {"tools": True, "vision": False, "json": True, "ctx": 131072},
        # Mistral / Mixtral
        "mistral": {"tools": True, "vision": False, "json": True, "ctx": 32768},
        "mixtral": {"tools": True, "vision": False, "json": True, "ctx": 32768},
        "mistral-large": {"tools": True, "vision": True, "json": True, "ctx": 131072},
        # Gemma (Google, lightweight)
        "gemma": {"tools": False, "vision": False, "json": False, "ctx": 8192},
        "gemma2": {"tools": True, "vision": False, "json": True, "ctx": 8192},
        "gemma3": {"tools": True, "vision": True, "json": True, "ctx": 128000},
        # Phi (Microsoft, very small but capable)
        "phi3": {"tools": True, "vision": False, "json": True, "ctx": 128000},
        "phi4": {"tools": True, "vision": False, "json": True, "ctx": 128000},
        "phi4-mini": {"tools": True, "vision": False, "json": True, "ctx": 128000},
        # NVIDIA
        "nemotron": {"tools": True, "vision": False, "json": True, "ctx": 4096},
        "nemotron-3": {"tools": True, "vision": False, "json": True, "ctx": 128000},
        "nemotron-4": {"tools": True, "vision": True, "json": True, "ctx": 128000},
        # Vision-specific
        "llava": {"tools": False, "vision": True, "json": False, "ctx": 4096},
        "bakllava": {"tools": False, "vision": True, "json": False, "ctx": 4096},
        "moondream": {"tools": False, "vision": True, "json": False, "ctx": 8192},
        # Embedding
        "nomic-embed": {"tools": False, "vision": False, "json": False, "ctx": 8192},
        "all-minilm": {"tools": False, "vision": False, "json": False, "ctx": 512},
        "bge": {"tools": False, "vision": False, "json": False, "ctx": 8192},
        # Cloud models — OpenAI (updated April 2026)
        "gpt-4": {"tools": True, "vision": True, "json": True, "ctx": 128000},
        "gpt-4o": {"tools": True, "vision": True, "json": True, "ctx": 128000},
        "gpt-4o-mini": {"tools": True, "vision": True, "json": True, "ctx": 128000},
        "gpt-4.5": {"tools": True, "vision": True, "json": True, "ctx": 256000},
        "gpt-5": {"tools": True, "vision": True, "json": True, "ctx": 256000},
        "o1": {"tools": True, "vision": False, "json": True, "ctx": 200000},
        "o3": {"tools": True, "vision": False, "json": True, "ctx": 200000},
        "o4": {"tools": True, "vision": True, "json": True, "ctx": 200000},
        "o4-mini": {"tools": True, "vision": True, "json": True, "ctx": 200000},
        # Cloud — Anthropic (Claude 4 era)
        "claude-3": {"tools": True, "vision": True, "json": True, "ctx": 200000},
        "claude-3-5": {"tools": True, "vision": True, "json": True, "ctx": 200000},
        "claude-4": {"tools": True, "vision": True, "json": True, "ctx": 200000},
        "claude-4-sonnet": {"tools": True, "vision": True, "json": True, "ctx": 200000},
        "claude-4-opus": {"tools": True, "vision": True, "json": True, "ctx": 200000},
        # Cloud — Google Gemini
        "gemini": {"tools": True, "vision": True, "json": True, "ctx": 1000000},
        "gemini-2": {"tools": True, "vision": True, "json": True, "ctx": 1000000},
        "gemini-2.5": {"tools": True, "vision": True, "json": True, "ctx": 1000000},
        "gemini-2.5-pro": {"tools": True, "vision": True, "json": True, "ctx": 1000000},
        # Cloud — xAI Grok
        "grok": {"tools": True, "vision": True, "json": True, "ctx": 131072},
        "grok-3": {"tools": True, "vision": True, "json": True, "ctx": 131072},
        # Cloud — Cohere
        "command-r": {"tools": True, "vision": False, "json": True, "ctx": 128000},
        "command-r-plus": {"tools": True, "vision": True, "json": True, "ctx": 128000},
        # Cloud — Mistral AI
        "mistral-large-latest": {"tools": True, "vision": True, "json": True, "ctx": 131072},
        "pixtral": {"tools": True, "vision": True, "json": True, "ctx": 131072},
    }

    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.ollama_url = ollama_url.rstrip("/")
        self._cache: dict[str, ModelCapabilities] = {}

    def detect(self, model_name: str, provider: str = "ollama") -> ModelCapabilities:
        """
        Detect capabilities for a model.
        
        Strategy:
            1. Check cache
            2. Try to probe Ollama for actual model info
            3. Fall back to heuristic matching on model name
            4. If totally unknown, assume basic chat only
        """
        cache_key = f"{provider}/{model_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        caps = ModelCapabilities(name=model_name, provider=provider)

        # Try Ollama API for actual model info
        if provider == "ollama":
            try:
                info = self._query_ollama_model(model_name)
                if info:
                    caps = self._parse_ollama_info(model_name, info)
                    self._cache[cache_key] = caps
                    return caps
            except Exception as e:
                logger.debug("Ollama model query failed: %s", e)

        # Fall back to heuristic matching
        caps = self._heuristic_detect(model_name, provider)
        self._cache[cache_key] = caps
        return caps

    def likely_supports_tools(self, model_name: str) -> bool:
        """Quick check if model likely supports tool use."""
        caps = self.detect(model_name)
        return caps.supports_tools

    def likely_supports_vision(self, model_name: str) -> bool:
        """Quick check if model likely supports vision."""
        caps = self.detect(model_name)
        return caps.supports_vision

    def list_installed(self) -> list[str]:
        """List models installed in local Ollama."""
        try:
            req = urllib.request.Request(
                f"{self.ollama_url}/api/tags",
                headers={"Accept": "application/json"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                models = data.get("models", [])
                return [m.get("name", "") for m in models if m.get("name")]
        except Exception as e:
            logger.warning("Could not list Ollama models: %s", e)
            return []

    def recommend_fallback(self, primary_model: str) -> str:
        """Recommend a fallback model if primary fails."""
        installed = self.list_installed()
        if not installed:
            return "llama3.2:3b"  # Safe default

        # Prefer smaller models from same family
        primary_caps = self.detect(primary_model)
        primary_family = self._extract_family(primary_model)

        candidates = []
        for name in installed:
            if name == primary_model:
                continue
            family = self._extract_family(name)
            caps = self.detect(name)
            score = 0
            if family == primary_family:
                score += 10
            if caps.supports_tools and primary_caps.supports_tools:
                score += 5
            # Prefer smaller context = likely smaller model = faster fallback
            if caps.context_length <= 8192:
                score += 3
            candidates.append((name, score))

        candidates.sort(key=lambda x: x[1], reverse=True)
        if candidates:
            return candidates[0][0]

        return installed[0] if installed else "llama3.2:3b"

    def _query_ollama_model(self, model_name: str) -> dict | None:
        """Query Ollama API for model info."""
        req = urllib.request.Request(
            f"{self.ollama_url}/api/show",
            data=json.dumps({"name": model_name}).encode(),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode())

    def _parse_ollama_info(self, model_name: str, info: dict) -> ModelCapabilities:
        """Parse Ollama model info into capabilities."""
        caps = ModelCapabilities(name=model_name, provider="ollama", detected_via="probe")

        # Check model file for capabilities
        modelfile = info.get("modelfile", "")
        template = info.get("template", "")

        # Tools: check if template has tool/function support
        caps.supports_tools = "tools" in template.lower() or "function" in template.lower()

        # Vision: check if model name or modelfile mentions vision
        caps.supports_vision = "vision" in modelfile.lower() or "clip" in modelfile.lower()

        # JSON mode: most modern models support this
        caps.supports_json_mode = True

        # Context length from parameters
        params = info.get("parameters", "")
        if "num_ctx" in params:
            try:
                import re
                match = re.search(r"num_ctx\s+(\d+)", params)
                if match:
                    caps.context_length = int(match.group(1))
            except Exception:
                pass

        # If probe didn't detect tools, still use heuristic
        if not caps.supports_tools:
            heuristic = self._heuristic_detect(model_name, "ollama")
            caps.supports_tools = heuristic.supports_tools
            caps.supports_vision = caps.supports_vision or heuristic.supports_vision
            if caps.context_length == 4096:
                caps.context_length = heuristic.context_length

        return caps

    def _heuristic_detect(self, model_name: str, provider: str) -> ModelCapabilities:
        """Detect capabilities based on model name heuristics."""
        caps = ModelCapabilities(name=model_name, provider=provider, detected_via="heuristic")
        name_lower = model_name.lower()

        # Match against known families
        for family, hints in self._FAMILY_HINTS.items():
            if family in name_lower:
                caps.supports_tools = hints["tools"]
                caps.supports_vision = hints["vision"]
                caps.supports_json_mode = hints["json"]
                caps.context_length = hints["ctx"]
                return caps

        # Generic fallback: assume tool support for anything with "latest" or numbers
        if any(c.isdigit() for c in model_name):
            # Likely a modern model
            caps.supports_tools = True
            caps.supports_json_mode = True

        logger.warning(
            "Unknown model '%s' — assuming basic chat only. "
            "Some features (tools, vision) may not work. "
            "Set capabilities manually in config if needed.",
            model_name,
        )
        return caps

    def _extract_family(self, model_name: str) -> str:
        """Extract model family from name."""
        name_lower = model_name.lower()
        for family in self._FAMILY_HINTS:
            if family in name_lower:
                return family
        return "unknown"


__all__ = ["ModelCapabilities", "ModelCapabilityDetector"]
