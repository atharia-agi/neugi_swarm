#!/usr/bin/env python3
"""
🤖 NEUGI SWARM - MAIN WITH ERROR RECOVERY
===========================================

Features:
- Auto error detection
- Auto-launch Technician on failure
- Health monitoring
- Dashboard

Version: 14.1.0
Date: March 13, 2026
"""

import os
import json
import time
import requests
import psutil
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from typing import Optional

# ============================================================
# CONFIG
# ============================================================

VERSION = "20.0.0"
PORT = 19888
NEUGI_DIR = os.path.expanduser("~/neugi")
WORKSPACE_DIR = os.path.expanduser("~/neugi/workspace")

# Ensure directories exist
os.makedirs(WORKSPACE_DIR, exist_ok=True)

# ============================================================
# HEALTH MONITOR
# ============================================================


class HealthMonitor:
    """Monitor NEUGI health and auto-recover"""

    def __init__(self):
        self.status = "starting"
        self.errors = []
        self.start_time = time.time()
        self.restart_count = 0

    def set_status(self, status: str, error: Optional[str] = None):
        """Update status"""
        self.status = status
        if error:
            self.errors.append({"time": datetime.now().isoformat(), "error": error})

    def get_health(self) -> dict:
        """Get health status with live telemetry"""
        # Get system metrics
        cpu_usage = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory()

        return {
            "status": self.status,
            "version": VERSION,
            "uptime": int(time.time() - self.start_time),
            "errors": len(self.errors),
            "restart_count": self.restart_count,
            "timestamp": datetime.now().isoformat(),
            "telemetry": {
                "cpu": cpu_usage,
                "ram": memory.percent,
                "ram_used": round(memory.used / (1024**3), 2),
                "ram_total": round(memory.total / (1024**3), 2),
                "load": os.getloadavg()[0] if hasattr(os, "getloadavg") and os.name != "nt" else 0,
            },
        }


# Global health monitor
health = HealthMonitor()

# ============================================================
# ERROR HANDLER
# ============================================================


class ErrorHandler:
    """Handle errors and auto-recover"""

    @staticmethod
    def detect_and_fix():
        """Detect issues using NEUGIWizard logic"""
        from neugi_wizard import SystemChecker

        diagnosis = SystemChecker.full_diagnosis()

        issues = []
        if not diagnosis["ollama"]["running"]:
            issues.append("Ollama not running")
        if not diagnosis["neugi"]["installed"]:
            issues.append("NEUGI configuration missing")
        if diagnosis["port_19888"]["in_use"]:
            issues.append("Port 19888 collision")

        # Add granular issues from Wizard
        issues.extend(diagnosis.get("granular_issues", []))

        return issues

    @staticmethod
    def auto_fix():
        """Trigger auto-repair via NEUGIWizard logic"""
        from neugi_wizard import Repair

        fixes = []

        # Quick fix: Ollama
        ollama = Repair.start_ollama()
        if ollama["success"]:
            fixes.append("Ollama started by Wizard")

        return fixes


# ============================================================
# DASHBOARD HANDLER
# ============================================================


