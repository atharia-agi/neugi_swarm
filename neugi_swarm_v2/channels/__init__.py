"""
NEUGI v2 Channel Integrations - Unified messaging platform abstraction.

Supports Telegram, Discord, Slack, and WhatsApp with a common interface
for message handling, user management, and channel orchestration.
"""

from channels.base import (
    BaseChannel,
    ChannelCapability,
    ChannelHealth,
    ChannelType,
    ConversationType,
    MessageFormat,
    MessageType,
    UserIdentity,
)
from channels.channel_manager import ChannelManager, ChannelStats, ChannelStatus
from channels.discord import DiscordChannel
from channels.slack import SlackChannel
from channels.telegram import TelegramChannel
from channels.whatsapp import WhatsAppChannel

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
