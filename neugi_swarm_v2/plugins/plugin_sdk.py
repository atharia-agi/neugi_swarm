"""
NEUGI v2 Plugin SDK - Core plugin development kit.

Provides the base class for plugins, registration APIs, lifecycle hooks,
plugin context, manifest schema validation, dependency resolution,
and version compatibility checking.

Usage:
    from plugins.plugin_sdk import PluginBase, PluginContext

    class MyPlugin(PluginBase):
        def on_load(self, ctx: PluginContext) -> None:
            register_tool("my_tool", self.my_tool_handler)

        def my_tool_handler(self, **kwargs):
            return {"result": "hello"}
"""

from __future__ import annotations

import importlib
import logging
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# -- Exceptions ---------------------------------------------------------------

class PluginError(Exception):
    """Base exception for plugin system errors."""
    pass


class PluginRegistrationError(PluginError):
    """Raised when a plugin registration fails."""
    pass


class PluginDependencyError(PluginError):
    """Raised when a plugin dependency cannot be resolved."""
    pass


class PluginVersionError(PluginError):
    """Raised when a plugin version is incompatible."""
    pass


# -- Version utilities --------------------------------------------------------

_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-(.+))?$")


@dataclass(frozen=True)
class SemVer:
    """Semantic version (major.minor.patch[-prerelease])."""

    major: int
    minor: int
    patch: int
    prerelease: Optional[str] = None

    @classmethod
    def parse(cls, version: str) -> SemVer:
        """Parse a version string like '1.2.3' or '1.2.3-beta'."""
        m = _VERSION_RE.match(version.strip())
        if not m:
            raise PluginVersionError(f"Invalid version string: {version!r}")
        return cls(
            major=int(m.group(1)),
            minor=int(m.group(2)),
            patch=int(m.group(3)),
            prerelease=m.group(4),
        )

    def __str__(self) -> str:
        s = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            s += f"-{self.prerelease}"
        return s

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)

    def __le__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return (self.major, self.minor, self.patch) <= (other.major, other.minor, other.patch)

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return (self.major, self.minor, self.patch) > (other.major, other.minor, other.patch)

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return (self.major, self.minor, self.patch) >= (other.major, other.minor, other.patch)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return (self.major, self.minor, self.patch) == (other.major, other.minor, other.patch)

    def is_compatible_with(self, other: SemVer) -> bool:
        """Check if this version is compatible with another (same major)."""
        return self.major == other.major


def check_version_constraint(version: SemVer, constraint: str) -> bool:
    """
    Check if a version satisfies a constraint string.

    Supported operators: ==, !=, >=, <=, >, <, ^, ~
    - ^1.2.3  -> >=1.2.3 and <2.0.0 (compatible with major)
    - ~1.2.3  -> >=1.2.3 and <1.3.0 (compatible with minor)
    - >=1.0.0 -> greater or equal
    - ==1.2.3 -> exact match
    - 1.2.3   -> shorthand for ==1.2.3

    Args:
        version: The version to check.
        constraint: Constraint string (e.g. ">=1.0.0", "^2.0").

    Returns:
        True if the version satisfies the constraint.
    """
    constraint = constraint.strip()
    if not constraint:
        return True

    # Parse operator and target version
    for op in (">=", "<=", "!=", "==", ">", "<", "^", "~"):
        if constraint.startswith(op):
            target_str = constraint[len(op):].strip()
            target = SemVer.parse(target_str)
            return _apply_op(version, op, target)

    # Bare version string -> exact match
    target = SemVer.parse(constraint)
    return version == target


def _apply_op(version: SemVer, op: str, target: SemVer) -> bool:
    """Apply a comparison operator between two versions."""
    if op == "==":
        return version == target
    if op == "!=":
        return version != target
    if op == ">=":
        return version >= target
    if op == "<=":
        return version <= target
    if op == ">":
        return version > target
    if op == "<":
        return version < target
    if op == "^":
        # Compatible with major: >=target and <(major+1).0.0
        if version < target:
            return False
        upper = SemVer(target.major + 1, 0, 0)
        return version < upper
    if op == "~":
        # Compatible with minor: >=target and <major.(minor+1).0
        if version < target:
            return False
        upper = SemVer(target.major, target.minor + 1, 0)
        return version < upper
    return False


# -- Manifest schema ----------------------------------------------------------

