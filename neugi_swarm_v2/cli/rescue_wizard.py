"""
NEUGI v2 Zero-Knowledge Rescue & Setup Wizard
===============================================
For users who know nothing about terminals, Python, or AI.

The Wizard DETECTS your system state and tells you EXACTLY what to do.
No memorizing commands. No editing JSON files. No Googling.

Usage:
    from cli.rescue_wizard import RescueWizard
    
    wizard = RescueWizard()
    wizard.run_setup()      # First-time: "Just press Enter"
    wizard.run_rescue()     # Broken? "I'll figure it out"
    wizard.system_check()   # What's wrong? Full report.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class WizardError(Exception):
    """Raised when the wizard encounters an unrecoverable error."""
    pass


class RescueWizard:
    """
    NEUGI Rescue & Setup Wizard — Zero Knowledge Required.
    
    Philosophy:
        1. DETECT first, ask later. We check what's on your system.
        2. SENSIBLE defaults. Press Enter to accept our recommendation.
        3. EXACT commands. Copy-paste what we show you, don't guess.
        4. NEVER leave you stuck. If we can't fix it, we tell you WHO can.
    """

    def __init__(self, base_dir: str | None = None):
        self.base_dir = Path(base_dir or os.environ.get("NEUGI_DIR", "~/.neugi")).expanduser()
        self.config_path = self.base_dir / "config.json"
        self._platform = platform.system().lower()  # windows, darwin, linux
        self._is_termux = "TERMUX_VERSION" in os.environ

    # ==================== PUBLIC ENTRY POINTS ====================

    def run_setup(self) -> bool:
        """
        First-time guided setup. Assumes ZERO knowledge.
        
        Flow:
            1. Check Python version (must be 3.10+)
            2. Check if Ollama installed
            3. If Ollama + models available → recommend local
            4. If no Ollama → offer cloud API key setup
            5. Auto-create directories
            6. Save config
            7. Test connection
        
        Returns:
            True if ready to chat
        """
        try:
            from neugi_swarm_v2.cli.genius_wizard import GeniusWizard

            wizard = GeniusWizard()
            wizard.neugi_dir = self.base_dir
            wizard.config_path = self.config_path
            return wizard.run()
        except Exception as exc:
            self._print_warning(f"Advanced setup wizard unavailable, using rescue setup: {exc}")

        self._print_header("NEUGI Setup Wizard")
        self._print("I'll check your system and get NEUGI running. Just press Enter to accept my suggestions.")

        # Step 1: Python check
        py_ok, py_msg = self._check_python()
        if not py_ok:
            self._print_error(py_msg)
            self._show_python_install_guide()
            return False
        self._print_success(f"Python {py_msg}")

        # Step 2: Detect what's available
        self._print_info("Detecting your system...")
        ollama_status = self._check_ollama_installed()
        installed_models = self._list_ollama_models() if ollama_status["installed"] else []
        has_api_key = bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"))

        # Step 3: Recommend setup path
        if ollama_status["installed"] and installed_models:
            self._print_success(f"Ollama found with {len(installed_models)} model(s)")
            recommended = self._recommend_local_model(installed_models)
            self._setup_local(recommended)
        elif ollama_status["installed"] and not installed_models:
            self._print_warning("Ollama is installed but has no models yet")
            if self._ask_yes_no("Download a small model (~4GB)? This lets NEUGI work offline."):
                self._pull_recommended_model()
                self._setup_local("qwen2.5-coder:7b")
            else:
                self._setup_cloud()
        elif has_api_key:
            self._print_info("No Ollama found, but API key detected")
            self._setup_cloud()
        else:
            self._print_info("No local AI and no API key found")
            self._ask_user_preference()

        # Step 4: Create directories
        self._ensure_directories()

        # Step 5: Test
        return self._test_and_finish()

    def run_rescue(self) -> bool:
        """
        Interactive rescue mode. Auto-detects and fixes issues.
        
        Returns:
            True if system is healthy after rescue
        """
        self._print_header("NEUGI Rescue Mode")
        self._print("Scanning your system for issues...")

        report = self.system_check()
        critical = [i for i in report["issues"] if i["severity"] == "critical"]
        warnings = [i for i in report["issues"] if i["severity"] == "warning"]

        if not report["issues"]:
            self._print_success("No issues found! NEUGI should work fine.")
            return True

        self._print(f"\nFound {len(critical)} critical issue(s), {len(warnings)} warning(s)")

        # Auto-fix what we can
        fixed = []
        for issue in report["issues"]:
            if issue.get("auto_fixable"):
                self._print_info(f"Fixing: {issue['message']}")
                if self._apply_fix(issue):
                    fixed.append(issue["message"])

        if fixed:
            self._print_success(f"Fixed {len(fixed)} issue(s) automatically")

        # Show remaining issues with exact commands
        remaining = [i for i in report["issues"] if i["message"] not in fixed]
        if remaining:
            self._print_warning(f"\n{len(remaining)} issue(s) need your attention:")
            for issue in remaining:
                self._print_issue_with_fix(issue)

        return len(critical) == 0 or len([i for i in critical if i["message"] not in fixed]) == 0

    def system_check(self) -> dict[str, Any]:
        """
        Non-interactive full system check.
        
        Returns:
            Dict with: python_ok, ollama_ok, config_ok, dirs_ok, 
                      models_available, issues[], fixes[]
        """
        issues = []

        # Python check
        py_ok, py_ver = self._check_python()
        if not py_ok:
            issues.append({
                "severity": "critical",
                "message": f"Python {py_ver} found, but 3.10+ required",
                "auto_fixable": False,
                "fix": "Install Python 3.10 or newer from python.org",
            })

        # Ollama check
        ollama = self._check_ollama_installed()
        if not ollama["installed"]:
            issues.append({
                "severity": "warning",
                "message": "Ollama not found",
                "auto_fixable": False,
                "fix": "Install from ollama.com or use cloud API instead",
            })
        elif not ollama["running"]:
            issues.append({
                "severity": "critical",
                "message": "Ollama installed but not running",
                "auto_fixable": True,
                "fix_command": self._get_ollama_start_command(),
            })

        # Config check
        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    cfg = json.load(f)
                if "llm" not in cfg or not cfg["llm"].get("model"):
                    issues.append({
                        "severity": "critical",
                        "message": "Config exists but no model configured",
                        "auto_fixable": True,
                        "fix": "Run 'neugi wizard' to set up",
                    })
            except json.JSONDecodeError:
                issues.append({
                    "severity": "critical",
                    "message": "Config file is corrupted (invalid JSON)",
                    "auto_fixable": True,
                    "fix": "Will restore defaults",
                })
        else:
            issues.append({
                "severity": "warning",
                "message": "No config file found",
                "auto_fixable": True,
                "fix": "Run 'neugi wizard' to create",
            })

        # Directory check
        for name in ["skills", "memory", "sessions"]:
            if not (self.base_dir / name).exists():
                issues.append({
                    "severity": "warning",
                    "message": f"Directory missing: {name}",
                    "auto_fixable": True,
                    "fix": f"mkdir -p {self.base_dir / name}",
                })

        # Model availability check
        models = self._list_ollama_models()
        cfg_model = self._get_configured_model()
        if cfg_model and models and cfg_model not in models:
            issues.append({
                "severity": "warning",
                "message": f"Configured model '{cfg_model}' not found in Ollama",
                "auto_fixable": False,
                "fix": f"ollama pull {cfg_model}",
            })

        return {
            "python_ok": py_ok,
            "python_version": py_ver,
            "ollama_ok": ollama["installed"] and ollama["running"],
            "ollama_models": models,
            "config_ok": self.config_path.exists(),
            "issues": issues,
            "healthy": len([i for i in issues if i["severity"] == "critical"]) == 0,
        }

    def check_health(self) -> dict[str, Any]:
        """Quick health check returning essential status flags."""
        py_ok, _ = self._check_python()
        ollama = self._check_ollama_installed()
        config_valid = False
        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    cfg = json.load(f)
                config_valid = "llm" in cfg and bool(cfg["llm"].get("model"))
            except Exception:
                config_valid = False
        return {
            "python_ok": py_ok,
            "ollama_running": ollama["installed"] and ollama["running"],
            "config_valid": config_valid,
            "healthy": py_ok and config_valid,
        }

    def _load_current_config(self) -> dict[str, Any]:
        """Load current config file, returning empty dict on missing or corruption."""
        if not self.config_path.exists():
            return {}
        try:
            with open(self.config_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _setup_directories(self) -> bool:
        """Create required NEUGI directories."""
        for name in ["skills", "memory", "sessions", "agents", "plugins", "workflows"]:
            (self.base_dir / name).mkdir(parents=True, exist_ok=True)
        return True

    def _save_config(self, provider: str, model: str, features: dict[str, Any]) -> None:
        """Save NEUGI configuration to disk."""
        base_url = ""
        ollama_url = "http://localhost:11434"
        if provider == "openai":
            base_url = "https://api.openai.com"
            ollama_url = ""
        elif provider == "anthropic":
            base_url = "https://api.anthropic.com"
            ollama_url = ""
        config = {
            "version": "2.1.3",
            "llm": {
                "provider": provider,
                "model": model,
                "fallback_model": "llama3.2:3b" if provider == "ollama" else "",
                "base_url": base_url,
                "ollama_url": ollama_url,
                "api_key": "",
                "temperature": 0.7,
                "max_tokens": 4096,
            },
            "memory": {"enabled": features.get("memory", True), "daily_ttl_days": 30, "dreaming_enabled": features.get("dreaming", True)},
            "skills": {"enabled": features.get("skills", True), "auto_generate": True},
            "channels": {"enabled": False},
            "dashboard": {"enabled": True, "port": 17901},
        }
        self.base_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

    def _update_config_field(self, key: str, value: Any) -> None:
        """Update a single field in the LLM config section."""
        cfg = self._load_current_config()
        if "llm" not in cfg:
            cfg["llm"] = {}
        cfg["llm"][key] = value
        self.base_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)

    def _restore_default_config(self) -> None:
        """Restore config to factory defaults."""
        self._save_config("ollama", "qwen2.5-coder:7b", {"memory": True, "skills": True, "dreaming": True})

    def _check_directories(self) -> list[str]:
        """Check for missing directories and return list of issue descriptions."""
        issues: list[str] = []
        for name in ["skills", "memory", "sessions"]:
            if not (self.base_dir / name).exists():
                issues.append(f"Directory missing: {name}")
        return issues

    def _check_config(self) -> list[str]:
        """Check config file for issues and return list of issue descriptions."""
        issues: list[str] = []
        if not self.config_path.exists():
            issues.append("Config file missing")
            return issues
        try:
            with open(self.config_path, encoding="utf-8") as f:
                cfg = json.load(f)
            if "llm" not in cfg or not cfg["llm"].get("model"):
                issues.append("Config missing model")
        except Exception:
            issues.append("Config file corrupted")
        return issues

    def _auto_fix(self, issues: list[str], category: str) -> list[str]:
        """Attempt to auto-fix detected issues. Returns list of fixes applied."""
        fixes: list[str] = []
        if category == "config":
            for issue in issues:
                if "missing" in issue.lower() or "corrupted" in issue.lower():
                    self._restore_default_config()
                    fixes.append("Restored default config")
        elif category == "directories":
            for issue in issues:
                if "Directory missing" in issue:
                    name = issue.split(":")[-1].strip()
                    (self.base_dir / name).mkdir(parents=True, exist_ok=True)
                    fixes.append(f"Created directory: {name}")
        return fixes

    def switch_provider(self) -> bool:
        """Interactive provider switching with connection test."""
        self._print_header("Switch Provider")

        current = self._get_current_provider()
        self._print(f"Current: {current.get('provider', 'unknown')} / {current.get('model', 'unknown')}")

        # Detect available options
        ollama_ok = self._check_ollama_installed()["running"]
        has_openai = bool(os.environ.get("OPENAI_API_KEY"))
        has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))

        options = []
        if ollama_ok:
            options.append(("ollama", "Local Ollama (private, free, works offline)"))
        if has_openai:
            options.append(("openai", "OpenAI Cloud (GPT-5, requires API key)"))
        if has_anthropic:
            options.append(("anthropic", "Anthropic Cloud (Claude, requires API key)"))

        if not options:
            self._print_error("No providers available!")
            self._print("Install Ollama (ollama.com) or set OPENAI_API_KEY / ANTHROPIC_API_KEY")
            return False

        self._print("\nAvailable providers:")
        for i, (key, desc) in enumerate(options, 1):
            self._print(f"  {i}. {desc}")

        choice = self._ask_choice("Select", len(options))
        provider = options[choice - 1][0]

        if provider == "ollama":
            models = self._list_ollama_models()
            model = models[0] if models else "qwen2.5-coder:7b"
        elif provider == "openai":
            model = "gpt-5-mini"
        else:
            model = "claude-sonnet-4-20250514"

        self._save_config(provider, model, {})
        return self._test_and_finish()

    def repair_corruption(self) -> bool:
        """Detect and repair corrupted files."""
        self._print_header("Corruption Repair")
        repaired = []

        # Config JSON
        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    json.load(f)
            except json.JSONDecodeError:
                self._print_warning("Config file corrupted. Restoring defaults...")
                self._restore_default_config()
                repaired.append("config.json")

        # Directories
        for name in ["skills", "memory", "sessions", "agents", "plugins", "workflows"]:
            path = self.base_dir / name
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
                repaired.append(f"directory: {name}")

        if repaired:
            self._print_success(f"Repaired: {', '.join(repaired)}")
        else:
            self._print_success("No corruption detected")

        return len(repaired) > 0

    # ==================== SETUP HELPERS ====================

    def _setup_local(self, model: str) -> None:
        """Setup with local Ollama model."""
        features = {"memory": True, "skills": True, "dreaming": True}
        self._save_config("ollama", model, features)
        self._print_success(f"Configured for local Ollama with model: {model}")

    def _setup_cloud(self) -> None:
        """Setup with cloud API."""
        self._print_info("Let's set up a cloud provider.")
        self._print("Your API key is kept locally and never sent anywhere except the provider.")

        if os.environ.get("OPENAI_API_KEY"):
            provider = "openai"
            model = "gpt-5-mini"
            self._print("OPENAI_API_KEY detected in environment")
        elif os.environ.get("ANTHROPIC_API_KEY"):
            provider = "anthropic"
            model = "claude-sonnet-4-20250514"
            self._print("ANTHROPIC_API_KEY detected in environment")
        else:
            self._print("\nNo API key found in environment.")
            self._print("Get one from:")
            self._print("  OpenAI:  https://platform.openai.com/api-keys")
            self._print("  Anthropic: https://console.anthropic.com/settings/keys")

            provider = self._ask_choice_str("Provider", ["openai", "anthropic"])
            import getpass
            key = getpass.getpass("  Paste your API key: ").strip()

            if provider == "openai":
                os.environ["OPENAI_API_KEY"] = key
                model = "gpt-5-mini"
            else:
                os.environ["ANTHROPIC_API_KEY"] = key
                model = "claude-sonnet-4-20250514"

        features = {"memory": True, "skills": True, "dreaming": False}
        self._save_config(provider, model, features)
        self._print_success(f"Configured for {provider} cloud with model: {model}")

    def _ask_user_preference(self) -> None:
        """Ask user what they prefer when nothing is detected."""
        self._print("\nHow would you like to run NEUGI?")
        self._print("  1. Local (free, private, needs ~4GB download)")
        self._print("  2. Cloud (easiest, requires API key)")

        choice = self._ask_choice("Select", 2)
        if choice == 1:
            self._print_info("\nTo install Ollama:")
            self._print(self._get_ollama_install_command())
            self._print("\nAfter installing, run this wizard again: neugi wizard")
            # Still create a basic config so they can try cloud fallback
            self._save_config("ollama", "qwen2.5-coder:7b", {"memory": True, "skills": True})
        else:
            self._setup_cloud()

    def _pull_recommended_model(self) -> None:
        """Guide user to pull a recommended model."""
        model = "qwen2.5-coder:7b"
        self._print_info(f"Downloading {model} (~4GB)...")
        self._print("Run this command in a separate terminal:")
        self._print(f"  ollama pull {model}")
        self._print("Then come back here and press Enter...")
        input()

    def _recommend_local_model(self, available: list[str]) -> str:
        """Pick the best model from what's installed."""
        # Priority order
        priority = ["qwen3.5", "qwen2.5-coder", "deepseek-coder", "llama3.2", "llama3.1", "mistral"]
        for pref in priority:
            for model in available:
                if pref in model.lower():
                    return model
        return available[0]

    # ==================== SYSTEM DETECTION ====================

    def _check_python(self) -> tuple[bool, str]:
        """Check Python version. Returns (ok, version_string)."""
        major, minor = sys.version_info[:2]
        ver_str = f"{major}.{minor}"
        return (major == 3 and minor >= 10) or major > 3, ver_str

    def _check_ollama_installed(self) -> dict[str, Any]:
        """Check Ollama installation status."""
        result = {"installed": False, "running": False, "version": ""}

        # Check if ollama command exists
        ollama_cmd = "ollama.exe" if self._platform == "windows" else "ollama"
        try:
            subprocess.run([ollama_cmd, "--version"], capture_output=True, timeout=5, check=True)
            result["installed"] = True
        except Exception:
            # Also check common install paths
            paths = []
            if self._platform == "windows":
                paths = [
                    Path.home() / "AppData" / "Local" / "Programs" / "Ollama" / "ollama.exe",
                    Path("C:/Program Files/Ollama/ollama.exe"),
                ]
            elif self._platform == "darwin":
                paths = [Path("/usr/local/bin/ollama"), Path("/opt/homebrew/bin/ollama")]
            else:
                paths = [Path("/usr/local/bin/ollama"), Path("/usr/bin/ollama")]

            for path in paths:
                if path.exists():
                    result["installed"] = True
                    break

        # Check if running
        if result["installed"]:
            try:
                req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
                with urllib.request.urlopen(req, timeout=3) as resp:
                    if resp.status == 200:
                        result["running"] = True
            except Exception:
                pass

        return result

    def _list_ollama_models(self) -> list[str]:
        """List models available in Ollama."""
        try:
            req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
                return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
        except Exception:
            return []

    def _get_configured_model(self) -> str:
        """Get currently configured model."""
        if not self.config_path.exists():
            return ""
        try:
            with open(self.config_path) as f:
                cfg = json.load(f)
            return cfg.get("llm", {}).get("model", "")
        except Exception:
            return ""

    def _get_current_provider(self) -> dict[str, str]:
        """Get current provider config."""
        if not self.config_path.exists():
            return {}
        try:
            with open(self.config_path) as f:
                cfg = json.load(f)
            return cfg.get("llm", {})
        except Exception:
            return {}

    # ==================== FIX HELPERS ====================

    def _apply_fix(self, issue: dict[str, Any]) -> bool:
        """Apply an auto-fixable issue."""
        msg = issue["message"]

        if "Config file missing" in msg or "Config file is corrupted" in msg:
            self._restore_default_config()
            return True

        if "Directory missing" in msg:
            dir_name = msg.split(": ")[-1]
            (self.base_dir / dir_name).mkdir(parents=True, exist_ok=True)
            return True

        if "Ollama installed but not running" in msg:
            self._print_info("Attempting to start Ollama...")
            cmd = self._get_ollama_start_command()
            self._print(f"Run: {cmd}")
            return False  # Can't auto-start, needs user

        return False

    def _print_issue_with_fix(self, issue: dict[str, Any]) -> None:
        """Print an issue with clear fix instructions."""
        severity = issue["severity"].upper()
        self._print(f"\n  [{severity}] {issue['message']}")

        if issue.get("fix_command"):
            self._print(f"  Fix: {issue['fix_command']}")
        elif issue.get("fix"):
            self._print(f"  Fix: {issue['fix']}")

    # ==================== OS-SPECIFIC COMMANDS ====================

    def _get_ollama_install_command(self) -> str:
        """Get install command for user's OS."""
        if self._platform == "windows":
            return (
                "Download from https://ollama.com/download/windows\n"
                "  Just double-click the .exe installer — no WSL needed!\n"
                "  After install, 'ollama' works in both CMD and PowerShell."
            )
        elif self._platform == "darwin":
            return "brew install ollama   # or download from ollama.com/download/mac"
        elif self._is_termux:
            return "pkg install ollama"
        else:
            return "curl -fsSL https://ollama.com/install.sh | sh"

    def _get_ollama_start_command(self) -> str:
        """Get start command for user's OS."""
        if self._platform == "windows":
            return "Start Ollama from the Start Menu, or run: ollama serve"
        elif self._platform == "darwin":
            return "ollama serve   # or start from Applications"
        else:
            return "ollama serve   # or: sudo systemctl start ollama"

    def _show_python_install_guide(self) -> None:
        """Show Python install instructions."""
        self._print_error("\nPython 3.10 or newer is required.")
        if self._platform == "windows":
            self._print("Install from: https://python.org/downloads")
            self._print("Make sure to check 'Add Python to PATH' during install.")
        elif self._platform == "darwin":
            self._print("brew install python@3.12")
        else:
            self._print("sudo apt install python3.12   # Ubuntu/Debian")
            self._print("sudo dnf install python3.12   # Fedora")

    # ==================== CONFIG ====================

    def _save_config(self, provider: str, model: str, features: dict[str, bool]) -> None:
        """Save configuration."""
        base_url = ""
        ollama_url = "http://localhost:11434"
        if provider == "openai":
            base_url = "https://api.openai.com"
            ollama_url = ""
        elif provider == "anthropic":
            base_url = "https://api.anthropic.com"
            ollama_url = ""

        config = {
            "version": "2.1.3",
            "llm": {
                "provider": provider,
                "model": model,
                "fallback_model": "llama3.2:3b" if provider == "ollama" else "",
                "base_url": base_url,
                "ollama_url": ollama_url,
                "api_key": "",  # Loaded from env
                "temperature": 0.7,
                "max_tokens": 4096,
            },
            "memory": {
                "enabled": features.get("memory", True),
                "daily_ttl_days": 30,
                "dreaming_enabled": features.get("dreaming", True),
            },
            "skills": {
                "enabled": features.get("skills", True),
                "auto_generate": True,
            },
            "channels": {"enabled": False},
            "dashboard": {"enabled": True, "port": 17901},
        }

        self.base_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        self._print(f"Config saved to {self.config_path}")

    def _restore_default_config(self) -> None:
        """Restore default configuration."""
        self._save_config("ollama", "qwen2.5-coder:7b", {"memory": True, "skills": True, "dreaming": True})

    def _ensure_directories(self) -> None:
        """Create required directories."""
        for name in ["skills", "memory", "sessions", "agents", "plugins", "workflows"]:
            (self.base_dir / name).mkdir(parents=True, exist_ok=True)

    def _test_and_finish(self) -> bool:
        """Test connection and finish."""
        self._print_info("\nTesting connection...")

        cfg = self._get_current_provider()
        provider = cfg.get("provider", "ollama")

        if provider == "ollama":
            ollama = self._check_ollama_installed()
            if not ollama["running"]:
                self._print_warning("Ollama is not running yet.")
                self._print(f"Start it with: {self._get_ollama_start_command()}")
                self._print("Then run: neugi chat")
                return False

            model = cfg.get("model", "")
            models = self._list_ollama_models()
            if model and models and model not in models:
                self._print_warning(f"Model '{model}' not downloaded yet.")
                self._print(f"Run: ollama pull {model}")
                return False

        self._print_success("Setup complete! Run 'neugi chat' to start.")
        return True

    # ==================== UI HELPERS ====================

    def _print(self, text: str) -> None:
        print(text)

    def _print_header(self, text: str) -> None:
        print(f"\n{'=' * 55}")
        print(f"  {text}")
        print(f"{'=' * 55}")

    def _print_success(self, text: str) -> None:
        print(f"  [OK] {text}")

    def _print_warning(self, text: str) -> None:
        print(f"  [WARN] {text}")

    def _print_error(self, text: str) -> None:
        print(f"  [ERR] {text}")

    def _print_info(self, text: str) -> None:
        print(f"  [INFO] {text}")

    def _ask_yes_no(self, question: str, default: bool = True) -> bool:
        default_str = "Y/n" if default else "y/N"
        response = input(f"  {question} [{default_str}]: ").strip().lower()
        if not response:
            return default
        return response in ("y", "yes")

    def _ask_choice(self, question: str, max_choice: int) -> int:
        while True:
            try:
                response = input(f"  {question} [1-{max_choice}]: ").strip()
                choice = int(response)
                if 1 <= choice <= max_choice:
                    return choice
            except ValueError:
                pass
            print("  Invalid choice, please try again.")

    def _ask_choice_str(self, question: str, options: list[str]) -> str:
        for i, opt in enumerate(options, 1):
            print(f"  {i}. {opt}")
        choice = self._ask_choice(question, len(options))
        return options[choice - 1]


__all__ = ["RescueWizard"]
