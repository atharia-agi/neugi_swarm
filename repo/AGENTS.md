# AGENTS.md — NEUGI Swarm v2.1.3

> Agent-facing context for AI coding assistants. Human contributors: see README.md.

---

## Project Identity

**NEUGI Swarm v2** is a production-grade autonomous multi-agent framework.
- **Language:** Python 3.10+
- **Architecture:** 29 subsystems, 117+ modules, ~64K LOC
- **Test count:** 326 tests (204 original + 122 MCP), all must pass
- **Version:** 2.1.3

This is NOT a chatbot wrapper. It is **sovereign autonomous infrastructure**:
- **Autonomous Loop** — pro-active behavior during idle periods (observe → decide → execute → report)
- Karpathy-style dreaming memory consolidation
- CrewAI hierarchical role-based agents
- LangGraph checkpointing & durable execution
- MCP server (stdio + HTTP transports)
- 61 built-in tools with composition engine

---

## Repository Layout

```
repo/
├── neugi_swarm_v2/           # Main Python package
│   ├── __init__.py           # NeugiSwarmV2 unified entry point
│   ├── assistant.py          # NeugiAssistantV2.chat() — primary user API
│   ├── llm_provider.py       # Ollama, OpenAI-compatible, Anthropic providers
│   ├── llm_multimodal.py     # Vision + image handling
│   ├── model_registry.py     # Dynamic capability detection
│   ├── response_format.py    # StructuredResponse with metadata
│   ├── config.py             # NeugiConfig dataclass + loader
│   ├── a2a.py                # Agent-to-agent protocol
│   │
│   ├── memory/               # 3-tier memory (core/daily/working)
│   │   ├── memory_core.py    # MemorySystem — SQLite FTS5 + optional vectors
│   │   ├── dreaming.py       # Sleep-cycle consolidation
│   │   ├── scopes.py         # Hierarchical scope paths
│   │   ├── scoring.py        # Composite recall scoring
│   │   └── embeddings.py     # sentence-transformers / Ollama fallback
│   │
│   ├── skills/               # 6-tier skill system
│   │   ├── skill_contract.py # SkillTier, SkillContract
│   │   ├── skill_loader.py   # YAML frontmatter parsing
│   │   ├── skill_manager.py  # Token budget + loading
│   │   ├── skill_matcher.py  # NL trigger matching
│   │   └── skill_prompt.py   # PromptAssembler integration
│   │
│   ├── session/              # Session lifecycle + compaction
│   │   ├── session_manager.py
│   │   ├── compaction.py     # Context window compaction
│   │   ├── steering.py       # Real-time steering
│   │   └── transcript.py
│   │
│   ├── context/              # Prompt assembly & token budgets
│   │   ├── prompt_assembler.py   # 10-section system prompt builder
│   │   ├── soul_engine.py        # SOUL.md identity/personality (NEW)
│   │   ├── token_budget.py
│   │   ├── cache_stability.py
│   │   └── context_injector.py
│   │
│   ├── agents/               # Agent orchestration
│   │   ├── agent.py          # Base Agent class
│   │   ├── typed.py          # TypedAgent (LLM-wired)
│   │   └── agent_manager.py  # Lifecycle + message bus
│   │
│   ├── tools/                # 61 tools + composition engine
│   │   ├── builtins.py       # 50+ built-in tools
│   │   ├── web_search.py     # Jina AI / DuckDuckGo
│   │   ├── browser.py        # Playwright DOM automation
│   │   ├── stealth_browser.py
│   │   ├── tool_registry.py
│   │   ├── tool_composer.py
│   │   ├── tool_executor.py  # Retry, cache, circuit breaker
│   │   └── tool_generator.py
│   │
│   ├── computer_use/         # GUI automation (VNC/SSH)
│   ├── channels/             # Telegram, Discord, Slack, WhatsApp
│   ├── dashboard/            # WebSocket + HTTP dashboard
│   ├── evals/                # Benchmark harness
│   ├── gateway/              # Device gateway + cron scheduler
│   ├── governance/           # Budget, approval, audit
│   ├── learning/             # Pattern tracking + skill generation
│   ├── mcp/                  # Model Context Protocol server
│   ├── planning/             # Tree of Thoughts, CoV, goals
│   ├── plugins/              # Plugin SDK + loader
│   ├── security/             # Sandbox, exploit prevention
│   ├── workflows/            # LangGraph-style state graphs
│   │
│   ├── autonomous/           # Pro-active autonomous behavior (NEW)
│   │   ├── loop_engine.py    # AutonomousLoop — main idle loop
│   │   ├── observer.py       # IdleObserver — system state sensing
│   │   ├── decision.py       # ProactiveDecisionEngine — action selection
│   │   ├── executor.py       # SelfDirectedExecutor — action execution
│   │   └── reporter.py       # ActivityReporter — activity logging
│   │
│   └── cli/                  # Command-line interface
│       ├── cli.py            # Main CLI (rich-based)
│       ├── interactive.py    # Interactive chat REPL
│       ├── genius_wizard.py  # Zero-dependency setup wizard
│       ├── smart_wizard.py   # AI-level setup wizard
│       ├── rescue_wizard.py  # Auto-fix rescue mode
│       └── wizard.py         # Original wizard (deprecated)
│
├── tests/                    # 165 tests across all subsystems
├── assets/                   # Brand images, favicon, hero video
├── index.html                # Landing page
├── docs.html                 # Documentation site
├── dashboard.html            # Dashboard UI
├── CHANGELOG.md
└── README.md
```