@dataclass
class PluginManifestSchema:
    """
    Schema definition for neugi.plugin.json manifest files.

    Attributes:
        name: Unique plugin identifier (required).
        version: SemVer string (required).
        description: Human-readable description.
        author: Author name or organization.
        homepage: Plugin homepage URL.
        license: SPDX license identifier.
        min_neugi_version: Minimum NEUGI version required.
        max_neugi_version: Maximum NEUGI version supported.
        dependencies: Dict of plugin_name -> version_constraint.
        optional_dependencies: Dict of plugin_name -> version_constraint.
        entry_point: Module path to the plugin class (e.g. "my_plugin:MyPlugin").
        capabilities: List of capability strings the plugin provides.
        config_schema: JSON schema for plugin configuration.
        tags: Categorization labels.
    """

    name: str
    version: str
    description: str = ""
    author: str = ""
    homepage: str = ""
    license: str = ""
    min_neugi_version: str = ""
    max_neugi_version: str = ""
    dependencies: dict[str, str] = field(default_factory=dict)
    optional_dependencies: dict[str, str] = field(default_factory=dict)
    entry_point: str = ""
    capabilities: list[str] = field(default_factory=list)
    config_schema: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    def validate(self) -> list[str]:
        """
        Validate the manifest against the schema.

        Returns:
            List of error messages (empty if valid).
        """
        errors: list[str] = []

        if not self.name or not self.name.strip():
            errors.append("Manifest 'name' is required and must be non-empty")
        elif not re.match(r"^[a-zA-Z0-9_-]+$", self.name):
            errors.append(
                f"Manifest 'name' must be alphanumeric with hyphens/underscores: {self.name!r}"
            )

        if not self.version:
            errors.append("Manifest 'version' is required")
        else:
            try:
                SemVer.parse(self.version)
            except PluginVersionError as e:
                errors.append(str(e))

        if self.min_neugi_version:
            try:
                SemVer.parse(self.min_neugi_version)
            except PluginVersionError:
                errors.append(f"Invalid min_neugi_version: {self.min_neugi_version!r}")

        if self.max_neugi_version:
            try:
                SemVer.parse(self.max_neugi_version)
            except PluginVersionError:
                errors.append(f"Invalid max_neugi_version: {self.max_neugi_version!r}")

        # Validate dependency constraints
        for dep_name, constraint in self.dependencies.items():
            try:
                # Just validate the constraint syntax; resolution happens later
                SemVer.parse("0.0.0")  # dummy
                check_version_constraint(SemVer(0, 0, 0), constraint)
            except PluginVersionError:
                errors.append(f"Invalid dependency constraint for {dep_name!r}: {constraint!r}")

        if self.entry_point and ":" not in self.entry_point:
            errors.append(
                f"Manifest 'entry_point' must be in 'module:Class' format: {self.entry_point!r}"
            )

        return errors

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "homepage": self.homepage,
            "license": self.license,
            "min_neugi_version": self.min_neugi_version,
            "max_neugi_version": self.max_neugi_version,
            "dependencies": self.dependencies,
            "optional_dependencies": self.optional_dependencies,
            "entry_point": self.entry_point,
            "capabilities": self.capabilities,
            "config_schema": self.config_schema,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PluginManifestSchema:
        """Deserialize from a dict."""
        return cls(
            name=data.get("name", ""),
            version=data.get("version", ""),
            description=data.get("description", ""),
            author=data.get("author", ""),
            homepage=data.get("homepage", ""),
            license=data.get("license", ""),
            min_neugi_version=data.get("min_neugi_version", ""),
            max_neugi_version=data.get("max_neugi_version", ""),
            dependencies=data.get("dependencies", {}),
            optional_dependencies=data.get("optional_dependencies", {}),
            entry_point=data.get("entry_point", ""),
            capabilities=data.get("capabilities", []),
            config_schema=data.get("config_schema", {}),
            tags=data.get("tags", []),
        )


# -- Plugin metadata ----------------------------------------------------------

