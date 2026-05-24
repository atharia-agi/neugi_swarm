"""
MCP Bridge CLI Commands Extension for NEUGI v2
===============================================

Adds MCP server management commands to the NEUGI CLI:
- neugi mcp start/stop/status
- neugi mcp bridge connect/disconnect
- neugi mcp sse enable/disable
- neugi mcp tools list
"""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.table import Table

from neugi_swarm_v2.config import load_config

console = Console()


class MCPCliExtension:
    """CLI extension for MCP server management."""

    def __init__(self, cli: Any):
        self.cli = cli
        self._server: Any = None
        self._bridge: Any = None
        self._sse_enabled = True

    def register_commands(self, commands: dict) -> None:
        """Register MCP-related CLI commands."""
        commands["mcp"] = {
            "handler": self._cmd_mcp,
            "description": "Manage MCP server and bridges",
            "subcommands": {
                "start": {
                    "handler": self._cmd_mcp_start,
                    "description": "Start MCP server",
                },
                "stop": {
                    "handler": self._cmd_mcp_stop,
                    "description": "Stop MCP server",
                },
                "status": {
                    "handler": self._cmd_mcp_status,
                    "description": "Show MCP server status",
                },
                "bridge": {
                    "handler": self._cmd_mcp_bridge,
                    "description": "Manage MCP-NEUGI bridge",
                    "subcommands": {
                        "connect": {
                            "handler": self._cmd_bridge_connect,
                            "description": "Connect bridge to NEUGI",
                        },
                        "disconnect": {
                            "handler": self._cmd_bridge_disconnect,
                            "description": "Disconnect bridge",
                        },
                        "status": {
                            "handler": self._cmd_bridge_status,
                            "description": "Show bridge status",
                        },
                    },
                },
                "sse": {
                    "handler": self._cmd_mcp_sse,
                    "description": "Manage SSE settings",
                    "subcommands": {
                        "enable": {
                            "handler": self._cmd_sse_enable,
                            "description": "Enable SSE",
                        },
                        "disable": {
                            "handler": self._cmd_sse_disable,
                            "description": "Disable SSE",
                        },
                        "status": {
                            "handler": self._cmd_sse_status,
                            "description": "Show SSE status",
                        },
                    },
                },
                "tools": {
                    "handler": self._cmd_mcp_tools,
                    "description": "List MCP tools",
                },
                "resources": {
                    "handler": self._cmd_mcp_resources,
                    "description": "List MCP resources",
                },
                "prompts": {
                    "handler": self._cmd_mcp_prompts,
                    "description": "List MCP prompts",
                },
                "test": {
                    "handler": self._cmd_mcp_test,
                    "description": "Test MCP server connection",
                },
            },
        }

    # -- Main MCP Command -------------------------------------------------

    def _cmd_mcp(self, args: list) -> dict:
        if not args:
            return self._cmd_mcp_status([])

        subcmd = args[0]
        sub_args = args[1:]

        subcommands = {
            "start": self._cmd_mcp_start,
            "stop": self._cmd_mcp_stop,
            "status": self._cmd_mcp_status,
            "bridge": self._cmd_mcp_bridge,
            "sse": self._cmd_mcp_sse,
            "tools": self._cmd_mcp_tools,
            "resources": self._cmd_mcp_resources,
            "prompts": self._cmd_mcp_prompts,
            "test": self._cmd_mcp_test,
        }

        if subcmd in subcommands:
            return subcommands[subcmd](sub_args)
        return {"error": f"Unknown subcommand: {subcmd}"}

    # -- Server Commands -------------------------------------------------

    def _cmd_mcp_start(self, args: list) -> dict:
        """Start the MCP server."""
        import sys

        config = load_config()
        port = config.observability.max_history if hasattr(config, 'observability') else 17902

        # Use port 17902 by default
        port = 17902

        try:
            if args and args[0] == "--stdio":
                # Start stdio mode inline
                console.print("[info]Starting MCP server (stdio mode)...[/info]")
                if sys.platform == "win32":
                    import subprocess
                    subprocess.Popen(
                        [sys.executable, "-m", "neugi_swarm_v2.mcp.server.stdio"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                else:
                    import subprocess
                    subprocess.Popen(
                        [sys.executable, "-m", "neugi_swarm_v2.mcp.server.stdio"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                return {"status": "started", "mode": "stdio", "pid": "background"}
            else:
                # Start HTTP mode
                console.print(f"[info]Starting MCP server (HTTP mode) on port {port}...[/info]")

                import subprocess
                proc = subprocess.Popen(
                    [sys.executable, "-m", "neugi_swarm_v2.mcp.server.http",
                     "--port", str(port), "--sse"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self._server = {"proc": proc, "port": port}
                return {"status": "started", "mode": "http", "port": port}

        except Exception as e:
            return {"error": str(e)}

    def _cmd_mcp_stop(self, args: list) -> dict:
        """Stop the MCP server."""
        if self._server and hasattr(self._server, "proc"):
            try:
                self._server.proc.terminate()
                self._server.proc.wait(timeout=5)
                self._server = None
                return {"status": "stopped"}
            except Exception as e:
                return {"error": str(e)}
        return {"status": "not running"}

    def _cmd_mcp_status(self, args: list) -> dict:
        """Show MCP server status."""
        from neugi_swarm_v2.mcp.server import MCPServer

        table = Table(title="MCP Server Status", box=None)
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Protocol Version", MCPServer.VERSION)
        table.add_row("HTTP Port", "17902")
        table.add_row("SSE Endpoint", "/sse")
        table.add_row("SSE Status", "enabled" if self._sse_enabled else "disabled")
        table.add_row("Bridge Status", "connected" if self._bridge and getattr(self._bridge, "is_connected", False) else "disconnected")

        if self._server:
            proc = getattr(self._server, "proc", None)
            if proc:
                table.add_row("Server Process", f"running (PID {proc.pid})")
            else:
                table.add_row("Server Process", "stopped")
        else:
            table.add_row("Server Process", "not started via CLI")

        console.print(table)
        return {"status": "displayed"}

    # -- Bridge Commands -------------------------------------------------

    def _cmd_mcp_bridge(self, args: list) -> dict:
        if not args:
            return self._cmd_bridge_status([])

        subcmd = args[0]
        sub_args = args[1:]

        subcommands = {
            "connect": self._cmd_bridge_connect,
            "disconnect": self._cmd_bridge_disconnect,
            "status": self._cmd_bridge_status,
        }

        if subcmd in subcommands:
            return subcommands[subcmd](sub_args)
        return {"error": f"Unknown bridge subcommand: {subcmd}"}

    def _cmd_bridge_connect(self, args: list) -> dict:
        """Connect the MCP bridge to NEUGI subsystems."""
        try:
            from neugi_swarm_v2 import NeugiSwarmV2
            from neugi_swarm_v2.mcp.bridge import create_bridge
            from neugi_swarm_v2.mcp.server import MCPServer

            # Create or get server
            if not self._server:
                self._server = MCPServer()

            server: MCPServer = self._server if isinstance(self._server, MCPServer) else self._server.get("server")

            # Try to get NEUGI instance
            neugi: NeugiSwarmV2 = None
            if hasattr(self.cli, "swarm"):
                neugi = self.cli.swarm
            elif hasattr(self.cli, "base_dir"):
                neugi = NeugiSwarmV2(base_dir=str(self.cli.base_dir))

            if neugi is None:
                return {"error": "NEUGI instance not available. Initialize NEUGI first."}

            # Create bridge
            if server:
                bridge = create_bridge(server, neugi)
                self._bridge = bridge
                return {"status": "connected", "tools_registered": server.tools.count()}
            else:
                return {"error": "MCP server not initialized"}

        except Exception as e:
            return {"error": str(e)}

    def _cmd_bridge_disconnect(self, args: list) -> dict:
        """Disconnect the MCP bridge."""
        if self._bridge:
            try:
                self._bridge.disconnect()
                self._bridge = None
                return {"status": "disconnected"}
            except Exception as e:
                return {"error": str(e)}
        return {"status": "not connected"}

    def _cmd_bridge_status(self, args: list) -> dict:
        """Show bridge status."""
        table = Table(title="MCP-NEUGI Bridge Status", box=None)
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")

        connected = self._bridge and getattr(self._bridge, "is_connected", False) if self._bridge else False
        table.add_row("Bridge Connected", "yes" if connected else "no")

        if connected:
            table.add_row("NEUGI Version", getattr(self._bridge.neugi, "__version__", "unknown"))
            table.add_row("MCP Tools", str(self._bridge.server.tools.count()))
            table.add_row("MCP Resources", str(self._bridge.server.resources.count()))
            table.add_row("MCP Prompts", str(self._bridge.server.prompts.count()))

            if hasattr(self._bridge, "_memory") and self._bridge._memory:
                table.add_row("Memory System", "active")
            if hasattr(self._bridge, "_a2a") and self._bridge._a2a:
                table.add_row("A2A Protocol", "active")
            if hasattr(self._bridge, "_plugin_registry") and self._bridge._plugin_registry:
                table.add_row("Plugin Registry", "active")

        console.print(table)
        return {"status": "displayed"}

    # -- SSE Commands ----------------------------------------------------

    def _cmd_mcp_sse(self, args: list) -> dict:
        if not args:
            return self._cmd_sse_status([])

        subcmd = args[0]
        if subcmd == "enable":
            return self._cmd_sse_enable([])
        elif subcmd == "disable":
            return self._cmd_sse_disable([])
        elif subcmd == "status":
            return self._cmd_sse_status([])
        return {"error": f"Unknown SSE subcommand: {subcmd}"}

    def _cmd_sse_enable(self, args: list) -> dict:
        self._sse_enabled = True
        return {"status": "SSE enabled", "endpoint": "/sse"}

    def _cmd_sse_disable(self, args: list) -> dict:
        self._sse_enabled = False
        return {"status": "SSE disabled"}

    def _cmd_sse_status(self, args: list) -> dict:
        table = Table(title="SSE Status", box=None)
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")
        table.add_row("SSE Enabled", "yes" if self._sse_enabled else "no")
        table.add_row("Endpoint", "/sse")
        table.add_row("Protocol", "text/event-stream")
        table.add_row("Connect Example", "curl -N http://127.0.0.1:17902/sse")
        console.print(table)
        return {"status": "displayed"}

    # -- Tool/Resource/Prompt Listing ------------------------------------

    def _cmd_mcp_tools(self, args: list) -> dict:
        """List available MCP tools."""
        from neugi_swarm_v2.mcp.server import MCPServer
        server: MCPServer = self._server if isinstance(self._server, MCPServer) else (self._server or {}).get("server")

        if server:
            tools = server.tools.get_tools()
            table = Table(title=f"MCP Tools ({len(tools)})", box=None)
            table.add_column("Name", style="cyan")
            table.add_column("Description", style="white")
            for t in tools:
                table.add_row(t["name"], t.get("description", "")[:60])
            console.print(table)
            return {"count": len(tools)}
        return {"error": "MCP server not initialized"}

    def _cmd_mcp_resources(self, args: list) -> dict:
        """List available MCP resources."""
        from neugi_swarm_v2.mcp.server import MCPServer
        server: MCPServer = self._server if isinstance(self._server, MCPServer) else (self._server or {}).get("server")

        if server:
            result = server.resources.list_resources()
            resources = result.resources
            table = Table(title=f"MCP Resources ({len(resources)})", box=None)
            table.add_column("URI", style="cyan")
            table.add_column("Name", style="white")
            for r in resources:
                table.add_row(r.get("uri", r.get("uriTemplate", "?")), r.get("name", ""))
            console.print(table)
            return {"count": len(resources)}
        return {"error": "MCP server not initialized"}

    def _cmd_mcp_prompts(self, args: list) -> dict:
        """List available MCP prompts."""
        from neugi_swarm_v2.mcp.server import MCPServer
        server: MCPServer = self._server if isinstance(self._server, MCPServer) else (self._server or {}).get("server")

        if server:
            result = server.prompts.list_prompts()
            prompts = result.prompts if result.prompts else []
            table = Table(title=f"MCP Prompts ({len(prompts)})", box=None)
            table.add_column("Name", style="cyan")
            table.add_column("Description", style="white")
            for p in prompts:
                table.add_row(p.get("name", "?"), p.get("description", ""))
            console.print(table)
            return {"count": len(prompts)}
        return {"error": "MCP server not initialized"}

    def _cmd_mcp_test(self, args: list) -> dict:
        """Test MCP server connection."""
        try:
            import urllib.error
            import urllib.request

            url = "http://127.0.0.1:17902"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:  # nosec B310
                if resp.status == 200:
                    console.print("[success]MCP server is reachable[/success]")
                    return {"status": "reachable", "url": url}
        except urllib.error.URLError:
            console.print(f"[warning]MCP server not reachable at {url}[/warning]")
            return {"status": "unreachable", "url": url}
        except (OSError, TimeoutError) as e:
            console.print(f"[error]Connection test failed: {e}[/error]")
            return {"error": str(e)}


def extend_cli(cli: Any) -> None:
    """Extend the NEUGI CLI with MCP commands."""
    ext = MCPCliExtension(cli)
    ext.register_commands(cli._commands if hasattr(cli, "_commands") else {})
