"""
NEUGI Swarm MCP Server
======================
Model Context Protocol (MCP) implementation for NEUGI Swarm v2.1.3

MCP is the standard protocol (created by Anthropic) for connecting AI agents
to external tools, data sources, and services. This implementation provides
native MCP server support for NEUGI, enabling:
- Tool discovery and invocation via standard protocol
- Resource access (files, APIs, databases)
- Prompt template management
- Bidirectional communication over stdio, HTTP, and SSE

Usage:
    # Stdio mode (for local development)
    python -m neugi_swarm_v2.mcp.server.stdio

    # HTTP mode (for production)
    python -m neugi_swarm_v2.mcp.server.http --port 17902

    # Connect as client from another MCP server
    # {"command": "python", "args": ["-m", "neugi_swarm_v2.mcp.server.stdio"]}
"""

from __future__ import annotations

import importlib

__version__ = "1.1.0"

# Lazy imports to avoid circular dependencies at package init
def __getattr__(name):
    module_map = {
        "MCPServer": "neugi_swarm_v2.mcp.mcp_server",
        "StdioTransport": "neugi_swarm_v2.mcp.transport",
        "HttpTransport": "neugi_swarm_v2.mcp.transport",
        "HTTPTransport": "neugi_swarm_v2.mcp.transport",
        "SSEConnection": "neugi_swarm_v2.mcp.transport",
        "RateLimiter": "neugi_swarm_v2.mcp.transport",
        "SSEAuth": "neugi_swarm_v2.mcp.transport",
        "ToolManager": "neugi_swarm_v2.mcp.tool_manager",
        "ResourceManager": "neugi_swarm_v2.mcp.resource_manager",
        "PromptManager": "neugi_swarm_v2.mcp.prompt_manager",
        "MCPBridge": "neugi_swarm_v2.mcp.bridge",
        "create_bridge": "neugi_swarm_v2.mcp.bridge",
        "SSEEventForwarder": "neugi_swarm_v2.mcp.sse_forwarder",
        "get_sse_forwarder": "neugi_swarm_v2.mcp.sse_forwarder",
        "CheckpointStore": "neugi_swarm_v2.mcp.checkpoint",
        "ResilientMCPExecutor": "neugi_swarm_v2.mcp.checkpoint",
        "MCPA2AAdapter": "neugi_swarm_v2.mcp.a2a_adapter",
        "create_a2a_adapter": "neugi_swarm_v2.mcp.a2a_adapter",
    }
    if name in module_map:
        module = importlib.import_module(module_map[name])
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "MCPServer",
    "StdioTransport",
    "HttpTransport",
    "HTTPTransport",
    "SSEConnection",
    "ToolManager",
    "ResourceManager",
    "PromptManager",
    "MCPSession",
    "MCPBridge",
    "mcp_tool",
    "mcp_resource",
    "mcp_prompt",
    "list_tools",
    "get_tools",
    "call_tool",
    "read_resource",
    "list_resources",
    "list_prompts",
    "get_prompt",
    "create_bridge",
]
