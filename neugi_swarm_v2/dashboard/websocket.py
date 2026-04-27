"""
NEUGI v2 WebSocket Server (stdlib-only implementation)
======================================================
RFC 6455 compliant WebSocket server using only Python stdlib.

Features:
    - WebSocket handshake with Sec-WebSocket-Accept
    - Text frame encoding/decoding
    - Ping/Pong keepalive
    - Close handshake
    - Broadcast to all connected clients
    - Thread-safe client management

Usage:
    from dashboard.websocket import WebSocketHandler
    
    # Inside HTTP request handler:
    if path == "/ws":
        ws = WebSocketHandler(request_handler)
        ws.handshake()
        ws.send_text('{"type": "connected"}')
        for msg in ws.receive_messages():
            print(f"Received: {msg}")
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import select
import socket
import struct
import threading
from typing import Any, Callable, Generator, List, Optional

logger = logging.getLogger(__name__)


class WebSocketError(Exception):
    """WebSocket protocol error."""
    pass


class WebSocketHandler:
    """
    Handle a single WebSocket connection.
    
    Implements RFC 6455 framing and handshake.
    """

    # Opcodes
    OP_CONT = 0x0
    OP_TEXT = 0x1
    OP_BINARY = 0x2
    OP_CLOSE = 0x8
    OP_PING = 0x9
    OP_PONG = 0xA

    def __init__(self, http_handler):
        """
        Args:
            http_handler: The BaseHTTPRequestHandler instance
        """
        self._request = http_handler
        self._socket: Optional[socket.socket] = None
        self._closed = False
        self._lock = threading.Lock()

    @property
    def is_connected(self) -> bool:
        return not self._closed and self._socket is not None

    def handshake(self) -> bool:
        """
        Perform WebSocket handshake.
        
        Returns:
            True if handshake successful
        """
        headers = self._request.headers
        
        # Check required headers
        key = headers.get("Sec-WebSocket-Key", "")
        version = headers.get("Sec-WebSocket-Version", "")
        
        if not key or version != "13":
            self._send_http_error(400, "Bad Request: Invalid WebSocket headers")
            return False
        
        # Compute accept key
        magic = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
        accept = base64.b64encode(
            hashlib.sha1((key + magic).encode()).digest()
        ).decode()
        
        # Send handshake response
        self._request.send_response(101, "Switching Protocols")
        self._request.send_header("Upgrade", "websocket")
        self._request.send_header("Connection", "Upgrade")
        self._request.send_header("Sec-WebSocket-Accept", accept)
        self._request.end_headers()
        
        # Get underlying socket
        self._socket = self._request.connection
        
        logger.debug("WebSocket handshake completed")
        return True

    def send_text(self, text: str) -> bool:
        """Send a text frame."""
        return self._send_frame(self.OP_TEXT, text.encode("utf-8"))

    def send_binary(self, data: bytes) -> bool:
        """Send a binary frame."""
        return self._send_frame(self.OP_BINARY, data)

    def send_ping(self) -> bool:
        """Send a ping frame."""
        return self._send_frame(self.OP_PING, b"")

    def send_pong(self, data: bytes = b"") -> bool:
        """Send a pong frame."""
        return self._send_frame(self.OP_PONG, data)

    def send_close(self, code: int = 1000, reason: str = "") -> bool:
        """Send a close frame."""
        payload = struct.pack("!H", code) + reason.encode("utf-8")
        result = self._send_frame(self.OP_CLOSE, payload)
        self._closed = True
        return result

    def _send_frame(self, opcode: int, payload: bytes) -> bool:
        """Encode and send a WebSocket frame."""
        if self._socket is None or self._closed:
            return False
        
        with self._lock:
            try:
                length = len(payload)
                
                # First byte: FIN=1, RSV=0, opcode
                frame = bytearray()
                frame.append(0x80 | opcode)
                
                # Mask bit = 0 (server-to-client), payload length
                if length < 126:
                    frame.append(length)
                elif length < 65536:
                    frame.append(126)
                    frame.extend(struct.pack("!H", length))
                else:
                    frame.append(127)
                    frame.extend(struct.pack("!Q", length))
                
                # Payload (not masked for server)
                frame.extend(payload)
                
                self._socket.sendall(bytes(frame))
                return True
                
            except Exception as e:
                logger.debug("WebSocket send failed: %s", e)
                self._closed = True
                return False

    def receive_messages(self, timeout: Optional[float] = None) -> Generator[str, None, None]:
        """
        Yield decoded text messages until connection closes.
        
        Handles ping/pong and close frames automatically.
        
        Yields:
            Decoded text strings
        """
        while not self._closed:
            try:
                message = self._read_frame(timeout)
                if message is None:
                    continue
                if isinstance(message, str):
                    yield message
                elif isinstance(message, bytes) and message == b"__close__":
                    break
            except WebSocketError as e:
                logger.debug("WebSocket error: %s", e)
                break
            except Exception as e:
                logger.debug("WebSocket receive exception: %s", e)
                break

    def _read_frame(self, timeout: Optional[float] = None) -> Optional[Any]:
        """Read and decode a single WebSocket frame."""
        if self._socket is None:
            raise WebSocketError("Socket not connected")
        
        # Set timeout for reading
        if timeout is not None:
            self._socket.settimeout(timeout)
        
        # Read first 2 bytes minimum
        header = self._recv_exactly(2)
        if header is None:
            raise WebSocketError("Connection closed")
        
        byte1, byte2 = header[0], header[1]
        
        fin = (byte1 >> 7) & 1
        rsv = (byte1 >> 4) & 0x7
        opcode = byte1 & 0xF
        masked = (byte2 >> 7) & 1
        payload_len = byte2 & 0x7F
        
        # Extended payload length
        if payload_len == 126:
            ext = self._recv_exactly(2)
            if ext is None:
                raise WebSocketError("Connection closed")
            payload_len = struct.unpack("!H", ext)[0]
        elif payload_len == 127:
            ext = self._recv_exactly(8)
            if ext is None:
                raise WebSocketError("Connection closed")
            payload_len = struct.unpack("!Q", ext)[0]
        
        # Mask key (client-to-server must be masked)
        mask_key = None
        if masked:
            mask_key = self._recv_exactly(4)
            if mask_key is None:
                raise WebSocketError("Connection closed")
        
        # Read payload
        if payload_len > 10 * 1024 * 1024:  # 10MB max
            raise WebSocketError("Payload too large")
        
        payload = self._recv_exactly(payload_len)
        if payload is None:
            raise WebSocketError("Connection closed")
        
        # Unmask if needed
        if mask_key:
            payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
        
        # Handle opcodes
        if opcode == self.OP_TEXT:
            return payload.decode("utf-8", errors="replace")
        
        elif opcode == self.OP_BINARY:
            return payload  # Return bytes for binary
        
        elif opcode == self.OP_CLOSE:
            self._closed = True
            if len(payload) >= 2:
                code = struct.unpack("!H", payload[:2])[0]
                reason = payload[2:].decode("utf-8", errors="replace")
                logger.debug("WebSocket close: %d %s", code, reason)
            # Send close acknowledgment
            self.send_close()
            return b"__close__"
        
        elif opcode == self.OP_PING:
            # Respond with pong
            self.send_pong(payload)
            return None
        
        elif opcode == self.OP_PONG:
            # Just acknowledge
            return None
        
        elif opcode == self.OP_CONT:
            # Continuation frames not fully implemented
            return None
        
        else:
            logger.warning("Unknown WebSocket opcode: %d", opcode)
            return None

    def _recv_exactly(self, n: int) -> Optional[bytes]:
        """Receive exactly n bytes."""
        data = bytearray()
        while len(data) < n:
            try:
                chunk = self._socket.recv(n - len(data))
                if not chunk:
                    return None
                data.extend(chunk)
            except socket.timeout:
                return None
            except Exception as e:
                logger.debug("Socket recv error: %s", e)
                return None
        return bytes(data)

    def _send_http_error(self, code: int, message: str) -> None:
        """Send HTTP error response."""
        self._request.send_response(code)
        self._request.send_header("Content-Type", "text/plain")
        self._request.end_headers()
        self._request.wfile.write(message.encode())

    def close(self) -> None:
        """Close the connection."""
        if not self._closed:
            self.send_close()
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
        self._closed = True


class WebSocketServer:
    """
    Manage multiple WebSocket connections with broadcast capability.
    """

    def __init__(self):
        self._clients: List[WebSocketHandler] = []
        self._lock = threading.Lock()
        self._running = False
        self._broadcast_thread: Optional[threading.Thread] = None

    def add_client(self, handler: WebSocketHandler) -> None:
        """Add a connected client."""
        with self._lock:
            self._clients.append(handler)
        logger.debug("WebSocket client connected. Total: %d", len(self._clients))

    def remove_client(self, handler: WebSocketHandler) -> None:
        """Remove a disconnected client."""
        with self._lock:
            if handler in self._clients:
                self._clients.remove(handler)
        logger.debug("WebSocket client disconnected. Total: %d", len(self._clients))

    def broadcast(self, message: dict[str, Any]) -> int:
        """
        Broadcast a message to all connected clients.
        
        Returns:
            Number of clients that received the message
        """
        data = json.dumps(message)
        sent = 0
        dead = []
        
        with self._lock:
            clients = self._clients.copy()
        
        for client in clients:
            if client.send_text(data):
                sent += 1
            else:
                dead.append(client)
        
        # Remove dead clients
        if dead:
            with self._lock:
                for client in dead:
                    if client in self._clients:
                        self._clients.remove(client)
        
        return sent

    def broadcast_event(self, event_type: str, payload: dict[str, Any]) -> int:
        """Broadcast a typed event."""
        return self.broadcast({
            "type": event_type,
            "timestamp": __import__("time").time(),
            **payload,
        })

    @property
    def client_count(self) -> int:
        with self._lock:
            return len(self._clients)

    def start(self) -> None:
        """Start background tasks."""
        self._running = True
        self._broadcast_thread = threading.Thread(target=self._ping_loop, daemon=True)
        self._broadcast_thread.start()

    def stop(self) -> None:
        """Stop and close all connections."""
        self._running = False
        
        with self._lock:
            clients = self._clients.copy()
            self._clients.clear()
        
        for client in clients:
            client.close()

    def _ping_loop(self) -> None:
        """Send periodic pings to keep connections alive."""
        import time
        while self._running:
            time.sleep(30)
            if not self._running:
                break
            
            with self._lock:
                clients = self._clients.copy()
            
            dead = []
            for client in clients:
                if not client.send_ping():
                    dead.append(client)
            
            if dead:
                with self._lock:
                    for client in dead:
                        if client in self._clients:
                            self._clients.remove(client)


__all__ = [
    "WebSocketError",
    "WebSocketHandler",
    "WebSocketServer",
]
