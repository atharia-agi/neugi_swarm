"""
Metrics Example Plugin for NEUGI.

This plugin demonstrates:
1. Subscribing to events from the event bus
2. Collecting metrics (counters) from tool execution events
3. Using the event bus history to get past events
4. Plugin lifecycle hooks
"""

import time
from neugi_swarm_v2.plugins import Plugin, HookContext
from neugi_swarm_v2.observability.event_bus import get_event_bus


class MetricsExamplePlugin(Plugin):
    def __init__(self):
        super().__init__()
        self.event_bus = get_event_bus()
        self.subscribed_events = []

        # Metrics storage
        self.tool_success_count = {}
        self.tool_failure_count = {}
        self.total_tool_time_ms = 0
        self.last_report_time = time.time()
        self.report_interval = 30  # seconds

    def activate(self, context: HookContext) -> None:
        """Activate the plugin and set up event subscriptions."""
        self.logger.info("MetricsExamplePlugin activated!")

        # Subscribe to tool execution events
        self.event_bus.subscribe("tool_execution_success", self._on_tool_success)
        self.event_bus.subscribe("tool_execution_failure", self._on_tool_failure)

        # Keep track of subscriptions
        self.subscribed_events = [
            "tool_execution_success",
            "tool_execution_failure"
        ]

        self.logger.info("Subscribed to tool execution events for metrics collection")

        # Start a background task to report metrics periodically?
        # For simplicity, we'll just check on each event and report if interval passed.
        # In a real plugin, you might use a separate thread or timer.

    def _on_tool_success(self, event):
        """Handle tool execution success events."""
        payload = event.payload or {}
        tool = payload.get("tool", "unknown")
        duration_ms = payload.get("duration_ms", 0)

        # Update metrics
        self.tool_success_count[tool] = self.tool_success_count.get(tool, 0) + 1
        self.total_tool_time_ms += duration_ms

        # Check if it's time to report
        self._maybe_report_metrics()

    def _on_tool_failure(self, event):
        """Handle tool execution failure events."""
        payload = event.payload or {}
        tool = payload.get("tool", "unknown")

        # Update metrics
        self.tool_failure_count[tool] = self.tool_failure_count.get(tool, 0) + 1

        # Check if it's time to report
        self._maybe_report_metrics()

    def _maybe_report_metrics(self):
        """Report metrics if the interval has passed."""
        now = time.time()
        if now - self.last_report_time >= self.report_interval:
            self._report_metrics()
            self.last_report_time = now

    def _report_metrics(self):
        """Log the current metrics."""
        self.logger.info("=== Tool Execution Metrics ===")
        self.logger.info(f"Success counts: {self.tool_success_count}")
        self.logger.info(f"Failure counts: {self.tool_failure_count}")
        if self.tool_success_count:
            avg_time = self.total_tool_time_ms / sum(self.tool_success_count.values())
            self.logger.info(f"Average success time: {avg_time:.2f} ms")
        self.logger.info(f"Total tool time: {self.total_tool_time_ms} ms")
        self.logger.info("==============================")

        # Reset metrics for next interval? Or keep accumulating?
        # For this example, we keep accumulating until the plugin is deactivated.
        # Alternatively, we could reset here to get per-interval metrics.
        # Let's reset to show per-interval metrics.
        self.tool_success_count.clear()
        self.tool_failure_count.clear()
        self.total_tool_time_ms = 0

    def deactivate(self, context: HookContext) -> None:
        """Clean up when plugin is deactivated."""
        self.logger.info("MetricsExamplePlugin deactivating...")

        # Report final metrics
        self._report_metrics()

        # Unsubscribe from events (if we stored the callbacks, we would unsubscribe here)
        # For simplicity, we skip explicit unsubscription in this example.

        self.logger.info("MetricsExamplePlugin deactivated.")


def activate():
    """Entry point for the plugin."""
    return MetricsExamplePlugin()