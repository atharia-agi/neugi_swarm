#!/usr/bin/env python3
"""
NEUGI SWARM V2 - LLM Provider Abstraction
==========================================

Unified interface for multiple LLM providers with failover, streaming,
and tool call extraction.

Providers:
- OllamaProvider (local models)
- OpenAICompatibleProvider (any OpenAI-compatible API)
- AnthropicCompatibleProvider (Claude API)

Version: 2.0.0
"""

from __future__ import annotations

import json
import time
import requests
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Generator, List, Optional


class ProviderType(Enum):
    OLLAMA = "ollama"
    OPENAI_COMPATIBLE = "openai_compatible"
    ANTHROPIC_COMPATIBLE = "anthropic_compatible"


class ErrorType(Enum):
    NONE = "none"
    CONTEXT_OVERFLOW = "context_overflow"
    RATE_LIMIT = "rate_limit"
    AUTH_ERROR = "auth_error"
    SERVER_ERROR = "server_error"
    CONNECTION_ERROR = "connection_error"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


@dataclass
class ToolCall:
    """A tool call extracted from model output."""
    id: str
    name: str
    arguments: str  # JSON string

    @property
    def parsed_arguments(self) -> Dict[str, Any]:
        try:
            return json.loads(self.arguments)
        except (json.JSONDecodeError, TypeError):
            return {}


@dataclass
class LLMResponse:
    """Response from an LLM provider."""
    content: str
    tool_calls: List[ToolCall] = field(default_factory=list)
    model: str = ""
    usage: Dict[str, int] = field(default_factory=dict)
    finish_reason: str = ""
    is_streaming: bool = False


@dataclass
class ProviderConfig:
    """Configuration for an LLM provider."""
    provider_type: ProviderType
    base_url: str = "http://localhost:11434"
    api_key: str = ""
    default_model: str = "qwen3.5:cloud"
    fallback_model: str = "nemotron-3-super:cloud"
    timeout: int = 60
    max_retries: int = 3
    retry_delay: float = 1.0
    extra_headers: Dict[str, str] = field(default_factory=dict)


class LLMProvider(ABC):
    """Base class for LLM providers."""

    def __init__(self, config: ProviderConfig):
        self.config = config
        self._last_error: Optional[Exception] = None
        self._total_tokens_used: int = 0
        self._request_count: int = 0

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> LLMResponse:
        """Generate a response from the model."""
        pass

    @abstractmethod
    def chat(
        self,
        messages: List[Dict[str, str]],
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: Optional[List[Dict]] = None,
        stream: bool = False,
    ) -> LLMResponse:
        """Chat with the model using message history."""
        pass

    @abstractmethod
    def stream_chat(
        self,
        messages: List[Dict[str, str]],
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: Optional[List[Dict]] = None,
    ) -> Generator[str, None, None]:
        """Stream chat responses."""
        pass

    @abstractmethod
    def classify_error(self, error: Exception) -> ErrorType:
        """Classify an error for failover decisions."""
        pass

    @property
    def total_tokens_used(self) -> int:
        return self._total_tokens_used

    @property
    def request_count(self) -> int:
        return self._request_count


