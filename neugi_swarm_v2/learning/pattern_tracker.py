"""
NEUGI v2 Pattern Tracker
=========================

Tracks and detects recurring patterns in task execution, tool usage,
skill invocation, and agent performance. Uses SQLite for persistent
storage with graceful degradation on errors.

Usage:
    tracker = PatternTracker("/path/to/learning.db")
    tracker.record_task_pattern("code_review", success=True, duration_ms=5000)
    tracker.record_tool_pattern("file_search", success=True, duration_ms=150)

    patterns = tracker.get_top_patterns(limit=10)
    detections = tracker.detect_repeated_sequences(min_occurrences=3)
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# -- Enums -------------------------------------------------------------------

class PatternType(Enum):
    """Categories of patterns that can be tracked."""
    TASK = "task"
    TOOL = "tool"
    SKILL = "skill"
    AGENT = "agent"
    SEQUENCE = "sequence"


class PatternScore:
    """Scoring utilities for pattern usefulness.

    Scores range from 0.0 (useless) to 1.0 (highly valuable).
    """

    @staticmethod
    def compute(
        frequency: int,
        success_rate: float,
        avg_duration_ms: float,
        recency_days: float,
        max_frequency: int = 100,
        max_duration_ms: float = 60000.0,
    ) -> float:
        """Compute a composite usefulness score for a pattern.

        Args:
            frequency: How many times the pattern occurred.
            success_rate: Fraction of successful executions (0.0-1.0).
            avg_duration_ms: Average execution time in milliseconds.
            recency_days: Days since last occurrence.
            max_frequency: Frequency cap for normalization.
            max_duration_ms: Duration cap for normalization.

        Returns:
            Score between 0.0 and 1.0.
        """
        freq_score = min(frequency / max_frequency, 1.0)
        success_score = success_rate
        speed_score = max(0.0, 1.0 - (avg_duration_ms / max_duration_ms))
        recency_score = max(0.0, 1.0 - (recency_days / 30.0))

        weights = {
            "frequency": 0.25,
            "success": 0.35,
            "speed": 0.15,
            "recency": 0.25,
        }

        return (
            weights["frequency"] * freq_score
            + weights["success"] * success_score
            + weights["speed"] * speed_score
            + weights["recency"] * recency_score
        )


# -- Data Classes ------------------------------------------------------------

@dataclass
class PatternRecord:
    """A single recorded pattern occurrence.

    Attributes:
        id: Unique identifier (auto-assigned by DB).
        pattern_type: Category of the pattern.
        name: Identifier for the pattern (task name, tool name, etc.).
        success: Whether this execution succeeded.
        duration_ms: Execution time in milliseconds.
        metadata: Additional context as a JSON-serializable dict.
        timestamp: When the pattern was recorded (UTC).
    """
    pattern_type: PatternType
    name: str
    success: bool
    duration_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)
    id: Optional[int] = None
    timestamp: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary."""
        return {
            "id": self.id,
            "pattern_type": self.pattern_type.value,
            "name": self.name,
            "success": self.success,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


@dataclass
class PatternSequence:
    """A recorded sequence of actions.

    Attributes:
        id: Unique identifier (auto-assigned by DB).
        actions: Ordered list of action names.
        success: Whether the full sequence succeeded.
        occurrence_count: How many times this exact sequence has been seen.
        first_seen: First occurrence timestamp (UTC).
        last_seen: Most recent occurrence timestamp (UTC).
    """
    actions: list[str]
    success: bool
    id: Optional[int] = None
    occurrence_count: int = 1
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None

    @property
    def signature(self) -> str:
        """Canonical string representation of the sequence."""
        return " -> ".join(self.actions)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary."""
        return {
            "id": self.id,
            "actions": self.actions,
            "success": self.success,
            "occurrence_count": self.occurrence_count,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "signature": self.signature,
        }


@dataclass
class PatternDetectionResult:
    """Result of pattern detection analysis.

    Attributes:
        pattern_name: Detected pattern identifier.
        pattern_type: Category of the pattern.
        occurrence_count: Total times observed.
        success_count: Times it succeeded.
        success_rate: Fraction of successful executions.
        avg_duration_ms: Mean execution time.
        score: Usefulness score (0.0-1.0).
        first_seen: First observation timestamp.
        last_seen: Most recent observation timestamp.
        metadata_aggregate: Merged metadata from all occurrences.
    """
    pattern_name: str
    pattern_type: PatternType
    occurrence_count: int
    success_count: int
    success_rate: float
    avg_duration_ms: float
    score: float
    first_seen: datetime
    last_seen: datetime
    metadata_aggregate: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary."""
        return {
            "pattern_name": self.pattern_name,
            "pattern_type": self.pattern_type.value,
            "occurrence_count": self.occurrence_count,
            "success_count": self.success_count,
            "success_rate": round(self.success_rate, 4),
            "avg_duration_ms": round(self.avg_duration_ms, 2),
            "score": round(self.score, 4),
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "metadata_aggregate": self.metadata_aggregate,
        }


# -- Pattern Tracker ---------------------------------------------------------

class PatternTracker:
    """Tracks and detects recurring patterns in agent behavior.

    Records task executions, tool calls, skill invocations, and agent
    performance. Detects repeated action sequences and scores patterns
    by usefulness.

    All data is persisted in SQLite with graceful degradation on errors.

    Usage:
        tracker = PatternTracker("/path/to/learning.db")
        tracker.record_task_pattern("deploy", success=True, duration_ms=30000)
        top = tracker.get_top_patterns(limit=5)
    """

    def __init__(self, db_path: str) -> None:
        """Initialize the pattern tracker.

        Args:
            db_path: Path to the SQLite database file.
        """
        self._db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get a database connection with row factory.

        Returns:
            Configured sqlite3 connection.
        """
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self) -> None:
        """Create database tables if they don't exist."""
        try:
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
            with self._get_conn() as conn:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS pattern_records (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        pattern_type TEXT NOT NULL,
                        name TEXT NOT NULL,
                        success INTEGER NOT NULL,
                        duration_ms REAL NOT NULL,
                        metadata TEXT DEFAULT '{}',
                        timestamp TEXT NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS idx_pattern_type
                        ON pattern_records(pattern_type);
                    CREATE INDEX IF NOT EXISTS idx_pattern_name
                        ON pattern_records(name);
                    CREATE INDEX IF NOT EXISTS idx_pattern_timestamp
                        ON pattern_records(timestamp);
                    CREATE INDEX IF NOT EXISTS idx_pattern_type_name
                        ON pattern_records(pattern_type, name);

                    CREATE TABLE IF NOT EXISTS pattern_sequences (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        actions TEXT NOT NULL,
                        success INTEGER NOT NULL,
                        occurrence_count INTEGER DEFAULT 1,
                        first_seen TEXT NOT NULL,
                        last_seen TEXT NOT NULL
                    );

                    CREATE UNIQUE INDEX IF NOT EXISTS idx_sequence_actions
                        ON pattern_sequences(actions);
                """)
        except OSError as e:
            logger.error("Failed to initialize pattern tracker DB: %s", e)

    def record_task_pattern(
        self,
        task_name: str,
        success: bool,
        duration_ms: float,
        metadata: dict[str, Any] | None = None,
    ) -> PatternRecord:
        """Record a task execution pattern.

        Args:
            task_name: Name/identifier of the task.
            success: Whether the task succeeded.
            duration_ms: Execution time in milliseconds.
            metadata: Optional additional context.

        Returns:
            The created PatternRecord.
        """
        return self._record_pattern(
            PatternType.TASK, task_name, success, duration_ms, metadata
        )

    def record_tool_pattern(
        self,
        tool_name: str,
        success: bool,
        duration_ms: float,
        metadata: dict[str, Any] | None = None,
    ) -> PatternRecord:
        """Record a tool usage pattern.

        Args:
            tool_name: Name of the tool.
            success: Whether the tool call succeeded.
            duration_ms: Execution time in milliseconds.
            metadata: Optional additional context.

        Returns:
            The created PatternRecord.
        """
        return self._record_pattern(
            PatternType.TOOL, tool_name, success, duration_ms, metadata
        )

    def record_skill_pattern(
        self,
        skill_name: str,
        success: bool,
        duration_ms: float,
        metadata: dict[str, Any] | None = None,
    ) -> PatternRecord:
        """Record a skill usage pattern.

        Args:
            skill_name: Name of the skill.
            success: Whether the skill execution succeeded.
            duration_ms: Execution time in milliseconds.
            metadata: Optional additional context.

        Returns:
            The created PatternRecord.
        """
        return self._record_pattern(
            PatternType.SKILL, skill_name, success, duration_ms, metadata
        )

    def record_agent_pattern(
        self,
        agent_name: str,
        success: bool,
        duration_ms: float,
        metadata: dict[str, Any] | None = None,
    ) -> PatternRecord:
        """Record an agent performance pattern.

        Args:
            agent_name: Name of the agent.
            success: Whether the agent task succeeded.
            duration_ms: Execution time in milliseconds.
            metadata: Optional additional context.

        Returns:
            The created PatternRecord.
        """
        return self._record_pattern(
            PatternType.AGENT, agent_name, success, duration_ms, metadata
        )

    def _record_pattern(
        self,
        pattern_type: PatternType,
        name: str,
        success: bool,
        duration_ms: float,
        metadata: dict[str, Any] | None = None,
    ) -> PatternRecord:
        """Record a pattern occurrence in the database.

        Args:
            pattern_type: Category of the pattern.
            name: Identifier for the pattern.
            success: Whether this execution succeeded.
            duration_ms: Execution time in milliseconds.
            metadata: Optional additional context.

        Returns:
            The created PatternRecord.
        """
        now = datetime.now(timezone.utc)
        record = PatternRecord(
            pattern_type=pattern_type,
            name=name,
            success=success,
            duration_ms=duration_ms,
            metadata=metadata or {},
            timestamp=now,
        )

        try:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO pattern_records
                        (pattern_type, name, success, duration_ms, metadata, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        pattern_type.value,
                        name,
                        1 if success else 0,
                        duration_ms,
                        json.dumps(record.metadata),
                        now.isoformat(),
                    ),
                )
                record.id = cursor.lastrowid
        except (sqlite3.Error, OSError) as e:
            logger.error("Failed to record pattern: %s", e)

        return record

    def record_sequence(
        self,
        actions: list[str],
        success: bool,
    ) -> PatternSequence:
        """Record an action sequence occurrence.

        Upserts the sequence: increments occurrence_count if the exact
        sequence already exists, otherwise creates a new record.

        Args:
            actions: Ordered list of action names.
            success: Whether the sequence completed successfully.

        Returns:
            The PatternSequence (new or updated).
        """
        now = datetime.now(timezone.utc)
        signature = " -> ".join(actions)
        seq = PatternSequence(
            actions=actions,
            success=success,
            first_seen=now,
            last_seen=now,
        )

        try:
            with self._get_conn() as conn:
                existing = conn.execute(
                    "SELECT id, occurrence_count, first_seen, success FROM pattern_sequences WHERE actions = ?",
                    (signature,),
                ).fetchone()

                if existing:
                    new_count = existing["occurrence_count"] + 1
                    conn.execute(
                        """
                        UPDATE pattern_sequences
                        SET occurrence_count = ?, last_seen = ?, success = ?
                        WHERE id = ?
                        """,
                        (new_count, now.isoformat(), 1 if success else 0, existing["id"]),
                    )
                    seq.id = existing["id"]
                    seq.occurrence_count = new_count
                    seq.first_seen = datetime.fromisoformat(existing["first_seen"])
                else:
                    cursor = conn.execute(
                        """
                        INSERT INTO pattern_sequences
                            (actions, success, occurrence_count, first_seen, last_seen)
                        VALUES (?, ?, 1, ?, ?)
                        """,
                        (signature, 1 if success else 0, now.isoformat(), now.isoformat()),
                    )
                    seq.id = cursor.lastrowid
        except (sqlite3.Error, OSError) as e:
            logger.error("Failed to record sequence: %s", e)

        return seq

    def get_pattern_stats(
        self,
        pattern_type: PatternType,
        name: str,
    ) -> Optional[PatternDetectionResult]:
        """Get aggregated statistics for a specific pattern.

        Args:
            pattern_type: Category of the pattern.
            name: Identifier for the pattern.

        Returns:
            PatternDetectionResult or None if no data exists.
        """
        try:
            with self._get_conn() as conn:
                row = conn.execute(
                    """
                    SELECT
                        COUNT(*) as occurrence_count,
                        SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success_count,
                        AVG(duration_ms) as avg_duration_ms,
                        MIN(timestamp) as first_seen,
                        MAX(timestamp) as last_seen
                    FROM pattern_records
                    WHERE pattern_type = ? AND name = ?
                    """,
                    (pattern_type.value, name),
                ).fetchone()

                if not row or row["occurrence_count"] == 0:
                    return None

                occurrence_count = row["occurrence_count"]
                success_count = row["success_count"]
                avg_duration_ms = row["avg_duration_ms"]
                first_seen = datetime.fromisoformat(row["first_seen"])
                last_seen = datetime.fromisoformat(row["last_seen"])
                success_rate = success_count / occurrence_count if occurrence_count > 0 else 0.0

                recency_days = (datetime.now(timezone.utc) - last_seen).total_seconds() / 86400.0
                score = PatternScore.compute(
                    frequency=occurrence_count,
                    success_rate=success_rate,
                    avg_duration_ms=avg_duration_ms,
                    recency_days=recency_days,
                )

                return PatternDetectionResult(
                    pattern_name=name,
                    pattern_type=pattern_type,
                    occurrence_count=occurrence_count,
                    success_count=success_count,
                    success_rate=success_rate,
                    avg_duration_ms=avg_duration_ms,
                    score=score,
                    first_seen=first_seen,
                    last_seen=last_seen,
                )
        except (sqlite3.Error, OSError) as e:
            logger.error("Failed to get pattern stats for %s/%s: %s", pattern_type.value, name, e)
            return None

    def get_top_patterns(
        self,
        pattern_type: Optional[PatternType] = None,
        limit: int = 20,
        min_occurrences: int = 1,
    ) -> list[PatternDetectionResult]:
        """Get the highest-scoring patterns.

        Args:
            pattern_type: Filter by type, or None for all types.
            limit: Maximum number of results.
            min_occurrences: Minimum occurrences to include.

        Returns:
            List of PatternDetectionResult sorted by score descending.
        """
        try:
            with self._get_conn() as conn:
                type_filter = "WHERE pattern_type = ?" if pattern_type else ""
                params: list[Any] = [min_occurrences]
                if pattern_type:
                    params.insert(0, pattern_type.value)

                query = f"""
                    SELECT
                        name,
                        pattern_type,
                        COUNT(*) as occurrence_count,
                        SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success_count,
                        AVG(duration_ms) as avg_duration_ms,
                        MIN(timestamp) as first_seen,
                        MAX(timestamp) as last_seen
                    FROM pattern_records
                    {type_filter}
                    GROUP BY pattern_type, name
                    HAVING COUNT(*) >= ?
                    ORDER BY occurrence_count DESC
                    LIMIT ?
                """
                params.append(limit)

                rows = conn.execute(query, params).fetchall()
                results = []
                now = datetime.now(timezone.utc)

                for row in rows:
                    occurrence_count = row["occurrence_count"]
                    success_count = row["success_count"]
                    avg_duration_ms = row["avg_duration_ms"]
                    first_seen = datetime.fromisoformat(row["first_seen"])
                    last_seen = datetime.fromisoformat(row["last_seen"])
                    success_rate = success_count / occurrence_count if occurrence_count > 0 else 0.0
                    recency_days = (now - last_seen).total_seconds() / 86400.0
                    score = PatternScore.compute(
                        frequency=occurrence_count,
                        success_rate=success_rate,
                        avg_duration_ms=avg_duration_ms,
                        recency_days=recency_days,
                    )

                    results.append(PatternDetectionResult(
                        pattern_name=row["name"],
                        pattern_type=PatternType(row["pattern_type"]),
                        occurrence_count=occurrence_count,
                        success_count=success_count,
                        success_rate=success_rate,
                        avg_duration_ms=avg_duration_ms,
                        score=score,
                        first_seen=first_seen,
                        last_seen=last_seen,
                    ))

                results.sort(key=lambda r: r.score, reverse=True)
                return results
        except (sqlite3.Error, OSError) as e:
            logger.error("Failed to get top patterns: %s", e)
            return []

    def detect_repeated_sequences(
        self,
        min_occurrences: int = 3,
        min_success_rate: float = 0.5,
    ) -> list[PatternSequence]:
        """Detect action sequences that occur repeatedly.

        Args:
            min_occurrences: Minimum times a sequence must appear.
            min_success_rate: Minimum success rate to include.

        Returns:
            List of PatternSequence objects meeting the criteria.
        """
        try:
            with self._get_conn() as conn:
                rows = conn.execute(
                    """
                    SELECT id, actions, success, occurrence_count, first_seen, last_seen
                    FROM pattern_sequences
                    WHERE occurrence_count >= ?
                    ORDER BY occurrence_count DESC
                    """,
                    (min_occurrences,),
                ).fetchall()

                results = []
                for row in rows:
                    seq = PatternSequence(
                        actions=row["actions"].split(" -> "),
                        success=bool(row["success"]),
                        id=row["id"],
                        occurrence_count=row["occurrence_count"],
                        first_seen=datetime.fromisoformat(row["first_seen"]),
                        last_seen=datetime.fromisoformat(row["last_seen"]),
                    )

                    if seq.occurrence_count >= min_occurrences:
                        results.append(seq)

                return results
        except (sqlite3.Error, OSError) as e:
            logger.error("Failed to detect repeated sequences: %s", e)
            return []

    def get_success_rate_trend(
        self,
        pattern_type: PatternType,
        name: str,
        window_days: int = 7,
    ) -> list[dict[str, Any]]:
        """Get daily success rate trend for a pattern.

        Args:
            pattern_type: Category of the pattern.
            name: Identifier for the pattern.
            window_days: Number of days to look back.

        Returns:
            List of dicts with 'date', 'count', 'success_count', 'rate'.
        """
        try:
            with self._get_conn() as conn:
                rows = conn.execute(
                    """
                    SELECT
                        DATE(timestamp) as date,
                        COUNT(*) as count,
                        SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success_count
                    FROM pattern_records
                    WHERE pattern_type = ?
                      AND name = ?
                      AND timestamp >= datetime('now', ?)
                    GROUP BY DATE(timestamp)
                    ORDER BY date DESC
                    """,
                    (pattern_type.value, name, f"-{window_days} days"),
                ).fetchall()

                return [
                    {
                        "date": row["date"],
                        "count": row["count"],
                        "success_count": row["success_count"],
                        "rate": row["success_count"] / row["count"] if row["count"] > 0 else 0.0,
                    }
                    for row in rows
                ]
        except (sqlite3.Error, OSError) as e:
            logger.error("Failed to get success rate trend: %s", e)
            return []

    def get_patterns_by_time_range(
        self,
        pattern_type: PatternType,
        start: datetime,
        end: datetime,
    ) -> list[PatternRecord]:
        """Get all pattern records within a time range.

        Args:
            pattern_type: Category of the pattern.
            start: Start of the time range (UTC).
            end: End of the time range (UTC).

        Returns:
            List of PatternRecord objects.
        """
        try:
            with self._get_conn() as conn:
                rows = conn.execute(
                    """
                    SELECT id, pattern_type, name, success, duration_ms, metadata, timestamp
                    FROM pattern_records
                    WHERE pattern_type = ?
                      AND timestamp >= ?
                      AND timestamp <= ?
                    ORDER BY timestamp ASC
                    """,
                    (pattern_type.value, start.isoformat(), end.isoformat()),
                ).fetchall()

                return [
                    PatternRecord(
                        id=row["id"],
                        pattern_type=PatternType(row["pattern_type"]),
                        name=row["name"],
                        success=bool(row["success"]),
                        duration_ms=row["duration_ms"],
                        metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                        timestamp=datetime.fromisoformat(row["timestamp"]),
                    )
                    for row in rows
                ]
        except (sqlite3.Error, OSError) as e:
            logger.error("Failed to get patterns by time range: %s", e)
            return []

    def delete_old_records(self, older_than_days: int = 90) -> int:
        """Delete pattern records older than a threshold.

        Args:
            older_than_days: Delete records older than this many days.

        Returns:
            Number of records deleted.
        """
        try:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    "DELETE FROM pattern_records WHERE timestamp < datetime('now', ?)",
                    (f"-{older_than_days} days",),
                )
                return cursor.rowcount
        except (sqlite3.Error, OSError) as e:
            logger.error("Failed to delete old records: %s", e)
            return 0

    def close(self) -> None:
        """No-op for API compatibility. SQLite connections are short-lived."""
        pass
