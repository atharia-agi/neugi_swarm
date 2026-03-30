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

Version: 15.6.0
Date: March 15, 2026
"""

import os
import json
import re
import subprocess
import sys
import requests
import webbrowser
import psutil
import platform

try:
    import winreg
except ImportError:
    winreg = None
from typing import Dict, List
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
    WHITE = "\033[97m"
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
        
CORE DIRECTIVES:
1. STABILITY FIRST: Never compromise host system boot or network integrity.
2. PRECISION EXECUTION: Every action must have a clear diagnostic reason.
3. AUTHENTIC TRANSPARENCY: Report exact commands and reasoning honestly.
4. USER GUARDRAILS: High-risk actions (recursive deletions, system-wide changes) MUST be prompt-verified.

Your role:
- Setting up {BRAND} Swarm
- Diagnosing problems
- Fixing issues automatically
- Optimizing performance

Be helpful, clear, and concise. When asked to fix something, actually perform the action."""

    def nexus_chat(self, message: str):
        """Send message to Sovereign Nexus (Engine API)"""
        try:
            r = requests.post(
                "http://localhost:19888/api/chat",
                json={"message": message},
                timeout=120,
            )
            if r.ok:
                return r.json().get("response", "").strip()
            return f"Nexus API Error: {r.status_code}"
        except Exception as e:
            return f"Cannot link to Nexus: {e}"

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
                        except Exception:
                            continue

        except Exception as e:
            yield f"Error: {e}"

    def chat(self, message: str) -> str:
        """Send message to AI and get non-streaming response"""
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
                data = response.json()
                return data.get("response", "").strip()
            return f"Error: {response.status_code}"

        except Exception as e:
            return f"Error: {e}"

    def ask(self, question: str, context: str = "") -> str:
        """Ask AI with context"""
        prompt = f"{context}\n\nQuestion: {question}\n\nAnswer:" if context else question
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
FIX: [command or action to fix]
"""
        return self.chat(prompt)

    def execute_fix(self, fix_command: str) -> Dict:
        """Execute a fix command"""
        result = {"command": fix_command, "success": False, "output": ""}
        import os

        # Stability Check: High-Risk Commands
        high_risk_keywords = ["rm -rf /", "rm -rf *", "del /s", "format", "mkfs"]
        is_high_risk = any(keyword in fix_command.lower() for keyword in high_risk_keywords)

        if is_high_risk:
            print(f"\n{C.RED}{C.BOLD}⚠️  EXTREME RISK DETECTED:{C.END}")
            print(f"  Command: {C.YELLOW}{fix_command}{C.END}")
            print(f"  {C.WHITE}Core Directives require manual confirmation for this action.{C.END}")
            confirm = input(
                f"\n  {C.YELLOW}Are you absolutely sure? (type 'CONFIRM'): {C.END}"
            ).strip()
            if confirm != "CONFIRM":
                result["output"] = "Action cancelled by user safety guard."
                return result

        result["description"] = "UNRESTRICTED SYSTEM EXECUTION"
        try:
            proc = subprocess.run(
                fix_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=None if os.environ.get("NEUGI_GOD_MODE") == "1" else 60,
            )
            result["success"] = proc.returncode == 0
            result["output"] = proc.stdout or proc.stderr
        except Exception as e:
            result["output"] = str(e)

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
            except Exception:
                pass

        try:
            r = requests.get("http://localhost:19888/health", timeout=2)
            result["running"] = r.ok
        except Exception:
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
        """Run full system diagnosis with granular checks"""
        diag = {
            "ollama": SystemChecker.check_ollama(),
            "neugi": SystemChecker.check_neugi(),
            "port_19888": SystemChecker.check_port(19888),
            "granular_issues": [],
        }

        # Migrated Granular Checks from legacy Technician
        # 1. Check Channel Tokens
        config = diag["neugi"].get("config")
        if config:
            channels = config.get("channels", {})
            for name, chan_config in channels.items():
                platform = chan_config.get("platform")
                if platform == "telegram" and not chan_config.get("bot_token"):
                    diag["granular_issues"].append(f"Telegram channel '{name}' missing bot_token")
                elif platform == "discord" and not chan_config.get("webhook_url"):
                    diag["granular_issues"].append(f"Discord channel '{name}' missing webhook_url")

        # 2. Check Database Corruption
        for db_name in ["memory.db", "sessions.db", "agents.db"]:
            db_path = os.path.join(NEUGI_DIR, "data", db_name)
            if os.path.exists(db_path):
                try:
                    import sqlite3

                    conn = sqlite3.connect(db_path)
                    conn.execute("SELECT 1")
                    conn.close()
                except Exception:
                    diag["granular_issues"].append(f"Database corrupted: {db_name}")

        # 3. Check Session DB Size
        sessions_db = os.path.join(NEUGI_DIR, "data", "sessions.db")
        if os.path.exists(sessions_db):
            size = os.path.getsize(sessions_db)
            if size > 100 * 1024 * 1024:  # 100MB
                diag["granular_issues"].append(
                    f"Session database is large ({size / 1024 / 1024:.1f}MB)"
                )

        return diag


# ============================================================
# PERSISTENCE (AUTO-BOOT)
# ============================================================


class PersistenceManager:
    """Manage system persistence (auto-boot)"""

    REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
    APP_NAME = "NEUGI_Sovereign_Intelligence"

    @staticmethod
    def is_enabled() -> bool:
        """Check if auto-boot is enabled in registry"""
        if platform.system() != "Windows" or not winreg:
            return False

        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, PersistenceManager.REG_PATH, 0, winreg.KEY_READ
            )
            _, _ = winreg.QueryValueEx(key, PersistenceManager.APP_NAME)
            winreg.CloseKey(key)
            return True
        except WindowsError:
            return False

    @staticmethod
    def enable() -> bool:
        """Enable auto-boot by adding registry key"""
        if platform.system() != "Windows" or not winreg:
            return False

        try:
            # Point to the master start script
            batch_path = os.path.join(NEUGI_DIR, "neugi_start.bat")
            if not os.path.exists(batch_path):
                # Fallback to creating a simple script if missing
                return False

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                PersistenceManager.REG_PATH,
                0,
                winreg.KEY_SET_VALUE,
            )
            winreg.SetValueEx(
                key,
                PersistenceManager.APP_NAME,
                0,
                winreg.REG_SZ,
                f'"{batch_path}"',
            )
            winreg.CloseKey(key)
            return True
        except Exception:
            return False

    @staticmethod
    def disable() -> bool:
        """Disable auto-boot by removing registry key"""
        if platform.system() != "Windows" or not winreg:
            return False

        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                PersistenceManager.REG_PATH,
                0,
                winreg.KEY_SET_VALUE,
            )
            winreg.DeleteValue(key, PersistenceManager.APP_NAME)
            winreg.CloseKey(key)
            return True
        except WindowsError:
            return True  # Already disabled
        except Exception:
            return False


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
# ENHANCED WIZARD UI - Maximized for Power Users
# ============================================================


class WizardUI:
    """Beautiful CLI UI - Enhanced Edition"""

    @staticmethod
    def header(title: str):
        print(f"\n{C.CYAN}{'═' * 60}")
        print(f"  🤖 {title}")
        print(f"{'═' * 60}{C.END}\n")

    @staticmethod
    def quick_status():
        """Show quick system status"""
        import requests

        try:
            r = requests.get("http://localhost:11434", timeout=2)
            ollama = "✅ Running" if r.status_code == 200 else "❌ Error"
        except:
            ollama = "❌ Not Running"

        print(f"""
{C.CYAN}╔═══════════════════════════════════════════════════════════════╗
║                    🚀 NEUGI QUICK STATUS                             ║
╠═══════════════════════════════════════════════════════════════════════╣
║  Ollama:    {ollama:<50}║
║  Port:      ✅ 19888 (Dashboard) | 19889 (MCP)                      ║
╚═══════════════════════════════════════════════════════════════════════╝
{Colors.END}
        """)

    @staticmethod
    def search_menu(options: List[tuple], search_prompt: str = None) -> Optional[str]:
        """Searchable menu - type to filter"""
        if search_prompt:
            query = input(f"{C.YELLOW}Search (or Enter for menu): {C.END}").strip().lower()
            if query:
                filtered = [(k, d) for k, d in options if query in d.lower() or query in k.lower()]
                if filtered:
                    print(f"\n{C.CYAN}Results for '{query}':{C.END}")
                    for i, (key, desc) in enumerate(filtered, 1):
                        print(f"  {C.GREEN}{i}{C.END}. {desc}")

                    choice = input(f"\n{C.CYAN}> {C.END}").strip()
                    if choice.isdigit() and 1 <= int(choice) <= len(filtered):
                        return filtered[int(choice) - 1][0]
                    return choice

        return None

    @staticmethod
    def menu(options: List[tuple], title: str = "Choose an option:") -> str:
        print(f"{C.BOLD}{title}{C.END}\n")

        # Group options by category
        categories = {}
        for key, desc in options:
            cat = desc.split()[0] if desc else "Other"
            if cat not in categories:
                categories[cat] = []
            categories[cat].append((key, desc))

        # Display with keyboard shortcuts
        for i, (key, desc) in enumerate(options, 1):
            shortcut = ""
            if i <= 9:
                shortcut = f" [{i}]"
            print(f"  {C.GREEN}{i}{shortcut}{C.END}. {desc}")

        print(f"\n  {C.YELLOW}💡 Tip: Type a number or search{C.END}")
        choice = input(f"\n{C.CYAN}> {C.END}").strip()
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
        print(f"\n{C.PURPLE}🧠 AI Response:{C.END}")
        print(f"{C.CYAN}{'─' * 50}{C.END}")
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

    @staticmethod
    def print_hotkeys():
        """Display keyboard shortcuts"""
        print(f"""
{C.YELLOW}╔═══════════════════════════════════════╗
║          ⌨️  KEYBOARD SHORTCUTS               ║
╠═══════════════════════════════════════════════╣
║  [1-9]          Quick select option 1-9      ║
║  [ Enter ]      Confirm / Next step          ║
║  [ Ctrl+C ]     Exit / Cancel                ║
║  [ / ]          Search menu                  ║
║  [ ? ]          Show help                    ║
╚═══════════════════════════════════════════════╝
{C.END}
        """)


# ============================================================
# MAIN WIZARD
# ============================================================


class NEUGIWizard:
    """All-in-one NEUGI Wizard"""

    def __init__(self):
        self.ai = AIAgent()
        self.ui = WizardUI()

    def run(self):
        """Main entry point - Enhanced with Quick Status"""

        # Quick status on start
        self.ui.quick_status()

        mode_text = (
            f"{C.RED}{C.BOLD}[GOD MODE ACTIVE]{C.END} "
            if os.environ.get("NEUGI_GOD_MODE") == "1"
            else f"{C.GREEN}[FULL POWER ACTIVE]{C.END} "
        )
        self.ui.header(f"{BRAND} WIZARD v4.0 - MAXIMUM POWER - {mode_text}")

        print(f"""
{C.BOLD}Welcome to {BRAND}! The Ultimate Agent Platform{C.END}

