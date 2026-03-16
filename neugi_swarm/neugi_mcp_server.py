#!/usr/bin/env python3
"""
🤖 NEUGI MCP SERVER
====================
Exposes NEUGI as an MCP Server using the official Model Context Protocol SDK.
Compatible with Claude Code, OpenClaw, Gemini CLI, etc. via stdio.

Version: 2.0.0
Date: March 17, 2026
"""

import os
import sys
import json
import asyncio
from typing import Any, Dict, List, Optional

try:
    # Import the MCP SDK
    from mcp.server import Server
    from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
    import mcp.server.stdio

    MCP_SDK_AVAILABLE = True
except ImportError:
    MCP_SDK_AVAILABLE = False
    # Fallback to the original HTTP server if SDK is not available
    # We'll keep the old server as a fallback, but we prefer the SDK.

# NEUGI-specific imports
try:
    from neugi_swarm_agents import AgentManager
    from neugi_swarm_memory import MemoryManager
    from neugi_swarm_tools import ToolManager
    from neugi_swarm import neugi_swarm

    NEUGI_MODULES_AVAILABLE = True
except ImportError:
    NEUGI_MODULES_AVAILABLE = False

# Configuration
NEUGI_DIR = os.path.expanduser("~/neugi")


class NEUGIMCPServer:
    def __init__(self):
        if not MCP_SDK_AVAILABLE:
            raise RuntimeError("MCP SDK not available. Please install 'mcp-server' package.")

        self.server = Server("neugi")
        self.agent_manager = AgentManager() if NEUGI_MODULES_AVAILABLE else None
        self.memory_manager = (
            MemoryManager(db_path=os.path.join(NEUGI_DIR, "data", "memory.db"))
            if NEUGI_MODULES_AVAILABLE
            else None
        )
        self.tool_manager = ToolManager() if NEUGI_MODULES_AVAILABLE else None

        # Set up handlers
        self._setup_handlers()

    def _setup_handlers(self):
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            return [
                # Agent delegation tools
                Tool(
                    name="neugi_delegate_task",
                    description="Delegate a task to a specific NEUGI swarm agent",
                    inputSchema={
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
                Tool(
                    name="neugi_execute_agent",
                    description="Execute a task with automatic agent routing (lets NEUGI choose the best agent)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "prompt": {"type": "string", "description": "Task prompt"},
                        },
                        "required": ["prompt"],
                    },
                ),
                # Memory tools
                Tool(
                    name="neugi_memory_recall",
                    description="Recall memories from NEUGI's memory system",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "memory_type": {
                                "type": "string",
                                "description": "Type of memory (conversation, fact, preference, etc.)",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results",
                                "default": 10,
                            },
                        },
                    },
                ),
                Tool(
                    name="neugi_memory_add",
                    description="Add a memory to NEUGI's memory system",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "content": {"type": "string", "description": "Memory content"},
                            "memory_type": {"type": "string", "description": "Type of memory"},
                            "importance": {
                                "type": "integer",
                                "description": "Importance level (1-20)",
                                "default": 5,
                            },
                        },
                        "required": ["content", "memory_type"],
                    },
                ),
                # Filesystem tools (basic)
                Tool(
                    name="neugi_filesystem_read",
                    description="Read a file from the NEUGI workspace",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "File path relative to NEUGI directory",
                            },
                        },
                        "required": ["path"],
                    },
                ),
                Tool(
                    name="neugi_filesystem_write",
                    description="Write a file to the NEUGI workspace",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "File path relative to NEUGI directory",
                            },
                            "content": {"type": "string", "description": "Content to write"},
                        },
                        "required": ["path", "content"],
                    },
                ),
                # System info
                Tool(
                    name="neugi_system_info",
                    description="Get information about the NEUGI system",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                    },
                ),
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            if not NEUGI_MODULES_AVAILABLE:
                return [
                    TextContent(
                        type="text",
                        text="NEUGI modules not available. Please ensure the NEUGI Swarm is properly installed.",
                    )
                ]

            try:
                if name == "neugi_delegate_task":
                    agent_id = arguments.get("agent")
                    task = arguments.get("task")
                    if not agent_id or not task:
                        return [
                            TextContent(
                                type="text", text="Error: Both 'agent' and 'task' are required."
                            )
                        ]

                    # Delegate to the agent manager
                    result = self.agent_manager.run(agent_id, task)
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]

                elif name == "neugi_execute_agent":
                    prompt = arguments.get("prompt")
                    if not prompt:
                        return [TextContent(type="text", text="Error: 'prompt' is required.")]

                    # Let NEUGI choose the best agent (simplified: we can use the agent manager's logic or just run a default)
                    # For now, we'll use the manager to run a task with a default agent or we can implement routing.
                    # We'll implement a simple routing: if the prompt contains certain keywords, we pick an agent.
                    # But for simplicity, we'll just run it with the aurora agent (researcher) as a placeholder.
                    # In a full implementation, we would have a more sophisticated router.
                    result = self.agent_manager.run(
                        "aurora", f"Analyze and route this task: {prompt}"
                    )
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]

                elif name == "neugi_memory_recall":
                    query = arguments.get("query")
                    memory_type = arguments.get("memory_type")
                    limit = arguments.get("limit", 10)

                    if self.memory_manager:
                        results = self.memory_manager.recall(
                            query=query, memory_type=memory_type, limit=limit
                        )
                        return [TextContent(type="text", text=json.dumps(results, indent=2))]
                    else:
                        return [TextContent(type="text", text="Memory manager not available.")]

                elif name == "neugi_memory_add":
                    content = arguments.get("content")
                    memory_type = arguments.get("memory_type")
                    importance = arguments.get("importance", 5)

                    if not content or not memory_type:
                        return [
                            TextContent(
                                type="text", text="Error: 'content' and 'memory_type' are required."
                            )
                        ]

                    if self.memory_manager:
                        memory_id = self.memory_manager.remember(
                            memory_type=memory_type, content=content, importance=importance
                        )
                        return [TextContent(type="text", text=f"Memory added with ID: {memory_id}")]
                    else:
                        return [TextContent(type="text", text="Memory manager not available.")]

                elif name == "neugi_filesystem_read":
                    path = arguments.get("path")
                    if not path:
                        return [TextContent(type="text", text="Error: 'path' is required.")]

                    full_path = os.path.join(NEUGI_DIR, path)
                    if not os.path.exists(full_path):
                        return [TextContent(type="text", text=f"File not found: {path}")]

                    with open(full_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    return [TextContent(type="text", text=content)]

                elif name == "neugi_filesystem_write":
                    path = arguments.get("path")
                    content = arguments.get("content")
                    if not path or content is None:
                        return [
                            TextContent(
                                type="text", text="Error: 'path' and 'content' are required."
                            )
                        ]

                    full_path = os.path.join(NEUGI_DIR, path)
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    return [TextContent(type="text", text=f"File written to {path}")]

                elif name == "neugi_system_info":
                    info = {
                        "neugi_dir": NEUGI_DIR,
                        "python_version": sys.version,
                        "platform": sys.platform,
                        "mcp_sdk_available": MCP_SDK_AVAILABLE,
                        "neugi_modules_available": NEUGI_MODULES_AVAILABLE,
                    }
                    if self.agent_manager:
                        info["agent_count"] = len(self.agent_manager.agents)
                    if self.memory_manager:
                        info["memory_stats"] = self.memory_manager.stats()
                    return [TextContent(type="text", text=json.dumps(info, indent=2))]

                else:
                    return [TextContent(type="text", text=f"Unknown tool: {name}")]

            except Exception as e:
                return [TextContent(type="text", text=f"Error executing tool {name}: {str(e)}")]

    async def run(self):
        # Run the server via stdio
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream, write_stream, self.server.create_initialization_options()
            )


def main():
    try:
        server = NEUGIMCPServer()
        asyncio.run(server.run())
    except KeyboardInterrupt:
        print("\nNEUGI MCP Server stopped.")
    except Exception as e:
        print(f"Failed to start NEUGI MCP Server: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
