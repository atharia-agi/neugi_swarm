"""
NEUGI v2 - Autonomous Subsystem Wiring
=======================================

Safe bridges between the synchronous autonomous executor and
async/potentially-unavailable subsystems.

Handles:
- Async-to-sync bridging for GoalSystem (async methods)
- Graceful fallback when subsystems are missing or fail
- Subsystem capability detection
- Error isolation (one subsystem failure doesn't break others)
"""

from __future__ import annotations

import asyncio
import logging
import traceback
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class SubsystemWiring:
    """Wires autonomous executor to real subsystems with safe fallbacks.

    Args:
        memory_system: MemorySystem or DreamingEngine instance.
        goal_system: GoalSystem instance (may have async methods).
        agent_manager: AgentManager instance.
        skill_generator: SkillGenerator instance.
        llm_callback: LLM inference callback.
    """

    def __init__(
        self,
        memory_system: Any = None,
        goal_system: Any = None,
        agent_manager: Any = None,
        skill_generator: Any = None,
        llm_callback: Optional[Callable[..., str]] = None,
    ) -> None:
        self.memory_system = memory_system
        self.goal_system = goal_system
        self.agent_manager = agent_manager
        self.skill_generator = skill_generator
        self.llm_callback = llm_callback

    # -- Dreaming / Memory Consolidation --------------------------------------

    def run_dream_cycle(self) -> Dict[str, Any]:
        """Run memory consolidation via DreamingEngine.

        Returns:
            Dict with results or fallback info.
        """
        # Try DreamingEngine first
        dreaming = self._find_dreaming_engine()
        if dreaming:
            try:
                results = dreaming.run_cycle()
                return {
                    "success": True,
                    "phases": len(results),
                    "details": [
                        {
                            "phase": getattr(r, "phase", "unknown"),
                            "candidates": getattr(r, "candidates_staged", 0),
                            "promoted": getattr(r, "candidates_promoted", 0),
                        }
                        for r in results
                    ],
                }
            except Exception as e:
                logger.warning("Dream cycle failed: %s", e)
                return {"success": False, "error": str(e), "fallback": True}

        # Fallback: simple memory cleanup via MemorySystem
        if self.memory_system and hasattr(self.memory_system, "consolidate"):
            try:
                result = self.memory_system.consolidate()
                return {"success": True, "fallback": True, "result": result}
            except Exception as e:
                logger.warning("Memory consolidate fallback failed: %s", e)

        return {"success": False, "error": "No dreaming or memory subsystem available"}

    def _find_dreaming_engine(self) -> Optional[Any]:
        """Find DreamingEngine from memory_system or direct reference."""
        if self.memory_system:
            # Check if memory_system IS a DreamingEngine
            if hasattr(self.memory_system, "run_cycle"):
                return self.memory_system
            # Check if memory_system has a .dream attribute
            if hasattr(self.memory_system, "dream") and callable(self.memory_system.dream):
                return self.memory_system
        return None

    # -- Goal System ----------------------------------------------------------

    def decompose_goal(self, goal_id: str) -> Dict[str, Any]:
        """Decompose a goal into subtasks.

        Handles async GoalSystem.decompose() safely from sync context.
        """
        if not self.goal_system:
            return {"success": False, "error": "Goal system not available"}

        try:
            decompose_fn = getattr(self.goal_system, "decompose", None)
            if not decompose_fn:
                return {"success": False, "error": "GoalSystem has no decompose method"}

            # Handle async decompose
            import inspect
            if inspect.iscoroutinefunction(decompose_fn):
                result = self._run_async(decompose_fn(goal_id))
            else:
                result = decompose_fn(goal_id)

            return {
                "success": True,
                "children_created": len(getattr(result, "children", [])),
                "completeness": getattr(result, "completeness", 0.0),
            }

        except Exception as e:
            logger.warning("Goal decomposition failed: %s\n%s", e, traceback.format_exc())
            return {"success": False, "error": str(e)}

    def complete_goal(self, goal_id: str) -> Dict[str, Any]:
        """Mark a goal as complete.

        Handles async GoalSystem.update_progress() safely.
        """
        if not self.goal_system:
            return {"success": False, "error": "Goal system not available"}

        try:
            # Try update_progress first
            update_fn = getattr(self.goal_system, "update_progress", None)
            if update_fn:
                import inspect
                if inspect.iscoroutinefunction(update_fn):
                    self._run_async(update_fn(goal_id, 1.0))
                else:
                    update_fn(goal_id, 1.0)
                return {"success": True, "goal_id": goal_id, "status": "completed"}

            # Fallback: try direct status update
            status_fn = getattr(self.goal_system, "update_status", None)
            if status_fn:
                import inspect
                if inspect.iscoroutinefunction(status_fn):
                    self._run_async(status_fn(goal_id, "completed"))
                else:
                    status_fn(goal_id, "completed")
                return {"success": True, "goal_id": goal_id, "status": "completed"}

            return {"success": False, "error": "No completion method available"}

        except Exception as e:
            logger.warning("Goal completion failed: %s", e)
            return {"success": False, "error": str(e)}

    # -- Agent Manager --------------------------------------------------------

    def delegate_to_agent(
        self,
        task: str,
        role: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Delegate a task to an idle agent.

        Args:
            task: Task description.
            role: Agent role preference (e.g., "researcher", "coder").
            context: Additional context dict.

        Returns:
            Dict with delegation result.
        """
        if not self.agent_manager:
            return {"success": False, "error": "Agent manager not available"}

        try:
            delegate_fn = getattr(self.agent_manager, "delegate", None)
            if not delegate_fn:
                return {"success": False, "error": "AgentManager has no delegate method"}

            result = delegate_fn(task, role=role, context=context)
            return {
                "success": result.get("success", False),
                "agent_id": result.get("agent_id"),
                "agent_name": result.get("agent_name"),
                "output": result.get("output", result.get("result")),
                "error": result.get("error"),
            }

        except Exception as e:
            logger.warning("Agent delegation failed: %s", e)
            return {"success": False, "error": str(e)}

    def get_idle_agents(self) -> List[Dict[str, Any]]:
        """Get list of idle agents."""
        if not self.agent_manager:
            return []

        try:
            agents = getattr(self.agent_manager, "_agents", {})
            idle = []
            for agent_id, agent in agents.items():
                status = getattr(agent, "status", None)
                if status and getattr(status, "value", str(status)) == "idle":
                    idle.append({
                        "id": agent_id,
                        "name": getattr(agent, "name", "unknown"),
                        "role": getattr(getattr(agent, "role", None), "value", "unknown"),
                    })
            return idle
        except Exception as e:
            logger.warning("Get idle agents failed: %s", e)
            return []

    # -- Skill Generator ------------------------------------------------------

    def generate_skills(
        self,
        min_occurrences: int = 3,
        min_success_rate: float = 0.7,
        auto_approve_threshold: float = 0.9,
    ) -> Dict[str, Any]:
        """Generate skills from observed patterns.

        Returns:
            Dict with generated skills info.
        """
        if not self.skill_generator:
            return {"success": False, "error": "Skill generator not available"}

        try:
            gen_fn = getattr(self.skill_generator, "generate_skills_from_patterns", None)
            if not gen_fn:
                return {"success": False, "error": "SkillGenerator has no generate method"}

            new_skills = gen_fn(
                min_occurrences=min_occurrences,
                min_success_rate=min_success_rate,
                auto_approve_threshold=auto_approve_threshold,
            )

            return {
                "success": True,
                "skills_generated": len(new_skills),
                "skills": [
                    {
                        "name": getattr(s, "name", "unknown"),
                        "title": getattr(s, "title", ""),
                        "quality": getattr(getattr(s, "quality_score", None), "overall", 0.0),
                        "status": getattr(getattr(s, "approval_status", None), "value", "unknown"),
                    }
                    for s in new_skills
                ],
            }

        except Exception as e:
            logger.warning("Skill generation failed: %s", e)
            return {"success": False, "error": str(e)}

    # -- Utility --------------------------------------------------------------

    @staticmethod
    def _run_async(coro: Any) -> Any:
        """Run an async coroutine from sync context safely.

        Uses existing event loop if one is running, else creates new.
        """
        try:
            loop = asyncio.get_running_loop()
            # Already in an async context — schedule and wait
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result(timeout=60)
        except RuntimeError:
            # No running loop — safe to use asyncio.run
            return asyncio.run(coro)
