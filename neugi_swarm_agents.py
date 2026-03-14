#!/usr/bin/env python3
"""
🤖 NEUGI SWARM - AGENTS
========================

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
    WORKING = "working"
    WAITING = "waiting"


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


class AgentManager:
    """Manages all Neugi agents"""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = os.path.expanduser("~/neugi/data/agents.db")
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.agents: Dict[str, Agent] = {}

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
                )
                self.agents[agent_id] = agent
                self._save_agent(agent)

    def _save_agent(self, agent: Agent):
        """Save agent to database"""
        c = self.conn.cursor()
        c.execute(
            """INSERT OR REPLACE INTO agents VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
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

    def get(self, agent_id: str) -> Optional[Agent]:
        """Get an agent"""
        return self.agents.get(agent_id)

    def list(self) -> List[Agent]:
        """List all agents"""
        return list(self.agents.values())

    def list_by_role(self, role: AgentRole) -> List[Agent]:
        """List agents by role"""
        return [a for a in self.agents.values() if a.role == role]

    def run(self, agent_id: str, task: str) -> Dict:
        """Run an agent on a task"""
        agent = self.get(agent_id)

        if not agent:
            return {"status": "error", "message": f"Agent {agent_id} not found"}

        # Perceive
        agent.status = AgentStatus.WORKING
        agent.current_task = task

        # Think - determine best action
        action = self._think(agent, task)

        # Act - execute action
        result = self._act(agent, action, task)

        # Learn
        agent.tasks_completed += 1
        leveled_up = agent.add_xp(10)

        agent.status = AgentStatus.IDLE
        agent.current_task = ""

        # Log
        self._log(agent_id, "task", result)

        response = {
            "status": "success",
            "agent": agent.name,
            "task": task,
            "result": result[:200],
            "xp_gained": 10,
            "level": agent.level,
        }

        if leveled_up:
            response["level_up"] = True
            response["new_level"] = agent.level

        return response

    def _call_llm(self, agent: Agent, prompt: str) -> str:
        """Call Ollama LLM with fallback"""
        try:
            import requests

            primary_model = "qwen3.5:cloud"
            fallback_model = "nemotron-3-super:cloud"
            try:
                config_path = os.path.expanduser("~/neugi/data/config.json")
                if os.path.exists(config_path):
                    with open(config_path, "r") as f:
                        cfg = json.load(f)
                        model_cfg = cfg.get("model", {})
                        if isinstance(model_cfg, dict):
                            primary_model = model_cfg.get("primary", primary_model)
                            fallback_model = model_cfg.get("fallback", fallback_model)
                        elif isinstance(model_cfg, str):
                            # backward compatibility
                            primary_model = model_cfg
            except Exception:
                pass  # keep defaults

            # Try primary model first
            for model_name in [primary_model, fallback_model]:
                payload = {
                    "model": model_name,
                    "messages": [
                        {
                            "role": "system",
                            "content": f"You are {agent.name}, the Neugi Swarm {agent.role.value}. Your capabilities are {', '.join(agent.capabilities)}. Keep responses concise, brilliant, and focused on your role. You are communicating with a 1B parameter optimized framework.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                }
                r = requests.post(
                    "http://localhost:11434/api/chat", json=payload, timeout=45
                )
                if r.ok:
                    return r.json().get("message", {}).get("content", "").strip()
        except Exception:
            pass
        return ""

    def _think(self, agent: Agent, task: str) -> str:
        """Agent thinks about the task"""
        task_lower = task.lower()

        # Match task to capabilities
        for cap in agent.capabilities:
            if cap in task_lower:
                return cap

        # Default to first capability
        return agent.capabilities[0] if agent.capabilities else "respond"

    def _act(self, agent: Agent, action: str, task: str) -> str:
        """Agent acts on the task"""

        # Call LLM to generate the actual response instead of simulating
        prompt = f"Perform the action '{action}' for the following task: {task}\nProvide the exact output or result of this action."
        llm_response = self._call_llm(agent, prompt)

        if llm_response:
            return f"[{agent.name}] {llm_response}"

        # Simulate action execution fallback if LLM fails
        if action in ["search", "fetch", "analyze"]:
            return f"[{agent.name}] Researching: {task}"
        elif action in ["code", "debug", "build"]:
            return f"[{agent.name}] Coding: {task}"
        elif action in ["create", "design", "generate"]:
            return f"[{agent.name}] Creating: {task}"
        elif action in ["analyze", "visualize", "report"]:
            return f"[{agent.name}] Analyzing: {task}"
        elif action in ["plan", "decide", "optimize"]:
            return f"[{agent.name}] Planning: {task}"
        elif action in ["scan", "audit", "protect"]:
            return f"[{agent.name}] Securing: {task}"
        elif action in ["post", "engage", "schedule"]:
            return f"[{agent.name}] Social: {task}"
        elif action in ["write", "edit", "proofread"]:
            return f"[{agent.name}] Writing: {task}"
        elif action in ["delegate", "coordinate", "oversee"]:
            return f"[{agent.name}] Managing: {task}"
        else:
            return f"[{agent.name}] Responding to: {task}"

    def _log(self, agent_id: str, action: str, result: str):
        """Log agent action"""
        c = self.conn.cursor()
        c.execute(
            "INSERT INTO agent_logs VALUES (?,?,?,?,?)",
            (None, agent_id, action, result[:200], datetime.now().isoformat()),
        )
        self.conn.commit()

    def get_leaderboard(self, limit: int = 10) -> List[Dict]:
        """Get top agents by XP"""
        sorted_agents = sorted(self.agents.values(), key=lambda a: a.xp, reverse=True)

        return [
            {
                "rank": i + 1,
                "name": a.name,
                "xp": a.xp,
                "level": a.level,
                "tasks": a.tasks_completed,
            }
            for i, a in enumerate(sorted_agents[:limit])
        ]

    def status(self) -> Dict:
        """Get agent system status"""
        total_xp = sum(a.xp for a in self.agents.values())
        total_tasks = sum(a.tasks_completed for a in self.agents.values())

        return {
            "total_agents": len(self.agents),
            "total_xp": total_xp,
            "total_tasks": total_tasks,
            "by_role": {role.value: len(self.list_by_role(role)) for role in AgentRole},
        }


# Main
if __name__ == "__main__":
    agents = AgentManager()

    print("🤖 Neugi Swarm Agents")
    print("=" * 40)

    # Run test
    result = agents.run("aurora", "research AI developments")
    print(f"\nAurora: {result}")

    # Leaderboard
    print("\n🏆 Leaderboard:")
    for lb in agents.get_leaderboard():
        print(f"  {lb['rank']}. {lb['name']} - {lb['xp']} XP (Level {lb['level']})")

    print(f"\n{json.dumps(agents.status(), indent=2)}")
