# Implementation Plan: Anomaly Cleanup Perfection

## Overview

Systematic cleanup and hardening of the NEUGI Swarm v2 codebase across all 29 subsystems. Organized into 4 phases following dependency order: Phase 1 removes dead code and fixes imports, Phase 2 wires subsystems, Phase 3 hardens code quality at scale, Phase 4 adds TLS and refactors tests. All tasks target `neugi_swarm_v2/` with tests at `neugi_swarm_v2/tests/`.

## Tasks

- [x] 1. Phase 1 — Dead Code, Deprecated Aliases, Useless Files, Import Hygiene
  - [x] 1.1 Remove dead code from security/ subsystem (~7,000 lines)
    - Run `vulture neugi_swarm_v2/security/ --min-confidence 80` to identify dead code
    - Remove dead infrastructure code (shield_reasoning.py bulk, exploit_prevention.py bulk)
    - Preserve `SecretManager`, `ExecutionSandbox`, `CommandValidator` as they are actively used
    - Remove unused imports detected by `ruff check neugi_swarm_v2/security/ --select F401`
    - Update or remove any tests that reference removed dead code
    - Verify: `python -m pytest tests/ -q --tb=short -p no:anchorpy`
    - _Requirements: 1.1, 1.2, 1.5_

  - [x] 1.2 Remove dead code from governance/ subsystem
    - Run `vulture neugi_swarm_v2/governance/ --min-confidence 80`
    - Remove unreachable governance enforcement code in policy.py and audit.py
    - Keep `BudgetTracker` and `ApprovalGate` (wired in ToolExecutor)
    - Remove any functions/classes with zero callers
    - Update or remove tests referencing removed code
    - Verify: `python -m pytest tests/ -q --tb=short -p no:anchorpy`
    - _Requirements: 1.1, 1.3, 1.5_

  - [x] 1.3 Remove dead code from remaining subsystems
    - Run `vulture neugi_swarm_v2/ --min-confidence 80` for full package scan
    - Cross-reference with `ruff check neugi_swarm_v2/ --select F401,F841`
    - Remove all functions, classes, and imports with zero callers (excluding `__init__.py` public API exports)
    - Process module-by-module, running tests after each batch
    - Verify: `python -m pytest tests/ -q --tb=short -p no:anchorpy`
    - _Requirements: 1.1, 1.4, 1.5_

  - [x] 1.4 Delete deprecated wizard aliases and update references
    - Delete `neugi_swarm_v2/cli/smart_wizard.py`
    - Delete `neugi_swarm_v2/cli/wizard.py`
    - Search all files: `grep -r "SmartWizard\|SetupWizard\|smart_wizard\|cli.wizard" neugi_swarm_v2/`
    - Replace all references with `from cli.genius_wizard import GeniusWizard`
    - Update any `__init__.py` exports that reference the deleted modules
    - Verify zero matches remain for deprecated references
    - Verify: `python -m pytest tests/ -q --tb=short -p no:anchorpy`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 1.5 Remove useless files and folders
    - Delete root-level `evals/` directory (empty)
    - Delete `neugi_swarm_v2/.ruff_cache/` if present
    - Delete `neugi_swarm_v2/.mypy_cache/` if present
    - Delete `neugi_swarm_v2/dist/` if present
    - Delete `neugi_swarm_v2/neugi_swarm_v2.egg-info/` if present
    - Scan for and remove empty directories within `neugi_swarm_v2/` (excluding `__pycache__`)
    - Preserve `audit/` directory and `neugi_swarm_v2/evals/` (benchmark harness)
    - Update `.gitignore` to include: `__pycache__/`, `*.egg-info/`, `dist/`, `.ruff_cache/`, `.mypy_cache/`, `.pytest_cache/`
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

  - [x] 1.6 Fix import hygiene — convert relative imports to absolute
    - Search: `grep -rn "from \." neugi_swarm_v2/ --include="*.py"`
    - Convert all relative imports (`from .module` / `from ..module`) to absolute imports
    - Ensure all imports use the absolute form: `from subsystem.module import ...`
    - Verify: `python -m pytest tests/ -q --tb=short -p no:anchorpy`
    - _Requirements: 13.1_

  - [x] 1.7 Fix circular imports
    - Write a script to attempt `importlib.import_module()` on every module in neugi_swarm_v2
    - Identify any `ImportError` from circular references
    - Break cycles by extracting shared types into `types.py` or using `TYPE_CHECKING` guards
    - Use `from __future__ import annotations` where needed for forward references
    - Verify all modules importable independently
    - Verify: `python -m pytest tests/ -q --tb=short -p no:anchorpy`
    - _Requirements: 13.2, 13.3, 13.4_


  - [x]* 1.8 Write property tests for Phase 1 invariants
    - **Property 1: No Unused Imports** — verify `ruff check --select F401` produces zero violations across all modules
    - **Property 2: No Deprecated Wizard References** — verify no file contains `SmartWizard`, `SetupWizard`, `smart_wizard`, or `cli.wizard`
    - **Property 14: No Empty Purposeless Directories** — verify all directories in neugi_swarm_v2/ contain at least one .py or resource file
    - **Property 15: Build Artifacts in .gitignore** — verify all artifact patterns appear in .gitignore
    - **Property 17: No Relative Imports** — verify no `from .` or `from ..` import statements exist
    - **Property 18: All Modules Importable Independently** — verify `importlib.import_module()` succeeds for every module
    - **Validates: Requirements 1.4, 2.3, 2.5, 11.2, 11.4, 13.1, 13.3**

