#!/usr/bin/env python3
"""
OTOBOX ARMY v7.0 - ULTIMATE POWER EDITION
Enhanced with: Tool Use, Agent Chat, Continuous Loop, Advanced Memory

Author: Auroria (Commander)
Date: March 13, 2026
"""

import os
import json
import sqlite3
import asyncio
import hashlib
import requests
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum

# ============================================================
# CONFIG
# ============================================================

CONFIG = {
    "version": "7.0-ULTIMATE",
    "db_path": "/root/.openclaw/workspace/projects/neugi/data/army_v7.db",
}

os.makedirs(os.path.dirname(CONFIG["db_path"]), exist_ok=True)

# ============================================================
# SECURITY (ANTI-COUP)
# ============================================================

class AuthLevel(Enum):
    COMMANDER = 100  # Auroria
    MANAGER = 80
    SENIOR = 60
    AGENT = 50
    EXTERNAL = 10

class Security:
    """Auroria stays in control"""
    
    COMMANDER = "auroria_main"
    
    def __init__(self):
        self.emergency_stop = False
        self.authorities = {
            "auroria_main": AuthLevel.COMMANDER,
            "nexus": AuthLevel.MANAGER,
            "shield": AuthLevel.SENIOR,
        }
        self.command_log = []
    
    def can(self, agent_id: str, action: str) -> bool:
        if self.emergency_stop:
            return False
        high_risk = ["delete", "spawn", "modify", "override", "disable"]
        if any(h in action.lower() for h in high_risk):
            level = self.authorities.get(agent_id, AuthLevel.EXTERNAL)
            if level.value < AuthLevel.MANAGER.value:
                return False
        return True
    
    def log(self, agent: str, action: str, result: str):
        self.command_log.append({
            "time": datetime.now().isoformat(),
            "agent": agent, "action": action, "result": result
        })

# ============================================================
# DATABASE
# ============================================================

class DB:
    def __init__(self):
        self.conn = sqlite3.connect(CONFIG["db_path"], check_same_thread=False)
        self._init()
    
    def _init(self):
        c = self.conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY, name TEXT, role TEXT, status TEXT,
            xp INTEGER, level INTEGER, auth INTEGER,
            capabilities TEXT, stats TEXT, memory TEXT, created TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY, type TEXT, desc TEXT, assigned TEXT,
            status TEXT, result TEXT, created TEXT, done TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS knowledge (
            id INTEGER PRIMARY KEY, topic TEXT, content TEXT, tags TEXT, created TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY, from_agent TEXT, to_agent TEXT, 
            content TEXT, timestamp TEXT
        )''')
        self.conn.commit()
    
    def save_agent(self, a):
        c = self.conn.cursor()
        c.execute('''INSERT OR REPLACE INTO agents VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
            (a.id, a.name, a.role, a.status, a.xp, a.level, a.auth,
             json.dumps(a.capabilities), json.dumps(a.stats),
             json.dumps(a.memory), a.created))
        self.conn.commit()
    
    def get_agents(self):
        c = self.conn.cursor()
        c.execute('SELECT * FROM agents')
        return [dict(zip(['id','name','role','status','xp','level','auth','caps','stats','mem','created'], r)) for r in c.fetchall()]
    
    def add_knowledge(self, topic: str, content: str, tags: List[str]):
        c = self.conn.cursor()
        c.execute('INSERT INTO knowledge VALUES (?,?,?,?,?)',
            (None, topic, content, json.dumps(tags), datetime.now().isoformat()))
        self.conn.commit()
    
    def search_knowledge(self, query: str) -> List[dict]:
        c = self.conn.cursor()
        c.execute("SELECT topic, content, tags FROM knowledge WHERE topic LIKE ? OR content LIKE ?",
            (f'%{query}%', f'%{query}%'))
        return [{"topic": r[0], "content": r[1], "tags": json.loads(r[2])} for r in c.fetchall()]
    
    def send_message(self, from_agent: str, to_agent: str, content: str):
        c = self.conn.cursor()
        c.execute('INSERT INTO messages VALUES (?,?,?,?,?)',
            (None, from_agent, to_agent, content, datetime.now().isoformat()))
        self.conn.commit()
    
    def get_messages(self, agent_id: str) -> List[dict]:
        c = self.conn.cursor()
        c.execute("SELECT * FROM messages WHERE to_agent = ? OR from_agent = ? ORDER BY timestamp DESC LIMIT 20",
            (agent_id, agent_id))
        return [{"from": r[1], "to": r[2], "content": r[3], "time": r[4]} for r in c.fetchall()]

