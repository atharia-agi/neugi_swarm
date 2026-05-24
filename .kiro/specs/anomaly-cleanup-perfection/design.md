# Design Document: Anomaly Cleanup Perfection

## Overview

This design describes the systematic cleanup and hardening of the NEUGI Swarm v2 codebase. The work is organized into 13 parallel workstreams that can be executed independently but share a common verification strategy. The approach prioritizes automated detection (static analysis, AST scanning) over manual inspection, and uses property-based testing to verify invariants hold across the entire codebase post-cleanup.

## Architecture

### Cleanup Pipeline Architecture

The cleanup follows a detect → transform → verify pipeline:

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Static Analysis │ →  │  Transformation   │ →  │  Verification    │
│  (detect issues) │     │  (apply fixes)    │     │  (confirm clean) │
└─────────────────┘     └──────────────────┘     └─────────────────┘
     Ruff, Bandit,           Manual + AST            pytest, mypy,
     vulture, mypy           rewrites               ruff, bandit
```

### Execution Order (Dependency Graph)

```
Phase 1 (Independent):
  ├── Req 1: Dead Code Removal
  ├── Req 2: Deprecated Alias Elimination
  ├── Req 11: Useless File/Folder Removal
  └── Req 13: Import Hygiene

Phase 2 (Depends on Phase 1):
  ├── Req 3: Secret Management Wiring
  ├── Req 4: Disconnected Subsystem Wiring
  └── Req 12: Scheduling Boundary Enforcement

Phase 3 (Independent, high-volume):
  ├── Req 5: Type Hints
  ├── Req 6: Docstrings
  ├── Req 7: Error Handling
  └── Req 8: Ruff/Bandit Compliance

Phase 4 (Depends on Phase 1-3):
  ├── Req 9: WebSocket TLS
  └── Req 10: Test Quality Refactoring
```

---

## Component Designs

### Component 1: Dead Code Removal (Requirement 1)

**Strategy:** Use `vulture` for detection, manual removal with test verification.

**Target files:**
- `security/` — ~7,000 lines of dead infrastructure (shield_reasoning.py, exploit_prevention.py bulk)
- `governance/` — unreachable enforcement code in policy.py, audit.py
- All modules — unused imports (detected by Ruff F401)

**Process:**
1. Run `vulture neugi_swarm_v2/ --min-confidence 80` to generate dead code report
2. Cross-reference with `ruff check --select F401,F841` for unused imports/variables
3. Remove identified dead code module-by-module
4. After each module cleanup, run `python -m pytest tests/ -q --tb=short -p no:anchorpy`
5. If a test breaks, update/remove the test (per Req 1.5)

**Key decisions:**
- Remove entire functions/classes that have zero callers (not just commented code)
- Preserve `__init__.py` exports that form the public API even if not internally called
- Security subsystem: keep `SecretManager`, `ExecutionSandbox`, `CommandValidator`; remove dead `ShieldReasoning` bulk

### Component 2: Deprecated Alias Elimination (Requirement 2)

**Strategy:** Delete files, grep-and-replace references.

**Files to delete:**
- `neugi_swarm_v2/cli/smart_wizard.py`
- `neugi_swarm_v2/cli/wizard.py`

**Replacement mapping:**
```python
# Before
from cli.smart_wizard import SmartWizard
from cli.wizard import SetupWizard

# After (all references point to GeniusWizard)
from cli.genius_wizard import GeniusWizard
```

**Verification:**
```bash
grep -r "SmartWizard\|SetupWizard\|smart_wizard\|cli.wizard" neugi_swarm_v2/
# Expected: zero matches
```

### Component 3: Secret Management Wiring (Requirement 3)

**Current state:** `config.py` already has `_migrate_api_key_to_secrets()` that moves plaintext keys to SecretManager. The migration runs on config load.

**Design changes:**

1. **Config loader enhancement** (`config.py`):
```python
def load_config(...) -> NeugiConfig:
    # After loading JSON, retrieve API key from SecretManager (not config)
    config = NeugiConfig.from_dict(data)
    if config.llm.api_key == "":
        # Try SecretManager
        secrets_db = neugi_dir / "secrets.db"
        if secrets_db.exists():
            manager = SecretManager(db_path=str(secrets_db))
            entry = manager.get_secret("llm_api_key")
            if entry:
                config.llm.api_key = manager._decrypt_value(entry.encrypted_value)
    return config
