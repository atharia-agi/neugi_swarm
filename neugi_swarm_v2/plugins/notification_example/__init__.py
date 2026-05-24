"""
Notification Example Plugin for NEUGI.

This plugin demonstrates:
1. Subscribing to events from the event bus
2. Using middleware for event processing
3. Plugin lifecycle hooks
"""

from neugi_swarm_v2.observability.event_bus import get_event_bus
from neugi_swarm_v2.plugins import HookContext, Plugin


class NotificationExamplePlugin(Plugin):
    def __init__(self):
        super().__init__()
        self.event_bus = get_event_bus()
        self.subscribed_events = []

    def activate(self, context: HookContext) -> None:
        """Activate the plugin and set up event subscriptions."""
        self.logger.info("NotificationExamplePlugin activated!")

        # Add custom middleware for this plugin
        self.event_bus.add_middleware(self._middleware_logger)

        # Subscribe to tool execution events
        self.event_bus.subscribe("tool_execution_success", self._on_tool_success)
        self.event_bus.subscribe("tool_execution_failure", self._on_tool_failure)

        # Keep track of subscriptions for cleanup (optional)
        self.subscribed_events = [
            "tool_execution_success",
            "tool_execution_failure"
        ]

        self.logger.info("Subscribed to tool execution events")

    def _middleware_logger(self, event):
        """Example middleware that logs every event."""
        # This middleware will be called for every event published
        # after the event is added to history but before subscribers are called
        self.logger.debug(f"Middleware saw event: {event.name}")

    def _on_tool_success(self, event):
        """Handle tool execution success events."""
        payload = event.payload or {}
        tool = payload.get("tool", "unknown")
        self.logger.info(f"✅ Tool success: {tool}")

    def _on_tool_failure(self, event):
        """Handle tool execution failure events."""
        payload = event.payload or {}
        tool = payload.get("tool", "unknown")
        error = payload.get("error", "unknown error")
        self.logger.warning(f"❌ Tool failure: {tool} - {error}")

    def deactivate(self, context: HookContext) -> None:
        """Clean up when plugin is deactivated."""
        self.logger.info("NotificationExamplePlugin deactivating...")

        # Unsubscribe from events
        for _event_name in self.subscribed_events:
            # We would need to store the actual callbacks to unsubscribe
            # For simplicity in this example, we'll skip explicit unsubscription
            # In a real plugin, you'd store the callbacks and unsubscribe them here
            pass

        self.logger.info("NotificationExamplePlugin deactivated.")


def activate() -> NotificationExamplePlugin:
    """Entry point for the plugin."""
    return NotificationExamplePlugin()
