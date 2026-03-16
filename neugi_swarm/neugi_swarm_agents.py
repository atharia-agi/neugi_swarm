#!/usr/bin/env python3
"""
🤖 NEUGI SWARM - AGENTS
=======================

Autonomous agent system

Agents:
- aurora (Researcher)
- cipher (Coder)
- nova (Creator)
- pulse (Analyst)
- quark (Strategist)
- shield (Security)
- spark (Social)
- ink (Writer)
- nexus (Manager)

Each agent has:
- Perceive → Think → Act cycle
- Own memory
- Tools
- XP/Level

Usage:
    from neugi_swarm_agents import Agent, AgentManager
    agents = AgentManager()
    agents.run("aurora", "research AI")
"""

import os
import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum

try:
    from neugi_swarm_memory import MemoryManager
except ImportError:
    MemoryManager = None


class AgentRole(Enum):
    RESEARCHER = "researcher"
    CODER = "coder"
    CREATOR = "creator"
    ANALYST = "analyst"
    STRATEGIST = "strategist"
    SECURITY = "security"
    SOCIAL = "social"
    WRITER = "writer"
    MANAGER = "manager"


class AgentStatus(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    ACTING = "acting"
    ERROR = "error"


@dataclass
class Agent:
    """Neugi Agent"""

    id: str
    name: str
    role: AgentRole
    status: AgentStatus

    # Stats
    xp: int = 0
    level: int = 1
    tasks_completed: int = 0

    # Capabilities
    capabilities: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)

    # Memory
    memory: List[Dict] = field(default_factory=list)

    # State
    current_task: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # Reference to memory manager for global workspace
    memory_manager: Optional[object] = field(default=None, repr=False)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role.value,
            "status": self.status.value,
            "xp": self.xp,
            "level": self.level,
            "tasks_completed": self.tasks_completed,
            "capabilities": self.capabilities,
            "tools": self.tools,
            "current_task": self.current_task,
        }

    def add_xp(self, amount: int):
        """Add XP and check for level up"""
        self.xp += amount

        # Level up every 100 XP
        new_level = (self.xp // 100) + 1
        if new_level > self.level:
            self.level = new_level
            return True  # Leveled up
        return False

    def get_augmented_task(self, task: str) -> str:
        """
        Augment a task with global workspace context for more conscious reasoning.
        Returns the original task if no memory manager is available.
        """
        if self.memory_manager is None:
            return task
        # Recall from global workspace (most relevant first)
        global_context = self.memory_manager.recall_from_global_workspace(task, limit=3)
        context_str = (
            "\n".join([mem["content"] for mem in global_context]) if global_context else ""
        )
        if context_str:
            return f"TASK: {task}\n\nGLOBAL SWARM CONTEXT:\n{context_str}\n\nPlease use the above context to inform your response."
        else:
            return task

    def write_to_global_workspace(self, content: str, importance: int = 8):
        """Write content to the global workspace shared across the swarm."""
        if self.memory_manager is not None:
            self.memory_manager.add_to_global_workspace(content, importance=importance)


class AgentManager:
    """Manages all Neugi agents"""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = os.path.expanduser("~/neugi/data/agents.db")
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.agents: Dict[str, Agent] = {}
        # Create a memory manager for global workspace and long-term memory
        self.memory_manager = MemoryManager(db_path=os.path.expanduser("~/neugi/data/memory.db"))

        self._init_tables()
        self._create_default_agents()

    def _init_tables(self):
        """Initialize agent tables"""
        c = self.conn.cursor()

        c.execute("""CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            name TEXT,
            role TEXT,
            status TEXT,
            xp INTEGER,
            level INTEGER,
            tasks_completed INTEGER,
            capabilities TEXT,
            tools TEXT,
            current_task TEXT,
            created_at TEXT
        )""")

        c.execute("""CREATE TABLE IF NOT EXISTS agent_memory (
            id INTEGER PRIMARY KEY,
            agent_id TEXT,
            content TEXT,
            importance INTEGER,
            created_at TEXT
        )""")

        c.execute("""CREATE TABLE IF NOT EXISTS agent_logs (
            id INTEGER PRIMARY KEY,
            agent_id TEXT,
            action TEXT,
            result TEXT,
            timestamp TEXT
        )""")

        self.conn.commit()

    def _create_default_agents(self):
        """Create default Neugi agents"""

        default_agents = [
            (
                "aurora",
                "Aurora",
                AgentRole.RESEARCHER,
                ["search", "fetch", "analyze"],
                ["web_search", "web_fetch", "llm_think"],
            ),
            (
                "cipher",
                "Cipher",
                AgentRole.CODER,
                ["code", "debug", "build"],
                ["code_execute", "file_write", "llm_think"],
            ),
            (
                "nova",
                "Nova",
                AgentRole.CREATOR,
                ["create", "design", "generate"],
                ["image_generate", "llm_think", "file_write"],
            ),
            (
                "pulse",
                "Pulse",
                AgentRole.ANALYST,
                ["analyze", "visualize", "report"],
                ["json_parse", "csv_analyze", "llm_think"],
            ),
            (
                "quark",
                "Quark",
                AgentRole.STRATEGIST,
                ["plan", "decide", "optimize"],
                ["llm_think"],
            ),
            (
                "shield",
                "Shield",
                AgentRole.SECURITY,
                ["scan", "audit", "protect"],
                ["code_debug", "web_fetch"],
            ),
            (
                "spark",
                "Spark",
                AgentRole.SOCIAL,
                ["post", "engage", "schedule"],
                ["send_telegram", "send_discord"],
            ),
            (
                "ink",
                "Ink",
                AgentRole.WRITER,
                ["write", "edit", "proofread"],
                ["file_write", "llm_think"],
            ),
            (
                "nexus",
                "Nexus",
                AgentRole.MANAGER,
                ["delegate", "coordinate", "oversee"],
                [],
            ),
        ]

        for agent_id, name, role, caps, tools in default_agents:
            if agent_id not in self.agents:
                agent = Agent(
                    id=agent_id,
                    name=name,
                    role=role,
                    status=AgentStatus.IDLE,
                    capabilities=caps,
                    tools=tools,
                    memory_manager=self.memory_manager,  # Pass the memory manager
                )
                self.agents[agent_id] = agent
                self._save_agent(agent)

    def _save_agent(self, agent: Agent):
        """Save agent to database"""
        c = self.conn.cursor()
        c.execute(
            """INSERT OR REPLACE INTO agents VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                agent.id,
                agent.name,
                agent.role.value,
                agent.status.value,
                agent.xp,
                agent.level,
                agent.tasks_completed,
                json.dumps(agent.capabilities),
                json.dumps(agent.tools),
                agent.current_task,
                agent.created_at,
            ),
        )
        self.conn.commit()

    # ... rest of the file remains unchanged ...
