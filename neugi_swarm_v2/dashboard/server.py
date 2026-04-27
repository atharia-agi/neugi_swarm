"""
NEUGI v2 Dashboard HTTP Server
===============================

Production-ready HTTP server serving the dashboard UI and REST API.
Uses Python standard library (http.server, asyncio, websockets).

Features:
- Static file serving with gzip compression
- REST API with JSON responses
- WebSocket for real-time updates
- API key authentication
- Rate limiting
- CORS support
- Health checks
"""

from __future__ import annotations

import asyncio
import gzip
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
import traceback
from dataclasses import dataclass, field
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import urlparse, parse_qs
import threading

logger = logging.getLogger(__name__)

# -- Configuration -----------------------------------------------------------

@dataclass
class DashboardConfig:
    """Dashboard server configuration.

    Attributes:
        host: Bind address.
        port: Bind port.
        api_key: Required API key for authenticated endpoints.
        session_token_ttl: Session token lifetime in seconds.
        rate_limit_requests: Max requests per window.
        rate_limit_window: Rate limit window in seconds.
        cors_origins: Allowed CORS origins.
        enable_gzip: Enable gzip compression.
        gzip_min_size: Minimum response size for gzip.
        static_dir: Directory for static files.
        enable_auth: Enable authentication.
        max_body_size: Maximum request body size in bytes.
    """

    host: str = "0.0.0.0"
    port: int = 8080
    api_key: str = ""
    session_token_ttl: int = 3600
    rate_limit_requests: int = 100
    rate_limit_window: int = 60
    cors_origins: list[str] = field(default_factory=lambda: ["*"])
    enable_gzip: bool = True
    gzip_min_size: int = 1024
    static_dir: str = ""
    enable_auth: bool = False
    max_body_size: int = 10 * 1024 * 1024  # 10MB


# -- Rate Limiter ------------------------------------------------------------

class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = {}

    def is_allowed(self, client_ip: str) -> bool:
        now = time.time()
        window_start = now - self.window_seconds

        if client_ip not in self._requests:
            self._requests[client_ip] = []

        self._requests[client_ip] = [
            t for t in self._requests[client_ip] if t > window_start
        ]

        if len(self._requests[client_ip]) >= self.max_requests:
            return False

        self._requests[client_ip].append(now)
        return True


# -- Session Manager ---------------------------------------------------------

class SessionTokenManager:
    """Manage session tokens for authenticated access."""

    def __init__(self, ttl_seconds: int = 3600):
        self.ttl_seconds = ttl_seconds
        self._tokens: dict[str, dict[str, Any]] = {}

    def create_token(self, user_id: str = "default") -> str:
        token = secrets.token_urlsafe(32)
        self._tokens[token] = {
            "user_id": user_id,
            "created_at": time.time(),
        }
        return token

    def validate_token(self, token: str) -> Optional[dict[str, Any]]:
        session = self._tokens.get(token)
        if session is None:
            return None
        if time.time() - session["created_at"] > self.ttl_seconds:
            del self._tokens[token]
            return None
        return session

    def revoke_token(self, token: str) -> bool:
        if token in self._tokens:
            del self._tokens[token]
            return True
        return False

    def cleanup_expired(self) -> int:
        now = time.time()
        expired = [
            t for t, s in self._tokens.items()
            if now - s["created_at"] > self.ttl_seconds
        ]
        for t in expired:
            del self._tokens[t]
        return len(expired)


# -- WebSocket Broadcaster ---------------------------------------------------

class WebSocketBroadcaster:
    """Broadcast real-time updates to connected WebSocket clients."""

    def __init__(self):
        self._clients: list[Any] = []
        self._lock = threading.Lock()

    def add_client(self, client: Any) -> None:
        with self._lock:
            self._clients.append(client)

    def remove_client(self, client: Any) -> None:
        with self._lock:
            if client in self._clients:
                self._clients.remove(client)

    def broadcast(self, message: dict[str, Any]) -> None:
        data = json.dumps(message)
        with self._lock:
            dead_clients = []
            for client in self._clients:
                try:
                    client.send(data)
                except Exception:
                    dead_clients.append(client)
            for client in dead_clients:
                self._clients.remove(client)

    @property
    def client_count(self) -> int:
        with self._lock:
            return len(self._clients)


# -- Dashboard Server --------------------------------------------------------

