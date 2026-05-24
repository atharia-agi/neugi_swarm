#!/usr/bin/env python
"""
MCP Server - HTTP Entry Point
==============================
Run NEUGI MCP server using HTTP transport (for remote connections).

Usage:
    python -m neugi_swarm_v2.mcp.server.http --host 127.0.0.1 --port 17902

This transport enables remote MCP clients to connect to NEUGI
over the network using HTTP/JSON. SSE support enabled by default
for browser-based MCP clients.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Main entry point for MCP HTTP server."""
    parser = argparse.ArgumentParser(
        description="NEUGI Swarm MCP Server (HTTP Transport)"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host address to bind (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=17902,
        help="Port to listen on (default: 17902)",
    )
    parser.add_argument(
        "--allow-origin",
        nargs="*",
        default=["*"],
        help="Allowed CORS origins (default: *)",
    )
    parser.add_argument(
        "--sse",
        action="store_true",
        default=True,
        help="Enable Server-Sent Events for browser clients (default: enabled)",
    )
    parser.add_argument(
        "--no-sse",
        action="store_true",
        help="Disable Server-Sent Events",
    )
    parser.add_argument(
        "--auth-tokens",
        type=str,
        default="",
        help='Auth tokens as JSON dict: {"client_name":"token",...}. Empty = no auth.',
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=10.0,
        help="Max SSE events per second per connection (default: 10.0)",
    )
    parser.add_argument(
        "--rate-burst",
        type=int,
        default=20,
        help="Max burst size for SSE rate limiter (default: 20)",
    )
    args = parser.parse_args()

    from neugi_swarm_v2.mcp.server import MCPServer
    from neugi_swarm_v2.mcp.transport import HTTPTransport

    enable_sse = not args.no_sse

    auth_tokens = None
    if args.auth_tokens:
        try:
            auth_tokens = json.loads(args.auth_tokens)
        except json.JSONDecodeError:
            logger.warning("Invalid auth tokens JSON, disabling auth")
            auth_tokens = None

    transport = HTTPTransport(
        host=args.host,
        port=args.port,
        cors_origins=args.allow_origin,
        enable_sse=enable_sse,
        rate_limit=args.rate_limit,
        rate_burst=args.rate_burst,
        auth_tokens=auth_tokens,
    )
    server = MCPServer(transport=transport)

    logger.info("=" * 60)
    logger.info("NEUGI Swarm MCP Server (HTTP)")
    logger.info("Version: %s | Protocol: %s", server.version, server.VERSION)
    logger.info("Session: %s", server.session_id)
    logger.info("=" * 60)
    logger.info("Listening on http://%s:%s", args.host, args.port)
    logger.info("Available tools: %d", server.tools.count())
    logger.info("Available resources: %d", server.resources.count())
    logger.info("Available prompts: %d", server.prompts.count())
    logger.info("Allowed origins: %s", args.allow_origin)
    logger.info("SSE support: %s", "enabled" if enable_sse else "disabled")
    logger.info("SSE auth: %s", "enabled" if auth_tokens else "disabled")
    logger.info("SSE rate limit: %.1f/s (burst: %d)", args.rate_limit, args.rate_burst)
    logger.info("=" * 60)

    try:
        await server.run_http(host=args.host, port=args.port, enable_sse=enable_sse)
    except KeyboardInterrupt:
        logger.info("Shutting down MCP server...")
    except Exception as e:
        logger.error("MCP server error: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
