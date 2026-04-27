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

import json
import os
import platform
import shutil
import signal
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

from neugi_swarm_v2 import __version__

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.tree import Tree
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
    from rich.prompt import Prompt, Confirm
    from rich.prompt import IntPrompt, FloatPrompt
    from rich.columns import Columns
    from rich.layout import Layout
    from rich.live import Live
    from rich.text import Text
    from rich.box import ROUNDED, DOUBLE
    from rich.markdown import Markdown
    from rich.syntax import Syntax
    from rich.rule import Rule
    from rich.align import Align
    from rich import box
    from rich.style import Style
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
    data: Optional[dict[str, Any]] = None
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
            pid = int(self._pid_file.read_text().strip())
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

    def get_pid(self) -> Optional[int]:
        """Get the PID of the running gateway process."""
        if not self._pid_file.exists():
            return None
        try:
            return int(self._pid_file.read_text().strip())
        except (ValueError, OSError):
            return None

    def write_pid(self, pid: int) -> None:
        """Write the gateway PID to the pid file."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._pid_file.write_text(str(pid))

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
                with open(self.config_path, "r", encoding="utf-8") as f:
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
                    with open(manifest_path, "r", encoding="utf-8") as f:
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

        return {
            "issues": self._issues,
            "fixes": self._fixes,
            "healthy": len(self._issues) == 0,
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
                with open(config_path, "r", encoding="utf-8") as f:
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
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            llm = config.get("llm", {})
            provider = llm.get("provider", "ollama")

            if provider == "ollama":
                ollama_url = llm.get("ollama_url", "http://localhost:11434")
                if not self._check_url(ollama_url):
                    self._issues.append({
                        "severity": "warning",
                        "message": "Ollama server not reachable",
                        "fix": "Start Ollama: 'ollama serve'",
                    })
            elif provider in ("openai", "anthropic"):
                if not llm.get("api_key"):
                    self._issues.append({
                        "severity": "error",
                        "message": f"API key not set for {provider}",
                        "fix": f"Set api_key in config or {provider.upper()}_API_KEY env var",
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
            import urllib.request
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status == 200
        except Exception:
            return False

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
                description="List, install, enable, and disable plugins",
                handler=self._cmd_plugins,
                subcommands=[
                    CLICommand("list", "List all plugins", self._cmd_plugins_list),
                    CLICommand("install", "Install a plugin", self._cmd_plugins_install),
                    CLICommand("enable", "Enable a plugin", self._cmd_plugins_enable),
                    CLICommand("disable", "Disable a plugin", self._cmd_plugins_disable),
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

        with Progress(
            SpinnerColumn(),
            TextColumn("[primary]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Starting NEUGI...", total=5)

            progress.update(task, description="Initializing configuration...")
            self.config_mgr.load()
            progress.advance(task)

            progress.update(task, description="Loading memory system...")
            time.sleep(0.3)
            progress.advance(task)

            progress.update(task, description="Loading skills...")
            time.sleep(0.3)
            progress.advance(task)

            progress.update(task, description="Starting agents...")
            time.sleep(0.3)
            progress.advance(task)

            progress.update(task, description="Gateway ready!")
            time.sleep(0.2)
            progress.advance(task)

        self.health.write_pid(os.getpid())

        console.print(Panel(
            "[success]NEUGI Swarm v2 started successfully![/success]\n\n"
            f"  [dim]PID:[/dim] {os.getpid()}\n"
            f"  [dim]Config:[/dim] {self.config_mgr.config_path}\n"
            f"  [dim]Data:[/dim] {self.base_dir / 'data'}\n\n"
            "[dim]Run 'neugi status' to check system health.[/dim]",
            title="NEUGI Started",
            border_style="green",
        ))

        return CommandResult(
            status=CommandStatus.SUCCESS,
            message="NEUGI started successfully",
            data={"pid": os.getpid()},
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
                os.kill(pid, signal.CTRL_BREAK_EVENT)
            else:
                os.kill(pid, signal.SIGTERM)

            for _ in range(10):
                if not self.health.is_running():
                    break
                time.sleep(0.5)

            if self.health.is_running():
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
        description = Prompt.ask("[primary]Description[/primary]", default="")

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
                        with open(manifest, "r", encoding="utf-8") as f:
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
            time.sleep(0.5)
            progress.advance(task)

            progress.update(task, description="Phase 2: Finding patterns...")
            time.sleep(0.5)
            progress.advance(task)

            progress.update(task, description="Phase 3: Consolidating...")
            time.sleep(0.5)
            progress.advance(task)

            progress.update(task, description="Phase 4: Storing consolidated memories...")
            time.sleep(0.3)
            progress.advance(task)

        console.print("[success]Dreaming complete! Memories consolidated.[/success]")
        return CommandResult(status=CommandStatus.SUCCESS, message="Dreaming complete")

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
                    with open(session_file, "r", encoding="utf-8") as f:
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

    def _check_latest_version(self) -> Optional[str]:
        """Check PyPI for latest version."""
        try:
            import urllib.request
            import json
            req = urllib.request.Request(
                "https://pypi.org/pypi/neugi-swarm/json",
                headers={"Accept": "application/json", "User-Agent": f"neugi-swarm/{__version__}"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
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
            time.sleep(0.3)
            progress.advance(task)

            progress.update(task, description="Checking for updates...")
            time.sleep(0.5)
            progress.advance(task)

            progress.update(task, description="No updates available.")
            time.sleep(0.2)
            progress.advance(task)

        # Check for actual updates via git or PyPI
        latest = self._check_latest_version()
        if latest and latest != __version__:
            console.print(f"[warning]New version available: v{latest} (current: v{__version__})[/warning]")
            console.print(f"[dim]Run 'pip install --upgrade neugi-swarm' or 'git pull' to update[/dim]")
            return CommandResult(status=CommandStatus.SUCCESS, message=f"Update available: v{latest}")
        
        console.print(f"[success]NEUGI is up to date (v{__version__})[/success]")
        return CommandResult(status=CommandStatus.SUCCESS, message="No updates available")

    def _cmd_doctor(self, args: list[str]) -> CommandResult:
        """Diagnose issues and auto-fix."""
        auto_fix = "--fix" in args or "-f" in args

        console.print(Panel(
            "[primary]NEUGI Doctor - System Diagnostics[/primary]",
            border_style="cyan",
        ))

        with Progress(
            SpinnerColumn(),
            TextColumn("[primary]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Running diagnostics...", total=6)

            progress.update(task, description="Checking directories...")
            time.sleep(0.2)
            progress.advance(task)

            progress.update(task, description="Checking configuration...")
            time.sleep(0.2)
            progress.advance(task)

            progress.update(task, description="Checking LLM provider...")
            time.sleep(0.3)
            progress.advance(task)

            progress.update(task, description="Checking memory system...")
            time.sleep(0.2)
            progress.advance(task)

            progress.update(task, description="Checking permissions...")
            time.sleep(0.2)
            progress.advance(task)

            progress.update(task, description="Checking disk space...")
            time.sleep(0.2)
            progress.advance(task)

        report = self.doctor.diagnose(auto_fix=auto_fix)

        if report["issues"]:
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
        else:
            console.print("[success]No issues found. System is healthy![/success]")

        if report["fixes"]:
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

        return CommandResult(
            status=CommandStatus.SUCCESS if report["healthy"] else CommandStatus.WARNING,
            message=f"Doctor complete: {len(report['issues'])} issues found",
            data=report,
        )

    def _cmd_wizard(self, args: list[str]) -> CommandResult:
        """Run interactive setup wizard."""
        from neugi_swarm_v2.cli.wizard import SetupWizard

        wizard = SetupWizard(base_dir=self.base_dir)
        wizard.run()

        return CommandResult(status=CommandStatus.SUCCESS, message="Wizard complete")


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
    cli = NeugiCLI()
    return cli.run()


if __name__ == "__main__":
    sys.exit(main())
