"""
NEUGI v2 Channel Integrations - Unified messaging platform abstraction.

Supports Telegram, Discord, Slack, and WhatsApp with a common interface
for message handling, user management, and channel orchestration.
"""

from .base import (
    BaseChannel,
    ChannelCapability,
    ChannelHealth,
    ChannelType,
    ConversationType,
    MessageFormat,
    MessageType,
    UserIdentity,
)
from .channel_manager import ChannelManager, ChannelStats, ChannelStatus
from .discord import DiscordChannel
from .slack import SlackChannel
from .telegram import TelegramChannel
from .whatsapp import WhatsAppChannel

__all__ = [
    "BaseChannel",
    "ChannelCapability",
    "ChannelHealth",
    "ChannelManager",
    "ChannelStats",
    "ChannelStatus",
    "ChannelType",
    "ConversationType",
    "DiscordChannel",
    "MessageFormat",
    "MessageType",
    "SlackChannel",
    "TelegramChannel",
    "UserIdentity",
    "WhatsAppChannel",
]
