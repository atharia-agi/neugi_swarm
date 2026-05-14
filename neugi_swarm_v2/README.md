# NEUGI SWARM V2 — The Ultimate Agentic AI Framework

> **53,871 lines. 96 files. 16 subsystems. Zero compromises.**

The most advanced open-source agentic AI framework ever built. Surpassing OpenClaw, CrewAI, AutoGen, LangGraph, and Paperclip combined.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        NEUGI GATEWAY V2                          │
│  ┌───────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ WebSocket  │  │ HTTP REST│  │  Cron    │  │  Heartbeat    │  │
│  │   RPC      │  │   API    │  │Scheduler │  │  Execution    │  │
│  └─────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬────────┘  │
│        └──────────────┴──────────────┴───────────────┘           │
│                            │                                     │
│                    ┌───────▼───────┐                              │
│                    │   ROUTER      │                              │
│                    │ (DM/Group/    │                              │
│                    │  Cron/Webhook)│                              │
│                    └───────┬───────┘                              │
└────────────────────────────┼─────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   ┌────▼────┐         ┌────▼────┐         ┌────▼────┐
   │CHANNELS │         │ SESSIONS│         │  MCP    │
   │Telegram │         │Isolation│         │ Server  │
   │Discord  │         │Compaction│         │(Claude/ │
   │Slack    │         │Steering │         │OpenClaw)│
   │WhatsApp │         │Checkpts │         │         │
   └────┬────┘         └────┬────┘         └────┬────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
              ┌─────────────▼─────────────┐
              │     NEUGI ASSISTANT V2     │
              │  ┌──────────────────────┐  │
              │  │  Tool-Use Loop (ReAct)│  │
              │  │  Planning Mode        │  │
              │  │  Sub-Agent Spawning   │  │
              │  │  Steering Mode        │  │
              │  │  Strict Execution     │  │
              │  └──────────────────────┘  │
              └─────────────┬──────────────┘
                            │
    ┌───────────────────────┼───────────────────────┐
    │          CORE SUBSYSTEMS                       │
    │                                               │
    │  ┌──────────┐  ┌──────────┐  ┌────────────┐  │
    │  │  MEMORY  │  │  SKILLS  │  │  AGENTS    │  │
    │  │Karpathy  │  │ 6-Tier   │  │Orchestrator│  │
    │  │Dreaming  │  │ Gating   │  │Evaluator   │  │
    │  │Scopes    │  │ Compaction│ │ MessageBus │  │
    │  └──────────┘  └──────────┘  └────────────┘  │
    │                                               │
    │  ┌──────────┐  ┌──────────┐  ┌────────────┐  │
    │  │ CONTEXT  │  │ PLANNING │  │   TOOLS    │  │
    │  │Assembly  │  │Tree of   │  │61 Builtins │  │
    │  │TokenBudget│ │Thoughts  │  │Composer    │  │
    │  │CacheStab │  │Verify    │  │Generator   │  │
    │  └──────────┘  └──────────┘  └────────────┘  │
    │                                               │
    │  ┌──────────┐  ┌──────────┐  ┌────────────┐  │
    │  │GOVERNANCE│  │ SECURITY │  │  WORKFLOWS │  │
    │  │Budget    │  │Sandbox   │  │StateGraph  │  │
    │  │Approval  │  │NeuroSym  │  │Checkpoint  │  │
    │  │Audit     │  │Exploit   │  │HumanInLoop │  │
    │  └──────────┘  └──────────┘  └────────────┘  │
    │                                               │
    │  ┌──────────┐  ┌──────────┐  ┌────────────┐  │
    │  │ PLUGINS  │  │ LEARNING │  │   CLI +    │  │
    │  │SDK       │  │Pattern   │  │  Dashboard │  │
    │  │Loader    │  │Feedback  │  │  Wizard    │  │
    │  │Hooks     │  │Dashboard │  │  Interactive│  │
    │  └──────────┘  └──────────┘  └────────────┘  │
    └───────────────────────────────────────────────┘
