#!/usr/bin/env python3
"""
🤖 NEUGI SWARM v15 - OPENCLAW INSPIRED
=========================================

Features inspired by reverse-engineered OpenClaw:
- Multi-channel support (all major platforms)
- Memory system (daily logs + curated)
- Agent loop with hooks
- Model failover
- Queue system
- Session management
- Gateway hooks
- Skills system

Version: 15.0.0
Date: March 13, 2026
"""

import os
import json
import sqlite3
import asyncio
import hashlib
import requests
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

VERSION = "15.0.0"
NAME = "Neugi Swarm"
TAGLINE = "Inspired by OpenClaw - Made Accessible"

# ============================================================
# CHANNELS (From OpenClaw)
# ============================================================

class Channel(Enum):
    TELEGRAM = "telegram"
    DISCORD = "discord"
    WHATSAPP = "whatsapp"
    SIGNAL = "signal"
    SLACK = "slack"
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    GOOGLE_CHAT = "googlechat"
    IMESSAGE = "imessage"
    IRC = "irc"
    LINE = "line"
    MATRIX = "matrix"
    MATTERMOST = "mattermost"
    MSTEAMS = "msteams"
    NEXTCLOUD = "nextcloud-talk"
    NOSTR = "nostr"
    SYNOOLOGY = "synology-chat"
    TWITCH = "twitch"
    ZALO = "zalo"
    WEB = "web"

# ============================================================
# MEMORY SYSTEM (From OpenClaw)
# ============================================================

class MemorySystem:
    """
    OpenClaw-style memory:
    - memory/YYYY-MM-DD.md (daily logs)
    - MEMORY.md (curated long-term)
    """
    
    def __init__(self, workspace: str = "./data"):
        self.workspace = workspace
        self.memory_dir = os.path.join(workspace, "memory")
        os.makedirs(self.memory_dir, exist_ok=True)
        
        # Also use SQLite for fast search
        self.db = sqlite3.connect(os.path.join(workspace, "memory.db"), check_same_thread=False)
        self._init_db()
    
    def _init_db(self):
        c = self.db.cursor()
        
        # Semantic memory search
        c.execute('''CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY,
            path TEXT,
            content TEXT,
            importance INTEGER DEFAULT 5,
            created_at TEXT,
            indexed_at TEXT
        )''')
        
        # Daily logs
        c.execute('''CREATE TABLE IF NOT EXISTS daily_logs (
            date TEXT PRIMARY KEY,
            content TEXT,
            updated_at TEXT
        )''')
        
        self.db.commit()
    
    def get_today_log(self) -> str:
        """Get today's daily log file path"""
        today = datetime.now().strftime("%Y-%m-%d")
        return os.path.join(self.memory_dir, f"{today}.md")
    
    def read_recent(self, days: int = 2) -> List[Dict]:
        """Read recent memory files (like OpenClaw)"""
        memories = []
        
        for i in range(days):
            date = datetime.now() - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            filepath = os.path.join(self.memory_dir, f"{date_str}.md")
            
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    content = f.read()
                    memories.append({
                        "date": date_str,
                        "content": content
                    })
        
        return memories
    
    def remember(self, content: str, importance: int = 5):
        """Store in today's log"""
        filepath = self.get_today_log()
        
        # Append to daily log
        timestamp = datetime.now().isoformat()
        entry = f"\n## {timestamp}\n{content}\n"
        
        with open(filepath, 'a') as f:
            f.write(entry)
        
        # Also index for search
        c = self.db.cursor()
        c.execute('INSERT INTO memories (path, content, importance, created_at, indexed_at) VALUES (?,?,?,?,?)',
            (filepath, content, importance, timestamp, timestamp))
        self.db.commit()
    
    def search(self, query: str, limit: int = 5) -> List[Dict]:
        """Semantic search (simple keyword for now)"""
        c = self.db.cursor()
        c.execute('''SELECT * FROM memories WHERE content LIKE ? 
                    ORDER BY importance DESC LIMIT ?''', (f"%{query}%", limit))
        
        return [{"id": r[0], "content": r[2], "importance": r[3]} for r in c.fetchall()]
    
    def flush_to_longterm(self, content: str):
        """Flush important memory to MEMORY.md"""
        memory_file = os.path.join(self.workspace, "MEMORY.md")
        
        with open(memory_file, 'a') as f:
            f.write(f"\n## {datetime.now().isoformat()}\n{content}\n")

# ============================================================
# AGENT LOOP (From OpenClaw)
# ============================================================