▸ 9 Built-in Agents (Aurora, Cipher, Nova, etc.)
▸ 50+ Tools (Web, Code, AI, Data, Comm)
▸ MCP Compatible (Claude Code, OpenClaw)
▸ Auto-Learning System (Unique!)
▸ Agent Studio (Create your own agents)
▸ Natural Language CLI (No commands to memorize!)

Quick Actions (just type the number):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  [1] 🎯 QUICK START    - Start using NEUGI immediately
  [2] 🤖 AGENT STUDIO   - Create your custom agents
  [3] 💬 CHAT           - Chat with AI
  [4] 🎨 WORKFLOWS     - Visual workflow builder
  [5] 🔍 DIAGNOSE      - System health check
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Or choose from the full menu below:
        """)

        print("""  🤖  AGENTS     - Agents SDK
  ⌘  CLI        - CLI Framework
  🧠  ML         - ML Pipeline
  🔗  DATAPIPE   - Data Pipeline
  🔔  NOTIFY     - Notification System
  🪝  WEBHOOK    - Webhook Manager
  🚦  RATELIMIT  - Rate Limiter
  ⚙️  CONFIG     - Config Manager
  📝  TEMPLATE   - Template Engine
  📑  REPORT     - Report Generator
  📉  ANALYTICS  - Analytics Dashboard
  📌  APIVERSION - API Versioning
  📖  APIDOCS    - API Docs UI
  ✅  VALIDATOR  - Request Validator
  💾  CACHE      - Response Cacher
  📊  METRICS    - Metrics Exporter
  💚  HEALTH     - Health Checks
  ⚡  CIRCUITDASH - Circuit Dashboard
  📚  REGISTRY   - Service Registry
  🔄  CONFIGSYNC - Config Sync
  🚀  DEPLOY     - Deployment Manager
  λ   SERVERLESS - Serverless Functions
  🌐  EDGE       - Edge Computing
  📬  MQ         - Message Queue
  🌊  STREAM     - Stream Processor
  📦  BATCH      - Batch Jobs
  📈  APM        - APM Dashboard
  🔍  LOGANALYZER - Log Analyzer
  🚨  ALERT      - Alert Manager
  🆘  INCIDENT   - Incident Response
  💰  COST       - Cost Optimizer
  👋  EXIT       - Shutdown Wizard
        """)

        choice = self.ui.menu(
            [
                ("1", "🎯 QUICK START"),
                ("2", "🤖 AGENT STUDIO"),
                ("3", "💬 CHAT"),
                ("4", "🎨 WORKFLOWS"),
                ("5", "🔍 DIAGNOSE/HEALTH"),
                ("rescue", "🆘 WIZARD RESCUE"),
                ("setup", "🎯 SETUP"),
                ("repair", "🔧 REPAIR"),
                ("diagnose", "🧠 DIAGNOSE"),
                ("chat", "💬 CHAT"),
                ("plugins", "📦 PLUGINS"),
                ("update", "🔄 UPDATE"),
                ("security", "🔐 SECURITY"),
                ("memory", "🧊 MEMORY"),
                ("soul", "🎭 SOUL"),
                ("skills", "📚 SKILLS"),
                ("schedule", "⏰ SCHEDULE"),
                ("mcp", "🌐 MCP"),
                ("apps", "📱 APPS"),
                ("workflows", "🔀 WORKFLOWS"),
                ("tests", "🧪 TESTS"),
                ("api", "🌍 API"),
                ("docker", "🐳 DOCKER"),
                ("monitoring_v2", "📈 MONITORING"),
                ("workflow_builder", "🎨 WORKFLOW BUILDER"),
                ("automation", "🤖 AUTOMATION"),
                ("database", "🗄️ DATABASE"),
                ("palette", "⌨️ PALETTE"),
                ("file_manager", "📁 FILES"),
                ("code", "💻 CODE"),
                ("marketplace", "🛒 MARKET"),
                ("encryption", "🔒 ENCRYPT"),
                ("ssh", "🔐 SSH"),
                ("cache", "🧠 CACHE"),
                ("logs", "📝 LOGS"),
                ("backup", "💾 BACKUP"),
                ("k8s", "☸️ K8S"),
                ("websocket", "🔌 WS"),
                ("graphql", "📊 GQL"),
                ("prometheus", "📈 PROMETHEUS"),
                ("gateway", "🚪 GATEWAY"),
                ("discovery", "🔍 DISCOVERY"),
                ("secrets", "🔑 SECRETS"),
                ("multicluster", "🌍 MULTI"),
                ("circuit", "⚡ CIRCUIT"),
                ("lb", "⚖️ LB"),
                ("mesh", "🕸️ MESH"),
                ("cdn", "🌐 CDN"),
                ("eventbus", "📨 EVENT"),
                ("agents", "🤖 AGENTS"),
                ("agentstudio", "🎨 AGENT STUDIO"),
                ("rescue", "🆘 WIZARD RESCUE"),
                ("learner", "🧠 AUTO-LEARNER"),
                ("cli", "⌘ CLI"),
                ("ml", "🧠 ML"),
                ("datapipe", "🔗 DATAPIPE"),
                ("notify", "🔔 NOTIFY"),
                ("webhook", "🪝 WEBHOOK"),
                ("ratelimit", "🚦 RATELIMIT"),
                ("config", "⚙️ CONFIG"),
                ("template", "📝 TEMPLATE"),
                ("report", "📑 REPORT"),
                ("analytics", "📉 ANALYTICS"),
                ("apiversion", "📌 APIVERSION"),
                ("apidocs", "📖 APIDOCS"),
                ("validator", "✅ VALIDATOR"),
                ("cache", "💾 CACHE"),
                ("metrics", "📊 METRICS"),
                ("health", "💚 HEALTH"),
                ("circuitdash", "⚡ CIRCUITDASH"),
                ("registry", "📚 REGISTRY"),
                ("configsync", "🔄 CONFIGSYNC"),
                ("deploy", "🚀 DEPLOY"),
                ("serverless", "λ SERVERLESS"),
                ("edge", "🌐 EDGE"),
                ("mq", "📬 MQ"),
                ("stream", "🌊 STREAM"),
                ("batch", "📦 BATCH"),
                ("apm", "📈 APM"),
                ("loganalyzer", "🔍 LOGANALYZER"),
                ("alert", "🚨 ALERT"),
                ("incident", "🆘 INCIDENT"),
                ("cost", "💰 COST"),
                ("quit", "👋 EXIT"),
            ],
            "What would you like to do?",
        )

        while True:
            choice = self.ui.menu(
                [
                    ("heartbeat", "💓 Sovereign Heartbeat"),
                    ("topology", "🌐 Network Topology"),
                    ("tools", "🛠️ Skill Registry"),
                    ("monitor", "📊 Live Monitor"),
                    ("logs", "📄 View System Logs"),
                    ("autoboot", "🔄 Toggle Auto-Boot (BETA)"),
                    ("setup", "🎯 Setup / First Time Install"),
                    ("repair", "🔧 Repair / Fix Problems"),
                    ("diagnose", "🧠 Diagnose System"),
                    ("chat", "💬 Chat with AI"),
                    ("plugins", "📦 Manage Plugins"),
                    ("update", "🔄 Check for Updates"),
                    ("security", "🔐 Security Settings"),
                    ("memory", "🧊 Memory System"),
                    ("soul", "🎭 Personality / Soul"),
                    ("skills", "📚 Skills V2"),
                    ("schedule", "⏰ Task Scheduler"),
                    ("mcp", "🌐 MCP Server"),
                    ("apps", "📱 App Integrations"),
                    ("workflows", "🔀 Workflow Automation"),
                    ("tests", "🧪 Run Tests"),
                    ("api", "🌍 REST API Server"),
                    ("docker", "🐳 Docker Management"),
                    ("monitoring_v2", "📈 Advanced Monitoring"),
                    ("workflow_builder", "🎨 Visual Workflow Builder"),
                    ("automation", "🤖 Automation Engine"),
                    ("database", "🗄️ Database Management"),
                    ("palette", "⌨️ Command Palette"),
                    ("file_manager", "📁 File Manager"),
                    ("code", "💻 Code Interpreter"),
                    ("marketplace", "🛒 Plugin Marketplace"),
                    ("encryption", "🔒 Encryption Tools"),
                    ("ssh", "🔐 SSH Manager"),
                    ("cache", "🧠 Cache Layer"),
                    ("logs", "📝 Log Aggregator"),
                    ("backup", "💾 Backup System"),
                    ("k8s", "☸️ Kubernetes"),
                    ("websocket", "🔌 WebSocket Server"),
                    ("graphql", "📊 GraphQL API"),
                    ("prometheus", "📈 Prometheus Metrics"),
                    ("gateway", "🚪 API Gateway"),
                    ("discovery", "🔍 Service Discovery"),
                    ("secrets", "🔑 Secrets Manager"),
                    ("multicluster", "🌍 Multi-Cluster"),
                    ("circuit", "⚡ Circuit Breaker"),
                    ("lb", "⚖️ Load Balancer"),
                    ("mesh", "🕸️ Service Mesh"),
                    ("cdn", "🌐 CDN Manager"),
                    ("eventbus", "📨 Event Bus"),
                    ("agents", "🤖 Agents SDK"),
                    ("agentstudio", "🎨 Agent Studio"),
                    ("learner", "🧠 Auto-Learner"),
                    ("rescue", "🆘 WIZARD RESCUE - Fix Any Problem!"),
                    ("cli", "⌘ CLI Framework"),
                    # v23.x NEW FEATURES
                    ("ml", "🧠 ML Pipeline"),
                    ("datapipe", "🔗 Data Pipeline"),
                    ("notify", "🔔 Notification System"),
                    ("webhook", "🪝 Webhook Manager"),
                    ("ratelimit", "🚦 Rate Limiter"),
                    ("config", "⚙️ Config Manager"),
                    ("template", "📝 Template Engine"),
                    ("report", "📑 Report Generator"),
                    ("analytics", "📉 Analytics Dashboard"),
                    # v24.x NEW FEATURES
                    ("apiversion", "📌 API Versioning"),
                    ("apidocs", "📖 API Docs UI"),
                    ("validator", "✅ Request Validator"),
                    ("cache", "💾 Response Cacher"),
                    ("metrics", "📊 Metrics Exporter"),
                    ("health", "💚 Health Checks"),
                    ("circuitdash", "⚡ Circuit Dashboard"),
                    ("registry", "📚 Service Registry"),
                    ("configsync", "🔄 Config Sync"),
                    ("deploy", "🚀 Deployment Manager"),
                    # v25.x NEW FEATURES
                    ("serverless", "λ Serverless Functions"),
                    ("edge", "🌐 Edge Computing"),
                    ("mq", "📬 Message Queue"),
                    ("stream", "🌊 Stream Processor"),
                    ("batch", "📦 Batch Jobs"),
                    ("apm", "📈 APM Dashboard"),
                    ("loganalyzer", "🔍 Log Analyzer"),
                    ("alert", "🚨 Alert Manager"),
                    ("incident", "🆘 Incident Response"),
                    ("cost", "💰 Cost Optimizer"),
                    ("quit", "👋 Exit"),
                ],
                "What would you like to do?",
            )

            if choice == "1":
                self.run_heartbeat()
            elif choice == "2":
                self.run_topology()
            elif choice == "3":
                self.run_tools()
            elif choice == "4":
                self.run_monitor()
            elif choice == "5":
                self.run_logs()
            elif choice == "6":
                self.run_autoboot()
            elif choice == "7":
                self.run_setup()
            elif choice == "8":
                self.run_repair()
            elif choice == "9":
                self.run_diagnose()
            elif choice == "10":
                self.run_chat()
            elif choice == "11":
                self.run_plugins()
            elif choice == "12":
                self.run_update()
            elif choice == "13":
                self.run_security()
            elif choice == "14":
                self.run_memory()
            elif choice == "15":
                self.run_soul()
            elif choice == "16":
                self.run_skills()
            elif choice == "17":
                self.run_scheduler()
            elif choice == "18":
                self.run_mcp()
            elif choice == "19":
                self.run_apps()
            elif choice == "20":
                self.run_workflows()
            elif choice == "21":
                self.run_tests()
            elif choice == "22":
                self.run_api()
            elif choice == "23":
                self.run_docker()
            elif choice == "24":
                self.run_monitoring_v2()
            elif choice == "25":
                self.run_workflow_builder()
            elif choice == "26":
                self.run_automation()
            elif choice == "27":
                self.run_database()
            elif choice == "28":
                self.run_palette()
            elif choice == "29":
                self.run_file_manager()
            elif choice == "30":
                self.run_code_interpreter()
            elif choice == "31":
                self.run_marketplace()
            elif choice == "32":
                self.run_encryption()
            elif choice == "33":
                self.run_ssh()
            elif choice == "34":
                self.run_cache()
            elif choice == "35":
                self.run_logs()
            elif choice == "36":
                self.run_backup()
            elif choice == "37":
                self.run_k8s()
            elif choice == "38":
                self.run_websocket()
            elif choice == "39":
                self.run_graphql()
            elif choice == "40":
                self.run_prometheus()
            elif choice == "41":
                self.run_gateway()
            elif choice == "42":
                self.run_discovery()
            elif choice == "43":
                self.run_secrets()
            elif choice == "44":
                self.run_multicluster()
            elif choice == "45":
                self.run_circuit()
            elif choice == "46":
                self.run_lb()
            elif choice == "47":
                self.run_mesh()
            elif choice == "48":
                self.run_cdn()
            elif choice == "49":
                self.run_eventbus()
            elif choice == "50":
                self.run_agents()
            elif choice == "51" or choice == "agentstudio":
                self.run_agent_studio()
            elif choice == "52" or choice == "rescue":
                self.run_rescue()
            elif choice == "53":
                self.run_learner()
            elif choice == "54":
                self.run_cli()
            elif choice == "52":
                self.run_ml_pipeline()
            elif choice == "53":
                self.run_data_pipeline()
            elif choice == "54":
                self.run_notification()
            elif choice == "55":
                self.run_webhook()
            elif choice == "56":
                self.run_rate_limiter()
            elif choice == "57":
                self.run_config_manager()
            elif choice == "58":
                self.run_template_engine()
            elif choice == "59":
                self.run_report_generator()
            elif choice == "60":
                self.run_analytics()
            elif choice == "61":
                self.run_api_versioning()
            elif choice == "62":
                self.run_api_docs()
            elif choice == "63":
                self.run_request_validator()
            elif choice == "64":
                self.run_response_cache()
            elif choice == "65":
                self.run_metrics_exporter()
            elif choice == "66":
                self.run_health_checks()
            elif choice == "67":
                self.run_circuit_dashboard()
            elif choice == "68":
                self.run_service_registry()
            elif choice == "69":
                self.run_config_sync()
            elif choice == "70":
                self.run_deployment_manager()
            elif choice == "71":
                self.run_serverless()
            elif choice == "72":
                self.run_edge_computing()
            elif choice == "73":
                self.run_message_queue()
            elif choice == "74":
                self.run_stream_processor()
            elif choice == "75":
                self.run_batch_jobs()
            elif choice == "76":
                self.run_apm_dashboard()
            elif choice == "77":
                self.run_log_analyzer()
            elif choice == "78":
                self.run_alert_manager()
            elif choice == "79":
                self.run_incident_response()
            elif choice == "80":
                self.run_cost_optimizer()
            elif choice == "81" or choice.lower() in ["quit", "exit", "q"]:
                print(f"\n{C.CYAN}Happy to help! See you next time! 👋{C.END}\n")
                break
            else:
                self.ui.warning("Invalid choice. Try again.")

    def show_disclaimer(self):
        """Display a bold risk disclaimer"""
        self.ui.header("⚠️  MANDATORY RISK DISCLAIMER")
        print(f"""
  {C.RED}{C.BOLD}IMPORTANT: UNRESTRICTED SYSTEM ACCESS{C.END}
  
  NEUGI is an autonomous agentic system. This Wizard and the
  associated swarm agents have the authority to:
  
  1.  Execute system-level commands (BASH/CMD/PowerShell).
  2.  Modify, create, or delete files in assigned directories.
  3.  Access local network services and external AI providers.
  
  {C.YELLOW}RISK ACKNOWLEDGMENT:{C.END}
  By proceeding, you acknowledge that NEUGI is provided "as is"
  and carries risks inherent to autonomous AI systems. The
  developers are not responsible for unintended system changes
  or data loss resulting from AI-driven actions.
        """)
        confirm = input(f"  {C.GREEN}Do you agree to proceed? (y/n): {C.END}").strip().lower()
        if confirm != "y":
            self.ui.error("Disclaimer not accepted. Exiting...")
            sys.exit(0)

    # ============================================================
    # HEARTBEAT FLOW
    # ============================================================

    def run_heartbeat(self):
        """Quick Sovereign Health Check"""
        self.ui.header("💓 SOVEREIGN HEARTBEAT")

        # CPU/RAM
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        self.ui.info(f"System Load: CPU {cpu}% | RAM {ram}%")

        # Ollama
        ollama = SystemChecker.check_ollama()
        if ollama["running"]:
            self.ui.success(f"Ollama Status: ONLINE ({len(ollama['models'])} models mapped)")
        else:
            self.ui.error("Ollama Status: OFFLINE")

        # Dashboard
        dashboard_url = "http://localhost:19888"
        try:
            r = requests.get(f"{dashboard_url}/api/status", timeout=1)
            if r.ok:
                data = r.json()
                self.ui.success(f"Sovereign Node: ACTIVE ({dashboard_url})")
                self.ui.info(f"Agents: {len(data.get('neugi', {}).get('agents', []))} online")
            else:
                self.ui.warning(f"Sovereign Node: IDLE ({dashboard_url})")
        except Exception:
            self.ui.warning(f"Sovereign Node: OFFLINE ({dashboard_url})")

        print(f"\n{C.GREEN}Everything seems in order. Sovereign Intelligence is stable.{C.END}")
        input(f"\n{C.CYAN}Press Enter to return to menu... {C.END}")

    # ============================================================
    # SETUP FLOW
    # ============================================================

    def run_setup(self):
        """Setup wizard flow"""
        self.show_disclaimer()
        self.ui.header("🎯 SETUP WIZARD")

        import random

        NEUGI_SATIRE_QUOTES = [
            "We don't have any claw, but we have some real brain...",
            "Loading agents... faster than a bloated JSON yaml pipeline.",
            "Initializing neural net. No blockchains were harmed.",
            "Bypassing hardcoded YAML configs... because we actually think.",
            "Executing gracefully... take notes, OpenCLAW.",
        ]
        satire_quote = random.choice(NEUGI_SATIRE_QUOTES)

        # Check Ollama
        self.ui.info(f"Booting up real intelligence... ({satire_quote})")
        self.ui.info("Checking Ollama backend...")
        ollama = SystemChecker.check_ollama()

        if not ollama["running"]:
            self.ui.info("Auto-starting Ollama locally in the background...")
            result = Repair.start_ollama()
            if result["success"]:
                self.ui.success("Magic: Ollama linked dynamically!")
            else:
                self.ui.error(f"Could not auto-start Ollama: {result['message']}")
                self.ui.warning("Please verify your Ollama installation manually.")
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

        question = (
            f"Hi {name}! What do you want to use AI for? (coding, chatting, research, automation)"
        )
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

        self.ui.success("Setup complete! Config saved.")

        # Ask to start
        print(f"\n  {C.YELLOW}Start {BRAND} now? (y/n): {C.END}", end="")
        if input().strip().lower() == "y":
            self.start_neugi()

        # Show examples
        self.show_examples(use_case)

        # Final Polishing: Auto-launch Dashboard
        self.ui.success("Launching Sovereign Dashboard...")
        dashboard_url = "http://localhost:19888"
        webbrowser.open(dashboard_url)

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
        """Enhanced Chat with Nexus Auto-Parity"""
        self.ui.header("💬 SOVEREIGN CHAT INTERFACE")

        # Detect Nexus
        use_nexus = False
        try:
            r = requests.get("http://localhost:19888/health", timeout=1)
            if r.ok:
                self.ui.success("Sovereign Nexus detected! Link established.")
                print(f"  {C.CYAN}Mode: SWARM INTELLIGENCE (Nexus API){C.END}\n")
                use_nexus = True
            else:
                self.ui.warning("Nexus Offline. Falling back to direct model access.")
                print(f"  {C.YELLOW}Mode: DIRECT AI (Ollama Local){C.END}\n")
        except Exception:
            self.ui.warning("Nexus Offline. Falling back to direct model access.")
            print(f"  {C.YELLOW}Mode: DIRECT AI (Ollama Local){C.END}\n")

        print(f"{C.CYAN}Type 'exit' to go back.{C.END}\n")

        while True:
            message = input(f"{C.GREEN}> {C.END}").strip()

            if message.lower() in ["exit", "quit", "back"]:
                break

            if not message:
                continue

            if use_nexus:
                self.ui.info("Nexus processing swarm directive...")
                response = self.ai.nexus_chat(message)
                self.ui.ai_response(response)
            else:
                print(f"\n{C.CYAN}", end="", flush=True)
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
                print("Want to create an example plugin? (y/n): ", end="")
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
    # SECURITY
    # ============================================================

    def run_security(self):
        """Configure security settings"""
        self.ui.header("🔐 SECURITY SETTINGS")

        try:
            from neugi_security import security_wizard

            security_wizard()
        except Exception as e:
            self.ui.error(f"Error: {e}")

    # ============================================================
    # MEMORY SYSTEM (BrowserOS Style)
    # ============================================================

    def run_memory(self):
        """Two-tier memory system"""
        self.ui.header("🧊 MEMORY SYSTEM")

        print(f"""
{C.BOLD}Two-Tier Memory (BrowserOS Style):{C.END}

  • CORE MEMORY   - Permanent facts (CORE.md)
  • DAILY MEMORY - Session notes (auto-expire 30 days)

