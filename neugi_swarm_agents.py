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
        import urllib.request
        import json
        import os

        primary_model = "qwen3.5:cloud"
        fallback_model = "nemotron-3-super:cloud"
        ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")

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
                        primary_model = model_cfg
        except Exception:
            pass  # keep defaults

        system_prompt = f"You are {agent.name}, the Neugi Swarm {agent.role.value}. Your tools are {', '.join(agent.tools)}. Keep responses concise, brilliant, and focused on your role. You are communicating with a 1B parameter optimized framework."

        for model_name in [primary_model, fallback_model]:
            try:
                payload = {
                    "model": model_name,
                    "prompt": f"{system_prompt}\n\nTask:\n{prompt}\n\nResponse:",
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                    }
                }
                req = urllib.request.Request(
                    f"{ollama_url}/api/generate",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=30) as response:
                    data = json.loads(response.read().decode())
                    return data.get("response", "").strip()
            except Exception:
                continue

        return f"[{agent.name}] Error: LLM context failed. Please run 'python neugi_wizard.py' to diagnose model connectivity."

    def _think(self, agent: Agent, task: str) -> str:
        """Agent thinks about the task and selects the best tool"""
        if not agent.tools:
            return "none"

        # Ask LLM to pick exactly ONE tool
        prompt = f"Analyze the following task and select exactly ONE tool to use from this list: {', '.join(agent.tools)}.\nTask: {task}\nONLY output the tool name, no other text."
        response = self._call_llm(agent, prompt).strip().lower()

        # Clean up response to ensure it matches a tool
        for tool in agent.tools:
            if tool.lower() in response:
                return tool

        # Default to first tool if LLM fails
        return agent.tools[0]

    def _act(self, agent: Agent, action: str, task: str) -> str:
        """Agent acts on the task - using real tools dynamically!"""
        try:
            from neugi_swarm_tools import ToolManager
            tools = ToolManager()
        except ImportError:
            tools = None

        if not tools:
            return f"[{agent.name}] Tool framework unavailable. Run 'python neugi_wizard.py' to repair dependencies."

        if action == "none":
            return f"[{agent.name}] Completed task without explicit tools."

        tool = tools.get(action)
        if not tool:
            # Ultimate fallback if tool missing
            llm_result = tools.execute("llm_think", prompt=f"You are {agent.name}. Perform task: {task}")
            return f"[{agent.name}] {llm_result.get('response', '')[:500]}"

        # Dynamically map the task string to the tool's primary argument.
        # This keeps it fast and optimized for 1B parameters without complex JSON schemas.
        result = None
        if action == "web_search":
            result = tools.execute(action, query=task)
        elif action == "web_fetch":
            # Extract basic URL if present
            words = task.split()
            url = next((w for w in words if w.startswith("http")), task)
            result = tools.execute(action, url=url)
        elif action == "neugi_browser":
            result = tools.execute(action, query=task, mode="search")
        elif action == "code_execute":
            result = tools.execute(action, code=task)
        elif action == "code_debug":
            result = tools.execute(action, code=task)
        elif action == "file_write":
            path = f"~/neugi/workspace/{agent.id}_{int(datetime.now().timestamp())}.txt"
            result = tools.execute(action, path=path, content=task)
        elif action == "json_parse":
            import json
            try:
                # Try to parse if raw JSON
                data = json.loads(task)
                result = tools.execute(action, data=json.dumps(data))
            except Exception:
                result = tools.execute("csv_analyze", data=task)
        elif action == "csv_analyze":
            result = tools.execute(action, data=task)
        elif action == "send_telegram":
            result = tools.execute(action, message=task)
        elif action == "send_discord":
            result = tools.execute(action, message=task)
        elif action == "send_email":
            result = tools.execute(action, to="user", subject="NEUGI Result", body=task)
        elif action == "file_read":
            result = tools.execute(action, path=task)
        elif action == "file_list":
            result = tools.execute(action, path="~/neugi/workspace")
        elif action == "process_list":
            result = tools.execute(action)
        elif action == "llm_think":
            result = tools.execute(action, prompt=task)
        elif action == "delegate_task":
            target = task.split(":")[0] if ":" in task else "aurora"
            sub_task = task.split(":")[1] if ":" in task else task
            result = tools.execute(action, target_agent=target, task=sub_task)
        elif action == "git_execute":
            result = tools.execute(action, command=task)
        elif action == "search_memory":
            result = tools.execute(action, query=task)
        else:
            # Fallback for unrecognized dynamically registered tools
            result = tools.execute(action, query=task, task=task)

        if result and not result.get("error"):
            # Provide generic success parsing
            out = str(result)[:500]
            if "response" in result:
                out = str(result["response"])[:500]
            elif "output" in result:
                out = str(result["output"])[:500]
            elif "summary" in result:
                out = str(result["summary"])[:500]
            return f"[{agent.name}] Successfully executed {action}: {out}"

        return f"[{agent.name}] Executed {action} but encountered an issue: {result.get('error', 'Unknown Error') if result else 'No result'}"

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
