"""
MCP Transport Layer - Stdio, HTTP, and SSE transports
=====================================================
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from neugi_swarm_v2.mcp.messages import JSONRPCMessage, NotificationMessage, RequestMessage, ResponseMessage

logger = logging.getLogger(__name__)


class TransportError(Exception):
    """Transport-level error."""
    pass


class RateLimiter:
    """Token bucket rate limiter for SSE connections."""

    def __init__(self, tokens_per_second: float = 10, burst: int = 20):
        import time as _time
        self.tokens_per_second = tokens_per_second
        self.max_tokens = burst
        self._tokens = float(burst)
        self._last_refill = _time.time()
        self._lock = asyncio.Lock()

    async def acquire(self) -> bool:
        import time as _time
        async with self._lock:
            now = _time.time()
            elapsed = now - self._last_refill
            self._tokens = min(self.max_tokens, self._tokens + elapsed * self.tokens_per_second)
            self._last_refill = now
            if self._tokens < 1:
                return False
            self._tokens -= 1
            return True


class SSEAuth:
    """Simple token-based authentication for SSE connections."""

    def __init__(self, tokens: dict[str, str] | None = None):
        self._tokens: dict[str, str] = tokens or {}
        self._enabled = bool(tokens)

    def enable(self, tokens: dict[str, str]) -> None:
        self._tokens = tokens
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False
        self._tokens = {}

    def validate(self, token: str) -> str | None:
        if not self._enabled:
            return "anonymous"
        for name, t in self._tokens.items():
            if t == token:
                return name
        return None

    @property
    def is_enabled(self) -> bool:
        return self._enabled and bool(self._tokens)


class SSEConnection:
    """Server-Sent Events connection for browser-based MCP clients."""

    def __init__(self, session_id: str, rate_limiter: RateLimiter | None = None, client_name: str = "anonymous"):
        self.session_id = session_id
        self._queue: asyncio.Queue = asyncio.Queue()
        self._subscribed_events: list[str] = []
        self._active = True
        self._rate_limiter = rate_limiter
        self.client_name = client_name

    def subscribe(self, event_name: str) -> None:
        if event_name not in self._subscribed_events:
            self._subscribed_events.append(event_name)

    def unsubscribe(self, event_name: str) -> None:
        self._subscribed_events = [e for e in self._subscribed_events if e != event_name]

    async def push(self, event_type: str, data: dict[str, Any]) -> None:
        if not self._active:
            return
        if self._rate_limiter:
            allowed = await self._rate_limiter.acquire()
            if not allowed:
                return
        event = self._format_event(event_type, data)
        await self._queue.put(event)

    def _format_event(self, event_type: str, data: dict[str, Any]) -> str:
        lines = [f"event: {event_type}"]
        payload = json.dumps(data, default=str)
        for line in payload.split("\n"):
            lines.append(f"data: {line}")
        lines.append("")
        lines.append("")
        return "\n".join(lines)

    async def get_event(self, timeout: float = 30.0) -> str | None:
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return ":keep-alive\n\n"

    def close(self) -> None:
        self._active = False


class BaseTransport(ABC):
    """Base class for MCP transports."""

    def __init__(self) -> None:
        self._message_handlers: dict[str, Callable] = {}
        self._request_handlers: dict[str, Callable] = {}
        self._running = False

    @abstractmethod
    async def start(self, handler: Callable[[dict], Any]) -> None:
        pass

    @abstractmethod
    async def stop(self) -> None:
        pass

    @abstractmethod
    async def send(self, message: JSONRPCMessage) -> None:
        pass

    async def send_response(self, response: ResponseMessage) -> None:
        await self.send(response)

    async def send_notification(self, notification: JSONRPCMessage) -> None:
        await self.send(notification)

    async def send_request(self, request: RequestMessage) -> ResponseMessage:
        await self.send(request)
        raise NotImplementedError("Synchronous request-response not implemented in base transport")

    def on_message(self, handler: Callable[[dict], Any]) -> None:
        self._message_handlers[id(handler)] = handler

    def remove_handler(self, handler: Callable[[dict], Any]) -> None:
        self._message_handlers.pop(id(handler), None)

    async def _dispatch(self, raw_message: str) -> None:
        try:
            data = json.loads(raw_message)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse incoming message: %s", e)
            return

        msg_type = data.get("jsonrpc")
        if msg_type is None:
            for handler in self._message_handlers.values():
                handler(data)
            return

        method = data.get("method", "")

        if "id" in data and "method" in data:
            msg = RequestMessage(
                jsonrpc=data.get("jsonrpc", "2.0"),
                method=method,
                params=data.get("params"),
                id=data["id"],
            )
            for handler in self._message_handlers.values():
                handler(msg)
        elif "id" in data and "result" in data:
            msg = ResponseMessage(
                jsonrpc=data.get("jsonrpc", "2.0"),
                result=data.get("result"),
                error=data.get("error"),
                id=data["id"],
            )
            for handler in self._message_handlers.values():
                handler(msg)
        elif "id" in data and "error" in data:
            msg = ResponseMessage(
                jsonrpc=data.get("jsonrpc", "2.0"),
                result=None,
                error=data["error"],
                id=data["id"],
            )
            for handler in self._message_handlers.values():
                handler(msg)
        else:
            msg = NotificationMessage(
                jsonrpc=data.get("jsonrpc", "2.0"),
                method=method,
                params=data.get("params"),
            )
            for handler in self._message_handlers.values():
                handler(msg)


class StdioTransport(BaseTransport):
    """Stdio-based transport for local/CLI MCP connections."""

    def __init__(self) -> None:
        super().__init__()
        self._reader_task: asyncio.Task | None = None
        self._running = False

    async def start(self, handler: Callable[[dict], Any]) -> None:
        self._running = True
        self.on_message(handler)
        logger.info("MCP Stdio transport started")
        try:
            loop = asyncio.get_event_loop()
            self._reader_task = loop.create_task(self._read_loop())
            await self._reader_task
        except asyncio.CancelledError:
            logger.info("MCP Stdio transport stopped")
        except Exception as e:
            logger.error("MCP Stdio transport error: %s", e)
        finally:
            self._running = False

    async def _read_loop(self) -> None:
        loop = asyncio.get_event_loop()
        while self._running:
            try:
                line = await loop.run_in_executor(None, self._read_line)
                if line is None or line == "":
                    break
                line = line.strip()
                if line:
                    await self._dispatch(line)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Stdio read error: %s", e)
                await asyncio.sleep(0.01)

    def _read_line(self) -> str | None:
        try:
            return sys.stdin.readline()
        except OSError:
            return None

    async def stop(self) -> None:
        self._running = False
        if self._reader_task and not self._reader_task.done():
            self._reader_task.cancel()
        logger.info("MCP Stdio transport stopping")

    async def send(self, message: JSONRPCMessage) -> None:
        try:
            sys.stdout.write(message.to_json() + "\n")
            sys.stdout.flush()
        except OSError as e:
            logger.error("Stdio write error: %s", e)


class HTTPTransport(BaseTransport):
    """HTTP-based transport with SSE support for browser-based MCP clients."""

    def __init__(self, host: str = "127.0.0.1", port: int = 17902,
                 cors_origins: list[str] | None = None,
                 enable_sse: bool = True,
                 rate_limit: float = 10, rate_burst: int = 20,
                 auth_tokens: dict[str, str] | None = None):
        super().__init__()
        self.host = host
        self.port = port
        self.cors_origins = cors_origins or ["*"]
        self._server: asyncio.AbstractServer | None = None
        self._sessions: dict[str, asyncio.Queue] = {}
        self._session_counter = 0
        self._enable_sse = enable_sse
        self._sse_connections: dict[str, SSEConnection] = {}
        self._rate_limiter = RateLimiter(rate_limit, rate_burst)
        self._auth = SSEAuth(auth_tokens)

    @property
    def sse_connections(self) -> dict[str, SSEConnection]:
        return dict(self._sse_connections)

    async def start(self, handler: Callable[[dict], Any]) -> None:
        self._running = True
        self.on_message(handler)
        loop = asyncio.get_event_loop()
        self._server = await loop.create_server(
            lambda: HTTPConnection(self, handler),
            self.host,
            self.port,
        )
        logger.info("MCP HTTP transport started at http://%s:%s", self.host, self.port)
        if self._enable_sse:
            logger.info("SSE endpoint available at /sse")
        auth_status = "enabled" if self._auth.is_enabled else "disabled"
        logger.info("SSE auth: %s", auth_status)
        logger.info("SSE rate limit: %.1f/s (burst: %d)", self._rate_limiter.tokens_per_second, self._rate_limiter.max_tokens)
        async with self._server:
            await self._server.serve_forever()

    async def stop(self) -> None:
        self._running = False
        for sse in self._sse_connections.values():
            sse.close()
        self._sse_connections.clear()
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        logger.info("MCP HTTP transport stopped")

    async def send(self, message: JSONRPCMessage) -> None:
        pass

    async def publish_sse_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Publish an event to all SSE subscribers."""
        disconnected = []
        for conn_id, conn in self._sse_connections.items():
            if not conn._active:
                disconnected.append(conn_id)
                continue
            if not conn._subscribed_events or event_type in conn._subscribed_events:
                try:
                    await conn.push(event_type, data)
                except Exception:
                    disconnected.append(conn_id)
        for conn_id in disconnected:
            self._sse_connections.pop(conn_id, None)

    def register_sse_connection(self, conn: SSEConnection) -> None:
        self._sse_connections[conn.session_id] = conn

    def unregister_sse_connection(self, session_id: str) -> None:
        self._sse_connections.pop(session_id, None)

    def set_auth_tokens(self, tokens: dict[str, str]) -> None:
        self._auth.enable(tokens)

    def disable_auth(self) -> None:
        self._auth.disable()

    @property
    def auth_enabled(self) -> bool:
        return self._auth.is_enabled


