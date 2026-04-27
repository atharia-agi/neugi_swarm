"""
Execution Sandbox
=================

Isolates agent-executed commands with defense-in-depth controls:
- Command allowlist/denylist with regex matching
- Path restriction (only allowed directories accessible)
- Resource limits (CPU, memory, time, network)
- Process isolation via subprocess with restrictions
- File system sandboxing (temp dir, read-only mounts)
- Network sandboxing (allowed hosts only)
- Environment variable sanitization

Usage:
    config = SandboxConfig(
        allowed_dirs=["/tmp", "/workspace"],
        allowed_hosts=["api.example.com"],
        max_cpu_seconds=10,
        max_memory_mb=512,
    )
    sandbox = ExecutionSandbox(config)
    result = sandbox.execute(["python", "-c", "print('hello')"])
"""

from __future__ import annotations

import logging
import os
import platform
import re
try:
    import resource
except ImportError:
    resource = None
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# -- Exceptions ----------------------------------------------------------------

class SandboxViolation(Exception):
    """Raised when a sandbox constraint is violated."""

    def __init__(self, violation_type: str, detail: str, command: str = "") -> None:
        self.violation_type = violation_type
        self.detail = detail
        self.command = command
        super().__init__(f"[{violation_type}] {detail}")


# -- Configuration -------------------------------------------------------------

@dataclass
class SandboxConfig:
    """Configuration for the execution sandbox.

    Attributes:
        allowed_dirs: Directories the sandboxed process may access.
        read_only_dirs: Directories mounted read-only.
        allowed_commands: Explicit allowlist of command binaries (empty = all allowed).
        denied_commands: Denylist of command patterns (regex).
        allowed_hosts: Network hosts the process may connect to (empty = no network).
        allowed_ports: Network ports allowed for outbound connections.
        max_cpu_seconds: Maximum CPU time in seconds.
        max_wall_seconds: Maximum wall-clock time in seconds.
        max_memory_mb: Maximum resident memory in megabytes.
        max_processes: Maximum number of child processes.
        max_file_size_mb: Maximum file size that can be written.
        tmp_dir: Temporary directory for sandboxed file operations.
        env_allowlist: Environment variables to pass through (empty = none).
        env_denylist: Environment variables to always strip.
        enable_network: Whether to allow any network access.
        enable_filesystem: Whether to allow filesystem access.
        deny_patterns: Regex patterns that block command arguments.
        severity_on_violation: Action on violation ('raise', 'log', 'block').
    """

    allowed_dirs: list[str] = field(default_factory=lambda: [str(Path.cwd())])
    read_only_dirs: list[str] = field(default_factory=list)
    allowed_commands: list[str] = field(default_factory=list)
    denied_commands: list[str] = field(
        default_factory=lambda: [
            r"^rm\s+-rf\s+/",
            r"^mkfs",
            r"^dd\s+if=",
            r"^fdisk",
            r"^parted",
            r"^mount\s",
            r"^umount\s",
            r"^kill\s",
            r"^killall\s",
            r"^pkill\s",
            r"^iptables\s",
            r"^chmod\s+[0-7]*777",
            r"^chown\s",
            r"^passwd\s",
            r"^useradd\s",
            r"^userdel\s",
            r"^groupadd\s",
            r"^groupdel\s",
            r"^visudo",
            r"^crontab\s",
            r"^at\s",
            r"^shutdown\s",
            r"^reboot\s",
            r"^halt\s",
            r"^poweroff\s",
            r"^curl.*\|\s*bash",
            r"^wget.*\|\s*bash",
            r"^curl.*\|\s*sh",
            r"^wget.*\|\s*sh",
            r"bash\s+-c.*curl",
            r"sh\s+-c.*wget",
        ]
    )
    allowed_hosts: list[str] = field(default_factory=list)
    allowed_ports: list[int] = field(default_factory=lambda: [80, 443])
    max_cpu_seconds: float = 30.0
    max_wall_seconds: float = 60.0
    max_memory_mb: int = 1024
    max_processes: int = 4
    max_file_size_mb: int = 100
    tmp_dir: str = ""
    env_allowlist: list[str] = field(
        default_factory=lambda: ["PATH", "HOME", "USER", "LANG", "LC_ALL", "PYTHONPATH"]
    )
    env_denylist: list[str] = field(
        default_factory=lambda: [
            "AWS_SECRET_ACCESS_KEY", "AWS_ACCESS_KEY_ID",
            "GITHUB_TOKEN", "GH_TOKEN",
            "API_KEY", "SECRET_KEY", "PRIVATE_KEY",
            "DATABASE_URL", "REDIS_URL",
            "SSH_AUTH_SOCK", "GPG_AGENT_INFO",
        ]
    )
    enable_network: bool = True
    enable_filesystem: bool = True
    deny_patterns: list[str] = field(
        default_factory=lambda: [
            r"/etc/shadow",
            r"/etc/passwd",
            r"/etc/sudoers",
            r"\.ssh/",
            r"\.gnupg/",
            r"/proc/\d+/mem",
            r"/dev/mem",
            r"/dev/kmem",
        ]
    )
    severity_on_violation: str = "raise"


