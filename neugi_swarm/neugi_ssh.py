#!/usr/bin/env python3
"""
🤖 NEUGI SSH MANAGER
======================

SSH and terminal management:
- SSH connections
- Key management
- Session management
- Command execution

Version: 1.0
Date: March 16, 2026
"""

import os
import json
import subprocess
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

NEUGI_DIR = os.path.expanduser("~/neugi")
SSH_DIR = os.path.join(NEUGI_DIR, "ssh")
CONFIG_FILE = os.path.join(SSH_DIR, "config.json")
os.makedirs(SSH_DIR, exist_ok=True)


class SSHConnection:
    """SSH Connection definition"""
    
    def __init__(self, id: str = None, name: str = "", host: str = "", 
                 port: int = 22, user: str = "root", key_file: str = None,
                 password: str = None):
        self.id = id or str(uuid.uuid4())[:8]
        self.name = name
        self.host = host
        self.port = port
        self.user = user
        self.key_file = key_file
        self.password = password
        self.last_connected = None
        self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "key_file": self.key_file,
            "last_connected": self.last_connected,
            "created_at": self.created_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "SSHConnection":
        conn = cls(
            data["id"], data["name"], data["host"], 
            data.get("port", 22), data.get("user", "root"),
            data.get("key_file"), data.get("password")
        )
        conn.last_connected = data.get("last_connected")
        conn.created_at = data.get("created_at", datetime.now().isoformat())
        return conn


