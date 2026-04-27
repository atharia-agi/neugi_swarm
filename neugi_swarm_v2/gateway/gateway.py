#!/usr/bin/env python3
"""
NEUGI SWARM V2 - Gateway Server
=================================

The central control plane for the entire NEUGI system.
Handles WebSocket RPC, HTTP REST API, device pairing,
connection management, and server-push events.

Version: 2.0.0
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class DeviceTrustLevel(Enum):
    TRUSTED = "trusted"
    PENDING = "pending"
    BLOCKED = "blocked"


class EventType(Enum):
    AGENT = "agent"
    CHAT = "chat"
    PRESENCE = "presence"
    HEALTH = "health"
    HEARTBEAT = "heartbeat"
    CRON = "cron"
    ERROR = "error"
    STEERING = "steering"


@dataclass
class Device:
    """Represents a connected device."""
    id: str
    name: str
    type: str  # "web", "cli", "mobile", "api"
    trust_level: DeviceTrustLevel = DeviceTrustLevel.PENDING
    token: str = ""
    capabilities: Dict[str, Any] = field(default_factory=dict)
    connected_at: float = 0.0
    last_seen: float = 0.0
    session_ids: List[str] = field(default_factory=list)
    ip_address: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "trust_level": self.trust_level.value,
            "capabilities": self.capabilities,
            "connected_at": self.connected_at,
            "last_seen": self.last_seen,
            "session_ids": self.session_ids,
        }


@dataclass
class Event:
    """Server-push event."""
    type: EventType
    data: Dict[str, Any]
    idempotency_key: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps({
            "type": self.type.value,
            "data": self.data,
            "idempotency_key": self.idempotency_key or str(uuid.uuid4()),
            "timestamp": self.timestamp,
        })


@dataclass
class RPCRequest:
    """JSON-RPC 2.0 request."""
    id: Any
    method: str
    params: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict) -> "RPCRequest":
        return cls(
            id=data.get("id"),
            method=data.get("method", ""),
            params=data.get("params", {}),
        )


@dataclass
class RPCResponse:
    """JSON-RPC 2.0 response."""
    id: Any
    result: Any = None
    error: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        resp: Dict[str, Any] = {"jsonrpc": "2.0", "id": self.id}
        if self.error:
            resp["error"] = self.error
        else:
            resp["result"] = self.result
        return resp


class Connection:
    """Represents a single WebSocket/HTTP connection."""

    def __init__(self, conn_id: str, device: Device, send_fn: Callable):
        self.conn_id = conn_id
        self.device = device
        self._send_fn = send_fn
        self.created_at = time.time()
        self.last_activity = time.time()
        self._pending_requests: Dict[str, asyncio.Future] = {}

    async def send(self, data: str):
        """Send data to the client."""
        self.last_activity = time.time()
        try:
            await self._send_fn(data)
        except Exception as e:
            logger.error(f"Send error on {self.conn_id}: {e}")

    async def send_event(self, event: Event):
        """Send a server-push event."""
        await self.send(event.to_json())

    async def send_response(self, response: RPCResponse):
        """Send an RPC response."""
        await self.send(json.dumps(response.to_dict()))

    def is_alive(self, timeout: float = 120.0) -> bool:
        return (time.time() - self.last_activity) < timeout


class GatewayServer:
    """
    Central Gateway daemon for NEUGI Swarm V2.

    Manages:
    - WebSocket RPC connections
    - HTTP REST API
    - Device pairing and trust
    - Event broadcasting
    - Health monitoring
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        ws_port: int = 19887,
        http_port: int = 19888,
        data_dir: str = "",
    ):
        self.host = host
        self.ws_port = ws_port
        self.http_port = http_port
        self.data_dir = data_dir or os.path.expanduser("~/neugi/data")
        os.makedirs(self.data_dir, exist_ok=True)

        # State
        self._connections: Dict[str, Connection] = {}
        self._devices: Dict[str, Device] = {}
        self._device_tokens: Dict[str, str] = {}  # token -> device_id
        self._handlers: Dict[str, Callable] = {}
        self._running = False
        self._start_time = 0.0
        self._request_count = 0
        self._error_count = 0

        # Pairing secrets
        self._pairing_secrets: Dict[str, str] = {}

        # Load persisted state
        self._load_devices()

        # Register default handlers
        self._register_default_handlers()

    def _register_default_handlers(self):
        """Register default RPC handlers."""
        self.register_handler("connect", self._handle_connect)
        self.register_handler("ping", self._handle_ping)
        self.register_handler("pair", self._handle_pair)
        self.register_handler("pair_confirm", self._handle_pair_confirm)
        self.register_handler("get_status", self._handle_get_status)
        self.register_handler("list_devices", self._handle_list_devices)
        self.register_handler("revoke_device", self._handle_revoke_device)
        self.register_handler("send_chat", self._handle_send_chat)
        self.register_handler("subscribe", self._handle_subscribe)
        self.register_handler("unsubscribe", self._handle_unsubscribe)

    def register_handler(self, method: str, handler: Callable):
        """Register an RPC method handler."""
        self._handlers[method] = handler

    async def handle_message(self, conn: Connection, raw: str) -> Optional[RPCResponse]:
        """Handle an incoming RPC message."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return RPCResponse(id=None, error={
                "code": -32700,
                "message": "Parse error",
            })

        if data.get("jsonrpc") != "2.0":
            return RPCResponse(id=data.get("id"), error={
                "code": -32600,
                "message": "Invalid Request",
            })

        request = RPCRequest.from_dict(data)
        handler = self._handlers.get(request.method)

        if not handler:
            return RPCResponse(id=request.id, error={
                "code": -32601,
                "message": f"Method not found: {request.method}",
            })

        try:
            result = await handler(conn, request.params)
            self._request_count += 1
            return RPCResponse(id=request.id, result=result)
        except Exception as e:
            self._error_count += 1
            logger.error(f"Handler error [{request.method}]: {e}")
            return RPCResponse(id=request.id, error={
                "code": -32603,
                "message": str(e),
            })

    # ========== RPC Handlers ==========

    async def _handle_connect(self, conn: Connection, params: Dict) -> Dict:
        """Handle device connection with identity."""
        device_id = params.get("device_id", "")
        device_name = params.get("device_name", "Unknown")
        device_type = params.get("device_type", "web")
        token = params.get("token", "")
        capabilities = params.get("capabilities", {})
        is_local = params.get("is_local", True)

        # Check if device exists
        device = self._devices.get(device_id)

        if device:
            # Existing device
            if device.trust_level == DeviceTrustLevel.BLOCKED:
                raise PermissionError("Device is blocked")

            if token and device.token:
                if not hmac.compare_digest(token, device.token):
                    raise PermissionError("Invalid token")
            elif not token and device.trust_level == DeviceTrustLevel.PENDING:
                if is_local:
                    device.trust_level = DeviceTrustLevel.TRUSTED
                    device.token = secrets.token_hex(32)
                    self._device_tokens[device.token] = device_id
                    self._save_devices()
                else:
                    # Remote device needs pairing
                    challenge = secrets.token_hex(16)
                    self._pairing_secrets[device_id] = challenge
                    return {
                        "status": "pairing_required",
                        "challenge": challenge,
                        "message": "Approve this device on the gateway",
                    }

            device.last_seen = time.time()
            device.capabilities.update(capabilities)
        else:
            # New device
            if is_local:
                # Auto-approve local devices
                device = Device(
                    id=device_id or str(uuid.uuid4()),
                    name=device_name,
                    type=device_type,
                    trust_level=DeviceTrustLevel.TRUSTED,
                    token=secrets.token_hex(32),
                    capabilities=capabilities,
                    connected_at=time.time(),
                    last_seen=time.time(),
                )
                self._device_tokens[device.token] = device.id
            else:
                # Remote device needs pairing
                device = Device(
                    id=device_id or str(uuid.uuid4()),
                    name=device_name,
                    type=device_type,
                    trust_level=DeviceTrustLevel.PENDING,
                    capabilities=capabilities,
                    connected_at=time.time(),
                    last_seen=time.time(),
                )
                challenge = secrets.token_hex(16)
                self._pairing_secrets[device.id] = challenge
                self._devices[device.id] = device
                self._save_devices()
                return {
                    "status": "pairing_required",
                    "device_id": device.id,
                    "challenge": challenge,
                    "message": "Approve this device on the gateway",
                }

            self._devices[device.id] = device
            self._save_devices()

        conn.device = device
        device.session_ids.append(conn.conn_id)
        self._connections[conn.conn_id] = conn

        return {
            "status": "connected",
            "device": device.to_dict(),
            "token": device.token,
        }

    async def _handle_ping(self, conn: Connection, params: Dict) -> Dict:
        """Handle ping request."""
        conn.last_activity = time.time()
        return {"pong": True, "timestamp": time.time()}

    async def _handle_pair(self, conn: Connection, params: Dict) -> Dict:
        """Initiate pairing for a remote device."""
        device_id = params.get("device_id", "")
        device_name = params.get("device_name", "Remote Device")

        device = Device(
            id=device_id or str(uuid.uuid4()),
            name=device_name,
            type="remote",
            trust_level=DeviceTrustLevel.PENDING,
            connected_at=time.time(),
            last_seen=time.time(),
        )
        self._devices[device.id] = device
        self._save_devices()

        challenge = secrets.token_hex(16)
        self._pairing_secrets[device.id] = challenge

        # Broadcast pairing request to all trusted devices
        await self.broadcast(Event(
            type=EventType.PRESENCE,
            data={
                "event": "pairing_request",
                "device_id": device.id,
                "device_name": device.name,
                "challenge": challenge,
            },
        ))

        return {
            "device_id": device.id,
            "challenge": challenge,
            "status": "pending_approval",
        }

    async def _handle_pair_confirm(self, conn: Connection, params: Dict) -> Dict:
        """Confirm/approve a pending device pairing."""
        device_id = params.get("device_id", "")
        approve = params.get("approve", True)

        device = self._devices.get(device_id)
        if not device:
            raise ValueError(f"Device not found: {device_id}")

        if approve:
            device.trust_level = DeviceTrustLevel.TRUSTED
            device.token = secrets.token_hex(32)
            self._device_tokens[device.token] = device.id
        else:
            device.trust_level = DeviceTrustLevel.BLOCKED

        self._save_devices()

        # Clean up pairing secret
        self._pairing_secrets.pop(device_id, None)

        return {
            "device_id": device_id,
            "status": "approved" if approve else "rejected",
            "token": device.token if approve else None,
        }

    async def _handle_get_status(self, conn: Connection, params: Dict) -> Dict:
        """Get gateway status."""
        active_conns = sum(1 for c in self._connections.values() if c.is_alive())
        return {
            "status": "running",
            "uptime": time.time() - self._start_time if self._start_time else 0,
            "connections": active_conns,
            "total_devices": len(self._devices),
            "trusted_devices": sum(
                1 for d in self._devices.values()
                if d.trust_level == DeviceTrustLevel.TRUSTED
            ),
            "requests_handled": self._request_count,
            "errors": self._error_count,
            "timestamp": time.time(),
        }

    async def _handle_list_devices(self, conn: Connection, params: Dict) -> List[Dict]:
        """List all registered devices."""
        return [d.to_dict() for d in self._devices.values()]

    async def _handle_revoke_device(self, conn: Connection, params: Dict) -> Dict:
        """Revoke a device's access."""
        device_id = params.get("device_id", "")
        device = self._devices.get(device_id)
        if not device:
            raise ValueError(f"Device not found: {device_id}")

        # Remove token
        if device.token in self._device_tokens:
            del self._device_tokens[device.token]

        device.trust_level = DeviceTrustLevel.BLOCKED
        device.token = ""
        self._save_devices()

        # Disconnect all connections from this device
        to_remove = [
            cid for cid, c in self._connections.items()
            if c.device.id == device_id
        ]
        for cid in to_remove:
            del self._connections[cid]

        return {"status": "revoked", "device_id": device_id}

    async def _handle_send_chat(self, conn: Connection, params: Dict) -> Dict:
        """Send a chat message through the gateway."""
        message = params.get("message", "")
        session_id = params.get("session_id", "default")
        agent_id = params.get("agent_id", "")

        if not message:
            raise ValueError("Message is required")

        # This would route to the assistant
        return {
            "status": "queued",
            "session_id": session_id,
            "message_id": str(uuid.uuid4()),
        }

    async def _handle_subscribe(self, conn: Connection, params: Dict) -> Dict:
        """Subscribe to event types."""
        event_types = params.get("types", [])
        conn.device.capabilities["subscriptions"] = event_types
        return {"status": "subscribed", "types": event_types}

    async def _handle_unsubscribe(self, conn: Connection, params: Dict) -> Dict:
        """Unsubscribe from event types."""
        event_types = params.get("types", [])
        current = conn.device.capabilities.get("subscriptions", [])
        conn.device.capabilities["subscriptions"] = [
            t for t in current if t not in event_types
        ]
        return {"status": "unsubscribed", "types": event_types}

    # ========== Event Broadcasting ==========

    async def broadcast(self, event: Event, exclude_conn: Optional[str] = None):
        """Broadcast an event to all connected devices."""
        targets = [
            c for c in self._connections.values()
            if c.is_alive() and c.conn_id != exclude_conn
        ]

        for conn in targets:
            # Check if device is subscribed to this event type
            subs = conn.device.capabilities.get("subscriptions", [])
            if subs and event.type.value not in subs:
                continue

            asyncio.create_task(conn.send_event(event))

    async def send_to_device(self, device_id: str, event: Event):
        """Send an event to a specific device."""
        for conn in self._connections.values():
            if conn.device.id == device_id and conn.is_alive():
                await conn.send_event(event)
                return True
        return False

    # ========== Connection Management ==========

    async def on_connect(self, send_fn: Callable, ip: str = "") -> Connection:
        """Handle a new connection."""
        conn_id = str(uuid.uuid4())
        device = Device(
            id="",
            name="Unidentified",
            type="unknown",
            ip_address=ip,
        )
        conn = Connection(conn_id, device, send_fn)
        return conn

    async def on_disconnect(self, conn_id: str):
        """Handle a connection disconnect."""
        conn = self._connections.pop(conn_id, None)
        if conn:
            # Remove conn_id from device session list
            if conn.device.id in self._devices:
                device = self._devices[conn.device.id]
                if conn_id in device.session_ids:
                    device.session_ids.remove(conn_id)

            await self.broadcast(Event(
                type=EventType.PRESENCE,
                data={
                    "event": "device_disconnected",
                    "device_id": conn.device.id,
                    "device_name": conn.device.name,
                },
            ))

    def cleanup_stale_connections(self, timeout: float = 120.0):
        """Remove connections that haven't sent a heartbeat."""
        stale = [
            cid for cid, c in self._connections.items()
            if not c.is_alive(timeout)
        ]
        for cid in stale:
            del self._connections[cid]
        if stale:
            logger.info(f"Cleaned up {len(stale)} stale connections")

    # ========== Health ==========

    def get_health(self) -> Dict[str, Any]:
        """Get gateway health status."""
        active = sum(1 for c in self._connections.values() if c.is_alive())
        return {
            "status": "healthy" if self._running else "stopped",
            "uptime": time.time() - self._start_time if self._start_time else 0,
            "active_connections": active,
            "total_devices": len(self._devices),
            "requests": self._request_count,
            "errors": self._error_count,
            "timestamp": time.time(),
        }

    # ========== Persistence ==========

    def _save_devices(self):
        """Save device registry to disk."""
        path = os.path.join(self.data_dir, "devices.json")
        data = {
            "devices": {did: d.to_dict() for did, d in self._devices.items()},
            "tokens": {t: did for t, did in self._device_tokens.items()},
        }
        try:
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save devices: {e}")

    def _load_devices(self):
        """Load device registry from disk."""
        path = os.path.join(self.data_dir, "devices.json")
        if not os.path.exists(path):
            return

        try:
            with open(path, "r") as f:
                data = json.load(f)

            for did, ddata in data.get("devices", {}).items():
                self._devices[did] = Device(
                    id=ddata["id"],
                    name=ddata["name"],
                    type=ddata["type"],
                    trust_level=DeviceTrustLevel(ddata.get("trust_level", "pending")),
                    token=ddata.get("token", ""),
                    capabilities=ddata.get("capabilities", {}),
                    connected_at=ddata.get("connected_at", 0),
                    last_seen=ddata.get("last_seen", 0),
                    session_ids=ddata.get("session_ids", []),
                )

            self._device_tokens = data.get("tokens", {})
            logger.info(f"Loaded {len(self._devices)} devices")
        except Exception as e:
            logger.error(f"Failed to load devices: {e}")

    # ========== Server Lifecycle ==========

    def start(self):
        """Start the gateway server."""
        self._running = True
        self._start_time = time.time()

        # Start HTTP server in background thread
        http_thread = Thread(target=self._run_http_server, daemon=True)
        http_thread.start()

        logger.info(f"Gateway started on {self.host}:{self.http_port}")

    def stop(self):
        """Stop the gateway server."""
        self._running = False
        logger.info("Gateway stopped")

    def _run_http_server(self):
        """Run the HTTP REST API server."""
        gateway = self

        class GatewayHTTPHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/health":
                    self._send_json(gateway.get_health())
                elif self.path == "/api/devices":
                    self._send_json([d.to_dict() for d in gateway._devices.values()])
                elif self.path == "/api/status":
                    self._send_json({
                        "running": gateway._running,
                        "connections": len(gateway._connections),
                        "devices": len(gateway._devices),
                        "requests": gateway._request_count,
                    })
                else:
                    self.send_error(404)

            def do_POST(self):
                if self.path == "/api/pair":
                    length = int(self.headers.get("Content-Length", 0))
                    body = json.loads(self.rfile.read(length))
                    device_id = body.get("device_id", str(uuid.uuid4()))
                    device_name = body.get("device_name", "HTTP Device")

                    device = Device(
                        id=device_id,
                        name=device_name,
                        type="http",
                        trust_level=DeviceTrustLevel.PENDING,
                        connected_at=time.time(),
                        last_seen=time.time(),
                    )
                    gateway._devices[device_id] = device
                    challenge = secrets.token_hex(16)
                    gateway._pairing_secrets[device_id] = challenge
                    gateway._save_devices()

                    self._send_json({
                        "device_id": device_id,
                        "challenge": challenge,
                        "status": "pending_approval",
                    })
                elif self.path == "/api/pair/approve":
                    length = int(self.headers.get("Content-Length", 0))
                    body = json.loads(self.rfile.read(length))
                    device_id = body.get("device_id", "")
                    device = gateway._devices.get(device_id)
                    if device:
                        device.trust_level = DeviceTrustLevel.TRUSTED
                        device.token = secrets.token_hex(32)
                        gateway._device_tokens[device.token] = device_id
                        gateway._save_devices()
                        self._send_json({
                            "status": "approved",
                            "token": device.token,
                        })
                    else:
                        self.send_error(404, "Device not found")
                else:
                    self.send_error(404)

            def _send_json(self, data: Dict):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())

            def log_message(self, format, *args):
                pass  # Suppress default logging

        try:
            server = HTTPServer((self.host, self.http_port), GatewayHTTPHandler)
            server.serve_forever()
        except Exception as e:
            logger.error(f"HTTP server error: {e}")