- [x] 2. Phase 1 Checkpoint
  - Ensure all tests pass, ask the user if questions arise.
  - Run: `python -m pytest tests/ -q --tb=short -p no:anchorpy`
  - Run: `ruff check neugi_swarm_v2/ --select F401`
  - Confirm test count ≥ 379

- [x] 3. Phase 2 — Secret Management, Subsystem Wiring, Scheduling Boundaries
  - [x] 3.1 Wire SecretManager convenience accessor and error types
    - Add `SecretNotFoundError` and `SecretDecryptionError` exception classes to `security/secret_manager.py`
    - Add `SecretManager.get(name: str) -> str` convenience method that raises `SecretNotFoundError` if missing
    - Ensure `get()` raises `SecretDecryptionError` on decrypt failure (never returns None or empty string)
    - Remove any fallback-to-plaintext code paths in SecretManager
    - Verify: `python -m pytest tests/ -q --tb=short -p no:anchorpy`
    - _Requirements: 3.3, 3.5_

  - [x] 3.2 Wire config.py to use SecretManager for API key retrieval
    - Modify `load_config()` in `config.py` to retrieve API keys via `SecretManager.get("llm_api_key")`
    - Remove any direct plaintext API key reading from config.json
    - Ensure `_migrate_api_key_to_secrets()` still works for first-time migration
    - If SecretManager fails, raise `ConfigurationError` — no silent fallback
    - Verify: `python -m pytest tests/ -q --tb=short -p no:anchorpy`
    - _Requirements: 3.1, 3.4_

  - [x] 3.3 Wire GeniusWizard to store API keys via SecretManager
    - Add `_store_api_key(self, key: str)` method to GeniusWizard
    - Use `SecretManager.add_secret()` with `SecretClass.API_KEY` classification
    - Ensure wizard stores key encrypted, not in plaintext config.json
    - Verify: `python -m pytest tests/ -q --tb=short -p no:anchorpy`
    - _Requirements: 3.2_

  - [x] 3.4 Wire BudgetTracker into ToolExecutor
    - Add `budget_tracker: BudgetTracker | None = None` parameter to `ToolExecutor.__init__()`
    - Add budget check before tool execution (after approval gate check)
    - Return `ExecutionResult(success=False, error="Budget exceeded")` when budget is exceeded
    - Wire BudgetTracker instantiation in the main orchestrator (`__init__.py` or wherever ToolExecutor is created)
    - Remove dead governance code (policy.py, audit.py) if they have zero callers after wiring
    - Verify: `python -m pytest tests/ -q --tb=short -p no:anchorpy`
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [x] 3.5 Enforce scheduling subsystem boundaries
    - Add boundary docstrings to `CronScheduler` class in `gateway/cron.py`
    - Add boundary docstrings to `HeartbeatEngine` class in `gateway/heartbeat.py`
    - Audit registered jobs — ensure no AI-driven callbacks in CronScheduler or HeartbeatEngine
    - Remove any duplicated AutonomousLoop decision-making logic from CronScheduler/HeartbeatEngine
    - Ensure CronScheduler is used exclusively for deterministic tasks
    - Ensure HeartbeatEngine is used exclusively for health-check watchdog tasks
    - Verify: `python -m pytest tests/ -q --tb=short -p no:anchorpy`
    - _Requirements: 12.1, 12.2, 12.3, 12.4_

  - [ ]* 3.6 Write property tests for Phase 2 invariants
    - **Property 3: API Key Access Through SecretManager** — verify no code path reads API keys directly from config.json at runtime
    - **Property 4: SecretManager Fails Loud** — verify `SecretManager.get()` raises exception for missing/invalid secrets (never returns None or empty)
    - **Property 16: Concurrent Schedulers Don't Deadlock** — verify concurrent `tick()` calls on AutonomousLoop, CronScheduler, HeartbeatEngine complete within 10s
    - **Validates: Requirements 3.1, 3.4, 3.5, 12.5**

