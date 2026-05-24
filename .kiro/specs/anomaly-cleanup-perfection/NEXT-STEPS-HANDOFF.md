# NEXT STEPS HANDOFF — NEUGI Swarm v2 Perfection

> **BACA INI PERTAMA.** Dokumen ini adalah satu-satunya sumber kebenaran untuk melanjutkan pekerjaan.

## ⚠️ PENTING: State Mungkin Sudah Berubah

Subagent sebelumnya mungkin masih running saat handoff ini dibuat. Tasks yang ditandai `[~]` (partially done) di tasks.md MUNGKIN sudah selesai atau berubah. **LANGKAH PERTAMA LU:**

1. Run `python -m pytest tests/ -q --tb=short -p no:anchorpy` dari `neugi_swarm_v2/` — cek berapa test pass
2. Run `ruff check neugi_swarm_v2/` — cek berapa violations tersisa
3. Run `bandit -r neugi_swarm_v2/ -c pyproject.toml` — cek berapa findings
4. Grep: `grep -rn "except:" neugi_swarm_v2/ --include="*.py" | grep -v "except "` — cek bare excepts
5. Baca tasks.md — cek mana yang sudah `[x]` vs masih `[~]` vs `[ ]`

**Jangan assume state dari dokumen ini — VERIFY DULU.**

## Status Saat Handoff Dibuat

**Completed: Phase 1 + Phase 2 (17/33 tasks)**
**Remaining: Phase 3 + Phase 4 (16 tasks, 11 substantive + 5 checkpoints/optional)**
**Partially started by previous subagents: 5.1, 5.2, 5.3, 5.4, 5.5, 7.1, 7.2, 7.3, 7.4**

### Yang Sudah Selesai ✅

| Task | Deskripsi |
|------|-----------|
| 1.1 | Dead code removal security/ (~7K lines removed) |
| 1.2 | Dead code removal governance/ (policy.py, audit.py removed) |
| 1.3 | Dead code removal remaining subsystems |
| 1.4 | Deprecated wizard aliases deleted (smart_wizard.py, wizard.py) |
| 1.5 | Useless files/folders removed (repo/, root evals/) |
| 1.6 | Relative imports → absolute imports |
| 1.7 | Circular imports fixed |
| 1.8 | Property tests Phase 1 (optional, done) |
| 3.1 | SecretManager .get() + error types added |
| 3.2 | config.py wired to SecretManager (no plaintext API keys) |
| 3.3 | GeniusWizard stores API keys via SecretManager |
| 3.4 | BudgetTracker wired into ToolExecutor |
| 3.5 | Scheduling boundaries enforced (CronScheduler/HeartbeatEngine docstrings) |

### Yang Partially Done [~] (sudah dimulai tapi belum verified)

Tasks 5.1-5.5 dan 7.1-7.4 ditandai `[~]` di tasks.md — artinya subagent sudah mulai kerjain tapi belum complete/verified. **Cek dulu state aktual sebelum lanjut.**

---

## Remaining Tasks (Prioritized)

### PHASE 3 — Code Quality (HIGH VOLUME, ~120 modules)

**Task 5.1: Type Annotations** [~]
- Target: semua public functions/methods di 29 subsystems
- Syntax: Python 3.10+ (`list[str]`, `str | None`, bukan `Optional`)
- Verify: `mypy neugi_swarm_v2/ --ignore-missing-imports`
- **TIP**: Kerjain per-subsystem, jangan sekaligus. Prioritas: core API (assistant.py, __init__.py, config.py, memory/, tools/, autonomous/)

**Task 5.2: Google-style Docstrings** [~]
- Target: semua public classes + functions tanpa docstring
- Format: one-line summary + Args + Returns + Raises
- **TIP**: Bisa digabung dengan 5.1 per-file supaya efisien

**Task 5.3: Error Handling Hardening** [~]
- Replace bare `except:` dan `except Exception:` dengan specific types
- Add `encoding="utf-8"` ke semua `open()` calls
- Wrap I/O operations in try/except
- **TIP**: Jalanin `grep -rn "except:" neugi_swarm_v2/ --include="*.py"` dulu untuk scope

**Task 5.4: Ruff Compliance** [~]
- Run: `ruff check neugi_swarm_v2/ --fix` (auto-fix dulu)
- Manual fix sisanya
- Config di pyproject.toml: target py310, rules E,F,W,I,B,S,UP
- Verify: zero violations

