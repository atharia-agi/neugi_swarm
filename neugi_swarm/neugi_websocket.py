#!/usr/bin/env python3
"""
🤖 NEUGI WEBSOCKET SERVER
===========================

WebSocket server for real-time communication:
- Real-time messaging
- Event streaming
- Live updates
- Broadcasting

Version: 1.0
Date: March 16, 2026
"""

import os
import json
import asyncio
import threading
from typing import Dict, List, Callable, Any
from datetime import datetime
from pathlib import Path

NEUGI_DIR = os.path.expanduser("~/neugi")


class WebSocketClient:
    """WebSocket client"""

    def __init__(self, client_id: str, websocket, address: tuple):
        self.client_id = client_id
        self.websocket = websocket
        self.address = address
        self.subscriptions = set()
        self.metadata = {}
        self.connected_at = datetime.now().isoformat()

    async def send(self, message: Dict):
        """Send message to client"""
        try:
            await self.websocket.send_json(message)
            return True
        except:
            return False

    async def receive(self) -> Dict:
        """Receive message from client"""
        try:
            data = await self.websocket.receive_json()
            return data
        except:
            return {}


class WebSocketServer:
    """WebSocket server"""

    def __init__(self, host: str = "0.0.0.0", port: int = 19920):
        self.host = host
        self.port = port
        self.clients: Dict[str, WebSocketClient] = {}
        self.handlers: Dict[str, Callable] = {}
        self._running = False
        self._thread = None

    def register_handler(self, event_type: str, handler: Callable):
        """Register event handler"""
        self.handlers[event_type] = handler

    def broadcast(self, event_type: str, data: Any):
        """Broadcast to all clients"""
        message = {"type": event_type, "data": data, "timestamp": datetime.now().isoformat()}

        for client in list(self.clients.values()):
            try:
                asyncio.create_task(client.send(message))
            except:
                pass

    def send_to(self, client_id: str, event_type: str, data: Any):
        """Send to specific client"""
        client = self.clients.get(client_id)
        if client:
            message = {"type": event_type, "data": data, "timestamp": datetime.now().isoformat()}
            asyncio.create_task(client.send(message))

    def send_to_group(self, group: str, event_type: str, data: Any):
        """Send to group of clients"""
        message = {"type": event_type, "data": data, "timestamp": datetime.now().isoformat()}

        for client in list(self.clients.values()):
            if group in client.subscriptions:
                asyncio.create_task(client.send(message))

    def get_clients(self) -> List[Dict]:
        """Get all connected clients"""
        return [
            {
                "id": c.client_id,
                "address": c.address,
                "subscriptions": list(c.subscriptions),
                "connected_at": c.connected_at,
            }
            for c in self.clients.values()
        ]

    def remove_client(self, client_id: str):
        """Remove client"""
        if client_id in self.clients:
            del self.clients[client_id]


class EventStream:
    """Event streaming"""

    def __init__(self):
        self.listeners: Dict[str, List[Callable]] = {}
        self.history: List[Dict] = []
        self.max_history = 100

    def emit(self, event_type: str, data: Any):
        """Emit event"""
        event = {"type": event_type, "data": data, "timestamp": datetime.now().isoformat()}

        self.history.append(event)
        if len(self.history) > self.max_history:
            self.history.pop(0)

        if event_type in self.listeners:
            for listener in self.listeners[event_type]:
                try:
                    listener(event)
                except:
                    pass

    def on(self, event_type: str, listener: Callable):
        """Register listener"""
        if event_type not in self.listeners:
            self.listeners[event_type] = []
        self.listeners[event_type].append(listener)

    def off(self, event_type: str, listener: Callable):
        """Unregister listener"""
        if event_type in self.listeners:
            if listener in self.listeners[event_type]:
                self.listeners[event_type].remove(listener)

    def get_history(self, event_type: str = None, limit: int = 50) -> List[Dict]:
        """Get event history"""
        if event_type:
            return [e for e in self.history if e["type"] == event_type][-limit:]
        return self.history[-limit:]


class WebSocketManager:
    """WebSocket manager with FastAPI"""

    def __init__(self):
        self.server = None
        self.event_stream = EventStream()

    def create_app(self):
        """Create FastAPI app with WebSocket"""
        try:
            from fastapi import FastAPI, WebSocket, WebSocketDisconnect
            from fastapi.responses import HTMLResponse
        except ImportError:
            print("Install: pip install fastapi websockets")
            return None

        app = FastAPI(title="NEUGI WebSocket")

        @app.websocket("/ws/{client_id}")
        async def websocket_endpoint(websocket: WebSocket, client_id: str):
            await websocket.accept()

            client = WebSocketClient(client_id, websocket, websocket.client)
            self.server.clients[client_id] = client

            try:
                while True:
                    data = await websocket.receive_json()
                    event_type = data.get("type", "message")

                    if event_type == "subscribe":
                        client.subscriptions.add(data.get("channel"))

                    elif event_type == "unsubscribe":
                        if data.get("channel") in client.subscriptions:
                            client.subscriptions.remove(data.get("channel"))

                    elif event_type in self.server.handlers:
                        await self.server.handlers[event_type](client, data)

                    else:
                        self.event_stream.emit(event_type, data.get("data"))

            except WebSocketDisconnect:
                self.server.remove_client(client_id)

        @app.get("/")
        async def index():
            return HTMLResponse("<h1>NEUGI WebSocket Server</h1>")

        @app.get("/clients")
        async def list_clients():
            return self.server.get_clients()

        @app.get("/events")
        async def get_events(event_type: str = None, limit: int = 50):
            return self.event_stream.get_history(event_type, limit)

        @app.post("/broadcast")
        async def broadcast(data: dict):
            event_type = data.get("type", "broadcast")
            self.server.broadcast(event_type, data.get("data"))
            return {"success": True}

        return app

    def run(self, host: str = "0.0.0.0", port: int = 19920):
        """Run WebSocket server"""
        try:
            import uvicorn
        except ImportError:
            print("Install: pip install uvicorn")
            return

        self.server = WebSocketServer(host, port)
        app = self.create_app()

        if app:
            print(f"WebSocket Server running at ws://{host}:{port}")
            uvicorn.run(app, host=host, port=port)


ws_manager = WebSocketManager()
event_stream = EventStream()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="NEUGI WebSocket Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host")
    parser.add_argument("--port", type=int, default=19920, help="Port")

    args = parser.parse_args()

    ws_manager.run(args.host, args.port)


if __name__ == "__main__":
    main()