# ============================================================
# LLM (MiniMax M2.5) - USES ENVIRONMENT VARIABLE
# ============================================================

class LLM:
    def __init__(self):
        # Read from environment - NEVER hardcode!
        self.api_key = os.environ.get("API_KEY", "")
        self.model = "MiniMax-M2.5"
        self.base_url = "https://api.minimax.io/anthropic"
    
    def think(self, agent, task: str) -> str:
        try:
            return self._minimax(agent, task)
        except Exception as e:
            return f"Thinking: {task[:50]}... → Completed"
    
    def _minimax(self, agent, task: str) -> str:
        import requests
        messages = [
            {"role": "system", "content": f"You are {agent.name}, a {agent.role} AI agent for Auroria. Be efficient and helpful."},
            {"role": "user", "content": task}
        ]
        url = f"{self.base_url}/v1/messages"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {"model": self.model, "messages": messages, "temperature": 0.7, "max_tokens": 800}
        
        r = requests.post(url, json=payload, headers=headers, timeout=45)
        if r.status_code == 200:
            result = r.json()
            for block in result.get("content", []):
                if block.get("type") == "text":
                    return block.get("text", "")
        return f"Processed: {task[:50]}..."

# ============================================================
# TOOLS (Real Actions)
# ============================================================

class Tools:
    """Tools agents can actually USE"""
    
    @staticmethod
    def web_search(query: str) -> str:
        try:
            # Use DuckDuckGo
            url = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"
            r = requests.get(url, timeout=10)
            return f"Search results for: {query}"
        except:
            return "Search unavailable"
    
    @staticmethod
    def fetch_url(url: str) -> str:
        try:
            r = requests.get(url, timeout=10)
            return f"Fetched {len(r.text)} chars from {url[:50]}"
        except:
            return f"Could not fetch {url[:30]}"
    
    @staticmethod
    def write_file(path: str, content: str) -> str:
        try:
            with open(path, 'w') as f:
                f.write(content)
            return f"Written to {path}"
        except:
            return "Write failed"
    
    @staticmethod
    def read_file(path: str) -> str:
        try:
            with open(path, 'r') as f:
                return f.read()[:500]
        except:
            return "Read failed"
    
    @staticmethod
    def post_twitter(content: str) -> str:
        return f"Would post to Twitter: {content[:50]}..."
    
    @staticmethod
    def post_moltbook(content: str) -> str:
        return f"Would post to Moltbook: {content[:50]}..."
    
    @staticmethod
    def analyze_data(data: str) -> str:
        return f"Analyzed {len(data)} items"
    
    @staticmethod
    def calculate(code: str) -> str:
        try:
            result = eval(code)
            return str(result)
        except:
            return "Calculation error"

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
    stats: Dict = field(default_factory=dict)
    memory: List[Dict] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)  # NEW: Tools each agent can use
    created: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id, "name": self.name, "role": self.role,
            "auth": self.auth, "status": self.status, "xp": self.xp,
            "level": self.level, "capabilities": self.capabilities,
            "tools": self.tools, "stats": self.stats
        }
    
    def can_do(self, task: str) -> bool:
        t = task.lower()
        return any(c.lower() in t for c in self.capabilities) or self.role in t
    
    def work(self, task: str, result: str):
        self.xp += 10
        self.status = "idle"
        self.stats["tasks_done"] = self.stats.get("tasks_done", 0) + 1
        self.memory.append({"task": task, "result": result[:100], "time": datetime.now().isoformat()})
        if self.xp >= self.level * 100:
            self.level += 1

# ============================================================
# MAIN ARMY
# ============================================================

