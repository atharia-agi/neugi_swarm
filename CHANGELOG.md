# NEUGI SWARM - CHANGELOG

> Complete development history and architecture documentation
> Last Updated: March 14, 2026

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Version History](#version-history)
3. [Architecture](#architecture)
4. [File Descriptions](#file-descriptions)
5. [Known Issues & Fixes](#known-issues--fixes)
6. [Configuration](#configuration)
7. [Installation](#installation)
8. [API Reference](#api-reference)
9. [Development Notes](#development-notes)

---

## Project Overview

**NEUGI SWARM** (Neural General Intelligence Swarm) is an autonomous AI agent system inspired by OpenClaw, Copaw, Perplex Personal Computer, and Claude Cowork.

### Core Features

- **15+ Autonomous Agents** - Specialized agents (Aurora, Cipher, Nova, Pulse, Quark, Shield, Spark, Ink, Nexus)
- **Knowledge Graph** - Structured memory connecting entities and facts
- **Reasoning** - Multi-step logical reasoning with explanations
- **Planning** - Goal decomposition with dependency handling
- **Learning** - Pattern extraction from experience
- **Auto-Recovery** - Automatic error detection and fixing
- **Telegram Gateway** - Mobile control via Telegram bot
- **Multi-OS Support** - Windows, macOS, Linux installers

### Technology Stack

- **Language**: Python 3.8+
- **LLM Backend**: Ollama (local) / Ollama Cloud
- **Database**: SQLite (memory storage)
- **Web Framework**: Built-in HTTP server
- **Mobile**: Telegram Bot API

---

## Version History

### v15.2 (March 14, 2026)

**Code Quality & CI/CD**

- **GitHub Actions CI**: Automated test, lint, and build workflows
- **Ruff Linting**: Fixed 116 lint errors across all Python files
- **Requirements.txt**: Added proper dependencies
- **pyproject.toml**: Added project configuration with pytest/mypy/ruff
- **Test Suite**: Comprehensive tests for landing page, config, installers, core files
- **Toast Notifications**: Professional toast instead of alert() popups
- **OS Selection**: Windows/Mac/Linux buttons with copy command (text only, no logos)
- **Vercel Analytics**: Added to index.html, docs.html, dashboard.html

**Landing Page & Docs**
- **Animated Agent Swarm**: Hero section with 9 agents orbiting Nexus center
- **Custom SVG Icons**: All emojis replaced with custom SVG icons
- **Docs Sidebar**: Passive scroll with auto-highlight, vertical list style
- **Terminal Demo**: Clean design without emojis

**Workspace & Extensions**
- **Workspace**: `~/neugi/workspace/` - Central hub for all agents
- **Enhanced Skills System**: 
  - Multi-format compatible: NEUGI native, OpenClaw, Claude Code, MCP
  - 10 built-in skills (GitHub, Weather, Coding, etc.)
  - **Skill-to-Agent Mapping**: Auto-map skills to appropriate agents based on capabilities
- **Enhanced Plugin System**:
  - Native Python + MCP plugins
  - Install from GitHub/GitLab URL
  - Marketplace support

**Agent Capabilities**
- **Real Tool Execution**: Agents now execute real tasks, not just simulate
  - Aurora: web_search, web_fetch, analyze
  - Cipher: code_execute, file_write
  - Nova: file_write, generate
  - Pulse: json_parse, csv_analyze
  - Ink: file_write
  - Shield: web_fetch, audit

### v15.1 (March 14, 2026)

**Professional Landing Page & Complete Documentation**

- **Animated Agent Swarm**: Hero section with 9 agents orbiting Nexus center
- **Unified Agent Design**: Rectangle-based SVG agents matching Chiper style
- **Terminal Demo**: Interactive wizard flow demonstration
- **Complete docs.html**: Full documentation with installation, API, security, contact
- **Footer**: Contact info (atharia.agi@gmail.com, @atharia_agi), Coming Soon links
- **Responsive Design**: Mobile-friendly with glassmorphism effects

### v15.0 (March 14, 2026)

**Native Web Browser Agent - NO API KEYS NEEDED!**

Based on research from openclaw-free-web-search, Firecrawl, and ScrapeGraphAI:

- **Multi-engine Search**: DuckDuckGo, SearXNG, Brave (all FREE!)
- **Content Extraction**: Jina AI Reader + BeautifulSoup fallback
- **Claim Verification**: Cross-validation with confidence scoring
- **No Brave/SerpAPI needed**: Solves OpenClaw's biggest weakness!
- **Model-agnostic**: Works with any LLM

**NEUGI Wizard v3.0 - All-in-One AI Assistant**
- Setup wizard with AI-powered recommendations
- Auto-repair with AI diagnosis
- System diagnostic with AI advice
- Chat with AI about anything
- Single entry point: `python3 neugi_wizard.py`

### v14.1.0 (March 13, 2026)

**Main Server with Error Recovery**
- Auto error detection
- Auto-launch Technician on failure
- Health monitoring dashboard
- Embedded dashboard HTML

### v2.4 (March 13, 2026)

**Wizard with Telegram Integration**
- Auto-start Ollama if not running
- Telegram bot setup during wizard
- Corporate branding: NEUGI

### v1.0 (March 13, 2026)

**Initial Release**
- Smart assistant with fallback models
- Agent system with real LLM integration

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      NEUGI SWARM                           │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Wizard     │  │  Assistant   │  │  Technician  │      │
│  │   (Setup)    │  │   (Chat)     │  │  (Doctor)    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────┐      │
│  │              AGENT MANAGER                        │      │
│  │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐        │      │
│  │  │AURORA│ │CIPHER│ │NOVA │ │PULSE│ │QUARK│ ...   │      │
│  │  └─────┘ └─────┘ └─────┘ └─────┘ └─────┘        │      │
│  └──────────────────────────────────────────────────┘      │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Memory     │  │    Tools     │  │   Skills     │      │
│  │  (SQLite)    │  │  (50+)       │  │  (Custom)    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────┐      │
│  │              CHANNELS / GATEWAYS                 │      │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐            │      │
│  │  │  HTTP   │ │Telegram │ │  Voice  │            │      │
│  │  │Dashboard│ │  Bot    │ │   TTS   │            │      │
│  │  └─────────┘ └─────────┘ └─────────┘            │      │
│  └──────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

---

## File Descriptions

### Core System Files

| File | Purpose |
|------|---------|
| `neugi_swarm.py` | Main server with HTTP dashboard, health monitoring, error recovery |
| `neugi_wizard.py` | All-in-one AI wizard: setup + repair + diagnose + chat |
| `neugi_assistant.py` | Smart chat assistant with fallback model support |
| `neugi_technician.py` | System doctor - diagnoses AND fixes issues |
| `neugi_telegram.py` | Telegram bot gateway for mobile control |
| `neugi_swarm_browser.py` | Native web browser - FREE search & content extraction |

### Agent System

| File | Purpose |
|------|---------|
| `neugi_swarm_agents.py` | Agent manager with 9 agents (aurora, cipher, nova, pulse, quark, shield, spark, ink, nexus) |
| `neugi_swarm_memory.py` | SQLite-based memory - conversation, facts, preferences, knowledge |
| `neugi_swarm_tools.py` | Tool system (50+ tools) - web, code, AI, files, data, comm |
| `neugi_swarm_skills.py` | Custom skills system |

### Infrastructure

| File | Purpose |
|------|---------|
| `neugi_swarm_channels.py` | Multi-channel management |
| `neugi_swarm_context.py` | Context window guide and model recommendations |
| `neugi_swarm_edge.py` | Edge computing support |
| `neugi_swarm_gateway.py` | API gateway |
| `neugi_swarm_setup.py` | Alternative setup wizard (CLI) |
| `neugi_swarm_voice.py` | Voice/TTS interface |
| `ollama_assistant.py` | Ollama-specific assistant |

### Configuration

| File | Purpose |
|------|---------|
| `config_template.py` | Configuration template |
| `VERIFIED_MODELS.py` | List of verified working models |

### Installers

| File | Purpose |
|------|---------|
| `install.sh` | Linux/Mac installer |
| `install.bat` | Windows installer |
| `neugi` | CLI wrapper (Unix) |
| `neugi.bat` | CLI wrapper (Windows) |
| `neugi.service` | Systemd service file |

---

## Active File Dependencies

### Core System (7 files - required for operation)

| File | Purpose | Imported By |
|------|---------|-------------|
| `neugi_swarm.py` | Main server, HTTP dashboard | CLI, install.sh |
| `neugi_wizard.py` | Setup wizard + Telegram setup | CLI, install.sh |
| `neugi_assistant.py` | Chat assistant (NeugiAssistant) | neugi_swarm.py |
| `neugi_swarm_agents.py` | Agent manager (9 agents) | neugi_swarm.py |
| `neugi_swarm_tools.py` | Tool system (50+ tools) | neugi_swarm.py |
| `neugi_telegram.py` | Telegram bot gateway | neugi_wizard.py |
| `neugi` | CLI wrapper | User |

### Standalone Tools (can run independently)

| File | Purpose | Command |
|------|---------|---------|
| `neugi_technician.py` | System doctor/fixer | `python neugi_technician.py` |
| `neugi_telegram.py` | Telegram bot | `python neugi_telegram.py` |

### Extension Modules (future expansion)

| File | Purpose | Status |
|------|---------|--------|
| `neugi_swarm_channels.py` | Multi-channel (Discord, WhatsApp) | Not imported |
| `neugi_swarm_voice.py` | TTS/STT voice | Not imported |
| `neugi_swarm_skills.py` | Custom skills | Not imported |
| `neugi_swarm_gateway.py` | Alternative HTTP gateway | Not imported |
| `ollama_assistant.py` | Advanced assistant with Groq/OpenRouter | Not imported |

### Reference Files (documentation)

| File | Purpose |
|------|---------|
| `neugi_swarm_edge.py` | Model recommendations |
| `neugi_swarm_context.py` | Context window guide |
| `VERIFIED_MODELS.py` | Verified model list |
| `config_template.py` | Config template |

### Deleted Files

| File | Reason |
|------|--------|
| `neugi_swarm_setup.py` | Duplicate of `neugi_wizard.py` |

### Web

| File | Purpose |
|------|---------|
| `index.html` | Landing page with robot SVG animation |
| `dashboard.html` | Internal dashboard (embedded in neugi_swarm.py) |

---

## Known Issues & Fixes

### Fixed Issues

1. **SyntaxError in neugi_swarm_context.py**
   - Issue: Variable named `2026_MODELS` (invalid Python identifier)
   - Fix: Renamed to valid identifier

2. **SQL Parameter Mismatch in neugi_swarm_memory.py**
   - Issue: 9 params vs 8 values in SQL query
   - Fix: Added missing parameter

3. **Hardcoded Relative Paths**
   - Issue: Using `./data/...` instead of `~/neugi/data/...`
   - Fix: Changed to `os.path.expanduser("~/neugi/data/...")`

4. **Fake Agent Behavior**
   - Issue: Agents were simulating responses instead of calling Ollama
   - Fix: Integrated real LLM calls via Ollama API

5. **Missing Fallback Models**
   - Issue: No fallback if primary model deprecated
   - Fix: Added `nemotron-3-super:cloud` as fallback

6. **Broken Robot Image**
   - Issue: `assets/robot.png` referenced but not in repo
   - Fix: Replaced with inline SVG robot

### Known Limitations

- Ollama Cloud models require internet connection
- Telegram bot requires bot token from @BotFather
- Voice features require system TTS support

---

## Configuration

### Config Location
```
~/neugi/data/config.json
```

### Sample Configuration

```json
{
  "user": {
    "name": "User"
  },
  "assistant": {
    "model": "qwen3.5:cloud",
    "fallback_model": "nemotron-3-super:cloud"
  },
  "ollama": {
    "url": "http://localhost:11434"
  },
  "channels": {
    "telegram": {
      "bot_token": "YOUR_BOT_TOKEN",
      "allowed_users": ["YOUR_USER_ID"]
    }
  },
  "security": {
    "api_key": "your-api-key-here"
  }
}
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_URL` | `http://localhost:11434` | Ollama API URL |
| `NEUGI_PORT` | `19888` | HTTP server port |
| `NEUGI_DIR` | `~/neugi` | Data directory |

---

## Installation

### Quick Install (Linux/macOS)

```bash
curl -fsSL https://neugi.sh/install | bash
```

### Quick Install (Windows)

```powershell
powershell -Command "Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/atharia-agi/neugi_swarm/master/install.bat' -OutFile 'install.bat'"
install.bat
```

### Manual Install

```bash
# Clone repository
git clone https://github.com/atharia-agi/neugi_swarm.git
cd neugi_swarm

# Run setup wizard
python3 neugi_wizard.py

# Start server
python3 neugi_swarm.py
```

### Access

- Dashboard: http://localhost:19888
- API: http://localhost:19888/api/*

---

## API Reference

### HTTP Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard |
| `/health` | GET | Health status |
| `/api/status` | GET | Detailed status |
| `/api/chat` | POST | Chat with assistant |
| `/api/errors` | GET | Error list |
| `/api/fix` | GET | Auto-fix issues |
| `/technician` | GET | Technician dashboard |

### Chat API

```bash
curl -X POST http://localhost:19888/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello!", "user": "User"}'
```

---

## Development Notes

### Model Selection

**Recommended Models (2026):**

1. **qwen3.5:cloud** - Primary model (fast, good reasoning)
2. **nemotron-3-super:cloud** - Fallback model
3. **qwen2.5:14b** - Local alternative
4. **llama3.3:70b** - High capability

### Context Windows

| Model | Context | Best For |
|-------|---------|----------|
| qwen3.5:cloud | 32K+ | General use |
| nemotron-3-super:cloud | 32K+ | Reasoning |
| llama3.3:70b | 128K | Large documents |

### Adding Custom Agents

```python
from neugi_swarm_agents import Agent, AgentManager

# Create custom agent
my_agent = Agent(
    id="my_agent",
    name="My Agent",
    role="custom",
    system_prompt="Your system prompt here"
)

# Register
manager = AgentManager()
manager.agents["my_agent"] = my_agent
```

### Adding Custom Tools

```python
from neugi_swarm_tools import Tool, ToolManager

# Create custom tool
my_tool = Tool(
    id="my_tool",
    name="My Tool",
    category="custom",
    description="What it does",
    function=my_function
)

# Register
tools = ToolManager()
tools.tools["my_tool"] = my_tool
```

---

## Troubleshooting

### Ollama Not Running

```bash
# Start Ollama
ollama serve

# Or let NEUGI auto-start it
python3 neugi_wizard.py
```

### Port Already in Use

```bash
# Find process using port 19888
lsof -i :19888

# Kill it
kill <PID>
```

### Reset Configuration

```bash
# Run wizard again
python3 neugi_wizard.py

# Or manually delete config
rm ~/neugi/data/config.json
```

### Check Logs

```bash
# Dashboard shows errors at /api/errors
curl http://localhost:19888/api/errors
```

---

## Contact

- **Email**: atharia.agi@gmail.com
- **Twitter**: https://x.com/atharia_agi
- **GitHub**: https://github.com/atharia-agi/neugi_swarm

---

## License

MIT License - See LICENSE file for details

---

## Credits

Inspired by:
- OpenClaw
- Copaw
- Perplex Personal Computer
- Claude Cowork

Built with:
- Ollama
- Python 3.8+
- SQLite

---

*This changelog is maintained by the NEUGI development team.*
*Last updated: March 14, 2026*
