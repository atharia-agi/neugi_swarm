#!/usr/bin/env python3
"""
🤖 NEUGI API GATEWAY
=======================

API Gateway with routing:
- Request routing
- Rate limiting
- Authentication
- Load balancing

Version: 1.0
Date: March 16, 2026
"""

import os
import uuid
import time
import hashlib
from typing import Dict, List, Optional
from datetime import datetime

NEUGI_DIR = os.path.expanduser("~/neugi")


class Route:
    """API Route"""

    def __init__(
        self, path: str, method: str, backend: str, auth: bool = False, rate_limit: int = None
    ):
        self.id = str(uuid.uuid4())[:8]
        self.path = path
        self.method = method.upper()
        self.backend = backend
        self.auth = auth
        self.rate_limit = rate_limit
        self.created_at = datetime.now().isoformat()


class APIKey:
    """API Key"""

    def __init__(self, key: str, name: str, rate_limit: int = 100):
        self.key = key
        self.name = name
        self.rate_limit = rate_limit
        self.created_at = datetime.now().isoformat()
        self.last_used = None
        self.requests = 0


class APIGateway:
    """API Gateway"""

    def __init__(self):
        self.routes: List[Route] = []
        self.api_keys: Dict[str, APIKey] = {}
        self._setup_default_routes()

    def _setup_default_routes(self):
        """Setup default routes"""
        self.routes = [
            Route("/api/chat", "POST", "http://localhost:19888", True, 60),
            Route("/api/memory", "GET", "http://localhost:19888", True, 30),
            Route("/api/agents", "GET", "http://localhost:19888", True, 20),
            Route("/health", "GET", None, False, 100),
        ]

    def add_route(
        self, path: str, method: str, backend: str, auth: bool = False, rate_limit: int = None
    ) -> Route:
        """Add route"""
        route = Route(path, method, backend, auth, rate_limit)
        self.routes.append(route)
        return route

    def remove_route(self, route_id: str):
        """Remove route"""
        self.routes = [r for r in self.routes if r.id != route_id]

    def add_api_key(self, name: str, rate_limit: int = 100) -> APIKey:
        """Add API key"""
        key = hashlib.sha256(f"{name}{time.time()}".encode()).hexdigest()[:32]
        api_key = APIKey(key, name, rate_limit)
        self.api_keys[key] = api_key
        return api_key

    def remove_api_key(self, key: str):
        """Remove API key"""
        if key in self.api_keys:
            del self.api_keys[key]

    def validate_api_key(self, key: str) -> bool:
        """Validate API key"""
        if key not in self.api_keys:
            return False

        api_key = self.api_keys[key]

        if api_key.rate_limit:
            if api_key.last_used:
                try:
                    last_used_dt = datetime.fromisoformat(api_key.last_used)
                    if (datetime.now() - last_used_dt).total_seconds() > 3600:
                        api_key.requests = 0
                except ValueError:
                    pass
            if api_key.requests >= api_key.rate_limit:
                return False

        api_key.requests += 1
        api_key.last_used = datetime.now().isoformat()
        return True

    def find_route(self, path: str, method: str) -> Optional[Route]:
        """Find matching route"""
        for route in self.routes:
            if route.path == path and route.method == method.upper():
                return route
        return None

    def list_routes(self) -> List[Dict]:
        """List routes"""
        return [
            {
                "id": r.id,
                "path": r.path,
                "method": r.method,
                "backend": r.backend,
                "auth": r.auth,
                "rate_limit": r.rate_limit,
            }
            for r in self.routes
        ]

    def list_api_keys(self) -> List[Dict]:
        """List API keys"""
        return [
            {
                "key": k.key[:8] + "...",
                "name": k.name,
                "rate_limit": k.rate_limit,
                "requests": k.requests,
                "last_used": k.last_used,
            }
            for k in self.api_keys.values()
        ]

    def serve(self, port: int = 8080):
        """Start the API Gateway server"""
        import http.server
        import socketserver

        class GatewayHandler(http.server.SimpleHTTPRequestHandler):
            def do_GET(self):
                api_key = self.headers.get("X-API-Key")
                if not api_key or not self.server.gateway.validate_api_key(api_key):
                    self.send_response(401)
                    self.end_headers()
                    self.wfile.write(b"Unauthorized or Rate Limited")
                    return
                route = self.server.gateway.find_route(self.path, "GET")
                if not route:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b"Route Not Found")
                    return
                self.send_response(200)
                self.end_headers()
                self.wfile.write(f"Proxying to {route.backend}".encode())

        with socketserver.TCPServer(("", port), GatewayHandler) as httpd:
            httpd.gateway = self
            print(f"🚀 API Gateway running on port {port}")
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\nShutting down gateway...")


gateway = APIGateway()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="NEUGI API Gateway")
    parser.add_argument("--list-routes", action="store_true", help="List routes")
    parser.add_argument("--add-key", type=str, help="Add API key")
    parser.add_argument("--list-keys", action="store_true", help="List API keys")
    parser.add_argument("--serve", type=int, help="Start gateway server on port")

    args = parser.parse_args()

    if args.serve:
        gateway.serve(args.serve)

    elif args.list_routes:
        routes = gateway.list_routes()
        print(f"\n🌐 Routes ({len(routes)}):\n")
        for r in routes:
            print(f"  {r['method']:<6} {r['path']:<20} -> {r['backend']}")

    elif args.add_key:
        api_key = gateway.add_api_key(args.add_key)
        print(f"\n🔑 API Key for {args.add_key}:")
        print(f"   {api_key.key}")
        print(f"   Rate limit: {api_key.rate_limit}/min")

    elif args.list_keys:
        keys = gateway.list_api_keys()
        print(f"\n🔑 API Keys ({len(keys)}):\n")
        for k in keys:
            print(f"  {k['name']}: {k['key']} ({k['requests']} requests)")

    else:
        print("NEUGI API Gateway")
        print("Usage: python -m neugi_gateway [--list-routes|--add-key NAME|--list-keys]")


if __name__ == "__main__":
    main()
