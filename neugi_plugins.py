#!/usr/bin/env python3
"""
🤖 NEUGI PLUGIN SYSTEM
======================

Advanced plugin system for NEUGI - compatible with multiple formats!

Plugin Sources:
- Native: Python modules in ~/neugi/plugins/
- MCP: Model Context Protocol plugins
- URL: Install from GitHub/GitLab
- Marketplace: Browse and install community plugins

Plugin Structure:
    neugi_plugins/
        my_plugin/
            __init__.py
            plugin.py
            config.json (optional)
            manifest.json (for MCP)

Version: 15.2.0
Date: March 14, 2026
"""

import os
import sys
import json
import importlib.util
import requests
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlparse


PLUGIN_DIR = os.path.expanduser("~/neugi/plugins")
WORKSPACE_PLUGIN_DIR = os.path.expanduser("~/neugi/workspace/plugins")


class PluginSource(Enum):
    NATIVE = "native"
    MCP = "mcp"
    URL = "url"
    MARKETPLACE = "marketplace"


class PluginType(Enum):
    CORE = "core"
    TELEGRAM = "telegram"
    VOICE = "voice"
    GATEWAY = "gateway"
    SECURITY = "security"
    DATABASE = "database"
    UI = "ui"
    CUSTOM = "custom"


@dataclass
class Plugin:
    """Plugin definition"""

    id: str
    name: str
    version: str
    description: str
    author: str
    plugin_type: PluginType = PluginType.CUSTOM
    source: PluginSource = PluginSource.NATIVE
    enabled: bool = True
    functions: Dict[str, Callable] = field(default_factory=dict)
    config: Dict = field(default_factory=dict)
    repository: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    manifest: Optional[Dict] = None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "type": self.plugin_type.value,
            "source": self.source.value,
            "enabled": self.enabled,
            "functions": list(self.functions.keys()),
            "repository": self.repository,
        }

    def to_mcp_manifest(self) -> Dict:
        """Export as MCP plugin manifest"""
        return {
            "name": self.id,
            "version": self.version,
            "description": self.description,
            "tools": [
                {
                    "name": f"{self.id}_{func_name}",
                    "description": f"Function {func_name} from {self.name}",
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                    },
                }
                for func_name in self.functions.keys()
            ],
        }


