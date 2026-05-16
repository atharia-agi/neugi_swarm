#!/usr/bin/env python3
"""
NEUGI Swarm V2 Assistant
========================

Runtime-compatible assistant facade for the v2.1.3 subsystem APIs.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any

from neugi_swarm_v2.config import NeugiConfig
from neugi_swarm_v2.context.prompt_assembler import PromptAssembler, PromptMode
from neugi_swarm_v2.context.token_budget import TokenBudget
from neugi_swarm_v2.llm_provider import (
    AnthropicCompatibleProvider,
    LLMProvider,
    LLMResponse,
    OllamaProvider,
    OpenAICompatibleProvider,
    ProviderConfig,
    ProviderType,
    ToolCall,
)
from neugi_swarm_v2.memory.memory_core import MemorySystem
from neugi_swarm_v2.memory.scopes import ScopePath
from neugi_swarm_v2.response_format import ResponseFormatter, StructuredResponse
from neugi_swarm_v2.session.session_manager import Session, SessionManager
from neugi_swarm_v2.skills.skill_manager import SkillManager


class NeugiAssistantV2:
    """Primary chat runtime for NEUGI Swarm v2.1.3."""

    def __init__(
        self,
        config: NeugiConfig | None = None,
        session_id: str = "default",
        llm: LLMProvider | None = None,
        memory: MemorySystem | None = None,
        skills: SkillManager | None = None,
        sessions: SessionManager | None = None,
        prompt_assembler: PromptAssembler | None = None,
        token_budget: TokenBudget | None = None,
        on_user_interaction: Callable[[], None] | None = None,
        **aliases: Any,
    ) -> None:
        self.config = config or NeugiConfig()
        self.session_id = session_id
        self._on_user_interaction = on_user_interaction

        self.memory = memory or aliases.get("memory_system") or MemorySystem(
            base_dir=str(self.config.memory_dir),
            daily_ttl_days=self.config.memory.daily_ttl_days,
            enable_fts=self.config.memory.enable_fts,
            enable_vec=self.config.memory.enable_vec,
        )
        self.skills = skills or aliases.get("skill_manager") or SkillManager(
            token_budget=self.config.skill.max_tokens_in_prompt,
            max_skills_in_prompt=self.config.skill.max_skills_in_prompt,
        )
        self.sessions = sessions or aliases.get("session_manager") or SessionManager(
            config=self.config.to_session_config(),
            registry_db_path=str(self.config.sessions_dir / "session_registry.db"),
        )
        self.prompt_assembler = prompt_assembler or PromptAssembler(
            base_dir=str(self.config.neugi_dir),
            model_max_chars=self.config.context.max_chars,
        )
        self.token_budget = token_budget or TokenBudget(
            model=self.config.llm.model,
            total_tokens=self.config.context.max_tokens,
            safety_margin=self.config.context.safety_margin,
        )

        self.llm = llm or self._create_llm_provider()
        self.fallback_llm = self._create_fallback_llm_provider()
        self.max_tool_iterations = int(getattr(self.config, "max_tool_iterations", 5))
        self.strict_execution = bool(getattr(self.config, "strict_agentic_execution", False))

        self._tools: dict[str, Callable[..., str]] = {}
        self._register_default_tools()
        self._steering_messages: list[str] = []
        self._steering_enabled = False

    # -- Provider setup -----------------------------------------------------

    def _create_llm_provider(self) -> LLMProvider:
        cfg = self.config.llm
        provider_map = {
            "ollama": ProviderType.OLLAMA,
            "anthropic": ProviderType.ANTHROPIC_COMPATIBLE,
            "anthropic_compatible": ProviderType.ANTHROPIC_COMPATIBLE,
        }
        provider_type = provider_map.get(cfg.provider, ProviderType.OPENAI_COMPATIBLE)
        base_url = cfg.ollama_url if provider_type == ProviderType.OLLAMA else cfg.base_url
        base_url = self._normalize_base_url(base_url)
        provider_config = ProviderConfig(
            provider_type=provider_type,
            base_url=base_url,
            api_key=cfg.api_key,
            default_model=cfg.model,
            fallback_model=cfg.fallback_model,
            timeout=int(cfg.timeout_seconds),
            max_retries=cfg.max_retries,
            retry_delay=cfg.retry_delay_seconds,
        )
        if provider_type == ProviderType.OLLAMA:
            return OllamaProvider(provider_config)
        if provider_type == ProviderType.ANTHROPIC_COMPATIBLE:
            return AnthropicCompatibleProvider(provider_config)
        return OpenAICompatibleProvider(provider_config)

    @staticmethod
    def _normalize_base_url(base_url: str) -> str:
        cleaned = (base_url or "").rstrip("/")
        if cleaned.endswith("/v1"):
            cleaned = cleaned[:-3]
        return cleaned or "http://localhost:11434"

    def _create_fallback_llm_provider(self) -> LLMProvider | None:
        fallback = self.llm.config.fallback_model
        if not fallback or fallback == self.llm.config.default_model:
            return None
        fallback_config = ProviderConfig(
            provider_type=self.llm.config.provider_type,
            base_url=self.llm.config.base_url,
            api_key=self.llm.config.api_key,
            default_model=fallback,
            fallback_model="",
            timeout=self.llm.config.timeout,
            max_retries=1,
            retry_delay=self.llm.config.retry_delay,
        )
        if fallback_config.provider_type == ProviderType.OLLAMA:
            return OllamaProvider(fallback_config)
        if fallback_config.provider_type == ProviderType.ANTHROPIC_COMPATIBLE:
            return AnthropicCompatibleProvider(fallback_config)
        return OpenAICompatibleProvider(fallback_config)

    # -- Session helpers ----------------------------------------------------

    def _get_session(self, session_id: str | None = None) -> Session:
        sid = session_id or self.session_id
        session = self.sessions.get_session(sid)
        if session is None:
            session = self.sessions.create_session(session_id=sid)
        if not session.is_active:
            session.activate()
            session.save_metadata()
        self.session_id = session.session_id
        return session

    def _append_session_message(self, session: Session, role: str, content: str) -> None:
        transcript_path = Path(session.metadata.transcript_path or "")
        transcript_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": time.time(),
            "role": role,
            "content": content,
        }
        with open(transcript_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        session.increment_message_count(max(1, len(content) // 4))
        session.save_metadata()

    def _recent_messages(self, session: Session, limit: int = 20) -> list[dict[str, str]]:
        transcript_path = Path(session.metadata.transcript_path or "")
        if not transcript_path.exists():
            return []
        try:
            lines = transcript_path.read_text(encoding="utf-8").splitlines()[-limit:]
        except OSError:
            return []
        messages: list[dict[str, str]] = []
        for line in lines:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            role = item.get("role")
            content = item.get("content")
            if role in {"system", "user", "assistant", "tool"} and isinstance(content, str):
                messages.append({"role": role, "content": content})
        return messages

    # -- Tools --------------------------------------------------------------

    def _register_default_tools(self) -> None:
        self._tools.update(
            {
                "memory_recall": self._tool_memory_recall,
                "memory_add": self._tool_memory_add,
                "read_file": self._tool_read_file,
                "write_file": self._tool_write_file,
                "get_skills": self._tool_get_skills,
            }
        )

    def _tool_schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "memory_recall",
                    "description": "Recall relevant NEUGI memories.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "limit": {"type": "integer", "default": 5},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "memory_add",
                    "description": "Persist an important memory.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string"},
                            "importance": {"type": "number", "default": 0.5},
                        },
                        "required": ["content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_skills",
                    "description": "List or search loaded skills.",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string", "default": ""}},
                    },
                },
            },
        ]

    def _tool_memory_recall(self, query: str, limit: int = 5) -> str:
        results = self.memory.recall(query=query, limit=limit)
        payload = [
            {"id": entry.id, "content": entry.content, "score": round(score, 4), "tags": entry.tags}
            for entry, score, _components in results
        ]
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def _tool_memory_add(self, content: str, importance: float = 0.5) -> str:
        entry = self.memory.save(
            content=content,
            scope=ScopePath.user_scope("default"),
            importance=max(0.0, min(1.0, float(importance))),
            source="assistant",
        )
        return f"Memory saved with ID: {entry.id}"

    def _tool_read_file(self, path: str) -> str:
        base = Path.cwd().resolve()
        target = (base / path).resolve()
        if not str(target).startswith(str(base)):
            return "Error: path escapes workspace"
        if not target.exists() or not target.is_file():
            return f"Error: file not found: {path}"
        return target.read_text(encoding="utf-8")

    def _tool_write_file(self, path: str, content: str) -> str:
        base = Path.cwd().resolve()
        target = (base / path).resolve()
        if not str(target).startswith(str(base)):
            return "Error: path escapes workspace"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"File written: {path}"

    def _tool_get_skills(self, query: str = "") -> str:
        if query:
            matches = self.skills.match(query, top_n=5)
            payload = [
                {
                    "name": match.skill.name,
                    "description": match.skill.frontmatter.description,
                    "score": round(match.score, 4),
                }
                for match in matches
            ]
        else:
            payload = [
                {"name": skill.name, "description": skill.frontmatter.description}
                for skill in self.skills.get_enabled()
            ]
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def register_tool(self, name: str, func: Callable[..., str]) -> None:
        self._tools[name] = func

    # -- Public controls ----------------------------------------------------

    def enable_steering(self) -> None:
        self._steering_enabled = True

    def disable_steering(self) -> None:
        self._steering_enabled = False

    def send_steering_message(self, message: str) -> None:
        if self._steering_enabled:
            self._steering_messages.append(message)

    def _check_steering(self) -> str | None:
        if self._steering_messages:
            return f"[STEERING] {self._steering_messages.pop(0)}"
        return None

    # -- Chat ---------------------------------------------------------------

    def chat(
        self,
        message: str,
        session_id: str | None = None,
        streaming: bool = False,
        stream: bool | None = None,
        structured: bool = True,
        **_: Any,
    ) -> StructuredResponse | str:
        start_time = time.time()
        if self._on_user_interaction:
            self._on_user_interaction()

        session = self._get_session(session_id)
        self._append_session_message(session, "user", message)
        self.memory.save(
            content=message,
            scope=ScopePath.user_scope("default"),
            importance=0.4,
            source="user",
            extract_triples=False,
        )

        if streaming or stream:
            text = "".join(self.chat_stream(message, session_id=session.session_id))
            return self._format_response(text, [], start_time, structured)

        messages = self._build_messages(message, session)
        all_tool_calls: list[ToolCall] = []
        final_text = ""
        iterations = 0

        while iterations <= self.max_tool_iterations:
            steering = self._check_steering()
            if steering:
                messages.append({"role": "user", "content": steering})

            response = self._call_llm(messages)
            final_text = response.content
            messages.append({"role": "assistant", "content": response.content})

            if not response.tool_calls:
                if self.strict_execution and iterations == 0 and self._is_planning_only(response.content):
                    messages.append(
                        {
                            "role": "user",
                            "content": "Stop planning. Use an available tool or provide the concrete result.",
                        }
                    )
                    iterations += 1
                    continue
                break

            all_tool_calls.extend(response.tool_calls)
            for tool_call in response.tool_calls:
                tool_result = self._execute_tool(tool_call)
                messages.append({"role": "tool", "content": tool_result})
            iterations += 1

        self._append_session_message(session, "assistant", final_text)
        if final_text:
            self.memory.save(
                content=final_text[:1000],
                scope=ScopePath.from_string(f"/session/{session.session_id}/"),
                importance=0.3,
                source="assistant",
                extract_triples=False,
            )

        return self._format_response(final_text, all_tool_calls, start_time, structured)

    def chat_stream(
        self,
        message: str,
        session_id: str | None = None,
    ) -> Generator[str, None, None]:
        session = self._get_session(session_id)
        messages = self._build_messages(message, session)
        full_response = ""
        try:
            for chunk in self.llm.stream_chat(
                messages=messages,
                model=self.llm.config.default_model,
                temperature=self.config.llm.temperature,
                max_tokens=self.config.llm.max_tokens,
                tools=self._tool_schemas(),
            ):
                full_response += chunk
                yield chunk
        except Exception as exc:
            yield f"Error: {exc}"
        finally:
            if full_response:
                self._append_session_message(session, "assistant", full_response)

    def _build_messages(self, user_message: str, session: Session) -> list[dict[str, str]]:
        prompt = self.prompt_assembler.assemble(mode=PromptMode.FULL).system_prompt
        messages = [{"role": "system", "content": prompt}]
        messages.extend(self._recent_messages(session, limit=20))
        if not messages or messages[-1].get("content") != user_message:
            messages.append({"role": "user", "content": user_message})
        return messages

    def _call_llm(self, messages: list[dict[str, str]]) -> LLMResponse:
        try:
            return self.llm.chat(
                messages=messages,
                model=self.llm.config.default_model,
                temperature=self.config.llm.temperature,
                max_tokens=self.config.llm.max_tokens,
                tools=self._tool_schemas(),
            )
        except Exception as exc:
            if self.fallback_llm:
                try:
                    return self.fallback_llm.chat(
                        messages=messages,
                        model=self.fallback_llm.config.default_model,
                        temperature=self.config.llm.temperature,
                        max_tokens=self.config.llm.max_tokens,
                        tools=self._tool_schemas(),
                    )
                except Exception:
                    pass
            return LLMResponse(content=f"Error: {exc}")

    def _execute_tool(self, tool_call: ToolCall) -> str:
        tool = self._tools.get(tool_call.name)
        if tool is None:
            return f"Error: unknown tool '{tool_call.name}'"
        try:
            return str(tool(**tool_call.parsed_arguments))
        except Exception as exc:
            return f"Error executing tool '{tool_call.name}': {exc}"

    def _format_response(
        self,
        text: str,
        tool_calls: list[ToolCall],
        start_time: float,
        structured: bool,
    ) -> StructuredResponse | str:
        if not structured:
            return text
        formatter = ResponseFormatter()
        usage = getattr(self.llm, "total_tokens_used", 0)
        return formatter.format(
            text=text,
            tool_calls=tool_calls,
            model=self.llm.config.default_model,
            provider=self.llm.config.provider_type.value,
            metadata={
                "tokens_used": usage,
                "generation_time": time.time() - start_time,
                "tool_iterations": len(tool_calls),
            },
        )

    def _is_planning_only(self, content: str) -> bool:
        lowered = content.lower()
        indicators = (
            "here's a plan",
            "i would approach",
            "the steps would be",
            "first, i would",
            "let me outline",
        )
        return sum(indicator in lowered for indicator in indicators) >= 2

    # -- Diagnostics --------------------------------------------------------

    def get_session_info(self) -> dict[str, Any]:
        return self._get_session().to_dict()

    def get_memory_stats(self) -> dict[str, Any]:
        return self.memory.stats

    def get_skill_count(self) -> int:
        return len(self.skills.get_enabled())

    def reset_session(self) -> None:
        self.sessions.reset_session(self.session_id)
        self._steering_messages.clear()

    def clear_memory(self) -> None:
        self.reset_session()
