"""
Central tool registry for NEUGI v2.

Provides tool registration with typed schemas, categorization, discovery,
versioning, allowlists, usage statistics, and health monitoring.
"""

import time
import threading
import logging
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    Union,
)
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class ToolCategory(str, Enum):
    """Categories for tool classification."""

    WEB = "web"
    CODE = "code"
    FILE = "file"
    DATA = "data"
    COMM = "comm"
    SYSTEM = "system"
    AI = "ai"
    GIT = "git"
    DOCKER = "docker"
    SECURITY = "security"
    COMPOSED = "composed"
    GENERATED = "generated"


@dataclass
class ToolSchema:
    """Typed schema describing a tool's interface."""

    name: str
    description: str
    category: ToolCategory
    parameters: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    return_type: str = "Any"
    required_params: List[str] = field(default_factory=list)
    optional_params: Dict[str, Any] = field(default_factory=dict)
    version: str = "1.0.0"
    deprecated: bool = False
    deprecation_message: str = ""
    tags: List[str] = field(default_factory=list)
    timeout_seconds: float = 30.0
    rate_limit_per_minute: int = 60
    cacheable: bool = True
    side_effects: bool = False

    def validate_params(self, kwargs: Dict[str, Any]) -> List[str]:
        """Validate parameters against schema. Returns list of errors."""
        errors = []
        for param in self.required_params:
            if param not in kwargs:
                errors.append(f"Missing required parameter: {param}")
        for param_name, param_value in kwargs.items():
            if param_name not in self.parameters:
                if param_name not in self.optional_params:
                    errors.append(f"Unknown parameter: {param_name}")
                continue
            expected_type = self.parameters[param_name].get("type", "Any")
            if expected_type != "Any":
                type_map = {
                    "str": str,
                    "int": int,
                    "float": float,
                    "bool": bool,
                    "list": list,
                    "dict": dict,
                }
                py_type = type_map.get(expected_type)
                if py_type and not isinstance(param_value, py_type):
                    errors.append(
                        f"Parameter {param_name} expected {expected_type}, "
                        f"got {type(param_value).__name__}"
                    )
        return errors


@dataclass
class ToolMetadata:
    """Metadata about a registered tool."""

    schema: ToolSchema
    func: Callable
    registered_at: float = field(default_factory=time.time)
    author: str = "system"
    source: str = "builtin"


@dataclass
class ToolStats:
    """Usage statistics for a tool."""

    name: str
    call_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    total_latency_ms: float = 0.0
    last_called_at: Optional[float] = None
    last_error: Optional[str] = None
    avg_latency_ms: float = 0.0
    success_rate: float = 1.0

    def record_call(self, latency_ms: float, success: bool, error: Optional[str] = None):
        """Record a tool call."""
        self.call_count += 1
        self.total_latency_ms += latency_ms
        self.last_called_at = time.time()
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
            self.last_error = error
        self.avg_latency_ms = self.total_latency_ms / self.call_count
        self.success_rate = (
            self.success_count / self.call_count if self.call_count > 0 else 1.0
        )


@dataclass
class ToolHealth:
    """Health status of a tool."""

    name: str
    status: str = "healthy"
    last_check: float = field(default_factory=time.time)
    consecutive_failures: int = 0
    last_error: Optional[str] = None
    uptime_ratio: float = 1.0
    circuit_open: bool = False

    def record_success(self):
        """Record a successful call."""
        self.consecutive_failures = 0
        self.status = "healthy"
        self.last_check = time.time()

    def record_failure(self, error: str):
        """Record a failed call."""
        self.consecutive_failures += 1
        self.last_error = error
        self.last_check = time.time()
        if self.consecutive_failures >= 5:
            self.status = "degraded"
        if self.consecutive_failures >= 10:
            self.status = "unhealthy"


class ToolNotFoundError(Exception):
    """Raised when a tool is not found in the registry."""

    pass


class ToolAlreadyRegisteredError(Exception):
    """Raised when attempting to register a tool that already exists."""

    pass


class ToolDeprecatedError(Exception):
    """Raised when attempting to call a deprecated tool."""

    pass


