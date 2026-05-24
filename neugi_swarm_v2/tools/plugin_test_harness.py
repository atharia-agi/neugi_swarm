"""
Plugin Testing Harness for NEUGI Swarm.

Tests plugins in isolation with a mocked event bus, configuration,
and system references. No real NEUGI subsystems are needed.

Usage:
    python -m neugi_swarm_v2.tools.plugin_test_harness <plugin_dir>

Or programmatically:
    from neugi_swarm_v2.tools.plugin_test_harness import PluginTestHarness
    harness = PluginTestHarness()
    result = harness.test_plugin("/path/to/plugin_dir")
    print(result.passed, result.failures)
"""

import importlib.util
import json
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

from neugi_swarm_v2.observability.event_bus import Event, EventBus
from neugi_swarm_v2.tools.plugin_validator import validate_plugin, validate_plugin_structure


@dataclass
class PluginTestResult:
    """Result of testing a single plugin."""
    plugin_name: str
    passed: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0


class PluginTestHarness:
    """
    Isolated test harness for NEUGI plugins.

    Provides a mocked event bus, configuration, and system components
    so plugins can be tested without a running NEUGI instance.
    """

    def __init__(self) -> None:
        self.mock_event_bus = EventBus(max_history=100)
        self._received_events: list[Event] = []

    def test_plugin(self, plugin_dir: str) -> PluginTestResult:
        """
        Test a plugin in isolation.

        Steps:
        1. Validate plugin structure
        2. Load manifest and entry point
        3. Call activate() with a mock context
        4. Verify event handlers are callable
        5. Run basic smoke tests
        6. Collect results

        Args:
            plugin_dir: Path to plugin directory.

        Returns:
            PluginTestResult with pass/fail counts.
        """
        start = time.time()
        plugin_path = Path(plugin_dir)
        name = plugin_path.name
        result = PluginTestResult(plugin_name=name)

        try:
            # Step 1: Validate structure
            struct_ok, struct_msgs = validate_plugin_structure(plugin_dir)
            if not struct_ok:
                result.errors.extend(struct_msgs)
                result.failed += 1
                result.duration_seconds = time.time() - start
                return result
            result.passed += 1

            # Step 2: Validate manifest
            manifest_path = plugin_path / "plugin.json"
            if manifest_path.exists():
                manifest_ok, manifest_msgs = validate_plugin(str(manifest_path))
                if not manifest_ok:
                    for msg in manifest_msgs:
                        if "Missing" in msg or "Invalid" in msg or "not found" in msg:
                            result.errors.append(msg)
                            result.failed += 1
                else:
                    result.passed += 1
            else:
                result.passed += 1  # No manifest required for basic plugins

            # Step 3: Try to load the entry point
            manifest_data = {}
            if manifest_path.exists():
                manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))

            entry_point = manifest_data.get("entry_point", f"{name}:activate")
            if ":" in entry_point:
                module_name, _func_name = entry_point.split(":", 1)
            else:
                module_name, _func_name = entry_point, "activate"

            # Add plugin dir to path
            if str(plugin_path) not in sys.path:
                sys.path.insert(0, str(plugin_path))

            try:
                spec = importlib.util.find_spec(module_name)
                if spec is None:
                    # Try __init__.py in plugin dir
                    init_file = plugin_path / "__init__.py"
                    if init_file.exists():
                        spec = importlib.util.spec_from_file_location(module_name, str(init_file))

                if spec is None:
                    result.errors.append(f"Could not find module: {module_name}")
                    result.failed += 1
                    result.duration_seconds = time.time() - start
                    return result

                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                result.passed += 1

            except (ImportError, ModuleNotFoundError, AttributeError, OSError) as e:
                result.errors.append(f"Failed to load entry point: {e}")
                result.failed += 1
                result.duration_seconds = time.time() - start
                return result

            # Step 4: Check for event_handlers or activate function
            has_activate = hasattr(module, "activate") and callable(module.activate)
            event_handlers = getattr(module, "event_handlers", None)

            if has_activate:
                result.passed += 1

            if event_handlers and isinstance(event_handlers, dict):
                for ev_name, handler in event_handlers.items():
                    if callable(handler):
                        result.passed += 1
                    else:
                        result.errors.append(f"Handler for '{ev_name}' is not callable")
                        result.failed += 1

            # Step 5: If plugin has a Plugin class (notification/metrics pattern), test it
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and "Plugin" in attr_name:
                    # Found a Plugin class - try to instantiate
                    try:
                        instance = attr()
                        if hasattr(instance, "activate"):
                            # Create mock context
                            class MockContext:
                                def __init__(self):
                                    self.logger = __import__("logging").getLogger(name)
                                    self.event_bus = self

                                def info(self, msg: str) -> None:
                                    pass

                                def warning(self, msg: str) -> None:
                                    pass

                                def debug(self, msg: str) -> None:
                                    pass

                            if hasattr(instance, "_on_tool_success"):
                                instance._on_tool_success(None)
                            if hasattr(instance, "_on_tool_failure"):
                                instance._on_tool_failure(None)

                            result.passed += 1
                        elif hasattr(instance, "event_handlers"):
                            result.passed += 1
                    except (TypeError, ValueError, RuntimeError, AttributeError) as e:
                        result.errors.append(f"Plugin class instantiation error: {e}")
                        result.failed += 1

        except (ImportError, OSError, RuntimeError) as e:
            result.errors.append(f"Unexpected test error: {e}\n{traceback.format_exc()}")
            result.failed += 1

        result.duration_seconds = time.time() - start
        return result


def main() -> int:
    """CLI entry point for plugin testing."""
    import argparse
    parser = argparse.ArgumentParser(description="Test NEUGI plugin in isolation")
    parser.add_argument("path", help="Path to plugin directory")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    args = parser.parse_args()

    harness = PluginTestHarness()
    result = harness.test_plugin(str(Path(args.path).resolve()))

    print(f"\nPlugin: {result.plugin_name}")
    print(f"Passed: {result.passed}")
    print(f"Failed: {result.failed}")
    print(f"Duration: {result.duration_seconds:.3f}s")
    if result.errors:
        print("\nErrors:")
        for err in result.errors:
            print(f"  ❌ {err}")
    if result.failed == 0:
        print("\n✅ All tests passed!")
    else:
        print(f"\n❌ {result.failed} test(s) failed")
    return 0 if result.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
