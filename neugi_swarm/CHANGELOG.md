# NEUGI SWARM - CHANGELOG

> Complete development history and architecture documentation
> Last Updated: March 15, 2026
> Version: 17.0.0

---

## Table of Contents

## Project Overview

### Sovereign Intelligence

NEUGI is an autonomous, multi-agent swarm intelligence system designed to run on local infrastructure. It coordinates specialized agents to execute system-level tasks with absolute sovereignty.

## Version History

### v17.0.0 (March 16, 2026) - DEVELOPER SUITE

#### New Features

- **Command Palette** (`neugi_command_palette.py`): Ctrl+K quick access with fuzzy search, 30+ commands
- **File Manager** (`neugi_file_manager.py`): Full-featured file manager - browse, copy, move, delete, search, hash
- **Code Interpreter** (`neugi_code_interpreter.py`): Sandboxed Python/JavaScript/SQL execution
- **Plugin Marketplace** (`neugi_marketplace.py`): Browse & install 12 official plugins
- **Encryption Layer** (`neugi_encryption.py`): File encryption, password hashing, secure storage, key management

#### New Menu Options (28-32)

- 28. ⌨️ Command Palette - Quick command access
- 29. 📁 File Manager - Full file operations
- 30. 💻 Code Interpreter - Sandboxed execution
- 31. 🛒 Plugin Marketplace - Browse & install plugins
- 32. 🔒 Encryption Tools - Security utilities

### v16.0.0 (March 16, 2026) - VISUAL AUTOMATION

#### New Features

- **Visual Workflow Builder** (`neugi_workflow_builder.py`): Web-based drag-and-drop workflow editor with 8 node types (trigger, action, condition, HTTP, transform, delay, log, notification)
- **Database Layer** (`neugi_database.py`): SQLite persistence for conversations, messages, memory, workflows, metrics, audit logs
- **Automation Engine** (`neugi_automation.py`): Rule-based automation with schedule/webhook/keyword triggers, conditions, action chains

#### New Menu Options (25-27)

- 25. 🎨 Visual Workflow Builder - Web-based editor
- 26. 🤖 Automation Engine - Rule-based automation
- 27. 🗄️ Database Management - SQLite persistence

### v15.9.0 (March 15, 2026) - API & MONITORING

#### New Features

- **REST API Server** (`neugi_api.py`): FastAPI-based REST API with endpoints for agent management, memory access, skill execution, system metrics
- **Docker Management** (`neugi_docker.py`): Docker container management - list, start, stop, logs, pull images
- **Advanced Monitoring** (`neugi_monitoring.py`): System monitoring with CPU, Memory, Disk, Network metrics, Prometheus export, alerts

#### New Menu Options (22-24)

- 22. 🌍 REST API Server - FastAPI server
- 23. 🐳 Docker Management - Container management
- 24. 📈 Advanced Monitoring - System metrics & Prometheus

### v15.8.0 (March 15, 2026) - EXTENDED ECOSYSTEM

#### New Features

- **App Integrations** (`neugi_app_integrations.py`): OAuth-based connections to 15+ apps (Gmail, Slack, GitHub, Linear, Notion, etc.)
- **Workflow Engine** (`neugi_workflows.py`): JSON-based workflow automation with step dependencies, built-in actions
- **Test Framework** (`neugi_test.py`): Built-in test runner for NEUGI components

#### New Menu Options (19-21)

- 19. 📱 App Integrations - OAuth connections
- 20. 🔀 Workflow Automation - Create & run workflows  
- 21. 🧪 Run Tests - Test suite

### v15.7.0 (March 15, 2026) - BROWSEROS INTEGRATION

#### BrowserOS-Style Features Implemented

- **Two-Tier Memory System** (`neugi_memory_v2.py`): Core + Daily memory with 30-day auto-expire, inspired by BrowserOS memory architecture
- **Soul System** (`neugi_soul.py`): Personality management with 5 presets (default, assistant, senior_dev, debugger, security)
- **Skills V2** (`neugi_skills_v2.py`): Full BrowserOS SKILL.md format with YAML frontmatter, scripts/, references/ support
- **MCP Server** (`neugi_mcp_server.py`): 30+ tools exposed via MCP protocol - compatible with Claude Code, OpenClaw, Gemini CLI
- **Native Scheduler** (`neugi_scheduler.py`): Daily/hourly/minute scheduling with background execution
- **Cowork** (`neugi_cowork.py`): Filesystem sandbox with 7 tools (read, write, edit, bash, find, grep, ls)
- **Wizard Integration**: All new features integrated into neugi_wizard.py menu (Options 14-18)

