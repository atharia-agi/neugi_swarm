"""
NEUGI v2 Feedback Loop
=======================

Collects implicit and explicit user feedback, tracks success/failure
rates over time, identifies degradation patterns, and auto-tunes
system parameters based on observed performance.

Usage:
    loop = FeedbackLoop("/path/to/learning.db")
    loop.record_feedback("skill:git-workflow", rating=5, comment="Great!")
    loop.record_implicit_feedback("tool:file_search", success=True, duration_ms=150)

    summary = loop.get_feedback_summary()
    recommendations = loop.get_tuning_recommendations()
    alerts = loop.check_degradation()
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# -- Enums -------------------------------------------------------------------

class FeedbackType(Enum):
    """Types of feedback that can be recorded."""
    EXPLICIT = "explicit"
    IMPLICIT = "implicit"
    AUTOMATED = "automated"


# -- Data Classes ------------------------------------------------------------

@dataclass
class FeedbackEntry:
    """A single feedback record.

    Attributes:
        id: Unique identifier (auto-assigned by DB).
        target: What the feedback is about (e.g. 'skill:git-workflow').
        rating: Numeric rating (1.0-5.0).
        feedback_type: How the feedback was collected.
        comment: Optional free-text feedback.
        timestamp: When the feedback was recorded (UTC).
        metadata: Additional context.
    """
    target: str
    rating: float
    feedback_type: FeedbackType
    comment: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    id: Optional[int] = None
    timestamp: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary."""
        return {
            "id": self.id,
            "target": self.target,
            "rating": self.rating,
            "feedback_type": self.feedback_type.value,
            "comment": self.comment,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "metadata": self.metadata,
        }


@dataclass
class FeedbackSummary:
    """Aggregated feedback statistics.

    Attributes:
        target: The feedback target.
        total_count: Total feedback entries.
        avg_rating: Mean rating.
        explicit_count: Number of explicit feedback entries.
        implicit_count: Number of implicit feedback entries.
        recent_avg: Average rating from the last 7 days.
        trend: 'improving', 'stable', or 'degrading'.
    """
    target: str
    total_count: int
    avg_rating: float
    explicit_count: int
    implicit_count: int
    recent_avg: float
    trend: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary."""
        return {
            "target": self.target,
            "total_count": self.total_count,
            "avg_rating": round(self.avg_rating, 4),
            "explicit_count": self.explicit_count,
            "implicit_count": self.implicit_count,
            "recent_avg": round(self.recent_avg, 4),
            "trend": self.trend,
        }


@dataclass
class TuningRecommendation:
    """A parameter tuning recommendation.

    Attributes:
        parameter: The parameter to adjust.
        current_value: Current value.
        recommended_value: Suggested new value.
        reason: Why the change is recommended.
        confidence: How confident the system is (0.0-1.0).
        impact: Expected impact ('low', 'medium', 'high').
    """
    parameter: str
    current_value: Any
    recommended_value: Any
    reason: str
    confidence: float
    impact: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary."""
        return {
            "parameter": self.parameter,
            "current_value": self.current_value,
            "recommended_value": self.recommended_value,
            "reason": self.reason,
            "confidence": round(self.confidence, 4),
            "impact": self.impact,
        }


