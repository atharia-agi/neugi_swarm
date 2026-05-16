# MCP Client Integration Guide

> How to connect Claude Desktop, Cursor, VS Code, and other MCP clients to NEUGI Swarm

## Overview

NEUGI Swarm v2.1.3 includes a full **Model Context Protocol (MCP) Server** that exposes 8+ default tools, all plugin tools, memory resources, and prompt templates through the standard MCP protocol.

### Transport Options

| Transport | Use Case | Port |
|-----------|----------|------|
| **Stdio** | Local CLI, Claude Desktop, Cursor | stdin/stdout |
| **Streamable HTTP-compatible JSON-RPC** | Remote clients and modern MCP clients | 17902 |
| **SSE event stream** | Browser dashboards and event subscriptions | 17902 |

---

## 1. Claude Desktop

### Stdio Connection (Local)

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "neugi-swarm": {
      "command": "python",
      "args": [
        "-m",
        "neugi_swarm_v2.mcp.server.stdio"
      ],
      "env": {
        "PYTHONPATH": "K:\\neugi_swarm\\repo\\neugi_swarm_v2"
      }
    }
  }
}
```

### HTTP Connection (Remote/Network)

```json
{
  "mcpServers": {
    "neugi-swarm": {
      "url": "http://127.0.0.1:17902",
      "headers": {
        "Content-Type": "application/json"
      }
    }
  }
}
```

---

## 2. Cursor IDE

### stdio

In Cursor settings -> MCP Servers:

- **Name**: `neugi-swarm`
- **Type**: `command`
- **Command**: `python -m neugi_swarm_v2.mcp.server.stdio`
- **Environment**: `{"PYTHONPATH": "K:\\neugi_swarm\\repo\\neugi_swarm_v2"}`

---

## 3. VS Code (via Continue extension)

In `~/.continue/config.json`:

```json
{
  "experimental": {
    "mcpServers": {
      "neugi-swarm": {
        "command": "python",
        "args": ["-m", "neugi_swarm_v2.mcp.server.stdio"]
      }
    }
  }
}
```

---

## 4. Browser / SSE Dashboard

Open in browser:

```
http://127.0.0.1:17902/sse?events=tool_execution_success,memory_update
```

With auth token:

```
http://127.0.0.1:17902/sse?token=your_token_here&events=tool_execution_success
```

---

## 5. Custom MCP Client (Python)

```python
import json
import asyncio
import subprocess

class NEUGIMCPClient:
    def __init__(self):
        self.proc = subprocess.Popen(
            ["python", "-m", "neugi_swarm_v2.mcp.server.stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    async def call_tool(self, name: str, args: dict) -> dict:
        request = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "tools/call",
            "params": {"name": name, "arguments": args},
        }
        self.proc.stdin.write(json.dumps(request) + "\n")
        self.proc.stdin.flush()
        resp = json.loads(self.proc.stdout.readline())
        return resp

    def list_tools(self) -> list:
        request = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "tools/list",
            "params": {},
        }
        self.proc.stdin.write(json.dumps(request) + "\n")
        self.proc.stdin.flush()
        resp = json.loads(self.proc.stdout.readline())
        return resp.get("result", {}).get("tools", [])

    def close(self):
        self.proc.terminate()
```

---

## 6. MCP Tools Available

| Tool | Description |
|------|-------------|
| `echo` | Echo back input (test) |
| `get_time` | Server timestamp |
| `list_tools` | List all MCP tools |
| `list_resources` | List all MCP resources |
| `list_prompts` | List all prompt templates |
| `read_resource` | Read resource by URI |
| `get_prompt` | Get prompt template |
| `system_info` | NEUGI system information |
| `health_check` | Server health status |
| `plugin:*` | Auto-registered plugin tools |
| `neugi_status` | NEUGI subsystem health |
| `neugi_memory_search` | Search memory system |
| `neugi_event_history` | Event bus history |
| `neugi_plugin_list` | List loaded plugins |
| `neugi_execute_tool` | Execute NEUGI tool |
| `neugi_soul_read` | Read soul/identity files |
| `neugi_a2a_mesh_status` | Agent mesh status |

---

## 7. Resources Available

| URI Pattern | Description |
|-------------|-------------|
| `neugi://server/info` | Server information |
| `neugi://server/capabilities` | MCP capabilities |
| `neugi://server/sse-info` | SSE endpoint info |
| `neugi://memory/...` | NEUGI memory search |
| `neugi://memory/stats` | Memory statistics |
| `neugi://soul/*` | Soul/identity files |

---

## 8. Security Configuration

Start MCP server with auth:

```bash
python -m neugi_swarm_v2.mcp.server.http \
  --port 17902 \
  --sse \
  --auth-tokens '{"admin":"your-secret-token","monitor":"readonly-token"}' \
  --rate-limit 10 \
  --rate-burst 20
```

### Rate Limiting

- **Default**: 10 events/second, burst 20
- Configure via `--rate-limit` and `--rate-burst`
- Events silently dropped when bucket exhausted

### Auth Tokens

- Optional, disabled by default
- Pass via `?token=<value>` query param on SSE connections
- Unauthorized connections get HTTP 401 response
- Configure via `--auth-tokens` CLI arg

### Streamable HTTP Compatibility

The HTTP transport returns `Mcp-Session-Id` on JSON-RPC and SSE responses so newer MCP clients can bind follow-up requests to a server-side session. SSE remains available for dashboard-style event subscriptions, while JSON-RPC over HTTP is the primary request/response path.

---

## 9. Tool Cancellation

Long-running tool executions can be cancelled:

```json
{
  "jsonrpc": "2.0",
  "id": "cancel-1",
  "method": "cancel",
  "params": {
    "requestId": "original-request-id"
  }
}
```

---

## 10. Troubleshooting

### "Connection refused"
- Ensure MCP server is running: `python -m neugi_swarm_v2.mcp.server.http`
- Check port 17902 is not in use

### "Tool not found"
- Ensure bridge is connected: `neugi mcp bridge connect`
- Plugin tools only appear after plugins are loaded

### SSE not receiving events
- Ensure `--sse` flag is enabled
- Check event filter: `?events=tool_execution_success`

### Auth errors
- Pass valid token: `?token=<token>`
- Or start server without auth tokens

### Rate limited
- Reduce event subscription scope
- Or increase rate limit: `--rate-limit 50`