#### New Menu Options

- 14. 🧊 Memory System - Two-tier memory management
- 15. 🎭 Soul - Personality/behavior configuration
- 16. 📚 Skills V2 - BrowserOS-style skills
- 17. ⏰ Task Scheduler - Native scheduled tasks
- 18. 🌐 MCP Server - Start MCP server for Claude Code

### v15.6.1 (March 15, 2026) - DEEP AUDIT & BUGFIX

#### Code Quality & Stability Fixes

- **Critical Imports Fixed**: Added missing `subprocess`, `re`, and `sys` imports in `neugi_wizard.py`
- **AIAgent.chat() Added**: Implemented missing non-streaming chat method for Wizard's AI diagnostics
- **Color Palette Extended**: Added `WHITE` color constant to C class for better terminal output
- **run_logs() Implemented**: Added View System Logs feature to Wizard menu (Option 5)
- **Version Sync**: Updated `neugi_swarm.py` VERSION from 15.2.0 to 15.6.0
- **Windows Compatibility**: Fixed `getloadavg()` error on Windows by adding platform check
- **Telegram Fix**: Fixed `/topology` command dict iteration bug
- **Plugin Manager**: Added missing `discover_plugins()` public method
- **Security Audit**: Replaced deprecated `os.popen("date")` with `datetime.now().isoformat()`
- **Updater Safety**: Replaced dangerous `subprocess.run(["rm", "-rf"])` with `shutil` for safer file operations

#### Architecture Improvements

- All core modules now properly import required dependencies
- Error handling improved across the codebase
- Cross-platform compatibility enhanced (Windows/Linux/macOS)

### v15.6.0 (March 15, 2026) - THE PARITY UPDATE (Phase 24)

#### Sovereign Parity & Observability

- **TUI/GUI Feature Parity**: Upgraded `neugi_wizard.py` (TUI) to include Network Topology, Skill Registry, and Live Monitoring, matching the Dashboard's capabilities.
- **Log Observer**: Implemented a unified system log viewer for both the Wizard (TUI) and Dashboard (GUI). Added `/api/logs` to the engine.
- **Conflict-Resilient Auto-Boot**: Refactored `neugi_start.bat` and `neugi.bat` with process and port detection to prevent duplicate engine/Ollama instances.
- **Sovereign Nexus Chat**: Enhanced Wizard's chat to automatically detect and link with the Sovereign Nexus (Swarm Engine API) for multi-agent reasoning parity.
- **Standardized Engine Lifecycle**: Unified engine startup logic across all entry points, ensuring safe deployment via port-aware wrappers.
- **Telegram Parity**: Upgraded the Telegram bot with `/logs`, `/topology`, `/monitor`, and `/fix` commands for complete mobile sovereignty.

### v15.5.0 (March 15, 2026) - THE SOVEREIGN UPDATE (Phase 17-22)

#### Architectural Consolidation

- **Sovereign Wizard**: Consolidated all diagnostic, repair, and provisioning logic from the decommissioned `neugi_technician.py` into `neugi_wizard.py`.
- **Unrestricted Execution**: Granted the Wizard core full system execution authority by default, removing all legacy safety command filters.
- **Neural Stability Layer**: Injected "Core Directives" and risk-aware logic guardrails to balance power with precision.
- **Mandatory Risk Disclaimers**: Implemented high-profile warning systems and explicit user agreement prompts in installation (`install.sh`, `install.bat`) and setup flows.

#### Wizard Branding & Usability

