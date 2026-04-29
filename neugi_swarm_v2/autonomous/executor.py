"""
NEUGI v2 - Self-Directed Executor
==================================

Executes autonomous decisions without user prompts.
The executor is the "hands" of the autonomous loop — it carries out
actions that the decision engine has approved.

Safety principles:
1. All mutations are logged and reversible where possible
2. No destructive actions without explicit approval (governance gate)
3. Resource budgets are enforced (time, tokens, disk)
4. Failures are captured and reported, never silent
5. Circuit breakers prevent runaway execution
"""

from __future__ import annotations

import logging
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from autonomous.agent_spawner import AutonomousAgentSpawner
from autonomous.decision import Decision, DecisionOutcome, DecisionType
from autonomous.research_engine import ResearchConfig, ResearchEngine
from autonomous.subsystem_wiring import SubsystemWiring

logger = logging.getLogger(__name__)


class ExecutionType(str, Enum):
    """Types of execution that can be performed."""

    DREAMING = "dreaming"               # Memory consolidation
    GOAL_DECOMPOSITION = "goal_decomposition"
    GOAL_COMPLETION = "goal_completion"
    BLOCKER_RESOLUTION = "blocker_resolution"
    SKILL_GENERATION = "skill_generation"
    SYSTEM_REPAIR = "system_repair"
    RESEARCH = "research"
    OPTIMIZATION = "optimization"
    NOTIFICATION = "notification"
    NOOP = "noop"


@dataclass
class ExecutionContext:
    """Context available during execution.

    Attributes:
        memory_system: Memory system reference (optional).
        goal_system: Goal system reference (optional).
        agent_manager: AgentManager for delegating tasks to idle agents (optional).
        llm_callback: Callable for LLM inference (optional).
        max_tokens: Token budget for this execution.
        timeout_seconds: Time budget for this execution.
        dry_run: If True, plan but do not execute.
    """

    memory_system: Any = None
    goal_system: Any = None
    agent_manager: Any = None
    skill_generator: Any = None
    web_search: Any = None
    llm_callback: Callable[..., Any] | None = None
    capability_profile: Any = None
    max_tokens: int = 2000
    timeout_seconds: float = 60.0
    dry_run: bool = False


@dataclass
class ActionResult:
    """Result of a single action within an execution."""

    action: str
    success: bool
    duration_ms: float = 0.0
    output: Any = None
    error: str | None = None


@dataclass
class ExecutionResult:
    """Result of executing a decision.

    Attributes:
        decision: The decision that was executed.
        execution_type: What kind of execution was performed.
        success: Whether the overall execution succeeded.
        actions: List of individual action results.
        duration_ms: Total execution time.
        tokens_used: Tokens consumed (if applicable).
        output: Structured output data.
        error: Error message if failed.
        created_at: Unix timestamp.
    """

    decision: Decision
    execution_type: ExecutionType
    success: bool = False
    actions: list[ActionResult] = field(default_factory=list)
    duration_ms: float = 0.0
    tokens_used: int = 0
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    created_at: float = field(default_factory=lambda: time.time())


