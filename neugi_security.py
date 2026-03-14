#!/usr/bin/env python3
"""
🤖 NEUGI SECURITY LAYER
========================

Security system with user-friendly defaults!

Default: SECURE (sandboxed)
User can configure: FULL ACCESS

Version: 1.0
Date: March 14, 2026
"""

import os
import sys
import json
import re
import subprocess
import tempfile
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


DEFAULT_CONFIG = {
    "sandbox_mode": True,  # Secure by default!
    "allowed_commands": ["python", "python3", "git", "pip"],
    "blocked_commands": ["rm -rf", "dd if=", ":(){:|:&};:", "mkfs", "fdisk"],
    "max_execution_time": 30,  # seconds
    "max_memory_mb": 512,
    "allow_network": True,
    "allow_file_write": False,
    "allowed_dirs": ["~/neugi", "~/neugi/data", "~/neugi/plugins", "/tmp"],
    "api_key_required": False,
    "telegram_whitelist": [],
    "audit_enabled": True,
}


@dataclass
class SecurityConfig:
    """Security configuration"""

    sandbox_mode: bool = True
    allowed_commands: List[str] = None
    blocked_commands: List[str] = None
    max_execution_time: int = 30
    max_memory_mb: int = 512
    allow_network: bool = True
    allow_file_write: bool = False
    allowed_dirs: List[str] = None
    api_key_required: bool = False
    telegram_whitelist: List[str] = None
    audit_enabled: bool = True

    def __post_init__(self):
        if self.allowed_commands is None:
            self.allowed_commands = DEFAULT_CONFIG["allowed_commands"]
        if self.blocked_commands is None:
            self.blocked_commands = DEFAULT_CONFIG["blocked_commands"]
        if self.allowed_dirs is None:
            self.allowed_dirs = DEFAULT_CONFIG["allowed_dirs"]
        if self.telegram_whitelist is None:
            self.telegram_whitelist = DEFAULT_CONFIG["telegram_whitelist"]