class DashboardHandler(BaseHTTPRequestHandler):
    """Handle dashboard requests"""

    def do_GET(self):
        """Handle GET requests"""
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html" or path == "/dashboard":
            self.serve_dashboard()
        elif path == "/health":
            self.serve_health()
        elif path == "/api/status":
            self.serve_status()
        elif path == "/api/errors":
            self.serve_errors()
        elif path == "/api/fix":
            self.serve_fix()
        elif path == "/technician":
            self.serve_technician()
        elif path == "/api/logs":
            self.serve_logs()
        elif path == "/api/swarm/nodes":
            self.serve_swarm_nodes()
        else:
            self.send_error(404)

    def do_POST(self):
        """Handle POST requests"""
        parsed = urlparse(self.path)

        if parsed.path == "/api/chat":
            self.handle_chat()
        elif parsed.path == "/api/swarm/join":
            self.handle_swarm_join()
        elif parsed.path == "/api/swarm/delegate":
            self.handle_swarm_delegate()
        else:
            self.send_error(404)

    def serve_dashboard(self):
        """Serve dashboard"""
        html = self.get_dashboard_html()
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())

    def serve_health(self):
        """Serve health status"""
        data = health.get_health()
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def serve_status(self):
        """Serve detailed status"""
        issues = ErrorHandler.detect_and_fix()
        auto_fixes = ErrorHandler.auto_fix()

        # Gather agent and tool data
        agents_data = []
        tools_data = []
        try:
            from neugi_swarm_agents import AgentManager
            from neugi_swarm_tools import ToolManager

            am = AgentManager()
            for a in am.list():
                agents_data.append(
                    {
                        "id": a.id,
                        "name": a.name,
                        "role": a.role.value,
                        "status": a.status.value,
                        "level": a.level,
                    }
                )

            tm = ToolManager()
            for t in tm.list(enabled_only=True):
                tools_data.append({"name": t.name, "category": t.category})
        except Exception as e:
            issues.append(f"Failed to load swarm state: {e}")

        data = {
            "neugi": health.get_health(),
            "issues": issues,
            "auto_fixes": auto_fixes,
            "ollama": self.check_ollama(),
            "agents": agents_data,
            "tools": tools_data,
        }

        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def serve_errors(self):
        """Serve errors list"""
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(health.errors).encode())

    def serve_fix(self):
        """Try to fix issues"""
        fixes = ErrorHandler.auto_fix()
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"fixes": fixes}).encode())

    def serve_technician(self):
        """Serve Technician interface (Wizard Console)"""
        wizard_path = os.path.join(NEUGI_DIR, "wizard.html")
        try:
            if os.path.exists(wizard_path):
                with open(wizard_path, "r", encoding="utf-8") as f:
                    html = f.read()
            else:
                html = self.get_technician_html()  # Fallback to embedded
        except Exception:
            html = self.get_technician_html()

        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())

    def serve_logs(self):
        """Serve system logs"""
        log_path = os.path.join(NEUGI_DIR, "logs", "neugi.log")
        try:
            if os.path.exists(log_path):
                # Return last 100 lines
                with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()[-100:]
                    data = {"logs": "".join(lines), "path": log_path}
            else:
                data = {"logs": "Log file not found.", "path": log_path}
        except Exception as e:
            data = {"logs": f"Error reading logs: {e}", "path": log_path}

        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def serve_swarm_nodes(self):
        """List all peer nodes"""
        from neugi_swarm_net import swarm_net

        data = swarm_net.get_online_nodes()
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def handle_swarm_join(self):
        """Register a peer node"""
        from neugi_swarm_net import swarm_net

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        data = json.loads(body)

        node_id = data.get("node_id")
        ip = self.client_address[0]
        port = data.get("port", 19888)

        if node_id:
            swarm_net.register_node(node_id, ip, port)
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps({"status": "joined", "message": f"Node {node_id} accepted"}).encode()
            )
        else:
            self.send_error(400, "Missing node_id")

    def handle_swarm_delegate(self):
        """Receive task from peer"""
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        data = json.loads(body)

        task = data.get("task", "")

        try:
            from neugi_assistant import NeugiAssistant

            assistant = NeugiAssistant()
            response = assistant.chat(f"[REMOTE TASK] {task}")
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "executed", "response": response}).encode())
        except Exception as e:
            self.send_error(500, str(e))

    def handle_chat(self):
        """Handle chat request"""
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        data = json.loads(body)

        message = data.get("message", "")
        stream = data.get("stream", False)

        # Check if streaming requested
        if stream:
            self.handle_chat_stream(message)
            return

        try:
            from neugi_assistant import NeugiAssistant

            assistant = NeugiAssistant()
            response = assistant.chat(message)
        except Exception as e:
            response = f"NEUGI: Sorry, I am currently offline. (Error: {str(e)})"

        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"response": response}).encode())

    def handle_chat_stream(self, message: str):
        """Handle streaming chat request"""
        self.send_response(200)
        self.send_header("Content-type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        try:
            from neugi_assistant import NeugiAssistant

            assistant = NeugiAssistant()

            # Stream response
            for chunk in assistant.chat_stream(message):
                self.wfile.write(f"data: {json.dumps({'chunk': chunk})}\n\n".encode())
                self.wfile.flush()

            self.wfile.write(b"data: [DONE]\n\n")

        except Exception as e:
            self.wfile.write(f"data: {json.dumps({'error': str(e)})}\n\n".encode())

    def check_ollama(self):
        """Check Ollama status"""
        try:
            r = requests.get("http://localhost:11434/api/tags", timeout=3)
            if r.ok:
                models = r.json().get("models", [])
                return {"status": "running", "models": len(models)}
        except Exception:
            pass
        return {"status": "not_running"}

    def get_dashboard_html(self) -> str:
        """Get clean, powerful dashboard HTML"""
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NEUGI SWARM - Command Center</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #030305;
            --bg-elevated: #0a0a0f;
            --bg-card: #12121a;
            --bg-glass: rgba(18, 18, 26, 0.7);
            --text: #f0f0f5;
            --text-muted: #8b8b9e;
            --border: rgba(255,255,255,0.08);
            --border-hover: rgba(255,255,255,0.15);
            --accent: #00e5ff;
            --primary: #9d4edd;
            --danger: #ff3366;
            --warning: #ffb84d;
            --success: #00e5ff;
            --gradient: linear-gradient(135deg, var(--accent), var(--primary));
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Outfit', -apple-system, sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
            line-height: 1.6;
            overflow-x: hidden;
        }

        .bg-grid {
            position: fixed; top: 0; left: 0; width: 100%; height: 100%; z-index: -1;
            background-image: 
                linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px), 
                linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px);
            background-size: 40px 40px;
            mask-image: radial-gradient(ellipse 80% 50% at 50% 0%, black 40%, transparent 100%);
            -webkit-mask-image: radial-gradient(ellipse 80% 50% at 50% 0%, black 40%, transparent 100%);
        }
        
        .header {
            background: var(--bg-glass);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            padding: 16px 40px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border);
            position: sticky; top: 0; z-index: 100;
        }
        
        .logo {
            font-size: 22px; font-weight: 700; letter-spacing: 1px;
            display: flex; align-items: center; gap: 12px;
        }
        
        .logo-mark {
            width: 32px; height: 32px; border-radius: 8px;
            background: linear-gradient(var(--bg), var(--bg)) padding-box, var(--gradient) border-box;
            border: 2px solid transparent;
            display: flex; align-items: center; justify-content: center;
        }

        .status-pill {
            display: flex; align-items: center; gap: 10px;
            font-size: 13px; font-weight: 600; color: var(--text-muted);
            background: var(--bg-elevated); padding: 8px 16px; border-radius: 100px;
            border: 1px solid var(--border);
            text-transform: uppercase; letter-spacing: 1px;
        }
        
        .status-dot {
            width: 8px; height: 8px; border-radius: 50%; background: var(--success);
            box-shadow: 0 0 12px var(--success);
        }
        .status-dot.error { background: var(--danger); box-shadow: 0 0 12px var(--danger); }
        .status-dot.warning { background: var(--warning); box-shadow: 0 0 12px var(--warning); }
        
        /* Modal */
        .modal { display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.8);z-index:1000;align-items:center;justify-content:center; }
        .modal.active { display:flex; }
        .modal-content { background:var(--bg-card);border:1px solid var(--border);border-radius:16px;padding:24px;max-width:500px;width:90%;max-height:80vh;overflow-y:auto; }
        .modal h2 { margin-bottom:16px;font-size:20px; }
        .modal-close { float:right;background:none;border:none;color:var(--text-muted);font-size:24px;cursor:pointer; }
        .modal-btn { background:var(--primary);color:#fff;border:none;padding:10px 20px;border-radius:8px;cursor:pointer;margin:4px; }
        .modal-btn.secondary { background:var(--bg-elevated); }
        .setting-row { display:flex;justify-content:space-between;align-items:center;padding:12px 0;border-bottom:1px solid var(--border); }
        .setting-label { font-weight:500; }
        .setting-desc { font-size:12px;color:var(--text-muted); }
        
        .container { max-width: 1400px; margin: 0 auto; padding: 40px 20px; }
        
        .dashboard-layout {
            display: grid;
            grid-template-columns: 1fr 350px;
            gap: 24px;
        }
        @media (max-width: 1024px) {
            .dashboard-layout { grid-template-columns: 1fr; }
        }

        .grid-4 {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 24px;
        }
        
        .card {
            background: var(--bg-card); border: 1px solid var(--border); border-radius: 16px;
            padding: 24px; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative; overflow: hidden;
        }
        .card::before {
            content: ''; position: absolute; top: 0; left: 0; width: 100%; height: 2px;
            background: var(--gradient); opacity: 0; transition: opacity 0.3s;
        }
        .card:hover { border-color: var(--border-hover); transform: translateY(-4px); box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
        .card:hover::before { opacity: 1; }
        
        .card .value { font-size: 32px; font-weight: 700; font-family: 'JetBrains Mono', monospace; color: var(--text); }
        .card .label { color: var(--text-muted); font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; margin-top: 8px; }
        .card .icon-bg { position: absolute; right: -10px; bottom: -10px; opacity: 0.05; font-size: 80px; }
        
        .panel {
            background: var(--bg-card); border: 1px solid var(--border); border-radius: 16px;
            padding: 24px; margin-bottom: 24px;
            display: flex; flex-direction: column;
        }
        
        .panel-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding-bottom: 16px; border-bottom: 1px solid var(--border); }
        .panel-title { font-size: 18px; font-weight: 600; display: flex; align-items: center; gap: 10px; }
        .panel-title svg { stroke: var(--primary); }
        
        .btn {
            background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text);
            padding: 10px 20px; border-radius: 10px; font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.2s;
            font-family: 'Outfit', sans-serif; text-decoration: none; display: inline-flex; align-items: center; gap: 8px;
        }
        .btn:hover { background: rgba(255,255,255,0.05); border-color: var(--text-muted); }
        .btn-primary { background: var(--gradient); color: #000; border: none; }
        .btn-primary:hover { opacity: 0.9; transform: translateY(-2px); box-shadow: 0 8px 20px rgba(157, 78, 221, 0.3); }
        .btn-danger { background: rgba(255,51,102,0.1); color: var(--danger); border-color: rgba(255,51,102,0.3); }
        .btn-danger:hover { background: rgba(255,51,102,0.2); }
        
        /* Agent Graph Styles */
        .agents-grid {
            display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 16px;
        }
        .agent-node {
            background: var(--bg-elevated); border: 1px solid var(--border); border-radius: 12px;
            padding: 16px; text-align: center; position: relative; transition: all 0.3s;
        }
        .agent-node:hover { border-color: var(--accent); background: rgba(0, 229, 255, 0.05); }
        .agent-avatar {
            width: 48px; height: 48px; margin: 0 auto 12px; background: #000; border-radius: 12px;
            display: flex; align-items: center; justify-content: center; font-size: 24px;
            border: 1px solid var(--border);
        }
        .agent-name { font-size: 15px; font-weight: 600; margin-bottom: 4px; }
        .agent-role { font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px; }
        .agent-status {
            position: absolute; top: 12px; right: 12px; width: 8px; height: 8px; border-radius: 50%;
        }
        .status-idle { background: var(--text-muted); }
        .status-working { background: var(--accent); box-shadow: 0 0 10px var(--accent); animation: pulse 1.5s infinite; }
        .status-thinking { background: var(--primary); box-shadow: 0 0 10px var(--primary); animation: pulse 1s infinite; }

        @keyframes pulse { 0% { opacity: 0.4; } 50% { opacity: 1; } 100% { opacity: 0.4; } }

        /* Tools Grid */
        .tools-list { display: flex; flex-wrap: wrap; gap: 8px; }
        .tool-tag {
            background: var(--bg-elevated); border: 1px solid var(--border); border-radius: 6px;
            padding: 6px 12px; font-size: 12px; font-family: 'JetBrains Mono', monospace; color: var(--text-muted);
            display: flex; align-items: center; gap: 6px;
        }
        .tool-tag::before { content: '⚙'; font-size: 14px; }

        /* Terminal/Chat */
        .chat-container { display: flex; flex-direction: column; height: 500px; background: #000; border-radius: 12px; overflow: hidden; border: 1px solid var(--border); }
        .chat-box { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 16px; font-family: 'JetBrains Mono', monospace; font-size: 13px; }
        .chat-msg { max-width: 85%; padding: 12px 16px; border-radius: 8px; line-height: 1.6; }
        .chat-msg.user { background: rgba(255,255,255,0.05); align-self: flex-end; color: #fff; border-left: 3px solid var(--text-muted); }
        .chat-msg.assistant { background: rgba(0, 229, 255, 0.05); align-self: flex-start; color: var(--accent); border-left: 3px solid var(--accent); }
        .chat-msg.system { align-self: center; text-align: center; color: var(--text-muted); font-size: 12px; background: transparent; padding: 4px; border: none; max-width: 100%; }
        
        .chat-input-wrapper { display: flex; background: var(--bg-elevated); padding: 12px; border-top: 1px solid var(--border); }
        .chat-input-wrapper input {
            flex: 1; background: transparent; border: none;
            padding: 8px 12px; color: var(--text); font-family: 'JetBrains Mono', monospace; font-size: 14px;
        }
        .chat-input-wrapper input:focus { outline: none; }
        .chat-input-wrapper button {
            background: transparent; color: var(--primary); border: none; font-weight: 700; cursor: pointer; padding: 0 16px; text-transform: uppercase; letter-spacing: 1px;
        }
        .chat-input-wrapper button:hover { color: var(--accent); }
        
        .issue-item { display: flex; align-items: flex-start; gap: 12px; padding: 16px; background: rgba(255,51,102,0.05); border: 1px solid rgba(255,51,102,0.2); border-radius: 12px; margin-bottom: 12px; font-size: 14px; color: #ff88aa; }
        .issue-ok { display: flex; align-items: center; gap: 12px; padding: 16px; background: rgba(0,229,255,0.05); border: 1px solid rgba(0,229,255,0.2); border-radius: 12px; font-size: 14px; color: var(--accent); }
        
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.2); }
    </style>
</head>
<body>
    <div class="bg-grid"></div>
    
    <!-- Settings Modal -->
    <div class="modal" id="settingsModal">
        <div class="modal-content">
            <button class="modal-close" onclick="closeSettings()">&times;</button>
            <h2>⚙️ NEUGI Settings</h2>
            <div class="setting-row">
                <div>
                    <div class="setting-label">🛡️ Security Mode</div>
                    <div class="setting-desc">Sandbox (secure) or Full Access</div>
                </div>
                <button class="modal-btn secondary" onclick="toggleSecurity()">Configure</button>
            </div>
            <div class="setting-row">
                <div>
                    <div class="setting-label">📦 Plugins</div>
                    <div class="setting-desc">Manage plugins</div>
                </div>
                <button class="modal-btn secondary" onclick="managePlugins()">Manage</button>
            </div>
            <div class="setting-row">
                <div>
                    <div class="setting-label">🔄 Check Updates</div>
                    <div class="setting-desc">Update NEUGI to latest version</div>
                </div>
                <button class="modal-btn secondary" onclick="checkUpdates()">Check</button>
            </div>
            <div class="setting-row">
                <div>
                    <div class="setting-label">🔌 Ollama URL</div>
                    <div class="setting-desc" id="ollamaUrlDisplay">http://localhost:11434</div>
                </div>
                <input type="text" id="ollamaUrlInput" style="background:var(--bg-elevated);border:1px solid var(--border);color:var(--text);padding:8px;border-radius:6px;width:200px;" placeholder="http://localhost:11434">
            </div>
            <div style="margin-top:20px;text-align:center;">
                <button class="modal-btn" onclick="saveSettings()">Save Settings</button>
            </div>
        </div>
    </div>
    
    <!-- Wizard Help Modal -->
    <div class="modal" id="wizardModal">
        <div class="modal-content" style="max-width:600px;">
            <button class="modal-close" onclick="closeWizard()">&times;</button>
            <h2>🧠 NEUGI Wizard Help</h2>
            <p style="color:var(--text-muted);margin-bottom:16px;">Chat with NEUGI Wizard for troubleshooting!</p>
            <div class="chat-box" id="wizardChatBox" style="height:300px;overflow-y:auto;background:var(--bg-elevated);border-radius:8px;padding:12px;margin-bottom:12px;">
                <div class="chat-msg system">NEUGI Wizard v3.0 Ready</div>
                <div class="chat-msg assistant">Hi! I'm here to help. What's wrong with your NEUGI?</div>
            </div>
            <div style="display:flex;gap:8px;">
                <input type="text" id="wizardChatInput" placeholder="Describe your issue..." style="flex:1;background:var(--bg-elevated);border:1px solid var(--border);color:var(--text);padding:12px;border-radius:8px;" onkeypress="if(event.key==='Enter')sendWizardChat()">
                <button class="modal-btn" onclick="sendWizardChat()">Send</button>
            </div>
        </div>
    </div>
    <div class="header">
        <div class="logo">
            <div class="logo-mark"><svg viewBox="0 0 24 24" fill="none" stroke="#000" stroke-width="2.5" style="width:16px;height:16px;"><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/></svg></div>
            NEUGI SWARM
        </div>
        <div style="display:flex;align-items:center;gap:12px;">
            <button onclick="openSettings()" style="background:var(--bg-elevated);border:1px solid var(--border);color:var(--text);padding:8px 16px;border-radius:8px;cursor:pointer;font-size:13px;">⚙️ Settings</button>
            <button onclick="openWizard()" style="background:var(--primary);border:none;color:#fff;padding:8px 16px;border-radius:8px;cursor:pointer;font-size:13px;font-weight:600;">🧠 Wizard Help</button>
            <div class="status-pill">
                <div class="status-dot" id="statusDot"></div>
                <span id="statusText">CONNECTING...</span>
            </div>
        </div>
    </div>
    
    <div class="container">
        <div class="dashboard-layout">
            <div class="main-content">
                <div class="grid-4">
                    <div class="card">
                        <div class="icon-bg">⏱️</div>
                        <div class="value" id="uptime">00:00:00</div>
                        <div class="label">System Uptime</div>
                    </div>
                    <div class="card">
                        <div class="icon-bg">🧠</div>
                        <div class="value" id="model" style="font-size:24px; line-height: 1.3; overflow:hidden; text-overflow:ellipsis;">--</div>
                        <div class="label">Active Model Core</div>
                    </div>
                    <div class="card">
                        <div class="icon-bg">🌐</div>
                        <div class="value" id="port">19888</div>
                        <div class="label">Gateway Port</div>
                    </div>
                    <div class="card">
                        <div class="icon-bg">⚠️</div>
                        <div class="value" id="errors" style="color: var(--success)">0</div>
                        <div class="label">Anomalies Detected</div>
                    </div>
                </div>
                
                <div class="panel">
                    <div class="panel-header">
                        <h2 class="panel-title">
                            <svg viewBox="0 0 24 24" fill="none" stroke-width="2" width="20" height="20"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>
                            Swarm Architecture
                        </h2>
                        <span style="font-size: 12px; color: var(--text-muted); font-family: 'JetBrains Mono'">[ LIVE SYNC ]</span>
                    </div>
                    <div class="agents-grid" id="agentsGrid">
                        <!-- Dynamic Agents -->
                        <div class="agent-node" style="opacity:0.5"><div class="agent-avatar">📡</div><div class="agent-name">Loading...</div></div>
                    </div>
                </div>

                <div class="panel">
                    <div class="panel-header">
                        <h2 class="panel-title">
                            <svg viewBox="0 0 24 24" fill="none" stroke-width="2" width="20" height="20"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path></svg>
                            Active Integrations & Tools
                        </h2>
                    </div>
                    <div class="tools-list" id="toolsList">
                        <span class="tool-tag">Loading Modules...</span>
                    </div>
                </div>
            </div>

            <div class="side-content">
                <div class="panel" style="padding: 0; background: transparent; border: none;">
                    <div class="chat-container">
                        <div class="panel-header" style="margin:0; padding: 16px 20px; background: var(--bg-card); border-bottom: 1px solid var(--border); border-radius: 12px 12px 0 0;">
                            <h2 class="panel-title" style="font-size: 16px;">
                                <svg viewBox="0 0 24 24" fill="none" stroke-width="2" width="18" height="18"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
                                Command Terminal
                            </h2>
                        </div>
                        <div class="chat-box" id="chatBox">
                            <div class="chat-msg system">SECURE CONNECTION ESTABLISHED</div>
                            <div class="chat-msg system">NEUGI OS v14.1.0 READY</div>
                            <div class="chat-msg assistant">
                                Swarm initialized. Awaiting commander input. Type a command or ask a question.
                            </div>
                        </div>
                        <div class="chat-input-wrapper">
                            <span style="color: var(--primary); font-weight: bold; margin-right: 8px;">></span>
                            <input type="text" id="chatInput" placeholder="Execute directive..." autocomplete="off" onkeypress="if(event.key==='Enter')sendChat()">
                            <button onclick="sendChat()">SEND</button>
                        </div>
                    </div>
                </div>

                <div class="panel" style="margin-top: 24px;">
                    <div class="panel-header">
                        <h2 class="panel-title">
                            <svg viewBox="0 0 24 24" fill="none" stroke-width="2" width="20" height="20"><path d="M22 12h-4l-3 9L9 3l-3 9H2"></path></svg>
                            System Diagnostics
                        </h2>
                    </div>
                    <div id="issues">
                        <div class="issue-ok">Scanning framework...</div>
                    </div>
                    <div style="display:flex; gap: 10px; margin-top: 20px;">
                        <a href="/technician" class="btn" style="flex:1; justify-content:center;">Open Technician</a>
                        <button class="btn btn-danger" onclick="autoFix()" style="flex:1; justify-content:center;">Auto Resolve</button>
                    </div>
                </div>

                <div class="panel">
                    <div class="panel-header">
                        <h2 class="panel-title">
                            <svg viewBox="0 0 24 24" fill="none" stroke-width="2" width="20" height="20"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
                            Neural Logs
                        </h2>
                        <button class="btn" onclick="refreshLogs()" style="padding: 4px 8px; font-size: 10px;">Refresh</button>
                    </div>
                    <div id="logViewer" style="height: 200px; background: #000; border-radius: 8px; padding: 12px; font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--text-muted); overflow-y: auto; border: 1px solid var(--border);">
                        Initializing log link...
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        let startTimestamp = Date.now();
        let serverUptimeOffset = 0;
        
        function formatTime(seconds) {
            const h = Math.floor(seconds / 3600).toString().padStart(2, '0');
            const m = Math.floor((seconds % 3600) / 60).toString().padStart(2, '0');
            const s = (seconds % 60).toString().padStart(2, '0');
            return `${h}:${m}:${s}`;
        }

        const agentEmojis = {
            'researcher': '🔍', 'coder': '💻', 'creator': '🎨', 'analyst': '📊',
            'strategist': '♟️', 'security': '🛡️', 'social': '🌐', 'writer': '✍️', 'manager': '👑'
        };

        async function refreshStatus() {
            try {
                const resp = await fetch('/api/status');
                const data = await resp.json();
                
                // Uptime Logic
                if (serverUptimeOffset === 0 && data.neugi) {
                    serverUptimeOffset = data.neugi.uptime - Math.floor((Date.now() - startTimestamp) / 1000);
                }
                const currentUptime = Math.floor((Date.now() - startTimestamp) / 1000) + serverUptimeOffset;
                document.getElementById('uptime').textContent = formatTime(currentUptime);
                
                // Model & Provider
                let modelName = 'Offline';
                if (data.ollama && data.ollama.status === 'running') {
                    modelName = 'Ollama Engine (' + data.ollama.models + ' models)';
                }
                document.getElementById('model').textContent = modelName;
                
                // Errors
                const errCount = data.issues ? data.issues.length : 0;
                const errEl = document.getElementById('errors');
                errEl.textContent = errCount;
                errEl.style.color = errCount > 0 ? 'var(--danger)' : 'var(--success)';
                
                // Header Status
                const dot = document.getElementById('statusDot');
                const text = document.getElementById('statusText');
                
                if (errCount > 0) {
                    dot.className = 'status-dot error';
                    text.textContent = 'SYSTEM ANOMALY';
                } else {
                    dot.className = 'status-dot';
                    text.textContent = 'SYSTEM OPTIMAL';
                }
                
                // Diagnostics Render
                const issuesDiv = document.getElementById('issues');
                if (errCount > 0) {
                    issuesDiv.innerHTML = data.issues.map(i => 
                        `<div class="issue-item">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18" style="flex-shrink:0; margin-top:2px;"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
                            <div>${i}</div>
                        </div>`
                    ).join('');
                } else {
                    issuesDiv.innerHTML = `
                        <div class="issue-ok">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><polyline points="20 6 9 17 4 12"></polyline></svg>
                            Core integrity at 100%. No anomalies detected.
                        </div>`;
                }

                // Render Agents
                if (data.agents && data.agents.length > 0) {
                    const grid = document.getElementById('agentsGrid');
                    grid.innerHTML = data.agents.map(a => {
                        const statusClass = 'status-' + a.status;
                        const icon = agentEmojis[a.role] || '🤖';
                        return `
                        <div class="agent-node">
                            <div class="agent-status ${statusClass}" title="${a.status}"></div>
                            <div class="agent-avatar">${icon}</div>
                            <div class="agent-name">${a.name}</div>
                            <div class="agent-role">${a.role} LVL.${a.level}</div>
                        </div>`;
                    }).join('');
                }

                // Render Tools
                if (data.tools && data.tools.length > 0) {
                    const tList = document.getElementById('toolsList');
                    tList.innerHTML = data.tools.map(t => `<span class="tool-tag">${t.name}</span>`).join('');
                }
                
                // Refresh logs too
                refreshLogs();
                
            } catch(e) {
                document.getElementById('statusText').textContent = 'CONNECTION LOST';
                document.getElementById('statusDot').className = 'status-dot error';
            }
        }

        async function refreshLogs() {
            try {
                const resp = await fetch('/api/logs');
                const data = await resp.json();
                const logEl = document.getElementById('logViewer');
                if (data.logs) {
                    logEl.textContent = data.logs;
                    logEl.scrollTop = logEl.scrollHeight;
                }
            } catch(e) { console.error("Log sync failed"); }
        }

        async function autoFix() {
            try {
                await fetch('/api/fix');
                refreshStatus();
            } catch(e) {
                console.error(e);
            }
        }
        
        async function sendChat() {
            const input = document.getElementById('chatInput');
            const msg = input.value.trim();
            if (!msg) return;
            
            const box = document.getElementById('chatBox');
            box.innerHTML += `<div class="chat-msg user">${msg}</div>`;
            
            const loadingId = 'loading-' + Date.now();
            box.innerHTML += `<div class="chat-msg assistant" id="${loadingId}">[Processing directive...]</div>`;
            
            input.value = '';
            box.scrollTop = box.scrollHeight;
            
            try {
                // Use streaming!
                const resp = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: msg, stream: true})
                });
                
                const reader = resp.body.getReader();
                const decoder = new TextDecoder();
                let assistantMessage = '';
                
                // Replace loading with streaming message
                const loadingEl = document.getElementById(loadingId);
                loadingEl.outerHTML = '<div class="chat-msg assistant" id="streaming-msg"></div>';
                const msgEl = document.getElementById('streaming-msg');
                
                while (true) {
                    const {done, value} = await reader.read();
                    if (done) break;
                    
                    const text = decoder.decode(value);
                    const lines = text.split('\\n');
                    
                    for (const line of lines) {
                        if (line.startsWith('data: ')) {
                            const data = line.slice(6);
                            if (data === '[DONE]') continue;
                            try {
                                const parsed = JSON.parse(data);
                                if (parsed.chunk) {
                                    assistantMessage += parsed.chunk;
                                    msgEl.innerHTML = assistantMessage.replace(/\\n/g, '<br>');
                                    box.scrollTop = box.scrollHeight;
                                }
                            } catch(e) {}
                        }
                    }
                }
            } catch(e) {
                document.getElementById(loadingId).outerHTML = '<div class="chat-msg assistant" style="color:var(--danger)">Error: Comm link severed.</div>';
            }
            box.scrollTop = box.scrollHeight;
        }
        
        // Auto refresh setup
        refreshStatus();
        setInterval(refreshStatus, 3000);
        
        // Clock tick
        setInterval(() => {
            const currentUptime = Math.floor((Date.now() - startTimestamp) / 1000) + serverUptimeOffset;
            document.getElementById('uptime').textContent = formatTime(currentUptime);
        }, 1000);
        
        // Settings Modal
        function openSettings() {
            document.getElementById('settingsModal').classList.add('active');
        }
        
        function closeSettings() {
            document.getElementById('settingsModal').classList.remove('active');
        }
        
        function saveSettings() {
            const url = document.getElementById('ollamaUrlInput').value;
            if (url) {
                localStorage.setItem('neugi_ollama_url', url);
                alert('Settings saved! Some changes may require restart.');
            }
            closeSettings();
        }
        
        function toggleSecurity() {
            alert('To configure security, run: python3 neugi_security.py\n\nOr use the Wizard: python3 neugi_wizard.py → Security Settings');
        }
        
        function managePlugins() {
            alert('Plugin manager: python3 neugi_plugins.py list\n\nOr use the Wizard: python3 neugi_wizard.py → Manage Plugins');
        }
        
        function checkUpdates() {
            alert('Checking for updates...\n\nRun: python3 neugi_updater.py check\n\nOr use the Wizard: python3 neugi_wizard.py → Check for Updates');
        }
        
        // Wizard Help Modal
        function openWizard() {
            document.getElementById('wizardModal').classList.add('active');
        }
        
        function closeWizard() {
            document.getElementById('wizardModal').classList.remove('active');
        }
        
        function sendWizardChat() {
            const input = document.getElementById('wizardChatInput');
            const msg = input.value.trim();
            if (!msg) return;
            
            const box = document.getElementById('wizardChatBox');
            box.innerHTML += '<div class="chat-msg user">' + msg + '</div>';
            box.innerHTML += '<div class="chat-msg assistant" id="wizardLoading">[Thinking...]</div>';
            box.scrollTop = box.scrollHeight;
            input.value = '';
            
            // Send to API
            fetch('/api/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({message: "Help: " + msg})
            })
            .then(r => r.json())
            .then(data => {
                document.getElementById('wizardLoading').outerHTML = '<div class="chat-msg assistant">' + (data.response || 'No response').replace(/\n/g, '<br>') + '</div>';
                box.scrollTop = box.scrollHeight;
            })
            .catch(e => {
                document.getElementById('wizardLoading').outerHTML = '<div class="chat-msg assistant" style="color:var(--danger)">Error connecting to NEUGI</div>';
            });
        }
    </script>
