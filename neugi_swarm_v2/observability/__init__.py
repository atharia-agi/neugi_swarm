"""
Observability subsystem for NEUGI.

Provides event bus, tracing, and monitoring capabilities.
"""

from .event_bus import EventBus, get_event_bus

__all__ = [
    "EventBus",
    "get_event_bus",
]