---

## Key Entry Points

### Running Tests
```bash
cd neugi_swarm_v2
python -m pytest tests/ -q --tb=short -p no:anchorpy
# Expected: 193 passed, 0 warnings
```

### Smoke Test CLI
```bash
# Requires PYTHONPATH=repo root
PYTHONPATH=../ python -m neugi_swarm_v2.cli.cli --help
```

### Core API
```python
from neugi_swarm_v2 import NeugiSwarmV2

swarm = NeugiSwarmV2()
response = swarm.chat("Hello, NEUGI!")
print(response.text)

# Persist continuity
swarm.remember("User prefers dark mode")
```

---

## Architecture Decisions

### Import System
- **ABSOLUTE imports** used throughout: `from memory.scopes import ...`
- `__init__.py` injects `sys.path.insert(0, _PACKAGE_DIR)` so `python -m` works
- Do NOT use relative imports (`from .scopes import ...`) — tests break

### Memory Storage
- **Single source of truth:** `MemorySystem` (SQLite + optional vectors)
- `SoulEngine` is a **view layer** — it renders MEMORY.md from MemorySystem, never duplicates storage
- `append_memory()` writes to SQLite when `memory_system` attached, else file fallback

### Wizard Architecture
- `GeniusWizard` — zero-dependency, pure stdlib, for first-time setup
- `SmartWizard` — same but with different UX flow
- `RescueWizard` — interactive auto-fix with health checks
- All three are maintained; `neugi wizard` uses `RescueWizard`

### Version Bumping
When changing version, update ALL of:
- `neugi_swarm_v2/__init__.py` → `__version__`
- `neugi_swarm_v2/tools/__init__.py` → `__version__`
- `neugi_swarm_v2/pyproject.toml` → `version`
- `neugi_swarm_v2/install.bat` / `install.sh` banners
- HTML files: `index.html`, `docs.html`, `dashboard.html`
- `CHANGELOG.md`

---

## Conventions

### File I/O
- **ALWAYS** specify `encoding="utf-8"` in `open()` calls
- Use `Path.read_text()` / `Path.write_text()` where possible

### Security
- `getpass.getpass()` for API key input (never `input()`)
- `webbrowser.open()` for URLs (never `os.system("start ...")`)
- `subprocess.run(shell=False)` (default) — never `shell=True`
- `eval()` must use `{"__builtins__": {}}` scope

### Adding New Tests
- Place in `tests/test_<module>.py`
- Use `tempfile.TemporaryDirectory()` for disk tests
- Import via absolute path: `from context.soul_engine import SoulEngine`

---

## Common Gotchas

1. **pytest anchorpy plugin conflict** — always run with `-p no:anchorpy`
2. **Windows `os.system("cls")`** — still in `genius_wizard.py`, safe but ideally use `subprocess`
3. **Circular imports** — `memory_core.py` imports `scopes.py` imports `memory_core.py`? No, it doesn't. But be careful with `assistant.py` importing `NeugiSwarmV2`.
4. **PromptAssembler `_build_identity`** — now checks `soul_engine.exists()` first; if soul files present, uses them instead of basic stub
5. **MemorySystem lazy init** — `EmbeddingEngine` is lazy-loaded; don't assume vectors work without `sentence-transformers` or Ollama

---

## Autonomous Subsystem (NEW in v2.1.1)

