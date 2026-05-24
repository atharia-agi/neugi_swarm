# Requirements Document

## Introduction

Comprehensive cleanup and hardening of the NEUGI Swarm v2 codebase across all 29 subsystems simultaneously. This effort removes dead code, wires disconnected subsystems, hardens code quality (error handling, type hints, docstrings), refactors weak tests to real assertions, removes deprecated aliases, wires SecretManager for credential handling, and deletes useless files/folders — all while prioritizing architectural cleanliness over backward compatibility.

## Glossary

- **Cleanup_Engine**: The collective refactoring process applied across all 29 subsystems of the NEUGI Swarm v2 package
- **Dead_Code**: Functions, classes, imports, or modules that are defined but never called, imported, or reachable from any entry point
- **Unwired_Subsystem**: A subsystem whose classes or functions exist in source but are not instantiated or invoked by any orchestrator, entry point, or integration path
- **SecretManager**: The existing credential management subsystem in security/ that provides encrypted secret storage
- **GeniusWizard**: The canonical zero-dependency setup wizard at cli/genius_wizard.py
- **Deprecated_Alias**: SmartWizard (cli/smart_wizard.py) and SetupWizard (cli/wizard.py) which exist only for backward compatibility
- **AutonomousLoop**: The pro-active idle behavior engine at autonomous/loop_engine.py
- **CronScheduler**: The deterministic task scheduler at gateway/cron.py
- **HeartbeatEngine**: The health-check watchdog at gateway/heartbeat.py
- **Weak_Test**: A test that uses hasattr() checks, trivial mock returns, or lacks real behavioral assertions
- **Production_Grade**: Code that includes type hints, docstrings, proper error handling, input validation, and encoding specifications
- **Ruff**: The Python linter/formatter used for code quality enforcement
- **Bandit**: The Python security linter for detecting common security issues
- **neugi_swarm_v2**: The main Python package directory containing all 29 subsystems

## Requirements

### Requirement 1: Dead Code Removal

**User Story:** As a developer, I want all unreachable code removed from the codebase, so that the project is leaner, easier to navigate, and free of misleading artifacts.

#### Acceptance Criteria

1. WHEN the Cleanup_Engine scans a module, THE Cleanup_Engine SHALL identify and remove all functions, classes, and imports that have zero callers across the entire neugi_swarm_v2 package.
2. WHEN the Cleanup_Engine identifies dead code in the security/ subsystem, THE Cleanup_Engine SHALL remove the approximately 7,000 lines of dead infrastructure code identified in prior audits.
3. WHEN the Cleanup_Engine identifies dead code in the governance/ subsystem, THE Cleanup_Engine SHALL remove all unreachable governance enforcement code that is defined but never invoked.
4. WHEN a module contains unused imports, THE Cleanup_Engine SHALL remove those imports without affecting any reachable code paths.
5. IF removal of a code block would break an existing test, THEN THE Cleanup_Engine SHALL update or remove the test that references the dead code rather than preserving the dead code.

### Requirement 2: Deprecated Alias Elimination

**User Story:** As a developer, I want deprecated wizard aliases removed, so that there is a single canonical path for setup logic and no confusion about which wizard to use.

#### Acceptance Criteria

1. THE Cleanup_Engine SHALL delete cli/smart_wizard.py (the SmartWizard deprecated alias).
2. THE Cleanup_Engine SHALL delete cli/wizard.py (the SetupWizard deprecated alias).
3. WHEN cli/smart_wizard.py or cli/wizard.py are deleted, THE Cleanup_Engine SHALL remove all import statements referencing SmartWizard or SetupWizard from every module in neugi_swarm_v2.
4. THE Cleanup_Engine SHALL verify that GeniusWizard remains the sole setup wizard entry point after alias removal.
5. IF any module references SmartWizard or SetupWizard by class name, THEN THE Cleanup_Engine SHALL replace that reference with GeniusWizard.

### Requirement 3: Secret Management Wiring

**User Story:** As a developer, I want all plaintext API keys routed through SecretManager, so that credentials are never stored or transmitted in cleartext.

#### Acceptance Criteria

1. WHEN the configuration system loads an API key, THE configuration system SHALL retrieve the key value through SecretManager rather than reading plaintext from config.json.
2. WHEN GeniusWizard collects an API key during setup, THE GeniusWizard SHALL store the key via SecretManager encrypted storage.
3. THE SecretManager SHALL provide a retrieval interface that all subsystems use to access credentials at runtime.
4. WHEN a module accesses an API key, THE module SHALL call SecretManager.get() instead of reading a plaintext string from configuration.
5. IF SecretManager is unavailable or fails to decrypt, THEN THE SecretManager SHALL raise a descriptive error rather than falling back to plaintext.

