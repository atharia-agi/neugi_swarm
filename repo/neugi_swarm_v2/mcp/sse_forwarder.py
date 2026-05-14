"""
SSE Event Forwarder - Bridges NEUGI EventBus to MCP SSE Transport
===================================================================

Forwards NEUGI observability events to connected SSE clients,
enabling real-time monitoring dashboards and browser-based MCP clients.
"""

from __future__ import annotations

import logging
from typing import Any

from neugi_swarm_v2.mcp.transport import HTTPTransport, SSEConnection

logger = logging.getLogger(__name__)


class SSEEventForwarder:
    """Forwards NEUGI EventBus events to MCP SSE connections.

    Subscribes to the NEUGI event bus and forwards events to all
    connected SSE clients that have subscribed to matching event types.
    """

    # Map NEUGI event names to SSE event types
    EVENT_MAPPING = {
        "tool_execution_success": "tool_execution_success",
        "tool_execution_failure": "tool_execution_failure",
        "mcp_call": "mcp_call",
        "memory_update": "memory_update",
        "memory_warning": "memory_warning",
        "agent_action": "agent_activity",
        "agent_heartbeat": "agent_activity",
    }

    def __init__(self, transport: HTTPTransport):
        self.transport = transport
        self._forwarding = False
        self._event_bus = None

    def start(self, event_bus: Any = None) -> None:
        """Start forwarding events from the NEUGI event bus.

        Args:
            event_bus: NEUGI EventBus instance. If None, gets global instance.
        """
        if not self.transport._enable_sse:
            logger.info("SSE not enabled on transport, skipping forwarder")
            return

        try:
            if event_bus is None:
                from observability.event_bus import get_event_bus
                event_bus = get_event_bus()

            self._event_bus = event_bus

            # Subscribe to all mapped events
            for neugi_event in self.EVENT_MAPPING:
                self._event_bus.subscribe(neugi_event, self._create_handler(neugi_event))

            # Also subscribe to wildcard for any unmapped events
            self._event_bus.subscribe("all", self._handle_generic_event)

            self._forwarding = True
            logger.info("SSE event forwarder started, forwarding to %d SSE connections",
                        len(self.transport.sse_connections))

        except Exception as e:
            logger.error("Failed to start SSE event forwarder: %s", e)

    def stop(self) -> None:
        """Stop forwarding events."""
        self._forwarding = False
        logger.info("SSE event forwarder stopped")

    @property
    def is_forwarding(self) -> bool:
        return self._forwarding

    def _create_handler(self, event_name: str):
        """Create a handler function for a specific NEUGI event."""
        def handler(event: Any) -> None:
            if not self._forwarding:
                return
            try:
                sse_event_type = self.EVENT_MAPPING.get(event_name, event_name)
                payload = {
                    "event": event_name,
                    "payload": event.payload if hasattr(event, "payload") else event,
                    "source": event.source if hasattr(event, "source") else "unknown",
                    "timestamp": event.timestamp.isoformat() if hasattr(event, "timestamp") else None,
                }
                # Broadcast to SSE connections
                import asyncio
                asyncio.create_task(
                    self.transport.publish_sse_event(sse_event_type, payload)
                )
            except Exception as e:
                logger.error("Error forwarding event %s: %s", event_name, e)

        return handler

    def _handle_generic_event(self, event: Any) -> None:
        """Handle events that don't have specific mappings."""
        if not self._forwarding:
            return
        try:
            event_name = event.name if hasattr(event, "name") else "generic"
            if event_name in self.EVENT_MAPPING:
                return  # Already handled by specific handler

            payload = {
                "event": event_name,
                "payload": event.payload if hasattr(event, "payload") else event,
                "source": event.source if hasattr(event, "source") else "unknown",
            }
            import asyncio
            asyncio.create_task(
                self.transport.publish_sse_event("system_event", payload)
            )
        except Exception as e:
            logger.error("Error in generic event handler: %s", e)

    def add_connection(self, conn: SSEConnection) -> None:
        """Register a new SSE connection and start forwarding if needed."""
        self.transport.register_sse_connection(conn)
        logger.debug("SSE connection registered: %s", conn.session_id)

    def remove_connection(self, session_id: str) -> None:
        """Remove an SSE connection."""
        self.transport.unregister_sse_connection(session_id)
        logger.debug("SSE connection removed: %s", session_id)


# Global singleton
_forwarder: SSEEventForwarder | None = None


def get_sse_forwarder(transport: HTTPTransport = None) -> SSEEventForwarder:
    """Get or create the global SSE event forwarder."""
    global _forwarder
    if _forwarder is None:
        if transport is None:
            transport = HTTPTransport(enable_sse=True)
        _forwarder = SSEEventForwarder(transport)
    return _forwarder


def setup_sse_forwarding(
    transport: HTTPTransport,
    event_bus: Any = None,
) -> SSEEventForwarder:
    """Convenience function to set up SSE event forwarding.

    Args:
        transport: HTTPTransport with SSE enabled
        event_bus: NEUGI EventBus instance

    Returns:
        Configured SSEEventForwarder
    """
    forwarder = SSEEventForwarder(transport)
    forwarder.start(event_bus)
    return forwarder