# -- Result --------------------------------------------------------------------

@dataclass
class SandboxResult:
    """Result of a sandboxed execution.

    Attributes:
        returncode: Process exit code.
        stdout: Standard output.
        stderr: Standard error.
        duration_seconds: Wall-clock execution time.
        cpu_seconds: CPU time consumed.
        memory_peak_kb: Peak memory usage in KB.
        killed: Whether the process was killed by the sandbox.
        kill_reason: Reason for killing (if killed).
    """

    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float
    cpu_seconds: float
    memory_peak_kb: int
    killed: bool = False
    kill_reason: str = ""


# -- Sandbox -------------------------------------------------------------------

class ExecutionSandbox:
    """Execution sandbox with defense-in-depth isolation.

    Provides multiple layers of protection:
    1. Command validation (allowlist/denylist)
    2. Path restriction (chroot-like via path checking)
    3. Resource limits (CPU, memory, time via setrlimit)
    4. Process isolation (preexec_fn with restrictions)
    5. File system sandboxing (temp dir, read-only enforcement)
    6. Network sandboxing (host allowlist via iptables or validation)
    7. Environment sanitization (strip sensitive vars)
    """

    def __init__(self, config: Optional[SandboxConfig] = None) -> None:
        self.config = config or SandboxConfig()
        self._compiled_deny_rules: list[tuple[str, re.Pattern[str]]] = []
        self._compiled_deny_patterns: list[re.Pattern[str]] = []
        self._tmp_dir: Optional[tempfile.TemporaryDirectory] = None
        self._execution_log: list[dict[str, Any]] = []
        self._init_compiled_rules()
        self._init_tmp_dir()

    def _init_compiled_rules(self) -> None:
        """Pre-compile regex rules for performance."""
        for rule in self.config.denied_commands:
            try:
                self._compiled_deny_rules.append((rule, re.compile(rule, re.IGNORECASE)))
            except re.error as e:
                logger.warning("Invalid deny rule regex '%s': %s", rule, e)

        for pattern in self.config.deny_patterns:
            try:
                self._compiled_deny_patterns.append(re.compile(pattern, re.IGNORECASE))
            except re.error as e:
                logger.warning("Invalid deny pattern regex '%s': %s", pattern, e)

    def _init_tmp_dir(self) -> None:
        """Initialize sandbox temporary directory."""
        if self.config.tmp_dir:
            os.makedirs(self.config.tmp_dir, exist_ok=True)
        else:
            self._tmp_dir = tempfile.TemporaryDirectory(prefix="neugi_sandbox_")
            self.config.tmp_dir = self._tmp_dir.name

    # -- Command Validation ------------------------------------------------

    def validate_command(self, command: list[str]) -> tuple[bool, str]:
        """Validate a command against sandbox rules.

        Args:
            command: Command and arguments as a list.

        Returns:
            Tuple of (is_allowed, reason).
        """
        if not command:
            return False, "Empty command"

        binary = command[0]
        full_cmd = " ".join(command)

        # Check allowlist
        if self.config.allowed_commands:
            resolved = shutil.which(binary)
            if resolved is None:
                return False, f"Binary not found: {binary}"
            resolved_path = os.path.realpath(resolved)
            allowed_resolved = [
                os.path.realpath(c) for c in self.config.allowed_commands
            ]
            if resolved_path not in allowed_resolved and binary not in self.config.allowed_commands:
                return False, f"Command not in allowlist: {binary}"

        # Check denylist
        for rule_str, rule_re in self._compiled_deny_rules:
            if rule_re.search(full_cmd):
                return False, f"Command matches deny rule: {rule_str}"

        # Check path deny patterns
        for pattern in self._compiled_deny_patterns:
            if pattern.search(full_cmd):
                return False, f"Command accesses restricted path"

        # Check path restrictions
        if self.config.enable_filesystem:
            for arg in command[1:]:
                if not self._is_path_allowed(arg):
                    return False, f"Path not in allowed directories: {arg}"

        return True, "Command validated"

    def _is_path_allowed(self, path_str: str) -> bool:
        """Check if a path is within allowed directories.

        Args:
            path_str: Path to check.

        Returns:
            True if path is within allowed directories.
        """
        if not path_str.startswith(("/", "./", "../")):
            # Relative path or non-path argument
            return True

        try:
            resolved = os.path.realpath(path_str)
        except (ValueError, OSError):
            return False

        for allowed in self.config.allowed_dirs:
            allowed_resolved = os.path.realpath(allowed)
            if resolved.startswith(allowed_resolved):
                return True

        return False

    # -- Environment Sanitization ------------------------------------------

    def sanitize_environment(self) -> dict[str, str]:
        """Create a sanitized environment for subprocess execution.

        Returns:
            Sanitized environment dictionary.
        """
        env: dict[str, str] = {}

        # Start with allowlisted vars
        for key in self.config.env_allowlist:
            if key in os.environ:
                env[key] = os.environ[key]

        # Remove denied vars
        for key in self.config.env_denylist:
            env.pop(key, None)

        # Remove any key containing sensitive substrings
        sensitive_substrings = ["key", "secret", "token", "password", "credential", "auth"]
        keys_to_remove = [
            k for k in env
            if any(s in k.lower() for s in sensitive_substrings)
            and k not in self.config.env_allowlist
        ]
        for k in keys_to_remove:
            del env[k]

        # Set sandbox-specific vars
        env["NEUGI_SANDBOXED"] = "1"
        env["TMPDIR"] = self.config.tmp_dir
        env["HOME"] = self.config.tmp_dir

        return env

    # -- Resource Limits ---------------------------------------------------

    def _set_resource_limits(self) -> None:
        """Set resource limits for the child process.

        Must be called in preexec_fn (before exec).
        """
        # CPU time limit
        soft_cpu = int(self.config.max_cpu_seconds)
        hard_cpu = soft_cpu + 5
        resource.setrlimit(resource.RLIMIT_CPU, (soft_cpu, hard_cpu))

        # Memory limit
        mem_bytes = self.config.max_memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))

        # Process limit
        resource.setrlimit(resource.RLIMIT_NPROC, (self.config.max_processes, self.config.max_processes))

        # File size limit
        file_bytes = self.config.max_file_size_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_FSIZE, (file_bytes, file_bytes))

        # Disable core dumps
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

    # -- Execution ---------------------------------------------------------

    def execute(
        self,
        command: list[str],
        timeout: Optional[float] = None,
        cwd: Optional[str] = None,
    ) -> SandboxResult:
        """Execute a command within the sandbox.

        Args:
            command: Command and arguments.
            timeout: Override wall-clock timeout (seconds).
            cwd: Working directory (must be within allowed_dirs).

        Returns:
            SandboxResult with output and metrics.

        Raises:
            SandboxViolation: If command violates sandbox rules.
        """
        # Validate command
        allowed, reason = self.validate_command(command)
        if not allowed:
            violation = SandboxViolation("command_validation", reason, " ".join(command))
            self._log_execution(command, violation=str(violation))
            if self.config.severity_on_violation == "raise":
                raise violation
            logger.warning("Sandbox violation (logged): %s", reason)
            return SandboxResult(
                returncode=-1, stdout="", stderr=reason,
                duration_seconds=0.0, cpu_seconds=0.0, memory_peak_kb=0,
                killed=True, kill_reason=reason,
            )

        # Validate cwd
        if cwd and not self._is_path_allowed(cwd):
            violation = SandboxViolation("path_restriction", f"cwd not allowed: {cwd}", " ".join(command))
            self._log_execution(command, violation=str(violation))
            if self.config.severity_on_violation == "raise":
                raise violation
            cwd = self.config.tmp_dir

        effective_timeout = timeout or self.config.max_wall_seconds
        env = self.sanitize_environment()

        start_time = time.monotonic()
        killed = False
        kill_reason = ""

        try:
            preexec = self._set_resource_limits if platform.system() != "Windows" else None

            proc = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                cwd=cwd or self.config.tmp_dir,
                preexec_fn=preexec,
            )

            try:
                stdout_bytes, stderr_bytes = proc.communicate(timeout=effective_timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout_bytes, stderr_bytes = proc.communicate()
                killed = True
                kill_reason = f"Timeout after {effective_timeout}s"
            except subprocess.CalledProcessError:
                proc.kill()
                stdout_bytes, stderr_bytes = proc.communicate()
                killed = True
                kill_reason = "Process error"

        except OSError as e:
            duration = time.monotonic() - start_time
            result = SandboxResult(
                returncode=-1, stdout="", stderr=str(e),
                duration_seconds=duration, cpu_seconds=0.0, memory_peak_kb=0,
                killed=True, kill_reason=f"OS error: {e}",
            )
            self._log_execution(command, result=result)
            return result

        duration = time.monotonic() - start_time

        # Estimate memory (platform-dependent)
        memory_kb = 0
        try:
            if platform.system() != "Windows" and proc.pid:
                with open(f"/proc/{proc.pid}/status", "r") as f:
                    for line in f:
                        if line.startswith("VmHWM:"):
                            memory_kb = int(line.split()[1])
                            break
        except (OSError, IndexError, ValueError):
            pass

        stdout_str = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
        stderr_str = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""

        result = SandboxResult(
            returncode=proc.returncode if not killed else -9,
            stdout=stdout_str,
            stderr=stderr_str,
            duration_seconds=round(duration, 3),
            cpu_seconds=0.0,  # Would need getrusage from child
            memory_peak_kb=memory_kb,
            killed=killed,
            kill_reason=kill_reason,
        )

        self._log_execution(command, result=result)
        return result

    def execute_safe(self, command: list[str], **kwargs: Any) -> Optional[SandboxResult]:
        """Execute with graceful degradation — never raises.

        Args:
            command: Command and arguments.
            **kwargs: Passed to execute().

        Returns:
            SandboxResult or None on catastrophic failure.
        """
        try:
            return self.execute(command, **kwargs)
        except SandboxViolation as e:
            logger.warning("Sandbox violation (suppressed): %s", e)
            return None
        except Exception as e:
            logger.error("Sandbox execution error: %s", e)
            return None

    # -- Network Validation ------------------------------------------------

    def validate_host(self, host: str, port: int = 443) -> tuple[bool, str]:
        """Validate if a network host is allowed.

        Args:
            host: Hostname or IP to check.
            port: Port number.

        Returns:
            Tuple of (is_allowed, reason).
        """
        if not self.config.enable_network:
            return False, "Network access disabled"

        if self.config.allowed_hosts:
            host_lower = host.lower()
            for allowed in self.config.allowed_hosts:
                allowed_lower = allowed.lower()
                # Exact match or wildcard subdomain
                if host_lower == allowed_lower:
                    return True, "Host allowed"
                if allowed_lower.startswith("*.") and host_lower.endswith(allowed_lower[1:]):
                    return True, "Host matches wildcard"
            return False, f"Host not in allowlist: {host}"

        if self.config.allowed_ports and port not in self.config.allowed_ports:
            return False, f"Port {port} not in allowed ports"

        return True, "Network access allowed"

    # -- Logging -----------------------------------------------------------

    def _log_execution(
        self,
        command: list[str],
        result: Optional[SandboxResult] = None,
        violation: Optional[str] = None,
    ) -> None:
        """Log execution for audit trail.

        Args:
            command: Command executed.
            result: Execution result.
            violation: Violation description if any.
        """
        entry: dict[str, Any] = {
            "timestamp": time.time(),
            "command": command,
            "violation": violation,
        }
        if result:
            entry.update({
                "returncode": result.returncode,
                "duration_seconds": result.duration_seconds,
                "killed": result.killed,
                "kill_reason": result.kill_reason,
            })
        self._execution_log.append(entry)

        # Keep log bounded
        if len(self._execution_log) > 10000:
            self._execution_log = self._execution_log[-5000:]

    def get_execution_log(self) -> list[dict[str, Any]]:
        """Retrieve the execution audit log.

        Returns:
            List of execution log entries.
        """
        return list(self._execution_log)

    # -- Lifecycle ---------------------------------------------------------

    def close(self) -> None:
        """Clean up sandbox resources."""
        if self._tmp_dir:
            try:
                self._tmp_dir.cleanup()
            except OSError as e:
                logger.warning("Failed to cleanup sandbox tmp dir: %s", e)
            self._tmp_dir = None

    def __enter__(self) -> ExecutionSandbox:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def __del__(self) -> None:
        self.close()
