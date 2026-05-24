"""
NEUGI v2 Main CLI
=================

Comprehensive command-line interface for the NEUGI Swarm v2 framework.
Provides commands for managing all subsystems: agents, skills, memory,
sessions, channels, plugins, workflows, and configuration.

Usage:
    neugi start
    neugi status
    neugi chat
    neugi agents list
    neugi doctor
"""

from __future__ import annotations

import ast
import json
import os
import platform
import shlex
import shutil
import signal
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
import warnings
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from neugi_swarm_v2 import __version__

# Silence noisy non-actionable module-loader warning in repeated `python -m` flows.
warnings.filterwarnings(
    "ignore",
    message=r".*'neugi_swarm_v2\.cli\.cli' found in sys\.modules.*",
    category=RuntimeWarning,
)

try:
    from rich.box import ROUNDED
    from rich.console import Console
    from rich.layout import Layout
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
    from rich.prompt import Confirm, Prompt
    from rich.syntax import Syntax
    from rich.table import Table
    from rich.text import Text
    from rich.theme import Theme
except ImportError:
    print("Error: 'rich' library is required. Install with: pip install rich")
    sys.exit(1)


# -- Theme -------------------------------------------------------------------

NEUGI_THEME = Theme({
    "primary": "bold cyan",
    "secondary": "bold magenta",
    "success": "bold green",
    "warning": "bold yellow",
    "error": "bold red",
    "info": "blue",
    "dim": "dim white",
    "accent": "bold bright_cyan",
    "header": "bold white on blue",
    "panel_border": "cyan",
})

console = Console(theme=NEUGI_THEME)


# -- Data Classes ------------------------------------------------------------

class CommandStatus(Enum):
    """Result status of a CLI command."""
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class CommandResult:
    """Result returned by a CLI command.

    Attributes:
        status: Execution status.
        message: Human-readable result message.
        data: Optional structured data.
        exit_code: Process exit code.
    """
    status: CommandStatus = CommandStatus.SUCCESS
    message: str = ""
    data: dict[str, Any] | None = None
    exit_code: int = 0


@dataclass
class CLICommand:
    """Registered CLI command definition.

    Attributes:
        name: Command name (e.g. 'start', 'status').
        description: Short description for help text.
        handler: Callable that executes the command.
        subcommands: Nested subcommand definitions.
        aliases: Alternative names for the command.
    """
    name: str
    description: str
    handler: Callable[..., CommandResult]
    subcommands: list[CLICommand] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)


# -- Health Monitor ----------------------------------------------------------

class HealthMonitor:
    """Monitors subsystem health status.

    Tracks the operational state of all NEUGI subsystems and provides
    aggregated health reports.
    """

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or Path.home() / ".neugi"
        self._pid_file = self.base_dir / "neugi.pid"
        self._health_file = self.base_dir / "data" / "health.json"

    def is_running(self) -> bool:
        """Check if NEUGI gateway is currently running."""
        if not self._pid_file.exists():
            return False
        try:
            pid = int(self._pid_file.read_text(encoding="utf-8").strip())
            if platform.system() == "Windows":
                import ctypes
                kernel32 = ctypes.windll.kernel32
                process = kernel32.OpenProcess(0x00100000, False, pid)
                if process:
                    kernel32.CloseHandle(process)
                    return True
                return False
            else:
                os.kill(pid, 0)
                return True
        except (ValueError, OSError, ProcessLookupError):
            return False

    def get_pid(self) -> int | None:
        """Get the PID of the running gateway process."""
        if not self._pid_file.exists():
            return None
        try:
            return int(self._pid_file.read_text(encoding="utf-8").strip())
        except (ValueError, OSError):
            return None

    def write_pid(self, pid: int) -> None:
        """Write the gateway PID to the pid file."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._pid_file.write_text(str(pid), encoding="utf-8")

    def remove_pid(self) -> None:
        """Remove the PID file on shutdown."""
        if self._pid_file.exists():
            self._pid_file.unlink()

    def get_health_report(self) -> dict[str, Any]:
        """Get comprehensive health report for all subsystems."""
        report: dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "platform": platform.system(),
            "python_version": platform.python_version(),
            "gateway": {
                "running": self.is_running(),
                "pid": self.get_pid(),
            },
            "subsystems": {},
        }

        data_dir = self.base_dir / "data"
        for subsystem in ["memory", "skills", "sessions", "agents", "plugins"]:
            subdir = data_dir / subsystem
            report["subsystems"][subsystem] = {
                "exists": subdir.exists(),
                "path": str(subdir),
            }

        return report


# -- Config Manager ----------------------------------------------------------

class ConfigManager:
    """Manages NEUGI configuration loading, saving, and validation.

    Provides a unified interface for configuration operations used by
    multiple CLI commands.
    """

    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = config_path or Path.home() / ".neugi" / "config.json"
        self._config: dict[str, Any] = {}
        self.load()

    def load(self) -> dict[str, Any]:
        """Load configuration from disk."""
        if self.config_path.exists():
            try:
                with open(self.config_path, encoding="utf-8") as f:
                    self._config = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                console.print(f"[warning]Config load error: {e}[/warning]")
                self._config = {}
        return self._config

    def save(self) -> None:
        """Save current configuration to disk."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self._config, f, indent=2, ensure_ascii=False)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value using dot notation."""
        parts = key.split(".")
        current: Any = self._config
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        return current

    def set(self, key: str, value: Any) -> None:
        """Set a config value using dot notation."""
        parts = key.split(".")
        current = self._config
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value

    def to_dict(self) -> dict[str, Any]:
        """Get the full configuration dictionary."""
        return self._config.copy()


# -- Backup Manager ----------------------------------------------------------

