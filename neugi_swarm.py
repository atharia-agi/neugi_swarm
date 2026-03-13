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
    <title>NEUGI - Neural General Intelligence</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0a0f;
            color: #e0e0e0;
            min-height: 100vh;
        }
        
        .header {
            background: linear-gradient(90deg, #1a1a2e, #16213e);
            padding: 20px 40px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #2a2a4e;
        }
        
        .logo {
            font-size: 32px;
            font-weight: 800;
            background: linear-gradient(90deg, #00d4ff, #7b2ff7);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .status {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .status-dot {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #00ff88;
            animation: pulse 2s infinite;
        }
        
        .status-dot.error {
            background: #ff4444;
            animation: none;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 40px 20px;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }
        
        .stat-card {
            background: #1a1a2e;
            border-radius: 16px;
            padding: 24px;
            border: 1px solid #2a2a4e;
        }
        
        .stat-value {
            font-size: 36px;
            font-weight: bold;
            color: #00d4ff;
        }
        
        .stat-label {
            color: #888;
            margin-top: 8px;
            font-size: 14px;
        }
        
        .section {
            background: #1a1a2e;
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 20px;
            border: 1px solid #2a2a4e;
        }
        
        .section h2 {
            font-size: 20px;
            margin-bottom: 20px;
            color: #fff;
        }
        
        .action-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
        }
        
        .action-btn {
            background: linear-gradient(135deg, #2a2a4e, #3a3a5e);
            border: 1px solid #4a4a6e;
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s;
            color: #e0e0e0;
            text-decoration: none;
            display: block;
        }
        
        .action-btn:hover {
            background: linear-gradient(135deg, #3a3a5e, #4a4a6e);
            transform: translateY(-3px);
            border-color: #00d4ff;
        }
        
        .action-icon {
            font-size: 28px;
            margin-bottom: 10px;
        }
        
        .action-title {
            font-weight: 600;
        }
        
        .issue-list {
            list-style: none;
        }
        
        .issue-item {
            background: #2a1a1a;
            border: 1px solid #4a2a2a;
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .issue-item.fixed {
            background: #1a2a1a;
            border-color: #2a4a2a;
        }
        
        .issue-text {
            color: #ff6666;
        }
        
        .fix-btn {
            background: #00aa66;
            color: #fff;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
        }
        
        .chat-box {
            background: #0f0f1a;
            border-radius: 12px;
            padding: 20px;
            height: 300px;
            overflow-y: auto;
            margin-bottom: 15px;
        }
        
        .chat-msg {
            margin-bottom: 12px;
            padding: 12px 16px;
            border-radius: 12px;
            max-width: 80%;
        }
        
        .chat-msg.user {
            background: linear-gradient(135deg, #1a3a5a, #2a4a6a);
            margin-left: auto;
        }
        
        .chat-msg.assistant {
            background: linear-gradient(135deg, #2a1a4a, #3a2a5a);
        }
        
        .chat-input {
            display: flex;
            gap: 10px;
        }
        
        .chat-input input {
            flex: 1;
            background: #1a1a2e;
            border: 1px solid #3a3a5e;
            border-radius: 8px;
            padding: 12px 16px;
            color: #e0e0e0;
            font-size: 14px;
        }
        
        .chat-input button {
            background: linear-gradient(135deg, #00d4ff, #7b2ff7);
            border: none;
            border-radius: 8px;
            padding: 12px 24px;
            color: #fff;
            font-weight: 600;
            cursor: pointer;
        }
        
        .refresh-btn {
            background: #2a2a4e;
            border: 1px solid #4a4a6e;
            border-radius: 8px;
            padding: 8px 16px;
            color: #e0e0e0;
            cursor: pointer;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">🤖 NEUGI</div>
        <div class="status">
            <div class="status-dot" id="statusDot"></div>
            <span id="statusText">Loading...</span>
        </div>
    </div>
    
    <div class="container">
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value" id="uptime">--</div>
                <div class="stat-label">Uptime</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="model">--</div>
                <div class="stat-label">Model</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="errors">0</div>
                <div class="stat-label">Errors</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">19888</div>
                <div class="stat-label">Port</div>
            </div>
        </div>
        
        <div class="section">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <h2>⚡ Quick Actions</h2>
                <button class="refresh-btn" onclick="refreshStatus()">🔄 Refresh</button>
            </div>
            <div class="action-grid">
                <a href="/chat" class="action-btn">
                    <div class="action-icon">💬</div>
                    <div class="action-title">Chat</div>
                </a>
                <a href="/technician" class="action-btn">
                    <div class="action-icon">🔧</div>
                    <div class="action-title">Technician</div>
                </a>
                <a href="/api/fix" target="_blank" class="action-btn">
                    <div class="action-icon">🩹</div>
                    <div class="action-title">Auto Fix</div>
                </a>
                <a href="/logs" class="action-btn">
                    <div class="action-icon">📋</div>
                    <div class="action-title">Logs</div>
                </a>
            </div>
        </div>
        
        <div class="section">
            <h2>🔍 System Status</h2>
            <div id="issues">
                <div style="color:#00ff88;">✅ No issues detected</div>
            </div>
        </div>
        
        <div class="section">
            <h2>💬 Quick Chat</h2>
            <div class="chat-box" id="chatBox">
                <div class="chat-msg assistant">
                    👋 Hello! I'm NEUGI. How can I help you today?
                </div>
            </div>
            <div class="chat-input">
                <input type="text" id="chatInput" placeholder="Type a message..." onkeypress="if(event.key==='Enter')sendChat()">
                <button onclick="sendChat()">Send</button>
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
                const elapsed = Math.floor((Date.now() - startTime) / 1000);
                const mins = Math.floor(elapsed / 60);
                const secs = elapsed % 60;
                document.getElementById('uptime').textContent = mins + 'm ' + secs + 's';
                
                // Update model
                const ollama = data.ollama;
                if (ollama.status === 'running') {
                    document.getElementById('model').textContent = ollama.models || 'Ready';
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
                    text.textContent = 'Issues Found';
                } else {
                    dot.className = 'status-dot';
                    text.textContent = 'Running';
                }
                
                // Show issues
                const issuesDiv = document.getElementById('issues');
                if (data.issues && data.issues.length > 0) {
                    issuesDiv.innerHTML = data.issues.map(i => 
                        '<div class="issue-item"><span class="issue-text">⚠️ ' + i + '</span></div>'
                    ).join('');
                    issuesDiv.innerHTML += '<div style="margin-top:10px"><a href="/technician" class="fix-btn" style="background:#ff6600">🔧 Open Technician</a></div>';
                } else {
                    issuesDiv.innerHTML = '<div style="color:#00ff88;">✅ No issues detected</div>';
                }
                
            } catch(e) {
                document.getElementById('statusText').textContent = 'Error';
                document.getElementById('statusDot').className = 'status-dot error';
            }
        }
        
        async function sendChat() {
            const input = document.getElementById('chatInput');
            const msg = input.value.trim();
            if (!msg) return;
            
            const box = document.getElementById('chatBox');
            box.innerHTML += '<div class="chat-msg user">' + msg + '</div>';
            box.innerHTML += '<div class="chat-msg assistant">Thinking...</div>';
            input.value = '';
            box.scrollTop = box.scrollHeight;
            
            try {
                const resp = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: msg})
                });
                const data = await resp.json();
                box.innerHTML = '<div class="chat-msg assistant">' + data.response + '</div>';
            } catch(e) {
                box.innerHTML += '<div class="chat-msg assistant">Error: Make sure NEUGI is running!</div>';
            }
        }
        
        // Auto refresh every 5 seconds
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