class OllamaProvider(LLMProvider):
    """Provider for Ollama (local models)."""

    def __init__(self, config: ProviderConfig):
        if config.provider_type != ProviderType.OLLAMA:
            config = ProviderConfig(
                provider_type=ProviderType.OLLAMA,
                base_url=config.base_url,
                default_model=config.default_model,
                fallback_model=config.fallback_model,
                timeout=config.timeout,
                max_retries=config.max_retries,
            )
        super().__init__(config)

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> LLMResponse:
        model = model or self.config.default_model
        full_prompt = ""
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        else:
            full_prompt = prompt

        payload = {
            "model": model,
            "prompt": full_prompt,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        if stream:
            return self._stream_generate(payload)
        else:
            return self._blocking_generate(payload)

    def _blocking_generate(self, payload: Dict) -> LLMResponse:
        for attempt in range(self.config.max_retries):
            try:
                response = requests.post(
                    f"{self.config.base_url}/api/generate",
                    json=payload,
                    timeout=self.config.timeout,
                )
                response.raise_for_status()
                data = response.json()
                self._request_count += 1
                return LLMResponse(
                    content=data.get("response", "").strip(),
                    model=payload["model"],
                    usage={"prompt_tokens": 0, "completion_tokens": 0},
                    finish_reason="stop" if data.get("done") else "length",
                )
            except Exception as e:
                self._last_error = e
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay * (attempt + 1))
        raise self._last_error or RuntimeError("Ollama generate failed")

    def _stream_generate(self, payload: Dict) -> LLMResponse:
        # For non-streaming interface, fall back to blocking
        return self._blocking_generate({**payload, "stream": False})

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: Optional[List[Dict]] = None,
        stream: bool = False,
    ) -> LLMResponse:
        model = model or self.config.default_model
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if tools:
            payload["tools"] = tools

        for attempt in range(self.config.max_retries):
            try:
                response = requests.post(
                    f"{self.config.base_url}/api/chat",
                    json=payload,
                    timeout=self.config.timeout,
                )
                response.raise_for_status()
                data = response.json()
                self._request_count += 1

                message = data.get("message", {})
                content = message.get("content", "").strip()
                tool_calls = []

                # Extract tool calls if present
                for tc in message.get("tool_calls", []):
                    tool_calls.append(ToolCall(
                        id=tc.get("function", {}).get("name", f"tc_{len(tool_calls)}"),
                        name=tc.get("function", {}).get("name", ""),
                        arguments=json.dumps(tc.get("function", {}).get("arguments", {})),
                    ))

                # Also parse from content if no structured tool calls
                if not tool_calls:
                    tool_calls = ToolCallParser.parse_tool_calls(content)
                    if tool_calls:
                        content = ToolCallParser.strip_tool_calls(content)

                return LLMResponse(
                    content=content,
                    tool_calls=tool_calls,
                    model=model,
                    finish_reason="stop" if data.get("done") else "length",
                )
            except Exception as e:
                self._last_error = e
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay * (attempt + 1))
        raise self._last_error or RuntimeError("Ollama chat failed")

    def stream_chat(
        self,
        messages: List[Dict[str, str]],
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: Optional[List[Dict]] = None,
    ) -> Generator[str, None, None]:
        model = model or self.config.default_model
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if tools:
            payload["tools"] = tools

        try:
            response = requests.post(
                f"{self.config.base_url}/api/chat",
                json=payload,
                stream=True,
                timeout=self.config.timeout,
            )
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    try:
                        data = json.loads(line.decode("utf-8"))
                        if "message" in data:
                            chunk = data["message"].get("content", "")
                            if chunk:
                                yield chunk
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            self._last_error = e
            raise

    def classify_error(self, error: Exception) -> ErrorType:
        if isinstance(error, requests.exceptions.Timeout):
            return ErrorType.TIMEOUT
        if isinstance(error, requests.exceptions.ConnectionError):
            return ErrorType.CONNECTION_ERROR
        if isinstance(error, requests.exceptions.HTTPError):
            status = error.response.status_code if hasattr(error, 'response') else 0
            if status == 429:
                return ErrorType.RATE_LIMIT
            if status in (401, 403):
                return ErrorType.AUTH_ERROR
            if status == 400 and "context length" in str(error.response.text).lower():
                return ErrorType.CONTEXT_OVERFLOW
        return ErrorType.UNKNOWN


