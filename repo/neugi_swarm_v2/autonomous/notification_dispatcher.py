"""
NEUGI v2 - Proactive Notification Dispatcher
=============================================

Dispatches autonomous activity notifications to external channels
(Telegram, Discord, Slack) and the dashboard event bus.

Respects user preferences from SoulEngine USER.md:
- notification_frequency: "immediate", "digest", "silent"
- notification_min_severity: debug, info, notice, warning, critical
- notification_channels: list of enabled channels

Only critical/urgent autonomous activities interrupt the user.
Everything else is batched for digest or logged silently.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class NotificationFrequency(str, Enum):
    """How often the user wants to be notified."""

    IMMEDIATE = "immediate"   # Send right away
    DIGEST = "digest"         # Batch and send periodically
    SILENT = "silent"         # Log only, no external notification


class NotificationChannel(str, Enum):
    """Channels that can receive notifications."""

    TELEGRAM = "telegram"
    DISCORD = "discord"
    SLACK = "slack"
    WHATSAPP = "whatsapp"
    DASHBOARD = "dashboard"
    LOG = "log"


@dataclass
class NotificationPreferences:
    """User notification preferences (from SoulEngine USER.md)."""

    frequency: NotificationFrequency = NotificationFrequency.DIGEST
    min_severity: str = "warning"  # debug, info, notice, warning, critical
    enabled_channels: list[NotificationChannel] = field(
        default_factory=lambda: [NotificationChannel.DASHBOARD, NotificationChannel.LOG]
    )
    digest_interval_hours: float = 24.0
    quiet_hours_start: int | None = None  # 0-23
    quiet_hours_end: int | None = None


@dataclass
class AutonomousNotification:
    """A single notification about autonomous activity."""

    severity: str
    title: str
    message: str
    activity_type: str
    channels: list[NotificationChannel] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=lambda: time.time())


class NotificationDispatcher:
    """Dispatches autonomous notifications to external channels.

    Args:
        preferences: User notification preferences.
        channel_manager: Optional ChannelManager for routing to Telegram/Discord/Slack.
        event_bus: Optional event bus for dashboard pushes.
    """

    def __init__(
        self,
        preferences: NotificationPreferences | None = None,
        channel_manager: Any = None,
        event_bus: Any = None,
    ) -> None:
        self.preferences = preferences or NotificationPreferences()
        self.channel_manager = channel_manager
        self.event_bus = event_bus

        self._digest_queue: list[AutonomousNotification] = []
        self._digest_lock = threading.RLock()
        self._last_digest_time: float = 0.0

    # -- Public API ------------------------------------------------------------

    def dispatch(self, notification: AutonomousNotification) -> dict[str, Any]:
        """Dispatch a notification according to user preferences.

        Returns:
            Dict with dispatch results per channel.
        """
        results: dict[str, Any] = {"dispatched": [], "skipped": [], "errors": []}

        # Check severity threshold
        severity_levels = ["debug", "info", "notice", "warning", "critical"]
        min_idx = severity_levels.index(self.preferences.min_severity)
        notif_idx = severity_levels.index(notification.severity) if notification.severity in severity_levels else 0

        if notif_idx < min_idx:
            results["skipped"].append("below_severity_threshold")
            return results

        # Check quiet hours
        if self._in_quiet_hours():
            results["skipped"].append("quiet_hours")
            return results

        # Determine routing based on frequency
        if self.preferences.frequency == NotificationFrequency.SILENT:
            results["skipped"].append("silent_mode")
            return results

        if self.preferences.frequency == NotificationFrequency.DIGEST:
            # Queue for digest unless critical
            if notification.severity != "critical":
                with self._digest_lock:
                    self._digest_queue.append(notification)
                results["dispatched"].append("digest_queued")
                return results

        # Immediate dispatch
        for channel in notification.channels:
            if channel not in self.preferences.enabled_channels:
                results["skipped"].append(f"{channel.value}_disabled")
                continue

            try:
                self._send_to_channel(channel, notification)
                results["dispatched"].append(channel.value)
            except Exception as e:
                logger.warning("Notification to %s failed: %s", channel.value, e)
                results["errors"].append({"channel": channel.value, "error": str(e)})

        return results

    def send_digest(self) -> dict[str, Any]:
        """Send all queued digest notifications.

        Returns:
            Dict with digest results.
        """
        with self._digest_lock:
            notifications = self._digest_queue[:]
            self._digest_queue = []

        if not notifications:
            return {"sent": False, "reason": "empty_queue"}

        # Group by severity
        by_severity: dict[str, list[AutonomousNotification]] = {}
        for n in notifications:
            by_severity.setdefault(n.severity, []).append(n)

        lines = [f"📋 NEUGI Autonomous Digest ({len(notifications)} activities)", ""]

        for sev in ["critical", "warning", "notice", "info", "debug"]:
            if sev not in by_severity:
                continue
            items = by_severity[sev]
            icon = {"critical": "🔴", "warning": "🟡", "notice": "🔵", "info": "⚪", "debug": "⚫"}.get(sev, "⚪")
            lines.append(f"{icon} {sev.upper()}: {len(items)}")
            for n in items[:5]:  # Max 5 per severity
                lines.append(f"  • {n.title}: {n.message[:80]}")
            if len(items) > 5:
                lines.append(f"  ... and {len(items) - 5} more")
            lines.append("")

        digest_text = "\n".join(lines)

        results: dict[str, Any] = {"sent": True, "count": len(notifications), "channels": []}

        for channel in self.preferences.enabled_channels:
            if channel == NotificationChannel.LOG:
                logger.info("Autonomous digest:\n%s", digest_text)
                results["channels"].append("log")
                continue

            try:
                self._send_raw_to_channel(channel, digest_text)
                results["channels"].append(channel.value)
            except Exception as e:
                logger.warning("Digest to %s failed: %s", channel.value, e)

        self._last_digest_time = time.time()
        return results

    def get_digest_preview(self) -> str:
        """Get a preview of queued digest items."""
        with self._digest_lock:
            count = len(self._digest_queue)
            if count == 0:
                return "No queued notifications."
            previews = [f"{n.severity}: {n.title}" for n in self._digest_queue[:10]]
            extra = f"\n... and {count - 10} more" if count > 10 else ""
            return f"Queued notifications ({count}):\n" + "\n".join(previews) + extra

    # -- Channel Senders -------------------------------------------------------

    def _send_to_channel(
        self,
        channel: NotificationChannel,
        notification: AutonomousNotification,
    ) -> None:
        """Send a single notification to a channel."""
        text = f"[{notification.severity.upper()}] {notification.title}\n{notification.message}"
        self._send_raw_to_channel(channel, text)

    def _send_raw_to_channel(self, channel: NotificationChannel, text: str) -> None:
        """Send raw text to a channel."""
        if channel == NotificationChannel.LOG:
            logger.info("[NOTIFY] %s", text)
            return

        if channel == NotificationChannel.DASHBOARD and self.event_bus:
            self._push_to_dashboard(text)
            return

        if self.channel_manager:
            self._send_via_channel_manager(channel, text)
            return

        # No dispatcher available — just log
        logger.info("Would notify %s: %s", channel.value, text[:200])

    def _push_to_dashboard(self, text: str) -> None:
        """Push notification to dashboard via event bus."""
        if not self.event_bus:
            return
        try:
            if hasattr(self.event_bus, "publish"):
                self.event_bus.publish("autonomous_notification", {"message": text})
            elif hasattr(self.event_bus, "emit"):
                self.event_bus.emit("autonomous_notification", {"message": text})
        except Exception as e:
            logger.warning("Dashboard push failed: %s", e)

    def _send_via_channel_manager(self, channel: NotificationChannel, text: str) -> None:
        """Send via ChannelManager if available."""
        if not self.channel_manager:
            return
        try:
            # Try to find the specific channel instance
            channel_key = channel.value
            if hasattr(self.channel_manager, "send"):
                self.channel_manager.send(channel_key, text)
            elif hasattr(self.channel_manager, "broadcast"):
                self.channel_manager.broadcast(text, channels=[channel_key])
        except Exception as e:
            logger.warning("ChannelManager send failed: %s", e)

    # -- Utilities -------------------------------------------------------------

    def _in_quiet_hours(self) -> bool:
        """Check if current time is in quiet hours."""
        if self.preferences.quiet_hours_start is None or self.preferences.quiet_hours_end is None:
            return False
        now = time.localtime().tm_hour
        start = self.preferences.quiet_hours_start
        end = self.preferences.quiet_hours_end
        if start <= end:
            return start <= now < end
        return now >= start or now < end