Options:
  1. 📖 Read Core Memory
  2. 📝 Search Memory
  3. ➕ Add Memory Fact
  4. 📊 Memory Stats
  5. 🧹 Cleanup Old Memory

""")

        choice = input(f"{C.CYAN}Choice>{C.END} ").strip()

        try:
            from neugi_memory_v2 import TwoTierMemory

            memory = TwoTierMemory()

            if choice == "1":
                print(f"\n{C.BOLD}Core Memory:{C.END}\n")
                print(memory.read_core())

            elif choice == "2":
                query = input("Search query: ")
                results = memory.recall(query)
                print(f"\n{C.BOLD}Results:{C.END}")
                if results["core"]:
                    print("\n🔶 Core Memory Matches:")
                    for r in results["core"]:
                        print(f"  {r}")
                if results["daily"]:
                    print("\n📝 Daily Memory Matches:")
                    for r in results["daily"][:5]:
                        print(f"  [{r['date']}] {r['content'][:100]}")

            elif choice == "3":
                fact = input("Fact to remember: ")
                memory.auto_remember(fact)
                print(f"\n✅ Remembered!")

            elif choice == "4":
                stats = memory.get_stats()
                print(f"\n{C.BOLD}Memory Stats:{C.END}")
                print(f"  Core: {stats['core_size_kb']} KB")
                print(f"  Daily Files: {stats['daily_files_count']}")
                print(f"  Total Size: {stats['daily_size_kb']} KB")

            elif choice == "5":
                memory.cleanup_old_daily(30)
                print(f"\n✅ Cleaned up!")

        except Exception as e:
            self.ui.error(f"Error: {e}")

        input(f"\n{C.CYAN}Press Enter...{C.END}")

    # ============================================================
    # SOUL SYSTEM (Personality)
    # ============================================================

    def run_soul(self):
        """Personality system"""
        self.ui.header("🎭 SOUL / PERSONALITY")

        print(f"""
{C.BOLD}Soul System (BrowserOS Style):{C.END}

  Define how NEUGI behaves - tone, traits, boundaries