```

2. **GeniusWizard integration** (`cli/genius_wizard.py`):
```python
def _store_api_key(self, key: str) -> None:
    """Store API key via SecretManager encrypted storage."""
    from security.secret_manager import SecretManager, SecretClass
    secrets_db = Path.home() / ".neugi" / "secrets.db"
    manager = SecretManager(db_path=str(secrets_db))
    manager.add_secret(
        name="llm_api_key",
        value=key,
        secret_class=SecretClass.API_KEY,
        description="LLM provider API key",
    )
```

3. **Failure behavior** — SecretManager already raises exceptions on decrypt failure. Ensure no fallback-to-plaintext paths exist anywhere.

4. **Convenience accessor** — Add `SecretManager.get(name: str) -> str` shorthand:
```python
def get(self, name: str) -> str:
    """Retrieve decrypted secret value. Raises SecretNotFoundError if missing."""
    entry = self.get_secret(name)
    if entry is None:
        raise SecretNotFoundError(f"Secret '{name}' not found")
    return self._decrypt_value(entry.encrypted_value)
```

### Component 4: Disconnected Subsystem Wiring (Requirement 4)

**Current state from code review:**
- `ExecutionSandbox` — already wired in `ToolExecutor` for subprocess-based tools ✓
- `ApprovalGate` — already wired in `ToolExecutor` for COMPLEX/STRATEGIC tools ✓
- `BudgetTracker` — NOT wired into ToolExecutor (needs integration)
- `governance/policy.py` — likely dead code (needs assessment)
- `governance/audit.py` — likely dead code (needs assessment)

**Wiring plan:**

1. **BudgetTracker → ToolExecutor**: Add budget check before tool execution:
```python
# In ToolExecutor.execute(), after approval gate check:
if self.budget_tracker:
    estimated_cost = self._estimate_tool_cost(tool_name, schema.complexity)
    if not self.budget_tracker.can_spend("default", tokens=0, cost=estimated_cost):
        return ExecutionResult(
            tool_name=tool_name,
            success=False,
            error="Budget exceeded for tool execution",
            ...
        )
```

2. **Dead governance code** — If `policy.py` and `audit.py` have no callers after BudgetTracker wiring, remove them (per Req 1).

### Component 5: Type Hints (Requirement 5)

**Strategy:** Systematic annotation of all public functions/methods.

**Conventions (Python 3.10+):**
```python
# Use built-in generics (PEP 604, PEP 585)
def process(items: list[str], config: dict[str, Any] | None = None) -> bool:
    ...

# Use | instead of Union
def get_value(key: str) -> str | None:
    ...
```

**Scope:** All public functions (not prefixed with `_`) across all 29 subsystems. Private functions are best-effort.

**Verification:** `mypy neugi_swarm_v2/ --ignore-missing-imports --no-strict-optional`

### Component 6: Docstrings (Requirement 6)

**Format:** Google-style consistently:
```python
def execute_tool(self, name: str, timeout: float = 30.0) -> ExecutionResult:
    """Execute a registered tool by name.

    Args:
        name: The registered tool name.
        timeout: Maximum execution time in seconds.

    Returns:
        ExecutionResult containing success status and output.

    Raises:
        ToolNotFoundError: If the tool name is not registered.
    """
```

**Scope:** All public classes, functions, and methods. One-line summary required for all; Args/Returns sections for functions with ≥2 parameters or non-None returns.

### Component 7: Error Handling (Requirement 7)

**Patterns to apply:**

1. **I/O wrapping:**
```python
# Before
data = open(path).read()

# After
try:
    with open(path, encoding="utf-8") as f:
        data = f.read()
except FileNotFoundError:
    logger.error("Config file not found: %s", path)
    raise ConfigurationError(f"Config file not found: {path}") from None
except OSError as e:
    logger.error("Failed to read config: %s — %s", path, e)
    raise ConfigurationError(f"Failed to read {path}: {e}") from e
```

2. **Bare except elimination:**
```python
# Before
except:
    pass

# After
except (ValueError, TypeError) as e:
    logger.warning("Unexpected value in %s: %s", context, e)