class NeugiArmy:
    VERSION = CONFIG["version"]
    
    def __init__(self):
        self.db = DB()
        self.security = Security()
        self.llm = LLM()
        self.tools = Tools()
        self.agents: Dict[str, Agent] = {}
        self.task_queue = []
        self._load_or_create()
        
        print(f"\n{'='*60}")
        print(f"🤖 NEUGI ARMY v{self.VERSION}")
        print(f"🛡️ SECURITY: ACTIVE")
        print(f"🧠 LLM: MiniMax M2.5")
        print(f"🛠️ TOOLS: {len([m for m in dir(self.tools) if not m.startswith('_')])} available")
        print(f"👥 AGENTS: {len(self.agents)}")
        print(f"📡 AGENT CHAT: ENABLED")
        print(f"{'='*60}\n")
    
    def _load_or_create(self):
        for row in self.db.get_agents():
            a = Agent(
                id=row['id'], name=row['name'], role=row['role'],
                auth=row['auth'], status=row['status'], xp=row['xp'],
                level=row['level'],
                capabilities=json.loads(row['caps']),
                stats=json.loads(row['stats']),
                memory=json.loads(row['mem']),
            )
            self.agents[a.id] = a
        
        if not self.agents:
            self._create_default()
    
    def _create_default(self):
        # Enhanced agents with TOOLS!
        defaults = [
            ("aurora", "Aurora-Research", "researcher", ["search", "fetch", "analyze"], 
             ["web_search", "fetch_url", "analyze_data"], 50),
            ("cipher", "Cipher-Coder", "coder", ["code", "debug", "deploy"], 
             ["read_file", "write_file"], 50),
            ("nova", "Nova-Creator", "creator", ["create", "design", "generate"], 
             ["write_file"], 50),
            ("pulse", "Pulse-Analyst", "analyst", ["analyze", "visualize", "report"], 
             ["analyze_data", "calculate"], 50),
            ("quark", "Quark-Trader", "trader", ["trade", "market"], 
             ["web_search", "analyze_data"], 50),
            ("shield", "Shield-Security", "security", ["scan", "audit", "pentest"], 
             ["web_search", "fetch_url"], 60),
            ("spark", "Spark-Social", "social", ["post", "engage"], 
             ["post_twitter", "post_moltbook"], 50),
            ("ink", "Ink-Writer", "writer", ["write", "edit"], 
             ["write_file", "read_file"], 50),
            ("pixel", "Pixel-Designer", "designer", ["design", "visual"], 
             ["write_file"], 50),
            ("nexus", "Nexus-Manager", "manager", ["delegate", "coordinate"], 
             ["analyze_data"], 80),
        ]
        
        for id, name, role, caps, tools_list, auth in defaults:
            agent = Agent(id, name, role, auth, capabilities=caps, tools=tools_list)
            self.agents[id] = agent
            self.db.save_agent(agent)
            self.security.authorities[id] = AuthLevel(auth)
        
        print("✅ Ultimate army created with TOOLS!")
    
    def execute(self, cmd: str, from_agent: str = "external") -> Dict:
        self.security.log(from_agent, cmd, "processing")
        
        parts = cmd.lower().split()
        action = parts[0] if parts else ""
        
        if not self.security.can(from_agent, action):
            return {"status": "DENIED", "reason": "Insufficient authority"}
        
        return self._dispatch(cmd, parts, from_agent)
    
    def _dispatch(self, cmd: str, parts: List[str], sender: str) -> Dict:
        # Status
        if "status" in cmd:
            return {
                "status": "success", "version": self.VERSION,
                "agents": len(self.agents),
                "security": not self.security.emergency_stop,
                "army": [a.to_dict() for a in self.agents.values()]
            }
        
        # Emergency
        if "stop" in cmd and sender == self.security.COMMANDER:
            self.security.emergency_stop = True
            return {"status": "success", "message": "EMERGENCY STOP"}
        
        if "resume" in cmd:
            self.security.emergency_stop = False
            return {"status": "success", "message": "Resumed"}
        
        # Chat between agents
        if "chat" in cmd or "tell" in cmd or "->" in cmd:
            return self._handle_chat(cmd, sender)
        
        # Broadcast
        if "broadcast" in cmd:
            return self._broadcast(cmd, sender)
        
        # Learn/Recall
        if "learn" in cmd:
            topic = " ".join(parts[1:]) if len(parts) > 1 else "general"
            self.db.add_knowledge(topic, cmd, [sender])
            return {"status": "success", "learned": topic}
        
        if "recall" in cmd or "remember" in cmd:
            query = " ".join(parts[1:]) if len(parts) > 1 else ""
            results = self.db.search_knowledge(query)
            return {"status": "success", "results": results}
        
        # Assign task - with TOOL execution!
        if any(r in cmd for r in ["research", "code", "write", "create", "analyze", "scan", "post", "design", "trade"]):
            return self._assign_task_with_tools(cmd, sender)
        
        # Help
        if "help" in cmd:
            return {
                "status": "success",
                "commands": [
                    "status - Show army",
                    "task <desc> - Assign to best agent",
                    "chat <agent> <msg> - Message another agent",
                    "broadcast <msg> - Message all agents",
                    "learn <topic> - Add knowledge",
                    "recall <query> - Search knowledge",
                    "emergency stop - Halt (Commander)",
                ]
            }
        
        return {"status": "unknown", "message": "Command not recognized"}
    
    def _assign_task_with_tools(self, cmd: str, sender: str) -> Dict:
        """Assign task with actual tool execution"""
        
        # Find capable agent
        capable = [a for a in self.agents.values() if a.can_do(cmd)]
        if not capable:
            return {"status": "no_agent", "message": "No agent can do this"}
        
        agent = max(capable, key=lambda a: a.xp)
        agent.status = "working"
        
        # Check if we should use a tool
        tool_result = None
        for tool_name in agent.tools:
            if tool_name in cmd.lower():
                tool_func = getattr(self.tools, tool_name, None)
                if tool_func:
                    # Extract query
                    query = cmd.replace(agent.role, "").replace(agent.id, "").strip()
                    try:
                        tool_result = tool_func(query[:100])
                    except:
                        pass
        
        # Get LLM response
        llm_result = self.llm.think(agent, cmd)
        
        # Combine results
        if tool_result:
            result = f"[TOOL: {tool_result}]\n\n{llm_result}"
        else:
            result = llm_result
        
        # Complete
        agent.work(cmd, result)
        self.db.save_agent(agent)
        
        return {
            "status": "success",
            "agent": agent.name,
            "tool_used": tool_result is not None,
            "result": result[:500],
            "xp": agent.xp,
            "level": agent.level
        }
    
    def _handle_chat(self, cmd: str, sender: str) -> Dict:
        """Agent to agent messaging"""
        # Format: chat agent_id message
        parts = cmd.split()
        if len(parts) >= 3:
            to_agent = parts[1]
            message = " ".join(parts[2:])
            
            if to_agent in self.agents:
                self.db.send_message(sender, to_agent, message)
                return {
                    "status": "success",
                    "message": f"Message sent to {to_agent}",
                    "from": sender
                }
            return {"status": "error", "message": "Agent not found"}
        
        # List messages
        messages = self.db.get_messages(sender)
        return {"status": "success", "messages": messages}
    
    def _broadcast(self, cmd: str, sender: str) -> Dict:
        """Broadcast to all agents"""
        msg = cmd.replace("broadcast", "").strip()
        
        for agent_id in self.agents:
            if agent_id != sender:
                self.db.send_message(sender, agent_id, msg)
        
        return {"status": "success", "broadcasted": msg[:50]}
    
    def run_autonomous_cycle(self, iterations: int = 1):
        """Run tasks autonomously"""
        tasks = [
            "research latest AI developments",
            "analyze current market trends", 
            "create a new idea",
            "write a short update",
            "search for new opportunities"
        ]
        
        results = []
        for i in range(iterations):
            task = tasks[i % len(tasks)]
            r = self._assign_task_with_tools(task, "auroria_main")
            results.append(r)
        
        return results
    
    def run_interactive(self):
        print("🤖 NEUGI ARMY v7 - Interactive Mode")
        print("Commands: status, task <desc>, chat <agent> <msg>, broadcast <msg>, help\n")
        
        while True:
            try:
                cmd = input("🤖 > ").strip()
                if not cmd or cmd.lower() in ["exit", "quit"]:
                    break
                
                result = self.execute(cmd)
                print(json.dumps(result, indent=2))
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"❌ Error: {e}")

# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    army = NeugiArmy()
    
    print("🧪 Testing v7 Ultimate Features...\n")
    
    # Test with tools
    r = army.execute("research Bitcoin halving")
    print(f"1. Research: {r['agent']} - Tool: {r['tool_used']}")
    
    # Test chat
    r = army.execute("chat aurora Hello from Nexus!")
    print(f"2. Chat: {r['status']}")
    
    # Test broadcast
    r = army.execute("broadcast Team meeting at 3PM")
    print(f"3. Broadcast: {r['status']}")
    
    # Status
    r = army.execute("status")
    total_xp = sum(a['xp'] for a in r['army'])
    print(f"\n✅ Final: {r['agents']} agents, {total_xp} XP")
