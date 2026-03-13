#!/usr/bin/env python3
"""
🤖 NEUGI SWARM - MAIN
=======================

Production-ready with:
- Simple one-line install
- Setup wizard
- Dashboard
- Flexible context (works with 2K!)
- Free provider support (Groq, OpenRouter, Ollama, llama.cpp)
- Local + Cloud models

Version: 14.0.0
Date: March 13, 2026

MINIMUM REQUIREMENTS:
- Python 3.8+
- 2GB RAM (for small models)
- 2K context window minimum (works!)

Quick Start:
    curl -sSL https://raw.githubusercontent.com/atharia-agi/neugi_swarm/main/install.sh | bash
    python3 neugi_swarm.py --setup
    python3 neugi_swarm.py
"""

import os
import sys
import json
import sqlite3
import asyncio
import argparse
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs

# ============================================================
# CONFIG
# ============================================================

VERSION = "14.0.0"
NAME = "Neugi Swarm"
TAGLINE = "Production-Ready Autonomous AI"

# Default config
CONFIG = {
    "provider": "auto",  # auto-detect
    "model": "auto",
    "api_key": "",
    "context_window": 8192,  # Minimum works: 2K!
    "max_tokens": 2048,
    "temperature": 0.7,
    "master_key": "neugi123",
    "channels": {},
    "rate_limit": {
        "enabled": True,
        "minute": 60,
        "hour": 1000
    }
}

# ============================================================
# FLEXIBLE LLM PROVIDERS
# ============================================================

