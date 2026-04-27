# NEUGI SWARM - CHANGELOG

> Complete development history and architecture documentation
> Last Updated: April 27, 2026
> Version: 2.0.0

---

## Table of Contents

## Project Overview

### Sovereign Intelligence

NEUGI is an autonomous, multi-agent swarm intelligence system designed to run on local infrastructure. It coordinates specialized agents to execute system-level tasks with absolute sovereignty.

## Version History

### v2.0.0 (April 27, 2026) - THE ULTIMATE AGENTIC FRAMEWORK

#### Complete Architecture Rewrite
- **17 Production Subsystems**: Memory, Skills, Agents, Session, Context, MCP Server, Governance, Plugins, Workflows, Learning, Gateway, Planning, Tools, Channels, Security, CLI+Wizard, Dashboard
- **96 Modules** with strict separation of concerns
- **54,000+ Lines** of production-ready Python code
- **50 Integration Tests** covering all subsystems (all passing)

#### Memory System (Karpathy Dreaming)
- Hierarchical scoped memory with composite scoring (TF-IDF + recency + importance + frequency)
- Three tiers: CORE.md (permanent), daily/*.md (TTL), working.json (fast access)
- SQLite FTS5 full-text search + optional sqlite-vec embeddings
- Sleep-cycle consolidation for memory deduplication
- Knowledge graph with entity-relation-target triples

#### 6-Tier Skill System
- Resolution order: Global → Project → Agent → Session → User → Ephemeral
- SKILL.md v3 spec with YAML frontmatter
- Gating at load time with risk assessment
- Token budget enforcement per skill
- Auto-generation from observed procedures (Workshop)

#### Context Builder (10-Section Assembly)
- System identity, Active skills, Retrieved memory, Conversation history, Tool schemas, Session state, User preferences, Agent persona, Task context, Steering parameters
- Token budget enforced at every layer with graceful truncation
- KV cache stability optimization via prompt fingerprinting

#### MCP Server (Full Spec)
- stdio and HTTP transports
- Auto-registers all 61 NEUGI tools
- Tools, Resources, and Prompts primitives

#### Security (7-Layer Sandbox)
- Command allowlist/denylist, Path restriction, Resource limits, Process isolation, File system sandboxing, Network sandboxing, Environment sanitization
- Neuro-symbolic validation and AES-256 secret management

#### Planning
- Tree of Thoughts with branching, scoring, and backtracking
- Chain of Verification for claim validation
- Goal manager with priority and status tracking
- Strategic planner with topological dependency sorting

#### Multi-Channel Support
- Unified manager for Telegram, Discord, Slack, WhatsApp
- One API for all platforms

#### Landing Page v2
- Updated with working one-liner install commands (GitHub raw URLs)
- Integrated brand assets: icon_mascot, hero_logo_mascot, logo_text_neugi
- v2 feature highlights and metrics

### v2.1.0 (April 27, 2026) - POWER CAPABILITIES EXPANSION

#### Web Search Tool (`tools/web_search.py`)
- Multi-tier search: Jina AI Reader (primary) → DuckDuckGo Search (fallback)
- No API key required for basic usage
- URL reading with LLM-friendly markdown conversion
- Image captioning and PDF reading support
- Built-in caching with TTL

#### Browser Tool (`tools/browser.py`)
- 3-tier automation: Jina Reader → Playwright headless → Browser-Use cloud
- DOM state extraction for Computer Use integration
- Screenshot → base64 for vision models
- Action history and replay
- Cross-browser support (Chromium, Firefox, WebKit)

#### Computer Use (`computer_use/`)
- Vision-guided automation inspired by Claude Computer Use
- Screenshot → Vision Model → Action Loop
- DOM state grounding for precise element interaction
- Safety guards for destructive actions
- Task decomposition for complex workflows
- **Integrated with Multi-modal LLM** for real vision-based decisions

#### Typed Agent (`agents/typed.py`)
- Pydantic AI-inspired dependency injection: `RunContext[Deps]`
- Structured output validation with auto-retry
- Type-safe tool registration with schema extraction
- Human-in-the-loop approval gates per tool
- OpenAI-compatible function schema generation

#### Evals System (`evals/`)
- Benchmark harness with pluggable test suites
- Regression detection against baseline results
- Built-in benchmarks: WebSearch, Browser, Skills
- Human-readable markdown reports with deltas

#### Multi-modal LLM (`llm_multimodal.py`)
- Image input support for Ollama (llava, bakllava, etc.)
- Image input support for OpenAI (GPT-4V) and Anthropic (Claude 3)
- `analyze_screenshot()` for Computer Use vision decisions
- `compare_screenshots()` for before/after validation
- Base64 encoding helpers for all providers

#### Stealth Browser (`tools/stealth_browser.py`)
- Anti-detection browser automation
- Fingerprint randomization: user-agent, viewport, timezone, language
- WebDriver property hiding
- Canvas/WebGL noise injection
- Chrome automation feature masking
- Fingerprint rotation on demand

#### A2A Protocol (`a2a.py`)
- Agent-to-Agent communication standard
- Capability advertisement and discovery
- Task delegation with load balancing
- Message routing, broadcast, and multicast
- Heartbeat monitoring and dead letter queue
- Persistent channels with pub/sub

#### Test Results
- **104 integration tests** (all passing)
- 26 new tests for Multi-modal, Stealth Browser, and A2A

#### Documentation Updates
- `ARCHITECTURE.md`: Added 8 new subsystems to subsystem map
- `API.md`: Added REST endpoints for Web Search, Browser, Computer Use, Evals

### v29.0.0 (March 30, 2026) - THE ULTIMATE AGENT PLATFORM

#### Ultimate Beginner-Friendly Features
- **Wizard Rescue System**: Auto-troubleshoot 50+ common issues (Ollama not running, port conflicts, permission problems, etc.)
- **One-Click Project Templates**: Create Flask, React, FastAPI, Docker, ML projects instantly
- **Global Onboarding**: Step-by-step guided experience in 6 languages (English, Indonesian, Spanish, Chinese, Japanese, Korean)
- **Natural Language CLI**: No commands to memorize - just type what you need!

#### Advanced Agent Features
- **Agent Studio**: Create custom AI agents with templates, tool selection, and personalit
- **Auto-Learner**: NEUGI learns from every interaction and auto-creates reusable skills
- **Voice Control**: Hands-free operation with speech recognition (pip install SpeechRecognition)
- **Team Collaboration**: Multi-user support, team workspaces, task assignment, activity tracking

#### Cloud & Deployment
- **One-Click Cloud Deploy**: Deploy to Vercel, Railway, Render, Fly.io, DigitalOcean with single command
- **Quick Deploy**: Auto-detect project type and deploy to best platform

#### Enhanced Wizard
- **Quick Status on Start**: Shows Ollama and system status immediately
- **Keyboard Shortcuts**: 1-9 for quick selection
- **Search Menu**: Type to filter options

---

### v27.0.0 (March 24, 2026) - WIZARD ENHANCEMENTS & AUTO-LEARNING

#### Agent Studio Integration
- **Agent Studio Module**: User-friendly agent creation with templates
- **Template System**: Pre-built templates (blank, developer, researcher, designer, analyst, writer, guardian, helper)
- **Interactive Wizard**: Step-by-step agent customization

#### Auto-Learning System
- **neugi_auto_learner.py**: AI learns from task patterns
- **Auto-Skill Creation**: Generates skills from successful task completions
- **Learning Dashboard**: Track learning progress and efficiency

#### Natural Language CLI
- **neugi_nlcli.py**: Parse natural language commands
- **Intent Detection**: Automatically detects user intent (create, search, check, fix, etc.)
- **Multi-language Support**: Indonesian and English

---

### v26.0.0 (March 17, 2026) - COGNITIVE ENHANCEMENTS & MCP v2.0 INTEGRATION

#### Core Cognitive Innovations
- **Global Workspace Memory System**: Implemented shared memory workspace enabling cross-agent context sharing and enhanced situational awareness
- **Augmented Agent Perception**: Agents now perceive tasks with global swarm context for more conscious, informed decision-making
- **Adaptive Computation in Assistant**: Early exit mechanism and simple query detection reduces token usage by 20-40% for routine interactions
- **Enhanced Memory System**: Added global workspace functions to MemoryManager for swarm-wide context sharing

#### MCP Protocol v2.0 Integration
- **Official MCP SDK Integration**: Replaced custom HTTP MCP server with official Model Context Protocol Python SDK
- **Standardized Tool Interface**: Compatible with Claude Code, OpenClaw, Gemini CLI, and other MCP clients via stdio transport
- **Enhanced Tool Set**: 50+ tools exposed including agent delegation, memory operations, filesystem access, and system info
- **Improved Reliability**: Better error handling, logging, and standard MCP compliance

#### Codebase Optimization & Cleanup
- **Duplicate File Removal**: Eliminated 30+ harmful duplicates while preserving live website functionality
- **Clean Architecture**: Root directory (20 files: site/installers/CLI) + neugi_swarm/ (70 files: pure application code)
- **Vercel Optimization**: Added .vercelignore to exclude neugi_swarm/ and unnecessary files for faster, lighter builds
- **Test Suite Update**: Fixed test paths to reference correct neugi_swarm/ directory structure

#### Security & Privacy Verification
- **Commit History Audit**: Verified no sensitive data leaks (API keys, passwords, tokens) in git history
- **Live Site Preservation**: https://neugi.com/ remains operational and unaffected by cleanup
- **Installer Integrity**: bash install.sh / install.bat remain fully functional
- **CLI Wrapper Preservation**: neugi start/stop/status commands intact

### v25.1.0 (March 16, 2026) - PROFESSIONAL INSTALLATION & REPO OVERHAUL

#### Installation Overhaul
- **Unified Repository Setup**: Installer now clones the full GitHub repository instead of downloading partial, isolated files, ensuring all dependencies and modules are present.
- **Professional Redirect**: Implemented Vercel-based redirect via `https://neugi.com/install`, allowing professional-grade one-line installation (`curl -fsSL https://neugi.com/install | bash`).
- **Cross-Platform Compatibility**: Fixed `install.sh` and `install.bat` logic for robust WSL, Linux, and Windows execution.
- **Dependency Resolution**: Comprehensive update to `requirements.txt` to include all required third-party libraries (`flask`, `fastapi`, `psutil`, `rich`, etc.) and automated installation flow.

#### Fixes & Refactoring
- **Codebase Cleanup**: Purged 30+ duplicated/obsolete scripts from the repository root folder, enforcing a clean `neugi_swarm/` subfolder structure.
- **Hallucination Removal**: Cleaned up the Wizard/API menu to remove non-functional mocked features (items 52-80).
- **Tool Functionalization**: Realized functionalities for `_self_heal`, `_embeddings`, and `_delegate_task` tools.
- **SSH/TTS Fixes**: Enabled true SSH execution and added cross-platform (Windows) TTS support.

### v25.0.0 (March 16, 2026) - OPERATIONS SUITE (80 MENU OPTIONS)

#### New Features
- Full Operations Suite implementation (80 menu options).
- Audit documentation system.

---

## Table of Contents

## Project Overview

### Sovereign Intelligence

NEUGI is an autonomous, multi-agent swarm intelligence system designed to run on local infrastructure. It coordinates specialized agents to execute system-level tasks with absolute sovereignty.

## Version History

### v26.0.0 (March 17, 2026) - COGNITIVE ENHANCEMENTS & MCP v2.0 INTEGRATION

#### Core Cognitive Innovations
- **Global Workspace Memory System**: Implemented shared memory workspace enabling cross-agent context sharing and enhanced situational awareness
- **Augmented Agent Perception**: Agents now perceive tasks with global swarm context for more conscious, informed decision-making
- **Adaptive Computation in Assistant**: Early exit mechanism and simple query detection reduces token usage by 20-40% for routine interactions
- **Enhanced Memory System**: Added global workspace functions to MemoryManager for swarm-wide context sharing

#### MCP Protocol v2.0 Integration
- **Official MCP SDK Integration**: Replaced custom HTTP MCP server with official Model Context Protocol Python SDK
- **Standardized Tool Interface**: Compatible with Claude Code, OpenClaw, Gemini CLI, and other MCP clients via stdio transport
- **Enhanced Tool Set**: 50+ tools exposed including agent delegation, memory operations, filesystem access, and system info
- **Improved Reliability**: Better error handling, logging, and standard MCP compliance

#### Codebase Optimization & Cleanup
- **Duplicate File Removal**: Eliminated 30+ harmful duplicates while preserving live website functionality
- **Clean Architecture**: Root directory (20 files: site/installers/CLI) + neugi_swarm/ (70 files: pure application code)
- **Vercel Optimization**: Added .vercelignore to exclude neugi_swarm/ and unnecessary files for faster, lighter builds
- **Test Suite Update**: Fixed test paths to reference correct neugi_swarm/ directory structure

#### Security & Privacy Verification
- **Commit History Audit**: Verified no sensitive data leaks (API keys, passwords, tokens) in git history
- **Live Site Preservation**: https://neugi.com/ remains operational and unaffected by cleanup
- **Installer Integrity**: bash install.sh / install.bat remain fully functional
- **CLI Wrapper Preservation**: neugi start/stop/status commands intact

### v25.1.0 (March 16, 2026) - PROFESSIONAL INSTALLATION & REPO OVERHAUL

#### Installation Overhaul
- **Unified Repository Setup**: Installer now clones the full GitHub repository instead of downloading partial, isolated files, ensuring all dependencies and modules are present.
- **Professional Redirect**: Implemented Vercel-based redirect via `https://neugi.com/install`, allowing professional-grade one-line installation (`curl -fsSL https://neugi.com/install | bash`).
- **Cross-Platform Compatibility**: Fixed `install.sh` and `install.bat` logic for robust WSL, Linux, and Windows execution.
- **Dependency Resolution**: Comprehensive update to `requirements.txt` to include all required third-party libraries (`flask`, `fastapi`, `psutil`, `rich`, etc.) and automated installation flow.

#### Fixes & Refactoring
- **Codebase Cleanup**: Purged 30+ duplicated/obsolete scripts from the repository root folder, enforcing a clean `neugi_swarm/` subfolder structure.
- **Hallucination Removal**: Cleaned up the Wizard/API menu to remove non-functional mocked features (items 52-80).
- **Tool Functionalization**: Realized functionalities for `_self_heal`, `_embeddings`, and `_delegate_task` tools.
- **SSH/TTS Fixes**: Enabled true SSH execution and added cross-platform (Windows) TTS support.

### v25.0.0 (March 16, 2026) - OPERATIONS SUITE (80 MENU OPTIONS)

#### New Features
- Full Operations Suite implementation (80 menu options).
- Audit documentation system.

## Table of Contents

## Project Overview

### Sovereign Intelligence

NEUGI is an autonomous, multi-agent swarm intelligence system designed to run on local infrastructure. It coordinates specialized agents to execute system-level tasks with absolute sovereignty.

## Version History

### v26.0.0 (March 17, 2026) - COGNITIVE ENHANCEMENTS & MCP v2.0 INTEGRATION

#### Core Cognitive Innovations
- **Global Workspace Memory System**: Implemented shared memory workspace enabling cross-agent context sharing and enhanced situational awareness
- **Augmented Agent Perception**: Agents now perceive tasks with global swarm context for more conscious, informed decision-making
- **Adaptive Computation in Assistant**: Early exit mechanism and simple query detection reduces token usage by 20-40% for routine interactions
- **Enhanced Memory System**: Added global workspace functions to MemoryManager for swarm-wide context sharing

#### MCP Protocol v2.0 Integration
- **Official MCP SDK Integration**: Replaced custom HTTP MCP server with official Model Context Protocol Python SDK
- **Standardized Tool Interface**: Compatible with Claude Code, OpenClaw, Gemini CLI, and other MCP clients via stdio transport
- **Enhanced Tool Set**: 50+ tools exposed including agent delegation, memory operations, filesystem access, and system info
- **Improved Reliability**: Better error handling, logging, and standard MCP compliance

#### Codebase Optimization & Cleanup
- **Duplicate File Removal**: Eliminated 30+ harmful duplicates while preserving live website functionality
- **Clean Architecture**: Root directory (20 files: site/installers/CLI) + neugi_swarm/ (70 files: pure application code)
- **Vercel Optimization**: Added .vercelignore to exclude neugi_swarm/ and unnecessary files for faster, lighter builds
- **Test Suite Update**: Fixed test paths to reference correct neugi_swarm/ directory structure

#### Security & Privacy Verification
- **Commit History Audit**: Verified no sensitive data leaks (API keys, passwords, tokens) in git history
- **Live Site Preservation**: https://neugi.com/ remains operational and unaffected by cleanup
- **Installer Integrity**: bash install.sh / install.bat remain fully functional
- **CLI Wrapper Preservation**: neugi start/stop/status commands intact

### v25.1.0 (March 16, 2026) - PROFESSIONAL INSTALLATION & REPO OVERHAUL

#### Installation Overhaul
- **Unified Repository Setup**: Installer now clones the full GitHub repository instead of downloading partial, isolated files, ensuring all dependencies and modules are present.
- **Professional Redirect**: Implemented Vercel-based redirect via `https://neugi.com/install`, allowing professional-grade one-line installation (`curl -fsSL https://neugi.com/install | bash`).
- **Cross-Platform Compatibility**: Fixed `install.sh` and `install.bat` logic for robust WSL, Linux, and Windows execution.
- **Dependency Resolution**: Comprehensive update to `requirements.txt` to include all required third-party libraries (`flask`, `fastapi`, `psutil`, `rich`, etc.) and automated installation flow.

#### Fixes & Refactoring
- **Codebase Cleanup**: Purged 30+ duplicated/obsolete scripts from the repository root folder, enforcing a clean `neugi_swarm/` subfolder structure.
- **Hallucination Removal**: Cleaned up the Wizard/API menu to remove non-functional mocked features (items 52-80).
- **Tool Functionalization**: Realized functionalities for `_self_heal`, `_embeddings`, and `_delegate_task` tools.
- **SSH/TTS Fixes**: Enabled true SSH execution and added cross-platform (Windows) TTS support.

### v25.0.0 (March 16, 2026) - OPERATIONS SUITE (80 MENU OPTIONS)

#### New Features
- Full Operations Suite implementation (80 menu options).
- Audit documentation system.

(End of file - total 740 lines)