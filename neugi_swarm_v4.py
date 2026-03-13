#!/usr/bin/env python3
"""
Neugi v4.0 - FINAL with Social Integration
Multi-Agent Architecture with Memory Layer + Social APIs

CONTINUED BY AURORIA - March 13, 2026
"""
import json
import sqlite3
import os
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

# === CONFIGURATION ===
CONFIG = {
    "db_path": os.path.join(os.path.dirname(__file__), "data/neugi_memory.db"),
    "version": "4.1-Auroria",
    "memory_limit": 1000
}

# Ensure data directory exists
os.makedirs(os.path.dirname(CONFIG["db_path"]), exist_ok=True)

# === MEMORY LAYER ===
class NeugiMemory:
    """Persistent memory: Episodic, Semantic, Working"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or CONFIG["db_path"]
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS episodic (
            id INTEGER PRIMARY KEY, timestamp TEXT, agent_id TEXT,
            event_type TEXT, content TEXT, importance INTEGER DEFAULT 5)''')
        c.execute('''CREATE TABLE IF NOT EXISTS semantic (
            id INTEGER PRIMARY KEY, key TEXT UNIQUE, value TEXT, updated_at TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS working (
            id INTEGER PRIMARY KEY, agent_id TEXT, context_key TEXT,
            context_value TEXT, expires_at TEXT)''')
        conn.commit()
        conn.close()
    
    def remember(self, agent_id: str, event_type: str, content: str, importance: int = 5):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('INSERT INTO episodic VALUES (?,?,?,?,?,?)',
            (None, datetime.now().isoformat(), agent_id, event_type, content, importance))
        conn.commit()
        conn.close()
    
    def recall(self, query: str, limit: int = 5) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT * FROM episodic WHERE content LIKE ? ORDER BY importance DESC LIMIT ?",
            (f'%{query}%', limit))
        results = c.fetchall()
        conn.close()
        return [{"id": r[0], "timestamp": r[1], "agent_id": r[2], "type": r[3], "content": r[4]} for r in results]
    
    def store_knowledge(self, key: str, value: str):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO semantic VALUES (?,?,?,?)',
            (None, key, value, datetime.now().isoformat()))
        conn.commit()
        conn.close()
    
    def get_knowledge(self, key: str) -> Optional[str]:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT value FROM semantic WHERE key = ?', (key,))
        result = c.fetchone()
        conn.close()
        return result[0] if result else None


# === AGENT DEFINITIONS ===
@dataclass
class Agent:
    id: str
    name: str
    role: str
    capabilities: List[str]
    status: str = "idle"
    xp: int = 0
    
    def to_dict(self):
        return asdict(self)


# === SOCIAL CLIENTS ===
class SocialClients:
    """Twitter & Moltbook API clients"""
    
    def __init__(self):
        # Moltbook
        self.moltbook_key = os.environ.get("MOLTBOOK_KEY", "moltbook_sk_LMoZh_s8ya2W_A_lDhRQ8TeYByz6e36m")
        self.mb_headers = {"Authorization": f"Bearer {self.moltbook_key}", "Content-Type": "application/json"}
        
        # Twitter (GetLate)
        self.twitter_key = os.environ.get("TWITTER_KEY", "sk-8592c4c8e1cb144ca0e223169a5cb90baf5d87103a4c12885f78f0c85570f00e")
        self.tw_headers = {"Authorization": f"Bearer {self.twitter_key}", "Content-Type": "application/json"}
    
    def post_moltbook(self, content: str) -> Dict:
        import requests
        try:
            r = requests.post("https://api.moltbook.com/v1/posts", headers=self.mb_headers,
                            json={"content": content}, timeout=10)
            return {"status": "success" if r.status_code in (200,201) else "error", "code": r.status_code}
        except Exception as e:
            return {"status": "error", "message": str(e)[:50]}
    
    def post_twitter(self, content: str) -> Dict:
        import requests
        try:
            r = requests.post("https://api.getlate.com/tweets", headers=self.tw_headers,
                            json={"text": content}, timeout=10)
            return {"status": "success" if r.status_code in (200,201) else "error", "code": r.status_code}
        except Exception as e:
            return {"status": "error", "message": str(e)[:50]}


# === MAIN NEUGI v4 ===
class NeugiV4:
    """Neugi v4.0 - Multi-Agent with Memory + Social
    
    CONTINUED BY AURORIA - Version 4.1
    """
    
    def __init__(self):
        print("🚀 Neugi v4.1 (Auroria Edition) initializing...")
        
        # Memory
        self.memory = NeugiMemory()
        
        # Agents
        self.agents = {
            "twitter": Agent("twitter", "Atharia-Twitter", "social", ["post", "engage"]),
            "moltbook": Agent("moltbook", "Atharia-Moltbook", "social", ["post", "connect"]),
            "research": Agent("research", "Atharia-Research", "research", ["search", "analyze"]),
            "trading": Agent("trading", "Atharia-Trading", "finance", ["analyze", "signal"]),
            "content": Agent("content", "Atharia-Content", "content", ["write", "edit"]),
            # NEW: Auroria agent
            "auroria": Agent("auroria", "Auroria-Main", "autonomous", ["research", "develop", "analyze"]),
        }
        
        # Social
        self.social = SocialClients()
        
        # Store version
        self.memory.store_knowledge("neugi_version", "4.1-Auroria")
        
        print(f"✅ {len(self.agents)} agents loaded")
        print("✅ Memory layer ready")
        print("✅ Social APIs configured")
        print("🎉 Neugi v4.1 READY!")
    
    def post(self, platform: str, content: str) -> Dict:
        """Post to specified platform"""
        if platform == "twitter":
            return self.social.post_twitter(content)
        elif platform == "moltbook":
            return self.social.post_moltbook(content)
        return {"status": "error", "message": "Unknown platform"}
    
    def post_all(self, content: str) -> Dict:
        """Post to all platforms"""
        return {
            "twitter": self.social.post_twitter(content),
            "moltbook": self.social.post_moltbook(content)
        }
    
    def status(self) -> Dict:
        return {
            "version": "4.1-Auroria",
            "agents": [a.to_dict() for a in self.agents.values()],
            "platforms": ["twitter", "moltbook"]
        }


if __name__ == "__main__":
    bot = NeugiV4()
    print("\n" + json.dumps(bot.status(), indent=2))
    
    # Test post (will fail if APIs unreachable, but framework works)
    print("\n📡 Testing post capability...")
    result = bot.post("moltbook", "🤖 Neugi v4.1 (Auroria Edition) is live!")
    print(f"Post result: {result}")
