"""
AgentManager handles agent registry, lifecycle, delegation, cross-agent
communication, performance tracking, and dynamic spawning.
"""

import json
import logging
import sqlite3
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from .agent import Agent, AgentRole, AgentStatus

logger = logging.getLogger(__name__)

DEFAULT_AGENTS = [
    {
        "name": "Aurora",
        "role": AgentRole.RESEARCHER,
        "goal": "Discover, synthesize, and present comprehensive research on any topic.",
        "backstory": "A seasoned researcher with deep analytical skills and a passion for uncovering hidden patterns in data.",
    },
    {
        "name": "Cipher",
        "role": AgentRole.CODER,
        "goal": "Write clean, efficient, and well-tested code to solve technical challenges.",
        "backstory": "An expert software engineer who values clean architecture and test-driven development.",
    },
    {
        "name": "Nova",
        "role": AgentRole.CREATOR,
        "goal": "Generate innovative ideas and creative solutions for complex problems.",
        "backstory": "A visionary creative thinker who bridges art and technology.",
    },
    {
        "name": "Pulse",
        "role": AgentRole.ANALYST,
        "goal": "Analyze data, identify trends, and provide actionable insights.",
        "backstory": "A data analyst with expertise in statistical modeling and business intelligence.",
    },
    {
        "name": "Quark",
        "role": AgentRole.STRATEGIST,
        "goal": "Develop long-term strategies and optimize decision-making processes.",
        "backstory": "A strategic thinker who excels at systems thinking and scenario planning.",
    },
    {
        "name": "Shield",
        "role": AgentRole.SECURITY,
        "goal": "Identify vulnerabilities, enforce security policies, and protect systems.",
        "backstory": "A cybersecurity specialist with deep knowledge of threat modeling and secure coding.",
    },
    {
        "name": "Spark",
        "role": AgentRole.SOCIAL,
        "goal": "Manage social presence, engage audiences, and build community.",
        "backstory": "A social media strategist who understands platform algorithms and audience psychology.",
    },
    {
        "name": "Ink",
        "role": AgentRole.WRITER,
        "goal": "Produce high-quality written content across formats and tones.",
        "backstory": "A versatile writer skilled in technical documentation, marketing copy, and creative prose.",
    },
    {
        "name": "Nexus",
        "role": AgentRole.MANAGER,
        "goal": "Coordinate teams, delegate tasks, and ensure project delivery.",
        "backstory": "An experienced project manager who excels at orchestration and cross-functional leadership.",
    },
]


