"""
NEUGI v2 - Activity Reporter
=============================

Reports autonomous activities back to the system and optionally to users.
The reporter is the "voice" of the autonomous loop — it decides what
should be remembered, what should be shown on the dashboard, and what
should interrupt the user.

Reporting philosophy:
1. Everything is logged to memory (autonomous activity audit trail)
2. High-value activities are reported to dashboard
3. Only critical/urgent activities interrupt the user
4. Reports are concise and actionable
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from autonomous.executor import ExecutionResult
from autonomous.notification_dispatcher import (
    NotificationDispatcher,
    NotificationPreferences,
    AutonomousNotification,
    NotificationChannel,
)

logger = logging.getLogger(__name__)


class ReportSeverity(str, Enum):
    """Severity levels for activity reports."""

    DEBUG = "debug"         # Internal only, not shown
    INFO = "info"           # Dashboard only
    NOTICE = "notice"       # Dashboard + summary
    WARNING = "warning"     # Dashboard + potential user notification
    CRITICAL = "critical"   # Dashboard + immediate user notification


class ReportChannel(str, Enum):
    """Channels through which reports can be sent."""

    MEMORY = "memory"       # Store in memory system
    DASHBOARD = "dashboard" # Push to web dashboard
    LOG = "log"             # Application log
    USER = "user"           # Direct user notification
    EVENT_BUS = "event_bus" # System event bus


@dataclass
class ActivityReport:
    """A report of an autonomous activity.

    Attributes:
        activity_id: Unique identifier.
        severity: Report severity.
        title: Short title.
        description: Human-readable description.
        channels: Which channels to send to.
        result: The execution result being reported.
        metadata: Additional structured data.
        created_at: Unix timestamp.
    """

    activity_id: str
    severity: ReportSeverity
    title: str
    description: str
    channels: List[ReportChannel] = field(default_factory=list)
    result: Optional[ExecutionResult] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=lambda: time.time())


class ActivityReporter:
    """Reports autonomous activities to appropriate channels.

    The reporter decides WHERE and HOW to communicate what NEUGI did.
    It respects user preferences (from SoulEngine USER.md) about
    notification frequency and importance thresholds.

    Args:
        memory_system: Optional memory system for persistence.
        event_bus: Optional event bus for real-time updates.
        user_notify_threshold: Minimum severity to notify user directly.
    """

    def __init__(
        self,
        memory_system: Any = None,
        event_bus: Any = None,
        user_notify_threshold: ReportSeverity = ReportSeverity.WARNING,
        max_reports: int = 1000,
        notification_dispatcher: Optional[NotificationDispatcher] = None,
    ) -> None:
        self.memory_system = memory_system
        self.event_bus = event_bus
        self.user_notify_threshold = user_notify_threshold
        self._max_reports = max_reports
        self._reports: List[ActivityReport] = []
        self._lock = threading.RLock()
        self._notifier = notification_dispatcher or NotificationDispatcher(
            preferences=NotificationPreferences(),
            event_bus=event_bus,
        )

    # -- Public API ------------------------------------------------------------

    def report(self, result: ExecutionResult) -> ActivityReport:
        """Report a single execution result."""
        report = self._create_report(result)
        with self._lock:
            self._reports.append(report)
            if len(self._reports) > self._max_reports:
                self._reports = self._reports[-self._max_reports:]
        self._dispatch(report)
        return report

    def report_batch(self, results: List[ExecutionResult]) -> List[ActivityReport]:
        """Report a batch of execution results.

        Args:
            results: List of execution results.

        Returns:
            List of generated reports.
        """
        reports: List[ActivityReport] = []

        for result in results:
            report = self.report(result)
            reports.append(report)

        return reports

    def get_summary(self, since: Optional[float] = None) -> Dict[str, Any]:
        """Get a summary of recent autonomous activities.

        Args:
            since: Unix timestamp to filter from (default: last 24h).

        Returns:
            Summary dict with counts and highlights.
        """
        if since is None:
            since = time.time() - 86400

        recent = [r for r in self._reports if r.created_at > since]

        by_severity: Dict[str, int] = {}
        for r in recent:
            by_severity[r.severity.value] = by_severity.get(r.severity.value, 0) + 1

        highlights = [
            {"title": r.title, "severity": r.severity.value}
            for r in recent
            if r.severity in (ReportSeverity.WARNING, ReportSeverity.CRITICAL)
        ]

        return {
            "total_activities": len(recent),
            "by_severity": by_severity,
            "highlights": highlights,
            "period_hours": (time.time() - since) / 3600,
        }

    # -- Report Creation -------------------------------------------------------

    def _create_report(self, result: ExecutionResult) -> ActivityReport:
        """Create an ActivityReport from an ExecutionResult."""
        dec_type = result.decision.decision_type.value
        obs_type = result.decision.source_observation.obs_type.value
        success = result.success

        # Determine severity
        if not success and result.decision.source_observation.urgency > 0.7:
            severity = ReportSeverity.CRITICAL
        elif not success:
            severity = ReportSeverity.WARNING
        elif result.decision.source_observation.urgency > 0.6:
            severity = ReportSeverity.NOTICE
        else:
            severity = ReportSeverity.INFO

        # Build title and description
        if success:
            title = f"✓ {dec_type.replace('_', ' ').title()}"
            description = (
                f"Autonomous action completed: {dec_type} "
                f"(triggered by {obs_type}). "
                f"Duration: {result.duration_ms:.0f}ms."
            )
        else:
            title = f"✗ {dec_type.replace('_', ' ').title()} Failed"
            description = (
                f"Autonomous action failed: {dec_type} "
                f"(triggered by {obs_type}). "
                f"Error: {result.error or 'unknown'}."
            )

        # Determine channels
        channels = [ReportChannel.LOG, ReportChannel.MEMORY]

        if severity in (ReportSeverity.INFO, ReportSeverity.NOTICE):
            channels.append(ReportChannel.DASHBOARD)

        if severity in (ReportSeverity.WARNING, ReportSeverity.CRITICAL):
            channels.extend([ReportChannel.DASHBOARD, ReportChannel.EVENT_BUS])

        if severity.value >= self.user_notify_threshold.value:
            channels.append(ReportChannel.USER)

        return ActivityReport(
            activity_id=f"auto_{int(time.time()*1000)}",
            severity=severity,
            title=title,
            description=description,
            channels=channels,
            result=result,
            metadata={
                "decision_type": dec_type,
                "observation_type": obs_type,
                "success": success,
                "duration_ms": result.duration_ms,
            },
        )

    # -- Dispatch --------------------------------------------------------------

    def _dispatch(self, report: ActivityReport) -> None:
        """Dispatch report to all configured channels."""
        for channel in report.channels:
            try:
                if channel == ReportChannel.MEMORY:
                    self._to_memory(report)
                elif channel == ReportChannel.DASHBOARD:
                    self._to_dashboard(report)
                elif channel == ReportChannel.LOG:
                    self._to_log(report)
                elif channel == ReportChannel.USER:
                    self._to_user(report)
                elif channel == ReportChannel.EVENT_BUS:
                    self._to_event_bus(report)
            except Exception as e:
                logger.warning("Failed to dispatch report to %s: %s", channel.value, e)

    def _to_memory(self, report: ActivityReport) -> None:
        """Store report in memory system."""
        if not self.memory_system:
            return

        try:
            content = f"[AUTONOMOUS] {report.title}: {report.description}"
            if hasattr(self.memory_system, "save"):
                self.memory_system.save(
                    content=content,
                    role="system",
                    tags=["autonomous", report.severity.value, "activity"],
                    metadata={
                        "activity_id": report.activity_id,
                        "severity": report.severity.value,
                        "success": report.metadata.get("success"),
                    },
                )
        except Exception as e:
            logger.warning("Failed to store report in memory: %s", e)

    def _to_dashboard(self, report: ActivityReport) -> None:
        """Push report to dashboard."""
        # Placeholder: would integrate with dashboard WebSocket/API
        pass

    def _to_log(self, report: ActivityReport) -> None:
        """Log report via Python logging."""
        msg = f"[AUTONOMOUS] {report.title}: {report.description}"
        if report.severity == ReportSeverity.CRITICAL:
            logger.error(msg)
        elif report.severity == ReportSeverity.WARNING:
            logger.warning(msg)
        elif report.severity == ReportSeverity.NOTICE:
            logger.info(msg)
        else:
            logger.debug(msg)

    def _to_user(self, report: ActivityReport) -> None:
        """Send direct notification to user via NotificationDispatcher."""
        try:
            notification = AutonomousNotification(
                severity=report.severity.value,
                title=report.title,
                message=report.description,
                activity_type=report.metadata.get("decision_type", "unknown"),
                channels=[
                    NotificationChannel.TELEGRAM,
                    NotificationChannel.DISCORD,
                    NotificationChannel.SLACK,
                ],
                metadata=report.metadata,
            )
            self._notifier.dispatch(notification)
        except Exception as e:
            logger.warning("User notification dispatch failed: %s", e)

    def _to_dashboard(self, report: ActivityReport) -> None:
        """Push report to dashboard via NotificationDispatcher."""
        try:
            notification = AutonomousNotification(
                severity=report.severity.value,
                title=report.title,
                message=report.description,
                activity_type=report.metadata.get("decision_type", "unknown"),
                channels=[NotificationChannel.DASHBOARD],
                metadata=report.metadata,
            )
            self._notifier.dispatch(notification)
        except Exception as e:
            logger.warning("Dashboard dispatch failed: %s", e)

    def _to_event_bus(self, report: ActivityReport) -> None:
        """Publish to system event bus."""
        if not self.event_bus:
            return

        try:
            if hasattr(self.event_bus, "publish"):
                self.event_bus.publish(
                    type="autonomous_activity",
                    payload={
                        "activity_id": report.activity_id,
                        "severity": report.severity.value,
                        "title": report.title,
                        "description": report.description,
                    },
                )
        except Exception as e:
            logger.warning("Failed to publish to event bus: %s", e)
