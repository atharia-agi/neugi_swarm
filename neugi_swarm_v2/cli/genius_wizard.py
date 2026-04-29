#!/usr/bin/env python3
"""
NEUGI v2 Genius Wizard — Zero-Dependency Smart Setup
======================================================

This wizard is SMART like an LLM but needs NO AI to run.
It uses pure Python + system heuristics to think, decide, and guide.

Key Features:
    - Thinks: Analyzes your system like a human expert
    - Decides: Picks the best setup automatically
    - Guides: Speaks in plain language, not tech jargon
    - Fixes: Auto-repairs common issues
    - Zero Dependencies: Runs on pure Python stdlib

Usage:
    python genius_wizard.py        # Interactive setup
    python genius_wizard.py rescue # Auto-fix mode
    python genius_wizard.py check  # System report only
"""

from __future__ import annotations

import getpass
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class Colors:
    """Terminal colors for pretty output."""
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    END = "\033[0m"


class GeniusWizard:
    """
    The Genius Wizard — An AI-like setup assistant using pure logic.
    
    How it "thinks":
        1. OBSERVE: Scans system state comprehensively
        2. REASON: Applies heuristics to determine best path
        3. ACT: Executes fixes automatically
        4. CONFIRM: Tests and verifies everything works
    """

    # Provider catalog — loaded dynamically from provider_catalog.py
    # Users can edit provider_catalog.py to add new providers/models anytime

    def __init__(self):
        self.os_name = platform.system()
        self.is_windows = self.os_name == "Windows"
        self.is_mac = self.os_name == "Darwin"
        self.is_linux = self.os_name == "Linux"
        self.is_wsl = "WSL_DISTRO_NAME" in os.environ
        self.home = Path.home()
        self.neugi_dir = self.home / ".neugi"
        self.config_path = self.neugi_dir / "config.json"
        self.issues_fixed = []
        self.issues_manual = []

    # ==================== ENTRY POINTS ====================

    def run(self) -> bool:
        """Main entry: smart setup."""
        self._clear_screen()
        self._print_logo()
        self._typewrite("Hi! I'm the NEUGI Setup Wizard. I'll get you running in minutes.")
        self._typewrite("I don't need any AI to work — I already know everything about your computer.")
        
        # Phase 1: Deep System Scan
        self._section("Scanning Your System")
        state = self._deep_scan()
        self._show_scan_summary(state)
        
        # Phase 2: Smart Decision Engine
        self._section("Deciding Best Setup")
        plan = self._create_setup_plan(state)
        self._explain_plan(plan)
        
        if not self._confirm("Does this look good?"):
            plan = self._manual_override(state)
        
        # Phase 3: Execute
        self._section("Setting Up")
        success = self._execute_plan(plan, state)
        
        # Phase 4: Verify
        if success:
            self._section("Final Check")
            self._verify_setup(plan)
        
        return success

    def rescue(self) -> bool:
        """Auto-fix everything."""
        self._clear_screen()
        self._print_logo()
        self._typewrite("Rescue Mode — I'll find and fix all problems automatically.")
        
        state = self._deep_scan()
        self._show_scan_summary(state)
        
        # Auto-fix loop
        self._section("Auto-Fixing Issues")
        
        if not state["python_ok"]:
            self._error("Python too old. This must be fixed manually.")
            self._show_python_guide()
            return False
        
        if state["config_missing"]:
            self._fix("Creating missing config file...")
            self._create_default_config(state)
        elif state["config_broken"]:
            self._fix("Config corrupted. Restoring defaults...")
            self._create_default_config(state)
        
        if state["dirs_missing"]:
            self._fix("Creating required folders...")
            self._ensure_directories()
        
        if state["ollama_installed"] and not state["ollama_running"]:
            self._fix("Starting Ollama...")
            if self._start_ollama():
                self._success("Ollama started!")
            else:
                self._warning("Couldn't auto-start Ollama.")
                self._show_ollama_start_guide()
        
        if state["model_missing"] and state["ollama_running"]:
            model = state["configured_model"] or "qwen2.5-coder:7b"
            self._fix(f"Downloading model {model}...")
            if self._pull_model(model):
                self._success(f"Model {model} ready!")
            else:
                self._warning(f"Couldn't download {model}")
                if state["available_models"]:
                    fallback = state["available_models"][0]
                    self._fix(f"Switching to available model: {fallback}")
                    self._update_config_model(fallback)
        
        # Final report
        self._section("Rescue Complete")
        if self.issues_fixed:
            self._success(f"Fixed {len(self.issues_fixed)} issue(s):")
            for issue in self.issues_fixed:
                print(f"   ✓ {issue}")
        
        if self.issues_manual:
            self._warning(f"{len(self.issues_manual)} issue(s) need manual fix:")
            for issue in self.issues_manual:
                print(f"   ⚠ {issue}")
        
        if not self.issues_fixed and not self.issues_manual:
            self._success("No issues found! Everything looks good.")
        
        return len([i for i in self.issues_manual if "CRITICAL" in i]) == 0

    def check(self) -> Dict[str, Any]:
        """System check only — returns report dict."""
        state = self._deep_scan()
        report = {
            "healthy": True,
            "python_ok": state["python_ok"],
            "ollama_ok": state["ollama_running"],
            "config_ok": state["config_valid"],
            "model_ready": not state["model_missing"],
            "recommendation": self._create_setup_plan(state)["description"],
        }
        
        critical = []
        if not state["python_ok"]:
            critical.append("Python version too old")
        if state["config_broken"]:
            critical.append("Config file corrupted")
        
        report["healthy"] = len(critical) == 0
        report["critical_issues"] = critical
        return report

    # ==================== THE BRAIN: DEEP SCAN ====================

    def _deep_scan(self) -> Dict[str, Any]:
        """
        Comprehensive system scan. This is the wizard's 'eyes'.
        Detects everything without asking the user.
        """
        state = {
            # Python
            "python_ok": False,
            "python_version": "",
            "python_path": sys.executable,
            
            # OS
            "os": self.os_name,
            "is_wsl": self.is_wsl,
            
            # Ollama
            "ollama_installed": False,
            "ollama_version": "",
            "ollama_running": False,
            "ollama_models": [],
            "ollama_path": None,
            
            # Config
            "config_exists": False,
            "config_valid": False,
            "config_broken": False,
            "config_missing": False,
            "configured_provider": "",
            "configured_model": "",
            "configured_url": "",
            
            # Directories
            "dirs_missing": False,
            "missing_dirs": [],
            
            # Cloud providers
            "has_openai_key": False,
            "has_anthropic_key": False,
            "has_gemini_key": False,
            "has_grok_key": False,
            "available_providers": [],

            # Model status
            "model_missing": False,
            "available_models": [],
            "recommended_model": "",
        }

        # Check Python
        major, minor = sys.version_info[:2]
        state["python_version"] = f"{major}.{minor}"
        state["python_ok"] = (major == 3 and minor >= 10) or major > 3

        # Check Ollama (multiple methods)
        ollama_cmd = self._find_ollama_binary()
        if ollama_cmd:
            state["ollama_installed"] = True
            state["ollama_path"] = str(ollama_cmd)
            try:
                result = subprocess.run([str(ollama_cmd), "--version"],
                    capture_output=True, text=True, timeout=5)
                state["ollama_version"] = result.stdout.strip()[:50]
            except Exception:
                pass

        # Check if Ollama API is up
        if state["ollama_installed"]:
            running, models = self._query_ollama_models()
            state["ollama_running"] = running
            state["ollama_models"] = models
            state["available_models"] = models

        # Check config
        if self.config_path.exists():
            state["config_exists"] = True
            try:
                with open(self.config_path, encoding="utf-8") as f:
                    cfg = json.load(f)
                state["config_valid"] = True
                llm = cfg.get("llm", {})
                state["configured_provider"] = llm.get("provider", "")
                state["configured_model"] = llm.get("model", "")
                state["configured_url"] = llm.get("ollama_url", "") or llm.get("base_url", "")

                # Check if configured model exists
                if state["configured_model"] and state["ollama_running"]:
                    if state["configured_model"] not in state["ollama_models"]:
                        state["model_missing"] = True
            except json.JSONDecodeError:
                state["config_broken"] = True
        else:
            state["config_missing"] = True

        # Check directories
        required = ["skills", "memory", "sessions", "agents"]
        for d in required:
            if not (self.neugi_dir / d).exists():
                state["missing_dirs"].append(d)
                state["dirs_missing"] = True

        # Check API keys for all supported providers
        state["has_openai_key"] = bool(os.environ.get("OPENAI_API_KEY"))
        state["has_anthropic_key"] = bool(os.environ.get("ANTHROPIC_API_KEY"))
        state["has_gemini_key"] = bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))
        state["has_grok_key"] = bool(os.environ.get("XAI_API_KEY") or os.environ.get("GROK_API_KEY"))

        # Build available providers list
        providers = []
        if state["ollama_installed"]:
            providers.append("ollama")
        if state["has_openai_key"]:
            providers.append("openai")
        if state["has_anthropic_key"]:
            providers.append("anthropic")
        if state["has_gemini_key"]:
            providers.append("gemini")
        if state["has_grok_key"]:
            providers.append("grok")
        # Compatible providers are always available (user fills in key + endpoint)
        providers.extend(["openai_compatible", "anthropic_compatible"])
        state["available_providers"] = providers

        # Pick recommended model
        if state["ollama_models"]:
            state["recommended_model"] = self._pick_best_model(state["ollama_models"])
        else:
            state["recommended_model"] = "qwen2.5-coder:7b"

        return state

    # ==================== THE BRAIN: SETUP PLANNER ====================

    # Provider ranking: cloud SOTA > local capable > cloud budget > local light
    _PROVIDER_RANK = [
        ("openai", "gpt-4o", "gpt-4o-mini"),
        ("anthropic", "claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"),
        ("gemini", "gemini-2.5-pro", "gemini-2.5-flash"),
        ("grok", "grok-3", "grok-3"),
        ("ollama", "qwen2.5-coder:7b", "llama3.2:3b"),
    ]

    def _create_setup_plan(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Zero-effort setup: auto-pick primary + fallback.
        User just presses Enter.
        """
        detected = self._rank_providers(state)

        if not detected:
            # Nothing detected — fresh install path
            return {
                "mode": "fresh_local",
                "provider": "ollama",
                "model": "qwen2.5-coder:7b",
                "fallback_provider": "ollama",
                "fallback_model": "llama3.2:3b",
                "base_url": "",
                "description": "Install Ollama + qwen2.5-coder:7b (~4GB). Works offline, free forever.",
                "actions": ["install_ollama", "pull_model", "save_config"],
                "needs_download": True,
            }

        primary = detected[0]
        fallback = detected[1] if len(detected) > 1 else None

        # Build plan
        plan = {
            "mode": primary["mode"],
            "provider": primary["provider"],
            "model": primary["model"],
            "base_url": primary.get("base_url", ""),
            "description": primary["description"],
            "actions": primary.get("actions", ["save_config"]),
            "needs_download": primary.get("needs_download", False),
        }

        if fallback:
            plan["fallback_provider"] = fallback["provider"]
            plan["fallback_model"] = fallback["model"]
            plan["description"] += f" (fallback: {fallback['provider']}/{fallback['model']})"
        else:
            # Same-provider fallback
            plan["fallback_provider"] = primary["provider"]
            plan["fallback_model"] = primary.get("fallback_model", "")

        return plan

    def _rank_providers(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Rank all detected providers by capability. Returns list of candidates."""
        candidates = []

        # Cloud providers with API keys
        if state["has_openai_key"]:
            candidates.append({
                "provider": "openai",
                "model": "gpt-4o",
                "fallback_model": "gpt-4o-mini",
                "base_url": "https://api.openai.com/v1",
                "mode": "cloud_openai",
                "description": "OpenAI GPT-4o — smartest, fastest setup",
                "rank": 1,
            })
        if state["has_anthropic_key"]:
            candidates.append({
                "provider": "anthropic",
                "model": "claude-3-5-sonnet-20241022",
                "fallback_model": "claude-3-haiku-20240307",
                "base_url": "https://api.anthropic.com",
                "mode": "cloud_anthropic",
                "description": "Anthropic Claude 3.5 Sonnet — excellent reasoning",
                "rank": 2,
            })
        if state["has_gemini_key"]:
            candidates.append({
                "provider": "gemini",
                "model": "gemini-2.5-pro",
                "fallback_model": "gemini-2.5-flash",
                "base_url": "https://generativelanguage.googleapis.com/v1",
                "mode": "cloud_gemini",
                "description": "Google Gemini 2.5 Pro — 1M context",
                "rank": 3,
            })
        if state["has_grok_key"]:
            candidates.append({
                "provider": "grok",
                "model": "grok-3",
                "fallback_model": "grok-3",
                "base_url": "https://api.x.ai/v1",
                "mode": "cloud_grok",
                "description": "xAI Grok 3 — real-time aware",
                "rank": 4,
            })

        # Ollama local
        if state["ollama_running"] and state["ollama_models"]:
            model = state["recommended_model"]
            # Pick fallback from installed models
            installed = state["ollama_models"]
            fallback = installed[0] if installed else "llama3.2:3b"
            if fallback == model and len(installed) > 1:
                fallback = installed[1]
            candidates.append({
                "provider": "ollama",
                "model": model,
                "fallback_model": fallback,
                "base_url": "",
                "mode": "local_ready",
                "description": f"Local Ollama — {model} (private, offline, free)",
                "actions": ["save_config"],
                "needs_download": False,
                "rank": 5,
            })
        elif state["ollama_running"] and not state["ollama_models"]:
            candidates.append({
                "provider": "ollama",
                "model": "qwen2.5-coder:7b",
                "fallback_model": "llama3.2:3b",
                "base_url": "",
                "mode": "local_needs_model",
                "description": "Local Ollama — need to download qwen2.5-coder:7b",
                "actions": ["pull_model", "save_config"],
                "needs_download": True,
                "rank": 6,
            })
        elif state["ollama_installed"] and not state["ollama_running"]:
            candidates.append({
                "provider": "ollama",
                "model": "qwen2.5-coder:7b",
                "fallback_model": "llama3.2:3b",
                "base_url": "",
                "mode": "local_needs_start",
                "description": "Local Ollama — installed but not running",
                "actions": ["start_ollama", "save_config"],
                "needs_download": False,
                "rank": 7,
            })

        # Sort by rank
        candidates.sort(key=lambda x: x["rank"])
        return candidates

    def _explain_plan(self, plan: Dict[str, Any]) -> None:
        """Explain the plan in human language."""
        self._typewrite(f"\nI recommend: {plan['description']}")
        
        if plan["mode"] == "local_ready":
            self._typewrite("This is perfect — you'll have a fully private AI that works offline.")
        elif plan["mode"].startswith("local"):
            self._typewrite("Local AI is the best choice: free forever, private, no internet needed after setup.")
        elif plan["mode"].startswith("cloud"):
            self._typewrite("Cloud setup is fastest — you'll be chatting in seconds, but it uses API credits.")
        elif plan["mode"] in ("openai_compatible", "anthropic_compatible"):
            self._typewrite("Custom endpoint setup — make sure your API key and base URL are correct.")
        elif plan["mode"] == "fresh_local":
            self._typewrite("You'll need to download about 4GB for the AI model. This is a one-time download.")

    def _manual_override(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Interactive provider & model selection with capability preview."""
        self._typewrite("\nLet's pick your AI provider and model.")
        self._typewrite("I only show models that run NEUGI well. Use 'Custom' for anything else.")
        print()

        # Step 1: Pick provider
        providers = self._build_provider_menu(state)
        print("  Available providers:")
        for i, (key, label) in enumerate(providers, 1):
            print(f"   {i}. {label}")
        print(f"   {len(providers)+1}. Other / I'll set up later")

        p_choice = self._ask_number("Pick provider", 1, len(providers) + 1)
        if p_choice == len(providers) + 1:
            # Fallback: minimal config
            return {
                "mode": "minimal",
                "provider": "ollama",
                "model": "qwen2.5-coder:7b",
                "description": "Minimal config — edit later",
                "actions": ["save_config"],
                "needs_download": False,
            }

        provider_key, _ = providers[p_choice - 1]

        # Step 2: Pick model
        model, custom_name = self._pick_model_interactive(provider_key, state)

        # Step 3: For compatible providers, ask endpoint
        base_url = ""
        if provider_key == "openai_compatible":
            base_url = input("   Custom base URL (e.g., https://api.groq.com/openai/v1): ").strip()
            if not base_url:
                base_url = "https://api.openai.com/v1"
        elif provider_key == "anthropic_compatible":
            base_url = input("   Custom base URL (e.g., https://api.anthropic.com): ").strip()
            if not base_url:
                base_url = "https://api.anthropic.com"

        # Step 4: API key if needed and not in env
        if provider_key in ("openai", "openai_compatible") and not state["has_openai_key"]:
            key = getpass.getpass("   OpenAI API key: ").strip()
            if key:
                os.environ["OPENAI_API_KEY"] = key
        elif provider_key in ("anthropic", "anthropic_compatible") and not state["has_anthropic_key"]:
            key = getpass.getpass("   Anthropic API key: ").strip()
            if key:
                os.environ["ANTHROPIC_API_KEY"] = key
        elif provider_key == "gemini" and not state["has_gemini_key"]:
            key = getpass.getpass("   Gemini API key: ").strip()
            if key:
                os.environ["GEMINI_API_KEY"] = key
        elif provider_key == "grok" and not state["has_grok_key"]:
            key = getpass.getpass("   Grok API key: ").strip()
            if key:
                os.environ["XAI_API_KEY"] = key

        # Step 5: Show capability preview
        self._show_capability_preview(provider_key, model)

        # Build plan
        is_ollama = provider_key == "ollama"
        actions = ["save_config"]
        if is_ollama and model not in state.get("ollama_models", []):
            actions.insert(0, "pull_model")

        return {
            "mode": provider_key,
            "provider": provider_key,
            "model": model,
            "custom_model_name": custom_name,
            "base_url": base_url,
            "description": f"{provider_key} with {model}",
            "actions": actions,
            "needs_download": is_ollama and model not in state.get("ollama_models", []),
        }

    def _build_provider_menu(self, state: Dict[str, Any]) -> List[Tuple[str, str]]:
        """Build provider menu dynamically from catalog."""
        from provider_catalog import get_all_providers

        menu = []
        # Ollama first (special handling for local install status)
        if state["ollama_installed"]:
            status = "running" if state["ollama_running"] else "installed"
            menu.append(("ollama", f"Ollama (local) — {status}"))
        else:
            menu.append(("ollama", "Ollama (local) — install free AI"))

        # Cloud providers from catalog
        for p in get_all_providers():
            if p.name in ("ollama", "openai_compatible", "anthropic_compatible"):
                continue
            model_names = ", ".join([m.name for m in p.models[:2]])
            menu.append((p.name, f"{p.display_name} — {model_names}"))

        # Custom endpoints
        menu.append(("openai_compatible", "OpenAI-compatible — custom endpoint (Groq, Together, etc.)"))
        menu.append(("anthropic_compatible", "Anthropic-compatible — custom endpoint"))
        return menu

    def _pick_model_interactive(self, provider: str, state: Dict[str, Any]) -> Tuple[str, str]:
        """Let user pick a model from the provider catalog."""
        from provider_catalog import get_models_for_provider

        models = get_models_for_provider(provider)

        # For Ollama, mark installed models
        if provider == "ollama":
            installed = set(state.get("ollama_models", []))
            items = []
            for m in models:
                tag = " [installed]" if m.id in installed else " [download]"
                items.append((m.id, f"{m.name} — {m.description}{tag}"))
            items.append(("custom", "Custom Ollama model — you type the name"))
        elif provider in ("openai_compatible", "anthropic_compatible"):
            items = [("custom", "Custom model — you type the name")]
        else:
            items = [(m.id, f"{m.name} — {m.description}") for m in models]
            items.append(("custom", "Custom model — you type the name"))

        print(f"\n  Models for {provider}:")
        for i, (mid, desc) in enumerate(items, 1):
            print(f"   {i}. {desc}")
        print(f"   {len(items)+1}. I'll enter a custom model name")

        choice = self._ask_number("Pick model", 1, len(items) + 1)
        if choice <= len(items):
            model = items[choice - 1][0]
            if model == "custom":
                custom = input("   Enter model name: ").strip()
                return custom, custom
            return model, ""
        else:
            custom = input("   Enter model name: ").strip()
            return custom, custom

    def _show_capability_preview(self, provider: str, model: str) -> None:
        """Show a quick capability preview for the selected model."""
        # Simple heuristic preview
        tier = "unknown"
        if provider == "ollama":
            if any(x in model for x in ["70b", "72b", "8x7b", "8x22b"]):
                tier = "medium-high (local)"
            elif any(x in model for x in ["3b", "4b"]):
                tier = "local (lightweight)"
            else:
                tier = "local (standard)"
        elif provider in ("openai", "anthropic", "gemini", "grok"):
            tier = "cloud (SOTA)"
        else:
            tier = "custom (auto-detect at runtime)"

        print(f"\n  {Colors.CYAN}Capability Preview:{Colors.END}")
        print(f"   Model: {model}")
        print(f"   Provider: {provider}")
        print(f"   Estimated tier: {tier}")
        print(f"   NEUGI will auto-adapt prompts, tools, and memory for this model.")

    # ==================== EXECUTION ENGINE ====================

    def _execute_plan(self, plan: Dict[str, Any], state: Dict[str, Any]) -> bool:
        """Execute the setup plan step by step."""
        
        # Step 1: Ensure directories
        self._ensure_directories()
        
        # Step 2: Execute actions
        for action in plan["actions"]:
            if action == "install_ollama":
                self._typewrite("\n📦 Installing Ollama...")
                if self._install_ollama():
                    self._success("Ollama installed!")
                    # Re-scan after install
                    time.sleep(2)
                    state = self._deep_scan()
                else:
                    self._warning("Couldn't auto-install Ollama.")
                    self._show_ollama_install_guide()
                    if not self._confirm("Continue after installing Ollama?"):
                        return False
            
            elif action == "start_ollama":
                self._typewrite("\n🚀 Starting Ollama...")
                if self._start_ollama():
                    self._success("Ollama started!")
                    time.sleep(2)
                    state = self._deep_scan()
                else:
                    self._warning("Please start Ollama manually.")
                    self._show_ollama_start_guide()
                    if not self._confirm("Continue after starting Ollama?"):
                        return False
            
            elif action == "pull_model":
                model = plan["model"]
                self._typewrite(f"\n📥 Downloading {model}...")
                self._typewrite("This will take a few minutes depending on your internet.")
                if self._pull_model(model):
                    self._success(f"{model} is ready!")
                else:
                    self._warning(f"Couldn't download {model}")
                    if state["ollama_models"]:
                        fallback = state["ollama_models"][0]
                        plan["model"] = fallback
                        self._typewrite(f"Using existing model: {fallback}")
            
            elif action == "save_config":
                self._save_config(plan)
                self._success("Configuration saved!")
        
        return True

    def _verify_setup(self, plan: Dict[str, Any]) -> None:
        """Final verification."""
        provider = plan["provider"]
        model = plan["model"]
        base_url = plan.get("base_url", "")

        self._typewrite("\n🔍 Verifying everything works...")

        if provider == "ollama":
            running, models = self._query_ollama_models()
            if running and model in models:
                self._success("All set! Your local AI is ready.")
                self._typewrite(f"\n🎉 Try it now: type 'neugi chat' and start talking to {model}!")
            elif running:
                self._warning(f"Model {model} not found, but Ollama is running.")
                if models:
                    self._typewrite(f"Available models: {', '.join(models)}")
            else:
                self._warning("Ollama isn't running. Start it with: ollama serve")
        elif provider in ("openai_compatible", "anthropic_compatible"):
            self._success(f"Custom {provider.replace('_', ' ')} setup saved!")
            self._typewrite(f"   Endpoint: {base_url or 'default'}")
            self._typewrite(f"   Model: {model}")
            self._typewrite("\n🎉 Try it now: type 'neugi chat'!")
            self._typewrite("   If it fails, run 'neugi rescue' to fix.")
        else:
            self._success(f"{provider.capitalize()} setup complete!")
            self._typewrite(f"   Model: {model}")
            self._typewrite("\n🎉 Try it now: type 'neugi chat'!")

    # ==================== SYSTEM OPERATIONS ====================

    def _find_ollama_binary(self) -> Optional[Path]:
        """Find Ollama executable across different install methods."""
        # Check PATH first
        ollama_exe = "ollama.exe" if self.is_windows else "ollama"
        if shutil.which(ollama_exe):
            return Path(shutil.which(ollama_exe))
        
        # Check common install locations
        paths = []
        if self.is_windows:
            paths = [
                self.home / "AppData" / "Local" / "Programs" / "Ollama" / "ollama.exe",
                Path("C:/Program Files/Ollama/ollama.exe"),
                Path("C:/Program Files (x86)/Ollama/ollama.exe"),
            ]
        elif self.is_mac:
            paths = [
                Path("/usr/local/bin/ollama"),
                Path("/opt/homebrew/bin/ollama"),
            ]
        else:
            paths = [
                Path("/usr/local/bin/ollama"),
                Path("/usr/bin/ollama"),
                self.home / ".local" / "bin" / "ollama",
            ]
        
        for path in paths:
            if path.exists():
                return path
        
        return None

    def _query_ollama_models(self) -> Tuple[bool, List[str]]:
        """Query Ollama API for running status and models."""
        try:
            req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
                models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
                return True, models
        except Exception:
            return False, []

    def _start_ollama(self) -> bool:
        """Attempt to start Ollama service."""
        try:
            binary = self._find_ollama_binary()
            if not binary:
                return False
            
            # Start in background
            kwargs = {}
            if self.is_windows:
                kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE if hasattr(subprocess, "CREATE_NEW_CONSOLE") else 0
            
            subprocess.Popen([str(binary), "serve"], 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL,
                **kwargs)
            
            # Wait and verify
            for _ in range(10):
                time.sleep(1)
                running, _ = self._query_ollama_models()
                if running:
                    return True
            
            return False
        except Exception:
            return False

    def _install_ollama(self) -> bool:
        """Attempt automatic Ollama installation."""
        try:
            if self.is_windows:
                # Try winget first
                if shutil.which("winget"):
                    self._typewrite("Installing Ollama via winget...")
                    subprocess.run(["winget", "install", "Ollama.Ollama",
                        "--accept-package-agreements", "--accept-source-agreements"],
                        timeout=120, check=False)
                    return True
                else:
                    self._typewrite("Opening Ollama download page...")
                    webbrowser.open("https://ollama.com/download/windows")
                    return False
            
            elif self.is_mac:
                if shutil.which("brew"):
                    self._typewrite("Installing Ollama via Homebrew...")
                    subprocess.run(["brew", "install", "ollama"], timeout=120, check=False)
                    return True
            
            else:  # Linux
                self._typewrite("Installing Ollama...")
                subprocess.run("curl -fsSL https://ollama.com/install.sh | sh",
                    shell=True, timeout=180, check=False)
                return True
        
        except Exception:
            return False

    def _pull_model(self, model: str) -> bool:
        """Download a model via Ollama."""
        try:
            binary = self._find_ollama_binary()
            if not binary:
                return False
            subprocess.run([str(binary), "pull", model], check=True, timeout=600)
            return True
        except Exception:
            return False

    def _save_config(self, plan: Dict[str, Any]) -> None:
        """Save NEUGI configuration — one simple JSON file."""
        provider = plan["provider"]
        model = plan["model"]
        base_url = plan.get("base_url", "")
        ollama_url = "http://localhost:11434"

        # Normalize provider names for config
        if provider in ("openai_compatible", "openai"):
            provider = "openai"
            if not base_url:
                base_url = "https://api.openai.com/v1"
            ollama_url = ""
        elif provider in ("anthropic_compatible", "anthropic"):
            provider = "anthropic"
            if not base_url:
                base_url = "https://api.anthropic.com"
            ollama_url = ""
        elif provider == "gemini":
            base_url = "https://generativelanguage.googleapis.com/v1"
            ollama_url = ""
        elif provider == "grok":
            base_url = "https://api.x.ai/v1"
            ollama_url = ""
        elif provider == "ollama":
            base_url = ""
            ollama_url = "http://localhost:11434"

        # Pick fallback model
        fallback_map = {
            "ollama": "llama3.2:3b",
            "openai": "gpt-4o-mini",
            "anthropic": "claude-3-5-sonnet-20241022",
            "gemini": "gemini-2.5-flash",
            "grok": "grok-3",
        }
        fallback = fallback_map.get(provider, "")

        # User-friendly config with self-documenting comments
        config = {
            "_readme": "NEUGI Config — Edit this file to change your AI setup",
            "version": "2.1.1",
            "llm": {
                "_comment": "Your AI provider and model",
                "provider": provider,
                "model": model,
                "fallback_model": fallback,
                "base_url": base_url,
                "ollama_url": ollama_url,
                "api_key": "",
                "temperature": 0.7,
                "max_tokens": 4096,
            },
            "memory": {
                "_comment": "How long NEUGI remembers things",
                "enabled": True,
                "daily_ttl_days": 30,
                "dreaming_enabled": True,
            },
            "skills": {
                "_comment": "Auto-generate skills from your conversations",
                "enabled": True,
                "auto_generate": True,
            },
            "dashboard": {
                "_comment": "Web dashboard settings",
                "enabled": True,
                "port": 17901,
            },
            "routing": {
                "_comment": "Multi-model routing (optional). NEUGI picks the best model per task.",
                "enabled": False,
                "default_model": "",
                "routes": [
                    {
                        "_comment_example": "Add routes like this to enable smart routing",
                        "name": "local",
                        "provider": "ollama",
                        "model": "qwen2.5-coder:7b",
                        "tier": "medium",
                        "enabled": False
                    },
                    {
                        "name": "cloud",
                        "provider": "openai",
                        "model": "gpt-4o",
                        "api_key": "",
                        "tier": "cloud",
                        "enabled": False
                    }
                ]
            },
        }

        self.neugi_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

    def _update_config_model(self, model: str) -> None:
        """Update just the model in config."""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            cfg["llm"]["model"] = model
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
        except Exception:
            pass

    def _ensure_directories(self) -> None:
        """Create required directories."""
        for name in ["skills", "memory", "sessions", "agents", "plugins", "workflows"]:
            (self.neugi_dir / name).mkdir(parents=True, exist_ok=True)

    def _pick_best_model(self, models: List[str]) -> str:
        """Pick the best model from available list."""
        priority = ["qwen3.5", "qwen2.5-coder", "deepseek-coder", "llama3.2", "llama3.1", "mistral"]
        for pref in priority:
            for m in models:
                if pref in m.lower():
                    return m
        return models[0] if models else "qwen2.5-coder:7b"

    def _setup_cloud_manual(self) -> Dict[str, Any]:
        """Manual cloud setup."""
        self._typewrite("\nCloud Setup:")
        self._typewrite("Get API key from:")
        self._typewrite("  OpenAI: https://platform.openai.com/api-keys")
        self._typewrite("  Anthropic: https://console.anthropic.com/settings/keys")
        
        providers = ["OpenAI", "Anthropic"]
        choice = self._ask_number("Select provider", 1, 2)
        provider_key = "openai" if choice == 1 else "anthropic"
        model = "gpt-4o-mini" if choice == 1 else "claude-3-5-sonnet-20241022"
        
        key = getpass.getpass("   Paste your API key: ").strip()
        if provider_key == "openai":
            os.environ["OPENAI_API_KEY"] = key
        else:
            os.environ["ANTHROPIC_API_KEY"] = key
        
        return {
            "mode": f"cloud_{provider_key}",
            "provider": provider_key,
            "model": model,
            "description": f"Use {providers[choice-1]} cloud API",
            "actions": ["save_config"],
            "needs_download": False,
        }

    # ==================== DISPLAY HELPERS ====================

    def _clear_screen(self) -> None:
        os.system("cls" if self.is_windows else "clear")

    def _print_logo(self) -> None:
        print(f"""
{Colors.CYAN}  ███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗{Colors.END}
{Colors.CYAN}  ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝{Colors.END}
{Colors.CYAN}  ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗{Colors.END}
{Colors.CYAN}  ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║{Colors.END}
{Colors.CYAN}  ██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝███████║{Colors.END}
{Colors.CYAN}  ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝{Colors.END}
{Colors.DIM}        Setup Wizard v2.1.1 — Zero-Dependency{Colors.END}
        """)

    def _typewrite(self, text: str, delay: float = 0.01) -> None:
        print(f"{text}")
        if delay > 0:
            time.sleep(delay)

    def _section(self, title: str) -> None:
        print(f"\n{Colors.BOLD}{Colors.BLUE}▶ {title}{Colors.END}")
        print("-" * 50)

    def _success(self, text: str) -> None:
        print(f"{Colors.GREEN}✓ {text}{Colors.END}")
        self.issues_fixed.append(text)

    def _warning(self, text: str) -> None:
        print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")
        self.issues_manual.append(text)

    def _error(self, text: str) -> None:
        print(f"{Colors.RED}✗ {text}{Colors.END}")
        self.issues_manual.append(f"CRITICAL: {text}")

    def _fix(self, text: str) -> None:
        print(f"{Colors.CYAN}→ {text}{Colors.END}")

    def _confirm(self, prompt: str, default: bool = True) -> bool:
        suffix = " [Y/n]: " if default else " [y/N]: "
        response = input(f"{Colors.BOLD}{prompt}{suffix}{Colors.END}").strip().lower()
        if not response:
            return default
        return response in ("y", "yes", "ya", "1")

    def _ask_number(self, prompt: str, min_val: int, max_val: int) -> int:
        while True:
            try:
                response = input(f"{prompt} [{min_val}-{max_val}]: ").strip()
                val = int(response)
                if min_val <= val <= max_val:
                    return val
            except ValueError:
                pass
            print("Please enter a valid number.")

    def _show_scan_summary(self, state: Dict[str, Any]) -> None:
        """Display scan results in a nice format."""
        print()

        # Python
        py_icon = "✓" if state["python_ok"] else "✗"
        py_color = Colors.GREEN if state["python_ok"] else Colors.RED
        print(f"  {py_color}{py_icon} Python {state['python_version']}{Colors.END}")

        # Providers
        if state["ollama_running"]:
            print(f"  {Colors.GREEN}✓ Ollama running ({len(state['ollama_models'])} models){Colors.END}")
        elif state["ollama_installed"]:
            print(f"  {Colors.YELLOW}⚠ Ollama installed but not running{Colors.END}")

        if state["has_openai_key"]:
            print(f"  {Colors.GREEN}✓ OpenAI API key detected{Colors.END}")
        if state["has_anthropic_key"]:
            print(f"  {Colors.GREEN}✓ Anthropic API key detected{Colors.END}")
        if state["has_gemini_key"]:
            print(f"  {Colors.GREEN}✓ Gemini API key detected{Colors.END}")
        if state["has_grok_key"]:
            print(f"  {Colors.GREEN}✓ Grok API key detected{Colors.END}")

        if not state["available_providers"]:
            print(f"  {Colors.YELLOW}⚠ No providers detected yet{Colors.END}")

        # Config
        if state["config_valid"]:
            print(f"  {Colors.GREEN}✓ Config OK{Colors.END}")
        elif state["config_broken"]:
            print(f"  {Colors.RED}✗ Config corrupted{Colors.END}")
        else:
            print(f"  {Colors.YELLOW}⚠ No config found{Colors.END}")

        # Directories
        if state["dirs_missing"]:
            print(f"  {Colors.YELLOW}⚠ Missing folders: {', '.join(state['missing_dirs'])}{Colors.END}")
        else:
            print(f"  {Colors.GREEN}✓ All folders present{Colors.END}")
        
        # Model
        if state["model_missing"]:
            print(f"  {Colors.YELLOW}⚠ Configured model not downloaded{Colors.END}")
        elif state["ollama_models"]:
            print(f"  {Colors.GREEN}✓ Models ready{Colors.END}")

    def _show_python_guide(self) -> None:
        self._typewrite("\n📋 How to update Python:")
        if self.is_windows:
            self._typewrite("   1. Visit https://python.org/downloads")
            self._typewrite("   2. Download Python 3.12")
            self._typewrite("   3. Run installer and CHECK 'Add Python to PATH'")
            self._typewrite("   4. Restart this window")
        elif self.is_mac:
            self._typewrite("   brew install python@3.12")
        else:
            self._typewrite("   sudo apt install python3.12")

    def _show_ollama_install_guide(self) -> None:
        self._typewrite("\n📋 How to install Ollama:")
        if self.is_windows:
            self._typewrite("   1. Go to https://ollama.com/download/windows")
            self._typewrite("   2. Download and run the installer (no WSL needed!)")
            self._typewrite("   3. Restart this window after install")
        elif self.is_mac:
            self._typewrite("   brew install ollama")
            self._typewrite("   OR download from ollama.com/download/mac")
        else:
            self._typewrite("   curl -fsSL https://ollama.com/install.sh | sh")

    def _show_ollama_start_guide(self) -> None:
        self._typewrite("\n📋 How to start Ollama:")
        if self.is_windows:
            self._typewrite("   • Search 'Ollama' in Start Menu and click it")
            self._typewrite("   • OR run: ollama serve")
        elif self.is_mac:
            self._typewrite("   ollama serve")
        else:
            self._typewrite("   ollama serve")
            self._typewrite("   OR: sudo systemctl start ollama")


# ==================== ENTRY POINT ====================

def main():
    wizard = GeniusWizard()
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == "rescue":
            wizard.rescue()
        elif cmd == "check":
            report = wizard.check()
            print(json.dumps(report, indent=2))
        else:
            wizard.run()
    else:
        wizard.run()


if __name__ == "__main__":
    main()