### Requirement 4: Disconnected Subsystem Wiring

**User Story:** As a developer, I want all subsystems that exist in source to be properly integrated into the orchestration layer, so that no code exists without a purpose.

#### Acceptance Criteria

1. WHEN the Cleanup_Engine identifies a subsystem class that is instantiated but never invoked by any orchestrator, THE Cleanup_Engine SHALL wire that subsystem into the appropriate integration point.
2. WHEN ExecutionSandbox is instantiated, THE security subsystem SHALL invoke ExecutionSandbox for all code execution paths that require sandboxing.
3. WHEN the governance subsystem defines approval or budget enforcement, THE governance subsystem SHALL be invoked by the tool execution pipeline at the appropriate decision points.
4. IF a subsystem cannot be meaningfully wired into any integration point, THEN THE Cleanup_Engine SHALL remove that subsystem entirely as dead code.

### Requirement 5: Code Quality Hardening — Type Hints

**User Story:** As a developer, I want all public functions and methods annotated with type hints, so that static analysis tools can catch errors and the code is self-documenting.

#### Acceptance Criteria

1. THE Cleanup_Engine SHALL add type annotations to all public function signatures (parameters and return types) across all 29 subsystems.
2. THE Cleanup_Engine SHALL add type annotations to all public method signatures (parameters and return types) across all 29 subsystems.
3. WHEN a function accepts or returns complex types, THE Cleanup_Engine SHALL use typing module constructs (Optional, Union, Dict, List, Tuple) appropriate for Python 3.10+.
4. THE Cleanup_Engine SHALL ensure all type annotations pass mypy in basic mode without errors for annotated functions.

### Requirement 6: Code Quality Hardening — Docstrings

**User Story:** As a developer, I want all public classes and functions to have docstrings, so that the codebase is comprehensible without reading implementation details.

#### Acceptance Criteria

1. THE Cleanup_Engine SHALL add a docstring to every public class that lacks one across all 29 subsystems.
2. THE Cleanup_Engine SHALL add a docstring to every public function and method that lacks one across all 29 subsystems.
3. WHEN a docstring is added, THE Cleanup_Engine SHALL include a one-line summary, parameter descriptions for functions with two or more parameters, and a return description for non-None returns.
4. THE Cleanup_Engine SHALL use Google-style docstring format consistently across the entire codebase.

### Requirement 7: Code Quality Hardening — Error Handling

**User Story:** As a developer, I want robust error handling throughout the codebase, so that failures are caught, logged, and reported rather than causing silent corruption or crashes.

#### Acceptance Criteria

1. WHEN a function performs I/O (file, network, database), THE function SHALL wrap the operation in a try/except block that catches specific exception types.
2. WHEN an exception is caught, THE handler SHALL log the error with sufficient context (operation name, relevant parameters) using the structured logging system.
3. THE Cleanup_Engine SHALL replace all bare `except:` and `except Exception:` clauses with specific exception types appropriate to the operation.
4. WHEN a function uses `open()`, THE function SHALL specify `encoding="utf-8"` as required by project conventions.
5. IF an error is unrecoverable, THEN THE handler SHALL raise a descriptive custom exception rather than silently swallowing the error.

### Requirement 8: Code Quality Hardening — Ruff and Bandit Compliance

**User Story:** As a developer, I want the entire codebase to pass Ruff and Bandit checks, so that code style is consistent and common security anti-patterns are eliminated.

#### Acceptance Criteria

1. THE Cleanup_Engine SHALL resolve all Ruff linting violations across all modules in neugi_swarm_v2.
2. THE Cleanup_Engine SHALL resolve all Bandit security findings across all modules in neugi_swarm_v2.
3. WHEN Bandit identifies a use of `eval()`, THE Cleanup_Engine SHALL ensure the eval uses `{"__builtins__": {}}` scope as required by project conventions.
4. WHEN Bandit identifies a use of `subprocess` with `shell=True`, THE Cleanup_Engine SHALL refactor to use `shell=False` with argument lists.
5. WHEN Ruff identifies unused variables or imports, THE Cleanup_Engine SHALL remove them.

### Requirement 9: Internal WebSocket TLS

