#!/usr/bin/env python3
"""
🤖 NEUGI PLUGIN SYSTEM
======================

Simple plugin system for NEUGI - like OpenClaw skills!

Plugin Structure:
    neugi_plugins/
        my_plugin/
            __init__.py
            plugin.py
            config.json (optional)

Version: 1.0
Date: March 14, 2026
"""

import os
import sys
import json
import importlib.util
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from datetime import datetime


PLUGIN_DIR = os.path.expanduser("~/neugi/plugins")


@dataclass
class Plugin:
    """Plugin definition"""

    id: str
    name: str
    version: str
    description: str
    author: str
    enabled: bool = True
    functions: Dict[str, Callable] = None

    def __post_init__(self):
        if self.functions is None:
            self.functions = {}


class PluginManager:
    """Manage NEUGI plugins"""

    def __init__(self, plugin_dir: str = None):
        self.plugin_dir = plugin_dir or PLUGIN_DIR
        self.plugins: Dict[str, Plugin] = {}
        os.makedirs(self.plugin_dir, exist_ok=True)

    def discover_plugins(self) -> List[Plugin]:
        """Discover all plugins in plugin directory"""
        discovered = []

        if not os.path.exists(self.plugin_dir):
            return discovered

        for item in os.listdir(self.plugin_dir):
            plugin_path = os.path.join(self.plugin_dir, item)

            if not os.path.isdir(plugin_path):
                continue

            # Check for plugin.py or __init__.py
            init_file = os.path.join(plugin_path, "__init__.py")
            plugin_file = os.path.join(plugin_path, "plugin.py")

            if os.path.exists(init_file) or os.path.exists(plugin_file):
                plugin = self._load_plugin(item, plugin_path)
                if plugin:
                    discovered.append(plugin)
                    self.plugins[plugin.id] = plugin

        return discovered

    def _load_plugin(self, plugin_id: str, plugin_path: str) -> Optional[Plugin]:
        """Load a single plugin"""
        try:
            # Load config if exists
            config = {}
            config_file = os.path.join(plugin_path, "config.json")
            if os.path.exists(config_file):
                with open(config_file) as f:
                    config = json.load(f)

            # Try to import
            sys.path.insert(0, plugin_path)

            try:
                # Try plugin.py first
                plugin_file = os.path.join(plugin_path, "plugin.py")
                if os.path.exists(plugin_file):
                    spec = importlib.util.spec_from_file_location("plugin", plugin_file)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                else:
                    # Try __init__.py
                    spec = importlib.util.spec_from_file_location(
                        plugin_id, os.path.join(plugin_path, "__init__.py")
                    )
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                # Get plugin info
                plugin_info = getattr(module, "PLUGIN", {})

                plugin = Plugin(
                    id=plugin_id,
                    name=plugin_info.get("name", plugin_id),
                    version=plugin_info.get("version", "1.0.0"),
                    description=plugin_info.get("description", ""),
                    author=plugin_info.get("author", "Unknown"),
                    enabled=config.get("enabled", True),
                )

                # Extract functions
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if callable(attr) and not attr_name.startswith("_"):
                        plugin.functions[attr_name] = attr

                return plugin

            except Exception as e:
                print(f"Error loading plugin {plugin_id}: {e}")
                return None
            finally:
                sys.path.pop(0)

        except Exception as e:
            print(f"Error loading plugin {plugin_id}: {e}")
            return None

    def enable_plugin(self, plugin_id: str) -> bool:
        """Enable a plugin"""
        if plugin_id in self.plugins:
            self.plugins[plugin_id].enabled = True
            self._save_config(plugin_id)
            return True
        return False

    def disable_plugin(self, plugin_id: str) -> bool:
        """Disable a plugin"""
        if plugin_id in self.plugins:
            self.plugins[plugin_id].enabled = False
            self._save_config(plugin_id)
            return True
        return False

    def _save_config(self, plugin_id: str):
        """Save plugin config"""
        plugin = self.plugins[plugin_id]
        plugin_path = os.path.join(self.plugin_dir, plugin_id, "config.json")

        config = {"enabled": plugin.enabled}

        with open(plugin_path, "w") as f:
            json.dump(config, f, indent=2)

    def execute(self, plugin_id: str, function_name: str, *args, **kwargs) -> Any:
        """Execute a plugin function"""
        if plugin_id not in self.plugins:
            return {"error": f"Plugin {plugin_id} not found"}

        plugin = self.plugins[plugin_id]

        if not plugin.enabled:
            return {"error": f"Plugin {plugin_id} is disabled"}

        if function_name not in plugin.functions:
            return {
                "error": f"Function {function_name} not found in plugin {plugin_id}"
            }

        try:
            func = plugin.functions[function_name]
            return func(*args, **kwargs)
        except Exception as e:
            return {"error": str(e)}

    def list_plugins(self) -> List[Dict]:
        """List all plugins"""
        return [
            {
                "id": p.id,
                "name": p.name,
                "version": p.version,
                "description": p.description,
                "author": p.author,
                "enabled": p.enabled,
                "functions": list(p.functions.keys()),
            }
            for p in self.plugins.values()
        ]


# Example plugin template
EXAMPLE_PLUGIN = '''
"""
Example NEUGI Plugin
=====================
Copy this to ~/neugi/plugins/my_plugin/
"""

# Plugin metadata
PLUGIN = {
    "name": "My Plugin",
    "version": "1.0.0",
    "description": "A sample plugin for NEUGI",
    "author": "Your Name",
}

# Plugin functions
def hello(name="World"):
    """Say hello"""
    return f"Hello, {name}! From NEUGI Plugin!"

def add(a, b):
    """Add two numbers"""
    return a + b

def process(data):
    """Process some data"""
    return {"processed": True, "data": data}
'''


def create_example_plugin(name: str = "example"):
    """Create example plugin"""
    plugin_dir = os.path.join(PLUGIN_DIR, name)
    os.makedirs(plugin_dir, exist_ok=True)

    with open(os.path.join(plugin_dir, "plugin.py"), "w") as f:
        f.write(EXAMPLE_PLUGIN)

    print(f"Example plugin created at: {plugin_dir}")


# CLI
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="NEUGI Plugin Manager")
    parser.add_argument(
        "action", choices=["list", "enable", "disable", "create"], help="Action"
    )
    parser.add_argument("plugin", nargs="?", help="Plugin ID")

    args = parser.parse_args()

    manager = PluginManager()

    if args.action == "list":
        plugins = manager.discover_plugins()
        print(f"\\n🤖 NEUGI Plugins ({len(plugins)} found)")
        print("=" * 50)
        for p in manager.list_plugins():
            status = "✅" if p["enabled"] else "❌"
            print(f"{status} {p['name']} v{p['version']}")
            print(f"   {p['description']}")
            print(f"   Functions: {', '.join(p['functions'])}")
            print()

    elif args.action == "enable" and args.plugin:
        manager.enable_plugin(args.plugin)
        print(f"Enabled: {args.plugin}")

    elif args.action == "disable" and args.plugin:
        manager.disable_plugin(args.plugin)
        print(f"Disabled: {args.plugin}")

    elif args.action == "create":
        create_example_plugin(args.plugin if args.plugin else "example")