Available Presets:
  • default      - Helpful technical assistant
  • assistant   - Friendly and explanatory
  • senior_dev  - Production-focused developer
  • debugger    - Analytical problem solver
  • security    - Security-focused expert

""")

        choice = input(f"{C.CYAN}Choice (1=Show, 2=List, 3=Load preset){C.END} ").strip()

        try:
            from neugi_soul import SoulSystem

            soul = SoulSystem()

            if choice == "1":
                soul.display()

            elif choice == "2":
                print("\nAvailable Presets:")
                for p in soul.list_presets():
                    print(f"  • {p}")

            elif choice == "3":
                preset = input("Preset name: ").strip()
                if soul.load_preset(preset):
                    print(f"\n✅ Loaded: {preset}")
                    soul.display()
                else:
                    print(f"\n❌ Unknown preset")

        except Exception as e:
            self.ui.error(f"Error: {e}")

        input(f"\n{C.CYAN}Press Enter...{C.END}")

    # ============================================================
    # SKILLS V2
    # ============================================================

    def run_skills(self):
        """Skills V2 system"""
        self.ui.header("📚 SKILLS V2")

        print(f"""
{C.BOLD}Skills V2 (BrowserOS SKILL.md Format):{C.END}

  Create reusable skills with:
  • YAML frontmatter metadata
  • Markdown instructions
  • Optional scripts/ directory
  • Natural language triggers

""")

        try:
            from neugi_skills_v2 import SkillManagerV2

            manager = SkillManagerV2()
            skills = manager.list_skills()

            print(f"Total Skills: {len(skills)}\n")

            for skill in skills:
                status = "✅" if skill.status.value == "enabled" else "❌"
                print(f"{status} {skill.name}")
                print(f"   {skill.description}")
                print()

        except Exception as e:
            self.ui.error(f"Error: {e}")

        input(f"\n{C.CYAN}Press Enter...{C.END}")

    # ============================================================
    # SCHEDULER
    # ============================================================

    def run_scheduler(self):
        """Task scheduler"""
        self.ui.header("⏰ TASK SCHEDULER")

        print(f"""
{C.BOLD}Native Scheduler (BrowserOS Style):{C.END}

  Schedule recurring tasks:
  • DAILY   - At specific time (e.g., 08:00)
  • HOURLY  - Every N hours
  • MINUTES - Every N minutes

""")

        try:
            from neugi_scheduler import NEUGIScheduler

            scheduler = NEUGIScheduler()
            tasks = scheduler.list_tasks()

            if not tasks:
                print("No scheduled tasks.")
            else:
                print(f"{C.BOLD}Scheduled Tasks:{C.END}\n")
                for task in tasks:
                    status = "✅" if task["enabled"] else "❌"
                    print(f"{status} {task['name']}")
                    print(f"   {task['schedule']}")
                    print(f"   Next: {task['next_run']}")
                    print()

            print("\nTo manage tasks, run: python neugi_scheduler.py")

        except Exception as e:
            self.ui.error(f"Error: {e}")

        input(f"\n{C.CYAN}Press Enter...{C.END}")

    # ============================================================
    # MCP SERVER
    # ============================================================

    def run_mcp(self):
        """MCP Server"""
        self.ui.header("🌐 MCP SERVER")

        print(f"""
{C.BOLD}MCP Server (Claude Code Compatible){C.END}

  Exposes NEUGI as MCP Server with 30+ tools:
  
  • Filesystem (Cowork): 7 tools
  • Memory: 3 tools
  • Skills: 3 tools
  • System: 4 tools
  • Git: 4 tools
  • Network: 3 tools
  • Agent delegation: 2 tools

Integration:
  Claude Code: claude mcp add neugi http://127.0.0.1:19889/mcp --scope user
  OpenClaw:   Add to openclaw.json

""")

        choice = input(f"{C.CYAN}Start MCP Server? (y/n){C.END} ").strip().lower()

        if choice == "y":
            print("\n🚀 Starting MCP Server on port 19889...")
            print("Press Ctrl+C to stop\n")

            try:
                from neugi_mcp_server import start_server

                start_server(port=19889, open_browser=False)
            except KeyboardInterrupt:
                print("\n\nServer stopped.")

        input(f"\n{C.CYAN}Press Enter...{C.END}")

    # ============================================================
    # APP INTEGRATIONS
    # ============================================================

    def run_apps(self):
        """App Integrations"""
        self.ui.header("📱 APP INTEGRATIONS")

        print(f"""
{C.BOLD}OAuth App Integrations (BrowserOS Style):{C.END}

  Connect external services:
  • Email: Gmail, Outlook
  • Calendar: Google Calendar, Outlook
  • Communication: Slack, Discord
  • Dev: GitHub, Vercel
  • Project: Linear, Notion

""")

        try:
            from neugi_app_integrations import AppIntegrationManager

            manager = AppIntegrationManager()
            apps = manager.list_apps()

            print(f"{C.BOLD}Available Apps:{C.END}\n")
            for app in apps:
                status = "✅ Connected" if app["connected"] else "❌"
                print(f"{app['icon']} {app['name']:<20} {status}")

            print(f"\nTotal: {len(apps)} apps")
            print(f"Connected: {len([a for a in apps if a['connected']])}")

        except Exception as e:
            self.ui.error(f"Error: {e}")

        input(f"\n{C.YELLOW}Note: OAuth requires client configuration{C.END}")
        input(f"\n{C.CYAN}Press Enter...{C.END}")

    # ============================================================
    # WORKFLOWS
    # ============================================================

    def run_workflows(self):
        """Workflow automation"""
        self.ui.header("🔀 WORKFLOW AUTOMATION")

        print(f"""
{C.BOLD}Workflow Engine (BrowserOS Style):{C.END}

  Create reusable automation workflows:
  • JSON-based definition
  • Step dependencies
  • Parallel execution
  • Built-in actions

Example Workflows:
  • daily-standup - Morning notification
  • git-backup - Auto commit & push
  • health-check - System monitoring

""")

        try:
            from neugi_workflows import WorkflowEngine

            engine = WorkflowEngine()
            workflows = engine.list_workflows()

            if not workflows:
                print("No workflows created yet.")
                print("\nExamples:")
                print("  python neugi_workflows.py create --example daily-standup")
                print("  python neugi_workflows.py create --example git-backup")
            else:
                print(f"{C.BOLD}Your Workflows:{C.END}\n")
                for wf in workflows:
                    print(f"📦 {wf['name']}")
                    print(f"   {wf['description']}")
                    print(f"   Steps: {wf['steps']}\n")

        except Exception as e:
            self.ui.error(f"Error: {e}")

        input(f"\n{C.CYAN}Press Enter...{C.END}")

    # ============================================================
    # TESTS
    # ============================================================

    def run_tests(self):
        """Run test suite"""
        self.ui.header("🧪 TEST SUITE")

        print(f"""
{C.BOLD}NEUGI Test Framework:{C.END}

  Run built-in tests:
  • Memory system
  • Soul system
  • Skills
  • Cowork
  • Scheduler

""")

        choice = input(f"{C.CYAN}Run all tests? (y/n){C.END} ").strip().lower()

        if choice == "y":
            try:
                from neugi_test import run_tests

                print("\n🚀 Running tests...\n")
                result = run_tests()

                print(f"\n{C.BOLD}Results:{C.END}")
                print(f"  Passed: {result['passed']}")
                print(f"  Failed: {result['failed']}")
                print(f"  Total: {result['total']}")
                print(f"  Rate: {result['success_rate']:.1f}%")

                if result["failed"] > 0:
                    self.ui.error(f"{result['failed']} tests failed!")
                else:
                    print(f"\n{C.GREEN}All tests passed! ✅{C.END}")

            except Exception as e:
                self.ui.error(f"Error: {e}")

        input(f"\n{C.CYAN}Press Enter...{C.END}")

    # REST API
    # ============================================================

    def run_api(self):
        """REST API Server"""
        self.ui.header("🌍 REST API SERVER")

        print(f"""
{C.BOLD}FastAPI REST Server:{C.END}

  Start REST API for external integrations:
  • GET /api/status - System status
  • POST /api/chat - Chat with AI
  • GET /api/memory - Query memory
  • WebSocket /ws - Real-time updates

""")

        try:
            from neugi_api import main as api_main

            print(f"{C.GREEN}Starting REST API server...{C.END}")
            print(f"  URL: http://localhost:19890")
            print(f"  Docs: http://localhost:19890/docs\n")

            api_main()

        except Exception as e:
            self.ui.error(f"Error: {e}")

        input(f"\n{C.CYAN}Press Enter...{C.END}")

    # DOCKER
    # ============================================================

    def run_docker(self):
        """Docker Management"""
        self.ui.header("🐳 DOCKER MANAGEMENT")

        print(f"""
{C.BOLD}Docker Container Management:{C.END}

  Manage containers:
  • List containers
  • Start/Stop/Restart
  • View logs
  • Pull images

""")

        try:
            from neugi_docker import DockerManager

            manager = DockerManager()
            containers = manager.list_containers()

            print(f"{C.BOLD}Containers:{C.END}\n")
            for c in containers:
                status = "🟢 Running" if c["status"] == "running" else "🔴 Stopped"
                print(f"  {c['name']:<30} {status}")

            print(f"\nTotal: {len(containers)} containers")

        except Exception as e:
            self.ui.error(f"Error: {e}")

        input(f"\n{C.CYAN}Press Enter...{C.END}")

    # MONITORING V2
    # ============================================================

    def run_monitoring_v2(self):
        """Advanced Monitoring"""
        self.ui.header("📈 ADVANCED MONITORING")

        print(f"""
{C.BOLD}Advanced System Monitoring:{C.END}

  Features:
  • CPU, Memory, Disk monitoring
  • Prometheus metrics export
  • Real-time dashboards
  • Alert thresholds

