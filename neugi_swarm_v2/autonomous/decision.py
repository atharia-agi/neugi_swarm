"""
NEUGI v2 - Proactive Decision Engine
=====================================

Evaluates observations and decides what autonomous actions to take.
This is the "brain" of the autonomous loop — it weighs urgency, value,
risk, and confidence to produce a ranked list of decisions.

Decision philosophy: NEUGI should act when:
1. The value of acting exceeds the cost (including user interruption)
2. Confidence is high enough that action won't cause harm
3. Urgency warrants pro-active behavior (not waiting for user prompt)
4. The action aligns with NEUGI's identity (SOUL.md) and current goals
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from autonomous.observer import Observation, ObservationType

logger = logging.getLogger(__name__)


class DecisionType(str, Enum):
    """Types of autonomous decisions."""

    CONSOLIDATE_MEMORY = "consolidate_memory"       # Run dreaming/ consolidation
    DECOMPOSE_GOAL = "decompose_goal"               # Break down a stuck goal
    RESOLVE_BLOCKER = "resolve_blocker"             # Try to unblock a goal
    COMPLETE_GOAL = "complete_goal"                 # Finish nearly-complete goal
    LEARN_SKILL = "learn_skill"                     # Generate skill from pattern
    SELF_HEAL = "self_heal"                         # Fix system health issue
    PROACTIVE_RESEARCH = "proactive_research"       # Fill knowledge gap
    NOTIFY_USER = "notify_user"                     # Inform user of something important
    OPTIMIZE = "optimize"                           # Improve performance
    IDLE = "idle"                                   # Do nothing, just observe


class DecisionOutcome(str, Enum):
    """Possible outcomes of a decision."""

    APPROVED = "approved"       # Decision approved for execution
    REJECTED = "rejected"       # Decision rejected (too risky, low value, etc.)
    DEFERRED = "deferred"       # Decision deferred to later
    ESCALATED = "escalated"     # Decision requires user approval


@dataclass
class RiskAssessment:
    """Risk analysis for a proposed action."""

    score: float = 0.0                  # 0.0-1.0, higher = riskier
    categories: List[str] = field(default_factory=list)
    mitigation: str = ""
    threshold: float = 0.6

    @property
    def is_acceptable(self) -> bool:
        return self.score < self.threshold


@dataclass
class ValueAssessment:
    """Value analysis for a proposed action."""

    score: float = 0.0                  # 0.0-1.0, higher = more valuable
    categories: List[str] = field(default_factory=list)
    explanation: str = ""


@dataclass
class DecisionCriteria:
    """Criteria used to evaluate decisions.

    These thresholds can be tuned per-deployment.
    """

    min_confidence: float = 0.5         # Minimum observation confidence
    min_value: float = 0.3              # Minimum value to act
    max_risk: float = 0.6               # Maximum acceptable risk
    min_urgency_for_notify: float = 0.7 # Urgency threshold to notify user
    max_daily_autonomous_actions: int = 20  # Rate limit
    user_interruption_cost: float = 0.3 # Cost of interrupting user


@dataclass
class Decision:
    """A single autonomous decision.

    Attributes:
        decision_type: What kind of action to take.
        source_observation: The observation that triggered this.
        outcome: Whether approved, rejected, deferred, or escalated.
        priority: 0.0-1.0 composite score.
        risk: Risk assessment.
        value: Value assessment.
        action_plan: Structured action parameters.
        reason: Human-readable reasoning.
        created_at: Unix timestamp.
    """

    decision_type: DecisionType
    source_observation: Observation
    outcome: DecisionOutcome = DecisionOutcome.APPROVED
    priority: float = 0.0
    risk: RiskAssessment = field(default_factory=RiskAssessment)
    value: ValueAssessment = field(default_factory=ValueAssessment)
    action_plan: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    created_at: float = field(default_factory=lambda: time.time())

    @property
    def should_execute(self) -> bool:
        """Whether this decision should be executed."""
        return self.outcome == DecisionOutcome.APPROVED

    @property
    def requires_user_approval(self) -> bool:
        """Whether this decision needs user confirmation."""
        return self.outcome == DecisionOutcome.ESCALATED


class ProactiveDecisionEngine:
    """Evaluates observations and produces ranked autonomous decisions.

    The decision engine is the "brain" of the autonomous loop.
    It applies configurable criteria to decide whether NEUGI should
    act on each observation, and if so, how.

    Args:
        criteria: Decision thresholds and limits.
        today_action_count: Current count of actions taken today (for rate limiting).
    """

    # Mapping from observation type to default decision type
    _OBS_TO_DECISION: Dict[ObservationType, DecisionType] = {
        ObservationType.MEMORY_TREND: DecisionType.CONSOLIDATE_MEMORY,
        ObservationType.GOAL_STUCK: DecisionType.DECOMPOSE_GOAL,
        ObservationType.GOAL_BLOCKED: DecisionType.RESOLVE_BLOCKER,
        ObservationType.GOAL_NEARLY_COMPLETE: DecisionType.COMPLETE_GOAL,
        ObservationType.SYSTEM_HEALTH: DecisionType.SELF_HEAL,
        ObservationType.SCHEDULED_OVERDUE: DecisionType.SELF_HEAL,
        ObservationType.LEARNING_OPPORTUNITY: DecisionType.LEARN_SKILL,
        ObservationType.SELF_IMPROVEMENT: DecisionType.OPTIMIZE,
        ObservationType.EXTERNAL_SIGNAL: DecisionType.PROACTIVE_RESEARCH,
        ObservationType.KNOWLEDGE_GAP: DecisionType.PROACTIVE_RESEARCH,
    }

    def __init__(
        self,
        criteria: Optional[DecisionCriteria] = None,
        today_action_count: int = 0,
        capability_profile: Optional[Any] = None,
    ) -> None:
        self.capability_profile = capability_profile
        self.criteria = criteria or self._adapt_criteria(DecisionCriteria())
        self.today_action_count = today_action_count
        self._decision_history: List[Decision] = []

    def _adapt_criteria(self, base: DecisionCriteria) -> DecisionCriteria:
        """Adapt decision criteria based on model capability.

        LOCAL tier: more conservative (higher thresholds, fewer actions)
        CLOUD tier: more aggressive (lower thresholds, more actions)
        """
        if self.capability_profile is None:
            return base

        tier = getattr(self.capability_profile, "tier", None)
        tier_value = tier.value if hasattr(tier, "value") else str(tier) if tier else "medium"

        if tier_value == "local":
            # Conservative: weak models shouldn't autonomously do much
            return DecisionCriteria(
                min_confidence=0.7,
                min_value=0.5,
                max_risk=0.4,
                min_urgency_for_notify=0.8,
                max_daily_autonomous_actions=5,
                user_interruption_cost=0.5,
            )
        elif tier_value == "cloud":
            # Aggressive: capable models can handle more autonomy
            return DecisionCriteria(
                min_confidence=0.4,
                min_value=0.2,
                max_risk=0.7,
                min_urgency_for_notify=0.6,
                max_daily_autonomous_actions=50,
                user_interruption_cost=0.2,
            )
        return base

    # -- Public API ------------------------------------------------------------

    def decide(self, observations: List[Observation]) -> List[Decision]:
        """Evaluate observations and produce ranked decisions.

        Args:
            observations: Observations from IdleObserver.

        Returns:
            List of decisions sorted by priority descending.
            Only APPROVED decisions should be executed.
        """
        decisions: List[Decision] = []

        for obs in observations:
            decision = self._evaluate_observation(obs)
            if decision:
                decisions.append(decision)
                self._decision_history.append(decision)

        # Sort by priority
        decisions.sort(key=lambda d: d.priority, reverse=True)

        # Apply rate limiting: cap total daily autonomous actions
        approved = [d for d in decisions if d.outcome == DecisionOutcome.APPROVED]
        if len(approved) + self.today_action_count > self.criteria.max_daily_autonomous_actions:
            # Defer lowest-priority decisions
            excess = len(approved) + self.today_action_count - self.criteria.max_daily_autonomous_actions
            for d in reversed(approved[-excess:]):
                d.outcome = DecisionOutcome.DEFERRED
                d.reason += " [deferred: daily action limit reached]"

        return decisions

    def get_stats(self) -> Dict[str, Any]:
        """Get decision engine statistics."""
        total = len(self._decision_history)
        approved = sum(1 for d in self._decision_history if d.outcome == DecisionOutcome.APPROVED)
        rejected = sum(1 for d in self._decision_history if d.outcome == DecisionOutcome.REJECTED)
        deferred = sum(1 for d in self._decision_history if d.outcome == DecisionOutcome.DEFERRED)
        escalated = sum(1 for d in self._decision_history if d.outcome == DecisionOutcome.ESCALATED)

        return {
            "total_evaluated": total,
            "approved": approved,
            "rejected": rejected,
            "deferred": deferred,
            "escalated": escalated,
            "today_action_count": self.today_action_count,
            "daily_limit": self.criteria.max_daily_autonomous_actions,
        }

    # -- Evaluation Logic ------------------------------------------------------

    def _evaluate_observation(self, obs: Observation) -> Optional[Decision]:
        """Evaluate a single observation and produce a decision."""

        # Filter: confidence too low
        if obs.confidence < self.criteria.min_confidence:
            return self._make_decision(
                obs, DecisionOutcome.REJECTED,
                f"Confidence {obs.confidence:.2f} below threshold {self.criteria.min_confidence}"
            )

        # Determine decision type
        dec_type = self._OBS_TO_DECISION.get(obs.obs_type, DecisionType.IDLE)

        if dec_type == DecisionType.IDLE:
            return None  # No action needed

        # Assess risk
        risk = self._assess_risk(obs, dec_type)

        # Assess value
        value = self._assess_value(obs, dec_type)

        # Filter: value too low
        if value.score < self.criteria.min_value:
            return self._make_decision(
                obs, DecisionOutcome.REJECTED,
                f"Value {value.score:.2f} below threshold {self.criteria.min_value}"
            )

        # Filter: risk too high
        if not risk.is_acceptable:
            # Escalate instead of reject — let governance decide
            return self._make_decision(
                obs, DecisionOutcome.ESCALATED,
                f"Risk {risk.score:.2f} exceeds threshold {self.criteria.max_risk}",
                dec_type, risk, value
            )

        # Compute priority
        priority = self._compute_priority(obs, risk, value, dec_type)

        # Determine if we should notify user
        if obs.urgency > self.criteria.min_urgency_for_notify and dec_type != DecisionType.NOTIFY_USER:
            # High urgency — add notification action
            pass  # Will be handled by reporter

        return self._make_decision(
            obs, DecisionOutcome.APPROVED,
            f"Approved: {dec_type.value} for {obs.obs_type.value}",
            dec_type, risk, value, priority
        )

    def _assess_risk(self, obs: Observation, dec_type: DecisionType) -> RiskAssessment:
        """Assess risk of taking action on an observation."""
        risk = RiskAssessment()

        # Base risk by decision type
        base_risk = {
            DecisionType.CONSOLIDATE_MEMORY: 0.05,
            DecisionType.COMPLETE_GOAL: 0.1,
            DecisionType.DECOMPOSE_GOAL: 0.15,
            DecisionType.PROACTIVE_RESEARCH: 0.2,
            DecisionType.LEARN_SKILL: 0.25,
            DecisionType.RESOLVE_BLOCKER: 0.35,
            DecisionType.OPTIMIZE: 0.3,
            DecisionType.SELF_HEAL: 0.4,
            DecisionType.NOTIFY_USER: 0.1,
        }.get(dec_type, 0.3)

        risk.score = base_risk

        # Adjust by observation confidence (lower confidence = higher risk)
        risk.score += (1.0 - obs.confidence) * 0.2

        # Adjust by observation type
        if obs.obs_type == ObservationType.SYSTEM_HEALTH:
            risk.categories.append("system_mutation")
        if obs.obs_type == ObservationType.GOAL_BLOCKED:
            risk.categories.append("goal_mutation")

        # Cap at 1.0
        risk.threshold = self.criteria.max_risk
        risk.score = min(risk.score, 1.0)

        # Mitigation
        if risk.score > 0.5:
            risk.mitigation = "Action logged; rollback checkpoint created"
        else:
            risk.mitigation = "Low risk; standard execution"

        return risk

    def _assess_value(self, obs: Observation, dec_type: DecisionType) -> ValueAssessment:
        """Assess value of taking action on an observation."""
        value = ValueAssessment()

        # Base value by decision type
        base_value = {
            DecisionType.SELF_HEAL: 0.9,
            DecisionType.RESOLVE_BLOCKER: 0.85,
            DecisionType.COMPLETE_GOAL: 0.8,
            DecisionType.CONSOLIDATE_MEMORY: 0.6,
            DecisionType.DECOMPOSE_GOAL: 0.7,
            DecisionType.PROACTIVE_RESEARCH: 0.5,
            DecisionType.LEARN_SKILL: 0.55,
            DecisionType.OPTIMIZE: 0.5,
            DecisionType.NOTIFY_USER: 0.4,
        }.get(dec_type, 0.4)

        value.score = base_value

        # Adjust by observation value signal
        value.score = (value.score + obs.value) / 2

        # Boost for high-urgency items
        if obs.urgency > 0.8:
            value.score = min(value.score * 1.2, 1.0)
            value.categories.append("urgent")

        # Boost for recurring patterns
        if obs.obs_type == ObservationType.MEMORY_TREND:
            count = obs.data.get("count", 1)
            if count > 10:
                value.score = min(value.score * 1.15, 1.0)
                value.categories.append("high_recall")

        value.explanation = f"Base value {base_value:.2f} adjusted by observation value {obs.value:.2f}"

        return value

    def _compute_priority(
        self,
        obs: Observation,
        risk: RiskAssessment,
        value: ValueAssessment,
        dec_type: DecisionType,
    ) -> float:
        """Compute composite priority score."""
        # Priority = value * urgency * (1 - risk)
        priority = value.score * obs.urgency * (1.0 - risk.score * 0.5)

        # Boost for certain decision types
        if dec_type in (DecisionType.SELF_HEAL, DecisionType.RESOLVE_BLOCKER):
            priority = min(priority * 1.1, 1.0)

        return priority

    def _make_decision(
        self,
        obs: Observation,
        outcome: DecisionOutcome,
        reason: str,
        dec_type: Optional[DecisionType] = None,
        risk: Optional[RiskAssessment] = None,
        value: Optional[ValueAssessment] = None,
        priority: float = 0.0,
    ) -> Decision:
        """Create a Decision object."""
        return Decision(
            decision_type=dec_type or DecisionType.IDLE,
            source_observation=obs,
            outcome=outcome,
            priority=priority,
            risk=risk or RiskAssessment(),
            value=value or ValueAssessment(),
            action_plan={"observation_type": obs.obs_type.value, **obs.data},
            reason=reason,
        )
