"""
Observability subsystem for NEUGI.

Provides event bus, tracing, and monitoring capabilities.
"""

from .event_bus import EventBus, Event, get_event_bus, setup_event_bus_persistence

__all__ = [
    "EventBus",
    "Event",
    "get_event_bus",
    "setup_event_bus_persistence",
]