"""
Channel manager for NEUGI v2 - orchestrates multiple messaging channels.

Provides multi-channel management, message routing, channel-specific formatting,
health monitoring, enable/disable controls, statistics, and a unified message queue.
"""

from __future__ import annotations

import asyncio
import enum
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .base import (
    BaseChannel,
    ChannelHealth,
    ChannelType,
    IncomingMessage,
    MessageFormat,
    MessageType,
    OutgoingMessage,
)

logger = logging.getLogger(__name__)


class ChannelStatus(enum.Enum):
    """Channel operational status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"
    CONNECTING = "connecting"
    DISCONNECTING = "disconnecting"


@dataclass
class ChannelStats:
    """Statistics for a single channel."""

    channel_type: ChannelType
    status: ChannelStatus = ChannelStatus.INACTIVE
    messages_sent: int = 0
    messages_received: int = 0
    errors: int = 0
    last_message_time: Optional[float] = None
    last_error_time: Optional[float] = None
    last_error: Optional[str] = None
    uptime_seconds: float = 0.0
    avg_response_time_ms: float = 0.0
    health_score: float = 1.0

    @property
    def total_messages(self) -> int:
        """Total messages processed."""
        return self.messages_sent + self.messages_received

    def to_dict(self) -> dict[str, Any]:
        """Serialize stats to dict."""
        return {
            "channel_type": self.channel_type.value,
            "status": self.status.value,
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "total_messages": self.total_messages,
            "errors": self.errors,
            "health_score": self.health_score,
            "uptime_seconds": self.uptime_seconds,
            "avg_response_time_ms": self.avg_response_time_ms,
        }


@dataclass
class QueuedMessage:
    """Message in the unified queue."""

    message: OutgoingMessage
    priority: int = 0
    queued_at: float = field(default_factory=time.time)
    attempts: int = 0
    max_attempts: int = 3
    status: str = "pending"
    error: Optional[str] = None


class ChannelManager:
    """
    Orchestrates multiple messaging channels simultaneously.

    Manages channel lifecycle, routes messages to the correct channel,
    monitors health, collects statistics, and provides a unified message queue
    for reliable delivery.

    Usage:
        manager = ChannelManager()
        manager.register_channel("telegram", TelegramChannel(token="..."))
        manager.register_channel("discord", DiscordChannel(token="..."))
        await manager.start_all()
    """

    def __init__(
        self,
        max_queue_size: int = 10000,
        queue_retry_delay: float = 5.0,
        health_check_interval: int = 60,
    ) -> None:
        self._channels: dict[str, BaseChannel] = {}
        self._channel_keys: dict[ChannelType, str] = {}
        self._stats: dict[str, ChannelStats] = {}
        self._status: dict[str, ChannelStatus] = {}
        self._enabled: dict[str, bool] = {}
        self._message_queue: asyncio.Queue[QueuedMessage] = asyncio.Queue(
            maxsize=max_queue_size
        )
        self._max_queue_size = max_queue_size
        self._queue_retry_delay = queue_retry_delay
        self._health_check_interval = health_check_interval
        self._message_handlers: list[Callable] = []
        self._error_handlers: list[Callable] = []
        self._format_overrides: dict[ChannelType, MessageFormat] = {}
        self._routing_rules: list[Callable] = []
        self._health_task: Optional[asyncio.Task] = None
        self._queue_task: Optional[asyncio.Task] = None
        self._is_running = False
        self._start_time: Optional[float] = None
        self._channel_health_cache: dict[str, ChannelHealth] = {}
        self._logger = logging.getLogger(__name__)

    def register_channel(self, key: str, channel: BaseChannel) -> None:
        """
        Register a channel with the manager.

        Args:
            key: Unique identifier for this channel instance.
            channel: Channel instance to register.
        """
        if key in self._channels:
            self._logger.warning("Replacing existing channel: %s", key)

        self._channels[key] = channel
        self._channel_keys[channel.channel_type] = key
        self._stats[key] = ChannelStats(channel_type=channel.channel_type)
        self._status[key] = ChannelStatus.INACTIVE
        self._enabled[key] = True

        channel.on_message(self._on_channel_message)
        channel.on_error(self._on_channel_error)

        self._logger.info(
            "Registered channel: %s (%s)", key, channel.channel_type.value
        )

    def unregister_channel(self, key: str) -> bool:
        """
        Unregister a channel from the manager.

        Args:
            key: Channel identifier to remove.

        Returns:
            True if channel was found and removed.
        """
        if key not in self._channels:
            return False

        channel = self._channels.pop(key)
        self._channel_keys.pop(channel.channel_type, None)
        self._stats.pop(key, None)
        self._status.pop(key, None)
        self._enabled.pop(key, None)
        self._channel_health_cache.pop(key, None)

        self._logger.info("Unregistered channel: %s", key)
        return True

    def get_channel(self, key: str) -> Optional[BaseChannel]:
        """Get a channel by its key."""
        return self._channels.get(key)

    def get_channel_by_type(self, channel_type: ChannelType) -> Optional[BaseChannel]:
        """Get a channel by its type."""
        key = self._channel_keys.get(channel_type)
        if key:
            return self._channels.get(key)
        return None

    def get_all_channels(self) -> dict[str, BaseChannel]:
        """Get all registered channels."""
        return dict(self._channels)

    def enable_channel(self, key: str) -> bool:
        """Enable a channel for message processing."""
        if key not in self._channels:
            return False
        self._enabled[key] = True
        self._logger.info("Enabled channel: %s", key)
        return True

    def disable_channel(self, key: str) -> bool:
        """Disable a channel (stops processing but keeps connection)."""
        if key not in self._channels:
            return False
        self._enabled[key] = False
        self._logger.info("Disabled channel: %s", key)
        return True

    def is_channel_enabled(self, key: str) -> bool:
        """Check if a channel is enabled."""
        return self._enabled.get(key, False)

    def set_format_override(self, channel_type: ChannelType, format: MessageFormat) -> None:
        """Set a default message format for a channel type."""
        self._format_overrides[channel_type] = format

    def add_routing_rule(self, rule: Callable[[IncomingMessage], Optional[str]]) -> None:
        """
        Add a custom routing rule.

        Args:
            rule: Function that takes a message and returns a channel key,
                  or None to use default routing.
        """
        self._routing_rules.append(rule)

    async def start_all(self) -> None:
        """Start all registered channels."""
        if self._is_running:
            self._logger.warning("Channel manager is already running")
            return

        self._is_running = True
        self._start_time = time.time()

        tasks = []
        for key, channel in self._channels.items():
            if self._enabled.get(key, True):
                self._status[key] = ChannelStatus.CONNECTING
                tasks.append(self._start_channel(key, channel))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for key, result in zip(self._channels.keys(), results):
                if isinstance(result, Exception):
                    self._status[key] = ChannelStatus.ERROR
                    self._logger.error("Failed to start channel %s: %s", key, result)
                else:
                    self._status[key] = ChannelStatus.ACTIVE

        self._health_task = asyncio.create_task(self._health_monitor_loop())
        self._queue_task = asyncio.create_task(self._queue_processor_loop())

        self._logger.info("Channel manager started with %d channels", len(self._channels))

    async def stop_all(self) -> None:
        """Stop all channels gracefully."""
        if not self._is_running:
            return

        self._is_running = False

        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass

        if self._queue_task:
            self._queue_task.cancel()
            try:
                await self._queue_task
            except asyncio.CancelledError:
                pass

        tasks = []
        for key, channel in self._channels.items():
            self._status[key] = ChannelStatus.DISCONNECTING
            tasks.append(self._stop_channel(key, channel))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        self._logger.info("Channel manager stopped")

    async def _start_channel(self, key: str, channel: BaseChannel) -> None:
        """Start a single channel."""
        try:
            await channel.start()
            self._status[key] = ChannelStatus.ACTIVE
            self._stats[key].status = ChannelStatus.ACTIVE
        except Exception as exc:
            self._status[key] = ChannelStatus.ERROR
            self._stats[key].status = ChannelStatus.ERROR
            self._stats[key].errors += 1
            self._stats[key].last_error = str(exc)
            self._stats[key].last_error_time = time.time()
            raise

    async def _stop_channel(self, key: str, channel: BaseChannel) -> None:
        """Stop a single channel."""
        try:
            await channel.stop()
            self._status[key] = ChannelStatus.INACTIVE
            self._stats[key].status = ChannelStatus.INACTIVE
        except Exception as exc:
            self._logger.error("Error stopping channel %s: %s", key, exc)
            self._status[key] = ChannelStatus.ERROR

    async def start_channel(self, key: str) -> bool:
        """Start a specific channel."""
        channel = self._channels.get(key)
        if not channel:
            return False

        try:
            await channel.start()
            self._status[key] = ChannelStatus.ACTIVE
            self._stats[key].status = ChannelStatus.ACTIVE
            self._enabled[key] = True
            return True
        except Exception as exc:
            self._status[key] = ChannelStatus.ERROR
            self._logger.error("Failed to start channel %s: %s", key, exc)
            return False

    async def stop_channel(self, key: str) -> bool:
        """Stop a specific channel."""
        channel = self._channels.get(key)
        if not channel:
            return False

        try:
            await channel.stop()
            self._status[key] = ChannelStatus.INACTIVE
            self._stats[key].status = ChannelStatus.INACTIVE
            return True
        except Exception as exc:
            self._logger.error("Failed to stop channel %s: %s", key, exc)
            return False

    async def send_message(
        self,
        channel_key: str,
        message: OutgoingMessage,
        priority: int = 0,
    ) -> Optional[str]:
        """
        Send a message through a specific channel.

        Args:
            channel_key: Channel identifier.
            message: Message to send.
            priority: Queue priority (higher = more urgent).

        Returns:
            Platform message ID if successful.
        """
        channel = self._channels.get(channel_key)
        if not channel:
            self._logger.error("Channel not found: %s", channel_key)
            return None

        if not self._enabled.get(channel_key, False):
            self._logger.warning("Channel disabled: %s", channel_key)
            return None

        if not channel.is_running:
            self._logger.warning("Channel not running: %s", channel_key)
            return None

        if message.format == MessageFormat.PLAIN:
            override = self._format_overrides.get(channel.channel_type)
            if override:
                message.format = override

        try:
            msg_id = await channel.send_message(message)
            if msg_id:
                self._stats[channel_key].messages_sent += 1
                self._stats[channel_key].last_message_time = time.time()
            return msg_id
        except Exception as exc:
            self._logger.error("Failed to send via %s: %s", channel_key, exc)
            self._stats[channel_key].errors += 1
            self._stats[channel_key].last_error = str(exc)
            self._stats[channel_key].last_error_time = time.time()
            return None

    async def queue_message(
        self,
        message: OutgoingMessage,
        priority: int = 0,
        max_attempts: int = 3,
    ) -> bool:
        """
        Add a message to the unified queue for delivery.

        Args:
            message: Message to queue.
            priority: Queue priority.
            max_attempts: Maximum delivery attempts.

        Returns:
            True if message was queued successfully.
        """
        try:
            queued = QueuedMessage(
                message=message,
                priority=priority,
                max_attempts=max_attempts,
            )
            self._message_queue.put_nowait(queued)
            return True
        except asyncio.QueueFull:
            self._logger.error("Message queue is full (%d)", self._max_queue_size)
            return False

    async def broadcast(
        self,
        message: OutgoingMessage,
        exclude: Optional[list[str]] = None,
    ) -> dict[str, Optional[str]]:
        """
        Send a message to all active channels.

        Args:
            message: Message to broadcast.
            exclude: List of channel keys to skip.

        Returns:
            Dict mapping channel keys to message IDs.
        """
        exclude = exclude or []
        results: dict[str, Optional[str]] = {}

        tasks = []
        for key, channel in self._channels.items():
            if key in exclude:
                continue
            if not self._enabled.get(key, False):
                continue
            if not channel.is_running:
                continue

            msg = OutgoingMessage(
                content=message.content,
                channel_type=channel.channel_type,
                conversation_id=message.conversation_id,
                message_type=message.message_type,
                format=message.format,
                metadata=message.metadata,
            )
            tasks.append((key, self.send_message(key, msg)))

        for key, task in tasks:
            try:
                results[key] = await task
            except Exception as exc:
                self._logger.error("Broadcast to %s failed: %s", key, exc)
                results[key] = None

        return results

    async def route_message(self, message: IncomingMessage) -> Optional[str]:
        """
        Route an incoming message to the appropriate handler.

        Applies custom routing rules first, then falls back to default.

        Args:
            message: Incoming message to route.

        Returns:
            Channel key that should handle this message.
        """
        for rule in self._routing_rules:
            try:
                target = rule(message)
                if target:
                    return target
            except Exception as exc:
                self._logger.error("Routing rule error: %s", exc)

        return self._channel_keys.get(message.channel_type)

    async def _on_channel_message(self, message: IncomingMessage) -> None:
        """Handle message from any channel."""
        channel_key = self._channel_keys.get(message.channel_type)
        if channel_key:
            self._stats[channel_key].messages_received += 1
            self._stats[channel_key].last_message_time = time.time()

        for handler in self._message_handlers:
            try:
                result = handler(message)
                if hasattr(result, "__await__"):
                    await result
            except Exception as exc:
                self._logger.error("Message handler error: %s", exc)

    async def _on_channel_error(self, error: Exception, context: Any = None) -> None:
        """Handle error from any channel."""
        for handler in self._error_handlers:
            try:
                result = handler(error, context)
                if hasattr(result, "__await__"):
                    await result
            except Exception as exc:
                self._logger.error("Error handler error: %s", exc)

    def on_message(self, handler: Callable) -> None:
        """Register a global message handler."""
        self._message_handlers.append(handler)

    def on_error(self, handler: Callable) -> None:
        """Register a global error handler."""
        self._error_handlers.append(handler)

    async def _health_monitor_loop(self) -> None:
        """Periodically check health of all channels."""
        while self._is_running:
            try:
                await asyncio.sleep(self._health_check_interval)

                for key, channel in self._channels.items():
                    if not self._enabled.get(key, False):
                        continue

                    try:
                        health = await channel.check_health()
                        self._channel_health_cache[key] = health
                        self._stats[key].health_score = health.health_score
                        self._stats[key].avg_response_time_ms = (
                            health.response_time_ms or 0
                        )

                        if not health.is_healthy:
                            if self._status[key] != ChannelStatus.ERROR:
                                self._status[key] = ChannelStatus.ERROR
                                self._logger.warning(
                                    "Channel %s health degraded: %s", key, health.last_error
                                )
                        else:
                            if self._status[key] == ChannelStatus.ERROR:
                                self._status[key] = ChannelStatus.ACTIVE

                        if health.rate_limit_remaining is not None and health.rate_limit_remaining == 0:
                            self._status[key] = ChannelStatus.RATE_LIMITED

                    except Exception as exc:
                        self._logger.error("Health check failed for %s: %s", key, exc)
                        self._status[key] = ChannelStatus.ERROR
                        self._stats[key].errors += 1

            except asyncio.CancelledError:
                break
            except Exception as exc:
                self._logger.error("Health monitor error: %s", exc)

    async def _queue_processor_loop(self) -> None:
        """Process queued messages."""
        while self._is_running:
            try:
                queued = await self._message_queue.get()

                channel_key = self._channel_keys.get(queued.message.channel_type)
                if not channel_key:
                    self._logger.error("No channel for type: %s", queued.message.channel_type)
                    queued.status = "failed"
                    queued.error = "No channel registered"
                    self._message_queue.task_done()
                    continue

                if not self._enabled.get(channel_key, False):
                    queued.status = "pending"
                    await asyncio.sleep(self._queue_retry_delay)
                    await self._message_queue.put(queued)
                    self._message_queue.task_done()
                    continue

                queued.attempts += 1
                queued.status = "sending"

                try:
                    msg_id = await self._channels[channel_key].send_message(queued.message)
                    if msg_id:
                        queued.status = "sent"
                        self._stats[channel_key].messages_sent += 1
                    else:
                        raise Exception("Send returned None")
                except Exception as exc:
                    queued.error = str(exc)
                    if queued.attempts >= queued.max_attempts:
                        queued.status = "failed"
                        self._logger.error(
                            "Queue message failed after %d attempts: %s",
                            queued.attempts, exc,
                        )
                    else:
                        queued.status = "retry"
                        await asyncio.sleep(self._queue_retry_delay * queued.attempts)
                        await self._message_queue.put(queued)

                self._message_queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as exc:
                self._logger.error("Queue processor error: %s", exc)
                await asyncio.sleep(1)

    def get_channel_health(self, key: str) -> Optional[ChannelHealth]:
        """Get cached health for a channel."""
        return self._channel_health_cache.get(key)

    def get_all_health(self) -> dict[str, ChannelHealth]:
        """Get cached health for all channels."""
        return dict(self._channel_health_cache)

    def get_stats(self, key: Optional[str] = None) -> Any:
        """
        Get statistics.

        Args:
            key: Channel key, or None for all channels.

        Returns:
            ChannelStats for a single channel, or dict of all stats.
        """
        if key:
            return self._stats.get(key)
        return {k: v.to_dict() for k, v in self._stats.items()}

    def get_status(self, key: Optional[str] = None) -> Any:
        """
        Get channel status.

        Args:
            key: Channel key, or None for all channels.
        """
        if key:
            return self._status.get(key, ChannelStatus.INACTIVE)
        return dict(self._status)

    def get_queue_size(self) -> int:
        """Get current queue size."""
        return self._message_queue.qsize()

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of all channels."""
        total_sent = sum(s.messages_sent for s in self._stats.values())
        total_received = sum(s.messages_received for s in self._stats.values())
        total_errors = sum(s.errors for s in self._stats.values())

        active_channels = sum(
            1 for s in self._status.values() if s == ChannelStatus.ACTIVE
        )

        return {
            "total_channels": len(self._channels),
            "active_channels": active_channels,
            "total_messages_sent": total_sent,
            "total_messages_received": total_received,
            "total_errors": total_errors,
            "queue_size": self._message_queue.qsize(),
            "is_running": self._is_running,
            "uptime_seconds": time.time() - self._start_time if self._start_time else 0,
            "channels": {k: v.to_dict() for k, v in self._stats.items()},
        }

    def format_for_channel(
        self, channel_type: ChannelType, text: str
    ) -> tuple[str, MessageFormat]:
        """
        Format text appropriately for a specific channel.

        Args:
            channel_type: Target channel type.
            text: Text to format.

        Returns:
            Tuple of (formatted_text, format_type).
        """
        override = self._format_overrides.get(channel_type)
        if override:
            return text, override

        format_map = {
            ChannelType.TELEGRAM: MessageFormat.HTML,
            ChannelType.DISCORD: MessageFormat.PLAIN,
            ChannelType.SLACK: MessageFormat.RICH_TEXT,
            ChannelType.WHATSAPP: MessageFormat.PLAIN,
        }

        return text, format_map.get(channel_type, MessageFormat.PLAIN)

    def __repr__(self) -> str:
        active = sum(1 for s in self._status.values() if s == ChannelStatus.ACTIVE)
        return f"ChannelManager({active}/{len(self._channels)} active)"
