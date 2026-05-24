"""
NEUGI v2 - Autonomous Agent Spawner
====================================

Enables the autonomous loop to dynamically spawn specialized agents
(TypedAgent instances) for complex tasks that benefit from dedicated
agentic execution.

Spawnable agent types:
- ResearchAgent: Deep-dive research on blockers/knowledge gaps
- CoderAgent: Generate skills, code fixes, or system improvements
- AnalystAgent: Analyze patterns, trends, or system health
- StrategistAgent: Plan goal decomposition or optimization strategies

Results from spawned agents are automatically saved to memory
and reported back to the autonomous loop.
"""

from __future__ import annotations

import logging
import time
import traceback
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SpawnedAgentResult:
    """Result from a spawned autonomous agent."""

    agent_type: str
    task: str
    success: bool = False
    output: str = ""
    error: str | None = None
    duration_ms: float = 0.0
    tokens_used: int = 0
    created_at: float = field(default_factory=lambda: time.time())

    def to_memory_entry(self) -> dict[str, Any]:
        """Convert to memory entry dict."""
        return {
            "content": f"[{self.agent_type}] {self.task}\n\n{self.output}",
            "role": "agent",
            "tags": ["autonomous_agent", f"type:{self.agent_type}"],
            "metadata": {
                "agent_type": self.agent_type,
                "task": self.task,
                "success": self.success,
                "duration_ms": self.duration_ms,
                "tokens_used": self.tokens_used,
            },
        }


class AutonomousAgentSpawner:
    """Spawns specialized agents for autonomous tasks.

    Args:
        llm_callback: LLM inference callback for agent execution.
        memory_system: Optional memory system for storing results.
        agent_manager: Optional AgentManager for registration.
    """

    def __init__(
        self,
        llm_callback: Any | None = None,
        memory_system: Any = None,
        agent_manager: Any = None,
    ) -> None:
        self.llm_callback = llm_callback
        self.memory_system = memory_system
        self.agent_manager = agent_manager
        self._spawn_count: int = 0
        self._success_count: int = 0

    # -- Public API ------------------------------------------------------------

    def spawn_research_agent(self, task: str, context: dict[str, Any] | None = None) -> SpawnedAgentResult:
        """Spawn a research agent to investigate a topic or blocker."""
        return self._spawn_and_run(
            agent_type="research",
            task=task,
            instructions=(
                "You are an autonomous research agent. Your task is to thoroughly "
                "investigate the given topic, gather key facts, and produce a "
                "concise but comprehensive summary with actionable recommendations. "
                "Be factual, cite sources where possible, and focus on practical outcomes."
            ),
            context=context,
        )

    def spawn_coder_agent(self, task: str, context: dict[str, Any] | None = None) -> SpawnedAgentResult:
        """Spawn a coder agent to generate code, fixes, or skills."""
        return self._spawn_and_run(
            agent_type="coder",
            task=task,
            instructions=(
                "You are an autonomous coding agent. Your task is to write clean, "
                "efficient, well-tested code or system improvements. Follow best practices, "
                "include comments, and ensure the code is production-ready. "
                "If generating a skill, follow the SKILL.md v3 format."
            ),
            context=context,
        )

    def spawn_analyst_agent(self, task: str, context: dict[str, Any] | None = None) -> SpawnedAgentResult:
        """Spawn an analyst agent to analyze patterns or system health."""
        return self._spawn_and_run(
            agent_type="analyst",
            task=task,
            instructions=(
                "You are an autonomous analyst agent. Your task is to analyze data, "
                "identify trends, detect anomalies, and provide actionable insights. "
                "Be precise, use metrics where available, and recommend concrete next steps."
            ),
            context=context,
        )

    def spawn_strategist_agent(self, task: str, context: dict[str, Any] | None = None) -> SpawnedAgentResult:
        """Spawn a strategist agent for planning and optimization."""
        return self._spawn_and_run(
            agent_type="strategist",
            task=task,
            instructions=(
                "You are an autonomous strategist agent. Your task is to develop "
                "long-term plans, optimize processes, and recommend strategic decisions. "
                "Consider trade-offs, risks, and dependencies in your recommendations."
            ),
            context=context,
        )

    def get_stats(self) -> dict[str, Any]:
        """Get spawner statistics."""
        return {
            "total_spawns": self._spawn_count,
            "successful": self._success_count,
            "success_rate": (
                self._success_count / self._spawn_count if self._spawn_count > 0 else 1.0
            ),
        }

    # -- Internal -------------------------------------------------------------

    def _spawn_and_run(
        self,
        agent_type: str,
        task: str,
        instructions: str,
        context: dict[str, Any] | None = None,
    ) -> SpawnedAgentResult:
        """Spawn an agent and execute the task."""
        self._spawn_count += 1
        start = time.time()
        result = SpawnedAgentResult(agent_type=agent_type, task=task)

        try:
            # Build full prompt
            full_prompt = f"{instructions}\n\n## Task\n{task}"
            if context:
                full_prompt += f"\n\n## Context\n{context}"

            # Execute via LLM callback
            if self.llm_callback:
                output = self.llm_callback(full_prompt, max_tokens=4000)
                result.output = output
                result.success = True
                result.tokens_used = int(len(output.split()) * 1.3)  # Rough estimate
                self._success_count += 1
            else:
                result.error = "No LLM callback available"

        except Exception as e:
            result.error = str(e)
            logger.error("Spawned agent %s failed: %s\n%s", agent_type, e, traceback.format_exc())

        result.duration_ms = (time.time() - start) * 1000

        # Store in memory
        self._store_result(result)

        return result

    def _store_result(self, result: SpawnedAgentResult) -> None:
        """Store agent result in memory system."""
        if not self.memory_system:
            return

        try:
            entry = result.to_memory_entry()
            if hasattr(self.memory_system, "save"):
                self.memory_system.save(
                    content=entry["content"],
                    role=entry["role"],
                    tags=entry["tags"],
                    metadata=entry["metadata"],
                )
            elif hasattr(self.memory_system, "add"):
                self.memory_system.add(
                    text=entry["content"],
                    metadata=entry["metadata"],
                )
        except Exception as e:
            logger.warning("Failed to store agent result in memory: %s", e)
