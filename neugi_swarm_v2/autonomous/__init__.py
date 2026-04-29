"""
NEUGI v2 - Autonomous Subsystem
================================

Sovereign infrastructure that enables NEUGI to act pro-actively
without user prompts. The autonomous loop observes, decides, executes,
and reports — continuously, even during idle periods.

Architecture:
    Observer → Decision → Executor → Reporter
         ↑___________________________↓

Key principle: NEUGI is not a chatbot. It is autonomous infrastructure
that advances its own goals, maintains its own health, and learns from
its own observations.
"""

from __future__ import annotations

from autonomous.loop_engine import (
    AutonomousLoop,
    LoopConfig,
    LoopState,
    LoopError,
    LoopResult,
    AutonomousActivity,
    ActivityType,
    ActivityPriority,
    ActivityStatus,
)

from autonomous.observer import (
    IdleObserver,
    Observation,
    ObservationType,
    SystemSignal,
    MemorySignal,
    GoalSignal,
    HealthSignal,
    LearningSignal,
)

from autonomous.decision import (
    ProactiveDecisionEngine,
    Decision,
    DecisionType,
    DecisionOutcome,
    DecisionCriteria,
    RiskAssessment,
    ValueAssessment,
)

from autonomous.executor import (
    SelfDirectedExecutor,
    ExecutionResult,
    ExecutionType,
    ExecutionContext,
    ActionResult,
)

from autonomous.reporter import (
    ActivityReporter,
    ActivityReport,
    ReportChannel,
    ReportSeverity,
)

from autonomous.research_engine import (
    ResearchEngine,
    ResearchConfig,
    ResearchReport,
    ResearchRound,
    ResearchSource,
    ResearchFinding,
    ResearchHypothesis,
)

from autonomous.subsystem_wiring import (
    SubsystemWiring,
)

from autonomous.notification_dispatcher import (
    NotificationDispatcher,
    NotificationPreferences,
    NotificationFrequency,
    NotificationChannel,
    AutonomousNotification,
)

from autonomous.agent_spawner import (
    AutonomousAgentSpawner,
    SpawnedAgentResult,
)

__all__ = [
    # Loop Engine
    "AutonomousLoop",
    "LoopConfig",
    "LoopState",
    "LoopError",
    "LoopResult",
    "AutonomousActivity",
    "ActivityType",
    "ActivityPriority",
    "ActivityStatus",
    # Observer
    "IdleObserver",
    "Observation",
    "ObservationType",
    "SystemSignal",
    "MemorySignal",
    "GoalSignal",
    "HealthSignal",
    "LearningSignal",
    # Decision
    "ProactiveDecisionEngine",
    "Decision",
    "DecisionType",
    "DecisionOutcome",
    "DecisionCriteria",
    "RiskAssessment",
    "ValueAssessment",
    # Executor
    "SelfDirectedExecutor",
    "ExecutionResult",
    "ExecutionType",
    "ExecutionContext",
    "ActionResult",
    # Reporter
    "ActivityReporter",
    "ActivityReport",
    "ReportChannel",
    "ReportSeverity",
    # Research Engine
    "ResearchEngine",
    "ResearchConfig",
    "ResearchReport",
    "ResearchRound",
    "ResearchSource",
    "ResearchFinding",
    "ResearchHypothesis",
    # Subsystem Wiring
    "SubsystemWiring",
    # Notification Dispatcher
    "NotificationDispatcher",
    "NotificationPreferences",
    "NotificationFrequency",
    "NotificationChannel",
    "AutonomousNotification",
    # Agent Spawner
    "AutonomousAgentSpawner",
    "SpawnedAgentResult",
]