```

3. **Encoding specification:**
```python
# All open() calls get encoding="utf-8"
open(path, "r", encoding="utf-8")
open(path, "w", encoding="utf-8")
Path(path).read_text(encoding="utf-8")
```

### Component 8: Ruff and Bandit Compliance (Requirement 8)

**Ruff configuration** (in `pyproject.toml`):
```toml
[tool.ruff]
target-version = "py310"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "S", "UP"]
ignore = ["S101"]  # assert in tests is fine
```

**Bandit fixes:**
- `eval()` → ensure `{"__builtins__": {}}` scope
- `subprocess` → ensure `shell=False` with list args
- `assert` in production code → replace with explicit checks
- Hardcoded passwords → route through SecretManager

**Verification:**
```bash
ruff check neugi_swarm_v2/ --fix
bandit -r neugi_swarm_v2/ -c pyproject.toml
```

### Component 9: WebSocket TLS (Requirement 9)

**Current state:** `dashboard/server.py` uses `http.server.HTTPServer` with no TLS. `dashboard/websocket.py` handles raw sockets.

**Design:**

1. **DashboardConfig extension:**
```python
@dataclass
class DashboardConfig:
    host: str = "127.0.0.1"
    port: int = 17901
    tls_enabled: bool = False
    tls_cert_path: str = ""
    tls_key_path: str = ""
    # ... existing fields
```

2. **TLS wrapping in DashboardServer.start():**
```python
def start(self, blocking: bool = False) -> None:
    server = HTTPServer((self.config.host, self.config.port), handler_class)
    
    if self.config.tls_enabled:
        if not self.config.tls_cert_path or not self.config.tls_key_path:
            raise DashboardTLSError("TLS enabled but cert_path or key_path not configured")
        
        cert_path = Path(self.config.tls_cert_path)
        key_path = Path(self.config.tls_key_path)
        
        if not cert_path.exists():
            raise DashboardTLSError(f"TLS certificate not found: {cert_path}")
        if not key_path.exists():
            raise DashboardTLSError(f"TLS key not found: {key_path}")
        
        import ssl
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(str(cert_path), str(key_path))
        server.socket = ctx.wrap_socket(server.socket, server_side=True)
    
    self._server = server
    # ... start serving
```

3. **Config.json extension:**
```json
{
  "dashboard": {
    "enabled": true,
    "port": 17901,
    "tls_enabled": false,
    "tls_cert_path": "",
    "tls_key_path": ""
  }
}
```

### Component 10: Test Quality Refactoring (Requirement 10)

**Anti-patterns to eliminate:**

1. **hasattr-only tests:**
```python
# Before
def test_memory_system():
    ms = MemorySystem(":memory:")
    assert hasattr(ms, "store")
    assert hasattr(ms, "recall")

# After
def test_memory_system_store_and_recall():
    ms = MemorySystem(":memory:")
    ms.store("test_key", "test_value", scope="core")
    result = ms.recall("test_key")
    assert result is not None
    assert result.content == "test_value"
```

2. **Trivial mock tests:**
```python
# Before
def test_tool_executor(mocker):
    mock_registry = mocker.Mock()
    mock_registry.get_tool.return_value = mocker.Mock()
    executor = ToolExecutor(registry=mock_registry)
    assert executor is not None

# After
def test_tool_executor_executes_registered_tool():
    registry = ToolRegistry()
    registry.register("echo", lambda text: text, ToolSchema(name="echo"))
    executor = ToolExecutor(registry=registry)
    result = executor.execute("echo", text="hello")
    assert result.success is True
    assert result.result == "hello"
```

**Constraint:** Test count must remain ≥ 379 after refactoring.

### Component 11: Useless File/Folder Removal (Requirement 11)

**Deletions:**
- `evals/` (root-level, empty)
- `neugi_swarm_v2/.ruff_cache/`
- `neugi_swarm_v2/.mypy_cache/`
- `neugi_swarm_v2/dist/`
- `neugi_swarm_v2/neugi_swarm_v2.egg-info/`
- Any empty directories within neugi_swarm_v2/

**Preserve:**
- `audit/` — historical documentation
- `neugi_swarm_v2/evals/` — benchmark harness (has code)

**.gitignore additions:**
```gitignore
__pycache__/
*.egg-info/
dist/
.ruff_cache/
.mypy_cache/
.pytest_cache/
```

### Component 12: Scheduling Boundary Enforcement (Requirement 12)

**Current state:** CronScheduler and HeartbeatEngine are well-implemented with clear SQLite-backed persistence. They share no decision logic with AutonomousLoop.

**Changes:**

1. **Docstring enforcement** — Add boundary docstrings:
```python
class CronScheduler:
    """Deterministic task scheduler for time-based recurring jobs.

    BOUNDARY: This scheduler handles ONLY deterministic, time-triggered tasks
    (backups, cleanup, log rotation). It does NOT make AI-driven decisions.
    For pro-active AI behavior, use AutonomousLoop.

    Relationship to AutonomousLoop:
        - CronScheduler: "run X every hour" (deterministic)
        - AutonomousLoop: "maybe do Y if conditions suggest it" (AI-driven)

    Safe to run concurrently with AutonomousLoop and HeartbeatEngine
    (SQLite WAL mode provides serialization).
    """
