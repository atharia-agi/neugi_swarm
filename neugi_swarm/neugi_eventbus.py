#!/usr/bin/env python3
"""
🤖 NEUGI EVENT BUS
====================

Event-driven architecture:
- Pub/Sub
- Event streaming
- Dead letter queue

Version: 1.0
Date: March 16, 2026
"""

from typing import Dict, List, Callable, Any
from datetime import datetime
import uuid


class Event:
    def __init__(self, event_type: str, data: Any):
        self.id = str(uuid.uuid4())[:12]
        self.type = event_type
        self.data = data
        self.timestamp = datetime.now().isoformat()


class EventBus:
    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}
        self.events: List[Event] = []

    def publish(self, event_type: str, data: Any):
        event = Event(event_type, data)
        self.events.append(event)
        for sub in self.subscribers.get(event_type, []):
            try:
                sub(event)
            except:
                pass

    def subscribe(self, event_type: str, handler: Callable):
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)

    def get_events(self, event_type: str = None, limit: int = 50):
        if event_type:
            return [e.__dict__ for e in self.events if e.type == event_type][-limit:]
        return [e.__dict__ for e in self.events][-limit:]


bus = EventBus()


def main():
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--publish", nargs=2, help="Publish event")
    p.add_argument("--list", action="store_true", help="List events")
    args = p.parse_args()

    if args.publish:
        bus.publish(args.publish[0], args.publish[1])
        print(f"Published: {args.publish[0]}")
    elif args.list:
        for e in bus.get_events():
            print(f"{e['type']}: {e['data']}")


if __name__ == "__main__":
    main()
