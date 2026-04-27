"""
NEUGI v2 MCP Tool Registry
============================

Dynamic tool registration, schema generation, execution, and result formatting
for the Model Context Protocol. Supports text, image, and resource content types
with pagination for large result sets.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from neugi_swarm_v2.mcp.protocol import (
    Tool,
    ToolResult,
    TextContent,
    ImageContent,
    ResourceContent,
    ContentBlock,
    CursorResult,
)

logger = logging.getLogger(__name__)


# -- Tool Call Log Entry -----------------------------------------------------

@dataclass
class ToolCallLog:
    """A single tool call log entry for tracing and auditing.

    Attributes:
        call_id: Unique call identifier.
        tool_name: Name of the tool invoked.
        arguments: Arguments passed to the tool.
        result: Tool result (truncated if large).
        duration_ms: Execution time in milliseconds.
        timestamp: When the call occurred.
        error: Error message if the call failed.
    """

    call_id: str
    tool_name: str
    arguments: dict[str, Any]
    result: Optional[str] = None
    duration_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "call_id": self.call_id,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
        }
        if self.result is not None:
            d["result"] = self.result
        if self.error is not None:
            d["error"] = self.error
        return d


# -- Tool Registration Entry -------------------------------------------------

@dataclass
class ToolEntry:
    """Internal registration entry for a tool.

    Attributes:
        definition: The MCP Tool definition.
        handler: Async or sync callable that executes the tool.
        is_async: Whether the handler is async.
        max_result_chars: Maximum result size before truncation.
    """

    definition: Tool
    handler: Callable[..., Any]
    is_async: bool = False
    max_result_chars: int = 50000


# -- Schema Helpers ----------------------------------------------------------

def build_schema(
    properties: dict[str, dict[str, Any]],
    required: Optional[list[str]] = None,
    description: str = "",
) -> dict[str, Any]:
    """Build a JSON Schema object for tool input.

    Args:
        properties: Property definitions (name -> schema).
        required: List of required property names.
        description: Schema description.

    Returns:
        JSON Schema dict.
    """
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required
    if description:
        schema["description"] = description
    return schema


def string_prop(
    description: str = "",
    enum: Optional[list[str]] = None,
    default: Optional[str] = None,
) -> dict[str, Any]:
    """Create a string property schema."""
    prop: dict[str, Any] = {"type": "string"}
    if description:
        prop["description"] = description
    if enum:
        prop["enum"] = enum
    if default is not None:
        prop["default"] = default
    return prop


def number_prop(
    description: str = "",
    minimum: Optional[float] = None,
    maximum: Optional[float] = None,
    default: Optional[float] = None,
) -> dict[str, Any]:
    """Create a number property schema."""
    prop: dict[str, Any] = {"type": "number"}
    if description:
        prop["description"] = description
    if minimum is not None:
        prop["minimum"] = minimum
    if maximum is not None:
        prop["maximum"] = maximum
    if default is not None:
        prop["default"] = default
    return prop


def integer_prop(
    description: str = "",
    minimum: Optional[int] = None,
    maximum: Optional[int] = None,
    default: Optional[int] = None,
) -> dict[str, Any]:
    """Create an integer property schema."""
    prop: dict[str, Any] = {"type": "integer"}
    if description:
        prop["description"] = description
    if minimum is not None:
        prop["minimum"] = minimum
    if maximum is not None:
        prop["maximum"] = maximum
    if default is not None:
        prop["default"] = default
    return prop


def bool_prop(
    description: str = "",
    default: Optional[bool] = None,
) -> dict[str, Any]:
    """Create a boolean property schema."""
    prop: dict[str, Any] = {"type": "boolean"}
    if description:
        prop["description"] = description
    if default is not None:
        prop["default"] = default
    return prop


def array_prop(
    items: dict[str, Any],
    description: str = "",
    min_items: Optional[int] = None,
    max_items: Optional[int] = None,
) -> dict[str, Any]:
    """Create an array property schema."""
    prop: dict[str, Any] = {"type": "array", "items": items}
    if description:
        prop["description"] = description
    if min_items is not None:
        prop["minItems"] = min_items
    if max_items is not None:
        prop["maxItems"] = max_items
    return prop


def object_prop(
    properties: dict[str, dict[str, Any]],
    description: str = "",
    required: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Create an object property schema."""
    prop: dict[str, Any] = {"type": "object", "properties": properties}
    if description:
        prop["description"] = description
    if required:
        prop["required"] = required
    return prop


# -- Result Helpers ----------------------------------------------------------

