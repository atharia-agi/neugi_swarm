"""
Real-time steering engine for course-correcting agent execution.

Allows inbound message injection during agent execution without
aborting the current operation. Supports priority-based queuing,
message validation, and steering history tracking.
"""

import logging
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Deque, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class SteeringPriority(int, Enum):
    """Priority levels for steering messages."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class MessageQueuePolicy(str, Enum):
    """Policy for handling queued steering messages."""
    FIFO = "fifo"
    PRIORITY = "priority"
    LATEST_ONLY = "latest_only"


@dataclass
class SteeringMessage:
    """A message injected to steer agent execution."""
    message_id: str
    content: str
    priority: SteeringPriority
    source: str
    timestamp: str
    acknowledged: bool = False
    applied: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "message_id": self.message_id,
            "content": self.content,
            "priority": self.priority.value,
            "source": self.source,
            "timestamp": self.timestamp,
            "acknowledged": self.acknowledged,
            "applied": self.applied,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SteeringMessage":
        """Deserialize from dictionary."""
        return cls(
            message_id=data["message_id"],
            content=data["content"],
            priority=SteeringPriority(data["priority"]),
            source=data["source"],
            timestamp=data["timestamp"],
            acknowledged=data.get("acknowledged", False),
            applied=data.get("applied", False),
            metadata=data.get("metadata", {}),
        )


@dataclass
class SteeringConfig:
    """Configuration for the steering engine."""
    queue_policy: MessageQueuePolicy = MessageQueuePolicy.PRIORITY
    max_queue_size: int = 50
    enable_validation: bool = True
    max_content_length: int = 4096
    allowed_sources: Optional[Set[str]] = None
    rate_limit_per_second: float = 5.0
    auto_acknowledge_timeout_seconds: float = 60.0
    enable_history: bool = True
    max_history_size: int = 500


class SteeringHistory:
    """
    Tracks all steering messages applied to a session.

    Provides a bounded history with search and statistics capabilities.
    """

    def __init__(self, max_size: int = 500) -> None:
        self._entries: Deque[SteeringMessage] = deque(maxlen=max_size)
        self._lock = threading.Lock()

    def add(self, message: SteeringMessage) -> None:
        """Add a steering message to the history."""
        with self._lock:
            self._entries.append(message)

    def get_all(self) -> List[SteeringMessage]:
        """Get all entries in chronological order."""
        with self._lock:
            return list(self._entries)

    def get_applied(self) -> List[SteeringMessage]:
        """Get only applied messages."""
        with self._lock:
            return [m for m in self._entries if m.applied]

    def get_by_source(self, source: str) -> List[SteeringMessage]:
        """Get messages from a specific source."""
        with self._lock:
            return [m for m in self._entries if m.source == source]

    def get_by_priority(self, priority: SteeringPriority) -> List[SteeringMessage]:
        """Get messages with a specific priority."""
        with self._lock:
            return [m for m in self._entries if m.priority == priority]

    def get_recent(self, count: int = 10) -> List[SteeringMessage]:
        """Get the most recent entries."""
        with self._lock:
            entries = list(self._entries)
            return entries[-count:] if len(entries) > count else entries

    def clear(self) -> None:
        """Clear all history entries."""
        with self._lock:
            self._entries.clear()

    def count(self) -> int:
        """Return number of entries."""
        with self._lock:
            return len(self._entries)

    def stats(self) -> Dict[str, Any]:
        """Get statistics about the steering history."""
        with self._lock:
            entries = list(self._entries)
            if not entries:
                return {
                    "total": 0,
                    "applied": 0,
                    "acknowledged": 0,
                    "by_priority": {},
                    "by_source": {},
                }

            by_priority: Dict[str, int] = {}
            by_source: Dict[str, int] = {}

            for entry in entries:
                p = entry.priority.name
                by_priority[p] = by_priority.get(p, 0) + 1
                by_source[entry.source] = by_source.get(entry.source, 0) + 1

            return {
                "total": len(entries),
                "applied": sum(1 for e in entries if e.applied),
                "acknowledged": sum(1 for e in entries if e.acknowledged),
                "by_priority": by_priority,
                "by_source": by_source,
            }


class SteeringEngine:
    """
    Real-time steering engine for course-correcting agent execution.

    Allows external systems to inject steering messages into an active
    session without aborting the current operation. Messages are queued
    according to the configured policy and injected at safe points.

    Usage:
        engine = SteeringEngine(config)
        engine.steer(session, "Shift focus to security analysis", priority=HIGH)
        pending = engine.get_pending()
        for msg in pending:
            apply_steering(msg)
            engine.acknowledge(msg.message_id)
    """

    def __init__(self, config: Optional[SteeringConfig] = None) -> None:
        self.config = config or SteeringConfig()
        self._queue: Deque[SteeringMessage] = deque()
        self._priority_queues: Dict[SteeringPriority, Deque[SteeringMessage]] = {
            p: deque() for p in SteeringPriority
        }
        self._lock = threading.Lock()
        self._history = SteeringHistory(self.config.max_history_size) if self.config.enable_history else None
        self._validators: List[Callable[[SteeringMessage], bool]] = []
        self._rate_timestamps: Deque[float] = deque()
        self._on_steering_applied: List[Callable[[SteeringMessage], None]] = []

    def register_validator(self, validator: Callable[[SteeringMessage], bool]) -> None:
        """
        Register a validation function for steering messages.

        Validators are called before a message is queued. If any validator
        returns False, the message is rejected.
        """
        self._validators.append(validator)

    def on_steering_applied(self, callback: Callable[[SteeringMessage], None]) -> None:
        """Register a callback for when steering messages are applied."""
        self._on_steering_applied.append(callback)

    def steer(
        self,
        content: str,
        source: str = "external",
        priority: SteeringPriority = SteeringPriority.NORMAL,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[SteeringMessage]:
        """
        Inject a steering message into the queue.

        Args:
            content: The steering instruction content.
            source: Identifier for the message source.
            priority: Priority level for queue ordering.
            metadata: Optional additional metadata.

        Returns:
            The created SteeringMessage if accepted, None if rejected.
        """
        if not self._check_rate_limit():
            logger.warning("Steering rate limit exceeded for source=%s", source)
            return None

        if len(content) > self.config.max_content_length:
            logger.warning(
                "Steering message too long: %d > %d",
                len(content),
                self.config.max_content_length,
            )
            return None

        if self.config.allowed_sources and source not in self.config.allowed_sources:
            logger.warning("Steering source not allowed: %s", source)
            return None

        message = SteeringMessage(
            message_id=str(uuid.uuid4())[:12],
            content=content,
            priority=priority,
            source=source,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata=metadata or {},
        )

        if self.config.enable_validation:
            if not self._validate(message):
                logger.warning("Steering message rejected by validator: %s", message.message_id)
                return None

        with self._lock:
            if len(self._queue) >= self.config.max_queue_size:
                self._evict_lowest_priority()

            self._queue.append(message)
            self._priority_queues[priority].append(message)

            if self._history:
                self._history.add(message)

            logger.debug(
                "Steering message queued: %s (priority=%s, source=%s)",
                message.message_id,
                priority.name,
                source,
            )

        return message

    def get_pending(self) -> List[SteeringMessage]:
        """
        Get pending steering messages according to the queue policy.

        Returns messages in the order determined by the configured policy.
        """
        with self._lock:
            if not self._queue:
                return []

            if self.config.queue_policy == MessageQueuePolicy.FIFO:
                return list(self._queue)

            elif self.config.queue_policy == MessageQueuePolicy.PRIORITY:
                result = []
                for priority in sorted(SteeringPriority, reverse=True):
                    result.extend(list(self._priority_queues[priority]))
                return result

            elif self.config.queue_policy == MessageQueuePolicy.LATEST_ONLY:
                if self._queue:
                    return [self._queue[-1]]
                return []

            return list(self._queue)

    def get_next(self) -> Optional[SteeringMessage]:
        """
        Get the next steering message to apply (and remove from queue).

        Returns the highest-priority message according to the queue policy.
        """
        with self._lock:
            if not self._queue:
                return None

            if self.config.queue_policy == MessageQueuePolicy.FIFO:
                return self._queue.popleft()

            elif self.config.queue_policy == MessageQueuePolicy.PRIORITY:
                for priority in sorted(SteeringPriority, reverse=True):
                    if self._priority_queues[priority]:
                        msg = self._priority_queues[priority].popleft()
                        self._queue.remove(msg)
                        return msg

            elif self.config.queue_policy == MessageQueuePolicy.LATEST_ONLY:
                msg = self._queue.pop()
                self._priority_queues[msg.priority].remove(msg)
                return msg

            return self._queue.popleft() if self._queue else None

    def acknowledge(self, message_id: str) -> bool:
        """
        Mark a steering message as acknowledged.

        Returns True if the message was found and acknowledged.
        """
        with self._lock:
            for msg in self._queue:
                if msg.message_id == message_id:
                    msg.acknowledged = True
                    return True
            return False

    def mark_applied(self, message_id: str) -> bool:
        """
        Mark a steering message as applied.

        Returns True if the message was found and marked.
        """
        with self._lock:
            for msg in self._queue:
                if msg.message_id == message_id:
                    msg.applied = True
                    msg.acknowledged = True
                    for callback in self._on_steering_applied:
                        try:
                            callback(msg)
                        except Exception:
                            logger.exception("Error in steering applied callback")
                    return True
            return False

    def clear(self) -> int:
        """Clear all pending steering messages. Returns count cleared."""
        with self._lock:
            count = len(self._queue)
            self._queue.clear()
            for pq in self._priority_queues.values():
                pq.clear()
            return count

    def check_steer(self, message: SteeringMessage) -> Tuple[bool, Optional[str]]:
        """
        Validate a steering message before injection.

        Args:
            message: The steering message to validate.

        Returns:
            Tuple of (is_valid, rejection_reason).
        """
        if not self.config.enable_validation:
            return True, None

        if len(message.content) > self.config.max_content_length:
            return False, f"Content exceeds max length ({self.config.max_content_length})"

        if self.config.allowed_sources and message.source not in self.config.allowed_sources:
            return False, f"Source '{message.source}' not in allowed sources"

        for validator in self._validators:
            try:
                if not validator(message):
                    return False, "Rejected by custom validator"
            except Exception as e:
                logger.exception("Validator error: %s", e)
                return False, f"Validator error: {e}"

        return True, None

    def get_history(self) -> Optional[SteeringHistory]:
        """Get the steering history tracker."""
        return self._history

    def has_pending(self) -> bool:
        """Check if there are pending steering messages."""
        with self._lock:
            return len(self._queue) > 0

    def pending_count(self) -> int:
        """Get the number of pending steering messages."""
        with self._lock:
            return len(self._queue)

    def _validate(self, message: SteeringMessage) -> bool:
        """Run all validators on a message."""
        valid, _ = self.check_steer(message)
        return valid

    def _check_rate_limit(self) -> bool:
        """Check if the rate limit allows a new message."""
        now = time.monotonic()
        window_start = now - 1.0

        with self._lock:
            while self._rate_timestamps and self._rate_timestamps[0] < window_start:
                self._rate_timestamps.popleft()

            if len(self._rate_timestamps) >= self.config.rate_limit_per_second:
                return False

            self._rate_timestamps.append(now)
            return True

    def _evict_lowest_priority(self) -> None:
        """Remove the lowest-priority message to make room."""
        for priority in sorted(SteeringPriority):
            if self._priority_queues[priority]:
                msg = self._priority_queues[priority].popleft()
                self._queue.remove(msg)
                logger.debug(
                    "Evicted low-priority steering message: %s",
                    msg.message_id,
                )
                return

    def get_stats(self) -> Dict[str, Any]:
        """Get steering engine statistics."""
        with self._lock:
            by_priority = {}
            for priority, queue in self._priority_queues.items():
                if queue:
                    by_priority[priority.name] = len(queue)

            stats = {
                "pending": len(self._queue),
                "by_priority": by_priority,
                "queue_policy": self.config.queue_policy.value,
                "max_queue_size": self.config.max_queue_size,
                "rate_limit": self.config.rate_limit_per_second,
            }

            if self._history:
                stats["history"] = self._history.stats()

            return stats

