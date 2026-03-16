#!/usr/bin/env python3
"""
🤖 NEUGI PLUGIN MARKETPLACE
==============================

Browse and install plugins:
- Official plugins
- Community plugins
- Install/Uninstall
- Ratings & reviews

Version: 1.0
Date: March 16, 2026
"""

import os
import json
from typing import List, Dict, Optional

NEUGI_DIR = os.path.expanduser("~/neugi")
MARKETPLACE_CACHE = os.path.join(NEUGI_DIR, "marketplace_cache.json")


class PluginMarketplace:
    """Plugin marketplace"""

    OFFICIAL_PLUGINS = [
        {
            "id": "github-integration",
            "name": "GitHub Integration",
            "description": "Connect to GitHub, manage repos, PRs, issues",
            "author": "NEUGI Team",
            "version": "1.0.0",
            "category": "integrations",
            "icon": "🐙",
            "installed": False,
            "rating": 4.8,
            "downloads": 15420,
        },
        {
            "id": "slack-notify",
            "name": "Slack Notifications",
            "description": "Send notifications to Slack channels",
            "author": "NEUGI Team",
            "version": "1.0.0",
            "category": "notifications",
            "icon": "💬",
            "installed": False,
            "rating": 4.5,
            "downloads": 8930,
        },
        {
            "id": "database-postgres",
            "name": "PostgreSQL Support",
            "description": "Connect to PostgreSQL databases",
            "author": "NEUGI Team",
            "version": "1.0.0",
            "category": "database",
            "icon": "🐘",
            "installed": False,
            "rating": 4.7,
            "downloads": 6540,
        },
        {
            "id": "browser-automation",
            "name": "Browser Automation",
            "description": "Automate browser actions with Playwright",
            "author": "NEUGI Team",
            "version": "1.0.0",
            "category": "automation",
            "icon": "🌐",
            "installed": False,
            "rating": 4.9,
            "downloads": 12340,
        },
        {
            "id": "voice-tts",
            "name": "Text-to-Speech",
            "description": "Convert text to speech output",
            "author": "NEUGI Team",
            "version": "1.0.0",
            "category": "audio",
            "icon": "🔊",
            "installed": False,
            "rating": 4.3,
            "downloads": 5670,
        },
        {
            "id": "image-generator",
            "name": "Image Generator",
            "description": "Generate images with AI models",
            "author": "NEUGI Team",
            "version": "1.0.0",
            "category": "ai",
            "icon": "🎨",
            "installed": False,
            "rating": 4.6,
            "downloads": 9870,
        },
        {
            "id": "pdf-tools",
            "name": "PDF Tools",
            "description": "Read, write, and manipulate PDF files",
            "author": "NEUGI Team",
            "version": "1.0.0",
            "category": "utilities",
            "icon": "📄",
            "installed": False,
            "rating": 4.4,
            "downloads": 4320,
        },
        {
            "id": "calendar-sync",
            "name": "Calendar Sync",
            "description": "Sync with Google Calendar",
            "author": "NEUGI Team",
            "version": "1.0.0",
            "category": "integrations",
            "icon": "📅",
            "installed": False,
            "rating": 4.2,
            "downloads": 3210,
        },
        {
            "id": "code-formatter",
            "name": "Code Formatter",
            "description": "Format code with Prettier/Black",
            "author": "NEUGI Team",
            "version": "1.0.0",
            "category": "developer",
            "icon": "✨",
            "installed": False,
            "rating": 4.8,
            "downloads": 7650,
        },
        {
            "id": "terminal multiplexer",
            "name": "Terminal Multiplexer",
            "description": "Multiple terminal sessions",
            "author": "NEUGI Team",
            "version": "1.0.0",
            "category": "developer",
            "icon": "🖥️",
            "installed": False,
            "rating": 4.5,
            "downloads": 5430,
        },
        {
            "id": "email-client",
            "name": "Email Client",
            "description": "Full email client functionality",
            "author": "NEUGI Team",
            "version": "1.0.0",
            "category": "communications",
            "icon": "📧",
            "installed": False,
            "rating": 4.1,
            "downloads": 2890,
        },
        {
            "id": "video-calls",
            "name": "Video Calls",
            "description": "Video call integration",
            "author": "NEUGI Team",
            "version": "1.0.0",
            "category": "communications",
            "icon": "📹",
            "installed": False,
            "rating": 4.0,
            "downloads": 2100,
        },
    ]

    CATEGORIES = [
        {"id": "all", "name": "All Plugins", "icon": "📦"},
        {"id": "integrations", "name": "Integrations", "icon": "🔗"},
        {"id": "automation", "name": "Automation", "icon": "🤖"},
        {"id": "database", "name": "Database", "icon": "🗄️"},
        {"id": "ai", "name": "AI & ML", "icon": "🧠"},
        {"id": "developer", "name": "Developer Tools", "icon": "👨‍💻"},
        {"id": "notifications", "name": "Notifications", "icon": "🔔"},
        {"id": "communications", "name": "Communications", "icon": "💬"},
        {"id": "utilities", "name": "Utilities", "icon": "🔧"},
        {"id": "audio", "name": "Audio", "icon": "🔊"},
    ]

    def __init__(self):
        self.plugins = self._load_plugins()

    def _load_plugins(self) -> List[Dict]:
        """Load plugins from cache or use official"""
        if os.path.exists(MARKETPLACE_CACHE):
            try:
                with open(MARKETPLACE_CACHE) as f:
                    return json.load(f)
            except:
                pass

        installed = self._get_installed_plugins()

        plugins = []
        for plugin in self.OFFICIAL_PLUGINS:
            p = plugin.copy()
            p["installed"] = plugin["id"] in installed
            plugins.append(p)

        return plugins

    def _get_installed_plugins(self) -> set:
        """Get installed plugin IDs"""
        installed = set()

        plugins_dir = os.path.join(NEUGI_DIR, "plugins")
        if os.path.exists(plugins_dir):
            for item in os.listdir(plugins_dir):
                if os.path.isdir(os.path.join(plugins_dir, item)):
                    installed.add(item)

        return installed

    def list_plugins(self, category: str = "all", search: str = None) -> List[Dict]:
        """List plugins"""
        plugins = self.plugins

        if category != "all":
            plugins = [p for p in plugins if p.get("category") == category]

        if search:
            search = search.lower()
            plugins = [
                p
                for p in plugins
                if search in p["name"].lower() or search in p["description"].lower()
            ]

        return plugins

    def get_plugin(self, plugin_id: str) -> Optional[Dict]:
        """Get plugin details"""
        for plugin in self.plugins:
            if plugin["id"] == plugin_id:
                return plugin
        return None

    def install_plugin(self, plugin_id: str) -> Dict:
        """Install plugin"""
        plugin = self.get_plugin(plugin_id)

        if not plugin:
            return {"success": False, "error": "Plugin not found"}

        if plugin.get("installed"):
            return {"success": False, "error": "Plugin already installed"}

        plugins_dir = os.path.join(NEUGI_DIR, "plugins", plugin_id)
        os.makedirs(plugins_dir, exist_ok=True)

        init_file = os.path.join(plugins_dir, "__init__.py")
        with open(init_file, "w") as f:
            f.write(f'"""\n{plugin["name"]}\n{plugin["description"]}\n"""\n\n')
            f.write(f'__version__ = "{plugin["version"]}"\n')
            f.write(f'__author__ = "{plugin["author"]}"\n')

        for p in self.plugins:
            if p["id"] == plugin_id:
                p["installed"] = True
                break

        self._save_cache()

        return {"success": True, "message": f"Installed {plugin['name']}"}

    def uninstall_plugin(self, plugin_id: str) -> Dict:
        """Uninstall plugin"""
        plugin = self.get_plugin(plugin_id)

        if not plugin:
            return {"success": False, "error": "Plugin not found"}

        if not plugin.get("installed"):
            return {"success": False, "error": "Plugin not installed"}

        plugins_dir = os.path.join(NEUGI_DIR, "plugins", plugin_id)

        import shutil

        if os.path.exists(plugins_dir):
            shutil.rmtree(plugins_dir)

        for p in self.plugins:
            if p["id"] == plugin_id:
                p["installed"] = False
                break

        self._save_cache()

        return {"success": True, "message": f"Uninstalled {plugin['name']}"}

    def _save_cache(self):
        """Save plugins cache"""
        with open(MARKETPLACE_CACHE, "w") as f:
            json.dump(self.plugins, f, indent=2)

    def get_categories(self) -> List[Dict]:
        """Get categories"""
        return self.CATEGORIES


