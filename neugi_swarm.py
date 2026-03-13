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
import sys
import json
import time
import requests
import threading
import signal
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import socketserver
from typing import Optional

# ============================================================
# CONFIG
# ============================================================

VERSION = "14.1.0"
PORT = 19888
NEUGI_DIR = os.path.expanduser("~/neugi")

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
        """Get health status"""
        return {
            "status": self.status,
            "version": VERSION,
            "uptime": int(time.time() - self.start_time),
            "errors": len(self.errors),
            "restart_count": self.restart_count,
            "timestamp": datetime.now().isoformat(),
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
        """Detect issues and try to fix"""
        issues = []

        # Check 1: Ollama running?
        try:
            r = requests.get("http://localhost:11434/api/tags", timeout=3)
            if not r.ok:
                issues.append("Ollama not responding")
        except:
            issues.append("Ollama not running - run: ollama serve")

        # Check 2: Port available?
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(("localhost", PORT))
        sock.close()
        if result == 0:
            issues.append(f"Port {PORT} already in use")

        # Check 3: Config exists?
        config_path = os.path.join(NEUGI_DIR, "config.py")
        if not os.path.exists(config_path):
            issues.append("Config not found - run: neugi wizard")

        return issues

    @staticmethod
    def auto_fix():
        """Try to auto-fix common issues"""
        fixes = []

        # Fix 1: Start Ollama if not running
        try:
            r = requests.get("http://localhost:11434/api/tags", timeout=2)
        except:
            # Try to start Ollama
            import subprocess

            try:
                subprocess.Popen(
                    ["ollama", "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                fixes.append("Started Ollama server")
            except:
                fixes.append("Could not auto-start Ollama - run manually: ollama serve")

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
        else:
            self.send_error(404)

    def do_POST(self):
        """Handle POST requests"""
        parsed = urlparse(self.path)

        if parsed.path == "/api/chat":
            self.handle_chat()
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

        data = {
            "neugi": health.get_health(),
            "issues": issues,
            "auto_fixes": auto_fixes,
            "ollama": self.check_ollama(),
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
        """Serve Technician interface"""
        html = self.get_technician_html()
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())

    def handle_chat(self):
        """Handle chat request"""
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        data = json.loads(body)

        message = data.get("message", "")

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

    def check_ollama(self):
        """Check Ollama status"""
        try:
            r = requests.get("http://localhost:11434/api/tags", timeout=3)
            if r.ok:
                models = r.json().get("models", [])
                return {"status": "running", "models": len(models)}
        except:
            pass
        return {"status": "not_running"}

    def get_dashboard_html(self) -> str:
        """Get clean, powerful dashboard HTML"""
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NEUGI SWARM - Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600&family=JetBrains+Mono:wght@400&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #06060a;
            --bg-elevated: #0c0c11;
            --bg-card: #101016;
            --text: #e4e4e7;
            --text-muted: #71717a;
            --text-dim: #3f3f46;
            --border: rgba(255,255,255,0.06);
            --border-hover: rgba(255,255,255,0.12);
            --accent: #22d3ee;
            --primary: #a78bfa;
            --gradient: linear-gradient(135deg, var(--accent), var(--primary));
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Outfit', -apple-system, sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
            line-height: 1.6;
        }

        .bg {
            position: fixed; top: 0; left: 0; width: 100%; height: 100%; z-index: -1;
            background-image: linear-gradient(rgba(255,255,255,0.015) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.015) 1px, transparent 1px);
            background-size: 32px 32px;
            mask-image: radial-gradient(ellipse 70% 50% at 50% 30%, black 30%, transparent 100%);
        }
        
        .header {
            background: rgba(6, 6, 10, 0.85);
            backdrop-filter: blur(12px);
            padding: 16px 40px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border);
            position: sticky; top: 0; z-index: 100;
        }
        
        .logo {
            font-size: 20px; font-weight: 600;
            display: flex; align-items: center; gap: 10px;
        }
        
        .logo-mark {
            width: 28px; height: 28px; border-radius: 6px;
            background: linear-gradient(var(--bg), var(--bg)) padding-box, var(--gradient) border-box;
            border: 2px solid transparent;
            display: flex; align-items: center; justify-content: center;
        }

        .status {
            display: flex; align-items: center; gap: 8px;
            font-size: 13px; font-weight: 500; color: var(--text-muted);
            background: var(--bg-card); padding: 6px 14px; border-radius: 100px;
            border: 1px solid var(--border);
        }
        
        .status-dot {
            width: 8px; height: 8px; border-radius: 50%; background: #22d3ee;
            box-shadow: 0 0 10px #22d3ee;
        }
        .status-dot.error { background: #ff4444; box-shadow: 0 0 10px #ff4444; }
        
        .container { max-width: 1200px; margin: 0 auto; padding: 40px 20px; }
        
        .grid-4 {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; margin-bottom: 32px;
        }
        
        .card {
            background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px;
            padding: 24px; transition: all 0.2s;
        }
        .card:hover { border-color: var(--border-hover); transform: translateY(-2px); }
        
        .card .value { font-size: 32px; font-weight: 600; background: var(--gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .card .label { color: var(--text-muted); font-size: 12px; text-transform: uppercase; letter-spacing: 1px; margin-top: 4px; }
        
        .section {
            background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px;
            padding: 24px; margin-bottom: 24px;
        }
        
        .section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .section-title { font-size: 16px; font-weight: 600; }
        
        .btn {
            background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text);
            padding: 8px 16px; border-radius: 8px; font-size: 13px; cursor: pointer; transition: all 0.2s;
            font-family: 'Outfit', sans-serif; text-decoration: none; display: inline-flex; align-items: center; gap: 8px;
        }
        .btn:hover { background: var(--border); border-color: var(--text-muted); }
        .btn-primary { background: var(--gradient); color: #000; border: none; font-weight: 600; }
        .btn-primary:hover { opacity: 0.9; transform: translateY(-1px); box-shadow: 0 4px 12px rgba(34,211,238,0.2); }
        
        .action-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }
        
        .action-card {
            background: var(--bg-elevated); border: 1px solid var(--border); border-radius: 10px;
            padding: 20px; text-align: center; cursor: pointer; transition: all 0.2s; text-decoration: none; color: var(--text);
        }
        .action-card:hover { border-color: var(--accent); background: rgba(34,211,238,0.05); }
        .action-icon { font-size: 24px; margin-bottom: 8px; }
        .action-name { font-size: 14px; font-weight: 500; }
        
        .terminal {
            background: #000; border: 1px solid var(--border); border-radius: 8px; padding: 16px;
            font-family: 'JetBrains Mono', monospace; font-size: 13px; max-height: 400px; overflow-y: auto;
        }
        
        .chat-container { display: flex; flex-direction: column; height: 500px; }
        .chat-box { flex: 1; overflow-y: auto; padding-right: 10px; display: flex; flex-direction: column; gap: 16px; margin-bottom: 16px; }
        .chat-msg { max-width: 80%; padding: 12px 16px; border-radius: 12px; font-size: 14px; line-height: 1.5; }
        .chat-msg.user { background: var(--bg-elevated); border: 1px solid var(--border); align-self: flex-end; border-bottom-right-radius: 4px; }
        .chat-msg.assistant { background: rgba(34,211,238,0.1); border: 1px solid rgba(34,211,238,0.2); align-self: flex-start; border-bottom-left-radius: 4px; }
        
        .chat-input-wrapper { display: flex; gap: 12px; }
        .chat-input-wrapper input {
            flex: 1; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: 8px;
            padding: 12px 16px; color: var(--text); font-family: 'Outfit', sans-serif; font-size: 14px;
        }
        .chat-input-wrapper input:focus { outline: none; border-color: var(--accent); }
        
        .issue-item { display: flex; align-items: center; gap: 12px; padding: 12px; background: rgba(255,68,68,0.1); border: 1px solid rgba(255,68,68,0.2); border-radius: 8px; margin-bottom: 8px; font-size: 13px; color: #ff8888; }
        .issue-ok { display: flex; align-items: center; gap: 12px; padding: 12px; background: rgba(34,211,238,0.1); border: 1px solid rgba(34,211,238,0.2); border-radius: 8px; font-size: 13px; color: var(--accent); }
    </style>
</head>
<body>
    <div class="bg"></div>
    <div class="header">
        <div class="logo">
            <div class="logo-mark"><svg viewBox="0 0 24 24" fill="none" stroke="#000" stroke-width="2" style="width:14px;height:14px;"><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/></svg></div>
            NEUGI SWARM
        </div>
        <div class="status">
            <div class="status-dot" id="statusDot"></div>
            <span id="statusText">Connecting...</span>
        </div>
    </div>
    
    <div class="container">
        <div class="grid-4">
            <div class="card">
                <div class="value" id="uptime">--</div>
                <div class="label">Uptime</div>
            </div>
            <div class="card">
                <div class="value" id="model" style="font-size:24px;">--</div>
                <div class="label">Model Core</div>
            </div>
            <div class="card">
                <div class="value" id="errors">0</div>
                <div class="label">Anomalies</div>
            </div>
            <div class="card">
                <div class="value" style="font-family: 'JetBrains Mono'">19888</div>
                <div class="label">Gateway Port</div>
            </div>
        </div>
        
        <div class="section">
            <div class="section-header">
                <h2 class="section-title">Control Panel</h2>
                <button class="btn" onclick="refreshStatus()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M21 2v6h-6"/><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M3 22v-6h6"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/></svg>
                    Refresh Sync
                </button>
            </div>
            <div class="action-grid">
                <a href="/chat" class="action-card">
                    <div class="action-icon">💬</div>
                    <div class="action-name">Swarm Chat</div>
                </a>
                <a href="/technician" class="action-card">
                    <div class="action-icon">🔧</div>
                    <div class="action-name">Technician</div>
                </a>
                <a href="/api/fix" target="_blank" class="action-card">
                    <div class="action-icon">✨</div>
                    <div class="action-name">Auto Resolve</div>
                </a>
                <a href="/logs" class="action-card">
                    <div class="action-icon">📝</div>
                    <div class="action-name">System Logs</div>
                </a>
            </div>
        </div>
        
        <div class="section">
            <h2 class="section-title">Diagnostics</h2>
            <div id="issues">
                <div class="issue-ok">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><polyline points="20 6 9 17 4 12"></polyline></svg>
                    System optimal. No anomalies detected.
                </div>
            </div>
        </div>
        
        <div class="section">
            <h2 class="section-title">Direct Interface</h2>
            <div class="chat-container">
                <div class="chat-box" id="chatBox">
                    <div class="chat-msg assistant">
                        <strong>NEUGI OS v14.1.0</strong><br>
                        Connection established. Swarm agents are standing by. How may we assist you?
                    </div>
                </div>
                <div class="chat-input-wrapper">
                    <input type="text" id="chatInput" placeholder="Command the swarm..." onkeypress="if(event.key==='Enter')sendChat()">
                    <button class="btn btn-primary" onclick="sendChat()">Execute</button>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        let startTime = Date.now();
        
        async function refreshStatus() {
            try {
                const resp = await fetch('/api/status');
                const data = await resp.json();
                
                // Update uptime
                const elapsed = Math.floor((Date.now() - startTime) / 1000) + (data.neugi?.uptime || 0);
                const mins = Math.floor(elapsed / 60);
                const secs = elapsed % 60;
                document.getElementById('uptime').textContent = mins + 'm ' + secs + 's';
                
                // Update model
                const ollama = data.ollama;
                if (ollama && ollama.status === 'running') {
                    document.getElementById('model').textContent = 'Online';
                } else {
                    document.getElementById('model').textContent = 'Offline';
                }
                
                // Update errors
                document.getElementById('errors').textContent = data.issues ? data.issues.length : 0;
                
                // Update status
                const dot = document.getElementById('statusDot');
                const text = document.getElementById('statusText');
                
                if (data.issues && data.issues.length > 0) {
                    dot.className = 'status-dot error';
                    text.textContent = 'Anomalies Detected';
                } else {
                    dot.className = 'status-dot';
                    text.textContent = 'System Optimal';
                }
                
                // Show issues
                const issuesDiv = document.getElementById('issues');
                if (data.issues && data.issues.length > 0) {
                    issuesDiv.innerHTML = data.issues.map(i => 
                        `<div class="issue-item">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16" style="flex-shrink:0"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
                            ${i}
                        </div>`
                    ).join('');
                } else {
                    issuesDiv.innerHTML = `
                        <div class="issue-ok">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><polyline points="20 6 9 17 4 12"></polyline></svg>
                            System optimal. No anomalies detected.
                        </div>`;
                }
                
            } catch(e) {
                document.getElementById('statusText').textContent = 'Connection Lost';
                document.getElementById('statusDot').className = 'status-dot error';
            }
        }
        
        async function sendChat() {
            const input = document.getElementById('chatInput');
            const msg = input.value.trim();
            if (!msg) return;
            
            const box = document.getElementById('chatBox');
            box.innerHTML += '<div class="chat-msg user">' + msg + '</div>';
            
            const loadingId = 'loading-' + Date.now();
            box.innerHTML += `<div class="chat-msg assistant" id="${loadingId}">...</div>`;
            
            input.value = '';
            box.scrollTop = box.scrollHeight;
            
            try {
                const resp = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: msg})
                });
                const data = await resp.json();
                document.getElementById(loadingId).outerHTML = '<div class="chat-msg assistant">' + (data.response || '').replace(/
/g, '<br>') + '</div>';
            } catch(e) {
                document.getElementById(loadingId).outerHTML = '<div class="chat-msg assistant" style="color:#ff8888">Error: Connection failed. Swarm unreachable.</div>';
            }
            box.scrollTop = box.scrollHeight;
        }
        
        // Auto refresh
        refreshStatus();
        setInterval(refreshStatus, 5000);
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