**Task 5.5: Bandit Security** [~]
- `eval()` → must use `{"__builtins__": {}}` scope
- `subprocess` → must use `shell=False`
- No hardcoded passwords
- Verify: `bandit -r neugi_swarm_v2/ -c pyproject.toml`

### PHASE 4 — TLS + Test Quality

**Task 7.1: Dashboard WebSocket TLS** [~]
- Add `tls_enabled`, `tls_cert_path`, `tls_key_path` to DashboardConfig
- Create `DashboardTLSError` exception
- Implement ssl.SSLContext wrapping in DashboardServer.start()
- File: `neugi_swarm_v2/dashboard/server.py`

**Task 7.2: Eliminate hasattr-only tests** [~]
- Search: `grep -rn "hasattr(" neugi_swarm_v2/tests/`
- Replace with behavioral assertions (invoke method, check output)

**Task 7.3: Upgrade trivial mock tests** [~]
- Add assertions on mock call args/count
- Or replace mocks with real invocations where possible

**Task 7.4: Verify test suite integrity** [~]
- Run: `python -m pytest tests/ -q --tb=short -p no:anchorpy`
- Must: ≥379 tests collected, all non-optional pass

---

## Critical Context

### Project Structure
```
k:\neugi_swarm\
├── neugi_swarm_v2/          ← MAIN PACKAGE (all work here)
│   ├── __init__.py          ← Entry point (NeugiSwarmV2)
│   ├── assistant.py         ← NeugiAssistantV2.chat()
│   ├── config.py            ← Config loader (SecretManager wired)
│   ├── security/            ← SecretManager, ExecutionSandbox, CommandValidator
│   ├── governance/          ← BudgetTracker, ApprovalGate (cleaned)
│   ├── tools/               ← 61 tools + ToolExecutor (BudgetTracker wired)
│   ├── autonomous/          ← AutonomousLoop, ResearchEngine
│   ├── memory/              ← 3-tier memory system
│   ├── cli/                 ← GeniusWizard (canonical), RescueWizard
│   ├── tests/               ← 379 tests
│   └── ... (29 subsystems total)
├── .kiro/specs/anomaly-cleanup-perfection/
│   ├── requirements.md      ← 13 requirements
│   ├── design.md            ← 18 correctness properties, 4 phases
│   └── tasks.md             ← This task list
└── AGENTS.md                ← Agent context (read this too)
```

### Key Conventions
- **Imports**: ABSOLUTE only (`from memory.scopes import ...`), never relative
- **open()**: Always `encoding="utf-8"`
- **eval()**: Always `{"__builtins__": {}}` scope
- **subprocess**: Always `shell=False`
- **Tests**: Run from `neugi_swarm_v2/` with `python -m pytest tests/ -q --tb=short -p no:anchorpy`
- **Type hints**: Python 3.10+ syntax (PEP 604 `|`, PEP 585 `list[]`)
- **Docstrings**: Google-style

### Known Issues (Pre-existing, NOT regressions)
- 12 test failures in `test_mcp.py` — async infrastructure issue (missing pytest-asyncio), unrelated to our changes
- 2 Playwright tests skipped when browser not available — expected

### File Lock Issue
- `C:\Users\Asus\.kiro\tasks\...\anomaly-cleanup-perfection.meta.json` has persistent EPERM lock
- Workaround: update tasks directly in tasks.md by changing `[ ]` → `[x]`
- Don't rely on `task_update` tool — it will fail with EPERM

---

## Execution Strategy for Next Agent

### Recommended Order (credit-efficient):

1. **5.4 Ruff first** — `ruff check --fix` auto-fixes 80% of issues, low effort
2. **5.5 Bandit** — targeted fixes (eval, subprocess, hardcoded secrets)
3. **5.3 Error handling** — grep for bare excepts, fix systematically
4. **5.1 + 5.2 combined** — type hints + docstrings per-file (most expensive, do last)
5. **7.1 TLS** — single file change (dashboard/server.py)
6. **7.2 + 7.3 Test refactoring** — grep hasattr, upgrade assertions
7. **7.4 Final verification** — run full test suite

