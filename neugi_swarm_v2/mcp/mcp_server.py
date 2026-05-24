"""
MCP Server Implementation - Core Server Class
==============================================
Main MCP server that integrates with NEUGI Swarm subsystems.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable
from typing import Any

from neugi_swarm_v2.mcp.messages import (
    CANCEL_REQUEST,
    ERROR_INTERNAL,
    ERROR_METHOD_NOT_FOUND,
    ERROR_PROMPT_NOT_FOUND,
    INITIALIZE,
    INITIALIZED,
    PING,
    PROMPTS_GET,
    PROMPTS_LIST,
    RESOURCES_LIST,
    RESOURCES_READ,
    TOOLS_CALL,
    TOOLS_LIST,
    CallToolResult,
    GetPromptResult,
    InitializeParams,
    InitializeResult,
    NotificationMessage,
    RequestMessage,
    ResponseMessage,
)
from neugi_swarm_v2.mcp.prompt_manager import PromptManager
from neugi_swarm_v2.mcp.resource_manager import ResourceManager
from neugi_swarm_v2.mcp.tool_manager import ToolManager
from neugi_swarm_v2.mcp.transport import (
    BaseTransport,
    HTTPTransport,
    StdioTransport,
)

logger = logging.getLogger(__name__)


class MCPServer:
    """Main MCP Server for NEUGI Swarm.

    Provides Model Context Protocol interface for connecting
    external agents, IDEs, and MCP clients to NEUGI's tools,
    resources, and prompt templates.
    """

    VERSION = "2024-11-05"
    CAPABILITIES: dict[str, dict[str, Any]] = {
        "tools": {},
        "resources": {},
        "prompts": {},
        "logging": {},
    }

    def __init__(
        self,
        name: str = "neugi-swarm",
        version: str = "2.1.3",
        transport: BaseTransport | None = None,
        bridge: Any | None = None,
    ):
        self.name = name
        self.version = version
        self.session_id = str(uuid.uuid4())

        # Core managers
        self.tools = ToolManager()
        self.resources = ResourceManager()
        self.prompts = PromptManager()

        # Transport
        self.transport = transport or StdioTransport()

        # Bridge to NEUGI subsystems
        self._bridge = bridge
        self._neugi: Any | None = None

        # Session state
        self._initialized = False
        self._client_capabilities: dict[str, Any] = {}
        self._message_handlers: list[Callable] = []
        self._running = False
        self._sse_publish_task: asyncio.Task | None = None

        # Running tool tasks for cancellation support
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._task_events: dict[str, asyncio.Event] = {}

        # Register default tools and resources
        self._install_defaults()

    def _install_defaults(self) -> None:
        """Install default tools, resources, and prompts."""
        self._install_default_tools()
        self._install_default_resources()
        self.prompts.install_default_prompts()

    def _install_default_tools(self) -> None:
        """Install default NEUGI MCP tools."""

        @self.tools.register(
            name="echo",
            description="Echo back the input message",
            input_schema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Message to echo",
                    }
                },
                "required": ["message"],
            },
        )
        def echo_tool(message: str) -> str:
            return f"Echo: {message}"

        @self.tools.register(
            name="get_time",
            description="Get current server time",
            input_schema={
                "type": "object",
                "properties": {},
            },
        )
        def get_time_tool() -> str:
            from datetime import datetime
            return datetime.now().isoformat()

        @self.tools.register(
            name="list_tools",
            description="List all available MCP tools",
            input_schema={
                "type": "object",
                "properties": {},
            },
        )
        def list_tools_tool() -> list:
            return self.tools.get_tools()

        @self.tools.register(
            name="list_resources",
            description="List all available MCP resources",
            input_schema={
                "type": "object",
                "properties": {},
            },
        )
        def list_resources_tool() -> list:
            result = self.resources.list_resources()
            return result.resources

        @self.tools.register(
            name="read_resource",
            description="Read a specific resource by URI",
            input_schema={
                "type": "object",
                "properties": {
                    "uri": {
                        "type": "string",
                        "description": "Resource URI to read",
                    }
                },
                "required": ["uri"],
            },
        )
        def read_resource_tool(uri: str) -> str:
            result = self.resources.read_resource(uri)
            if result.contents:
                return result.contents[0].get("text", "")
            return "Resource not found"

        @self.tools.register(
            name="list_prompts",
            description="List all available prompt templates",
            input_schema={
                "type": "object",
                "properties": {},
            },
        )
        def list_prompts_tool() -> list:
            result = self.prompts.list_prompts()
            return result.prompts if result.prompts else []

        @self.tools.register(
            name="get_prompt",
            description="Get a specific prompt template",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Prompt template name",
                    }
                },
                "required": ["name"],
            },
        )
        def get_prompt_tool(name: str) -> str:
            template = self.prompts.get_prompt(name)
            if template:
                return f"Name: {template.name}\nDescription: {template.description}\n\nTemplate:\n{template.template}"
            return f"Prompt template not found: {name}"

        @self.tools.register(
            name="system_info",
            description="Get NEUGI system information",
            input_schema={
                "type": "object",
                "properties": {},
            },
        )
        def system_info_tool() -> dict:
            info = {
                "name": self.name,
                "version": self.version,
                "mcp_version": self.VERSION,
                "session_id": self.session_id,
                "tools_count": self.tools.count(),
                "resources_count": self.resources.count(),
                "prompts_count": self.prompts.count(),
                "initialized": self._initialized,
                "bridge_connected": self._bridge is not None and self._bridge.is_connected if self._bridge else False,
            }
            if self._neugi:
                info["neugi_version"] = getattr(self._neugi, "__version__", "unknown")
                info["autonomous_running"] = (
                    self._neugi.autonomous_loop.state.value
                    if self._neugi.autonomous_loop
                    else None
                )
            return info

        @self.tools.register(
            name="health_check",
            description="Perform a health check on the MCP server",
            input_schema={
                "type": "object",
                "properties": {},
            },
        )
        def health_check_tool() -> dict:
            health = {
                "status": "healthy",
                "timestamp": __import__('datetime').datetime.now().isoformat(),
                "tools": self.tools.count(),
                "resources": self.resources.count(),
                "prompts": self.prompts.count(),
                "bridge": "connected" if (self._bridge and self._bridge.is_connected) else "disconnected",
            }
            if self._neugi:
                try:
                    from neugi_swarm_v2.memory import MemorySystem
                    if isinstance(self._neugi.memory, MemorySystem):
                        health["memory"] = "active"
                except Exception:
                    pass
            return health

        logger.info("Installed %d default MCP tools", self.tools.count())

    def _install_default_resources(self) -> None:
        """Install default MCP resources."""
        self.resources.register_static(
            uri="neugi://server/info",
            name="NEUGI Server Info",
            description="Basic server information and status",
            mimeType="application/json",
            content={
                "name": self.name,
                "version": self.version,
                "mcp_version": self.VERSION,
                "capabilities": self.CAPABILITIES,
            },
        )

        self.resources.register_static(
            uri="neugi://server/capabilities",
            name="Server Capabilities",
            description="MCP capabilities supported by this server",
            mimeType="application/json",
            content=self.CAPABILITIES,
        )

        # SSE info resource
        self.resources.register_static(
            uri="neugi://server/sse-info",
            name="SSE Endpoint Info",
            description="How to connect via Server-Sent Events",
            mimeType="application/json",
            content={
                "endpoint": "/sse",
                "protocol": "text/event-stream",
                "events_available": [
                    "tool_execution_success",
                    "tool_execution_failure",
                    "mcp_call",
                    "memory_update",
                    "agent_activity",
                    "system_event",
                ],
                "connect_example": "GET /sse?events=tool_execution_success,memory_update&token=<auth_token>",
                "rate_limiting": "10 events/second, burst 20",
                "authentication": "Optional query param: ?token=<token>",
                "cancellation_supported": True,
            },
        )

        logger.info("Installed default MCP resources")

    async def initialize(self, params: InitializeParams) -> InitializeResult:
        """Handle MCP initialize request."""
        logger.info(
            "Initializing MCP session (protocol=%s, client=%s)",
            params.protocol_version,
            params.client_info,
        )

        self._client_capabilities = params.capabilities or {}
        self._initialized = True

        return InitializeResult(
            protocol_version=self.VERSION,
            capabilities=self.CAPABILITIES,
            server_info={
                "name": self.name,
                "version": self.version,
            },
        )

    async def handle_request(self, request: RequestMessage) -> ResponseMessage:
        """Handle an incoming MCP request."""
        method = request.method
        params = request.params or {}

        logger.debug("Handling request: %s", method)

        try:
            if method == INITIALIZE:
                init_params = InitializeParams(**params)
                result = await self.initialize(init_params)
                return ResponseMessage(result=result.to_dict(), id=request.id)

            elif method == INITIALIZED:
                return ResponseMessage(result={}, id=request.id)

            elif method == TOOLS_LIST:
                result = self.tools.list_tools()
                return ResponseMessage(result=result.to_dict(), id=request.id)

            elif method == TOOLS_CALL:
                tool_name = params.get("name", "")
                tool_args = params.get("arguments", {})
                task_id = str(request.id)

                # Track for cancellation support
                cancel_event = asyncio.Event()
                self._task_events[task_id] = cancel_event

                async def _call_with_cancel():
                    return await self.tools.call_tool(tool_name, tool_args, request.id)

                task = asyncio.create_task(_call_with_cancel())
                self._running_tasks[task_id] = task

                try:
                    result = await asyncio.wait_for(
                        task,
                        timeout=params.get("timeout", None),
                    )
                except asyncio.TimeoutError:
                    task.cancel()
                    result = CallToolResult(
                        content=[{"type": "text", "text": f"Tool execution timed out: {tool_name}"}],
                        isError=True,
                    )
                except asyncio.CancelledError:
                    result = CallToolResult(
                        content=[{"type": "text", "text": f"Tool execution cancelled: {tool_name}"}],
                        isError=True,
                    )
                finally:
                    self._running_tasks.pop(task_id, None)
                    self._task_events.pop(task_id, None)
                    cancel_event.set()

                # Publish SSE event if available
                if isinstance(self.transport, HTTPTransport):
                    try:
                        await self.transport.publish_sse_event(
                            "tool_execution_result",
                            {
                                "tool_name": tool_name,
                                "result": result.to_dict(),
                                "session_id": self.session_id,
                            },
                        )
                    except Exception:
                        pass

                return ResponseMessage(result=result.to_dict(), id=request.id)

            elif method == RESOURCES_LIST:
                cursor = params.get("cursor")
                result = self.resources.list_resources(cursor)
                return ResponseMessage(result=result.to_dict(), id=request.id)

            elif method == RESOURCES_READ:
                uri = params.get("uri", "")
                result = self.resources.read_resource(uri)
                return ResponseMessage(result=result.to_dict(), id=request.id)

            elif method == PROMPTS_LIST:
                result = self.prompts.list_prompts()
                return ResponseMessage(result=result.to_dict(), id=request.id)

            elif method == PROMPTS_GET:
                name = params.get("name", "")
                args = params.get("arguments", {})
                template = self.prompts.get_prompt(name)
                if template:
                    rendered = self.prompts.render_prompt(name, args)
                    result = GetPromptResult(
                        description=template.description,
                        messages=[{
                            "role": "system",
                            "content": rendered,
                        }],
                    )
                else:
                    return ResponseMessage(
                        error={
                            "code": ERROR_PROMPT_NOT_FOUND,
                            "message": f"Prompt not found: {name}",
                        },
                        id=request.id,
                    )
                return ResponseMessage(result=result.to_dict(), id=request.id)

            elif method == PING:
                return ResponseMessage(result={}, id=request.id)

            elif method == CANCEL_REQUEST:
                cancel_id = params.get("requestId", str(request.id))
                task = self._running_tasks.get(cancel_id)
                if task and not task.done():
                    task.cancel()
                    logger.info("Cancelled running task: %s", cancel_id)
                    return ResponseMessage(
                        result={"status": "cancelled", "task_id": cancel_id},
                        id=request.id,
                    )
                # Also try the event-based cancellation
                cancel_event = self._task_events.get(cancel_id)
                if cancel_event:
                    cancel_event.set()
                    logger.info("Cancelled task via event: %s", cancel_id)
                    return ResponseMessage(
                        result={"status": "cancelled", "task_id": cancel_id},
                        id=request.id,
                    )
                return ResponseMessage(
                    result={"status": "not_found", "task_id": cancel_id},
                    id=request.id,
                )

            else:
                return ResponseMessage(
                    error={
                        "code": ERROR_METHOD_NOT_FOUND,
                        "message": f"Method not found: {method}",
                    },
                    id=request.id,
                )

        except Exception as e:
            logger.error("Error handling request %s: %s", method, e, exc_info=True)
            return ResponseMessage(
                error={
                    "code": ERROR_INTERNAL,
                    "message": str(e),
                },
                id=request.id,
            )

    def _create_error_response(
        self, request_id: Any, code: int, message: str
    ) -> dict:
        """Create a JSON-RPC error response."""
        return {
            "jsonrpc": "2.0",
            "error": {"code": code, "message": message},
            "id": request_id,
        }

    async def run_stdio(self) -> None:
        """Run MCP server using stdio transport."""
        transport = StdioTransport()

        async def message_handler(message: Any) -> None:
            if isinstance(message, RequestMessage):
                response = await self.handle_request(message)
                await transport.send_response(response)
            elif isinstance(message, NotificationMessage):
                logger.debug("Received notification: %s", message.method)
            else:
                logger.warning("Unknown message type: %s", type(message))

        await transport.start(message_handler)

    async def run_http(self, host: str = "127.0.0.1", port: int = 17902,
                        enable_sse: bool = True) -> None:
        """Run MCP server using HTTP transport with SSE support.

        Args:
            host: Host address to bind
            port: Port to listen on
            enable_sse: Enable Server-Sent Events for browser clients
        """
        transport = HTTPTransport(host=host, port=port, enable_sse=enable_sse)

        async def message_handler(message: Any) -> dict[str, Any] | None:
            if isinstance(message, RequestMessage):
                response = await self.handle_request(message)
                return response.to_dict()
            return None

        await transport.start(message_handler)

    def register_tool(
        self,
        name: str,
        description: str = "",
        input_schema: dict | None = None,
    ) -> Callable:
        """Shortcut to register a tool."""
        return self.tools.register(name, description, input_schema)

    def register_resource(
        self,
        uri: str,
        name: str,
        description: str = "",
        content: Any = None,
    ) -> None:
        """Shortcut to register a resource."""
        self.resources.register_static(
            uri=uri,
            name=name,
            description=description,
            content=content,
        )

    def register_prompt(
        self,
        name: str,
        description: str,
        template: str,
        input_variables: list[str] | None = None,
    ) -> None:
        """Shortcut to register a prompt template."""
        self.prompts.register_prompt(
            name=name,
            description=description,
            template=template,
            input_variables=input_variables,
        )

    def add_message_handler(self, handler: Callable) -> None:
        """Add a handler for all incoming messages."""
        self._message_handlers.append(handler)

    async def _notify_message_handlers(self, message: dict) -> None:
        """Notify all registered message handlers."""
        for handler in self._message_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                logger.error("Message handler error: %s", e)

    def set_bridge(self, bridge: Any) -> None:
        """Set the MCP-NEUGI bridge instance."""
        self._bridge = bridge
        logger.info("MCP bridge set to: %s", type(bridge).__name__)

    def set_neugi(self, neugi: Any) -> None:
        """Set the NEUGI instance for subsystem access."""
        self._neugi = neugi
        logger.info("NEUGI instance connected to MCP server")

    def __repr__(self) -> str:
        return f"MCPServer(name={self.name}, version={self.version}, tools={self.tools.count()}, resources={self.resources.count()})"