- [x] 4. Phase 2 Checkpoint
  - Ensure all tests pass, ask the user if questions arise.
  - Run: `python -m pytest tests/ -q --tb=short -p no:anchorpy`
  - Confirm test count ≥ 379

- [ ] 5. Phase 3 — Type Hints, Docstrings, Error Handling, Ruff/Bandit
  - [~] 5.1 Add type annotations to all public functions and methods
    - Annotate all public function signatures (parameters + return types) across all 29 subsystems
    - Use Python 3.10+ syntax: `list[str]`, `dict[str, Any]`, `str | None` (not `Optional`, `Union`)
    - Skip private functions (prefixed with `_`) — best-effort only
    - Use `from __future__ import annotations` where needed for forward references
    - Verify: `mypy neugi_swarm_v2/ --ignore-missing-imports --no-strict-optional` (target zero errors on annotated functions)
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [~] 5.2 Add Google-style docstrings to all public classes and functions
    - Add docstrings to every public class lacking one
    - Add docstrings to every public function/method lacking one
    - Format: one-line summary + Args section (for ≥2 params) + Returns section (for non-None) + Raises section
    - Use Google-style consistently
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [~] 5.3 Harden error handling across all subsystems
    - Wrap all I/O operations (file, network, database) in try/except with specific exception types
    - Replace all bare `except:` and `except Exception:` with specific exception types
    - Add contextual logging to all exception handlers (operation name + relevant params)
    - Add `encoding="utf-8"` to all `open()` calls (and `Path.read_text()`/`Path.write_text()`)
    - Ensure unrecoverable errors raise descriptive custom exceptions (not silently swallowed)
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [~] 5.4 Fix all Ruff linting violations
    - Run `ruff check neugi_swarm_v2/ --fix` to auto-fix what's possible
    - Manually fix remaining violations (unused variables, import ordering, etc.)
    - Ensure Ruff config in pyproject.toml targets Python 3.10 with rules: E, F, W, I, B, S, UP
    - Remove all unused variables and imports flagged by Ruff
    - Verify: `ruff check neugi_swarm_v2/` produces zero violations
    - _Requirements: 8.1, 8.5_

  - [~] 5.5 Fix all Bandit security findings
    - Run `bandit -r neugi_swarm_v2/ -c pyproject.toml` to identify issues
    - Ensure all `eval()` calls use `{"__builtins__": {}}` scope
    - Refactor all `subprocess` calls with `shell=True` to use `shell=False` with argument lists
    - Replace hardcoded passwords/secrets with SecretManager references
    - Remove `assert` statements in production code (replace with explicit checks)
    - Verify: `bandit -r neugi_swarm_v2/ -c pyproject.toml` produces zero findings (excluding test files)
    - _Requirements: 8.2, 8.3, 8.4_

  - [ ]* 5.6 Write property tests for Phase 3 invariants
    - **Property 5: Public Callables Have Type Annotations** — AST-scan all public functions/methods, verify all params (except self/cls) and return types are annotated
    - **Property 6: Public Symbols Have Docstrings** — verify `__doc__` is not None/empty for all public classes, functions, methods
    - **Property 7: No Bare Except Clauses** — AST-parse all files, verify zero bare `except:` or unhandled `except Exception:`
    - **Property 8: All open() Calls Specify Encoding** — AST-scan for `open()` calls without `encoding` param (excluding binary mode)
    - **Property 9: All eval() Uses Restricted Builtins** — verify all `eval()` calls include `{"__builtins__": {}}` in globals
    - **Property 10: No Subprocess shell=True** — verify no subprocess call uses `shell=True`
    - **Validates: Requirements 5.1, 5.2, 6.1, 6.2, 7.3, 7.4, 8.3, 8.4**

- [~] 6. Phase 3 Checkpoint
  - Ensure all tests pass, ask the user if questions arise.
  - Run: `python -m pytest tests/ -q --tb=short -p no:anchorpy`
  - Run: `ruff check neugi_swarm_v2/`
  - Run: `bandit -r neugi_swarm_v2/ -c pyproject.toml`
  - Confirm test count ≥ 379

