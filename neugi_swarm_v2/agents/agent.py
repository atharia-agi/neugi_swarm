"""
Core Agent class with role-based identity, perceive-think-act cycle,
XP/level progression, tool allowlists, scoped memory, and persistent state.
"""

import json
import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class AgentRole(str, Enum):
    """Pre-defined agent roles with associated capabilities."""
    RESEARCHER = "researcher"
    CODER = "coder"
    CREATOR = "creator"
    ANALYST = "analyst"
    STRATEGIST = "strategist"
    SECURITY = "security"
    SOCIAL = "social"
    WRITER = "writer"
    MANAGER = "manager"


class AgentStatus(str, Enum):
    """Agent execution states."""
    IDLE = "idle"
    THINKING = "thinking"
    ACTING = "acting"
    WAITING = "waiting"
    ERROR = "error"
    SLEEPING = "sleeping"


@dataclass
class AgentState:
    """Serializable snapshot of agent internals for persistence."""
    agent_id: str
    status: str
    xp: int
    level: int
    tasks_completed: int
    tasks_failed: int
    current_task_id: Optional[str]
    current_task_context: Optional[Dict[str, Any]]
    last_heartbeat: Optional[str]
    error_count: int
    last_error: Optional[str]
    memory_entries: int
    created_at: str
    updated_at: str


