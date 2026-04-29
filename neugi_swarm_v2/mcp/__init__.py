"""
NEUGI v2 MCP Server - Model Context Protocol Implementation
============================================================

Full MCP spec implementation with stdio and Streamable HTTP transports.
Compatible with Claude Code, OpenClaw, Gemini CLI, and any MCP client.

Usage:
    # stdio transport (primary)
    python -m neugi_swarm_v2.mcp.mcp_server

    # Streamable HTTP transport (secondary)
    python -m neugi_swarm_v2.mcp.mcp_server --transport http --port 17901
"""

from __future__ import annotations

from neugi_swarm_v2.mcp.prompts import PromptRegistry
from neugi_swarm_v2.mcp.protocol import (
    ContentBlock,
    ErrorCode,
    ImageContent,
    Implementation,
    InitializeResult,
    JSONRPCError,
    JSONRPCNotification,
    JSONRPCRequest,
    JSONRPCResponse,
    MCPError,
    Prompt,
    PromptArgument,
    PromptMessage,
    PromptResult,
    Resource,
    ResourceContent,
    ResourceTemplate,
    ServerCapabilities,
    TextContent,
    Tool,
    ToolResult,
)
from neugi_swarm_v2.mcp.resources import ResourceRegistry
from neugi_swarm_v2.mcp.tools import ToolRegistry

__all__ = [
    "MCPServer",
    "ToolRegistry",
    "ResourceRegistry",
    "PromptRegistry",
    "JSONRPCRequest",
    "JSONRPCResponse",
    "JSONRPCError",
    "JSONRPCNotification",
    "MCPError",
    "ErrorCode",
    "Tool",
    "ToolResult",
    "ContentBlock",
    "TextContent",
    "ImageContent",
    "ResourceContent",
    "Resource",
    "ResourceTemplate",
    "Prompt",
    "PromptArgument",
    "PromptMessage",
    "PromptResult",
    "ServerCapabilities",
    "InitializeResult",
    "Implementation",
]
