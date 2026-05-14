"""
NEUGI v2 - Autonomous Loop Engine
==================================

The sovereign heart of NEUGI. This is what makes NEUGI pro-active.

When NEUGI is idle (no user interaction), the AutonomousLoop continuously:
1. OBSERVES the system state (memory, goals, health, learning signals)
2. DECIDES what actions would be valuable
3. EXECUTES approved actions
4. REPORTS what was done

The loop respects:
- Idle time (only runs when no recent user interaction)
- Resource budgets (time, tokens, disk)
- Rate limits (max actions per day)
- Circuit breakers (stops if too many failures)
- User preferences (from SoulEngine USER.md)

Thread-safety guarantees:
- All mutable shared state is protected by self._lock (RLock)
- _last_user_interaction is atomic (float assignment is safe on CPython)
- _stop_event is thread-safe by design
- Database connections are opened per-tick and closed immediately

Resource guarantees:
- _activities capped at _MAX_ACTIVITIES
- _action_count_today auto-resets at midnight UTC
- All exceptions are caught; loop never dies
"""

from __future__ import annotations

import logging
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from autonomous.decision import DecisionCriteria, DecisionOutcome, ProactiveDecisionEngine
from autonomous.executor import ExecutionContext, ExecutionResult, SelfDirectedExecutor
from autonomous.observer import IdleObserver
from autonomous.reporter import ActivityReporter, ReportSeverity

logger = logging.getLogger(__name__)


class ActivityType(str, Enum):
    OBSERVATION = "observation"
    DECISION = "decision"
    EXECUTION = "execution"
    REPORT = "report"
    IDLE_TICK = "idle_tick"


class ActivityPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class ActivityStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class LoopState(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class AutonomousActivity:
    activity_id: str
    activity_type: ActivityType
    priority: ActivityPriority
    status: ActivityStatus
    description: str
    result: dict[str, Any] | None = None
    error: str | None = None
    started_at: float = field(default_factory=lambda: time.time())
    finished_at: float | None = None

    @property
    def duration_ms(self) -> float:
        if self.finished_at:
            return (self.finished_at - self.started_at) * 1000
        return (time.time() - self.started_at) * 1000


@dataclass
class LoopResult:
    tick_id: str
    observations: int = 0
    decisions: int = 0
    executions: int = 0
    reports: int = 0
    success: bool = True
    duration_ms: float = 0.0
    error: str | None = None


@dataclass
class LoopConfig:
    """Configuration for the autonomous loop.

    Attributes:
        tick_interval_seconds: Seconds between ticks (default 60).
        idle_threshold_seconds: Min idle before acting (default 300 = 5 min).
        max_actions_per_tick: Max actions per tick (default 3).
        max_actions_per_day: Max actions per day (default 20).
        circuit_breaker_threshold: Failures before circuit opens (default 5).
        circuit_breaker_timeout_seconds: Retry delay after open (default 300).
        dry_run: If True, observe+decide without execute.
        enabled: Master switch.
        autostart: If True, loop auto-starts after init (default True).
        max_activities_history: Cap for in-memory activity log (default 1000).
    """

    tick_interval_seconds: float = 60.0
    idle_threshold_seconds: float = 300.0
    max_actions_per_tick: int = 3
    max_actions_per_day: int = 20
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout_seconds: float = 300.0
    dry_run: bool = False
    enabled: bool = True
    autostart: bool = True
    max_activities_history: int = 1000


class LoopError(Exception):
    pass


class AutonomousLoop:
    """Sovereign autonomous loop for NEUGI.

    Thread-safe. Resource-capped. Self-healing. Auto-starts by default.
    """

    _MAX_ACTIVITIES: int = 1000  # hard ceiling for safety

    def __init__(
        self,
        swarm: Any,
        config: LoopConfig | None = None,
    ) -> None:
        self.swarm = swarm
        self.config = config or LoopConfig()

        # Subsystems
        self.observer: IdleObserver | None = None
        self.decision_engine: ProactiveDecisionEngine | None = None
        self.executor: SelfDirectedExecutor | None = None
        self.reporter: ActivityReporter | None = None

        # Threading
        self._state = LoopState.STOPPED
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.RLock()

        # Statistics — all mutable counters protected by _lock
        self._tick_count: int = 0
        self._action_count_today: int = 0
        self._last_day_reset: str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self._last_tick: float = 0.0
        self._last_user_interaction: float = time.time()
        self._failure_count: int = 0
        self._circuit_open: bool = False
        self._circuit_opened_at: float = 0.0
        self._activities: list[AutonomousActivity] = []

        self._init_subsystems()

        # Auto-start if configured
        if self.config.autostart and self.config.enabled:
            self.start()

    def _init_subsystems(self) -> None:
        """Initialize observer, decision, executor, and reporter."""
        memory_db = getattr(self.swarm, "memory_db_path", "~/.neugi/memory.db")
        goals_db = getattr(self.swarm, "goals_db_path", None)
        system_db = getattr(self.swarm, "system_db_path", None)

        self.observer = IdleObserver(
            memory_db_path=memory_db,
            goals_db_path=goals_db,
            system_db_path=system_db,
        )

        criteria = DecisionCriteria(
            max_daily_autonomous_actions=self.config.max_actions_per_day,
        )
        self.decision_engine = ProactiveDecisionEngine(
            criteria=criteria,
            today_action_count=self._action_count_today,
            capability_profile=getattr(self.swarm, "capability_profile", None),
        )

        context = ExecutionContext(
            memory_system=getattr(self.swarm, "memory", None),
            goal_system=getattr(self.swarm, "goals", None),
            agent_manager=getattr(self.swarm, "agents", None),
            skill_generator=getattr(self.swarm, "skill_generator", None),
            web_search=getattr(self.swarm, "web_search", None),
            llm_callback=getattr(self.swarm, "_llm_call", None),
            capability_profile=getattr(self.swarm, "capability_profile", None),
            dry_run=self.config.dry_run,
        )
        self.executor = SelfDirectedExecutor(context=context)

        # Notification dispatcher for proactive channels
        from autonomous.notification_dispatcher import (
            NotificationDispatcher,
            NotificationPreferences,
        )
        notifier = NotificationDispatcher(
            preferences=NotificationPreferences(),
            channel_manager=getattr(self.swarm, "channel_manager", None),
            event_bus=getattr(self.swarm, "message_bus", None),
        )

        self.reporter = ActivityReporter(
            memory_system=getattr(self.swarm, "memory", None),
            event_bus=getattr(self.swarm, "message_bus", None),
            user_notify_threshold=ReportSeverity.WARNING,
            max_reports=self.config.max_activities_history,
            notification_dispatcher=notifier,
        )

    # -- Lifecycle --------------------------------------------------------------

    @property
    def state(self) -> LoopState:
        with self._lock:
            return self._state

    def start(self) -> None:
        """Start the autonomous loop in a background thread."""
        with self._lock:
            if self._state in (LoopState.RUNNING, LoopState.STARTING):
                logger.debug("AutonomousLoop already running")
                return
            if not self.config.enabled:
                logger.info("AutonomousLoop disabled in config")
                return
            self._state = LoopState.STARTING
            self._stop_event.clear()

        self._thread = threading.Thread(
            target=self._run_loop,
            name="NEUGI-AutonomousLoop",
            daemon=True,
        )
        self._thread.start()

        logger.info(
            "AutonomousLoop started (tick=%.0fs, idle_threshold=%.0fs, autostart=%s)",
            self.config.tick_interval_seconds,
            self.config.idle_threshold_seconds,
            self.config.autostart,
        )

    def stop(self) -> None:
        """Stop the autonomous loop gracefully."""
        with self._lock:
            if self._state in (LoopState.STOPPED, LoopState.STOPPING):
                return
            self._state = LoopState.STOPPING

        self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
            if self._thread.is_alive():
                logger.warning("AutonomousLoop thread did not terminate within 5s")

        with self._lock:
            self._state = LoopState.STOPPED

        logger.info("AutonomousLoop stopped")

    def pause(self) -> None:
        with self._lock:
            if self._state == LoopState.RUNNING:
                self._state = LoopState.PAUSED
                logger.info("AutonomousLoop paused")

    def resume(self) -> None:
        with self._lock:
            if self._state == LoopState.PAUSED:
                self._state = LoopState.RUNNING
                logger.info("AutonomousLoop resumed")

    def touch(self) -> None:
        """Record user interaction (resets idle timer). Thread-safe."""
        self._last_user_interaction = time.time()
        logger.debug("User interaction detected, idle timer reset")

    # -- Main Loop --------------------------------------------------------------

    def _run_loop(self) -> None:
        """Main loop thread — never raises."""
        # Set state to RUNNING only after thread is actually executing
        with self._lock:
            self._state = LoopState.RUNNING

        while not self._stop_event.is_set():
            try:
                with self._lock:
                    should_run = self._state == LoopState.RUNNING
                if not should_run:
                    time.sleep(1.0)
                    continue

                self._tick()

            except Exception as e:
                logger.error("AutonomousLoop tick error: %s\n%s", e, traceback.format_exc())
                with self._lock:
                    self._failure_count += 1
                    if self._failure_count >= self.config.circuit_breaker_threshold:
                        self._open_circuit()

            self._stop_event.wait(self.config.tick_interval_seconds)

    def _tick(self) -> LoopResult:
        """Execute one loop tick. Thread-safe."""
        tick_id = f"tick_{int(time.time())}_{uuid.uuid4().hex[:4]}"
        start = time.time()

        result = LoopResult(tick_id=tick_id)

        with self._lock:
            self._tick_count += 1
            self._last_tick = start
            # Reset daily counters if date changed
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if today != self._last_day_reset:
                self._action_count_today = 0
                self._last_day_reset = today
                logger.info("Autonomous daily counters reset")

            circuit_open = self._circuit_open
            circuit_opened_at = self._circuit_opened_at
            idle_threshold = self.config.idle_threshold_seconds
            max_actions_per_tick = self.config.max_actions_per_tick
            action_count_today = self._action_count_today
            failure_count = self._failure_count

        # Circuit breaker check
        if circuit_open:
            if time.time() - circuit_opened_at > self.config.circuit_breaker_timeout_seconds:
                self._close_circuit()
            else:
                logger.debug("Circuit breaker open, skipping tick")
                result.success = True
                return result

        # Idle threshold check
        idle_seconds = time.time() - self._last_user_interaction
        if idle_seconds < idle_threshold:
            logger.debug("Not idle enough (%.0fs < %.0fs), skipping", idle_seconds, idle_threshold)
            result.success = True
            return result

        # Step 1: OBSERVE
        try:
            observations = self.observer.observe() if self.observer else []
        except Exception as e:
            logger.warning("Observation failed: %s", e)
            observations = []
        result.observations = len(observations)

        if not observations:
            result.success = True
            result.duration_ms = (time.time() - start) * 1000
            return result

        # Step 2: DECIDE
        try:
            decisions = self.decision_engine.decide(observations) if self.decision_engine else []
        except Exception as e:
            logger.warning("Decision failed: %s", e)
            decisions = []
        approved = [d for d in decisions if d.outcome == DecisionOutcome.APPROVED]
        result.decisions = len(approved)

        if not approved:
            result.success = True
            result.duration_ms = (time.time() - start) * 1000
            return result

        # Limit actions per tick
        to_execute = approved[:max_actions_per_tick]

        # Step 3: EXECUTE
        exec_results: list[ExecutionResult] = []
        if self.executor:
            try:
                exec_results = self.executor.execute_batch(to_execute)
            except Exception as e:
                logger.error("Execution batch failed: %s", e)
                exec_results = []
            result.executions = len(exec_results)

            # Update counters under lock
            successful = sum(1 for r in exec_results if r.success)
            failed = len(exec_results) - successful
            with self._lock:
                self._action_count_today += successful
                self._failure_count += failed

            # Step 4: REPORT
            if self.reporter:
                try:
                    self.reporter.report_batch(exec_results)
                except Exception as e:
                    logger.warning("Reporting failed: %s", e)

            # Critical failure check
            if failed > 0 and any(
                r.decision.source_observation.urgency > 0.8
                for r in exec_results if not r.success
            ):
                logger.warning("Critical autonomous action failed")

        result.success = True
        result.duration_ms = (time.time() - start) * 1000

        # Update decision engine
        if self.decision_engine:
            with self._lock:
                self.decision_engine.today_action_count = self._action_count_today

        # Prune activity log
        self._prune_activities()

        logger.debug(
            "Autonomous tick %s: %d obs, %d decisions, %d execs, %.0fms",
            tick_id, result.observations, result.decisions, result.executions,
            result.duration_ms,
        )
        return result

    def _open_circuit(self) -> None:
        with self._lock:
            self._circuit_open = True
            self._circuit_opened_at = time.time()
            logger.warning("Circuit breaker OPENED after %d failures", self._failure_count)

    def _close_circuit(self) -> None:
        with self._lock:
            self._circuit_open = False
            self._failure_count = 0
            logger.info("Circuit breaker CLOSED")

    def _prune_activities(self) -> None:
        """Cap activity log to prevent unbounded growth."""
        with self._lock:
            cap = min(self.config.max_activities_history, self._MAX_ACTIVITIES)
            if len(self._activities) > cap:
                self._activities = self._activities[-cap:]

    # -- Stats & Diagnostics ----------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "state": self._state.value,
                "tick_count": self._tick_count,
                "action_count_today": self._action_count_today,
                "failure_count": self._failure_count,
                "circuit_open": self._circuit_open,
                "last_tick": self._last_tick,
                "idle_seconds": time.time() - self._last_user_interaction,
                "config": {
                    "tick_interval": self.config.tick_interval_seconds,
                    "idle_threshold": self.config.idle_threshold_seconds,
                    "max_actions_per_tick": self.config.max_actions_per_tick,
                    "max_actions_per_day": self.config.max_actions_per_day,
                    "dry_run": self.config.dry_run,
                    "enabled": self.config.enabled,
                    "autostart": self.config.autostart,
                },
                "observer": self.observer.get_signals() if self.observer else {},
                "decision_engine": self.decision_engine.get_stats() if self.decision_engine else {},
                "executor": self.executor.get_stats() if self.executor else {},
                "reporter": self.reporter.get_summary() if self.reporter else {},
            }

    def get_recent_activities(self, limit: int = 20) -> list[AutonomousActivity]:
        with self._lock:
            return self._activities[-limit:]

    def get_live_status(self) -> dict[str, Any]:
        """Get real-time autonomous status for dashboard/WebSocket.

        Returns:
            Dict with current state, recent activities, and subsystem health.
        """
        with self._lock:
            recent_activities = [
                {
                    "id": a.activity_id,
                    "type": a.activity_type.value,
                    "priority": a.priority.value,
                    "status": a.status.value,
                    "description": a.description,
                    "duration_ms": a.duration_ms,
                }
                for a in self._activities[-10:]
            ]

            return {
                "state": self._state.value,
                "idle_seconds": time.time() - self._last_user_interaction,
                "is_idle": (time.time() - self._last_user_interaction) >= self.config.idle_threshold_seconds,
                "circuit_open": self._circuit_open,
                "action_count_today": self._action_count_today,
                "daily_limit": self.config.max_actions_per_day,
                "tick_count": self._tick_count,
                "failure_count": self._failure_count,
                "config": {
                    "tick_interval": self.config.tick_interval_seconds,
                    "idle_threshold": self.config.idle_threshold_seconds,
                    "max_actions_per_tick": self.config.max_actions_per_tick,
                    "dry_run": self.config.dry_run,
                },
                "recent_activities": recent_activities,
                "observer": self.observer.get_signals() if self.observer else {},
                "decision_engine": self.decision_engine.get_stats() if self.decision_engine else {},
                "executor": self.executor.get_stats() if self.executor else {},
                "reporter": self.reporter.get_summary() if self.reporter else {},
            }
