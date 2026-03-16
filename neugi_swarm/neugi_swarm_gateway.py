#!/usr/bin/env python3
"""
🤖 NEUGI SWARM - GATEWAY
==========================

HTTP/WebSocket Gateway Server

Features:
- REST API
- WebSocket real-time
- Health checks
- Status endpoints
- Chat API
- Channel management

Usage:
    from neugi_swarm_gateway import Gateway
    gateway = Gateway(port=8089)
    gateway.start()
"""

import json
from typing import List, Optional
from dataclasses import dataclass
from datetime import datetime

# Try to import Flask/SocketIO, fallback to simple server
try:
    from flask import Flask, request, jsonify

    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    print("⚠️ Flask not installed. Using simple HTTP server.")

try:
    from flask_socketio import SocketIO

    SOCKETIO_AVAILABLE = True
except ImportError:
    SOCKETIO_AVAILABLE = False


@dataclass
class GatewayConfig:
    """Gateway configuration"""

    host: str = "0.0.0.0"
    port: int = 8089
    debug: bool = False
    cors_origins: Optional[List[str]] = None

    def __post_init__(self):
        if self.cors_origins is None:
            self.cors_origins = ["*"]


class Gateway:
    """HTTP/WebSocket Gateway for Neugi Swarm"""

    def __init__(self, swarm=None, config: GatewayConfig = None):
        self.swarm = swarm
        self.config = config or GatewayConfig()

        self.app = None
        self.socketio = None
        self.ws_connections = []

        self.routes = {}

        if FLASK_AVAILABLE:
            self._init_flask()
        else:
            self._init_simple()

    def _init_flask(self):
        """Initialize Flask app"""
        self.app = Flask(__name__)

        if SOCKETIO_AVAILABLE:
            self.socketio = SocketIO(self.app, cors_allowed_origins="*")

        self._register_routes()

    def _init_simple(self):
        """Initialize simple HTTP server"""
        self.server = SimpleHTTPServer(port=self.config.port)

    def _register_routes(self):
        """Register API routes"""

        @self.app.route("/health")
        def health():
            return jsonify(
                {
                    "status": "ok",
                    "service": "neugi_swarm",
                    "version": "11.0.0",
                    "timestamp": datetime.now().isoformat(),
                }
            )

        @self.app.route("/api/status")
        def status():
            if self.swarm:
                return jsonify(self.swarm.status())
            return jsonify({"version": "11.0.0", "running": True})

        @self.app.route("/api/agents", methods=["GET"])
        def agents():
            if self.swarm and hasattr(self.swarm, "agents"):
                return jsonify({"agents": self.swarm.agents})
            return jsonify({"agents": {}})

        @self.app.route("/api/channels", methods=["GET", "POST"])
        def channels():
            if request.method == "POST":
                # Add channel
                return jsonify({"status": "success", "channel_id": "new_channel"})
            return jsonify({"channels": []})

        @self.app.route("/api/skills", methods=["GET"])
        def skills():
            return jsonify(
                {
                    "skills": [
                        {"id": "github", "name": "GitHub"},
                        {"id": "weather", "name": "Weather"},
                        {"id": "coding-agent", "name": "Coding Agent"},
                    ]
                }
            )

        @self.app.route("/api/tools", methods=["GET"])
        def tools():
            return jsonify(
                {
                    "tools": [
                        {"id": "web_search", "category": "web"},
                        {"id": "web_fetch", "category": "web"},
                        {"id": "llm_think", "category": "ai"},
                        {"id": "file_read", "category": "files"},
                    ]
                }
            )

        @self.app.route("/api/memory", methods=["GET", "POST"])
        def memory():
            if request.method == "POST":
                # Store memory
                return jsonify({"status": "success", "memory_id": "new_memory"})
            return jsonify({"memories": []})

        @self.app.route("/api/chat", methods=["POST"])
        def chat():
            data = request.json
            message = data.get("message", "")

            # Process message
            if self.swarm and hasattr(self.swarm, "think"):
                response = self.swarm.think(message)
            else:
                response = f"[Simulation] Received: {message[:50]}..."

            return jsonify({"response": response, "timestamp": datetime.now().isoformat()})

        @self.app.route("/api/execute", methods=["POST"])
        def execute():
            """Execute a tool or command"""
            data = request.json
            tool = data.get("tool")
            args = data.get("args", {})

            if self.swarm and hasattr(self.swarm, "tools"):
                result = self.swarm.tools.execute(tool, **args)
            else:
                result = {"status": "simulation", "tool": tool}

            return jsonify(result)

        # WebSocket events
        if self.socketio:

            @self.socketio.on("connect")
            def handle_connect():
                print("🔌 WebSocket client connected")
                self.ws_connections.append(request.sid)

            @self.socketio.on("disconnect")
            def handle_disconnect():
                print("🔌 WebSocket client disconnected")
                if request.sid in self.ws_connections:
                    self.ws_connections.remove(request.sid)

            @self.socketio.on("message")
            def handle_message(msg):
                # Process message
                response = f"[WS] Received: {msg}"
                self.socketio.emit("response", response, room=request.sid)

    def start(self, blocking: bool = True):
        """Start the gateway"""
        print("\n🌐 Neugi Swarm Gateway")
        print(f"   Host: {self.config.host}")
        print(f"   Port: {self.config.port}")
        print(f"   WebSocket: {'Enabled' if self.socketio else 'Disabled'}")

        if FLASK_AVAILABLE:
            if self.socketio:
                print("\n🚀 Starting server...")
                self.socketio.run(
                    self.app,
                    host=self.config.host,
                    port=self.config.port,
                    debug=self.config.debug,
                )
            else:
                print("\n🚀 Starting Flask server...")
                self.app.run(
                    host=self.config.host,
                    port=self.config.port,
                    debug=self.config.debug,
                )
        else:
            print("⚠️ Falling back to SimpleHTTPServer")
            if hasattr(self, "server"):
                self.server.start()

    def stop(self):
        """Stop the gateway"""
        print("\n🛑 Stopping gateway...")

    def broadcast(self, message: str):
        """Broadcast to all WebSocket clients"""
        if self.socketio:
            self.socketio.emit("broadcast", message)


# Simple HTTP server fallback
class SimpleHTTPServer:
    """Simple HTTP server if Flask not available"""

    def __init__(self, port: int = 8089):
        self.port = port

    def start(self):
        import http.server
        import socketserver

        class Handler(http.server.SimpleHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                response = json.dumps({"status": "ok", "service": "neugi_swarm"})
                self.wfile.write(response.encode())

        with socketserver.TCPServer(("", self.port), Handler) as httpd:
            print(f"Serving on port {self.port}")
            httpd.serve_forever()


# Main
if __name__ == "__main__":
    gateway = Gateway()
    gateway.start()