```

## Subsystems

### 1. Memory System (5 files, 2,563 lines)
**Surpasses**: OpenClaw Memory, CrewAI Memory, LangGraph Memory

- **Karpathy Dreaming Consolidation**: Light Sleep → Deep Sleep → REM Sleep cycle
  - 6-signal weighted ranking: relevance (0.30), frequency (0.24), query diversity (0.15), recency (0.15), consolidation (0.10), conceptual richness (0.06)
  - Thresholds: minScore 0.75, minRecallCount 3, minUniqueQueries 3
  - Only Deep Sleep writes to CORE.md
  - Grounded backfill for historical recovery
- **Hierarchical Scoped Memory**: `/swarm/`, `/agent/{id}/`, `/task/{id}/`, `/user/`, `/global/`
- **3-Tier Storage**: CORE.md (permanent), daily/*.md (30-day TTL), working.json (active context)
- **Composite Scoring**: TF-IDF semantic + recency decay + importance + frequency
- **SQLite FTS5** full-text search with graceful fallback
- **Knowledge Graph**: entity-relation-target triples with confidence
- **Non-blocking background saves** with read barriers

### 2. Skills System (6 files, 2,119 lines)
**Surpasses**: OpenClaw Skills, Claude Code Commands, MCP Tools

- **6-Tier Loading**: workspace > project > personal > managed > bundled > extra
- **Name Collision Resolution**: highest tier wins
- **SKILL.md Parsing**: YAML frontmatter + markdown instructions
- **Gating at Load Time**: bins, env vars, config, OS, always bypass
- **Token Impact Calculation**: deterministic cost per skill (~24 tokens baseline)
- **3 Compaction Tiers**: full, compact, truncated (maxSkillsInPrompt)
- **Agent Allowlists**: per-agent skill filtering
- **Natural Language Trigger Matching**: weighted scoring (name 0.4, trigger 0.3, keyword 0.2, description 0.1)
- **Skill Workshop**: auto-generate SKILL.md from observed procedures
- **Import/Export**: NEUGI, OpenClaw, Claude Code, MCP, LangChain formats

### 3. Agent System (7 files, 2,920 lines)
**Surpasses**: CrewAI, AutoGen, Anthropic Orchestrator-Workers

- **CrewAI-Style Roles**: role, goal, backstory per agent
- **9 Pre-Configured Agents**: Aurora (researcher), Cipher (coder), Nova (creator), Pulse (analyst), Quark (strategist), Shield (security), Spark (social), Ink (writer), Nexus (manager)
- **Orchestrator-Worker Pattern**: dynamic task decomposition, parallel execution, result synthesis
- **Evaluator-Optimizer Loop**: generate → evaluate → refine with quality gates
- **4 Process Patterns**: Sequential, Hierarchical, Parallel, Consensus
- **Event-Driven Message Bus**: typed protocol, pub/sub, dead letter queue, persistence
- **XP/Level System** with skill progression
- **Heartbeat Execution**: resume task context across restarts
- **Sub-Agent Spawning**: create temporary workers dynamically

### 4. Session Management (5 files, 2,799 lines)
**Surpasses**: OpenClaw Sessions, LangGraph Checkpointing

- **4 Isolation Modes**: shared, per-peer, per-channel-peer, per-account-channel-peer
- **Daily/Idle Reset**: configurable thresholds
- **Exclusive Write Locks**: safe compaction
- **Checkpointing**: before/after snapshots with restore
- **3 Compaction Strategies**: summarize, truncate, hybrid
- **Steering Mode**: real-time course correction without aborting
- **JSONL Transcripts**: append-only with fsync, search, export, pruning

### 5. Context Optimization (5 files, 3,427 lines)
**Surpasses**: OpenClaw Prompt Assembly, Claude Context Management

- **10 Modular Sections**: identity, heartbeat, skills, memory, project context, voice/tone, model aliases, bootstrap, tools, conversation
- **3 Prompt Modes**: full (main agent), minimal (sub-agents/crons), none
- **Token Budget**: 10 model presets, priority-based overflow, emergency truncation
- **KV Cache Stability**: SHA-256 fingerprinting, normalization, cache hit detection, prompt diffing
- **Context Injection**: relevance scoring, 5 scope levels, dynamic swapping, TTL-based freshness

### 6. MCP Server (6 files, 3,104 lines)
**Surpasses**: Official MCP SDK, Claude Code MCP

- **Full MCP Spec Compliance**: tools, resources, prompts, ping, logging, subscriptions
- **Dual Transport**: stdio (primary) + Streamable HTTP (secondary)
- **Version Negotiation** per MCP spec
- **Dynamic Tool Registry**: auto-registers NEUGI subsystem tools
- **Resource System**: file/memory/agent/skill resources with URI templates
- **Prompt Templates**: system, task, multi-turn with composition
- **Cursor-Based Pagination** for list endpoints
- **Tool Call Logging/Tracing** with duration tracking

### 7. Governance Layer (5 files, 3,378 lines)
**Surpasses**: Paperclip Governance, Enterprise AI Controls

- **Hierarchical Budget Tracking**: swarm > agent > task, warning thresholds (50/75/90%), hard stops
- **Multi-Level Approval Gates**: configurable rules, auto-approval for low-risk, timeout handling
- **Immutable Audit Log**: append-only SQLite with hash chain verification
- **Tool Call Tracing**: who called what, when, with what args, result
- **Policy Engine**: 12 condition operators, allow/deny/require_approval/rate_limit, default-deny

### 8. Plugin Architecture (5 files, 2,624 lines)
**Surpasses**: OpenClaw Plugins, LangChain Integrations

- **Plugin SDK**: register_tool, register_skill, register_hook, register_route
- **Manifest-Based Discovery**: neugi.plugin.json with schema validation
- **Topological Dependency Resolution**: Kahn's algorithm
- **Sandboxed Execution**: timeout protection, isolated context
- **8 Lifecycle Hooks**: pre/post tool call, pre/post response, on_error, on_memory_save, session start/end
- **Hot Reload**: file watcher support
- **SemVer**: parsing and constraint checking (^, ~, >=)

### 9. Graph Workflow Engine (5 files, 2,753 lines)
**Surpasses**: LangGraph StateGraph, CrewAI Flows

- **StateGraph**: typed state, nodes, conditional/unconditional edges, sub-graph composition
- **Workflow Executor**: sequential/parallel execution, retry with exponential backoff, error strategies (ABORT/RETRY/SKIP)
- **Durable Execution**: SQLite checkpoints, resume from checkpoint, versioning, diff
- **Human-in-the-Loop**: approval gates, pause points, state modification, override, timeout
- **Topological Sort** with cycle detection, parallel execution levels

### 10. Auto-Learning System (5 files, 3,027 lines)
**Surpasses**: OpenClaw Skill Workshop, Continuous Learning

- **Pattern Tracking**: task/tool/skill/agent patterns, repeated sequence detection, scoring
- **Auto Skill Generation**: detect 3+ recurring patterns, generate SKILL.md, quality scoring, approval workflow
- **Feedback Loop**: explicit/implicit feedback, degradation detection, auto-tune recommendations
- **Learning Dashboard**: skills learned, performance trends, skill usage analytics, optimization recommendations

### 11. Gateway Server (5 files, 3,827 lines)
**Surpasses**: OpenClaw Gateway, Paperclip Server

- **WebSocket RPC**: primary control plane with device identity
- **HTTP REST API**: secondary interface
- **Pairing & Trust**: device-based pairing with signed challenge nonces
- **Message Routing**: DM/group/cron/webhook/sub-agent routing
- **Device Management**: registration, tokens, trust levels, revocation
- **Heartbeat Execution**: DB-backed wakeup queue, coalescing, budget checks, execution lock
- **Cron Scheduler**: expression parsing, job management, dependency chains, concurrent limiting

### 12. Advanced Planning (6 files, 3,763 lines)
**Surpasses**: All existing planning systems

- **Tree of Thoughts**: 5 search strategies (best-first, BFS, DFS, beam, Monte Carlo), configurable branching/pruning
- **Chain of Verification**: claim extraction, independent verification, discrepancy detection, auto-revision
- **Self-Reflection**: post-action analysis, root cause classification, pattern detection, confidence calibration
- **Goal System**: 4-level hierarchy (mission→objective→task→subtask), decomposition, dependency tracking, ancestry tracing
- **Strategic Planner**: LLM-generated plans, milestone Gantt charts, risk heatmaps, quality scoring, plan adaptation

### 13. Tool Composition Engine (6 files, 4,798 lines)
**Surpasses**: LangChain Tools, OpenClaw Tools

- **61 Built-in Tools** across 10 categories: Web (5), Code (5), File (6), Data (6), Comm (5), System (7), AI (5), Git (8), Docker (7), Security (7)
- **Tool Composition**: sequential, parallel, conditional, loop composition with validation
- **Dynamic Tool Generation**: from NL descriptions, observed patterns, OpenAPI/Swagger specs
- **Advanced Execution**: retry/backoff, caching, rate limiting, circuit breaker, result transformation
- **Tool Registry**: categorization, versioning, allowlists, usage stats, health monitoring

### 14. Channel Integrations (7 files, 4,171 lines)
**Surpasses**: OpenClaw Channels, Multi-platform bots

- **Telegram**: Bot API, long polling + webhook, inline keyboards, admin commands, rate limiting
- **Discord**: REST API, slash commands, role-based access, threads, embed builder
- **Slack**: Events API + Web API, Block Kit, interactive components, signature verification
- **WhatsApp**: Meta Cloud API, templates, interactive buttons/lists, media handling
- **Unified Channel Manager**: multi-channel orchestration, routing, format overrides, health monitoring

### 15. Security Sandbox (6 files, 4,596 lines)
**Surpasses**: All existing agentic security systems

- **7-Layer Sandbox**: command allowlist/denylist, path restriction, resource limits, process isolation, filesystem sandboxing, network sandboxing, env sanitization
- **Neuro-Symbolic Validation**: 25+ symbolic rules + neural risk scoring, combined verdict, explainable decisions
- **6-Vector Exploit Prevention**: prompt injection, indirect injection, jailbreak, data exfiltration, privilege escalation, supply chain
- **Secret Management**: AES-256-GCM encryption, rotation, access logging, leak scanning, classification
- **Explainable Security**: risk scoring (0-100), threat classification, confidence scoring, FP tracking

### 16. CLI + Dashboard (6 files, 5,631 lines)
**Surpasses**: All existing agentic UIs

- **CLI**: 17 commands with subcommands (start, stop, status, chat, agents, skills, memory, sessions, channels, plugins, workflows, config, backup, restore, update, doctor, wizard)
- **8-Step Setup Wizard**: skip/redo, progress save/resume, 6 languages (EN/ID/ES/FR/DE/JP)
- **Interactive Chat**: Rich terminal UI, command palette, tab completion, streaming, token tracking
- **Web Dashboard**: Glass morphism dark theme, real-time metrics, agent grid, chat interface, 20 REST API endpoints, WebSocket updates

## Quick Start

```bash
# Install
pip install neugi-swarm-v2

