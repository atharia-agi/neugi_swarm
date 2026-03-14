#!/usr/bin/env python3
"""
🤖 NEUGI WIZARD - All-in-One AI Assistant
==========================================

Single entry point for:
1. Onboarding - Guide new users
2. Diagnosis - Find problems
3. Repair - Fix issues automatically
4. Configuration - Optimize settings

Powered by Ollama AI!

Version: 3.0
Date: March 14, 2026
"""

import os
import json
import requests
import subprocess
import sys
import shutil
import re
from typing import Optional, Dict, List
from datetime import datetime

# ============================================================
# CONFIG
# ============================================================

BRAND = "NEUGI"
NEUGI_DIR = os.path.expanduser("~/neugi")
OLLAMA_URL = "http://localhost:11434"
MODEL = "qwen3.5:cloud"

# ============================================================
# COLORS
# ============================================================


class C:
    PURPLE = "\033[95m"
    CYAN = "\033[96m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    END = "\033[0m"


# ============================================================
# AI CORE
# ============================================================


class AIAgent:
    """AI agent powered by Ollama"""

    def __init__(self):
        self.url = OLLAMA_URL
        self.model = MODEL
        self.system_prompt = f"""You are {BRAND} Wizard - an expert AI assistant.

You help users with:
- Setting up {BRAND} Swarm
- Diagnosing problems
- Fixing issues automatically
- Optimizing performance
- Answering questions about AI and technology

Be helpful, clear, and concise. When asked to fix something, actually perform the action."""

    def chat(self, message: str) -> str:
        """Send message to AI and get response (non-streaming)"""
        try:
            response = requests.post(
                f"{self.url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": f"{self.system_prompt}\n\nUser: {message}\n\n{BRAND}:",
                    "stream": False,
                },
                timeout=60,
            )
            if response.ok:
                return response.json().get("response", "").strip()
        except Exception as e:
            return f"Error: {e}"
        return "Cannot connect to Ollama. Is it running?"

    def chat_stream(self, message: str):
        """
        Send message to AI and get streaming response.

        Yields:
            Text chunks as they arrive
        """
        try:
            response = requests.post(
                f"{self.url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": f"{self.system_prompt}\n\nUser: {message}\n\n{BRAND}:",
                    "stream": True,
                },
                stream=True,
                timeout=60,
            )

            if response.ok:
                for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line.decode())
                            if "response" in data:
                                yield data["response"]
                        except:
                            continue

        except Exception as e:
            yield f"Error: {e}"

    def ask(self, question: str, context: str = "") -> str:
        """Ask AI with context"""
        prompt = (
            f"{context}\n\nQuestion: {question}\n\nAnswer:" if context else question
        )
        return self.chat(prompt)

    def diagnose(self, issue_description: str) -> str:
        """AI diagnoses the problem"""
        prompt = f"""Diagnose this issue with {BRAND} Swarm:

Issue: {issue_description}

Think step by step:
1. What could cause this?
2. How to verify?
3. What's the fix?

Provide diagnosis and fix in this format:
DIAGNOSIS: [your diagnosis]
FIX: [command or action to fix]"
"""
        return self.chat(prompt)

    def execute_fix(self, fix_command: str) -> Dict:
        """Execute a fix command"""
        result = {"command": fix_command, "success": False, "output": ""}

        # Only allow safe commands
        safe_commands = {
            "ollama serve": "Starting Ollama server",
            "pip install": "Installing package",
            "curl": "Downloading file",
            "mkdir": "Creating directory",
            "rm -rf ~/neugi": "Resetting NEUGI directory",
        }

        for safe_cmd, description in safe_commands.items():
            if safe_cmd in fix_command.lower():
                result["description"] = description
                try:
                    # For dangerous commands, don't actually execute
                    if "rm -rf" in fix_command.lower():
                        result["output"] = "Would execute: " + fix_command
                        result["safe"] = False
                        return result

                    # Execute other commands
                    proc = subprocess.run(
                        fix_command,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    result["success"] = proc.returncode == 0
                    result["output"] = proc.stdout or proc.stderr
                except Exception as e:
                    result["output"] = str(e)
                return result

        result["output"] = f"Command not in safe list: {fix_command}"
        return result


# ============================================================
# SYSTEM CHECKS
# ============================================================


class SystemChecker:
    """Check system status"""

    @staticmethod
    def check_ollama() -> Dict:
        """Check Ollama status"""
        result = {"running": False, "models": [], "error": ""}
        try:
            r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
            if r.ok:
                result["running"] = True
                result["models"] = [m["name"] for m in r.json().get("models", [])]
        except Exception as e:
            result["error"] = str(e)
        return result

    @staticmethod
    def check_neugi() -> Dict:
        """Check NEUGI status"""
        result = {"installed": False, "running": False, "config": None}
        config_path = os.path.join(NEUGI_DIR, "data", "config.json")

        if os.path.exists(config_path):
            result["installed"] = True
            try:
                with open(config_path) as f:
                    result["config"] = json.load(f)
            except:
                pass

        try:
            r = requests.get(f"http://localhost:19888/health", timeout=2)
            result["running"] = r.ok
        except:
            pass

        return result

    @staticmethod
    def check_port(port: int) -> Dict:
        """Check if port is in use"""
        import socket

        result = {"in_use": False, "process": ""}
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if sock.connect_ex(("localhost", port)) == 0:
            result["in_use"] = True
        sock.close()
        return result

    @staticmethod
    def full_diagnosis() -> Dict:
        """Run full system diagnosis"""
        return {
            "ollama": SystemChecker.check_ollama(),
            "neugi": SystemChecker.check_neugi(),
            "port_19888": SystemChecker.check_port(19888),
        }


# ============================================================
# REPAIR ACTIONS
# ============================================================


class Repair:
    """Auto-repair common issues"""

    @staticmethod
    def start_ollama() -> Dict:
        """Start Ollama"""
        try:
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            # Wait
            for _ in range(10):
                import time

                time.sleep(1)
                if SystemChecker.check_ollama()["running"]:
                    return {"success": True, "message": "Ollama started!"}
            return {"success": False, "message": "Ollama didn't start in time"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    @staticmethod
    def reset_config() -> Dict:
        """Reset NEUGI config"""
        try:
            config_path = os.path.join(NEUGI_DIR, "data", "config.json")
            if os.path.exists(config_path):
                os.remove(config_path)
            return {"success": True, "message": "Config reset! Run wizard again."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    @staticmethod
    def install_dependencies() -> Dict:
        """Install required packages"""
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "requests"],
                capture_output=True,
                timeout=60,
            )
            return {"success": True, "message": "Dependencies installed!"}
        except Exception as e:
            return {"success": False, "message": str(e)}


# ============================================================
# WIZARD UI
# ============================================================


class WizardUI:
    """Beautiful CLI UI"""

    @staticmethod
    def header(title: str):
        print(f"\n{C.CYAN}{'═' * 60}")
        print(f"  🤖 {title}")
        print(f"{'═' * 60}{C.END}\n")

    @staticmethod
    def menu(options: List[tuple], title: str = "Choose an option:") -> str:
        """Show menu and get choice"""
        print(f"{C.BOLD}{title}{C.END}\n")
        for i, (key, desc) in enumerate(options, 1):
            print(f"  {C.GREEN}{i}{C.END}. {desc}")
        print()
        choice = input(f"{C.CYAN}> {C.END}").strip()
        return choice

    @staticmethod
    def success(msg: str):
        print(f"{C.GREEN}  ✅ {msg}{C.END}")

    @staticmethod
    def warning(msg: str):
        print(f"{C.YELLOW}  ⚠️  {msg}{C.END}")

    @staticmethod
    def error(msg: str):
        print(f"{C.RED}  ❌ {msg}{C.END}")

    @staticmethod
    def info(msg: str):
        print(f"{C.CYAN}  ℹ️  {msg}{C.END}")

    @staticmethod
    def ai_response(response: str):
        """Display AI response beautifully"""
        print(f"\n{C.PURPLE}🧠 AI Response:{C.END}")
        print(f"{C.CYAN}{'─' * 50}{C.END}")
        # Word wrap
        words = response.split()
        line = ""
        for word in words:
            if len(line) + len(word) > 48:
                print(f"  {line}")
                line = word
            else:
                line += " " + word if line else word
        if line:
            print(f"  {line}")
        print(f"{C.CYAN}{'─' * 50}{C.END}\n")


# ============================================================
# MAIN WIZARD
# ============================================================


class NEUGIWizard:
    """All-in-one NEUGI Wizard"""

    def __init__(self):
        self.ai = AIAgent()
        self.ui = WizardUI()

    def run(self):
        """Main entry point"""
        self.ui.header(f"{BRAND} WIZARD v3.0 - AI-Powered!")

        print(f"""
{C.BOLD}Welcome to {BRAND}!{C.END}

I'm your AI assistant. I can help you with:

  🎯  SETUP      - Install and configure {BRAND}
  🔧  REPAIR    - Fix problems automatically  
  🧠  DIAGNOSE  - Find out what's wrong
  💬  CHAT      - Ask me anything
  📦  PLUGINS   - Manage plugins
  🔄  UPDATE    - Check for updates
  👋  EXIT      - Exit

""")

        while True:
            choice = self.ui.menu(
                [
                    ("setup", "🎯 Setup / First Time Install"),
                    ("repair", "🔧 Repair / Fix Problems"),
                    ("diagnose", "🧠 Diagnose System"),
                    ("chat", "💬 Chat with AI"),
                    ("plugins", "📦 Manage Plugins"),
                    ("update", "🔄 Check for Updates"),
                    ("quit", "👋 Exit"),
                ],
                "What would you like to do?",
            )

            if choice == "1":
                self.run_setup()
            elif choice == "2":
                self.run_repair()
            elif choice == "3":
                self.run_diagnose()
            elif choice == "4":
                self.run_chat()
            elif choice == "5":
                self.run_plugins()
            elif choice == "6":
                self.run_update()
            elif choice == "7" or choice.lower() in ["quit", "exit", "q"]:
                print(f"\n{C.CYAN}Happy to help! See you next time! 👋{C.END}\n")
                break
            else:
                self.ui.warning("Invalid choice. Try again.")

    # ============================================================
    # SETUP FLOW
    # ============================================================

    def run_setup(self):
        """Setup wizard flow"""
        self.ui.header("🎯 SETUP WIZARD")

        # Check Ollama
        self.ui.info("Checking Ollama...")
        ollama = SystemChecker.check_ollama()

        if not ollama["running"]:
            self.ui.warning("Ollama is not running!")
            print(f"\n  {C.YELLOW}Shall I start it? (y/n): {C.END}", end="")
            if input().strip().lower() == "y":
                result = Repair.start_ollama()
                if result["success"]:
                    self.ui.success(result["message"])
                else:
                    self.ui.error(result["message"])
                    return
            else:
                self.ui.info("Okay, but NEUGI needs Ollama to work.")
                return
        else:
            self.ui.success(f"Ollama is running! ({len(ollama['models'])} models)")

        # Check if already installed
        neugi = SystemChecker.check_neugi()
        if neugi["installed"]:
            self.ui.warning(f"{BRAND} is already installed!")
            print(
                f"\n  {C.YELLOW}Re-run setup? This will reset config. (y/n): {C.END}",
                end="",
            )
            if input().strip().lower() != "y":
                return
            Repair.reset_config()

        # Get user info
        print(f"\n{C.BOLD}Let's get to know you!{C.END}\n")

        name = input(f"  {C.CYAN}What's your name? {C.END}").strip() or "User"

        # AI-powered use case detection
        print(f"\n  {C.PURPLE}🧠 Let AI help determine best setup...{C.END}\n")

        question = f"Hi {name}! What do you want to use AI for? (coding, chatting, research, automation)"
        print(f"  {C.CYAN}💭 {question}{C.END}")
        use_case = input(f"  {C.GREEN}> {C.END}").strip().lower()

        # Save config
        config = {
            "user": {"name": name},
            "use_case": use_case,
            "model": {"provider": "ollama_cloud", "model": MODEL},
            "assistant": {
                "primary": MODEL,
                "fallback": "nemotron-3-super:cloud",
            },
            "setup_date": datetime.now().isoformat(),
        }

        os.makedirs(os.path.join(NEUGI_DIR, "data"), exist_ok=True)
        config_path = os.path.join(NEUGI_DIR, "data", "config.json")

        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)

        self.ui.success(f"Setup complete! Config saved.")

        # Ask to start
        print(f"\n  {C.YELLOW}Start {BRAND} now? (y/n): {C.END}", end="")
        if input().strip().lower() == "y":
            self.start_neugi()

        # Show examples
        self.show_examples(use_case)

    def show_examples(self, use_case: str):
        """Show example questions"""
        examples = {
            "coding": [
                "Write a Python function for Fibonacci",
                "Explain what is recursion",
                "Help me debug this error",
            ],
            "chat": [
                "What's your opinion on AI?",
                "Tell me a joke",
                "What can you help me with?",
            ],
            "research": [
                "Summarize latest AI news",
                "Compare Ollama vs OpenAI",
                "What is NGI?",
            ],
            "automation": [
                "Create a backup script",
                "How to schedule tasks?",
                "Automate file organization",
            ],
        }

        sample = examples.get(use_case, examples["chat"])

        print(f"\n{C.BOLD}💬 Try these examples:{C.END}")
        for q in sample:
            print(f'  {C.PURPLE}•{C.END} "{q}"')
        print()

    # ============================================================
    # REPAIR FLOW
    # ============================================================

    def run_repair(self):
        """Auto-repair flow"""
        self.ui.header("🔧 AUTO-REPAIR")

        self.ui.info("Running system diagnosis...")

        # Quick check
        diagnosis = SystemChecker.full_diagnosis()

        issues = []

        # Check Ollama
        if not diagnosis["ollama"]["running"]:
            issues.append("Ollama not running")

        # Check NEUGI
        if not diagnosis["neugi"]["installed"]:
            issues.append("NEUGI not installed")
        elif not diagnosis["neugi"]["running"]:
            issues.append("NEUGI not running")

        # Check port
        if diagnosis["port_19888"]["in_use"]:
            issues.append("Port 19888 in use")

        if not issues:
            self.ui.success("No issues found! System looks good.")
            return

        self.ui.warning(f"Found {len(issues)} issue(s):")
        for issue in issues:
            print(f"  {C.RED}•{C.END} {issue}")

        print()

        # Auto-fix what we can
        choice = self.ui.menu(
            [
                ("auto", "🤖 Let AI fix automatically"),
                ("manual", "💬 Describe your problem to AI"),
                ("back", "← Go back"),
            ],
            "How would you like to proceed?",
        )

        if choice == "1":
            self.auto_repair(issues)
        elif choice == "2":
            self.manual_repair()
        # choice 3 = back

    def auto_repair(self, issues: List[str]):
        """AI automatically fixes issues"""
        self.ui.info("🧠 Analyzing issues with AI...")

        issue_text = ", ".join(issues)

        # Get AI diagnosis and fix
        diagnosis = self.ai.diagnose(issue_text)
        self.ui.ai_response(diagnosis)

        # Extract and execute fix
        fix_match = re.search(r"FIX:\s*(.+)", diagnosis, re.IGNORECASE)
        if fix_match:
            fix_cmd = fix_match.group(1).strip()
            print(f"\n  {C.YELLOW}Execute this fix? (y/n): {C.END}", end="")
            if input().strip().lower() == "y":
                result = self.ai.execute_fix(fix_cmd)
                if result.get("success"):
                    self.ui.success("Fix applied!")
                else:
                    self.ui.warning(f"Fix output: {result.get('output', 'Unknown')}")
        else:
            self.ui.warning("AI couldn't determine specific fix.")

    def manual_repair(self):
        """User describes problem, AI helps"""
        print(f"\n{C.BOLD}Describe your problem:{C.END}")
        print(f"  {C.CYAN}(e.g., 'neugi won't start', 'error message here'){C.END}\n")

        problem = input(f"  {C.GREEN}> {C.END}").strip()

        if not problem:
            return

        self.ui.info("🧠 Analyzing...")

        # Get system info
        diagnosis = SystemChecker.full_diagnosis()
        context = f"""
System status:
- Ollama: {diagnosis["ollama"]["running"]}
- NEUGI installed: {diagnosis["neugi"]["installed"]}
- NEUGI running: {diagnosis["neugi"]["running"]}
- Port 19888: {diagnosis["port_19888"]["in_use"]}
"""

        response = self.ai.ask(problem, context)
        self.ui.ai_response(response)

    # ============================================================
    # DIAGNOSE FLOW
    # ============================================================

    def run_diagnose(self):
        """System diagnosis"""
        self.ui.header("🧠 SYSTEM DIAGNOSIS")

        self.ui.info("Analyzing system...")

        diagnosis = SystemChecker.full_diagnosis()

        # Ollama
        print(f"\n{C.BOLD}📡 Ollama:{C.END}")
        if diagnosis["ollama"]["running"]:
            self.ui.success(f"Running! Models: {len(diagnosis['ollama']['models'])}")
            for m in diagnosis["ollama"]["models"][:5]:
                print(f"  • {m}")
        else:
            self.ui.error(f"Not running: {diagnosis['ollama']['error']}")

        # NEUGI
        print(f"\n{C.BOLD}🤖 {BRAND}:{C.END}")
        if diagnosis["neugi"]["installed"]:
            self.ui.success("Installed")
            if diagnosis["neugi"]["running"]:
                self.ui.success("Running on port 19888")
            else:
                self.ui.warning("Not running (start with: python3 neugi_swarm.py)")
        else:
            self.ui.warning("Not installed (run setup)")

        # Ask AI for recommendations
        print(f"\n{C.YELLOW}Ask AI for recommendations? (y/n): {C.END}", end="")
        if input().strip().lower() == "y":
            self.ui.info("🧠 Getting AI recommendations...")
            response = self.ai.ask(
                "Based on this system status, what should I do to optimize?",
                f"System: {json.dumps(diagnosis)}",
            )
            self.ui.ai_response(response)

    # ============================================================
    # CHAT FLOW
    # ============================================================

    def run_chat(self):
        """Chat with AI - with streaming!"""
        self.ui.header("💬 CHAT WITH AI (Streaming)")

        print(f"{C.CYAN}Type 'exit' to go back.{C.END}")
        print(f"{C.YELLOW}Responses stream in real-time!{C.END}\n")

        while True:
            message = input(f"{C.GREEN}> {C.END}").strip()

            if message.lower() in ["exit", "quit", "back"]:
                break

            if not message:
                continue

            print(f"\n{C.CYAN}", end="", flush=True)

            # Stream response
            for chunk in self.ai.chat_stream(message):
                print(chunk, end="", flush=True)

            print(f"{C.END}\n")

    # ============================================================
    # PLUGINS
    # ============================================================

    def run_plugins(self):
        """Manage plugins"""
        self.ui.header("📦 PLUGIN MANAGER")

        try:
            from neugi_plugins import PluginManager

            manager = PluginManager()
            plugins = manager.discover_plugins()

            if not plugins:
                print(f"\n{C.YELLOW}No plugins found.{C.END}")
                print(f"\n{C.CYAN}Plugin directory: ~/neugi/plugins{C.END}")
                print(f"Want to create an example plugin? (y/n): ", end="")
                if input().strip().lower() == "y":
                    from neugi_plugins import create_example_plugin

                    create_example_plugin("my_first_plugin")
                    self.ui.success("Example plugin created!")
                return

            print(f"\n{C.BOLD}Found {len(plugins)} plugins:{C.END}\n")

            for p in manager.list_plugins():
                status = f"{C.GREEN}✓{C.END}" if p["enabled"] else f"{C.RED}✗{C.END}"
                print(f"{status} {p['name']} v{p['version']}")
                print(f"   {p['description']}")
                print(f"   Functions: {', '.join(p['functions'])}")
                print()

            print(f"\n{C.CYAN}To add plugins, copy to: ~/neugi/plugins/{C.END}")

        except Exception as e:
            self.ui.error(f"Error: {e}")

    # ============================================================
    # UPDATE
    # ============================================================

    def run_update(self):
        """Check for updates"""
        self.ui.header("🔄 AUTO-UPDATER")

        try:
            from neugi_updater import AutoUpdater

            updater = AutoUpdater()

            self.ui.info("Checking for updates...")
            result = updater.check_for_update()

            print(f"\n{C.CYAN}Current version: {result['current']}{C.END}")
            print(f"{C.CYAN}Latest version: {result['latest']}{C.END}")

            if result["update_available"]:
                self.ui.success("Update available!")
                print(f"\n{C.YELLOW}Download and apply? (y/n): {C.END}", end="")
                if input().strip().lower() == "y":
                    self.ui.info("Downloading update...")
                    dl = updater.download_update()
                    if dl["success"]:
                        self.ui.success("Update downloaded!")
                        print(f"\n{C.YELLOW}Apply now? (y/n): {C.END}", end="")
                        if input().strip().lower() == "y":
                            apply = updater.apply_update()
                            if apply["success"]:
                                self.ui.success("Update applied!")
                            else:
                                self.ui.error(apply["message"])
            else:
                self.ui.success("You're up to date!")

        except Exception as e:
            self.ui.error(f"Error: {e}")

    # ============================================================
    # HELPERS
    # ============================================================

    def start_neugi(self):
        """Start NEUGI"""
        self.ui.info("Starting NEUGI...")

        script_path = os.path.join(NEUGI_DIR, "neugi_swarm.py")

        if not os.path.exists(script_path):
            self.ui.warning(f"neugi_swarm.py not found in {NEUGI_DIR}")
            print(f"\n  {C.YELLOW}Download from GitHub? (y/n): {C.END}", end="")
            if input().strip().lower() == "y":
                self.download_files()

        # Start
        try:
            subprocess.Popen(
                [sys.executable, script_path],
                cwd=NEUGI_DIR,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            self.ui.success(f"{BRAND} started!")
            self.ui.info("Open: http://localhost:19888")
        except Exception as e:
            self.ui.error(f"Failed to start: {e}")

    def download_files(self):
        """Download NEUGI files"""
        self.ui.info("Downloading...")

        files = [
            "neugi_swarm.py",
            "neugi_assistant.py",
            "neugi_swarm_agents.py",
            "neugi_swarm_tools.py",
            "neugi_telegram.py",
            "neugi_technician.py",
            "dashboard.html",
        ]

        os.makedirs(NEUGI_DIR, exist_ok=True)

        base_url = "https://raw.githubusercontent.com/atharia-agi/neugi_swarm/master"

        for f in files:
            try:
                url = f"{base_url}/{f}"
                r = requests.get(url, timeout=10)
                if r.ok:
                    with open(os.path.join(NEUGI_DIR, f), "w") as fp:
                        fp.write(r.text)
                    self.ui.success(f"Downloaded: {f}")
            except:
                self.ui.error(f"Failed: {f}")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    wizard = NEUGIWizard()
    wizard.run()