NEUGI now acts pro-actively during idle periods via the **AutonomousLoop**:

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌──────────┐
│  Observer   │ → │   Decision   │ → │   Executor  │ → │ Reporter │
│  (lihat)    │    │   (pikir)    │    │   (lakukan) │    │ (lapor)  │
└─────────────┘    └──────────────┘    └─────────────┘    └──────────┘
```

**IdleObserver** collects signals from:
- Memory trends (recurring topics, consolidation needs)
- Goals (stuck, blocked, nearly-complete)
- System health (errors, circuit breakers, rate limits)
- Learning opportunities (repeated patterns, skill gaps)

**ProactiveDecisionEngine** evaluates each observation:
- Confidence threshold (default: 0.5)
- Value threshold (default: 0.3)
- Risk threshold (default: 0.6)
- Daily action limit (default: 20)

**SelfDirectedExecutor** handles (NOW WIRED TO REAL SUBSYSTEMS):
- Memory consolidation (`CONSOLIDATE_MEMORY`) → `DreamingEngine.run_cycle()`
- Goal decomposition (`DECOMPOSE_GOAL`) → `GoalSystem.decompose()` (async-safe)
- Goal completion (`COMPLETE_GOAL`) → `GoalSystem.update_progress(goal_id, 1.0)`
- Blocker resolution (`RESOLVE_BLOCKER`) → `AutonomousAgentSpawner.spawn_strategist_agent()` + `AgentManager.delegate()`
- Self-healing (`SELF_HEAL`) → Real health checks + circuit breaker reset
- Pro-active research (`PROACTIVE_RESEARCH`) → `ResearchEngine.research()` + `AutonomousAgentSpawner.spawn_research_agent()`
- Skill learning (`LEARN_SKILL`) → `SkillGenerator.generate_skills_from_patterns()`
- System optimization (`OPTIMIZE`) → Performance suggestions logged to memory

**ActivityReporter** routes reports to:
- Memory system (audit trail)
- Dashboard (real-time updates via `NotificationDispatcher`)
- Logs (structured logging)
- User notification (critical/urgent only via Telegram/Discord/Slack)

**NotificationDispatcher** (`autonomous/notification_dispatcher.py`):
- Supports Telegram, Discord, Slack, WhatsApp, Dashboard, Log channels
- Respects user preferences: frequency (immediate/digest/silent), severity threshold, quiet hours
- Critical notifications sent immediately; others batched for digest

**AutonomousAgentSpawner** (`autonomous/agent_spawner.py`):
- Spawns dedicated TypedAgent instances for complex tasks:
  - `spawn_research_agent()` — deep-dive investigation
  - `spawn_coder_agent()` — code/skill generation
  - `spawn_analyst_agent()` — pattern/trend analysis
  - `spawn_strategist_agent()` — planning & optimization
- All agent results auto-saved to memory with `role="agent"`

**Dashboard Live Status** (`AutonomousLoop.get_live_status()`):
- Returns real-time dict: state, idle_seconds, circuit_open, action_count_today, recent_activities
- Designed for WebSocket streaming to dashboard UI

### Safety Mechanisms
- **Auto-start**: Loop auto-starts in daemon thread after `NeugiSwarmV2` init (configurable via `autonomous=False`)
- **Circuit breaker**: Stops after 5 consecutive failures, retries after 5 min
- **Idle threshold**: Only acts after 5 min of no user interaction; reset by ANY user chat (Swarm + Assistant)
- **Rate limiting**: Max 20 autonomous actions per day (auto-resets at midnight UTC)
- **Thread safety**: All mutable shared state protected by `RLock`; no races on counters or circuit breaker
- **Resource caps**: Activity log capped at 1000 entries; report log capped at 1000
- **Dry run mode**: Observe and decide without executing
- **Resource budgets**: Time and token limits per execution

### Known Architectural Boundaries
`CronScheduler` (gateway/cron.py) and `HeartbeatEngine` (gateway/heartbeat.py) are legacy scheduling subsystems. They are NOT yet unified with `AutonomousLoop`. To avoid redundancy:
- Use `AutonomousLoop` for pro-active AI-driven decisions (memory, goals, learning)
- Use `CronScheduler` only for hard-scheduled deterministic tasks (backups, cleanup)
- Use `HeartbeatEngine` only for health-check watchdog tasks
They share SQLite backends and are safe to run concurrently (SQLite WAL serialization).

### CLI Commands
```bash
neugi autonomous start     # Enable pro-active behavior
neugi autonomous stop      # Disable pro-active behavior
neugi autonomous status    # Show loop state and statistics
neugi autonomous once      # Run one tick immediately (testing)
```

### Programmatic API
```python
from neugi_swarm_v2 import NeugiSwarmV2