class ToolRegistry:
    """
    Central registry for all tools in the NEUGI v2 system.

    Provides registration, discovery, versioning, allowlists,
    usage statistics, and health monitoring.

    Example:
        >>> registry = ToolRegistry()
        >>> registry.register_tool(
        ...     "greet",
        ...     lambda name: f"Hello, {name}!",
        ...     category=ToolCategory.SYSTEM,
        ...     parameters={"name": {"type": "str", "description": "Name to greet"}},
        ...     required_params=["name"],
        ... )
        >>> tool = registry.get_tool("greet")
        >>> result = tool.func("World")
    """

    def __init__(self):
        self._tools: Dict[str, ToolMetadata] = {}
        self._stats: Dict[str, ToolStats] = {}
        self._health: Dict[str, ToolHealth] = {}
        self._allowlists: Dict[str, Set[str]] = {}
        self._lock = threading.RLock()
        self._categories: Dict[ToolCategory, Set[str]] = {
            cat: set() for cat in ToolCategory
        }

    def register_tool(
        self,
        name: str,
        func: Callable,
        category: ToolCategory,
        description: str = "",
        parameters: Optional[Dict[str, Dict[str, Any]]] = None,
        return_type: str = "Any",
        required_params: Optional[List[str]] = None,
        optional_params: Optional[Dict[str, Any]] = None,
        version: str = "1.0.0",
        deprecated: bool = False,
        deprecation_message: str = "",
        tags: Optional[List[str]] = None,
        timeout_seconds: float = 30.0,
        rate_limit_per_minute: int = 60,
        cacheable: bool = True,
        side_effects: bool = False,
        author: str = "system",
        source: str = "builtin",
    ) -> ToolSchema:
        """
        Register a tool in the registry.

        Args:
            name: Unique tool name.
            func: Callable implementing the tool.
            category: Tool category.
            description: Human-readable description.
            parameters: Parameter schema dict.
            return_type: Expected return type string.
            required_params: List of required parameter names.
            optional_params: Default values for optional parameters.
            version: Tool version string.
            deprecated: Whether the tool is deprecated.
            deprecation_message: Message shown when calling deprecated tools.
            tags: Search tags.
            timeout_seconds: Default timeout for execution.
            rate_limit_per_minute: Max calls per minute.
            cacheable: Whether results can be cached.
            side_effects: Whether the tool has side effects.
            author: Tool author.
            source: Tool source (builtin, generated, composed, etc.).

        Returns:
            The created ToolSchema.

        Raises:
            ToolAlreadyRegisteredError: If tool name already exists.
        """
        with self._lock:
            if name in self._tools:
                raise ToolAlreadyRegisteredError(f"Tool '{name}' is already registered")

            schema = ToolSchema(
                name=name,
                description=description or func.__doc__ or name,
                category=category,
                parameters=parameters or {},
                return_type=return_type,
                required_params=required_params or [],
                optional_params=optional_params or {},
                version=version,
                deprecated=deprecated,
                deprecation_message=deprecation_message,
                tags=tags or [],
                timeout_seconds=timeout_seconds,
                rate_limit_per_minute=rate_limit_per_minute,
                cacheable=cacheable,
                side_effects=side_effects,
            )

            metadata = ToolMetadata(
                schema=schema,
                func=func,
                author=author,
                source=source,
            )

            self._tools[name] = metadata
            self._stats[name] = ToolStats(name=name)
            self._health[name] = ToolHealth(name=name)
            self._categories[category].add(name)

            logger.info(f"Registered tool '{name}' in category '{category.value}'")
            return schema

    def unregister_tool(self, name: str) -> bool:
        """
        Remove a tool from the registry.

        Args:
            name: Tool name to remove.

        Returns:
            True if tool was removed, False if not found.
        """
        with self._lock:
            if name not in self._tools:
                return False
            metadata = self._tools.pop(name)
            self._stats.pop(name, None)
            self._health.pop(name, None)
            self._categories[metadata.schema.category].discard(name)
            logger.info(f"Unregistered tool '{name}'")
            return True

    def get_tool(self, name: str) -> ToolMetadata:
        """
        Get a tool by name.

        Args:
            name: Tool name.

        Returns:
            ToolMetadata for the tool.

        Raises:
            ToolNotFoundError: If tool doesn't exist.
        """
        with self._lock:
            if name not in self._tools:
                raise ToolNotFoundError(f"Tool '{name}' not found")
            return self._tools[name]

    def get_tool_func(self, name: str) -> Callable:
        """
        Get the callable for a tool.

        Args:
            name: Tool name.

        Returns:
            The tool's callable function.

        Raises:
            ToolNotFoundError: If tool doesn't exist.
        """
        return self.get_tool(name).func

    def get_schema(self, name: str) -> ToolSchema:
        """
        Get the schema for a tool.

        Args:
            name: Tool name.

        Returns:
            ToolSchema for the tool.

        Raises:
            ToolNotFoundError: If tool doesn't exist.
        """
        return self.get_tool(name).schema

    def list_tools(
        self,
        category: Optional[ToolCategory] = None,
        tags: Optional[List[str]] = None,
        include_deprecated: bool = False,
    ) -> List[ToolSchema]:
        """
        List registered tools with optional filters.

        Args:
            category: Filter by category.
            tags: Filter by tags (must match all).
            include_deprecated: Whether to include deprecated tools.

        Returns:
            List of matching ToolSchema objects.
        """
        with self._lock:
            tools = list(self._tools.values())
            if category:
                tools = [t for t in tools if t.schema.category == category]
            if not include_deprecated:
                tools = [t for t in tools if not t.schema.deprecated]
            if tags:
                tools = [
                    t
                    for t in tools
                    if all(tag in t.schema.tags for tag in tags)
                ]
            return [t.schema for t in tools]

    def search_tools(self, query: str) -> List[ToolSchema]:
        """
        Search tools by name, description, or tags.

        Args:
            query: Search query string.

        Returns:
            List of matching ToolSchema objects, sorted by relevance.
        """
        query_lower = query.lower()
        results = []
        with self._lock:
            for tool in self._tools.values():
                score = 0
                if query_lower in tool.schema.name.lower():
                    score += 10
                if query_lower in tool.schema.description.lower():
                    score += 5
                for tag in tool.schema.tags:
                    if query_lower in tag.lower():
                        score += 3
                if score > 0:
                    results.append((score, tool.schema))
        results.sort(key=lambda x: x[0], reverse=True)
        return [schema for _, schema in results]

    def set_agent_allowlist(self, agent_id: str, tool_names: Set[str]):
        """
        Set the allowlist of tools for a specific agent.

        Args:
            agent_id: Agent identifier.
            tool_names: Set of allowed tool names.
        """
        with self._lock:
            self._allowlists[agent_id] = tool_names

    def get_agent_allowlist(self, agent_id: str) -> Optional[Set[str]]:
        """
        Get the allowlist for an agent.

        Args:
            agent_id: Agent identifier.

        Returns:
            Set of allowed tool names, or None if no allowlist set.
        """
        with self._lock:
            return self._allowlists.get(agent_id)

    def is_tool_allowed(self, agent_id: str, tool_name: str) -> bool:
        """
        Check if a tool is allowed for an agent.

        Args:
            agent_id: Agent identifier.
            tool_name: Tool name to check.

        Returns:
            True if allowed, False otherwise.
        """
        with self._lock:
            allowlist = self._allowlists.get(agent_id)
            if allowlist is None:
                return True
            return tool_name in allowlist

    def record_stats(
        self, name: str, latency_ms: float, success: bool, error: Optional[str] = None
    ):
        """
        Record usage statistics for a tool call.

        Args:
            name: Tool name.
            latency_ms: Call latency in milliseconds.
            success: Whether the call succeeded.
            error: Error message if failed.
        """
        with self._lock:
            if name in self._stats:
                self._stats[name].record_call(latency_ms, success, error)
            if name in self._health:
                if success:
                    self._health[name].record_success()
                else:
                    self._health[name].record_failure(error or "Unknown error")

    def get_stats(self, name: str) -> Optional[ToolStats]:
        """
        Get usage statistics for a tool.

        Args:
            name: Tool name.

        Returns:
            ToolStats or None if not found.
        """
        with self._lock:
            return self._stats.get(name)

    def get_health(self, name: str) -> Optional[ToolHealth]:
        """
        Get health status for a tool.

        Args:
            name: Tool name.

        Returns:
            ToolHealth or None if not found.
        """
        with self._lock:
            return self._health.get(name)

    def get_all_health(self) -> Dict[str, ToolHealth]:
        """
        Get health status for all tools.

        Returns:
            Dict mapping tool names to ToolHealth.
        """
        with self._lock:
            return dict(self._health)

    def get_tools_by_category(self, category: ToolCategory) -> List[ToolSchema]:
        """
        Get all tools in a category.

        Args:
            category: Tool category.

        Returns:
            List of ToolSchema objects.
        """
        with self._lock:
            names = self._categories.get(category, set())
            return [
                self._tools[name].schema
                for name in names
                if name in self._tools
            ]

    def get_tool_count(self) -> int:
        """Get total number of registered tools."""
        with self._lock:
            return len(self._tools)

    def get_category_summary(self) -> Dict[str, int]:
        """Get count of tools per category."""
        with self._lock:
            return {
                cat.value: len(names)
                for cat, names in self._categories.items()
                if names
            }

    def deprecate_tool(self, name: str, message: str = "This tool is deprecated"):
        """
        Mark a tool as deprecated.

        Args:
            name: Tool name.
            message: Deprecation message.
        """
        with self._lock:
            if name in self._tools:
                self._tools[name].schema.deprecated = True
                self._tools[name].schema.deprecation_message = message
                logger.warning(f"Deprecated tool '{name}': {message}")

    def get_tool_versions(self, name: str) -> List[str]:
        """
        Get version history for a tool (tracks current version).

        Args:
            name: Tool name.

        Returns:
            List containing current version string.
        """
        with self._lock:
            if name in self._tools:
                return [self._tools[name].schema.version]
            return []