```

2. **Verify no overlap** — Audit registered jobs/tasks to ensure no AI-driven callbacks are registered in CronScheduler or HeartbeatEngine.

3. **Concurrency safety** — Already handled by SQLite WAL mode. Add explicit test for concurrent access.

### Component 13: Import Hygiene (Requirement 13)

**Strategy:**

1. **Detect relative imports:**
```bash
grep -rn "from \." neugi_swarm_v2/ --include="*.py"
# Convert all to absolute imports
```

2. **Detect circular imports:**
```python
# Script to attempt importing every module independently
import importlib
import pkgutil

for importer, modname, ispkg in pkgutil.walk_packages(["neugi_swarm_v2"]):
    try:
        importlib.import_module(modname)
    except ImportError as e:
        print(f"CIRCULAR: {modname} — {e}")
```

3. **Break cycles** — Extract shared types into `types.py` or use `TYPE_CHECKING` guard:
```python
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from memory.memory_core import MemorySystem
```

---

## Data Models

### Configuration Extension (config.json)

```json
{
  "dashboard": {
    "enabled": true,
    "port": 17901,
    "tls_enabled": false,
    "tls_cert_path": "",
    "tls_key_path": ""
  }
}
```

### SecretManager Convenience Interface

```python
class SecretNotFoundError(Exception):
    """Raised when a requested secret does not exist."""
    pass

class SecretDecryptionError(Exception):
    """Raised when a secret cannot be decrypted."""
    pass
```

---

## Components and Interfaces

### SecretManager.get() — New Convenience Method

```python
def get(self, name: str) -> str:
    """Retrieve a decrypted secret value by name.

    Args:
        name: The secret identifier.

    Returns:
        The decrypted plaintext value.

    Raises:
        SecretNotFoundError: If no secret with this name exists.
        SecretDecryptionError: If decryption fails.
    """
```

### DashboardServer TLS Configuration

```python
@dataclass
class DashboardConfig:
    host: str = "127.0.0.1"
    port: int = 17901
    auth_enabled: bool = True
    tls_enabled: bool = False
    tls_cert_path: str = ""
    tls_key_path: str = ""

class DashboardTLSError(Exception):
    """Raised when TLS configuration is invalid or certs are missing."""
    pass
```

### BudgetTracker → ToolExecutor Integration

```python
class ToolExecutor:
    def __init__(
        self,
        registry: ToolRegistry,
        ...,
        budget_tracker: BudgetTracker | None = None,
    ):
        self.budget_tracker = budget_tracker
```

---

## Error Handling

All error handling follows these principles:

1. **Specific exceptions** — Never bare `except:` or `except Exception:`
2. **Contextual logging** — Every caught exception logs operation name + relevant params
3. **Fail-loud for security** — SecretManager and TLS never fall back silently
4. **Custom exceptions** — Each subsystem defines its own exception hierarchy
5. **Encoding always specified** — Every `open()` call includes `encoding="utf-8"`

### Exception Hierarchy

```python
# security/
class SecretNotFoundError(Exception): ...
class SecretDecryptionError(Exception): ...

# dashboard/
class DashboardTLSError(Exception): ...

# governance/
class BudgetExceededError(Exception): ...

# config
class ConfigurationError(Exception): ...
```

## Testing Strategy

### Automated Checks (CI Pipeline)

```bash
# Phase 1: Static analysis
ruff check neugi_swarm_v2/
bandit -r neugi_swarm_v2/ -c pyproject.toml
mypy neugi_swarm_v2/ --ignore-missing-imports

# Phase 2: Tests
python -m pytest tests/ -q --tb=short -p no:anchorpy

# Phase 3: Import health
python -c "import importlib, pkgutil; [importlib.import_module(m.name) for m in pkgutil.walk_packages(['neugi_swarm_v2'])]"

