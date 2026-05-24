# NEXT STEPS — NEUGI Swarm v2 Perfection (Handoff Document)

> For the next AI agent session. Pick up from here.
> **FULL DETAILED HANDOFF:** `.kiro/specs/anomaly-cleanup-perfection/NEXT-STEPS-HANDOFF.md`

## ⚠️ STATE MUNGKIN SUDAH BERUBAH

Subagent sebelumnya mungkin masih running. Tasks `[~]` di tasks.md mungkin sudah selesai.
**VERIFY DULU sebelum lanjut:**
```bash
cd neugi_swarm_v2
python -m pytest tests/ -q --tb=short -p no:anchorpy
ruff check neugi_swarm_v2/
bandit -r neugi_swarm_v2/ -c pyproject.toml
```

## Current State: 17/33 tasks completed (mungkin lebih kalau subagent selesai)

**Phase 1 ✅ DONE** — Dead code removal, deprecated aliases, useless files, import hygiene
**Phase 2 ✅ DONE** — SecretManager wiring, BudgetTracker→ToolExecutor, scheduling boundaries
**Phase 3 🔄 PARTIALLY DONE** — Some subagents already started (marked `[~]` in tasks.md)
**Phase 4 🔄 PARTIALLY DONE** — Some subagents already started

## Spec Location

```
k:\neugi_swarm\.kiro\specs\anomaly-cleanup-perfection\
├── requirements.md   (13 requirements)
├── design.md         (18 correctness properties)
├── tasks.md          (33 tasks, 17 done)
└── .config.kiro
```

## What Was Already Done

1. **~7K lines dead code removed** from security/ and governance/
2. **Deprecated wizards deleted** (smart_wizard.py, wizard.py) → GeniusWizard is sole wizard
3. **SecretManager fully wired** — config.py retrieves API keys encrypted, GeniusWizard stores encrypted
4. **BudgetTracker wired** into ToolExecutor (governance check before tool execution)
5. **Import hygiene fixed** — no relative imports, no circular deps
6. **Scheduling boundaries enforced** — CronScheduler/HeartbeatEngine have boundary docstrings
7. **Useless files/folders removed** — repo/ deleted, root evals/ deleted, caches cleaned
8. **Root .gitignore updated** with all artifact patterns

## Remaining Tasks (Priority Order)

### HIGH PRIORITY — Do These First

| Task | Description | Effort |
|------|-------------|--------|
| 5.4 | Fix all Ruff linting violations | Medium — `ruff check --fix` does most work |
| 5.5 | Fix all Bandit security findings | Medium — eval(), subprocess, shell=True |
| 5.3 | Harden error handling | Large — bare excepts, encoding, I/O wrapping |
| 7.1 | Add TLS to dashboard WebSocket | Small — ssl.SSLContext wrapping |

### MEDIUM PRIORITY — Quality Polish

| Task | Description | Effort |
|------|-------------|--------|
| 5.1 | Type annotations (all public functions) | HUGE — 120+ modules |
| 5.2 | Google-style docstrings (all public) | HUGE — 120+ modules |
| 7.2 | Refactor hasattr-only tests | Medium |
| 7.3 | Upgrade trivial mock tests | Medium |

### LOW PRIORITY — Optional

| Task | Description |
|------|-------------|
| 3.6 | Property tests for Phase 2 |
| 5.6 | Property tests for Phase 3 |
| 7.5 | Property tests for Phase 4 |

## Quick Commands

```bash
# Run tests (from neugi_swarm_v2/)
cd k:\neugi_swarm\neugi_swarm_v2
python -m pytest tests/ -q --tb=short -p no:anchorpy

# Ruff lint
ruff check neugi_swarm_v2/

# Ruff auto-fix
ruff check neugi_swarm_v2/ --fix

# Bandit security scan
bandit -r neugi_swarm_v2/ -c pyproject.toml

# Check imports
python -c "import importlib, pkgutil; [importlib.import_module(m.name) for m in pkgutil.walk_packages(['neugi_swarm_v2'])]"
```

## Known Issues (Pre-existing, Not Caused By Us)

- **12 test failures in test_mcp.py** — async infrastructure issue (missing pytest-asyncio). Unrelated to our changes.
- **2 Playwright tests skipped** — expected when Playwright not installed
- **Meta.json file lock** — `C:\Users\Asus\.kiro\tasks\...\anomaly-cleanup-perfection.meta.json` has persistent EPERM. May need to close Kiro and delete the .tmp files manually.

## Architecture Notes for Next Agent

- **Absolute imports only** — `from memory.memory_core import MemorySystem` (not `from .memory_core`)
- **sys.path injection** in `__init__.py` makes this work
- **Python 3.10+ syntax** — use `str | None`, `list[str]`, `dict[str, Any]`
- **Google-style docstrings** — one-line summary + Args + Returns + Raises
- **encoding="utf-8"** on ALL `open()` calls
- **eval() must use** `{"__builtins__": {}}` scope
- **subprocess must use** `shell=False` with list args
- **Tests run from** `neugi_swarm_v2/` directory
- **Test count invariant** — must remain ≥ 379 at all times

## User's Additional Request (Not Yet Done)

User wants a button on neugi.com (index.html) linking to **smar.neugi.com** (Micro-Frontier Model Research page). Suggested placement: **hero section + header nav**. This is a simple HTML edit to `k:\neugi_swarm\index.html`.

---

## ULTIMATE GOAL

Project ini harus bisa:
1. `pip install .` tanpa error
2. `neugi wizard` → setup config + API key encrypted
3. `neugi chat "Hello"` → response dari LLM
4. `neugi autonomous start` → autonomous loop running
5. Dashboard di `localhost:17901`
6. Semua 61 tools functional
7. Memory persistent (SQLite FTS5)
8. Multi-agent delegation working
9. MCP server connectable

## SETELAH SEMUA TASKS SELESAI

1. Smoke test end-to-end (import, CLI, config)
2. Fix test_mcp.py (install pytest-asyncio)
3. Packaging (`python -m build`)
4. Update README.md + CHANGELOG.md
5. Add smar.neugi.com button di index.html
6. Git commit & push

**Baca `.kiro/specs/anomaly-cleanup-perfection/NEXT-STEPS-HANDOFF.md` untuk detail lengkap.**