# Interactive setup wizard
neugi wizard

# Start the gateway
neugi start

# Chat
neugi chat

# Open dashboard
# http://localhost:19888
```

## Comparison

| Feature | NEUGI v2 | OpenClaw | CrewAI | AutoGen | LangGraph | Paperclip |
|---------|----------|----------|--------|---------|-----------|-----------|
| Memory Systems | 3-tier + dreaming | 3-tier | Unified | Basic | Basic | Basic |
| Skill Loading | 6-tier + gating | 6-tier | None | None | None | None |
| Agent Patterns | 5 patterns | 2 | 2 | 3 | 1 | 1 |
| Planning | 5 advanced | Basic | None | None | None | None |
| Tool Count | 61 builtins | ~20 | ~15 | ~10 | ~10 | ~5 |
| Tool Composition | Yes | No | No | No | No | No |
| Channels | 4 platforms | 20+ | 0 | 0 | 0 | 0 |
| Security | 5 layers | 2 | 1 | 1 | 1 | 2 |
| Governance | 4 systems | 1 | 0 | 0 | 0 | 3 |
| Workflows | StateGraph + checkpoints | None | Flows | None | StateGraph | Basic |
| Plugins | Full SDK | Full SDK | None | Extensions | None | Basic |
| Auto-Learning | 4 systems | 1 | 0 | 0 | 0 | 0 |
| CLI Commands | 17 | 12 | 3 | 2 | 1 | 5 |
| Dashboard | Full web UI | Basic | None | None | None | None |
| Lines of Code | 53,871 | ~200K | ~15K | ~50K | ~30K | ~40K |

## License

MIT — Build the future.
