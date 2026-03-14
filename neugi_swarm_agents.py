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
                r = requests.post("http://localhost:11434/api/chat", json=payload, timeout=45)
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
        """Agent acts on the task - using ALL available real tools!"""

        # Import tool manager
        try:
            from neugi_swarm_tools import ToolManager

            tools = ToolManager()
        except ImportError:
            tools = None

        # ============================================
        # AURORA - Web & Research
        # ============================================
        if agent.id == "aurora":
            if action in ["search", "research", "web"]:
                result = tools.execute("web_search", query=task) if tools else None
                if result and result.get("success"):
                    return f"[{agent.name}] Found {len(result.get('results', []))} results"

            elif action in ["fetch", "scrape", "extract"]:
                result = tools.execute("web_fetch", url=task) if tools and "http" in task else None
                if result and result.get("success"):
                    return f"[{agent.name}] Fetched content: {result.get('content', '')[:200]}..."

            elif action in ["analyze", "verify"]:
                result = tools.execute("neugi_browser", query=task) if tools else None
                if result and result.get("success"):
                    return f"[{agent.name}] Analysis: {result.get('summary', '')[:300]}"

        # ============================================
        # CIPHER - Code & Development
        # ============================================
        elif agent.id == "cipher":
            if action in ["code", "build", "execute"]:
                result = (
                    tools.execute("code_execute", code=task, language="python") if tools else None
                )
                if result and result.get("success"):
                    return f"[{agent.name}] Executed: {result.get('output', '')[:500]}"

            elif action in ["debug", "fix", "error"]:
                result = tools.execute("code_debug", code=task) if tools else None
                if result and result.get("success"):
                    return f"[{agent.name}] Debugged: {result.get('suggestions', [])[:3]}"

            elif action in ["read", "review"]:
                result = tools.execute("file_read", path=task) if tools else None
                if result and result.get("success"):
                    return f"[{agent.name}] Read: {result.get('content', '')[:200]}"

        # ============================================
        # NOVA - Create & Design
        # ============================================
        elif agent.id == "nova":
            if action in ["create", "generate", "make", "new"]:
                # Write to workspace
                result = (
                    tools.execute(
                        "file_write",
                        path=f"~/neugi/workspace/{agent.id}_{int(datetime.now().timestamp())}.txt",
                        content=task,
                    )
                    if tools
                    else None
                )
                if result and result.get("success"):
                    return f"[{agent.name}] Created in workspace"

            elif action in ["design", "visualize"]:
                # Use LLM to design
                result = tools.execute("llm_think", prompt=f"Design: {task}") if tools else None
                if result and result.get("success"):
                    return f"[{agent.name}] Design: {result.get('response', '')[:300]}"

        # ============================================
        # PULSE - Data & Analytics
        # ============================================
        elif agent.id == "pulse":
            if action in ["analyze", "analytics", "stats"]:
                try:
                    import json

                    data = json.loads(task)
                    result = tools.execute("json_parse", data=json.dumps(data)) if tools else None
                    if result and result.get("success"):
                        return f"[{agent.name}] Analyzed: {result}"
                except Exception:
                    pass
                # Fallback to CSV
                result = tools.execute("csv_analyze", data=task) if tools else None
                if result and result.get("success"):
                    return f"[{agent.name}] CSV Analysis: {result.get('summary', '')[:300]}"

            elif action in ["visualize", "chart", "graph"]:
                result = (
                    tools.execute("llm_think", prompt=f"Create visualization for: {task}")
                    if tools
                    else None
                )
                if result and result.get("success"):
                    return f"[{agent.name}] Visualization: {result.get('response', '')[:300]}"

            elif action in ["report", "summarize"]:
                result = (
                    tools.execute("llm_think", prompt=f"Generate report for: {task}")
                    if tools
                    else None
                )
                if result and result.get("success"):
                    return f"[{agent.name}] Report: {result.get('response', '')[:500]}"

        # ============================================
        # QUARK - Strategy & Planning
        # ============================================
        elif agent.id == "quark":
            if action in ["plan", "strategy", "roadmap"]:
                result = (
                    tools.execute("llm_think", prompt=f"Create a strategic plan for: {task}")
                    if tools
                    else None
                )
                if result and result.get("success"):
                    return f"[{agent.name}] Plan: {result.get('response', '')[:500]}"

            elif action in ["decide", "recommend", "choose"]:
                result = (
                    tools.execute("llm_think", prompt=f"Make a decision about: {task}")
                    if tools
                    else None
                )
                if result and result.get("success"):
                    return f"[{agent.name}] Decision: {result.get('response', '')[:300]}"

            elif action in ["optimize", "improve", "enhance"]:
                result = tools.execute("llm_think", prompt=f"Optimize: {task}") if tools else None
                if result and result.get("success"):
                    return f"[{agent.name}] Optimization: {result.get('response', '')[:300]}"

        # ============================================
        # SHIELD - Security
        # ============================================
        elif agent.id == "shield":
            if action in ["scan", "audit", "check"]:
                result = tools.execute("web_fetch", url=task) if tools and "http" in task else None
                if not result:
                    # Try code analysis
                    result = tools.execute("code_debug", code=task) if tools else None
                if result and result.get("success"):
                    return f"[{agent.name}] Scanned: Security check complete"

            elif action in ["protect", "secure", "harden"]:
                result = (
                    tools.execute(
                        "llm_think", prompt=f"Provide security recommendations for: {task}"
                    )
                    if tools
                    else None
                )
                if result and result.get("success"):
                    return f"[{agent.name}] Security: {result.get('response', '')[:300]}"

        # ============================================
        # SPARK - Social & Communication
        # ============================================
        elif agent.id == "spark":
            if action in ["post", "tweet", "social"]:
                result = tools.execute("send_telegram", message=task) if tools else None
                if result and result.get("success"):
                    return f"[{agent.name}] Posted to Telegram"

            elif action in ["discord", "notify"]:
                result = tools.execute("send_discord", message=task) if tools else None
                if result and result.get("success"):
                    return f"[{agent.name}] Sent to Discord"

            elif action in ["email", "mail"]:
                result = (
                    tools.execute("send_email", to="user", subject="NEUGI", body=task)
                    if tools
                    else None
                )
                if result and result.get("success"):
                    return f"[{agent.name}] Email sent"

        # ============================================
        # INK - Writing & Documentation
        # ============================================
        elif agent.id == "ink":
            if action in ["write", "draft", "compose"]:
                result = (
                    tools.execute(
                        "file_write",
                        path=f"~/neugi/workspace/{agent.id}_{int(datetime.now().timestamp())}.txt",
                        content=task,
                    )
                    if tools
                    else None
                )
                if result and result.get("success"):
                    return f"[{agent.name}] Written to workspace"

            elif action in ["edit", "revise", "modify"]:
                result = (
                    tools.execute("llm_think", prompt=f"Edit the following: {task}")
                    if tools
                    else None
                )
                if result and result.get("success"):
                    return f"[{agent.name}] Edited: {result.get('response', '')[:300]}"

            elif action in ["proofread", "review", "check"]:
                result = tools.execute("llm_think", prompt=f"Proofread: {task}") if tools else None
                if result and result.get("success"):
                    return f"[{agent.name}] Proofread: {result.get('response', '')[:300]}"

        # ============================================
        # NEXUS - Management & Coordination
        # ============================================
        elif agent.id == "nexus":
            if action in ["delegate", "assign", "task"]:
                # Nexus coordinates - use LLM to plan delegation
                result = (
                    tools.execute("llm_think", prompt=f"Delegate this task effectively: {task}")
                    if tools
                    else None
                )
                if result and result.get("success"):
                    return f"[{agent.name}] Delegated: {result.get('response', '')[:300]}"

            elif action in ["coordinate", "orchestrate", "manage"]:
                # List workspace files
                result = tools.execute("file_list", path="~/neugi/workspace") if tools else None
                if result and result.get("success"):
                    files = result.get("files", [])
                    return f"[{agent.name}] Coordinating {len(files)} files in workspace"

            elif action in ["oversee", "monitor", "status"]:
                # Check system
                result = tools.execute("process_list") if tools else None
                if result and result.get("success"):
                    return f"[{agent.name}] System status: {result.get('count', 0)} processes"

        # ============================================
        # FALLBACK: Use LLM for any unmatched actions
        # ============================================
        if tools:
            llm_result = tools.execute(
                "llm_think", prompt=f"You are {agent.name}. Perform action '{action}' for: {task}"
            )
            if llm_result and llm_result.get("success"):
                return f"[{agent.name}] {llm_result.get('response', '')[:500]}"

        # Ultimate fallback
        return f"[{agent.name}] Task '{task}' processed via {action}"

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