- **Console Rebranding**: Renamed `technician.html` to `wizard.html` and updated all navigation links for role consistency across the ecosystem.
- **Simplified Setup**: Replaced the 'I AGREE' text confirmation with a swift `y/n` prompt for better developer efficiency.
- **Enhanced Documentation**: Refreshed `README.md`, `index.html`, and `docs.html` with hard-hitting risk disclaimers and "Sovereign Intelligence" branding.
- **Wizard-Centric Error Handling**: All agent error paths now route through the Wizard for autonomous resolution.

### v15.4.0 (March 15, 2026) - The "Ultimate Polish" & Reliability Update

#### Phase 13: System-Wide Functional Audit & Recursive Repair

- **Dashboard Integrity**: Resolved JS errors by restoring missing DOM IDs (`statusDot`, `statusText`) in the sidebar telemetry.
- **Ecosystem Branding**: Replaced custom SVG logos with a safe, minimalist text-based integration section for **Ollama, MiniMax, OpenCode,** and **Antigravity**.
- **UX Fixes**: Repaired all dead footer links and re-linked the main brand logo to the landing page.
- **Docs Level-Up**: Integrated "Copy to Clipboard" functionality with visual feedback for every code snippet.

#### Phase 14: Advanced Functional Polish & Interactivity

- **Live Telemetry**: Implemented high-frequency metric simulation in `technician.html` (Memory & LLM loads) for a real-time system feel.
- **Documentation Search**: Added a real-time, client-side search/filter engine to the docs sidebar.
- **Chat Realism**: Enhanced Showcase Mode in `dashboard.html` with randomized "Thinking..." delays (400ms-1200ms) and automatic input focus.

#### Phase 1: Deep LLM Wiring & True Agentic Reasoning

- **Dynamic Tool Selection**: Ripped out hardcoded `if-elif` logic in `neugi_swarm_agents.py` (`_think` and `_act`). Agents now truly prompt the LLM to dynamically select tools based on capabilities, optimized for 1B LLMs.
- **Real Tool Execution**: Abolished simulated mock returns (e.g. `"Would execute code"`) in `neugi_swarm_tools.py`. Tools like `_code_execute` now use live `subprocess` with timeouts, and `_llm_think` connects directly to local Ollama.
- **Database Fix**: Repaired `sqlite3.OperationalError` in `agents` table insertions.

#### Phase 2: Ultimate Usability & OpenClaw Competitiveness

- **Zero-Config Intelligence**: Modified `neugi_assistant.py` to no longer require `config.json`. If missing, the system silently pings local Ollama APIs and dynamically binds the best available model (prioritizing 1B/8B Qwen variants).
- **Silent Auto-Healing**: Enhanced `neugi_wizard.py` to automatically execute a background `subprocess` to launch Ollama if it detects it offline, eliminating friction without prompting users.
- **Dynamic Skill Spawning**: Overhauled `neugi_swarm_skills.py` to replace simulated `"Would install"` functions. `install_from_url` now successfully fetches raw Python skills from the web and dynamically hot-loads them into the active swarm using `importlib`. `execute()` now hooks into live Python processes.

#### Phase 4: Swarm Autonomy & Extended Tooling

- **Sudo-level Execution Power**: Introduced the global `/godmode` feature explicitly overriding the 1B framework's Python-only safety loop.
- **Unrestricted Code Tools**: If God Mode is active, `_code_execute` in `neugi_swarm_tools.py` lifts process timeouts and permits raw `bash/powershell` routing mapping via `subprocess.run(shell=True)`.
- **System-Prompt Context Upgrade**: Injected dynamic roleplaying flags to ensure the agent uses God Mode appropriately when active.

#### Phase 5: Ultimate CLI Dashboard (TUI)

- **Rich Terminal Interface**: Integrated `rich` and `prompt_toolkit` to deliver a professional, Claude-tier interactive CLI.
- **Dynamic Spinners**: Replaced static loading dots with animated Markdown-rendered streams.
- **Swarm Management**: Deepened native tool access (`git_execute`, `list_directory`, etc.).

#### Phase 7: Ultra-Premium UI/UX Ecosystem