class PluginManager:
    """Advanced plugin manager with MCP and URL support"""

    def __init__(self, plugin_dir: str = None):
        self.plugin_dir = plugin_dir or PLUGIN_DIR
        self.plugins: Dict[str, Plugin] = {}
        self._ensure_directories()
        self._discover_all_plugins()

    def _ensure_directories(self):
        """Ensure plugin directories exist"""
        os.makedirs(self.plugin_dir, exist_ok=True)
        os.makedirs(WORKSPACE_PLUGIN_DIR, exist_ok=True)

    def _discover_all_plugins(self):
        """Discover all plugins from all sources"""
        # Native plugins
        self._discover_native_plugins(self.plugin_dir)
        # Workspace plugins
        self._discover_native_plugins(WORKSPACE_PLUGIN_DIR)

    def _discover_native_plugins(self, plugin_dir: str):
        """Discover native plugins"""
        if not os.path.exists(plugin_dir):
            return

        for item in os.listdir(plugin_dir):
            plugin_path = os.path.join(plugin_dir, item)

            if not os.path.isdir(plugin_path):
                continue

            init_file = os.path.join(plugin_path, "__init__.py")
            plugin_file = os.path.join(plugin_path, "plugin.py")
            manifest_file = os.path.join(plugin_path, "manifest.json")

            # Check for MCP manifest first
            if os.path.exists(manifest_file):
                self._load_mcp_plugin(item, plugin_path)
            elif os.path.exists(init_file) or os.path.exists(plugin_file):
                self._load_native_plugin(item, plugin_path)

    def _load_native_plugin(self, plugin_id: str, plugin_path: str):
        """Load native Python plugin"""
        try:
            config = {}
            config_file = os.path.join(plugin_path, "config.json")
            if os.path.exists(config_file):
                with open(config_file) as f:
                    config = json.load(f)

            sys.path.insert(0, plugin_path)

            try:
                plugin_file = os.path.join(plugin_path, "plugin.py")
                if os.path.exists(plugin_file):
                    spec = importlib.util.spec_from_file_location("plugin", plugin_file)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                else:
                    spec = importlib.util.spec_from_file_location(
                        plugin_id, os.path.join(plugin_path, "__init__.py")
                    )
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                plugin_info = getattr(module, "PLUGIN", {})

                plugin = Plugin(
                    id=plugin_id,
                    name=plugin_info.get("name", plugin_id),
                    version=plugin_info.get("version", "1.0.0"),
                    description=plugin_info.get("description", ""),
                    author=plugin_info.get("author", "Unknown"),
                    plugin_type=PluginType(plugin_info.get("type", "custom")),
                    source=PluginSource.NATIVE,
                    enabled=config.get("enabled", True),
                    config=config,
                )

                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if callable(attr) and not attr_name.startswith("_"):
                        plugin.functions[attr_name] = attr

                self.plugins[plugin.id] = plugin

            finally:
                sys.path.pop(0)

        except Exception as e:
            print(f"Error loading plugin {plugin_id}: {e}")

    def _load_mcp_plugin(self, plugin_id: str, plugin_path: str):
        """Load MCP (Model Context Protocol) plugin"""
        try:
            manifest_file = os.path.join(plugin_path, "manifest.json")
            with open(manifest_file) as f:
                manifest = json.load(f)

            config = {}
            config_file = os.path.join(plugin_path, "config.json")
            if os.path.exists(config_file):
                with open(config_file) as f:
                    config = json.load(f)

            plugin = Plugin(
                id=plugin_id,
                name=manifest.get("name", plugin_id),
                version=manifest.get("version", "1.0.0"),
                description=manifest.get("description", ""),
                author=manifest.get("author", "Unknown"),
                plugin_type=PluginType.CUSTOM,
                source=PluginSource.MCP,
                enabled=config.get("enabled", True),
                config=config,
                manifest=manifest,
            )

            # Load tools from manifest
            for tool in manifest.get("tools", []):
                tool_name = tool.get("name", "")
                if tool_name:
                    plugin.functions[tool_name] = lambda **kwargs: {
                        "tool": tool_name,
                        "result": f"MCP tool {tool_name} called",
                    }

            self.plugins[plugin.id] = plugin

        except Exception as e:
            print(f"Error loading MCP plugin {plugin_id}: {e}")

    def install_from_url(self, url: str) -> Dict:
        """Install plugin from GitHub/GitLab URL"""
        try:
            parsed = urlparse(url)
            if "github.com" in parsed.netloc:
                return self._install_from_github(url)
            elif "gitlab.com" in parsed.netloc:
                return self._install_from_gitlab(url)
            else:
                return {"error": f"Unsupported URL: {url}"}
        except Exception as e:
            return {"error": str(e)}

    def _install_from_github(self, url: str) -> Dict:
        """Install from GitHub"""
        try:
            # Extract owner/repo from URL
            parts = url.rstrip("/").split("/")
            owner = parts[-2]
            repo = parts[-1].replace(".git", "")

            # Download main files
            api_url = f"https://api.github.com/repos/{owner}/{repo}/contents"
            response = requests.get(api_url, timeout=10)

            if not response.ok:
                return {"error": "Failed to fetch repository"}

            plugin_id = repo.lower().replace("-", "_")
            plugin_path = os.path.join(self.plugin_dir, plugin_id)
            os.makedirs(plugin_path, exist_ok=True)

            # Download files
            for item in response.json():
                if item["type"] == "file" and item["name"].endswith((".py", ".json", ".md")):
                    file_url = item["download_url"]
                    file_response = requests.get(file_url, timeout=10)
                    if file_response.ok:
                        file_path = os.path.join(plugin_path, item["name"])
                        with open(file_path, "w") as f:
                            f.write(file_response.text)

            # Create manifest if not exists
            manifest = {
                "name": repo,
                "version": "1.0.0",
                "description": f"Installed from GitHub: {url}",
                "author": owner,
                "tools": [],
            }
            with open(os.path.join(plugin_path, "manifest.json"), "w") as f:
                json.dump(manifest, f, indent=2)

            # Reload plugins
            self._discover_all_plugins()

            return {
                "status": "success",
                "message": f"Installed plugin: {plugin_id}",
                "path": plugin_path,
            }

        except Exception as e:
            return {"error": str(e)}

    def _install_from_gitlab(self, url: str) -> Dict:
        """Install from GitLab (similar to GitHub)"""
        return self._install_from_github(url)

    def search_marketplace(self, query: str = "") -> List[Dict]:
        """Search NEUGI marketplace (mock for now)"""
        # This would connect to a real marketplace in production
        mock_plugins = [
            {
                "id": "telegram-pro",
                "name": "Telegram Pro",
                "description": "Advanced Telegram bot with more features",
                "author": "NEUGI Team",
                "version": "1.0.0",
                "installs": 1234,
            },
            {
                "id": "slack-integration",
                "name": "Slack Integration",
                "description": "Send notifications to Slack",
                "author": "Community",
                "version": "1.0.0",
                "installs": 890,
            },
            {
                "id": "database-pro",
                "name": "Database Pro",
                "description": "Advanced database operations",
                "author": "NEUGI Team",
                "version": "1.0.0",
                "installs": 567,
            },
            {
                "id": "voice-premium",
                "name": "Voice Premium",
                "description": "Premium voice features",
                "author": "Community",
                "version": "1.0.0",
                "installs": 432,
            },
        ]

        if query:
            query = query.lower()
            return [
                p
                for p in mock_plugins
                if query in p["name"].lower() or query in p["description"].lower()
            ]

        return mock_plugins

    def install_from_marketplace(self, plugin_id: str) -> Dict:
        """Install plugin from marketplace"""
        marketplace_plugins = {
            "telegram-pro": "https://github.com/neugi-plugins/telegram-pro",
            "slack-integration": "https://github.com/neugi-plugins/slack",
            "database-pro": "https://github.com/neugi-plugins/database-pro",
            "voice-premium": "https://github.com/neugi-plugins/voice-premium",
        }

        if plugin_id not in marketplace_plugins:
            return {"error": f"Plugin {plugin_id} not found in marketplace"}

        return self.install_from_url(marketplace_plugins[plugin_id])

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
        os.makedirs(os.path.dirname(plugin_path), exist_ok=True)

        config = {"enabled": plugin.enabled, **plugin.config}

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
            return {"error": f"Function {function_name} not found in plugin {plugin_id}"}

        try:
            func = plugin.functions[function_name]
            return func(*args, **kwargs)
        except Exception as e:
            return {"error": str(e)}

    def list_plugins(self, source: PluginSource = None) -> List[Dict]:
        """List all plugins, optionally filtered by source"""
        plugins = self.plugins.values()
        if source:
            plugins = [p for p in plugins if p.source == source]
        return [p.to_dict() for p in plugins]

    def list_by_type(self, plugin_type: PluginType) -> List[Dict]:
        """List plugins by type"""
        return [p.to_dict() for p in self.plugins.values() if p.plugin_type == plugin_type]

    def get_plugin(self, plugin_id: str) -> Optional[Plugin]:
        """Get a specific plugin"""
        return self.plugins.get(plugin_id)

    def uninstall_plugin(self, plugin_id: str) -> Dict:
        """Uninstall a plugin"""
        if plugin_id not in self.plugins:
            return {"error": f"Plugin {plugin_id} not found"}

        plugin_path = os.path.join(self.plugin_dir, plugin_id)
        if os.path.exists(plugin_path):
            import shutil

            shutil.rmtree(plugin_path)

        del self.plugins[plugin_id]

        return {"status": "success", "message": f"Uninstalled: {plugin_id}"}

    def export_plugin(self, plugin_id: str, format: str = "native") -> Optional[str]:
        """Export plugin to specified format"""
        plugin = self.get_plugin(plugin_id)
        if not plugin:
            return None

        if format == "mcp":
            return json.dumps(plugin.to_mcp_manifest(), indent=2)
        elif format == "native":
            return json.dumps(plugin.to_dict(), indent=2)

        return None