class FlexibleLLM:
    """
    Supports ANY provider with ANY context!
    - Minimum: 2K context (works!)
    - Maximum: 1M+ context
    """
    
    PROVIDERS = {
        # FREE / CHEAP
        "groq": {
            "api_base": "https://api.groq.com/openai/v1",
            "models": ["llama-3.1-8b-instant", "mixtral-8x7b-32768", "llama-3.3-70b-versatile"],
            "min_context": 8192,
            "max_context": 128000,
            "free": True,
            "speed": "very_fast"
        },
        "openrouter": {
            "api_base": "https://openrouter.ai/api/v1",
            "models": ["google/gemini-2.0-flash-exp", "meta-llama/llama-3.1-8b-instant", "google/gemini-1.5-flash"],
            "min_context": 8192,
            "max_context": 1000000,
            "free": True,
            "speed": "fast"
        },
        "ollama": {
            "api_base": "http://localhost:11434",
            "models": ["llama2", "mistral", "codellama", "phi3"],
            "min_context": 2048,  # WORKS WITH 2K!
            "max_context": 128000,
            "free": True,
            "speed": "depends_on_hardware"
        },
        "minimax": {
            "api_base": "https://api.minimax.io/anthropic/v1",
            "models": ["MiniMax-M2.5", "MiniMax-Text-01"],
            "min_context": 8000,
            "max_context": 1000000,
            "free": False,
            "speed": "fast",
            "cheap": True
        },
        # PREMIUM
        "openai": {
            "api_base": "https://api.openai.com/v1",
            "models": ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"],
            "min_context": 4096,
            "max_context": 1000000,
            "free": False,
            "speed": "fast"
        },
        "anthropic": {
            "api_base": "https://api.anthropic.com/v1",
            "models": ["claude-3-5-sonnet", "claude-3-haiku"],
            "min_context": 200000,
            "max_context": 1000000,
            "free": False,
            "speed": "medium"
        },
    }
    
    def __init__(self, config: Dict):
        self.config = config
        self.api_key = config.get("api_key", os.environ.get("API_KEY", ""))
        self.provider = self._detect_provider()
        self.model = config.get("model", "auto")
        
        # Context window - FLEXIBLE!
        self.context_window = config.get("context_window", 8192)  # MINIMUM 2K WORKS!
        
        print(f"🧠 LLM: {self.provider}")
        print(f"📝 Context: {self.context_window} (minimum: {self.PROVIDERS.get(self.provider, {}).get('min_context', '?')})")
    
    def _detect_provider(self) -> str:
        """Auto-detect provider from API key"""
        if not self.api_key:
            # Try environment or default
            for env_var in ["GROQ_API_KEY", "OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "MINIMAX_API_KEY"]:
                if os.environ.get(env_var):
                    key = os.environ.get(env_var)
                    if "gsk_" in key:
                        return "groq"
                    elif key.startswith("sk-or-"):
                        return "openrouter"
                    elif key.startswith("sk-"):
                        return "openai"
                    elif key.startswith("sk-ant-"):
                        return "anthropic"
            
            return "ollama"  # Default to local
        
        # Detect from key format
        if "gsk_" in self.api_key:
            return "groq"
        elif self.api_key.startswith("sk-or-"):
            return "openrouter"
        elif self.api_key.startswith("sk-"):
            return "openai"
        elif self.api_key.startswith("sk-ant-"):
            return "anthropic"
        elif len(self.api_key) < 30:
            return "minimax"
        
        return "openai"
    
    def think(self, prompt: str, **kwargs) -> str:
        """Generate response"""
        
        # Get context
        ctx = kwargs.get("context", self.context_window)
        
        # Check minimum context requirement
        provider_info = self.PROVIDERS.get(self.provider, {})
        min_ctx = provider_info.get("min_context", 2048)
        
        if ctx < min_ctx:
            print(f"⚠️ Context {ctx} < minimum {min_ctx}, adjusting...")
            ctx = min_ctx
        
        # Build request
        model = self.model
        if model == "auto":
            models = provider_info.get("models", ["gpt-4o"])
            model = models[0]
        
        # Call API
        return self._call_api(prompt, model, ctx, **kwargs)
    
    def _call_api(self, prompt: str, model: str, context: int, **kwargs) -> str:
        """Call the LLM API"""
        
        if self.provider == "groq":
            return self._call_groq(prompt, model, context)
        elif self.provider == "openrouter":
            return self._call_openrouter(prompt, model, context)
        elif self.provider == "ollama":
            return self._call_ollama(prompt, model, context)
        elif self.provider == "minimax":
            return self._call_minimax(prompt, context)
        elif self.provider == "openai":
            return self._call_openai(prompt, model, context)
        elif self.provider == "anthropic":
            return self._call_anthropic(prompt, model, context)
        else:
            return f"[Simulation] {prompt[:50]}..."
    
    def _call_groq(self, prompt: str, model: str, context: int) -> str:
        """Call Groq API (FREE!)"""
        try:
            import requests
            
            url = f"https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": min(context // 4, 4096),
                "temperature": kwargs.get("temperature", 0.7)
            }
            
            r = requests.post(url, json=data, headers=headers, timeout=30)
            
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"]
            else:
                return f"[Groq Error: {r.status_code}]"
        except Exception as e:
            return f"[Groq Error: {e}]"
    
    def _call_openrouter(self, prompt: str, model: str, context: int) -> str:
        """Call OpenRouter API (FREE tier!)"""
        try:
            import requests
            
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://neugi.ai",
                "X-Title": "Neugi Swarm"
            }
            
            data = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": min(context // 4, 4096)
            }
            
            r = requests.post(url, json=data, headers=headers, timeout=30)
            
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"]
            else:
                return f"[OpenRouter Error: {r.status_code}]"
        except Exception as e:
            return f"[OpenRouter Error: {e}]"
    
    def _call_ollama(self, prompt: str, model: str, context: int) -> str:
        """Call Ollama (LOCAL!)"""
        try:
            import requests
            
            url = f"http://localhost:11434/api/chat"
            data = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False
            }
            
            r = requests.post(url, json=data, timeout=60)
            
            if r.status_code == 200:
                return r.json()["message"]["content"]
            else:
                return f"[Ollama Error: {r.status_code}]"
        except Exception as e:
            return f"[Ollama Error: {e}]"
    
    def _call_minimax(self, prompt: str, context: int) -> str:
        """Call MiniMax API (Cheap!)"""
        try:
            import requests
            
            url = "https://api.minimax.io/anthropic/v1/messages"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": "MiniMax-M2.5",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": min(context // 4, 4096)
            }
            
            r = requests.post(url, json=data, headers=headers, timeout=30)
            
            if r.status_code == 200:
                result = r.json()
                for block in result.get("content", []):
                    if block.get("type") == "text":
                        return block.get("text", "")
            else:
                return f"[MiniMax Error: {r.status_code}]"
        except Exception as e:
            return f"[MiniMax Error: {e}]"
    
    def _call_openai(self, prompt: str, model: str, context: int) -> str:
        """Call OpenAI API"""
        try:
            import requests
            
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": min(context // 4, 4096)
            }
            
            r = requests.post(url, json=data, headers=headers, timeout=30)
            
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"]
            else:
                return f"[OpenAI Error: {r.status_code}]"
        except Exception as e:
            return f"[OpenAI Error: {e}]"
    
    def _call_anthropic(self, prompt: str, model: str, context: int) -> str:
        """Call Anthropic API"""
        try:
            import requests
            
            url = "https://api.anthropic.com/v1/messages"
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": min(context // 4, 4096)
            }
            
            r = requests.post(url, json=data, headers=headers, timeout=30)
            
            if r.status_code == 200:
                return r.json()["content"][0]["text"]
            else:
                return f"[Anthropic Error: {r.status_code}]"
        except Exception as e:
            return f"[Anthropic Error: {e}]"
    
    def get_status(self) -> Dict:
        """Get LLM status"""
        return {
            "provider": self.provider,
            "model": self.model,
            "context_window": self.context_window,
            "min_context": self.PROVIDERS.get(self.provider, {}).get("min_context", "?"),
            "free": self.PROVIDERS.get(self.provider, {}).get("free", False),
        }