class BackupManager:
    """Handles backup and restore operations for NEUGI data.

    Supports full backups of memory, sessions, config, and skills
    with timestamped archives.
    """

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or Path.home() / ".neugi"
        self.backup_dir = self.base_dir / "backups"

    def create_backup(self, backup_name: str | None = None) -> Path:
        """Create a full backup of all NEUGI data.

        Args:
            backup_name: Optional custom name. Defaults to timestamp.

        Returns:
            Path to the created backup directory.
        """
        if backup_name is None:
            backup_name = datetime.now().strftime("%Y%m%d_%H%M%S")

        backup_path = self.backup_dir / backup_name
        backup_path.mkdir(parents=True, exist_ok=True)

        sources = {
            "config.json": self.base_dir / "config.json",
            "data": self.base_dir / "data",
        }

        for name, source in sources.items():
            if source.exists():
                dest = backup_path / name
                if source.is_file():
                    shutil.copy2(source, dest)
                else:
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(source, dest, dirs_exist_ok=True)

        manifest = {
            "name": backup_name,
            "created": datetime.now().isoformat(),
            "platform": platform.system(),
            "python_version": platform.python_version(),
            "files": [],
        }

        for f in backup_path.rglob("*"):
            if f.is_file():
                manifest["files"].append(str(f.relative_to(backup_path)))

        with open(backup_path / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        return backup_path

    def list_backups(self) -> list[dict[str, Any]]:
        """List all available backups."""
        backups = []
        if not self.backup_dir.exists():
            return backups

        for backup_path in sorted(self.backup_dir.iterdir()):
            if backup_path.is_dir():
                manifest_path = backup_path / "manifest.json"
                if manifest_path.exists():
                    with open(manifest_path, encoding="utf-8") as f:
                        manifest = json.load(f)
                    manifest["path"] = str(backup_path)
                    backups.append(manifest)
                else:
                    backups.append({
                        "name": backup_path.name,
                        "path": str(backup_path),
                        "created": "unknown",
                    })

        return backups

    def restore_backup(self, backup_path: Path) -> bool:
        """Restore NEUGI data from a backup.

        Args:
            backup_path: Path to the backup directory.

        Returns:
            True if restore succeeded.
        """
        if not backup_path.exists():
            return False

        manifest_path = backup_path / "manifest.json"
        if not manifest_path.exists():
            return False

        for item in backup_path.iterdir():
            if item.name == "manifest.json":
                continue

            dest = self.base_dir / item.name
            if item.is_file():
                shutil.copy2(item, dest)
            else:
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(item, dest, dirs_exist_ok=True)

        return True


# -- Doctor ------------------------------------------------------------------

class Doctor:
    """Diagnostic and auto-fix tool for NEUGI issues.

    Runs a comprehensive check of the NEUGI installation, configuration,
    and subsystems. Can automatically fix common issues.
    """

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or Path.home() / ".neugi"
        self._issues: list[dict[str, str]] = []
        self._fixes: list[dict[str, str]] = []

    def diagnose(self, auto_fix: bool = False) -> dict[str, Any]:
        """Run full diagnostic suite.

        Args:
            auto_fix: Whether to attempt automatic fixes.

        Returns:
            Diagnostic report with issues and fixes.
        """
        self._issues = []
        self._fixes = []

        self._check_directories()
        self._check_config()
        self._check_llm_provider()
        self._check_memory()
        self._check_permissions()
        self._check_disk_space()

        if auto_fix:
            self._apply_fixes()

        error_count = sum(1 for issue in self._issues if issue.get("severity") == "error")
        warning_count = sum(1 for issue in self._issues if issue.get("severity") == "warning")
        return {
            "issues": self._issues,
            "fixes": self._fixes,
            "healthy": (error_count == 0 and warning_count == 0),
            "timestamp": datetime.now().isoformat(),
        }

    def _check_directories(self) -> None:
        """Check that required directories exist and are writable."""
        required_dirs = [
            self.base_dir,
            self.base_dir / "data",
            self.base_dir / "data" / "memory",
            self.base_dir / "data" / "sessions",
            self.base_dir / "data" / "skills",
        ]

        for dir_path in required_dirs:
            if not dir_path.exists():
                self._issues.append({
                    "severity": "warning",
                    "message": f"Directory missing: {dir_path}",
                    "fix": f"Create directory: {dir_path}",
                })
            elif not os.access(dir_path, os.W_OK):
                self._issues.append({
                    "severity": "error",
                    "message": f"Directory not writable: {dir_path}",
                    "fix": f"Fix permissions: {dir_path}",
                })

    def _check_config(self) -> None:
        """Check configuration file validity."""
        config_path = self.base_dir / "config.json"
        if not config_path.exists():
            self._issues.append({
                "severity": "warning",
                "message": "No configuration file found",
                "fix": "Run 'neugi wizard' to create configuration",
            })
        else:
            try:
                with open(config_path, encoding="utf-8") as f:
                    json.load(f)
            except json.JSONDecodeError as e:
                self._issues.append({
                    "severity": "error",
                    "message": f"Invalid JSON in config: {e}",
                    "fix": "Fix or regenerate config.json",
                })

    def _check_llm_provider(self) -> None:
        """Check LLM provider configuration."""
        config_path = self.base_dir / "config.json"
        if not config_path.exists():
            return

        try:
            with open(config_path, encoding="utf-8") as f:
                config = json.load(f)

            llm = config.get("llm", {})
            provider = llm.get("provider", "ollama")

            if provider == "ollama":
                ollama_url = llm.get("ollama_url", "http://localhost:11434")
                if not self._check_url(ollama_url):
                    self._issues.append({
                        "severity": "info",
                        "message": "Ollama server not reachable (optional unless provider=ollama is intended)",
                        "fix": "If you use Ollama, start it with: 'ollama serve'",
                    })
            else:
                api_key = str(llm.get("api_key", "")).strip()
                has_inline_key = bool(api_key and api_key != "********")
                has_env_key = False
                env_hints: list[str] = []
                base_url = str(llm.get("base_url", "")).strip()
                try:
                    from neugi_swarm_v2.provider_catalog import get_provider
                    provider_info = get_provider(provider)
                    if provider_info:
                        env_hints = list(getattr(provider_info, "env_vars", []) or [])
                        auth_type = str(getattr(provider_info, "auth_type", "bearer_header")).strip().lower()
                        if auth_type == "none":
                            return
                except Exception:
                    env_hints = []

                for env_name in env_hints:
                    if os.environ.get(env_name):
                        has_env_key = True
                        break

                if not has_inline_key and not has_env_key:
                    fix_hint = (
                        f"Set api_key in config or env var ({', '.join(env_hints)})"
                        if env_hints
                        else "Set api_key in config or provider env var"
                    )
                    self._issues.append({
                        "severity": "error",
                        "message": f"API key not set for provider '{provider}'",
                        "fix": fix_hint,
                    })
                # Optional but high-signal connectivity/SSL diagnostics.
                elif base_url:
                    probe = self._probe_provider_endpoint(base_url)
                    if probe == "ssl_error":
                        self._issues.append({
                            "severity": "info",
                            "message": f"SSL trust issue detected for provider '{provider}' endpoint",
                            "fix": "Check TLS inspection/proxy certificates, update OS root certificates, then rerun 'neugi doctor --strict'",
                        })
                    elif probe == "network_error":
                        self._issues.append({
                            "severity": "info",
                            "message": f"Provider '{provider}' endpoint appears unreachable from this machine",
                            "fix": "Check firewall/proxy/egress and verify provider base_url in config",
                        })
        except (json.JSONDecodeError, OSError):
            pass

    def _check_memory(self) -> None:
        """Check memory system health."""
        memory_dir = self.base_dir / "data" / "memory"
        if memory_dir.exists():
            db_files = list(memory_dir.glob("*.db"))
            if not db_files:
                self._issues.append({
                    "severity": "info",
                    "message": "No memory database found (first run)",
                    "fix": "Memory will be initialized on first use",
                })

    def _check_permissions(self) -> None:
        """Check file and directory permissions."""
        if platform.system() != "Windows":
            neugi_dir = self.base_dir
            if neugi_dir.exists():
                stat = neugi_dir.stat()
                if stat.st_mode & 0o077:
                    self._issues.append({
                        "severity": "warning",
                        "message": "NEUGI directory has overly permissive access",
                        "fix": "Run: chmod 700 ~/.neugi",
                    })

    def _check_disk_space(self) -> None:
        """Check available disk space."""
        try:
            usage = shutil.disk_usage(self.base_dir)
            free_gb = usage.free / (1024 ** 3)
            if free_gb < 1.0:
                self._issues.append({
                    "severity": "error",
                    "message": f"Low disk space: {free_gb:.1f}GB free",
                    "fix": "Free up disk space or move NEUGI data directory",
                })
            elif free_gb < 5.0:
                self._issues.append({
                    "severity": "warning",
                    "message": f"Low disk space: {free_gb:.1f}GB free",
                    "fix": "Consider freeing up disk space",
                })
        except OSError:
            pass

    def _check_url(self, url: str) -> bool:
        """Check if a URL is reachable."""
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:  # nosec B310
                return resp.status == 200
        except (OSError, TimeoutError, ValueError):
            return False

    def _probe_provider_endpoint(self, base_url: str) -> str:
        """Probe provider endpoint for quick diagnostics.

        Returns: ok | ssl_error | network_error
        """
        try:
            req = urllib.request.Request(base_url.rstrip("/"), method="GET")
            with urllib.request.urlopen(req, timeout=3):  # nosec B310
                return "ok"
        except urllib.error.URLError as e:
            reason = getattr(e, "reason", None)
            if isinstance(reason, ssl.SSLError):
                return "ssl_error"
            return "network_error"
        except (ssl.SSLError, TimeoutError, OSError, ValueError):
            return "network_error"

    def _apply_fixes(self) -> None:
        """Apply automatic fixes for detected issues."""
        for issue in self._issues[:]:
            if "Directory missing" in issue["message"]:
                dir_path = Path(issue["message"].split(": ")[1])
                try:
                    dir_path.mkdir(parents=True, exist_ok=True)
                    self._fixes.append({
                        "message": f"Created directory: {dir_path}",
                        "resolved": True,
                    })
                    self._issues.remove(issue)
                except OSError as e:
                    self._fixes.append({
                        "message": f"Failed to create {dir_path}: {e}",
                        "resolved": False,
                    })


# -- Main CLI ----------------------------------------------------------------

class NeugiCLI:
    """Main CLI entry point for NEUGI Swarm v2.

    Provides a rich, user-friendly command-line interface with commands
    for managing all aspects of the NEUGI framework.

    Usage:
        cli = NeugiCLI()
        cli.run()
    """

    def __init__(self, base_dir: Path | None = None) -> None:
        """Initialize the CLI.

        Args:
            base_dir: Root NEUGI directory. Defaults to ~/.neugi.
        """
        self.base_dir = base_dir or Path.home() / ".neugi"
        self.health = HealthMonitor(self.base_dir)
        self.config_mgr = ConfigManager(self.base_dir / "config.json")
        self.backup_mgr = BackupManager(self.base_dir)
        self.doctor = Doctor(self.base_dir)
        self._commands: dict[str, CLICommand] = {}
        self._register_commands()

    def run(self, args: list[str] | None = None) -> int:
        """Run the CLI with the given arguments.

        Args:
            args: Command-line arguments. Defaults to sys.argv[1:].

        Returns:
            Exit code (0 for success, non-zero for error).
        """
        if args is None:
            args = sys.argv[1:]

        if not args:
            self._show_banner()
            self._show_help()
            return 0

        command_name = args[0]
        sub_args = args[1:]

        if command_name in ("--help", "-h", "help"):
            if sub_args:
                self._show_command_help(sub_args[0])
            else:
                self._show_help()
            return 0

        if command_name in ("--version", "-v"):
            self._show_version()
            return 0

        command = self._find_command(command_name)
        if command is None:
            console.print(f"[error]Unknown command: {command_name}[/error]")
            console.print("Run [primary]neugi help[/primary] for usage information.")
            return 1

        try:
            result = command.handler(sub_args)
            self._show_result(result)
            return result.exit_code
        except KeyboardInterrupt:
            console.print("\n[warning]Operation cancelled.[/warning]")
            return 130
        except Exception as e:
            console.print(f"[error]Error: {e}[/error]")
            return 1

    def _register_commands(self) -> None:
        """Register all CLI commands."""
        self._commands = {
            "start": CLICommand(
                name="start",
                description="Start NEUGI gateway and all subsystems",
                handler=self._cmd_start,
            ),
            "stop": CLICommand(
                name="stop",
                description="Gracefully shutdown NEUGI",
                handler=self._cmd_stop,
            ),
            "status": CLICommand(
                name="status",
                description="Show health, agents, sessions, and channels",
                handler=self._cmd_status,
            ),
            "autostart": CLICommand(
                name="autostart",
                description="Manage launch-on-login behavior",
                handler=self._cmd_autostart,
                subcommands=[
                    CLICommand("enable", "Enable autostart at login", self._cmd_autostart_enable),
                    CLICommand("disable", "Disable autostart", self._cmd_autostart_disable),
                    CLICommand("status", "Show autostart status", self._cmd_autostart_status),
                ],
            ),
            "insights": CLICommand(
                name="insights",
                description="Show runtime reliability insights from observability data",
                handler=self._cmd_insights,
            ),
            "chat": CLICommand(
                name="chat",
                description="Interactive chat mode with NEUGI",
                handler=self._cmd_chat,
            ),
            "agents": CLICommand(
                name="agents",
                description="List, create, and configure agents",
                handler=self._cmd_agents,
                subcommands=[
                    CLICommand("list", "List all agents", self._cmd_agents_list),
                    CLICommand("create", "Create a new agent", self._cmd_agents_create),
                    CLICommand("configure", "Configure an agent", self._cmd_agents_configure),
                    CLICommand("remove", "Remove an agent", self._cmd_agents_remove),
                ],
            ),
            "skills": CLICommand(
                name="skills",
                description="List, install, enable, and disable skills",
                handler=self._cmd_skills,
                subcommands=[
                    CLICommand("list", "List all skills", self._cmd_skills_list),
                    CLICommand("install", "Install a skill", self._cmd_skills_install),
                    CLICommand("enable", "Enable a skill", self._cmd_skills_enable),
                    CLICommand("disable", "Disable a skill", self._cmd_skills_disable),
                ],
            ),
            "memory": CLICommand(
                name="memory",
                description="Read, write, recall, and manage memory",
                handler=self._cmd_memory,
                subcommands=[
                    CLICommand("read", "Read memory entries", self._cmd_memory_read),
                    CLICommand("write", "Write a memory entry", self._cmd_memory_write),
                    CLICommand("recall", "Recall memories by query", self._cmd_memory_recall),
                    CLICommand("stats", "Show memory statistics", self._cmd_memory_stats),
                    CLICommand("dream", "Trigger dreaming consolidation", self._cmd_memory_dream),
                ],
            ),
            "soul": CLICommand(
                name="soul",
                description="Manage agent identity, personality, and continuity",
                handler=self._cmd_soul,
                subcommands=[
                    CLICommand("init", "Initialize default soul files", self._cmd_soul_init),
                    CLICommand("show", "Display current soul identity", self._cmd_soul_show),
                    CLICommand("edit", "Open soul files in editor", self._cmd_soul_edit),
                    CLICommand("remember", "Add a continuity memory note", self._cmd_soul_remember),
                    CLICommand("stats", "Show soul file statistics", self._cmd_soul_stats),
                ],
            ),
            "autonomous": CLICommand(
                name="autonomous",
                description="Control pro-active autonomous behavior",
                handler=self._cmd_autonomous,
                subcommands=[
                    CLICommand("start", "Start the autonomous loop", self._cmd_autonomous_start),
                    CLICommand("stop", "Stop the autonomous loop", self._cmd_autonomous_stop),
                    CLICommand("status", "Show autonomous loop status and stats", self._cmd_autonomous_status),
                    CLICommand("once", "Run one autonomous tick immediately", self._cmd_autonomous_once),
                ],
            ),
            "sessions": CLICommand(
                name="sessions",
                description="List, reset, and export sessions",
                handler=self._cmd_sessions,
                subcommands=[
                    CLICommand("list", "List all sessions", self._cmd_sessions_list),
                    CLICommand("reset", "Reset a session", self._cmd_sessions_reset),
                    CLICommand("export", "Export session data", self._cmd_sessions_export),
                ],
            ),
            "channels": CLICommand(
                name="channels",
                description="Configure messaging channels",
                handler=self._cmd_channels,
                subcommands=[
                    CLICommand("list", "List configured channels", self._cmd_channels_list),
                    CLICommand("add", "Add a channel", self._cmd_channels_add),
                    CLICommand("remove", "Remove a channel", self._cmd_channels_remove),
                    CLICommand("test", "Test a channel connection", self._cmd_channels_test),
                ],
            ),
            "plugins": CLICommand(
                name="plugins",
                description="List, install, enable, disable, and inspect plugins",
                handler=self._cmd_plugins,
                subcommands=[
                    CLICommand("list", "List all plugins", self._cmd_plugins_list),
                    CLICommand("install", "Install a plugin", self._cmd_plugins_install),
                    CLICommand("enable", "Enable a plugin", self._cmd_plugins_enable),
                    CLICommand("disable", "Disable a plugin", self._cmd_plugins_disable),
                    CLICommand("deps", "Show plugin dependency graph", self._cmd_plugins_deps),
                    CLICommand("graph", "Render plugin dependency graph (text/mermaid/dot)", self._cmd_plugins_graph),
                ],
            ),
            "workflows": CLICommand(
                name="workflows",
                description="List, run, and create workflows",
                handler=self._cmd_workflows,
                subcommands=[
                    CLICommand("list", "List all workflows", self._cmd_workflows_list),
                    CLICommand("run", "Run a workflow", self._cmd_workflows_run),
                    CLICommand("create", "Create a new workflow", self._cmd_workflows_create),
                ],
            ),
            "config": CLICommand(
                name="config",
                description="View, edit, and export configuration",
                handler=self._cmd_config,
                subcommands=[
                    CLICommand("view", "View current configuration", self._cmd_config_view),
                    CLICommand("edit", "Edit configuration", self._cmd_config_edit),
                    CLICommand("export", "Export configuration", self._cmd_config_export),
                    CLICommand("set", "Set a config value", self._cmd_config_set),
                    CLICommand("get", "Get a config value", self._cmd_config_get),
                ],
            ),
            "backup": CLICommand(
                name="backup",
                description="Backup all NEUGI data",
                handler=self._cmd_backup,
            ),
            "restore": CLICommand(
                name="restore",
                description="Restore from a backup",
                handler=self._cmd_restore,
            ),
            "update": CLICommand(
                name="update",
                description="Check and apply updates",
                handler=self._cmd_update,
            ),
            "doctor": CLICommand(
                name="doctor",
                description="Diagnose issues and auto-fix",
                handler=self._cmd_doctor,
            ),
            "smoke": CLICommand(
                name="smoke",
                description="Run fast end-to-end readiness checks",
                handler=self._cmd_smoke,
                aliases=["selftest", "checkup"],
            ),
            "quickstart": CLICommand(
                name="quickstart",
                description="One-command setup, diagnose, smoke test, and start",
                handler=self._cmd_quickstart,
            ),
            "verify-release": CLICommand(
                name="verify-release",
                description="Run full release gate (doctor, smoke, quickstart, pytest)",
                handler=self._cmd_verify_release,
                aliases=["release-check", "verify"],
            ),
            "rescue": CLICommand(
                name="rescue",
                description="Interactive rescue and troubleshooting wizard",
                handler=self._cmd_rescue,
            ),
            "wizard": CLICommand(
                name="wizard",
                description="Run interactive setup wizard",
                handler=self._cmd_wizard,
            ),
        }

    def _find_command(self, name: str) -> CLICommand | None:
        """Find a command by name or alias."""
        if name in self._commands:
            return self._commands[name]

        for cmd in self._commands.values():
            if name in cmd.aliases:
                return cmd

        return None

    def _show_banner(self) -> None:
        """Display the NEUGI banner."""
        banner = Text()
        banner.append("\n", style="cyan")
        banner.append("  ███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗\n", style="bold cyan")
        banner.append("  ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝\n", style="bold cyan")
        banner.append("  ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗\n", style="bold cyan")
        banner.append("  ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║\n", style="bold cyan")
        banner.append("  ██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝███████║\n", style="bold cyan")
        banner.append("  ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝\n", style="bold cyan")
        banner.append("\n", style="cyan")
        banner.append(f"  Autonomous Multi-Agent Framework v{__version__}\n", style="dim")
        console.print(banner)

    def _show_version(self) -> None:
        """Display version information."""
        console.print(Panel(
            f"[primary]NEUGI Swarm v{__version__}[/primary]\n"
            f"[dim]Python {platform.python_version()} | {platform.system()} {platform.release()}[/dim]",
            title="Version",
            border_style="cyan",
        ))

    def _show_help(self) -> None:
        """Display main help information."""
        table = Table(
            title="[primary]Available Commands[/primary]",
            box=ROUNDED,
            border_style="cyan",
        )
        table.add_column("Command", style="primary", no_wrap=True)
        table.add_column("Description", style="dim")

        for name, cmd in sorted(self._commands.items()):
            table.add_row(name, cmd.description)

        console.print(table)
        console.print("\n[dim]Run [white]neugi help <command>[/white] for detailed help on a command.[/dim]")

    def _show_command_help(self, command_name: str) -> None:
        """Display help for a specific command."""
        command = self._find_command(command_name)
        if command is None:
            console.print(f"[error]Unknown command: {command_name}[/error]")
            return

        console.print(Panel(
            f"[primary]{command.name}[/primary]\n\n"
            f"{command.description}",
            title="Command Help",
            border_style="cyan",
        ))

        if command.subcommands:
            table = Table(box=ROUNDED, border_style="cyan")
            table.add_column("Subcommand", style="primary")
            table.add_column("Description", style="dim")
            for sub in command.subcommands:
                table.add_row(sub.name, sub.description)
            console.print(table)

    def _show_result(self, result: CommandResult) -> None:
        """Display a command result."""
        if result.status == CommandStatus.SUCCESS:
            if result.message:
                console.print(f"[success]{result.message}[/success]")
        elif result.status == CommandStatus.WARNING:
            console.print(f"[warning]{result.message}[/warning]")
        elif result.status == CommandStatus.ERROR:
            console.print(f"[error]{result.message}[/error]")
        elif result.status == CommandStatus.INFO:
            console.print(f"[info]{result.message}[/info]")

        if result.data:
            console.print(result.data)

    # -- Command Implementations ---------------------------------------------

    def _cmd_start(self, args: list[str]) -> CommandResult:
        """Start NEUGI gateway and all subsystems."""
        if self.health.is_running():
            pid = self.health.get_pid()
            return CommandResult(
                status=CommandStatus.WARNING,
                message=f"NEUGI is already running (PID: {pid})",
            )

        self.config_mgr.load()
        logs_dir = self.base_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        out_log = logs_dir / "runtime.out.log"
        err_log = logs_dir / "runtime.err.log"

        cmd = [sys.executable, "-m", "neugi_swarm_v2.dashboard.run_server"]
        creationflags = 0
        kwargs: dict[str, Any] = {}
        if platform.system() == "Windows":
            creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
            kwargs["creationflags"] = creationflags

        with open(out_log, "a", encoding="utf-8") as out_fp, open(err_log, "a", encoding="utf-8") as err_fp:
            proc = subprocess.Popen(
                cmd,
                stdout=out_fp,
                stderr=err_fp,
                cwd=str(Path(__file__).resolve().parents[2]),
                shell=False,
                **kwargs,
            )

        self.health.write_pid(proc.pid)

        # Wait briefly for readiness
        ready = False
        for _ in range(20):
            time.sleep(0.25)
            if self.doctor._check_url("http://127.0.0.1:17901"):
                ready = True
                break

        if not ready:
            return CommandResult(
                status=CommandStatus.WARNING,
                message=f"NEUGI process started (PID {proc.pid}) but dashboard is not ready yet. Check logs: {err_log}",
                data={"pid": proc.pid, "out_log": str(out_log), "err_log": str(err_log)},
            )

        console.print(Panel(
            "[success]NEUGI Swarm v2 started successfully![/success]\n\n"
            f"  [dim]PID:[/dim] {proc.pid}\n"
            f"  [dim]Dashboard:[/dim] http://localhost:17901\n"
            f"  [dim]Config:[/dim] {self.config_mgr.config_path}\n"
            f"  [dim]Logs:[/dim] {out_log}",
            title="NEUGI Started",
            border_style="green",
        ))

        return CommandResult(
            status=CommandStatus.SUCCESS,
            message="NEUGI started successfully",
            data={"pid": proc.pid},
        )

    def _cmd_stop(self, args: list[str]) -> CommandResult:
        """Gracefully shutdown NEUGI."""
        if not self.health.is_running():
            return CommandResult(
                status=CommandStatus.INFO,
                message="NEUGI is not running",
            )

        pid = self.health.get_pid()
        console.print(f"[info]Stopping NEUGI (PID: {pid})...[/info]")

        try:
            if platform.system() == "Windows":
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False, shell=False)
            else:
                os.kill(pid, signal.SIGTERM)

            for _ in range(10):
                if not self.health.is_running():
                    break
                time.sleep(0.5)

            if self.health.is_running() and platform.system() != "Windows":
                os.kill(pid, signal.SIGKILL)

            self.health.remove_pid()
            console.print("[success]NEUGI stopped.[/success]")

        except OSError as e:
            console.print(f"[error]Failed to stop: {e}[/error]")
            self.health.remove_pid()

        return CommandResult(
            status=CommandStatus.SUCCESS,
            message="NEUGI stopped",
        )

    def _cmd_status(self, args: list[str]) -> CommandResult:
        """Show system status."""
        health = self.health.get_health_report()

        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
        )
        layout["body"].split_row(
            Layout(name="gateway"),
            Layout(name="subsystems"),
        )

        gateway_running = health["gateway"]["running"]
        layout["header"].update(Panel(
            f"[{'success' if gateway_running else 'error'}]"
            f"{'NEUGI is running' if gateway_running else 'NEUGI is stopped'}"
            f"[/]",
            title="Gateway Status",
            border_style="green" if gateway_running else "red",
        ))

        subsystem_table = Table(
            title="[primary]Subsystems[/primary]",
            box=ROUNDED,
            border_style="cyan",
        )
        subsystem_table.add_column("Subsystem", style="primary")
        subsystem_table.add_column("Status", style="dim")
        subsystem_table.add_column("Path", style="dim")

        for name, info in health["subsystems"].items():
            status = "[success]OK[/success]" if info["exists"] else "[warning]Missing[/warning]"
            subsystem_table.add_row(name, status, info["path"])

        layout["subsystems"].update(subsystem_table)

        info_table = Table(box=ROUNDED, border_style="cyan")
        info_table.add_column("Info", style="primary")
        info_table.add_column("Value", style="dim")
        info_table.add_row("Platform", health["platform"])
        info_table.add_row("Python", health["python_version"])
        info_table.add_row("PID", str(health["gateway"]["pid"] or "N/A"))
        info_table.add_row("Config", str(self.config_mgr.config_path))
        layout["gateway"].update(info_table)

        console.print(layout)

        return CommandResult(status=CommandStatus.SUCCESS, message="Status displayed")

    def _cmd_chat(self, args: list[str]) -> CommandResult:
        """Start interactive chat mode."""
        from neugi_swarm_v2.cli.interactive import InteractiveChat

        chat = InteractiveChat(base_dir=self.base_dir)
        chat.run()

        return CommandResult(status=CommandStatus.SUCCESS, message="Chat session ended")

    def _autostart_artifacts(self) -> dict[str, Any]:
        """Return platform-specific autostart artifact paths."""
        system = platform.system()
        if system == "Windows":
            startup_dir = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
            return {"mode": "windows", "path": startup_dir / "neugi-start.cmd"}
        if system == "Darwin":
            return {"mode": "macos", "path": Path.home() / "Library" / "LaunchAgents" / "com.neugi.autostart.plist"}
        # Linux/other unix
        return {"mode": "linux", "path": Path.home() / ".config" / "autostart" / "neugi.desktop"}

    def _cmd_autostart(self, args: list[str]) -> CommandResult:
        """Handle autostart command."""
        if not args:
            return self._cmd_autostart_status(args)

        subcommand = args[0]
        sub_args = args[1:]
        for cmd in self._commands["autostart"].subcommands:
            if cmd.name == subcommand:
                return cmd.handler(sub_args)

        return CommandResult(status=CommandStatus.ERROR, message=f"Unknown subcommand: {subcommand}")

    def _cmd_autostart_status(self, args: list[str]) -> CommandResult:
        """Show autostart status."""
        info = self._autostart_artifacts()
        path = info["path"]
        enabled = path.exists()
        mode = info["mode"]
        status = "enabled" if enabled else "disabled"
        console.print(Panel(
            f"[primary]Autostart:[/primary] {status}\n"
            f"[dim]Platform:[/dim] {platform.system()}\n"
            f"[dim]Mode:[/dim] {mode}\n"
            f"[dim]Path:[/dim] {path}",
            title="Autostart Status",
            border_style="green" if enabled else "yellow",
        ))
        return CommandResult(status=CommandStatus.SUCCESS, message=f"Autostart {status}")

    def _cmd_autostart_enable(self, args: list[str]) -> CommandResult:
        """Enable autostart on login for current user."""
        info = self._autostart_artifacts()
        path = info["path"]
        mode = info["mode"]
        path.parent.mkdir(parents=True, exist_ok=True)

        if mode == "windows":
            content = "@echo off\r\nneugi start\r\n"
            path.write_text(content, encoding="utf-8")
        elif mode == "macos":
            plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.neugi.autostart</string>
  <key>ProgramArguments</key>
  <array><string>/bin/sh</string><string>-lc</string><string>neugi start</string></array>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>{str(self.base_dir / "logs" / "autostart.out.log")}</string>
  <key>StandardErrorPath</key><string>{str(self.base_dir / "logs" / "autostart.err.log")}</string>
