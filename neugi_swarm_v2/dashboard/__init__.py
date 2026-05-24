"""
NEUGI v2 Web Dashboard
======================

Production-ready web dashboard for the NEUGI Swarm v2 agentic framework.
Provides real-time monitoring, agent management, chat interface, and
system administration through a beautiful glass-morphism UI.

Usage:
    from neugi_swarm_v2.dashboard.server import DashboardServer

    server = DashboardServer(swarm_instance, host="0.0.0.0", port=17901)
    server.start()
"""

from __future__ import annotations


def __getattr__(name: str):
    """Lazy import to avoid circular dependency with server.py ↔ websocket.py."""
    if name == "DashboardServer":
        from neugi_swarm_v2.dashboard.server import DashboardServer
        return DashboardServer
    if name == "DashboardConfig":
        from neugi_swarm_v2.dashboard.server import DashboardConfig
        return DashboardConfig
    raise AttributeError(f"module 'neugi_swarm_v2.dashboard' has no attribute {name!r}")


__all__ = [
    "DashboardServer",
    "DashboardConfig",
]