@dataclass
class PluginMetadata:
    """
    Runtime metadata for a loaded plugin.

    Attributes:
        name: Plugin identifier.
        version: Plugin version.
        description: Plugin description.
        author: Author name.
        path: Filesystem path to the plugin directory.
        module: The loaded Python module (if any).
        instance: The plugin class instance (if any).
        load_time: Time taken to load in seconds.
        load_error: Error message if loading failed.
    """

    name: str
    version: str
    description: str = ""
    author: str = ""
    path: Optional[Path] = None
    module: Optional[Any] = None
    instance: Optional[PluginBase] = None
    load_time: float = 0.0
    load_error: Optional[str] = None

    @property
    def is_loaded(self) -> bool:
        """Whether the plugin was successfully loaded."""
        return self.instance is not None and self.load_error is None

    @property
    def semver(self) -> SemVer:
        """Parse the version string into a SemVer."""
        return SemVer.parse(self.version)


# -- Plugin capabilities ------------------------------------------------------

class PluginCapability(str, Enum):
    """
    Capability flags that a plugin can declare.

    These are used by the registry to filter and query plugins.
    """

    TOOL = "tool"
    SKILL = "skill"
    HOOK = "hook"
    ROUTE = "route"
    MEMORY = "memory"
    AGENT = "agent"
    CONFIG = "config"
    EVENT = "event"


# -- Plugin context -----------------------------------------------------------

