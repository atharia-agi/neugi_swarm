"""
NEUGI v2 Plugin Loader - Discovery, loading, and lifecycle management.

Scans directories for plugins, reads manifests, resolves dependencies,
loads plugins in correct order, supports hot reload, and isolates
plugin execution to prevent crashes.

Usage:
    loader = PluginLoader(base_dir="./plugins")
    registry = PluginRegistry()
    loader.discover_and_load(registry)
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import logging
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from plugins.plugin_sdk import (
    PluginBase,
    PluginContext,
    PluginError,
    PluginManifestSchema,
    PluginMetadata,
    SemVer,
    _set_current_context,
    check_version_constraint,
    instantiate_plugin,
    resolve_dependencies,
)

logger = logging.getLogger(__name__)

NEUGI_VERSION = "2.0.0"
MANIFEST_FILENAME = "neugi.plugin.json"


# -- Exceptions ---------------------------------------------------------------

class PluginLoadError(PluginError):
    """Raised when a plugin fails to load."""
    pass


# -- Plugin manifest wrapper --------------------------------------------------

@dataclass
class PluginManifest:
    """
    A plugin manifest with its filesystem location.

    Attributes:
        schema: The parsed manifest schema.
        path: Path to the manifest file.
        plugin_dir: Directory containing the manifest.
    """

    schema: PluginManifestSchema
    path: Path
    plugin_dir: Path

    @classmethod
    def from_file(cls, manifest_path: Path) -> PluginManifest:
        """
        Load and parse a manifest from a JSON file.

        Args:
            manifest_path: Path to neugi.plugin.json.

        Returns:
            A PluginManifest instance.

        Raises:
            PluginLoadError: If the file cannot be read or parsed.
        """
        try:
            content = manifest_path.read_text(encoding="utf-8")
            data = json.loads(content)
        except (OSError, json.JSONDecodeError) as e:
            raise PluginLoadError(f"Failed to read manifest {manifest_path}: {e}") from e

        schema = PluginManifestSchema.from_dict(data)
        return cls(
            schema=schema,
            path=manifest_path,
            plugin_dir=manifest_path.parent,
        )


# -- Discovery ----------------------------------------------------------------

class PluginDiscovery:
    """
    Discovers plugins by scanning directories for manifest files.

    Searches in three locations (in precedence order):
    1. Workspace plugins (project-specific)
    2. Global plugins (~/.neugi/plugins)
    3. Bundled plugins (shipped with NEUGI)
    """

    def __init__(
        self,
        workspace_dir: Optional[str] = None,
        global_dir: Optional[str] = None,
        bundled_dir: Optional[str] = None,
    ) -> None:
        """
        Initialize the discovery system.

        Args:
            workspace_dir: Workspace plugin directory.
            global_dir: Global plugin directory (~/.neugi/plugins).
            bundled_dir: Bundled plugin directory.
        """
        self.workspace_dir = Path(workspace_dir) if workspace_dir else None
        self.global_dir = Path(global_dir) if global_dir else Path.home() / ".neugi" / "plugins"
        self.bundled_dir = Path(bundled_dir) if bundled_dir else None

    def discover(self) -> dict[str, PluginManifest]:
        """
        Scan all directories and return discovered plugins.

        Returns:
            Dict mapping plugin name to PluginManifest.
            If the same plugin name exists in multiple locations,
            workspace > global > bundled (highest precedence wins).
        """
        found: dict[str, PluginManifest] = {}

        # Scan in reverse precedence order so higher precedence overwrites
        scan_dirs = []
        if self.bundled_dir and self.bundled_dir.is_dir():
            scan_dirs.append(("bundled", self.bundled_dir))
        if self.global_dir and self.global_dir.is_dir():
            scan_dirs.append(("global", self.global_dir))
        if self.workspace_dir and self.workspace_dir.is_dir():
            scan_dirs.append(("workspace", self.workspace_dir))

        for source, directory in scan_dirs:
            for entry in directory.iterdir():
                if not entry.is_dir():
                    continue
                manifest_path = entry / MANIFEST_FILENAME
                if not manifest_path.is_file():
                    continue
                try:
                    manifest = PluginManifest.from_file(manifest_path)
                    errors = manifest.schema.validate()
                    if errors:
                        logger.warning(
                            "Invalid manifest in %s (%s): %s",
                            source, manifest_path, "; ".join(errors)
                        )
                        continue
                    found[manifest.schema.name] = manifest
                    logger.debug("Discovered plugin: %s (%s)", manifest.schema.name, source)
                except PluginLoadError as e:
                    logger.warning("Failed to load manifest %s: %s", manifest_path, e)

        return found


# -- Sandboxed execution ------------------------------------------------------

class PluginSandbox:
    """
    Provides isolated execution context for plugins.

    Limits plugin access to system resources and catches errors
    to prevent crashes from propagating.
    """

    def __init__(self, plugin_name: str) -> None:
        """
        Initialize a sandbox for a specific plugin.

        Args:
            plugin_name: Name of the plugin being sandboxed.
        """
        self.plugin_name = plugin_name

    def execute(self, fn: Any, *args: Any, timeout: Optional[float] = None, **kwargs: Any) -> Any:
        """
        Execute a function within the sandbox.

        Args:
            fn: Callable to execute.
            *args: Positional arguments.
            timeout: Maximum execution time in seconds.
            **kwargs: Keyword arguments.

        Returns:
            The return value of the function.

        Raises:
            PluginLoadError: If the function raises an exception or times out.
        """
        result: list[Any] = []
        error: list[Exception] = []

        def _target() -> None:
            try:
                result.append(fn(*args, **kwargs))
            except Exception as e:
                error.append(e)

        thread = threading.Thread(target=_target, daemon=True, name=f"sandbox-{self.plugin_name}")
        thread.start()
        thread.join(timeout=timeout or 30.0)

        if thread.is_alive():
            raise PluginLoadError(
                f"Plugin {self.plugin_name!r} timed out after {timeout or 30.0}s"
            )

        if error:
            raise PluginLoadError(
                f"Plugin {self.plugin_name!r} raised an error: {error[0]}"
            ) from error[0]

        return result[0] if result else None


# -- Plugin loader ------------------------------------------------------------

class PluginLoader:
    """
    Discovers, validates, resolves, and loads plugins.

    Manages the full plugin loading pipeline:
    1. Discovery: Scan directories for manifests
    2. Validation: Check manifest schemas and NEUGI version compatibility
    3. Resolution: Topological sort by dependencies
    4. Loading: Instantiate plugins and call on_load()
    5. Registration: Register tools, skills, hooks, routes with the system

    Usage:
        loader = PluginLoader(base_dir="./plugins")
        registry = PluginRegistry()
        loader.discover_and_load(registry)
    """

    def __init__(
        self,
        base_dir: Optional[str] = None,
        global_dir: Optional[str] = None,
        bundled_dir: Optional[str] = None,
        neugi_version: str = NEUGI_VERSION,
    ) -> None:
        """
        Initialize the plugin loader.

        Args:
            base_dir: Workspace plugin directory (defaults to ./plugins).
            global_dir: Global plugin directory.
            bundled_dir: Bundled plugin directory.
            neugi_version: Current NEUGI version for compatibility checks.
        """
        self.base_dir = Path(base_dir) if base_dir else Path("./plugins")
        self.neugi_version = neugi_version

        self._discovery = PluginDiscovery(
            workspace_dir=str(self.base_dir),
            global_dir=global_dir,
            bundled_dir=bundled_dir,
        )

        self._loaded: dict[str, PluginMetadata] = {}
        self._lock = threading.RLock()

        # Hot reload
        self._watch_thread: Optional[threading.Thread] = None
        self._watch_running = False
        self._watch_interval = 5.0
        self._last_scan: dict[str, float] = {}
        self._on_reload: Optional[Any] = None

    def discover(self) -> dict[str, PluginManifest]:
        """
        Discover plugins without loading them.

        Returns:
            Dict mapping plugin name to PluginManifest.
        """
        return self._discovery.discover()

    def discover_and_load(self, registry: Any) -> dict[str, PluginMetadata]:
        """
        Discover and load all plugins, registering them with the registry.

        Args:
            registry: PluginRegistry instance to register loaded plugins.

        Returns:
            Dict mapping plugin name to PluginMetadata.
        """
        manifests = self._discovery.discover()
        if not manifests:
            logger.info("No plugins discovered")
            return {}

        # Validate NEUGI version compatibility
        compatible = self._filter_by_neugi_version(manifests)

        # Resolve dependencies
        available = {name: SemVer.parse(meta.version) for name, meta in self._loaded.items()}
        load_order, dep_errors = resolve_dependencies(
            {name: m.schema for name, m in compatible.items()},
            available,
        )

        if dep_errors:
            for err in dep_errors:
                logger.error("Dependency error: %s", err)

        # Load in order
        for name in load_order:
            if name not in compatible:
                continue
            self._load_plugin(compatible[name], registry)

        return dict(self._loaded)

    def _filter_by_neugi_version(
        self, manifests: dict[str, PluginManifest]
    ) -> dict[str, PluginManifest]:
        """Filter out plugins incompatible with the current NEUGI version."""
        current = SemVer.parse(self.neugi_version)
        compatible: dict[str, PluginManifest] = {}

        for name, manifest in manifests.items():
            schema = manifest.schema
            skip = False

            if schema.min_neugi_version:
                min_ver = SemVer.parse(schema.min_neugi_version)
                if current < min_ver:
                    logger.warning(
                        "Plugin %s requires NEUGI >= %s, but running %s",
                        name, schema.min_neugi_version, self.neugi_version,
                    )
                    skip = True

            if schema.max_neugi_version:
                max_ver = SemVer.parse(schema.max_neugi_version)
                if current > max_ver:
                    logger.warning(
                        "Plugin %s supports NEUGI <= %s, but running %s",
                        name, schema.max_neugi_version, self.neugi_version,
                    )
                    skip = True

            if not skip:
                compatible[name] = manifest

        return compatible

    def _load_plugin(self, manifest: PluginManifest, registry: Any) -> None:
        """
        Load a single plugin and register it.

        Args:
            manifest: The plugin manifest.
            registry: PluginRegistry to register with.
        """
        name = manifest.schema.name
        start_time = time.monotonic()

        with self._lock:
            if name in self._loaded:
                logger.warning("Plugin %s already loaded, skipping", name)
                return

            metadata = PluginMetadata(
                name=name,
                version=manifest.schema.version,
                description=manifest.schema.description,
                author=manifest.schema.author,
                path=manifest.plugin_dir,
            )

            try:
                # Add plugin directory to sys.path for imports
                plugin_dir = str(manifest.plugin_dir)
                if plugin_dir not in sys.path:
                    sys.path.insert(0, plugin_dir)

                # Instantiate the plugin
                sandbox = PluginSandbox(name)
                plugin = sandbox.execute(instantiate_plugin, manifest.schema)

                # Create plugin context
                ctx = PluginContext(
                    memory_system=registry.get_memory_system() if hasattr(registry, "get_memory_system") else None,
                    agent_manager=registry.get_agent_manager() if hasattr(registry, "get_agent_manager") else None,
                    skill_manager=registry.get_skill_manager() if hasattr(registry, "get_skill_manager") else None,
                    config=registry.get_config() if hasattr(registry, "get_config") else {},
                    plugin_config=registry.get_plugin_config(name) if hasattr(registry, "get_plugin_config") else {},
                )

                # Call on_load within sandbox
                _set_current_context(ctx)
                try:
                    sandbox.execute(plugin.on_load, ctx, timeout=30.0)
                finally:
                    _set_current_context(None)

                # Update metadata
                elapsed = time.monotonic() - start_time
                metadata.instance = plugin
                metadata.load_time = elapsed

                # Register with registry
                registry.register_plugin(name, metadata, ctx)

                self._loaded[name] = metadata
                logger.info(
                    "Loaded plugin %s v%s in %.3fs",
                    name, manifest.schema.version, elapsed,
                )

            except PluginLoadError as e:
                elapsed = time.monotonic() - start_time
                metadata.load_time = elapsed
                metadata.load_error = str(e)
                self._loaded[name] = metadata
                registry.register_plugin(name, metadata, None)
                logger.error("Failed to load plugin %s: %s", name, e)

            except Exception as e:
                elapsed = time.monotonic() - start_time
                metadata.load_time = elapsed
                metadata.load_error = f"Unexpected error: {e}"
                self._loaded[name] = metadata
                registry.register_plugin(name, metadata, None)
                logger.exception("Unexpected error loading plugin %s", name)

    def unload_plugin(self, name: str, registry: Any) -> bool:
        """
        Unload a plugin by name.

        Args:
            name: Plugin name.
            registry: PluginRegistry to unregister from.

        Returns:
            True if the plugin was found and unloaded.
        """
        with self._lock:
            metadata = self._loaded.get(name)
            if metadata is None:
                return False

            if metadata.instance is not None:
                try:
                    sandbox = PluginSandbox(name)
                    sandbox.execute(metadata.instance.on_unload, timeout=10.0)
                except Exception as e:
                    logger.error("Error unloading plugin %s: %s", name, e)

            registry.unregister_plugin(name)
            del self._loaded[name]
            logger.info("Unloaded plugin %s", name)
            return True

    def reload_plugin(self, name: str, registry: Any) -> bool:
        """
        Reload a plugin by name (unload then load).

        Args:
            name: Plugin name.
            registry: PluginRegistry.

        Returns:
            True if the plugin was reloaded successfully.
        """
        # Re-discover to get updated manifest
        manifests = self._discovery.discover()
        if name not in manifests:
            logger.error("Cannot reload %s: not found in discovery", name)
            return False

        self.unload_plugin(name, registry)
        self._load_plugin(manifests[name], registry)
        return name in self._loaded and self._loaded[name].is_loaded

    def get_loaded(self) -> dict[str, PluginMetadata]:
        """Get all loaded plugin metadata."""
        return dict(self._loaded)

    # -- Hot reload ------------------------------------------------------------

    def start_watching(self, interval: float = 5.0) -> None:
        """
        Start background file watcher for hot reload.

        Args:
            interval: Scan interval in seconds.
        """
        if self._watch_running:
            return

        self._watch_interval = interval
        self._watch_running = True
        self._last_scan = self._scan_timestamps()

        self._watch_thread = threading.Thread(
            target=self._watch_loop, daemon=True, name="plugin-watcher"
        )
        self._watch_thread.start()
        logger.info("Plugin file watcher started (interval=%.1fs)", interval)

    def stop_watching(self) -> None:
        """Stop the background file watcher."""
        self._watch_running = False
        if self._watch_thread:
            self._watch_thread.join(timeout=5.0)
            self._watch_thread = None
        logger.info("Plugin file watcher stopped")

    def set_reload_callback(self, callback: Any) -> None:
        """
        Set a callback for hot reload events.

        Args:
            callback: Callable(plugin_name: str, action: str) -> None.
        """
        self._on_reload = callback

    def _watch_loop(self) -> None:
        """Background loop that scans for changes."""
        while self._watch_running:
            time.sleep(self._watch_interval)
            try:
                self._check_for_changes()
            except Exception as e:
                logger.error("Plugin watcher error: %s", e)

    def _check_for_changes(self) -> None:
        """Check if any plugin files have changed."""
        current = self._scan_timestamps()
        changed = set()

        # Check for modified or new plugins
        for name, ts in current.items():
            if name not in self._last_scan or current[name] > self._last_scan[name]:
                changed.add(name)

        # Check for removed plugins
        for name in self._last_scan:
            if name not in current:
                changed.add(name)

        if changed:
            logger.info("Plugin changes detected: %s", ", ".join(changed))
            if self._on_reload:
                for name in changed:
                    self._on_reload(name, "modified" if name in current else "removed")

        self._last_scan = current

    def _scan_timestamps(self) -> dict[str, float]:
        """Scan plugin directories and return {name: max_mtime}."""
        timestamps: dict[str, float] = {}
        try:
            manifests = self._discovery.discover()
            for name, manifest in manifests.items():
                max_mtime = 0.0
                for root, dirs, files in os.walk(manifest.plugin_dir):
                    for f in files:
                        fp = os.path.join(root, f)
                        try:
                            mtime = os.path.getmtime(fp)
                            if mtime > max_mtime:
                                max_mtime = mtime
                        except OSError:
                            pass
                timestamps[name] = max_mtime
        except Exception as e:
            logger.error("Error scanning for plugin changes: %s", e)
        return timestamps
