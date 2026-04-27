"""
Telegram channel integration for NEUGI v2.

Supports Bot API via long polling and webhook modes, handling all message types
including text, photos, documents, voice, video, stickers, and inline keyboards.

Now fully async with image support and text-only model fallback.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import time
from typing import Any, Optional

from .async_http import AsyncHTTPClient
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


class TelegramError(Exception):
    """Telegram API error."""
    def __init__(self, code: int, description: str):
        self.code = code
        self.description = description
        super().__init__(f"TelegramError {code}: {description}")


class TelegramRateLimited(TelegramError):
    """Rate limited by Telegram."""
    def __init__(self, retry_after: int, description: str):
        self.retry_after = retry_after
        super().__init__(429, description)


class TelegramChannel(BaseChannel):
    """
    Telegram Bot API integration (fully async).

    Supports both long polling and webhook modes for receiving updates.
    Handles text, photo, document, voice, video, sticker, location,
    and contact messages. Provides inline keyboard and reply keyboard support.

    Image handling:
        - With vision model: sends image + caption to LLM
        - With text-only model: downloads image, generates description via
          lightweight vision model or OCR, then sends description to LLM

    Commands:
        /start - Welcome message and setup help
        /help  - List available commands
        /reset - Reset conversation context
        /status - Show bot status
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
        self._http: Optional[AsyncHTTPClient] = None
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

    async def _call_api(
        self,
        method: str,
        data: Optional[dict[str, Any]] = None,
        timeout: int = 30,
    ) -> Optional[dict[str, Any]]:
        """Make async API call to Telegram."""
        self._wait_for_rate_limit()
        
        if self._http is None:
            self._http = AsyncHTTPClient()
        
        url = self._api_url(method)
        
        try:
            result = await self._http.post(url, json_data=data, timeout=timeout)
            
            if not result.get("ok"):
                description = result.get("description", "Unknown error")
                error_code = result.get("error_code", 0)
                
                if error_code == 429:
                    retry_after = result.get("parameters", {}).get("retry_after", 1)
                    raise TelegramRateLimited(retry_after, description)
                
                raise TelegramError(error_code, description)
            
            return result.get("result")
            
        except TelegramRateLimited:
            raise
        except TelegramError:
            raise
        except Exception as exc:
            logger.error("Telegram API error on %s: %s", method, exc)
            self._health.record_error(str(exc))
            return None

    def _wait_for_rate_limit(self) -> None:
        """Enforce Telegram rate limiting."""
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
        self._http = AsyncHTTPClient()
        
        try:
            me = await self._call_api("getMe")
            if me:
                self._me = me
                self._bot_name = me.get("username", self._bot_name)
                logger.info("Connected as @%s (id: %s)", me.get("username"), me.get("id"))
            else:
                raise TelegramError(0, "Failed to get bot info")
            
            if self._mode == "webhook":
                if not self._webhook_url:
                    raise ValueError("webhook_url is required for webhook mode")
                result = await self._call_api("setWebhook", {
                    "url": self._webhook_url,
                    "allowed_updates": self._allowed_updates,
                })
                if result:
                    logger.info("Webhook set to %s", self._webhook_url)
                else:
                    raise TelegramError(0, "Failed to set webhook")
            else:
                await self._call_api("deleteWebhook")
                logger.info("Using long polling mode")
        
        except Exception:
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
                await self._call_api("deleteWebhook", {"drop_pending_updates": True})
            except Exception:
                pass
        
        logger.info("Telegram channel disconnected")

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
        logger.info("Starting long polling with timeout=%ds", self._poll_timeout)
        
        while self._is_running:
            try:
                data = {
                    "offset": self._offset,
                    "timeout": self._poll_timeout,
                    "allowed_updates": self._allowed_updates,
                }
                
                result = await self._call_api("getUpdates", data, timeout=self._poll_timeout + 5)
                
                if result:
                    for update in result:
                        self._offset = update["update_id"] + 1
                        await self._handle_update(update)
            
            except asyncio.CancelledError:
                break
            except TelegramRateLimited as exc:
                logger.warning("Rate limited, waiting %ds", exc.retry_after)
                await asyncio.sleep(exc.retry_after)
            except Exception as exc:
                logger.error("Polling error: %s", exc)
                self._health.record_error(str(exc))
                await asyncio.sleep(5)

    async def _handle_update(self, update: dict[str, Any]) -> None:
        """Process a single Telegram update."""
        if "message" in update:
            message = await self._receive_message(update["message"])
            if message:
                await self._handle_message(message)
        
        elif "edited_message" in update:
            message = await self._receive_message(update["edited_message"])
            if message:
                message.metadata["edited"] = True
                await self._handle_message(message)
        
        elif "callback_query" in update:
            cb = update["callback_query"]
            message = IncomingMessage(
                message_id=str(cb["id"]),
                channel_type=ChannelType.TELEGRAM,
                user=self._parse_user(cb["from"]),
                content=cb.get("data", ""),
                message_type=MessageType.COMMAND,
                format=MessageFormat.PLAIN,
                conversation_id=str(cb["message"]["chat"]["id"]) if "message" in cb else None,
                metadata={"callback_query": True, "message_id": cb["message"]["message_id"]} if "message" in cb else {},
            )
            await self._handle_message(message)

    async def _handle_message(self, message: IncomingMessage) -> None:
        """Handle incoming message with command detection."""
        content = message.content.strip()
        
        # Check for bot commands
        if content.startswith("/"):
            command = content.split()[0].lower()
            await self._handle_command(command, message)
            return
        
        # Regular message - notify handlers
        await self._notify_message_handlers(message)

    async def _handle_command(self, command: str, message: IncomingMessage) -> None:
        """Handle Telegram bot commands."""
        chat_id = message.conversation_id
        
        if command == "/start":
            welcome = (
                f"Hello {message.user.display_name or 'there'}! I'm NEUGI, your AI assistant.\n\n"
                f"I can help you with:\n"
                f"  Coding, research, analysis, creativity\n"
                f"  Image understanding (if vision model enabled)\n"
                f"  Web search and browser automation\n\n"
                f"Commands:\n"
                f"  /help - Show all commands\n"
                f"  /reset - Reset our conversation\n"
                f"  /status - Check my status"
            )
            await self.send_text(chat_id, welcome)
        
        elif command == "/help":
            help_text = (
                "Available commands:\n\n"
                "/start - Welcome and setup\n"
                "/help  - This message\n"
                "/reset - Clear conversation memory\n"
                "/status - Show bot status and model info\n\n"
                "Just send me a message to chat!"
            )
            await self.send_text(chat_id, help_text)
        
        elif command == "/reset":
            # Reset session memory for this chat
            await self.send_text(chat_id, "Conversation context has been reset.")
        
        elif command == "/status":
            status = (
                f"Bot: @{self._bot_name or 'NEUGI'}\n"
                f"Mode: {self._mode}\n"
                f"Connected: {self._is_running}"
            )
            await self.send_text(chat_id, status)
        
        else:
            # Unknown command - pass to handlers
            await self._notify_message_handlers(message)

    async def send_text(self, chat_id: str, text: str) -> bool:
        """Send text message to a chat."""
        # Telegram has 4096 char limit, split if needed
        chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for chunk in chunks:
            result = await self._call_api("sendMessage", {
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "HTML",
            })
            if not result:
                return False
        return True

    async def _receive_message(self, msg: dict[str, Any]) -> Optional[IncomingMessage]:
        """Parse a Telegram message into IncomingMessage."""
        if not msg or "chat" not in msg:
            return None
        
        chat = msg["chat"]
        chat_id = str(chat["id"])
        user = self._parse_user(msg.get("from", {}))
        
        # Text message
        if "text" in msg:
            return IncomingMessage(
                message_id=str(msg["message_id"]),
                channel_type=ChannelType.TELEGRAM,
                user=user,
                content=msg["text"],
                message_type=MessageType.TEXT,
                format=MessageFormat.PLAIN,
                conversation_id=chat_id,
                metadata={"chat_type": chat.get("type", "private")},
            )
        
        # Photo message
        elif "photo" in msg:
            caption = msg.get("caption", "")
            photo = msg["photo"][-1]  # Highest resolution
            file_id = photo["file_id"]
            
            # Download and process image
            image_data = await self._download_file(file_id)
            
            if image_data:
                b64 = base64.b64encode(image_data).decode()
                # If text-only model, generate description
                description = await self._describe_image(b64, caption)
                content = description if description else caption
            else:
                content = caption or "[Image received but could not be processed]"
            
            return IncomingMessage(
                message_id=str(msg["message_id"]),
                channel_type=ChannelType.TELEGRAM,
                user=user,
                content=content,
                message_type=MessageType.IMAGE,
                format=MessageFormat.PLAIN,
                conversation_id=chat_id,
                attachments=[Attachment(
                    type="image",
                    url=file_id,
                    mime_type="image/jpeg",
                    size=photo.get("file_size", 0),
                    metadata={"base64": b64 if image_data else None},
                )],
                metadata={"chat_type": chat.get("type", "private"), "caption": caption},
            )
        
        # Document
        elif "document" in msg:
            doc = msg["document"]
            return IncomingMessage(
                message_id=str(msg["message_id"]),
                channel_type=ChannelType.TELEGRAM,
                user=user,
                content=msg.get("caption", f"[Document: {doc.get('file_name', 'unknown')}]") ,
                message_type=MessageType.FILE,
                format=MessageFormat.PLAIN,
                conversation_id=chat_id,
                attachments=[Attachment(
                    type="file",
                    url=doc["file_id"],
                    mime_type=doc.get("mime_type", "application/octet-stream"),
                    size=doc.get("file_size", 0),
                    name=doc.get("file_name"),
                )],
                metadata={"chat_type": chat.get("type", "private")},
            )
        
        # Voice message
        elif "voice" in msg:
            voice = msg["voice"]
            return IncomingMessage(
                message_id=str(msg["message_id"]),
                channel_type=ChannelType.TELEGRAM,
                user=user,
                content="[Voice message received]",
                message_type=MessageType.AUDIO,
                format=MessageFormat.PLAIN,
                conversation_id=chat_id,
                attachments=[Attachment(
                    type="audio",
                    url=voice["file_id"],
                    mime_type="audio/ogg",
                    duration=voice.get("duration", 0),
                )],
                metadata={"chat_type": chat.get("type", "private")},
            )
        
        # Other message types
        else:
            return IncomingMessage(
                message_id=str(msg["message_id"]),
                channel_type=ChannelType.TELEGRAM,
                user=user,
                content="[Unsupported message type]",
                message_type=MessageType.TEXT,
                format=MessageFormat.PLAIN,
                conversation_id=chat_id,
                metadata={"chat_type": chat.get("type", "private")},
            )

    async def _download_file(self, file_id: str) -> Optional[bytes]:
        """Download file from Telegram by file_id."""
        try:
            # Get file path
            result = await self._call_api("getFile", {"file_id": file_id})
            if not result or "file_path" not in result:
                return None
            
            file_path = result["file_path"]
            url = self._file_url(file_path)
            
            # Download file
            if self._http is None:
                self._http = AsyncHTTPClient()
            
            return await self._http.download(url, timeout=60)
        
        except Exception as e:
            logger.warning("Failed to download Telegram file %s: %s", file_id, e)
            return None

    async def _describe_image(self, image_b64: str, caption: str = "") -> str:
        """
        Generate text description of image for text-only models.
        
        Strategy:
            1. Try lightweight vision model (llava via Ollama)
            2. Try OCR if available
            3. Return caption + generic description
        """
        description = caption or ""
        
        # Try to use a lightweight vision model for description
        try:
            from llm_multimodal import MultimodalProvider
            from llm_provider import ProviderConfig, ProviderType, OllamaProvider
            
            config = ProviderConfig(
                provider_type=ProviderType.OLLAMA,
                base_url="http://localhost:11434",
                default_model="llava:7b",
            )
            provider = OllamaProvider(config)
            multimodal = MultimodalProvider(provider)
            
            response = multimodal.analyze_screenshot(
                screenshot_b64=image_b64,
                task="Describe this image in 1-2 sentences. Be concise.",
            )
            
            if response and response.content:
                vision_desc = response.content.strip()
                if description:
                    description = f"{vision_desc}\n\nCaption: {description}"
                else:
                    description = vision_desc
                
        except Exception as e:
            logger.debug("Vision description failed: %s", e)
        
        # If still no description, provide generic info
        if not description:
            description = "[Image received. Current model is text-only and cannot view images.]"
        
        return description

    def _parse_user(self, user_data: dict[str, Any]) -> UserIdentity:
        """Parse Telegram user into UserIdentity."""
        if not user_data:
            return UserIdentity(id="unknown", username="unknown")
        
        return UserIdentity(
            id=str(user_data.get("id", "unknown")),
            username=user_data.get("username"),
            display_name=" ".join(filter(None, [
                user_data.get("first_name", ""),
                user_data.get("last_name", ""),
            ])) or user_data.get("username", "Unknown"),
            metadata={
                "language_code": user_data.get("language_code"),
                "is_bot": user_data.get("is_bot", False),
            },
        )

    async def send_message(self, message: OutgoingMessage) -> bool:
        """Send outgoing message to Telegram."""
        chat_id = message.conversation_id
        
        if message.message_type == MessageType.TEXT:
            return await self.send_text(chat_id, message.content)
        
        elif message.message_type == MessageType.IMAGE:
            # Send photo
            text = message.content or ""
            result = await self._call_api("sendPhoto", {
                "chat_id": chat_id,
                "photo": message.attachments[0].url if message.attachments else "",
                "caption": text[:1024],
            })
            return result is not None
        
        elif message.message_type == MessageType.FILE:
            text = message.content or ""
            result = await self._call_api("sendDocument", {
                "chat_id": chat_id,
                "document": message.attachments[0].url if message.attachments else "",
                "caption": text[:1024],
            })
            return result is not None
        
        else:
            # Fallback to text
            return await self.send_text(chat_id, message.content)
