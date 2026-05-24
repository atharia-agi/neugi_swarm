"""
MCP Tool Manager - Manages tool registration and execution
===========================================================
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from neugi_swarm_v2.mcp.messages import CallToolResult, ListToolsResult

logger = logging.getLogger(__name__)


@dataclass
class Tool:
    """Represents a registered MCP tool."""
    name: str
    description: str
    input_schema: dict
    handler: Callable
    tags: list[str] | None = None


class ToolManager:
    """Manages tool registration, discovery, and execution."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._aliases: dict[str, str] = {}

    def register(
        self,
        name: str,
        description: str = "",
        input_schema: dict | None = None,
        tags: list[str] | None = None,
    ) -> Callable:
        """Decorator to register a tool function.

        Args:
            name: Unique tool name (e.g., "web_search", "file_read")
            description: Human-readable description
            input_schema: JSON Schema for input validation
            tags: Optional categories for filtering
        """
        if input_schema is None:
            input_schema = {
                "type": "object",
                "properties": {},
                "required": [],
            }

        def decorator(func: Callable) -> Callable:
            self._tools[name] = Tool(
                name=name,
                description=description,
                input_schema=input_schema,
                handler=func,
                tags=tags,
            )
            logger.debug("Registered MCP tool: %s", name)
            return func

        return decorator

    def register_tool(self, tool: Tool) -> None:
        """Register a Tool instance directly."""
        self._tools[tool.name] = tool
        logger.debug("Registered MCP tool: %s", tool.name)

    def register_alias(self, alias: str, target: str) -> None:
        """Register an alias for a tool name."""
        self._aliases[alias] = target
        logger.debug("Registered MCP alias: %s -> %s", alias, target)

    def get_tool(self, name: str) -> Tool | None:
        """Get a tool by name, resolving aliases."""
        resolved = self._aliases.get(name, name)
        return self._tools.get(resolved)

    def list_tools(self, cursor: str | None = None) -> ListToolsResult:
        """List all registered tools with pagination support."""
        tools = [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.input_schema,
                "tags": tool.tags or [],
            }
            for tool in self._tools.values()
        ]
        return ListToolsResult(tools=tools)

    def get_tools(self) -> list[dict]:
        """Get all registered tools as dict list."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.input_schema,
                "tags": tool.tags or [],
            }
            for tool in self._tools.values()
        ]

    async def call_tool(
        self,
        name: str,
        arguments: dict | None = None,
        session_id: str | None = None,
    ) -> CallToolResult:
        """Execute a registered tool with given arguments.

        Args:
            name: Tool name (or alias)
            arguments: Tool input parameters
            session_id: Optional session context

        Returns:
            CallToolResult with output content
        """
        tool = self.get_tool(name)
        if tool is None:
            aliases_matched = [
                (alias, target)
                for alias, target in self._aliases.items()
                if target == name or alias == name
            ]
            suggestion = ""
            if aliases_matched:
                suggestion = f" (did you mean: {aliases_matched[0][1]}?)"
            return CallToolResult(
                content=[{
                    "type": "text",
                    "text": f"Tool '{name}' not found.{suggestion}",
                }],
                is_error=True,
            )

        if arguments is None:
            arguments = {}

        try:
            logger.info("Calling tool: %s (session=%s)", name, session_id)

            # Support both sync and async handlers
            result = tool.handler(**arguments)

            if hasattr(result, "__await__"):
                # It's a coroutine, would need async context
                raise RuntimeError(
                    f"Tool '{name}' is async but called synchronously. "
                    "Use async call_tool method."
                )

            content = self._normalize_result(result)
            logger.info("Tool '%s' completed successfully", name)
            return CallToolResult(content=content, is_error=False)

        except Exception as e:
            logger.error("Tool '%s' execution failed: %s", name, e, exc_info=True)
            return CallToolResult(
                content=[{
                    "type": "text",
                    "text": f"Error executing tool '{name}': {type(e).__name__}: {e}",
                }],
                is_error=True,
            )

    def _normalize_result(self, result: Any) -> list[dict]:
        """Convert tool result to MCP content format."""
        if result is None:
            return [{"type": "text", "text": "null"}]

        if isinstance(result, str):
            return [{"type": "text", "text": result}]

        if isinstance(result, dict):
            return [{
                "type": "text",
                "text": self._format_json(result),
            }]

        if isinstance(result, (list, tuple)):
            return [{
                "type": "text",
                "text": self._format_json(result),
            }]

        if hasattr(result, "__dict__"):
            return [{
                "type": "text",
                "text": self._format_json(result.__dict__),
            }]

        return [{"type": "text", "text": str(result)}]

    @staticmethod
    def _format_json(data: Any, indent: int = 2) -> str:
        """Format data as pretty JSON string."""
        try:
            return json.dumps(data, indent=indent, default=str, ensure_ascii=False)
        except TypeError:
            return str(data)

    def has_tool(self, name: str) -> bool:
        """Check if a tool is registered."""
        return self.get_tool(name) is not None

    def count(self) -> int:
        """Return number of registered tools."""
        return len(self._tools)

    def clear(self) -> None:
        """Remove all registered tools."""
        self._tools.clear()
        self._aliases.clear()
        logger.debug("Cleared all MCP tools")
