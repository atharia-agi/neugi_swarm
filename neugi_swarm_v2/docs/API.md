# NEUGI v2 API Reference (v2.1.3)

## REST API (Dashboard Server)

Base URL: `http://localhost:17901/api`

Runtime-validated endpoint count: `32`

### Core Runtime

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/chat` | Run chat request |
| POST | `/steering` | Send steering instruction |

### Agents & Sessions

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/agents` | List agents |
| POST | `/agents/{id}/task` | Delegate a task to an agent |
| GET | `/sessions` | List active sessions |
| GET | `/sessions/{id}/messages` | Fetch session transcript |

### Skills, Memory, Learning

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/skills` | List loaded skills |
| GET | `/memory/stats` | Memory statistics |
| GET | `/memory/recall` | Recall memory by query |
| GET | `/learning/stats` | Learning subsystem stats |

### Workflows & Plugins

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/workflows` | List workflow definitions |
| POST | `/workflows/{id}/run` | Execute workflow |
| GET | `/plugins` | List plugins |
| POST | `/plugins/toggle` | Enable/disable plugin |

### Governance

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/governance/budget` | Budget status |
| GET | `/governance/audit` | Audit log |
| GET | `/governance/approvals` | Approval queue |
| POST | `/governance/approvals/decide` | Approve/deny request |

### Provider & Config Setup

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/providers` | Provider + model catalog |
| GET | `/providers/health` | Provider readiness summary |
| GET | `/config` | Read runtime config |
| PUT | `/config` | Update runtime config |
| POST | `/config/test-llm` | Test provider/model connection |

Provider matrix (auto-generated from runtime catalog):
- [PROVIDER_MATRIX.md](./PROVIDER_MATRIX.md)

### Runtime Control & Observability

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/autonomous/status` | Autonomous loop status |
| GET | `/observability/status` | Observability status |
| GET | `/runtime/autostart` | Autostart state |
| POST | `/runtime/autostart` | Update autostart state |
| GET | `/benchmarks` | Benchmark snapshots |
| GET | `/channels` | Configured channel list |

### Auth

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/login` | Issue dashboard session token |
| POST | `/auth/logout` | Invalidate dashboard session |

---

## WebSocket Events

Connect to: `ws://localhost:17901/ws`

Typical stream includes:
- `agent_status`
- `memory_event`
- `tool_execution`
- `system_alert`

---

## MCP API

NEUGI implements MCP with:
- stdio transport
- HTTP transport
- SSE event streaming (optional auth + rate limiting + cancellation)

Run modes:

```bash
python -m neugi_swarm_v2.mcp.server.stdio
python -m neugi_swarm_v2.mcp.server.http --port 17902 --sse
```

---

## CLI Surface

Top-level commands (current): `24`

Examples:
- `neugi wizard`
- `neugi smoke`
- `neugi quickstart`
- `neugi chat`
- `neugi start`
- `neugi status`
- `neugi autonomous status`
- `neugi config view`

For full tree, run:

```bash
neugi help
```

---

## Quick Call Snippets

```bash
# Health
curl http://localhost:17901/api/health

# Provider catalog
curl http://localhost:17901/api/providers

# Provider readiness
curl http://localhost:17901/api/providers/health

# Config read
curl http://localhost:17901/api/config
```
