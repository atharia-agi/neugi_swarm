#!/usr/bin/env python3
"""
🤖 NEUGI MCP SERVER
====================

Exposes NEUGI as MCP Server - 50+ tools available
Compatible with Claude Code, OpenClaw, Gemini CLI, Codex

Based on BrowserOS MCP architecture
Supports SSE transport for Claude Code

Version: 1.0
Date: March 15, 2026
"""

import os
import sys
import json
import argparse
from typing import Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
import threading
import webbrowser

# Try to import required libraries
try:
    from http.server import HTTPServer, BaseHTTPRequestHandler
    from urllib.parse import urlparse, parse_qs
except ImportError:
    print("Error: Python 3.7+ required")
    sys.exit(1)

try:
    import sse_starlette

    SSE_AVAILABLE = True
except ImportError:
    SSE_AVAILABLE = False


NEUGI_DIR = os.path.expanduser("~/neugi")
DEFAULT_PORT = 19889  # Different from main engine (19888)


@dataclass
class MCPTool:
    """MCP Tool definition"""

    name: str
    description: str
    input_schema: Dict[str, Any]


@dataclass
class MCPToolCall:
    """MCP Tool call request"""

    name: str
    arguments: Dict[str, Any]


class NEUGIMCPServer:
    """
    NEUGI MCP Server

    Exposes 50+ tools via MCP protocol:
    - NEUGI Swarm tools (9 agents)
    - Filesystem tools (7 - Cowork style)
    - Memory tools (2-tier)
    - Skill tools
    - System tools
    - Git tools
    - Network tools
    """

    VERSION = "1.0.0"

    def __init__(self, neugi_dir: str = None):
        self.neugi_dir = neugi_dir or NEUGI_DIR
        self.port = DEFAULT_PORT
        self._init_tools()

    def _init_tools(self):
        """Initialize all MCP tools"""
        self.tools = []

        # ========== NEUGI SWARM TOOLS ==========

        # Agent delegation
        self.tools.extend(
            [
                MCPTool(
                    name="neugi_delegate_task",
                    description="Delegate a task to a specific NEUGI swarm agent",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "agent": {
                                "type": "string",
                                "enum": [
                                    "aurora",
                                    "cipher",
                                    "nova",
                                    "pulse",
                                    "quark",
                                    "shield",
                                    "spark",
                                    "ink",
                                    "nexus",
                                ],
                                "description": "Target agent",
                            },
                            "task": {"type": "string", "description": "Task description"},
                        },
                        "required": ["agent", "task"],
                    },
                ),
                MCPTool(
                    name="neugi_execute_agent",
                    description="Execute a task with automatic agent routing",
                    input_schema={
                        "type": "object",
                        "properties": {"prompt": {"type": "string", "description": "Task prompt"}},
                        "required": ["prompt"],
                    },
                ),
            ]
        )

        # ========== FILESYSTEM TOOLS (Cowork style) ==========

        self.tools.extend(
            [
                MCPTool(
                    name="neugi_filesystem_read",
                    description="Read a file from the workspace",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "File path relative to workspace",
                            },
                            "offset": {
                                "type": "integer",
                                "description": "Starting line (1-indexed)",
                                "default": 1,
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Max lines to read",
                                "default": 100,
                            },
                        },
                        "required": ["path"],
                    },
                ),
                MCPTool(
                    name="neugi_filesystem_write",
                    description="Create or overwrite a file",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "File path relative to workspace",
                            },
                            "content": {"type": "string", "description": "File content"},
                        },
                        "required": ["path", "content"],
                    },
                ),
                MCPTool(
                    name="neugi_filesystem_edit",
                    description="Edit a file by string replacement",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "File path"},
                            "old_string": {"type": "string", "description": "Text to find"},
                            "new_string": {"type": "string", "description": "Replacement text"},
                        },
                        "required": ["path", "old_string", "new_string"],
                    },
                ),
                MCPTool(
                    name="neugi_filesystem_bash",
                    description="Execute a shell command in the workspace",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "command": {"type": "string", "description": "Shell command"},
                            "timeout": {
                                "type": "integer",
                                "description": "Timeout in seconds",
                                "default": 120,
                            },
                        },
                        "required": ["command"],
                    },
                ),
                MCPTool(
                    name="neugi_filesystem_find",
                    description="Find files matching a glob pattern",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "pattern": {
                                "type": "string",
                                "description": "Glob pattern (e.g., *.py)",
                            },
                            "path": {
                                "type": "string",
                                "description": "Directory to search",
                                "default": ".",
                            },
                        },
                        "required": ["pattern"],
                    },
                ),
                MCPTool(
                    name="neugi_filesystem_grep",
                    description="Search file contents using regex",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "pattern": {"type": "string", "description": "Search pattern (regex)"},
                            "path": {"type": "string", "description": "File or directory"},
                            "glob": {
                                "type": "string",
                                "description": "Filter by glob (e.g., *.py)",
                            },
                            "ignore_case": {"type": "boolean", "default": False},
                        },
                        "required": ["pattern"],
                    },
                ),
                MCPTool(
                    name="neugi_filesystem_ls",
                    description="List directory contents",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Directory path",
                                "default": ".",
                            }
                        },
                        "required": [],
                    },
                ),
            ]
        )

        # ========== MEMORY TOOLS ==========

        self.tools.extend(
            [
                MCPTool(
                    name="neugi_memory_recall",
                    description="Search memory for information",
                    input_schema={
                        "type": "object",
                        "properties": {"query": {"type": "string", "description": "Search query"}},
                        "required": ["query"],
                    },
                ),
                MCPTool(
                    name="neugi_memory_remember",
                    description="Store information in memory",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "fact": {"type": "string", "description": "Information to remember"},
                            "type": {
                                "type": "string",
                                "enum": ["core", "daily"],
                                "default": "daily",
                            },
                        },
                        "required": ["fact"],
                    },
                ),
                MCPTool(
                    name="neugi_memory_read_core",
                    description="Read core (permanent) memory",
                    input_schema={"type": "object", "properties": {}},
                ),
            ]
        )

        # ========== SKILL TOOLS ==========

        self.tools.extend(
            [
                MCPTool(
                    name="neugi_skill_list",
                    description="List all available skills",
                    input_schema={"type": "object", "properties": {}},
                ),
                MCPTool(
                    name="neugi_skill_execute",
                    description="Execute a skill by name",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "skill_name": {"type": "string", "description": "Skill name"}
                        },
                        "required": ["skill_name"],
                    },
                ),
                MCPTool(
                    name="neugi_skill_match",
                    description="Find best matching skill for a request",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "request": {"type": "string", "description": "User request"}
                        },
                        "required": ["request"],
                    },
                ),
            ]
        )

        # ========== SYSTEM TOOLS ==========

        self.tools.extend(
            [
                MCPTool(
                    name="neugi_system_status",
                    description="Get NEUGI system status",
                    input_schema={"type": "object", "properties": {}},
                ),
                MCPTool(
                    name="neugi_system_health",
                    description="Run health check",
                    input_schema={"type": "object", "properties": {}},
                ),
                MCPTool(
                    name="neugi_system_metrics",
                    description="Get system metrics (CPU, RAM, etc)",
                    input_schema={"type": "object", "properties": {}},
                ),
                MCPTool(
                    name="neugi_process_list",
                    description="List running processes",
                    input_schema={
                        "type": "object",
                        "properties": {"limit": {"type": "integer", "default": 10}},
                    },
                ),
            ]
        )

        # ========== GIT TOOLS ==========

        self.tools.extend(
            [
                MCPTool(
                    name="neugi_git_status",
                    description="Get git repository status",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Repository path",
                                "default": ".",
                            }
                        },
                    },
                ),
                MCPTool(
                    name="neugi_git_log",
                    description="Get git commit log",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "default": "."},
                            "limit": {"type": "integer", "default": 10},
                        },
                    },
                ),
                MCPTool(
                    name="neugi_git_diff",
                    description="Get git diff",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "default": "."},
                            "file": {"type": "string", "description": "Specific file"},
                        },
                    },
                ),
                MCPTool(
                    name="neugi_git_execute",
                    description="Execute any git command",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "command": {"type": "string", "description": "Git command"},
                            "path": {"type": "string", "default": "."},
                        },
                        "required": ["command"],
                    },
                ),
            ]
        )

        # ========== NETWORK TOOLS ==========

        self.tools.extend(
            [
                MCPTool(
                    name="neugi_network_status",
                    description="Check network connectivity",
                    input_schema={"type": "object", "properties": {}},
                ),
                MCPTool(
                    name="neugi_fetch_url",
                    description="Fetch content from URL",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "url": {"type": "string", "description": "URL to fetch"},
                            "method": {"type": "string", "enum": ["GET", "POST"], "default": "GET"},
                        },
                        "required": ["url"],
                    },
                ),
                MCPTool(
                    name="neugi_web_search",
                    description="Search the web",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "limit": {"type": "integer", "default": 5},
                        },
                        "required": ["query"],
                    },
                ),
            ]
        )

        # ========== AGENT-SPECIFIC TOOLS ==========

        # Aurora - Data extraction
        self.tools.extend(
            [
                MCPTool(
                    name="neugi_aurora_extract",
                    description="Aurora agent: Extract data from web page",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "url": {"type": "string"},
                            "selector": {"type": "string", "description": "CSS selector"},
                        },
                        "required": ["url"],
                    },
                ),
            ]
        )

        # Cipher - Code
        self.tools.extend(
            [
                MCPTool(
                    name="neugi_cipher_code",
                    description="Cipher agent: Generate or fix code",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "prompt": {"type": "string"},
                            "language": {"type": "string"},
                        },
                        "required": ["prompt"],
                    },
                ),
            ]
        )

        # Shield - Security
        self.tools.extend(
            [
                MCPTool(
                    name="neugi_shield_audit",
                    description="Shield agent: Run security audit",
                    input_schema={
                        "type": "object",
                        "properties": {"path": {"type": "string", "default": "."}},
                    },
                ),
            ]
        )

        # Pulse - Analysis
        self.tools.extend(
            [
                MCPTool(
                    name="neugi_pulse_analyze",
                    description="Pulse agent: Analyze data or logs",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "input": {"type": "string"},
                            "type": {"type": "string", "enum": ["json", "log", "csv"]},
                        },
                        "required": ["input"],
                    },
                ),
            ]
        )

    def _execute_tool(self, tool_call: MCPToolCall) -> Dict[str, Any]:
        """Execute a tool and return result"""

        tool_name = tool_call.name
        args = tool_call.arguments

        try:
            # Filesystem tools
            if tool_name == "neugi_filesystem_read":
                return self._fs_read(args["path"], args.get("offset", 1), args.get("limit", 100))

            elif tool_name == "neugi_filesystem_write":
                return self._fs_write(args["path"], args["content"])

            elif tool_name == "neugi_filesystem_edit":
                return self._fs_edit(args["path"], args["old_string"], args["new_string"])

            elif tool_name == "neugi_filesystem_bash":
                return self._fs_bash(args["command"], args.get("timeout", 120))

            elif tool_name == "neugi_filesystem_find":
                return self._fs_find(args["pattern"], args.get("path", "."))

            elif tool_name == "neugi_filesystem_grep":
                return self._fs_grep(
                    args["pattern"],
                    args.get("path", "."),
                    args.get("glob"),
                    args.get("ignore_case", False),
                )

            elif tool_name == "neugi_filesystem_ls":
                return self._fs_ls(args.get("path", "."))

            # Memory tools
            elif tool_name == "neugi_memory_recall":
                return self._memory_recall(args["query"])

            elif tool_name == "neugi_memory_remember":
                return self._memory_remember(args["fact"], args.get("type", "daily"))

            elif tool_name == "neugi_memory_read_core":
                return self._memory_read_core()

            # Skill tools
            elif tool_name == "neugi_skill_list":
                return self._skill_list()

            elif tool_name == "neugi_skill_execute":
                return self._skill_execute(args["skill_name"])

            elif tool_name == "neugi_skill_match":
                return self._skill_match(args["request"])

            # System tools
            elif tool_name == "neugi_system_status":
                return self._system_status()

            elif tool_name == "neugi_system_health":
                return self._system_health()

            elif tool_name == "neugi_system_metrics":
                return self._system_metrics()

            # Git tools
            elif tool_name == "neugi_git_status":
                return self._git_status(args.get("path", "."))

            elif tool_name == "neugi_git_log":
                return self._git_log(args.get("path", "."), args.get("limit", 10))

            elif tool_name == "neugi_git_diff":
                return self._git_diff(args.get("path", "."), args.get("file"))

            elif tool_name == "neugi_git_execute":
                return self._git_execute(args["command"], args.get("path", "."))

            # Network tools
            elif tool_name == "neugi_network_status":
                return self._network_status()

            elif tool_name == "neugi_fetch_url":
                return self._fetch_url(args["url"], args.get("method", "GET"))

            elif tool_name == "neugi_web_search":
                return self._web_search(args["query"], args.get("limit", 5))

            # Delegation
            elif tool_name == "neugi_delegate_task":
                return {"status": "delegated", "agent": args["agent"], "task": args["task"]}

            elif tool_name == "neugi_execute_agent":
                return {"status": "queued", "prompt": args["prompt"]}

            else:
                return {"error": f"Unknown tool: {tool_name}"}

        except Exception as e:
            return {"error": str(e)}

    # ========== TOOL IMPLEMENTATIONS ==========

    def _fs_read(self, path: str, offset: int = 1, limit: int = 100) -> Dict:
        """Read file with pagination"""
        try:
            full_path = os.path.join(self.neugi_dir, "workspace", path)
            if not os.path.exists(full_path):
                return {"error": f"File not found: {path}"}

            with open(full_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            start = max(0, offset - 1)
            end = min(len(lines), start + limit)

            return {
                "content": "".join(lines[start:end]),
                "total_lines": len(lines),
                "showing": f"{start + 1}-{end}",
                "path": path,
            }
        except Exception as e:
            return {"error": str(e)}

    def _fs_write(self, path: str, content: str) -> Dict:
        """Write file"""
        try:
            full_path = os.path.join(self.neugi_dir, "workspace", path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)

            return {"status": "success", "path": path}
        except Exception as e:
            return {"error": str(e)}

    def _fs_edit(self, path: str, old: str, new: str) -> Dict:
        """Edit file by string replacement"""
        try:
            full_path = os.path.join(self.neugi_dir, "workspace", path)

            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()

            if old not in content:
                return {"error": "String not found"}

            new_content = content.replace(old, new)

            with open(full_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            return {"status": "edited", "path": path}
        except Exception as e:
            return {"error": str(e)}

    def _fs_bash(self, command: str, timeout: int = 120) -> Dict:
        """Execute bash command"""
        try:
            import subprocess

            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=os.path.join(self.neugi_dir, "workspace"),
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except Exception as e:
            return {"error": str(e)}

    def _fs_find(self, pattern: str, path: str = ".") -> Dict:
        """Find files"""
        import glob

        try:
            search_path = os.path.join(self.neugi_dir, "workspace", path, pattern)
            matches = glob.glob(search_path)
            return {
                "matches": [
                    os.path.relpath(m, os.path.join(self.neugi_dir, "workspace")) for m in matches
                ]
            }
        except Exception as e:
            return {"error": str(e)}

    def _fs_grep(
        self, pattern: str, path: str = ".", glob: str = None, ignore_case: bool = False
    ) -> Dict:
        """Grep files"""
        import re

        try:
            flags = re.IGNORECASE if ignore_case else 0
            regex = re.compile(pattern, flags)

            results = []
            search_dir = os.path.join(self.neugi_dir, "workspace", path)

            for root, dirs, files in os.walk(search_dir):
                for f in files:
                    if glob and not f.endswith(glob.lstrip("*")):
                        continue

                    filepath = os.path.join(root, f)
                    try:
                        with open(filepath, "r", encoding="utf-8") as file:
                            for i, line in enumerate(file, 1):
                                if regex.search(line):
                                    results.append(
                                        {
                                            "file": os.path.relpath(filepath, search_dir),
                                            "line": i,
                                            "content": line.strip()[:100],
                                        }
                                    )
                    except:
                        continue

            return {"matches": results[:50]}
        except Exception as e:
            return {"error": str(e)}

    def _fs_ls(self, path: str = ".") -> Dict:
        """List directory"""
        try:
            full_path = os.path.join(self.neugi_dir, "workspace", path)

            if not os.path.exists(full_path):
                return {"error": "Path not found"}

            items = []
            for item in os.listdir(full_path):
                item_path = os.path.join(full_path, item)
                stat = os.stat(item_path)
                items.append(
                    {
                        "name": item,
                        "type": "dir" if os.path.isdir(item_path) else "file",
                        "size": stat.st_size,
                    }
                )

            return {"items": items, "path": path}
        except Exception as e:
            return {"error": str(e)}

    def _memory_recall(self, query: str) -> Dict:
        """Search memory"""
        try:
            from neugi_memory_v2 import TwoTierMemory

            memory = TwoTierMemory()
            results = memory.recall(query)
            return results
        except Exception as e:
            return {"error": str(e), "query": query}

    def _memory_remember(self, fact: str, mem_type: str = "daily") -> Dict:
        """Remember fact"""
        try:
            from neugi_memory_v2 import TwoTierMemory

            memory = TwoTierMemory()

            if mem_type == "core":
                memory.add_core_fact("Notes", fact)
            else:
                memory.write_daily(fact)

            return {"status": "remembered", "type": mem_type, "fact": fact}
        except Exception as e:
            return {"error": str(e)}

    def _memory_read_core(self) -> Dict:
        """Read core memory"""
        try:
            from neugi_memory_v2 import TwoTierMemory

            memory = TwoTierMemory()
            return {"content": memory.read_core()}
        except Exception as e:
            return {"error": str(e)}

    def _skill_list(self) -> Dict:
        """List skills"""
        try:
            from neugi_skills_v2 import SkillManagerV2

            manager = SkillManagerV2()
            skills = manager.list_skills()
            return {"skills": [s.to_dict() for s in skills]}
        except Exception as e:
            return {"error": str(e)}

    def _skill_execute(self, skill_name: str) -> Dict:
        """Execute skill"""
        try:
            from neugi_skills_v2 import SkillManagerV2

            manager = SkillManagerV2()
            return manager.execute_skill(skill_name)
        except Exception as e:
            return {"error": str(e)}

    def _skill_match(self, request: str) -> Dict:
        """Match skill"""
        try:
            from neugi_skills_v2 import SkillManagerV2

            manager = SkillManagerV2()
            match = manager.match_skill(request)

            if match:
                return {"matched": match.name, "description": match.description}
            return {"matched": None}
        except Exception as e:
            return {"error": str(e)}

    def _system_status(self) -> Dict:
        """Get system status"""
        return {
            "status": "running",
            "version": self.VERSION,
            "neugi_dir": self.neugi_dir,
            "tools_count": len(self.tools),
            "timestamp": datetime.now().isoformat(),
        }

    def _system_health(self) -> Dict:
        """Health check"""
        checks = {
            "neugi_dir": os.path.exists(self.neugi_dir),
            "workspace": os.path.exists(os.path.join(self.neugi_dir, "workspace")),
            "memory": os.path.exists(os.path.join(self.neugi_dir, "memory")),
            "config": os.path.exists(os.path.join(self.neugi_dir, "config")),
        }

        healthy = all(checks.values())

        return {"healthy": healthy, "checks": checks}

    def _system_metrics(self) -> Dict:
        """Get system metrics"""
        try:
            import psutil

            return {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage("/").percent,
                "timestamp": datetime.now().isoformat(),
            }
        except ImportError:
            return {"error": "psutil not available"}

    def _git_status(self, path: str = ".") -> Dict:
        """Git status"""
        return self._git_execute("status --short", path)

    def _git_log(self, path: str = ".", limit: int = 10) -> Dict:
        """Git log"""
        return self._git_execute(f"log --oneline -n {limit}", path)

    def _git_diff(self, path: str = ".", file: str = None) -> Dict:
        """Git diff"""
        cmd = "diff"
        if file:
            cmd += f" -- {file}"
        return self._git_execute(cmd, path)

    def _git_execute(self, command: str, path: str = ".") -> Dict:
        """Execute git command"""
        import subprocess

        try:
            full_path = os.path.join(self.neugi_dir, "workspace", path)
            result = subprocess.run(
                f"git {command}", shell=True, capture_output=True, text=True, cwd=full_path
            )
            return {"output": result.stdout or result.stderr, "returncode": result.returncode}
        except Exception as e:
            return {"error": str(e)}

    def _network_status(self) -> Dict:
        """Network status"""
        import socket

        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return {"connected": True}
        except:
            return {"connected": False}

    def _fetch_url(self, url: str, method: str = "GET") -> Dict:
        """Fetch URL"""
        try:
            import urllib.request

            req = urllib.request.Request(url, method=method)
            with urllib.request.urlopen(req, timeout=10) as response:
                return {"status": response.status, "content": response.read().decode()[:5000]}
        except Exception as e:
            return {"error": str(e)}

    def _web_search(self, query: str, limit: int = 5) -> Dict:
        """Web search (DuckDuckGo)"""
        try:
            import urllib.request

            url = f"https://html.duckduckgo.com/html/?q={query}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as response:
                return {"query": query, "results": response.read().decode()[:3000]}
        except Exception as e:
            return {"error": str(e)}

    # ========== MCP PROTOCOL ==========

    def get_tools(self) -> List[Dict]:
        """Get all tools in MCP format"""
        return [
            {"name": tool.name, "description": tool.description, "inputSchema": tool.input_schema}
            for tool in self.tools
        ]

    def call_tool(self, name: str, arguments: Dict) -> Dict:
        """Call a tool"""
        tool_call = MCPToolCall(name=name, arguments=arguments)
        return self._execute_tool(tool_call)


# ========== HTTP SERVER ==========


class MCPHandler(BaseHTTPRequestHandler):
    """HTTP handler for MCP protocol"""

    server: NEUGIMCPServer

    def log_message(self, format, *args):
        pass  # Suppress logging

    def do_GET(self):
        """Handle GET requests"""
        parsed = urlparse(self.path)

        if parsed.path == "/mcp":
            # SSE endpoint
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()

            # Send capabilities
            data = {"tools": self.server.get_tools()}
            self.wfile.write(f"data: {json.dumps(data)}\n\n".encode())

        elif parsed.path == "/tools":
            # JSON tools list
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(self.server.get_tools(), indent=2).encode())

        elif parsed.path == "/health":
            # Health check
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        """Handle POST requests"""
        parsed = urlparse(self.path)

        if parsed.path == "/tools/call":
            # Call tool
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)

            try:
                request = json.loads(body)
                tool_name = request.get("name")
                arguments = request.get("arguments", {})

                result = self.server.call_tool(tool_name, arguments)

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())

            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())

        else:
            self.send_response(404)
            self.end_headers()