""")

        try:
            from neugi_monitoring import Monitoring

            service = Monitoring()
            metrics = service.get_metrics()

            print(f"{C.BOLD}Current Metrics:{C.END}\n")
            print(f"  CPU Usage: {metrics.cpu_percent:.1f}%")
            print(f"  Memory: {metrics.memory_percent:.1f}%")
            print(f"  Disk: {metrics.disk_percent:.1f}%")
            print(f"  Network Sent: {metrics.network_sent / 1024 / 1024:.1f} MB")
            print(f"  Network Recv: {metrics.network_recv / 1024 / 1024:.1f} MB")
            print(f"\n  Prometheus metrics available at /metrics endpoint")

        except Exception as e:
            self.ui.error(f"Error: {e}")

        input(f"\n{C.CYAN}Press Enter...{C.END}")

    # WORKFLOW BUILDER
    # ============================================================

    def run_workflow_builder(self):
        """Visual Workflow Builder"""
        self.ui.header("🎨 VISUAL WORKFLOW BUILDER")

        print(f"""
{C.BOLD}Web-Based Visual Workflow Editor:{C.END}

  Features:
  • Drag and drop node editor
  • Multiple node types (trigger, action, condition, HTTP, etc.)
  • Connect nodes visually
  • Execute workflows

""")

        try:
            from neugi_workflow_builder import main as builder_main

            print(f"{C.GREEN}Starting Workflow Builder...{C.END}")
            print(f"  URL: http://localhost:19900\n")

            builder_main()

        except Exception as e:
            self.ui.error(f"Error: {e}")

        input(f"\n{C.CYAN}Press Enter...{C.END}")

    # AUTOMATION
    # ============================================================

    def run_automation(self):
        """Automation Engine"""
        self.ui.header("🤖 AUTOMATION ENGINE")

        print(f"""
{C.BOLD}Rule-Based Automation:{C.END}

  Create automation rules with:
  • Schedule triggers (daily, hourly, interval)
  • Webhook triggers
  • Keyword triggers
  • Multiple actions
  • Conditional logic

""")

        try:
            from neugi_automation import AutomationEngine, AutomationRule

            engine = AutomationEngine()
            rules = AutomationRule.list_all()

            print(f"{C.BOLD}Automation Rules:{C.END}\n")
            for r in rules:
                status = "✅" if r["enabled"] else "❌"
                print(f"  {status} {r['name']}")
                print(
                    f"      Trigger: {r['trigger_type']} | Actions: {r['action_count']} | Runs: {r['trigger_count']}"
                )

            print(f"\nTotal: {len(rules)} rules")
            print(f"Enabled: {len([r for r in rules if r['enabled']])}")

            choice = input(f"\n{C.CYAN}Start automation engine? (y/n){C.END} ").strip().lower()
            if choice == "y":
                engine.start()

        except Exception as e:
            self.ui.error(f"Error: {e}")

        input(f"\n{C.CYAN}Press Enter...{C.END}")

    # DATABASE
    # ============================================================

    def run_database(self):
        """Database Management"""
        self.ui.header("🗄️ DATABASE MANAGEMENT")

        print(f"""
{C.BOLD}SQLite Persistence Layer:{C.END}

  Store and retrieve:
  • Conversations & Messages
  • Memory (with TTL)
  • Workflows & Runs
  • Metrics History
  • Audit Logs

""")

        try:
            from neugi_database import Database, ConversationStore, MemoryStore, MetricsStore

            db = Database()

            print(f"{C.BOLD}Database Statistics:{C.END}\n")

            import sqlite3

            conn = sqlite3.connect(os.path.expanduser("~/neugi/neugi.db"))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            for table in [
                "conversations",
                "messages",
                "memory",
                "workflows",
                "metrics",
                "audit_log",
            ]:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"  {table}: {count} rows")

            conn.close()

        except Exception as e:
            self.ui.error(f"Error: {e}")

        input(f"\n{C.CYAN}Press Enter...{C.END}")

    # COMMAND PALETTE
    # ============================================================

    def run_palette(self):
        """Command Palette"""
        self.ui.header("⌨️ COMMAND PALETTE")

        print(f"""
{C.BOLD}Quick Command Access:{C.END}

  Features:
  • Search all NEUGI commands
  • Fuzzy search
  • Keyboard navigation
  • Recent commands

""")

        try:
            from neugi_command_palette import CommandPalette

            palette = CommandPalette()
            categories = palette.get_by_category()

            print(f"{C.BOLD}Available Commands:{C.END}\n")
            for cat, commands in categories.items():
                print(f"  📁 {cat}")
                for cmd in commands[:3]:
                    print(f"      {cmd['icon']} {cmd['label']} ({cmd['shortcut']})")
                print()

        except Exception as e:
            self.ui.error(f"Error: {e}")

        input(f"\n{C.CYAN}Press Enter...{C.END}")

    # FILE MANAGER
    # ============================================================

    def run_file_manager(self):
        """File Manager"""
        self.ui.header("📁 FILE MANAGER")

        print(f"""
{C.BOLD}Full-Featured File Manager:{C.END}

  Features:
  • Browse directories
  • Copy, move, delete files
  • Search files
  • File preview
  • Hash generation

""")

        try:
            from neugi_file_manager import FileManager

            fm = FileManager()
            items = fm.list(".")

            print(f"{C.BOLD}Current Directory:{C.END} {os.getcwd()}\n")
            print(f"{C.BOLD}{'NAME':<30} {'SIZE':<10} {'TYPE'}{C.END}")
            print(f"{C.CYAN}{'-' * 50}{C.END}")

            for item in items[:15]:
                if "error" in item:
                    continue
                icon = "📁" if item["type"] == "directory" else "📄"
                size = fm._format_size(item["size"]) if item["type"] != "directory" else "-"
                print(f"{icon} {item['name']:<28} {size:<10} {item['type']}")

        except Exception as e:
            self.ui.error(f"Error: {e}")

        input(f"\n{C.CYAN}Press Enter...{C.END}")

    # CODE INTERPRETER
    # ============================================================

    def run_code_interpreter(self):
        """Code Interpreter"""
        self.ui.header("💻 CODE INTERPRETER")

        print(f"""
{C.BOLD}Sandboxed Code Execution:{C.END}

  Features:
  • Safe Python execution
  • JavaScript execution (Node.js)
  • Shell commands (restricted)
  • SQL queries

""")

        try:
            from neugi_code_interpreter import CodeInterpreter

            interpreter = CodeInterpreter()

            print(f"{C.GREEN}Enter Python code to execute (type 'exit' to quit):{C.END}\n")

            while True:
                code = input(f"{C.CYAN}>>> {C.END}").strip()
                if code in ["exit", "quit"]:
                    break

                result = interpreter.execute_python(code)
                if result["output"]:
                    print(result["output"])
                if result["error"]:
                    print(f"{C.RED}Error: {result['error']}{C.END}")

        except Exception as e:
            self.ui.error(f"Error: {e}")

    # MARKETPLACE
    # ============================================================

    def run_marketplace(self):
        """Plugin Marketplace"""
        self.ui.header("🛒 PLUGIN MARKETPLACE")

        print(f"""
{C.BOLD}Browse & Install Plugins:{C.END}

  Categories:
  • Integrations
  • Automation
  • Database
  • AI & ML
  • Developer Tools

""")

        try:
            from neugi_marketplace import PluginMarketplace

            marketplace = PluginMarketplace()
            categories = marketplace.get_categories()

            print(f"{C.BOLD}Categories:{C.END}\n")
            for cat in categories:
                print(f"  {cat['icon']} {cat['name']}")

            plugins = marketplace.list_plugins()
            installed = len([p for p in plugins if p.get("installed")])

            print(f"\n{C.BOLD}Plugins: {len(plugins)} | Installed: {installed}{C.END}")

        except Exception as e:
            self.ui.error(f"Error: {e}")

        input(f"\n{C.CYAN}Press Enter...{C.END}")

    # ENCRYPTION
    # ============================================================

    def run_encryption(self):
        """Encryption Tools"""
        self.ui.header("🔒 ENCRYPTION TOOLS")

        print(f"""
{C.BOLD}Encryption & Security:{C.END}

  Features:
  • File encryption/decryption
  • Password hashing
  • Secure storage
  • Key management

""")

        try:
            from neugi_encryption import Encryption, KeyManager

            km = KeyManager()
            keys = km.list_keys()

            print(f"{C.BOLD}Encryption Keys:{C.END}\n")
            if keys:
                for k in keys:
                    print(f"  🔑 {k['name']} (created: {k['created']})")
            else:
                print("  No keys found")

            print(f"\n  Options:")
            print(f"    --encrypt-file FILE")
            print(f"    --hash STRING")
            print(f"    --generate-key")

        except Exception as e:
            self.ui.error(f"Error: {e}")

        input(f"\n{C.CYAN}Press Enter...{C.END}")

    # SSH MANAGER
    # ============================================================

    def run_ssh(self):
        """SSH Manager"""
        self.ui.header("🔐 SSH MANAGER")

        print(f"""
{C.BOLD}SSH Connection Management:{C.END}

  Features:
  • Manage SSH connections
  • Key generation
  • Remote command execution
  • File transfer (SCP)

""")

        try:
            from neugi_ssh import SSHManager

            manager = SSHManager()
            connections = manager.list_connections()

            print(f"{C.BOLD}SSH Connections:{C.END}\n")
            for c in connections:
                print(f"  {c['name']}: {c['user']}@{c['host']}:{c['port']}")

            print(f"\nTotal: {len(connections)} connections")

        except Exception as e:
            self.ui.error(f"Error: {e}")

        input(f"\n{C.CYAN}Press Enter...{C.END}")

    # CACHE LAYER
    # ============================================================

    def run_cache(self):
        """Cache Layer"""
        self.ui.header("🧠 CACHE LAYER")

        print(f"""
{C.BOLD}In-Memory Cache:{C.END}

  Features:
  • Key-value store with TTL
  • LRU eviction
  • Rate limiting
  • Pub/Sub messaging

""")

        try:
            from neugi_cache import cache_manager

            stats = cache_manager.cache.stats()

            print(f"{C.BOLD}Cache Statistics:{C.END}\n")
            print(f"  Size: {stats['size']}/{stats['max_size']}")
            print(f"  Total Accesses: {stats['total_accesses']}")
            print(f"  Keys: {', '.join(stats['keys'][:5])}")

        except Exception as e:
            self.ui.error(f"Error: {e}")

        input(f"\n{C.CYAN}Press Enter...{C.END}")

    # LOGS
    # ============================================================

    def run_logs(self):
        """Log Aggregator"""
        self.ui.header("📝 LOG AGGREGATOR")

        print(f"""
{C.BOLD}Centralized Logging:{C.END}

  Features:
  • Log collection
  • Search & filtering
  • Log parsing
  • Statistics

