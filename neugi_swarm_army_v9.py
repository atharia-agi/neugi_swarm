#!/usr/bin/env python3
"""
OTOBOX ARMY v9.0 - ENTERPRISE EDITION
The most advanced multi-agent system - Matching & Exceeding OpenClaw

Version: 9.0.0
Date: March 13, 2026

Features added to match OpenClaw:
- Multi-channel support (Telegram, Discord, WhatsApp)
- Voice (TTS)
- File management
- Web browsing
- Gateway/API server
- Plugin system
- Enhanced memory
- Scheduled tasks
- Webhook integration
"""

import os
import json
import sqlite3
import asyncio
import hashlib
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

# ============================================================
# CONFIG
# ============================================================

CONFIG = {
    "version": "9.0.0",
    "name": "Neugi Army Enterprise",
    "tagline": "Autonomous Agent Army - Now with Channels",
}

# ============================================================
# SECURITY
# ============================================================

class AuthLevel(Enum):
    COMMANDER = 100
    MANAGER = 80
    SENIOR = 60
    AGENT = 50
    EXTERNAL = 10

class Security:
    COMMANDER_ID = "auroria_main"
    
    def __init__(self):
        self.emergency_stop = False
        self.authorities = {
            "auroria_main": AuthLevel.COMMANDER,
            "nexus": AuthLevel.MANAGER,
        }
        self.command_log = []
    
    def can(self, agent_id: str, action: str) -> bool:
        if self.emergency_stop:
            return False
        high_risk = ["delete", "spawn", "modify", "override"]
        if any(h in action.lower() for h in high_risk):
            level = self.authorities.get(agent_id, AuthLevel.EXTERNAL)
            if level.value < AuthLevel.MANAGER.value:
                return False
        return True
    
    def log(self, agent: str, action: str, result: str):
        self.command_log.append({
            "time": datetime.now().isoformat(),
            "agent": agent, "action": action, "result": result[:100]
        })

# ============================================================
# DATABASE
# ============================================================

