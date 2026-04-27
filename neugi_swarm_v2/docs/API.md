# NEUGI v2 API Reference

## REST API (Dashboard Server)

Base URL: `http://localhost:8080/api/v2`

### Agents

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/agents` | List all agents |
| POST | `/agents` | Create new agent |
| GET | `/agents/{id}` | Get agent state |
| POST | `/agents/{id}/task` | Assign task |
| POST | `/agents/{id}/pause` | Pause agent |
| POST | `/agents/{id}/resume` | Resume agent |

### Sessions

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/sessions` | List sessions |
| POST | `/sessions` | Create session |
| GET | `/sessions/{id}` | Get session state |
| POST | `/sessions/{id}/message` | Send message |
| POST | `/sessions/{id}/compact` | Compact session |

### Memory

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/memory/search?q={query}` | Search memories |
| POST | `/memory` | Store memory |
| DELETE | `/memory/{id}` | Delete memory |

### Tools

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/tools` | List all tools |
| POST | `/tools/execute` | Execute tool |
| POST | `/tools/compose` | Compose tool chain |

### Skills

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/skills` | List loaded skills |
| POST | `/skills/reload` | Hot-reload skills |
| POST | `/skills/workshop` | Generate from observation |

### Governance

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/governance/budget` | Budget status |
| GET | `/governance/audit` | Audit log |
| POST | `/governance/approve` | Approve request |

### System

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/metrics` | Prometheus metrics |
| GET | `/version` | Version info |

## WebSocket Events

Connect to `ws://localhost:8080/ws`

**Client → Server:**
```json
{"type": "subscribe", "channel": "agents"}
{"type": "command", "target": "agent_1", "action": "execute", "payload": "..."}
```

**Server → Client:**
```json
{"type": "agent.status", "agent_id": "agent_1", "status": "thinking"}
{"type": "memory.new", "memory_id": "...", "content": "..."}
{"type": "tool.result", "tool": "file_read", "result": "..."}
```

## MCP Protocol

NEUGI v2 implements the full Model Context Protocol spec.

**stdio transport:**
```bash
neugi mcp --transport stdio
```

**HTTP transport:**
```bash
neugi mcp --transport http --port 8081
```

**Available primitives:**
- `tools/list` — List 61 built-in tools
- `tools/call` — Execute any tool
- `resources/list` — List memory resources
- `resources/read` — Read memory by URI
- `prompts/list` — List skill prompts
- `prompts/get` — Get assembled prompt

## Python SDK

```python
from neugi_swarm_v2 import NeugiAssistant

assistant = NeugiAssistant()
response = assistant.chat("Build me a Flask API")

# Direct subsystem access
from neugi_swarm_v2.memory import MemorySystem
from neugi_swarm_v2.skills import SkillManager
from neugi_swarm_v2.agents import AgentManager
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `neugi chat` | Interactive chat |
| `neugi agent list` | List agents |
| `neugi agent create` | Create agent |
| `neugi skill list` | List skills |
| `neugi skill reload` | Hot-reload |
| `neugi memory search` | Search memory |
| `neugi tool list` | List tools |
| `neugi tool exec` | Execute tool |
| `neugi workflow run` | Run workflow |
| `neugi plan` | Strategic plan |
| `neugi gateway` | Start gateway |
| `neugi dashboard` | Launch dashboard |
| `neugi deploy` | Deploy to cloud |
| `neugi wizard` | Setup wizard |
| `neugi status` | System status |
| `neugi test` | Run tests |
| `neugi migrate` | Migrate data |