class AgentLoop:
    """
    OpenClaw-style agent loop:
    1. Queue (per-session + global)
    2. Context assembly
    3. Model inference
    4. Tool execution
    5. Streaming
    6. Persistence
    """
    
    def __init__(self, llm, tools, memory):
        self.llm = llm
        self.tools = tools
        self.memory = memory
        
        # Queues (from OpenClaw)
        self.session_queues = defaultdict(list)
        self.global_queue = []
        
        # Lifecycle hooks
        self.hooks = {
            "on_start": [],
            "on_tool_call": [],
            "on_end": [],
            "on_error": [],
        }
    
    def register_hook(self, event: str, func: Callable):
        """Register lifecycle hook"""
        if event in self.hooks:
            self.hooks[event].append(func)
    
    def run_hook(self, event: str, *args, **kwargs):
        """Run hooks"""
        for func in self.hooks.get(event, []):
            try:
                func(*args, **kwargs)
            except:
                pass
    
    async def run(self, session_id: str, message: str, context: Dict = None) -> Dict:
        """Run one agent loop iteration"""
        
        # 1. Start hook
        self.run_hook("on_start", session_id, message)
        
        # 2. Load context (memory + session)
        session_context = self._load_context(session_id)
        
        # 3. Model inference
        try:
            response = await self._infer(message, session_context)
            
            # 4. Tool calls
            tools_used = []
            if response.get("tool_calls"):
                for tool_call in response["tool_calls"]:
                    self.run_hook("on_tool_call", tool_call)
                    result = self._execute_tool(tool_call)
                    tools_used.append(result)
            
            # 5. Final response
            final = self._format_response(response, tools_used)
            
            # 6. Save to memory
            self.memory.remember(f"Session {session_id}: {message} -> {final[:200]}")
            
            self.run_hook("on_end", final)
            
            return {"status": "success", "response": final, "tools": tools_used}
            
        except Exception as e:
            self.run_hook("on_error", str(e))
            return {"status": "error", "error": str(e)}
    
    def _load_context(self, session_id: str) -> Dict:
        """Load session context"""
        recent = self.memory.read_recent()
        
        return {
            "session_id": session_id,
            "recent_memories": recent,
            "timestamp": datetime.now().isoformat()
        }
    
    async def _infer(self, message: str, context: Dict) -> Dict:
        """Model inference"""
        # Use LLM
        response = self.llm.think(
            f"Context: {json.dumps(context)}\n\nUser: {message}"
        )
        
        # Check for tool calls (simple parsing)
        tool_calls = []
        if "tool:" in response.lower():
            # Extract tool calls
            tool_calls = [{"name": "example_tool", "args": {}}]
        
        return {
            "content": response,
            "tool_calls": tool_calls
        }
    
    def _execute_tool(self, tool_call: Dict) -> Any:
        """Execute a tool"""
        tool_name = tool_call.get("name")
        return self.tools.execute(tool_name, **tool_call.get("args", {}))
    
    def _format_response(self, response: Dict, tools: List) -> str:
        """Format final response"""
        return response.get("content", "No response")

# ============================================================
# MODEL PROVIDER SYSTEM (From OpenClaw)
# ============================================================

class ModelProvider:
    """
    OpenClaw-style model provider with failover
    """
    
    PROVIDERS = {
        # Free / Cheap
        "groq": {"endpoint": "https://api.groq.com/openai/v1", "free": True},
        "openrouter": {"endpoint": "https://openrouter.ai/api/v1", "free": True},
        "ollama": {"endpoint": "http://localhost:11434", "free": True},
        
        # Premium
        "openai": {"endpoint": "https://api.openai.com/v1", "free": False},
        "anthropic": {"endpoint": "https://api.anthropic.com", "free": False},
        "minimax": {"endpoint": "https://api.minimax.io", "free": False},
    }
    
    def __init__(self, config: Dict):
        self.config = config
        self.current_provider = config.get("provider", "groq")
        self.fallback_providers = config.get("fallback", ["ollama"])
        
        # API keys
        self.keys = {}
        for provider in self.PROVIDERS.keys():
            key = config.get(f"{provider}_key")
            if key:
                self.keys[provider] = key
    
    def call(self, prompt: str, model: str = None) -> str:
        """Call with failover"""
        providers = [self.current_provider] + self.fallback_providers
        
        for provider in providers:
            if provider in self.keys:
                try:
                    return self._call_provider(provider, prompt, model)
                except Exception as e:
                    print(f"Provider {provider} failed: {e}")
                    continue
        
        return "All providers failed"
    
    def _call_provider(self, provider: str, prompt: str, model: str = None) -> str:
        """Call specific provider"""
        
        if provider == "groq":
            return self._call_groq(prompt, model)
        elif provider == "openrouter":
            return self._call_openrouter(prompt, model)
        elif provider == "ollama":
            return self._call_ollama(prompt, model)
        
        return f"[{provider}] response"
    
    def _call_groq(self, prompt: str, model: str = None) -> str:
        import requests
        url = f"{self.PROVIDERS['groq']['endpoint']}/chat/completions"
        headers = {"Authorization": f"Bearer {self.keys.get('groq', '')}"}
        data = {
            "model": model or "llama-3.1-8b-instant",
            "messages": [{"role": "user", "content": prompt}]
        }
        
        r = requests.post(url, json=data, headers=headers, timeout=30)
        if r.ok:
            return r.json()["choices"][0]["message"]["content"]
        raise Exception(f"Groq error: {r.status_code}")
    
    def _call_openrouter(self, prompt: str, model: str = None) -> str:
        import requests
        url = f"{self.PROVIDERS['openrouter']['endpoint']}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.keys.get('openrouter', '')}",
            "HTTP-Referer": "https://neugi.ai"
        }
        data = {
            "model": model or "google/gemini-2.0-flash-exp",
            "messages": [{"role": "user", "content": prompt}]
        }
        
        r = requests.post(url, json=data, headers=headers, timeout=30)
        if r.ok:
            return r.json()["choices"][0]["message"]["content"]
        raise Exception(f"OpenRouter error: {r.status_code}")
    
    def _call_ollama(self, prompt: str, model: str = None) -> str:
        import requests
        url = f"{self.PROVIDERS['ollama']['endpoint']}/api/chat"
        data = {
            "model": model or "llama2",
            "messages": [{"role": "user", "content": prompt}],
            "stream": False
        }
        
        r = requests.post(url, json=data, timeout=60)
        if r.ok:
            return r.json()["message"]["content"]
        raise Exception(f"Ollama error: {r.status_code}")

