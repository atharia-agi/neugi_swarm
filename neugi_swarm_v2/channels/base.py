"""
Channel abstraction layer providing unified interfaces for all messaging platforms.

Defines base classes for channels, message types, user identities, conversation types,
message formatting, channel capabilities, and health monitoring.
"""

from __future__ import annotations

import enum
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


class MessageType(enum.Enum):
    """Supported message content types across all channels."""

    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    AUDIO = "audio"
    VIDEO = "video"
    REACTION = "reaction"
    LOCATION = "location"
    CONTACT = "contact"
    STICKER = "sticker"
    POLL = "poll"
    SYSTEM = "system"
    COMMAND = "command"


class ChannelType(enum.Enum):
    """Messaging platform types."""

    TELEGRAM = "telegram"
    DISCORD = "discord"
    SLACK = "slack"
    WHATSAPP = "whatsapp"


class ConversationType(enum.Enum):
    """Conversation context types."""

    DM = "dm"
    GROUP = "group"
    CHANNEL = "channel"
    THREAD = "thread"
    BROADCAST = "broadcast"


class MessageFormat(enum.Enum):
    """Message formatting options supported by channels."""

    PLAIN = "plain"
    MARKDOWN = "markdown"
    MARKDOWN_V2 = "markdown_v2"
    HTML = "html"
    RICH_TEXT = "rich_text"


class ChannelCapability(enum.Enum):
    """Features that channels may or may not support."""

    SEND_TEXT = "send_text"
    SEND_IMAGE = "send_image"
    SEND_FILE = "send_file"
    SEND_AUDIO = "send_audio"
    SEND_VIDEO = "send_video"
    SEND_LOCATION = "send_location"
    SEND_POLL = "send_poll"
    SEND_STICKER = "send_sticker"
    INLINE_KEYBOARD = "inline_keyboard"
    REPLY_KEYBOARD = "reply_keyboard"
    REACTIONS = "reactions"
    THREADS = "threads"
    EMBEDS = "embeds"
    SLASH_COMMANDS = "slash_commands"
    INTERACTIVE_COMPONENTS = "interactive_components"
    TEMPLATES = "templates"
    FILE_DOWNLOAD = "file_download"
    FILE_UPLOAD = "file_upload"
    VOICE_MESSAGES = "voice_messages"
    WEBHOOKS = "webhooks"
    LONG_POLLING = "long_polling"
    RATE_LIMITING = "rate_limiting"
    USER_ROLES = "user_roles"
    ADMIN_COMMANDS = "admin_commands"
    MESSAGE_EDITING = "message_editing"
    MESSAGE_DELETION = "message_deletion"
    PINNED_MESSAGES = "pinned_messages"
    BULK_MESSAGES = "bulk_messages"
    SCHEDULED_MESSAGES = "scheduled_messages"


@dataclass
class UserIdentity:
    """Unified user identity across all messaging platforms."""

    id: str
    name: str
    avatar_url: Optional[str] = None
    role: Optional[str] = None
    is_bot: bool = False
    platform_id: Optional[str] = None
    platform_username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    locale: Optional[str] = None
    timezone: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def display_name(self) -> str:
        """Return the best available display name."""
        if self.name:
            return self.name
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        if self.first_name:
            return self.first_name
        if self.platform_username:
            return self.platform_username
        return f"User({self.id})"

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, UserIdentity):
            return NotImplemented
        return self.id == other.id


@dataclass
class Attachment:
    """File attachment associated with a message."""

    url: str
    filename: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration_ms: Optional[int] = None
    local_path: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class IncomingMessage:
    """Normalized incoming message from any channel."""

    message_id: str
    channel_type: ChannelType
    user: UserIdentity
    content: str
    message_type: MessageType = MessageType.TEXT
    conversation_type: ConversationType = ConversationType.DM
    conversation_id: Optional[str] = None
    thread_id: Optional[str] = None
    reply_to_message_id: Optional[str] = None
    attachments: list[Attachment] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    raw_payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_command(self) -> bool:
        """Check if message is a command (starts with / or !)."""
        return self.content.startswith(("/", "!"))

    @property
    def command_name(self) -> Optional[str]:
        """Extract command name from message content."""
        if not self.is_command:
            return None
        parts = self.content.split()
        return parts[0].lstrip("/!").split("@")[0] if parts else None

    @property
    def command_args(self) -> str:
        """Extract command arguments from message content."""
        if not self.is_command:
            return ""
        parts = self.content.split(maxsplit=1)
        return parts[1] if len(parts) > 1 else ""

    def has_attachment_type(self, mime_prefix: str) -> bool:
        """Check if message has an attachment of given MIME type prefix."""
        return any(
            a.mime_type and a.mime_type.startswith(mime_prefix)
            for a in self.attachments
        )