# Example plugin template
EXAMPLE_PLUGIN = '''
"""Example NEUGI Plugin"""

PLUGIN = {
    "name": "My Plugin",
    "version": "1.0.0",
    "description": "A sample plugin for NEUGI",
    "author": "Your Name",
    "type": "custom",
}

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

# Example MCP plugin manifest
EXAMPLE_MCP_MANIFEST = {
    "name": "my_mcp_plugin",
    "version": "1.0.0",
    "description": "An MCP-compatible plugin",
    "author": "Your Name",
    "tools": [
        {
            "name": "calculate",
            "description": "Perform calculations",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Math expression to evaluate",
                    }
                },
                "required": ["expression"],
            },
        },
        {
            "name": "convert",
            "description": "Convert units",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "value": {"type": "number"},
                    "from": {"type": "string"},
                    "to": {"type": "string"},
                },
                "required": ["value", "from", "to"],
            },
        },
    ],
}


def create_example_plugin(name: str = "example", mcp: bool = False):
    """Create example plugin"""
    plugin_dir = os.path.join(PLUGIN_DIR, name)
    os.makedirs(plugin_dir, exist_ok=True)

    if mcp:
        with open(os.path.join(plugin_dir, "manifest.json"), "w") as f:
            json.dump(EXAMPLE_MCP_MANIFEST, f, indent=2)
    else:
        with open(os.path.join(plugin_dir, "plugin.py"), "w") as f:
            f.write(EXAMPLE_PLUGIN)

    print(f"Example plugin created at: {plugin_dir}")
    print(f"Type: {'MCP' if mcp else 'Native'}")


# CLI
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="NEUGI Plugin Manager")
    parser.add_argument(
        "action",
        choices=["list", "enable", "disable", "create", "install", "uninstall", "marketplace"],
        help="Action",
    )
    parser.add_argument("plugin", nargs="?", help="Plugin ID or URL")
    parser.add_argument("--mcp", action="store_true", help="Create MCP plugin")
    parser.add_argument("--source", help="Filter by source (native/mcp/url/marketplace)")

    args = parser.parse_args()

    manager = PluginManager()

    if args.action == "list":
        source_filter = PluginSource(args.source) if args.source else None
        plugins = manager.list_plugins(source_filter)
        print(f"\n🤖 NEUGI Plugins ({len(plugins)} found)")
        print("=" * 50)
        for p in plugins:
            status = "✅" if p["enabled"] else "❌"
            print(f"{status} {p['name']} v{p['version']} [{p['source']}]")
            print(f"   {p['description']}")
            print(f"   Type: {p['type']}, Author: {p['author']}")
            print(f"   Functions: {', '.join(p.get('functions', []))}")
            print()

    elif args.action == "enable" and args.plugin:
        manager.enable_plugin(args.plugin)
        print(f"Enabled: {args.plugin}")

    elif args.action == "disable" and args.plugin:
        manager.disable_plugin(args.plugin)
        print(f"Disabled: {args.plugin}")

    elif args.action == "create":
        create_example_plugin(args.plugin if args.plugin else "example", args.mcp)

    elif args.action == "install" and args.plugin:
        if args.plugin.startswith("http"):
            result = manager.install_from_url(args.plugin)
        else:
            result = manager.install_from_marketplace(args.plugin)
        print(json.dumps(result, indent=2))

    elif args.action == "uninstall" and args.plugin:
        result = manager.uninstall_plugin(args.plugin)
        print(json.dumps(result, indent=2))

    elif args.action == "marketplace":
        plugins = manager.search_marketplace(args.plugin if args.plugin else "")
        print("\n🛒 NEUGI Marketplace")
        print("=" * 50)
        for p in plugins:
            print(f"📦 {p['name']} v{p['version']}")
            print(f"   {p['description']}")
            print(f"   By: {p['author']} | Installs: {p['installs']}")
            print(f"   Install: neugi plugins install {p['id']}")
            print()
