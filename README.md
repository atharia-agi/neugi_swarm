# 🤖 NEUGI SWARM - Neural General Intelligence

> **Not just another chatbot. A true reasoning, learning, evolving AI system.**

---

## What is Neugi Swarm?

**Neugi Swarm** is a comprehensive AI agent system that implements TRUE general intelligence:

- 🧠 **Reasoning** - Logical inference and problem solving
- 📚 **Knowledge Representation** - Graph-based knowledge
- 📋 **Planning** - Goal decomposition and execution
- 🧬 **Learning** - Improves from experience
- 🤖 **Autonomy** - Autonomous agents
- 🔄 **Self-Evolution** - Gets better over time

---

## Core Components

| Component | File | Description |
|-----------|------|-------------|
| **Main** | `neugi_swarm.py` | Entry point |
| **Skills** | `neugi_swarm_skills.py` | Skill system (GitHub, Weather, etc) |
| **Channels** | `neugi_swarm_channels.py` | Multi-channel (Telegram, Discord, etc) |
| **Tools** | `neugi_swarm_tools.py` | Tool system (web, code, AI, files) |
| **Memory** | `neugi_swarm_memory.py` | Long-term + short-term memory |
| **Gateway** | `neugi_swarm_gateway.py` | HTTP/WebSocket API server |
| **Voice** | `neugi_swarm_voice.py` | TTS + STT |
| **Agents** | `neugi_swarm_agents.py` | 9 autonomous agents |
| **NGI** | `neugi_swarm_ngi_v1.py` | True Neural General Intelligence |

---

## Features

### ✅ Channels (10 platforms)
```
Telegram, Discord, WhatsApp, Signal, Slack, Teams, SMS, Email, Web
```

### ✅ Tools (15+ tools)
```
Web: search, fetch, browser
Code: execute, debug
AI: llm, embeddings
Files: read, write, list
Data: json, csv
Comm: email, telegram, discord
```

### ✅ Skills (6 built-in)
```
GitHub, Weather, Coding Agent, Health Check, Tmux, ClawHub
```

### ✅ Agents (9 autonomous)
```
Aurora (Researcher), Cipher (Coder), Nova (Creator), 
Pulse (Analyst), Quark (Strategist), Shield (Security),
Spark (Social), Ink (Writer), Nexus (Manager)
```

### ✅ Memory
- Short-term (cache)
- Long-term (SQLite)
- Knowledge graph
- Conversation history

### ✅ Gateway
- REST API
- WebSocket
- Health checks
- Status endpoints

---

## Quick Start

```bash
# Clone
git clone https://github.com/atharia-agi/neugi_swarm.git
cd neugi_swarm

# Run main
python3 neugi_swarm.py

# Run NGI
python3 neugi_swarm_ngi_v1.py

# Run specific component
python3 neugi_swarm_agents.py
python3 neugi_swarm_tools.py
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    NEUGI SWARM                         │
├─────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │  Skills  │  │ Channels │  │  Tools   │            │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘            │
│       │             │             │                    │
│       └─────────────┼─────────────┘                    │
│                     ▼                                  │
│              ┌────────────┐                             │
│              │   Agents   │  (9 autonomous)            │
│              └─────┬──────┘                            │
│                    │                                    │
│       ┌────────────┼────────────┐                      │
│       ▼            ▼            ▼                      │
│  ┌────────┐   ┌────────┐   ┌────────┐                │
│  │Memory │   │Knowledge│   │Gateway │                │
│  └────────┘   └────────┘   └────────┘                │
└─────────────────────────────────────────────────────────┘
```

---

## Version History

| Version | Type | Features |
|---------|------|----------|
| v11.0 | Army | Swarm, Marketplace, Analytics |
| v10.0 | Enterprise | Channels, Voice, Gateway |
| v9.0 | Full | All platforms, tools |
| v8.0 | Multi-agent | 15 agents, battle system |
| v1.0 | NGI | True AGI core |

---

## Configuration

Set your API key:

```bash
export API_KEY="your-api-key"
```

Supports: MiniMax, OpenAI, Anthropic, Ollama

---

## Domain

Ready for **neugi.com**!

---

**Neugi = Neural General Intelligence** 🤖

Built by Auroria for the future of AI.