# Autonomous loop auto-starts by default (daemon thread)
swarm = NeugiSwarmV2()

# User chat automatically resets idle timer
response = swarm.chat("Hello!")

# Disable autonomous behavior entirely
swarm = NeugiSwarmV2(autonomous=False)

swarm.stop_autonomous()    # Stop the loop
swarm.start_autonomous()   # Restart manually
```

### Touch Points (Idle Timer Reset)
The idle timer is reset automatically from:
- `NeugiSwarmV2.chat()` — calls `autonomous_loop.touch()`
- `NeugiAssistantV2.chat()` — calls `on_user_interaction()` callback (wired by Swarm)
- Channels that integrate via `NeugiSwarmV2` will inherit this automatically

---

## Karpathy Autoresearch Engine (NEW in v2.1.1)

Implements Andrej Karpathy's vision of autonomous research:

```
Query → Search → Read → Synthesize → Hypothesize → Iterate → Report
```

**ResearchEngine** (`autonomous/research_engine.py`):
- Iterative deep-dive research with configurable rounds (default: 3)
- Web search integration via `WebSearch` (Jina AI + DuckDuckGo fallback)
- LLM-driven synthesis and hypothesis generation
- Source tracking with citations for verification
- Early convergence when no new hypotheses generated
- Automatic memory storage of research reports

**Usage:**
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

**Autonomous Integration:**
- `IdleObserver._observe_research_opportunities()` detects repeated question patterns
- `SelfDirectedExecutor._execute_research()` triggers full ResearchEngine when `web_search` available
- `DecisionType.PROACTIVE_RESEARCH` maps from `ObservationType.KNOWLEDGE_GAP`
- Research reports stored in memory with `role="research"` and `tags=["autoresearch"]`

**Resource Limits:**
- Max rounds: 3 (configurable)
- Max sources per round: 5 (configurable)
- Token budget per synthesis: 4000 (configurable)
- Timeout per session: 120s (configurable)

---

## How to Extend

### Adding a New Soul File
1. Add `SoulFile` to `context/soul_engine.py` `DEFAULT_FILES`
2. Add default template constant
3. Update `get_identity_prompt()` if order matters
4. Add test in `tests/test_soul_engine.py`

### Adding a New CLI Command
1. Add entry in `cli/cli.py` `_register_commands()`
2. Add handler method `_cmd_<name>()`
3. Follow existing pattern: return `CommandResult(status=..., message=...)`
4. Use `console.print()` with rich tags: `[success]`, `[error]`, `[warning]`, `[info]`

### Adding a New Tool
1. Add static method in `tools/builtins.py` under appropriate class
2. Register in `register_builtin_tools()` at bottom of file
3. Add test in `tests/test_tools.py`

### Adding a New Autonomous Execution Handler
1. Add handler method in `autonomous/executor.py` under `_execute_*` pattern
2. Map `DecisionType` → handler in `_execute_decision()`
3. Map `DecisionType` → `ExecutionType` in `_map_decision_type()`
4. Add test in `tests/test_autonomous.py` under `TestSelfDirectedExecutor`

### Adding a New Observation Source
1. Add observation method in `autonomous/observer.py` under `_observe_*` pattern
2. Add signal dataclass if needed (e.g., `ExternalSignal`)
3. Wire into `observe()` dispatch
4. Map `ObservationType` → `DecisionType` in `ProactiveDecisionEngine._OBS_TO_DECISION`
5. Add test in `tests/test_autonomous.py` under `TestIdleObserver`

### Adding a New Research Capability
1. Research engine is modular — extend `ResearchEngine` subclass or modify `ResearchConfig`
2. Add source type in `ResearchSource.source_engine` enum space
3. Customize `_build_synthesis_prompt()` for domain-specific prompting
4. Wire into `ExecutionContext.web_search` for autonomous triggers
5. Add test in `tests/test_autonomous.py` under `TestResearchEngine`

---

## Model Capability Routing (NEW in v2.1.1)

NEUGI adapts its entire behavior based on the connected model's capability:

```
User selects model → CapabilityProfile auto-built → All subsystems adapt
```

**CapabilityProfile** (`model_capability_router.py`):
- `ModelTier.LOCAL` (<7B): fragile, needs maximal prompting, 1 tool/call
- `ModelTier.MEDIUM` (7B-70B): balanced, 3 tools/call
- `ModelTier.CLOUD` (200B+): native function calling, 10 tools/call

**Adaptation surfaces:**
1. **PromptAssembler** — section budgets, identity notes, memory entry limits
2. **ToolRegistry** — `list_compatible_tools()` filters by complexity (trivial/simple/medium/complex/strategic)
3. **ToolExecutor** — retries, timeout, circuit breaker thresholds adapted by tier
4. **ProactiveDecisionEngine** — confidence/value/risk thresholds + daily action limits by tier
5. **Autonomous Research** — rounds (1/2/3) and sources (2/3/5) by tier

**Tool Complexity Classification** (`tools/builtins.py`):
- `TRIVIAL`: 0 params (system_cpu_info)
- `SIMPLE`: 1-2 params, no side effects (web_search, file_read)
- `MEDIUM`: multi-param, stateful (code_lint, git_commit)
- `COMPLEX`: dangerous side effects (docker_run, system_execute_command)
- `STRATEGIC`: requires planning, high risk (git_push, docker_compose_up)

**Wizard Multi-Provider Support** (`cli/genius_wizard.py`):
- Curated capable models only (weak models excluded)
- Custom model input for any model
- Custom endpoint for OpenAI-compatible / Anthropic-compatible providers
- Auto-detects API keys for all providers
- Capability preview shown before saving config

---

## Configuration (Simple)

NEUGI keeps it simple — **one JSON file** that anyone can edit:

```
~/.neugi/config.json
```

**Auto-generated by the wizard**, user-editable anytime:

```json
{
  "_readme": "NEUGI Config — Edit this file to change your AI setup",
  "version": "2.1.1",
  "llm": {
    "_comment": "Your AI provider and model",
    "provider": "ollama",
    "model": "qwen2.5-coder:7b",
    "fallback_model": "llama3.2:3b",
    "base_url": "",
    "ollama_url": "http://localhost:11434",
    "api_key": "",
    "temperature": 0.7,
    "max_tokens": 4096
  },
  "memory": {
    "_comment": "How long NEUGI remembers things",
    "enabled": true,
    "daily_ttl_days": 30,
    "dreaming_enabled": true
  },
  "skills": {
    "_comment": "Auto-generate skills from your conversations",
    "enabled": true,
    "auto_generate": true
  },
  "dashboard": {
    "_comment": "Web dashboard settings",
    "enabled": true,
    "port": 17901
  }
}
```

**To change your AI:**
1. Run `neugi setup` again, or
2. Edit `~/.neugi/config.json` with any text editor, or
3. Use `neugi config set llm.model=gpt-4o`

That's it. No YAML, no profiles, no layers.

---

## Soul System (NEW in v2.1.1)

NEUGI now implements the SOUL.md pattern:

```
~/.neugi/soul/
├── SOUL.md      → Identity, worldview, values (static)
├── STYLE.md     → Voice, syntax, patterns (static)
├── USER.md      → User preferences & facts (semi-static)
├── WORLD.md     → Project/environment context (static)
└── MEMORY.md    → Continuity snapshot (volatile / rendered)
```

- Static files are written once by `SoulEngine.init_defaults()`
- MEMORY.md is **rendered** from MemorySystem when `memory_system` attached
- `SoulEngine.append_memory()` writes to SQLite (not duplicate file)
- `neugi soul remember <note>` CLI command for manual continuity

---

---

## Observability Event Bus (NEW in v2.1.2)

NEUGI now includes a lightweight, thread-safe event bus:

```
EventBus (thread-safe, history, middleware)
  ├── subscribe(event_name, callback)
  ├── add_middleware(callback)      ← called for ALL events
  ├── publish(event_name, payload, source)
  └── get_history(event_name=None)
```

**Core events** (published by ToolExecutor):
- `tool_execution_success`: tool name, duration_ms, result
- `tool_execution_failure`: tool name, error

**Plugin integration**: Use `get_event_bus()` from `observability.event_bus` to subscribe.

Example plugins: `plugins/notification_example/`, `plugins/metrics_example/`

---

## Browser Agent Plugin (NEW in v2.1.2)

Plugin at `plugins/browser_agent/`:
- `agent.py`: TypedAgent-based LLM-driven browser control
- `browser_agent.py`: reasoning-loop alternative
- `README.md`: full documentation

---

## Plugin Validator (NEW in v2.1.2)

`tools/plugin_validator.py`: validates plugin manifest, entry points, hooks before install.
CLI: `python tools/plugin_validator.py <path>`

---

## Configuration

Added `observability` section to `~/.neugi/config.json`:
```json
{
  "observability": { "enabled": true, "max_history": 1000 }
}
```

---

## Version
Current: **2.1.2** (previously 2.1.1)

---

Last updated: 2026-05-01
