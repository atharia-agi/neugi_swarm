"""
Slack channel integration for NEUGI v2.

Supports Slack Events API for receiving messages and Web API for sending,
including message blocks, slash commands, interactive components, threads,
and channel management.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
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

SLACK_API_BASE = "https://slack.com/api"


class SlackChannel(BaseChannel):
    """
    Slack Bot API integration.

    Supports Events API for receiving messages and Web API for sending.
    Handles message blocks (Block Kit), slash commands, interactive components
    (buttons, menus), threads, and channel/group/DM management.

    Args:
        token: Slack Bot token (xoxb-...).
        signing_secret: Slack signing secret for webhook verification.
        bot_name: Optional display name.
        health_check_interval: Seconds between health checks.
    """

    def __init__(
        self,
        token: str,
        signing_secret: str,
        bot_name: Optional[str] = None,
        health_check_interval: int = 60,
    ) -> None:
        super().__init__(token, bot_name, health_check_interval)
        self._signing_secret = signing_secret
        self._session: Optional[requests.Session] = None
        self._bot_id: Optional[str] = None
        self._bot_user_id: Optional[str] = None
        self._slash_commands: dict[str, Any] = {}
        self._block_actions: dict[str, Any] = {}

    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.SLACK

    def _headers(self) -> dict[str, str]:
        """Build standard Slack API headers."""
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "NEUGI-v2/1.0",
        }

    def _call_api(
        self,
        method: str,
        data: Optional[dict[str, Any]] = None,
        files: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        """
        Make a synchronous API call to Slack.

        Args:
            method: API method name (e.g., "chat.postMessage").
            data: JSON payload.
            files: File attachments.

        Returns:
            Parsed JSON response or None on failure.
        """
        url = f"{SLACK_API_BASE}/{method}"

        if self._session is None:
            self._session = requests.Session()

        try:
            if files:
                response = self._session.post(
                    url, headers={"Authorization": f"Bearer {self._token}"},
                    data=data, files=files, timeout=30,
                )
            else:
                response = self._session.post(
                    url, headers=self._headers(), json=data, timeout=30,
                )

            response.raise_for_status()
            result = response.json()

            if not result.get("ok"):
                error = result.get("error", "Unknown error")
                raise SlackError(error)

            remaining = response.headers.get("X-RateLimit-Remaining")
            reset = response.headers.get("X-RateLimit-Reset")
            retry = response.headers.get("Retry-After")
            if remaining is not None and reset is not None:
                self._health.record_rate_limit(
                    int(remaining), float(reset)
                )

            return result

        except requests.exceptions.Timeout:
            self._logger.error("Slack API timeout: %s", method)
            self._health.record_error(f"Timeout on {method}")
            return None
        except requests.exceptions.ConnectionError:
            self._logger.error("Slack API connection error: %s", method)
            self._health.record_error(f"Connection error on {method}")
            return None
        except SlackError:
            raise
        except Exception as exc:
            self._logger.error("Slack API error: %s", exc)
            self._health.record_error(str(exc))
            return None

    def verify_signature(
        self,
        timestamp: str,
        signature: str,
        body: bytes,
    ) -> bool:
        """
        Verify Slack request signature.

        Args:
            timestamp: X-Slack-Request-Timestamp header.
            signature: X-Slack-Signature header.
            body: Raw request body bytes.

        Returns:
            True if signature is valid.
        """
        try:
            if abs(time.time() - int(timestamp)) > 60 * 5:
                return False

            basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
            expected = hmac.new(
                self._signing_secret.encode("utf-8"),
                basestring.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()

            return hmac.compare_digest(f"v0={expected}", signature)

        except Exception:
            return False

    async def _connect(self) -> None:
        """Initialize Slack Bot API connection."""
        self._session = requests.Session()

        try:
            result = self._call_api("auth.test")
            if result:
                self._bot_name = result.get("user", self._bot_name)
                self._bot_id = result.get("user_id")
                self._logger.info("Connected as %s (id: %s)",
                                  result.get("user"), result.get("user_id"))
            else:
                raise SlackError("Failed to authenticate")

            result = self._call_api("bot.info")
            if result:
                self._bot_user_id = result.get("user_id")

        except Exception:
            if self._session:
                self._session.close()
                self._session = None
            raise

    async def _disconnect(self) -> None:
        """Close Slack Bot API connection."""
        if self._session:
            self._session.close()
            self._session = None

        self._logger.info("Slack channel disconnected")

    async def _build_capabilities(self) -> ChannelCapabilities:
        """Build Slack channel capabilities."""
        caps = ChannelCapabilities()
        caps.supported_message_types = {
            MessageType.TEXT, MessageType.IMAGE, MessageType.FILE,
            MessageType.AUDIO, MessageType.VIDEO,
        }
        caps.supported_formats = {MessageFormat.PLAIN, MessageFormat.RICH_TEXT}
        caps.max_message_length = 40000
        caps.max_attachments = 10
        caps.max_attachment_size_mb = 1000
        caps.supports_threads = True
        caps.supports_reactions = True
        caps.supports_editing = True
        caps.supports_deletion = True
        caps.supports_keyboard = True
        caps.supports_embeds = False
        caps.supports_voice = False
        caps.supports_polls = False
        caps.supports_templates = False
        caps.supports_scheduled = True
        caps.native_rate_limits = {
            "tier_1": 1,
            "tier_2": 20,
            "tier_3": 50,
            "per_minute": True,
        }
        return caps

    async def _parse_message(self, raw_data: dict[str, Any]) -> Optional[IncomingMessage]:
        """Parse raw Slack message data into IncomingMessage."""
        channel = raw_data.get("channel", "")
        thread_ts = raw_data.get("thread_ts")

        if channel.startswith("D"):
            conv_type = ConversationType.DM
        elif channel.startswith("G"):
            conv_type = ConversationType.GROUP
        elif channel.startswith("C"):
            conv_type = ConversationType.CHANNEL
        else:
            conv_type = ConversationType.DM

        if thread_ts:
            conv_type = ConversationType.THREAD

        user = self._parse_user(raw_data)

        message_type, content, attachments = self._parse_content(raw_data)

        reply_to = None
        if raw_data.get("thread_ts") and raw_data.get("thread_ts") != raw_data.get("ts"):
            reply_to = raw_data.get("thread_ts")

        return IncomingMessage(
            message_id=raw_data.get("ts", ""),
            channel_type=ChannelType.SLACK,
            user=user,
            content=content,
            message_type=message_type,
            conversation_type=conv_type,
            conversation_id=channel,
            thread_id=thread_ts,
            reply_to_message_id=reply_to,
            attachments=attachments,
            timestamp=float(raw_data.get("ts", time.time())),
            raw_payload=raw_data,
            metadata={
                "team_id": raw_data.get("team"),
                "event_ts": raw_data.get("event_ts"),
                "subtype": raw_data.get("subtype"),
            },
        )

    def _parse_user(self, message_data: dict[str, Any]) -> UserIdentity:
        """Parse Slack message data into UserIdentity."""
        user_id = message_data.get("user", "")
        username = message_data.get("username", "")
        bot_id = message_data.get("bot_id")

        if bot_id:
            return UserIdentity(
                id=bot_id,
                name=username or "Bot",
                is_bot=True,
                metadata={"bot_id": bot_id},
            )

        return UserIdentity(
            id=user_id,
            name=username or f"User({user_id})",
            metadata={
                "team_id": message_data.get("team"),
            },
        )

    def _parse_content(
        self, raw_data: dict[str, Any]
    ) -> tuple[MessageType, str, list[Attachment]]:
        """Parse Slack message content."""
        attachments: list[Attachment] = []
        content = raw_data.get("text", "")

        if raw_data.get("blocks"):
            block_text = self._extract_block_text(raw_data["blocks"])
            if block_text:
                content = content + "\n" + block_text if content else block_text

        for file_data in raw_data.get("files", []):
            attachments.append(Attachment(
                url=file_data.get("url_private", file_data.get("permalink", "")),
                filename=file_data.get("name"),
                mime_type=file_data.get("mimetype"),
                size_bytes=file_data.get("size"),
                width=file_data.get("original_w"),
                height=file_data.get("original_h"),
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
        else:
            message_type = MessageType.TEXT

        if raw_data.get("subtype") == "bot_message":
            message_type = MessageType.TEXT

        return message_type, content, attachments

    def _extract_block_text(self, blocks: list[dict[str, Any]]) -> str:
        """Extract plain text from Slack Block Kit blocks."""
        texts = []
        for block in blocks:
            block_type = block.get("type")
            if block_type == "section":
                text = block.get("text", {})
                if isinstance(text, dict):
                    texts.append(text.get("text", ""))
                for field in block.get("fields", []):
                    if isinstance(field, dict):
                        texts.append(field.get("text", ""))
            elif block_type == "header":
                text = block.get("text", {})
                if isinstance(text, dict):
                    texts.append(text.get("text", ""))
            elif block_type == "divider":
                texts.append("---")
            elif block_type == "context":
                for element in block.get("elements", []):
                    if isinstance(element, dict) and "text" in element:
                        texts.append(element["text"])
        return "\n".join(texts)

    async def send_message(self, message: OutgoingMessage) -> Optional[str]:
        """Send a message via Slack Web API."""
        try:
            if message.message_type == MessageType.TEXT:
                return await self._send_text(message)
            elif message.message_type == MessageType.FILE:
                return await self._send_file(message)
            else:
                return await self._send_text(message)
        except Exception as exc:
            self._logger.error("Failed to send message: %s", exc)
            self._health.record_error(str(exc))
            return None

    async def _send_text(self, message: OutgoingMessage) -> Optional[str]:
        """Send a text message."""
        data: dict[str, Any] = {
            "channel": message.conversation_id,
            "text": message.content,
        }

        if message.thread_id:
            data["thread_ts"] = message.thread_id

        if message.reply_to_message_id:
            data["thread_ts"] = message.reply_to_message_id

        if message.buttons:
            data["blocks"] = message.buttons

        if message.metadata.get("unfurl_links") is False:
            data["unfurl_links"] = False

        if message.metadata.get("unfurl_media") is False:
            data["unfurl_media"] = False

        result = self._call_api("chat.postMessage", data)
        if result:
            self._health.messages_sent += 1
            return result.get("ts")
        return None

    async def _send_file(self, message: OutgoingMessage) -> Optional[str]:
        """Send a file."""
        data = {"channels": message.conversation_id}

        if message.content:
            data["initial_comment"] = message.content

        if message.thread_id:
            data["thread_ts"] = message.thread_id

        if message.attachments:
            file_url = message.attachments[0].url
            data["file"] = file_url

        result = self._call_api("files.upload", data)
        if result:
            self._health.messages_sent += 1
            return result.get("file", {}).get("id")
        return None

    async def send_blocks(
        self,
        conversation_id: str,
        blocks: list[dict[str, Any]],
        text: str = "",
        thread_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Send a message with Block Kit blocks.

        Args:
            conversation_id: Channel ID.
            blocks: Block Kit block structure.
            text: Fallback plain text.
            thread_id: Thread timestamp.
        """
        data: dict[str, Any] = {
            "channel": conversation_id,
            "text": text,
            "blocks": blocks,
        }
        if thread_id:
            data["thread_ts"] = thread_id

        result = self._call_api("chat.postMessage", data)
        if result:
            self._health.messages_sent += 1
            return result.get("ts")
        return None

    async def send_ephemeral(
        self,
        conversation_id: str,
        user_id: str,
        text: str,
        blocks: Optional[list[dict[str, Any]]] = None,
    ) -> Optional[str]:
        """Send an ephemeral message visible only to a user."""
        data: dict[str, Any] = {
            "channel": conversation_id,
            "user": user_id,
            "text": text,
        }
        if blocks:
            data["blocks"] = blocks

        result = self._call_api("chat.postEphemeral", data)
        if result:
            self._health.messages_sent += 1
            return result.get("ts")
        return None

    async def edit_message(
        self,
        conversation_id: str,
        message_id: str,
        new_content: str,
        format: MessageFormat = MessageFormat.PLAIN,
    ) -> bool:
        """Edit a message."""
        data = {
            "channel": conversation_id,
            "ts": message_id,
            "text": new_content,
        }
        result = self._call_api("chat.update", data)
        return result is not None and result.get("ok")

    async def delete_message(self, conversation_id: str, message_id: str) -> bool:
        """Delete a message."""
        data = {"channel": conversation_id, "ts": message_id}
        result = self._call_api("chat.delete", data)
        return result is not None and result.get("ok")

    async def add_reaction(
        self, conversation_id: str, message_id: str, emoji: str
    ) -> bool:
        """Add a reaction."""
        data = {
            "channel": conversation_id,
            "timestamp": message_id,
            "name": emoji,
        }
        result = self._call_api("reactions.add", data)
        return result is not None and result.get("ok")

    async def remove_reaction(
        self, conversation_id: str, message_id: str, emoji: str
    ) -> bool:
        """Remove a reaction."""
        data = {
            "channel": conversation_id,
            "timestamp": message_id,
            "name": emoji,
        }
        result = self._call_api("reactions.remove", data)
        return result is not None and result.get("ok")

    async def pin_message(self, conversation_id: str, message_id: str) -> bool:
        """Pin a message."""
        data = {"channel": conversation_id, "timestamp": message_id}
        result = self._call_api("pins.add", data)
        return result is not None and result.get("ok")

    async def unpin_message(self, conversation_id: str, message_id: str) -> bool:
        """Unpin a message."""
        data = {"channel": conversation_id, "timestamp": message_id}
        result = self._call_api("pins.remove", data)
        return result is not None and result.get("ok")

    async def get_user(self, user_id: str) -> Optional[UserIdentity]:
        """Get user information."""
        result = self._call_api("users.info", {"user": user_id})
        if result and result.get("user"):
            user = result["user"]
            profile = user.get("profile", {})
            return UserIdentity(
                id=user_id,
                name=profile.get("display_name") or profile.get("real_name") or user.get("name", ""),
                avatar_url=profile.get("image_512"),
                is_bot=user.get("is_bot", False),
                platform_username=user.get("name"),
                first_name=profile.get("first_name"),
                last_name=profile.get("last_name"),
                metadata={
                    "is_admin": user.get("is_admin", False),
                    "is_owner": user.get("is_owner", False),
                    "tz": profile.get("tz"),
                    "status_text": profile.get("status_text"),
                },
            )
        return None

    async def get_chat_info(self, chat_id: str) -> Optional[dict[str, Any]]:
        """Get channel/conversation information."""
        if chat_id.startswith("D"):
            result = self._call_api("conversations.info", {"channel": chat_id})
        else:
            result = self._call_api("conversations.info", {"channel": chat_id})
        return result.get("channel") if result else None

    async def get_conversations(
        self,
        types: Optional[list[str]] = None,
        limit: int = 100,
        cursor: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """List conversations the bot is a member of."""
        data: dict[str, Any] = {"limit": limit}
        if types:
            data["types"] = ",".join(types)
        if cursor:
            data["cursor"] = cursor

        result = self._call_api("conversations.list", data)
        if result:
            return result.get("channels", [])
        return []

    async def join_channel(self, channel_id: str) -> bool:
        """Join a public channel."""
        result = self._call_api("conversations.join", {"channel": channel_id})
        return result is not None and result.get("ok")

    async def leave_channel(self, channel_id: str) -> bool:
        """Leave a channel."""
        result = self._call_api("conversations.leave", {"channel": channel_id})
        return result is not None and result.get("ok")

    async def invite_to_channel(self, channel_id: str, user_id: str) -> bool:
        """Invite a user to a channel."""
        data = {"channel": channel_id, "users": user_id}
        result = self._call_api("conversations.invite", data)
        return result is not None and result.get("ok")

    async def get_conversation_history(
        self,
        channel_id: str,
        limit: int = 10,
        oldest: Optional[str] = None,
        latest: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Get conversation history."""
        data: dict[str, Any] = {"channel": channel_id, "limit": limit}
        if oldest:
            data["oldest"] = oldest
        if latest:
            data["latest"] = latest

        result = self._call_api("conversations.history", data)
        if result:
            return result.get("messages", [])
        return []

    async def get_thread_replies(
        self, channel_id: str, thread_ts: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Get thread replies."""
        data = {"channel": channel_id, "ts": thread_ts, "limit": limit}
        result = self._call_api("conversations.replies", data)
        if result:
            return result.get("messages", [])
        return []

    async def lookup_user_by_email(self, email: str) -> Optional[UserIdentity]:
        """Look up a user by email."""
        result = self._call_api("users.lookupByEmail", {"email": email})
        if result and result.get("user"):
            return self._parse_user(result["user"])
        return None

    def register_slash_command(self, command: str, handler) -> None:
        """Register a slash command handler."""
        self._slash_commands[command] = handler

    def register_block_action(self, action_id: str, handler) -> None:
        """Register a block action handler."""
        self._block_actions[action_id] = handler

    async def process_event(self, event_data: dict[str, Any]) -> Optional[dict[str, Any]]:
        """
        Process a Slack Events API event.

        Args:
            event_data: Parsed JSON from the event webhook.

        Returns:
            Response dict for the webhook (e.g., challenge response).
        """
        if "challenge" in event_data:
            return {"challenge": event_data["challenge"]}

        event = event_data.get("event", {})
        event_type = event.get("type")

        if event_type == "message":
            if event.get("subtype") in ("bot_message", "message_changed", "message_deleted"):
                return None

            message = await self.receive_message(event)
            if message:
                await self._notify_message_handlers(message)

        elif event_type == "app_mention":
            message = await self.receive_message(event)
            if message:
                message.metadata["mention"] = True
                await self._notify_message_handlers(message)

        elif event_type == "reaction_added":
            message = IncomingMessage(
                message_id=event.get("item", {}).get("ts", ""),
                channel_type=ChannelType.SLACK,
                user=self._parse_user(event),
                content=event.get("reaction", ""),
                message_type=MessageType.REACTION,
                conversation_type=ConversationType.CHANNEL,
                conversation_id=event.get("item", {}).get("channel", ""),
                raw_payload=event,
            )
            await self._notify_message_handlers(message)

        return None

    async def process_interaction(
        self, interaction_data: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        """
        Process a Slack interaction (slash command, block action, etc.).

        Args:
            interaction_data: Parsed form data from interaction webhook.
        """
        payload_type = interaction_data.get("type")

        if payload_type == "slash_command":
            command = interaction_data.get("command", "").lstrip("/")
            handler = self._slash_commands.get(command)
            if handler:
                try:
                    await handler(interaction_data)
                except Exception as exc:
                    self._logger.error("Slash command handler error: %s", exc)
                    return {"text": f"Error executing `/{command}`"}
            else:
                return {"text": f"Command `/{command}` not found"}

        elif payload_type == "block_actions":
            actions = interaction_data.get("actions", [])
            for action in actions:
                action_id = action.get("action_id")
                handler = self._block_actions.get(action_id)
                if handler:
                    try:
                        await handler(action, interaction_data)
                    except Exception as exc:
                        self._logger.error("Block action handler error: %s", exc)

        return None

    async def respond_to_webhook(
        self,
        response_url: str,
        text: str,
        blocks: Optional[list[dict[str, Any]]] = None,
        replace_original: bool = False,
        delete_original: bool = False,
    ) -> bool:
        """
        Respond to a webhook (slash command or interaction).

        Args:
            response_url: Response URL from the interaction payload.
            text: Response text.
            blocks: Optional Block Kit blocks.
            replace_original: Replace the original message.
            delete_original: Delete the original message.
        """
        data: dict[str, Any] = {"text": text}
        if blocks:
            data["blocks"] = blocks
        if replace_original:
            data["replace_original"] = True
        if delete_original:
            data["delete_original"] = True

        if self._session is None:
            self._session = requests.Session()

        try:
            response = self._session.post(response_url, json=data, timeout=30)
            return response.ok
        except Exception as exc:
            self._logger.error("Webhook response error: %s", exc)
            return False

    async def schedule_message(
        self,
        conversation_id: str,
        post_at: int,
        text: str,
        blocks: Optional[list[dict[str, Any]]] = None,
        thread_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Schedule a message for future delivery.

        Args:
            conversation_id: Channel ID.
            post_at: Unix timestamp for delivery.
            text: Message text.
            blocks: Optional Block Kit blocks.
            thread_id: Thread timestamp.
        """
        data: dict[str, Any] = {
            "channel": conversation_id,
            "text": text,
            "post_at": post_at,
        }
        if blocks:
            data["blocks"] = blocks
        if thread_id:
            data["thread_ts"] = thread_id

        result = self._call_api("chat.scheduleMessage", data)
        if result:
            self._health.messages_sent += 1
            return result.get("scheduled_message_id")
        return None

    async def _health_check(self) -> None:
        """Check Slack API connectivity."""
        result = self._call_api("auth.test")
        if not result or not result.get("ok"):
            raise SlackError("Health check failed")


class SlackError(Exception):
    """Slack API error."""

    def __init__(self, error: str) -> None:
        self.error = error
        super().__init__(f"Slack API error: {error}")