### Per-Subsystem Priority (if credit-limited):
1. Core: `__init__.py`, `assistant.py`, `config.py`, `llm_provider.py`
2. Memory: `memory/memory_core.py`, `memory/dreaming.py`
3. Tools: `tools/tool_executor.py`, `tools/builtins.py`
4. Autonomous: `autonomous/loop_engine.py`, `autonomous/executor.py`
5. CLI: `cli/genius_wizard.py`, `cli/cli.py`
6. Rest: best-effort

### Verification Commands
```bash
cd neugi_swarm_v2
python -m pytest tests/ -q --tb=short -p no:anchorpy    # Tests (≥379 pass)
ruff check neugi_swarm_v2/                               # Lint (zero violations)
bandit -r neugi_swarm_v2/ -c pyproject.toml              # Security (zero findings)
mypy neugi_swarm_v2/ --ignore-missing-imports            # Types (best-effort)
```

---

## JANGAN LUPA

- Baca `AGENTS.md` di root — itu context lengkap project
- Baca `requirements.md` dan `design.md` di spec folder untuk full context
- Test count HARUS ≥ 379 setelah semua perubahan
- Breaking changes OK — project belum public release
- Tasks `[~]` artinya partially done — CEK DULU sebelum overwrite
- Optional tasks (marked `*`) bisa di-skip kalau credit terbatas

---

## ULTIMATE GOAL: Production-Ready Agentic Framework

Project ini HARUS bisa:
1. `pip install .` tanpa error
2. `neugi wizard` → setup config + API key (encrypted via SecretManager)
3. `neugi chat "Hello"` → dapat response dari LLM
4. `neugi autonomous start` → autonomous loop berjalan
5. Dashboard accessible di `http://localhost:17901`
6. Semua 61 tools callable dan functional
7. Memory system persistent (SQLite FTS5)
8. Multi-agent delegation working (CrewAI-style)
9. MCP server bisa di-connect dari client

## SETELAH SEMUA TASKS SELESAI — Launch Checklist

Setelah Phase 3 + 4 selesai, lakukan ini:

### 1. Smoke Test End-to-End
```bash
cd neugi_swarm_v2
# Unit tests
python -m pytest tests/ -q --tb=short -p no:anchorpy

# Import health
python -c "from neugi_swarm_v2 import NeugiSwarmV2; print('OK')"

# CLI smoke
PYTHONPATH=../ python -m neugi_swarm_v2.cli.cli --help

# Config loading (tanpa API key = OK, harus gak crash)
python -c "from config import load_config; c = load_config(); print(c.llm.provider)"
```

### 2. Fix test_mcp.py (Pre-existing Issue)
```bash
pip install pytest-asyncio
# Atau tambahkan ke pyproject.toml [project.optional-dependencies] test = ["pytest-asyncio"]
# Lalu fix async test markers
```

### 3. Packaging
```bash
# Pastikan pyproject.toml valid
pip install build
python -m build
# Harus menghasilkan dist/neugi_swarm_v2-2.1.3-py3-none-any.whl
```

### 4. Documentation Sync
- Update README.md kalau ada breaking changes
- Update CHANGELOG.md dengan semua perubahan
- Update AGENTS.md kalau ada perubahan arsitektur

### 5. Button smar.neugi.com
User mau tombol di `index.html` yang link ke `smar.neugi.com` (Micro-Frontier Model Research). Taruh di:
- Header nav (next to existing links)
- Hero section (as a secondary CTA button)

### 6. Final Git Commit
```bash
git add -A
git commit -m "feat: complete anomaly cleanup and production hardening (Phase 1-4)"
git push origin main
```

---

## TL;DR UNTUK NEXT AGENT

1. **VERIFY STATE DULU** — run tests, ruff, bandit, cek tasks.md
2. **Selesaikan tasks yang masih `[~]` atau `[ ]`** — prioritas: 5.4 → 5.5 → 5.3 → 5.1+5.2 → 7.x
3. **Run full verification** — semua harus pass
4. **Smoke test end-to-end** — import, CLI, config loading
5. **Fix test_mcp.py** — install pytest-asyncio
6. **Add smar.neugi.com button** — di index.html header + hero
7. **Commit & push**

**TARGET: Project ini harus bisa di-clone, di-install, dan di-run oleh siapapun sebagai agentic framework yang functional.**