class HTTPConnection(asyncio.Protocol):
    """HTTP connection handler supporting JSON-RPC and SSE."""

    def __init__(self, transport: HTTPTransport, handler: Callable):
        self.transport = transport
        self.handler = handler
        self._buffer = b""
        self._session_id: str | None = None
        self._is_sse = False

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self._transport = transport
        self._session_id = f"session-{self.transport._session_counter}"
        self.transport._session_counter += 1
        self.transport._sessions[self._session_id] = asyncio.Queue()
        logger.debug("New HTTP MCP connection: %s", self._session_id)

    def data_received(self, data: bytes) -> None:
        self._buffer += data
        raw = self._buffer.decode("utf-8", errors="replace")

        # Check for SSE upgrade request
        if "GET " in raw and "/sse" in raw.split("GET ")[1].split(" ")[0]:
            self._handle_sse_request()
            return

        if b"\r\n\r\n" in self._buffer:
            request, _, self._buffer = self._buffer.partition(b"\r\n\r\n")
            content_length = 0
            for line in request.decode("utf-8", errors="replace").split("\r\n"):
                if line.lower().startswith("content-length:"):
                    try:
                        content_length = int(line.split(":")[1].strip())
                    except (ValueError, IndexError):
                        pass
                    break
            if len(self._buffer) >= content_length and content_length > 0:
                json_body = self._buffer[:content_length]
                self._buffer = self._buffer[content_length:]
                try:
                    message = json.loads(json_body.decode("utf-8"))
                    asyncio.create_task(self._handle_message(message))
                except json.JSONDecodeError:
                    self._send_error(400, "Invalid JSON")

    def _handle_sse_request(self) -> None:
        try:
            headers = self._buffer.decode("utf-8", errors="replace")
            event_filter = ""
            auth_token = ""

            params = headers.split("?")[1].split(" ")[0] if "?" in headers else ""
            for param in params.split("&"):
                if param.startswith("events="):
                    event_filter = param.split("=")[1]
                if param.startswith("token="):
                    auth_token = param.split("=")[1]

            # Validate auth token
            client_name = self.transport._auth.validate(auth_token)
            if client_name is None:
                body = json.dumps({"error": "Unauthorized: invalid or missing token"}).encode("utf-8")
                resp = (
                    "HTTP/1.1 401 Unauthorized\r\n"
                    "Content-Type: application/json\r\n"
                    f"Content-Length: {len(body)}\r\n"
                    "\r\n"
                ).encode() + body
                self._transport.write(resp)
                return

            response = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: text/event-stream\r\n"
                "Cache-Control: no-cache\r\n"
                "Connection: keep-alive\r\n"
                f"Mcp-Session-Id: {self._session_id}\r\n"
                f"Access-Control-Allow-Origin: {self.transport.cors_origins[0] if self.transport.cors_origins else '*'}\r\n"
                "\r\n"
            )
            self._transport.write(response.encode("utf-8"))
            self._is_sse = True

            sse_conn = SSEConnection(
                session_id=self._session_id,
                rate_limiter=self.transport._rate_limiter,
                client_name=client_name,
            )
            if event_filter:
                for event in event_filter.split(","):
                    sse_conn.subscribe(event.strip())
            self.transport.register_sse_connection(sse_conn)
            self._sse_conn = sse_conn
            logger.info("SSE connection: %s (client: %s, filter: %s)", self._session_id, client_name, event_filter)

            asyncio.create_task(self._send_sse_event("connected", {
                "session_id": self._session_id,
                "client_name": client_name,
                "timestamp": __import__('datetime').datetime.now().isoformat(),
            }))
        except Exception as e:
            logger.error("SSE upgrade failed: %s", e)
            self._send_error(500, str(e))

    async def _send_sse_event(self, event_type: str, data: dict) -> None:
        try:
            payload = json.dumps(data, default=str)
            message = f"event: {event_type}\n"
            for line in payload.split("\n"):
                message += f"data: {line}\n"
            message += "\n"
            self._transport.write(message.encode("utf-8"))
        except Exception as e:
            logger.error("SSE send error: %s", e)

    async def _handle_message(self, message: dict) -> None:
        await self._async_handle(message)

    async def _async_handle(self, message: dict) -> None:
        try:
            response = await self.handler(message)
            if response:
                self._send_json(response.to_dict() if hasattr(response, "to_dict") else response)
        except Exception as e:
            self._send_error(500, str(e))

    def _send_json(self, data: dict) -> None:
        body = json.dumps(data).encode("utf-8")
        response = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Mcp-Session-Id: {self._session_id}\r\n"
            f"Access-Control-Allow-Origin: {self.transport.cors_origins[0] if self.transport.cors_origins else '*'}\r\n"
            "\r\n"
        ).encode() + body
        self._transport.write(response)

    def _send_error(self, status: int, message: str) -> None:
        body = json.dumps({"error": message}).encode("utf-8")
        response = (
            f"HTTP/1.1 {status} Error\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            "\r\n"
        ).encode() + body
        self._transport.write(response)

    def connection_lost(self, exc: Exception | None) -> None:
        if self._is_sse and self._session_id:
            self.transport.unregister_sse_connection(self._session_id)
            logger.debug("SSE connection lost: %s", self._session_id)
        elif self._session_id:
            self.transport._sessions.pop(self._session_id, None)
            logger.debug("HTTP MCP connection lost: %s", self._session_id)