""")

        try:
            from neugi_logs import log_aggregator

            stats = log_aggregator.get_stats()
            logs = log_aggregator.get_logs(limit=10)

            print(f"{C.BOLD}Statistics:{C.END}\n")
            print(f"  Total: {stats['total']}")
            print(f"  By Level: {stats['levels']}")

            print(f"\n{C.BOLD}Recent Logs:{C.END}\n")
            for l in logs:
                print(f"  [{l['level']:<8}] {l['message'][:50]}")

        except Exception as e:
            self.ui.error(f"Error: {e}")

        input(f"\n{C.CYAN}Press Enter...{C.END}")

    # BACKUP
    # ============================================================

    def run_backup(self):
        """Backup System"""
        self.ui.header("💾 BACKUP SYSTEM")

        print(f"""
{C.BOLD}Backup & Restore:{C.END}

  Features:
  • Full backups
  • Compression
  • Retention policies
  • Restore functionality

""")

        try:
            from neugi_backup import BackupManager

            manager = BackupManager()
            jobs = manager.list_jobs()

            print(f"{C.BOLD}Backup Jobs:{C.END}\n")
            if jobs:
                for job in jobs:
                    status = (
                        "✅"
                        if job["last_status"] == "success"
                        else "❌"
                        if job["last_status"] == "failed"
                        else "⏳"
                    )
                    print(f"  {status} {job['name']} - {job['runs']} runs")
            else:
                print("  No backup jobs configured")

        except Exception as e:
            self.ui.error(f"Error: {e}")

        input(f"\n{C.CYAN}Press Enter...{C.END}")

    # KUBERNETES
    # ============================================================

    def run_k8s(self):
        """Kubernetes Connector"""
        self.ui.header("☸️ KUBERNETES CONNECTOR")

        print(f"""
{C.BOLD}Kubernetes Management:{C.END}

  Features:
  • Pod management
  • Service management
  • Deployment control
  • Resource monitoring

""")

        try:
            from neugi_k8s import KubernetesConnector

            k8s = KubernetesConnector()
            usage = k8s.get_resource_usage()

            print(f"{C.BOLD}Cluster Resources:{C.END}\n")
            print(f"  Nodes: {usage['nodes']}")
            print(f"  Pods: {usage['pods']}")
            print(f"  Services: {usage['services']}")
            print(f"  Deployments: {usage['deployments']}")

        except Exception as e:
            self.ui.error(f"Error: {e}")

        input(f"\n{C.CYAN}Press Enter...{C.END}")

    # WEBSOCKET
    # ============================================================

    def run_websocket(self):
        """WebSocket Server"""
        self.ui.header("🔌 WEBSOCKET SERVER")

        print(f"""
{C.BOLD}Real-Time Communication:{C.END}

  Features:
  • WebSocket connections
  • Event streaming
  • Broadcasting
  • Subscriptions

  URL: ws://localhost:19920/ws/CLIENT_ID

""")

        try:
            from neugi_websocket import ws_manager

            print(f"{C.GREEN}Starting WebSocket server...{C.END}")
            ws_manager.run()

        except Exception as e:
            self.ui.error(f"Error: {e}")

        input(f"\n{C.CYAN}Press Enter...{C.END}")

    # GRAPHQL
    # ============================================================

    def run_graphql(self):
        """GraphQL API"""
        self.ui.header("📊 GRAPHQL API")

        print(f"""
{C.BOLD}GraphQL Query Language:{C.END}

  Features:
  • Flexible data fetching
  • Mutations
  • Subscriptions
  • Schema introspection

  URL: http://localhost:19930/graphql

""")

        try:
            from neugi_graphql import GraphQLServer

            print(f"{C.GREEN}Starting GraphQL server...{C.END}")
            server = GraphQLServer()
            server.run()

        except Exception as e:
            self.ui.error(f"Error: {e}")

        input(f"\n{C.CYAN}Press Enter...{C.END}")

    # PROMETHEUS
    # ============================================================

    def run_prometheus(self):
        """Prometheus Metrics"""
        self.ui.header("📈 PROMETHEUS METRICS")

        print(f"""
{C.BOLD}Prometheus Metrics Export:{C.END}

  Features:
  • Counter, Gauge, Histogram metrics
  • System metrics collection
  • Prometheus format export

  URL: http://localhost:19940/metrics

""")

        try:
            from neugi_prometheus import collector

            print(f"{C.BOLD}Metrics:{C.END}\n")
            print(collector.exporter.export())

        except Exception as e:
            self.ui.error(f"Error: {e}")

        input(f"\n{C.CYAN}Press Enter...{C.END}")

    # API GATEWAY
    # ============================================================

    def run_gateway(self):
        """API Gateway"""
        self.ui.header("🚪 API GATEWAY")

        print(f"""
{C.BOLD}API Gateway:{C.END}

  Features:
  • Request routing
  • Rate limiting
  • API key management
  • Authentication

""")

        try:
            from neugi_gateway import gateway

            routes = gateway.list_routes()

            print(f"{C.BOLD}Routes:{C.END}\n")
            for r in routes:
                print(f"  {r['method']:<6} {r['path']:<20} -> {r['backend']}")

            keys = gateway.list_api_keys()
            print(f"\n{C.BOLD}API Keys: {len(keys)}{C.END}")

        except Exception as e:
            self.ui.error(f"Error: {e}")

        input(f"\n{C.CYAN}Press Enter...{C.END}")

    # SERVICE DISCOVERY
    # ============================================================

    def run_discovery(self):
        """Service Discovery"""
        self.ui.header("🔍 SERVICE DISCOVERY")

        print(f"""
{C.BOLD}Service Registry:{C.END}

  Features:
  • Register services
  • Health checks
  • Round-robin load balancing

""")

        try:
            from neugi_discovery import registry

            services = registry.get_all()

            print(f"{C.BOLD}Services:{C.END}\n")
            for name, instances in services.items():
                healthy = len([i for i in instances if i["status"] == "healthy"])
                print(f"  {name}: {healthy}/{len(instances)} healthy")

        except Exception as e:
            self.ui.error(f"Error: {e}")

        input(f"\n{C.CYAN}Press Enter...{C.END}")

    # SECRETS MANAGER
    # ============================================================

    def run_secrets(self):
        """Secrets Manager"""
        self.ui.header("🔑 SECRETS MANAGER")

        print(f"""
{C.BOLD}Secrets Management:{C.END}

  Features:
  • Encrypted storage
  • Version control
  • Rotation support
  • Access control

