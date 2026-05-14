"""
NEUGI v2 — Multi-Model Router
==============================

Routes user tasks to the best available model based on task complexity.
Simple chat → Local model (fast, free)
Complex coding → Cloud model (smart, accurate)

Configured via config.json — no hardcoded restrictions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from model_capability_router import TaskComplexity, TaskComplexityClassifier

logger = logging.getLogger(__name__)


@dataclass
class ModelRoute:
    """A configured model endpoint for routing."""

    name: str
    provider: str
    model: str
    base_url: str = ""
    api_key: str = ""
    tier: str = "medium"  # local / medium / cloud
    context_length: int = 4096
    max_tools: int = 3
    cost_per_1k: float = 0.0  # Approximate cost for comparison
    enabled: bool = True


@dataclass
class RoutingConfig:
    """Configuration for multi-model routing."""

    enabled: bool = False
    default_model: str = ""  # Which model to use when no route matches
    routes: list[ModelRoute] = field(default_factory=list)
    # Complexity thresholds for routing
    local_threshold: TaskComplexity = TaskComplexity.SIMPLE
    medium_threshold: TaskComplexity = TaskComplexity.MEDIUM


class MultiModelRouter:
    """Routes tasks to the best model based on complexity.

    Usage:
        router = MultiModelRouter(config)
        route = router.pick_model("Write a complex Python script")
        # route.name == "cloud", route.model == "gpt-4o"
    """

    def __init__(self, config: RoutingConfig) -> None:
        self.config = config
        self._classifier = TaskComplexityClassifier()
        self._route_history: list[dict[str, Any]] = []

    def pick_model(self, message: str, context: dict[str, Any] | None = None) -> ModelRoute | None:
        """Pick the best model for a user message.

        Returns:
            ModelRoute or None if no routes configured.
        """
        if not self.config.enabled or not self.config.routes:
            return None

        complexity = self._classifier.classify(message, context)
        route = self._route_by_complexity(complexity)

        self._route_history.append({
            "message": message[:100],
            "complexity": complexity.value,
            "route": route.name if route else None,
        })

        return route

    def pick_for_task(self, task_type: str, description: str = "") -> ModelRoute | None:
        """Pick model for a specific task type.

        Task types: chat, code, research, summarize, vision
        """
        if not self.config.enabled or not self.config.routes:
            return None

        complexity_map = {
            "chat": TaskComplexity.SIMPLE,
            "summarize": TaskComplexity.SIMPLE,
            "code": TaskComplexity.COMPLEX,
            "research": TaskComplexity.COMPLEX,
            "planning": TaskComplexity.STRATEGIC,
            "vision": TaskComplexity.MEDIUM,
            "memory": TaskComplexity.SIMPLE,
            "tool_use": TaskComplexity.MEDIUM,
        }
        complexity = complexity_map.get(task_type, TaskComplexity.MEDIUM)
        return self._route_by_complexity(complexity)

    def _route_by_complexity(self, complexity: TaskComplexity) -> ModelRoute | None:
        """Internal: pick route by complexity tier."""
        enabled_routes = [r for r in self.config.routes if r.enabled]
        if not enabled_routes:
            return None

        # Sort by tier preference
        tier_order = {"local": 0, "medium": 1, "cloud": 2}
        enabled_routes.sort(key=lambda r: tier_order.get(r.tier, 1))

        # Route logic
        if complexity == TaskComplexity.TRIVIAL:
            # Use cheapest/fastest (local)
            for r in enabled_routes:
                if r.tier == "local":
                    return r
            return enabled_routes[0]

        if complexity in (TaskComplexity.SIMPLE, TaskComplexity.MEDIUM):
            # Use medium tier if available, else local
            for r in enabled_routes:
                if r.tier == "medium":
                    return r
            for r in enabled_routes:
                if r.tier == "local":
                    return r
            return enabled_routes[0]

        if complexity in (TaskComplexity.COMPLEX, TaskComplexity.STRATEGIC):
            # Use cloud tier if available
            for r in enabled_routes:
                if r.tier == "cloud":
                    return r
            # Fallback to best available
            enabled_routes.sort(key=lambda r: tier_order.get(r.tier, 1), reverse=True)
            return enabled_routes[0]

        return enabled_routes[0]

    def get_stats(self) -> dict[str, Any]:
        """Get routing statistics."""
        total = len(self._route_history)
        by_complexity = {}
        for h in self._route_history:
            c = h["complexity"]
            by_complexity[c] = by_complexity.get(c, 0) + 1

        return {
            "total_routed": total,
            "by_complexity": by_complexity,
            "routes_configured": len(self.config.routes),
            "enabled": self.config.enabled,
        }

    @classmethod
    def from_config(cls, config_dict: dict[str, Any]) -> MultiModelRouter:
        """Build router from config dict (loaded from config.json)."""
        routing_cfg = config_dict.get("routing", {})
        if not routing_cfg.get("enabled", False):
            return cls(RoutingConfig(enabled=False))

        routes = []
        for r in routing_cfg.get("routes", []):
            routes.append(ModelRoute(
                name=r.get("name", "unnamed"),
                provider=r.get("provider", ""),
                model=r.get("model", ""),
                base_url=r.get("base_url", ""),
                api_key=r.get("api_key", ""),
                tier=r.get("tier", "medium"),
                context_length=r.get("context_length", 4096),
                max_tools=r.get("max_tools", 3),
                cost_per_1k=r.get("cost_per_1k", 0.0),
                enabled=r.get("enabled", True),
            ))

        return cls(RoutingConfig(
            enabled=True,
            default_model=routing_cfg.get("default_model", ""),
            routes=routes,
        ))
