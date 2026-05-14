"""
WebSocket Event Bridge for NEUGI Observability.

Bridges the event bus to the dashboard WebSocket server so events
are streamed live to all connected dashboard clients.
"""

import json
import logging
import threading
from typing import Any, Optional

from neugi_swarm_v2.dashboard.websocket import WebSocketServer
from neugi_swarm_v2.observability.event_bus import Event, get_event_bus

logger = logging.getLogger(__name__)


class EventWebSocketBridge:
    """
    Bridges event bus events to WebSocket clients.

    Subscribes to the global event bus and forwards events to
    all connected dashboard WebSocket clients in real-time.
    """

    def __init__(self, ws_server: WebSocketServer):
        self.ws_server = ws_server
        self.event_bus = get_event_bus()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the bridge in a background thread."""
        if self._running:
            return
        self._running = True

        # Subscribe to all events using middleware
        self.event_bus.add_middleware(self._forward_to_websocket)

        logger.info("Event-WebSocket bridge started, forwarding all events to dashboard")

    def stop(self) -> None:
        """Stop the bridge."""
        self._running = False

    def _forward_to_websocket(self, event: Event) -> None:
        """Forward a single event to all WebSocket clients."""
        if not self._running:
            return
        try:
            payload = {
                "type": "event_bus",
                "event": {
                    "name": event.name,
                    "payload": event.payload,
                    "source": event.source,
                    "timestamp": event.timestamp.isoformat(),
                },
            }
            self.ws_server.broadcast(payload)
        except Exception:
            pass


def setup_ws_bridge(ws_server: WebSocketServer) -> EventWebSocketBridge:
    """Create and start the WebSocket event bridge."""
    bridge = EventWebSocketBridge(ws_server)
    bridge.start()
    return bridge