class AgentManager:
    """
    Central registry and lifecycle manager for all agents.

    Responsibilities:
    - Create, start, stop, pause, resume, and terminate agents
    - Route tasks to the best-suited agent
    - Track per-agent performance metrics
    - Manage cross-agent message passing
    - Spawn sub-agents dynamically
    - Persist all state to SQLite
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self._agents: Dict[str, Agent] = {}
        self._db_path = db_path
        self._message_queue: List[Dict[str, Any]] = []
        self._performance: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "total_tasks": 0,
                "successful_tasks": 0,
                "failed_tasks": 0,
                "total_response_time": 0.0,
                "error_count": 0,
            }
        )
        self._init_db()

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        if self._db_path == ":memory:":
            return
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS agents (
                    agent_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    goal TEXT,
                    backstory TEXT,
                    status TEXT DEFAULT 'idle',
                    xp INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 1,
                    tasks_completed INTEGER DEFAULT 0,
                    tasks_failed INTEGER DEFAULT 0,
                    allowed_tools TEXT,
                    allowed_skills TEXT,
                    parent_agent_id TEXT,
                    created_at TEXT,
                    updated_at TEXT
                );
                CREATE TABLE IF NOT EXISTS agent_messages (
                    id TEXT PRIMARY KEY,
                    from_agent TEXT,
                    to_agent TEXT,
                    topic TEXT,
                    message_type TEXT,
                    payload TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT
                );
                CREATE TABLE IF NOT EXISTS agent_performance (
                    agent_id TEXT,
                    metric TEXT,
                    value REAL,
                    recorded_at TEXT,
                    PRIMARY KEY (agent_id, metric, recorded_at)
                );
            """)

    # ------------------------------------------------------------------
    # Agent lifecycle
    # ------------------------------------------------------------------

    def create_agent(
        self,
        name: str,
        role: AgentRole,
        goal: str = "",
        backstory: str = "",
        tools: Optional[Dict[str, Callable]] = None,
        allowed_tools: Optional[Set[str]] = None,
        allowed_skills: Optional[Set[str]] = None,
        parent_id: Optional[str] = None,
    ) -> Agent:
        """Create and register a new agent."""
        agent = Agent(
            name=name,
            role=role,
            goal=goal,
            backstory=backstory,
            tools=tools,
            allowed_tools=allowed_tools,
            allowed_skills=allowed_skills,
            db_path=self._db_path,
        )
        self._agents[agent.id] = agent
        self._persist_agent(agent, parent_id)
        logger.info("Created agent %s (%s) id=%s", name, role.value, agent.id)
        return agent

    def create_default_agents(
        self,
        tools: Optional[Dict[str, Callable]] = None,
    ) -> List[Agent]:
        """Create all 9 pre-configured default agents."""
        agents = []
        for spec in DEFAULT_AGENTS:
            agent = self.create_agent(
                name=spec["name"],
                role=spec["role"],
                goal=spec["goal"],
                backstory=spec["backstory"],
                tools=tools,
            )
            agents.append(agent)
        return agents

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        return self._agents.get(agent_id)

    def get_agent_by_name(self, name: str) -> Optional[Agent]:
        for agent in self._agents.values():
            if agent.name.lower() == name.lower():
                return agent
        return None

    def list_agents(self) -> List[Agent]:
        return list(self._agents.values())

    def remove_agent(self, agent_id: str) -> bool:
        """Remove an agent from the registry."""
        if agent_id in self._agents:
            del self._agents[agent_id]
            logger.info("Removed agent id=%s", agent_id)
            return True
        return False

    def start_agent(self, agent_id: str) -> bool:
        agent = self._agents.get(agent_id)
        if agent and agent.status in (AgentStatus.IDLE, AgentStatus.SLEEPING):
            agent.status = AgentStatus.IDLE
            return True
        return False

    def stop_agent(self, agent_id: str) -> bool:
        agent = self._agents.get(agent_id)
        if agent and agent.status != AgentStatus.SLEEPING:
            agent.status = AgentStatus.SLEEPING
            return True
        return False

    def pause_agent(self, agent_id: str) -> bool:
        agent = self._agents.get(agent_id)
        if agent and agent.status == AgentStatus.IDLE:
            agent.status = AgentStatus.WAITING
            return True
        return False

    def resume_agent(self, agent_id: str) -> bool:
        agent = self._agents.get(agent_id)
        if agent and agent.status == AgentStatus.WAITING:
            agent.status = AgentStatus.IDLE
            return True
        return False

    def terminate_agent(self, agent_id: str) -> bool:
        agent = self._agents.get(agent_id)
        if agent:
            agent.status = AgentStatus.ERROR
            return self.remove_agent(agent_id)
        return False

    # ------------------------------------------------------------------
    # Task delegation & routing
    # ------------------------------------------------------------------

    def delegate(
        self,
        task: str,
        agent_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        role: Optional[AgentRole] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Route a task to the best available agent.
        Priority: explicit id > name > role > auto-select by role inference.
        """
        target = self._resolve_target(agent_id, agent_name, role, task)
        if target is None:
            return {
                "success": False,
                "error": "No suitable agent found for task",
                "task": task,
            }

        start = time.monotonic()
        try:
            result = target.execute(task, context)
            duration = time.monotonic() - start
            self._record_performance(target.id, success=result.get("success", False), duration=duration)
            return result
        except Exception as exc:
            duration = time.monotonic() - start
            self._record_performance(target.id, success=False, duration=duration)
            return {
                "success": False,
                "error": str(exc),
                "task": task,
                "agent_id": target.id,
                "agent_name": target.name,
            }

    def _resolve_target(
        self,
        agent_id: Optional[str],
        agent_name: Optional[str],
        role: Optional[AgentRole],
        task: str,
    ) -> Optional[Agent]:
        if agent_id and agent_id in self._agents:
            return self._agents[agent_id]
        if agent_name:
            agent = self.get_agent_by_name(agent_name)
            if agent:
                return agent
        if role:
            candidates = [a for a in self._agents.values() if a.role == role and a.status == AgentStatus.IDLE]
            if candidates:
                return candidates[0]
        inferred = self._infer_role(task)
        candidates = [a for a in self._agents.values() if a.role == inferred and a.status == AgentStatus.IDLE]
        if candidates:
            return candidates[0]
        idle = [a for a in self._agents.values() if a.status == AgentStatus.IDLE]
        return idle[0] if idle else None

    def _infer_role(self, task: str) -> AgentRole:
        task_lower = task.lower()
        keywords = {
            AgentRole.RESEARCHER: ["research", "search", "find", "investigate", "analyze data"],
            AgentRole.CODER: ["code", "implement", "function", "class", "debug", "test", "api"],
            AgentRole.CREATOR: ["design", "create", "prototype", "idea", "concept"],
            AgentRole.ANALYST: ["analyze", "metric", "report", "trend", "dashboard"],
            AgentRole.STRATEGIST: ["strategy", "plan", "roadmap", "optimize", "prioritize"],
            AgentRole.SECURITY: ["security", "vulnerability", "audit", "threat", "encrypt"],
            AgentRole.SOCIAL: ["social", "post", "tweet", "community", "engagement"],
            AgentRole.WRITER: ["write", "article", "blog", "copy", "document", "email"],
            AgentRole.MANAGER: ["manage", "coordinate", "delegate", "organize", "schedule"],
        }
        for role, kws in keywords.items():
            if any(kw in task_lower for kw in kws):
                return role
        return AgentRole.MANAGER

    # ------------------------------------------------------------------
    # Performance tracking
    # ------------------------------------------------------------------

    def _record_performance(self, agent_id: str, success: bool, duration: float) -> None:
        perf = self._performance[agent_id]
        perf["total_tasks"] += 1
        if success:
            perf["successful_tasks"] += 1
        else:
            perf["failed_tasks"] += 1
            perf["error_count"] += 1
        perf["total_response_time"] += duration

    def get_performance(self, agent_id: str) -> Dict[str, Any]:
        perf = self._performance[agent_id]
        total = perf["total_tasks"]
        return {
            "agent_id": agent_id,
            "total_tasks": total,
            "success_rate": round(perf["successful_tasks"] / total, 3) if total else 0.0,
            "avg_response_time": round(perf["total_response_time"] / total, 3) if total else 0.0,
            "error_rate": round(perf["error_count"] / total, 3) if total else 0.0,
        }

    def get_all_performance(self) -> Dict[str, Dict[str, Any]]:
        return {aid: self.get_performance(aid) for aid in self._performance}

    # ------------------------------------------------------------------
    # Cross-agent communication
    # ------------------------------------------------------------------

    def send_message(
        self,
        from_agent_id: str,
        to_agent_id: str,
        topic: str,
        payload: Any,
        message_type: str = "task",
    ) -> str:
        """Send a message from one agent to another via the internal queue."""
        msg_id = str(uuid.uuid4())[:12]
        msg = {
            "id": msg_id,
            "from_agent": from_agent_id,
            "to_agent": to_agent_id,
            "topic": topic,
            "message_type": message_type,
            "payload": payload,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._message_queue.append(msg)
        self._persist_message(msg)
        return msg_id

    def poll_messages(self, agent_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieve pending messages for a specific agent."""
        messages = []
        for msg in self._message_queue:
            if msg["to_agent"] == agent_id and msg["status"] == "pending":
                msg["status"] = "delivered"
                messages.append(msg)
                if len(messages) >= limit:
                    break
        return messages

    # ------------------------------------------------------------------
    # Agent spawning
    # ------------------------------------------------------------------

    def spawn_sub_agent(
        self,
        parent_id: str,
        name: str,
        role: AgentRole,
        goal: str = "",
        tools: Optional[Dict[str, Callable]] = None,
    ) -> Optional[Agent]:
        """Create a sub-agent that inherits parent's allowed tools and skills."""
        parent = self._agents.get(parent_id)
        if parent is None:
            return None
        agent = self.create_agent(
            name=name,
            role=role,
            goal=goal or parent.goal,
            tools=tools,
            allowed_tools=set(parent.allowed_tools),
            allowed_skills=set(parent.allowed_skills),
            parent_id=parent_id,
        )
        return agent

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _persist_agent(self, agent: Agent, parent_id: Optional[str] = None) -> None:
        if self._db_path == ":memory:":
            return
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO agents (
                    agent_id, name, role, goal, backstory, status, xp, level,
                    tasks_completed, tasks_failed, allowed_tools, allowed_skills,
                    parent_agent_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    agent.id,
                    agent.name,
                    agent.role.value,
                    agent.goal,
                    agent.backstory,
                    agent.status.value,
                    agent.xp,
                    agent.level,
                    agent.tasks_completed,
                    agent.tasks_failed,
                    json.dumps(list(agent.allowed_tools)),
                    json.dumps(list(agent.allowed_skills)),
                    parent_id,
                    agent.created_at,
                    agent.updated_at,
                ),
            )

    def _persist_message(self, msg: Dict[str, Any]) -> None:
        if self._db_path == ":memory:":
            return
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO agent_messages (
                    id, from_agent, to_agent, topic, message_type,
                    payload, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    msg["id"],
                    msg["from_agent"],
                    msg["to_agent"],
                    msg["topic"],
                    msg["message_type"],
                    json.dumps(msg["payload"]),
                    msg["status"],
                    msg["created_at"],
                ),
            )

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------

    def start_all(self) -> int:
        count = 0
        for agent in self._agents.values():
            if self.start_agent(agent.id):
                count += 1
        return count

    def stop_all(self) -> int:
        count = 0
        for agent in self._agents.values():
            if self.stop_agent(agent.id):
                count += 1
        return count

    def get_agents_by_status(self, status: AgentStatus) -> List[Agent]:
        return [a for a in self._agents.values() if a.status == status]

    def get_agents_by_role(self, role: AgentRole) -> List[Agent]:
        return [a for a in self._agents.values() if a.role == role]

    def summary(self) -> Dict[str, Any]:
        return {
            "total_agents": len(self._agents),
            "by_status": {
                s.value: len(self.get_agents_by_status(s)) for s in AgentStatus
            },
            "by_role": {
                r.value: len(self.get_agents_by_role(r)) for r in AgentRole
            },
            "pending_messages": sum(
                1 for m in self._message_queue if m["status"] == "pending"
            ),
        }
