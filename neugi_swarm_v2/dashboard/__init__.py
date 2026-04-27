"""
NEUGI v2 Web Dashboard
======================

Production-ready web dashboard for the NEUGI Swarm v2 agentic framework.
Provides real-time monitoring, agent management, chat interface, and
system administration through a beautiful glass-morphism UI.

Usage:
    from neugi_swarm_v2.dashboard import DashboardServer

    server = DashboardServer(swarm_instance, host="0.0.0.0", port=8080)
    server.start()
"""

from __future__ import annotations

from neugi_swarm_v2.dashboard.server import DashboardServer, DashboardConfig

__all__ = [
    "DashboardServer",
    "DashboardConfig",
]
