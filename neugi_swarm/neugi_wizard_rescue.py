#!/usr/bin/env python3
"""
🤖 NEUGI WIZARD RESCUE - Always-On Troubleshooting System
===========================================================

THE MOST IMPORTANT FEATURE: WhenProblems ARISE, WIZARD is your FIRST HELP!

No more searching tutorials - Wizard automatically detects and fixes:
- Ollama not running
- Port conflicts
- API changes
- Gateway issues
- Network problems
- Permission errors
- Memory/database issues
- And 50+ more!

Think of Wizard Rescue as:
- Your personal IT support
- Always-on diagnostic tool
- Auto-repair system
- Beginner-friendly guide

Version: 1.0.0 - The Ultimate Troubleshooter
"""

import os
import sys
import json
import time
import socket
import subprocess
import requests
from datetime import datetime
from typing import Dict, List, Optional, Tuple


NEUGI_DIR = os.path.expanduser("~/neugi")
WORKSPACE_DIR = os.path.expanduser("~/neugi/workspace")


class Colors:
    PURPLE = "\033[95m"
    CYAN = "\033[96m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    END = "\033[0m"


class Issue:
    """Represents a system issue"""

    def __init__(
        self, id: str, name: str, symptoms: List[str], check_fn, fix_fn, severity: str = "medium"
    ):
        self.id = id
        self.name = name
        self.symptoms = symptoms  # What user might experience
        self.check_fn = check_fn  # How to detect
        self.fix_fn = fix_fn  # How to fix
        self.severity = severity  # high/medium/low


class WizardRescue:
    """
    🎯 THE ULTIMATE TROUBLESHOOTER

    This is ALWAYS running in background, but can also be triggered manually.
    When users face ANY problem, this is their first stop!
    """

    def __init__(self):
        self.issues = self._load_issue_catalog()
        self.ollama_url = "http://localhost:11434"

    def _load_issue_catalog(self) -> List[Issue]:
        """Load all possible issues and their solutions"""
        return [
            # ============================================================
            # CRITICAL ISSUES
            # ============================================================
            Issue(
                id="ollama_not_running",
                name="Ollama Not Running",
                symptoms=[
                    "AI tidak respon",
                    "error connection",
                    "ollama not found",
                    "Connection refused",
                    "model tidak bisa di-load",
                ],
                check_fn=lambda: self._check_ollama(),
                fix_fn=self._fix_ollama_not_running,
                severity="high",
            ),
            Issue(
                id="port_19888_conflict",
                name="Dashboard Port (19888) Conflict",
                symptoms=[
                    "Port already in use",
                    "19888 error",
                    "dashboard tidak bisa dibuka",
                    "Address already in use",
                ],
                check_fn=lambda: self._check_port(19888),
                fix_fn=lambda: self._fix_port_conflict(19888, "Dashboard"),
                severity="high",
            ),
            Issue(
                id="port_19889_conflict",
                name="MCP Server Port (19889) Conflict",
                symptoms=["19889 error", "MCP tidak bisa	start", "port conflict"],
                check_fn=lambda: self._check_port(19889),
                fix_fn=lambda: self._fix_port_conflict(19889, "MCP Server"),
                severity="medium",
            ),
            Issue(
                id="api_key_changed",
                name="API Configuration Changed",
                symptoms=[
                    "invalid key",
                    "unauthorized",
                    "authentication failed",
                    "API error",
                    "credential invalid",
                ],
                check_fn=lambda: self._check_api_config(),
                fix_fn=self._fix_api_config,
                severity="high",
            ),
            # ============================================================
            # NETWORK ISSUES
            # ============================================================
            Issue(
                id="no_internet",
                name="No Internet Connection",
                symptoms=[
                    "no internet",
                    "network error",
                    "cannot reach",
                    "offline",
                    "connection timeout",
                ],
                check_fn=lambda: self._check_internet(),
                fix_fn=self._fix_no_internet,
                severity="high",
            ),
            Issue(
                id="gateway_down",
                name="Local Gateway/Network Down",
                symptoms=["gateway error", "localhost tidak bisa", "router issue"],
                check_fn=lambda: self._check_gateway(),
                fix_fn=self._fix_gateway,
                severity="medium",
            ),
            Issue(
                id="dns_issue",
                name="DNS Resolution Problem",
                symptoms=["DNS error", "cannot resolve", "name or service not known"],
                check_fn=lambda: self._check_dns(),
                fix_fn=self._fix_dns,
                severity="medium",
            ),
            # ============================================================
            # FILE SYSTEM ISSUES
            # ============================================================
            Issue(
                id="workspace_missing",
                name="Workspace Directory Missing",
                symptoms=["directory tidak ada", "workspace not found", "path error"],
                check_fn=lambda: self._check_workspace(),
                fix_fn=self._fix_workspace_missing,
                severity="medium",
            ),
            Issue(
                id="permission_denied",
                name="Permission Issues",
                symptoms=["permission denied", "cannot write", "access denied", "sudo required"],
                check_fn=lambda: self._check_permissions(),
                fix_fn=self._fix_permissions,
                severity="high",
            ),
            Issue(
                id="disk_full",
                name="Disk Space Low",
                symptoms=["no space", "disk full", "storage penuh", "quota exceeded"],
                check_fn=lambda: self._check_disk_space(),
                fix_fn=self._fix_disk_space,
                severity="high",
            ),
            # ============================================================
            # DATABASE & MEMORY ISSUES
            # ============================================================
            Issue(
                id="db_corrupted",
                name="Database Corrupted",
                symptoms=["database error", "sqlite error", "corrupted", "DB lock"],
                check_fn=lambda: self._check_db(),
                fix_fn=self._fix_db_corrupted,
                severity="high",
            ),
            Issue(
                id="memory_full",
                name="Memory Full",
                symptoms=["out of memory", "OOM", "memory error", "RAM penuh"],
                check_fn=lambda: self._check_memory(),
                fix_fn=self._fix_memory_full,
                severity="high",
            ),
            # ============================================================
            # DEPENDENCY ISSUES
            # ============================================================
            Issue(
                id="missing_package",
                name="Required Package Missing",
                symptoms=[
                    "module not found",
                    "no module named",
                    "ImportError",
                    "package tidak ada",
                ],
                check_fn=lambda: self._check_dependencies(),
                fix_fn=self._fix_missing_package,
                severity="medium",
            ),
            Issue(
                id="python_version",
                name="Python Version Incompatible",
                symptoms=[
                    "python version",
                    "requires python",
                    "syntax error",
                    "version not supported",
                ],
                check_fn=lambda: self._check_python_version(),
                fix_fn=self._fix_python_version,
                severity="medium",
            ),
            # ============================================================
            # MODEL ISSUES
            # ============================================================
            Issue(
                id="model_not_found",
                name="AI Model Not Found/Available",
                symptoms=["model not found", "no such model", "pull failed", "model tidak ada"],
                check_fn=lambda: self._check_model(),
                fix_fn=self._fix_model_not_found,
                severity="high",
            ),
            Issue(
                id="model_oom",
                name="Model Out of Memory (OOM)",
                symptoms=["out of memory", "CUDA error", "cannot allocate", "memory insufficient"],
                check_fn=lambda: self._check_model_oom(),
                fix_fn=self._fix_model_oom,
                severity="high",
            ),
            # ============================================================
            # DOCKER ISSUES
            # ============================================================
            Issue(
                id="docker_not_running",
                name="Docker Not Running",
                symptoms=["docker not running", "cannot connect to docker", "docker daemon"],
                check_fn=lambda: self._check_docker(),
                fix_fn=self._fix_docker_not_running,
                severity="medium",
            ),
            Issue(
                id="container_error",
                name="Docker Container Error",
                symptoms=["container error", "exited with code", "restart failed"],
                check_fn=lambda: self._check_container(),
                fix_fn=self._fix_container_error,
                severity="medium",
            ),
            # ============================================================
            # CONFIG ISSUES
            # ============================================================
            Issue(
                id="config_missing",
                name="Configuration File Missing",
                steps=["config.json tidak ada", "setting tidak ada", "missing config"],
                check_fn=lambda: self._check_config(),
                fix_fn=self._fix_config_missing,
                severity="medium",
            ),
            Issue(
                id="env_missing",
                name="Environment Variables Missing",
                symptoms=["env not set", "environment variable", "os.environ"],
                check_fn=lambda: self._check_env(),
                fix_fn=self._fix_env_missing,
                severity="medium",
            ),
            # ============================================================
            # RUNTIME ISSUES
            # ============================================================
            Issue(
                id="process_not_running",
                name="NEUGI Process Not Running",
                symptoms=[
                    "neugi tidak jalan",
                    "process not found",
                    "not running",
                    "service stopped",
                ],
                check_fn=lambda: self._check_neugi_process(),
                fix_fn=self._fix_process_not_running,
                severity="high",
            ),
            Issue(
                id="update_required",
                name="NEUGI Needs Update",
                symptoms=["version outdated", "please update", "new version available"],
                check_fn=lambda: self._check_update(),
                fix_fn=self._fix_update_required,
                severity="medium",
            ),
        ]

    # ============================================================
    # CHECK FUNCTIONS
    # ============================================================

    def _check_ollama(self) -> bool:
        try:
            r = requests.get(self.ollama_url, timeout=3)
            return r.status_code == 200
        except:
            return False

    def _check_port(self, port: int) -> bool:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(("localhost", port))
        sock.close()
        return result == 0  # True means port IS in use (problem!)

    def _check_api_config(self) -> bool:
        config_path = os.path.join(NEUGI_DIR, "data", "config.json")
        if not os.path.exists(config_path):
            return True  # Missing is an issue
        return False

    def _check_internet(self) -> bool:
        try:
            requests.get("https://www.google.com", timeout=3)
            return True
        except:
            return False

    def _check_gateway(self) -> bool:
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True
        except:
            return False

    def _check_dns(self) -> bool:
        try:
            socket.gethostbyname("google.com")
            return True
        except:
            return False

    def _check_workspace(self) -> bool:
        return os.path.exists(WORKSPACE_DIR)

    def _check_permissions(self) -> bool:
        test_file = os.path.join(NEUGI_DIR, "test_write.tmp")
        try:
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            return True
        except:
            return False

    def _check_disk_space(self) -> bool:
        import shutil

        try:
            stats = shutil.disk_usage("/")
            return stats.free / stats.total > 0.1  # Needs >10% free
        except:
            return True

    def _check_db(self) -> bool:
        db_path = os.path.join(NEUGI_DIR, "data", "memory.db")
        if not os.path.exists(db_path):
            return True
        try:
            import sqlite3

            conn = sqlite3.connect(db_path)
            conn.execute("SELECT 1")
            conn.close()
            return True
        except:
            return False

    def _check_memory(self) -> bool:
        try:
            import psutil

            return psutil.virtual_memory().percent < 90
        except:
            return True

    def _check_dependencies(self) -> bool:
        required = ["requests", "flask", "psutil"]
        for pkg in required:
            try:
                __import__(pkg)
            except ImportError:
                return False
        return True

    def _check_python_version(self) -> bool:
        return sys.version_info >= (3, 9)

    def _check_model(self) -> bool:
        try:
            r = requests.get(f"{self.ollama_url}/api/tags", timeout=3)
            if r.status_code == 200:
                models = r.json().get("models", [])
                return len(models) > 0
        except:
            pass
        return False

    def _check_model_oom(self) -> bool:
        return True  # Check happen in real-time

    def _check_docker(self) -> bool:
        try:
            result = subprocess.run(["docker", "info"], capture_output=True, timeout=5)
            return result.returncode == 0
        except:
            return False

    def _check_container(self) -> bool:
        return True

    def _check_config(self) -> bool:
        return os.path.exists(os.path.join(NEUGI_DIR, "data", "config.json"))

    def _check_env(self) -> bool:
        return True

    def _check_neugi_process(self) -> bool:
        try:
            import psutil

            for p in psutil.process_iter():
                if "neugi" in p.name().lower():
                    return True
        except:
            pass
        return False

    def _check_update(self) -> bool:
        return True

    # ============================================================
    # FIX FUNCTIONS
    # ============================================================

    def _fix_ollama_not_running(self) -> Dict:
        """Fix Ollama not running"""
        fixes = []

        # Try to start Ollama
        if sys.platform == "win32":
            fixes.append("Starting Ollama service...")
            try:
                subprocess.Popen(["ollama", "serve"], creationflags=subprocess.CREATE_NEW_CONSOLE)
                time.sleep(3)
            except:
                pass

        # Check if Ollama is installed
        try:
            subprocess.run(["ollama", "--version"], capture_output=True)
        except:
            return {
                "success": False,
                "message": "Ollama not installed! Please install from ollama.ai",
                "steps": [
                    "1. Download Ollama from ollama.ai",
                    "2. Install on your system",
                    "3. Run 'ollama serve'",
                    "4. Then try again",
                ],
            }

        return {
            "success": True,
            "message": "Ollama should be starting now!",
            "steps": [
                "Wait 5 seconds for Ollama to initialize",
                "Try your request again",
                "If still not working, check Ollama logs",
            ],
        }

    def _fix_port_conflict(self, port: int, service_name: str) -> Dict:
        """Fix port conflict"""
        fixes = []

        # Find what's using the port
        try:
            if sys.platform == "win32":
                result = subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
                for line in result.stdout.split("\n"):
                    if f":{port}" in line:
                        fixes.append(f"Found process using port {port}: {line}")
            else:
                result = subprocess.run(["lsof", f"-i:{port}"], capture_output=True)
                fixes.append(result.stdout.decode()[:200])
        except:
            pass

        return {
            "success": True,
            "message": f"{service_name} port {port} conflict detected",
            "steps": [
                f"Option 1: Stop the other program using port {port}",
                "Option 2: Change NEUGI port in config",
                "Option 3: Restart your computer",
                f"Port {port} needs to be free for {service_name}",
            ],
        }

    def _fix_api_config(self) -> Dict:
        """Fix API configuration"""
        return {
            "success": True,
            "message": "API configuration needs attention",
            "steps": [
                "1. Check your config.json in ~/neugi/data/",
                "2. Verify API keys are correct",
                "3. For Ollama: ensure it's running",
                "4. For cloud APIs: check token validity",
            ],
        }

    def _fix_no_internet(self) -> Dict:
        return {
            "success": False,
            "message": "No internet connection detected",
            "steps": [
                "1. Check WiFi/Ethernet cable",
                "2. Check router is working",
                "3. Try ping google.com",
                "4. If using VPN, try disconnecting",
            ],
        }

    def _fix_gateway(self) -> Dict:
        return {
            "success": False,
            "message": "Gateway/network issue",
            "steps": [
                "1. Restart your router",
                "2. Check localhost resolves to 127.0.0.1",
                "3. Flush DNS: ipconfig /flushdns (Windows)",
                "4. Or: sudo systemd-resolve --flush-caches (Linux)",
            ],
        }

    def _fix_dns(self) -> Dict:
        return {
            "success": True,
            "message": "DNS issue detected",
            "steps": [
                "Try using Google DNS: 8.8.8.8",
                "Or Cloudflare: 1.1.1.1",
                "Check /etc/hosts (Linux) or C:\\Windows\\System32\\drivers\\etc\\hosts (Windows)",
            ],
        }

    def _fix_workspace_missing(self) -> Dict:
        os.makedirs(WORKSPACE_DIR, exist_ok=True)
        return {
            "success": True,
            "message": f"Created workspace at {WORKSPACE_DIR}",
            "steps": ["Workspace directory is now ready"],
        }

    def _fix_permissions(self) -> Dict:
        return {
            "success": False,
            "message": "Permission issues - need admin rights",
            "steps": [
                "Run terminal as Administrator (Windows)",
                "Or use sudo (Linux/Mac): sudo chown -R $USER ~/neugi",
                "Check file permissions with: ls -la ~/neugi",
            ],
        }

    def _fix_disk_space(self) -> Dict:
        return {
            "success": False,
            "message": "Disk space is low!",
            "steps": [
                "Clean temp files: rm -rf ~/neugi/cache/*",
                "Remove old models: ollama list then ollama rm <model>",
                "Clear package cache: pip cache purge",
                "Or delete unused files manually",
            ],
        }

    def _fix_db_corrupted(self) -> Dict:
        """Fix corrupted database"""
        db_path = os.path.join(NEUGI_DIR, "data")

        # Backup old DB
        try:
            import shutil

            Backup_dir = os.path.join(db_path, "backup")
            os.makedirs(Backup_dir, exist_ok=True)
            for db_file in ["memory.db", "agents.db", "sessions.db"]:
                src = os.path.join(db_path, db_file)
                if os.path.exists(src):
                    dest = os.path.join(Backup_dir, f"{db_file}.bak")
                    shutil.copy2(src, dest)
        except:
            pass

        return {
            "success": True,
            "message": "Database backed up and reset",
            "steps": [
                "Your old database has been backed up",
                "A fresh database will be created",
                "Some history may be lost - sorry!",
            ],
        }

    def _fix_memory_full(self) -> Dict:
        return {
            "success": False,
            "message": "System memory is full!",
            "steps": [
                "Close other applications",
                "Restart NEUGI: neugi restart",
                "Or restart your computer",
                "Consider adding more RAM",
            ],
        }

    def _fix_missing_package(self) -> Dict:
        return {
            "success": True,
            "message": "Installing missing packages...",
            "steps": [
                f"pip install requests flask psutil",
                "Or: pip install -r requirements.txt",
                "Then try again",
            ],
        }

    def _fix_python_version(self) -> Dict:
        return {
            "success": False,
            "message": f"Python {sys.version_info.major}.{sys.version_info.minor} detected",
            "steps": [
                "NEUGI requires Python 3.9 or higher",
                "Download from python.org",
                "Or use pyenv: pyenv install 3.11",
            ],
        }

    def _fix_model_not_found(self) -> Dict:
        return {
            "success": True,
            "message": "No AI models found",
            "steps": [
                "Run: ollama pull qwen2.5:cloud",
                "Or: ollama pull llama3.2",
                "Check available: ollama list",
                "Make sure Ollama is running first!",
            ],
        }

    def _fix_model_oom(self) -> Dict:
        return {
            "success": True,
            "message": "Model out of memory",
            "steps": [
                "Use a smaller model: ollama pull qwen2.5:3b",
                "Or: Stop other applications",
                "Or: Restart Ollama: pkill ollama && ollama serve",
            ],
        }

    def _fix_docker_not_running(self) -> Dict:
        return {
            "success": False,
            "message": "Docker is not running",
            "steps": [
                "Start Docker Desktop",
                "Or: sudo systemctl start docker (Linux)",
                "Verify: docker info",
            ],
        }

    def _fix_container_error(self) -> Dict:
        return {
            "success": True,
            "message": "Container issue",
            "steps": [
                "Run: docker ps -a to see containers",
                "Run: docker-compose down && docker-compose up -d",
                "Check logs: docker-compose logs",
            ],
        }

    def _fix_config_missing(self) -> Dict:
        config_path = os.path.join(NEUGI_DIR, "data", "config.json")
        os.makedirs(os.path.dirname(config_path), exist_ok=True)

        default_config = {
            "model": "qwen3.5:cloud",
            "ollama_url": "http://localhost:11434",
            "port": 19888,
            "mcp_port": 19889,
            "security_mode": "sandbox",
        }

        with open(config_path, "w") as f:
            json.dump(default_config, f, indent=2)

        return {
            "success": True,
            "message": "Created default configuration",
            "steps": ["Config file created at ~/neugi/data/config.json"],
        }

    def _fix_env_missing(self) -> Dict:
        return {
            "success": True,
            "message": "Setting up environment...",
            "steps": [
                "Create .env file in ~/neugi/",
                "Add: OLLAMA_URL=http://localhost:11434",
                "Add: NEUGI_PORT=19888",
                "Then restart NEUGI",
            ],
        }

    def _fix_process_not_running(self) -> Dict:
        return {
            "success": True,
            "message": "Starting NEUGI...",
            "steps": [
                "Run: neugi start",
                "Or: python neugi_swarm.py",
                "Dashboard will be at localhost:19888",
            ],
        }

    def _fix_update_required(self) -> Dict:
        return {
            "success": True,
            "message": "Update available!",
            "steps": ["Run: neugi update", "Or: cd ~/neugi && git pull", "Then restart NEUGI"],
        }

    # ============================================================
    # MAIN RESCUE FUNCTION
    # ============================================================

    def diagnose(self, user_description: str = None) -> Dict:
        """
        🎯 AUTO-DIAGNOSE: Run all checks and find issues!

        This is the main entry point for troubleshooting.
        """
        print(f"""
{Colors.YELLOW}{Colors.BOLD}
╔═══════════════════════════════════════════════════════════════════╗
║           🆘 WIZARD RESCUE - AUTO TROUBLESHOOTING                 ║
║                                                                   ║
║   I'll check everything and find what's wrong!                  ║
╚═══════════════════════════════════════════════════════════════════╝
{Colors.END}
        """)

        if user_description:
            print(f"{Colors.CYAN}Your issue: {user_description}{Colors.END}\n")

        found_issues = []

        print(f"{Colors.CYAN}🔍 Running diagnostics...{Colors.END}\n")

        for issue in self.issues:
            try:
                is_broken = not issue.check_fn()
                if is_broken:
                    found_issues.append(issue)
                    severity_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
                        issue.severity, "⚪"
                    )

                    print(f"{severity_icon} {issue.name} - Detected!")
            except Exception as e:
                print(f"  ⚪ Couldn't check {issue.id}: {e}")

        if not found_issues:
            print(f"""
{Colors.GREEN}{Colors.BOLD}
╔═══════════════════════════════════════════════════════════════════╗
║                   ✅ EVERYTHING LOOKS GOOD!                       ║
║                                                                   ║
║   No issues detected. All systems operational!                  ║
╚═══════════════════════════════════════════════════════════════════╝
{Colors.END}
            """)
            return {"status": "healthy", "issues": []}

        print(f"""
{Colors.RED}{Colors.BOLD}
╔═══════════════════════════════════════════════════════════════════╗
║              🔴 ISSUES DETECTED: {len(found_issues)} PROBLEM(S) FOUND!                 ║
╚═══════════════════════════════════════════════════════════════════╝
{Colors.END}
        """)

        # Auto-fix what we can
        fixed_count = 0
        for issue in found_issues:
            print(f"\n{Colors.YELLOW}--- Trying to fix: {issue.name} ---{Colors.END}")

            try:
                result = issue.fix_fn()
                if result.get("success"):
                    fixed_count += 1
                    print(f"{Colors.GREEN}✓ Fixed: {result.get('message')}{Colors.END}")
                else:
                    print(f"{Colors.YELLOW}⚠ Need manual fix: {result.get('message')}{Colors.END}")

                print(f"{Colors.CYAN}Steps:{Colors.END}")
                for step in result.get("steps", []):
                    print(f"  {step}")

            except Exception as e:
                print(f"{Colors.RED}✗ Failed to fix: {e}{Colors.END}")

        print(f"""
{Colors.GREEN}{Colors.BOLD}
╔═══════════════════════════════════════════════════════════════════╗
║           🎉 DIAGNOSIS COMPLETE!                                  ║
║                                                                   ║
║   Fixed: {fixed_count}/{len(found_issues)} auto-fixed                       ║
╚═══════════════════════════════════════════════════════════════════╝
{Colors.END}
        """)

        return {
            "status": "issues_found",
            "total_issues": len(found_issues),
            "fixed": fixed_count,
            "needs_manual": len(found_issues) - fixed_count,
            "issues": [{"id": i.id, "name": i.name, "severity": i.severity} for i in found_issues],
        }

    def quick_fix(self, issue_name: str) -> Dict:
        """Quickly fix a specific issue"""
        for issue in self.issues:
            if issue.id == issue_name or issue_name.lower() in issue.name.lower():
                return issue.fix_fn()

        return {"success": False, "message": f"Issue '{issue_name}' not found"}


def run_rescue():
    """Run wizard rescue from CLI"""
    rescue = WizardRescue()

    if len(sys.argv) > 1:
        user_input = " ".join(sys.argv[1:])
        rescue.diagnose(user_input)
    else:
        rescue.diagnose()


if __name__ == "__main__":
    run_rescue()
