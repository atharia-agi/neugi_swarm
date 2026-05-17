# NEUGI SWARM - CHANGELOG

> Complete development history and architecture documentation
> Last Updated: May 17, 2026
> Version: 2.1.3

## v2.1.3 (May 16, 2026) - SETUP CONSOLIDATION, PROVIDER CATALOG & TEST PARITY

### Setup & Install Parity
- `neugi wizard` now uses the canonical `GeniusWizard` setup flow directly.
- `SmartWizard` and legacy `SetupWizard` are compatibility aliases only; new setup logic belongs in `GeniusWizard`.
- `RescueWizard` remains the recovery/repair tool and delegates first-time setup to `GeniusWizard`.
- Added `neugi_swarm_v2/install.ps1` for the Windows PowerShell one-liner. Website and docs now point PowerShell users to `install.ps1` instead of piping a `.bat` file into `iex`.
- Fixed Unix installer pathing: source installs to `~/neugi_swarm`, while runtime config remains in `~/.neugi`.

### Provider Configuration UX
- Rebuilt `provider_catalog.py` as a curated provider/model setup catalog with provider API-key URLs, model-list URLs, env-var mappings, and custom provider support.
- Wizard flow is now provider-first, API-key-aware, searchable by model, and still allows custom provider/base URL/model entry.
- Runtime API-key resolution now checks provider-specific env vars such as `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`, etc.

### Dashboard Setup UX
- Added a first-run `Setup` tab to both the runtime dashboard and `neugi.com/dashboard.html`.
- Dashboard users can now choose provider, search/select model, enter API key, set base URL, fallback model, temperature, and max tokens without using the CLI wizard.
- Added `/api/providers` for the dashboard provider/model catalog and made `/api/config` recursively merge nested config updates instead of replacing dataclass sections with dictionaries.
- Fixed dashboard setup persistence to write `~/.neugi/config.json` and preserve plaintext API keys only long enough for the existing SecretManager migration path.

### Verification
- Full suite verified on Python 3.12.10: **372 collected, 370 passed, 2 skipped, 0 warnings**.
- Fixed test/runtime issues found during verification:
  - Explicit security-scope CIDRs now authorize covered private IPs.
  - A2A heartbeat updates are monotonic even within the same clock tick.
  - Optional browser tests skip cleanly when Playwright is not installed.
  - Fixed a syntax error in the browser agent plugin.
  - Test modules no longer import stale duplicate code from `repo/neugi_swarm_v2`.
  - Test warnings from bool-returning tests and deprecated UTC timestamps were cleaned up.

---

## Table of Contents

