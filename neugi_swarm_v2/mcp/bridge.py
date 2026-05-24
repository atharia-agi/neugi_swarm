"""
MCP-NEUGI Bridge - Connects MCP Server to Live NEUGI Subsystems
================================================================

Provides the integration layer between the Model Context Protocol server
and NEUGI's core subsystems: EventBus, ToolExecutor, PluginRegistry,
MemorySystem, and A2A protocol.

This module ensures zero core modifications — all integration happens
through the existing plugin and event bus architecture.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from neugi_swarm_v2.mcp.mcp_server import MCPServer
from neugi_swarm_v2.mcp.messages import (
    RequestMessage,
)

logger = logging.getLogger(__name__)


class MCPBridge:
    """Bridge between MCP Server and NEUGI subsystems.

    Wires up:
    - EventBus for MCP call telemetry
    - ToolExecutor/ToolRegistry for tool execution
    - PluginRegistry for auto-discovery of plugin tools
    - MemorySystem for resource access
    - A2AProtocol for inter-agent tool routing
    """

    def __init__(self, server: MCPServer, neugi: Any = None):
        """Initialize the bridge.

        Args:
            server: MCPServer instance to bridge
            neugi: NeugiSwarmV2 instance (optional, can be set later)
        """
        self.server = server
        self._neugi = neugi
        self._connected = False
        self._event_bus = None
        self._tool_executor = None
        self._tool_registry = None
        self._plugin_registry = None
        self._memory = None
        self._a2a = None
        self._register_bridge_tools()

    @property
    def neugi(self) -> Any:
        """Get the NEUGI instance."""
        return self._neugi

    @neugi.setter
    def neugi(self, value: Any) -> None:
        """Set the NEUGI instance."""
        self._neugi = value

    def connect(self, neugi: Any = None) -> None:
        """Connect the bridge to NEUGI subsystems.

        Args:
            neugi: NeugiSwarmV2 instance. Uses existing if None.
        """
        if neugi is not None:
            self._neugi = neugi

        if self._neugi is None:
            logger.warning("Cannot connect bridge: no NEUGI instance available")
            return

        try:
            # Wire EventBus
            from neugi_swarm_v2.observability.event_bus import get_event_bus
            self._event_bus = get_event_bus()
            self._event_bus.subscribe(
                "tool_execution_success", self._on_neugi_tool_success
            )
            self._event_bus.subscribe(
                "tool_execution_failure", self._on_neugi_tool_failure
            )
            logger.debug("EventBus connected")

            # Wire ToolExecutor
            from tools.tool_executor import ToolExecutor
            budget_tracker = None
            try:
                from governance.budget import BudgetTracker
                governance_db = getattr(self._neugi, "config", None)
                if governance_db and hasattr(governance_db, "data_dir"):
                    db_path = str(governance_db.data_dir / "governance.db")
                else:
                    db_path = "governance.db"
                budget_tracker = BudgetTracker(db_path=db_path)
            except Exception as e:
                logger.debug("BudgetTracker not available: %s", e)
            self._tool_executor = ToolExecutor(
                registry=self._neugi.tool_registry if hasattr(self._neugi, "tool_registry") else None,
                budget_tracker=budget_tracker,
            )
            logger.debug("ToolExecutor connected")

            # Wire ToolRegistry
            from tools.tool_registry import ToolRegistry
            # Use the shared registry if available on the neugi instance
            if hasattr(self._neugi, "tool_registry"):
                self._tool_registry = self._neugi.tool_registry
            else:
                self._tool_registry = ToolRegistry()
            logger.debug("ToolRegistry connected (%d tools)", self._tool_registry.get_tool_count())

            # Wire PluginRegistry
            from plugins.plugin_registry import PluginRegistry
            self._plugin_registry = PluginRegistry()
            logger.debug("PluginRegistry connected")

            # Wire MemorySystem
            self._memory = getattr(self._neugi, "memory", None)
            if self._memory:
                logger.debug("MemorySystem connected")

                # Register memory resources in MCP
                self._register_memory_resources()

            # Wire A2A Protocol
            from a2a import A2AProtocol
            if hasattr(self._neugi, "a2a") and isinstance(self._neugi.a2a, A2AProtocol):
                self._a2a = self._neugi.a2a
                logger.debug("A2A protocol connected")

            # Auto-register plugin tools
            self._auto_register_plugin_tools()

            # Register bridge-specific tools
            self._register_bridge_tools()

            self._connected = True
            logger.info("MCP-NEUGI bridge connected successfully")

        except Exception as e:
            logger.error("Failed to connect MCP bridge: %s", e, exc_info=True)
            raise

    def disconnect(self) -> None:
        """Disconnect the bridge from NEUGI subsystems."""
        if self._event_bus:
            try:
                self._event_bus.unsubscribe(
                    "tool_execution_success", self._on_neugi_tool_success
                )
                self._event_bus.unsubscribe(
                    "tool_execution_failure", self._on_neugi_tool_failure
                )
            except Exception as e:
                logger.debug("Event bus unsubscribe (non-critical): %s", e)

        self._connected = False
        logger.info("MCP-NEUGI bridge disconnected")

    @property
    def is_connected(self) -> bool:
        """Whether the bridge is currently connected."""
        return self._connected

    def _on_neugi_tool_success(self, event: Any) -> None:
        """Forward NEUGI tool success events to MCP event bus."""
        try:
            self.server._notify_message_handlers({
                "type": "tool_execution_success",
                "data": event.payload or {},
                "timestamp": datetime.now().isoformat(),
            })
        except Exception:
            logger.warning("Failed to forward tool success event", exc_info=True)

    def _on_neugi_tool_failure(self, event: Any) -> None:
        """Forward NEUGI tool failure events to MCP event bus."""
        try:
            self.server._notify_message_handlers({
                "type": "tool_execution_failure",
                "data": event.payload or {},
                "timestamp": datetime.now().isoformat(),
            })
        except Exception:
            logger.warning("Failed to forward tool failure event", exc_info=True)

    def _register_memory_resources(self) -> None:
        """Register NEUGI memory system as MCP resources."""
        if not self._memory:
            return

        # Register core memory as a dynamic resource
        def memory_loader(uri: str) -> str:
            try:
                parts = uri.replace("neugi://memory/", "").split("/")
                search_key = parts[-1] if parts else "recent"
                entries = self._memory.search(search_key, limit=10)
                return json.dumps([
                    {
                        "key": e.key,
                        "value": e.value,
                        "timestamp": e.timestamp.isoformat() if hasattr(e, "timestamp") else None,
                        "category": getattr(e, "category", None),
                    }
                    for e in entries
                ], indent=2, default=str)
            except Exception as e:
                return json.dumps({"error": str(e)})

        self.server.resources.register_dynamic("neugi://memory", memory_loader)

        # Register memory stats resource
        self.server.resources.register_static(
            uri="neugi://memory/stats",
            name="Memory Statistics",
            description="Current memory system statistics",
            mimeType="application/json",
            content=lambda: json.dumps({
                "total_entries": self._memory.stats().get("total", 0) if hasattr(self._memory, "stats") else 0,
                "status": "active",
            }, indent=2),
        )

        # Register identity/soul files as resources
        try:
            soul_path = self._neugi.neugi_dir / "soul"
            if soul_path.exists():
                for soul_file in soul_path.glob("*.md"):
                    safe_name = soul_file.stem.replace(" ", "_")
                    self.server.resources.register_file(
                        file_path=str(soul_file),
                        uri=f"neugi://soul/{safe_name}",
                        name=f"SOUL: {soul_file.stem}",
                    )
        except Exception:
            logger.debug("No soul files to register (optional)")

    def _auto_register_plugin_tools(self) -> None:
        """Auto-register tools from loaded NEUGI plugins into MCP server."""
        if not self._plugin_registry or not self._neugi:
            return

        # Get plugin manager from neugi
        plugin_manager = getattr(self._neugi, "plugin_manager", None)
        if not plugin_manager:
            return

        registered_count = 0
        for plugin_name, plugin_info in plugin_manager._plugins.items():
            plugin_instance = plugin_info.get("instance")
            if not plugin_instance:
                continue

            ctx = plugin_info.get("context")
            if not ctx:
                continue

            # Register each plugin tool with the MCP server
            for tool_name, handler in ctx.tools.items():
                try:
                    # Try to determine schema from plugin
                    description = getattr(handler, "__doc__", f"Plugin tool: {tool_name}")

                    # Check for param info in the handler
                    import inspect
                    sig = inspect.signature(handler)
                    params = {}
                    required = []
                    for pname, p in sig.parameters.items():
                        if p.default is inspect.Parameter.empty:
                            required.append(pname)
                            params[pname] = {"type": "Any", "description": pname}
                        else:
                            params[pname] = {
                                "type": "Any",
                                "description": pname,
                                "default": str(p.default),
                            }

                    # Register as MCP tool
                    @self.server.tools.register(
                        name=f"plugin:{plugin_name}:{tool_name}",
                        description=f"[{plugin_name}] {description}",
                        input_schema={
                            "type": "object",
                            "properties": params,
                            "required": required,
                        },
                    )
                    def make_wrapper(h: Callable) -> Callable:
                        def wrapper(**kwargs: Any) -> Any:
                            return h(**kwargs)
                        return wrapper

                    # Actually register the function
                    self.server.tools._tools[f"plugin:{plugin_name}:{tool_name}"].handler = handler
                    registered_count += 1
                    logger.debug(
                        "Auto-registered plugin tool: plugin:%s:%s", plugin_name, tool_name
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to auto-register plugin tool %s:%s: %s",
                        plugin_name, tool_name, e
                    )

        if registered_count:
            logger.info(
                "Auto-registered %d plugin tools to MCP server", registered_count
            )

    def _register_bridge_tools(self) -> None:
        """Register NEUGI bridge system tools on the MCP server."""

        @self.server.tools.register(
            name="neugi_status",
            description="Get NEUGI Swarm system status and subsystem health",
            input_schema={
                "type": "object",
                "properties": {},
            },
        )
        async def neugi_status() -> dict:
            """Get comprehensive NEUGI system status."""
            status = {
                "version": getattr(self._neugi, "__version__", "unknown"),
                "bridge_connected": self._connected,
                "mcp_tools_count": self.server.tools.count(),
                "mcp_resources_count": self.server.resources.count(),
                "mcp_prompts_count": self.server.prompts.count(),
                "event_bus_history": len(self._event_bus._history) if self._event_bus else 0,
            }

            if self._memory:
                try:
                    status["memory"] = {
                        "status": "active",
                        "entries": self._memory.stats().get("total", "unknown"),
                    }
                except Exception:
                    status["memory"] = {"status": "initializing"}

            if self._a2a:
                try:
                    mesh = self._a2a.get_mesh_status()
                    status["a2a_mesh"] = mesh
                except Exception:
                    status["a2a_mesh"] = {"status": "not_available"}

            if self._tool_registry:
                try:
                    status["tool_registry"] = {
                        "total_tools": self._tool_registry.get_tool_count(),
                        "categories": self._tool_registry.get_category_summary(),
                    }
                except Exception:
                    status["tool_registry"] = {"status": "not_available"}

            return status

        @self.server.tools.register(
            name="neugi_memory_search",
            description="Search NEUGI memory system",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default: 10)",
                    },
                },
                "required": ["query"],
            },
        )
        async def neugi_memory_search(query: str, limit: int = 10) -> dict:
            """Search the NEUGI memory system."""
            if not self._memory:
                return {"error": "Memory system not available"}
            try:
                entries = self._memory.search(query, limit=limit)
                return {
                    "results": [
                        {
                            "key": e.key,
                            "value": e.value,
                            "timestamp": e.timestamp.isoformat() if hasattr(e, "timestamp") else None,
                            "score": getattr(e, "score", None),
                        }
                        for e in entries
                    ],
                    "count": len(entries),
                }
            except Exception as e:
                return {"error": str(e)}

        @self.server.tools.register(
            name="neugi_event_history",
            description="Get observable event history from NEUGI event bus",
            input_schema={
                "type": "object",
                "properties": {
                    "event_name": {
                        "type": "string",
                        "description": "Filter by event name (optional)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max events to return (default: 50)",
                    },
                },
            },
        )
        async def neugi_event_history(event_name: str = "", limit: int = 50) -> dict:
            """Get event history from the NEUGI event bus."""
            if not self._event_bus:
                return {"error": "Event bus not available"}
            try:
                events = self._event_bus.get_history(
                    event_name if event_name else None
                )
                return {
                    "events": [
                        {
                            "name": e.name,
                            "payload": e.payload,
                            "source": e.source,
                            "timestamp": e.timestamp.isoformat(),
                        }
                        for e in events[-limit:]
                    ],
                    "total": len(events),
                }
            except Exception as e:
                return {"error": str(e)}

        @self.server.tools.register(
            name="neugi_plugin_list",
            description="List all loaded NEUGI plugins",
            input_schema={
                "type": "object",
                "properties": {},
            },
        )
        async def neugi_plugin_list() -> dict:
            """List all loaded NEUGI plugins."""
            if not self._plugin_registry:
                return {"plugins": [], "note": "Plugin registry not available"}
            try:
                return {
                    "plugins": [
                        {
                            "name": name,
                            "version": info.get("version", "unknown"),
                            "description": info.get("description", ""),
                            "status": info.get("status", "unknown"),
                        }
                        for name, info in self._plugin_registry._plugins.items()
                    ]
                }
            except Exception as e:
                return {"error": str(e)}

        @self.server.tools.register(
            name="neugi_execute_tool",
            description="Execute a NEUGI tool through the MCP bridge with full security pipeline",
            input_schema={
                "type": "object",
                "properties": {
                    "tool_name": {
                        "type": "string",
                        "description": "Name of the NEUGI tool to execute",
                    },
                    "parameters": {
                        "type": "object",
                        "description": "Tool parameters as key-value pairs",
                    },
                    "trace_id": {
                        "type": "string",
                        "description": "Optional trace ID for execution tracking",
                    },
                },
                "required": ["tool_name"],
            },
        )
        async def neugi_execute_tool(
            tool_name: str, parameters: dict = None, trace_id: str = None
        ) -> dict:
            """Execute a NEUGI tool through the MCP bridge with full security pipeline."""
            if not self._tool_executor:
                return {"error": "Tool executor not available"}

            try:
                params = parameters or {}
                # Publish MCP call start event
                if self._event_bus:
                    self._event_bus.publish(
                        "mcp_tool_call_start",
                        {
                            "tool_name": tool_name,
                            "params": params,
                            "trace_id": trace_id,
                            "source": "mcp_client",
                        },
                        source="mcp_bridge",
                    )

                # Execute through NEUGI's tool executor (includes all security layers)
                result = self._tool_executor.execute(
                    tool_name, trace_id=trace_id, **params
                )

                return {
                    "success": result.success,
                    "result": result.result,
                    "error": result.error,
                    "latency_ms": result.latency_ms,
                    "cached": result.cached,
                    "retries": result.retries,
                    "trace_id": trace_id,
                }

            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "trace_id": trace_id,
                }

        @self.server.tools.register(
            name="neugi_soul_read",
            description="Read NEUGI soul/identity files",
            input_schema={
                "type": "object",
                "properties": {
                    "file": {
                        "type": "string",
                        "description": "Soul file name (e.g., SOUL.md, MEMORY.md). Omit for list.",
                    },
                },
            },
        )
        async def neugi_soul_read(file: str = "") -> dict:
            """Read NEUGI soul/identity files."""
            if not self._neugi or not hasattr(self._neugi, "soul"):
                return {"error": "Soul engine not available"}

            try:
                if file:
                    soul = self._neugi.soul
                    if hasattr(soul, "get_file_content"):
                        content = soul.get_file_content(file)
                    else:
                        soul_path = self._neugi.neugi_dir / "soul" / file
                        if soul_path.exists():
                            content = soul_path.read_text(encoding="utf-8")
                        else:
                            return {"error": f"Soul file not found: {file}"}
                    return {"file": file, "content": content}
                else:
                    # List available soul files
                    soul_path = self._neugi.neugi_dir / "soul"
                    files = []
                    if soul_path.exists():
                        for f in soul_path.glob("*.md"):
                            files.append(f.name)
                    return {"files": files}
            except Exception as e:
                return {"error": str(e)}

        @self.server.tools.register(
            name="neugi_a2a_mesh_status",
            description="Get the A2A agent mesh status for inter-agent communication",
            input_schema={
                "type": "object",
                "properties": {},
            },
        )
        async def neugi_a2a_mesh_status() -> dict:
            """Get A2A agent mesh status."""
            if not self._a2a:
                return {"error": "A2A protocol not available", "available": False}
            try:
                return self._a2a.get_mesh_status()
            except Exception as e:
                return {"error": str(e), "available": False}

        logger.info("Bridge tools registered on MCP server")

    def _on_mcp_tool_call(self, request: RequestMessage) -> None:
        """Handle MCP tool calls with NEUGI event bus integration."""
        if self._event_bus:
            method = request.method
            params = request.params or {}
            self._event_bus.publish(
                "mcp_call",
                {
                    "method": method,
                    "params": params,
                    "id": str(request.id),
                },
                source="mcp_server",
            )


def create_bridge(
    server: MCPServer,
    neugi: Any,
    *,
    register_plugin_tools: bool = True,
    register_memory_resources: bool = True,
    forward_events: bool = True,
) -> MCPBridge:
    """Convenience function to create and connect an MCP bridge.

    Args:
        server: MCPServer instance
        neugi: NeugiSwarmV2 instance
        register_plugin_tools: Auto-register plugin tools on MCP
        register_memory_resources: Register NEUGI memory as MCP resources
        forward_events: Forward NEUGI events to MCP

    Returns:
        Connected MCPBridge instance
    """
    bridge = MCPBridge(server, neugi)
    bridge.connect(neugi)
    return bridge