</body>
</html>"""

    def get_technician_html(self) -> str:
        """Get Technician interface HTML"""
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NEUGI Technician - System Doctor</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0a0f;
            color: #e0e0e0;
            min-height: 100vh;
        }
        
        .header {
            background: linear-gradient(90deg, #ff6600, #ff9900);
            padding: 20px 40px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .logo {
            font-size: 28px;
            font-weight: bold;
            color: #fff;
        }
        
        .container {
            max-width: 1000px;
            margin: 0 auto;
            padding: 40px 20px;
        }
        
        .section {
            background: #1a1a2e;
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 20px;
            border: 1px solid #2a2a4e;
        }
        
        h2 { margin-bottom: 20px; font-size: 20px; }
        
        .diagnose-btn {
            background: linear-gradient(135deg, #ff6600, #ff9900);
            border: none;
            border-radius: 12px;
            padding: 20px 40px;
            color: #fff;
            font-size: 18px;
            font-weight: bold;
            cursor: pointer;
            width: 100%;
            margin-bottom: 20px;
        }
        
        .diagnose-btn:hover {
            transform: scale(1.02);
        }
        
        .result-box {
            background: #0f0f1a;
            border-radius: 12px;
            padding: 20px;
            font-family: monospace;
            white-space: pre-wrap;
            max-height: 400px;
            overflow-y: auto;
        }
        
        .fix-btn {
            background: #00aa66;
            color: #fff;
            border: none;
            border-radius: 8px;
            padding: 12px 24px;
            font-size: 14px;
            cursor: pointer;
            margin-top: 15px;
        }
        
        .fix-btn:hover { background: #00cc77; }
        
        .status-ok { color: #00ff88; }
        .status-error { color: #ff4444; }
        .status-warn { color: #ffaa00; }
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">🔧 NEUGI Technician</div>
    </div>
    
    <div class="container">
        <div class="section">
            <h2>🩺 System Doctor</h2>
            <button class="diagnose-btn" onclick="runDiagnosis()">
                🔍 Run Full Diagnosis
            </button>
            
            <div class="result-box" id="result">
                Click "Run Full Diagnosis" to check system health...
            </div>
            
            <button class="fix-btn" onclick="autoFix()">
                🩹 Auto Fix Issues
            </button>
        </div>
        
        <div class="section">
            <h2>⚡ Quick Fixes</h2>
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:15px;">
                <button class="fix-btn" onclick="fix('ollama')" style="background:#2a4a6a">
                    Start Ollama
                </button>
                <button class="fix-btn" onclick="fix('restart')" style="background:#4a2a6a">
                    Restart NEUGI
                </button>
                <button class="fix-btn" onclick="fix('config')" style="background:#4a4a2a">
                    Reset Config
                </button>
                <button class="fix-btn" onclick="fix('clear')" style="background:#6a2a2a">
                    Clear Logs
                </button>
            </div>
        </div>
    </div>
    
    <script>
        async function runDiagnosis() {
            const result = document.getElementById('result');
            result.textContent = '🔄 Running diagnosis...';
            
            try {
                const resp = await fetch('/api/status');
                const data = await resp.json();
                
                let output = '═══ DIAGNOSIS RESULTS ═══\\n\\n';
                output += 'NEUGI Status: ' + (data.neugi?.status || 'unknown') + '\\n';
                output += 'Uptime: ' + (data.neugi?.uptime || 0) + 's\\n';
                output += 'Errors: ' + (data.neugi?.errors || 0) + '\\n\\n';
                
                output += '━━━ OLLAMA STATUS ━━━\\n';
                output += 'Status: ' + (data.ollama?.status || 'unknown') + '\\n';
                output += 'Models: ' + (data.ollama?.models || 0) + '\\n\\n';
                
                output += '━━━ ISSUES FOUND ━━━\\n';
                if (data.issues && data.issues.length > 0) {
                    data.issues.forEach((issue, i) => {
                        output += (i+1) + '. ' + issue + '\\n';
                    });
                } else {
                    output += '✅ No issues found!\\n';
                }
                
                result.textContent = output;
                
            } catch(e) {
                result.textContent = '❌ Error running diagnosis: ' + e.message;
            }
        }
        
        async function autoFix() {
            const result = document.getElementById('result');
            result.textContent = '🔄 Attempting auto-fix...';
            
            try {
                const resp = await fetch('/api/fix');
                const data = await resp.json();
                
                let output = '═══ AUTO FIX RESULTS ═══\\n\\n';
                if (data.fixes && data.fixes.length > 0) {
                    data.fixes.forEach(fix => {
                        output += '✅ ' + fix + '\\n';
                    });
                } {
                    output += '⚠️ Could not auto-fix. Try manual fixes above.';
                }
                
                result.textContent = output;
                
            } catch(e) {
                result.textContent = '❌ Error: ' + e.message;
            }
        }
        
        async function fix(type) {
            const result = document.getElementById('result');
            result.textContent = '🔧 Running: ' + type + '...';
            
            // For now, just show message
            setTimeout(() => {
                result.textContent = '✅ Command sent: ' + type + '\\n\\nRefresh to see results.';
            }, 1000);
        }
    </script>
</body>
</html>"""


