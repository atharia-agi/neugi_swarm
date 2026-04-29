"""
NEUGI v2 Smart Setup Wizard — AI-Level Zero-Knowledge Support
===============================================================

This wizard thinks for the user. It auto-detects everything, makes smart
recommendations, and only asks when absolutely necessary.

Principle: "Don't make me think" — The user should just press Enter.
"""

from __future__ import annotations

import getpass
import json
import logging
import os
import platform
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SmartWizard:
    """
    AI-level setup and rescue wizard.
    
    Detects → Recommends → Acts. Only asks the user when:
        - Multiple good options exist (e.g., 3 installed models)
        - A decision has cost (e.g., downloading 4GB)
        - We genuinely cannot know (e.g., API key)
    """

    def __init__(self, base_dir: str | None = None):
        self.base_dir = Path(base_dir or os.environ.get("NEUGI_DIR", "~/.neugi")).expanduser()
        self.config_path = self.base_dir / "config.json"
        self._platform = platform.system().lower()
        self._is_wsl = "WSL_DISTRO_NAME" in os.environ
        self._state: dict[str, Any] = {}

    # ==================== PUBLIC: SMART SETUP ====================

    def run(self) -> bool:
        """
        One-shot smart setup. User presses Enter to accept, or types to override.
        
        Returns True if NEUGI is ready to use after this.
        """
        self._banner("NEUGI Smart Setup")
        self._say("I'll check your system and set everything up. Just press Enter to accept my suggestions.")

        # Phase 1: System Scan (fully automatic)
        scan = self._scan_system()

        # Phase 2: Smart Configuration (auto-decide, user confirms)
        config = self._smart_configure(scan)

        # Phase 3: Auto-Fix & Validate
        ready = self._apply_and_test(config)

        if ready:
            self._say("\n🎉 NEUGI is ready! Type 'neugi chat' to start.")
        else:
            self._say("\n⚠️  Setup saved but needs one more step (see above).")

        return ready

    def rescue(self) -> bool:
        """Auto-detect issues and fix them without asking."""
        self._banner("NEUGI Auto-Rescue")

        scan = self._scan_system()
        fixes_applied = []
        needs_user = []

        # Auto-fix what we can
        if not scan["python_ok"]:
            needs_user.append(("CRITICAL", f"Python {scan['python_version']} too old. Need 3.10+", self._python_guide))

        if scan["ollama_installed"] and not scan["ollama_running"]:
            self._say("Starting Ollama for you...")
            if self._auto_start_ollama():
                fixes_applied.append("Started Ollama")
            else:
                needs_user.append(("FIX", "Ollama installed but not running", self._ollama_start_guide))

        if not scan["config_exists"]:
            self._say("Creating default config...")
            self._auto_create_config(scan)
            fixes_applied.append("Created default config")

        if scan["config_corrupted"]:
            self._say("Config corrupted. Restoring defaults...")
            self._auto_create_config(scan)
            fixes_applied.append("Restored default config")

        # Missing directories
        for d in ["skills", "memory", "sessions", "agents"]:
            p = self.base_dir / d
            if not p.exists():
                p.mkdir(parents=True, exist_ok=True)
                fixes_applied.append(f"Created directory: {d}")

        # Missing model
        if scan["configured_model"] and scan["ollama_running"]:
            if scan["configured_model"] not in scan["ollama_models"]:
                self._say(f"Model '{scan['configured_model']}' not found.")
                if self._ask("Download it now? (~4GB) [Y/n]:", default=True):
                    self._pull_model(scan["configured_model"])
                    fixes_applied.append(f"Pulled model: {scan['configured_model']}")
                else:
                    # Auto-switch to available model
                    if scan["ollama_models"]:
                        new_model = scan["ollama_models"][0]
                        self._update_config_model(new_model)
                        fixes_applied.append(f"Switched to available model: {new_model}")
                    else:
                        needs_user.append(("FIX", f"Model missing: {scan['configured_model']}",
                                          lambda: self._say(f"Run: ollama pull {scan['configured_model']}")))

        # Report
        if fixes_applied:
            self._say(f"\n✅ Fixed {len(fixes_applied)} issue(s) automatically:")
            for f in fixes_applied:
                self._say(f"   • {f}")

        if needs_user:
            self._say(f"\n⚠️  {len(needs_user)} issue(s) need your attention:")
            for severity, msg, guide in needs_user:
                self._say(f"   [{severity}] {msg}")
                guide()

        if not fixes_applied and not needs_user:
            self._say("\n✅ Everything looks good! No issues found.")

        return len([s for s, _, _ in needs_user if s == "CRITICAL"]) == 0

    # ==================== SMART CONFIGURATION ENGINE ====================

    def _scan_system(self) -> dict[str, Any]:
        """Full system scan. Returns everything we know."""
        self._say("\n🔍 Scanning your system...", delay=0)

        # Python
        py_major, py_minor = sys.version_info[:2]

        # Ollama
        ollama_installed = self._cmd_exists("ollama")
        ollama_running = False
        ollama_models: list[str] = []
        if ollama_installed:
            ollama_running, ollama_models = self._check_ollama_api()

        # Config
        config_exists = self.config_path.exists()
        config_corrupted = False
        configured_model = ""
        configured_provider = ""
        if config_exists:
            try:
                with open(self.config_path) as f:
                    cfg = json.load(f)
                configured_model = cfg.get("llm", {}).get("model", "")
                configured_provider = cfg.get("llm", {}).get("provider", "")
            except json.JSONDecodeError:
                config_corrupted = True

        # Cloud API keys
        has_openai = bool(os.environ.get("OPENAI_API_KEY"))
        has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))

        return {
            "python_ok": py_major == 3 and py_minor >= 10,
            "python_version": f"{py_major}.{py_minor}",
            "ollama_installed": ollama_installed,
            "ollama_running": ollama_running,
            "ollama_models": ollama_models,
            "config_exists": config_exists,
            "config_corrupted": config_corrupted,
            "configured_model": configured_model,
            "configured_provider": configured_provider,
            "has_openai_key": has_openai,
            "has_anthropic_key": has_anthropic,
        }

    def _smart_configure(self, scan: dict[str, Any]) -> dict[str, Any]:
        """
        Smart configuration engine.
        
        Decision tree:
            1. Ollama running + models → Local (best privacy/cost)
            2. Ollama running, no models → Ask to download
            3. Ollama installed, not running → Start it
            4. No Ollama + API key → Cloud
            5. No Ollama, no API key → Ask preference
        """
        self._say("\n🧠 Analyzing best setup for your system...")

        # Scenario 1: Perfect local setup
        if scan["ollama_running"] and scan["ollama_models"]:
            model = self._pick_best_model(scan["ollama_models"])
            self._say("\n💡 Recommendation: Use local Ollama")
            self._say(f"   Found {len(scan['ollama_models'])} model(s)")
            self._say(f"   Best for your system: {model}")
            if self._ask("Use this setup? [Enter = Yes]:", default=True):
                return self._make_config("ollama", model)

        # Scenario 2: Ollama running but no models
        if scan["ollama_running"] and not scan["ollama_models"]:
            self._say("\n💡 Ollama is ready but has no models yet.")
            if self._ask("Download qwen2.5-coder:7b (~4GB)? [Enter = Yes]:", default=True):
                self._pull_model("qwen2.5-coder:7b")
                return self._make_config("ollama", "qwen2.5-coder:7b")
            else:
                self._say("Okay, let's try cloud instead.")
                return self._setup_cloud(scan)

        # Scenario 3: Ollama installed but not running
        if scan["ollama_installed"] and not scan["ollama_running"]:
            self._say("\n💡 Ollama is installed but not running.")
            if self._auto_start_ollama():
                time.sleep(2)
                scan = self._scan_system()  # Re-scan
                if scan["ollama_running"]:
                    return self._smart_configure(scan)
            self._say("Couldn't auto-start Ollama.")
            self._ollama_start_guide()
            if self._ask("Try cloud instead? [Enter = Yes]:", default=True):
                return self._setup_cloud(scan)

        # Scenario 4: No Ollama but has API key
        if scan["has_openai_key"] or scan["has_anthropic_key"]:
            self._say("\n💡 No local AI found, but API key detected.")
            return self._setup_cloud(scan)

        # Scenario 5: Nothing available
        self._say("\n💡 No AI engine found on your system.")
        self._say("You have 3 options:")
        self._say("   1. Local (free, private, offline) — needs ~4GB download")
        self._say("   2. Cloud (easiest) — needs API key from OpenAI/Anthropic")
        self._say("   3. I'll decide later — create minimal config")

        choice = self._ask_choice("Pick one:", ["Local (Ollama)", "Cloud (API Key)", "Decide Later"])

        if choice == 0:
            self._say("\n📥 Installing Ollama...")
            if self._install_ollama():
                time.sleep(2)
                if self._ask("Download qwen2.5-coder:7b (~4GB)? [Enter = Yes]:", default=True):
                    self._pull_model("qwen2.5-coder:7b")
                    return self._make_config("ollama", "qwen2.5-coder:7b")
            return self._make_config("ollama", "qwen2.5-coder:7b")
        elif choice == 1:
            return self._setup_cloud(scan)
        else:
            return self._make_config("ollama", "qwen2.5-coder:7b")

    def _setup_cloud(self, scan: dict[str, Any]) -> dict[str, Any]:
        """Configure cloud provider."""
        if scan["has_openai_key"]:
            self._say("Using OpenAI (API key found)")
            return self._make_config("openai", "gpt-4o-mini")
        elif scan["has_anthropic_key"]:
            self._say("Using Anthropic (API key found)")
            return self._make_config("anthropic", "claude-3-5-sonnet-20241022")
        else:
            self._say("\n🌐 Cloud Setup")
            self._say("Get an API key from:")
            self._say("   OpenAI: https://platform.openai.com/api-keys")
            self._say("   Anthropic: https://console.anthropic.com/settings/keys")
            provider = self._ask_choice("Which provider?", ["OpenAI", "Anthropic"])
            key = getpass.getpass("   Paste your API key: ").strip()
            if provider == 0:
                os.environ["OPENAI_API_KEY"] = key
                return self._make_config("openai", "gpt-4o-mini")
            else:
                os.environ["ANTHROPIC_API_KEY"] = key
                return self._make_config("anthropic", "claude-3-5-sonnet-20241022")

    # ==================== AUTO-FIX ENGINE ====================

    def _auto_start_ollama(self) -> bool:
        """Try to start Ollama automatically."""
        try:
            if self._platform == "windows":
                # Try starting the service
                subprocess.Popen(["ollama", "serve"],
                    creationflags=subprocess.CREATE_NEW_CONSOLE if hasattr(subprocess, 'CREATE_NEW_CONSOLE') else 0,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.Popen(["ollama", "serve"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(3)
            running, _ = self._check_ollama_api()
            return running
        except Exception:
            return False

    def _install_ollama(self) -> bool:
        """Try to install Ollama automatically."""
        self._say("Attempting automatic Ollama installation...")
        try:
            if self._platform == "windows":
                # Check winget
                result = subprocess.run(["winget", "--version"], capture_output=True, timeout=5)
                if result.returncode == 0:
                    self._say("Installing via winget...")
                    subprocess.run(["winget", "install", "Ollama.Ollama",
                        "--accept-package-agreements", "--accept-source-agreements"],
                        timeout=60, check=False)
                    self._say("✅ Ollama installed! Restart your terminal.")
                    return True
                else:
                    self._say("Opening download page in browser...")
                    webbrowser.open("https://ollama.com/download/windows")
                    return False
            elif self._platform == "darwin":
                result = subprocess.run(["brew", "--version"], capture_output=True, timeout=5)
                if result.returncode == 0:
                    self._say("Installing via Homebrew...")
                    subprocess.run(["brew", "install", "ollama"], timeout=120, check=False)
                    return True
            else:
                self._say("Installing via official script...")
                subprocess.run("curl -fsSL https://ollama.com/install.sh | sh",
                    shell=True, timeout=120, check=False)
                return True
        except Exception as e:
            self._say(f"Auto-install failed: {e}")
            return False

    def _pull_model(self, model: str) -> bool:
        """Download a model via Ollama."""
        self._say(f"📥 Downloading {model}... This may take a few minutes.")
        try:
            subprocess.run(["ollama", "pull", model], check=True, timeout=600)
            self._say(f"✅ {model} ready!")
            return True
        except Exception as e:
            self._say(f"❌ Download failed: {e}")
            return False

    # ==================== HELPERS ====================

    def _check_ollama_api(self) -> tuple[bool, list[str]]:
        """Check if Ollama API is responding."""
        try:
            req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
                models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
                return True, models
        except Exception:
            return False, []

    def _cmd_exists(self, cmd: str) -> bool:
        """Check if a command exists in PATH."""
        try:
            subprocess.run([cmd, "--version"], capture_output=True, timeout=3)
            return True
        except Exception:
            return False

    def _pick_best_model(self, models: list[str]) -> str:
        """Pick the best model from available list."""
        priority = ["qwen3.5", "qwen2.5-coder", "deepseek-coder", "llama3.2", "llama3.1", "mistral", "gemma"]
        for pref in priority:
            for m in models:
                if pref in m.lower():
                    return m
        return models[0]

    def _make_config(self, provider: str, model: str) -> dict[str, Any]:
        """Generate config dict."""
        base_url = ""
        ollama_url = "http://localhost:11434"
        if provider == "openai":
            base_url = "https://api.openai.com/v1"
            ollama_url = ""
        elif provider == "anthropic":
            base_url = "https://api.anthropic.com"
            ollama_url = ""

        return {
            "version": "2.1.1",
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
            "memory": {"enabled": True, "daily_ttl_days": 30, "dreaming_enabled": True},
            "skills": {"enabled": True, "auto_generate": True},
            "channels": {"enabled": False},
            "dashboard": {"enabled": True, "port": 17901},
        }

    def _auto_create_config(self, scan: dict[str, Any]) -> None:
        """Create config with best guess."""
        if scan["ollama_running"] and scan["ollama_models"]:
            config = self._make_config("ollama", self._pick_best_model(scan["ollama_models"]))
        elif scan["has_openai_key"]:
            config = self._make_config("openai", "gpt-4o-mini")
        elif scan["has_anthropic_key"]:
            config = self._make_config("anthropic", "claude-3-5-sonnet-20241022")
        else:
            config = self._make_config("ollama", "qwen2.5-coder:7b")

        self.base_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

    def _update_config_model(self, model: str) -> None:
        """Update just the model in existing config."""
        try:
            with open(self.config_path, encoding="utf-8") as f:
                cfg = json.load(f)
            cfg["llm"]["model"] = model
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
        except Exception:
            pass

    def _apply_and_test(self, config: dict[str, Any]) -> bool:
        """Save config and test connection."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        for d in ["skills", "memory", "sessions", "agents", "plugins", "workflows"]:
            (self.base_dir / d).mkdir(exist_ok=True)

        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

        provider = config["llm"]["provider"]
        model = config["llm"]["model"]

        self._say(f"\n🧪 Testing connection to {provider}...")

        if provider == "ollama":
            running, models = self._check_ollama_api()
            if not running:
                self._say("❌ Ollama is not responding. Start it with: ollama serve")
                return False
            if model not in models:
                self._say(f"⚠️  Model '{model}' not downloaded yet.")
                if self._ask("Download it now? [Enter = Yes]:", default=True):
                    return self._pull_model(model)
                return False
            self._say(f"✅ Ollama ready with {len(models)} model(s)")
            return True
        else:
            # Cloud — just assume OK since we can't test without spending tokens
            self._say(f"✅ Configured for {provider}")
            self._say("   (Connection will be verified on first chat)")
            return True

    # ==================== GUIDES ====================

    def _python_guide(self) -> None:
        self._say("\n📋 Install Python 3.10+:")
        if self._platform == "windows":
            self._say("   1. Go to https://python.org/downloads")
            self._say("   2. Download Python 3.12")
            self._say("   3. Run installer — CHECK 'Add Python to PATH'")
            self._say("   4. Restart this terminal")
        elif self._platform == "darwin":
            self._say("   brew install python@3.12")
        else:
            self._say("   sudo apt install python3.12")

    def _ollama_start_guide(self) -> None:
        self._say("\n📋 Start Ollama:")
        if self._platform == "windows":
            self._say("   1. Press Windows key, type 'Ollama', click to open")
            self._say("   2. OR run in PowerShell: ollama serve")
        elif self._platform == "darwin":
            self._say("   ollama serve")
        else:
            self._say("   ollama serve")
            self._say("   OR: sudo systemctl start ollama")

    # ==================== UI ====================

    def _banner(self, text: str) -> None:
        print(f"\n{'=' * 55}")
        print(f"  {text}")
        print(f"{'=' * 55}")

    def _say(self, text: str, delay: float = 0.01) -> None:
        print(text)
        if delay > 0:
            time.sleep(delay)

    def _ask(self, prompt: str, default: bool = True) -> bool:
        suffix = " [Y/n]: " if default else " [y/N]: "
        response = input(f"  {prompt}{suffix}").strip().lower()
        if not response:
            return default
        return response in ("y", "yes", "ya", "1")

    def _ask_choice(self, prompt: str, options: list[str]) -> int:
        self._say(f"\n  {prompt}")
        for i, opt in enumerate(options, 1):
            self._say(f"   {i}. {opt}")
        while True:
            try:
                response = input(f"  Choice [1-{len(options)}]: ").strip()
                choice = int(response)
                if 1 <= choice <= len(options):
                    return choice - 1
            except ValueError:
                pass
            self._say("   Invalid choice.")


__all__ = ["SmartWizard"]
