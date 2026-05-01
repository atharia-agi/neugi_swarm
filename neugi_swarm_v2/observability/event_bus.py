"""
Event Bus for NEUGI Observability.

Provides a simple event bus system for decoupled communication between
components. Allows publishing and subscribing to events with optional
filtering and history.

Thread-safe implementation using threading.Lock.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional


@dataclass
class Event:
    """An event emitted on the bus."""
    name: str
    payload: Any = None
    timestamp: datetime = field(default_factory=datetime.now)
    source: Optional[str] = None


class EventBus:
    """
    A simple thread-safe event bus.
    
    Example:
        bus = EventBus()
        
        def handler(event):
            print(f"Received {event.name}: {event.payload}")
            
        bus.subscribe("tool_call", handler)
        bus.publish("tool_call", {"tool": "web_search", "query": "hello"})
    """
    
    def __init__(self, max_history: int = 1000):
        self._subscribers: Dict[str, List[Callable[[Event], None]]] = defaultdict(list)
        self._history: List[Event] = []
        self._max_history = max_history
        self._lock = threading.RLock()
    
    def subscribe(self, event_name: str, callback: Callable[[Event], None]) -> None:
        """
        Subscribe to an event.
        
        Args:
            event_name: The name of the event to subscribe to.
            callback: A function that takes an Event object.
        """
        with self._lock:
            self._subscribers[event_name].append(callback)
    
    def unsubscribe(self, event_name: str, callback: Callable[[Event], None]) -> None:
        """
        Unsubscribe from an event.
        
        Args:
            event_name: The name of the event to unsubscribe from.
            callback: The callback function to remove.
        """
        with self._lock:
            if event_name in self._subscribers:
                try:
                    self._subscribers[event_name].remove(callback)
                except ValueError:
                    pass  # Callback not in list
    
    def publish(self, event_name: str, payload: Any = None, source: Optional[str] = None) -> None:
        """
        Publish an event to all subscribers.
        
        Args:
            event_name: The name of the event.
            payload: The data associated with the event.
            source: Optional identifier of the component that published the event.
        """
        event = Event(name=event_name, payload=payload, source=source)
        
        with self._lock:
            # Add to history
            self._history.append(event)
            if len(self._history) > self._max_history:
                self._history.pop(0)
            
            # Get a copy of subscribers to avoid issues if they modify during iteration
            subscribers = self._subscribers.get(event_name, []).copy()
        
        # Call subscribers outside the lock to avoid deadlocks
        for callback in subscribers:
            try:
                callback(event)
            except Exception:
                # Don't let one subscriber's exception break others
                pass
    
    def get_history(self, event_name: Optional[str] = None) -> List[Event]:
        """
        Get event history, optionally filtered by event name.
        
        Args:
            event_name: If provided, only return events with this name.
            
        Returns:
            List of events, most recent last.
        """
        with self._lock:
            if event_name is None:
                return self._history.copy()
            return [e for e in self._history if e.name == event_name]
    
    def clear_history(self) -> None:
        """Clear the event history."""
        with self._lock:
            self._history.clear()


# Global event bus instance
event_bus = EventBus()


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    return event_bus