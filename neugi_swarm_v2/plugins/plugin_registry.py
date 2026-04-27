"""
NEUGI v2 Plugin Registry - Central plugin management and monitoring.

Tracks plugin state, manages enable/disable, handles configuration,
provides capability querying, monitors health, and manages uninstall/cleanup.

Usage:
    registry = PluginRegistry()
    registry.register_plugin("my-plugin", metadata, context)
    registry.enable_plugin("my-plugin")
    tools = registry.get_tools_by_capability("tool")
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

from plugins.plugin_sdk import PluginContext, PluginMetadata

logger = logging.getLogger(__name__)


# -- Plugin state and status --------------------------------------------------

class PluginState(str, Enum):
    """Lifecycle state of a plugin."""

    LOADED = "loaded"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"
    UNINSTALLED = "uninstalled"


@dataclass
class PluginStatus:
    """
    Runtime status of a plugin.

    Attributes:
        state: Current lifecycle state.
        enabled_at: When the plugin was enabled.
        disabled_at: When the plugin was disabled.
        last_error: Last error message (if any).
        error_count: Number of errors since load.
        health_status: Health check result.
        uptime: Seconds since enabled (if enabled).
    """

    state: PluginState = PluginState.LOADED
    enabled_at: Optional[datetime] = None
    disabled_at: Optional[datetime] = None
    last_error: Optional[str] = None
    error_count: int = 0
    health_status: str = "unknown"
    uptime: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "state": self.state.value,
            "enabled_at": self.enabled_at.isoformat() if self.enabled_at else None,
            "disabled_at": self.disabled_at.isoformat() if self.disabled_at else None,
            "last_error": self.last_error,
            "error_count": self.error_count,
            "health_status": self.health_status,
            "uptime": round(self.uptime, 2),
        }


@dataclass
class PluginInfo:
    """
    Complete information about a registered plugin.

    Combines metadata, status, context, and configuration.
    """

    name: str
    metadata: PluginMetadata
    status: PluginStatus
    context: Optional[PluginContext] = None
    config: dict[str, Any] = field(default_factory=dict)
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "name": self.name,
            "metadata": {
                "name": self.metadata.name,
                "version": self.metadata.version,
                "description": self.metadata.description,
                "author": self.metadata.author,
                "path": str(self.metadata.path) if self.metadata.path else None,
                "load_time": round(self.metadata.load_time, 3),
                "load_error": self.metadata.load_error,
                "is_loaded": self.metadata.is_loaded,
            },
            "status": self.status.to_dict(),
            "config": self.config,
            "registered_at": self.registered_at.isoformat(),
            "tools": list(self.context.tools.keys()) if self.context else [],
            "skills": list(self.context.skills.keys()) if self.context else [],
            "hooks": len(self.context.hooks) if self.context else 0,
            "routes": len(self.context.routes) if self.context else 0,
        }


# -- Plugin registry ----------------------------------------------------------

class PluginRegistry:
    """
    Central registry for all plugins.

    Manages:
    - Plugin registration and unregistration
    - Enable/disable lifecycle
    - Configuration management
    - Capability querying
    - Health monitoring
    - Uninstall and cleanup
    - Tool/skill/hook/route aggregation

    Usage:
        registry = PluginRegistry()
        registry.register_plugin("my-plugin", metadata, context)
        registry.enable_plugin("my-plugin")
        tools = registry.get_all_tools()
    """

    def __init__(
        self,
        config_store: Optional[Any] = None,
        health_check_interval: float = 60.0,
    ) -> None:
        """
        Initialize the plugin registry.

        Args:
            config_store: Optional persistent config storage (dict-like).
            health_check_interval: Seconds between health checks.
        """
        self._plugins: dict[str, PluginInfo] = {}
        self._lock = threading.RLock()

        # System component references (set by the loader)
        self._memory_system: Optional[Any] = None
        self._agent_manager: Optional[Any] = None
        self._skill_manager: Optional[Any] = None
        self._global_config: dict[str, Any] = {}

        # Configuration
        self._config_store = config_store or {}
        self._plugin_configs: dict[str, dict[str, Any]] = {}

        # Health monitoring
        self._health_check_interval = health_check_interval
        self._health_thread: Optional[threading.Thread] = None
        self._health_running = False
        self._health_checks: dict[str, Callable[[], bool]] = {}

        # Aggregated registrations
        self._tools: dict[str, tuple[str, Callable]] = {}  # name -> (plugin_name, handler)
        self._skills: dict[str, tuple[str, Any]] = {}
        self._hooks: dict[str, list[tuple[int, str, Callable]]] = {}  # event -> [(priority, plugin, handler)]
        self._routes: list[tuple[str, str, Callable, list[str]]] = []  # (path, plugin, handler, methods)

    def set_system_components(
        self,
        memory_system: Optional[Any] = None,
        agent_manager: Optional[Any] = None,
        skill_manager: Optional[Any] = None,
        config: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Set references to system components for plugin context.

        Args:
            memory_system: MemorySystem instance.
            agent_manager: AgentManager instance.
            skill_manager: SkillManager instance.
            config: Global configuration dict.
        """
        self._memory_system = memory_system
        self._agent_manager = agent_manager
        self._skill_manager = skill_manager
        if config:
            self._global_config = config

    def get_memory_system(self) -> Optional[Any]:
        """Get the memory system reference."""
        return self._memory_system

    def get_agent_manager(self) -> Optional[Any]:
        """Get the agent manager reference."""
        return self._agent_manager

    def get_skill_manager(self) -> Optional[Any]:
        """Get the skill manager reference."""
        return self._skill_manager

    def get_config(self) -> dict[str, Any]:
        """Get the global configuration."""
        return dict(self._global_config)

    def get_plugin_config(self, plugin_name: str) -> dict[str, Any]:
        """Get configuration for a specific plugin."""
        return dict(self._plugin_configs.get(plugin_name, {}))

    # -- Registration ----------------------------------------------------------

    def register_plugin(
        self,
        name: str,
        metadata: PluginMetadata,
        context: Optional[PluginContext],
    ) -> PluginInfo:
        """
        Register a plugin with the registry.

        Args:
            name: Plugin name.
            metadata: Plugin metadata from the loader.
            context: Plugin context (may be None if load failed).

        Returns:
            The created PluginInfo.
        """
        with self._lock:
            # Load persisted config
            config = dict(self._config_store.get(name, {}))

            # Merge with runtime plugin config
            if context:
                runtime_config = context.plugin_config
                config.update(runtime_config)

            status = PluginState.LOADED
            if metadata.load_error:
                status = PluginState.ERROR

            info = PluginInfo(
                name=name,
                metadata=metadata,
                status=PluginStatus(state=status, last_error=metadata.load_error),
                context=context,
                config=config,
            )

            self._plugins[name] = info
            self._plugin_configs[name] = config

            # Aggregate registrations from context
            if context:
                for tool_name, handler in context.tools.items():
                    self._tools[tool_name] = (name, handler)

                for skill_name, skill in context.skills.items():
                    self._skills[skill_name] = (name, skill)

                for hook_def in context.hooks:
                    event = hook_def["event"]
                    priority = hook_def["priority"]
                    handler = hook_def["handler"]
                    if event not in self._hooks:
                        self._hooks[event] = []
                    self._hooks[event].append((priority, name, handler))
                    # Sort by priority
                    self._hooks[event].sort(key=lambda x: x[0])

                for route_def in context.routes:
                    self._routes.append((
                        route_def["path"],
                        name,
                        route_def["handler"],
                        route_def["methods"],
                    ))

            logger.info("Registered plugin: %s", name)
            return info

    def unregister_plugin(self, name: str) -> bool:
        """
        Unregister a plugin from the registry.

        Args:
            name: Plugin name.

        Returns:
            True if the plugin was found and unregistered.
        """
        with self._lock:
            if name not in self._plugins:
                return False

            info = self._plugins[name]

            # Remove aggregated registrations
            if info.context:
                for tool_name in info.context.tools:
                    self._tools.pop(tool_name, None)

                for skill_name in info.context.skills:
                    self._skills.pop(skill_name, None)

                for hook_def in info.context.hooks:
                    event = hook_def["event"]
                    if event in self._hooks:
                        self._hooks[event] = [
                            h for h in self._hooks[event] if h[1] != name
                        ]

                self._routes = [r for r in self._routes if r[1] != name]

            # Remove health check
            self._health_checks.pop(name, None)

            del self._plugins[name]
            logger.info("Unregistered plugin: %s", name)
            return True

    # -- Enable / Disable ------------------------------------------------------

    def enable_plugin(self, name: str) -> bool:
        """
        Enable a plugin.

        Args:
            name: Plugin name.

        Returns:
            True if the plugin was found and enabled.
        """
        with self._lock:
            info = self._plugins.get(name)
            if info is None:
                return False

            if info.status.state == PluginState.ERROR:
                logger.warning("Cannot enable plugin %s: in error state", name)
                return False

            if info.status.state == PluginState.ENABLED:
                return True

            if info.metadata.instance:
                try:
                    info.metadata.instance.on_enable()
                except Exception as e:
                    info.status.state = PluginState.ERROR
                    info.status.last_error = str(e)
                    info.status.error_count += 1
                    logger.error("Failed to enable plugin %s: %s", name, e)
                    return False

            info.status.state = PluginState.ENABLED
            info.status.enabled_at = datetime.now(timezone.utc)
            info.status.disabled_at = None
            info.status.uptime = 0.0
            logger.info("Enabled plugin: %s", name)
            return True

    def disable_plugin(self, name: str) -> bool:
        """
        Disable a plugin.

        Args:
            name: Plugin name.

        Returns:
            True if the plugin was found and disabled.
        """
        with self._lock:
            info = self._plugins.get(name)
            if info is None:
                return False

            if info.status.state == PluginState.DISABLED:
                return True

            if info.metadata.instance:
                try:
                    info.metadata.instance.on_disable()
                except Exception as e:
                    info.status.last_error = str(e)
                    info.status.error_count += 1
                    logger.error("Failed to disable plugin %s: %s", name, e)

            info.status.state = PluginState.DISABLED
            info.status.disabled_at = datetime.now(timezone.utc)
            info.status.uptime = 0.0
            logger.info("Disabled plugin: %s", name)
            return True

    # -- Configuration ---------------------------------------------------------

    def set_plugin_config(self, name: str, config: dict[str, Any]) -> bool:
        """
        Set configuration for a plugin.

        Args:
            name: Plugin name.
            config: Configuration dict.

        Returns:
            True if the plugin was found.
        """
        with self._lock:
            info = self._plugins.get(name)
            if info is None:
                return False

            old_config = dict(info.config)
            info.config.update(config)
            self._plugin_configs[name] = info.config
            self._config_store[name] = info.config

            # Notify plugin of config changes
            if info.metadata.instance:
                for key, new_value in config.items():
                    old_value = old_config.get(key)
                    if old_value != new_value:
                        try:
                            info.metadata.instance.on_config_change(key, old_value, new_value)
                        except Exception as e:
                            logger.error(
                                "Plugin %s config change handler error: %s", name, e
                            )

            return True

    def get_plugin_config_value(self, name: str, key: str, default: Any = None) -> Any:
        """Get a specific configuration value for a plugin."""
        with self._lock:
            info = self._plugins.get(name)
            if info is None:
                return default
            return info.config.get(key, default)

    # -- Capability querying ---------------------------------------------------

    def get_plugin_by_capability(self, capability: str) -> list[PluginInfo]:
        """
        Get all plugins that declare a specific capability.

        Args:
            capability: Capability string (e.g. "tool", "hook").

        Returns:
            List of PluginInfo that declare the capability.
        """
        with self._lock:
            return [
                info for info in self._plugins.values()
                if info.metadata.is_loaded
                and info.status.state == PluginState.ENABLED
                and capability in (info.context.skills if info.context else {})
            ]

    def get_tools_by_capability(self, capability: str) -> dict[str, Callable]:
        """
        Get all tools from plugins with a specific capability.

        Args:
            capability: Capability string.

        Returns:
            Dict mapping tool name to handler.
        """
        with self._lock:
            return {
                name: handler
                for name, (plugin_name, handler) in self._tools.items()
                if self._plugins.get(plugin_name)
                and self._plugins[plugin_name].status.state == PluginState.ENABLED
            }

    def get_hooks_for_event(self, event: str) -> list[tuple[str, Callable]]:
        """
        Get all hooks registered for an event, sorted by priority.

        Args:
            event: Hook event name.

        Returns:
            List of (plugin_name, handler) tuples.
        """
        with self._lock:
            hooks = self._hooks.get(event, [])
            return [(plugin_name, handler) for _, plugin_name, handler in hooks]

    # -- Aggregated access -----------------------------------------------------

    def get_all_tools(self) -> dict[str, Callable]:
        """Get all registered tools from enabled plugins."""
        with self._lock:
            return {
                name: handler
                for name, (plugin_name, handler) in self._tools.items()
                if self._plugins.get(plugin_name)
                and self._plugins[plugin_name].status.state == PluginState.ENABLED
            }

    def get_all_skills(self) -> dict[str, Any]:
        """Get all registered skills from enabled plugins."""
        with self._lock:
            return {
                name: skill
                for name, (plugin_name, skill) in self._skills.items()
                if self._plugins.get(plugin_name)
                and self._plugins[plugin_name].status.state == PluginState.ENABLED
            }

    def get_all_routes(self) -> list[tuple[str, Callable, list[str]]]:
        """Get all registered routes from enabled plugins."""
        with self._lock:
            return [
                (path, handler, methods)
                for path, plugin_name, handler, methods in self._routes
                if self._plugins.get(plugin_name)
                and self._plugins[plugin_name].status.state == PluginState.ENABLED
            ]

    # -- Listing and status ----------------------------------------------------

    def list_plugins(self) -> list[PluginInfo]:
        """Get all registered plugins."""
        with self._lock:
            return list(self._plugins.values())

    def get_plugin(self, name: str) -> Optional[PluginInfo]:
        """Get a plugin by name."""
        return self._plugins.get(name)

    def get_enabled_plugins(self) -> list[PluginInfo]:
        """Get all enabled plugins."""
        with self._lock:
            return [
                info for info in self._plugins.values()
                if info.status.state == PluginState.ENABLED
            ]

    def get_plugin_status(self, name: str) -> Optional[dict[str, Any]]:
        """Get the status dict for a plugin."""
        info = self._plugins.get(name)
        if info is None:
            return None
        return info.to_dict()

    def get_stats(self) -> dict[str, Any]:
        """Get registry statistics."""
        with self._lock:
            total = len(self._plugins)
            enabled = sum(1 for p in self._plugins.values() if p.status.state == PluginState.ENABLED)
            disabled = sum(1 for p in self._plugins.values() if p.status.state == PluginState.DISABLED)
            errored = sum(1 for p in self._plugins.values() if p.status.state == PluginState.ERROR)

            return {
                "total_plugins": total,
                "enabled": enabled,
                "disabled": disabled,
                "errored": errored,
                "total_tools": len(self._tools),
                "total_skills": len(self._skills),
                "total_hook_events": len(self._hooks),
                "total_routes": len(self._routes),
            }

    # -- Health monitoring -----------------------------------------------------

    def register_health_check(self, name: str, check_fn: Callable[[], bool]) -> None:
        """
        Register a health check function for a plugin.

        Args:
            name: Plugin name.
            check_fn: Callable that returns True if healthy.
        """
        with self._lock:
            self._health_checks[name] = check_fn

    def run_health_check(self, name: str) -> str:
        """
        Run a health check for a specific plugin.

        Args:
            name: Plugin name.

        Returns:
            Health status string ("healthy", "unhealthy", "unknown").
        """
        with self._lock:
            info = self._plugins.get(name)
            if info is None:
                return "unknown"

            if info.status.state != PluginState.ENABLED:
                info.status.health_status = info.status.state.value
                return info.status.state.value

            check_fn = self._health_checks.get(name)
            if check_fn is None:
                # No custom check; assume healthy if enabled
                info.status.health_status = "healthy"
                return "healthy"

            try:
                if check_fn():
                    info.status.health_status = "healthy"
                else:
                    info.status.health_status = "unhealthy"
            except Exception as e:
                info.status.health_status = "unhealthy"
                info.status.last_error = str(e)
                info.status.error_count += 1
                logger.error("Health check failed for plugin %s: %s", name, e)

            return info.status.health_status

    def run_all_health_checks(self) -> dict[str, str]:
        """Run health checks for all plugins."""
        results: dict[str, str] = {}
        with self._lock:
            for name in self._plugins:
                results[name] = self.run_health_check(name)
        return results

    def start_health_monitoring(self) -> None:
        """Start background health monitoring."""
        if self._health_running:
            return

        self._health_running = True
        self._health_thread = threading.Thread(
            target=self._health_loop, daemon=True, name="plugin-health-monitor"
        )
        self._health_thread.start()
        logger.info("Plugin health monitoring started")

    def stop_health_monitoring(self) -> None:
        """Stop background health monitoring."""
        self._health_running = False
        if self._health_thread:
            self._health_thread.join(timeout=5.0)
            self._health_thread = None
        logger.info("Plugin health monitoring stopped")

    def _health_loop(self) -> None:
        """Background health check loop."""
        while self._health_running:
            time.sleep(self._health_check_interval)
            try:
                self.run_all_health_checks()
            except Exception as e:
                logger.error("Health monitoring error: %s", e)

    # -- Uninstall / Cleanup ---------------------------------------------------

    def uninstall_plugin(self, name: str) -> bool:
        """
        Uninstall a plugin (disable, unregister, and clean up).

        Args:
            name: Plugin name.

        Returns:
            True if the plugin was found and uninstalled.
        """
        with self._lock:
            info = self._plugins.get(name)
            if info is None:
                return False

            # Disable first
            self.disable_plugin(name)

            # Unregister
            self.unregister_plugin(name)

            # Clean up config
            self._plugin_configs.pop(name, None)
            self._config_store.pop(name, None)

            # Clean up health check
            self._health_checks.pop(name, None)

            logger.info("Uninstalled plugin: %s", name)
            return True

    def cleanup_all(self) -> dict[str, Any]:
        """
        Clean up all plugins (for shutdown).

        Returns:
            Summary dict with cleanup stats.
        """
        stats = {"unloaded": 0, "errors": 0}

        # Disable all first
        for name in list(self._plugins.keys()):
            try:
                self.disable_plugin(name)
            except Exception as e:
                logger.error("Error disabling plugin %s during cleanup: %s", name, e)
                stats["errors"] += 1

        # Unregister all
        for name in list(self._plugins.keys()):
            try:
                self.unregister_plugin(name)
                stats["unloaded"] += 1
            except Exception as e:
                logger.error("Error unregistering plugin %s during cleanup: %s", name, e)
                stats["errors"] += 1

        # Clear aggregated state
        self._tools.clear()
        self._skills.clear()
        self._hooks.clear()
        self._routes.clear()

        logger.info("Plugin cleanup complete: %s", stats)
        return stats
