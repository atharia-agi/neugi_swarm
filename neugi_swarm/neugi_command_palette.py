#!/usr/bin/env python3
"""
🤖 NEUGI COMMAND PALETTE
==========================

Ctrl+K command palette for quick access:
- Quick actions
- Search commands
- Recent items
- File search

Version: 1.0
Date: March 16, 2026
"""

import os
import json
import subprocess
from typing import List, Dict, Optional, Any
from datetime import datetime
from pathlib import Path

NEUGI_DIR = os.path.expanduser("~/neugi")
HISTORY_FILE = os.path.join(NEUGI_DIR, "command_palette_history.json")


class CommandPalette:
    """Command Palette with fuzzy search"""

    COMMANDS = [
        {"id": "chat", "label": "Chat with AI", "category": "AI", "icon": "💬", "shortcut": "c"},
        {
            "id": "heartbeat",
            "label": "Sovereign Heartbeat",
            "category": "System",
            "icon": "💓",
            "shortcut": "h",
        },
        {
            "id": "topology",
            "label": "Network Topology",
            "category": "System",
            "icon": "🌐",
            "shortcut": "t",
        },
        {
            "id": "monitor",
            "label": "Live Monitor",
            "category": "System",
            "icon": "📊",
            "shortcut": "m",
        },
        {"id": "logs", "label": "View Logs", "category": "System", "icon": "📄", "shortcut": "l"},
        {
            "id": "setup",
            "label": "Setup/Install",
            "category": "System",
            "icon": "🎯",
            "shortcut": "s",
        },
        {
            "id": "repair",
            "label": "Repair System",
            "category": "System",
            "icon": "🔧",
            "shortcut": "r",
        },
        {
            "id": "diagnose",
            "label": "Diagnose System",
            "category": "System",
            "icon": "🧠",
            "shortcut": "d",
        },
        {
            "id": "plugins",
            "label": "Manage Plugins",
            "category": "Extensions",
            "icon": "📦",
            "shortcut": "p",
        },
        {
            "id": "update",
            "label": "Check Updates",
            "category": "System",
            "icon": "🔄",
            "shortcut": "u",
        },
        {
            "id": "security",
            "label": "Security Settings",
            "category": "System",
            "icon": "🔐",
            "shortcut": "sec",
        },
        {
            "id": "memory",
            "label": "Memory System",
            "category": "AI",
            "icon": "🧊",
            "shortcut": "mem",
        },
        {
            "id": "soul",
            "label": "Personality/Soul",
            "category": "AI",
            "icon": "🎭",
            "shortcut": "sou",
        },
        {
            "id": "skills",
            "label": "Skills V2",
            "category": "Extensions",
            "icon": "📚",
            "shortcut": "ski",
        },
        {
            "id": "schedule",
            "label": "Task Scheduler",
            "category": "Automation",
            "icon": "⏰",
            "shortcut": "sch",
        },
        {
            "id": "mcp",
            "label": "MCP Server",
            "category": "Integrations",
            "icon": "🌐",
            "shortcut": "mcp",
        },
        {
            "id": "apps",
            "label": "App Integrations",
            "category": "Integrations",
            "icon": "📱",
            "shortcut": "app",
        },
        {
            "id": "workflows",
            "label": "Workflow Automation",
            "category": "Automation",
            "icon": "🔀",
            "shortcut": "w",
        },
        {
            "id": "tests",
            "label": "Run Tests",
            "category": "System",
            "icon": "🧪",
            "shortcut": "test",
        },
        {
            "id": "api",
            "label": "REST API Server",
            "category": "Integrations",
            "icon": "🌍",
            "shortcut": "api",
        },
        {
            "id": "docker",
            "label": "Docker Management",
            "category": "System",
            "icon": "🐳",
            "shortcut": "dock",
        },
        {
            "id": "monitoring_v2",
            "label": "Advanced Monitoring",
            "category": "System",
            "icon": "📈",
            "shortcut": "mon",
        },
        {
            "id": "workflow_builder",
            "label": "Visual Workflow Builder",
            "category": "Automation",
            "icon": "🎨",
            "shortcut": "wb",
        },
        {
            "id": "automation",
            "label": "Automation Engine",
            "category": "Automation",
            "icon": "🤖",
            "shortcut": "auto",
        },
        {
            "id": "database",
            "label": "Database Management",
            "category": "System",
            "icon": "🗄️",
            "shortcut": "db",
        },
        {
            "id": "file_manager",
            "label": "File Manager",
            "category": "Tools",
            "icon": "📁",
            "shortcut": "f",
        },
        {"id": "voice", "label": "Voice Commands", "category": "AI", "icon": "🎤", "shortcut": "v"},
        {
            "id": "code",
            "label": "Code Interpreter",
            "category": "Tools",
            "icon": "💻",
            "shortcut": "code",
        },
        {
            "id": "marketplace",
            "label": "Plugin Marketplace",
            "category": "Extensions",
            "icon": "🛒",
            "shortcut": "market",
        },
        {
            "id": "encrypt",
            "label": "Encryption Tools",
            "category": "Security",
            "icon": "🔒",
            "shortcut": "enc",
        },
    ]

    def __init__(self):
        self.history = self._load_history()

    def _load_history(self) -> List[str]:
        """Load command history"""
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE) as f:
                    return json.load(f)
            except:
                pass
        return []

    def _save_history(self):
        """Save command history"""
        os.makedirs(NEUGI_DIR, exist_ok=True)
        with open(HISTORY_FILE, "w") as f:
            json.dump(self.history[-50:], f, indent=2)

    def add_to_history(self, command_id: str):
        """Add command to history"""
        if command_id in self.history:
            self.history.remove(command_id)
        self.history.append(command_id)
        self._save_history()

    def search(self, query: str, limit: int = 10) -> List[Dict]:
        """Fuzzy search commands"""
        if not query:
            return self._get_recent_commands(limit)

        query_lower = query.lower()
        results = []

        for cmd in self.COMMANDS:
            score = 0

            if cmd["label"].lower().startswith(query_lower):
                score = 100
            elif query_lower in cmd["label"].lower():
                score = 80
            elif cmd["shortcut"].startswith(query_lower):
                score = 70
            elif query_lower in cmd["category"].lower():
                score = 50

            if score > 0:
                results.append({**cmd, "score": score})

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def _get_recent_commands(self, limit: int) -> List[Dict]:
        """Get recent commands"""
        recent = []
        for cmd_id in reversed(self.history[-10:]):
            for cmd in self.COMMANDS:
                if cmd["id"] == cmd_id:
                    recent.append(cmd)
                    break
            if len(recent) >= limit:
                break

        if len(recent) < limit:
            for cmd in self.COMMANDS:
                if cmd not in recent:
                    recent.append(cmd)
                if len(recent) >= limit:
                    break

        return recent

    def get_by_category(self) -> Dict[str, List[Dict]]:
        """Get commands grouped by category"""
        categories = {}
        for cmd in self.COMMANDS:
            cat = cmd["category"]
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(cmd)
        return categories

    def execute_command(self, command_id: str) -> Any:
        """Execute a command"""
        self.add_to_history(command_id)

        commands_map = {
            "chat": lambda: "run_chat",
            "heartbeat": lambda: "run_heartbeat",
            "topology": lambda: "run_topology",
            "monitor": lambda: "run_monitor",
            "logs": lambda: "run_logs",
            "setup": lambda: "run_setup",
            "repair": lambda: "run_repair",
            "diagnose": lambda: "run_diagnose",
            "plugins": lambda: "run_plugins",
            "update": lambda: "run_update",
            "security": lambda: "run_security",
            "memory": lambda: "run_memory",
            "soul": lambda: "run_soul",
            "skills": lambda: "run_skills",
            "schedule": lambda: "run_scheduler",
            "mcp": lambda: "run_mcp",
            "apps": lambda: "run_apps",
            "workflows": lambda: "run_workflows",
            "tests": lambda: "run_tests",
            "api": lambda: "run_api",
            "docker": lambda: "run_docker",
            "monitoring_v2": lambda: "run_monitoring_v2",
            "workflow_builder": lambda: "run_workflow_builder",
            "automation": lambda: "run_automation",
            "database": lambda: "run_database",
            "file_manager": lambda: "run_file_manager",
            "voice": lambda: "run_voice",
            "code": lambda: "run_code_interpreter",
            "marketplace": lambda: "run_marketplace",
            "encrypt": lambda: "run_encryption",
        }

        return commands_map.get(command_id, lambda: None)()