- [ ] 7. Phase 4 — WebSocket TLS and Test Quality
  - [~] 7.1 Add TLS support to dashboard WebSocket server
    - Extend `DashboardConfig` dataclass with `tls_enabled`, `tls_cert_path`, `tls_key_path` fields
    - Create `DashboardTLSError` exception class in dashboard module
    - Implement TLS wrapping in `DashboardServer.start()` using `ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)`
    - Validate cert/key paths exist at startup — raise `DashboardTLSError` if missing
    - Reject unencrypted connections when TLS is enabled
    - Add `dashboard.tls_enabled`, `dashboard.tls_cert_path`, `dashboard.tls_key_path` to config.json schema
    - Verify: `python -m pytest tests/ -q --tb=short -p no:anchorpy`
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

  - [~] 7.2 Refactor weak tests — eliminate hasattr-only assertions
    - Search tests for `hasattr(` usage as primary assertion
    - Replace each `hasattr` check with a behavioral assertion that invokes the method and verifies output
    - Ensure each refactored test calls the method under test and asserts on the result
    - Verify: `python -m pytest tests/ -q --tb=short -p no:anchorpy`
    - _Requirements: 10.1, 10.5_

  - [~] 7.3 Refactor weak tests — upgrade trivial mock tests
    - Identify tests that use mocks returning trivial values without verifying behavior
    - Add assertions on mock call arguments, call count, or replace mocks with real invocations
    - Ensure no test relies solely on import success as proof of correctness
    - Maintain test count ≥ 379 (add new tests if removing weak ones)
    - Verify: `python -m pytest tests/ -q --tb=short -p no:anchorpy`
    - _Requirements: 10.2, 10.3, 10.5_

  - [~] 7.4 Verify test suite integrity
    - Run full test suite: `python -m pytest tests/ -q --tb=short -p no:anchorpy`
    - Confirm collected test count ≥ 379
    - Confirm all non-optional tests pass (2 Playwright skips acceptable)
    - Fix any regressions introduced during refactoring
    - _Requirements: 10.3, 10.4_

  - [ ]* 7.5 Write property tests for Phase 4 invariants
    - **Property 11: TLS Rejects Unencrypted Connections** — verify plain connection to TLS-enabled server is rejected
    - **Property 12: Missing TLS Certs Raise Descriptive Error** — verify `DashboardServer.start()` raises `DashboardTLSError` for invalid cert paths
    - **Property 13: Every Test Has Behavioral Assertions** — scan all test functions, verify each contains `assert`, `pytest.raises`, or equivalent (not just `hasattr`)
    - **Validates: Requirements 9.2, 9.4, 10.1, 10.5**

- [~] 8. Final Checkpoint
  - Ensure all tests pass, ask the user if questions arise.
  - Run full verification suite:
    - `ruff check neugi_swarm_v2/` — zero violations
    - `bandit -r neugi_swarm_v2/ -c pyproject.toml` — zero findings
    - `python -m pytest tests/ -q --tb=short -p no:anchorpy` — ≥379 tests, all pass
    - `python -c "import importlib, pkgutil; [importlib.import_module(m.name) for m in pkgutil.walk_packages(['neugi_swarm_v2'])]"` — no ImportError
  - Confirm no deprecated wizard references remain
  - Confirm no relative imports remain

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation after each phase
- Property tests validate universal correctness properties from the design document
- Breaking changes are acceptable — backward compatibility is not a constraint
- Test count must remain ≥ 379 at all times
- All verification commands run from `neugi_swarm_v2/` directory
- Python 3.10+ syntax used throughout (PEP 604 unions, PEP 585 generics)

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.4", "1.5"] },
    { "id": 1, "tasks": ["1.2", "1.6"] },
    { "id": 2, "tasks": ["1.3", "1.7"] },
    { "id": 3, "tasks": ["1.8"] },
    { "id": 4, "tasks": ["3.1", "3.5"] },
    { "id": 5, "tasks": ["3.2", "3.3", "3.4"] },
    { "id": 6, "tasks": ["3.6"] },
    { "id": 7, "tasks": ["5.1", "5.2", "5.3"] },
    { "id": 8, "tasks": ["5.4", "5.5"] },
    { "id": 9, "tasks": ["5.6"] },
    { "id": 10, "tasks": ["7.1", "7.2"] },
    { "id": 11, "tasks": ["7.3"] },
    { "id": 12, "tasks": ["7.4", "7.5"] }
  ]
}
```