class SSHManager:
    """SSH Connection Manager"""
    
    def __init__(self):
        self.connections = self._load_connections()
    
    def _load_connections(self) -> List[SSHConnection]:
        """Load saved connections"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE) as f:
                    data = json.load(f)
                    return [SSHConnection.from_dict(c) for c in data]
            except:
                pass
        return []
    
    def _save_connections(self):
        """Save connections"""
        with open(CONFIG_FILE, "w") as f:
            json.dump([c.to_dict() for c in self.connections], f, indent=2)
    
    def add_connection(self, name: str, host: str, user: str = "root", 
                       port: int = 22, key_file: str = None, password: str = None) -> SSHConnection:
        """Add new SSH connection"""
        conn = SSHConnection(None, name, host, port, user, key_file, password)
        self.connections.append(conn)
        self._save_connections()
        return conn
    
    def remove_connection(self, conn_id: str):
        """Remove connection"""
        self.connections = [c for c in self.connections if c.id != conn_id]
        self._save_connections()
    
    def get_connection(self, conn_id: str) -> Optional[SSHConnection]:
        """Get connection by ID"""
        for c in self.connections:
            if c.id == conn_id:
                return c
        return None
    
    def list_connections(self) -> List[Dict]:
        """List all connections"""
        return [c.to_dict() for c in self.connections]
    
    def connect(self, conn_id: str) -> Dict:
        """Connect via SSH"""
        conn = self.get_connection(conn_id)
        if not conn:
            return {"success": False, "error": "Connection not found"}
        
        cmd = ["ssh"]
        
        if conn.port != 22:
            cmd.extend(["-p", str(conn.port)])
        
        if conn.key_file:
            cmd.extend(["-i", conn.key_file])
        
        cmd.append(f"{conn.user}@{conn.host}")
        
        conn.last_connected = datetime.now().isoformat()
        self._save_connections()
        
        return {
            "success": True,
            "command": " ".join(cmd),
            "message": "Use terminal to connect"
        }
    
    def execute_command(self, conn_id: str, command: str) -> Dict:
        """Execute command on remote"""
        conn = self.get_connection(conn_id)
        if not conn:
            return {"success": False, "error": "Connection not found"}
        
        cmd = ["ssh"]
        
        if conn.port != 22:
            cmd.extend(["-p", str(conn.port)])
        
        if conn.key_file:
            cmd.extend(["-i", conn.key_file])
        
        cmd.append(f"{conn.user}@{conn.host}")
")
        cmd.append(command)
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Command timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def copy_file(self, conn_id: str, local_path: str, remote_path: str, 
                  direction: str = "upload") -> Dict:
        """Copy files via SCP"""
        conn = self.get_connection(conn_id)
        if not conn:
            return {"success": False, "error": "Connection not found"}
        
        if direction == "upload":
            cmd = ["scp"]
            if conn.port != 22:
                cmd.extend(["-P", str(conn.port)])
            if conn.key_file:
                cmd.extend(["-i", conn.key_file])
            cmd.extend([local_path, f"{conn.user}@{conn.host}:{remote_path}"])
        else:
            cmd = ["scp"]
            if conn.port != 22:
                cmd.extend(["-P", str(conn.port)])
            if conn.key_file:
                cmd.extend(["-i", conn.key_file])
            cmd.extend([f"{conn.user}@{conn.host}:{remote_path}", local_path])
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


class TerminalSession:
    """Terminal session manager"""
    
    def __init__(self):
        self.sessions = {}
    
    def create_session(self, name: str = "default") -> str:
        """Create terminal session"""
        session_id = str(uuid.uuid4())[:8]
        self.sessions[session_id] = {
            "id": session_id,
            "name": name,
            "created_at": datetime.now().isoformat(),
            "history": []
        }
        return session_id
    
    def add_to_history(self, session_id: str, command: str, output: str = ""):
        """Add command to history"""
        if session_id in self.sessions:
            self.sessions[session_id]["history"].append({
                "command": command,
                "output": output,
                "timestamp": datetime.now().isoformat()
            })
    
    def get_history(self, session_id: str) -> List[Dict]:
        """Get session history"""
        if session_id in self.sessions:
            return self.sessions[session_id]["history"]
        return []


class SSHKeyManager:
    """SSH Key Management"""
    
    def __init__(self):
        self.keys_dir = os.path.join(SSH_DIR, "keys")
        os.makedirs(self.keys_dir, exist_ok=True)
    
    def generate_key(self, name: str, key_type: str = "rsa", bits: int = 4096) -> Dict:
        """Generate SSH key"""
        key_path = os.path.join(self.keys_dir, name)
        
        cmd = ["ssh-keygen", "-t", key_type, "-b", str(bits), "-f", key_path, "-N", ""]
        
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            return {
                "success": True,
                "private_key": key_path,
                "public_key": f"{key_path}.pub"
            }
        except subprocess.CalledProcessError as e:
            return {"success": False, "error": e.stderr.decode()}
    
    def list_keys(self) -> List[Dict]:
        """List SSH keys"""
        keys = []
        for f in os.listdir(self.keys_dir):
            if f.endswith(".pub"):
                name = f[:-4]
                key_path = os.path.join(self.keys_dir, f)
                with open(key_path) as fp:
                    content = fp.read().strip()
                keys.append({
                    "name": name,
                    "public_key": content,
                    "path": key_path
                })
        return keys
    
    def delete_key(self, name: str) -> Dict:
        """Delete SSH key"""
        key_path = os.path.join(self.keys_dir, name)
        pub_path = f"{key_path}.pub"
        
        try:
            if os.path.exists(key_path):
                os.remove(key_path)
            if os.path.exists(pub_path):
                os.remove(pub_path)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="NEUGI SSH Manager")
    parser.add_argument("--list", action="store_true", help="List connections")
    parser.add_argument("--add", nargs=4, metavar=("NAME", "HOST", "USER", "PORT"), help="Add connection")
    parser.add_argument("--connect", type=str, help="Connect to host")
    parser.add_argument("--exec", nargs=2, metavar=("HOST", "CMD"), help="Execute command")
    parser.add_argument("--keys", action="store_true", help="List SSH keys")
    parser.add_argument("--gen-key", type=str, metavar="NAME", help="Generate SSH key")
    
    args = parser.parse_args()
    
    manager = SSHManager()
    
    if args.list:
        connections = manager.list_connections()
        print(f"\n🔗 SSH Connections ({len(connections)}):\n")
        for c in connections:
            print(f"  {c['name']} - {c['user']}@{c['host']}:{c['port']}")
    
    elif args.add:
        name, host, user, port = args.add
        conn = manager.add_connection(name, host, user, int(port))
        print(f"Added connection: {conn.name}")
    
    elif args.connect:
        result = manager.connect(args.connect)
        print(result.get("command") or result.get("error"))
    
    elif args.exec:
        host_id, cmd = args.exec
        result = manager.execute_command(host_id, cmd)
        if result.get("success"):
            print(result.get("stdout"))
        else:
            print(f"Error: {result.get('error')}")
    
    elif args.keys:
        km = SSHKeyManager()
        keys = km.list_keys()
        print(f"\n🔑 SSH Keys ({len(keys)}):\n")
        for k in keys:
            print(f"  {k['name']}")
            print(f"    {k['public_key'][:60]}...")
    
    elif args.gen_key:
        km = SSHKeyManager()
        result = km.generate_key(args.gen_key)
        if result.get("success"):
            print(f"Generated key: {result['private_key']}")
        else:
            print(f"Error: {result.get('error')}")
    
    else:
        print("NEUGI SSH Manager")
        print("Usage: python -m neugi_ssh [--list|--add NAME HOST USER PORT|--connect ID|--exec ID CMD|--keys|--gen-key NAME]")


if __name__ == "__main__":
    main()