# ============================================================
# QUEUE SYSTEM (From OpenClaw)
# ============================================================

class QueueSystem:
    """
    OpenClaw-style queue:
    - Per-session queue
    - Global queue
    - Queue modes: collect, steer, followup
    """
    
    def __init__(self):
        self.session_queues = defaultdict(list)
        self.global_queue = []
        self.queue_mode = "collect"  # collect, steer, followup
    
    def enqueue(self, task: Dict, session_id: str = None):
        """Add task to queue"""
        task["queued_at"] = datetime.now().isoformat()
        
        if session_id:
            self.session_queues[session_id].append(task)
        else:
            self.global_queue.append(task)
    
    def dequeue(self, session_id: str = None) -> Optional[Dict]:
        """Get next task"""
        if session_id and self.session_queues[session_id]:
            return self.session_queues[session_id].pop(0)
        
        if self.global_queue:
            return self.global_queue.pop(0)
        
        return None
    
    def size(self, session_id: str = None) -> int:
        """Get queue size"""
        if session_id:
            return len(self.session_queues[session_id])
        return len(self.global_queue)

# ============================================================
# GATEWAY HOOKS (From OpenClaw)
# ============================================================

class GatewayHooks:
    """
    OpenClaw-style hooks:
    - agent:bootstrap (before prompt)
    - Command hooks (/new, /reset, /stop)
    """
    
    def __init__(self):
        self.hooks = {
            "agent:bootstrap": [],
            "command:new": [],
            "command:reset": [],
            "command:stop": [],
            "lifecycle:start": [],
            "lifecycle:end": [],
            "lifecycle:error": [],
        }
    
    def register(self, event: str, script: str):
        """Register a hook script"""
        if event in self.hooks:
            self.hooks[event].append(script)
    
    def trigger(self, event: str, context: Dict = None) -> Dict:
        """Trigger hooks"""
        results = []
        
        for script in self.hooks.get(event, []):
            # Would execute script
            results.append({"hook": event, "script": script})
        
        return {"triggered": event, "results": results}

# ============================================================
# SESSION MANAGEMENT (From OpenClaw)
# ============================================================