@dataclass
class DegradationAlert:
    """Alert about performance degradation.

    Attributes:
        target: What is degrading.
        severity: 'warning' or 'critical'.
        current_rate: Current success/performance rate.
        baseline_rate: Historical baseline rate.
        drop_percentage: How much performance dropped.
        detected_at: When the degradation was detected (UTC).
        recommendation: Suggested action.
    """
    target: str
    severity: str
    current_rate: float
    baseline_rate: float
    drop_percentage: float
    detected_at: datetime
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary."""
        return {
            "target": self.target,
            "severity": self.severity,
            "current_rate": round(self.current_rate, 4),
            "baseline_rate": round(self.baseline_rate, 4),
            "drop_percentage": round(self.drop_percentage, 2),
            "detected_at": self.detected_at.isoformat(),
            "recommendation": self.recommendation,
        }


# -- Feedback Loop -----------------------------------------------------------

class FeedbackLoop:
    """Manages the performance feedback lifecycle.

    Collects explicit user ratings and implicit performance signals,
    aggregates them into summaries, detects degradation patterns,
    and generates parameter tuning recommendations.

    All data is persisted in SQLite with graceful degradation on errors.

    Usage:
        loop = FeedbackLoop("/path/to/learning.db")
        loop.record_feedback("task:deploy", rating=4, comment="Fast")
        summary = loop.get_feedback_summary("task:deploy")
    """

    def __init__(self, db_path: str) -> None:
        """Initialize the feedback loop.

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
        return conn

    def _init_db(self) -> None:
        """Create database tables if they don't exist."""
        try:
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
            with self._get_conn() as conn:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS feedback_entries (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        target TEXT NOT NULL,
                        rating REAL NOT NULL,
                        feedback_type TEXT NOT NULL,
                        comment TEXT DEFAULT '',
                        timestamp TEXT NOT NULL,
                        metadata TEXT DEFAULT '{}'
                    );

                    CREATE INDEX IF NOT EXISTS idx_feedback_target
                        ON feedback_entries(target);
                    CREATE INDEX IF NOT EXISTS idx_feedback_timestamp
                        ON feedback_entries(timestamp);
                    CREATE INDEX IF NOT EXISTS idx_feedback_type
                        ON feedback_entries(feedback_type);

                    CREATE TABLE IF NOT EXISTS performance_snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        target TEXT NOT NULL,
                        metric TEXT NOT NULL,
                        value REAL NOT NULL,
                        timestamp TEXT NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS idx_perf_target
                        ON performance_snapshots(target);
                    CREATE INDEX IF NOT EXISTS idx_perf_timestamp
                        ON performance_snapshots(timestamp);

                    CREATE TABLE IF NOT EXISTS tuning_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        parameter TEXT NOT NULL,
                        old_value TEXT NOT NULL,
                        new_value TEXT NOT NULL,
                        reason TEXT DEFAULT '',
                        timestamp TEXT NOT NULL
                    );
                """)
        except OSError as e:
            logger.error("Failed to initialize feedback loop DB: %s", e)

    def record_feedback(
        self,
        target: str,
        rating: float,
        feedback_type: str = "explicit",
        comment: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> FeedbackEntry:
        """Record a feedback entry.

        Args:
            target: What the feedback is about (e.g. 'skill:git-workflow').
            rating: Numeric rating (1.0-5.0).
            feedback_type: 'explicit', 'implicit', or 'automated'.
            comment: Optional free-text feedback.
            metadata: Optional additional context.

        Returns:
            The created FeedbackEntry.
        """
        rating = max(1.0, min(5.0, rating))
        now = datetime.now(timezone.utc)

        try:
            ft = FeedbackType(feedback_type)
        except ValueError:
            ft = FeedbackType.EXPLICIT

        entry = FeedbackEntry(
            target=target,
            rating=rating,
            feedback_type=ft,
            comment=comment,
            metadata=metadata or {},
            timestamp=now,
        )

        try:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO feedback_entries
                        (target, rating, feedback_type, comment, timestamp, metadata)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        target,
                        rating,
                        ft.value,
                        comment,
                        now.isoformat(),
                        json.dumps(entry.metadata),
                    ),
                )
                entry.id = cursor.lastrowid
        except (sqlite3.Error, OSError) as e:
            logger.error("Failed to record feedback: %s", e)

        return entry

    def record_implicit_feedback(
        self,
        target: str,
        success: bool,
        duration_ms: float,
        metadata: dict[str, Any] | None = None,
    ) -> FeedbackEntry:
        """Record implicit feedback from a tool/task execution.

        Converts success/failure and duration into a 1-5 rating:
        - Success + fast (<1s): 5
        - Success + moderate (<5s): 4
        - Success + slow (<30s): 3
        - Failure: 1-2 based on duration

        Args:
            target: What was executed.
            success: Whether it succeeded.
            duration_ms: Execution time in milliseconds.
            metadata: Optional additional context.

        Returns:
            The created FeedbackEntry.
        """
        if success:
            if duration_ms < 1000:
                rating = 5.0
            elif duration_ms < 5000:
                rating = 4.0
            elif duration_ms < 30000:
                rating = 3.0
            else:
                rating = 2.0
        else:
            if duration_ms < 5000:
                rating = 2.0
            else:
                rating = 1.0

        return self.record_feedback(
            target=target,
            rating=rating,
            feedback_type="implicit",
            metadata={
                **(metadata or {}),
                "success": success,
                "duration_ms": duration_ms,
            },
        )

    def record_performance_snapshot(
        self,
        target: str,
        metric: str,
        value: float,
    ) -> bool:
        """Record a performance metric snapshot.

        Args:
            target: What the metric is about.
            metric: Metric name (e.g. 'success_rate', 'avg_duration').
            value: Metric value.

        Returns:
            True if recording succeeded.
        """
        now = datetime.now(timezone.utc)
        try:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO performance_snapshots
                        (target, metric, value, timestamp)
                    VALUES (?, ?, ?, ?)
                    """,
                    (target, metric, value, now.isoformat()),
                )
                return True
        except (sqlite3.Error, OSError) as e:
            logger.error("Failed to record performance snapshot: %s", e)
            return False

    def get_feedback_summary(self, target: str) -> Optional[FeedbackSummary]:
        """Get aggregated feedback for a target.

        Args:
            target: The feedback target.

        Returns:
            FeedbackSummary or None if no data exists.
        """
        try:
            with self._get_conn() as conn:
                row = conn.execute(
                    """
                    SELECT
                        COUNT(*) as total_count,
                        AVG(rating) as avg_rating,
                        SUM(CASE WHEN feedback_type = 'explicit' THEN 1 ELSE 0 END) as explicit_count,
                        SUM(CASE WHEN feedback_type = 'implicit' THEN 1 ELSE 0 END) as implicit_count
                    FROM feedback_entries
                    WHERE target = ?
                    """,
                    (target,),
                ).fetchone()

                if not row or row["total_count"] == 0:
                    return None

                recent_row = conn.execute(
                    """
                    SELECT AVG(rating) as recent_avg
                    FROM feedback_entries
                    WHERE target = ?
                      AND timestamp >= datetime('now', '-7 days')
                    """,
                    (target,),
                ).fetchone()

                recent_avg = recent_row["recent_avg"] if recent_row and recent_row["recent_avg"] else 0.0

                older_row = conn.execute(
                    """
                    SELECT AVG(rating) as older_avg
                    FROM feedback_entries
                    WHERE target = ?
                      AND timestamp < datetime('now', '-7 days')
                    """,
                    (target,),
                ).fetchone()

                older_avg = older_row["older_avg"] if older_row and older_row["older_avg"] else 0.0

                if older_avg > 0:
                    if recent_avg > older_avg + 0.3:
                        trend = "improving"
                    elif recent_avg < older_avg - 0.3:
                        trend = "degrading"
                    else:
                        trend = "stable"
                else:
                    trend = "stable"

                return FeedbackSummary(
                    target=target,
                    total_count=row["total_count"],
                    avg_rating=row["avg_rating"],
                    explicit_count=row["explicit_count"],
                    implicit_count=row["implicit_count"],
                    recent_avg=recent_avg,
                    trend=trend,
                )
        except (sqlite3.Error, OSError) as e:
            logger.error("Failed to get feedback summary for %s: %s", target, e)
            return None

    def get_all_summaries(self) -> list[FeedbackSummary]:
        """Get feedback summaries for all targets.

        Returns:
            List of FeedbackSummary objects.
        """
        try:
            with self._get_conn() as conn:
                targets = conn.execute(
                    "SELECT DISTINCT target FROM feedback_entries"
                ).fetchall()

                summaries = []
                for row in targets:
                    summary = self.get_feedback_summary(row["target"])
                    if summary:
                        summaries.append(summary)

                return summaries
        except (sqlite3.Error, OSError) as e:
            logger.error("Failed to get all summaries: %s", e)
            return []

    def check_degradation(
        self,
        window_days: int = 7,
        baseline_days: int = 30,
        threshold: float = 0.15,
    ) -> list[DegradationAlert]:
        """Check for performance degradation across all targets.

        Compares recent performance (last window_days) against the
        historical baseline (last baseline_days). Flags targets where
        the drop exceeds the threshold.

        Args:
            window_days: Days for the recent window.
            baseline_days: Days for the baseline window.
            threshold: Minimum drop to trigger an alert (0.0-1.0).

        Returns:
            List of DegradationAlert objects.
        """
        alerts = []
        try:
            with self._get_conn() as conn:
                targets = conn.execute(
                    "SELECT DISTINCT target FROM feedback_entries"
                ).fetchall()

                now = datetime.now(timezone.utc)

                for row in targets:
                    target = row["target"]

                    recent = conn.execute(
                        """
                        SELECT AVG(rating) as avg_rating
                        FROM feedback_entries
                        WHERE target = ?
                          AND timestamp >= datetime('now', ?)
                        """,
                        (target, f"-{window_days} days"),
                    ).fetchone()

                    baseline = conn.execute(
                        """
                        SELECT AVG(rating) as avg_rating
                        FROM feedback_entries
                        WHERE target = ?
                          AND timestamp >= datetime('now', ?)
                          AND timestamp < datetime('now', ?)
                        """,
                        (target, f"-{baseline_days} days", f"-{window_days} days"),
                    ).fetchone()

                    recent_avg = recent["avg_rating"] if recent and recent["avg_rating"] else 0.0
                    baseline_avg = baseline["avg_rating"] if baseline and baseline["avg_rating"] else 0.0

                    if baseline_avg > 0 and recent_avg > 0:
                        drop = (baseline_avg - recent_avg) / baseline_avg

                        if drop >= threshold:
                            severity = "critical" if drop >= 0.30 else "warning"
                            alerts.append(DegradationAlert(
                                target=target,
                                severity=severity,
                                current_rate=recent_avg,
                                baseline_rate=baseline_avg,
                                drop_percentage=drop * 100,
                                detected_at=now,
                                recommendation=self._get_degradation_recommendation(
                                    target, drop, severity
                                ),
                            ))
        except (sqlite3.Error, OSError) as e:
            logger.error("Failed to check degradation: %s", e)

        return alerts

    def _get_degradation_recommendation(
        self,
        target: str,
        drop: float,
        severity: str,
    ) -> str:
        """Generate a recommendation for a degradation alert.

        Args:
            target: The degrading target.
            drop: Drop fraction (0.0-1.0).
            severity: Alert severity.

        Returns:
            Recommendation string.
        """
        if severity == "critical":
            return (
                f"Critical degradation detected for {target} "
                f"({drop:.0%} drop). Immediate review recommended. "
                f"Consider disabling or rolling back recent changes."
            )
        else:
            return (
                f"Performance decline detected for {target} "
                f"({drop:.0%} drop). Monitor closely and review "
                f"recent changes that may have affected quality."
            )

    def get_tuning_recommendations(self) -> list[TuningRecommendation]:
        """Generate parameter tuning recommendations based on feedback.

        Analyzes feedback patterns and suggests parameter adjustments
        to improve overall system performance.

        Returns:
            List of TuningRecommendation objects.
        """
        recommendations = []
        try:
            summaries = self.get_all_summaries()

            if not summaries:
                return recommendations

            overall_avg = sum(s.avg_rating for s in summaries) / len(summaries)
            overall_recent = sum(s.recent_avg for s in summaries) / len(summaries)

            low_performers = [s for s in summaries if s.avg_rating < 3.0]
            degrading = [s for s in summaries if s.trend == "degrading"]

            if low_performers:
                worst = min(low_performers, key=lambda s: s.avg_rating)
                recommendations.append(TuningRecommendation(
                    parameter=f"skill:{worst.target}",
                    current_value=f"rating={worst.avg_rating:.2f}",
                    recommended_value="review_and_update",
                    reason=(
                        f"Target '{worst.target}' has low average rating "
                        f"({worst.avg_rating:.2f}/5.0). Review and update "
                        f"the skill or task definition."
                    ),
                    confidence=0.8,
                    impact="high",
                ))

            if degrading:
                for s in degrading:
                    recommendations.append(TuningRecommendation(
                        parameter=f"trend:{s.target}",
                        current_value=f"trend={s.trend}",
                        recommended_value="investigate_recent_changes",
                        reason=(
                            f"Target '{s.target}' is showing degrading "
                            f"performance (recent avg: {s.recent_avg:.2f}). "
                            f"Investigate recent changes."
                        ),
                        confidence=0.7,
                        impact="medium",
                    ))

            if overall_recent < 3.5:
                recommendations.append(TuningRecommendation(
                    parameter="system:default_model",
                    current_value="current_model",
                    recommended_value="higher_capability_model",
                    reason=(
                        f"Overall system performance is below threshold "
                        f"({overall_recent:.2f}/5.0). Consider using a "
                        f"more capable model for better results."
                    ),
                    confidence=0.6,
                    impact="high",
                ))

            slow_tools = self._identify_slow_tools()
            for tool_name, avg_duration in slow_tools:
                recommendations.append(TuningRecommendation(
                    parameter=f"tool:{tool_name}",
                    current_value=f"avg_duration={avg_duration:.0f}ms",
                    recommended_value="optimize_or_cache",
                    reason=(
                        f"Tool '{tool_name}' is consistently slow "
                        f"(avg {avg_duration:.0f}ms). Consider adding "
                        f"caching or optimizing the implementation."
                    ),
                    confidence=0.75,
                    impact="medium",
                ))

            recommendations.sort(key=lambda r: (
                {"high": 3, "medium": 2, "low": 1}.get(r.impact, 0),
                r.confidence,
            ), reverse=True)

        except Exception as e:
            logger.error("Failed to generate tuning recommendations: %s", e)

        return recommendations

    def _identify_slow_tools(self, threshold_ms: float = 5000.0) -> list[tuple[str, float]]:
        """Identify tools with consistently high execution times.

        Args:
            threshold_ms: Duration threshold in milliseconds.

        Returns:
            List of (tool_name, avg_duration_ms) tuples.
        """
        slow_tools = []
        try:
            with self._get_conn() as conn:
                rows = conn.execute(
                    """
                    SELECT
                        SUBSTR(target, 6) as tool_name,
                        AVG(CAST(json_extract(metadata, '$.duration_ms') AS REAL)) as avg_duration
                    FROM feedback_entries
                    WHERE feedback_type = 'implicit'
                      AND target LIKE 'tool:%'
                      AND json_extract(metadata, '$.duration_ms') IS NOT NULL
                    GROUP BY target
                    HAVING avg_duration > ?
                    ORDER BY avg_duration DESC
                    """,
                    (threshold_ms,),
                ).fetchall()

                for row in rows:
                    if row["avg_duration"]:
                        slow_tools.append((row["tool_name"], row["avg_duration"]))
        except (sqlite3.Error, OSError) as e:
            logger.error("Failed to identify slow tools: %s", e)

        return slow_tools

    def apply_tuning(
        self,
        parameter: str,
        old_value: Any,
        new_value: Any,
        reason: str = "",
    ) -> bool:
        """Record a tuning action in the history.

        Args:
            parameter: The parameter that was tuned.
            old_value: Previous value.
            new_value: New value.
            reason: Why the change was made.

        Returns:
            True if recording succeeded.
        """
        now = datetime.now(timezone.utc)
        try:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO tuning_history
                        (parameter, old_value, new_value, reason, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (parameter, str(old_value), str(new_value), reason, now.isoformat()),
                )
                return True
        except (sqlite3.Error, OSError) as e:
            logger.error("Failed to record tuning action: %s", e)
            return False

    def get_tuning_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent tuning actions.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of tuning history dicts.
        """
        try:
            with self._get_conn() as conn:
                rows = conn.execute(
                    """
                    SELECT parameter, old_value, new_value, reason, timestamp
                    FROM tuning_history
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()

                return [
                    {
                        "parameter": row["parameter"],
                        "old_value": row["old_value"],
                        "new_value": row["new_value"],
                        "reason": row["reason"],
                        "timestamp": row["timestamp"],
                    }
                    for row in rows
                ]
        except (sqlite3.Error, OSError) as e:
            logger.error("Failed to get tuning history: %s", e)
            return []

    def get_feedback_trend(
        self,
        target: str,
        days: int = 30,
    ) -> list[dict[str, Any]]:
        """Get daily feedback trend for a target.

        Args:
            target: The feedback target.
            days: Number of days to look back.

        Returns:
            List of dicts with 'date', 'count', 'avg_rating'.
        """
        try:
            with self._get_conn() as conn:
                rows = conn.execute(
                    """
                    SELECT
                        DATE(timestamp) as date,
                        COUNT(*) as count,
                        AVG(rating) as avg_rating
                    FROM feedback_entries
                    WHERE target = ?
                      AND timestamp >= datetime('now', ?)
                    GROUP BY DATE(timestamp)
                    ORDER BY date DESC
                    """,
                    (target, f"-{days} days"),
                ).fetchall()

                return [
                    {
                        "date": row["date"],
                        "count": row["count"],
                        "avg_rating": round(row["avg_rating"], 4) if row["avg_rating"] else 0.0,
                    }
                    for row in rows
                ]
        except (sqlite3.Error, OSError) as e:
            logger.error("Failed to get feedback trend: %s", e)
            return []

    def delete_old_feedback(self, older_than_days: int = 180) -> int:
        """Delete feedback entries older than a threshold.

        Args:
            older_than_days: Delete entries older than this many days.

        Returns:
            Number of entries deleted.
        """
        try:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    "DELETE FROM feedback_entries WHERE timestamp < datetime('now', ?)",
                    (f"-{older_than_days} days",),
                )
                return cursor.rowcount
        except (sqlite3.Error, OSError) as e:
            logger.error("Failed to delete old feedback: %s", e)
            return 0

    def close(self) -> None:
        """No-op for API compatibility."""
        pass
