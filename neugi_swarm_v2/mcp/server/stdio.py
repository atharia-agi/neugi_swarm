#!/usr/bin/env python
"""
MCP Server - Stdio Entry Point
===============================
Run NEUGI MCP server using stdio transport (for CLI integration).

Usage:
    python -m neugi_swarm_v2.mcp.server.stdio

This is the default transport for local development and IDE integration.
All communication happens through stdin/stdout using JSON-RPC 2.0 messages.
"""

from __future__ import annotations

import asyncio
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Main entry point for MCP stdio server."""
    from neugi_swarm_v2.mcp.server import MCPServer

    server = MCPServer()

    logger.info("=" * 60)
    logger.info("NEUGI Swarm MCP Server (Stdio)")
    logger.info("Version: %s | Protocol: %s", server.version, server.VERSION)
    logger.info("Session: %s", server.session_id)
    logger.info("=" * 60)
    logger.info("Available tools: %d", server.tools.count())
    logger.info("Available resources: %d", server.resources.count())
    logger.info("Available prompts: %d", server.prompts.count())
    logger.info("=" * 60)
    logger.info("Waiting for MCP client connection on stdin/stdout...")

    try:
        await server.run_stdio()
    except KeyboardInterrupt:
        logger.info("Shutting down MCP server...")
    except Exception as e:
        logger.error("MCP server error: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())