class SecurityManager:
    """
    NEUGI Security Manager

    Secure by default! User can enable full access when needed.
    """

    def __init__(self, config_path: str = None):
        self.config_path = config_path or os.path.expanduser(
            "~/neugi/data/security.json"
        )
        self.config = self._load_config()
        self.audit_log = []

    def _load_config(self) -> SecurityConfig:
        """Load security config"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path) as f:
                    data = json.load(f)
                return SecurityConfig(
                    **{k: v for k, v in data.items() if k in DEFAULT_CONFIG}
                )
            except:
                pass
        return SecurityConfig(**DEFAULT_CONFIG)

    def _save_config(self):
        """Save security config"""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, "w") as f:
            json.dump(self.config.__dict__, f, indent=2)

    def enable_full_access(self):
        """
        Enable FULL ACCESS mode - for advanced users!

        ⚠️  WARNING: This allows executing ANY command!
        Only use when you trust what you're doing!
        """
        self.config.sandbox_mode = False
        self.config.allow_file_write = True
        self.config.allowed_commands = ["*"]  # Allow all
        self.config.allowed_dirs = ["*"]  # Allow all dirs
        self._save_config()
        return "FULL ACCESS enabled! ⚠️"

    def enable_sandbox(self):
        """Enable secure sandbox mode (default)"""
        self.config.sandbox_mode = True
        self.config.allow_file_write = False
        self.config.allowed_commands = DEFAULT_CONFIG["allowed_commands"]
        self.config.allowed_dirs = DEFAULT_CONFIG["allowed_dirs"]
        self._save_config()
        return "Sandbox mode enabled! 🔒"

    def add_allowed_command(self, cmd: str):
        """Add command to allowed list"""
        if cmd not in self.config.allowed_commands:
            self.config.allowed_commands.append(cmd)
            self._save_config()

    def add_allowed_dir(self, path: str):
        """Add directory to allowed list"""
        expanded = os.path.expanduser(path)
        if expanded not in self.config.allowed_dirs:
            self.config.allowed_dirs.append(expanded)
            self._save_config()

    def is_command_safe(self, command: str) -> tuple:
        """
        Check if command is safe to execute

        Returns: (is_safe, reason)
        """
        if self.config.sandbox_mode:
            # Check blocked commands
            for blocked in self.config.blocked_commands:
                if blocked in command:
                    return False, f"Blocked: {blocked}"

            # Check allowed commands
            if "*" not in self.config.allowed_commands:
                cmd_parts = command.strip().split()
                if cmd_parts:
                    base_cmd = cmd_parts[0]
                    if base_cmd not in self.config.allowed_commands:
                        return False, f"Command not allowed: {base_cmd}"

            # Check dangerous patterns
            dangerous = ["sudo", "chmod 777", "curl | sh", "wget | sh"]
            for d in dangerous:
                if d in command:
                    return False, f"Dangerous pattern: {d}"

        return True, "OK"

    def is_path_safe(self, path: str) -> tuple:
        """Check if path is safe"""
        expanded = os.path.expanduser(path)

        if self.config.sandbox_mode:
            if "*" not in self.config.allowed_dirs:
                allowed = False
                for allowed_dir in self.config.allowed_dirs:
                    if expanded.startswith(os.path.expanduser(allowed_dir)):
                        allowed = True
                        break
                if not allowed:
                    return False, f"Directory not allowed: {path}"

        return True, "OK"

    def execute_sandboxed(self, command: str, timeout: int = None) -> Dict:
        """
        Execute command in sandbox

        Returns: {success, output, error}
        """
        # Check safety
        is_safe, reason = self.is_command_safe(command)
        if not is_safe:
            self._audit("BLOCKED", command, reason)
            return {"success": False, "error": reason}

        timeout = timeout or self.config.max_execution_time

        try:
            # Execute in temp environment
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            self._audit("EXECUTE", command, "success")
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr if result.returncode != 0 else None,
                "returncode": result.returncode,
            }

        except subprocess.TimeoutExpired:
            self._audit("TIMEOUT", command, f"Exceeded {timeout}s")
            return {"success": False, "error": f"Execution timeout ({timeout}s)"}
        except Exception as e:
            self._audit("ERROR", command, str(e))
            return {"success": False, "error": str(e)}

    def _audit(self, action: str, target: str, result: str):
        """Log security event"""
        if self.config.audit_enabled:
            entry = {
                "timestamp": str(os.popen("date").read().strip()),
                "action": action,
                "target": target[:100],  # Truncate long commands
                "result": result[:100],
            }
            self.audit_log.append(entry)

            # Also save to file
            audit_path = os.path.expanduser("~/neugi/data/security_audit.json")
            try:
                with open(audit_path, "a") as f:
                    f.write(json.dumps(entry) + "\n")
            except:
                pass

    def get_audit_log(self, limit: int = 20) -> List[Dict]:
        """Get recent audit log"""
        return self.audit_log[-limit:]

    def get_status(self) -> Dict:
        """Get security status"""
        return {
            "sandbox_mode": self.config.sandbox_mode,
            "full_access": not self.config.sandbox_mode,
            "allowed_commands": self.config.allowed_commands,
            "allowed_dirs": len(self.config.allowed_dirs),
            "audit_enabled": self.config.audit_enabled,
            "security_level": "FULL ACCESS ⚠️"
            if not self.config.sandbox_mode
            else "SECURE 🔒",
        }


# Easy config UI
def security_wizard():
    """Interactive security configuration"""
    manager = SecurityManager()

    print("\n" + "=" * 50)
    print("🔐 NEUGI SECURITY CONFIGURATION")
    print("=" * 50)

    status = manager.get_status()
    print(f"\nCurrent: {status['security_level']}")
    print(f"Sandbox: {status['sandbox_mode']}")
    print(f"Allowed Commands: {', '.join(status['allowed_commands'][:5])}...")

    print("\nOptions:")
    print("  1. 🔒 Enable Sandbox (SECURE - Default)")
    print("  2. ⚠️  Enable FULL ACCESS (Advanced)")
    print("  3. ➕ Add Allowed Command")
    print("  4. 📋 Show Security Status")
    print("  5. 📜 Show Audit Log")
    print("  0. Exit")

    choice = input("\n> ").strip()

    if choice == "1":
        result = manager.enable_sandbox()
        print(f"\n✅ {result}")
    elif choice == "2":
        print("\n⚠️  WARNING: Full access allows ANY command execution!")
        confirm = input("Type 'YES' to confirm: ").strip()
        if confirm == "YES":
            result = manager.enable_full_access()
            print(f"\n✅ {result}")
        else:
            print("\nCancelled.")
    elif choice == "3":
        cmd = input("Command to add (e.g., docker): ").strip()
        if cmd:
            manager.add_allowed_command(cmd)
            print(f"\n✅ Added: {cmd}")
    elif choice == "4":
        status = manager.get_status()
        print("\n" + "-" * 40)
        for k, v in status.items():
            print(f"  {k}: {v}")
    elif choice == "5":
        logs = manager.get_audit_log()
        print("\nRecent Security Events:")
        for log in logs[-10:]:
            print(f"  [{log['action']}] {log['target'][:40]}")


if __name__ == "__main__":
    security_wizard()
