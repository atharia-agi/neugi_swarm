"""
NEUGI v2 - Idle Observer
=========================

Collects signals from the entire system during idle periods.
The observer is the "sensory system" of the autonomous loop —
it watches memory, goals, health, and external state to identify
opportunities for pro-active action.

Observations are non-invasive: they read state but do not modify it.
All signals are scored by urgency and confidence.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ObservationType(str, Enum):
    """Categories of observations the system can make."""

    MEMORY_TREND = "memory_trend"           # Recurring topics in memory
    GOAL_STUCK = "goal_stuck"               # Goal without progress for N hours
    GOAL_NEARLY_COMPLETE = "goal_nearly_complete"  # Goal >80% done
    GOAL_BLOCKED = "goal_blocked"           # Goal with unresolved blockers
    SYSTEM_HEALTH = "system_health"         # Errors, disk space, etc.
    SCHEDULED_OVERDUE = "scheduled_overdue" # Cron job past due
    LEARNING_OPPORTUNITY = "learning_opportunity"  # Pattern suggests new skill
    SELF_IMPROVEMENT = "self_improvement"   # Detected inefficiency
    EXTERNAL_SIGNAL = "external_signal"     # File changes, API changes
    KNOWLEDGE_GAP = "knowledge_gap"         # Repeated failed queries


@dataclass
class Observation:
    """A single observation from the system.

    Attributes:
        obs_type: What kind of observation this is.
        source: Which subsystem produced it (e.g., "memory", "goals").
        description: Human-readable description.
        confidence: 0.0-1.0, how certain we are this is real.
        urgency: 0.0-1.0, how time-sensitive this is.
        value: 0.0-1.0, how much acting on this would help.
        data: Arbitrary structured data.
        observed_at: Unix timestamp.
    """

    obs_type: ObservationType
    source: str
    description: str
    confidence: float = 0.5
    urgency: float = 0.5
    value: float = 0.5
    data: dict[str, Any] = field(default_factory=dict)
    observed_at: float = field(default_factory=lambda: time.time())

    @property
    def priority_score(self) -> float:
        """Composite priority: urgency * value * confidence."""
        return self.urgency * self.value * self.confidence


@dataclass
class SystemSignal:
    """Aggregated system health signal."""

    error_count_24h: int = 0
    warning_count_24h: int = 0
    disk_usage_percent: float = 0.0
    memory_usage_percent: float = 0.0
    last_backup_age_hours: float = 0.0
    uptime_hours: float = 0.0
    anomalies: list[str] = field(default_factory=list)


@dataclass
class MemorySignal:
    """Trends detected in the memory system."""

    top_topics: list[tuple[str, int]] = field(default_factory=list)
    recurring_queries: list[str] = field(default_factory=list)
    memory_count_24h: int = 0
    consolidation_needed: bool = False
    gaps: list[str] = field(default_factory=list)  # Topics with few entries


@dataclass
class GoalSignal:
    """State of goals that may need attention."""

    stuck_goals: list[dict[str, Any]] = field(default_factory=list)
    nearly_complete: list[dict[str, Any]] = field(default_factory=list)
    blocked_goals: list[dict[str, Any]] = field(default_factory=list)
    overdue_milestones: list[dict[str, Any]] = field(default_factory=list)
    active_count: int = 0
    total_count: int = 0


@dataclass
class HealthSignal:
    """Health and performance signals."""

    slow_operations: list[dict[str, Any]] = field(default_factory=list)
    failed_operations_24h: int = 0
    circuit_breakers_tripped: list[str] = field(default_factory=list)
    rate_limits_hit: int = 0


@dataclass
class LearningSignal:
    """Opportunities for the system to learn or improve."""

    repeated_patterns: list[dict[str, Any]] = field(default_factory=list)
    skill_gaps: list[str] = field(default_factory=list)
    user_preferences_detected: list[str] = field(default_factory=list)
    tool_usage_inefficiencies: list[str] = field(default_factory=list)


class IdleObserver:
    """Observes system state during idle periods to find action opportunities.

    The observer is read-only: it inspects subsystems but never modifies them.
    All observations are scored by urgency, value, and confidence.

    Args:
        memory_db_path: Path to memory SQLite database.
        goals_db_path: Path to goals SQLite database (optional).
        system_db_path: Path to system/audit SQLite database (optional).
    """

    def __init__(
        self,
        memory_db_path: str | Path,
        goals_db_path: str | Path | None = None,
        system_db_path: str | Path | None = None,
    ) -> None:
        self.memory_db_path = str(memory_db_path)
        self.goals_db_path = str(goals_db_path) if goals_db_path else None
        self.system_db_path = str(system_db_path) if system_db_path else None

    # -- Public API ------------------------------------------------------------

    def observe(self) -> list[Observation]:
        """Collect all observations from all subsystems.

        Returns:
            List of observations sorted by priority_score descending.
        """
        observations: list[Observation] = []

        observations.extend(self._observe_memory())
        observations.extend(self._observe_goals())
        observations.extend(self._observe_system_health())
        observations.extend(self._observe_learning_opportunities())
        observations.extend(self._observe_scheduled_tasks())
        observations.extend(self._observe_research_opportunities())

        observations.sort(key=lambda o: o.priority_score, reverse=True)
        return observations

    def get_signals(self) -> dict[str, Any]:
        """Get structured signal summary for decision engine.

        Returns:
            Dict with memory, goal, health, and learning signals.
        """
        return {
            "memory": self._get_memory_signal(),
            "goals": self._get_goal_signal(),
            "health": self._get_health_signal(),
            "learning": self._get_learning_signal(),
            "timestamp": time.time(),
        }

    # -- Memory Observations ---------------------------------------------------

    def _observe_memory(self) -> list[Observation]:
        """Observe memory trends and consolidation needs."""
        observations: list[Observation] = []

        try:
            signal = self._get_memory_signal()

            if signal.consolidation_needed:
                observations.append(Observation(
                    obs_type=ObservationType.MEMORY_TREND,
                    source="memory",
                    description=f"Memory consolidation needed: {signal.memory_count_24h} new entries in 24h",
                    confidence=0.9,
                    urgency=0.4,
                    value=0.7,
                    data={"entry_count": signal.memory_count_24h},
                ))

            for topic, count in signal.top_topics[:3]:
                observations.append(Observation(
                    obs_type=ObservationType.MEMORY_TREND,
                    source="memory",
                    description=f"Recurring topic '{topic}' ({count} mentions)",
                    confidence=0.85,
                    urgency=0.2,
                    value=0.6,
                    data={"topic": topic, "count": count},
                ))

            for gap in signal.gaps[:3]:
                observations.append(Observation(
                    obs_type=ObservationType.KNOWLEDGE_GAP,
                    source="memory",
                    description=f"Knowledge gap detected: '{gap}'",
                    confidence=0.6,
                    urgency=0.3,
                    value=0.5,
                    data={"gap": gap},
                ))

        except Exception as e:
            logger.warning("Memory observation failed: %s", e)

        return observations

    def _get_memory_signal(self) -> MemorySignal:
        """Analyze memory database for trends."""
        signal = MemorySignal()

        try:
            with sqlite3.connect(self.memory_db_path) as conn:
                conn.row_factory = sqlite3.Row

                # Count entries in last 24h
                day_ago = time.time() - 86400
                row = conn.execute(
                    "SELECT COUNT(*) FROM memory_entries WHERE created_at > ?",
                    (day_ago,),
                ).fetchone()
                signal.memory_count_24h = row[0] if row else 0

                # Top topics (from tags)
                rows = conn.execute(
                    """SELECT tag, COUNT(*) as cnt
                       FROM entry_tags
                       JOIN memory_entries ON entry_tags.entry_id = memory_entries.id
                       WHERE memory_entries.created_at > ?
                       GROUP BY tag
                       ORDER BY cnt DESC
                       LIMIT 5""",
                    (day_ago,),
                ).fetchall()
                signal.top_topics = [(r["tag"], r["cnt"]) for r in rows]

                # Consolidation threshold: >50 entries in 24h
                signal.consolidation_needed = signal.memory_count_24h > 50

                # Recurring queries (simple heuristic: repeated content similarity)
                rows = conn.execute(
                    """SELECT content FROM memory_entries
                       WHERE created_at > ?
                       ORDER BY created_at DESC
                       LIMIT 100""",
                    (day_ago,),
                ).fetchall()
                # Simple word-frequency heuristic for gaps
                all_text = " ".join(r[0] for r in rows if r[0])
                # If we see "how to" or "what is" patterns but few results
                if all_text.count("how to") > 3:
                    signal.gaps.append("procedural knowledge")
                if all_text.count("error") > 5:
                    signal.gaps.append("error handling patterns")

        except Exception as e:
            if "unable to open database file" in str(e).lower():
                logger.debug("Memory signal analysis skipped: %s", e)
            else:
                logger.warning("Memory signal analysis failed: %s", e)

        return signal

    # -- Goal Observations -----------------------------------------------------

    def _observe_goals(self) -> list[Observation]:
        """Observe goal state for stuck or nearly-complete goals."""
        observations: list[Observation] = []

        if not self.goals_db_path:
            return observations

        try:
            signal = self._get_goal_signal()

            for goal in signal.stuck_goals:
                observations.append(Observation(
                    obs_type=ObservationType.GOAL_STUCK,
                    source="goals",
                    description=f"Goal stuck: '{goal.get('title', 'Untitled')}' ({goal.get('idle_hours', 0):.0f}h idle)",
                    confidence=0.8,
                    urgency=0.6,
                    value=0.7,
                    data=goal,
                ))

            for goal in signal.blocked_goals:
                observations.append(Observation(
                    obs_type=ObservationType.GOAL_BLOCKED,
                    source="goals",
                    description=f"Goal blocked: '{goal.get('title', 'Untitled')}' — {goal.get('blocker', 'unknown blocker')}",
                    confidence=0.85,
                    urgency=0.7,
                    value=0.8,
                    data=goal,
                ))

            for goal in signal.nearly_complete:
                observations.append(Observation(
                    obs_type=ObservationType.GOAL_NEARLY_COMPLETE,
                    source="goals",
                    description=f"Goal nearly complete: '{goal.get('title', 'Untitled')}' ({goal.get('progress', 0):.0%})",
                    confidence=0.9,
                    urgency=0.3,
                    value=0.8,
                    data=goal,
                ))

        except Exception as e:
            logger.warning("Goal observation failed: %s", e)

        return observations

    def _get_goal_signal(self) -> GoalSignal:
        """Analyze goals database for actionable signals."""
        signal = GoalSignal()

        if not self.goals_db_path:
            return signal

        try:
            with sqlite3.connect(self.goals_db_path) as conn:
                conn.row_factory = sqlite3.Row

                # Total and active counts
                row = conn.execute(
                    "SELECT COUNT(*) FROM goals WHERE status != 'cancelled' AND status != 'failed'"
                ).fetchone()
                signal.total_count = row[0] if row else 0

                row = conn.execute(
                    "SELECT COUNT(*) FROM goals WHERE status IN ('active', 'in_progress')"
                ).fetchone()
                signal.active_count = row[0] if row else 0

                # Stuck goals: active but no update in 24h
                day_ago = time.time() - 86400
                rows = conn.execute(
                    """SELECT id, title, status, updated_at,
                              (SELECT COUNT(*) FROM goals WHERE parent_id = g.id) as children
                       FROM goals g
                       WHERE status IN ('active', 'in_progress')
                         AND updated_at < ?
                       ORDER BY updated_at ASC
                       LIMIT 5""",
                    (day_ago,),
                ).fetchall()
                for r in rows:
                    idle_hours = (time.time() - r["updated_at"]) / 3600
                    signal.stuck_goals.append({
                        "id": r["id"],
                        "title": r["title"],
                        "status": r["status"],
                        "idle_hours": idle_hours,
                        "children": r["children"],
                    })

                # Blocked goals
                rows = conn.execute(
                    """SELECT id, title, status, metadata
                       FROM goals
                       WHERE status = 'blocked'
                       ORDER BY updated_at DESC
                       LIMIT 5"""
                ).fetchall()
                for r in rows:
                    meta = json.loads(r["metadata"] or "{}")
                    signal.blocked_goals.append({
                        "id": r["id"],
                        "title": r["title"],
                        "status": r["status"],
                        "blocker": meta.get("blocker", "unknown"),
                        "metadata": meta,
                    })

                # Nearly complete goals
                rows = conn.execute(
                    """SELECT id, title, status, metadata
                       FROM goals
                       WHERE status IN ('active', 'in_progress')
                       ORDER BY updated_at DESC"""
                ).fetchall()
                for r in rows:
                    meta = json.loads(r["metadata"] or "{}")
                    progress = meta.get("progress", 0)
                    if progress >= 0.8:
                        signal.nearly_complete.append({
                            "id": r["id"],
                            "title": r["title"],
                            "progress": progress,
                            "metadata": meta,
                        })

        except Exception as e:
            logger.warning("Goal signal analysis failed: %s", e)

        return signal

    # -- System Health Observations -------------------------------------------

    def _observe_system_health(self) -> list[Observation]:
        """Observe system health for anomalies."""
        observations: list[Observation] = []

        try:
            signal = self._get_health_signal()

            if signal.failed_operations_24h > 10:
                observations.append(Observation(
                    obs_type=ObservationType.SYSTEM_HEALTH,
                    source="health",
                    description=f"High failure rate: {signal.failed_operations_24h} failed operations in 24h",
                    confidence=0.9,
                    urgency=0.8,
                    value=0.9,
                    data={"failed_count": signal.failed_operations_24h},
                ))

            for cb in signal.circuit_breakers_tripped:
                observations.append(Observation(
                    obs_type=ObservationType.SYSTEM_HEALTH,
                    source="health",
                    description=f"Circuit breaker tripped: {cb}",
                    confidence=0.95,
                    urgency=0.7,
                    value=0.8,
                    data={"circuit_breaker": cb},
                ))

            if signal.rate_limits_hit > 5:
                observations.append(Observation(
                    obs_type=ObservationType.SELF_IMPROVEMENT,
                    source="health",
                    description=f"Rate limit pattern detected: {signal.rate_limits_hit} hits in 24h",
                    confidence=0.8,
                    urgency=0.5,
                    value=0.7,
                    data={"rate_limit_hits": signal.rate_limits_hit},
                ))

        except Exception as e:
            logger.warning("Health observation failed: %s", e)

        return observations

    def _get_health_signal(self) -> HealthSignal:
        """Analyze health/audit database."""
        signal = HealthSignal()

        if not self.system_db_path:
            return signal

        try:
            with sqlite3.connect(self.system_db_path) as conn:
                conn.row_factory = sqlite3.Row

                day_ago = time.time() - 86400

                # Failed operations
                row = conn.execute(
                    """SELECT COUNT(*) FROM audit_log
                       WHERE level = 'error' AND timestamp > ?""",
                    (day_ago,),
                ).fetchone()
                signal.failed_operations_24h = row[0] if row else 0

                # Circuit breakers
                rows = conn.execute(
                    """SELECT DISTINCT component FROM audit_log
                       WHERE message LIKE '%circuit breaker%' AND timestamp > ?""",
                    (day_ago,),
                ).fetchall()
                signal.circuit_breakers_tripped = [r[0] for r in rows]

                # Rate limits
                row = conn.execute(
                    """SELECT COUNT(*) FROM audit_log
                       WHERE message LIKE '%rate limit%' AND timestamp > ?""",
                    (day_ago,),
                ).fetchone()
                signal.rate_limits_hit = row[0] if row else 0

                # Slow operations
                rows = conn.execute(
                    """SELECT component, AVG(duration_ms) as avg_dur
                       FROM audit_log
                       WHERE timestamp > ? AND duration_ms > 5000
                       GROUP BY component
                       ORDER BY avg_dur DESC
                       LIMIT 5""",
                    (day_ago,),
                ).fetchall()
                signal.slow_operations = [
                    {"component": r["component"], "avg_duration_ms": r["avg_dur"]}
                    for r in rows
                ]

        except Exception as e:
            logger.warning("Health signal analysis failed: %s", e)

        return signal

    # -- Learning Observations -------------------------------------------------

    def _observe_learning_opportunities(self) -> list[Observation]:
        """Observe for self-improvement opportunities."""
        observations: list[Observation] = []

        try:
            signal = self._get_learning_signal()

            for pattern in signal.repeated_patterns:
                observations.append(Observation(
                    obs_type=ObservationType.LEARNING_OPPORTUNITY,
                    source="learning",
                    description=f"Repeated pattern: {pattern.get('description', 'unknown')}",
                    confidence=pattern.get("confidence", 0.5),
                    urgency=0.2,
                    value=0.7,
                    data=pattern,
                ))

            for gap in signal.skill_gaps:
                observations.append(Observation(
                    obs_type=ObservationType.LEARNING_OPPORTUNITY,
                    source="learning",
                    description=f"Skill gap: {gap}",
                    confidence=0.6,
                    urgency=0.1,
                    value=0.6,
                    data={"skill_gap": gap},
                ))

        except Exception as e:
            logger.warning("Learning observation failed: %s", e)

        return observations

    def _get_learning_signal(self) -> LearningSignal:
        """Analyze for learning opportunities."""
        signal = LearningSignal()

        try:
            with sqlite3.connect(self.memory_db_path) as conn:
                conn.row_factory = sqlite3.Row

                week_ago = time.time() - 604800

                # Repeated queries (same query pattern >3 times)
                rows = conn.execute(
                    """SELECT content, COUNT(*) as cnt
                       FROM memory_entries
                       WHERE created_at > ? AND role = 'user'
                       GROUP BY content
                       HAVING cnt > 3
                       ORDER BY cnt DESC
                       LIMIT 5""",
                    (week_ago,),
                ).fetchall()
                for r in rows:
                    signal.repeated_patterns.append({
                        "description": f"Query repeated {r['cnt']} times: {r['content'][:60]}...",
                        "confidence": min(0.5 + r["cnt"] * 0.05, 0.95),
                        "count": r["cnt"],
                    })

                # Tool usage inefficiency: same tool combo repeated
                rows = conn.execute(
                    """SELECT tags, COUNT(*) as cnt
                       FROM memory_entries
                       WHERE created_at > ? AND role = 'tool'
                       GROUP BY tags
                       HAVING cnt > 5
                       ORDER BY cnt DESC
                       LIMIT 3""",
                    (week_ago,),
                ).fetchall()
                for r in rows:
                    signal.tool_usage_inefficiencies.append(
                        f"Tool pattern used {r['cnt']} times: {r['tags']}"
                    )

        except Exception as e:
            if "unable to open database file" in str(e).lower():
                logger.debug("Learning signal analysis skipped: %s", e)
            else:
                logger.warning("Learning signal analysis failed: %s", e)

        return signal

    # -- Scheduled Task Observations ------------------------------------------

    def _observe_scheduled_tasks(self) -> list[Observation]:
        """Observe for overdue scheduled tasks."""
        observations: list[Observation] = []

        # This requires cron scheduler integration; simplified here
        # In full implementation, would query CronScheduler's DB

        return observations

    # -- Research Opportunity Observations -------------------------------------

    def _observe_research_opportunities(self) -> list[Observation]:
        """Observe for topics that would benefit from autonomous research.

        Detects knowledge gaps where the user has asked questions but
        no comprehensive research exists in memory.
        """
        observations: list[Observation] = []

        try:
            with sqlite3.connect(self.memory_db_path) as conn:
                conn.row_factory = sqlite3.Row

                week_ago = time.time() - 604800

                # Find question patterns (how/what/why/when) with no research tag
                rows = conn.execute(
                    """SELECT content, COUNT(*) as cnt
                       FROM memory_entries
                       WHERE created_at > ?
                         AND role = 'user'
                         AND (content LIKE '%how%' OR content LIKE '%what%'
                              OR content LIKE '%why%' OR content LIKE '%when%'
                              OR content LIKE '%latest%' OR content LIKE '%news%')
                         AND content NOT IN (
                             SELECT content FROM memory_entries
                             WHERE role = 'research'
                         )
                       GROUP BY content
                       HAVING cnt >= 2
                       ORDER BY cnt DESC
                       LIMIT 3""",
                    (week_ago,),
                ).fetchall()

                for r in rows:
                    topic = r["content"][:100]
                    observations.append(Observation(
                        obs_type=ObservationType.KNOWLEDGE_GAP,
                        source="research",
                        description=f"Research opportunity: '{topic}' (asked {r['cnt']} times)",
                        confidence=0.7,
                        urgency=0.3,
                        value=0.6,
                        data={"topic": topic, "query_count": r["cnt"]},
                    ))

        except Exception as e:
            if "unable to open database file" in str(e).lower():
                logger.debug("Research opportunity observation skipped: %s", e)
            else:
                logger.warning("Research opportunity observation failed: %s", e)

        return observations