@dataclass
class OutgoingMessage:
    """Normalized outgoing message to any channel."""

    content: str
    channel_type: ChannelType
    conversation_id: str
    message_type: MessageType = MessageType.TEXT
    thread_id: Optional[str] = None
    reply_to_message_id: Optional[str] = None
    format: MessageFormat = MessageFormat.PLAIN
    attachments: list[Attachment] = field(default_factory=list)
    buttons: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize message for transmission."""
        return {
            "content": self.content,
            "channel_type": self.channel_type.value,
            "conversation_id": self.conversation_id,
            "message_type": self.message_type.value,
            "thread_id": self.thread_id,
            "reply_to_message_id": self.reply_to_message_id,
            "format": self.format.value,
            "metadata": self.metadata,
        }


@dataclass
class ChannelHealth:
    """Health status of a channel connection."""

    channel_type: ChannelType
    is_healthy: bool = True
    last_check: float = field(default_factory=time.time)
    response_time_ms: Optional[float] = None
    error_count: int = 0
    last_error: Optional[str] = None
    uptime_seconds: float = 0.0
    messages_sent: int = 0
    messages_received: int = 0
    rate_limit_remaining: Optional[int] = None
    rate_limit_reset: Optional[float] = None
    connection_state: str = "connected"

    @property
    def health_score(self) -> float:
        """Calculate health score from 0.0 to 1.0."""
        if not self.is_healthy:
            return 0.0
        score = 1.0
        if self.error_count > 0:
            score -= min(0.3, self.error_count * 0.1)
        if self.response_time_ms and self.response_time_ms > 1000:
            score -= min(0.2, (self.response_time_ms - 1000) / 5000)
        if self.rate_limit_remaining is not None and self.rate_limit_remaining == 0:
            score -= 0.2
        return max(0.0, score)

    def record_success(self, response_time_ms: float) -> None:
        """Record a successful API call."""
        self.is_healthy = True
        self.response_time_ms = response_time_ms
        self.last_check = time.time()

    def record_error(self, error: str) -> None:
        """Record a failed API call."""
        self.error_count += 1
        self.last_error = error
        self.last_check = time.time()
        if self.error_count >= 10:
            self.is_healthy = False

    def record_rate_limit(self, remaining: int, reset_time: float) -> None:
        """Record rate limit information."""
        self.rate_limit_remaining = remaining
        self.rate_limit_reset = reset_time

    def reset(self) -> None:
        """Reset health counters after reconnection."""
        self.error_count = 0
        self.last_error = None
        self.is_healthy = True
        self.last_check = time.time()


@dataclass
class ChannelCapabilities:
    """Describes what features a specific channel supports."""

    supported_message_types: set[MessageType] = field(default_factory=set)
    supported_formats: set[MessageFormat] = field(default_factory=set)
    max_message_length: int = 4096
    max_attachments: int = 10
    max_attachment_size_mb: int = 50
    supports_threads: bool = False
    supports_reactions: bool = False
    supports_editing: bool = False
    supports_deletion: bool = False
    supports_keyboard: bool = False
    supports_embeds: bool = False
    supports_voice: bool = False
    supports_polls: bool = False
    supports_templates: bool = False
    supports_scheduled: bool = False
    native_rate_limits: dict[str, Any] = field(default_factory=dict)

    def supports(self, capability: ChannelCapability) -> bool:
        """Check if this channel supports a given capability."""
        capability_map = {
            ChannelCapability.SEND_TEXT: MessageType.TEXT in self.supported_message_types,
            ChannelCapability.SEND_IMAGE: MessageType.IMAGE in self.supported_message_types,
            ChannelCapability.SEND_FILE: MessageType.FILE in self.supported_message_types,
            ChannelCapability.SEND_AUDIO: MessageType.AUDIO in self.supported_message_types,
            ChannelCapability.SEND_VIDEO: MessageType.VIDEO in self.supported_message_types,
            ChannelCapability.SEND_LOCATION: MessageType.LOCATION in self.supported_message_types,
            ChannelCapability.SEND_POLL: MessageType.POLL in self.supported_message_types,
            ChannelCapability.SEND_STICKER: MessageType.STICKER in self.supported_message_types,
            ChannelCapability.THREADS: self.supports_threads,
            ChannelCapability.REACTIONS: self.supports_reactions,
            ChannelCapability.EMBEDS: self.supports_embeds,
            ChannelCapability.SLASH_COMMANDS: True,
            ChannelCapability.INTERACTIVE_COMPONENTS: self.supports_keyboard,
            ChannelCapability.TEMPLATES: self.supports_templates,
            ChannelCapability.VOICE_MESSAGES: self.supports_voice,
            ChannelCapability.MESSAGE_EDITING: self.supports_editing,
            ChannelCapability.MESSAGE_DELETION: self.supports_deletion,
            ChannelCapability.SCHEDULED_MESSAGES: self.supports_scheduled,
        }
        return capability_map.get(capability, False)


class BaseChannel(ABC):
    """
    Abstract base class for all messaging channel integrations.

    Each channel implementation must implement the abstract methods to handle
    platform-specific message sending, receiving, and user management while
    conforming to this unified interface.

    Usage:
        class MyChannel(BaseChannel):
            async def _connect(self): ...
            async def _disconnect(self): ...
            async def send_message(self, message): ...
            ...
    """

    def __init__(
        self,
        token: str,
        bot_name: Optional[str] = None,
        health_check_interval: int = 60,
    ) -> None:
        self._token = token
        self._bot_name = bot_name or self.__class__.__name__
        self._is_running = False
        self._health = ChannelHealth(channel_type=self.channel_type)
        self._start_time: Optional[float] = None
        self._health_check_interval = health_check_interval
        self._capabilities = self._build_capabilities()
        self._message_handlers: list = []
        self._error_handlers: list = []
        self._logger = logging.getLogger(f"{__name__}.{self.channel_type.value}")

    @property
    @abstractmethod
    def channel_type(self) -> ChannelType:
        """Return the channel type this implementation handles."""

    @abstractmethod
    async def _connect(self) -> None:
        """Establish connection to the messaging platform."""

    @abstractmethod
    async def _disconnect(self) -> None:
        """Gracefully disconnect from the messaging platform."""

    @abstractmethod
    async def send_message(self, message: OutgoingMessage) -> Optional[str]:
        """
        Send a message to the platform.

        Args:
            message: Normalized outgoing message.

        Returns:
            Platform-specific message ID if successful, None otherwise.
        """

    @abstractmethod
    async def _build_capabilities(self) -> ChannelCapabilities:
        """Build and return the capabilities of this channel."""

    async def start(self) -> None:
        """Start the channel connection and begin receiving messages."""
        if self._is_running:
            self._logger.warning("Channel is already running")
            return

        self._logger.info("Starting %s channel", self.channel_type.value)
        try:
            await self._connect()
            self._is_running = True
            self._start_time = time.time()
            self._health.reset()
            self._logger.info("%s channel started", self.channel_type.value)
        except Exception as exc:
            self._logger.error("Failed to start %s: %s", self.channel_type.value, exc)
            self._health.record_error(str(exc))
            raise

    async def stop(self) -> None:
        """Stop the channel connection gracefully."""
        if not self._is_running:
            return

        self._logger.info("Stopping %s channel", self.channel_type.value)
        try:
            await self._disconnect()
            self._is_running = False
            if self._start_time:
                self._health.uptime_seconds += time.time() - self._start_time
            self._logger.info("%s channel stopped", self.channel_type.value)
        except Exception as exc:
            self._logger.error("Error stopping %s: %s", self.channel_type.value, exc)
            self._health.record_error(str(exc))

    async def receive_message(self, raw_data: dict[str, Any]) -> Optional[IncomingMessage]:
        """
        Convert raw platform data into a normalized IncomingMessage.

        Args:
            raw_data: Raw payload from the platform.

        Returns:
            Normalized message or None if the update should be ignored.
        """
        try:
            message = await self._parse_message(raw_data)
            if message:
                self._health.messages_received += 1
            return message
        except Exception as exc:
            self._logger.error("Error parsing message: %s", exc)
            self._health.record_error(str(exc))
            await self._notify_error_handlers(exc, raw_data)
            return None

    @abstractmethod
    async def _parse_message(self, raw_data: dict[str, Any]) -> Optional[IncomingMessage]:
        """Parse raw platform data into IncomingMessage."""

    async def send_text(
        self,
        conversation_id: str,
        text: str,
        format: MessageFormat = MessageFormat.PLAIN,
        thread_id: Optional[str] = None,
        reply_to_message_id: Optional[str] = None,
    ) -> Optional[str]:
        """Convenience method to send a text message."""
        message = OutgoingMessage(
            content=text,
            channel_type=self.channel_type,
            conversation_id=conversation_id,
            message_type=MessageType.TEXT,
            thread_id=thread_id,
            reply_to_message_id=reply_to_message_id,
            format=format,
        )
        return await self.send_message(message)

    async def send_image(
        self,
        conversation_id: str,
        image_url: str,
        caption: Optional[str] = None,
        thread_id: Optional[str] = None,
    ) -> Optional[str]:
        """Convenience method to send an image."""
        attachment = Attachment(url=image_url)
        message = OutgoingMessage(
            content=caption or "",
            channel_type=self.channel_type,
            conversation_id=conversation_id,
            message_type=MessageType.IMAGE,
            thread_id=thread_id,
            attachments=[attachment],
        )
        return await self.send_message(message)

    async def send_file(
        self,
        conversation_id: str,
        file_url: str,
        filename: Optional[str] = None,
        caption: Optional[str] = None,
        thread_id: Optional[str] = None,
    ) -> Optional[str]:
        """Convenience method to send a file."""
        attachment = Attachment(url=file_url, filename=filename)
        message = OutgoingMessage(
            content=caption or "",
            channel_type=self.channel_type,
            conversation_id=conversation_id,
            message_type=MessageType.FILE,
            thread_id=thread_id,
            attachments=[attachment],
        )
        return await self.send_message(message)

    async def download_file(self, file_id: str, local_path: str) -> bool:
        """
        Download a file from the platform to local storage.

        Args:
            file_id: Platform-specific file identifier.
            local_path: Destination path on local filesystem.

        Returns:
            True if download succeeded.
        """
        self._logger.warning("File download not implemented for %s", self.channel_type.value)
        return False

    async def edit_message(
        self,
        conversation_id: str,
        message_id: str,
        new_content: str,
        format: MessageFormat = MessageFormat.PLAIN,
    ) -> bool:
        """Edit an existing message."""
        self._logger.warning("Message editing not supported on %s", self.channel_type.value)
        return False

    async def delete_message(self, conversation_id: str, message_id: str) -> bool:
        """Delete a message."""
        self._logger.warning("Message deletion not supported on %s", self.channel_type.value)
        return False

    async def get_user(self, user_id: str) -> Optional[UserIdentity]:
        """Fetch user information from the platform."""
        self._logger.warning("User lookup not implemented for %s", self.channel_type.value)
        return None

    async def get_chat_info(self, chat_id: str) -> Optional[dict[str, Any]]:
        """Fetch chat/conversation information."""
        self._logger.warning("Chat info not implemented for %s", self.channel_type.value)
        return None

    async def check_health(self) -> ChannelHealth:
        """
        Perform a health check on the channel connection.

        Returns:
            Current health status with updated metrics.
        """
        start = time.time()
        try:
            await self._health_check()
            elapsed = (time.time() - start) * 1000
            self._health.record_success(elapsed)
        except Exception as exc:
            elapsed = (time.time() - start) * 1000
            self._health.record_error(str(exc))
            self._logger.error("Health check failed: %s", exc)

        if self._start_time:
            self._health.uptime_seconds = time.time() - self._start_time

        return self._health

    @abstractmethod
    async def _health_check(self) -> None:
        """Perform platform-specific health check."""

    def on_message(self, handler) -> None:
        """Register a message handler callback."""
        self._message_handlers.append(handler)

    def on_error(self, handler) -> None:
        """Register an error handler callback."""
        self._error_handlers.append(handler)

    async def _notify_message_handlers(self, message: IncomingMessage) -> None:
        """Notify all registered message handlers."""
        for handler in self._message_handlers:
            try:
                result = handler(message)
                if hasattr(result, "__await__"):
                    await result
            except Exception as exc:
                self._logger.error("Message handler error: %s", exc)

    async def _notify_error_handlers(self, error: Exception, context: Any = None) -> None:
        """Notify all registered error handlers."""
        for handler in self._error_handlers:
            try:
                result = handler(error, context)
                if hasattr(result, "__await__"):
                    await result
            except Exception as exc:
                self._logger.error("Error handler error: %s", exc)

    @property
    def is_running(self) -> bool:
        """Check if the channel is currently running."""
        return self._is_running

    @property
    def health(self) -> ChannelHealth:
        """Get current health status."""
        return self._health

    @property
    def capabilities(self) -> ChannelCapabilities:
        """Get channel capabilities."""
        return self._capabilities

    def get_stats(self) -> dict[str, Any]:
        """Get channel statistics."""
        return {
            "channel_type": self.channel_type.value,
            "is_running": self._is_running,
            "uptime_seconds": self._health.uptime_seconds,
            "messages_sent": self._health.messages_sent,
            "messages_received": self._health.messages_received,
            "error_count": self._health.error_count,
            "health_score": self._health.health_score,
            "connection_state": self._health.connection_state,
        }

    def __repr__(self) -> str:
        status = "running" if self._is_running else "stopped"
        return f"{self.__class__.__name__}({self.channel_type.value}, {status})"