class OpenAICompatibleProvider(LLMProvider):
    """Provider for any OpenAI-compatible API."""

    def __init__(self, config: ProviderConfig):
        if config.provider_type != ProviderType.OPENAI_COMPATIBLE:
            config = ProviderConfig(
                provider_type=ProviderType.OPENAI_COMPATIBLE,
                base_url=config.base_url,
                api_key=config.api_key,
                default_model=config.default_model,
                fallback_model=config.fallback_model,
                timeout=config.timeout,
                max_retries=config.max_retries,
            )
        super().__init__(config)

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        headers.update(self.config.extra_headers)
        return headers

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> LLMResponse:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages, model, temperature, max_tokens, stream=stream)

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: Optional[List[Dict]] = None,
        stream: bool = False,
    ) -> LLMResponse:
        model = model or self.config.default_model
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        if tools:
            payload["tools"] = tools

        for attempt in range(self.config.max_retries):
            try:
                response = requests.post(
                    f"{self.config.base_url}/v1/chat/completions",
                    json=payload,
                    headers=self._headers(),
                    timeout=self.config.timeout,
                )
                response.raise_for_status()
                data = response.json()
                self._request_count += 1

                choice = data.get("choices", [{}])[0]
                message = choice.get("message", {})
                content = message.get("content", "").strip()

                tool_calls = []
                for tc in message.get("tool_calls", []):
                    tool_calls.append(ToolCall(
                        id=tc.get("id", f"tc_{len(tool_calls)}"),
                        name=tc.get("function", {}).get("name", ""),
                        arguments=tc.get("function", {}).get("arguments", "{}"),
                    ))

                if not tool_calls:
                    tool_calls = ToolCallParser.parse_tool_calls(content)
                    if tool_calls:
                        content = ToolCallParser.strip_tool_calls(content)

                usage = data.get("usage", {})
                return LLMResponse(
                    content=content,
                    tool_calls=tool_calls,
                    model=model,
                    usage=usage,
                    finish_reason=choice.get("finish_reason", ""),
                )
            except Exception as e:
                self._last_error = e
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay * (attempt + 1))
        raise self._last_error or RuntimeError("OpenAI-compatible chat failed")

    def stream_chat(
        self,
        messages: List[Dict[str, str]],
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: Optional[List[Dict]] = None,
    ) -> Generator[str, None, None]:
        model = model or self.config.default_model
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools

        response = requests.post(
            f"{self.config.base_url}/v1/chat/completions",
            json=payload,
            headers=self._headers(),
            stream=True,
            timeout=self.config.timeout,
        )
        response.raise_for_status()

        for line in response.iter_lines():
            if line:
                line_str = line.decode("utf-8")
                if line_str.startswith("data: "):
                    data_str = line_str[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue

    def classify_error(self, error: Exception) -> ErrorType:
        if isinstance(error, requests.exceptions.Timeout):
            return ErrorType.TIMEOUT
        if isinstance(error, requests.exceptions.ConnectionError):
            return ErrorType.CONNECTION_ERROR
        if isinstance(error, requests.exceptions.HTTPError):
            status = error.response.status_code if hasattr(error, 'response') else 0
            if status == 429:
                return ErrorType.RATE_LIMIT
            if status in (401, 403):
                return ErrorType.AUTH_ERROR
            if status == 400 and "context" in str(error.response.text).lower():
                return ErrorType.CONTEXT_OVERFLOW
        return ErrorType.UNKNOWN


class AnthropicCompatibleProvider(LLMProvider):
    """Provider for Anthropic Claude API."""

    def __init__(self, config: ProviderConfig):
        if config.provider_type != ProviderType.ANTHROPIC_COMPATIBLE:
            config = ProviderConfig(
                provider_type=ProviderType.ANTHROPIC_COMPATIBLE,
                base_url=config.base_url or "https://api.anthropic.com",
                api_key=config.api_key,
                default_model=config.default_model or "claude-sonnet-4-20250514",
                fallback_model=config.fallback_model or "claude-haiku-4-20250514",
                timeout=config.timeout,
                max_retries=config.max_retries,
            )
        super().__init__(config)

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        if self.config.api_key:
            headers["x-api-key"] = self.config.api_key
        headers.update(self.config.extra_headers)
        return headers

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> LLMResponse:
        messages = [{"role": "user", "content": prompt}]
        return self.chat(messages, model, temperature, max_tokens,
                        system_prompt=system_prompt, stream=stream)

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: Optional[List[Dict]] = None,
        stream: bool = False,
        system_prompt: str = "",
    ) -> LLMResponse:
        model = model or self.config.default_model
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system_prompt:
            payload["system"] = system_prompt
        if tools:
            payload["tools"] = tools

        for attempt in range(self.config.max_retries):
            try:
                response = requests.post(
                    f"{self.config.base_url}/v1/messages",
                    json=payload,
                    headers=self._headers(),
                    timeout=self.config.timeout,
                )
                response.raise_for_status()
                data = response.json()
                self._request_count += 1

                content = ""
                tool_calls = []

                for block in data.get("content", []):
                    if block.get("type") == "text":
                        content += block.get("text", "")
                    elif block.get("type") == "tool_use":
                        tool_calls.append(ToolCall(
                            id=block.get("id", f"tc_{len(tool_calls)}"),
                            name=block.get("name", ""),
                            arguments=json.dumps(block.get("input", {})),
                        ))

                if not tool_calls:
                    tool_calls = ToolCallParser.parse_tool_calls(content)
                    if tool_calls:
                        content = ToolCallParser.strip_tool_calls(content)

                usage = data.get("usage", {})
                return LLMResponse(
                    content=content.strip(),
                    tool_calls=tool_calls,
                    model=model,
                    usage=usage,
                    finish_reason=data.get("stop_reason", ""),
                )
            except Exception as e:
                self._last_error = e
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay * (attempt + 1))
        raise self._last_error or RuntimeError("Anthropic chat failed")

    def stream_chat(
        self,
        messages: List[Dict[str, str]],
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: Optional[List[Dict]] = None,
        system_prompt: str = "",
    ) -> Generator[str, None, None]:
        model = model or self.config.default_model
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if system_prompt:
            payload["system"] = system_prompt
        if tools:
            payload["tools"] = tools

        response = requests.post(
            f"{self.config.base_url}/v1/messages",
            json=payload,
            headers=self._headers(),
            stream=True,
            timeout=self.config.timeout,
        )
        response.raise_for_status()

        for line in response.iter_lines():
            if line:
                line_str = line.decode("utf-8")
                if line_str.startswith("data: "):
                    try:
                        data = json.loads(line_str[6:])
                        if data.get("type") == "content_block_delta":
                            delta = data.get("delta", {})
                            if delta.get("type") == "text_delta":
                                yield delta.get("text", "")
                    except json.JSONDecodeError:
                        continue

    def classify_error(self, error: Exception) -> ErrorType:
        if isinstance(error, requests.exceptions.Timeout):
            return ErrorType.TIMEOUT
        if isinstance(error, requests.exceptions.ConnectionError):
            return ErrorType.CONNECTION_ERROR
        if isinstance(error, requests.exceptions.HTTPError):
            status = error.response.status_code if hasattr(error, 'response') else 0
            if status == 429:
                return ErrorType.RATE_LIMIT
            if status in (401, 403):
                return ErrorType.AUTH_ERROR
            if status == 400 and "context" in str(error.response.text).lower():
                return ErrorType.CONTEXT_OVERFLOW
        return ErrorType.UNKNOWN