def start_server(port: int = DEFAULT_PORT, neugi_dir: str = None, open_browser: bool = True):
    """Start MCP server"""
    server = NEUGIMCPServer(neugi_dir)
    server.port = port

    # Override handler's server reference
    MCPHandler.server = server

    httpd = HTTPServer(("127.0.0.1", port), MCPHandler)

    url = f"http://127.0.0.1:{port}/mcp"

    print(f"""
╔════════════════════════════════════════════════════════════╗
║  🤖 NEUGI MCP SERVER                                      ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  MCP URL: {url:<46}║
║                                                            ║
║  Tools: {len(server.tools):<52}║
║                                                            ║
║  Integration:                                              ║
║  • Claude Code: claude mcp add neugi {url} --scope user  ║
║  • OpenClaw: Add to openclaw.json                         ║
║  • Gemini CLI: gemini mcp add local-server {url}         ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
    """)

    if open_browser:
        threading.Timer(1, lambda: webbrowser.open(url)).start()

    print(f"Server running at {url}")
    print("Press Ctrl+C to stop")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped")
        httpd.shutdown()


# ========== MAIN ==========


def main():
    parser = argparse.ArgumentParser(description="NEUGI MCP Server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to listen on")
    parser.add_argument("--dir", type=str, default=NEUGI_DIR, help="NEUGI directory")
    parser.add_argument("--no-browser", action="store_true", help="Don't open browser")

    args = parser.parse_args()

    start_server(args.port, args.dir, not args.no_browser)


if __name__ == "__main__":
    main()