# Phase 4: Dead code scan
vulture neugi_swarm_v2/ --min-confidence 80
```

### Test Count Invariant

Before: 379 collected (377 pass, 2 skip)
After: ≥ 379 collected, all non-optional pass

### Property-Based Tests

Properties 1-18 below are implemented as property-based tests that scan the codebase programmatically. Each test iterates over all relevant files/modules and asserts the invariant holds universally.

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: No Unused Imports

*For any* Python module in neugi_swarm_v2, running the Ruff F401 (unused import) check SHALL produce zero violations.

**Validates: Requirements 1.4**

### Property 2: No Deprecated Wizard References

*For any* Python file in neugi_swarm_v2, the file SHALL NOT contain any import of, or reference to, `SmartWizard`, `SetupWizard`, `smart_wizard`, or `cli.wizard` as a module path.

**Validates: Requirements 2.3, 2.5**

### Property 3: API Key Access Through SecretManager

*For any* code path that retrieves an API key at runtime, the retrieval SHALL go through `SecretManager.get()` or `SecretManager.get_secret()` rather than reading a plaintext string from config.json directly.

**Validates: Requirements 3.1, 3.4**

### Property 4: SecretManager Fails Loud

*For any* secret name that does not exist or cannot be decrypted, `SecretManager.get()` SHALL raise a descriptive exception rather than returning None, an empty string, or falling back to plaintext.

**Validates: Requirements 3.5**

### Property 5: Public Callables Have Type Annotations

*For any* public function or method (not prefixed with `_`) in neugi_swarm_v2, all parameters (except `self`/`cls`) SHALL have type annotations and the return type SHALL be annotated.

**Validates: Requirements 5.1, 5.2**

### Property 6: Public Symbols Have Docstrings

*For any* public class, function, or method (not prefixed with `_`) in neugi_swarm_v2, the `__doc__` attribute SHALL not be None or empty.

**Validates: Requirements 6.1, 6.2**

### Property 7: No Bare Except Clauses

*For any* Python file in neugi_swarm_v2, AST parsing SHALL find zero bare `except:` clauses and zero `except Exception:` clauses that do not re-raise or handle with specific logic.

**Validates: Requirements 7.3**

### Property 8: All open() Calls Specify Encoding

*For any* call to the built-in `open()` function in neugi_swarm_v2 source files (excluding binary mode opens), the `encoding` parameter SHALL be explicitly set to `"utf-8"`.

**Validates: Requirements 7.4**

### Property 9: All eval() Uses Restricted Builtins

*For any* call to `eval()` in neugi_swarm_v2, the globals argument SHALL contain `{"__builtins__": {}}` to prevent access to dangerous built-in functions.

**Validates: Requirements 8.3**

### Property 10: No Subprocess shell=True

*For any* call to `subprocess.run()`, `subprocess.Popen()`, or `subprocess.call()` in neugi_swarm_v2, the `shell` parameter SHALL NOT be set to `True`.

**Validates: Requirements 8.4**

### Property 11: TLS Rejects Unencrypted Connections

*For any* connection attempt to the dashboard WebSocket server when TLS is enabled, a plain (non-TLS) connection SHALL be rejected and not served.

**Validates: Requirements 9.2**

### Property 12: Missing TLS Certs Raise Descriptive Error

*For any* invalid or missing certificate/key file path in the dashboard TLS configuration, `DashboardServer.start()` SHALL raise a `DashboardTLSError` with a message identifying the missing file, rather than falling back to unencrypted mode.

**Validates: Requirements 9.4**

### Property 13: Every Test Has Behavioral Assertions

*For any* test function in the test suite (functions prefixed with `test_`), the function body SHALL contain at least one `assert` statement, `pytest.raises` context, or equivalent behavioral verification — not solely `hasattr()` checks or import statements.

**Validates: Requirements 10.1, 10.5**

### Property 14: No Empty Purposeless Directories

*For any* directory within neugi_swarm_v2/ (excluding `__pycache__`), the directory SHALL contain at least one `.py` file or a meaningful non-Python resource file.

**Validates: Requirements 11.2**

### Property 15: Build Artifacts in .gitignore

*For any* known build artifact pattern (`__pycache__/`, `*.egg-info/`, `dist/`, `.ruff_cache/`, `.mypy_cache/`, `.pytest_cache/`), the pattern SHALL appear in the project's `.gitignore` file.

**Validates: Requirements 11.4**

### Property 16: Concurrent Schedulers Don't Deadlock

*For any* concurrent execution of AutonomousLoop.tick(), CronScheduler.tick(), and HeartbeatEngine.tick() against the same SQLite database, all three operations SHALL complete within 10 seconds without deadlock.

**Validates: Requirements 12.5**

### Property 17: No Relative Imports

*For any* Python file in neugi_swarm_v2, no `from .` or `from ..` import statements SHALL exist — all imports SHALL be absolute.

**Validates: Requirements 13.1**

### Property 18: All Modules Importable Independently

*For any* Python module in neugi_swarm_v2, calling `importlib.import_module(module_name)` SHALL succeed without raising `ImportError` from circular references.

**Validates: Requirements 13.3**
