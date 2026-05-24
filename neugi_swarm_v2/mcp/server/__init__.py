"""
MCP Server Package
==================
Re-exports MCPServer from mcp_server module for backward compatibility.

Entry points:
    python -m neugi_swarm_v2.mcp.server.stdio   (stdio transport)
    python -m neugi_swarm_v2.mcp.server.http    (HTTP transport)
"""

from __future__ import annotations

try:
    from neugi_swarm_v2.mcp.mcp_server import MCPServer
except ImportError:
    from mcp.mcp_server import MCPServer

__all__ = ["MCPServer"]