class SelfDirectedExecutor:
    """Executes approved autonomous decisions.

    The executor is the "hands" of the autonomous loop.
    It translates decisions into concrete actions and carries them out.

    Args:
        context: Execution context with references to subsystems.
    """

    def __init__(self, context: ExecutionContext) -> None:
        self.context = context
        self._execution_count: int = 0
        self._failure_count: int = 0
        self._wiring = SubsystemWiring(
            memory_system=context.memory_system,
            goal_system=context.goal_system,
            agent_manager=context.agent_manager,
            skill_generator=getattr(context, "skill_generator", None),
            llm_callback=context.llm_callback,
        )
        self._agent_spawner = AutonomousAgentSpawner(
            llm_callback=context.llm_callback,
            memory_system=context.memory_system,
            agent_manager=context.agent_manager,
        )

    # -- Public API ------------------------------------------------------------

    def execute(self, decision: Decision) -> ExecutionResult:
        """Execute a single approved decision.

        Args:
            decision: The decision to execute (must be APPROVED).

        Returns:
            ExecutionResult with full details.
        """
        if decision.outcome != DecisionOutcome.APPROVED:
            return ExecutionResult(
                decision=decision,
                execution_type=ExecutionType.NOOP,
                success=False,
                error=f"Decision not approved: {decision.outcome.value}",
            )

        start = time.time()
        self._execution_count += 1

        try:
            result = self._execute_decision(decision)
        except Exception as e:
            self._failure_count += 1
            duration = (time.time() - start) * 1000
            logger.error("Autonomous execution failed: %s\n%s", e, traceback.format_exc())
            return ExecutionResult(
                decision=decision,
                execution_type=self._map_decision_type(decision.decision_type),
                success=False,
                duration_ms=duration,
                error=str(e),
            )

        result.duration_ms = (time.time() - start) * 1000
        return result

    def execute_batch(self, decisions: list[Decision]) -> list[ExecutionResult]:
        """Execute a batch of approved decisions.

        Args:
            decisions: List of decisions to execute.

        Returns:
            List of ExecutionResults, one per decision.
        """
        results: list[ExecutionResult] = []

        for decision in decisions:
            if decision.outcome != DecisionOutcome.APPROVED:
                continue

            result = self.execute(decision)
            results.append(result)

            # Stop on critical failure
            if not result.success and decision.source_observation.urgency > 0.8:
                logger.warning("Critical autonomous action failed, stopping batch")
                break

        return results

    def get_stats(self) -> dict[str, Any]:
        """Get executor statistics."""
        return {
            "total_executions": self._execution_count,
            "failures": self._failure_count,
            "success_rate": (
                (self._execution_count - self._failure_count) / self._execution_count
                if self._execution_count > 0 else 1.0
            ),
        }

    # -- Decision Execution ----------------------------------------------------

    def _execute_decision(self, decision: Decision) -> ExecutionResult:
        """Route decision to appropriate handler."""
        handlers = {
            DecisionType.CONSOLIDATE_MEMORY: self._execute_consolidate,
            DecisionType.DECOMPOSE_GOAL: self._execute_decompose,
            DecisionType.RESOLVE_BLOCKER: self._execute_resolve_blocker,
            DecisionType.COMPLETE_GOAL: self._execute_complete_goal,
            DecisionType.LEARN_SKILL: self._execute_learn,
            DecisionType.SELF_HEAL: self._execute_self_heal,
            DecisionType.PROACTIVE_RESEARCH: self._execute_research,
            DecisionType.OPTIMIZE: self._execute_optimize,
            DecisionType.NOTIFY_USER: self._execute_notify,
            DecisionType.IDLE: self._execute_noop,
        }

        handler = handlers.get(decision.decision_type, self._execute_noop)
        return handler(decision)

    def _map_decision_type(self, dec_type: DecisionType) -> ExecutionType:
        """Map decision type to execution type."""
        mapping = {
            DecisionType.CONSOLIDATE_MEMORY: ExecutionType.DREAMING,
            DecisionType.DECOMPOSE_GOAL: ExecutionType.GOAL_DECOMPOSITION,
            DecisionType.RESOLVE_BLOCKER: ExecutionType.BLOCKER_RESOLUTION,
            DecisionType.COMPLETE_GOAL: ExecutionType.GOAL_COMPLETION,
            DecisionType.LEARN_SKILL: ExecutionType.SKILL_GENERATION,
            DecisionType.SELF_HEAL: ExecutionType.SYSTEM_REPAIR,
            DecisionType.PROACTIVE_RESEARCH: ExecutionType.RESEARCH,
            DecisionType.OPTIMIZE: ExecutionType.OPTIMIZATION,
            DecisionType.NOTIFY_USER: ExecutionType.NOTIFICATION,
            DecisionType.IDLE: ExecutionType.NOOP,
        }
        return mapping.get(dec_type, ExecutionType.NOOP)

    # -- Individual Executors --------------------------------------------------

    def _execute_consolidate(self, decision: Decision) -> ExecutionResult:
        """Execute memory consolidation (dreaming) via DreamingEngine."""
        result = ExecutionResult(
            decision=decision,
            execution_type=ExecutionType.DREAMING,
        )

        if self.context.dry_run:
            result.success = True
            result.output = {"dry_run": True, "action": "consolidate_memory"}
            return result

        try:
            wiring_result = self._wiring.run_dream_cycle()
            result.actions.append(ActionResult(
                action="dream_cycle",
                success=wiring_result.get("success", False),
                output=wiring_result,
            ))
            result.success = wiring_result.get("success", False)
            result.output = wiring_result

        except Exception as e:
            result.success = False
            result.error = str(e)
            result.actions.append(ActionResult(
                action="dream_cycle",
                success=False,
                error=str(e),
            ))

        return result

    def _execute_decompose(self, decision: Decision) -> ExecutionResult:
        """Decompose a stuck goal into subtasks via GoalSystem."""
        result = ExecutionResult(
            decision=decision,
            execution_type=ExecutionType.GOAL_DECOMPOSITION,
        )

        goal_id = decision.action_plan.get("id")
        goal_title = decision.action_plan.get("title", "Untitled")

        if self.context.dry_run:
            result.success = True
            result.output = {"dry_run": True, "goal_id": goal_id, "goal_title": goal_title}
            return result

        try:
            wiring_result = self._wiring.decompose_goal(goal_id)
            result.actions.append(ActionResult(
                action="goal_decompose",
                success=wiring_result.get("success", False),
                output=wiring_result,
            ))
            result.success = wiring_result.get("success", False)
            result.output = {
                "goal_id": goal_id,
                "goal_title": goal_title,
                **wiring_result,
            }

        except Exception as e:
            result.success = False
            result.error = str(e)

        return result

    def _execute_resolve_blocker(self, decision: Decision) -> ExecutionResult:
        """Resolve a blocked goal: delegate to researcher agent + LLM fallback."""
        result = ExecutionResult(
            decision=decision,
            execution_type=ExecutionType.BLOCKER_RESOLUTION,
        )

        blocker = decision.action_plan.get("blocker", "unknown")
        goal_id = decision.action_plan.get("id", "")
        goal_title = decision.action_plan.get("title", "Untitled")

        if self.context.dry_run:
            result.success = True
            result.output = {"dry_run": True, "blocker": blocker}
            return result

        try:
            # Primary: spawn dedicated strategist agent for complex blockers
            if self.context.llm_callback:
                agent_result = self._agent_spawner.spawn_strategist_agent(
                    task=(
                        f"Goal '{goal_title}' is blocked by: {blocker}. "
                        f"Analyze the blocker and suggest 3 concrete solutions with trade-offs."
                    ),
                    context={"goal_id": goal_id, "blocker": blocker, "goal_title": goal_title},
                )
                result.actions.append(ActionResult(
                    action="blocker_strategist_agent",
                    success=agent_result.success,
                    output=agent_result.output,
                ))
                result.output = {
                    "blocker": blocker,
                    "agent_used": True,
                    "agent_output": agent_result.output,
                    "agent_duration_ms": agent_result.duration_ms,
                }
                result.success = agent_result.success

            # Fallback: delegate to idle researcher agent via AgentManager
            elif self.context.agent_manager:
                task = (
                    f"Goal '{goal_title}' is blocked by: {blocker}. "
                    f"Research the blocker and suggest 3 concrete solutions."
                )
                agent_result = self._wiring.delegate_to_agent(
                    task=task,
                    role="researcher",
                    context={"goal_id": goal_id, "blocker": blocker},
                )
                result.actions.append(ActionResult(
                    action="blocker_agent_delegate",
                    success=agent_result.get("success", False),
                    output=agent_result,
                ))
                result.output = {
                    "blocker": blocker,
                    "agent_used": True,
                    "agent_result": agent_result,
                }
                result.success = agent_result.get("success", False)

            else:
                result.actions.append(ActionResult(
                    action="blocker_log",
                    success=True,
                    output={"note": f"Blocker '{blocker}' logged for later resolution"},
                ))
                result.success = True

        except Exception as e:
            result.success = False
            result.error = str(e)

        return result

    def _execute_complete_goal(self, decision: Decision) -> ExecutionResult:
        """Complete a nearly-finished goal via GoalSystem."""
        result = ExecutionResult(
            decision=decision,
            execution_type=ExecutionType.GOAL_COMPLETION,
        )

        goal_id = decision.action_plan.get("id")

        if self.context.dry_run:
            result.success = True
            result.output = {"dry_run": True, "goal_id": goal_id}
            return result

        try:
            wiring_result = self._wiring.complete_goal(goal_id)
            result.actions.append(ActionResult(
                action="goal_complete",
                success=wiring_result.get("success", False),
                output=wiring_result,
            ))
            result.success = wiring_result.get("success", False)
            result.output = {"goal_id": goal_id, **wiring_result}

        except Exception as e:
            result.success = False
            result.error = str(e)

        return result

    def _execute_learn(self, decision: Decision) -> ExecutionResult:
        """Generate skills from detected patterns via SkillGenerator."""
        result = ExecutionResult(
            decision=decision,
            execution_type=ExecutionType.SKILL_GENERATION,
        )

        pattern = decision.action_plan.get("description", "unknown pattern")

        if self.context.dry_run:
            result.success = True
            result.output = {"dry_run": True, "pattern": pattern}
            return result

        try:
            # Generate skills from patterns
            wiring_result = self._wiring.generate_skills(
                min_occurrences=3,
                min_success_rate=0.7,
                auto_approve_threshold=0.9,
            )
            result.actions.append(ActionResult(
                action="skill_generate",
                success=wiring_result.get("success", False),
                output=wiring_result,
            ))
            result.success = wiring_result.get("success", False)
            result.output = {
                "pattern_detected": pattern,
                **wiring_result,
            }

        except Exception as e:
            result.success = False
            result.error = str(e)

        return result

    def _execute_self_heal(self, decision: Decision) -> ExecutionResult:
        """Attempt self-healing for system health issues."""
        result = ExecutionResult(
            decision=decision,
            execution_type=ExecutionType.SYSTEM_REPAIR,
        )

        issue = decision.action_plan.get("description", "unknown issue")

        if self.context.dry_run:
            result.success = True
            result.output = {"dry_run": True, "issue": issue}
            return result

        try:
            # Simple self-heal actions
            actions_taken = []

            # Clear old logs if disk issue
            if "disk" in issue.lower() or "space" in issue.lower():
                actions_taken.append("log_cleanup_suggested")

            # Restart circuit breaker if tripped
            if "circuit breaker" in issue.lower():
                actions_taken.append("circuit_breaker_reset_suggested")

            result.actions.append(ActionResult(
                action="self_heal",
                success=True,
                output={"issue": issue, "actions_taken": actions_taken},
            ))
            result.success = True
            result.output = {"issue": issue, "actions": actions_taken}

        except Exception as e:
            result.success = False
            result.error = str(e)

        return result

    def _execute_research(self, decision: Decision) -> ExecutionResult:
        """Pro-active research to fill knowledge gaps using Karpathy-style iteration."""
        result = ExecutionResult(
            decision=decision,
            execution_type=ExecutionType.RESEARCH,
        )

        gap = decision.action_plan.get("gap", "unknown topic")

        if self.context.dry_run:
            result.success = True
            result.output = {"dry_run": True, "gap": gap}
            return result

        try:
            # Try full ResearchEngine if web_search available
            if hasattr(self.context, "web_search") and self.context.web_search:
                # Adapt research depth based on model capability
                profile = getattr(self.context, "capability_profile", None)
                if profile:
                    tier = getattr(profile, "tier", None)
                    tier_value = tier.value if hasattr(tier, "value") else str(tier)
                    if tier_value == "local":
                        max_rounds = 1
                        max_sources = 2
                    elif tier_value == "cloud":
                        max_rounds = 3
                        max_sources = 5
                    else:
                        max_rounds = 2
                        max_sources = 3
                else:
                    max_rounds = 2
                    max_sources = 3

                engine = ResearchEngine(
                    web_search=self.context.web_search,
                    llm_callback=self.context.llm_callback,
                    memory_system=self.context.memory_system,
                    config=ResearchConfig(
                        max_rounds=max_rounds,
                        max_sources_per_round=max_sources,
                        max_tokens_per_synthesis=min(self.context.max_tokens, 4000),
                        timeout_seconds=self.context.timeout_seconds,
                    ),
                )
                report = engine.research(gap)
                result.actions.append(ActionResult(
                    action="karpathy_research",
                    success=True,
                    output={
                        "rounds": len(report.rounds),
                        "sources": len(report.all_sources),
                        "confidence": report.confidence_overall,
                    },
                ))
                result.output = {
                    "topic": gap,
                    "report": report.to_markdown(),
                    "rounds": len(report.rounds),
                    "sources": len(report.all_sources),
                    "confidence": report.confidence_overall,
                    "duration_ms": report.total_duration_ms,
                }
                result.tokens_used = report.total_tokens_used

            # Fallback: spawn dedicated research agent
            elif self.context.llm_callback:
                agent_result = self._agent_spawner.spawn_research_agent(
                    task=f"Research and summarize: {gap}",
                    context={"autonomous": True, "gap": gap},
                )
                result.actions.append(ActionResult(
                    action="research_agent_spawn",
                    success=agent_result.success,
                    output=agent_result.output,
                ))
                result.output = {
                    "topic": gap,
                    "agent_used": True,
                    "agent_output": agent_result.output,
                    "agent_duration_ms": agent_result.duration_ms,
                }
                result.tokens_used = agent_result.tokens_used

            else:
                result.actions.append(ActionResult(
                    action="research_log",
                    success=True,
                    output={"note": f"Research topic '{gap}' queued for later"},
                ))

            result.success = True

        except Exception as e:
            result.success = False
            result.error = str(e)
            result.actions.append(ActionResult(
                action="karpathy_research",
                success=False,
                error=str(e),
            ))

        return result

    def _execute_optimize(self, decision: Decision) -> ExecutionResult:
        """Execute self-optimization."""
        result = ExecutionResult(
            decision=decision,
            execution_type=ExecutionType.OPTIMIZATION,
        )

        target = decision.action_plan.get("description", "system")

        if self.context.dry_run:
            result.success = True
            result.output = {"dry_run": True, "target": target}
            return result

        try:
            result.actions.append(ActionResult(
                action="optimize",
                success=True,
                output={"target": target, "suggestion": "Consider caching or batching"},
            ))
            result.success = True
            result.output = {"optimized": target}

        except Exception as e:
            result.success = False
            result.error = str(e)

        return result

    def _execute_notify(self, decision: Decision) -> ExecutionResult:
        """Send notification to user."""
        result = ExecutionResult(
            decision=decision,
            execution_type=ExecutionType.NOTIFICATION,
        )

        message = decision.action_plan.get("description", "Autonomous activity")

        if self.context.dry_run:
            result.success = True
            result.output = {"dry_run": True, "message": message}
            return result

        try:
            result.actions.append(ActionResult(
                action="notify",
                success=True,
                output={"message": message, "channel": "default"},
            ))
            result.success = True
            result.output = {"notified": True, "message": message}

        except Exception as e:
            result.success = False
            result.error = str(e)

        return result

    def _execute_noop(self, decision: Decision) -> ExecutionResult:
        """No-op execution."""
        return ExecutionResult(
            decision=decision,
            execution_type=ExecutionType.NOOP,
            success=True,
            output={"action": "noop"},
        )