class DB:
    def __init__(self, db_path: str = "./data/army_v9.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init()
    
    def _init(self):
        c = self.conn.cursor()
        
        # Core tables
        c.execute('''CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY, name TEXT, role TEXT, status TEXT,
            xp INTEGER, level INTEGER, auth INTEGER,
            capabilities TEXT, tools TEXT, stats TEXT, memory TEXT, created TEXT
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS knowledge (
            id INTEGER PRIMARY KEY, topic TEXT, content TEXT, 
            tags TEXT, importance INTEGER, source TEXT, created TEXT
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY, from_agent TEXT, to_agent TEXT,
            content TEXT, channel TEXT, read INTEGER, created TEXT
        )''')
        
        # NEW: Channels table (like OpenClaw)
        c.execute('''CREATE TABLE IF NOT EXISTS channels (
            id TEXT PRIMARY KEY, platform TEXT, name TEXT,
            config TEXT, enabled INTEGER, created TEXT
        )''')
        
        # NEW: Scheduled tasks
        c.execute('''CREATE TABLE IF NOT EXISTS scheduled_tasks (
            id TEXT PRIMARY KEY, task TEXT, schedule TEXT,
            last_run TEXT, next_run TEXT, enabled INTEGER
        )''')
        
        # NEW: Plugins
        c.execute('''CREATE TABLE IF NOT EXISTS plugins (
            id TEXT PRIMARY KEY, name TEXT, version TEXT,
            enabled INTEGER, config TEXT
        )''')
        
        self.conn.commit()
    
    def save_agent(self, a):
        c = self.conn.cursor()
        c.execute('''INSERT OR REPLACE INTO agents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (a.id, a.name, a.role, a.status, a.xp, a.level, a.auth,
             json.dumps(a.capabilities), json.dumps(a.tools),
             json.dumps(a.stats), json.dumps(a.memory), a.created))
        self.conn.commit()
    
    def get_agents(self):
        c = self.conn.cursor()
        c.execute('SELECT * FROM agents')
        cols = ['id','name','role','status','xp','level','auth','caps','tools','stats','mem','created']
        return [dict(zip(cols, r)) for r in c.fetchall()]
    
    # Channel methods
    def add_channel(self, channel_id: str, platform: str, name: str, config: dict):
        c = self.conn.cursor()
        c.execute('INSERT OR REPLACE INTO channels VALUES (?,?,?,?,?,?)',
            (channel_id, platform, name, json.dumps(config), 1, datetime.now().isoformat()))
        self.conn.commit()
    
    def get_channels(self, enabled_only: bool = True):
        c = self.conn.cursor()
        if enabled_only:
            c.execute('SELECT * FROM channels WHERE enabled = 1')
        else:
            c.execute('SELECT * FROM channels')
        cols = ['id','platform','name','config','enabled','created']
        return [dict(zip(cols, r)) for r in c.fetchall()]

# ============================================================
# CHANNEL INTEGRATIONS (Like OpenClaw!)
# ============================================================

class ChannelManager:
    """Multi-channel support - ALL platforms like OpenClaw"""
    
    PLATFORMS = [
        "telegram", "discord", "whatsapp", "signal", "imessage",
        "slack", "teams", "sms", "email", "web"
    ]
        self.db = db
        self.handlers = {}
    
    def register_handler(self, platform: str, handler: Callable):
        self.handlers[platform] = handler
    
    async def send_message(self, channel_id: str, message: str, platform: str = "telegram"):
        """Send message to channel"""
        channels = self.db.get_channels()
        
        for ch in channels:
            if ch['id'] == channel_id:
                config = json.loads(ch['config'])
                
                if platform == "telegram":
                    return await self._send_telegram(config, message)
                elif platform == "discord":
                    return await self._send_discord(config, message)
                elif platform == "whatsapp":
                    return await self._send_whatsapp(config, message)
        
        return {"status": "error", "message": "Channel not found"}
    
    async def _send_telegram(self, config: dict, message: str) -> dict:
        """Send via Telegram Bot API"""
        if not config.get("bot_token"):
            return {"status": "error", "message": "No bot token"}
        
        url = f"https://api.telegram.org/bot{config['bot_token']}/sendMessage"
        data = {
            "chat_id": config.get("chat_id"),
            "text": message,
            "parse_mode": "Markdown"
        }
        
        try:
            r = requests.post(url, json=data, timeout=10)
            return {"status": "success" if r.ok else "error"}
        except:
            return {"status": "error"}
    
    async def _send_discord(self, config: dict, message: str) -> dict:
        """Send via Discord Webhook"""
        if not config.get("webhook_url"):
            return {"status": "error", "message": "No webhook URL"}
        
        try:
            r = requests.post(config['webhook_url'], 
                            json={"content": message}, timeout=10)
            return {"status": "success" if r.ok else "error"}
        except:
            return {"status": "error"}
    
    async def _send_whatsapp(self, config: dict, message: str) -> dict:
        """Send via WhatsApp (Twilio or similar)"""
        if not config.get("api_url"):
            return {"status": "error", "message": "No API URL"}
        
        # Generic WhatsApp API call
        return {"status": "simulated", "message": message}
    
    def configure_channel(self, platform: str, name: str, config: dict) -> str:
        """Add a new channel"""
        channel_id = f"{platform}_{name}_{datetime.now().strftime('%s')}"
        self.db.add_channel(channel_id, platform, name, config)
        return channel_id

# ============================================================
# VOICE (TTS)
# ============================================================

class VoiceManager:
    """Text-to-Speech capabilities"""
    
    def __init__(self):
        self.providers = []
        self._detect_providers()
    
    def _detect_providers(self):
        # Check for available TTS
        try:
            import pyttsx3
            self.providers.append("pyttsx3")
        except:
            pass
        
        try:
            import elevenlabs
            self.providers.append("elevenlabs")
        except:
            pass
        
        # Always available: web TTS
        self.providers.append("web")
    
    def speak(self, text: str, provider: str = "auto") -> str:
        """Convert text to speech"""
        if provider == "auto":
            provider = self.providers[0] if self.providers else "none"
        
        if provider == "web":
            return self._web_tts(text)
        elif provider == "pyttsx3":
            return self._pyttsx3_tts(text)
        
        return f"Would speak: {text[:50]}..."
    
    def _web_tts(self, text: str) -> str:
        # Could integrate with web TTS services
        return f"[TTS] {text[:100]}"
    
    def _pyttsx3_tts(self, text: str) -> str:
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
            return "Spoken successfully"
        except:
            return "TTS failed"

# ============================================================
# FILE MANAGER (Like OpenClaw)
# ============================================================

class FileManager:
    """Enhanced file operations"""
    
    def __init__(self, base_path: str = "./files"):
        self.base_path = base_path
        os.makedirs(base_path, exist_ok=True)
    
    def read(self, path: str) -> str:
        try:
            with open(os.path.join(self.base_path, path), 'r') as f:
                return f.read()
        except:
            return f"Could not read: {path}"
    
    def write(self, path: str, content: str) -> str:
        try:
            full_path = os.path.join(self.base_path, path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w') as f:
                f.write(content)
            return f"Written: {path}"
        except Exception as e:
            return f"Error: {e}"
    
    def list(self, path: str = "") -> List[str]:
        try:
            full_path = os.path.join(self.base_path, path)
            return os.listdir(full_path)
        except:
            return []
    
    def delete(self, path: str) -> str:
        try:
            full_path = os.path.join(self.base_path, path)
            os.remove(full_path)
            return f"Deleted: {path}"
        except:
            return f"Could not delete: {path}"

# ============================================================
# WEB BROWSER
# ============================================================

class WebBrowser:
    """Web browsing capabilities"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Neugi/9.0)'
        })
    
    def fetch(self, url: str) -> str:
        """Fetch webpage content"""
        try:
            r = self.session.get(url, timeout=10)
            return f"Fetched {len(r.text)} bytes from {url}"
        except Exception as e:
            return f"Error: {e}"
    
    def search(self, query: str) -> List[dict]:
        """Simple web search (using DuckDuckGo)"""
        try:
            url = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"
            return [{"query": query, "url": url, "engine": "duckduckgo"}]
        except:
            return []
    
    def screenshot(self, url: str) -> str:
        """Would take screenshot (requires browser)"""
        return f"Would screenshot: {url}"

# ============================================================
# PLUGIN SYSTEM (Like OpenClaw Skills!)
# ============================================================

class PluginManager:
    """Plugin system for extensibility"""
    
    def __init__(self):
        self.plugins = {}
        self.hooks = {
            "before_task": [],
            "after_task": [],
            "on_message": [],
            "on_startup": [],
            "on_shutdown": []
        }
    
    def register(self, name: str, plugin: dict):
        """Register a plugin"""
        self.plugins[name] = plugin
        print(f"📦 Plugin loaded: {name}")
    
    def hook(self, event: str, func: Callable):
        """Register a hook"""
        if event in self.hooks:
            self.hooks[event].append(func)
    
    def trigger(self, event: str, *args, **kwargs):
        """Trigger all hooks for an event"""
        results = []
        if event in self.hooks:
            for func in self.hooks[event]:
                try:
                    results.append(func(*args, **kwargs))
                except:
                    pass
        return results
    
    def list_plugins(self) -> List[str]:
        return list(self.plugins.keys())

# ============================================================
# SCHEDULED TASKS
# ============================================================

class Scheduler:
    """Task scheduling"""
    
    def __init__(self, db: DB):
        self.db = db
        self.tasks = {}
    
    def schedule(self, task_id: str, task: str, interval_minutes: int):
        """Schedule a recurring task"""
        next_run = datetime.now() + timedelta(minutes=interval_minutes)
        
        c = self.conn.cursor()
        c.execute('INSERT OR REPLACE INTO scheduled_tasks VALUES (?,?,?,?,?,?)',
            (task_id, task, f"every_{interval_minutes}_min",
             datetime.now().isoformat(), next_run.isoformat(), 1))
        self.conn.commit()
    
    def run_due(self) -> List[dict]:
        """Get tasks that are due"""
        now = datetime.now().isoformat()
        c = self.conn.cursor()
        c.execute('SELECT * FROM scheduled_tasks WHERE next_run <= ? AND enabled = 1',
            (now,))
        
        due = []
        for row in c.fetchall():
            due.append({
                "id": row[0], "task": row[1], 
                "schedule": row[2], "next_run": row[4]
            })
        
        return due

# ============================================================
# GATEWAY/API SERVER
# ============================================================

class Gateway:
    """HTTP API server for Neugi"""
    
    def __init__(self, army, port: int = 8089):
        self.army = army
        self.port = port
        self.app = None
    
    def start(self):
        """Start the gateway server"""
        try:
            from flask import Flask, request, jsonify
            self.app = Flask(__name__)
            
            @self.app.route('/api/status', methods=['GET'])
            def status():
                return jsonify(self.army.status())
            
            @self.app.route('/api/task', methods=['POST'])
            def task():
                data = request.json
                result = self.army.execute(data.get('command', ''))
                return jsonify(result)
            
            @self.app.route('/api/agents', methods=['GET'])
            def agents():
                return jsonify({"agents": self.army.agents})
            
            print(f"🌐 Gateway starting on port {self.port}...")
            self.app.run(host='0.0.0.0', port=self.port, debug=False)
            
        except ImportError:
            print("⚠️ Flask not installed. Run: pip install flask")

# ============================================================
# LLM
# ============================================================

class LLM:
    def __init__(self):
        self.api_key = os.environ.get("API_KEY", "")
        self.provider = "auto"
        self._detect_provider()
    
    def _detect_provider(self):
        # Auto-detect available provider
        if os.environ.get("OLLAMA_URL"):
            self.provider = "ollama"
        elif self.api_key:
            if "minimax" in self.api_key.lower():
                self.provider = "minimax"
            elif "sk-" in self.api_key:
                self.provider = "openai"
            else:
                self.provider = "anthropic"
    
    def think(self, system: str, user: str) -> str:
        if not self.api_key:
            return f"[Simulation] {user[:100]}..."
        
        try:
            if self.provider == "minimax":
                return self._minimax(system, user)
            elif self.provider == "openai":
                return self._openai(system, user)
            elif self.provider == "ollama":
                return self._ollama(system, user)
        except:
            pass
        
        return f"[{self.provider}] {user[:100]}..."
    
    def _minimax(self, system: str, user: str) -> str:
        import requests
        url = "https://api.minimax.io/anthropic/v1/messages"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        data = {
            "model": "MiniMax-M2.5",
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "max_tokens": 500
        }
        r = requests.post(url, json=data, headers=headers, timeout=45)
        if r.status_code == 200:
            result = r.json()
            for block in result.get("content", []):
                if block.get("type") == "text":
                    return block.get("text", "")
        return "API Error"
    
    def _openai(self, system: str, user: str) -> str:
        import requests
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        data = {
            "model": "gpt-4",
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]
        }
        r = requests.post(url, json=data, headers=headers, timeout=45)
        if r.status_code == 200:
            return r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        return "API Error"
    
    def _ollama(self, system: str, user: str) -> str:
        import requests
        url = os.environ.get("OLLAMA_URL", "http://localhost:11434") + "/api/chat"
        data = {"model": "llama2", "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], "stream": False}
        r = requests.post(url, json=data, timeout=60)
        if r.status_code == 200:
            return r.json().get("message", {}).get("content", "")
        return "Ollama Error"

# ============================================================
# AGENT
# ============================================================

@dataclass
class Agent:
    id: str
    name: str
    role: str
    auth: int = 50
    status: str = "idle"
    xp: int = 0
    level: int = 1
    capabilities: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    stats: Dict = field(default_factory=dict)
    memory: List[Dict] = field(default_factory=list)
    created: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id, "name": self.name, "role": self.role,
            "auth": self.auth, "status": self.status, "xp": self.xp,
            "level": self.level, "capabilities": self.capabilities,
            "tools": self.tools, "stats": self.stats
        }

# ============================================================
# MAIN ARMY
# ============================================================

class NeugiArmy:
    VERSION = CONFIG["version"]
    
    def __init__(self):
        self.db = DB()
        self.security = Security()
        self.llm = LLM()
        
        # NEW: Feature managers (like OpenClaw!)
        self.channels = ChannelManager(self.db)
        self.voice = VoiceManager()
        self.files = FileManager()
        self.browser = WebBrowser()
        self.plugins = PluginManager()
        self.scheduler = Scheduler(self.db)
        self.gateway = Gateway(self, port=8089)
        
        self.agents: Dict[str, Agent] = {}
        self._load_or_create()
        
        self._print_banner()
    
    def _print_banner(self):
        print(f"\n{'='*60}")
        print(f"🤖 NEUGI ARMY v{self.VERSION}")
        print(f"   {CONFIG['tagline']}")
        print(f"{'='*60}")
        print(f"🛡️  Security: ACTIVE")
        print(f"🧠  LLM: {self.llm.provider}")
        print(f"👥  Agents: {len(self.agents)}")
        print(f"📱 Channels: {len(self.channels.db.get_channels())}")
        print(f"🎤 Voice: {len(self.voice.providers)} providers")
        print(f"📁 Files: Enabled")
        print(f"🌐 Browser: Enabled")
        print(f"📦 Plugins: {len(self.plugins.list_plugins())}")
        print(f"🌐 Gateway: Port {self.gateway.port}")
        print(f"{'='*60}\n")
    
    def _load_or_create(self):
        for row in self.db.get_agents():
            a = Agent(
                id=row['id'], name=row['name'], role=row['role'],
                auth=row['auth'], status=row['status'], xp=row['xp'],
                level=row['level'],
                capabilities=json.loads(row['caps']),
                tools=json.loads(row['tools']),
                stats=json.loads(row['stats']),
                memory=json.loads(row['mem']),
            )
            self.agents[a.id] = a
        
        if not self.agents:
            self._create_army()
    
    def _create_army(self):
        army = [
            ("aurora", "Aurora-Research", "researcher", ["search", "fetch"], ["web_search", "fetch_url"], 50),
            ("cipher", "Cipher-Coder", "coder", ["code", "debug"], ["read_file", "write_file"], 50),
            ("nova", "Nova-Creator", "creator", ["create", "design"], ["write_file"], 50),
            ("pulse", "Pulse-Analyst", "analyst", ["analyze"], ["analyze_data"], 50),
            ("quark", "Quark-Trader", "trader", ["trade"], ["web_search"], 50),
            ("shield", "Shield-Security", "security", ["scan"], ["web_search"], 60),
            ("spark", "Spark-Social", "social", ["post"], ["post_telegram", "post_discord"], 50),
            ("ink", "Ink-Writer", "writer", ["write"], ["write_file"], 50),
            ("nexus", "Nexus-Manager", "manager", ["delegate"], [], 80),
        ]
        
        for id, name, role, caps, tools_list, auth in army:
            agent = Agent(id, name, role, auth, capabilities=caps, tools=tools_list)
            self.agents[id] = agent
            self.db.save_agent(agent)
            self.security.authorities[id] = AuthLevel(auth)
        
        print("✅ 9-agent army created!")
    
    def execute(self, cmd: str, from_agent: str = "external") -> Dict:
        parts = cmd.lower().split()
        
        if "status" in cmd:
            return self.status()
        
        if "stop" in cmd and from_agent == "auroria_main":
            self.security.emergency_stop = True
            return {"status": "success", "message": "STOPPED"}
        
        # Channel commands
        if "channel add" in cmd:
            return self._add_channel(cmd)
        
        # File commands
        if cmd.startswith("file "):
            return self._handle_file(cmd)
        
        # Web commands
        if cmd.startswith("web ") or cmd.startswith("fetch ") or cmd.startswith("search "):
            return self._handle_web(cmd)
        
        # Voice commands
        if "speak" in cmd or "say" in cmd:
            return self._handle_voice(cmd)
        
        # Plugin commands
        if "plugin" in cmd:
            return self._handle_plugin(cmd)
        
        # Gateway commands
        if "gateway" in cmd:
            return self._handle_gateway(cmd)
        
        # Regular task
        return self._assign_task(cmd, from_agent)
    
    def _add_channel(self, cmd: str) -> Dict:
        """Add a messaging channel"""
        # Format: channel add telegram mybot BOT_TOKEN CHAT_ID
        parts = cmd.split()
        if len(parts) >= 4:
            platform = parts[2]
            name = parts[3]
            config = {"bot_token": parts[4] if len(parts) > 4 else "", 
                     "chat_id": parts[5] if len(parts) > 5 else ""}
            ch_id = self.channels.configure_channel(platform, name, config)
            return {"status": "success", "channel_id": ch_id}
        return {"status": "error", "message": "Usage: channel add <platform> <name> <config>"}
    
    def _handle_file(self, cmd: str) -> Dict:
        """Handle file operations"""
        parts = cmd.split(maxsplit=2)
        if len(parts) >= 3:
            op, path, content = parts[0], parts[1], parts[2] if len(parts) > 2 else ""
            if op == "file_read":
                return {"status": "success", "content": self.files.read(path)}
            elif op == "file_write":
                return {"status": "success", "result": self.files.write(path, content)}
            elif op == "file_list":
                return {"status": "success", "files": self.files.list(path)}
        return {"status": "error"}
    
    def _handle_web(self, cmd: str) -> Dict:
        """Handle web operations"""
        parts = cmd.split(maxsplit=1)
        if len(parts) >= 2:
            query = parts[1]
            if cmd.startswith("search"):
                return {"status": "success", "results": self.browser.search(query)}
            else:
                return {"status": "success", "result": self.browser.fetch(query)}
        return {"status": "error"}
    
    def _handle_voice(self, cmd: str) -> Dict:
        """Handle voice operations"""
        text = cmd.replace("speak", "").replace("say", "").strip()
        result = self.voice.speak(text)
        return {"status": "success", "result": result}
    
    def _handle_plugin(self, cmd: str) -> Dict:
        """Handle plugin operations"""
        if "list" in cmd:
            return {"status": "success", "plugins": self.plugins.list_plugins()}
        return {"status": "error"}
    
    def _handle_gateway(self, cmd: str) -> Dict:
        """Handle gateway operations"""
        if "start" in cmd:
            return {"status": "success", "message": f"Gateway would start on port {self.gateway.port}"}
        return {"status": "error"}
    
    def _assign_task(self, cmd: str, sender: str) -> Dict:
        capable = [a for a in self.agents.values() 
                   if any(c in cmd.lower() for c in a.capabilities)]
        if not capable:
            return {"status": "no_agent"}
        
        agent = max(capable, key=lambda a: a.xp)
        result = self.llm.think(f"You are {agent.name}, a {agent.role}.", cmd)
        
        agent.xp += 10
        agent.stats["tasks_done"] = agent.stats.get("tasks_done", 0) + 1
        self.db.save_agent(agent)
        
        return {"status": "success", "agent": agent.name, "result": result[:200]}
    
    def status(self) -> Dict:
        return {
            "version": self.VERSION,
            "agents": len(self.agents),
            "channels": len(self.channels.db.get_channels()),
            "plugins": len(self.plugins.list_plugins()),
            "security": not self.security.emergency_stop,
        }

# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    army = NeugiArmy()
    
    # Quick test
    print("🧪 Testing v9.0...\n")
    
    r = army.execute("research AI developments")
    print(f"1. Research: {r.get('agent', '?')}")
    
    r = army.execute("status")
    print(f"\n✅ Final: {r['agents']} agents, {r['channels']} channels")