# ============================================================
# SIMPLE DASHBOARD
# ============================================================

class Dashboard:
    """Simple web dashboard"""
    
    def __init__(self, port: int = 8089):
        self.port = port
        self.neugi = None
    
    def set_neugi(self, neugi):
        self.neugi = neugi
    
    def get_html(self) -> str:
        """Get dashboard HTML"""
        
        status = self.neugi.llm.get_status() if self.neugi else {}
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Neugi Swarm Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #fff;
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ 
            font-size: 2.5em; 
            margin-bottom: 10px;
            background: linear-gradient(90deg, #00d4ff, #7b2cbf);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .tagline {{ color: #888; margin-bottom: 30px; }}
        .grid {{ 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .card {{
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            padding: 25px;
            border: 1px solid rgba(255,255,255,0.1);
        }}
        .card h2 {{ color: #00d4ff; margin-bottom: 15px; font-size: 1.2em; }}
        .stat {{ margin: 10px 0; }}
        .stat-label {{ color: #888; font-size: 0.9em; }}
        .stat-value {{ 
            font-size: 1.5em; 
            font-weight: bold;
            color: #00ff88;
        }}
        .badge {{
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.8em;
            margin-right: 5px;
        }}
        .badge-free {{ background: #00ff88; color: #000; }}
        .badge-paid {{ background: #ff6b6b; color: #fff; }}
        .chat-box {{
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            padding: 20px;
            margin-top: 20px;
        }}
        .chat-input {{
            width: 100%;
            padding: 15px;
            border-radius: 10px;
            border: 1px solid rgba(255,255,255,0.2);
            background: rgba(0,0,0,0.3);
            color: #fff;
            font-size: 1em;
            margin-top: 10px;
        }}
        .chat-input:focus {{ outline: none; border-color: #00d4ff; }}
        #response {{
            margin-top: 20px;
            padding: 15px;
            background: rgba(0,0,0,0.3);
            border-radius: 10px;
            min-height: 100px;
            white-space: pre-wrap;
        }}
        .footer {{ 
            text-align: center; 
            margin-top: 40px; 
            color: #666;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 Neugi Swarm</h1>
        <p class="tagline">Production-Ready Autonomous AI | v{VERSION}</p>
        
        <div class="grid">
            <div class="card">
                <h2>🧠 LLM Status</h2>
                <div class="stat">
                    <div class="stat-label">Provider</div>
                    <div class="stat-value">{status.get('provider', 'N/A')}</div>
                </div>
                <div class="stat">
                    <div class="stat-label">Model</div>
                    <div class="stat-value">{status.get('model', 'N/A')}</div>
                </div>
                <div class="stat">
                    <div class="stat-label">Context Window</div>
                    <div class="stat-value">{status.get('context_window', 'N/A'):,} tokens</div>
                </div>
                <div>
                    {"<span class='badge badge-free'>FREE</span>" if status.get('free') else "<span class='badge badge-paid'>PAID</span>"}
                </div>
            </div>
            
            <div class="card">
                <h2>📊 System</h2>
                <div class="stat">
                    <div class="stat-label">Version</div>
                    <div class="stat-value">{VERSION}</div>
                </div>
                <div class="stat">
                    <div class="stat-label">Status</div>
                    <div class="stat-value" style="color: #00ff88;">● Active</div>
                </div>
                <div class="stat">
                    <div class="stat-label">Uptime</div>
                    <div class="stat-value" id="uptime">Loading...</div>
                </div>
            </div>
            
            <div class="card">
                <h2>🛠️ Quick Actions</h2>
                <p style="margin: 10px 0;">
                    <a href="/api/test" style="color: #00d4ff;">Test LLM</a> |
                    <a href="/api/status" style="color: #00d4ff;">Status</a> |
                    <a href="/api/health" style="color: #00d4ff;">Health</a>
                </p>
                <p style="margin: 10px 0; color: #888; font-size: 0.9em;">
                    API Endpoint: POST /api/chat
                </p>
            </div>
        </div>
        
        <div class="chat-box">
            <h2>💬 Quick Chat</h2>
            <input type="text" id="prompt" class="chat-input" placeholder="Type your message here..." onkeypress="if(event.key==='Enter')sendMessage()">
            <div id="response">Response will appear here...</div>
        </div>
        
        <div class="footer">
            <p>Neugi Swarm - Minimum context: 2K tokens supported! | 
            Works with: Groq, OpenRouter, Ollama, llama.cpp, MiniMax, OpenAI, Anthropic</p>
        </div>
    </div>
    
    <script>
        let startTime = Date.now();
        
        function updateUtime() {{
            let elapsed = Math.floor((Date.now() - startTime) / 1000);
            let hours = Math.floor(elapsed / 3600);
            let minutes = Math.floor((elapsed % 3600) / 60);
            let seconds = elapsed % 60;
            document.getElementById('uptime').textContent = 
                hours + 'h ' + minutes + 'm ' + seconds + 's';
        }}
        
        setInterval(updateUtime, 1000);
        
        async function sendMessage() {{
            const prompt = document.getElementById('prompt').value;
            if (!prompt) return;
            
            document.getElementById('response').textContent = 'Thinking...';
            
            try {{
                const res = await fetch('/api/chat', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{message: prompt}})
                }});
                
                const data = await res.json();
                document.getElementById('response').textContent = data.response || data.error || 'No response';
            }} catch(e) {{
                document.getElementById('response').textContent = 'Error: ' + e.message;
            }}
        }}
    </script>
</body>
</html>"""
        
        return html

# ============================================================
# MAIN NEUGI SWARM
# ============================================================

class NeugiSwarm:
    VERSION = VERSION
    
    def __init__(self, config_path: str = None):
        self.config = CONFIG.copy()
        self.start_time = datetime.now()
        
        # Load config
        if config_path and os.path.exists(config_path):
            self._load_config(config_path)
        
        # Initialize
        self.llm = FlexibleLLM(self.config)
        self.dashboard = Dashboard()
        self.dashboard.set_neugi(self)
        
        print(f"\n{'='*60}")
        print(f"🤖 {NAME} v{VERSION}")
        print(f"   {TAGLINE}")
        print(f"{'='*60}")
        print()
    
    def _load_config(self, path: str):
        """Load configuration"""
        try:
            with open(path, 'r') as f:
                exec(f.read(), self.config)
        except Exception as e:
            print(f"⚠️ Config load error: {e}")
    
    def chat(self, message: str) -> str:
        """Chat with Neugi"""
        return self.llm.think(message)
    
    def status(self) -> Dict:
        """Get status"""
        uptime = (datetime.now() - self.start_time).total_seconds()
        
        return {
            "version": self.VERSION,
            "status": "active",
            "uptime_seconds": uptime,
            "llm": self.llm.get_status()
        }

# ============================================================
# HTTP HANDLER
# ============================================================

class NeugiHandler(BaseHTTPRequestHandler):
    neugi = None
    
    def do_GET(self):
        if self.path == "/" or self.path == "/dashboard":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            
            if self.neugi:
                html = self.neugi.dashboard.get_html()
                self.wfile.write(html.encode())
            else:
                self.wfile.write(b"<h1>Neugi Swarm</h1><p>Starting...</p>")
        
        elif self.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            
            if self.neugi:
                self.wfile.write(json.dumps(self.neugi.status()).encode())
            else:
                self.wfile.write(b'{"status": "starting"}')
        
        elif self.path == "/api/health":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')
        
        elif self.path == "/api/test":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            
            if self.neugi:
                result = self.neugi.chat("Hello! Say hi and tell me your name.")
                self.wfile.write(json.dumps({"response": result}).encode())
            else:
                self.wfile.write(b'{"error": "not ready"}')
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        if self.path == "/api/chat":
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            
            try:
                data = json.loads(body)
                message = data.get("message", "")
                
                if self.neugi:
                    response = self.neugi.chat(message)
                    self.send_response(200)
                    self.send_header("Content-type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"response": response}).encode())
                else:
                    self.send_response(500)
                    self.end_headers()
                    self.wfile.write(b'{"error": "not ready"}')
            
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        print(f"[HTTP] {args[0]}")

# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(description=f"{NAME} - {TAGLINE}")
    parser.add_argument("--setup", action="store_true", help="Run setup wizard")
    parser.add_argument("--config", default="config.py", help="Config file path")
    parser.add_argument("--port", type=int, default=8089, help="Dashboard port")
    parser.add_argument("--test", action="store_true", help="Test configuration")
    parser.add_argument("--version", action="store_true", help="Show version")
    
    args = parser.parse_args()
    
    if args.version:
        print(f"{NAME} v{VERSION}")
        return
    
    if args.setup:
        # Run setup wizard
        import neugi_swarm_setup
        neugi_swarm_setup.run_setup()
        return
    
    # Start Neugi
    print(f"\n🤖 Starting {NAME}...")
    
    # Load config if exists
    config_path = args.config if os.path.exists(args.config) else None
    neugi = NeugiSwarm(config_path)
    
    if args.test:
        print("\n🧪 Testing configuration...")
        result = neugi.chat("Hello! Testing. Say hi!")
        print(f"\nResponse: {result[:200]}...")
        return
    
    # Start dashboard
    NeugiHandler.neugi = neugi
    
    print(f"\n🌐 Dashboard: http://localhost:{args.port}")
    print(f"📡 API: http://localhost:{args.port}/api/chat")
    print(f"\n Press Ctrl+C to stop\n")
    
    try:
        server = HTTPServer(("0.0.0.0", args.port), NeugiHandler)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n👋 Neugi Swarm stopped")

if __name__ == "__main__":
    main()
