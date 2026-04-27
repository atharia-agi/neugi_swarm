"""
WhatsApp channel integration for NEUGI v2.

Supports Meta WhatsApp Cloud API for message handling, template messages,
interactive messages, media management, and webhook processing.
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

WHATSAPP_API_BASE = "https://graph.facebook.com/v18.0"


class WhatsAppChannel(BaseChannel):
    """
    WhatsApp Cloud API integration.

    Supports Meta's WhatsApp Cloud API for sending and receiving messages.
    Handles text, image, document, audio, video, location, and contact messages.
    Provides template messages, interactive buttons/lists, and media management.

    Args:
        token: Meta access token.
        phone_number_id: WhatsApp Business phone number ID.
        phone_number: WhatsApp Business phone number (for verification).
        app_secret: Meta app secret for webhook verification.
        bot_name: Optional display name.
        health_check_interval: Seconds between health checks.
    """

    def __init__(
        self,
        token: str,
        phone_number_id: str,
        phone_number: Optional[str] = None,
        app_secret: Optional[str] = None,
        bot_name: Optional[str] = None,
        health_check_interval: int = 60,
    ) -> None:
        super().__init__(token, bot_name, health_check_interval)
        self._phone_number_id = phone_number_id
        self._phone_number = phone_number
        self._app_secret = app_secret
        self._session: Optional[requests.Session] = None
        self._business_account_id: Optional[str] = None
        self._templates: dict[str, dict[str, Any]] = {}

    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.WHATSAPP

    def _headers(self) -> dict[str, str]:
        """Build standard WhatsApp API headers."""
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "User-Agent": "NEUGI-v2/1.0",
        }

    def _call_api(
        self,
        endpoint: str,
        method: str = "POST",
        data: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        """
        Make a synchronous API call to WhatsApp Cloud API.

        Args:
            endpoint: API endpoint path.
            method: HTTP method.
            data: JSON payload.
            params: Query parameters.

        Returns:
            Parsed JSON response or None on failure.
        """
        url = f"{WHATSAPP_API_BASE}{endpoint}"

        if self._session is None:
            self._session = requests.Session()

        try:
            if method == "GET":
                response = self._session.get(
                    url, headers=self._headers(), params=params, timeout=30,
                )
            elif method == "POST":
                response = self._session.post(
                    url, headers=self._headers(), json=data, params=params, timeout=30,
                )
            elif method == "DELETE":
                response = self._session.delete(
                    url, headers=self._headers(), params=params, timeout=30,
                )
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 204:
                return {}

            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 1))
                raise WhatsAppRateLimited(retry_after)

            error_data = response.json() if response.text else {}
            error_msg = error_data.get("error", {}).get("message", "Unknown error")
            raise WhatsAppError(error_msg, response.status_code)

        except requests.exceptions.Timeout:
            self._logger.error("WhatsApp API timeout: %s", endpoint)
            self._health.record_error(f"Timeout on {endpoint}")
            return None
        except requests.exceptions.ConnectionError:
            self._logger.error("WhatsApp API connection error: %s", endpoint)
            self._health.record_error(f"Connection error on {endpoint}")
            return None
        except (WhatsAppRateLimited, WhatsAppError):
            raise
        except Exception as exc:
            self._logger.error("WhatsApp API error: %s", exc)
            self._health.record_error(str(exc))
            return None

    def verify_webhook(
        self,
        mode: str,
        token: str,
        challenge: str,
        verify_token: str,
    ) -> Optional[str]:
        """
        Verify webhook subscription (GET request from Meta).

        Args:
            mode: Should be "subscribe".
            token: Hub verify token sent by Meta.
            challenge: Challenge string to echo back.
            verify_token: Your configured verify token.

        Returns:
            Challenge string if valid, None otherwise.
        """
        if mode == "subscribe" and token == verify_token:
            return challenge
        return None

    def verify_signature(self, signature: str, body: bytes) -> bool:
        """
        Verify webhook request signature.

        Args:
            signature: X-Hub-Signature-256 header.
            body: Raw request body bytes.

        Returns:
            True if signature is valid.
        """
        if not self._app_secret:
            return True

        import hashlib
        import hmac

        expected = hmac.new(
            self._app_secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(f"sha256={expected}", signature)

    async def _connect(self) -> None:
        """Initialize WhatsApp Cloud API connection."""
        self._session = requests.Session()

        try:
            phone_info = self._call_api(
                f"/{self._phone_number_id}",
                method="GET",
                params={"fields": "id,display_name,quality_rating,status"},
            )
            if phone_info:
                self._bot_name = phone_info.get("display_name", self._bot_name)
                self._logger.info("Connected to WhatsApp Business: %s",
                                  phone_info.get("display_name"))
            else:
                raise WhatsAppError("Failed to get phone number info")

            account_info = self._call_api(
                f"/{self._phone_number_id}",
                method="GET",
                params={"fields": "messaging_product,phone_numbers"},
            )
            if account_info:
                self._logger.info("Messaging product: %s",
                                  account_info.get("messaging_product"))

        except Exception:
            if self._session:
                self._session.close()
                self._session = None
            raise

    async def _disconnect(self) -> None:
        """Close WhatsApp Cloud API connection."""
        if self._session:
            self._session.close()
            self._session = None

        self._logger.info("WhatsApp channel disconnected")

    async def _build_capabilities(self) -> ChannelCapabilities:
        """Build WhatsApp channel capabilities."""
        caps = ChannelCapabilities()
        caps.supported_message_types = {
            MessageType.TEXT, MessageType.IMAGE, MessageType.FILE,
            MessageType.AUDIO, MessageType.VIDEO, MessageType.LOCATION,
            MessageType.CONTACT,
        }
        caps.supported_formats = {MessageFormat.PLAIN}
        caps.max_message_length = 4096
        caps.max_attachments = 1
        caps.max_attachment_size_mb = 16
        caps.supports_threads = False
        caps.supports_reactions = False
        caps.supports_editing = False
        caps.supports_deletion = False
        caps.supports_keyboard = True
        caps.supports_embeds = False
        caps.supports_voice = True
        caps.supports_polls = False
        caps.supports_templates = True
        caps.supports_scheduled = False
        caps.native_rate_limits = {
            "tier_free": 50,
            "tier_low": 250,
            "tier_medium": 1000,
            "tier_high": 100000,
            "per_day": True,
        }
        return caps

    async def _parse_message(self, raw_data: dict[str, Any]) -> Optional[IncomingMessage]:
        """Parse raw WhatsApp message data into IncomingMessage."""
        entry = raw_data.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})

        if "messages" not in value:
            return None

        msg = value["messages"][0]
        from_id = msg.get("from", "")
        msg_type = msg.get("type", "text")

        user = UserIdentity(
            id=from_id,
            name=from_id,
            metadata={
                "profile": value.get("contacts", [{}])[0].get("profile", {}),
            },
        )

        if user.metadata["profile"].get("name"):
            user.name = user.metadata["profile"]["name"]

        content, attachments = self._parse_content(msg, msg_type)

        message_type_map = {
            "text": MessageType.TEXT,
            "image": MessageType.IMAGE,
            "document": MessageType.FILE,
            "audio": MessageType.AUDIO,
            "video": MessageType.VIDEO,
            "sticker": MessageType.STICKER,
            "location": MessageType.LOCATION,
            "contacts": MessageType.CONTACT,
            "reaction": MessageType.REACTION,
            "interactive": MessageType.TEXT,
            "button": MessageType.TEXT,
            "template": MessageType.TEXT,
            "system": MessageType.SYSTEM,
            "order": MessageType.TEXT,
        }

        return IncomingMessage(
            message_id=msg.get("id", ""),
            channel_type=ChannelType.WHATSAPP,
            user=user,
            content=content,
            message_type=message_type_map.get(msg_type, MessageType.TEXT),
            conversation_type=ConversationType.DM,
            conversation_id=from_id,
            timestamp=float(msg.get("timestamp", time.time())),
            raw_payload=raw_data,
            attachments=attachments,
            metadata={
                "waba_id": value.get("metadata", {}).get("phone_number_id"),
                "display_phone": value.get("metadata", {}).get("display_phone_number"),
            },
        )

    def _parse_content(
        self, msg: dict[str, Any], msg_type: str
    ) -> tuple[str, list[Attachment]]:
        """Parse WhatsApp message content."""
        attachments: list[Attachment] = []
        content = ""

        if msg_type == "text":
            content = msg.get("text", {}).get("body", "")

        elif msg_type == "image":
            image = msg.get("image", {})
            attachments.append(Attachment(
                url=image.get("id", ""),
                mime_type=image.get("mime_type", "image/jpeg"),
                size_bytes=image.get("file_size"),
            ))
            content = image.get("caption", "")

        elif msg_type == "document":
            doc = msg.get("document", {})
            attachments.append(Attachment(
                url=doc.get("id", ""),
                filename=doc.get("filename"),
                mime_type=doc.get("mime_type"),
                size_bytes=doc.get("file_size"),
            ))
            content = doc.get("caption", "")

        elif msg_type == "audio":
            audio = msg.get("audio", {})
            attachments.append(Attachment(
                url=audio.get("id", ""),
                mime_type=audio.get("mime_type", "audio/ogg"),
                size_bytes=audio.get("file_size"),
            ))
            content = ""

        elif msg_type == "video":
            video = msg.get("video", {})
            attachments.append(Attachment(
                url=video.get("id", ""),
                mime_type=video.get("mime_type", "video/mp4"),
                size_bytes=video.get("file_size"),
            ))
            content = video.get("caption", "")

        elif msg_type == "sticker":
            sticker = msg.get("sticker", {})
            attachments.append(Attachment(
                url=sticker.get("id", ""),
                mime_type=sticker.get("mime_type", "image/webp"),
            ))
            content = ""

        elif msg_type == "location":
            loc = msg.get("location", {})
            content = f"{loc.get('latitude', '')},{loc.get('longitude', '')}"
            if loc.get("name"):
                content += f" ({loc['name']})"
            elif loc.get("address"):
                content += f" ({loc['address']})"

        elif msg_type == "contacts":
            contacts = msg.get("contacts", [])
            if contacts:
                contact = contacts[0]
                content = contact.get("name", {}).get("formatted_name", "")

        elif msg_type == "reaction":
            reaction = msg.get("reaction", {})
            content = reaction.get("emoji", "")

        elif msg_type == "interactive":
            interactive = msg.get("interactive", {})
            if interactive.get("type") == "button_reply":
                content = interactive.get("button_reply", {}).get("title", "")
            elif interactive.get("type") == "list_reply":
                content = interactive.get("list_reply", {}).get("title", "")

        elif msg_type == "button":
            content = msg.get("button", {}).get("text", "")

        elif msg_type == "system":
            system = msg.get("system", {})
            content = f"System: {system.get('body', '')}"

        return content, attachments

    async def send_message(self, message: OutgoingMessage) -> Optional[str]:
        """Send a message via WhatsApp Cloud API."""
        try:
            endpoint = f"/{self._phone_number_id}/messages"

            if message.message_type == MessageType.TEXT:
                if message.buttons:
                    return await self._send_interactive(message)
                return await self._send_text(message)
            elif message.message_type == MessageType.IMAGE:
                return await self._send_image(message)
            elif message.message_type == MessageType.FILE:
                return await self._send_document(message)
            elif message.message_type == MessageType.AUDIO:
                return await self._send_audio(message)
            elif message.message_type == MessageType.VIDEO:
                return await self._send_video(message)
            else:
                return await self._send_text(message)

        except WhatsAppRateLimited as exc:
            self._logger.warning("Rate limited, retrying after %ds", exc.retry_after)
            await asyncio.sleep(exc.retry_after)
            return await self.send_message(message)
        except Exception as exc:
            self._logger.error("Failed to send message: %s", exc)
            self._health.record_error(str(exc))
            return None

    async def _send_text(self, message: OutgoingMessage) -> Optional[str]:
        """Send a text message."""
        endpoint = f"/{self._phone_number_id}/messages"
        data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": message.conversation_id,
            "type": "text",
            "text": {"body": message.content},
        }

        if message.reply_to_message_id:
            data["context"] = {"message_id": message.reply_to_message_id}

        result = self._call_api(endpoint, data=data)
        if result:
            self._health.messages_sent += 1
            messages = result.get("messages", [])
            if messages:
                return messages[0].get("id")
        return None

    async def _send_image(self, message: OutgoingMessage) -> Optional[str]:
        """Send an image."""
        endpoint = f"/{self._phone_number_id}/messages"

        if message.attachments:
            attachment = message.attachments[0]
            if attachment.url.startswith(("http://", "https://")):
                image_data = {"link": attachment.url}
            else:
                image_data = {"id": attachment.url}
        else:
            return None

        data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": message.conversation_id,
            "type": "image",
            "image": image_data,
        }

        if message.content:
            data["image"]["caption"] = message.content

        result = self._call_api(endpoint, data=data)
        if result:
            self._health.messages_sent += 1
            messages = result.get("messages", [])
            if messages:
                return messages[0].get("id")
        return None

    async def _send_document(self, message: OutgoingMessage) -> Optional[str]:
        """Send a document."""
        endpoint = f"/{self._phone_number_id}/messages"

        if message.attachments:
            attachment = message.attachments[0]
            if attachment.url.startswith(("http://", "https://")):
                doc_data = {"link": attachment.url}
            else:
                doc_data = {"id": attachment.url}
        else:
            return None

        data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": message.conversation_id,
            "type": "document",
            "document": doc_data,
        }

        if message.content:
            data["document"]["caption"] = message.content
        if message.attachments[0].filename:
            data["document"]["filename"] = message.attachments[0].filename

        result = self._call_api(endpoint, data=data)
        if result:
            self._health.messages_sent += 1
            messages = result.get("messages", [])
            if messages:
                return messages[0].get("id")
        return None

    async def _send_audio(self, message: OutgoingMessage) -> Optional[str]:
        """Send an audio message."""
        endpoint = f"/{self._phone_number_id}/messages"

        if message.attachments:
            attachment = message.attachments[0]
            if attachment.url.startswith(("http://", "https://")):
                audio_data = {"link": attachment.url}
            else:
                audio_data = {"id": attachment.url}
        else:
            return None

        data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": message.conversation_id,
            "type": "audio",
            "audio": audio_data,
        }

        result = self._call_api(endpoint, data=data)
        if result:
            self._health.messages_sent += 1
            messages = result.get("messages", [])
            if messages:
                return messages[0].get("id")
        return None

    async def _send_video(self, message: OutgoingMessage) -> Optional[str]:
        """Send a video message."""
        endpoint = f"/{self._phone_number_id}/messages"

        if message.attachments:
            attachment = message.attachments[0]
            if attachment.url.startswith(("http://", "https://")):
                video_data = {"link": attachment.url}
            else:
                video_data = {"id": attachment.url}
        else:
            return None

        data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": message.conversation_id,
            "type": "video",
            "video": video_data,
        }

        if message.content:
            data["video"]["caption"] = message.content

        result = self._call_api(endpoint, data=data)
        if result:
            self._health.messages_sent += 1
            messages = result.get("messages", [])
            if messages:
                return messages[0].get("id")
        return None

    async def send_location(
        self,
        conversation_id: str,
        latitude: float,
        longitude: float,
        name: Optional[str] = None,
        address: Optional[str] = None,
    ) -> Optional[str]:
        """Send a location message."""
        endpoint = f"/{self._phone_number_id}/messages"
        data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": conversation_id,
            "type": "location",
            "location": {
                "longitude": longitude,
                "latitude": latitude,
            },
        }
        if name:
            data["location"]["name"] = name
        if address:
            data["location"]["address"] = address

        result = self._call_api(endpoint, data=data)
        if result:
            self._health.messages_sent += 1
            messages = result.get("messages", [])
            if messages:
                return messages[0].get("id")
        return None

    async def send_contact(
        self,
        conversation_id: str,
        contact: dict[str, Any],
    ) -> Optional[str]:
        """
        Send a contact message.

        Args:
            conversation_id: Phone number to send to.
            contact: Contact dict with name, phones, etc.
        """
        endpoint = f"/{self._phone_number_id}/messages"
        data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": conversation_id,
            "type": "contacts",
            "contacts": [contact],
        }

        result = self._call_api(endpoint, data=data)
        if result:
            self._health.messages_sent += 1
            messages = result.get("messages", [])
            if messages:
                return messages[0].get("id")
        return None

    async def _send_interactive(self, message: OutgoingMessage) -> Optional[str]:
        """Send an interactive message (buttons or list)."""
        endpoint = f"/{self._phone_number_id}/messages"

        if message.buttons:
            if len(message.buttons) <= 3:
                return await self._send_button_message(message)
            else:
                return await self._send_list_message(message)

        return await self._send_text(message)

    async def _send_button_message(self, message: OutgoingMessage) -> Optional[str]:
        """Send a message with reply buttons (max 3)."""
        endpoint = f"/{self._phone_number_id}/messages"
        buttons = []
        for i, btn in enumerate(message.buttons[:3]):
            if isinstance(btn, dict):
                buttons.append({
                    "type": "reply",
                    "reply": {
                        "id": btn.get("id", f"btn_{i}"),
                        "title": btn.get("title", btn.get("text", "Button")),
                    },
                })
            else:
                buttons.append({
                    "type": "reply",
                    "reply": {"id": f"btn_{i}", "title": str(btn)},
                })

        data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": message.conversation_id,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": message.content},
                "action": {"buttons": buttons},
            },
        }

        result = self._call_api(endpoint, data=data)
        if result:
            self._health.messages_sent += 1
            messages = result.get("messages", [])
            if messages:
                return messages[0].get("id")
        return None

    async def _send_list_message(self, message: OutgoingMessage) -> Optional[str]:
        """Send a list message (up to 10 sections)."""
        endpoint = f"/{self._phone_number_id}/messages"
        sections = []

        for section in message.buttons:
            if isinstance(section, dict):
                rows = []
                for row in section.get("rows", []):
                    rows.append({
                        "id": row.get("id", ""),
                        "title": row.get("title", ""),
                        "description": row.get("description", ""),
                    })
                sections.append({
                    "title": section.get("title", ""),
                    "rows": rows,
                })

        data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": message.conversation_id,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "header": {"type": "text", "text": message.content[:60]},
                "body": {"text": message.content},
                "action": {
                    "button": message.metadata.get("button_text", "Menu"),
                    "sections": sections,
                },
            },
        }

        result = self._call_api(endpoint, data=data)
        if result:
            self._health.messages_sent += 1
            messages = result.get("messages", [])
            if messages:
                return messages[0].get("id")
        return None

    async def send_template(
        self,
        conversation_id: str,
        template_name: str,
        language: str = "en",
        components: Optional[list[dict[str, Any]]] = None,
    ) -> Optional[str]:
        """
        Send a template message.

        Args:
            conversation_id: Phone number to send to.
            template_name: Approved template name.
            language: Language code.
            components: Template components (header, body, buttons).
        """
        endpoint = f"/{self._phone_number_id}/messages"

        template_data: dict[str, Any] = {
            "name": template_name,
            "language": {"code": language},
        }

        if components:
            template_data["components"] = components

        data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": conversation_id,
            "type": "template",
            "template": template_data,
        }

        result = self._call_api(endpoint, data=data)
        if result:
            self._health.messages_sent += 1
            messages = result.get("messages", [])
            if messages:
                return messages[0].get("id")
        return None

    async def send_template_with_buttons(
        self,
        conversation_id: str,
        template_name: str,
        buttons: list[dict[str, Any]],
        language: str = "en",
        body_variables: Optional[list[str]] = None,
    ) -> Optional[str]:
        """Send a template with interactive buttons."""
        components: list[dict[str, Any]] = []

        if body_variables:
            components.append({
                "type": "body",
                "parameters": [
                    {"type": "text", "text": var} for var in body_variables
                ],
            })

        button_components = []
        for btn in buttons:
            btn_type = btn.get("type", "quick_reply")
            if btn_type == "quick_reply":
                button_components.append({
                    "type": "button",
                    "sub_type": "quick_reply",
                    "index": btn.get("index", 0),
                    "parameters": [
                        {"type": "payload", "payload": btn.get("payload", "")}
                    ],
                })
            elif btn_type == "url":
                button_components.append({
                    "type": "button",
                    "sub_type": "url",
                    "index": btn.get("index", 0),
                    "parameters": [
                        {"type": "text", "text": btn.get("suffix", "")}
                    ],
                })
            elif btn_type == "phone":
                button_components.append({
                    "type": "button",
                    "sub_type": "phone_number",
                    "index": btn.get("index", 0),
                    "parameters": [
                        {"type": "action", "action": btn.get("phone_number", "")}
                    ],
                })

        if button_components:
            components.extend(button_components)

        return await self.send_template(
            conversation_id, template_name, language, components
        )

    async def mark_read(self, message_id: str) -> bool:
        """Mark a message as read."""
        endpoint = f"/{self._phone_number_id}/messages"
        data = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }
        result = self._call_api(endpoint, data=data)
        return result is not None

    async def mark_delivered(self, message_id: str) -> bool:
        """Mark a message as delivered."""
        endpoint = f"/{self._phone_number_id}/messages"
        data = {
            "messaging_product": "whatsapp",
            "status": "delivered",
            "message_id": message_id,
        }
        result = self._call_api(endpoint, data=data)
        return result is not None

    async def download_file(self, file_id: str, local_path: str) -> bool:
        """Download media from WhatsApp."""
        try:
            media_info = self._call_api(
                f"/{file_id}",
                method="GET",
            )
            if not media_info:
                return False

            media_url = media_info.get("url")
            if not media_url:
                return False

            if self._session is None:
                self._session = requests.Session()

            response = self._session.get(
                media_url, headers=self._headers(), timeout=60,
            )
            response.raise_for_status()

            with open(local_path, "wb") as f:
                f.write(response.content)

            return True

        except Exception as exc:
            self._logger.error("Media download failed: %s", exc)
            return False

    async def upload_media(self, file_path: str, mime_type: str) -> Optional[str]:
        """
        Upload media to WhatsApp.

        Args:
            file_path: Path to local file.
            mime_type: MIME type of the file.

        Returns:
            Media ID if successful.
        """
        endpoint = f"/{self._phone_number_id}/media"

        if self._session is None:
            self._session = requests.Session()

        try:
            with open(file_path, "rb") as f:
                files = {"file": (file_path, f, mime_type)}
                data = {"messaging_product": "whatsapp", "type": mime_type}

                response = self._session.post(
                    f"{WHATSAPP_API_BASE}{endpoint}",
                    headers={"Authorization": f"Bearer {self._token}"},
                    data=data,
                    files=files,
                    timeout=60,
                )

            if response.status_code == 200:
                result = response.json()
                return result.get("id")
            return None

        except Exception as exc:
            self._logger.error("Media upload failed: %s", exc)
            return None

    async def get_user(self, user_id: str) -> Optional[UserIdentity]:
        """Get user profile (limited by WhatsApp API)."""
        return UserIdentity(
            id=user_id,
            name=user_id,
            metadata={"phone": user_id},
        )

    async def get_phone_number_info(self) -> Optional[dict[str, Any]]:
        """Get phone number information."""
        return self._call_api(
            f"/{self._phone_number_id}",
            method="GET",
            params={"fields": "id,display_name,quality_rating,status,code_verification_status"},
        )

    async def get_message_templates(self) -> list[dict[str, Any]]:
        """Get available message templates."""
        result = self._call_api(
            f"/{self._phone_number_id}/message_templates",
            method="GET",
        )
        if result:
            return result.get("data", [])
        return []

    async def get_media_url(self, media_id: str) -> Optional[str]:
        """Get a temporary media URL."""
        result = self._call_api(f"/{media_id}", method="GET")
        if result:
            return result.get("url")
        return None

    async def delete_media(self, media_id: str) -> bool:
        """Delete uploaded media."""
        result = self._call_api(f"/{media_id}", method="DELETE")
        return result is not None

    async def process_webhook(self, request_data: dict[str, Any]) -> None:
        """
        Process a webhook event.

        Args:
            request_data: Parsed JSON from webhook POST body.
        """
        entry = request_data.get("entry", [])
        for e in entry:
            changes = e.get("changes", [])
            for change in changes:
                value = change.get("value", {})

                if "messages" in value:
                    message = await self.receive_message(request_data)
                    if message:
                        await self._notify_message_handlers(message)

                elif "statuses" in value:
                    for status in value["statuses"]:
                        self._handle_status_update(status)

    def _handle_status_update(self, status: dict[str, Any]) -> None:
        """Handle message status update."""
        message_id = status.get("id")
        msg_status = status.get("status")
        conversation = status.get("conversation", {})
        pricing = status.get("pricing", {})

        self._logger.info(
            "Message %s status: %s (conversation: %s, pricing: %s)",
            message_id, msg_status, conversation, pricing,
        )

        if msg_status == "failed":
            error = status.get("errors", [{}])[0]
            self._health.record_error(
                f"Message {message_id} failed: {error.get('title', 'Unknown')}"
            )

    async def _health_check(self) -> None:
        """Check WhatsApp API connectivity."""
        result = self._call_api(
            f"/{self._phone_number_id}",
            method="GET",
            params={"fields": "id"},
        )
        if not result:
            raise WhatsAppError("Health check failed")


class WhatsAppError(Exception):
    """WhatsApp API error."""

    def __init__(self, message: str, status_code: int = 0) -> None:
        self.status_code = status_code
        super().__init__(f"WhatsApp API error ({status_code}): {message}")


class WhatsAppRateLimited(WhatsAppError):
    """WhatsApp rate limit exceeded."""

    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__(f"Rate limited. Retry after {retry_after}s", 429)