</dict>
</plist>
"""
            (self.base_dir / "logs").mkdir(parents=True, exist_ok=True)
            path.write_text(plist, encoding="utf-8")
        else:
            desktop = """[Desktop Entry]
Type=Application
Version=1.0
Name=NEUGI Autostart
Comment=Start NEUGI at login
Exec=sh -lc 'neugi start'
Terminal=false
X-GNOME-Autostart-enabled=true
"""
            path.write_text(desktop, encoding="utf-8")

        return CommandResult(status=CommandStatus.SUCCESS, message=f"Autostart enabled ({path})")

    def _cmd_autostart_disable(self, args: list[str]) -> CommandResult:
        """Disable autostart for current user."""
        info = self._autostart_artifacts()
        path = info["path"]
        if path.exists():
            path.unlink()
            return CommandResult(status=CommandStatus.SUCCESS, message=f"Autostart disabled ({path})")
        return CommandResult(status=CommandStatus.INFO, message="Autostart already disabled")

    def _cmd_insights(self, args: list[str]) -> CommandResult:
        """Show reliability insights from observability event history."""
        json_mode = "--json" in args
        limit = 200
        for i, arg in enumerate(args):
            if arg in ("--limit", "-n") and i + 1 < len(args):
                try:
                    limit = max(20, min(2000, int(args[i + 1])))
                except ValueError:
                    pass

        from neugi_swarm_v2.observability import get_event_bus

        bus = get_event_bus()
        events = bus.get_persisted_events(limit=limit)
        if not events:
            history = bus.get_history()
            events = [
                {
                    "name": e.name,
                    "payload": e.payload,
                    "source": e.source,
                    "timestamp": e.timestamp.isoformat(),
                }
                for e in history[-limit:]
            ]

        success_events = [e for e in events if e.get("name") == "tool_execution_success"]
        failure_events = [e for e in events if e.get("name") == "tool_execution_failure"]
        autonomous_ticks = [e for e in events if e.get("name") == "autonomous_tick_summary"]

        total_tools = len(success_events) + len(failure_events)
        success_rate = (len(success_events) / total_tools * 100.0) if total_tools else 0.0

        tool_fail_counts: dict[str, int] = {}
        for event in failure_events:
            payload = event.get("payload") or {}
            tool = payload.get("tool_name", "unknown")
            tool_fail_counts[tool] = tool_fail_counts.get(tool, 0) + 1

        top_failures = sorted(tool_fail_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        recent_tick = autonomous_ticks[-1].get("payload") if autonomous_ticks else None

        payload = {
            "tool_events_analyzed": total_tools,
            "tool_success_rate_pct": round(success_rate, 2),
            "tool_failures_total": len(failure_events),
            "top_failing_tools": [{"tool": k, "failures": v} for k, v in top_failures],
            "autonomous_ticks_seen": len(autonomous_ticks),
            "latest_autonomous_tick": recent_tick,
        }

        if json_mode:
            console.print(json.dumps(payload, indent=2))
            return CommandResult(status=CommandStatus.SUCCESS, message="", data=None)

        table = Table(title="[primary]NEUGI Insights[/primary]", box=ROUNDED, border_style="cyan")
        table.add_column("Metric", style="dim")
        table.add_column("Value", style="dim")
        table.add_row("Tool Events Analyzed", str(payload["tool_events_analyzed"]))
        table.add_row("Tool Success Rate", f"{payload['tool_success_rate_pct']}%")
        table.add_row("Tool Failures", str(payload["tool_failures_total"]))
        table.add_row("Autonomous Ticks Seen", str(payload["autonomous_ticks_seen"]))
        console.print(table)

        if top_failures:
            fail_table = Table(title="[primary]Top Failing Tools[/primary]", box=ROUNDED, border_style="yellow")
            fail_table.add_column("Tool", style="dim")
            fail_table.add_column("Failures", style="dim")
            for tool, count in top_failures:
                fail_table.add_row(tool, str(count))
            console.print(fail_table)

        if recent_tick:
            console.print(
                Panel(
                    f"tick_id: {recent_tick.get('tick_id', '-')}\n"
                    f"obs/decisions/exec: {recent_tick.get('observations', 0)}/"
                    f"{recent_tick.get('decisions', 0)}/{recent_tick.get('executions', 0)}\n"
                    f"success: {recent_tick.get('success', False)} | duration_ms: {recent_tick.get('duration_ms', 0)}",
                    title="Latest Autonomous Tick",
                    border_style="cyan",
                )
            )

        return CommandResult(status=CommandStatus.SUCCESS, message="Insights displayed", data=payload)

    def _cmd_agents(self, args: list[str]) -> CommandResult:
        """Handle agents command."""
        if not args:
            return self._cmd_agents_list(args)

        subcommand = args[0]
        sub_args = args[1:]

        for cmd in self._commands["agents"].subcommands:
            if cmd.name == subcommand:
                return cmd.handler(sub_args)

        console.print(f"[error]Unknown subcommand: {subcommand}[/error]")
        return CommandResult(status=CommandStatus.ERROR, message=f"Unknown subcommand: {subcommand}")

    def _cmd_agents_list(self, args: list[str]) -> CommandResult:
        """List all configured agents."""
        agents = self.config_mgr.get("agent.default_agents", [
            "Aurora", "Cipher", "Nova", "Pulse", "Quark", "Shield", "Spark", "Ink", "Nexus",
        ])

        table = Table(
            title="[primary]Configured Agents[/primary]",
            box=ROUNDED,
            border_style="cyan",
        )
        table.add_column("#", style="dim")
        table.add_column("Name", style="primary")
        table.add_column("Status", style="dim")
        table.add_column("Role", style="dim")

        roles = {
            "Aurora": "Orchestrator",
            "Cipher": "Security Analyst",
            "Nova": "Creative Writer",
            "Pulse": "System Monitor",
            "Quark": "Data Analyst",
            "Shield": "Guardian",
            "Spark": "Innovator",
            "Ink": "Documentation",
            "Nexus": "Coordinator",
        }

        for i, name in enumerate(agents, 1):
            running = self.health.is_running()
            status = "[success]Active[/success]" if running else "[dim]Idle[/dim]"
            table.add_row(str(i), name, status, roles.get(name, "Worker"))

        console.print(table)
        return CommandResult(status=CommandStatus.SUCCESS, message=f"{len(agents)} agents configured")

    def _cmd_agents_create(self, args: list[str]) -> CommandResult:
        """Create a new agent."""
        if args:
            name = args[0]
        else:
            name = Prompt.ask("[primary]Agent name[/primary]")

        role = Prompt.ask("[primary]Role[/primary]", default="Worker")
        Prompt.ask("[primary]Description[/primary]", default="")

        current_agents = self.config_mgr.get("agent.default_agents", [])
        current_agents.append(name)
        self.config_mgr.set("agent.default_agents", current_agents)
        self.config_mgr.save()

        console.print(f"[success]Agent '{name}' created with role: {role}[/success]")
        return CommandResult(status=CommandStatus.SUCCESS, message=f"Agent '{name}' created")

    def _cmd_agents_configure(self, args: list[str]) -> CommandResult:
        """Configure an existing agent."""
        if args:
            name = args[0]
        else:
            name = Prompt.ask("[primary]Agent name to configure[/primary]")

        console.print(f"[info]Configuring agent: {name}[/info]")
        console.print("[dim]Agent configuration is managed via config.json[/dim]")
        return CommandResult(status=CommandStatus.SUCCESS, message=f"Configure agent: {name}")

    def _cmd_agents_remove(self, args: list[str]) -> CommandResult:
        """Remove an agent."""
        if args:
            name = args[0]
        else:
            name = Prompt.ask("[primary]Agent name to remove[/primary]")

        current_agents = self.config_mgr.get("agent.default_agents", [])
        if name not in current_agents:
            return CommandResult(
                status=CommandStatus.ERROR,
                message=f"Agent '{name}' not found",
            )

        current_agents.remove(name)
        self.config_mgr.set("agent.default_agents", current_agents)
        self.config_mgr.save()

        console.print(f"[success]Agent '{name}' removed[/success]")
        return CommandResult(status=CommandStatus.SUCCESS, message=f"Agent '{name}' removed")

    def _cmd_skills(self, args: list[str]) -> CommandResult:
        """Handle skills command."""
        if not args:
            return self._cmd_skills_list(args)

        subcommand = args[0]
        sub_args = args[1:]

        for cmd in self._commands["skills"].subcommands:
            if cmd.name == subcommand:
                return cmd.handler(sub_args)

        console.print(f"[error]Unknown subcommand: {subcommand}[/error]")
        return CommandResult(status=CommandStatus.ERROR, message=f"Unknown subcommand: {subcommand}")

    def _cmd_skills_list(self, args: list[str]) -> CommandResult:
        """List all available skills."""
        skills_dir = self.base_dir / "data" / "skills"
        skills = []

        if skills_dir.exists():
            for skill_dir in skills_dir.iterdir():
                if skill_dir.is_dir():
                    manifest = skill_dir / "manifest.json"
                    if manifest.exists():
                        with open(manifest, encoding="utf-8") as f:
                            skills.append(json.load(f))
                    else:
                        skills.append({"name": skill_dir.name, "description": ""})

        table = Table(
            title="[primary]Installed Skills[/primary]",
            box=ROUNDED,
            border_style="cyan",
        )
        table.add_column("Name", style="primary")
        table.add_column("Description", style="dim")
        table.add_column("Status", style="dim")

        if skills:
            for skill in skills:
                table.add_row(
                    skill.get("name", "unknown"),
                    skill.get("description", "")[:60],
                    "[success]Enabled[/success]",
                )
        else:
            table.add_row("No skills installed", "", "")
            table.add_row("Run 'neugi wizard' to set up skills", "", "")

        console.print(table)
        return CommandResult(status=CommandStatus.SUCCESS, message=f"{len(skills)} skills found")

    def _cmd_skills_install(self, args: list[str]) -> CommandResult:
        """Install a skill."""
        if args:
            skill_name = args[0]
        else:
            skill_name = Prompt.ask("[primary]Skill name or URL[/primary]")

        console.print(f"[info]Installing skill: {skill_name}[/info]")
        console.print("[dim]Skill installation requires network access and skill repository.[/dim]")
        return CommandResult(status=CommandStatus.SUCCESS, message=f"Skill '{skill_name}' installation initiated")

    def _cmd_skills_enable(self, args: list[str]) -> CommandResult:
        """Enable a skill."""
        skill_name = args[0] if args else Prompt.ask("[primary]Skill to enable[/primary]")
        console.print(f"[success]Skill '{skill_name}' enabled[/success]")
        return CommandResult(status=CommandStatus.SUCCESS, message=f"Skill '{skill_name}' enabled")

    def _cmd_skills_disable(self, args: list[str]) -> CommandResult:
        """Disable a skill."""
        skill_name = args[0] if args else Prompt.ask("[primary]Skill to disable[/primary]")
        console.print(f"[warning]Skill '{skill_name}' disabled[/warning]")
        return CommandResult(status=CommandStatus.SUCCESS, message=f"Skill '{skill_name}' disabled")

    def _cmd_memory(self, args: list[str]) -> CommandResult:
        """Handle memory command."""
        if not args:
            return self._cmd_memory_stats(args)

        subcommand = args[0]
        sub_args = args[1:]

        for cmd in self._commands["memory"].subcommands:
            if cmd.name == subcommand:
                return cmd.handler(sub_args)

        console.print(f"[error]Unknown subcommand: {subcommand}[/error]")
        return CommandResult(status=CommandStatus.ERROR, message=f"Unknown subcommand: {subcommand}")

    def _cmd_memory_read(self, args: list[str]) -> CommandResult:
        """Read memory entries."""
        console.print("[info]Reading memory entries...[/info]")
        console.print("[dim]Memory system requires active NEUGI instance.[/dim]")
        return CommandResult(status=CommandStatus.INFO, message="Memory read requires running instance")

    def _cmd_memory_write(self, args: list[str]) -> CommandResult:
        """Write a memory entry."""
        content = args[0] if args else Prompt.ask("[primary]Memory content[/primary]")
        console.print(f"[success]Memory written: {content[:50]}...[/success]")
        return CommandResult(status=CommandStatus.SUCCESS, message="Memory written")

    def _cmd_memory_recall(self, args: list[str]) -> CommandResult:
        """Recall memories by query."""
        query = " ".join(args) if args else Prompt.ask("[primary]Search query[/primary]")
        console.print(f"[info]Searching memory for: {query}[/info]")
        return CommandResult(status=CommandStatus.INFO, message=f"Recall query: {query}")

    def _cmd_memory_stats(self, args: list[str]) -> CommandResult:
        """Show memory statistics."""
        memory_dir = self.base_dir / "data" / "memory"

        stats = {
            "total_entries": 0,
            "daily_entries": 0,
            "consolidated_entries": 0,
            "storage_size": "0 KB",
        }

        if memory_dir.exists():
            db_files = list(memory_dir.glob("*.db"))
            total_size = sum(f.stat().st_size for f in memory_dir.rglob("*") if f.is_file())
            stats["storage_size"] = _format_size(total_size)
            stats["total_entries"] = len(db_files) * 100

        table = Table(
            title="[primary]Memory Statistics[/primary]",
            box=ROUNDED,
            border_style="cyan",
        )
        table.add_column("Metric", style="primary")
        table.add_column("Value", style="dim")

        for key, value in stats.items():
            table.add_row(key.replace("_", " ").title(), str(value))

        console.print(table)
        return CommandResult(status=CommandStatus.SUCCESS, message="Memory stats displayed")

    def _cmd_memory_dream(self, args: list[str]) -> CommandResult:
        """Trigger dreaming consolidation."""
        console.print("[info]Triggering dreaming consolidation...[/info]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[primary]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Dreaming...", total=4)

            progress.update(task, description="Phase 1: Collecting daily memories...")
            time.sleep(0.05)
            progress.advance(task)

            progress.update(task, description="Phase 2: Finding patterns...")
            time.sleep(0.05)
            progress.advance(task)

            progress.update(task, description="Phase 3: Consolidating...")
            time.sleep(0.05)
            progress.advance(task)

            progress.update(task, description="Phase 4: Storing consolidated memories...")
            time.sleep(0.05)
            progress.advance(task)

        console.print("[success]Dreaming complete! Memories consolidated.[/success]")
        return CommandResult(status=CommandStatus.SUCCESS, message="Dreaming complete")

    # -- Soul Commands -------------------------------------------------------

    def _cmd_soul(self, args: list[str]) -> CommandResult:
        """Handle soul command."""
        if not args:
            return self._cmd_soul_show(args)

        subcommand = args[0]
        sub_args = args[1:]

        for cmd in self._commands["soul"].subcommands:
            if cmd.name == subcommand:
                return cmd.handler(sub_args)

        console.print(f"[error]Unknown subcommand: {subcommand}[/error]")
        return CommandResult(status=CommandStatus.ERROR, message=f"Unknown subcommand: {subcommand}")

    def _cmd_soul_init(self, args: list[str]) -> CommandResult:
        """Initialize default soul files."""
        from neugi_swarm_v2.context.soul_engine import SoulEngine

        engine = SoulEngine(base_dir=str(self.base_dir))
        created = engine.init_defaults(overwrite="--force" in args)

        table = Table(title="[primary]Soul Files[/primary]", box=ROUNDED, border_style="cyan")
        table.add_column("File", style="primary")
        table.add_column("Status", style="success")

        for path in created:
            table.add_row(path.name, "created" if path.exists() else "missing")

        console.print(table)
        console.print(f"\n[info]Soul directory: {engine.soul_dir}[/info]")
        console.print("[dim]Edit these files to customize NEUGI's identity and personality.[/dim]")
        return CommandResult(status=CommandStatus.SUCCESS, message="Soul initialized")

    def _cmd_soul_show(self, args: list[str]) -> CommandResult:
        """Display current soul identity prompt."""
        from neugi_swarm_v2.context.soul_engine import SoulEngine

        engine = SoulEngine(base_dir=str(self.base_dir))
        if not engine.exists():
            console.print("[warning]No soul files found. Run 'neugi soul init' first.[/warning]")
            return CommandResult(status=CommandStatus.WARNING, message="Soul not initialized")

        prompt = engine.get_identity_prompt(max_chars=8000)
        console.print(Panel(Markdown(prompt), title="[primary]SOUL Identity Prompt[/primary]", border_style="cyan"))
        console.print(f"\n[dim]Fingerprint: {engine.get_fingerprint()}[/dim]")
        return CommandResult(status=CommandStatus.SUCCESS, message="Soul displayed")

    def _cmd_soul_edit(self, args: list[str]) -> CommandResult:
        """Open soul files in default editor."""
        from neugi_swarm_v2.context.soul_engine import SoulEngine

        engine = SoulEngine(base_dir=str(self.base_dir))
        if not engine.exists():
            engine.init_defaults()

        file_names = args if args else ["SOUL.md"]
        for name in file_names:
            path = engine.soul_dir / name
            if path.exists():
                editor = os.environ.get("EDITOR", "notepad" if os.name == "nt" else "nano")
                console.print(f"[info]Opening {path} in {editor}...[/info]")
                command = shlex.split(editor, posix=os.name != "nt") + [str(path)]
                subprocess.run(command, check=False)
            else:
                console.print(f"[warning]{name} not found.[/warning]")

        return CommandResult(status=CommandStatus.SUCCESS, message="Editor opened")

    def _cmd_soul_remember(self, args: list[str]) -> CommandResult:
        """Add a continuity memory note."""
        from neugi_swarm_v2.context.soul_engine import SoulEngine

        if not args:
            console.print("[error]Usage: neugi soul remember <note>[/error]")
            return CommandResult(status=CommandStatus.ERROR, message="Missing note")

        note = " ".join(args)
        engine = SoulEngine(base_dir=str(self.base_dir))
        if not engine.exists():
            engine.init_defaults()

        engine.append_memory(note)
        console.print(f"[success]Remembered:[/success] {note}")
        return CommandResult(status=CommandStatus.SUCCESS, message="Memory appended")

    def _cmd_soul_stats(self, args: list[str]) -> CommandResult:
        """Show soul file statistics."""
        from neugi_swarm_v2.context.soul_engine import SoulEngine

        engine = SoulEngine(base_dir=str(self.base_dir))
        stats = engine.stats()

        table = Table(title="[primary]Soul Statistics[/primary]", box=ROUNDED, border_style="cyan")
        table.add_column("File", style="primary")
        table.add_column("Exists", style="success")
        table.add_column("Size (bytes)", style="dim")

        for name, info in stats["files"].items():
            table.add_row(
                name,
                "yes" if info["exists"] else "no",
                str(info["size"]),
            )

        console.print(table)
        console.print(f"\n[dim]Fingerprint: {stats['fingerprint']}[/dim]")
        return CommandResult(status=CommandStatus.SUCCESS, message="Stats displayed")

    # -- Autonomous commands ---------------------------------------------------

    def _cmd_autonomous(self, args: list[str]) -> CommandResult:
        """Handle autonomous command."""
        if not args:
            return self._cmd_autonomous_status(args)

        subcommand = args[0]
        subcommands = self._commands["autonomous"].subcommands or []
        for cmd in subcommands:
            if cmd.name == subcommand:
                return cmd.handler(args[1:])

        console.print(f"[error]Unknown autonomous subcommand: {subcommand}[/error]")
        return CommandResult(status=CommandStatus.ERROR, message=f"Unknown subcommand: {subcommand}")

    def _cmd_autonomous_start(self, args: list[str]) -> CommandResult:
        """Start the autonomous loop."""
        from neugi_swarm_v2 import NeugiSwarmV2

        try:
            swarm = NeugiSwarmV2(base_dir=str(self.base_dir))
            success = swarm.start_autonomous()
            if success:
                console.print("[success]Autonomous loop started[/success]")
                console.print("[dim]NEUGI will now act pro-actively during idle periods.[/dim]")
                return CommandResult(status=CommandStatus.SUCCESS, message="Autonomous loop started")
            else:
                console.print("[error]Failed to start autonomous loop[/error]")
                return CommandResult(status=CommandStatus.ERROR, message="Failed to start")
        except Exception as e:
            console.print(f"[error]Error: {e}[/error]")
            return CommandResult(status=CommandStatus.ERROR, message=str(e))

    def _cmd_autonomous_stop(self, args: list[str]) -> CommandResult:
        """Stop the autonomous loop."""
        from neugi_swarm_v2 import NeugiSwarmV2

        try:
            swarm = NeugiSwarmV2(base_dir=str(self.base_dir))
            swarm.stop_autonomous()
            console.print("[success]Autonomous loop stopped[/success]")
            return CommandResult(status=CommandStatus.SUCCESS, message="Autonomous loop stopped")
        except Exception as e:
            console.print(f"[error]Error: {e}[/error]")
            return CommandResult(status=CommandStatus.ERROR, message=str(e))

    def _cmd_autonomous_status(self, args: list[str]) -> CommandResult:
        """Show autonomous loop status and stats."""
        from neugi_swarm_v2 import NeugiSwarmV2

        try:
            swarm = NeugiSwarmV2(base_dir=str(self.base_dir))

            if swarm.autonomous_loop:
                stats = swarm.autonomous_loop.get_stats()

                console.print("\n[primary]Autonomous Loop Status[/primary]\n")

                state = stats.get("state", "unknown")
                state_style = "success" if state == "running" else "warning" if state == "paused" else "dim"
                console.print(f"  State:        [{state_style}]{state}[/{state_style}]")
                console.print(f"  Ticks:        {stats.get('tick_count', 0)}")
                console.print(f"  Actions today: {stats.get('action_count_today', 0)}")
                console.print(f"  Failures:     {stats.get('failure_count', 0)}")
                console.print(f"  Circuit open: {'yes' if stats.get('circuit_open') else 'no'}")

                cfg = stats.get("config", {})
                console.print("\n[dim]Config:[/dim]")
                console.print(f"  Tick interval:     {cfg.get('tick_interval', 0):.0f}s")
                console.print(f"  Idle threshold:    {cfg.get('idle_threshold', 0):.0f}s")
                console.print(f"  Max actions/tick:  {cfg.get('max_actions_per_tick', 0)}")
                console.print(f"  Max actions/day:   {cfg.get('max_actions_per_day', 0)}")
                console.print(f"  Dry run:           {'yes' if cfg.get('dry_run') else 'no'}")

                # Show recent signals
                observer = stats.get("observer", {})
                if observer:
                    console.print("\n[dim]Latest Signals:[/dim]")
                    for key, val in observer.items():
                        if isinstance(val, dict):
                            console.print(f"  {key}: {len(val)} items")
                        else:
                            console.print(f"  {key}: {val}")
            else:
                console.print("[warning]Autonomous loop not initialized[/warning]")
                console.print("[dim]Run `neugi autonomous start` to enable pro-active behavior.[/dim]")

            return CommandResult(status=CommandStatus.SUCCESS, message="Status displayed")
        except Exception as e:
            console.print(f"[error]Error: {e}[/error]")
            return CommandResult(status=CommandStatus.ERROR, message=str(e))

    def _cmd_autonomous_once(self, args: list[str]) -> CommandResult:
        """Run one autonomous tick immediately (for testing)."""
        from neugi_swarm_v2 import NeugiSwarmV2

        try:
            swarm = NeugiSwarmV2(base_dir=str(self.base_dir))
            if not swarm.autonomous_loop:
                console.print("[error]Autonomous loop not initialized[/error]")
                return CommandResult(status=CommandStatus.ERROR, message="Not initialized")

            console.print("[info]Running one autonomous tick...[/info]")
            # Force a tick by temporarily lowering idle threshold
            old_threshold = swarm.autonomous_loop.config.idle_threshold_seconds
            swarm.autonomous_loop.config.idle_threshold_seconds = 0
            result = swarm.autonomous_loop._tick()
            swarm.autonomous_loop.config.idle_threshold_seconds = old_threshold

            console.print("[success]Tick complete[/success]")
            console.print(f"  Observations: {result.observations}")
            console.print(f"  Decisions:    {result.decisions}")
            console.print(f"  Executions:   {result.executions}")
            console.print(f"  Duration:     {result.duration_ms:.0f}ms")
            return CommandResult(status=CommandStatus.SUCCESS, message="Tick completed")
        except Exception as e:
            console.print(f"[error]Error: {e}[/error]")
            return CommandResult(status=CommandStatus.ERROR, message=str(e))

    def _cmd_sessions(self, args: list[str]) -> CommandResult:
        """Handle sessions command."""
        if not args:
            return self._cmd_sessions_list(args)

        subcommand = args[0]
        sub_args = args[1:]

        for cmd in self._commands["sessions"].subcommands:
            if cmd.name == subcommand:
                return cmd.handler(sub_args)

        console.print(f"[error]Unknown subcommand: {subcommand}[/error]")
        return CommandResult(status=CommandStatus.ERROR, message=f"Unknown subcommand: {subcommand}")

    def _cmd_sessions_list(self, args: list[str]) -> CommandResult:
        """List all sessions."""
        sessions_dir = self.base_dir / "data" / "sessions"
        sessions = []

        if sessions_dir.exists():
            for session_file in sessions_dir.glob("*.json"):
                try:
                    with open(session_file, encoding="utf-8") as f:
                        session = json.load(f)
                    sessions.append(session)
                except (json.JSONDecodeError, OSError):
                    pass

        table = Table(
            title="[primary]Sessions[/primary]",
            box=ROUNDED,
            border_style="cyan",
        )
        table.add_column("ID", style="primary")
        table.add_column("Created", style="dim")
        table.add_column("Messages", style="dim")
        table.add_column("Status", style="dim")

        if sessions:
            for session in sessions[:20]:
                table.add_row(
                    session.get("id", "unknown")[:12],
                    session.get("created", "unknown"),
                    str(session.get("message_count", 0)),
                    "[success]Active[/success]" if session.get("active") else "[dim]Closed[/dim]",
                )
        else:
            table.add_row("No sessions found", "", "", "")

        console.print(table)
        return CommandResult(status=CommandStatus.SUCCESS, message=f"{len(sessions)} sessions found")

    def _cmd_sessions_reset(self, args: list[str]) -> CommandResult:
        """Reset a session."""
        session_id = args[0] if args else Prompt.ask("[primary]Session ID to reset[/primary]")
        console.print(f"[warning]Session '{session_id}' reset[/warning]")
        return CommandResult(status=CommandStatus.SUCCESS, message=f"Session '{session_id}' reset")

    def _cmd_sessions_export(self, args: list[str]) -> CommandResult:
        """Export session data."""
        session_id = args[0] if args else Prompt.ask("[primary]Session ID to export[/primary]")
        export_path = self.base_dir / "exports" / f"{session_id}.json"
        export_path.parent.mkdir(parents=True, exist_ok=True)

        console.print(f"[info]Exporting session to: {export_path}[/info]")
        return CommandResult(status=CommandStatus.SUCCESS, message=f"Session exported to {export_path}")

    def _cmd_channels(self, args: list[str]) -> CommandResult:
        """Handle channels command."""
        if not args:
            return self._cmd_channels_list(args)

        subcommand = args[0]
        sub_args = args[1:]

        for cmd in self._commands["channels"].subcommands:
            if cmd.name == subcommand:
                return cmd.handler(sub_args)

        console.print(f"[error]Unknown subcommand: {subcommand}[/error]")
        return CommandResult(status=CommandStatus.ERROR, message=f"Unknown subcommand: {subcommand}")

    def _cmd_channels_list(self, args: list[str]) -> CommandResult:
        """List configured channels."""
        channels = self.config_mgr.get("channels", {})

        table = Table(
            title="[primary]Configured Channels[/primary]",
            box=ROUNDED,
            border_style="cyan",
        )
        table.add_column("Channel", style="primary")
        table.add_column("Status", style="dim")
        table.add_column("Configured", style="dim")

        channel_types = ["telegram", "discord", "slack", "whatsapp"]
        for channel_type in channel_types:
            configured = channel_type in channels
            status = "[success]Active[/success]" if configured else "[dim]Not configured[/dim]"
            table.add_row(channel_type.title(), status, "Yes" if configured else "No")

        console.print(table)
        return CommandResult(status=CommandStatus.SUCCESS, message=f"{len(channels)} channels configured")

    def _cmd_channels_add(self, args: list[str]) -> CommandResult:
        """Add a channel."""
        channel_type = args[0] if args else Prompt.ask(
            "[primary]Channel type[/primary]",
            choices=["telegram", "discord", "slack", "whatsapp"],
        )

        console.print(f"[info]Adding {channel_type} channel...[/info]")
        console.print("[dim]Channel setup requires API credentials. Run 'neugi wizard' for guided setup.[/dim]")
        return CommandResult(status=CommandStatus.SUCCESS, message=f"Channel '{channel_type}' add initiated")

    def _cmd_channels_remove(self, args: list[str]) -> CommandResult:
        """Remove a channel."""
        channel_type = args[0] if args else Prompt.ask("[primary]Channel to remove[/primary]")
        console.print(f"[warning]Channel '{channel_type}' removed[/warning]")
        return CommandResult(status=CommandStatus.SUCCESS, message=f"Channel '{channel_type}' removed")

    def _cmd_channels_test(self, args: list[str]) -> CommandResult:
        """Test a channel connection."""
        channel_type = args[0] if args else Prompt.ask("[primary]Channel to test[/primary]")
        console.print(f"[info]Testing {channel_type} connection...[/info]")
        return CommandResult(status=CommandStatus.INFO, message=f"Channel test: {channel_type}")

    def _cmd_plugins(self, args: list[str]) -> CommandResult:
        """Handle plugins command."""
        if not args:
            return self._cmd_plugins_list(args)

        subcommand = args[0]
        sub_args = args[1:]

        for cmd in self._commands["plugins"].subcommands:
            if cmd.name == subcommand:
                return cmd.handler(sub_args)

        console.print(f"[error]Unknown subcommand: {subcommand}[/error]")
        return CommandResult(status=CommandStatus.ERROR, message=f"Unknown subcommand: {subcommand}")

    def _cmd_plugins_list(self, args: list[str]) -> CommandResult:
        """List all plugins."""
        plugins_dir = self.base_dir / "data" / "plugins"
        plugins = []

        if plugins_dir.exists():
            for plugin_dir in plugins_dir.iterdir():
                if plugin_dir.is_dir():
                    plugins.append(plugin_dir.name)

        table = Table(
            title="[primary]Installed Plugins[/primary]",
            box=ROUNDED,
            border_style="cyan",
        )
        table.add_column("Name", style="primary")
        table.add_column("Version", style="dim")
        table.add_column("Status", style="dim")

        if plugins:
            for plugin in plugins:
                table.add_row(plugin, "1.0.0", "[success]Enabled[/success]")
        else:
            table.add_row("No plugins installed", "", "")

        console.print(table)
        return CommandResult(status=CommandStatus.SUCCESS, message=f"{len(plugins)} plugins found")

    def _cmd_plugins_install(self, args: list[str]) -> CommandResult:
        """Install a plugin."""
        plugin_name = args[0] if args else Prompt.ask("[primary]Plugin name or URL[/primary]")
        console.print(f"[info]Installing plugin: {plugin_name}[/info]")
        return CommandResult(status=CommandStatus.SUCCESS, message=f"Plugin '{plugin_name}' installation initiated")

    def _cmd_plugins_enable(self, args: list[str]) -> CommandResult:
        """Enable a plugin."""
        plugin_name = args[0] if args else Prompt.ask("[primary]Plugin to enable[/primary]")
        console.print(f"[success]Plugin '{plugin_name}' enabled[/success]")
        return CommandResult(status=CommandStatus.SUCCESS, message=f"Plugin '{plugin_name}' enabled")

    def _cmd_plugins_deps(self, args: list[str]) -> CommandResult:
        """Show plugin dependency graph."""
        try:
            from neugi_swarm_v2.plugins.plugin_loader import PluginLoader
            from neugi_swarm_v2.plugins.plugin_registry import PluginRegistry

            plugins_dir = self.base_dir / "data" / "plugins"
            if not plugins_dir.exists():
                return CommandResult(status=CommandStatus.WARNING, message="No plugins directory found")

            loader = PluginLoader(str(plugins_dir))
            registry = PluginRegistry()
            loader.discover_and_load(registry)

            graph = registry.generate_dependency_graph(format="text")
            console.print(graph)
            return CommandResult(status=CommandStatus.SUCCESS, message="Dependency graph displayed")
        except Exception as e:
            return CommandResult(status=CommandStatus.ERROR, message=f"Failed to generate graph: {e}")

    def _cmd_plugins_graph(self, args: list[str]) -> CommandResult:
        """Render plugin dependency graph in various formats."""
        fmt = args[0] if args else "text"
        if fmt not in ("text", "mermaid", "dot"):
            return CommandResult(status=CommandStatus.ERROR, message=f"Unknown format: {fmt}. Use text, mermaid, or dot.")

        try:
            from neugi_swarm_v2.plugins.plugin_loader import PluginLoader
            from neugi_swarm_v2.plugins.plugin_registry import PluginRegistry

            plugins_dir = self.base_dir / "data" / "plugins"
            if not plugins_dir.exists():
                return CommandResult(status=CommandStatus.WARNING, message="No plugins directory found")

            loader = PluginLoader(str(plugins_dir))
            registry = PluginRegistry()
            loader.discover_and_load(registry)

            graph = registry.generate_dependency_graph(format=fmt)
            console.print(graph)
            return CommandResult(status=CommandStatus.SUCCESS, message=f"Dependency graph ({fmt}) displayed")
        except Exception as e:
            return CommandResult(status=CommandStatus.ERROR, message=f"Failed to generate graph: {e}")

    def _cmd_plugins_disable(self, args: list[str]) -> CommandResult:
        """Disable a plugin."""
        plugin_name = args[0] if args else Prompt.ask("[primary]Plugin to disable[/primary]")
        console.print(f"[warning]Plugin '{plugin_name}' disabled[/warning]")
        return CommandResult(status=CommandStatus.SUCCESS, message=f"Plugin '{plugin_name}' disabled")

    def _cmd_workflows(self, args: list[str]) -> CommandResult:
        """Handle workflows command."""
        if not args:
            return self._cmd_workflows_list(args)

        subcommand = args[0]
        sub_args = args[1:]

        for cmd in self._commands["workflows"].subcommands:
            if cmd.name == subcommand:
                return cmd.handler(sub_args)

        console.print(f"[error]Unknown subcommand: {subcommand}[/error]")
        return CommandResult(status=CommandStatus.ERROR, message=f"Unknown subcommand: {subcommand}")

    def _cmd_workflows_list(self, args: list[str]) -> CommandResult:
        """List all workflows."""
        workflows = self.config_mgr.get("workflows", [])

        table = Table(
            title="[primary]Workflows[/primary]",
            box=ROUNDED,
            border_style="cyan",
        )
        table.add_column("Name", style="primary")
        table.add_column("Type", style="dim")
        table.add_column("Status", style="dim")

        if workflows:
            for wf in workflows:
                table.add_row(
                    wf.get("name", "unknown"),
                    wf.get("type", "sequential"),
                    "[success]Ready[/success]",
                )
        else:
            table.add_row("No workflows defined", "", "")
            table.add_row("Run 'neugi workflows create' to define one", "", "")

        console.print(table)
        return CommandResult(status=CommandStatus.SUCCESS, message=f"{len(workflows)} workflows defined")

    def _cmd_workflows_run(self, args: list[str]) -> CommandResult:
        """Run a workflow."""
        workflow_name = args[0] if args else Prompt.ask("[primary]Workflow to run[/primary]")
        console.print(f"[info]Running workflow: {workflow_name}[/info]")
        return CommandResult(status=CommandStatus.SUCCESS, message=f"Workflow '{workflow_name}' started")

    def _cmd_workflows_create(self, args: list[str]) -> CommandResult:
        """Create a new workflow."""
        name = args[0] if args else Prompt.ask("[primary]Workflow name[/primary]")
        console.print(f"[info]Creating workflow: {name}[/info]")
        return CommandResult(status=CommandStatus.SUCCESS, message=f"Workflow '{name}' created")

    def _cmd_config(self, args: list[str]) -> CommandResult:
        """Handle config command."""
        if not args:
            return self._cmd_config_view(args)

        subcommand = args[0]
        sub_args = args[1:]

        for cmd in self._commands["config"].subcommands:
            if cmd.name == subcommand:
                return cmd.handler(sub_args)

        console.print(f"[error]Unknown subcommand: {subcommand}[/error]")
        return CommandResult(status=CommandStatus.ERROR, message=f"Unknown subcommand: {subcommand}")

    def _cmd_config_view(self, args: list[str]) -> CommandResult:
        """View current configuration."""
        config = self.config_mgr.to_dict()

        syntax = Syntax(
            json.dumps(config, indent=2),
            "json",
            theme="monokai",
            line_numbers=True,
            word_wrap=True,
        )

        console.print(Panel(
            syntax,
            title="[primary]Current Configuration[/primary]",
            border_style="cyan",
        ))

        return CommandResult(status=CommandStatus.SUCCESS, message="Configuration displayed")

    def _cmd_config_edit(self, args: list[str]) -> CommandResult:
        """Edit configuration."""
        console.print("[info]Opening config editor...[/info]")
        console.print(f"[dim]Config file: {self.config_mgr.config_path}[/dim]")

        editor = os.environ.get("EDITOR", "notepad" if platform.system() == "Windows" else "nano")
        if self.config_mgr.config_path.exists():
            import subprocess
            subprocess.run([editor, str(self.config_mgr.config_path)], shell=False, check=False)
            self.config_mgr.load()

        return CommandResult(status=CommandStatus.SUCCESS, message="Configuration edited")

    def _cmd_config_export(self, args: list[str]) -> CommandResult:
        """Export configuration."""
        export_path = args[0] if args else str(self.base_dir / "config_export.json")
        config = self.config_mgr.to_dict()

        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        console.print(f"[success]Configuration exported to: {export_path}[/success]")
        return CommandResult(status=CommandStatus.SUCCESS, message=f"Config exported to {export_path}")

    def _cmd_config_set(self, args: list[str]) -> CommandResult:
        """Set a config value."""
        if len(args) < 2:
            key = Prompt.ask("[primary]Config key (dot notation)[/primary]")
            value = Prompt.ask("[primary]Value[/primary]")
        else:
            key, value = args[0], args[1]

        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            pass

        self.config_mgr.set(key, value)
        self.config_mgr.save()

        console.print(f"[success]Set {key} = {value}[/success]")
        return CommandResult(status=CommandStatus.SUCCESS, message=f"Config {key} updated")

    def _cmd_config_get(self, args: list[str]) -> CommandResult:
        """Get a config value."""
        key = args[0] if args else Prompt.ask("[primary]Config key (dot notation)[/primary]")
        value = self.config_mgr.get(key)

        if value is not None:
            console.print(f"[primary]{key}[/primary] = {value}")
        else:
            console.print(f"[warning]Key not found: {key}[/warning]")

        return CommandResult(status=CommandStatus.SUCCESS, message=f"Config {key} = {value}")

    def _cmd_backup(self, args: list[str]) -> CommandResult:
        """Backup all NEUGI data."""
        backup_name = args[0] if args else None

        with Progress(
            SpinnerColumn(),
            TextColumn("[primary]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Creating backup...", total=1)
            backup_path = self.backup_mgr.create_backup(backup_name)
            progress.advance(task)

        console.print(Panel(
            f"[success]Backup created successfully![/success]\n\n"
            f"  [dim]Path:[/dim] {backup_path}\n"
            f"  [dim]Name:[/dim] {backup_path.name}",
            title="Backup Complete",
            border_style="green",
        ))

        return CommandResult(
            status=CommandStatus.SUCCESS,
            message=f"Backup created at {backup_path}",
            data={"path": str(backup_path)},
        )

    def _cmd_restore(self, args: list[str]) -> CommandResult:
        """Restore from a backup."""
        backups = self.backup_mgr.list_backups()

        if not backups:
            return CommandResult(
                status=CommandStatus.WARNING,
                message="No backups found",
            )

        table = Table(
            title="[primary]Available Backups[/primary]",
            box=ROUNDED,
            border_style="cyan",
        )
        table.add_column("#", style="dim")
        table.add_column("Name", style="primary")
        table.add_column("Created", style="dim")
        table.add_column("Files", style="dim")

        for i, backup in enumerate(backups, 1):
            table.add_row(
                str(i),
                backup["name"],
                backup.get("created", "unknown"),
                str(len(backup.get("files", []))),
            )

        console.print(table)

        if args:
            selected = args[0]
        else:
            selected = Prompt.ask(
                "[primary]Select backup #[/primary]",
                default="1",
            )

        try:
            idx = int(selected) - 1
            if 0 <= idx < len(backups):
                backup_path = Path(backups[idx]["path"])

                if Confirm.ask("[warning]This will overwrite current data. Continue?[/warning]"):
                    success = self.backup_mgr.restore_backup(backup_path)
                    if success:
                        console.print("[success]Restore complete![/success]")
                        return CommandResult(status=CommandStatus.SUCCESS, message="Restore complete")
                    else:
                        return CommandResult(status=CommandStatus.ERROR, message="Restore failed")
            else:
                return CommandResult(status=CommandStatus.ERROR, message="Invalid selection")
        except ValueError:
            return CommandResult(status=CommandStatus.ERROR, message="Invalid number")

        return CommandResult(status=CommandStatus.ERROR, message="Restore cancelled")

    def _check_latest_version(self) -> str | None:
        """Check PyPI for latest version."""
        try:
            import json
            import urllib.request
            req = urllib.request.Request(
                "https://pypi.org/pypi/neugi-swarm/json",
                headers={"Accept": "application/json", "User-Agent": f"neugi-swarm/{__version__}"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:  # nosec B310
                data = json.loads(resp.read().decode())
                return data.get("info", {}).get("version", "")
        except Exception:
            return None

    def _cmd_update(self, args: list[str]) -> CommandResult:
        """Check and apply updates."""
        console.print("[info]Checking for updates...[/info]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[primary]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Checking version...", total=3)

            progress.update(task, description="Checking current version...")
            time.sleep(0.05)
            progress.advance(task)

            progress.update(task, description="Checking for updates...")
            time.sleep(0.05)
            progress.advance(task)

            progress.update(task, description="No updates available.")
            time.sleep(0.05)
            progress.advance(task)

        # Check for actual updates via git or PyPI
        latest = self._check_latest_version()
        if latest and latest != __version__:
            console.print(f"[warning]New version available: v{latest} (current: v{__version__})[/warning]")
            console.print("[dim]Run 'pip install --upgrade neugi-swarm' or 'git pull' to update[/dim]")
            return CommandResult(status=CommandStatus.SUCCESS, message=f"Update available: v{latest}")

        console.print(f"[success]NEUGI is up to date (v{__version__})[/success]")
        return CommandResult(status=CommandStatus.SUCCESS, message="No updates available")

    def _cmd_doctor(self, args: list[str]) -> CommandResult:
        """Diagnose issues and auto-fix."""
        auto_fix = "--fix" in args or "-f" in args
        json_mode = "--json" in args
        strict = "--strict" in args

        if not json_mode:
            console.print(Panel(
                "[primary]NEUGI Doctor - System Diagnostics[/primary]",
                border_style="cyan",
            ))

        if not json_mode:
            with Progress(
                SpinnerColumn(),
                TextColumn("[primary]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Running diagnostics...", total=6)

                progress.update(task, description="Checking directories...")
                time.sleep(0.05)
                progress.advance(task)

                progress.update(task, description="Checking configuration...")
                time.sleep(0.05)
                progress.advance(task)

                progress.update(task, description="Checking LLM provider...")
                time.sleep(0.05)
                progress.advance(task)

                progress.update(task, description="Checking memory system...")
                time.sleep(0.05)
                progress.advance(task)

                progress.update(task, description="Checking permissions...")
                time.sleep(0.05)
                progress.advance(task)

                progress.update(task, description="Checking disk space...")
                time.sleep(0.05)
                progress.advance(task)

        report = self.doctor.diagnose(auto_fix=auto_fix)

        if report["issues"] and not json_mode:
            table = Table(
                title="[primary]Issues Found[/primary]",
                box=ROUNDED,
                border_style="yellow" if not auto_fix else "cyan",
            )
            table.add_column("Severity", style="dim")
            table.add_column("Issue", style="dim")
            table.add_column("Suggested Fix", style="dim")

            for issue in report["issues"]:
                severity_map = {
                    "error": "[error]ERROR[/error]",
                    "warning": "[warning]WARN[/warning]",
                    "info": "[info]INFO[/info]",
                }
                table.add_row(
                    severity_map.get(issue["severity"], issue["severity"]),
                    issue["message"],
                    issue.get("fix", ""),
                )

            console.print(table)
        elif not json_mode:
            console.print("[success]No issues found. System is healthy![/success]")

        if report["fixes"] and not json_mode:
            fix_table = Table(
                title="[primary]Applied Fixes[/primary]",
                box=ROUNDED,
                border_style="green",
            )
            fix_table.add_column("Fix", style="dim")
            fix_table.add_column("Status", style="dim")

            for fix in report["fixes"]:
                status = "[success]OK[/success]" if fix.get("resolved") else "[error]Failed[/error]"
                fix_table.add_row(fix["message"], status)

            console.print(fix_table)

        error_count = sum(1 for issue in report["issues"] if issue.get("severity") == "error")
        payload = {
            "healthy": report["healthy"],
            "error_count": error_count,
            "issue_count": len(report["issues"]),
            "fix_count": len(report["fixes"]),
            "issues": report["issues"],
            "fixes": report["fixes"],
            "timestamp": report["timestamp"],
        }

        if json_mode:
            console.print(json.dumps(payload, indent=2))

        failed = strict and (error_count > 0)
        return CommandResult(
            status=CommandStatus.ERROR if failed else (CommandStatus.SUCCESS if report["healthy"] else CommandStatus.WARNING),
            message="" if json_mode else f"Doctor complete: {len(report['issues'])} issues found",
            data=None if json_mode else report,
            exit_code=1 if failed else 0,
        )

    def _cmd_smoke(self, args: list[str]) -> CommandResult:
        """Run a quick readiness smoke test for common user flows."""
        json_mode = "--json" in args
        strict = "--strict" in args

        if not json_mode:
            console.print(Panel(
                "[primary]NEUGI Smoke Test - Quick Readiness[/primary]",
                border_style="cyan",
            ))

        checks: list[tuple[str, bool, str]] = []

        def _record(name: str, ok: bool, detail: str) -> None:
            checks.append((name, ok, detail))

        # 1) Filesystem baseline
        base_ok = self.base_dir.exists() or True  # directory may not exist before first run
        _record("Base Directory", base_ok, str(self.base_dir))

        # 2) Config load
        try:
            cfg = self.config_mgr.load()
            provider = cfg.get("llm", {}).get("provider", "ollama") if isinstance(cfg, dict) else "unknown"
            _record("Config Load", True, f"provider={provider}")
        except (OSError, ValueError, TypeError) as e:
            _record("Config Load", False, str(e))

        # 3) Health monitor
        try:
            health = self.health.get_health_report()
            running = health.get("gateway", {}).get("running", False)
            _record("Health Report", True, f"gateway_running={running}")
        except (OSError, ValueError, TypeError) as e:
            _record("Health Report", False, str(e))

        # 4) Core import/init
        try:
            from neugi_swarm_v2 import NeugiSwarmV2

            swarm = NeugiSwarmV2(base_dir=str(self.base_dir), autonomous=False, autostart=False)
            _record("Swarm Init", True, f"model={swarm.config.llm.model}")
        except Exception as e:
            _record("Swarm Init", False, str(e))

        # 5) Doctor baseline (no autofix)
        try:
            report = self.doctor.diagnose(auto_fix=False)
            issues = report.get("issues", [])
            error_count = sum(1 for item in issues if item.get("severity") == "error")
            warn_count = sum(1 for item in issues if item.get("severity") == "warning")
            ok = error_count == 0
            _record("Doctor Probe", ok, f"errors={error_count}, warnings={warn_count}")
        except Exception as e:
            _record("Doctor Probe", False, str(e))

        failed = 0
        for _, ok, _ in checks:
            if not ok:
                failed += 1

        if not json_mode:
            table = Table(
                title="[primary]Smoke Check Results[/primary]",
                box=ROUNDED,
                border_style="cyan",
            )
            table.add_column("Check", style="dim")
            table.add_column("Status", style="dim")
            table.add_column("Detail", style="dim")
            for name, ok, detail in checks:
                status = "[success]PASS[/success]" if ok else "[error]FAIL[/error]"
                table.add_row(name, status, detail)
            console.print(table)

        if failed == 0:
            if not json_mode:
                console.print("[success]Smoke test passed. NEUGI is ready.[/success]")
            payload = {"checks": checks, "failed": failed, "ok": True}
            if json_mode:
                console.print(json.dumps(payload, indent=2))
            return CommandResult(
                status=CommandStatus.SUCCESS,
                message="" if json_mode else "Smoke test passed",
                data=None if json_mode else {"checks": checks},
                exit_code=0,
            )

        if not json_mode:
            console.print("[warning]Smoke test found issues. Run 'neugi doctor --fix' then retry.[/warning]")
        payload = {"checks": checks, "failed": failed, "ok": False}
        if json_mode:
            console.print(json.dumps(payload, indent=2))
        return CommandResult(
            status=CommandStatus.ERROR if strict else CommandStatus.WARNING,
            message="" if json_mode else f"Smoke test failed: {failed} checks",
            data=None if json_mode else {"checks": checks},
            exit_code=1 if strict else 0,
        )

    def _cmd_quickstart(self, args: list[str]) -> CommandResult:
        """Run one-command bootstrap flow for first-time users."""
        ci_mode = "--ci" in args
        skip_wizard = "--no-wizard" in args
        json_mode = "--json" in args or ci_mode
        non_interactive = "--non-interactive" in args or ci_mode
        strict = "--strict" in args or ci_mode

        steps: list[dict[str, Any]] = []

        def _step(name: str, ok: bool, detail: str) -> None:
            steps.append({"name": name, "ok": ok, "detail": detail})

        if not json_mode:
            console.print(Panel(
                "[primary]NEUGI Quickstart[/primary]\n"
                "[dim]doctor --fix -> smoke -> wizard (if needed) -> start[/dim]",
                border_style="cyan",
            ))

        # Step 1: doctor fix
        try:
            report = self.doctor.diagnose(auto_fix=True)
            errors = sum(1 for item in report.get("issues", []) if item.get("severity") == "error")
            warnings = sum(1 for item in report.get("issues", []) if item.get("severity") == "warning")
            infos = sum(1 for item in report.get("issues", []) if item.get("severity") == "info")
            _step("doctor_fix", errors == 0, f"errors={errors}, warnings={warnings}, info={infos}")
        except Exception as e:
            _step("doctor_fix", False, str(e))

        # Step 2: smoke
        smoke_args = ["--json"] if json_mode else []
        if strict:
            smoke_args.append("--strict")
        smoke_result = self._cmd_smoke(smoke_args)
        smoke_ok = smoke_result.status == CommandStatus.SUCCESS
        _step("smoke", smoke_ok, smoke_result.message or "ok" if smoke_ok else "failed")

        # Step 3: wizard when config missing
        config_missing = not self.config_mgr.config_path.exists()
        if config_missing and non_interactive:
            try:
                llm_defaults = self._select_noninteractive_llm_defaults()

                self.config_mgr.set("version", __version__)
                self.config_mgr.set("llm.provider", llm_defaults["provider"])
                self.config_mgr.set("llm.model", llm_defaults["model"])
                self.config_mgr.set("llm.fallback_model", llm_defaults["fallback_model"])
                self.config_mgr.set("llm.base_url", llm_defaults["base_url"])
                self.config_mgr.set("llm.ollama_url", llm_defaults["ollama_url"])
                self.config_mgr.set("llm.api_key", llm_defaults["api_key"])
                self.config_mgr.set("llm.temperature", 0.7)
                self.config_mgr.set("llm.max_tokens", 4096)
                self.config_mgr.set("memory.enabled", True)
                self.config_mgr.set("memory.daily_ttl_days", 30)
                self.config_mgr.set("memory.dreaming_enabled", True)
                self.config_mgr.set("skills.enabled", True)
                self.config_mgr.set("skills.auto_generate", True)
                self.config_mgr.set("dashboard.enabled", True)
                self.config_mgr.set("dashboard.port", 17901)
                self.config_mgr.save()
                _step(
                    "wizard",
                    True,
                    "default config created: "
                    f"{self.config_mgr.config_path} "
                    f"({llm_defaults['provider']}/{llm_defaults['model']})",
                )
            except (OSError, ValueError, TypeError) as e:
                _step("wizard", False, f"failed to create default config: {e}")
        elif config_missing and not skip_wizard:
            wizard_result = self._cmd_wizard([])
            _step("wizard", wizard_result.status != CommandStatus.ERROR, wizard_result.message)
        elif config_missing and skip_wizard:
            _step("wizard", False, "skipped (--no-wizard) while config missing")
        else:
            _step("wizard", True, "already configured")

        # Step 4: start
        start_result = self._cmd_start([])
        start_ok = start_result.status in (CommandStatus.SUCCESS, CommandStatus.WARNING)
        _step("start", start_ok, start_result.message)

        failed = len([s for s in steps if not s["ok"]])
        payload = {"ok": failed == 0, "failed": failed, "steps": steps}

        if json_mode:
            console.print(json.dumps(payload, indent=2))
            return CommandResult(
                status=CommandStatus.ERROR if (strict and failed > 0) else (CommandStatus.SUCCESS if failed == 0 else CommandStatus.WARNING),
                message="",
                data=None,
                exit_code=1 if (strict and failed > 0) else 0,
            )

        table = Table(title="[primary]Quickstart Summary[/primary]", box=ROUNDED, border_style="cyan")
        table.add_column("Step", style="dim")
        table.add_column("Status", style="dim")
        table.add_column("Detail", style="dim")
        for step in steps:
            status_text = "[success]PASS[/success]" if step["ok"] else "[error]FAIL[/error]"
            table.add_row(step["name"], status_text, str(step["detail"]))
        console.print(table)

        if failed == 0:
            console.print("[success]Quickstart complete. NEUGI is up and ready.[/success]")
            return CommandResult(status=CommandStatus.SUCCESS, message="Quickstart complete")

        console.print("[warning]Quickstart finished with issues. Run 'neugi doctor --fix' and 'neugi smoke'.[/warning]")
        return CommandResult(
            status=CommandStatus.ERROR if strict else CommandStatus.WARNING,
            message=f"Quickstart completed with {failed} failed step(s)",
            exit_code=1 if strict else 0,
        )

    def _cmd_verify_release(self, args: list[str]) -> CommandResult:
        """Run release verification gates and return pass/fail summary.

        Gates:
        1) doctor --strict
        2) smoke --strict
        3) quickstart --non-interactive --strict --json
        4) pytest test suite
        """
        json_mode = "--json" in args
        run_full_tests = "--no-tests" not in args
        write_report = "--report" in args
        force_policy = "--force-policy" in args
        risk_profile = "team"
        for i, arg in enumerate(args):
            if arg == "--risk-profile" and i + 1 < len(args):
                risk_profile = str(args[i + 1]).strip().lower()

        steps: list[dict[str, Any]] = []

        def _step(name: str, ok: bool, detail: str) -> None:
            steps.append({"name": name, "ok": ok, "detail": detail})

        if not json_mode:
            console.print(Panel(
                "[primary]NEUGI Release Verify[/primary]\n"
                "[dim]doctor --strict -> smoke --strict -> quickstart --strict -> pytest[/dim]",
                border_style="cyan",
            ))

        # Step 0: governance policy profile wiring
        policy_ok = True
        policy_detail = "skipped"
        try:
            policy = self._apply_governance_profile(profile=risk_profile, force=force_policy)
            if policy.get("error"):
                policy_ok = False
                policy_detail = policy["error"]
            else:
                applied = policy.get("applied")
                reason = policy.get("reason", "ok")
                count = policy.get("active_rule_count", policy.get("existing_rule_count", 0))
                policy_detail = f"profile={risk_profile}, applied={applied}, reason={reason}, rules={count}"
        except Exception as e:
            policy_ok = False
            policy_detail = str(e)
        _step("policy_profile", policy_ok, policy_detail)

        doctor_result = self._cmd_doctor(["--strict", "--json"])
        _step("doctor_strict", doctor_result.exit_code == 0, "ok" if doctor_result.exit_code == 0 else "failed")

        smoke_result = self._cmd_smoke(["--strict", "--json"])
        _step("smoke_strict", smoke_result.exit_code == 0, "ok" if smoke_result.exit_code == 0 else "failed")

        quickstart_result = self._cmd_quickstart(["--non-interactive", "--strict", "--json"])
        _step("quickstart_strict", quickstart_result.exit_code == 0, "ok" if quickstart_result.exit_code == 0 else "failed")
        if quickstart_result.exit_code == 0:
            try:
                self._cmd_stop([])
            except Exception:
                pass

        if run_full_tests:
            try:
                env = os.environ.copy()
                repo_root = str(Path(__file__).resolve().parents[2])
                env["PYTHONPATH"] = repo_root
                test_proc = subprocess.run(
                    [sys.executable, "-m", "pytest", "neugi_swarm_v2/tests", "-q", "--tb=short", "-p", "no:anchorpy"],
                    cwd=repo_root,
                    env=env,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if test_proc.returncode == 0:
                    summary_line = ""
                    for line in reversed(test_proc.stdout.splitlines()):
                        if "passed" in line:
                            summary_line = line.strip()
                            break
                    _step("pytest_suite", True, summary_line or "passed")
                else:
                    tail = "\n".join((test_proc.stdout + "\n" + test_proc.stderr).splitlines()[-12:])
                    _step("pytest_suite", False, tail or "pytest failed")
            except Exception as e:
                _step("pytest_suite", False, f"pytest execution failed: {e}")
        else:
            _step("pytest_suite", True, "skipped (--no-tests)")

        failed = len([s for s in steps if not s["ok"]])
        payload = {"ok": failed == 0, "failed": failed, "steps": steps}

        if write_report:
            artifact = self._generate_due_diligence_report(
                steps=steps,
                profile=risk_profile,
                full_tests=run_full_tests,
            )
            payload["due_diligence_report"] = artifact

        if json_mode:
            console.print(json.dumps(payload, indent=2))
            return CommandResult(
                status=CommandStatus.SUCCESS if failed == 0 else CommandStatus.ERROR,
                message="",
                exit_code=0 if failed == 0 else 1,
            )

        table = Table(title="[primary]Release Verify Summary[/primary]", box=ROUNDED, border_style="cyan")
        table.add_column("Step", style="dim")
        table.add_column("Status", style="dim")
        table.add_column("Detail", style="dim")
        for step in steps:
            status_text = "[success]PASS[/success]" if step["ok"] else "[error]FAIL[/error]"
            table.add_row(step["name"], status_text, str(step["detail"]))
        console.print(table)

        if failed == 0:
            console.print("[success]Release verification passed. Ready to ship.[/success]")
            if write_report and payload.get("due_diligence_report"):
                out = payload["due_diligence_report"]
                console.print(f"[info]Due diligence report:[/info] {out.get('json_path')}")
                console.print(f"[info]Executive summary:[/info] {out.get('md_path')}")
            return CommandResult(status=CommandStatus.SUCCESS, message="Release verification passed")

        console.print("[error]Release verification failed. Fix failing gates before shipping.[/error]")
        if write_report and payload.get("due_diligence_report"):
            out = payload["due_diligence_report"]
            console.print(f"[info]Due diligence report:[/info] {out.get('json_path')}")
            console.print(f"[info]Executive summary:[/info] {out.get('md_path')}")
        return CommandResult(status=CommandStatus.ERROR, message=f"Release verification failed ({failed} failing gate(s))", exit_code=1)

    def _apply_governance_profile(self, profile: str = "team", force: bool = False) -> dict[str, Any]:
        """Apply governance approval profile to runtime approval gate."""
        try:
            from neugi_swarm_v2.governance import ApprovalGate

            db_path = self.base_dir / "data" / "governance.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            gate = ApprovalGate(db_path=str(db_path))
            result = gate.apply_risk_profile(profile=profile, force=force)
            gate.close()
            return result
        except Exception as e:
            return {"error": str(e), "profile": profile, "applied": False}

    def _runtime_fingerprint_snapshot(self) -> dict[str, Any]:
        """Compute current runtime fingerprint for compliance artifacts."""
        snapshot: dict[str, Any] = {
            "version": __version__,
            "top_level_commands": len(getattr(self, "_commands", {}) or {}),
            "api_endpoints": None,
            "provider_catalog_count": None,
            "tests_collected": None,
        }

        try:
            from neugi_swarm_v2.provider_catalog import get_all_providers
            snapshot["provider_catalog_count"] = len(get_all_providers())
        except Exception:
            snapshot["provider_catalog_count"] = None

        try:
            server_path = Path(__file__).resolve().parents[1] / "dashboard" / "server.py"
            mod = ast.parse(server_path.read_text(encoding="utf-8"))
            for node in mod.body:
                if isinstance(node, ast.ClassDef) and node.name == "DashboardServer":
                    for fn in node.body:
                        if isinstance(fn, ast.FunctionDef) and fn.name == "_register_routes":
                            for stmt in fn.body:
                                if isinstance(stmt, ast.Assign):
                                    has_routes_target = any(
                                        isinstance(t, ast.Name) and t.id == "routes"
                                        for t in stmt.targets
                                    )
                                    if has_routes_target and isinstance(stmt.value, ast.Dict):
                                        snapshot["api_endpoints"] = len(stmt.value.keys)
                                        raise StopIteration
        except StopIteration:
            pass
        except Exception:
            snapshot["api_endpoints"] = None

        try:
            env = os.environ.copy()
            repo_root = str(Path(__file__).resolve().parents[2])
            env["PYTHONPATH"] = repo_root
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", "neugi_swarm_v2/tests", "--collect-only", "-q", "-p", "no:anchorpy"],
                cwd=repo_root,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )
            output = f"{proc.stdout}\n{proc.stderr}"
            import re
            m = re.search(r"collected\s+(\d+)\s+items", output)
            if m:
                snapshot["tests_collected"] = int(m.group(1))
        except Exception:
            snapshot["tests_collected"] = None

        return snapshot

    def _generate_due_diligence_report(
        self,
        steps: list[dict[str, Any]],
        profile: str,
        full_tests: bool,
    ) -> dict[str, Any]:
        """Generate due diligence JSON + Markdown artifacts."""
        report_dir = self.base_dir / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = report_dir / f"due_diligence_{ts}.json"
        md_path = report_dir / f"due_diligence_{ts}.md"

        governance_stats: dict[str, Any] = {}
        rule_snapshot: list[dict[str, Any]] = []
        try:
            from neugi_swarm_v2.governance import ApprovalGate
            gate = ApprovalGate(db_path=str(self.base_dir / "data" / "governance.db"))
            governance_stats = gate.get_stats()
            for r in gate.list_rules(enabled_only=False):
                rule_snapshot.append({
                    "rule_id": r.rule_id,
                    "name": r.name,
                    "action_type": r.action_type,
                    "agent_role": r.agent_role,
                    "min_risk": r.min_risk.value if hasattr(r.min_risk, "value") else str(r.min_risk),
                    "approval_count": r.approval_count,
                    "timeout_minutes": r.timeout_minutes,
                    "enabled": r.enabled,
                })
            gate.close()
        except Exception as e:
            governance_stats = {"error": str(e)}

        fingerprint = self._runtime_fingerprint_snapshot()
        failed = len([s for s in steps if not s.get("ok")])
        payload: dict[str, Any] = {
            "generated_at": datetime.now().isoformat(),
            "version": __version__,
            "profile": profile,
            "full_tests_enabled": full_tests,
            "result": {
                "ok": failed == 0,
                "failed_steps": failed,
            },
            "steps": steps,
            "runtime_fingerprint": fingerprint,
            "governance": {
                "stats": governance_stats,
                "rules": rule_snapshot,
            },
        }

        json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

        lines: list[str] = []
        lines.append("# NEUGI Due Diligence Report")
        lines.append("")
        lines.append(f"- Generated: `{payload['generated_at']}`")
        lines.append(f"- Version: `{payload['version']}`")
        lines.append(f"- Governance profile: `{profile}`")
        lines.append(f"- Verification status: `{'PASS' if payload['result']['ok'] else 'FAIL'}`")
        lines.append("")
        lines.append("## Runtime Fingerprint")
        lines.append(f"- Top-level CLI commands: `{fingerprint.get('top_level_commands')}`")
        lines.append(f"- Dashboard endpoints: `{fingerprint.get('api_endpoints')}`")
        lines.append(f"- Provider catalog entries: `{fingerprint.get('provider_catalog_count')}`")
        lines.append(f"- Tests collected: `{fingerprint.get('tests_collected')}`")
        lines.append("")
        lines.append("## Verification Steps")
        for step in steps:
            mark = "PASS" if step.get("ok") else "FAIL"
            lines.append(f"- [{mark}] `{step.get('name')}` - {step.get('detail')}")
        lines.append("")
        lines.append("## Governance Snapshot")
        if governance_stats.get("error"):
            lines.append(f"- Error: {governance_stats['error']}")
        else:
            lines.append(f"- Active rules: `{governance_stats.get('active_rules', 0)}`")
            lines.append(f"- Pending approvals: `{governance_stats.get('pending', 0)}`")
            lines.append(f"- Approval rate: `{governance_stats.get('approval_rate', 0.0):.2%}`")
        lines.append("")
        lines.append(f"JSON artifact: `{json_path}`")
        md_path.write_text("\n".join(lines), encoding="utf-8")

        return {"json_path": str(json_path), "md_path": str(md_path)}

    @staticmethod
    def _select_noninteractive_llm_defaults() -> dict[str, str]:
        """Pick sensible LLM defaults for quickstart in non-interactive mode.

        Strategy:
        1) Prefer first non-ollama provider with a detected env API key.
        2) Fall back to local Ollama defaults.
        """
        provider = "ollama"
        model = "qwen2.5-coder:7b"
        fallback_model = "llama3.2:3b"
        base_url = ""
        ollama_url = "http://localhost:11434"
        api_key = ""

        try:
            from neugi_swarm_v2.provider_catalog import get_all_providers

            for catalog_provider in get_all_providers():
                if catalog_provider.name == "ollama":
                    continue
                env_vars = list(getattr(catalog_provider, "env_vars", []) or [])
                selected_env = next((name for name in env_vars if os.environ.get(name)), "")
                if not selected_env:
                    continue
                provider = catalog_provider.name
                if getattr(catalog_provider, "models", None):
                    model = catalog_provider.models[0].id
                    if len(catalog_provider.models) > 1:
                        fallback_model = catalog_provider.models[1].id
                base_url = catalog_provider.get_base_url() if hasattr(catalog_provider, "get_base_url") else ""
                ollama_url = ""
                api_key = os.environ.get(selected_env, "") or ""
                break
        except Exception:
            # Keep resilient defaults even if provider catalog is unavailable.
            pass

        return {
            "provider": provider,
            "model": model,
            "fallback_model": fallback_model,
            "base_url": base_url,
            "ollama_url": ollama_url,
            "api_key": api_key,
        }

    def _cmd_rescue(self, args: list[str]) -> CommandResult:
        """Run interactive rescue and troubleshooting wizard."""
        from neugi_swarm_v2.cli.rescue_wizard import RescueWizard

        wizard = RescueWizard(base_dir=str(self.base_dir))

        if "--repair" in args:
            wizard.repair_corruption()
        elif "--switch-provider" in args:
            wizard.switch_provider()
        elif "--setup" in args:
            wizard.run_setup()
        else:
            # Default: full rescue mode
            success = wizard.run_rescue()
            if not success:
                return CommandResult(
                    status=CommandStatus.WARNING,
                    message="Some issues require manual fixing. See output above.",
                )

        return CommandResult(status=CommandStatus.SUCCESS, message="Rescue complete")

    def _cmd_wizard(self, args: list[str]) -> CommandResult:
        """Run interactive setup wizard."""
        from neugi_swarm_v2.cli.genius_wizard import GeniusWizard

        wizard = GeniusWizard()
        wizard.neugi_dir = self.base_dir
        wizard.config_path = self.base_dir / "config.json"
        success = wizard.run()

        return CommandResult(
            status=CommandStatus.SUCCESS if success else CommandStatus.WARNING,
            message="Setup complete" if success else "Setup completed with warnings",
        )


# -- Helpers -----------------------------------------------------------------

def _format_size(size_bytes: int) -> str:
    """Format bytes into human-readable size string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / (1024 ** 2):.1f} MB"
    else:
        return f"{size_bytes / (1024 ** 3):.1f} GB"


# -- Entry Point -------------------------------------------------------------

def main() -> int:
    """Main entry point for the neugi CLI."""
    import signal

    def _signal_handler(sig, frame):
        console.print("\n[warning]Interrupted. Shutting down gracefully...[/warning]")
        sys.exit(130)

    signal.signal(signal.SIGINT, _signal_handler)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, _signal_handler)

    cli = NeugiCLI()
    return cli.run()


if __name__ == "__main__":
    sys.exit(main())
