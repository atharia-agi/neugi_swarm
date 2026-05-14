"""
NEUGI v2 Advanced Planning System
==================================

Production-grade planning subsystem combining the most advanced patterns
from modern agentic systems:

- Tree of Thoughts: Multi-branch exploration with best-first search
- Chain of Verification: Self-factifying response generation
- Self-Reflection: Post-action learning and strategy adjustment
- Goal System: Hierarchical goal-aware execution with autonomy
- Strategic Planner: Long-term planning with risk assessment

Usage:
    from neugi_swarm_v2.planning import (
        TreeOfThoughts,
        ChainOfVerification,
        SelfReflectionEngine,
        GoalSystem,
        StrategicPlanner,
    )
"""

from __future__ import annotations

from .chain_of_verification import (
    ChainOfVerification,
    CoVConfig,
    CoVResult,
    VerificationAnswer,
    VerificationQuestion,
    VerificationState,
)
from .goal_system import (
    Goal,
    GoalDecomposition,
    GoalDependency,
    GoalError,
    GoalHierarchy,
    GoalLevel,
    GoalProgress,
    GoalStatus,
    GoalSuggestion,
    GoalSystem,
)
from .self_reflection import (
    ConfidenceLevel,
    ErrorCategory,
    Reflection,
    ReflectionConfig,
    ReflectionMemory,
    ReflectionResult,
    SelfReflectionEngine,
)
from .strategic_planner import (
    Milestone,
    PlanError,
    PlanPhase,
    PlanQualityReport,
    PlanVisualization,
    ResourceAllocation,
    RiskAssessment,
    RiskLevel,
    StrategicPlan,
    StrategicPlanner,
)
from .tree_of_thoughts import (
    SearchStrategy,
    ThoughtBranch,
    ThoughtNode,
    ThoughtState,
    ToTConfig,
    ToTResult,
    TreeOfThoughts,
)

__all__ = [
    # Tree of Thoughts
    "TreeOfThoughts",
    "ThoughtNode",
    "ThoughtBranch",
    "ToTConfig",
    "ToTResult",
    "SearchStrategy",
    "ThoughtState",
    # Chain of Verification
    "ChainOfVerification",
    "VerificationQuestion",
    "VerificationAnswer",
    "CoVConfig",
    "CoVResult",
    "VerificationState",
    # Self Reflection
    "SelfReflectionEngine",
    "Reflection",
    "ReflectionMemory",
    "ReflectionConfig",
    "ReflectionResult",
    "ConfidenceLevel",
    "ErrorCategory",
    # Goal System
    "GoalSystem",
    "Goal",
    "GoalHierarchy",
    "GoalStatus",
    "GoalLevel",
    "GoalDecomposition",
    "GoalProgress",
    "GoalDependency",
    "GoalSuggestion",
    "GoalError",
    # Strategic Planner
    "StrategicPlanner",
    "StrategicPlan",
    "Milestone",
    "ResourceAllocation",
    "RiskAssessment",
    "RiskLevel",
    "PlanPhase",
    "PlanQualityReport",
    "PlanVisualization",
    "PlanError",
]