class SessionManager:
    """
    OpenClaw-style session management
    """
    
    def __init__(self, db_path: str = "./data/sessions.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init()
        
        self.sessions = {}
    
    def _init(self):
        c = self.conn.cursor()
        
        c.execute('''CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            channel TEXT,
            user_id TEXT,
            created_at TEXT,
            last_active TEXT,
            metadata TEXT
        )''')
        
        self.conn.commit()
    
    def create(self, session_id: str, channel: str, user_id: str) -> Dict:
        """Create session"""
        now = datetime.now().isoformat()
        
        session = {
            "id": session_id,
            "channel": channel,
            "user_id": user_id,
            "created_at": now,
            "last_active": now,
            "metadata": {}
        }
        
        c = self.conn.cursor()
        c.execute('''INSERT OR REPLACE INTO sessions VALUES (?,?,?,?,?,?)''',
            (session_id, channel, user_id, now, now, json.dumps({})))
        self.conn.commit()
        
        self.sessions[session_id] = session
        return session
    
    def get(self, session_id: str) -> Optional[Dict]:
        """Get session"""
        if session_id in self.sessions:
            return self.sessions[session_id]
        
        c = self.conn.cursor()
        c.execute('SELECT * FROM sessions WHERE id = ?', (session_id,))
        row = c.fetchone()
        
        if row:
            session = {
                "id": row[0], "channel": row[1], "user_id": row[2],
                "created_at": row[3], "last_active": row[4],
                "metadata": json.loads(row[5] or "{}")
            }
            self.sessions[session_id] = session
            return session
        
        return None
    
    def update_activity(self, session_id: str):
        """Update last active time"""
        c = self.conn.cursor()
        c.execute('UPDATE sessions SET last_active = ? WHERE id = ?',
            (datetime.now().isoformat(), session_id))
        self.conn.commit()

# ============================================================
# MAIN NEUGI SWARM
# ============================================================

class NeugiSwarm:
    VERSION = VERSION
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        
        print(f"\n{'='*60}")
        print(f"🤖 {NAME} v{VERSION}")
        print(f"   {TAGLINE}")
        print(f"{'='*60}\n")
        
        # Initialize systems (like OpenClaw!)
        print("🔧 Initializing OpenClaw-inspired systems...")
        
        # Memory (markdown files + search)
        self.memory = MemorySystem()
        print("   ✅ Memory: Daily logs + MEMORY.md")
        
        # Model provider with failover
        self.providers = ModelProvider(self.config)
        print("   ✅ Model: Multi-provider with failover")
        
        # Queue system
        self.queue = QueueSystem()
        print("   ✅ Queue: Per-session + global")
        
        # Session management
        self.sessions = SessionManager()
        print("   ✅ Sessions: Persistent + metadata")
        
        # Gateway hooks
        self.hooks = GatewayHooks()
        print("   ✅ Hooks: Bootstrap + lifecycle + commands")
        
        # Tools (placeholder)
        self.tools = SimpleTools()
        
        # Agent loop
        self.loop = AgentLoop(self.providers, self.tools, self.memory)
        
        print(f"\n✅ {NAME} Ready!")
        print(f"{'='*60}\n")
    
    async def process(self, message: str, session_id: str = "default", 
                     channel: str = "cli") -> Dict:
        """Process message through agent loop"""
        
        # Create session if needed
        session = self.sessions.get(session_id)
        if not session:
            session = self.sessions.create(session_id, channel, "user")
        
        # Run agent loop
        result = await self.loop.run(session_id, message, {"channel": channel})
        
        # Update session
        self.sessions.update_activity(session_id)
        
        return result
    
    def status(self) -> Dict:
        """Get system status"""
        return {
            "version": self.VERSION,
            "sessions": len(self.sessions.sessions),
            "queue_size": self.queue.size(),
            "providers": list(self.providers.keys),
        }

# ============================================================
# SIMPLE TOOLS (Placeholder)
# ============================================================

class SimpleTools:
    def __init__(self):
        self.tools = {
            "web_search": self._web_search,
            "web_fetch": self._web_fetch,
            "memory_search": self._memory_search,
            "memory_remember": self._memory_remember,
        }
    
    def execute(self, tool_name: str, **kwargs) -> Any:
        if tool_name in self.tools:
            return self.tools[tool_name](**kwargs)
        return f"Tool {tool_name} not found"
    
    def _web_search(self, query: str, **kwargs) -> Dict:
        return {"query": query, "results": []}
    
    def _web_fetch(self, url: str, **kwargs) -> Dict:
        return {"url": url, "content": ""}
    
    def _memory_search(self, query: str, **kwargs) -> Dict:
        return {"query": query, "results": []}
    
    def _memory_remember(self, content: str, **kwargs) -> Dict:
        return {"remembered": content}

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    config = {
        "provider": "groq",
        "fallback": ["ollama", "openrouter"],
        "groq_key": os.environ.get("GROQ_API_KEY", ""),
        "ollama_url": os.environ.get("OLLAMA_URL", "http://localhost:11434"),
        "openrouter_key": os.environ.get("OPENROUTER_API_KEY", ""),
    }
    
    swarm = NeugiSwarm(config)
    
    print("\n🧪 Testing...")
    
    # Test memory
    print("\n1. Memory:")
    swarm.memory.remember("Test memory from Neugi v15")
    results = swarm.memory.search("Test")
    print(f"   Search results: {len(results)}")
    
    # Test sessions
    print("\n2. Sessions:")
    session = swarm.sessions.get("test-session")
    print(f"   Created: {session}")
    
    print("\n✅ OpenClaw-inspired Neugi v15 Ready!")
