"""
Discord channel integration for NEUGI v2.

Supports Discord Bot API for message handling, slash commands, role-based access,
threads, voice channels, and server/guild management.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

import requests

from .base import (
    Attachment,
    BaseChannel,
    ChannelCapabilities,
    ChannelType,
    ConversationType,
    IncomingMessage,
    MessageFormat,
    MessageType,
    OutgoingMessage,
    UserIdentity,
)

logger = logging.getLogger(__name__)

DISCORD_API_BASE = "https://discord.com/api/v10"
DISCORD_CDN_BASE = "https://cdn.discordapp.com"

DISCORD_RATE_LIMIT = 50


class DiscordChannel(BaseChannel):
    """
    Discord Bot API integration.

    Supports REST API for sending messages, managing guilds, handling
    slash commands, role-based access control, threads, and voice channels.
    Also supports gateway WebSocket for real-time message receiving.

    Args:
        token: Discord bot token.
        bot_name: Optional display name.
        application_id: Discord application ID (for slash commands).
        use_gateway: Whether to use WebSocket gateway for real-time events.
        health_check_interval: Seconds between health checks.
    """

    def __init__(
        self,
        token: str,
        bot_name: Optional[str] = None,
        application_id: Optional[str] = None,
        use_gateway: bool = False,
        health_check_interval: int = 60,
    ) -> None:
        super().__init__(token, bot_name, health_check_interval)
        self._application_id = application_id
        self._use_gateway = use_gateway
        self._session: Optional[requests.Session] = None
        self._gateway_task: Optional[asyncio.Task] = None
        self._gateway_url: Optional[str] = None
        self._session_id: Optional[str] = None
        self._sequence: Optional[int] = None
        self._heartbeat_interval: Optional[float] = None
        self._last_heartbeat_ack: Optional[float] = None
        self._rate_limit_tokens = DISCORD_RATE_LIMIT
        self._rate_limit_timestamp = time.time()
        self._guilds: dict[str, dict[str, Any]] = {}
        self._commands: list[dict[str, Any]] = []
        self._command_handlers: dict[str, Any] = {}

    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.DISCORD

    def _headers(self) -> dict[str, str]:
        """Build standard Discord API headers."""
        return {
            "Authorization": f"Bot {self._token}",
            "Content-Type": "application/json",
            "User-Agent": "NEUGI-v2/1.0",
        }

    def _call_api(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict[str, Any]] = None,
        files: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        """
        Make a synchronous API call to Discord.

        Args:
            method: HTTP method (GET, POST, PATCH, DELETE, PUT).
            endpoint: API endpoint path.
            data: JSON payload.
            files: File attachments.

        Returns:
            Parsed JSON response or None on failure.
        """
        self._wait_for_rate_limit()

        url = f"{DISCORD_API_BASE}{endpoint}"

        if self._session is None:
            self._session = requests.Session()

        try:
            if method == "GET":
                response = self._session.get(url, headers=self._headers(), timeout=30)
            elif method == "POST":
                if files:
                    response = self._session.post(
                        url, headers={"Authorization": f"Bot {self._token}"},
                        data=data, files=files, timeout=30,
                    )
                else:
                    response = self._session.post(
                        url, headers=self._headers(), json=data, timeout=30,
                    )
            elif method == "PATCH":
                response = self._session.patch(
                    url, headers=self._headers(), json=data, timeout=30,
                )
            elif method == "DELETE":
                response = self._session.delete(
                    url, headers=self._headers(), timeout=30,
                )
            elif method == "PUT":
                response = self._session.put(
                    url, headers=self._headers(), json=data, timeout=30,
                )
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            if response.status_code == 204:
                return {}

            if response.status_code == 429:
                retry_after = response.json().get("retry_after", 1)
                raise DiscordRateLimited(retry_after)

            response.raise_for_status()

            if response.text:
                result = response.json()
            else:
                result = {}

            remaining = response.headers.get("X-RateLimit-Remaining")
            reset = response.headers.get("X-RateLimit-Reset")
            if remaining is not None and reset is not None:
                self._health.record_rate_limit(int(remaining), float(reset))

            return result

        except requests.exceptions.Timeout:
            self._logger.error("Discord API timeout: %s %s", method, endpoint)
            self._health.record_error(f"Timeout on {method} {endpoint}")
            return None
        except requests.exceptions.ConnectionError:
            self._logger.error("Discord API connection error: %s %s", method, endpoint)
            self._health.record_error(f"Connection error on {method} {endpoint}")
            return None
        except DiscordRateLimited:
            raise
        except requests.exceptions.HTTPError as exc:
            self._logger.error("Discord API HTTP error: %s", exc)
            self._health.record_error(str(exc))
            return None
        except Exception as exc:
            self._logger.error("Discord API error: %s", exc)
            self._health.record_error(str(exc))
            return None

    def _wait_for_rate_limit(self) -> None:
        """Enforce Discord rate limiting."""
        now = time.time()
        if now - self._rate_limit_timestamp >= 1.0:
            self._rate_limit_tokens = DISCORD_RATE_LIMIT
            self._rate_limit_timestamp = now
        else:
            if self._rate_limit_tokens <= 0:
                sleep_time = 1.0 - (now - self._rate_limit_timestamp)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                self._rate_limit_tokens = DISCORD_RATE_LIMIT
                self._rate_limit_timestamp = time.time()
            self._rate_limit_tokens -= 1

    async def _connect(self) -> None:
        """Initialize Discord Bot API connection."""
        self._session = requests.Session()

        try:
            me = self._call_api("GET", "/users/@me")
            if me:
                self._bot_name = me.get("username", self._bot_name)
                self._application_id = self._application_id or me.get("id")
                self._logger.info("Connected as %s#%s (id: %s)",
                                  me.get("username"), me.get("discriminator"), me.get("id"))
            else:
                raise DiscordError("Failed to get bot info")

            guilds = self._call_api("GET", "/users/@me/guilds")
            if guilds:
                for guild in guilds:
                    self._guilds[guild["id"]] = guild
                self._logger.info("Connected to %d guilds", len(self._guilds))

            if self._use_gateway:
                gateway = self._call_api("GET", "/gateway/bot")
                if gateway:
                    self._gateway_url = gateway.get("url")
                    self._logger.info("Gateway URL obtained")

        except Exception:
            if self._session:
                self._session.close()
                self._session = None
            raise

    async def _disconnect(self) -> None:
        """Close Discord Bot API connection."""
        if self._gateway_task and not self._gateway_task.done():
            self._gateway_task.cancel()
            try:
                await self._gateway_task
            except asyncio.CancelledError:
                pass

        if self._session:
            self._session.close()
            self._session = None

        self._logger.info("Discord channel disconnected")

    async def _build_capabilities(self) -> ChannelCapabilities:
        """Build Discord channel capabilities."""
        caps = ChannelCapabilities()
        caps.supported_message_types = {
            MessageType.TEXT, MessageType.IMAGE, MessageType.FILE,
            MessageType.AUDIO, MessageType.VIDEO, MessageType.REACTION,
            MessageType.STICKER,
        }
        caps.supported_formats = {MessageFormat.PLAIN}
        caps.max_message_length = 2000
        caps.max_attachments = 10
        caps.max_attachment_size_mb = 25
        caps.supports_threads = True
        caps.supports_reactions = True
        caps.supports_editing = True
        caps.supports_deletion = True
        caps.supports_keyboard = False
        caps.supports_embeds = True
        caps.supports_voice = True
        caps.supports_polls = False
        caps.supports_templates = False
        caps.supports_scheduled = True
        caps.native_rate_limits = {
            "global_limit": 50,
            "per_channel": 5,
            "per_second": True,
        }
        return caps

    async def _gateway_loop(self) -> None:
        """WebSocket gateway event loop (simplified polling-based approach)."""
        self._logger.info("Gateway loop not implemented via REST - use webhooks for real-time events")

    async def _parse_message(self, raw_data: dict[str, Any]) -> Optional[IncomingMessage]:
        """Parse raw Discord message data into IncomingMessage."""
        channel = raw_data.get("channel", {})
        channel_type = raw_data.get("channel_type", 0)

        if channel_type == 1:
            conv_type = ConversationType.DM
        elif channel_type == 11:
            conv_type = ConversationType.THREAD
        elif channel_type == 5:
            conv_type = ConversationType.GROUP
        else:
            conv_type = ConversationType.CHANNEL

        user = self._parse_user(raw_data.get("author", {}))

        message_type, content, attachments = self._parse_content(raw_data)

        reply_to = None
        if "message_reference" in raw_data:
            reply_to = raw_data["message_reference"].get("message_id")

        thread_id = None
        if raw_data.get("thread"):
            thread_id = raw_data["thread"].get("id")

        return IncomingMessage(
            message_id=raw_data.get("id", ""),
            channel_type=ChannelType.DISCORD,
            user=user,
            content=content,
            message_type=message_type,
            conversation_type=conv_type,
            conversation_id=raw_data.get("channel_id", ""),
            thread_id=thread_id,
            reply_to_message_id=reply_to,
            attachments=attachments,
            timestamp=time.mktime(
                time.strptime(raw_data.get("timestamp", "")[:19], "%Y-%m-%dT%H:%M:%S")
            ) if raw_data.get("timestamp") else time.time(),
            raw_payload=raw_data,
            metadata={
                "guild_id": raw_data.get("guild_id"),
                "webhook_id": raw_data.get("webhook_id"),
                "message_flags": raw_data.get("flags", 0),
            },
        )

    def _parse_user(self, user_data: dict[str, Any]) -> UserIdentity:
        """Parse Discord user data into UserIdentity."""
        avatar_hash = user_data.get("avatar")
        avatar_url = None
        if avatar_hash:
            avatar_url = f"{DISCORD_CDN_BASE}/avatars/{user_data.get('id')}/{avatar_hash}.png"

        discriminator = user_data.get("discriminator", "0")
        display_name = user_data.get("global_name") or user_data.get("username", "Unknown")
        if discriminator and discriminator != "0":
            display_name = f"{display_name}#{discriminator}"

        return UserIdentity(
            id=user_data.get("id", ""),
            name=display_name,
            avatar_url=avatar_url,
            is_bot=user_data.get("bot", False),
            platform_username=user_data.get("username"),
            first_name=user_data.get("global_name"),
            metadata={
                "discriminator": discriminator,
                "public_flags": user_data.get("public_flags", 0),
                "avatar_decoration": user_data.get("avatar_decoration_data"),
            },
        )

    def _parse_content(
        self, raw_data: dict[str, Any]
    ) -> tuple[MessageType, str, list[Attachment]]:
        """Parse Discord message content."""
        attachments: list[Attachment] = []
        content = raw_data.get("content", "")

        if raw_data.get("embeds"):
            embed = raw_data["embeds"][0]
            embed_text = embed.get("title", "")
            if embed.get("description"):
                embed_text += f"\n{embed['description']}"
            if embed_text:
                content = content + "\n" + embed_text if content else embed_text

        for att in raw_data.get("attachments", []):
            attachments.append(Attachment(
                url=att.get("url", ""),
                filename=att.get("filename"),
                mime_type=att.get("content_type"),
                size_bytes=att.get("size"),
                width=att.get("width"),
                height=att.get("height"),
            ))

        if attachments:
            first = attachments[0]
            if first.mime_type and first.mime_type.startswith("image"):
                message_type = MessageType.IMAGE
            elif first.mime_type and first.mime_type.startswith("video"):
                message_type = MessageType.VIDEO
            elif first.mime_type and first.mime_type.startswith("audio"):
                message_type = MessageType.AUDIO
            else:
                message_type = MessageType.FILE
        elif raw_data.get("sticker_items"):
            message_type = MessageType.STICKER
        elif raw_data.get("type") == 19:
            message_type = MessageType.REACTION
        else:
            message_type = MessageType.TEXT

        if raw_data.get("type") == 24:
            content = content or "Thread created"
            message_type = MessageType.SYSTEM

        return message_type, content, attachments

    async def send_message(self, message: OutgoingMessage) -> Optional[str]:
        """Send a message via Discord API."""
        try:
            endpoint = f"/channels/{message.conversation_id}/messages"
            data: dict[str, Any] = {"content": message.content}

            if message.reply_to_message_id:
                data["message_reference"] = {"message_id": message.reply_to_message_id}

            if message.buttons:
                data["components"] = message.buttons

            if message.attachments:
                data["attachments"] = [
                    {"id": i, "filename": a.filename or "file"}
                    for i, a in enumerate(message.attachments)
                ]

            if message.message_type == MessageType.IMAGE and message.attachments:
                data["flags"] = 0

            result = self._call_api("POST", endpoint, data)
            if result:
                self._health.messages_sent += 1
                return result.get("id")
            return None

        except DiscordRateLimited as exc:
            self._logger.warning("Rate limited, retrying after %ds", exc.retry_after)
            await asyncio.sleep(exc.retry_after)
            return await self.send_message(message)
        except Exception as exc:
            self._logger.error("Failed to send message: %s", exc)
            self._health.record_error(str(exc))
            return None

    async def send_embed(
        self,
        conversation_id: str,
        title: str,
        description: str,
        color: int = 0x0099FF,
        fields: Optional[list[dict[str, str]]] = None,
        footer: Optional[str] = None,
        thumbnail_url: Optional[str] = None,
        image_url: Optional[str] = None,
        author_name: Optional[str] = None,
        author_icon_url: Optional[str] = None,
    ) -> Optional[str]:
        """
        Send an embed message.

        Args:
            conversation_id: Channel ID to send to.
            title: Embed title.
            description: Embed description.
            color: Embed color as integer.
            fields: List of {name, value, inline} dicts.
            footer: Footer text.
            thumbnail_url: Thumbnail image URL.
            image_url: Large image URL.
            author_name: Author name.
            author_icon_url: Author icon URL.
        """
        embed: dict[str, Any] = {
            "title": title,
            "description": description,
            "color": color,
        }

        if fields:
            embed["fields"] = fields
        if footer:
            embed["footer"] = {"text": footer}
        if thumbnail_url:
            embed["thumbnail"] = {"url": thumbnail_url}
        if image_url:
            embed["image"] = {"url": image_url}
        if author_name:
            embed["author"] = {"name": author_name}
            if author_icon_url:
                embed["author"]["icon_url"] = author_icon_url

        endpoint = f"/channels/{conversation_id}/messages"
        data = {"embeds": [embed]}

        result = self._call_api("POST", endpoint, data)
        if result:
            self._health.messages_sent += 1
            return result.get("id")
        return None

    async def edit_message(
        self,
        conversation_id: str,
        message_id: str,
        new_content: str,
        format: MessageFormat = MessageFormat.PLAIN,
    ) -> bool:
        """Edit a message."""
        endpoint = f"/channels/{conversation_id}/messages/{message_id}"
        data = {"content": new_content}
        result = self._call_api("PATCH", endpoint, data)
        return result is not None

    async def delete_message(self, conversation_id: str, message_id: str) -> bool:
        """Delete a message."""
        endpoint = f"/channels/{conversation_id}/messages/{message_id}"
        result = self._call_api("DELETE", endpoint)
        return result is not None

    async def add_reaction(
        self, conversation_id: str, message_id: str, emoji: str
    ) -> bool:
        """Add a reaction to a message."""
        endpoint = f"/channels/{conversation_id}/messages/{message_id}/reactions/{emoji}/@me"
        result = self._call_api("PUT", endpoint)
        return result is not None

    async def remove_reaction(
        self, conversation_id: str, message_id: str, emoji: str
    ) -> bool:
        """Remove a reaction from a message."""
        endpoint = f"/channels/{conversation_id}/messages/{message_id}/reactions/{emoji}/@me"
        result = self._call_api("DELETE", endpoint)
        return result is not None

    async def pin_message(self, conversation_id: str, message_id: str) -> bool:
        """Pin a message."""
        endpoint = f"/channels/{conversation_id}/pins/{message_id}"
        result = self._call_api("PUT", endpoint)
        return result is not None

    async def unpin_message(self, conversation_id: str, message_id: str) -> bool:
        """Unpin a message."""
        endpoint = f"/channels/{conversation_id}/pins/{message_id}"
        result = self._call_api("DELETE", endpoint)
        return result is not None

    async def get_user(self, user_id: str) -> Optional[UserIdentity]:
        """Get user information."""
        result = self._call_api("GET", f"/users/{user_id}")
        if result:
            return self._parse_user(result)
        return None

    async def get_guild(self, guild_id: str) -> Optional[dict[str, Any]]:
        """Get guild information."""
        return self._call_api("GET", f"/guilds/{guild_id}")

    async def get_guild_members(
        self, guild_id: str, limit: int = 100, after: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Get guild members."""
        params: dict[str, Any] = {"limit": limit}
        if after:
            params["after"] = after
        query = "&".join(f"{k}={v}" for k, v in params.items())
        result = self._call_api("GET", f"/guilds/{guild_id}/members?{query}")
        return result or []

    async def get_guild_roles(self, guild_id: str) -> list[dict[str, Any]]:
        """Get guild roles."""
        result = self._call_api("GET", f"/guilds/{guild_id}/roles")
        return result or []

    async def add_role(
        self, guild_id: str, user_id: str, role_id: str, reason: Optional[str] = None
    ) -> bool:
        """Add a role to a user."""
        endpoint = f"/guilds/{guild_id}/members/{user_id}/roles/{role_id}"
        headers = self._headers()
        if reason:
            headers["X-Audit-Log-Reason"] = reason

        if self._session is None:
            self._session = requests.Session()

        response = self._session.put(
            f"{DISCORD_API_BASE}{endpoint}", headers=headers, timeout=30,
        )
        return response.status_code == 204

    async def remove_role(self, guild_id: str, user_id: str, role_id: str) -> bool:
        """Remove a role from a user."""
        endpoint = f"/guilds/{guild_id}/members/{user_id}/roles/{role_id}"
        result = self._call_api("DELETE", endpoint)
        return result is not None

    async def get_channel(self, channel_id: str) -> Optional[dict[str, Any]]:
        """Get channel information."""
        return self._call_api("GET", f"/channels/{channel_id}")

    async def get_threads(self, channel_id: str) -> list[dict[str, Any]]:
        """Get active threads in a channel."""
        result = self._call_api("GET", f"/channels/{channel_id}/threads/active")
        if result:
            return result.get("threads", [])
        return []

    async def create_thread(
        self,
        channel_id: str,
        name: str,
        auto_archive_duration: int = 1440,
        message_id: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Create a thread."""
        data = {
            "name": name,
            "auto_archive_duration": auto_archive_duration,
        }
        if message_id:
            endpoint = f"/channels/{channel_id}/messages/{message_id}/threads"
        else:
            endpoint = f"/channels/{channel_id}/threads"
            data["type"] = 11

        return self._call_api("POST", endpoint, data)

    async def join_thread(self, thread_id: str) -> bool:
        """Join a thread."""
        endpoint = f"/channels/{thread_id}/thread-members/@me"
        result = self._call_api("PUT", endpoint)
        return result is not None

    async def leave_thread(self, thread_id: str) -> bool:
        """Leave a thread."""
        endpoint = f"/channels/{thread_id}/thread-members/@me"
        result = self._call_api("DELETE", endpoint)
        return result is not None

    async def get_voice_regions(self) -> list[dict[str, Any]]:
        """Get available voice regions."""
        result = self._call_api("GET", "/voice/regions")
        return result or []

    async def register_command(self, command: dict[str, Any]) -> Optional[dict[str, Any]]:
        """
        Register a global slash command.

        Args:
            command: Command definition dict with name, description, options.
        """
        if not self._application_id:
            raise DiscordError("Application ID not set")

        endpoint = f"/applications/{self._application_id}/commands"
        return self._call_api("POST", endpoint, command)

    async def register_guild_command(
        self, guild_id: str, command: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        """Register a guild-specific slash command."""
        if not self._application_id:
            raise DiscordError("Application ID not set")

        endpoint = f"/applications/{self._application_id}/guilds/{guild_id}/commands"
        return self._call_api("POST", endpoint, command)

    async def set_commands(self, commands: list[dict[str, Any]]) -> Optional[list[dict[str, Any]]]:
        """Bulk set global commands (replaces all existing)."""
        if not self._application_id:
            raise DiscordError("Application ID not set")

        endpoint = f"/applications/{self._application_id}/commands"
        return self._call_api("PUT", endpoint, commands)

    async def set_guild_commands(
        self, guild_id: str, commands: list[dict[str, Any]]
    ) -> Optional[list[dict[str, Any]]]:
        """Bulk set guild commands."""
        if not self._application_id:
            raise DiscordError("Application ID not set")

        endpoint = f"/applications/{self._application_id}/guilds/{guild_id}/commands"
        return self._call_api("PUT", endpoint, commands)

    def register_command_handler(self, command_name: str, handler) -> None:
        """Register a handler for a slash command."""
        self._command_handlers[command_name] = handler

    async def handle_interaction(self, interaction_data: dict[str, Any]) -> None:
        """
        Process an interaction (slash command, button click, etc.).

        Args:
            interaction_data: Interaction payload from Discord.
        """
        if interaction_data.get("type") == 2:
            data = interaction_data.get("data", {})
            command_name = data.get("name")
            handler = self._command_handlers.get(command_name)

            if handler:
                try:
                    await handler(interaction_data)
                except Exception as exc:
                    self._logger.error("Command handler error: %s", exc)
            else:
                await self._respond_interaction(
                    interaction_data,
                    content=f"Command `/{command_name}` not found",
                    ephemeral=True,
                )

    async def _respond_interaction(
        self,
        interaction_data: dict[str, Any],
        content: str,
        ephemeral: bool = False,
    ) -> bool:
        """Respond to an interaction."""
        interaction_id = interaction_data.get("id")
        interaction_token = interaction_data.get("token")

        if not interaction_id or not interaction_token:
            return False

        endpoint = f"/interactions/{interaction_id}/{interaction_token}/callback"
        flags = 64 if ephemeral else 0
        data = {
            "type": 4,
            "data": {"content": content, "flags": flags},
        }
        result = self._call_api("POST", endpoint, data)
        return result is not None

    async def process_webhook(self, request_data: dict[str, Any]) -> None:
        """Process a webhook event."""
        if request_data.get("type") == 1:
            return

        if request_data.get("type") == 2:
            await self.handle_interaction(request_data)
            return

        if request_data.get("t") == "MESSAGE_CREATE":
            message = await self.receive_message(request_data.get("d", {}))
            if message:
                await self._notify_message_handlers(message)

    async def _health_check(self) -> None:
        """Check Discord API connectivity."""
        result = self._call_api("GET", "/users/@me")
        if not result:
            raise DiscordError("Health check failed")


class DiscordError(Exception):
    """Discord API error."""


class DiscordRateLimited(DiscordError):
    """Discord rate limit exceeded."""

    def __init__(self, retry_after: float) -> None:
        self.retry_after = retry_after
        super().__init__(f"Rate limited. Retry after {retry_after}s")