- **Enterprise-Tier Web Dashboard**: Completely rewrote `index.html`, `dashboard.html`, and `docs.html` conforming to a dark, minimalist OpenAI/Anthropic aesthetic.
- **Pixel-Art Vector Avatars**: Hand-coded 8 bespoke 24x24 retro SVG avatars replacing default emojis, perfectly mapping to each Swarm Node's specialized function (e.g., Crown for Quark, Shield for Shield, Scanner for Aurora).
- **UI Polishing**: Scaled agent avatars to 48px and removed container frames on the landing page for a cleaner, bolder enterprise aesthetic.

#### Phase 8: Advanced Swarm Autonomy (Recursive Orchestration)

- **Recursive Reasoning Loop**: Enabled `neugi_assistant.py` to detect tool calls and recursively re-prompt the LLM with results, allowing multi-step autonomous behavior.
- **Dynamic Swarm Delegation**: Integrated `AgentManager` into the core CLI loop. The Assistant can now spin up specialized sub-agents (Aurora, Cipher, etc.) on-the-fly via the `delegate_task` tool.
- **Live TUI Streaming**: Transitioned the Rich CLI to a true streaming architecture with real-time feedback for tool execution and sub-agent results.

### v15.2.0 (March 14, 2026)

#### All Changes Since Project Start

#### Code Quality & Engineering Standards

- GitHub Actions CI: Automated test, lint, and build workflows
- Ruff Linting: Fixed 116+ lint errors across all Python files
- Requirements.txt: Added proper dependencies
- pyproject.toml: Added project configuration with pytest/mypy/ruff
- Test Suite: Comprehensive tests for landing page, config, installers, core files

#### UI/UX Improvements

- Toast Notifications: Professional toast instead of alert() popups
- OS Selection: Windows/Mac/Linux buttons with copy command (text only)
- Vercel Analytics: Added to index.html, docs.html, dashboard.html
- Animated Agent Swarm: Hero section with 9 agents orbiting Nexus center
- Custom SVG Icons: All emojis replaced with custom SVG icons
- Docs Sidebar: Passive scroll with auto-highlight, vertical list style
- Terminal Demo: Clean design without emojis

#### Core Features

- **Workspace**: `~/neugi/workspace/` - Central hub for all agents
- **Enhanced Skills System**: Multi-format compatible (NEUGI native, OpenClaw, Claude Code, MCP)
- **Skill-to-Agent Mapping**: Auto-map skills to appropriate agents based on capabilities
- **Enhanced Plugin System**: Native Python + MCP plugins, install from GitHub/GitLab URL, Marketplace
- **Real Tool Execution**: Agents now execute real tasks, not just simulate

#### Agent Tool Execution (19 Tools Connected)

- Aurora (Researcher): web_search, web_fetch, neuigi_browser
- Cipher (Coder): code_execute, code_debug, file_read
- Nova (Creator): file_write, llm_think
- Pulse (Analyst): json_parse, csv_analyze, llm_think
- Quark (Strategist): llm_think
- Shield (Security): web_fetch, code_debug, llm_think
- Spark (Social): send_telegram, send_discord, send_email
- Ink (Writer): file_write, llm_think
- Nexus (Manager): file_list, process_list, llm_think

### v15.1 (March 14, 2026) - Professional Release

#### Public Assets & Documentation Hub

