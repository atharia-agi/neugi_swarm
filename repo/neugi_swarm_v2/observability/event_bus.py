"""
Event Bus for NEUGI Observability.

Provides a simple event bus system for decoupled communication between
components. Allows publishing and subscribing to events with optional
filtering, history, middleware support, and SQLite persistence.

Thread-safe implementation using threading.Lock.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
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
    A simple thread-safe event bus with optional SQLite persistence.
    
    Example:
        bus = EventBus()
        
        def handler(event):
            print(f"Received {event.name}: {event.payload}")
            
        bus.subscribe("tool_call", handler)
        bus.publish("tool_call", {"tool": "web_search", "query": "hello"})
    """
    
    def __init__(self, max_history: int = 1000, persist_path: Optional[str] = None):
        self._subscribers: Dict[str, List[Callable[[Event], None]]] = defaultdict(list)
        self._middleware: List[Callable[[Event], None]] = []
        self._history: List[Event] = []
        self._max_history = max_history
        self._lock = threading.RLock()
        self._persist_path: Optional[str] = persist_path
        self._db_conn: Optional[sqlite3.Connection] = None
        if persist_path:
            self._init_persistence()
    
    def subscribe(self, event_name: str, callback: Callable[[Event], None]) -> None:
        """
        Subscribe to an event.
        
        Args:
            event_name: The name of the event to subscribe to.
            callback: A function that takes an Event object.
        """
        with self._lock:
            self._subscribers[event_name].append(callback)
    
    def add_middleware(self, middleware: Callable[[Event], None]) -> None:
        """
        Add middleware that will be called for every published event.
        
        Args:
            middleware: A function that takes an Event object.
        """
        with self._lock:
            self._middleware.append(middleware)
    
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
            
            # Get copies to avoid issues if they modify during iteration
            subscribers = self._subscribers.get(event_name, []).copy()
            middleware = self._middleware.copy()
        
        # Persist event (fire-and-forget, non-blocking)
        self._persist_event(event)
        
        # Call middleware first
        for mw in middleware:
            try:
                mw(event)
            except Exception:
                # Don't let one middleware's exception break others
                pass
        
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
        """Clear the event history and persisted storage."""
        with self._lock:
            self._history.clear()
        if self._db_conn:
            try:
                self._db_conn.execute("DELETE FROM events")
                self._db_conn.commit()
            except Exception:
                pass

    def _init_persistence(self) -> None:
        """Initialize SQLite persistence for events."""
        try:
            db_path = Path(self._persist_path)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self._db_conn = sqlite3.connect(str(db_path), check_same_thread=False)
            self._db_conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    payload TEXT,
                    source TEXT,
                    timestamp TEXT NOT NULL
                )
            """)
            self._db_conn.execute("CREATE INDEX IF NOT EXISTS idx_event_name ON events(name)")
            self._db_conn.execute("CREATE INDEX IF NOT EXISTS idx_event_ts ON events(timestamp)")
            self._db_conn.commit()
        except Exception as e:
            self._db_conn = None
            import logging
            logging.getLogger(__name__).warning("Event bus persistence init failed: %s", e)

    def _persist_event(self, event: Event) -> None:
        """Write an event to SQLite."""
        if not self._db_conn:
            return
        try:
            self._db_conn.execute(
                "INSERT INTO events (name, payload, source, timestamp) VALUES (?, ?, ?, ?)",
                (event.name, json.dumps(event.payload) if event.payload else None,
                 event.source, event.timestamp.isoformat())
            )
            self._db_conn.commit()
        except Exception:
            pass

    def set_persistence(self, persist_path: str) -> None:
        """Enable persistence with the given database path."""
        with self._lock:
            self._persist_path = persist_path
            self._init_persistence()

    def get_persisted_events(self, event_name: Optional[str] = None,
                              limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Retrieve persisted events from SQLite."""
        if not self._db_conn:
            return []
        try:
            if event_name:
                cursor = self._db_conn.execute(
                    "SELECT name, payload, source, timestamp FROM events WHERE name = ? ORDER BY id DESC LIMIT ? OFFSET ?",
                    (event_name, limit, offset)
                )
            else:
                cursor = self._db_conn.execute(
                    "SELECT name, payload, source, timestamp FROM events ORDER BY id DESC LIMIT ? OFFSET ?",
                    (limit, offset)
                )
            return [
                {
                    "name": row[0],
                    "payload": json.loads(row[1]) if row[1] else None,
                    "source": row[2],
                    "timestamp": row[3],
                }
                for row in cursor.fetchall()
            ]
        except Exception:
            return []


# Global event bus instance (persistence disabled by default)
event_bus = EventBus()


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    return event_bus


def setup_event_bus_persistence(db_path: str) -> EventBus:
    """Enable persistence on the global event bus and return it."""
    bus = get_event_bus()
    bus.set_persistence(db_path)
    return bus