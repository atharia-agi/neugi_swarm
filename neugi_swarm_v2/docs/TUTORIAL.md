# NEUGI Swarm v2.1.3 — Complete A-Z Tutorial

> The ultimate guide to installing, configuring, and mastering NEUGI — the most advanced open-source autonomous multi-agent framework ever built.

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Quick Start — Install in 30 Seconds](#2-quick-start--install-in-30-seconds)
3. [Configuration Deep Dive](#3-configuration-deep-dive)
4. [CLI Reference — Every Command](#4-cli-reference--every-command)
5. [Architecture Overview](#5-architecture-overview)
6. [Agent System — 9 Archetypes](#6-agent-system--9-archetypes)
7. [Memory System — 3-Tier Karpathy Memory](#7-memory-system--3-tier-karpathy-memory)
8. [Skills System — 6 Tiers](#8-skills-system--6-tiers)
9. [MCP Server — Model Context Protocol](#9-mcp-server--model-context-protocol)
10. [Autonomous Loop — Pro-Active Behavior](#10-autonomous-loop--pro-active-behavior)
11. [Security — Defense in Depth](#11-security--defense-in-depth)
12. [61 Built-in Tools](#12-61-built-in-tools)
13. [Plugin System — SDK & Development](#13-plugin-system--sdk--development)
14. [Channels — Telegram, Discord, Slack, WhatsApp](#14-channels--telegram-discord-slack-whatsapp)
15. [Workflows — LangGraph State Graphs](#15-workflows--langgraph-state-graphs)
16. [Planning — Tree of Thoughts & Strategic Planning](#16-planning--tree-of-thoughts--strategic-planning)
17. [Observability — Event Bus & Monitoring](#17-observability--event-bus--monitoring)
18. [Research Engine — Karpathy Autoresearch](#18-research-engine--karpathy-autoresearch)
19. [Dashboard — Web Monitoring UI](#19-dashboard--web-monitoring-ui)
20. [Troubleshooting](#20-troubleshooting)

---

## 1. Introduction

**NEUGI (Neural General Intelligence)** is a deterministic multi-agent state machine designed for production-grade reliability at scale. Unlike monolithic chatbots, NEUGI decomposes every task into specialized agent workflows orchestrated by a central director.

### Key Capabilities
- **29 subsystems**, 120+ modules, ~65K lines of code
- **375 collected tests** (373 passing, 2 optional browser tests skipped when Playwright is absent)
- **9 specialized agents** with XP/level progression
- **Karpathy-style dreaming memory** with 3-tier storage
- **6-tier skill system** with YAML frontmatter
- **Full MCP Server** — stdio, HTTP, SSE transports
- **Autonomous pro-active loop** — observe, decide, execute
- **7-layer security** — sandbox, exploit prevention, AES-256 secrets
- **61 built-in tools** across 10 categories
- **4 messaging channels** — Telegram, Discord, Slack, WhatsApp
- **Plugin SDK** with dependency management
- **LangGraph-style workflows** with checkpointing
- **Tree of Thoughts** multi-branch reasoning

---

## 2. Quick Start — Install in 30 Seconds

### Windows (PowerShell)
```powershell
irm https://raw.githubusercontent.com/atharia-agi/neugi_swarm/master/neugi_swarm_v2/install.ps1 | iex
```

### macOS / Linux
```bash
curl -fsSL https://raw.githubusercontent.com/atharia-agi/neugi_swarm/master/neugi_swarm_v2/install.sh | bash
```

### Manual Install
```bash
git clone https://github.com/atharia-agi/neugi_swarm.git
cd neugi_swarm
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -e "neugi_swarm_v2[dev]"
```

### Verify Installation
```bash
neugi status          # Check system health
neugi wizard          # Interactive setup (recommended)
neugi chat            # Start chatting with NEUGI
```

---

## 3. Configuration Deep Dive

NEUGI stores all configuration in `~/.neugi/config.json` — a single JSON file anyone can edit.

### Default Config
```json
{
  "_readme": "NEUGI Config — Edit this file to change your AI setup",
  "version": "2.1.3",
  "llm": {
    "provider": "ollama",
    "model": "qwen2.5-coder:7b",
    "fallback_model": "llama3.2:3b",
    "temperature": 0.7,
    "max_tokens": 4096
  },
  "memory": {
    "enabled": true,
    "daily_ttl_days": 30,
    "dreaming_enabled": true
  },
  "skills": {
    "enabled": true,
    "auto_generate": true
  },
  "dashboard": {
    "enabled": true,
    "port": 17901
  },
  "observability": {
    "enabled": true,
    "max_history": 1000
  }
}
```

### CLI Config Management
```bash
neugi config view              # Show current config
neugi config set llm.model=gpt-4o  # Change model
neugi config set llm.provider=openai
neugi config get llm.temperature   # Get specific value
neugi config export            # Export config
```

### API Key Security
API keys are auto-migrated from plaintext `config.json` to encrypted `SecretManager` (AES-256-GCM) on first load. Keys are never stored in plaintext after first run.

---

## 4. CLI Reference — Every Command

### Core Commands
| Command | Description |
|---------|-------------|
| `neugi start` | Start NEUGI gateway + all subsystems |
| `neugi stop` | Graceful shutdown |
| `neugi status` | Health, agents, sessions, channels |
| `neugi chat` | Interactive chat REPL |
| `neugi doctor` | Diagnose and auto-fix issues |
| `neugi rescue` | Interactive rescue wizard |
| `neugi wizard` | Setup wizard |

### Agent Management
| Command | Description |
|---------|-------------|
| `neugi agents list` | List all agents |
| `neugi agents create <name> --role RESEARCHER` | Create agent |
| `neugi agents configure <name>` | Change agent config |
| `neugi agents remove <name>` | Delete agent |

### Skills
| Command | Description |
|---------|-------------|
| `neugi skills list` | List installed skills |
| `neugi skills install <path>` | Install skill from file |
| `neugi skills enable <name>` | Enable a skill |
| `neugi skills disable <name>` | Disable a skill |

### Memory
| Command | Description |
|---------|-------------|
| `neugi memory read <key>` | Read memory entry |
| `neugi memory write <key> <value>` | Write to memory |
| `neugi memory recall <query>` | Search memory |
| `neugi memory stats` | Memory statistics |
| `neugi memory dream` | Trigger dreaming cycle |

### Soul (Identity)
| Command | Description |
|---------|-------------|
| `neugi soul init` | Initialize soul files |
| `neugi soul show` | Show current soul |
| `neugi soul edit <file>` | Edit soul file |
| `neugi soul remember <note>` | Save continuity note |
| `neugi soul stats` | Soul statistics |

### Autonomous Loop
| Command | Description |
|---------|-------------|
| `neugi autonomous start` | Enable pro-active behavior |
| `neugi autonomous stop` | Disable |
| `neugi autonomous status` | Show loop state |
| `neugi autonomous once` | Run one tick (testing) |

### Sessions & Channels
| Command | Description |
|---------|-------------|
| `neugi sessions list` | List sessions |
| `neugi sessions reset` | Reset session |
| `neugi sessions export` | Export session |
| `neugi channels list` | List channels |
| `neugi channels add <type>` | Add channel |
| `neugi channels remove <name>` | Remove channel |
| `neugi channels test <name>` | Test channel |

### Plugins
| Command | Description |
|---------|-------------|
| `neugi plugins list` | List plugins |
| `neugi plugins install <path>` | Install plugin |
| `neugi plugins enable <name>` | Enable plugin |
| `neugi plugins disable <name>` | Disable plugin |
| `neugi plugins deps <name>` | Show plugin dependencies |
| `neugi plugins graph` | Dependency graph |

### MCP Server
| Command | Description |
|---------|-------------|
| `neugi mcp start` | Start MCP server |
| `neugi mcp stop` | Stop MCP server |
| `neugi mcp status` | MCP server status |
| `neugi mcp bridge connect` | Connect MCP-NEUGI bridge |
| `neugi mcp bridge disconnect` | Disconnect bridge |
| `neugi mcp bridge status` | Bridge status |
| `neugi mcp tools` | List MCP tools |
| `neugi mcp resources` | List MCP resources |
| `neugi mcp prompts` | List MCP prompts |
| `neugi mcp test` | Test MCP connection |

### Workflows & Config
| Command | Description |
|---------|-------------|
| `neugi workflows list` | List workflows |
| `neugi workflows run <name>` | Run workflow |
| `neugi workflows create` | Create workflow |
| `neugi config view` | View config |
| `neugi config set <key>=<value>` | Set config value |
| `neugi backup` | Backup all data |
| `neugi restore` | Restore from backup |

---

## 5. Architecture Overview

NEUGI consists of 29 subsystems organized into layers:

```
┌─────────────────────────────────────────────────────────────┐
│                    USER INTERFACE LAYER                      │
│  CLI (cli/)  │  Dashboard (dashboard/)  │  Chat REPL        │
├─────────────────────────────────────────────────────────────┤
│                    AGENT ORCHESTRATION                       │
│  9 Agents (agents/)  │  A2A Protocol  │  Message Bus        │
│  TypedAgent  │  Orchestrator  │  Process Patterns           │
├─────────────────────────────────────────────────────────────┤
│                    INTELLIGENCE LAYER                        │
│  Memory 3-tier  │  6-tier Skills  │  Planning (ToT, CoV)    │
│  Research Engine  │  Autonomous Loop  │  Learning            │
├─────────────────────────────────────────────────────────────┤
│                    TOOLS & PROTOCOLS                         │
│  61 Tools  │  MCP Server  │  Workflows  │  Web Search       │
│  Browser  │  Computer Use  │  File I/O  │  Code Execution    │
├─────────────────────────────────────────────────────────────┤
│                    INTEGRATION LAYER                         │
│  Channels (TG/DC/SL/WA)  │  Plugins  │  Gateway             │
├─────────────────────────────────────────────────────────────┤
│                    SECURITY LAYER                            │
│  Sandbox  │  Exploit Prevention  │  Secret Manager           │
│  Command Validator  │  Shield Reasoner  │  Governance        │
├─────────────────────────────────────────────────────────────┤
│                    INFRASTRUCTURE                            │
│  Observability  │  Session Mgr  │  Config  │  Backup         │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. Agent System — 9 Archetypes

### Predefined Agents
| Agent | Role | Default Goal |
|-------|------|-------------|
| **Aurora** | RESEARCHER | Discover, synthesize, present comprehensive research |
| **Cipher** | CODER | Write clean, efficient, well-tested code |
| **Nova** | CREATOR | Generate innovative ideas, creative solutions |
| **Pulse** | ANALYST | Analyze data, identify trends, insights |
| **Quark** | STRATEGIST | Long-term strategy, optimize decisions |
| **Shield** | SECURITY | Identify vulnerabilities, enforce security |
| **Spark** | SOCIAL | Manage social presence, build community |
| **Ink** | WRITER | High-quality written content |
| **Nexus** | MANAGER | Coordinate teams, delegate tasks |

### Agent Lifecycle
```
perceive() → think() → act()
    ↑                        │
    └──────── repeat ────────┘
```

- **XP/Level**: 100 XP per level, max level 50
- **Tool allowlists**: Per-agent tool whitelist for security
- **SQLite persistence**: Full state with heartbeat crash recovery
- **Heartbeat**: Default 30s interval, auto-restart on failure

### TypedAgent (Generic)
```python
from agents.typed import TypedAgent

agent = TypedAgent[MyDeps, MyOutput](
    name="my-agent",
    deps=MyDeps(api_key="..."),
    output_type=MyOutput,
)

result = await agent.run("Do something")
# result is automatically validated as MyOutput
```

### Process Patterns
- **Sequential**: Steps execute in order, output feeds next
- **Hierarchical**: Manager decomposes, workers execute in parallel
- **Parallel**: All steps concurrent with optional sync barrier
- **Consensus**: Independent outputs, voting, configurable threshold

---

## 7. Memory System — 3-Tier Karpathy Memory

### Three Tiers
| Tier | Persistence | TTL | Purpose |
|------|------------|-----|---------|
| **CORE** | SQLite | Permanent | High-importance knowledge |
| **DAILY** | SQLite + files | 30 days | Session notes, auto-expired |
| **WORKING** | In-memory | Volatile | Active task context |

### Karpathy Dreaming (Sleep Cycle)
```
Light Sleep → Deep Sleep → REM Sleep
    │              │            │
    ├ Stage        ├ Rank &     ├ Extract
    │ candidates   │ promote    │ patterns
    └ (6 signals)  └ to CORE    └ write DREAMS.md
```

### Memory Scopes
```python
/global/           # World-wide knowledge
/swarm/            # Multi-agent shared
/agent/{id}/       # Per-agent private
/task/{id}/        # Per-task context
/user/{id}/        # Per-user preferences
```

### Search
```python
# Full-text search (FTS5)
results = swarm.memory.search("quantum computing", limit=10)

# Vector search (if embeddings enabled)
results = swarm.memory.search("similar concept", mode="vector")

# Scoped search
results = swarm.memory.search("task", scope="/agent/aurora/")
```

### CLI
```bash
neugi memory write user_prefers "Dark mode"     # Save
neugi memory recall "user preferences"           # Search
neugi memory stats                                # Statistics
neugi memory dream                                # Trigger consolidation
```

---

## 8. Skills System — 6 Tiers

### Skill Tiers (Higher = Higher Precedence)
| Tier | Level | Example |
|------|-------|---------|
| BUNDLED | 0 | Shipped with NEUGI |
| EXTRA | 1 | Community/extra |
| MANAGED | 2 | Admin-managed |
| PERSONAL | 3 | User's personal |
| PROJECT | 4 | Project-specific |
| WORKSPACE | 5 | Active workspace |

### SKILL.md Format
```yaml
---
name: web_search
description: Search the web using DuckDuckGo
version: 1.0.0
author: NEUGI
triggers: ["search the web", "find information", "look up"]
tags: [web, search, utility]
category: research
gating:
  requires: ["web_search"]
token_cost: 50
actions:
  - name: search
    description: Execute web search
    parameters:
      query: {type: string, description: "Search query"}
    returns: {type: string, description: "Search results"}
---
```

### CLI
```bash
neugi skills list                # List installed
neugi skills install path/       # Install from directory
neugi skills enable web_search   # Enable skill
neugi skills disable web_search  # Disable skill
```

---

## 9. MCP Server — Model Context Protocol

NEUGI implements the full MCP specification, enabling any MCP client (Claude Desktop, Cursor, VS Code) to connect to NEUGI's tools, resources, and prompts.

### Starting the Server
```bash
# stdio mode (for local clients)
python -m neugi_swarm_v2.mcp.server.stdio

# HTTP mode (for remote clients)
python -m neugi_swarm_v2.mcp.server.http --port 17902 --sse

# With auth tokens
python -m neugi_swarm_v2.mcp.server.http --port 17902 --sse \
  --auth-tokens '{"admin":"your-token"}' \
  --rate-limit 10 --rate-burst 20
```

### Available MCP Tools
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
| `neugi_status` | NEUGI subsystem health |
| `neugi_memory_search` | Search memory system |
| `neugi_event_history` | Event bus history |
| `neugi_plugin_list` | List loaded plugins |
| `neugi_execute_tool` | Execute NEUGI tool |
| `neugi_soul_read` | Read soul/identity files |
| `neugi_a2a_mesh_status` | Agent mesh status |

### Available MCP Resources
| URI | Description |
|-----|-------------|
| `neugi://server/info` | Server information |
| `neugi://server/capabilities` | MCP capabilities |
| `neugi://server/sse-info` | SSE endpoint info |
| `neugi://memory/...` | NEUGI memory search |
| `neugi://memory/stats` | Memory statistics |
| `neugi://soul/*` | Soul/identity files |

### Claude Desktop Integration
Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "neugi-swarm": {
      "command": "python",
      "args": ["-m", "neugi_swarm_v2.mcp.server.stdio"]
    }
  }
}
```

### SSE Dashboard
```
# Browser-based event streaming
GET http://localhost:17902/sse?events=tool_execution_success

# With auth
GET http://localhost:17902/sse?token=your-token&events=memory_update
```

---

## 10. Autonomous Loop — Pro-Active Behavior

NEUGI acts pro-actively during idle periods via a sovereign loop:

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌──────────┐
│  Observer   │ → │   Decision   │ → │   Executor  │ → │ Reporter │
│  (lihat)    │    │   (pikir)    │    │   (lakukan) │    │ (lapor)  │
└─────────────┘    └──────────────┘    └─────────────┘    └──────────┘
```

### Auto-Start
```python
from neugi_swarm_v2 import NeugiSwarmV2

# Autonomous loop auto-starts as daemon thread
swarm = NeugiSwarmV2()

# User chat resets idle timer
response = swarm.chat("Hello, NEUGI!")

# Manual control
swarm.stop_autonomous()
swarm.start_autonomous()
```

### Safety Mechanisms
| Mechanism | Default | Behavior |
|-----------|---------|----------|
| Circuit breaker | 5 failures | Stops loop, retry after 5 min |
| Idle threshold | 300s (5 min) | Only acts when idle |
| Daily rate limit | 20 actions | Resets at midnight UTC |
| Thread safety | RLock | No race conditions |

### Decision Types
1. **CONSOLIDATE_MEMORY** — Run dreaming cycle
2. **DECOMPOSE_GOAL** — Break down complex goals
3. **RESOLVE_BLOCKER** — Spawn strategist agent
4. **COMPLETE_GOAL** — Mark goal complete
5. **LEARN_SKILL** — Generate skill from patterns
6. **SELF_HEAL** — Health check + reset circuit breaker
7. **PROACTIVE_RESEARCH** — Deep research topics
8. **NOTIFY_USER** — Send notification
9. **OPTIMIZE** — Performance suggestions
10. **IDLE** — No action needed

### CLI Control
```bash
neugi autonomous start     # Enable
neugi autonomous stop      # Disable
neugi autonomous status    # Show state
neugi autonomous once      # Test one tick
```

---

## 11. Security — Defense in Depth

NEUGI implements 5 security layers:

### Layer 1: Execution Sandbox
```python
# Command allowlist/denylist with regex
# Blocks: rm -rf /, mkfs, dd if=, sudo, docker exec, etc.
# Env sanitization: strips AWS keys, tokens, DB URLs
# Resource limits: 30s CPU, 1024MB memory, 4 processes
```

### Layer 2: Secret Manager
```python
# AES-256-GCM encrypted SQLite storage
# Auto-rotation with expiry management
# Secret scanning and redaction in output
# Access audit logging
```

### Layer 3: Exploit Prevention
```python
# 6 detection layers:
# 1. Prompt injection (direct + indirect)
# 2. Jailbreak (DAN, role-play, encoding attacks)
# 3. Data exfiltration (base64, DNS tunneling)
# 4. Privilege escalation (SUID, sudo abuse)
# 5. Supply chain (typosquatting, curl|bash)
# 6. API abuse (rate limiting, patterns)
```

### Layer 4: Command Validator
```python
# 40+ symbolic rules across 8 threat categories
# Neural risk scoring (0-100)
# Explainable verdict with reasoning
```

### Layer 5: Shield Reasoner
```python
# 6-factor risk breakdown
# False positive tracking and learning
# Security posture assessment
# Recommendation generation
```

---

## 12. 61 Built-in Tools

### Web Tools (5)
`web_search`, `web_fetch`, `web_scrape`, `web_monitor`, `web_screenshot`

### Code Tools (5)
`code_execute`, `code_lint`, `code_review`, `code_refactor`, `code_debug`

### File Tools (6)
`file_read`, `file_write`, `file_list`, `file_find`, `file_diff`, `file_archive`

### Data Tools (6)
`data_parse_json`, `data_format_json`, `data_parse_csv`, `data_parse_xml`, `data_transform`, `data_visualize`

### Communication Tools (5)
`comm_webhook`, `comm_email_smtp`, `comm_slack_message`, `comm_discord_message`, `comm_telegram_message`

### System Tools (7)
`system_cpu_info`, `system_memory_info`, `system_disk_info`, `system_network_info`, `system_process_list`, `system_env_vars`, `system_execute_command`

### AI Tools (5)
`ai_summarize`, `ai_translate`, `ai_classify`, `ai_extract_entities`, `ai_generate_text`

### Git Tools (8)
`git_status`, `git_diff`, `git_log`, `git_commit`, `git_push`, `git_pull`, `git_branch`, `git_merge`

### Docker Tools (7)
`docker_build`, `docker_run`, `docker_stop`, `docker_logs`, `docker_exec`, `docker_compose_up`, `docker_ps`

### Security Tools (7)
`security_hash`, `security_encrypt`, `security_decrypt`, `security_sign`, `security_verify`, `security_scan_code`, `security_audit_file`

---

## 13. Plugin System — SDK & Development

### Plugin Structure
```
my-plugin/
├── plugin.json         # Manifest (name, version, deps, entry_point)
├── __init__.py         # Plugin class extending PluginBase
├── tools.py            # Optional: custom tools
└── skills/             # Optional: bundled skills
```

### plugin.json
```json
{
  "name": "my-plugin",
  "version": "1.0.0",
  "description": "My custom NEUGI plugin",
  "entry_point": "my_plugin:MyPlugin",
  "dependencies": [],
  "neugi_version": ">=2.1.0",
  "capabilities": ["tools", "hooks"]
}
```

### Plugin Class
```python
from plugins.plugin_sdk import PluginBase, PluginContext

class MyPlugin(PluginBase):
    def on_load(self, ctx: PluginContext):
        # Register custom tools
        ctx.register_tool("my_tool", my_handler)
        # Register hooks
        ctx.register_hook("pre_tool_call", my_hook)
    
    def on_unload(self):
        # Cleanup resources
        pass
```

### CLI
```bash
neugi plugins list              # List all plugins
neugi plugins install ./my-plugin  # Install plugin
neugi plugins enable my-plugin   # Enable
neugi plugins disable my-plugin  # Disable
neugi plugins deps my-plugin     # Show dependencies
neugi plugins graph              # Visualize dependency graph
```

---

## 14. Channels — Telegram, Discord, Slack, WhatsApp

### Add a Channel
```bash
neugi channels add telegram    # Interactive setup with token
neugi channels add discord     # Interactive setup
neugi channels add slack       # Interactive setup
neugi channels add whatsapp    # Interactive setup
```

### Channel Commands
```bash
neugi channels list            # List all channels
neugi channels test telegram   # Test channel connectivity
neugi channels remove telegram # Remove channel
```

### Programmatic Usage
```python
from neugi_swarm_v2 import NeugiSwarmV2

swarm = NeugiSwarmV2()
swarm.start_channels()

# Broadcast to all channels
await swarm.channel_manager.broadcast("Hello from NEUGI!")

# Send to specific channel
await swarm.channel_manager.send(
    channel_type="telegram",
    message="Hello Telegram!"
)
```

---

## 15. Workflows — LangGraph State Graphs

### Define a Workflow
```python
from workflows.state_graph import StateGraph, NodeDefinition, EdgeDefinition

# Define state
class MyState:
    input_text: str
    processed: bool = False
    result: str = ""

# Define graph
graph = StateGraph(MyState)

# Add nodes
graph.add_node(NodeDefinition(name="process", handler=process_text))
graph.add_node(NodeDefinition(name="format", handler=format_output))

# Add edges
graph.add_edge(EdgeDefinition(source="__start__", target="process"))
graph.add_edge(EdgeDefinition(source="process", target="format"))
graph.add_edge(EdgeDefinition(source="format", target="__end__"))

# Compile and run
compiled = graph.compile()
result = compiled.run({"input_text": "Hello, World!"})
```

### CLI
```bash
neugi workflows list            # List workflows
neugi workflows run my-workflow # Run workflow
neugi workflows create          # Interactive creation
```

---

## 16. Planning — Tree of Thoughts & Strategic Planning

### Tree of Thoughts
```python
from planning.tree_of_thoughts import TreeOfThoughts

tot = TreeOfThoughts(
    branching_factor=3,
    max_depth=5,
    strategy="beam_search",
    beam_width=5,
)

result = tot.solve("Design a scalable microservice architecture")
for solution in result.solutions:
    print(f"Score: {solution.score}")
    print(solution.thought_chain)
```

### Chain of Verification
```python
from planning.chain_of_verification import ChainOfVerification

cov = ChainOfVerification(llm_callback=my_llm)
result = cov.verify("The Eiffel Tower was built in 1889 in Paris")
print(f"Verified: {result.is_verified}")
print(f"Confidence: {result.confidence}")
```

### Goal System
```python
from planning.goal_system import GoalSystem

goals = GoalSystem(storage_path="./goals.db")
goals.create_goal(
    mission="Build a production-ready AI agent",
    objectives=[
        "Set up development environment",
        "Implement core agent logic",
        "Deploy to production"
    ]
)
```

---

## 17. Observability — Event Bus & Monitoring

### Event Bus
```python
from observability.event_bus import get_event_bus

bus = get_event_bus()

# Subscribe to events
bus.subscribe("tool_execution_success", my_handler)
bus.subscribe("tool_execution_failure", my_handler)

# Add middleware (called for ALL events)
bus.add_middleware(logging_middleware)

# Get event history
history = bus.get_history("tool_execution_success")
```

### Built-in Events
```python
"tool_execution_success"   # Tool completed successfully
"tool_execution_failure"   # Tool execution failed
"mcp_call"                # MCP method called
"memory_update"           # Memory modified
"agent_activity"          # Agent started/stopped
```

---

## 18. Research Engine — Karpathy Autoresearch

NEUGI implements Andrej Karpathy's vision of autonomous research:

```
Query → Search → Read → Synthesize → Hypothesize → Iterate → Report
```

### Programmatic Usage
```python
from autonomous.research_engine import ResearchEngine, ResearchConfig

engine = ResearchEngine(
    web_search=swarm.web_search,
    llm_callback=swarm._llm_call,
    memory_system=swarm.memory,
    config=ResearchConfig(max_rounds=3, max_sources_per_round=5),
)

report = engine.research("quantum computing breakthroughs 2026")
print(report.to_markdown())  # Full cited research paper
```

### Research Report Format
- Title and abstract
- Key findings with citations
- Source tracking (URL + access date)
- Hypothesis generation
- Confidence scoring
- Gaps and future directions

---

## 19. Dashboard — Web Monitoring UI

NEUGI includes a real-time web dashboard for monitoring:

```bash
# Dashboard auto-starts on port 17901
neugi start

# Access at:
http://localhost:17901
https://neugi.com/dashboard.html
```

### Dashboard Features
- Subsystem health monitoring
- Setup tab for provider choice, model search, API-key entry, live provider test, and config save
- Agent status and activity
- Memory usage statistics
- Event bus real-time feed
- Channel message log
- Plugin status

### WebSocket Streaming
```javascript
// Connect to live event stream
const ws = new WebSocket("ws://localhost:17901/ws");
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log("NEUGI event:", data);
};
```

---

## 20. Troubleshooting

### Common Issues

**"Connection refused" for MCP server**
```bash
# Ensure MCP server is running
python -m neugi_swarm_v2.mcp.server.http --port 17902
# Check port availability
netstat -an | findstr 17902
```

**Assets not loading on website**
```bash
# vercel.json must use **/* pattern (not index.html only)
# Verify: check vercel.json has "src": "**/*"
# Redeploy from Vercel dashboard
```

**Agent not responding**
```bash
neugi doctor           # Run diagnostics
neugi status           # Check subsystem health
neugi rescue           # Interactive rescue wizard
```

**Memory issues**
```bash
neugi memory stats     # Check memory usage
neugi memory dream     # Force consolidation
```

**Plugin loading failure**
```bash
neugi plugins list     # Check plugin state
neugi plugins deps <name>  # Check dependencies
```

**CI/CD failures**
```bash
# Check GitHub Actions for specific error
# Common: missing dependencies, test discovery errors
# Run locally: pytest tests/ -v -p no:anchorpy --ignore=test_heavy.py
```

### Recovery
```bash
neugi backup           # Create full backup
neugi restore          # Restore from backup
neugi rescue           # Auto-fix common issues
neugi doctor           # Full system diagnostics
```

---

## Quick Reference Card

```bash
# === INSTALL ===
irm https://raw.githubusercontent.com/atharia-agi/neugi_swarm/master/neugi_swarm_v2/install.ps1 | iex

# === SETUP ===
neugi wizard           # Interactive setup
neugi config set llm.model=qwen2.5-coder:7b

# === RUN ===
neugi start            # Start everything
neugi chat             # Interactive chat
neugi status           # Check health

# === MCP ===
neugi mcp start        # Start MCP server (port 17902)

# === MEMORY ===
neugi memory recall "topic"

# === AGENTS ===
neugi agents list

# === SKILLS ===
neugi skills list

# === AUTONOMOUS ===
neugi autonomous status

# === BACKUP ===
neugi backup

# === DOCTOR ===
neugi doctor           # Diagnose & fix
neugi rescue           # Rescue mode
```

---

> **NEUGI v2.1.3** — 29 subsystems, 120+ modules, ~65K LOC, 375 collected tests
>
> GitHub: https://github.com/atharia-agi/neugi_swarm
> Web: https://neugi.com
> MCP Server: port 17902 | Dashboard: port 17901
