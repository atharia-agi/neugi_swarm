#!/usr/bin/env python3
"""
NEUGI SWARM V2 - Upgraded Assistant
=====================================

Production-ready AI assistant with:
- Tool-use loop (ReAct pattern)
- Planning mode
- Sub-agent spawning
- Steering mode
- Memory/skill/context integration
- Session management
- Multi-provider LLM support
- Streaming responses
- Strict agentic execution contract

Version: 2.0.0
"""

from __future__ import annotations

import json
import time
import re
from typing import Any, Callable, Dict, Generator, List, Optional

from neugi_swarm_v2.config import NeugiConfig
from neugi_swarm_v2.memory.memory_core import MemorySystem
from neugi_swarm_v2.skills.skill_manager import SkillManager
from neugi_swarm_v2.agents.agent_manager import AgentManager
from neugi_swarm_v2.session.session_manager import SessionManager
from neugi_swarm_v2.context.prompt_assembler import PromptAssembler
from neugi_swarm_v2.context.token_budget import TokenBudget
from neugi_swarm_v2.llm_provider import (
    LLMProvider,
    LLMResponse,
    OllamaProvider,
    OpenAICompatibleProvider,
    AnthropicCompatibleProvider,
    ProviderConfig,
    ProviderType,
    ToolCall,
    ErrorType,
)


