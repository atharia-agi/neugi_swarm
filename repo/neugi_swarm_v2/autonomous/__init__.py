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

from autonomous.agent_spawner import (
    AutonomousAgentSpawner,
    SpawnedAgentResult,
)
from autonomous.decision import (
    Decision,
    DecisionCriteria,
    DecisionOutcome,
    DecisionType,
    ProactiveDecisionEngine,
    RiskAssessment,
    ValueAssessment,
)
from autonomous.executor import (
    ActionResult,
    ExecutionContext,
    ExecutionResult,
    ExecutionType,
    SelfDirectedExecutor,
)
from autonomous.loop_engine import (
    ActivityPriority,
    ActivityStatus,
    ActivityType,
    AutonomousActivity,
    AutonomousLoop,
    LoopConfig,
    LoopError,
    LoopResult,
    LoopState,
)
from autonomous.notification_dispatcher import (
    AutonomousNotification,
    NotificationChannel,
    NotificationDispatcher,
    NotificationFrequency,
    NotificationPreferences,
)
from autonomous.observer import (
    GoalSignal,
    HealthSignal,
    IdleObserver,
    LearningSignal,
    MemorySignal,
    Observation,
    ObservationType,
    SystemSignal,
)
from autonomous.reporter import (
    ActivityReport,
    ActivityReporter,
    ReportChannel,
    ReportSeverity,
)
from autonomous.research_engine import (
    ResearchConfig,
    ResearchEngine,
    ResearchFinding,
    ResearchHypothesis,
    ResearchReport,
    ResearchRound,
    ResearchSource,
)
from autonomous.subsystem_wiring import (
    SubsystemWiring,
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