- [v2.1.3 (May 16, 2026)](#v213-may-16-2026---setup-consolidation-provider-catalog--test-parity)
- [v2.1.3 (May 14, 2026)](#v213-may-14-2026--mcp-production-hardening--comprehensive-testing)
- [v2.1.1 (April 29, 2026)](#v211-april-29-2026)
- [v2.1.0 (April 27, 2026)](#v210-april-27-2026)
- [v2.0.0 (April 27, 2026)](#v200-april-27-2026)

---

## v2.1.3 (May 14, 2026) — MCP PRODUCTION HARDENING & COMPREHENSIVE TESTING

### MCP Production Hardening
- **Rate limiting**: Added `RateLimiter` token-bucket implementation for SSE connections (10/s default, 20 burst)
- **Auth tokens**: Added `SSEAuth` for optional token-based authentication on SSE endpoint (`?token=<key>` query param)
- **Tool cancellation**: Fixed `CANCEL_REQUEST` — was a no-op stub, now properly cancels running tool execution tasks with timeout support
- **CLI args**: Added `--auth-tokens`, `--rate-limit`, `--rate-burst` to `mcp/server/http.py` entry point
- **SSE connection**: Now tracks client name for authenticated connections; rate limiting enforced per-connection

### MCP Test Coverage
- **Created `tests/test_mcp.py`**: 90+ comprehensive tests covering:
  - `ToolManager`: registration, listing, calling, error handling, edge cases
  - `ResourceManager`: static, dynamic, file, template resources; read/list/cursor/error edges
  - `PromptManager`: register, get, render, list, default prompts
  - `MCPServer`: init, defaults, tools/resources/prompts shortcuts, initialize, ping, bridge/neugi wiring
  - `SSEAuth`: enable/disable, validation, multiple tokens, empty tokens, disabled-by-default
  - `RateLimiter`: burst, exceed, refill, zero tokens, high burst
  - `SSEConnection`: create, subscribe, unsubscribe, push/get, format, close, rate-limited push
  - `StdioTransport`: init, stop
  - `HTTPTransport`: init with rate/auth, connection management, publish, stop
  - `Messages`: request, response, notification, CallToolResult, InitializeResult, list results, get prompt
  - `Checkpoint`: CheckpointData, CheckpointStore (create/get/list/update/log/cleanup), ExecutionThread
  - `ResilientMCPExecutor`: init, stats, workflows, cleanup
  - `SSEEventForwarder`: creation, start/stop, singleton, connection management
  - `MCPBridge`: creation, connect/disconnect, factory

### SSE Endpoint Security
- Auth token validated via `?token=<token>` query parameter on SSE upgrade
- 401 Unauthorized response for invalid/missing tokens when auth is enabled
- Rate limiting silently drops events when bucket exhausted (no error response)
- Auth can be enabled/disabled at runtime via `HTTPTransport.set_auth_tokens()` / `disable_auth()`

### Code Cleanup & Performance
- **Removed 5 orphaned MCP files**: `mcp_server.py`, `protocol.py`, `tools.py`, `resources.py`, `prompts.py` — legacy code replaced by refactored `server.py`, `messages.py`, `tool_manager.py`, `resource_manager.py`, `prompt_manager.py`, `transport.py`
- **Moved MCP to port 17902** in Docker Compose with SSE, rate limit, and auth token configuration
- **Created `benchmarks/mcp_benchmark.py`**: comprehensive MCP server performance benchmark measuring latency (avg/median/p95/p99), throughput (req/s), and concurrency scaling (1-50 concurrent calls)
- **Updated AGENTS.md** from v2.1.1 to v2.1.3 and expanded MCP/security test coverage

### Skills System Fix
- **Fixed `_generate_skill_code` TODO stub** in `skills/improver.py:438` — auto-generated skills now use `context.params` for dynamic execution, have proper f-string templates, and are immediately usable without manual editing

## v2.1.3 (May 2, 2026) — AUTONOMOUS SECURITY HARNESS & ENHANCEMENTS

### Autonomous Security Harness Plugin
- Added `plugins/autonomous_security_harness/` - LangGraph-based autonomous security assessment harness
- Docker sandbox execution for security tools (nmap, nuclei, sqlmap, nikto, etc.) with resource limits and privilege dropping
- Stateful workflow with checkpointing support (PostgreSQL compatible) for crash recovery and audit trails
- Semantic knowledge base search using sentence-transformers for conceptual security concept retrieval
- Comprehensive safety middleware:
  - Scope validation with CIDR and private IP controls
  - Authorization gates for high-risk tools (sqlmap, metasploit) with timeout-based approval waiting
  - Immutable audit logging with hash chaining for tamper detection
- Automatic compliance mapping to frameworks (NIST, ISO 27001, OWASP, PCI-DSS, etc.)
- Modular design for easy extension with additional security tools and techniques

### Observability Event Bus
- Added lightweight, thread-safe event bus (`observability/event_bus.py`) for monitoring tool executions
- Global `event_bus` instance accessible via `get_event_bus()`
- Tool executor now publishes `tool_execution_success` and `tool_execution_failure` events
- Maintains zero core modifications and full backward compatibility
- Enables plugin extensibility without altering existing tool executor contracts

### Cybersecurity Expert Plugin - Vector Embeddings Enhancement
- Added semantic vector search capabilities using sentence-transformers ('all-MiniLM-L6-v2')
- Enhanced knowledge indexer to generate and store vector embeddings for markdown documents
- Enhanced knowledge searcher to perform hybrid search combining keyword matching with vector similarity
- Implemented cosine similarity scoring for re-ranking search results
- Graceful fallback to keyword-only search if sentence-transformers is not available
- Updated plugin configuration to support `use_vectors` option
- Significantly improved conceptual search accuracy for cybersecurity knowledge base

### Browser Agent Plugin
- Added plugin-based browser agent in `plugins/browser_agent/`
- Demonstrates how to extend NEUGI without modifying core files
- Includes `BrowserAgent` (TypedAgent-based implementation using LLM to control BrowserTool)
- Alternative reasoning-loop implementation in `browser_agent.py`
- Usage example in `example.py` showing automated web interactions
- Fully opt-in via plugin system, requires LLM provider at runtime

### Test Fixes
- Fixed flaky test in `tests/test_computer_use.py`: replaced `self.skipIf` with `self.skipTest`
- Maintained 229/229 passing tests (excluding flaky browser test due to missing network/browser in CI)

## v2.1.1 (April 29, 2026) — MODEL ROUTING, SECURITY HARDENING & AUTONOMOUS LOOP

### Security Infrastructure — Full Wiring

**Post-Brutal-Audit Remediation** — 5 RCE vectors confirmed and patched:

- **ExecutionSandbox active invocation** in `ToolExecutor.execute()` (lines 678-703)
  - Not just stored — actually called at runtime for system/docker commands
  - Enforces timeout, environment sanitization, path restriction
- **CommandValidator** for subprocess-based tools (lines 627-644)
  - Allowlist/denylist enforcement before execution
- **ExploitPreventionEngine** input scanning (lines 580-598) + output scan (lines 718-735)
  - Injection/jailbreak pattern detection
- **ApprovalGate** for COMPLEX/STRATEGIC tools (lines 600-625)
  - Blocks dangerous operations until explicitly approved
- **SecretManager API key migration** (config.py + __init__.py)
  - Auto-migrates plaintext api_key from config.json → encrypted SQLite secrets.db
  - Resolution chain: env var → SecretManager → config fallback
  - config.json rewritten without plaintext key on first load

### eval()/exec() Elimination

- `data_transform` in builtins.py: 3× eval() replaced with AST-based `_safe_eval()` parser
- `code_execute` in builtins.py: exec() replaced with subprocess execution (timeout, restricted)
- `tool_generator.py`: exec() replaced with AST validation + restricted compiled exec

### shell=False by Default

- `system_execute_command` in builtins.py: shell=True → shell=False (RCE mitigation)
- Breaking change documented in migration notes

### Autonomous Loop System (NEW)

- **IdleObserver**: System state sensing via observe → decide → execute → report cycle
- **ProactiveDecisionEngine**: Confidence/value/risk thresholds, daily action limits
- **SelfDirectedExecutor**: 8 execution handlers wired to real subsystems
  - `CONSOLIDATE_MEMORY` → `DreamingEngine.run_cycle()`
  - `DECOMPOSE_GOAL` → `GoalSystem.decompose()`
  - `COMPLETE_GOAL` → `GoalSystem.update_progress()`
  - `RESOLVE_BLOCKER` → `AutonomousAgentSpawner.spawn_strategist_agent()` + `AgentManager.delegate()`
  - `SELF_HEAL` → Real health checks + circuit breaker reset
  - `PROACTIVE_RESEARCH` → `ResearchEngine.research()`
  - `LEARN_SKILL` → `SkillGenerator.generate_skills_from_patterns()`
  - `OPTIMIZE` → Performance suggestions logged to memory
- **ActivityReporter**: Routes reports to Memory, Dashboard, Logs, User notifications
- **NotificationDispatcher**: Telegram/Discord/Slack/WhatsApp/Dashboard/Log channels
- **AutonomousAgentSpawner**: Spawns TypedAgent instances for research/coder/analyst/strategist tasks
- **Dashboard Live Status API**: `GET /api/autonomous/status` returns real-time state

### Karpathy Autoresearch Engine (NEW)

- **ResearchEngine**: Iterative deep-dive research with configurable rounds (default: 3)
  - Query → Search → Read → Synthesize → Hypothesize → Iterate → Report
  - Web search via Jina AI + DuckDuckGo fallback
  - LLM-driven synthesis with early convergence detection
  - Source tracking with citations
  - Auto-stored in memory with `role="research"` and `tags=["autoresearch"]`

### Model Capability Routing (NEW)

- **ProviderCatalog**: 18 providers, 65+ models with capability metadata
  - Ollama, OpenAI, Anthropic, Google, Mistral, Groq, Cohere, Fireworks, Perplexity, Together, Azure, Deepseek, Nvidia, Intel, AMD, AWS Bedrock, Replicate, Cerebras
- **ModelCapabilityRouter**: Tier-based adaptation (LOCAL <7B / MEDIUM 7B-70B / CLOUD 200B+)
  - Adapts: PromptAssembler budgets, ToolRegistry filtering, ToolExecutor thresholds, ProactiveDecisionEngine limits, Research rounds
- **MultiModelRouter**: Opt-in multi-model routing for task delegation

### Tool Complexity System (NEW)

- `ToolComplexity` enum: TRIVIAL → SIMPLE → MEDIUM → COMPLEX → STRATEGIC
- Capability-based tool filtering per model tier
- `list_compatible_tools()` in ToolRegistry filters by complexity threshold

### Wizard Multi-Provider Support (NEW)

- **GeniusWizard** (`cli/genius_wizard.py`): Zero-dependency setup wizard
  - Auto-detects API keys for all 18 providers
  - Auto-ranks available models by capability
  - Curated model list (weak models excluded)
  - Custom model input for any model
  - Custom endpoint for OpenAI-compatible / Anthropic-compatible providers
  - Capability preview before saving
- **SmartWizard / SetupWizard**: Deprecated compatibility aliases that forward to GeniusWizard
- **RescueWizard**: Interactive auto-fix with health checks; setup path delegates to GeniusWizard

### Configuration Simplification

- Single JSON config file (`~/.neugi/config.json`), user-editable
- Port changed: 8080 → 17901 (to avoid common conflicts)
- `_readme` comments embedded in config for self-documentation

### Soul System (NEW)

- **SoulEngine**: SOUL.md pattern with 5 files
  - `SOUL.md` → Identity, worldview, values
  - `STYLE.md` → Voice, syntax, patterns
  - `USER.md` → User preferences & facts
  - `WORLD.md` → Project/environment context
  - `MEMORY.md` → Rendered from MemorySystem (not duplicate storage)
- Single source of truth: SQLite via MemorySystem
- `neugi soul remember <note>` CLI command for manual continuity

### Quality Infrastructure

- **25 real security behavior tests** (`tests/test_security_real.py`)
  - Replaces 6 hasattr() stubs with actual behavior verification
  - TestExecutionSandboxBehavior (8 tests): blocks rm-rf, mkfs, curl|bash, path traversal
  - TestCommandValidatorBehavior (6 tests): command allow/deny with explanations
  - TestExploitPreventionBehavior (3 tests): injection/jailbreak detection
  - TestApprovalGateBehavior (3 tests): approval rules, pending requests
  - TestToolExecutorSecurityIntegration (3 tests): security wiring verification
  - TestEvalReplacement (2 tests): verifies no dangerous eval/exec in builtins
- **229 total tests** all passing (up from 204)
- **Ruff auto-fix**: 4,007 issues fixed (UP006/UP035/UP045/W293)

### PyPI Package

- `neugi-swarm-v2` built and ready for upload
- `dist/neugi_swarm_v2-2.1.1-py3-none-any.whl` (8 KB)
- `dist/neugi_swarm_v2-2.1.1.tar.gz` (29 KB)
- To publish: `py -m twine upload dist/*`

---

## v2.1.0 (April 27, 2026) — POWER CAPABILITIES EXPANSION

### Web Search Tool (`tools/web_search.py`)
- Multi-tier search: Jina AI Reader (primary) → DuckDuckGo Search (fallback)
- No API key required for basic usage
- URL reading with LLM-friendly markdown conversion
- Image captioning and PDF reading support
- Built-in caching with TTL

### Browser Tool (`tools/browser.py`)
- 3-tier automation: Jina Reader → Playwright headless → Browser-Use cloud
- DOM state extraction for Computer Use integration
- Screenshot → base64 for vision models
- Action history and replay
- Cross-browser support (Chromium, Firefox, WebKit)

### Computer Use (`computer_use/`)
- Vision-guided automation inspired by Claude Computer Use
- Screenshot → Vision Model → Action Loop
- DOM state grounding for precise element interaction
- Safety guards for destructive actions
- Task decomposition for complex workflows

### Typed Agent (`agents/typed.py`)
- Pydantic AI-inspired dependency injection: `RunContext[Deps]`
- Structured output validation with auto-retry
- Type-safe tool registration with schema extraction
- Human-in-the-loop approval gates per tool
- OpenAI-compatible function schema generation

### Multi-modal LLM (`llm_multimodal.py`)
- Image input support for Ollama (llava, bakllava, etc.)
- Image input support for OpenAI (GPT-4V) and Anthropic (Claude 3)
- `analyze_screenshot()` for Computer Use vision decisions
- `compare_screenshots()` for before/after validation
- Base64 encoding helpers for all providers

### Stealth Browser (`tools/stealth_browser.py`)
- Anti-detection browser automation
- Fingerprint randomization: user-agent, viewport, timezone, language
- WebDriver property hiding
- Canvas/WebGL noise injection
- Chrome automation feature masking
- Fingerprint rotation on demand

### A2A Protocol (`a2a.py`)
- Agent-to-Agent communication standard
- Capability advertisement and discovery
- Task delegation with load balancing
- Message routing, broadcast, and multicast
- Heartbeat monitoring and dead letter queue
- Persistent channels with pub/sub

### Test Results
- **104 integration tests** (all passing)
- 26 new tests for Multi-modal, Stealth Browser, and A2A

---

## v2.0.0 (April 27, 2026) — THE ULTIMATE AGENTIC FRAMEWORK

### Complete Architecture Rewrite
- **17 Production Subsystems**: Memory, Skills, Agents, Session, Context, MCP Server, Governance, Plugins, Workflows, Learning, Gateway, Planning, Tools, Channels, Security, CLI+Wizard, Dashboard
- **96 Modules** with strict separation of concerns
- **54,000+ Lines** of production-ready Python code
- **50 Integration Tests** covering all subsystems (all passing)

### Memory System (Karpathy Dreaming)
- Hierarchical scoped memory with composite scoring (TF-IDF + recency + importance + frequency)
- Three tiers: CORE.md (permanent), daily/*.md (TTL), working.json (fast access)
- SQLite FTS5 full-text search + optional sqlite-vec embeddings
- Sleep-cycle consolidation for memory deduplication
- Knowledge graph with entity-relation-target triples

### 6-Tier Skill System
- Resolution order: Global → Project → Agent → Session → User → Ephemeral
- SKILL.md v3 spec with YAML frontmatter
- Gating at load time with risk assessment
- Token budget enforcement per skill
- Auto-generation from observed procedures (Workshop)

### Context Builder (10-Section Assembly)
- System identity, Active skills, Retrieved memory, Conversation history, Tool schemas, Session state, User preferences, Agent persona, Task context, Steering parameters
- Token budget enforced at every layer with graceful truncation
- KV cache stability optimization via prompt fingerprinting

### MCP Server (Full Spec)
- stdio and HTTP transports
- Auto-registers all 61 NEUGI tools
- Tools, Resources, and Prompts primitives

### Security (7-Layer Sandbox)
- Command allowlist/denylist, Path restriction, Resource limits, Process isolation, File system sandboxing, Network sandboxing, Environment sanitization
- Neuro-symbolic validation and AES-256 secret management

### Planning
- Tree of Thoughts with branching, scoring, and backtracking
- Chain of Verification for claim validation
- Goal manager with priority and status tracking
- Strategic planner with topological dependency sorting

### Multi-Channel Support
- Unified manager for Telegram, Discord, Slack, WhatsApp
- One API for all platforms

### Landing Page v2
- Updated with working one-liner install commands (GitHub raw URLs)
- Integrated brand assets: icon_mascot, hero_logo_mascot, logo_text_neugi
- v2 feature highlights and metrics