def format_result_text(text: str, max_chars: int = 50000) -> str:
    """Truncate text to max_chars with an indicator if truncated."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n\n... [truncated, total {len(text)} chars]"


def paginate_results(
    items: list[Any],
    cursor: Optional[str] = None,
    page_size: int = 50,
) -> CursorResult:
    """Paginate a list of items using cursor-based pagination.

    Args:
        items: Full list of items.
        cursor: Opaque cursor string (index to start from).
        page_size: Items per page.

    Returns:
        CursorResult with page items and optional next cursor.
    """
    start = int(cursor) if cursor else 0
    end = start + page_size
    page = items[start:end]
    next_cursor = str(end) if end < len(items) else None
    return CursorResult(items=page, next_cursor=next_cursor)


# -- Tool Registry -----------------------------------------------------------

class ToolRegistry:
    """Registry for MCP tools with dynamic registration and execution.

    Manages tool definitions, schemas, handlers, call logging, and
    result pagination.

    Usage:
        registry = ToolRegistry()

        @registry.register("greet", "Greet someone by name")
        def greet(name: str) -> str:
            return f"Hello, {name}!"

        # Or manual registration:
        registry.register_tool(
            Tool(name="add", description="Add two numbers", input_schema=...),
            handler=lambda a, b: a + b,
        )

        # Execute:
        result = registry.execute("greet", {"name": "World"})
    """

    def __init__(self, default_max_chars: int = 50000) -> None:
        """Initialize the tool registry.

        Args:
            default_max_chars: Default maximum result size.
        """
        self._tools: dict[str, ToolEntry] = {}
        self._call_log: list[ToolCallLog] = []
        self._max_log_entries: int = 1000
        self._default_max_chars = default_max_chars
        self._on_tool_registered: Optional[Callable[[Tool], None]] = None

    def register(
        self,
        name: str,
        description: str,
        input_schema: Optional[dict[str, Any]] = None,
        annotations: Optional[dict[str, Any]] = None,
        max_result_chars: Optional[int] = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator to register a function as an MCP tool.

        Args:
            name: Tool name.
            description: Tool description.
            input_schema: JSON Schema for arguments (auto-inferred if None).
            annotations: Optional tool annotations.
            max_result_chars: Maximum result size.

        Returns:
            Decorator function.
        """
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            schema = input_schema or self._infer_schema(func)
            tool = Tool(
                name=name,
                description=description,
                input_schema=schema,
                annotations=annotations,
            )
            self.register_tool(tool, func, max_result_chars=max_result_chars)
            return func
        return decorator

    def register_tool(
        self,
        tool: Tool,
        handler: Callable[..., Any],
        is_async: bool = False,
        max_result_chars: Optional[int] = None,
    ) -> None:
        """Register a tool with its handler.

        Args:
            tool: Tool definition.
            handler: Callable that executes the tool.
            is_async: Whether the handler is async.
            max_result_chars: Maximum result size.
        """
        entry = ToolEntry(
            definition=tool,
            handler=handler,
            is_async=is_async,
            max_result_chars=max_result_chars or self._default_max_chars,
        )
        self._tools[tool.name] = entry
        logger.info("Registered tool: %s", tool.name)
        if self._on_tool_registered:
            self._on_tool_registered(tool)

    def unregister(self, name: str) -> bool:
        """Remove a tool from the registry.

        Returns:
            True if the tool was found and removed.
        """
        if name in self._tools:
            del self._tools[name]
            logger.info("Unregistered tool: %s", name)
            return True
        return False

    def get_tool(self, name: str) -> Optional[Tool]:
        """Get a tool definition by name."""
        entry = self._tools.get(name)
        return entry.definition if entry else None

    def list_tools(self) -> list[Tool]:
        """List all registered tools."""
        return [entry.definition for entry in self._tools.values()]

    def has_tool(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools

    def execute(
        self,
        name: str,
        arguments: Optional[dict[str, Any]] = None,
    ) -> ToolResult:
        """Execute a tool by name with the given arguments.

        Args:
            name: Tool name.
            arguments: Tool arguments dict.

        Returns:
            ToolResult with content blocks.

        Raises:
            ValueError: If the tool is not found.
        """
        entry = self._tools.get(name)
        if entry is None:
            return ToolResult.from_text(
                f"Tool '{name}' not found", is_error=True
            )

        call_id = uuid.uuid4().hex[:12]
        start = time.monotonic()
        args = arguments or {}

        log_entry = ToolCallLog(
            call_id=call_id,
            tool_name=name,
            arguments=args,
        )

        try:
            result = entry.handler(**args)
            duration_ms = (time.monotonic() - start) * 1000

            content = self._format_result(result, entry.max_result_chars)
            log_entry.result = self._summarize_result(result)
            log_entry.duration_ms = duration_ms

            self._log_call(log_entry)
            return ToolResult(content=content, is_error=False)

        except Exception as exc:
            duration_ms = (time.monotonic() - start) * 1000
            logger.error("Tool '%s' execution failed: %s", name, exc)
            log_entry.error = str(exc)
            log_entry.duration_ms = duration_ms
            self._log_call(log_entry)
            return ToolResult.from_text(str(exc), is_error=True)

    async def execute_async(
        self,
        name: str,
        arguments: Optional[dict[str, Any]] = None,
    ) -> ToolResult:
        """Execute a tool asynchronously.

        Falls back to sync execution if the handler is not async.
        """
        entry = self._tools.get(name)
        if entry is None:
            return ToolResult.from_text(
                f"Tool '{name}' not found", is_error=True
            )

        call_id = uuid.uuid4().hex[:12]
        start = time.monotonic()
        args = arguments or {}

        log_entry = ToolCallLog(
            call_id=call_id,
            tool_name=name,
            arguments=args,
        )

        try:
            if entry.is_async:
                result = await entry.handler(**args)
            else:
                import asyncio
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, lambda: entry.handler(**args))

            duration_ms = (time.monotonic() - start) * 1000
            content = self._format_result(result, entry.max_result_chars)
            log_entry.result = self._summarize_result(result)
            log_entry.duration_ms = duration_ms

            self._log_call(log_entry)
            return ToolResult(content=content, is_error=False)

        except Exception as exc:
            duration_ms = (time.monotonic() - start) * 1000
            logger.error("Tool '%s' async execution failed: %s", name, exc)
            log_entry.error = str(exc)
            log_entry.duration_ms = duration_ms
            self._log_call(log_entry)
            return ToolResult.from_text(str(exc), is_error=True)

    def get_call_log(
        self,
        tool_name: Optional[str] = None,
        limit: int = 50,
    ) -> list[ToolCallLog]:
        """Get tool call log entries.

        Args:
            tool_name: Filter by tool name.
            limit: Maximum entries to return.

        Returns:
            List of ToolCallLog entries.
        """
        entries = self._call_log
        if tool_name:
            entries = [e for e in entries if e.tool_name == tool_name]
        return entries[-limit:]

    def clear_call_log(self) -> None:
        """Clear the tool call log."""
        self._call_log.clear()

    @property
    def stats(self) -> dict[str, Any]:
        """Get registry statistics."""
        total_calls = len(self._call_log)
        error_calls = sum(1 for e in self._call_log if e.error)
        avg_duration = (
            sum(e.duration_ms for e in self._call_log) / total_calls
            if total_calls > 0
            else 0
        )
        return {
            "registered_tools": len(self._tools),
            "total_calls": total_calls,
            "error_calls": error_calls,
            "avg_duration_ms": round(avg_duration, 2),
        }

    # -- Internal helpers ----------------------------------------------------

    def _format_result(
        self, result: Any, max_chars: int
    ) -> list[ContentBlock]:
        """Format a tool result into content blocks."""
        if result is None:
            return [TextContent(text="")]

        if isinstance(result, str):
            return [TextContent(text=format_result_text(result, max_chars))]

        if isinstance(result, dict):
            if "type" in result and result["type"] == "image":
                return [ImageContent(
                    data=result["data"],
                    mime_type=result.get("mime_type", "image/png"),
                )]
            if "type" in result and result["type"] == "resource":
                return [ResourceContent(resource=result.get("resource", {}))]
            text = json.dumps(result, indent=2, ensure_ascii=False, default=str)
            return [TextContent(text=format_result_text(text, max_chars))]

        if isinstance(result, (list, tuple)):
            text = json.dumps(result, indent=2, ensure_ascii=False, default=str)
            return [TextContent(text=format_result_text(text, max_chars))]

        return [TextContent(text=format_result_text(str(result), max_chars))]

    def _summarize_result(self, result: Any) -> str:
        """Create a short summary of a result for logging."""
        if result is None:
            return "(null)"
        if isinstance(result, str):
            return result[:200] + ("..." if len(result) > 200 else "")
        if isinstance(result, dict):
            keys = ", ".join(result.keys())
            return f"{{{keys}}}"
        if isinstance(result, (list, tuple)):
            return f"[{len(result)} items]"
        return str(result)[:200]

    def _log_call(self, entry: ToolCallLog) -> None:
        """Add an entry to the call log with size limiting."""
        self._call_log.append(entry)
        if len(self._call_log) > self._max_log_entries:
            self._call_log = self._call_log[-self._max_log_entries:]

    def _infer_schema(self, func: Callable[..., Any]) -> dict[str, Any]:
        """Infer a JSON Schema from a function's signature.

        Uses Python's inspect module to extract parameter names,
        type hints, and defaults.
        """
        import inspect

        sig = inspect.signature(func)
        properties: dict[str, dict[str, Any]] = {}
        required: list[str] = []

        type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
        }

        for name, param in sig.parameters.items():
            if name in ("self", "cls"):
                continue

            prop: dict[str, Any] = {}
            if param.annotation != inspect.Parameter.empty:
                prop["type"] = type_map.get(param.annotation, "string")

            if param.default != inspect.Parameter.empty:
                prop["default"] = param.default
            else:
                required.append(name)

            properties[name] = prop

        return build_schema(properties, required=required or None)

    def register_neugi_tools(
        self,
        memory_system: Optional[Any] = None,
        skill_manager: Optional[Any] = None,
        agent_manager: Optional[Any] = None,
        session_manager: Optional[Any] = None,
    ) -> None:
        """Register NEUGI subsystem tools dynamically.

        Args:
            memory_system: MemorySystem instance.
            skill_manager: SkillManager instance.
            agent_manager: AgentManager instance.
            session_manager: SessionManager instance.
        """
        if memory_system:
            self._register_memory_tools(memory_system)
        if skill_manager:
            self._register_skill_tools(skill_manager)
        if agent_manager:
            self._register_agent_tools(agent_manager)
        if session_manager:
            self._register_session_tools(session_manager)

    def _register_memory_tools(self, memory_system: Any) -> None:
        """Register memory-related MCP tools."""

        @self.register(
            "memory_save",
            "Save a new memory entry",
            input_schema=build_schema({
                "content": string_prop("Memory content",),
                "scope": string_prop("Hierarchical scope path"),
                "tier": string_prop("Storage tier", enum=["core", "daily", "working"]),
                "tags": array_prop(string_prop("Tag"), "Categorization labels"),
                "importance": number_prop("Importance [0, 1]", minimum=0, maximum=1),
                "source": string_prop("Origin identifier"),
            }, required=["content"]),
        )
        def memory_save(
            content: str,
            scope: Optional[str] = None,
            tier: str = "daily",
            tags: Optional[list[str]] = None,
            importance: Optional[float] = None,
            source: str = "mcp",
        ) -> str:
            from neugi_swarm_v2.memory import MemoryTier, ScopePath

            tier_map = {
                "core": MemoryTier.CORE,
                "daily": MemoryTier.DAILY,
                "working": MemoryTier.WORKING,
            }
            scope_path = ScopePath.from_string(scope) if scope else ScopePath.global_scope()
            entry = memory_system.save(
                content=content,
                scope=scope_path,
                tier=tier_map.get(tier, MemoryTier.DAILY),
                tags=tags,
                importance=importance,
                source=source,
            )
            return json.dumps({
                "id": entry.id,
                "scope": str(entry.scope),
                "tier": entry.tier.value,
                "importance": entry.importance,
                "tags": entry.tags,
            }, indent=2)

        @self.register(
            "memory_recall",
            "Recall memories matching a query",
            input_schema=build_schema({
                "query": string_prop("Search query"),
                "scope": string_prop("Filter by scope"),
                "tier": string_prop("Filter by tier", enum=["core", "daily", "working"]),
                "tags": array_prop(string_prop("Tag"), "Filter by tags"),
                "limit": integer_prop("Maximum results", minimum=1, maximum=100, default=20),
            }, required=["query"]),
        )
        def memory_recall(
            query: str,
            scope: Optional[str] = None,
            tier: Optional[str] = None,
            tags: Optional[list[str]] = None,
            limit: int = 20,
        ) -> str:
            from neugi_swarm_v2.memory import MemoryTier, ScopePath

            scope_path = ScopePath.from_string(scope) if scope else None
            tier_enum = MemoryTier(tier) if tier else None
            results = memory_system.recall(
                query=query,
                scope=scope_path,
                tier=tier_enum,
                tags=tags,
                limit=limit,
            )
            items = []
            for entry, score, _ in results:
                items.append({
                    "id": entry.id,
                    "content": entry.content[:500],
                    "scope": str(entry.scope),
                    "tier": entry.tier.value,
                    "score": round(score, 4),
                    "importance": entry.importance,
                    "tags": entry.tags,
                    "created_at": entry.created_at.isoformat(),
                })
            return json.dumps(items, indent=2, ensure_ascii=False)

        @self.register(
            "memory_search",
            "Full-text search memories",
            input_schema=build_schema({
                "query": string_prop("Search text"),
                "limit": integer_prop("Maximum results", minimum=1, maximum=100, default=20),
            }, required=["query"]),
        )
        def memory_search(query: str, limit: int = 20) -> str:
            results = memory_system.search(query=query, limit=limit)
            items = [
                {
                    "id": e.id,
                    "content": e.content[:500],
                    "scope": str(e.scope),
                    "tier": e.tier.value,
                    "tags": e.tags,
                }
                for e in results
            ]
            return json.dumps(items, indent=2, ensure_ascii=False)

        @self.register(
            "memory_stats",
            "Get memory system statistics",
        )
        def memory_stats() -> str:
            return json.dumps(memory_system.stats, indent=2)

    def _register_skill_tools(self, skill_manager: Any) -> None:
        """Register skill-related MCP tools."""

        @self.register(
            "skills_list",
            "List all loaded skills",
            input_schema=build_schema({
                "tier": string_prop("Filter by tier"),
                "agent": string_prop("Filter by agent"),
            }),
        )
        def skills_list(
            tier: Optional[str] = None,
            agent: Optional[str] = None,
        ) -> str:
            if tier:
                from neugi_swarm_v2.skills import SkillTier
                tier_enum = SkillTier[tier.upper()]
                skills = skill_manager.get_by_tier(tier_enum)
            elif agent:
                skills = skill_manager.get_by_agent(agent)
            else:
                skills = skill_manager.get_enabled()

            items = [
                {
                    "name": s.name,
                    "description": s.frontmatter.description,
                    "tier": s.tier.value,
                    "tags": s.frontmatter.tags,
                    "enabled": s.is_enabled,
                }
                for s in skills
            ]
            return json.dumps(items, indent=2, ensure_ascii=False)

        @self.register(
            "skills_match",
            "Match skills to a natural language query",
            input_schema=build_schema({
                "query": string_prop("Natural language query"),
                "top_n": integer_prop("Maximum results", minimum=1, maximum=20, default=5),
                "agent": string_prop("Filter by agent"),
            }, required=["query"]),
        )
        def skills_match(
            query: str,
            top_n: int = 5,
            agent: Optional[str] = None,
        ) -> str:
            results = skill_manager.match(query, top_n=top_n, agent_name=agent)
            items = [
                {
                    "skill": r.skill.name,
                    "score": round(r.score, 4),
                    "matched_by": r.matched_by,
                    "description": r.skill.frontmatter.description,
                }
                for r in results
            ]
            return json.dumps(items, indent=2, ensure_ascii=False)

        @self.register(
            "skills_stats",
            "Get skill manager statistics",
        )
        def skills_stats() -> str:
            stats = skill_manager.get_stats()
            return json.dumps({
                "total_loaded": stats.total_loaded,
                "enabled": stats.enabled,
                "disabled": stats.disabled,
                "errored": stats.errored,
                "total_token_cost": stats.total_token_cost,
                "tier_counts": stats.tier_counts,
            }, indent=2)

    def _register_agent_tools(self, agent_manager: Any) -> None:
        """Register agent-related MCP tools."""

        @self.register(
            "agents_list",
            "List all registered agents",
        )
        def agents_list() -> str:
            agents = agent_manager.list_agents()
            items = [
                {
                    "id": a.id,
                    "name": a.name,
                    "role": a.role.value,
                    "level": a.level,
                    "status": a.status.value,
                    "xp": a.xp,
                }
                for a in agents
            ]
            return json.dumps(items, indent=2)

        @self.register(
            "agent_execute",
            "Execute a task via an agent",
            input_schema=build_schema({
                "agent_name": string_prop("Agent name"),
                "task": string_prop("Task description"),
            }, required=["agent_name", "task"]),
        )
        def agent_execute(agent_name: str, task: str) -> str:
            agent = agent_manager.get(agent_name)
            if agent is None:
                return json.dumps({"error": f"Agent '{agent_name}' not found"})
            result = agent.execute(task)
            return json.dumps(result, indent=2, default=str)

    def _register_session_tools(self, session_manager: Any) -> None:
        """Register session-related MCP tools."""

        @self.register(
            "sessions_list",
            "List active sessions",
        )
        def sessions_list() -> str:
            sessions = session_manager.list_sessions()
            items = [
                {
                    "id": s.id,
                    "state": s.state.value if hasattr(s.state, "value") else str(s.state),
                    "created_at": s.created_at if hasattr(s, "created_at") else None,
                }
                for s in sessions
            ]
            return json.dumps(items, indent=2, default=str)