class NeugiAssistantV2:
    """Upgraded NEUGI Assistant with full agentic capabilities."""

    def __init__(self, config: Optional[NeugiConfig] = None, session_id: str = "default"):
        self.config = config or NeugiConfig()
        self.session_id = session_id

        # Initialize subsystems
        self.memory = MemorySystem(
            memory_dir=self.config.memory_dir,
            data_dir=self.config.data_dir,
        )
        self.skills = SkillManager(
            skills_dirs=self.config.skill_dirs,
            max_skills_in_prompt=self.config.max_skills_in_prompt,
        )
        self.agents = AgentManager(
            db_path=self.config.agent_db_path,
        )
        self.sessions = SessionManager(
            sessions_dir=self.config.sessions_dir,
            daily_reset_hour=self.config.session_daily_reset_hour,
            idle_timeout_minutes=self.config.session_idle_timeout,
        )
        self.prompt_assembler = PromptAssembler(
            max_tokens=self.config.context_max_tokens,
        )
        self.token_budget = TokenBudget(
            max_tokens=self.config.context_max_tokens,
        )

        # Initialize LLM provider with failover
        self.llm = self._create_llm_provider()
        self.fallback_llm = self._create_fallback_llm_provider()

        # Session management
        self.session = self.sessions.get_or_create_session(
            session_id=session_id,
            isolation_mode=self.config.session_isolation_mode,
        )

        # Tool registry
        self._tools: Dict[str, Callable] = {}
        self._register_default_tools()

        # Execution config
        self.max_tool_iterations = self.config.max_tool_iterations
        self.strict_execution = self.config.strict_agentic_execution

        # Steering
        self._steering_messages: List[str] = []
        self._steering_enabled = False

    def _create_llm_provider(self) -> LLMProvider:
        """Create the primary LLM provider."""
        llm_config = self.config.llm
        provider_type = llm_config.get("provider", "ollama")

        config = ProviderConfig(
            provider_type=ProviderType(provider_type),
            base_url=llm_config.get("base_url", "http://localhost:11434"),
            api_key=llm_config.get("api_key", ""),
            default_model=llm_config.get("default_model", "qwen3.5:cloud"),
            fallback_model=llm_config.get("fallback_model", "nemotron-3-super:cloud"),
            timeout=llm_config.get("timeout", 60),
            max_retries=llm_config.get("max_retries", 3),
        )

        if provider_type == "ollama":
            return OllamaProvider(config)
        elif provider_type == "openai_compatible":
            return OpenAICompatibleProvider(config)
        elif provider_type == "anthropic_compatible":
            return AnthropicCompatibleProvider(config)
        else:
            return OllamaProvider(config)

    def _create_fallback_llm_provider(self) -> Optional[LLMProvider]:
        """Create fallback LLM provider."""
        llm_config = self.config.llm
        fallback_model = llm_config.get("fallback_model", "")
        if not fallback_model or fallback_model == llm_config.get("default_model"):
            return None

        config = ProviderConfig(
            provider_type=self.llm.config.provider_type,
            base_url=self.llm.config.base_url,
            api_key=self.llm.config.api_key,
            default_model=fallback_model,
            timeout=self.llm.config.timeout,
            max_retries=2,
        )

        if self.llm.config.provider_type == ProviderType.OLLAMA:
            return OllamaProvider(config)
        elif self.llm.config.provider_type == ProviderType.OPENAI_COMPATIBLE:
            return OpenAICompatibleProvider(config)
        elif self.llm.config.provider_type == ProviderType.ANTHROPIC_COMPATIBLE:
            return AnthropicCompatibleProvider(config)
        return None

    def _register_default_tools(self):
        """Register default tools."""
        self._tools["memory_recall"] = self._tool_memory_recall
        self._tools["memory_add"] = self._tool_memory_add
        self._tools["read_file"] = self._tool_read_file
        self._tools["write_file"] = self._tool_write_file
        self._tools["list_agents"] = self._tool_list_agents
        self._tools["delegate_task"] = self._tool_delegate_task
        self._tools["get_skills"] = self._tool_get_skills

    # ========== Tool Implementations ==========

    def _tool_memory_recall(self, query: str, scope: str = "/global/", limit: int = 5) -> str:
        results = self.memory.recall(query=query, scope=scope, top_k=limit)
        return json.dumps(results, indent=2)

    def _tool_memory_add(self, content: str, scope: str = "/global/", importance: int = 5) -> str:
        mem_id = self.memory.save(content=content, scope=scope, importance=importance)
        return f"Memory saved with ID: {mem_id}"

    def _tool_read_file(self, path: str) -> str:
        import os
        full_path = os.path.join(self.config.workspace_dir, path)
        if not os.path.exists(full_path):
            return f"Error: File not found: {path}"
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"Error reading file: {e}"

    def _tool_write_file(self, path: str, content: str) -> str:
        import os
        full_path = os.path.join(self.config.workspace_dir, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        try:
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"File written: {path}"
        except Exception as e:
            return f"Error writing file: {e}"

    def _tool_list_agents(self) -> str:
        agents = self.agents.list_agents()
        return json.dumps([{"id": a.id, "name": a.name, "role": a.role.value, "status": a.status.value} for a in agents], indent=2)

    def _tool_delegate_task(self, agent_id: str, task: str) -> str:
        result = self.agents.delegate_task(agent_id=agent_id, task=task)
        return json.dumps(result, indent=2)

    def _tool_get_skills(self, query: str = "") -> str:
        if query:
            matches = self.skills.match_skill(query, top_k=5)
            return json.dumps([{"name": m.name, "description": m.description} for m in matches], indent=2)
        skills = self.skills.list_skills()
        return json.dumps([{"name": s.name, "description": s.description} for s in skills], indent=2)

    def register_tool(self, name: str, func: Callable):
        """Register a custom tool."""
        self._tools[name] = func

    # ========== Steering ==========

    def enable_steering(self):
        """Enable steering mode for real-time course correction."""
        self._steering_enabled = True

    def disable_steering(self):
        """Disable steering mode."""
        self._steering_enabled = False

    def send_steering_message(self, message: str):
        """Send a steering message to the running agent."""
        if self._steering_enabled:
            self._steering_messages.append(message)

    def _check_steering(self) -> Optional[str]:
        """Check for pending steering messages."""
        if self._steering_messages:
            msg = self._steering_messages.pop(0)
            return f"\n[STEERING] {msg}"
        return None

    # ========== Main Chat Interface ==========

    def chat(self, message: str, stream: bool = False) -> str:
        """Send a message and get a response with full agentic loop."""
        # Save user message to session
        self.sessions.add_message(self.session_id, "user", message)

        # Save to memory
        self.memory.save(content=message, scope="/user/", importance=3)

        if stream:
            return self._chat_stream(message)

        # Build the agentic loop
        full_response = ""
        tool_iterations = 0
        messages = self._build_messages(message)

        while tool_iterations < self.max_tool_iterations:
            # Check for steering
            steering = self._check_steering()
            if steering:
                messages.append({"role": "user", "content": steering})

            # Check if session needs compaction
            if self.sessions.needs_compaction(self.session_id):
                self._pre_compaction_flush()
                self.sessions.compact_session(self.session_id)
                messages = self._build_messages(message)

            try:
                response = self.llm.chat(
                    messages=messages,
                    model=self.llm.config.default_model,
                    temperature=0.7,
                    max_tokens=4096,
                )
            except Exception as e:
                # Try fallback
                if self.fallback_llm:
                    try:
                        response = self.fallback_llm.chat(
                            messages=messages,
                            model=self.fallback_llm.config.default_model,
                            temperature=0.7,
                            max_tokens=4096,
                        )
                    except Exception:
                        response = LLMResponse(content=f"Error: {str(e)}")
                else:
                    response = LLMResponse(content=f"Error: {str(e)}")

            # Check strict execution: if no tool calls and just planning, force action
            if self.strict_execution and not response.tool_calls and tool_iterations == 0:
                if self._is_planning_only(response.content):
                    messages.append({"role": "assistant", "content": response.content})
                    messages.append({
                        "role": "user",
                        "content": "Stop planning. Take action now using available tools.",
                    })
                    tool_iterations += 1
                    continue

            # Add assistant response to messages
            messages.append({"role": "assistant", "content": response.content})
            full_response = response.content

            # Execute tool calls
            if response.tool_calls:
                for tool_call in response.tool_calls:
                    tool_result = self._execute_tool(tool_call)
                    messages.append({
                        "role": "tool",
                        "content": tool_result,
                        "tool_call_id": tool_call.id,
                    })
                tool_iterations += 1
            else:
                # No tool calls, we're done
                break

        # Save assistant response
        self.sessions.add_message(self.session_id, "assistant", full_response)

        # Auto-save to memory if important
        if len(full_response) > 100:
            self.memory.save(content=full_response[:500], scope=f"/session/{self.session_id}/", importance=2)

        return full_response

    def chat_stream(self, message: str) -> Generator[str, None, None]:
        """Stream chat responses."""
        self.sessions.add_message(self.session_id, "user", message)
        self.memory.save(content=message, scope="/user/", importance=3)

        messages = self._build_messages(message)
        full_response = ""

        try:
            for chunk in self.llm.stream_chat(
                messages=messages,
                model=self.llm.config.default_model,
                temperature=0.7,
                max_tokens=4096,
            ):
                full_response += chunk
                yield chunk
        except Exception as e:
            if self.fallback_llm:
                try:
                    for chunk in self.fallback_llm.stream_chat(
                        messages=messages,
                        model=self.fallback_llm.config.default_model,
                        temperature=0.7,
                        max_tokens=4096,
                    ):
                        full_response += chunk
                        yield chunk
                except Exception:
                    yield f"Error: {str(e)}"
            else:
                yield f"Error: {str(e)}"

        self.sessions.add_message(self.session_id, "assistant", full_response)

    def _chat_stream(self, message: str) -> str:
        """Collect streamed response into a string."""
        full_response = ""
        for chunk in self.chat_stream(message):
            full_response += chunk
        return full_response

    # ========== Message Building ==========

    def _build_messages(self, user_message: str) -> List[Dict[str, str]]:
        """Build message list with system prompt, memory, skills, and context."""
        # Assemble system prompt
        system_prompt = self.prompt_assembler.assemble(
            identity=self._get_identity(),
            memory=self.memory.read_core()[:2000],
            skills=self.skills.get_prompt_text(max_tokens=3000),
            conversation=self.sessions.get_recent_messages(self.session_id, limit=10),
            mode="full",
        )

        # Build messages
        messages = [{"role": "system", "content": system_prompt}]

        # Add recent conversation from session
        recent = self.sessions.get_recent_messages(self.session_id, limit=20)
        for msg in recent:
            messages.append({"role": msg["role"], "content": msg["content"]})

        # Add current user message
        messages.append({"role": "user", "content": user_message})

        return messages

    def _get_identity(self) -> Dict[str, str]:
        """Get agent identity info."""
        return {
            "name": "NEUGI",
            "role": "Autonomous AI Assistant",
            "version": "2.0.0",
            "description": "A powerful AI assistant with a swarm of specialized agents, skills, and memory.",
        }

    # ========== Tool Execution ==========

    def _execute_tool(self, tool_call: ToolCall) -> str:
        """Execute a tool call and return the result."""
        tool_name = tool_call.name
        tool_args = tool_call.parsed_arguments

        if tool_name not in self._tools:
            return f"Error: Unknown tool '{tool_name}'. Available tools: {', '.join(self._tools.keys())}"

        try:
            result = self._tools[tool_name](**tool_args)
            return str(result)
        except Exception as e:
            return f"Error executing tool '{tool_name}': {str(e)}"

    # ========== Pre-compaction Memory Flush ==========

    def _pre_compaction_flush(self):
        """Save important context to memory before compaction."""
        recent = self.sessions.get_recent_messages(self.session_id, limit=50)
        important_content = []
        for msg in recent:
            if msg["role"] == "assistant" and len(msg["content"]) > 200:
                important_content.append(msg["content"][:300])

        if important_content:
            self.memory.save(
                content="\n---\n".join(important_content[:5]),
                scope=f"/session/{self.session_id}/summary/",
                importance=6,
            )

    # ========== Strict Execution Contract ==========

    def _is_planning_only(self, content: str) -> bool:
        """Detect if response is planning-only without taking action."""
        content_lower = content.lower()

        # Indicators of planning-only
        planning_indicators = [
            "here's how i would",
            "i would approach this by",
            "the steps would be",
            "here's a plan",
            "let me outline",
            "i can help you by",
            "i'll need to",
            "first, i would",
        ]

        # Check for planning language
        planning_count = sum(1 for indicator in planning_indicators if indicator in content_lower)

        # Check for actual tool usage mentions
        tool_mentions = sum(1 for tool_name in self._tools if tool_name in content_lower)

        # If heavy planning language but no tool mentions, likely planning-only
        return planning_count >= 2 and tool_mentions == 0

    # ========== Utility Methods ==========

    def get_session_info(self) -> Dict[str, Any]:
        """Get current session information."""
        return self.sessions.get_session_info(self.session_id)

    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory system statistics."""
        return self.memory.get_stats()

    def get_skill_count(self) -> int:
        """Get number of loaded skills."""
        return len(self.skills.list_skills())

    def get_agent_count(self) -> int:
        """Get number of registered agents."""
        return len(self.agents.list_agents())

    def reset_session(self):
        """Reset the current session."""
        self.sessions.reset_session(self.session_id)
        self._steering_messages.clear()

    def clear_memory(self):
        """Clear conversation memory (not core memory)."""
        self.sessions.reset_session(self.session_id)
