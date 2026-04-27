"""
Telegram channel integration for NEUGI v2.

Supports Bot API via long polling and webhook modes, handling all message types
including text, photos, documents, voice, video, stickers, and inline keyboards.
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

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}"
TELEGRAM_FILE_BASE = "https://api.telegram.org/file/bot{token}"

TELEGRAM_RATE_LIMIT = 30
TELEGRAM_GROUP_LIMIT = 20


class TelegramChannel(BaseChannel):
    """
    Telegram Bot API integration.

    Supports both long polling and webhook modes for receiving updates.
    Handles text, photo, document, voice, video, sticker, location,
    and contact messages. Provides inline keyboard and reply keyboard support.

    Args:
        token: Telegram Bot API token from @BotFather.
        bot_name: Optional display name for the bot.
        mode: "polling" or "webhook".
        webhook_url: Required if mode is "webhook".
        poll_timeout: Seconds to wait for long polling updates.
        allowed_updates: List of update types to receive.
        health_check_interval: Seconds between health checks.
    """

    def __init__(
        self,
        token: str,
        bot_name: Optional[str] = None,
        mode: str = "polling",
        webhook_url: Optional[str] = None,
        poll_timeout: int = 30,
        allowed_updates: Optional[list[str]] = None,
        health_check_interval: int = 60,
    ) -> None:
        super().__init__(token, bot_name, health_check_interval)
        self._mode = mode
        self._webhook_url = webhook_url
        self._poll_timeout = poll_timeout
        self._allowed_updates = allowed_updates or [
            "message", "edited_message", "callback_query",
            "inline_query", "channel_post", "my_chat_member",
        ]
        self._offset = 0
        self._poll_task: Optional[asyncio.Task] = None
        self._session: Optional[requests.Session] = None
        self._rate_limit_tokens = TELEGRAM_RATE_LIMIT
        self._rate_limit_timestamp = time.time()
        self._webhook_secret: Optional[str] = None
        self._me: Optional[dict[str, Any]] = None

    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.TELEGRAM

    def _api_url(self, method: str) -> str:
        """Build Telegram API URL for a method."""
        return TELEGRAM_API_BASE.format(token=self._token) + f"/{method}"

    def _file_url(self, file_path: str) -> str:
        """Build Telegram file download URL."""
        return TELEGRAM_FILE_BASE.format(token=self._token) + f"/{file_path}"

    def _call_api(
        self,
        method: str,
        data: Optional[dict[str, Any]] = None,
        files: Optional[dict[str, Any]] = None,
        timeout: int = 30,
    ) -> Optional[dict[str, Any]]:
        """
        Make a synchronous API call to Telegram.

        Args:
            method: API method name (e.g., "sendMessage").
            data: JSON payload for the request.
            files: File attachments for multipart upload.
            timeout: Request timeout in seconds.

        Returns:
            Parsed JSON response or None on failure.

        Raises:
            TelegramRateLimited: If rate limit is exceeded.
            TelegramError: If the API returns an error.
        """
        self._wait_for_rate_limit()

        url = self._api_url(method)

        if self._session is None:
            self._session = requests.Session()

        try:
            if files:
                response = self._session.post(url, data=data, files=files, timeout=timeout)
            else:
                response = self._session.post(url, json=data, timeout=timeout)

            response.raise_for_status()
            result = response.json()

            if not result.get("ok"):
                description = result.get("description", "Unknown error")
                error_code = result.get("error_code", 0)

                if error_code == 429:
                    retry_after = result.get("parameters", {}).get("retry_after", 1)
                    raise TelegramRateLimited(retry_after, description)

                raise TelegramError(error_code, description)

            headers = response.headers
            if "x-ratelimit-remaining" in headers:
                self._health.record_rate_limit(
                    int(headers["x-ratelimit-remaining"]),
                    time.time() + 1,
                )

            return result.get("result")

        except requests.exceptions.Timeout:
            self._logger.error("Telegram API timeout: %s", method)
            self._health.record_error(f"Timeout on {method}")
            return None
        except requests.exceptions.ConnectionError:
            self._logger.error("Telegram API connection error: %s", method)
            self._health.record_error(f"Connection error on {method}")
            return None
        except TelegramRateLimited:
            raise
        except TelegramError:
            raise
        except Exception as exc:
            self._logger.error("Telegram API error on %s: %s", method, exc)
            self._health.record_error(str(exc))
            return None

    def _wait_for_rate_limit(self) -> None:
        """Enforce Telegram rate limiting (30 msg/sec for individual, 20 msg/sec for groups)."""
        now = time.time()
        if now - self._rate_limit_timestamp >= 1.0:
            self._rate_limit_tokens = TELEGRAM_RATE_LIMIT
            self._rate_limit_timestamp = now
        else:
            if self._rate_limit_tokens <= 0:
                sleep_time = 1.0 - (now - self._rate_limit_timestamp)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                self._rate_limit_tokens = TELEGRAM_RATE_LIMIT
                self._rate_limit_timestamp = time.time()
            self._rate_limit_tokens -= 1

    async def _connect(self) -> None:
        """Initialize Telegram Bot API connection."""
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "NEUGI-v2/1.0"})

        try:
            me = self._call_api("getMe")
            if me:
                self._me = me
                self._bot_name = me.get("username", self._bot_name)
                self._logger.info("Connected as @%s (id: %s)", me.get("username"), me.get("id"))
            else:
                raise TelegramError(0, "Failed to get bot info")

            if self._mode == "webhook":
                if not self._webhook_url:
                    raise ValueError("webhook_url is required for webhook mode")
                result = self._call_api("setWebhook", {
                    "url": self._webhook_url,
                    "allowed_updates": self._allowed_updates,
                })
                if result:
                    self._logger.info("Webhook set to %s", self._webhook_url)
                else:
                    raise TelegramError(0, "Failed to set webhook")
            else:
                result = self._call_api("deleteWebhook")
                self._logger.info("Using long polling mode")

        except Exception:
            if self._session:
                self._session.close()
                self._session = None
            raise

    async def _disconnect(self) -> None:
        """Close Telegram Bot API connection."""
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass

        if self._mode == "webhook":
            try:
                self._call_api("deleteWebhook", {"drop_pending_updates": True})
            except Exception:
                pass

        if self._session:
            self._session.close()
            self._session = None

        self._logger.info("Telegram channel disconnected")

    async def _build_capabilities(self) -> ChannelCapabilities:
        """Build Telegram channel capabilities."""
        caps = ChannelCapabilities()
        caps.supported_message_types = {
            MessageType.TEXT, MessageType.IMAGE, MessageType.FILE,
            MessageType.AUDIO, MessageType.VIDEO, MessageType.REACTION,
            MessageType.LOCATION, MessageType.CONTACT, MessageType.STICKER,
            MessageType.POLL,
        }
        caps.supported_formats = {MessageFormat.PLAIN, MessageFormat.HTML, MessageFormat.MARKDOWN_V2}
        caps.max_message_length = 4096
        caps.max_attachments = 10
        caps.max_attachment_size_mb = 50
        caps.supports_threads = False
        caps.supports_reactions = True
        caps.supports_editing = True
        caps.supports_deletion = True
        caps.supports_keyboard = True
        caps.supports_embeds = False
        caps.supports_voice = True
        caps.supports_polls = True
        caps.supports_templates = False
        caps.supports_scheduled = False
        caps.native_rate_limits = {
            "global_limit": 30,
            "group_limit": 20,
            "per_second": True,
        }
        return caps

    async def _poll_updates(self) -> None:
        """Long polling loop for receiving updates."""
        self._logger.info("Starting long polling with timeout=%ds", self._poll_timeout)

        while self._is_running:
            try:
                data = {
                    "offset": self._offset,
                    "timeout": self._poll_timeout,
                    "allowed_updates": self._allowed_updates,
                }

                result = self._call_api("getUpdates", data, timeout=self._poll_timeout + 5)

                if result:
                    for update in result:
                        self._offset = update["update_id"] + 1
                        await self._handle_update(update)

            except asyncio.CancelledError:
                break
            except TelegramRateLimited as exc:
                self._logger.warning("Rate limited, waiting %ds", exc.retry_after)
                await asyncio.sleep(exc.retry_after)
            except Exception as exc:
                self._logger.error("Polling error: %s", exc)
                self._health.record_error(str(exc))
                await asyncio.sleep(5)

    async def _handle_update(self, update: dict[str, Any]) -> None:
        """Process a single Telegram update."""
        if "message" in update:
            message = await self.receive_message(update["message"])
            if message:
                await self._notify_message_handlers(message)

        elif "edited_message" in update:
            message = await self.receive_message(update["edited_message"])
            if message:
                message.metadata["edited"] = True
                await self._notify_message_handlers(message)

        elif "callback_query" in update:
            cb = update["callback_query"]
            message = IncomingMessage(
                message_id=str(cb["id"]),
                channel_type=ChannelType.TELEGRAM,
                user=self._parse_user(cb["from"]),
                content=cb.get("data", ""),
                message_type=MessageType.COMMAND,
                conversation_type=ConversationType.DM,
                conversation_id=str(cb["message"]["chat"]["id"]),
                raw_payload=cb,
            )
            await self._notify_message_handlers(message)

        elif "channel_post" in update:
            message = await self.receive_message(update["channel_post"])
            if message:
                message.metadata["channel_post"] = True
                await self._notify_message_handlers(message)

    async def _parse_message(self, raw_data: dict[str, Any]) -> Optional[IncomingMessage]:
        """Parse raw Telegram message data into IncomingMessage."""
        chat = raw_data.get("chat", {})
        chat_id = str(chat.get("id", ""))
        chat_type = chat.get("type", "private")

        if chat_type == "private":
            conv_type = ConversationType.DM
        elif chat_type in ("group", "supergroup"):
            conv_type = ConversationType.GROUP
        elif chat_type == "channel":
            conv_type = ConversationType.CHANNEL
        else:
            conv_type = ConversationType.DM

        user = self._parse_user(raw_data.get("from", {}))

        message_type, content, attachments = self._parse_content(raw_data)

        reply_to = None
        if "reply_to_message" in raw_data:
            reply_to = str(raw_data["reply_to_message"].get("message_id"))

        thread_id = None
        if "message_thread_id" in raw_data:
            thread_id = str(raw_data["message_thread_id"])

        return IncomingMessage(
            message_id=str(raw_data.get("message_id", "")),
            channel_type=ChannelType.TELEGRAM,
            user=user,
            content=content,
            message_type=message_type,
            conversation_type=conv_type,
            conversation_id=chat_id,
            thread_id=thread_id,
            reply_to_message_id=reply_to,
            attachments=attachments,
            timestamp=float(raw_data.get("date", time.time())),
            raw_payload=raw_data,
        )

    def _parse_user(self, user_data: dict[str, Any]) -> UserIdentity:
        """Parse Telegram user data into UserIdentity."""
        return UserIdentity(
            id=str(user_data.get("id", "")),
            name=user_data.get("username") or user_data.get("first_name", "Unknown"),
            platform_username=user_data.get("username"),
            first_name=user_data.get("first_name"),
            last_name=user_data.get("last_name"),
            is_bot=user_data.get("is_bot", False),
            language_code=user_data.get("language_code"),
            metadata={
                "is_premium": user_data.get("is_premium", False),
                "added_to_attachment_menu": user_data.get("added_to_attachment_menu", False),
            },
        )

    def _parse_content(
        self, raw_data: dict[str, Any]
    ) -> tuple[MessageType, str, list[Attachment]]:
        """Parse message content and determine message type."""
        attachments: list[Attachment] = []

        if "text" in raw_data:
            return MessageType.TEXT, raw_data["text"], attachments

        if "caption" in raw_data:
            caption = raw_data["caption"]
        else:
            caption = ""

        if "photo" in raw_data:
            photos = raw_data["photo"]
            best = max(photos, key=lambda p: p.get("file_size", 0))
            attachments.append(Attachment(
                url=best.get("file_id", ""),
                mime_type="image/jpeg",
                width=best.get("width"),
                height=best.get("height"),
                size_bytes=best.get("file_size"),
            ))
            return MessageType.IMAGE, caption, attachments

        if "document" in raw_data:
            doc = raw_data["document"]
            attachments.append(Attachment(
                url=doc.get("file_id", ""),
                filename=doc.get("file_name"),
                mime_type=doc.get("mime_type"),
                size_bytes=doc.get("file_size"),
            ))
            return MessageType.FILE, caption, attachments

        if "voice" in raw_data:
            voice = raw_data["voice"]
            attachments.append(Attachment(
                url=voice.get("file_id", ""),
                mime_type=voice.get("mime_type", "audio/ogg"),
                duration_ms=voice.get("duration", 0) * 1000,
                size_bytes=voice.get("file_size"),
            ))
            return MessageType.AUDIO, caption, attachments

        if "video" in raw_data:
            video = raw_data["video"]
            attachments.append(Attachment(
                url=video.get("file_id", ""),
                mime_type=video.get("mime_type", "video/mp4"),
                width=video.get("width"),
                height=video.get("height"),
                duration_ms=video.get("duration", 0) * 1000,
                size_bytes=video.get("file_size"),
            ))
            return MessageType.VIDEO, caption, attachments

        if "video_note" in raw_data:
            video_note = raw_data["video_note"]
            attachments.append(Attachment(
                url=video_note.get("file_id", ""),
                mime_type="video/mp4",
                duration_ms=video_note.get("duration", 0) * 1000,
                size_bytes=video_note.get("file_size"),
            ))
            return MessageType.VIDEO, caption, attachments

        if "audio" in raw_data:
            audio = raw_data["audio"]
            attachments.append(Attachment(
                url=audio.get("file_id", ""),
                filename=audio.get("file_name"),
                mime_type=audio.get("mime_type", "audio/mpeg"),
                duration_ms=audio.get("duration", 0) * 1000,
                size_bytes=audio.get("file_size"),
            ))
            return MessageType.AUDIO, caption, attachments

        if "sticker" in raw_data:
            sticker = raw_data["sticker"]
            attachments.append(Attachment(
                url=sticker.get("file_id", ""),
                mime_type="image/webp" if not sticker.get("is_video") else "video/webm",
                width=sticker.get("width"),
                height=sticker.get("height"),
                size_bytes=sticker.get("file_size"),
            ))
            return MessageType.STICKER, caption, attachments

        if "location" in raw_data:
            loc = raw_data["location"]
            return MessageType.LOCATION, f"{loc['latitude']},{loc['longitude']}", attachments

        if "contact" in raw_data:
            contact = raw_data["contact"]
            return MessageType.CONTACT, contact.get("phone_number", ""), attachments

        if "poll" in raw_data:
            return MessageType.POLL, raw_data["poll"].get("question", ""), attachments

        return MessageType.TEXT, "", attachments

    async def send_message(self, message: OutgoingMessage) -> Optional[str]:
        """Send a message via Telegram Bot API."""
        try:
            if message.message_type == MessageType.TEXT:
                return await self._send_text(message)
            elif message.message_type == MessageType.IMAGE:
                return await self._send_photo(message)
            elif message.message_type == MessageType.FILE:
                return await self._send_document(message)
            elif message.message_type == MessageType.AUDIO:
                return await self._send_audio(message)
            elif message.message_type == MessageType.VIDEO:
                return await self._send_video(message)
            else:
                return await self._send_text(message)
        except TelegramRateLimited as exc:
            self._logger.warning("Rate limited, retrying after %ds", exc.retry_after)
            await asyncio.sleep(exc.retry_after)
            return await self.send_message(message)
        except Exception as exc:
            self._logger.error("Failed to send message: %s", exc)
            self._health.record_error(str(exc))
            return None

    async def _send_text(self, message: OutgoingMessage) -> Optional[str]:
        """Send a text message."""
        data: dict[str, Any] = {
            "chat_id": message.conversation_id,
            "text": message.content,
        }

        if message.format == MessageFormat.HTML:
            data["parse_mode"] = "HTML"
        elif message.format == MessageFormat.MARKDOWN_V2:
            data["parse_mode"] = "MarkdownV2"

        if message.reply_to_message_id:
            data["reply_to_message_id"] = message.reply_to_message_id

        if message.buttons:
            data["reply_markup"] = {"inline_keyboard": message.buttons}

        if message.metadata.get("disable_notification"):
            data["disable_notification"] = True

        result = self._call_api("sendMessage", data)
        if result:
            self._health.messages_sent += 1
            return str(result.get("message_id"))
        return None

    async def _send_photo(self, message: OutgoingMessage) -> Optional[str]:
        """Send a photo."""
        data: dict[str, Any] = {
            "chat_id": message.conversation_id,
        }

        if message.attachments:
            data["photo"] = message.attachments[0].url

        if message.content:
            data["caption"] = message.content
            if message.format == MessageFormat.HTML:
                data["parse_mode"] = "HTML"

        if message.reply_to_message_id:
            data["reply_to_message_id"] = message.reply_to_message_id

        if message.buttons:
            data["reply_markup"] = {"inline_keyboard": message.buttons}

        result = self._call_api("sendPhoto", data)
        if result:
            self._health.messages_sent += 1
            return str(result.get("message_id"))
        return None

    async def _send_document(self, message: OutgoingMessage) -> Optional[str]:
        """Send a document."""
        data: dict[str, Any] = {
            "chat_id": message.conversation_id,
        }

        if message.attachments:
            data["document"] = message.attachments[0].url

        if message.content:
            data["caption"] = message.content

        if message.reply_to_message_id:
            data["reply_to_message_id"] = message.reply_to_message_id

        result = self._call_api("sendDocument", data)
        if result:
            self._health.messages_sent += 1
            return str(result.get("message_id"))
        return None

    async def _send_audio(self, message: OutgoingMessage) -> Optional[str]:
        """Send an audio/voice message."""
        data: dict[str, Any] = {
            "chat_id": message.conversation_id,
        }

        if message.attachments:
            data["audio"] = message.attachments[0].url

        if message.content:
            data["caption"] = message.content

        result = self._call_api("sendAudio", data)
        if result:
            self._health.messages_sent += 1
            return str(result.get("message_id"))
        return None

    async def _send_video(self, message: OutgoingMessage) -> Optional[str]:
        """Send a video message."""
        data: dict[str, Any] = {
            "chat_id": message.conversation_id,
        }

        if message.attachments:
            data["video"] = message.attachments[0].url

        if message.content:
            data["caption"] = message.content

        if message.reply_to_message_id:
            data["reply_to_message_id"] = message.reply_to_message_id

        result = self._call_api("sendVideo", data)
        if result:
            self._health.messages_sent += 1
            return str(result.get("message_id"))
        return None

    async def send_inline_keyboard(
        self,
        conversation_id: str,
        text: str,
        keyboard: list[list[dict[str, Any]]],
        format: MessageFormat = MessageFormat.PLAIN,
    ) -> Optional[str]:
        """
        Send a message with an inline keyboard.

        Args:
            conversation_id: Chat ID to send to.
            text: Message text.
            keyboard: List of rows, each row is a list of InlineKeyboardButton dicts.
            format: Message format.

        Returns:
            Message ID if successful.
        """
        message = OutgoingMessage(
            content=text,
            channel_type=ChannelType.TELEGRAM,
            conversation_id=conversation_id,
            message_type=MessageType.TEXT,
            format=format,
            buttons=keyboard,
        )
        return await self.send_message(message)

    async def send_poll(
        self,
        conversation_id: str,
        question: str,
        options: list[str],
        is_anonymous: bool = True,
        allows_multiple_answers: bool = False,
    ) -> Optional[str]:
        """Send a poll message."""
        data = {
            "chat_id": conversation_id,
            "question": question,
            "options": options,
            "is_anonymous": is_anonymous,
            "allows_multiple_answers": allows_multiple_answers,
        }
        result = self._call_api("sendPoll", data)
        if result:
            self._health.messages_sent += 1
            return str(result.get("message_id"))
        return None

    async def send_chat_action(self, conversation_id: str, action: str = "typing") -> bool:
        """
        Send a chat action (typing, uploading_photo, etc.).

        Args:
            conversation_id: Chat ID.
            action: Action type (typing, upload_photo, record_video, etc.).
        """
        data = {"chat_id": conversation_id, "action": action}
        result = self._call_api("sendChatAction", data)
        return result is not None

    async def edit_message_text(
        self,
        conversation_id: str,
        message_id: str,
        new_text: str,
        format: MessageFormat = MessageFormat.PLAIN,
    ) -> bool:
        """Edit message text."""
        data: dict[str, Any] = {
            "chat_id": conversation_id,
            "message_id": message_id,
            "text": new_text,
        }
        if format == MessageFormat.HTML:
            data["parse_mode"] = "HTML"
        elif format == MessageFormat.MARKDOWN_V2:
            data["parse_mode"] = "MarkdownV2"

        result = self._call_api("editMessageText", data)
        return result is not None

    async def delete_message(self, conversation_id: str, message_id: str) -> bool:
        """Delete a message."""
        data = {"chat_id": conversation_id, "message_id": message_id}
        result = self._call_api("deleteMessage", data)
        return result is not None

    async def download_file(self, file_id: str, local_path: str) -> bool:
        """Download a file from Telegram."""
        try:
            file_info = self._call_api("getFile", {"file_id": file_id})
            if not file_info:
                return False

            file_path = file_info.get("file_path")
            if not file_path:
                return False

            url = self._file_url(file_path)

            if self._session is None:
                self._session = requests.Session()

            response = self._session.get(url, timeout=60)
            response.raise_for_status()

            with open(local_path, "wb") as f:
                f.write(response.content)

            return True

        except Exception as exc:
            self._logger.error("File download failed: %s", exc)
            return False

    async def get_user(self, user_id: str) -> Optional[UserIdentity]:
        """Get user info (limited by Telegram API - only works for chat members)."""
        return None

    async def get_chat_info(self, chat_id: str) -> Optional[dict[str, Any]]:
        """Get chat information."""
        result = self._call_api("getChat", {"chat_id": chat_id})
        return result

    async def get_chat_administrators(self, chat_id: str) -> list[dict[str, Any]]:
        """Get list of chat administrators."""
        result = self._call_api("getChatAdministrators", {"chat_id": chat_id})
        return result or []

    async def ban_chat_member(self, chat_id: str, user_id: str) -> bool:
        """Ban a user from a chat."""
        data = {"chat_id": chat_id, "user_id": user_id}
        result = self._call_api("banChatMember", data)
        return result is not None

    async def unban_chat_member(self, chat_id: str, user_id: str) -> bool:
        """Unban a user from a chat."""
        data = {"chat_id": chat_id, "user_id": user_id}
        result = self._call_api("unbanChatMember", data)
        return result is not None

    async def promote_chat_member(
        self,
        chat_id: str,
        user_id: str,
        permissions: Optional[dict[str, bool]] = None,
    ) -> bool:
        """Promote a chat member with specific permissions."""
        data: dict[str, Any] = {"chat_id": chat_id, "user_id": user_id}
        if permissions:
            data.update(permissions)
        result = self._call_api("promoteChatMember", data)
        return result is not None

    async def set_chat_title(self, chat_id: str, title: str) -> bool:
        """Set a chat title."""
        data = {"chat_id": chat_id, "title": title}
        result = self._call_api("setChatTitle", data)
        return result is not None

    async def set_chat_description(self, chat_id: str, description: str) -> bool:
        """Set a chat description."""
        data = {"chat_id": chat_id, "description": description}
        result = self._call_api("setChatDescription", data)
        return result is not None

    async def pin_chat_message(
        self,
        chat_id: str,
        message_id: str,
        disable_notification: bool = False,
    ) -> bool:
        """Pin a message in a chat."""
        data = {
            "chat_id": chat_id,
            "message_id": message_id,
            "disable_notification": disable_notification,
        }
        result = self._call_api("pinChatMessage", data)
        return result is not None

    async def unpin_chat_message(self, chat_id: str, message_id: Optional[str] = None) -> bool:
        """Unpin a message in a chat."""
        data: dict[str, Any] = {"chat_id": chat_id}
        if message_id:
            data["message_id"] = message_id
        result = self._call_api("unpinChatMessage", data)
        return result is not None

    async def leave_chat(self, chat_id: str) -> bool:
        """Leave a chat."""
        result = self._call_api("leaveChat", {"chat_id": chat_id})
        return result is not None

    async def get_user_profile_photos(
        self, user_id: str, offset: int = 0, limit: int = 1
    ) -> Optional[dict[str, Any]]:
        """Get user profile photos."""
        data = {"user_id": user_id, "offset": offset, "limit": limit}
        return self._call_api("getUserProfilePhotos", data)

    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: Optional[str] = None,
        show_alert: bool = False,
    ) -> bool:
        """Answer a callback query (inline button press)."""
        data: dict[str, Any] = {"callback_query_id": callback_query_id}
        if text:
            data["text"] = text
        if show_alert:
            data["show_alert"] = True
        result = self._call_api("answerCallbackQuery", data)
        return result is not None

    async def process_webhook(self, request_data: dict[str, Any]) -> None:
        """
        Process a webhook update (for webhook mode).

        Call this from your webhook endpoint handler.

        Args:
            request_data: Parsed JSON from the webhook POST body.
        """
        await self._handle_update(request_data)

    async def _health_check(self) -> None:
        """Check Telegram API connectivity."""
        result = self._call_api("getMe", timeout=10)
        if not result:
            raise TelegramError(0, "Health check failed")

    def handle_webhook_request(self, request_data: dict[str, Any]) -> None:
        """
        Synchronous webhook handler for use in Flask/FastAPI/etc.

        This schedules async processing in the background.
        """
        if self._is_running:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self.process_webhook(request_data))
            else:
                loop.run_until_complete(self.process_webhook(request_data))

    async def start_polling(self) -> None:
        """Start the long polling loop. Call this after start()."""
        if self._mode != "polling":
            self._logger.warning("Polling not available in webhook mode")
            return

        self._poll_task = asyncio.create_task(self._poll_updates())
        try:
            await self._poll_task
        except asyncio.CancelledError:
            pass


class TelegramError(Exception):
    """Telegram API error."""

    def __init__(self, error_code: int, description: str) -> None:
        self.error_code = error_code
        self.description = description
        super().__init__(f"Telegram API error {error_code}: {description}")


class TelegramRateLimited(TelegramError):
    """Telegram rate limit exceeded."""

    def __init__(self, retry_after: int, description: str) -> None:
        self.retry_after = retry_after
        super().__init__(429, f"Rate limited. Retry after {retry_after}s: {description}")