**User Story:** As a developer, I want internal WebSocket connections to use TLS, so that dashboard and inter-subsystem communication is encrypted.

#### Acceptance Criteria

1. WHEN the dashboard subsystem creates a WebSocket server, THE dashboard subsystem SHALL configure TLS with a certificate and key.
2. WHEN a client connects to the internal WebSocket, THE dashboard subsystem SHALL require TLS and reject unencrypted connections.
3. THE dashboard subsystem SHALL support self-signed certificates for local development with a configuration option to specify certificate paths.
4. IF TLS certificate files are missing or invalid, THEN THE dashboard subsystem SHALL raise a descriptive error at startup rather than falling back to unencrypted communication.

### Requirement 10: Test Quality Refactoring

**User Story:** As a developer, I want weak tests upgraded to real behavioral assertions, so that the test suite provides genuine confidence in correctness.

#### Acceptance Criteria

1. WHEN a test uses `hasattr()` as its primary assertion, THE Cleanup_Engine SHALL replace it with a behavioral assertion that invokes the method and verifies the output.
2. WHEN a test uses mocks that return trivial values without verifying call arguments or behavior, THE Cleanup_Engine SHALL add assertions on mock call arguments, call count, or replace the mock with a real invocation.
3. THE Cleanup_Engine SHALL preserve all existing test coverage (test count shall remain at 379 or higher after refactoring).
4. WHEN a test is refactored, THE refactored test SHALL pass when run with `python -m pytest tests/ -q --tb=short -p no:anchorpy`.
5. THE Cleanup_Engine SHALL ensure no test relies solely on import success as proof of correctness — each test SHALL assert at least one behavioral property.

### Requirement 11: Useless File and Folder Removal

**User Story:** As a developer, I want empty and purposeless directories removed, so that the repository structure reflects only meaningful content.

#### Acceptance Criteria

1. THE Cleanup_Engine SHALL delete the root-level evals/ directory (confirmed empty except for evals/results/ with no content).
2. THE Cleanup_Engine SHALL delete any empty directories within neugi_swarm_v2/ that contain no source files and serve no structural purpose.
3. THE Cleanup_Engine SHALL retain the audit/ directory and all its contents as historical documentation.
4. WHEN a file is identified as a build artifact or cache (dist/, .egg-info/, __pycache__/), THE Cleanup_Engine SHALL ensure it is listed in .gitignore and not tracked in version control.
5. THE Cleanup_Engine SHALL delete neugi_swarm_v2/.ruff_cache/ and neugi_swarm_v2/.mypy_cache/ directories as they are regenerable tool caches.

### Requirement 12: Scheduling Subsystem Boundary Enforcement

**User Story:** As a developer, I want clear boundaries between AutonomousLoop, CronScheduler, and HeartbeatEngine, so that scheduling responsibilities do not overlap or conflict.

#### Acceptance Criteria

1. THE Cleanup_Engine SHALL add docstrings to CronScheduler and HeartbeatEngine that explicitly state their bounded responsibility and relationship to AutonomousLoop.
2. WHEN CronScheduler or HeartbeatEngine contain logic that duplicates AutonomousLoop decision-making, THE Cleanup_Engine SHALL remove the duplicated logic.
3. THE Cleanup_Engine SHALL ensure CronScheduler is used exclusively for deterministic scheduled tasks (backups, cleanup) and not for AI-driven decisions.
4. THE Cleanup_Engine SHALL ensure HeartbeatEngine is used exclusively for health-check watchdog tasks and not for pro-active behavior.
5. WHEN AutonomousLoop, CronScheduler, and HeartbeatEngine run concurrently, THE scheduling subsystems SHALL operate without deadlocks or resource contention on shared SQLite backends.

### Requirement 13: Import Hygiene and Circular Dependency Prevention

**User Story:** As a developer, I want clean import graphs with no circular dependencies, so that module loading is predictable and refactoring is safe.

#### Acceptance Criteria

1. THE Cleanup_Engine SHALL use absolute imports exclusively as required by project conventions (no relative imports).
2. WHEN the Cleanup_Engine identifies a circular import between two modules, THE Cleanup_Engine SHALL break the cycle by extracting shared types into a separate module or using deferred imports.
3. THE Cleanup_Engine SHALL ensure all modules in neugi_swarm_v2 can be imported independently without triggering ImportError from circular references.
4. WHEN an import is added or modified, THE Cleanup_Engine SHALL verify the import resolves correctly when running from the package root with `python -m`.