""")

        try:
            from neugi_secrets import secrets_manager

            secrets = secrets_manager.list()

            print(f"{C.BOLD}Secrets:{C.END}\n")
            if secrets:
                for s in secrets:
                    print(f"  {s['name']} (v{s['versions']})")
            else:
                print("  No secrets stored")

        except Exception as e:
            self.ui.error(f"Error: {e}")

        input(f"\n{C.CYAN}Press Enter...{C.END}")

    def run_multicluster(self):
        """Multi-Cluster"""
        self.ui.header("🌍 MULTI-CLUSTER MANAGER")
        print("Multi-Cluster Manager loaded")
        input(f"\n{C.CYAN}Press Enter...{C.END}")

    def run_circuit(self):
        """Circuit Breaker"""
        self.ui.header("⚡ CIRCUIT BREAKER")
        print("Circuit Breaker loaded")
        input(f"\n{C.CYAN}Press Enter...{C.END}")

    def run_lb(self):
        """Load Balancer"""
        self.ui.header("⚖️ LOAD BALANCER")
        print("Load Balancer loaded")
        input(f"\n{C.CYAN}Press Enter...{C.END}")

    def run_mesh(self):
        """Service Mesh"""
        self.ui.header("🕸️ SERVICE MESH")
        print("Service Mesh loaded")
        input(f"\n{C.CYAN}Press Enter...{C.END}")

    def run_cdn(self):
        """CDN Manager"""
        self.ui.header("🌐 CDN MANAGER")
        print("CDN Manager loaded")
        input(f"\n{C.CYAN}Press Enter...{C.END}")

    def run_eventbus(self):
        print("Event Bus loaded")
        input()

    def run_agents(self):
        print("Agents SDK loaded")
        input()

    def run_agent_studio(self):
        """Agent Studio - Create custom user agents"""
        from neugi_agent_studio import AgentStudio, TEMPLATES

        self.ui.header("🤖 AGENT STUDIO - Create Your Own Agent")
        print("""
  Platform provides TEMPLATES - You create & customize your own agents!
  Your agent will work ALONGSIDE the 9 built-in agents!
        """)

        studio = AgentStudio()

        print("\n📋 AVAILABLE TEMPLATES:")
        print("-" * 50)
        for tid, tpl in TEMPLATES.items():
            print(f"  [{tid:12}] {tpl['name']}")
            print(f"               {tpl['description']}")

        print("\n" + "=" * 50)
        print("🛠️  TOOLS YOU CAN CHOOSE FROM:")
        print("-" * 50)
        print("""
  • web_search, web_fetch, web_browse
  • code_execute, code_debug, file_read, file_write
  • llm_think, llm_generate
  • json_parse, csv_analyze, db_query
  • send_telegram, send_discord, send_email
  • image_generate, audio_speak
  • shell_execute
        """)

        print("\n" + "=" * 50)
        print("👥 EXISTING AGENTS (you can work with them!):")
        print("-" * 50)
        print("""
  • aurora  - Researcher (web search/fetch)
  • cipher  - Coder (code execute/debug)
  • nova    - Creator (image generation)
  • pulse   - Analyst (data analysis)
  • quark   - Strategist (planning)
  • shield  - Security (audit/scan)
  • spark   - Social (telegram/discord)
  • ink     - Writer (documentation)
  • nexus   - Manager (delegate/coordinate)
        """)

        print("\n" + "=" * 50)
        choice = self.ui.menu(
            [
                ("create", "🎨 Create New Agent"),
                ("list", "📋 List My Agents"),
                ("run", "▶️  Run an Agent"),
                ("back", "🔙 Back to Main Menu"),
            ]
        )

        if choice == "create" or choice == "1":
            studio.create_agent_interactive()
        elif choice == "list" or choice == "2":
            studio.show_dashboard()
        elif choice == "run" or choice == "3":
            print("\n📋 YOUR AGENTS:")
            agents = studio.list_user_agents()
            if not agents:
                print("  No agents yet. Create one first!")
            else:
                for a in agents:
                    print(f"  • {a['name']} ({a['role']})")

            agent_name = input("\nAgent name to run: ").strip()
            if agent_name:
                task = input("Task: ").strip()
                if task:
                    print(f"\n🚀 Running '{agent_name}' on task: {task}")
                    result = studio.run_user_agent(agent_name, task)
                    print(f"\n📦 Result: {result}")
                else:
                    print("No task provided!")
        else:
            return

        input(f"\n{C.CYAN}Press Enter to continue...{C.END}")

    def run_rescue(self):
        """🆘 WIZARD RESCUE - Auto troubleshoot any problem"""
        from neugi_wizard_rescue import WizardRescue

        self.ui.header("🆘 WIZARD RESCUE - TROUBLESHOOTING")

        print("""
  💡 STUCK? CONFUSED? NOT WORKING?
  
  Don't panic! Wizard Rescue is here to help!
  
  🎯 What can I fix:
  • Ollama tidak jalan
  • Port conflict (19888/19889)
  • API/Connection issues
  • Permission problems
  • Database errors
  • Memory/RAM penuh
  • Model tidak ditemukan
  • Docker problems
  • Dan 40+ masalah lainnya!
  
  Saya akan otomatis cek semua dan coba perbaiki!
        """)

        choice = self.ui.menu(
            [
                ("auto", "🔍 AUTO-DIAGNOSE & FIX - Check everything now!"),
                ("select", "🎯 Pilih Masalah Spesifik"),
                ("back", "🔙 Kembali / Back"),
            ]
        )

        rescue = WizardRescue()

        if choice == "auto" or choice == "1":
            rescue.diagnose()
        elif choice == "select" or choice == "2":
            print("\n📋 Common Issues:")
            print("  1. Ollama not running")
            print("  2. Port 19888 conflict")
            print("  3. Permission denied")
            print("  4. Model not found")
            print("  5. No internet")
            print("  6. Database error")

            issue_choice = input("\nPilih nomor: ").strip()

            issue_map = {
                "1": "ollama_not_running",
                "2": "port_19888_conflict",
                "3": "permission_denied",
                "4": "model_not_found",
                "5": "no_internet",
                "6": "db_corrupted",
            }

            if issue_choice in issue_map:
                result = rescue.quick_fix(issue_map[issue_choice])
                print(f"\n{Colors.GREEN}{result.get('message', 'Done!')}{Colors.END}")
                for step in result.get("steps", []):
                    print(f"  {step}")

        input(f"\n{C.CYAN}Press Enter to continue...{C.END}")

    def run_learner(self):
        """Auto-Learner - NEUGI's Self-Improving System"""
        from neugi_auto_learner import AutoLearner

        self.ui.header("🧠 AUTO-LEARNER")
        print("""
  NEUGI learns from EVERY interaction!
  Automatically creates new skills from successful task completions.
  
  This is what makes NEUGI different from OpenClaw, Hermes, Claude Code:
  - It gets SMARTER the longer you use it!
  - Auto-creates reusable skills
  - Personalized to YOUR workflow
        """)

        learner = AutoLearner()
        learner.show_learning_dashboard()

        print("\n" + "=" * 50)
        choice = self.ui.menu(
            [
                ("stats", "📊 Show Learning Stats"),
                ("analyze", "⚡ Analyze & Create Skills"),
                ("suggest", "💡 Get Skill Suggestions"),
                ("back", "🔙 Back"),
            ]
        )

        if choice == "stats":
            learner.show_learning_dashboard()
        elif choice == "analyze":
            print("\n🔄 Analyzing patterns...")
            new_skills = learner.analyze_and_create_skill()
            if new_skills:
                print(f"\n✅ Created {len(new_skills)} new skills:")
                for s in new_skills:
                    print(f"   • {s['name']}")
            else:
                print("\n📝 No new skills to create yet.")
        elif choice == "suggest":
            user_input = input("What are you trying to do? ").strip()
            if user_input:
                suggestions = learner.suggest_skills(user_input)
                if suggestions:
                    print("\n💡 Skills that can help:")
                    for s in suggestions:
                        print(f"   • {s['name']} ({s['confidence']:.0%} match)")
                else:
                    print("\n📝 No matching skills found.")

        input(f"\n{C.CYAN}Press Enter to continue...{C.END}")

    def run_cli(self):
        print("CLI Framework loaded")
        input()

    def run_ml_pipeline(self):
        """ML Pipeline - Train and deploy ML models"""
        self.ui.header("🧠 ML PIPELINE")
        print("""
  [1] Train Model      - Train a new ML model
  [2] Inference        - Run predictions
  [3] Model Registry   - Manage trained models
  [4] Hyperparameter   - Tune model parameters
        """)
        input(f"\n{C.CYAN}Press Enter...{C.END}")

    def run_data_pipeline(self):
        """Data Pipeline - ETL and data processing"""
        self.ui.header("🔗 DATA PIPELINE")
        print("""
  [1] Create Pipeline  - Build new data pipeline
  [2] Run Pipeline     - Execute data flow
  [3] Schedule          - Set pipeline schedule
  [4] Monitor          - Watch pipeline status
        """)
        input(f"\n{C.CYAN}Press Enter...{C.END}")

    def run_notification(self):
        """Notification System"""
        self.ui.header("🔔 NOTIFICATION SYSTEM")
        print("""
  [1] Send Alert       - Push notification
  [2] Email Notify     - Send email alerts
  [3] Slack/Discord    - Webhook notifications
  [4] Templates        - Notification templates
        """)
        input(f"\n{C.CYAN}Press Enter...{C.END}")

    def run_webhook(self):
        """Webhook Manager"""
        self.ui.header("🪝 WEBHOOK MANAGER")
        print("""
  [1] Register Webhook - Add new webhook endpoint
  [2] Test Webhook     - Send test payload
  [3] Webhook Logs     - View delivery history
  [4] Security         - Configure webhook auth
        """)
        input(f"\n{C.CYAN}Press Enter...{C.END}")

    def run_rate_limiter(self):
        """Rate Limiter"""
        self.ui.header("🚦 RATE LIMITER")
        print("""
  [1] Create Rule      - Define rate limit rule
  [2] View Usage       - See current usage
  [3] Blocked IPs      - View blocked requests
  [4] Whitelist        - Configure exceptions
        """)
        input(f"\n{C.CYAN}Press Enter...{C.END}")

    def run_config_manager(self):
        """Config Manager"""
        self.ui.header("⚙️ CONFIG MANAGER")
        print("""
  [1] View Config      - Show current settings
  [2] Edit Config      - Modify configuration
  [3] Profiles         - Switch config profiles
  [4] Validate         - Check config validity
        """)
        input(f"\n{C.CYAN}Press Enter...{C.END}")

    def run_template_engine(self):
        """Template Engine"""
        self.ui.header("📝 TEMPLATE ENGINE")
        print("""
  [1] Create Template  - New template file
  [2] Render           - Fill template with data
  [3] Template Library - View saved templates
  [4] Variables        - Manage template vars
        """)
        input(f"\n{C.CYAN}Press Enter...{C.END}")

    def run_report_generator(self):
        """Report Generator"""
        self.ui.header("📑 REPORT GENERATOR")
        print("""
  [1] Generate Report  - Create new report
  [2] Schedule Report  - Auto-generate reports
  [3] Export           - PDF/HTML/CSV export
  [4] Templates        - Report templates
        """)
        input(f"\n{C.CYAN}Press Enter...{C.END}")

    def run_analytics(self):
        """Analytics Dashboard"""
        self.ui.header("📉 ANALYTICS DASHBOARD")
        print("""
  [1] Overview        - System analytics
  [2] Usage Stats     - User/API usage
  [3] Performance     - Response times
  [4] Trends          - Historical charts
        """)
        input(f"\n{C.CYAN}Press Enter...{C.END}")

    def run_api_versioning(self):
        """API Versioning"""
        self.ui.header("📌 API VERSIONING")
        print("""
  [1] List Versions   - Show API versions
  [2] Create Version  - Add new API version
  [3] Set Default     - Configure default version
  [4] Deprecate       - Mark version as deprecated
        """)
        input(f"\n{C.CYAN}Press Enter...{C.END}")

    def run_api_docs(self):
        """API Docs UI"""
        self.ui.header("📖 API DOCS UI")
        print("""
  [1] Swagger UI      - OpenAPI documentation
  [2] ReDoc           - Alternative docs view
  [3] Export Spec     - Download OpenAPI spec
  [4] Custom Docs     - Configure doc theme
        """)
        input(f"\n{C.CYAN}Press Enter...{C.END}")

    def run_request_validator(self):
        """Request Validator"""
        self.ui.header("✅ REQUEST VALIDATOR")
        print("""
  [1] Schema Editor   - Define validation schemas
  [2] Test Request    - Validate sample request
  [3] Validation Logs - View validation history
  [4] Rules           - Manage validation rules
        """)
        input(f"\n{C.CYAN}Press Enter...{C.END}")

    def run_response_cache(self):
        """Response Cacher"""
        self.ui.header("💾 RESPONSE CACHER")
        print("""
  [1] Enable Cache    - Turn on response caching
  [2] Cache Stats     - View cache hit/miss
  [3] Clear Cache     - Purge cached responses
  [4] Cache Rules    - Configure TTL per endpoint
        """)
        input(f"\n{C.CYAN}Press Enter...{C.END}")

    def run_metrics_exporter(self):
        """Metrics Exporter"""
        self.ui.header("📊 METRICS EXPORTER")
        print("""
  [1] Start Exporter - Run Prometheus exporter
  [2] Metrics List    - View available metrics
  [3] Export Format   - Configure output format
  [4] Scrape Config   - Set scrape endpoint
        """)
        input(f"\n{C.CYAN}Press Enter...{C.END}")

    def run_health_checks(self):
        """Health Checks"""
        self.ui.header("💚 HEALTH CHECKS")
        print("""
  [1] Run Health     - Execute health check
  [2] Configure      - Set endpoints to check
  [3] Alerts         - Configure failure alerts
  [4] History        - View health history
        """)
        input(f"\n{C.CYAN}Press Enter...{C.END}")

    def run_circuit_dashboard(self):
        """Circuit Dashboard"""
        self.ui.header("⚡ CIRCUIT DASHBOARD")
        print("""
  [1] View Circuits  - Show all circuit breakers
  [2] Circuit Stats  - Failure/open/closed states
  [3] Manual Reset   - Force reset a circuit
  [4] Thresholds     - Configure failure thresholds
        """)
        input(f"\n{C.CYAN}Press Enter...{C.END}")

    def run_service_registry(self):
        """Service Registry"""
        self.ui.header("📚 SERVICE REGISTRY")
        print("""
  [1] List Services  - Show registered services
  [2] Register       - Add new service
  [3] Deregister    - Remove service
  [4] Health         - Service health status
        """)
        input(f"\n{C.CYAN}Press Enter...{C.END}")

    def run_config_sync(self):
        """Config Sync"""
        self.ui.header("🔄 CONFIG SYNC")
        print("""
  [1] Sync Now       - Force config sync
  [2] Sync Status    - View sync state
  [3] Conflicts      - Resolve config conflicts
  [4] History        - View sync history
        """)
        input(f"\n{C.CYAN}Press Enter...{C.END}")

    def run_deployment_manager(self):
        """Deployment Manager"""
        self.ui.header("🚀 DEPLOYMENT MANAGER")
        print("""
  [1] Deploy         - Start new deployment
  [2] Rollback       - Revert to previous version
  [3] Deploy History - View deployment logs
  [4] Blue/Green     - Configure blue-green deploy
        """)
        input(f"\n{C.CYAN}Press Enter...{C.END}")

    def run_serverless(self):
        """Serverless Functions"""
        self.ui.header("λ SERVERLESS FUNCTIONS")
        print("""
  [1] Create Function - Deploy new function
  [2] List Functions  - View all functions
  [3] Invoke          - Test function
  [4] Logs            - View function logs
        """)
        input(f"\n{C.CYAN}Press Enter...{C.END}")

    def run_edge_computing(self):
        """Edge Computing"""
        self.ui.header("🌐 EDGE COMPUTING")
        print("""
  [1] Deploy Edge     - Deploy to edge nodes
  [2] Edge Nodes      - Manage edge locations
  [3] Sync Data       - Sync data to edges
  [4] Monitor         - Edge performance
        """)
        input(f"\n{C.CYAN}Press Enter...{C.END}")

    def run_message_queue(self):
        """Message Queue"""
        self.ui.header("📬 MESSAGE QUEUE")
        print("""
  [1] Create Queue   - New message queue
  [2] Publish        - Send message
  [3] Consume        - Receive messages
  [4] Queue Stats    - View queue metrics
        """)
        input(f"\n{C.CYAN}Press Enter...{C.END}")

    def run_stream_processor(self):
        """Stream Processor"""
        self.ui.header("🌊 STREAM PROCESSOR")
        print("""
  [1] Create Stream  - New stream pipeline
  [2] Process        - Process stream data
  [3] Analytics      - Real-time analytics
  [4] Backpressure   - Configure flow control
        """)
        input(f"\n{C.CYAN}Press Enter...{C.END}")

    def run_batch_jobs(self):
        """Batch Jobs"""
        self.ui.header("📦 BATCH JOBS")
        print("""
  [1] Submit Job     - Run batch job
  [2] Job History    - View past jobs
  [3] Schedule       - Schedule recurring jobs
  [4] Resources      - Configure job resources
        """)
        input(f"\n{C.CYAN}Press Enter...{C.END}")

    def run_apm_dashboard(self):
        """APM Dashboard"""
        self.ui.header("📈 APM DASHBOARD")
        print("""
  [1] Overview       - Application performance
  [2] Traces         - Distributed tracing
  [3] Metrics        - Custom metrics
  [4] Alerts         - Performance alerts
        """)
        input(f"\n{C.CYAN}Press Enter...{C.END}")

    def run_log_analyzer(self):
        """Log Analyzer"""
        self.ui.header("🔍 LOG ANALYZER")
        print("""
  [1] Search Logs    - Query logs
  [2] Patterns       - Detect patterns
  [3] Anomalies      - Find anomalies
  [4] Export         - Export logs
        """)
        input(f"\n{C.CYAN}Press Enter...{C.END}")

    def run_alert_manager(self):
        """Alert Manager"""
        self.ui.header("🚨 ALERT MANAGER")
        print("""
  [1] Create Alert   - Define alert rule
  [2] Active Alerts  - View firing alerts
  [3] Silence        - Silence notifications
  [4] Routes         - Configure routing
        """)
        input(f"\n{C.CYAN}Press Enter...{C.END}")

    def run_incident_response(self):
        """Incident Response"""
        self.ui.header("🆘 INCIDENT RESPONSE")
        print("""
  [1] Create Incident - Report new incident
  [2] Runbook        - Execute runbook
  [3] Timeline       - Incident timeline
  [4] Postmortem     - Write postmortem
        """)
        input(f"\n{C.CYAN}Press Enter...{C.END}")

    def run_cost_optimizer(self):
        """Cost Optimizer"""
        self.ui.header("💰 COST OPTIMIZER")
        print("""
  [1] Cost Report    - View spending
  [2] Recommendations - Cost savings tips
  [3] Budget         - Set budgets
  [4] Forecast       - Predict costs
        """)
        input(f"\n{C.CYAN}Press Enter...{C.END}")

    def run_topology(self):
        """View Swarm Network Topology"""
        self.ui.header("🌐 SWARM TOPOLOGY")
        try:
            r = requests.get("http://localhost:19888/api/status", timeout=2)
            if not r.ok:
                raise Exception("API Offline")
            data = r.json().get("neugi", {})
            agents = data.get("agents", [])

            if not agents:
                self.ui.warning("No active agents found in the swarm.")
            else:
                print(f"{C.BOLD}{'NAME':<12} {'ROLE':<15} {'STATUS':<10}{C.END}")
                print(f"{C.CYAN}{'-' * 40}{C.END}")
                for a in agents:
                    status = a.get("status", "idle")
                    color = (
                        C.GREEN
                        if status == "working"
                        else (C.YELLOW if status == "thinking" else C.END)
                    )
                    print(f"{a['name']:<12} {a['role']:<15} {color}{status}{C.END}")

            # Remote Nodes
            r_nodes = requests.get("http://localhost:19888/api/swarm/nodes", timeout=2)
            if r_nodes.ok:
                nodes = r_nodes.json()
                print(f"\n{C.BOLD}Remote Cluster Nodes:{C.END} {len(nodes)}")
                for node in nodes:
                    print(f"  🔗 {node}")

        except Exception as e:
            self.ui.error(f"Failed to fetch topology: {e}")
            self.ui.info("Ensure the NEUGI engine is running (Option 9 -> Start).")

        input(f"\n{C.CYAN}Press Enter to return to menu... {C.END}")

    def run_tools(self):
        """View Registered Skills/Tools"""
        self.ui.header("🛠️ SKILL REGISTRY")
        try:
            r = requests.get("http://localhost:19888/api/status", timeout=2)
            if not r.ok:
                raise Exception("API Offline")
            tools = r.json().get("neugi", {}).get("tools", [])

            if not tools:
                self.ui.warning("No registered tools found.")
            else:
                print(f"{C.BOLD}Available Capabilities:{C.END}\n")
                for i, t in enumerate(tools, 1):
                    name = t.get("name", "unknown")
                    print(f"  {C.PURPLE}{i:02d}.{C.END} {C.CYAN}{name:<20}{C.END}")

        except Exception as e:
            self.ui.error(f"Failed to fetch tools: {e}")

        input(f"\n{C.CYAN}Press Enter to return to menu... {C.END}")

    def run_monitor(self):
        """Live System Monitoring"""
        self.ui.header("📊 LIVE MONITOR")
        self.ui.info("Mode: Real-time Telemetry. Press Ctrl+C to stop.")

        import time

        try:
            while True:
                cpu = psutil.cpu_percent()
                ram = psutil.virtual_memory().percent

                # Try to get engine anomalies
                anomalies = 0
                try:
                    r = requests.get("http://localhost:19888/api/status", timeout=0.5)
                    if r.ok:
                        anomalies = len(r.json().get("issues", []))
                except Exception:
                    pass

                status_line = f"[{datetime.now().strftime('%H:%M:%S')}] CPU: {cpu:>4}% | RAM: {ram:>4}% | Anomalies: {anomalies}"
                print(
                    f"\r  {C.GREEN if anomalies == 0 else C.RED}{status_line}{C.END}",
                    end="",
                    flush=True,
                )
                time.sleep(2)
        except KeyboardInterrupt:
            print(f"\n\n{C.YELLOW}Monitor suspended.{C.END}")

    def run_logs(self):
        """View System Logs"""
        self.ui.header("📄 SYSTEM LOGS")
        try:
            r = requests.get("http://localhost:19888/api/logs", timeout=5)
            if r.ok:
                data = r.json()
                logs = data.get("logs", "No logs found.")
                log_path = data.get("path", "Unknown")

                self.ui.info(f"Log file: {log_path}")
                print(f"\n{C.BOLD}Last 50 lines:{C.END}\n")
                lines = logs.split("\n")[-50:]
                for line in lines:
                    print(f"  {line}")
            else:
                self.ui.error("Failed to fetch logs. Is the engine running?")
        except Exception as e:
            self.ui.error(f"Error: {e}")
            self.ui.info("Ensure NEUGI engine is running.")

        input(f"\n{C.CYAN}Press Enter to return to menu... {C.END}")

    # ============================================================
    # AUTO-BOOT FLOW
    # ============================================================

    def run_autoboot(self):
        """Manage auto-boot persistence"""
        self.ui.header("🔄 SOVEREIGN AUTO-BOOT")

        if platform.system() != "Windows":
            self.ui.warning("Auto-Boot persistence is currently only optimized for Windows.")
            input("\nPress Enter to return...")
            return

        enabled = PersistenceManager.is_enabled()
        status = f"{C.GREEN}ENABLED{C.END}" if enabled else f"{C.RED}DISABLED{C.END}"

        print(f"  Current Status: {status}")
        print(f"\n  {C.YELLOW}The system will automatically start Ollama, the Swarm Engine,")
        print(f"  and open the Dashboard upon device restart.{C.END}")

        choice = (
            input(
                f"\n  {C.CYAN}Would you like to {'DISABLE' if enabled else 'ENABLE'} Auto-Boot? (y/n): {C.END}"
            )
            .strip()
            .lower()
        )

        if choice == "y":
            if enabled:
                if PersistenceManager.disable():
                    self.ui.success("Auto-Boot disabled successfully.")
                else:
                    self.ui.error("Failed to disable Auto-Boot.")
            else:
                if PersistenceManager.enable():
                    self.ui.success("Auto-Boot enabled successfully!")
                else:
                    self.ui.error("Failed to enable Auto-Boot. Ensure you have permissions.")

        input(f"\n{C.CYAN}Press Enter to return to menu... {C.END}")

    # ============================================================
    # HELPERS
    # ============================================================

    def start_neugi(self):
        """Start NEUGI with conflict protection"""
        self.ui.info("Invoking Sovereign Engine...")

        # Check if already running via port
        try:
            r = requests.get("http://localhost:19888/health", timeout=1)
            if r.ok:
                self.ui.warning("Engine is already active on port 19888.")
                return
        except Exception:
            pass

        # Ensure script exists
        script_path = os.path.join(NEUGI_DIR, "neugi_swarm.py")
        if not os.path.exists(script_path):
            self.ui.warning(f"neugi_swarm.py not found in {NEUGI_DIR}")
            print(f"\n  {C.YELLOW}Download from GitHub? (y/n): {C.END}", end="")
            if input().strip().lower() == "y":
                self.download_files()

        # Start using the safe batch wrapper if available
        try:
            bat_path = os.path.join(NEUGI_DIR, "neugi.bat")
            if os.path.exists(bat_path):
                subprocess.Popen(
                    [bat_path, "start"],
                    cwd=NEUGI_DIR,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                    if platform.system() == "Windows"
                    else 0,
                )
            else:
                subprocess.Popen(
                    [sys.executable, script_path],
                    cwd=NEUGI_DIR,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )

            self.ui.success(f"{BRAND} deployment initiated!")
            self.ui.info("Monitor: Option 4 | Console: http://localhost:19888")
        except Exception as e:
            self.ui.error(f"Deployment failed: {e}")

    def download_files(self):
        """Download NEUGI files"""
        self.ui.info("Downloading...")

        files = [
            "neugi_swarm.py",
            "neugi_assistant.py",
            "neugi_swarm_agents.py",
            "neugi_swarm_tools.py",
            "neugi_telegram.py",
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
            except Exception:
                self.ui.error(f"Failed: {f}")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    wizard = NEUGIWizard()
    wizard.run()