- Animated Agent Swarm: Hero section with 9 agents orbiting Nexus center
- Unified Agent Design: Rectangle-based SVG agents matching Chiper style
- Terminal Demo: Interactive wizard flow demonstration
- Complete docs.html: Full documentation with installation, API, security, contact
- Footer: Contact info (<atharia.agi@gmail.com>, [@atharia_agi](https://x.com/atharia_agi)), Coming Soon links
- Responsive Design: Mobile-friendly with glassmorphism effects

#### Infrastructure & Deployment Automation

- **GitHub Actions CI**: Automated test, lint, and build workflows
- **Ruff Linting**: Fixed 116 lint errors across all Python files
- **Requirements.txt**: Added proper dependencies
- **pyproject.toml**: Added project configuration with pytest/mypy/ruff
- **Test Suite**: Comprehensive tests for landing page, config, installers, core files
- **Toast Notifications**: Professional toast instead of alert() popups
- **OS Selection**: Windows/Mac/Linux buttons with copy command (text only, no logos)
- **Vercel Analytics**: Added to index.html, docs.html, dashboard.html

#### Landing Page & Documentation Overview

- **Animated Agent Swarm**: Hero section with 9 agents orbiting Nexus center
- **Custom SVG Icons**: All emojis replaced with custom SVG icons
- **Docs Sidebar**: Passive scroll with auto-highlight, vertical list style
- **Terminal Demo**: Clean design without emojis

#### Workspace & Ecosystem Extensions

- **Workspace**: `~/neugi/workspace/` - Central hub for all agents
- **Enhanced Skills System**:
  - Multi-format compatible: NEUGI native, OpenClaw, Claude Code, MCP
  - 10 built-in skills (GitHub, Weather, Coding, etc.)
  - **Skill-to-Agent Mapping**: Auto-map skills to appropriate agents based on capabilities
- **Enhanced Plugin System**:
  - Native Python + MCP plugins
  - Install from GitHub/GitLab URL
  - Marketplace support

#### Agent Core Capabilities

- **Real Tool Execution**: Agents now execute real tasks, not just simulate
  - Aurora: web_search, web_fetch, neuigi_browser (all web research)
  - Cipher: code_execute, code_debug, file_read (all coding)
  - Nova: file_write, llm_think (create/design)
  - Pulse: json_parse, csv_analyze, llm_think (data analytics)
  - Quark: llm_think (strategy/planning)
  - Shield: web_fetch, code_debug (security scanning)
  - Spark: send_telegram, send_discord, send_email (social)
  - Ink: file_write, llm_think (writing/editing)
  - Nexus: file_list, process_list, llm_think (coordination)

### v15.1 (March 14, 2026) - Swarm Beta Pre-Release

#### Heritage Landing Page Layout

- Animated Agent Swarm: Hero section with 9 agents orbiting Nexus center
- Unified Agent Design: Rectangle-based SVG agents matching Chiper style
- Terminal Demo: Interactive wizard flow demonstration
- Complete docs.html: Full documentation with installation, API, security, contact
- Footer: Contact info (<atharia.agi@gmail.com>, [@atharia_agi](https://x.com/atharia_agi)), Coming Soon links
- Responsive Design: Mobile-friendly with glassmorphism effects

### v15.0 (March 14, 2026)

#### Native Web Browser Agent - NO API KEYS NEEDED

Based on research from openclaw-free-web-search, Firecrawl, and ScrapeGraphAI:

- **Multi-engine Search**: DuckDuckGo, SearXNG, Brave (all FREE!)
- **Content Extraction**: Jina AI Reader + BeautifulSoup fallback
- **Claim Verification**: Cross-validation with confidence scoring
- **No Brave/SerpAPI needed**: Solves OpenClaw's biggest weakness!
- **Model-agnostic**: Works with any LLM

#### NEUGI Wizard v3.0 - All-in-One AI Assistant

- Setup wizard with AI-powered recommendations
- Auto-repair with AI diagnosis
- System diagnostic with AI advice
- Chat with AI about anything
- Single entry point: `python3 neugi_wizard.py`

### v14.1.0 (March 13, 2026)

#### Main Server with Error Recovery

- Auto error detection
- Auto-launch Technician on failure
- Health monitoring dashboard
- Embedded dashboard HTML

### v2.4 (March 13, 2026)

#### Wizard with Telegram Integration

- Auto-start Ollama if not running
- Telegram bot setup during wizard
- Corporate branding: NEUGI

### v1.0 (March 13, 2026)

#### Initial Release

- Smart assistant with fallback models
- Agent system with real LLM integration

---

## Architecture

```text
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
| :--- | :--- |
| `neugi_swarm.py` | Main server with HTTP dashboard, health monitoring, error recovery |
| `neugi_wizard.py` | All-in-one AI wizard: setup + repair + diagnose + chat |
| `neugi_assistant.py` | Smart chat assistant with fallback model support |
| `neugi_telegram.py` | Telegram bot gateway for mobile control |
| `neugi_swarm_browser.py` | Native web browser - FREE search & content extraction |

### Agent System

| File | Purpose |
| :--- | :--- |
| `neugi_swarm_agents.py` | Agent manager with 9 agents |
| `neugi_swarm_memory.py` | SQLite-based memory system |
| `neugi_swarm_tools.py` | Tool system (50+ tools) |
| `neugi_swarm_skills.py` | Custom skills system |

### Infrastructure

| File | Purpose |
| :--- | :--- |
| `neugi_swarm_channels.py` | Multi-channel management |
| `neugi_swarm_context.py` | Context window guide and model recommendations |
| `neugi_swarm_edge.py` | Edge computing support |
| `neugi_swarm_gateway.py` | API gateway |
| `neugi_swarm_setup.py` | Alternative setup wizard (CLI) |
| `neugi_swarm_voice.py` | Voice/TTS interface |
| `ollama_assistant.py` | Ollama-specific assistant |

### Configuration

| File | Purpose |
| :--- | :--- |
| `config_template.py` | Configuration template |
| `VERIFIED_MODELS.py` | List of verified working models |

### Installers

| File | Purpose |
| :--- | :--- |
| `install.sh` | Linux/Mac installer |
| `install.bat` | Windows installer |
| `neugi` | CLI wrapper (Unix) |
| `neugi.bat` | CLI wrapper (Windows) |
| `neugi.service` | Systemd service file |

---

#### Active File Dependencies

### Swarm Core Integration

| File | Purpose | Imported By |
| :--- | :--- | :--- |
| `neugi_swarm.py` | Main server, HTTP dashboard | CLI, install.sh |
| `neugi_wizard.py` | Setup wizard + Telegram setup | CLI, install.sh |
| `neugi_assistant.py` | Chat assistant | neugi_swarm.py |
| `neugi_swarm_agents.py` | Agent manager | neugi_swarm.py |
| `neugi_swarm_tools.py` | Tool system | neugi_swarm.py |
| `neugi_telegram.py` | Telegram bot gateway | neugi_wizard.py |
| `neugi` | CLI wrapper | User |

### Standalone Tools

| File | Purpose | Command |
| :--- | :--- | :--- |
| `neugi_telegram.py` | Telegram bot | `python neugi_telegram.py` |

### Extension Modules

| File | Purpose | Status |
| :--- | :--- | :--- |
| `neugi_swarm_channels.py` | Multi-channel (Discord, WhatsApp) | Not imported |
| `neugi_swarm_voice.py` | TTS/STT voice | Not imported |
| `neugi_swarm_skills.py` | Custom skills | Not imported |
| `neugi_swarm_gateway.py` | Alternative HTTP gateway | Not imported |
| `ollama_assistant.py` | Advanced assistant | Not imported |

### Reference Files (documentation)

| File | Purpose |
| :--- | :--- |
| `neugi_swarm_edge.py` | Model recommendations |
| `neugi_swarm_context.py` | Context window guide |
| `VERIFIED_MODELS.py` | Verified model list |
| `config_template.py` | Config template |

### Deleted Files

| File | Reason |
| :--- | :--- |
| `neugi_swarm_setup.py` | Duplicate of `neugi_wizard.py` |
| `neugi_technician.py` | Retired - functionality consolidated into `neugi_wizard.py` |

### Web Content

| File | Purpose |
| :--- | :--- |
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

## Configuration Settings

### Config Location

```bash
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

#### Environment Variables

| Variable | Default | Description |
| :--- | :--- | :--- |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama API URL |
| `NEUGI_PORT` | `19888` | HTTP server port |
| `NEUGI_DIR` | `~/neugi` | Data directory |

---

## Installation Guide

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

- Dashboard: <http://localhost:19888>
- API: <http://localhost:19888/api/*>

---

## API Reference Guide

### HTTP Endpoints

| Endpoint | Method | Description |
| :--- | :--- | :--- |
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
| :--- | :--- | :--- |
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

## Troubleshooting Guide

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
curl <http://localhost:19888/api/errors>
```

---

## Project Contact

- **Email**: <atharia.agi@gmail.com>
- **Twitter**: [https://x.com/atharia_agi](https://x.com/atharia_agi)
- **GitHub**: [https://github.com/atharia-agi/neugi_swarm](https://github.com/atharia-agi/neugi_swarm)

---

## License Info

MIT License - See LICENSE file for details

---

## Credits & Inspiration

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
*Last updated: March 15, 2026*