class Agent:
    """
    Autonomous agent with role-based identity and goal-directed behavior.

    Lifecycle:
        1. Perceive - gather context from environment, memory, and messages
        2. Think - plan action using role-specific reasoning
        3. Act - execute tools and produce output
        4. Reflect - update memory, gain XP, persist state

    Supports heartbeat-based resumption: if the process crashes mid-task,
    the agent can reload its last checkpoint and continue.
    """

    XP_PER_LEVEL = 100
    MAX_LEVEL = 50
    MAX_MEMORY_ENTRIES = 500

    def __init__(
        self,
        name: str,
        role: AgentRole,
        goal: str = "",
        backstory: str = "",
        tools: Optional[Dict[str, Callable]] = None,
        allowed_tools: Optional[Set[str]] = None,
        allowed_skills: Optional[Set[str]] = None,
        db_path: str = ":memory:",
    ) -> None:
        self.id = f"{role.value}-{uuid.uuid4().hex[:8]}"
        self.name = name
        self.role = role
        self.goal = goal
        self.backstory = backstory

        self.status = AgentStatus.IDLE
        self.xp = 0
        self.level = 1
        self.tasks_completed = 0
        self.tasks_failed = 0

        self._tools: Dict[str, Callable] = tools or {}
        self.allowed_tools: Set[str] = allowed_tools or set(self._tools.keys())
        self.allowed_skills: Set[str] = allowed_skills or set()

        self._memory: List[Dict[str, Any]] = []
        self._skills: Dict[str, Any] = {}

        self.current_task_id: Optional[str] = None
        self.current_task_context: Optional[Dict[str, Any]] = None
        self.last_heartbeat: Optional[datetime] = None
        self.error_count = 0
        self.last_error: Optional[str] = None

        self.created_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = self.created_at

        self._db_path = db_path
        self._init_db()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def xp_to_next_level(self) -> int:
        return self.level * self.XP_PER_LEVEL

    @property
    def skill_points(self) -> int:
        return max(0, self.level - 1)

    @property
    def memory_size(self) -> int:
        return len(self._memory)

    # ------------------------------------------------------------------
    # Perceive-Think-Act cycle
    # ------------------------------------------------------------------

    def perceive(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Gather all available context: agent memory, recent messages,
        environment state, and external input.
        """
        self.status = AgentStatus.THINKING
        perception = {
            "agent_id": self.id,
            "role": self.role.value,
            "level": self.level,
            "status": self.status.value,
            "memory_summary": self._summarize_memory(),
            "recent_memory": self._memory[-5:] if self._memory else [],
            "skills_loaded": list(self._skills.keys()),
            "tools_available": list(self.allowed_tools),
            "external_context": context or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._record_memory("perception", perception)
        return perception

    def think(
        self,
        task: str,
        perception: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Plan the next action given a task and current perception.
        Returns a plan dict with steps, tool choices, and confidence.
        """
        if perception is None:
            perception = self.perceive()

        plan = {
            "task": task,
            "role": self.role.value,
            "strategy": self._select_strategy(task),
            "tools_to_use": self._select_tools(task),
            "steps": self._plan_steps(task),
            "confidence": self._estimate_confidence(task),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._record_memory("plan", plan)
        return plan

    def act(
        self,
        task: str,
        plan: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute the plan by invoking allowed tools.
        Returns result dict with output, metrics, and any errors.
        """
        if plan is None:
            plan = self.think(task)

        self.status = AgentStatus.ACTING
        self.current_task_id = str(uuid.uuid4())[:12]
        self.current_task_context = {"task": task, "plan": plan}
        self._heartbeat()

        result: Dict[str, Any] = {
            "task": task,
            "agent_id": self.id,
            "agent_name": self.name,
            "role": self.role.value,
            "steps_executed": [],
            "output": "",
            "errors": [],
            "duration_seconds": 0.0,
            "success": False,
        }

        start = time.monotonic()
        try:
            for tool_name in plan.get("tools_to_use", []):
                step_result = self._invoke_tool(tool_name, task)
                result["steps_executed"].append(step_result)

            combined = " ".join(
                str(s.get("output", "")) for s in result["steps_executed"]
            )
            result["output"] = combined or f"[{self.name}] Task processed via role {self.role.value}"
            result["success"] = len(result["errors"]) == 0

        except Exception as exc:
            result["errors"].append(str(exc))
            self.error_count += 1
            self.last_error = str(exc)
            self.status = AgentStatus.ERROR
            logger.error("Agent %s act failed: %s", self.name, exc)

        finally:
            result["duration_seconds"] = round(time.monotonic() - start, 3)
            self._record_memory("result", result)
            self.current_task_context = None
            self.current_task_id = None

            if result["success"]:
                self.tasks_completed += 1
                self.gain_xp(10)
            else:
                self.tasks_failed += 1

            self.status = AgentStatus.IDLE
            self._heartbeat()
            self.save()

        return result

    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Full perceive-think-act pipeline for a single task."""
        perception = self.perceive(context)
        plan = self.think(task, perception)
        return self.act(task, plan)

    # ------------------------------------------------------------------
    # XP / Level system
    # ------------------------------------------------------------------

    def gain_xp(self, amount: int) -> None:
        """Add XP and level up if threshold reached."""
        self.xp += amount
        while self.xp >= self.xp_to_next_level and self.level < self.MAX_LEVEL:
            self.xp -= self.xp_to_next_level
            self.level += 1
            logger.info("Agent %s leveled up to %d", self.name, self.level)
            self._record_memory("level_up", {"level": self.level})

    # ------------------------------------------------------------------
    # Tool management
    # ------------------------------------------------------------------

    def add_tool(self, name: str, func: Callable) -> None:
        """Register a tool and add to allowlist."""
        self._tools[name] = func
        self.allowed_tools.add(name)

    def remove_tool(self, name: str) -> None:
        """Unregister a tool and remove from allowlist."""
        self._tools.pop(name, None)
        self.allowed_tools.discard(name)

    def _invoke_tool(self, name: str, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """Safely invoke a tool if it is allowed."""
        if name not in self.allowed_tools:
            return {"tool": name, "output": "", "error": f"Tool '{name}' not allowed"}
        func = self._tools.get(name)
        if func is None:
            return {"tool": name, "output": "", "error": f"Tool '{name}' not registered"}
        try:
            output = func(*args, **kwargs)
            return {"tool": name, "output": output, "error": None}
        except Exception as exc:
            return {"tool": name, "output": "", "error": str(exc)}

    # ------------------------------------------------------------------
    # Skill management
    # ------------------------------------------------------------------

    def add_skill(self, name: str, data: Any) -> None:
        """Load a skill into the agent's skill registry."""
        if name in self.allowed_skills or not self.allowed_skills:
            self._skills[name] = data

    def get_skill(self, name: str) -> Optional[Any]:
        return self._skills.get(name)

    # ------------------------------------------------------------------
    # Memory
    # ------------------------------------------------------------------

    def remember(self, entry_type: str, data: Any) -> None:
        """Add a memory entry with automatic trimming."""
        self._record_memory(entry_type, data)

    def _record_memory(self, entry_type: str, data: Any) -> None:
        entry = {
            "type": entry_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._memory.append(entry)
        if len(self._memory) > self.MAX_MEMORY_ENTRIES:
            self._memory = self._memory[-self.MAX_MEMORY_ENTRIES:]

    def get_memory(
        self,
        entry_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Retrieve memory entries, optionally filtered by type."""
        entries = self._memory
        if entry_type:
            entries = [e for e in entries if e["type"] == entry_type]
        return entries[-limit:]

    def clear_memory(self) -> None:
        self._memory.clear()

    def _summarize_memory(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for entry in self._memory:
            counts[entry["type"]] = counts.get(entry["type"], 0) + 1
        return counts

    # ------------------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------------------

    def _heartbeat(self) -> None:
        """Record a heartbeat timestamp for crash recovery."""
        self.last_heartbeat = datetime.now(timezone.utc)

    def time_since_heartbeat(self) -> float:
        """Seconds since last heartbeat. Returns inf if never heartbeated."""
        if self.last_heartbeat is None:
            return float("inf")
        return (datetime.now(timezone.utc) - self.last_heartbeat).total_seconds()

    # ------------------------------------------------------------------
    # Persistence (SQLite)
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        if self._db_path == ":memory:":
            return
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_state (
                    agent_id TEXT PRIMARY KEY,
                    name TEXT,
                    role TEXT,
                    goal TEXT,
                    backstory TEXT,
                    status TEXT,
                    xp INTEGER,
                    level INTEGER,
                    tasks_completed INTEGER,
                    tasks_failed INTEGER,
                    current_task_id TEXT,
                    current_task_context TEXT,
                    last_heartbeat TEXT,
                    error_count INTEGER,
                    last_error TEXT,
                    memory_json TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)

    def save(self) -> None:
        """Persist agent state to SQLite."""
        self.updated_at = datetime.now(timezone.utc).isoformat()
        if self._db_path == ":memory:":
            return
        state = self._to_row()
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO agent_state (
                    agent_id, name, role, goal, backstory, status, xp, level,
                    tasks_completed, tasks_failed, current_task_id,
                    current_task_context, last_heartbeat, error_count,
                    last_error, memory_json, created_at, updated_at
                ) VALUES (
                    :agent_id, :name, :role, :goal, :backstory, :status,
                    :xp, :level, :tasks_completed, :tasks_failed,
                    :current_task_id, :current_task_context, :last_heartbeat,
                    :error_count, :last_error, :memory_json,
                    :created_at, :updated_at
                )
                ON CONFLICT(agent_id) DO UPDATE SET
                    name=:name, role=:role, goal=:goal, backstory=:backstory,
                    status=:status, xp=:xp, level=:level,
                    tasks_completed=:tasks_completed, tasks_failed=:tasks_failed,
                    current_task_id=:current_task_id,
                    current_task_context=:current_task_context,
                    last_heartbeat=:last_heartbeat, error_count=:error_count,
                    last_error=:last_error, memory_json=:memory_json,
                    updated_at=:updated_at
                """,
                state,
            )

    def load(self, agent_id: str) -> bool:
        """Restore agent state from SQLite by agent_id. Returns True if found."""
        if self._db_path == ":memory:":
            return False
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM agent_state WHERE agent_id = ?", (agent_id,)
            ).fetchone()
        if row is None:
            return False
        self._from_row(dict(row))
        return True

    def _to_row(self) -> Dict[str, Any]:
        return {
            "agent_id": self.id,
            "name": self.name,
            "role": self.role.value,
            "goal": self.goal,
            "backstory": self.backstory,
            "status": self.status.value,
            "xp": self.xp,
            "level": self.level,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "current_task_id": self.current_task_id,
            "current_task_context": json.dumps(self.current_task_context)
            if self.current_task_context
            else None,
            "last_heartbeat": self.last_heartbeat.isoformat()
            if self.last_heartbeat
            else None,
            "error_count": self.error_count,
            "last_error": self.last_error,
            "memory_json": json.dumps(self._memory[-100:]),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def _from_row(self, row: Dict[str, Any]) -> None:
        self.id = row["agent_id"]
        self.name = row["name"]
        self.role = AgentRole(row["role"])
        self.goal = row["goal"] or ""
        self.backstory = row["backstory"] or ""
        self.status = AgentStatus(row["status"])
        self.xp = row["xp"]
        self.level = row["level"]
        self.tasks_completed = row["tasks_completed"]
        self.tasks_failed = row["tasks_failed"]
        self.current_task_id = row["current_task_id"]
        self.current_task_context = (
            json.loads(row["current_task_context"])
            if row["current_task_context"]
            else None
        )
        self.last_heartbeat = (
            datetime.fromisoformat(row["last_heartbeat"])
            if row["last_heartbeat"]
            else None
        )
        self.error_count = row["error_count"]
        self.last_error = row["last_error"]
        self._memory = json.loads(row["memory_json"]) if row["memory_json"] else []
        self.created_at = row["created_at"]
        self.updated_at = row["updated_at"]

    def to_state(self) -> AgentState:
        """Return a serializable state snapshot."""
        return AgentState(
            agent_id=self.id,
            status=self.status.value,
            xp=self.xp,
            level=self.level,
            tasks_completed=self.tasks_completed,
            tasks_failed=self.tasks_failed,
            current_task_id=self.current_task_id,
            current_task_context=self.current_task_context,
            last_heartbeat=self.last_heartbeat.isoformat()
            if self.last_heartbeat
            else None,
            error_count=self.error_count,
            last_error=self.last_error,
            memory_entries=len(self._memory),
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    # ------------------------------------------------------------------
    # Internal planning helpers
    # ------------------------------------------------------------------

    def _select_strategy(self, task: str) -> str:
        strategies = {
            AgentRole.RESEARCHER: "gather_analyze_synthesize",
            AgentRole.CODER: "implement_test_refactor",
            AgentRole.CREATOR: "ideate_prototype_refine",
            AgentRole.ANALYST: "measure_insight_recommend",
            AgentRole.STRATEGIST: "assess_plan_execute",
            AgentRole.SECURITY: "scan_assess_mitigate",
            AgentRole.SOCIAL: "engage_amplify_convert",
            AgentRole.WRITER: "draft_edit_polish",
            AgentRole.MANAGER: "delegate_coordinate_review",
        }
        return strategies.get(self.role, "analyze_execute")

    def _select_tools(self, task: str) -> List[str]:
        return list(self.allowed_tools)[:3]

    def _plan_steps(self, task: str) -> List[str]:
        return [
            f"Step 1: Analyze task via {self.role.value} lens",
            f"Step 2: Apply {self._select_strategy(task)}",
            f"Step 3: Validate and record outcome",
        ]

    def _estimate_confidence(self, task: str) -> float:
        base = 0.5
        level_bonus = min(0.3, self.level * 0.02)
        xp_bonus = min(0.2, self.xp / self.XP_PER_LEVEL * 0.1)
        error_penalty = min(0.3, self.error_count * 0.05)
        return round(min(1.0, max(0.0, base + level_bonus + xp_bonus - error_penalty)), 2)

    # ------------------------------------------------------------------
    # Representation
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"Agent(name={self.name!r}, role={self.role.value}, "
            f"level={self.level}, status={self.status.value})"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role.value,
            "goal": self.goal,
            "backstory": self.backstory,
            "status": self.status.value,
            "xp": self.xp,
            "level": self.level,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "tools": list(self.allowed_tools),
            "skills": list(self._skills.keys()),
            "error_count": self.error_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
