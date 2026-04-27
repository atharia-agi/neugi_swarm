"""
NEUGI v2 MCP Server - Main Server Implementation
==================================================

Full Model Context Protocol server with stdio (primary) and Streamable HTTP
(secondary) transports. Handles initialization, tool/resource/prompt operations,
ping/health, error handling, and version negotiation.

Usage:
    # stdio transport (primary - for Claude Code, OpenClaw, etc.)
    python -m neugi_swarm_v2.mcp.mcp_server

    # Streamable HTTP transport (secondary)
    python -m neugi_swarm_v2.mcp.mcp_server --transport http --port 8080

    # With custom server info
    python -m neugi_swarm_v2.mcp.mcp_server --name "NEUGI" --version "2.0.0"
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from typing import Any, Optional

from neugi_swarm_v2.mcp.protocol import (
    JSONRPCRequest,
    JSONRPCResponse,
    JSONRPCNotification,
    MCPError,
    ErrorCode,
    Implementation,
    ServerCapabilities,
    InitializeResult,
    ToolResult,
    TextContent,
    CursorResult,
    content_from_dict,
    generate_id,
)
from neugi_swarm_v2.mcp.tools import ToolRegistry
from neugi_swarm_v2.mcp.resources import ResourceRegistry
from neugi_swarm_v2.mcp.prompts import PromptRegistry

logger = logging.getLogger(__name__)

# MCP Protocol version
MCP_PROTOCOL_VERSION = "2025-03-26"

# Server metadata
SERVER_NAME = "NEUGI"
SERVER_VERSION = "2.0.0"


# -- Server State ------------------------------------------------------------

class ServerState:
    """Tracks the server lifecycle state.

    MCP servers must be initialized before handling tool/resource/prompt
    requests. This state machine enforces that contract.
    """

    CREATED = "created"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    SHUTDOWN = "shutdown"

    def __init__(self) -> None:
        self._state = self.CREATED
        self._client_info: Optional[dict[str, Any]] = None
        self._client_capabilities: Optional[dict[str, Any]] = None

    @property
    def state(self) -> str:
        return self._state

    @property
    def is_initialized(self) -> bool:
        return self._state == self.INITIALIZED

    def initialize(
        self,
        client_info: dict[str, Any],
        client_capabilities: dict[str, Any],
    ) -> None:
        """Transition to initialized state."""
        self._state = self.INITIALIZING
        self._client_info = client_info
        self._client_capabilities = client_capabilities
        self._state = self.INITIALIZED

    def shutdown(self) -> None:
        """Transition to shutdown state."""
        self._state = self.SHUTDOWN

    @property
    def client_info(self) -> Optional[dict[str, Any]]:
        return self._client_info

    @property
    def client_capabilities(self) -> Optional[dict[str, Any]]:
        return self._client_capabilities


# -- MCP Server --------------------------------------------------------------

class MCPServer:
    """Main MCP server implementing the full protocol.

    Supports:
    - stdio transport (primary)
    - Streamable HTTP transport (secondary)
    - Tool listing and invocation
    - Resource listing and reading
    - Prompt template listing and getting
    - Server ping/health
    - Error handling per MCP spec
    - Version negotiation

    Usage:
        server = MCPServer()

        # Register tools
        server.tools.register_tool(...)

        # Run with stdio
        server.run_stdio()

        # Or run with HTTP
        server.run_http(port=8080)
    """

    def __init__(
        self,
        name: str = SERVER_NAME,
        version: str = SERVER_VERSION,
        instructions: Optional[str] = None,
    ) -> None:
        """Initialize the MCP server.

        Args:
            name: Server name advertised to clients.
            version: Server version string.
            instructions: Optional human-readable instructions for clients.
        """
        self.name = name
        self.version = version
        self.instructions = instructions
        self.state = ServerState()

        # Subsystems
        self.tools = ToolRegistry()
        self.resources = ResourceRegistry()
        self.prompts = PromptRegistry()

        # Request tracking
        self._request_count = 0
        self._start_time: Optional[float] = None

        # Logging
        self._log_level = logging.INFO
        self._log_handler: Optional[logging.Handler] = None

    # -- Request Routing -----------------------------------------------------

    def handle_request(self, raw: str) -> Optional[str]:
        """Handle a raw JSON-RPC request and return a response string.

        Args:
            raw: JSON-RPC request string.

        Returns:
            JSON-RPC response string, or None for notifications.
        """
        try:
            request = JSONRPCRequest.parse(raw)
        except (json.JSONDecodeError, KeyError) as exc:
            return JSONRPCResponse.error(
                None,
                MCPError(code=ErrorCode.PARSE_ERROR, message=str(exc)),
            ).to_json()

        return self._dispatch(request)

    def _dispatch(self, request: JSONRPCRequest) -> Optional[str]:
        """Dispatch a parsed request to the appropriate handler."""
        self._request_count += 1
        method = request.method
        params = request.params or {}
        request_id = request.id

        # Notifications (no id) don't get responses
        is_notification = request_id is None

        try:
            # Initialize must come first
            if method == "initialize":
                return self._handle_initialize(params, request_id).to_json()

            # After initialization, check state
            if not self.state.is_initialized and method != "initialized":
                return JSONRPCResponse.error(
                    request_id,
                    MCPError(
                        code=ErrorCode.INVALID_REQUEST,
                        message="Server not initialized. Call 'initialize' first.",
                    ),
                ).to_json()

            # Routing table
            handlers = {
                "notifications/initialized": self._handle_initialized,
                "tools/list": self._handle_tools_list,
                "tools/call": self._handle_tools_call,
                "resources/list": self._handle_resources_list,
                "resources/read": self._handle_resources_read,
                "resources/templates/list": self._handle_resources_templates_list,
                "resources/subscribe": self._handle_resources_subscribe,
                "resources/unsubscribe": self._handle_resources_unsubscribe,
                "prompts/list": self._handle_prompts_list,
                "prompts/get": self._handle_prompts_get,
                "ping": self._handle_ping,
                "logging/setLevel": self._handle_logging_set_level,
            }

            handler = handlers.get(method)
            if handler is None:
                return JSONRPCResponse.error(
                    request_id,
                    MCPError(
                        code=ErrorCode.METHOD_NOT_FOUND,
                        message=f"Method not found: {method}",
                    ),
                ).to_json()

            result = handler(params, request_id)

            # Notifications don't get responses
            if is_notification:
                return None

            if result is not None:
                return JSONRPCResponse.success(request_id, result).to_json()
            return JSONRPCResponse.success(request_id, {}).to_json()

        except Exception as exc:
            logger.error("Request handler error for %s: %s", method, exc, exc_info=True)
            return JSONRPCResponse.error(
                request_id,
                MCPError(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=f"Internal error: {str(exc)}",
                ),
            ).to_json()

    # -- Initialize ----------------------------------------------------------

    def _handle_initialize(
        self, params: dict[str, Any], request_id: Any
    ) -> JSONRPCResponse:
        """Handle the initialize request.

        Validates protocol version and establishes server capabilities.
        """
        protocol_version = params.get("protocolVersion", "")

        # Version negotiation
        if protocol_version and protocol_version != MCP_PROTOCOL_VERSION:
            logger.warning(
                "Client protocol version mismatch: client=%s, server=%s",
                protocol_version,
                MCP_PROTOCOL_VERSION,
            )
            # We still accept but log the mismatch per MCP spec

        client_info = params.get("clientInfo", {})
        client_capabilities = params.get("capabilities", {})

        self.state.initialize(client_info, client_capabilities)
        self._start_time = time.time()

        logger.info(
            "Initialized by client: %s %s",
            client_info.get("name", "unknown"),
            client_info.get("version", "unknown"),
        )

        result = InitializeResult(
            protocol_version=MCP_PROTOCOL_VERSION,
            capabilities=ServerCapabilities.full_capabilities(),
            server_info=Implementation(name=self.name, version=self.version),
            instructions=self.instructions,
        )

        return JSONRPCResponse.success(request_id, result.to_dict())

    def _handle_initialized(
        self, params: dict[str, Any], request_id: Any
    ) -> None:
        """Handle the initialized notification (client confirms initialization)."""
        logger.info("Client confirmed initialization")

    # -- Tools ---------------------------------------------------------------

    def _handle_tools_list(
        self, params: dict[str, Any], request_id: Any
    ) -> dict[str, Any]:
        """Handle tools/list request with pagination."""
        cursor = params.get("cursor")
        page_size = int(params.get("pageSize", 50))

        tools = self.tools.list_tools()
        page_result = self._paginate([t.to_dict() for t in tools], cursor, page_size)

        return {"tools": page_result.items, **({"nextCursor": page_result.next_cursor} if page_result.next_cursor else {})}

    def _handle_tools_call(
        self, params: dict[str, Any], request_id: Any
    ) -> dict[str, Any]:
        """Handle tools/call request."""
        name = params.get("name")
        if not name:
            raise ValueError("Tool name is required")

        arguments = params.get("arguments", {})

        result = self.tools.execute(name, arguments)
        return result.to_dict()

    # -- Resources -----------------------------------------------------------

    def _handle_resources_list(
        self, params: dict[str, Any], request_id: Any
    ) -> dict[str, Any]:
        """Handle resources/list request with pagination."""
        cursor = params.get("cursor")
        page_size = int(params.get("pageSize", 50))

        resources = self.resources.list_resources()
        page_result = self._paginate([r.to_dict() for r in resources], cursor, page_size)

        return {
            "resources": page_result.items,
            **({"nextCursor": page_result.next_cursor} if page_result.next_cursor else {}),
        }

    def _handle_resources_read(
        self, params: dict[str, Any], request_id: Any
    ) -> dict[str, Any]:
        """Handle resources/read request."""
        uri = params.get("uri")
        if not uri:
            raise ValueError("Resource URI is required")

        contents = self.resources.read_resource(uri)
        return {"contents": [contents.to_dict()]}

    def _handle_resources_templates_list(
        self, params: dict[str, Any], request_id: Any
    ) -> dict[str, Any]:
        """Handle resources/templates/list request."""
        cursor = params.get("cursor")
        page_size = int(params.get("pageSize", 50))

        templates = self.resources.list_templates()
        page_result = self._paginate([t.to_dict() for t in templates], cursor, page_size)

        return {
            "resourceTemplates": page_result.items,
            **({"nextCursor": page_result.next_cursor} if page_result.next_cursor else {}),
        }

    def _handle_resources_subscribe(
        self, params: dict[str, Any], request_id: Any
    ) -> dict[str, Any]:
        """Handle resources/subscribe request."""
        uri = params.get("uri")
        if not uri:
            raise ValueError("Resource URI is required")

        # For stdio transport, we track subscriptions but notifications
        # are sent via the transport layer
        self.resources.subscribe(uri, lambda n: self._on_resource_update(n))
        return {}

    def _handle_resources_unsubscribe(
        self, params: dict[str, Any], request_id: Any
    ) -> dict[str, Any]:
        """Handle resources/unsubscribe request."""
        uri = params.get("uri")
        if not uri:
            raise ValueError("Resource URI is required")

        self.resources.unsubscribe(uri)
        return {}

    def _on_resource_update(self, notification: Any) -> None:
        """Handle resource update notifications."""
        logger.info("Resource updated: %s", notification.uri)
        # In stdio mode, we'd send this as a notification to the client
        # This is handled by the transport layer

    # -- Prompts -------------------------------------------------------------

    def _handle_prompts_list(
        self, params: dict[str, Any], request_id: Any
    ) -> dict[str, Any]:
        """Handle prompts/list request with pagination."""
        cursor = params.get("cursor")
        page_size = int(params.get("pageSize", 50))

        prompts = self.prompts.list_templates()
        page_result = self._paginate([p.to_dict() for p in prompts], cursor, page_size)

        return {
            "prompts": page_result.items,
            **({"nextCursor": page_result.next_cursor} if page_result.next_cursor else {}),
        }

    def _handle_prompts_get(
        self, params: dict[str, Any], request_id: Any
    ) -> dict[str, Any]:
        """Handle prompts/get request."""
        name = params.get("name")
        if not name:
            raise ValueError("Prompt name is required")

        arguments = params.get("arguments", {})
        result = self.prompts.get_prompt(name, arguments)
        return result.to_dict()

    # -- Ping / Health -------------------------------------------------------

    def _handle_ping(
        self, params: dict[str, Any], request_id: Any
    ) -> dict[str, Any]:
        """Handle ping request for health checking."""
        uptime = time.time() - self._start_time if self._start_time else 0
        return {
            "status": "ok",
            "uptime_seconds": round(uptime, 2),
            "requests_handled": self._request_count,
            "state": self.state.state,
        }

    # -- Logging -------------------------------------------------------------

    def _handle_logging_set_level(
        self, params: dict[str, Any], request_id: Any
    ) -> dict[str, Any]:
        """Handle logging/setLevel request."""
        level = params.get("level", "info")
        level_map = {
            "debug": logging.DEBUG,
            "info": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
            "critical": logging.CRITICAL,
        }
        self._log_level = level_map.get(level.lower(), logging.INFO)
        logging.getLogger("neugi_swarm_v2.mcp").setLevel(self._log_level)
        return {}

    # -- Pagination Helper ---------------------------------------------------

    def _paginate(
        self, items: list[Any], cursor: Optional[str], page_size: int
    ) -> CursorResult:
        """Paginate a list of items."""
        start = int(cursor) if cursor else 0
        end = start + page_size
        page = items[start:end]
        next_cursor = str(end) if end < len(items) else None
        return CursorResult(items=page, next_cursor=next_cursor)

    # -- Transport: stdio ----------------------------------------------------

    def run_stdio(self) -> None:
        """Run the server using stdio transport.

        Reads JSON-RPC messages from stdin, writes responses to stdout.
        This is the primary transport for Claude Code, OpenClaw, etc.
        """
        logging.basicConfig(
            level=logging.WARNING,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            stream=sys.stderr,  # Logs go to stderr, not stdout
        )
        logger.info("NEUGI MCP Server starting (stdio transport)")

        try:
            for line in sys.stdin:
                line = line.strip()
                if not line:
                    continue

                response = self.handle_request(line)
                if response is not None:
                    sys.stdout.write(response + "\n")
                    sys.stdout.flush()

        except KeyboardInterrupt:
            logger.info("Server interrupted")
        except Exception as exc:
            logger.error("Server error: %s", exc, exc_info=True)
        finally:
            self.state.shutdown()
            logger.info("NEUGI MCP Server stopped")

    # -- Transport: Streamable HTTP ------------------------------------------

    def run_http(self, host: str = "0.0.0.0", port: int = 8080) -> None:
        """Run the server using Streamable HTTP transport.

        Implements the MCP Streamable HTTP transport spec:
        - POST /message for requests/notifications
        - GET /messages for SSE stream (optional)
        - Server-Sent Events for notifications

        Args:
            host: Bind address.
            port: Bind port.
        """
        try:
            from http.server import HTTPServer, BaseHTTPRequestHandler
            import threading
        except ImportError:
            logger.error("http.server not available")
            return

        server_instance = self

        class MCPHTTPHandler(BaseHTTPRequestHandler):
            """HTTP request handler for MCP Streamable HTTP."""

            def do_POST(self) -> None:
                """Handle POST requests (MCP messages)."""
                if self.path not in ("/message", "/messages"):
                    self._send_error(404, "Not found")
                    return

                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length)

                try:
                    raw = body.decode("utf-8")
                    response = server_instance.handle_request(raw)

                    if response is not None:
                        self._send_json(200, json.loads(response))
                    else:
                        self._send_json(202, {"status": "accepted"})

                except Exception as exc:
                    self._send_error(500, str(exc))

            def do_GET(self) -> None:
                """Handle GET requests (health check / SSE)."""
                if self.path == "/health":
                    self._send_json(200, {
                        "status": "ok",
                        "server": server_instance.name,
                        "version": server_instance.version,
                        "state": server_instance.state.state,
                    })
                elif self.path == "/messages":
                    self._send_sse_headers()
                else:
                    self._send_error(404, "Not found")

            def _send_json(self, status: int, data: Any) -> None:
                """Send a JSON response."""
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(data).encode("utf-8"))

            def _send_error(self, status: int, message: str) -> None:
                """Send an error response."""
                self._send_json(status, {"error": message})

            def _send_sse_headers(self) -> None:
                """Send SSE headers for streaming."""
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()

            def log_message(self, format: str, *args: Any) -> None:
                """Suppress default HTTP logging."""
                pass

        httpd = HTTPServer((host, port), MCPHTTPHandler)
        logger.info("NEUGI MCP Server starting (HTTP transport) on %s:%d", host, port)
        print(f"NEUGI MCP Server running on http://{host}:{port}")
        print(f"  POST /message - Send MCP requests")
        print(f"  GET  /health  - Health check")
        print(f"  GET  /messages - SSE stream")

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            logger.info("Server interrupted")
        finally:
            httpd.shutdown()
            self.state.shutdown()
            logger.info("NEUGI MCP Server stopped")

    # -- Setup Helpers -------------------------------------------------------

    def setup_neugi(
        self,
        memory_system: Optional[Any] = None,
        skill_manager: Optional[Any] = None,
        agent_manager: Optional[Any] = None,
        session_manager: Optional[Any] = None,
        config: Optional[Any] = None,
    ) -> None:
        """Set up the server with NEUGI subsystems.

        Args:
            memory_system: MemorySystem instance.
            skill_manager: SkillManager instance.
            agent_manager: AgentManager instance.
            session_manager: SessionManager instance.
            config: NeugiConfig instance.
        """
        self.tools.register_neugi_tools(
            memory_system=memory_system,
            skill_manager=skill_manager,
            agent_manager=agent_manager,
            session_manager=session_manager,
        )

        self.resources.register_neugi_resources(
            memory_system=memory_system,
            skill_manager=skill_manager,
            agent_manager=agent_manager,
            config=config,
        )

        self.prompts.register_neugi_prompts()

    @property
    def stats(self) -> dict[str, Any]:
        """Get server statistics."""
        return {
            "server": self.name,
            "version": self.version,
            "state": self.state.state,
            "requests_handled": self._request_count,
            "tools": self.tools.stats,
            "resources": self.resources.stats,
            "prompts": self.prompts.stats,
        }


# -- CLI Entry Point ---------------------------------------------------------

def main() -> None:
    """CLI entry point for the MCP server."""
    parser = argparse.ArgumentParser(description="NEUGI v2 MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport mode (default: stdio)",
    )
    parser.add_argument("--host", default="0.0.0.0", help="HTTP bind host")
    parser.add_argument("--port", type=int, default=8080, help="HTTP bind port")
    parser.add_argument("--name", default=SERVER_NAME, help="Server name")
    parser.add_argument("--version", default=SERVER_VERSION, help="Server version")
    parser.add_argument(
        "--instructions",
        default=None,
        help="Server instructions for clients",
    )
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error"],
        default="warning",
        help="Logging level",
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.WARNING),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )

    server = MCPServer(
        name=args.name,
        version=args.version,
        instructions=args.instructions,
    )

    if args.transport == "stdio":
        server.run_stdio()
    else:
        server.run_http(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