class PluginContext:
    """
    Execution context provided to plugins during lifecycle hooks.

    Gives plugins controlled access to system components (memory, agents,
    skills, config) without exposing internals directly.

    Usage:
        def on_load(self, ctx: PluginContext) -> None:
            memory = ctx.get_memory_system()
            agents = ctx.get_agent_manager()
            value = ctx.get_config("my_plugin.setting")
    """

    def __init__(
        self,
        memory_system: Optional[Any] = None,
        agent_manager: Optional[Any] = None,
        skill_manager: Optional[Any] = None,
        config: Optional[dict[str, Any]] = None,
        plugin_config: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Initialize the plugin context.

        Args:
            memory_system: Reference to the MemorySystem instance.
            agent_manager: Reference to the AgentManager instance.
            skill_manager: Reference to the SkillManager instance.
            config: Global NEUGI configuration dict.
            plugin_config: This plugin's configuration dict.
        """
        self._memory_system = memory_system
        self._agent_manager = agent_manager
        self._skill_manager = skill_manager
        self._config = config or {}
        self._plugin_config = plugin_config or {}
        self._tools: dict[str, Callable] = {}
        self._skills: dict[str, Any] = {}
        self._hooks: list[dict[str, Any]] = []
        self._routes: list[dict[str, Any]] = []

    def get_memory_system(self) -> Optional[Any]:
        """Get the memory system instance (read-only access)."""
        return self._memory_system

    def get_agent_manager(self) -> Optional[Any]:
        """Get the agent manager instance (read-only access)."""
        return self._agent_manager

    def get_skill_manager(self) -> Optional[Any]:
        """Get the skill manager instance (read-only access)."""
        return self._skill_manager

    def get_config(self, key: str, default: Any = None) -> Any:
        """
        Get a global configuration value by dotted key.

        Args:
            key: Dotted path (e.g. "llm.provider").
            default: Default value if key not found.

        Returns:
            The configuration value or default.
        """
        parts = key.split(".")
        value: Any = self._config
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
                if value is None:
                    return default
            else:
                return default
        return value

    def get_plugin_config(self, key: str, default: Any = None) -> Any:
        """
        Get this plugin's configuration value.

        Args:
            key: Configuration key.
            default: Default value if key not found.

        Returns:
            The configuration value or default.
        """
        return self._plugin_config.get(key, default)

    @property
    def plugin_config(self) -> dict[str, Any]:
        """Get the full plugin configuration dict."""
        return dict(self._plugin_config)

    # -- Registration helpers (used by register_* functions) -------------------

    def register_tool(self, name: str, handler: Callable, description: str = "") -> None:
        """Register a tool provided by this plugin."""
        if name in self._tools:
            raise PluginRegistrationError(f"Tool {name!r} already registered")
        self._tools[name] = handler
        logger.debug("Plugin registered tool: %s", name)

    def register_skill(self, name: str, skill: Any) -> None:
        """Register a skill provided by this plugin."""
        if name in self._skills:
            raise PluginRegistrationError(f"Skill {name!r} already registered")
        self._skills[name] = skill
        logger.debug("Plugin registered skill: %s", name)

    def register_hook(self, event: str, handler: Callable, priority: int = 0) -> None:
        """Register a lifecycle hook."""
        self._hooks.append({"event": event, "handler": handler, "priority": priority})
        logger.debug("Plugin registered hook: %s (priority=%d)", event, priority)

    def register_route(self, path: str, handler: Callable, methods: list[str] | None = None) -> None:
        """Register an HTTP route."""
        self._routes.append({
            "path": path,
            "handler": handler,
            "methods": methods or ["GET"],
        })
        logger.debug("Plugin registered route: %s", path)

    @property
    def tools(self) -> dict[str, Callable]:
        """Get all registered tools."""
        return dict(self._tools)

    @property
    def skills(self) -> dict[str, Any]:
        """Get all registered skills."""
        return dict(self._skills)

    @property
    def hooks(self) -> list[dict[str, Any]]:
        """Get all registered hooks."""
        return list(self._hooks)

    @property
    def routes(self) -> list[dict[str, Any]]:
        """Get all registered routes."""
        return list(self._routes)


# -- Plugin base class --------------------------------------------------------

class PluginBase:
    """
    Base class for all NEUGI v2 plugins.

    Subclass this to create a plugin. Override lifecycle hooks as needed:
    - on_load: Called when the plugin is loaded.
    - on_unload: Called when the plugin is unloaded.
    - on_enable: Called when the plugin is enabled.
    - on_disable: Called when the plugin is disabled.

    Usage:
        class MyPlugin(PluginBase):
            def on_load(self, ctx: PluginContext) -> None:
                register_tool("greet", self.greet)

            def greet(self, name: str) -> str:
                return f"Hello, {name}!"
    """

    def __init__(self) -> None:
        """Initialize the plugin."""
        self._context: Optional[PluginContext] = None
        self._enabled = False

    @property
    def name(self) -> str:
        """Plugin name (override or set via manifest)."""
        return self.__class__.__name__

    @property
    def version(self) -> str:
        """Plugin version (override or set via manifest)."""
        return "0.0.0"

    @property
    def description(self) -> str:
        """Plugin description (override or set via manifest)."""
        return ""

    @property
    def is_enabled(self) -> bool:
        """Whether the plugin is currently enabled."""
        return self._enabled

    def on_load(self, ctx: PluginContext) -> None:
        """
        Called when the plugin is loaded into the system.

        Use this to register tools, skills, hooks, and routes.

        Args:
            ctx: Plugin context with access to system components.
        """
        pass

    def on_unload(self) -> None:
        """
        Called when the plugin is unloaded from the system.

        Use this to clean up resources, close connections, etc.
        """
        pass

    def on_enable(self) -> None:
        """Called when the plugin is enabled."""
        self._enabled = True

    def on_disable(self) -> None:
        """Called when the plugin is disabled."""
        self._enabled = False

    def on_config_change(self, key: str, old_value: Any, new_value: Any) -> None:
        """
        Called when a plugin configuration value changes.

        Args:
            key: Configuration key that changed.
            old_value: Previous value.
            new_value: New value.
        """
        pass


# -- Registration API (module-level) ------------------------------------------

# These are convenience functions that plugins can call from within on_load().
# They operate on the current plugin's context.

_current_context: Optional[PluginContext] = None


def _set_current_context(ctx: Optional[PluginContext]) -> None:
    """Set the current plugin context (internal use)."""
    global _current_context
    _current_context = ctx


def register_tool(name: str, handler: Callable, description: str = "") -> None:
    """
    Register a tool with the plugin system.

    Must be called from within a plugin's on_load() method.

    Args:
        name: Unique tool name.
        handler: Callable that implements the tool.
        description: Human-readable tool description.
    """
    if _current_context is None:
        raise PluginRegistrationError("register_tool() must be called from within on_load()")
    _current_context.register_tool(name, handler, description)


def register_skill(name: str, skill: Any) -> None:
    """
    Register a skill with the plugin system.

    Must be called from within a plugin's on_load() method.

    Args:
        name: Unique skill name.
        skill: Skill object or contract.
    """
    if _current_context is None:
        raise PluginRegistrationError("register_skill() must be called from within on_load()")
    _current_context.register_skill(name, skill)


def register_hook(event: str, handler: Callable, priority: int = 0) -> None:
    """
    Register a lifecycle hook.

    Must be called from within a plugin's on_load() method.

    Args:
        event: Hook event name (e.g. "pre_tool_call").
        handler: Callable that handles the hook.
        priority: Execution priority (lower = earlier).
    """
    if _current_context is None:
        raise PluginRegistrationError("register_hook() must be called from within on_load()")
    _current_context.register_hook(event, handler, priority)


def register_route(path: str, handler: Callable, methods: list[str] | None = None) -> None:
    """
    Register an HTTP route.

    Must be called from within a plugin's on_load() method.

    Args:
        path: URL path pattern.
        handler: Callable that handles the request.
        methods: HTTP methods (default: ["GET"]).
    """
    if _current_context is None:
        raise PluginRegistrationError("register_route() must be called from within on_load()")
    _current_context.register_route(path, handler, methods)


# -- Dependency resolution ----------------------------------------------------

def resolve_dependencies(
    manifests: dict[str, PluginManifestSchema],
    available: dict[str, SemVer],
) -> tuple[list[str], list[str]]:
    """
    Resolve plugin dependencies using topological sort.

    Args:
        manifests: Dict of plugin_name -> manifest for all plugins to load.
        available: Dict of plugin_name -> version for already-loaded plugins.

    Returns:
        (load_order, errors) where load_order is the topological order
        and errors is a list of unresolvable dependency errors.
    """
    # Build adjacency list
    graph: dict[str, set[str]] = {name: set() for name in manifests}
    errors: list[str] = []

    for name, manifest in manifests.items():
        for dep_name, constraint in manifest.dependencies.items():
            if dep_name in available:
                # Check version constraint against available version
                if not check_version_constraint(available[dep_name], constraint):
                    errors.append(
                        f"Plugin {name!r} requires {dep_name} {constraint}, "
                        f"but {available[dep_name]} is available"
                    )
            elif dep_name in manifests:
                # Dependency is another plugin being loaded
                graph[name].add(dep_name)
            else:
                errors.append(
                    f"Plugin {name!r} has unmet dependency: {dep_name} {constraint}"
                )

    # Topological sort (Kahn's algorithm)
    in_degree: dict[str, int] = {name: 0 for name in graph}
    for name, deps in graph.items():
        for dep in deps:
            if dep in in_degree:
                in_degree[name] = in_degree.get(name, 0)

    # Recalculate in-degrees properly
    in_degree = {name: 0 for name in graph}
    for name, deps in graph.items():
        for dep in deps:
            if dep in in_degree:
                pass  # dep must be loaded before name
    # Reverse: for each name, its deps must come first
    reverse_graph: dict[str, set[str]] = {name: set() for name in graph}
    for name, deps in graph.items():
        for dep in deps:
            if dep in reverse_graph:
                reverse_graph[dep].add(name)
                in_degree[name] += 1

    queue = [name for name, degree in in_degree.items() if degree == 0]
    queue.sort()  # Deterministic order
    load_order: list[str] = []

    while queue:
        node = queue.pop(0)
        load_order.append(node)
        for dependent in sorted(reverse_graph.get(node, [])):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    if len(load_order) != len(graph):
        # Cycle detected
        remaining = set(graph.keys()) - set(load_order)
        errors.append(f"Circular dependency detected among: {', '.join(sorted(remaining))}")

    return load_order, errors


# -- Plugin instantiation -----------------------------------------------------

def instantiate_plugin(manifest: PluginManifestSchema) -> PluginBase:
    """
    Instantiate a plugin class from its entry point.

    Args:
        manifest: The validated plugin manifest.

    Returns:
        An instance of the plugin class.

    Raises:
        PluginError: If the entry point cannot be loaded.
    """
    if not manifest.entry_point:
        # Fallback: try to find a PluginBase subclass in a module named after the plugin
        module_name = manifest.name.replace("-", "_")
        try:
            mod = importlib.import_module(module_name)
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, PluginBase)
                    and attr is not PluginBase
                ):
                    return attr()
        except ImportError:
            pass
        # Last resort: return a bare PluginBase
        return PluginBase()

    # Parse "module.path:ClassName"
    module_path, class_name = manifest.entry_point.split(":", 1)

    try:
        mod = importlib.import_module(module_path)
    except ImportError as e:
        raise PluginError(f"Failed to import module {module_path!r}: {e}") from e

    plugin_class = getattr(mod, class_name, None)
    if plugin_class is None:
        raise PluginError(f"Class {class_name!r} not found in module {module_path!r}")

    if not isinstance(plugin_class, type) or not issubclass(plugin_class, PluginBase):
        raise PluginError(
            f"{class_name!r} is not a subclass of PluginBase"
        )

    return plugin_class()