def main():
    import argparse

    parser = argparse.ArgumentParser(description="NEUGI Plugin Marketplace")
    parser.add_argument("--list", action="store_true", help="List plugins")
    parser.add_argument("--category", type=str, help="Filter by category")
    parser.add_argument("--search", type=str, help="Search plugins")
    parser.add_argument("--install", type=str, help="Install plugin")
    parser.add_argument("--uninstall", type=str, help="Uninstall plugin")
    parser.add_argument("--categories", action="store_true", help="List categories")

    args = parser.parse_args()

    marketplace = PluginMarketplace()

    if args.categories:
        print("\n📁 Categories:\n")
        for cat in marketplace.get_categories():
            print(f"  {cat['icon']} {cat['name']}")

    elif args.list:
        plugins = marketplace.list_plugins(args.category or "all", args.search)
        print(f"\n📦 Plugins ({len(plugins)}):\n")
        for p in plugins:
            status = "✅" if p.get("installed") else "○"
            print(f"  {status} {p['icon']} {p['name']}")
            print(f"      {p['description']}")
            print(f"      ⭐ {p.get('rating', 0)} | 📥 {p.get('downloads', 0)}")
            print()

    elif args.install:
        result = marketplace.install_plugin(args.install)
        print(result.get("message") or result.get("error"))

    elif args.uninstall:
        result = marketplace.uninstall_plugin(args.uninstall)
        print(result.get("message") or result.get("error"))

    else:
        print("NEUGI Plugin Marketplace")
        print(
            "Usage: python -m neugi_marketplace [--list] [--category CAT] [--search TERM] [--install ID] [--uninstall ID]"
        )


if __name__ == "__main__":
    main()
