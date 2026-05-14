"""
NEUGI v2 - Model Capability Profile & Router
=============================================

Adaptive intelligence layer that tailors NEUGI's behavior to the
actual capabilities of the connected LLM.

NEUGI works with ANY model — from 3B local to SOTA cloud — but the
way NEUGI talks to that model must adapt. This module provides:

1. CapabilityProfile — comprehensive model capability fingerprint
2. TaskComplexity — classifies user requests by cognitive load
3. ModelTier — categorizes models (local/medium/cloud)
4. CapabilityRouter — matches task to best model/config

Philosophy: Don't treat all models the same. Adapt.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

from model_registry import ModelCapabilities, ModelCapabilityDetector

logger = logging.getLogger(__name__)


# -- Enums -------------------------------------------------------------------

class ReasoningDepth(str, Enum):
    """How deep a model can reason."""
    SHALLOW = "shallow"      # 1-2 steps (3B models)
    MEDIUM = "medium"        # 3-5 steps (7B-13B)
    DEEP = "deep"            # 10+ steps (70B+)
    STRATEGIC = "strategic"  # 20+ steps with self-critique (SOTA)


class InstructionFollowing(str, Enum):
    """How well model follows complex instructions."""
    WEAK = "weak"        # Needs few-shot examples
    STRONG = "strong"    # Follows with clear prompt
    PERFECT = "perfect"  # Follows nuanced instructions


class OutputFormatReliability(str, Enum):
    """How reliably model outputs structured formats."""
    FRAGILE = "fragile"    # Needs strict schema + retries
    GOOD = "good"          # Works with examples
    PERFECT = "perfect"    # Native JSON mode


class PlanningHorizon(str, Enum):
    """How far ahead model can plan."""
    IMMEDIATE = "immediate"  # Single action only
    SHORT = "short"          # 2-3 step plans
    LONG = "long"            # Multi-step with dependencies


class SelfCorrection(str, Enum):
    """Ability to detect and fix own mistakes."""
    NONE = "none"
    SOMETIMES = "sometimes"
    BUILT_IN = "built_in"  # e.g., o1 reasoning traces


class ToolUseReliability(str, Enum):
    """How natively model uses tools."""
    COERCE = "coerce"      # Needs prompt engineering
    STRUCTURED = "structured"  # Good with ReAct pattern
    NATIVE = "native"      # Native function calling


class PromptTier(str, Enum):
    """How much prompt engineering the model needs."""
    MINIMAL = "minimal"    # Just instruction, no examples
    STANDARD = "standard"  # Standard system prompt + few-shot
    MAXIMAL = "maximal"    # Detailed schemas, examples, guardrails


class ModelTier(str, Enum):
    """Broad model category."""
    LOCAL = "local"        # < 7B, runs on consumer hardware
    MEDIUM = "medium"      # 7B-70B, good balance
    CLOUD = "cloud"        # 200B+, SOTA capabilities


class TaskComplexity(str, Enum):
    """Cognitive load of a task."""
    TRIVIAL = "trivial"       # Direct answer, no reasoning
    SIMPLE = "simple"         # 1-step reasoning
    MEDIUM = "medium"         # Multi-step, single domain
    COMPLEX = "complex"       # Cross-domain, planning needed
    STRATEGIC = "strategic"   # Long-term, self-critique needed


# -- Capability Profile ------------------------------------------------------

@dataclass
class CapabilityProfile:
    """Comprehensive capability fingerprint of an LLM.

    This is NOT a static whitelist. It's a dynamic profile built from:
    1. Model name heuristics (family detection)
    2. Ollama API probing (actual model file inspection)
    3. Runtime performance tracking (success rates per capability)

    The profile drives adaptive behavior across all NEUGI subsystems.
    """

    # Identity
    name: str = ""
    provider: str = ""
    tier: ModelTier = ModelTier.MEDIUM

    # Raw capabilities (from detection)
    context_length: int = 4096
    supports_tools: bool = False
    supports_vision: bool = False
    supports_json_mode: bool = False

    # Reasoning & cognition
    reasoning_depth: ReasoningDepth = ReasoningDepth.MEDIUM
    instruction_following: InstructionFollowing = InstructionFollowing.STRONG
    output_format_reliability: OutputFormatReliability = OutputFormatReliability.GOOD
    planning_horizon: PlanningHorizon = PlanningHorizon.SHORT
    self_correction: SelfCorrection = SelfCorrection.SOMETIMES

    # Tool use
    tool_use_reliability: ToolUseReliability = ToolUseReliability.STRUCTURED
    max_tools_per_call: int = 3
    preferred_tool_format: str = "react"  # "react", "function_call", "xml"

    # Prompt engineering
    recommended_prompt_tier: PromptTier = PromptTier.STANDARD
    needs_few_shot_examples: bool = True
    prefers_concise_system_prompt: bool = False

    # Context management
    effective_context_ratio: float = 0.75  # Usable context vs advertised
    memory_chunk_size: int = 1000  # Optimal memory chunk for recall
    max_memory_entries: int = 10  # How many memories to inject

    # Performance tracking (runtime-updated)
    avg_response_time_ms: float = 0.0
    tool_success_rate: float = 1.0
    format_success_rate: float = 1.0
    total_calls: int = 0
    failed_calls: int = 0

    @property
    def effective_context_length(self) -> int:
        """Context length usable in practice (after overhead)."""
        return int(self.context_length * self.effective_context_ratio)

    @property
    def supports_deep_planning(self) -> bool:
        """Whether model can handle complex multi-step planning."""
        return self.reasoning_depth in (ReasoningDepth.DEEP, ReasoningDepth.STRATEGIC)

    @property
    def supports_autonomous_execution(self) -> bool:
        """Whether model is reliable enough for self-directed actions."""
        return (
            self.tool_use_reliability in (ToolUseReliability.STRUCTURED, ToolUseReliability.NATIVE)
            and self.reasoning_depth in (ReasoningDepth.DEEP, ReasoningDepth.STRATEGIC)
            and self.self_correction in (SelfCorrection.SOMETIMES, SelfCorrection.BUILT_IN)
        )

    @property
    def is_local(self) -> bool:
        return self.tier == ModelTier.LOCAL

    @property
    def is_cloud(self) -> bool:
        return self.tier == ModelTier.CLOUD

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "name": self.name,
            "provider": self.provider,
            "tier": self.tier.value,
            "context_length": self.context_length,
            "effective_context_length": self.effective_context_length,
            "supports_tools": self.supports_tools,
            "supports_vision": self.supports_vision,
            "supports_json_mode": self.supports_json_mode,
            "reasoning_depth": self.reasoning_depth.value,
            "instruction_following": self.instruction_following.value,
            "output_format_reliability": self.output_format_reliability.value,
            "planning_horizon": self.planning_horizon.value,
            "self_correction": self.self_correction.value,
            "tool_use_reliability": self.tool_use_reliability.value,
            "max_tools_per_call": self.max_tools_per_call,
            "recommended_prompt_tier": self.recommended_prompt_tier.value,
            "effective_context_ratio": self.effective_context_ratio,
            "max_memory_entries": self.max_memory_entries,
            "supports_autonomous_execution": self.supports_autonomous_execution,
        }


# -- Profile Builder ---------------------------------------------------------

class CapabilityProfileBuilder:
    """Builds CapabilityProfile from ModelCapabilities + heuristics."""

    # Model family → tier mapping
    _TIER_MAP = {
        # Local (< 7B effective)
        "gemma": ModelTier.LOCAL,
        "gemma2": ModelTier.LOCAL,
        "phi3": ModelTier.LOCAL,
        "phi4": ModelTier.LOCAL,
        "qwen2.5": ModelTier.LOCAL,
        "llama3.2": ModelTier.LOCAL,
        "llama3.1": ModelTier.MEDIUM,
        # Medium (7B-70B)
        "qwen3": ModelTier.MEDIUM,
        "llama3": ModelTier.MEDIUM,
        "mistral": ModelTier.MEDIUM,
        "mixtral": ModelTier.MEDIUM,
        "deepseek": ModelTier.MEDIUM,
        "nemotron": ModelTier.MEDIUM,
        # Cloud (200B+ or API-only)
        "gpt-4": ModelTier.CLOUD,
        "gpt-4o": ModelTier.CLOUD,
        "o1": ModelTier.CLOUD,
        "o3": ModelTier.CLOUD,
        "claude-3": ModelTier.CLOUD,
        "claude-4": ModelTier.CLOUD,
        "gemini": ModelTier.CLOUD,
    }

    # Tier → default profile dimensions
    _TIER_DEFAULTS = {
        ModelTier.LOCAL: {
            "reasoning_depth": ReasoningDepth.SHALLOW,
            "instruction_following": InstructionFollowing.WEAK,
            "output_format_reliability": OutputFormatReliability.FRAGILE,
            "planning_horizon": PlanningHorizon.IMMEDIATE,
            "self_correction": SelfCorrection.NONE,
            "tool_use_reliability": ToolUseReliability.COERCE,
            "max_tools_per_call": 1,
            "recommended_prompt_tier": PromptTier.MAXIMAL,
            "needs_few_shot_examples": True,
            "prefers_concise_system_prompt": True,
            "effective_context_ratio": 0.6,
            "memory_chunk_size": 500,
            "max_memory_entries": 3,
        },
        ModelTier.MEDIUM: {
            "reasoning_depth": ReasoningDepth.MEDIUM,
            "instruction_following": InstructionFollowing.STRONG,
            "output_format_reliability": OutputFormatReliability.GOOD,
            "planning_horizon": PlanningHorizon.SHORT,
            "self_correction": SelfCorrection.SOMETIMES,
            "tool_use_reliability": ToolUseReliability.STRUCTURED,
            "max_tools_per_call": 3,
            "recommended_prompt_tier": PromptTier.STANDARD,
            "needs_few_shot_examples": False,
            "prefers_concise_system_prompt": False,
            "effective_context_ratio": 0.75,
            "memory_chunk_size": 1000,
            "max_memory_entries": 10,
        },
        ModelTier.CLOUD: {
            "reasoning_depth": ReasoningDepth.STRATEGIC,
            "instruction_following": InstructionFollowing.PERFECT,
            "output_format_reliability": OutputFormatReliability.PERFECT,
            "planning_horizon": PlanningHorizon.LONG,
            "self_correction": SelfCorrection.BUILT_IN,
            "tool_use_reliability": ToolUseReliability.NATIVE,
            "max_tools_per_call": 10,
            "recommended_prompt_tier": PromptTier.MINIMAL,
            "needs_few_shot_examples": False,
            "prefers_concise_system_prompt": False,
            "effective_context_ratio": 0.85,
            "memory_chunk_size": 2000,
            "max_memory_entries": 20,
        },
    }

    # Specific model overrides (fine-tuned profiles)
    _MODEL_OVERRIDES = {
        "o1": {"reasoning_depth": ReasoningDepth.STRATEGIC, "self_correction": SelfCorrection.BUILT_IN},
        "o3": {"reasoning_depth": ReasoningDepth.STRATEGIC, "self_correction": SelfCorrection.BUILT_IN},
        "deepseek-r1": {"reasoning_depth": ReasoningDepth.DEEP, "self_correction": SelfCorrection.BUILT_IN},
        "claude-3-5": {"reasoning_depth": ReasoningDepth.DEEP, "planning_horizon": PlanningHorizon.LONG},
        "claude-4": {"reasoning_depth": ReasoningDepth.STRATEGIC, "planning_horizon": PlanningHorizon.LONG},
        "gemini-2": {"context_length": 2000000, "effective_context_ratio": 0.9},
    }

    @classmethod
    def build(cls, caps: ModelCapabilities) -> CapabilityProfile:
        """Build full CapabilityProfile from base ModelCapabilities."""
        profile = CapabilityProfile(
            name=caps.name,
            provider=caps.provider,
            context_length=caps.context_length,
            supports_tools=caps.supports_tools,
            supports_vision=caps.supports_vision,
            supports_json_mode=caps.supports_json_mode,
        )

        # Detect tier
        profile.tier = cls._detect_tier(caps.name)

        # Apply tier defaults
        defaults = cls._TIER_DEFAULTS.get(profile.tier, cls._TIER_DEFAULTS[ModelTier.MEDIUM])
        for key, value in defaults.items():
            setattr(profile, key, value)

        # Apply model-specific overrides
        name_lower = caps.name.lower()
        for model_key, overrides in cls._MODEL_OVERRIDES.items():
            if model_key in name_lower:
                for key, value in overrides.items():
                    setattr(profile, key, value)

        # Context-based adjustments
        if caps.context_length >= 100000:
            profile.effective_context_ratio = max(profile.effective_context_ratio, 0.8)
            profile.memory_chunk_size = 2000
            profile.max_memory_entries = 15
        elif caps.context_length <= 4096:
            profile.effective_context_ratio = min(profile.effective_context_ratio, 0.6)
            profile.memory_chunk_size = 500
            profile.max_memory_entries = 3
            profile.prefers_concise_system_prompt = True

        # Tool support adjustments
        if not caps.supports_tools:
            profile.tool_use_reliability = ToolUseReliability.COERCE
            profile.max_tools_per_call = 0
            profile.supports_autonomous_execution  # computed property, no effect

        # JSON mode adjustments
        if caps.supports_json_mode:
            profile.output_format_reliability = max(
                profile.output_format_reliability,
                OutputFormatReliability.GOOD,
                key=lambda x: [OutputFormatReliability.FRAGILE, OutputFormatReliability.GOOD, OutputFormatReliability.PERFECT].index(x)
            )

        return profile

    @classmethod
    def _detect_tier(cls, model_name: str) -> ModelTier:
        """Detect model tier from name."""
        name_lower = model_name.lower()
        for family, tier in cls._TIER_MAP.items():
            if family in name_lower:
                return tier
        # Fallback: context-length based
        if "3b" in name_lower or "2b" in name_lower or "1b" in name_lower:
            return ModelTier.LOCAL
        if "70b" in name_lower or "72b" in name_lower or "8x" in name_lower:
            return ModelTier.MEDIUM
        if "405b" in name_lower:
            return ModelTier.MEDIUM
        return ModelTier.MEDIUM


# -- Task Complexity Classifier ----------------------------------------------

class TaskComplexityClassifier:
    """Classifies user requests by cognitive load for model routing."""

    # Keywords that indicate complexity
    _KEYWORDS = {
        TaskComplexity.TRIVIAL: [
            "what is", "who is", "when", "where", "how many", "define",
            "list", "name", "yes or no", "true or false",
        ],
        TaskComplexity.SIMPLE: [
            "explain", "summarize", "convert", "translate", "compare",
            "calculate", "find", "search",
        ],
        TaskComplexity.MEDIUM: [
            "analyze", "evaluate", "design", "create", "build",
            "implement", "write", "generate", "plan",
        ],
        TaskComplexity.COMPLEX: [
            "architect", "orchestrate", "integrate", "optimize",
            "refactor", "debug", "troubleshoot", "migrate",
        ],
        TaskComplexity.STRATEGIC: [
            "strategy", "roadmap", "vision", "long-term", "forecast",
            "innovate", "transform", "disrupt", "pivot",
        ],
    }

    # Signal multipliers
    _SIGNALS = {
        "multi_domain": 1.5,
        "self_reference": 1.3,
        "temporal_reasoning": 1.4,
        "counterfactual": 1.6,
        "creative": 1.2,
    }

    @classmethod
    def classify(cls, task: str, context: dict[str, Any] | None = None) -> TaskComplexity:
        """Classify task complexity from natural language."""
        task_lower = task.lower()
        scores: dict[TaskComplexity, float] = {c: 0.0 for c in TaskComplexity}

        # Keyword scoring
        for complexity, keywords in cls._KEYWORDS.items():
            for kw in keywords:
                if kw in task_lower:
                    scores[complexity] += 1.0

        # Length signal (longer = more complex, up to a point)
        word_count = len(task.split())
        if word_count > 50:
            scores[TaskComplexity.COMPLEX] += 0.5
            scores[TaskComplexity.STRATEGIC] += 0.3
        elif word_count < 10:
            scores[TaskComplexity.TRIVIAL] += 0.5

        # Structural signals
        if any(x in task_lower for x in ["and then", "after that", "step", "first"]):
            scores[TaskComplexity.MEDIUM] += 0.5
            scores[TaskComplexity.COMPLEX] += 0.3

        if any(x in task_lower for x in ["while", "meanwhile", "concurrently", "parallel"]):
            scores[TaskComplexity.COMPLEX] += 0.7

        if any(x in task_lower for x in ["if", "unless", "depending on", "scenario"]):
            scores[TaskComplexity.COMPLEX] += 0.5
            scores[TaskComplexity.STRATEGIC] += 0.3

        # Tool invocation signals
        tool_count = task_lower.count("[") + task_lower.count("<")
        if tool_count > 2:
            scores[TaskComplexity.MEDIUM] += 0.3 * tool_count

        # Context signals
        if context:
            if context.get("requires_memory_recall", False):
                scores[TaskComplexity.MEDIUM] += 0.3
            if context.get("has_dependencies", False):
                scores[TaskComplexity.COMPLEX] += 0.5
            if context.get("is_autonomous", False):
                scores[TaskComplexity.COMPLEX] += 0.5

        # Pick highest score
        if not any(scores.values()):
            return TaskComplexity.SIMPLE

        best = max(scores, key=lambda c: scores[c])
        return best

    @classmethod
    def classify_for_autonomous(cls, observation_type: str, data: dict[str, Any]) -> TaskComplexity:
        """Classify autonomous observation into task complexity."""
        mapping = {
            "memory_trend": TaskComplexity.SIMPLE,
            "goal_stuck": TaskComplexity.MEDIUM,
            "goal_blocked": TaskComplexity.COMPLEX,
            "goal_nearly_complete": TaskComplexity.SIMPLE,
            "system_health": TaskComplexity.MEDIUM,
            "scheduled_overdue": TaskComplexity.SIMPLE,
            "learning_opportunity": TaskComplexity.MEDIUM,
            "self_improvement": TaskComplexity.COMPLEX,
            "external_signal": TaskComplexity.MEDIUM,
            "knowledge_gap": TaskComplexity.MEDIUM,
        }
        return mapping.get(observation_type, TaskComplexity.MEDIUM)


# -- Capability Router -------------------------------------------------------

@dataclass
class RouteDecision:
    """Decision from the capability router."""
    profile: CapabilityProfile
    task_complexity: TaskComplexity
    recommended: bool  # True if this model can handle the task
    fallback_needed: bool
    adaptations: list[str]  # What adaptations to apply
    reason: str


class CapabilityRouter:
    """Routes tasks to the best model configuration based on capability profile.

    The router answers: "Given this model's capabilities, how should NEUGI
    adapt to handle this specific task?"

    It does NOT swap models (that's provider-level). It adapts NEUGI's
    behavior to the model that IS connected.
    """

    def __init__(self, profile: CapabilityProfile) -> None:
        self.profile = profile
        self._call_history: list[dict[str, Any]] = []

    # -- Public API ------------------------------------------------------------

    def route_task(self, task: str, context: dict[str, Any] | None = None) -> RouteDecision:
        """Determine how to execute a task with the current model."""
        complexity = TaskComplexityClassifier.classify(task, context)
        return self._route_by_complexity(complexity)

    def route_autonomous(self, observation_type: str, data: dict[str, Any]) -> RouteDecision:
        """Route an autonomous observation."""
        complexity = TaskComplexityClassifier.classify_for_autonomous(observation_type, data)
        return self._route_by_complexity(complexity)

    def adapt_prompt(self, base_prompt: str, purpose: str = "chat") -> str:
        """Adapt a prompt to the model's capability profile."""
        adaptations = []

        if self.profile.prefers_concise_system_prompt:
            adaptations.append("concise")

        if self.profile.needs_few_shot_examples and purpose in ("tool_use", "format"):
            adaptations.append("few_shot")

        if self.profile.output_format_reliability == OutputFormatReliability.FRAGILE:
            adaptations.append("strict_schema")

        if self.profile.reasoning_depth == ReasoningDepth.SHALLOW:
            adaptations.append("step_by_step")

        # Apply adaptations
        prompt = base_prompt
        if "concise" in adaptations:
            prompt = self._make_concise(prompt)
        if "few_shot" in adaptations:
            prompt = self._add_few_shot(prompt, purpose)
        if "strict_schema" in adaptations:
            prompt = self._add_schema_guardrails(prompt)
        if "step_by_step" in adaptations:
            prompt = self._add_step_by_step(prompt)

        return prompt

    def adapt_tools(self, available_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Adapt tool list to model's capability."""
        if self.profile.max_tools_per_call == 0:
            return []

        if len(available_tools) > self.profile.max_tools_per_call:
            # Prioritize by relevance — for now, just take first N
            return available_tools[:self.profile.max_tools_per_call]

        return available_tools

    def adapt_context_budget(self, total_budget: int) -> dict[str, int]:
        """Distribute context budget based on model capability."""
        effective = self.profile.effective_context_length
        actual_budget = min(total_budget, effective)

        # Allocation strategy based on tier
        if self.profile.tier == ModelTier.LOCAL:
            return {
                "system_prompt": int(actual_budget * 0.2),
                "memory": int(actual_budget * 0.2),
                "skills": int(actual_budget * 0.1),
                "user_message": int(actual_budget * 0.3),
                "response_reserve": int(actual_budget * 0.2),
            }
        elif self.profile.tier == ModelTier.MEDIUM:
            return {
                "system_prompt": int(actual_budget * 0.15),
                "memory": int(actual_budget * 0.25),
                "skills": int(actual_budget * 0.15),
                "user_message": int(actual_budget * 0.25),
                "response_reserve": int(actual_budget * 0.2),
            }
        else:  # CLOUD
            return {
                "system_prompt": int(actual_budget * 0.1),
                "memory": int(actual_budget * 0.3),
                "skills": int(actual_budget * 0.2),
                "user_message": int(actual_budget * 0.2),
                "response_reserve": int(actual_budget * 0.2),
            }

    def record_result(self, task: str, success: bool, format_valid: bool = True) -> None:
        """Record execution result for adaptive tracking."""
        self._call_history.append({
            "task": task,
            "success": success,
            "format_valid": format_valid,
            "timestamp": time.time(),
        })

        # Update running stats
        total = len(self._call_history)
        successes = sum(1 for c in self._call_history if c["success"])
        format_valids = sum(1 for c in self._call_history if c["format_valid"])

        self.profile.total_calls = total
        self.profile.failed_calls = total - successes
        self.profile.tool_success_rate = successes / total if total > 0 else 1.0
        self.profile.format_success_rate = format_valids / total if total > 0 else 1.0

        # Adaptive adjustment: if failure rate > 30%, downgrade expectations
        if total >= 10 and self.profile.tool_success_rate < 0.7:
            self._downgrade_expectations()

    def get_profile_summary(self) -> str:
        """Get human-readable capability summary."""
        lines = [
            f"Model: {self.profile.name} ({self.profile.provider})",
            f"Tier: {self.profile.tier.value}",
            f"Context: {self.profile.effective_context_length:,} tokens (of {self.profile.context_length:,})",
            f"Reasoning: {self.profile.reasoning_depth.value}",
            f"Tool use: {self.profile.tool_use_reliability.value} (max {self.profile.max_tools_per_call} per call)",
            f"Output format: {self.profile.output_format_reliability.value}",
            f"Planning: {self.profile.planning_horizon.value}",
            f"Prompt tier: {self.profile.recommended_prompt_tier.value}",
            f"Autonomous capable: {'yes' if self.profile.supports_autonomous_execution else 'no'}",
        ]
        if self.profile.total_calls > 0:
            lines.append(
                f"Runtime stats: {self.profile.tool_success_rate:.0%} success, "
                f"{self.profile.format_success_rate:.0%} format valid "
                f"({self.profile.total_calls} calls)"
            )
        return "\n".join(lines)

    # -- Internal --------------------------------------------------------------

    def _route_by_complexity(self, complexity: TaskComplexity) -> RouteDecision:
        """Route based on task complexity and model capability."""
        profile = self.profile
        adaptations: list[str] = []
        reason_parts: list[str] = []

        # Check if model can handle this complexity
        can_handle = True

        if complexity == TaskComplexity.STRATEGIC:
            if profile.reasoning_depth not in (ReasoningDepth.DEEP, ReasoningDepth.STRATEGIC):
                can_handle = False
                reason_parts.append("model lacks deep reasoning")
            if profile.planning_horizon != PlanningHorizon.LONG:
                adaptations.append("break_into_subtasks")
                reason_parts.append("planning horizon limited")

        elif complexity == TaskComplexity.COMPLEX:
            if profile.reasoning_depth == ReasoningDepth.SHALLOW:
                can_handle = False
                reason_parts.append("model has shallow reasoning")
            if profile.planning_horizon == PlanningHorizon.IMMEDIATE:
                adaptations.append("break_into_subtasks")
                reason_parts.append("no planning capability")

        elif complexity == TaskComplexity.MEDIUM:
            if profile.reasoning_depth == ReasoningDepth.SHALLOW:
                adaptations.append("simplify_steps")
                reason_parts.append("may struggle with multi-step")

        # Tool use check
        if complexity in (TaskComplexity.COMPLEX, TaskComplexity.STRATEGIC):
            if profile.tool_use_reliability == ToolUseReliability.COERCE:
                adaptations.append("manual_tool_orchestration")
                reason_parts.append("tool use unreliable")

        # Format reliability check
        if profile.output_format_reliability == OutputFormatReliability.FRAGILE:
            adaptations.append("format_validation_retry")
            reason_parts.append("output format fragile")

        # Build decision
        fallback_needed = not can_handle
        if not reason_parts:
            reason = f"Model can handle {complexity.value} tasks natively"
        else:
            reason = "; ".join(reason_parts)

        return RouteDecision(
            profile=profile,
            task_complexity=complexity,
            recommended=can_handle,
            fallback_needed=fallback_needed,
            adaptations=adaptations,
            reason=reason,
        )

    def _downgrade_expectations(self) -> None:
        """Downgrade capability expectations after repeated failures."""
        logger.warning(
            "Model %s success rate %.0f%% — downgrading expectations",
            self.profile.name,
            self.profile.tool_success_rate * 100,
        )

        # Step down output format reliability
        if self.profile.output_format_reliability == OutputFormatReliability.PERFECT:
            self.profile.output_format_reliability = OutputFormatReliability.GOOD
        elif self.profile.output_format_reliability == OutputFormatReliability.GOOD:
            self.profile.output_format_reliability = OutputFormatReliability.FRAGILE

        # Step down tool reliability
        if self.profile.tool_use_reliability == ToolUseReliability.NATIVE:
            self.profile.tool_use_reliability = ToolUseReliability.STRUCTURED
        elif self.profile.tool_use_reliability == ToolUseReliability.STRUCTURED:
            self.profile.tool_use_reliability = ToolUseReliability.COERCE
            self.profile.max_tools_per_call = max(1, self.profile.max_tools_per_call - 1)

        # Reduce memory
        self.profile.max_memory_entries = max(1, self.profile.max_memory_entries - 1)
        self.profile.effective_context_ratio *= 0.9

    def _make_concise(self, prompt: str) -> str:
        """Strip non-essential content for low-capacity models."""
        lines = prompt.split("\n")
        filtered = []
        in_example = False
        for line in lines:
            if line.strip().startswith("Example:") or line.strip().startswith("```"):
                in_example = not in_example
                continue
            if in_example:
                continue
            if line.strip().startswith("# Note:") or line.strip().startswith("# Tip:"):
                continue
            filtered.append(line)
        return "\n".join(filtered)

    def _add_few_shot(self, prompt: str, purpose: str) -> str:
        """Add few-shot examples for models that need them."""
        examples = {
            "tool_use": "\nExample:\nUser: Search for Python tutorials\nAssistant: I'll search for that.\n<tool>web_search</tool><arg>Python tutorials</arg>\n",
            "format": "\nExample:\nUser: Summarize this article\nAssistant: {\"summary\": \"...\", \"key_points\": [...]}\n",
        }
        return prompt + examples.get(purpose, "")

    def _add_schema_guardrails(self, prompt: str) -> str:
        """Add strict output format instructions."""
        guardrail = (
            "\n\nIMPORTANT: Your response MUST be valid JSON. "
            "Do not include any text outside the JSON. "
            "Use double quotes for all strings."
        )
        return prompt + guardrail

    def _add_step_by_step(self, prompt: str) -> str:
        """Add step-by-step instruction for shallow reasoning models."""
        instruction = (
            "\n\nThink step by step. Break this into small, simple steps. "
            "Handle one step at a time."
        )
        return prompt + instruction


# -- Convenience API ---------------------------------------------------------

def detect_profile(model_name: str, provider: str = "ollama") -> CapabilityProfile:
    """Detect capability profile for a model (one-liner)."""
    detector = ModelCapabilityDetector()
    caps = detector.detect(model_name, provider)
    return CapabilityProfileBuilder.build(caps)


def create_router(model_name: str, provider: str = "ollama") -> CapabilityRouter:
    """Create a capability router for a model (one-liner)."""
    profile = detect_profile(model_name, provider)
    return CapabilityRouter(profile)


__all__ = [
    # Enums
    "ReasoningDepth",
    "InstructionFollowing",
    "OutputFormatReliability",
    "PlanningHorizon",
    "SelfCorrection",
    "ToolUseReliability",
    "PromptTier",
    "ModelTier",
    "TaskComplexity",
    # Classes
    "CapabilityProfile",
    "CapabilityProfileBuilder",
    "TaskComplexityClassifier",
    "RouteDecision",
    "CapabilityRouter",
    # Functions
    "detect_profile",
    "create_router",
]
