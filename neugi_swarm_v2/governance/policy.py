"""
NEUGI v2 Policy Engine
=======================

Rule-based policy evaluation system for controlling agent behavior
with support for allow/deny/require_approval/rate_limit effects.

Features:
    - Rule-based policy evaluation
    - Policy types: allow, deny, require_approval, rate_limit
    - Policy conditions (agent role, action type, cost, time, risk)
    - Policy inheritance and override
    - Policy evaluation result with explanation
    - Default deny policy

Usage:
    from neugi_swarm_v2.governance.policy import (
        PolicyEngine, Policy, PolicyRule, PolicyEffect,
        PolicyCondition, ConditionOperator,
    )

    engine = PolicyEngine(default_effect=PolicyEffect.DENY)

    # Add a policy
    policy = Policy(
        policy_id="allow_code_execution",
        name="Allow Code Execution",
        effect=PolicyEffect.ALLOW,
        priority=100,
        rules=[
            PolicyRule(
                condition=PolicyCondition(
                    field="action_type",
                    operator=ConditionOperator.EQUALS,
                    value="execute_code",
                ),
            ),
            PolicyRule(
                condition=PolicyCondition(
                    field="agent_role",
                    operator=ConditionOperator.IN,
                    value=["developer", "admin"],
                ),
            ),
        ],
    )
    engine.add_policy(policy)

    # Evaluate an action
    result = engine.evaluate(
        agent_id="aurora",
        agent_role="developer",
        action_type="execute_code",
        cost=0.5,
        risk_level="medium",
    )
    print(result.allowed)  # True
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


# -- Enums -------------------------------------------------------------------

class PolicyEffect(str, Enum):
    """Policy evaluation effects."""
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"
    RATE_LIMIT = "rate_limit"


class ConditionOperator(str, Enum):
    """Condition comparison operators."""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    IN = "in"
    NOT_IN = "not_in"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_EQUALS = "greater_equals"
    LESS_EQUALS = "less_equals"
    CONTAINS = "contains"
    MATCHES = "matches"
    IS_TRUE = "is_true"
    IS_FALSE = "is_false"


# -- Data Classes ------------------------------------------------------------

@dataclass
class PolicyCondition:
    """A single condition for policy evaluation.

    Attributes:
        field: Field to evaluate (e.g., 'action_type', 'agent_role', 'cost').
        operator: Comparison operator.
        value: Value to compare against.
    """

    field: str
    operator: ConditionOperator
    value: Any

    def evaluate(self, context: dict[str, Any]) -> bool:
        """Evaluate this condition against a context.

        Args:
            context: Dictionary of field values.

        Returns:
            True if the condition is satisfied.
        """
        actual = context.get(self.field)

        if self.operator == ConditionOperator.EQUALS:
            return actual == self.value

        elif self.operator == ConditionOperator.NOT_EQUALS:
            return actual != self.value

        elif self.operator == ConditionOperator.IN:
            return actual in self.value

        elif self.operator == ConditionOperator.NOT_IN:
            return actual not in self.value

        elif self.operator == ConditionOperator.GREATER_THAN:
            if actual is None:
                return False
            return actual > self.value

        elif self.operator == ConditionOperator.LESS_THAN:
            if actual is None:
                return False
            return actual < self.value

        elif self.operator == ConditionOperator.GREATER_EQUALS:
            if actual is None:
                return False
            return actual >= self.value

        elif self.operator == ConditionOperator.LESS_EQUALS:
            if actual is None:
                return False
            return actual <= self.value

        elif self.operator == ConditionOperator.CONTAINS:
            if actual is None:
                return False
            return self.value in actual

        elif self.operator == ConditionOperator.MATCHES:
            if actual is None:
                return False
            return bool(re.match(self.value, str(actual)))

        elif self.operator == ConditionOperator.IS_TRUE:
            return bool(actual)

        elif self.operator == ConditionOperator.IS_FALSE:
            return not bool(actual)

        return False


@dataclass
class PolicyRule:
    """A rule within a policy.

    Rules within a policy are ANDed together (all must match).

    Attributes:
        rule_id: Unique rule identifier.
        condition: Condition to evaluate.
        description: Human-readable description.
    """

    condition: PolicyCondition
    rule_id: str = ""
    description: str = ""

    def evaluate(self, context: dict[str, Any]) -> bool:
        """Evaluate this rule against a context.

        Args:
            context: Dictionary of field values.

        Returns:
            True if the condition is satisfied.
        """
        return self.condition.evaluate(context)


@dataclass
class PolicyOverride:
    """An override for a specific policy.

    Overrides can temporarily change a policy's effect.

    Attributes:
        override_id: Unique override identifier.
        policy_id: Policy being overridden.
        new_effect: New effect to apply.
        reason: Reason for the override.
        expires_at: When the override expires.
        created_by: Who created the override.
        created_at: When the override was created.
    """

    policy_id: str
    new_effect: PolicyEffect
    reason: str = ""
    override_id: str = ""
    expires_at: Optional[datetime] = None
    created_by: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_active(self) -> bool:
        """Check if the override is currently active."""
        if self.expires_at is None:
            return True
        return datetime.now(timezone.utc) <= self.expires_at


@dataclass
class Policy:
    """A policy with rules and an effect.

    Attributes:
        policy_id: Unique policy identifier.
        name: Human-readable policy name.
        effect: Effect when policy matches.
        priority: Evaluation priority (higher = evaluated first).
        rules: List of rules (ANDed together).
        description: Human-readable description.
        enabled: Whether the policy is active.
        overrides: Active overrides.
        metadata: Additional context.
        created_at: Creation timestamp.
    """

    policy_id: str
    name: str
    effect: PolicyEffect
    priority: int = 0
    rules: list[PolicyRule] = field(default_factory=list)
    description: str = ""
    enabled: bool = True
    overrides: list[PolicyOverride] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def evaluate(self, context: dict[str, Any]) -> tuple[bool, list[str]]:
        """Evaluate this policy against a context.

        All rules must match (AND logic) for the policy to apply.

        Args:
            context: Dictionary of field values.

        Returns:
            Tuple of (matches, list of reasons).
        """
        if not self.enabled:
            return False, ["Policy is disabled"]

        if not self.rules:
            return True, ["No rules (matches all)"]

        reasons = []
        for rule in self.rules:
            if rule.evaluate(context):
                reasons.append(f"Rule matched: {rule.description or rule.condition.field}")
            else:
                return False, [f"Rule failed: {rule.description or rule.condition.field}"]

        return True, reasons

    def get_effective_effect(self) -> PolicyEffect:
        """Get the effective effect considering overrides.

        Returns:
            The active PolicyEffect.
        """
        for override in self.overrides:
            if override.is_active:
                return override.new_effect
        return self.effect

    def add_override(self, override: PolicyOverride) -> None:
        """Add an override to this policy.

        Args:
            override: Override to add.
        """
        self.overrides.append(override)

    def remove_expired_overrides(self) -> int:
        """Remove expired overrides.

        Returns:
            Number of overrides removed.
        """
        before = len(self.overrides)
        self.overrides = [o for o in self.overrides if o.is_active]
        return before - len(self.overrides)


@dataclass
class PolicyEvaluation:
    """Context for a policy evaluation.

    Attributes:
        agent_id: Agent being evaluated.
        agent_role: Role of the agent.
        action_type: Action being performed.
        cost: Estimated cost.
        risk_level: Risk level.
        timestamp: Evaluation time.
        metadata: Additional context.
    """

    agent_id: str = ""
    agent_role: str = ""
    action_type: str = ""
    cost: float = 0.0
    risk_level: str = "low"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_context(self) -> dict[str, Any]:
        """Convert to a context dictionary for policy evaluation.

        Returns:
            Dictionary of field values.
        """
        return {
            "agent_id": self.agent_id,
            "agent_role": self.agent_role,
            "action_type": self.action_type,
            "cost": self.cost,
            "risk_level": self.risk_level,
            "timestamp": self.timestamp.isoformat(),
            **self.metadata,
        }


@dataclass
class PolicyEvaluationResult:
    """Result of a policy evaluation.

    Attributes:
        allowed: Whether the action is allowed.
        effect: The policy effect that was applied.
        policy_id: ID of the matching policy.
        policy_name: Name of the matching policy.
        explanation: Human-readable explanation.
        reasons: Detailed reasons for the decision.
        requires_approval: Whether approval is needed.
        rate_limit: Rate limit info (if applicable).
        evaluated_at: Evaluation timestamp.
    """

    allowed: bool
    effect: PolicyEffect
    policy_id: str = ""
    policy_name: str = ""
    explanation: str = ""
    reasons: list[str] = field(default_factory=list)
    requires_approval: bool = False
    rate_limit: Optional[dict[str, Any]] = None
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PolicyError(Exception):
    """Raised when a policy operation fails.

    Attributes:
        message: Human-readable error message.
        policy_id: Related policy ID.
    """

    message: str = ""
    policy_id: str = ""


# -- Policy Engine -----------------------------------------------------------

class PolicyEngine:
    """Rule-based policy evaluation engine.

    Evaluates actions against a set of policies with support for
    inheritance, overrides, and default-deny semantics.

    Args:
        default_effect: Effect when no policy matches.

    Attributes:
        default_effect: Default policy effect.
        _policies: Policy storage (ordered by priority).
        _rate_limits: Rate limit tracking.
    """

    def __init__(
        self,
        default_effect: PolicyEffect = PolicyEffect.DENY,
    ) -> None:
        self.default_effect = default_effect
        self._policies: dict[str, Policy] = {}
        self._rate_limits: dict[str, list[float]] = {}

    def add_policy(self, policy: Policy) -> Policy:
        """Add a policy to the engine.

        Args:
            policy: Policy to add.

        Returns:
            The added policy.
        """
        self._policies[policy.policy_id] = policy
        logger.info("Policy added: %s (effect=%s, priority=%d)",
                     policy.name, policy.effect.value, policy.priority)
        return policy

    def remove_policy(self, policy_id: str) -> bool:
        """Remove a policy from the engine.

        Args:
            policy_id: Policy to remove.

        Returns:
            True if removed, False if not found.
        """
        if policy_id in self._policies:
            del self._policies[policy_id]
            logger.info("Policy removed: %s", policy_id)
            return True
        return False

    def get_policy(self, policy_id: str) -> Optional[Policy]:
        """Get a policy by ID.

        Args:
            policy_id: Policy identifier.

        Returns:
            Policy if found, None otherwise.
        """
        return self._policies.get(policy_id)

    def list_policies(self, enabled_only: bool = True) -> list[Policy]:
        """List all policies sorted by priority.

        Args:
            enabled_only: Only return enabled policies.

        Returns:
            List of policies sorted by priority (highest first).
        """
        policies = list(self._policies.values())
        if enabled_only:
            policies = [p for p in policies if p.enabled]
        return sorted(policies, key=lambda p: p.priority, reverse=True)

    def evaluate(
        self,
        agent_id: str = "",
        agent_role: str = "",
        action_type: str = "",
        cost: float = 0.0,
        risk_level: str = "low",
        metadata: Optional[dict[str, Any]] = None,
    ) -> PolicyEvaluationResult:
        """Evaluate an action against all policies.

        Policies are evaluated in priority order (highest first).
        The first matching policy determines the result.

        Args:
            agent_id: Agent being evaluated.
            agent_role: Role of the agent.
            action_type: Action being performed.
            cost: Estimated cost.
            risk_level: Risk level.
            metadata: Additional context.

        Returns:
            PolicyEvaluationResult with decision and explanation.
        """
        evaluation = PolicyEvaluation(
            agent_id=agent_id,
            agent_role=agent_role,
            action_type=action_type,
            cost=cost,
            risk_level=risk_level,
            metadata=metadata or {},
        )
        context = evaluation.to_context()

        policies = self.list_policies(enabled_only=True)

        for policy in policies:
            matches, reasons = policy.evaluate(context)

            if matches:
                effect = policy.get_effective_effect()
                return self._build_result(
                    policy=policy,
                    effect=effect,
                    reasons=reasons,
                    context=context,
                )

        return self._build_default_result(context)

    def _build_result(
        self,
        policy: Policy,
        effect: PolicyEffect,
        reasons: list[str],
        context: dict[str, Any],
    ) -> PolicyEvaluationResult:
        """Build an evaluation result from a matching policy.

        Args:
            policy: Matching policy.
            effect: Effective policy effect.
            reasons: Reasons for the match.
            context: Evaluation context.

        Returns:
            PolicyEvaluationResult.
        """
        if effect == PolicyEffect.ALLOW:
            return PolicyEvaluationResult(
                allowed=True,
                effect=effect,
                policy_id=policy.policy_id,
                policy_name=policy.name,
                explanation=f"Allowed by policy: {policy.name}",
                reasons=reasons,
            )

        elif effect == PolicyEffect.DENY:
            return PolicyEvaluationResult(
                allowed=False,
                effect=effect,
                policy_id=policy.policy_id,
                policy_name=policy.name,
                explanation=f"Denied by policy: {policy.name}",
                reasons=reasons,
            )

        elif effect == PolicyEffect.REQUIRE_APPROVAL:
            return PolicyEvaluationResult(
                allowed=False,
                effect=effect,
                policy_id=policy.policy_id,
                policy_name=policy.name,
                explanation=f"Approval required by policy: {policy.name}",
                reasons=reasons,
                requires_approval=True,
            )

        elif effect == PolicyEffect.RATE_LIMIT:
            rate_limit_info = self._check_rate_limit(
                policy.policy_id, context,
            )
            return PolicyEvaluationResult(
                allowed=rate_limit_info["allowed"],
                effect=effect,
                policy_id=policy.policy_id,
                policy_name=policy.name,
                explanation=f"Rate limited by policy: {policy.name}",
                reasons=reasons,
                rate_limit=rate_limit_info,
            )

        return PolicyEvaluationResult(
            allowed=False,
            effect=effect,
            policy_id=policy.policy_id,
            policy_name=policy.name,
            explanation=f"Unknown effect: {effect.value}",
            reasons=reasons,
        )

    def _build_default_result(
        self,
        context: dict[str, Any],
    ) -> PolicyEvaluationResult:
        """Build a result when no policy matches.

        Args:
            context: Evaluation context.

        Returns:
            PolicyEvaluationResult with default effect.
        """
        if self.default_effect == PolicyEffect.ALLOW:
            return PolicyEvaluationResult(
                allowed=True,
                effect=self.default_effect,
                explanation="Allowed by default (no matching policy)",
                reasons=["No policy matched"],
            )

        return PolicyEvaluationResult(
            allowed=False,
            effect=self.default_effect,
            explanation=f"Denied by default (no matching policy, default={self.default_effect.value})",
            reasons=["No policy matched", f"Default effect: {self.default_effect.value}"],
        )

    def _check_rate_limit(
        self,
        policy_id: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Check rate limit for a policy.

        Args:
            policy_id: Policy identifier.
            context: Evaluation context.

        Returns:
            Dictionary with rate limit info.
        """
        policy = self._policies.get(policy_id)
        if policy is None:
            return {"allowed": True, "reason": "Policy not found"}

        rate_config = policy.metadata.get("rate_limit", {})
        max_requests = rate_config.get("max_requests", 10)
        window_seconds = rate_config.get("window_seconds", 60)

        key = f"{policy_id}:{context.get('agent_id', '')}:{context.get('action_type', '')}"
        now = time.time()

        if key not in self._rate_limits:
            self._rate_limits[key] = []

        timestamps = self._rate_limits[key]
        timestamps = [t for t in timestamps if now - t < window_seconds]
        self._rate_limits[key] = timestamps

        if len(timestamps) >= max_requests:
            return {
                "allowed": False,
                "reason": f"Rate limit exceeded: {len(timestamps)}/{max_requests} in {window_seconds}s",
                "max_requests": max_requests,
                "window_seconds": window_seconds,
                "retry_after": window_seconds - (now - timestamps[0]) if timestamps else 0,
            }

        timestamps.append(now)
        return {
            "allowed": True,
            "reason": f"Rate limit OK: {len(timestamps)}/{max_requests} in {window_seconds}s",
            "max_requests": max_requests,
            "window_seconds": window_seconds,
            "remaining": max_requests - len(timestamps),
        }

    def add_override(
        self,
        policy_id: str,
        new_effect: PolicyEffect,
        reason: str = "",
        expires_at: Optional[datetime] = None,
        created_by: str = "",
    ) -> Optional[PolicyOverride]:
        """Add an override to a policy.

        Args:
            policy_id: Policy to override.
            new_effect: New effect.
            reason: Reason for override.
            expires_at: When override expires.
            created_by: Who created it.

        Returns:
            PolicyOverride if policy found, None otherwise.
        """
        policy = self._policies.get(policy_id)
        if policy is None:
            return None

        override = PolicyOverride(
            policy_id=policy_id,
            new_effect=new_effect,
            reason=reason,
            expires_at=expires_at,
            created_by=created_by,
        )
        policy.add_override(override)
        logger.info("Policy override added: %s -> %s (%s)",
                     policy_id, new_effect.value, reason)
        return override

    def cleanup_overrides(self) -> int:
        """Remove expired overrides from all policies.

        Returns:
            Total number of overrides removed.
        """
        total = 0
        for policy in self._policies.values():
            total += policy.remove_expired_overrides()
        if total > 0:
            logger.info("Cleaned up %d expired overrides", total)
        return total

    def get_matching_policies(
        self,
        agent_id: str = "",
        agent_role: str = "",
        action_type: str = "",
        cost: float = 0.0,
        risk_level: str = "low",
    ) -> list[tuple[Policy, bool, list[str]]]:
        """Get all policies that match the given context.

        Args:
            agent_id: Agent being evaluated.
            agent_role: Role of the agent.
            action_type: Action being performed.
            cost: Estimated cost.
            risk_level: Risk level.

        Returns:
            List of (policy, matches, reasons) tuples.
        """
        context = {
            "agent_id": agent_id,
            "agent_role": agent_role,
            "action_type": action_type,
            "cost": cost,
            "risk_level": risk_level,
        }

        results = []
        for policy in self.list_policies(enabled_only=True):
            matches, reasons = policy.evaluate(context)
            results.append((policy, matches, reasons))

        return results

    def export_policies(self) -> list[dict[str, Any]]:
        """Export all policies as serializable dictionaries.

        Returns:
            List of policy dictionaries.
        """
        policies = []
        for policy in self.list_policies(enabled_only=False):
            policy_data = {
                "policy_id": policy.policy_id,
                "name": policy.name,
                "effect": policy.effect.value,
                "priority": policy.priority,
                "description": policy.description,
                "enabled": policy.enabled,
                "created_at": policy.created_at.isoformat(),
                "rules": [],
                "metadata": policy.metadata,
            }

            for rule in policy.rules:
                policy_data["rules"].append({
                    "rule_id": rule.rule_id,
                    "description": rule.description,
                    "condition": {
                        "field": rule.condition.field,
                        "operator": rule.condition.operator.value,
                        "value": rule.condition.value,
                    },
                })

            policies.append(policy_data)

        return policies

    def import_policies(self, policies_data: list[dict[str, Any]]) -> int:
        """Import policies from serialized dictionaries.

        Args:
            policies_data: List of policy dictionaries.

        Returns:
            Number of policies imported.
        """
        count = 0
        for data in policies_data:
            try:
                rules = []
                for rule_data in data.get("rules", []):
                    condition_data = rule_data.get("condition", {})
                    condition = PolicyCondition(
                        field=condition_data.get("field", ""),
                        operator=ConditionOperator(condition_data.get("operator", "equals")),
                        value=condition_data.get("value"),
                    )
                    rules.append(PolicyRule(
                        condition=condition,
                        rule_id=rule_data.get("rule_id", ""),
                        description=rule_data.get("description", ""),
                    ))

                policy = Policy(
                    policy_id=data["policy_id"],
                    name=data["name"],
                    effect=PolicyEffect(data.get("effect", "deny")),
                    priority=data.get("priority", 0),
                    rules=rules,
                    description=data.get("description", ""),
                    enabled=data.get("enabled", True),
                    metadata=data.get("metadata", {}),
                )
                self.add_policy(policy)
                count += 1
            except (KeyError, ValueError) as e:
                logger.warning("Failed to import policy: %s", e)

        logger.info("Imported %d policies", count)
        return count

    def get_stats(self) -> dict[str, Any]:
        """Get policy engine statistics.

        Returns:
            Dictionary with statistics.
        """
        policies = self.list_policies(enabled_only=False)
        enabled = [p for p in policies if p.enabled]

        effects = {}
        for p in policies:
            effect = p.effect.value
            effects[effect] = effects.get(effect, 0) + 1

        return {
            "total_policies": len(policies),
            "enabled_policies": len(enabled),
            "disabled_policies": len(policies) - len(enabled),
            "effects": effects,
            "default_effect": self.default_effect.value,
            "active_overrides": sum(len(p.overrides) for p in policies),
        }

    def close(self) -> None:
        """Clean up resources."""
        self._rate_limits.clear()

    def __enter__(self) -> "PolicyEngine":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