# ============================================================
# MAIN SERVER
# ============================================================


def start_server():
    """Start NEUGI server"""
    health.set_status("running")

    print(f"""
╔═══════════════════════════════════════════════════╗
║         🚀 NEUGI SWARM v{VERSION}                 ║
║         Neural General Intelligence              ║
╚═══════════════════════════════════════════════════╝

📖 Dashboard: http://localhost:{PORT}
🔧 Technician: http://localhost:{PORT}/technician
📋 Health: http://localhost:{PORT}/health

Press Ctrl+C to stop
""")

    # Try to start server
    try:
        server = HTTPServer(("0.0.0.0", PORT), DashboardHandler)
        server.serve_forever()
    except Exception as e:
        health.set_status("error", str(e))
        print(f"❌ Error: {e}")

        # Auto-open Technician
        print("\n🔧 Opening Technician...")
        import webbrowser

        webbrowser.open(f"http://localhost:{PORT}/technician")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    # Check for errors first
    print("🔍 Checking system...")
    issues = ErrorHandler.detect_and_fix()

    if issues:
        print("\n⚠️ Issues detected:")
        for issue in issues:
            print(f"   - {issue}")

        print("\n🔧 Opening Technician for fixes...")
        import webbrowser

        webbrowser.open(f"http://localhost:{PORT}/technician")

    # Start server
    start_server()