class ToolCallParser:
    """Parse tool calls from model text output."""

    @staticmethod
    def parse_tool_calls(text: str) -> List[ToolCall]:
        tool_calls = []

        # Pattern 1: JSON blocks with tool call structure
        patterns = [
            r'```(?:json)?\s*\{[^}]*"name"[^}]*"arguments"[^}]*\}\s*```',
            r'\{\s*"name"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{[^}]*\}\s*\}',
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, text, re.DOTALL):
                block = match.group()
                block = block.replace("```json", "").replace("```", "").strip()
                block = block.replace("`", "").strip()
                try:
                    data = json.loads(block)
                    tool_calls.append(ToolCall(
                        id=data.get("id", f"tc_{len(tool_calls)}"),
                        name=data.get("name", ""),
                        arguments=json.dumps(data.get("arguments", {})),
                    ))
                except json.JSONDecodeError:
                    pass

            if tool_calls:
                break

        # Pattern 2: Function call style
        if not tool_calls:
            import re
            func_pattern = r'(\w+)\((.*?)\)'
            for match in re.finditer(func_pattern, text):
                name = match.group(1)
                args_str = match.group(2)
                if name and (name[0].isupper() or len(name) > 2):
                    try:
                        args = {}
                        for part in args_str.split(","):
                            if "=" in part:
                                k, v = part.split("=", 1)
                                args[k.strip()] = v.strip().strip('"')
                        tool_calls.append(ToolCall(
                            id=f"tc_{len(tool_calls)}",
                            name=name,
                            arguments=json.dumps(args),
                        ))
                    except Exception:
                        pass

        return tool_calls

    @staticmethod
    def strip_tool_calls(text: str) -> str:
        import re
        patterns = [
            r'```(?:json)?\s*\{[^}]*"name"[^}]*"arguments"[^}]*\}\s*```\n?',
            r'\{\s*"name"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{[^}]*\}\s*\}\n?',
            r'\{\s*"tool_name"\s*:\s*"[^"]+"\s*,\s*"parameters"\s*:\s*\{[^}]*\}\s*\}\n?',
        ]

        for pattern in patterns:
            text = re.sub(pattern, "", text, flags=re.DOTALL)

        return text.strip()


import re