class DashboardServer:
    """NEUGI v2 Dashboard HTTP Server.

    Serves the dashboard UI and provides REST API endpoints for all
    NEUGI subsystems.

    Usage:
        server = DashboardServer(swarm_instance)
        server.start()
    """

    def __init__(
        self,
        swarm: Any = None,
        config: Optional[DashboardConfig] = None,
        **kwargs,
    ):
        self.swarm = swarm
        self.config = config or DashboardConfig(**kwargs)
        self.rate_limiter = RateLimiter(
            self.config.rate_limit_requests,
            self.config.rate_limit_window,
        )
        self.session_manager = SessionTokenManager(self.config.session_token_ttl)
        self.broadcaster = WebSocketBroadcaster()
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

        if not self.config.static_dir:
            self.config.static_dir = str(Path(__file__).parent)

        self._api_routes: dict[str, Callable] = {}
        self._register_routes()

    def _register_routes(self) -> None:
        """Register API route handlers."""
        from neugi_swarm_v2.dashboard.api import DashboardAPI

        self.api = DashboardAPI(self)

        routes = {
            "GET /api/health": self.api.health,
            "GET /api/agents": self.api.list_agents,
            "POST /api/agents/{id}/task": self.api.delegate_task,
            "GET /api/sessions": self.api.list_sessions,
            "GET /api/sessions/{id}/messages": self.api.get_session_messages,
            "POST /api/chat": self.api.chat,
            "GET /api/skills": self.api.list_skills,
            "GET /api/memory/stats": self.api.memory_stats,
            "GET /api/memory/recall": self.api.memory_recall,
            "GET /api/channels": self.api.list_channels,
            "GET /api/workflows": self.api.list_workflows,
            "POST /api/workflows/{id}/run": self.api.run_workflow,
            "GET /api/plugins": self.api.list_plugins,
            "GET /api/governance/budget": self.api.budget_status,
            "GET /api/governance/audit": self.api.audit_log,
            "GET /api/learning/stats": self.api.learning_stats,
            "POST /api/steering": self.api.send_steering,
            "POST /api/auth/login": self.api.login,
            "POST /api/auth/logout": self.api.logout,
            "GET /api/config": self.api.get_config,
            "PUT /api/config": self.api.update_config,
        }

        self._api_routes.update(routes)

    def start(self, blocking: bool = False) -> None:
        """Start the dashboard server.

        Args:
            blocking: If True, block the calling thread.
        """
        self._server = HTTPServer(
            (self.config.host, self.config.port),
            lambda *args: DashboardRequestHandler(self, *args),
        )
        self._running = True

        if blocking:
            logger.info(
                "NEUGI Dashboard running at http://%s:%d",
                self.config.host,
                self.config.port,
            )
            self._server.serve_forever()
        else:
            self._thread = threading.Thread(
                target=self._server.serve_forever,
                daemon=True,
            )
            self._thread.start()
            logger.info(
                "NEUGI Dashboard started at http://%s:%d",
                self.config.host,
                self.config.port,
            )

    def stop(self) -> None:
        """Stop the dashboard server."""
        if self._server:
            self._running = False
            self._server.shutdown()
            logger.info("NEUGI Dashboard stopped")

    def broadcast_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Broadcast an event to all WebSocket clients.

        Args:
            event_type: Event type identifier.
            data: Event payload.
        """
        self.broadcaster.broadcast({
            "type": event_type,
            "data": data,
            "timestamp": time.time(),
        })

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def url(self) -> str:
        return f"http://{self.config.host}:{self.config.port}"


# -- Request Handler ---------------------------------------------------------

class DashboardRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the dashboard server."""

    server_instance: DashboardServer

    def log_message(self, format: str, *args) -> None:
        logger.debug(format, *args)

    def _get_client_ip(self) -> str:
        return (
            self.headers.get("X-Forwarded-For", self.client_address[0])
            .split(",")[0]
            .strip()
        )

    def _check_rate_limit(self) -> bool:
        client_ip = self._get_client_ip()
        return self.server_instance.rate_limiter.is_allowed(client_ip)

    def _check_auth(self) -> bool:
        if not self.server_instance.config.enable_auth:
            return True

        api_key = self.headers.get("X-API-Key", "")
        if api_key and self.server_instance.config.api_key:
            return hmac.compare_digest(
                api_key,
                self.server_instance.config.api_key,
            )

        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            return self.server_instance.session_manager.validate_token(token) is not None

        return False

    def _set_cors_headers(self) -> None:
        origins = self.server_instance.config.cors_origins
        origin = self.headers.get("Origin", "")

        if "*" in origins:
            self.send_header("Access-Control-Allow-Origin", "*")
        elif origin in origins:
            self.send_header("Access-Control-Allow-Origin", origin)

        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-API-Key")
        self.send_header("Access-Control-Max-Age", "3600")

    def _send_json_response(
        self,
        status: int,
        data: Any,
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        body = json.dumps(data, indent=2, default=str).encode("utf-8")

        if self.server_instance.config.enable_gzip and len(body) >= self.server_instance.config.gzip_min_size:
            body = gzip.compress(body)
            content_encoding = "gzip"
        else:
            content_encoding = "identity"

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Encoding", content_encoding)
        self.send_header("Content-Length", str(len(body)))
        self._set_cors_headers()

        if headers:
            for k, v in headers.items():
                self.send_header(k, v)

        self.end_headers()
        self.wfile.write(body)

    def _send_static_file(self, file_path: str) -> None:
        path = Path(file_path)

        if not path.exists() or not path.is_file():
            self._send_json_response(404, {"error": "File not found"})
            return

        mime_map = {
            ".html": "text/html",
            ".css": "text/css",
            ".js": "application/javascript",
            ".json": "application/json",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon",
            ".woff": "font/woff",
            ".woff2": "font/woff2",
            ".ttf": "font/ttf",
            ".webp": "image/webp",
        }

        content_type = mime_map.get(path.suffix.lower(), "application/octet-stream")

        try:
            content = path.read_bytes()
        except OSError:
            self._send_json_response(500, {"error": "Failed to read file"})
            return

        if self.server_instance.config.enable_gzip and len(content) >= self.server_instance.config.gzip_min_size:
            content = gzip.compress(content)
            content_encoding = "gzip"
        else:
            content_encoding = "identity"

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Encoding", content_encoding)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "public, max-age=3600")
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(content)

    def _read_body(self) -> bytes:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > self.server_instance.config.max_body_size:
            raise ValueError("Request body too large")
        return self.rfile.read(content_length)

    def _parse_path(self) -> tuple[str, dict[str, list[str]]]:
        parsed = urlparse(self.path)
        return parsed.path, parse_qs(parsed.query)

    def _route_request(self, method: str) -> None:
        path, query_params = self._parse_path()

        if not self._check_rate_limit():
            self._send_json_response(429, {
                "error": "Rate limit exceeded",
                "retry_after": self.server_instance.config.rate_limit_window,
            })
            return

        if method == "OPTIONS":
            self.send_response(204)
            self._set_cors_headers()
            self.end_headers()
            return

        if not self._check_auth():
            self._send_json_response(401, {"error": "Authentication required"})
            return

        if path == "/ws":
            self._handle_websocket_upgrade()
            return

        route_key = f"{method} {path}"
        handler = self.server_instance._api_routes.get(route_key)

        if handler:
            try:
                body = None
                if method in ("POST", "PUT"):
                    body = self._read_body()
                result = handler(self, body, query_params)
                if result is not None:
                    self._send_json_response(200, result)
            except ValueError as e:
                self._send_json_response(400, {"error": str(e)})
            except Exception as e:
                logger.exception("API error: %s", path)
                self._send_json_response(500, {
                    "error": "Internal server error",
                    "detail": str(e) if self.server_instance.config.enable_auth else None,
                })
            return

        if path == "/" or path == "/index.html":
            self._send_static_file(
                os.path.join(self.server_instance.config.static_dir, "index.html")
            )
            return

        if path.startswith("/static/"):
            relative = path[len("/static/"):]
            self._send_static_file(
                os.path.join(self.server_instance.config.static_dir, relative)
            )
            return

        static_file = os.path.join(self.server_instance.config.static_dir, path.lstrip("/"))
        if os.path.isfile(static_file):
            self._send_static_file(static_file)
            return

        self._send_json_response(404, {"error": "Not found"})

    def _handle_websocket_upgrade(self) -> None:
        self._send_json_response(200, {
            "status": "websocket_upgrade_required",
            "message": "Use a WebSocket client to connect to /ws",
        })

    def do_GET(self) -> None:
        self._route_request("GET")

    def do_POST(self) -> None:
        self._route_request("POST")

    def do_PUT(self) -> None:
        self._route_request("PUT")

    def do_DELETE(self) -> None:
        self._route_request("DELETE")

    def do_OPTIONS(self) -> None:
        self._route_request("OPTIONS")