def run_palette():
    """Run command palette in terminal"""
    palette = CommandPalette()

    print("\n" + "=" * 50)
    print("🎯 NEUGI COMMAND PALETTE")
    print("=" * 50)
    print("\nType to search, Enter to execute, Esc to exit\n")

    query = ""
    results = palette.search("")

    while True:
        print("\033[H\033[J", end="")
        print("\n" + "=" * 50)
        print("🎯 NEUGI COMMAND PALETTE")
        print("=" * 50)

        if query:
            results = palette.search(query)

        print(f"\nSearch: {query}_\n")

        for i, cmd in enumerate(results):
            marker = "→ " if i == 0 else "  "
            print(f"{marker}{cmd['icon']} {cmd['label']} ({cmd['category']})")

        print("\n" + "-" * 50)
        print("↑↓ Navigate | Enter Select | Esc Exit | Ctrl+C Quit")

        try:
            import tty
            import termios

            old_settings = termios.tcgetattr(0)
            tty.setcbreak(0)

            key = ord(os.read(0, 1))

            if key == 27:
                break
            elif key == 13:
                if results:
                    print(f"\nExecuting: {results[0]['label']}")
                    break
            elif key == 127:
                query = query[:-1]
            elif key >= 32:
                query += chr(key)

            termios.tcsetattr(0, termios.TCSADRAIN, old_settings)

        except (KeyboardInterrupt, ImportError):
            break

    print("\n")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="NEUGI Command Palette")
    parser.add_argument("--run", action="store_true", help="Run interactive palette")
    parser.add_argument("--list", action="store_true", help="List all commands")
    parser.add_argument("--search", type=str, help="Search commands")

    args = parser.parse_args()

    palette = CommandPalette()

    if args.run:
        run_palette()

    elif args.list:
        categories = palette.get_by_category()
        for cat, commands in categories.items():
            print(f"\n📁 {cat}")
            for cmd in commands:
                print(f"   {cmd['icon']} {cmd['label']} ({cmd['shortcut']})")

    elif args.search:
        results = palette.search(args.search)
        print(f"\nSearch: {args.search}\n")
        for cmd in results:
            print(f"{cmd['icon']} {cmd['label']} ({cmd['category']}) - Score: {cmd['score']}")

    else:
        print("Usage: python -m neugi_command_palette [--run|--list|--search QUERY]")


if __name__ == "__main__":
    main()
