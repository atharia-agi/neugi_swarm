"""
NEUGI v2 Plugin Architecture - Extensible plugin system based on OpenClaw patterns.

Provides plugin discovery, loading, registration, lifecycle management,
and a hook system for intercepting system events.

Usage:
    from neugi_swarm_v2.plugins import PluginLoader, PluginRegistry, HookManager

    loader = PluginLoader(base_dir="./plugins")
    registry = PluginRegistry()
    hooks = HookManager()

    loader.discover_and_load(registry)
"""

from __future__ import annotations

from plugins.hooks import HookContext, HookEvent, HookManager, HookPriority, HookResult
from plugins.plugin_loader import PluginLoader, PluginLoadError, PluginManifest
from plugins.plugin_registry import PluginInfo, PluginRegistry, PluginState, PluginStatus
from plugins.plugin_sdk import (
    PluginBase,
    PluginCapability,
    PluginContext,
    PluginError,
    PluginManifestSchema,
    PluginMetadata,
    register_hook,
    register_route,
    register_skill,
    register_tool,
)

__all__ = [
    # SDK
    "PluginBase",
    "PluginCapability",
    "PluginContext",
    "PluginError",
    "PluginManifestSchema",
    "PluginMetadata",
    "register_hook",
    "register_route",
    "register_skill",
    "register_tool",
    # Loader
    "PluginLoader",
    "PluginLoadError",
    "PluginManifest",
    # Registry
    "PluginInfo",
    "PluginRegistry",
    "PluginState",
    "PluginStatus",
    # Hooks
    "HookContext",
    "HookEvent",
    "HookManager",
    "HookPriority",
    "HookResult",
]
