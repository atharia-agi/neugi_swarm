#!/usr/bin/env python3
"""
NEUGI v2 - Goal-Aware Execution System
=======================================

Hierarchical goal management with decomposition, tracking, prioritization,
completion verification, ancestry tracing, and autonomous suggestion.

Key features:
- Goal hierarchy (mission > objective > task > subtask)
- Goal decomposition (break goals into actionable tasks)
- Goal tracking (progress, blockers, dependencies)
- Goal prioritization (urgency, importance, dependencies)
- Goal completion verification
- Goal ancestry tracing (every task knows its "why")
- Autonomous goal suggestion based on patterns
- SQLite-backed persistent goal storage

Usage:
    gs = GoalSystem(llm_callback, db_path="goals.db")
    mission = await gs.create_goal(
        level=GoalLevel.MISSION,
        title="Build a production-ready web application",
        description="Full-stack app with auth, CRUD, and deployment",
    )
    decomposition = await gs.decompose(mission.id)
    progress = gs.get_progress(mission.id)
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class GoalLevel(Enum):
    """Hierarchy level of a goal."""

    MISSION = "mission"
    OBJECTIVE = "objective"
    TASK = "task"
    SUBTASK = "subtask"

    @property
    def depth(self) -> int:
        return {"mission": 0, "objective": 1, "task": 2, "subtask": 3}[self.value]

    @property
    def children_level(self) -> Optional["GoalLevel"]:
        mapping = {
            "mission": GoalLevel.OBJECTIVE,
            "objective": GoalLevel.TASK,
            "task": GoalLevel.SUBTASK,
            "subtask": None,
        }
        return mapping[self.value]


class GoalStatus(Enum):
    """Status of a goal."""

    PROPOSED = "proposed"
    ACTIVE = "active"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class GoalError(Exception):
    """Error in goal system operations."""

    def __init__(self, message: str, goal_id: Optional[str] = None) -> None:
        super().__init__(message)
        self.goal_id = goal_id


@dataclass
class GoalDependency:
    """A dependency between goals.

    Args:
        goal_id: The goal that has the dependency.
        depends_on_id: The goal it depends on.
        dependency_type: Type of dependency (blocks, requires, relates).
    """

    goal_id: str
    depends_on_id: str
    dependency_type: str = "blocks"


@dataclass
class Goal:
    """A single goal in the hierarchy.

    Args:
        id: Unique identifier.
        level: Hierarchy level.
        title: Short descriptive title.
        description: Detailed description.
        status: Current status.
        parent_id: ID of parent goal (None for missions).
        children_ids: IDs of child goals.
        dependencies: List of dependencies.
        priority: Priority score (0.0-1.0).
        urgency: Urgency score (0.0-1.0).
        importance: Importance score (0.0-1.0).
        progress: Completion progress (0.0-1.0).
        blocker_reason: Reason if blocked.
        acceptance_criteria: Criteria for completion.
        estimated_effort: Estimated effort (story points or hours).
        actual_effort: Actual effort spent.
        tags: Categorization tags.
        metadata: Arbitrary metadata.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
        completed_at: Completion timestamp.
        deadline: Optional deadline timestamp.
    """

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    level: GoalLevel = GoalLevel.TASK
    title: str = ""
    description: str = ""
    status: GoalStatus = GoalStatus.PROPOSED
    parent_id: Optional[str] = None
    children_ids: List[str] = field(default_factory=list)
    dependencies: List[GoalDependency] = field(default_factory=list)
    priority: float = 0.5
    urgency: float = 0.5
    importance: float = 0.5
    progress: float = 0.0
    blocker_reason: str = ""
    acceptance_criteria: List[str] = field(default_factory=list)
    estimated_effort: float = 0.0
    actual_effort: float = 0.0
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    deadline: Optional[float] = None

    @property
    def is_leaf(self) -> bool:
        return self.children_level is None or not self.children_ids

    @property
    def children_level(self) -> Optional[GoalLevel]:
        return self.level.children_level

    @property
    def ancestry_depth(self) -> int:
        return self.level.depth

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "level": self.level.value,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "parent_id": self.parent_id,
            "children_ids": json.dumps(self.children_ids),
            "dependencies": json.dumps(
                [
                    {
                        "goal_id": d.goal_id,
                        "depends_on_id": d.depends_on_id,
                        "dependency_type": d.dependency_type,
                    }
                    for d in self.dependencies
                ]
            ),
            "priority": self.priority,
            "urgency": self.urgency,
            "importance": self.importance,
            "progress": self.progress,
            "blocker_reason": self.blocker_reason,
            "acceptance_criteria": json.dumps(self.acceptance_criteria),
            "estimated_effort": self.estimated_effort,
            "actual_effort": self.actual_effort,
            "tags": json.dumps(self.tags),
            "metadata": json.dumps(self.metadata),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "deadline": self.deadline,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Goal":
        def _parse_json(key: str, default: Any = None) -> Any:
            val = data.get(key)
            if val is None:
                return default
            if isinstance(val, str):
                try:
                    return json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    return default
            return val

        deps_data = _parse_json("dependencies", [])
        deps = [
            GoalDependency(
                goal_id=d["goal_id"],
                depends_on_id=d["depends_on_id"],
                dependency_type=d.get("dependency_type", "blocks"),
            )
            for d in deps_data
        ] if isinstance(deps_data, list) else []

        return cls(
            id=data.get("id", ""),
            level=GoalLevel(data.get("level", "task")),
            title=data.get("title", ""),
            description=data.get("description", ""),
            status=GoalStatus(data.get("status", "proposed")),
            parent_id=data.get("parent_id"),
            children_ids=_parse_json("children_ids", []),
            dependencies=deps,
            priority=float(data.get("priority", 0.5)),
            urgency=float(data.get("urgency", 0.5)),
            importance=float(data.get("importance", 0.5)),
            progress=float(data.get("progress", 0.0)),
            blocker_reason=data.get("blocker_reason", ""),
            acceptance_criteria=_parse_json("acceptance_criteria", []),
            estimated_effort=float(data.get("estimated_effort", 0.0)),
            actual_effort=float(data.get("actual_effort", 0.0)),
            tags=_parse_json("tags", []),
            metadata=_parse_json("metadata", {}),
            created_at=float(data.get("created_at", time.time())),
            updated_at=float(data.get("updated_at", time.time())),
            completed_at=data.get("completed_at"),
            deadline=data.get("deadline"),
        )


@dataclass
class GoalHierarchy:
    """A complete goal hierarchy tree.

    Args:
        root: The root goal.
        descendants: All descendant goals.
        depth: Maximum depth of the hierarchy.
        total_progress: Aggregated progress across all goals.
    """

    root: Goal
    descendants: List[Goal] = field(default_factory=list)
    depth: int = 0
    total_progress: float = 0.0

    def get_all_ids(self) -> Set[str]:
        ids = {self.root.id}
        ids.update(g.id for g in self.descendants)
        return ids

    def get_by_level(self, level: GoalLevel) -> List[Goal]:
        result = []
        if self.root.level == level:
            result.append(self.root)
        result.extend(g for g in self.descendants if g.level == level)
        return result

    def get_blocked(self) -> List[Goal]:
        return [g for g in self.descendants if g.status == GoalStatus.BLOCKED]

    def get_active(self) -> List[Goal]:
        return [
            g
            for g in self.descendants
            if g.status in (GoalStatus.ACTIVE, GoalStatus.IN_PROGRESS)
        ]


@dataclass
class GoalDecomposition:
    """Result of decomposing a goal into sub-goals.

    Args:
        parent_id: ID of the decomposed goal.
        children: Generated child goals.
        decomposition_strategy: Strategy used for decomposition.
        completeness: Estimated completeness of decomposition (0.0-1.0).
    """

    parent_id: str
    children: List[Goal] = field(default_factory=list)
    decomposition_strategy: str = "recursive"
    completeness: float = 0.0


@dataclass
class GoalProgress:
    """Progress report for a goal and its subtree.

    Args:
        goal_id: The goal being reported on.
        goal_progress: Direct progress of this goal.
        subtree_progress: Aggregated progress of all children.
        total_progress: Weighted total progress.
        completed_children: Number of completed children.
        total_children: Total number of children.
        blockers: List of blocking issues.
        at_risk: Goals at risk of missing deadline.
        estimated_completion: Estimated completion timestamp.
    """

    goal_id: str
    goal_progress: float = 0.0
    subtree_progress: float = 0.0
    total_progress: float = 0.0
    completed_children: int = 0
    total_children: int = 0
    blockers: List[str] = field(default_factory=list)
    at_risk: List[str] = field(default_factory=list)
    estimated_completion: Optional[float] = None


@dataclass
class GoalSuggestion:
    """An autonomously suggested goal.

    Args:
        title: Suggested goal title.
        description: Suggested description.
        level: Suggested level.
        parent_id: Suggested parent (if any).
        reasoning: Why this goal is suggested.
        confidence: Confidence in the suggestion.
        related_goals: IDs of related existing goals.
    """

    title: str
    description: str
    level: GoalLevel
    parent_id: Optional[str] = None
    reasoning: str = ""
    confidence: float = 0.5
    related_goals: List[str] = field(default_factory=list)


class GoalSystem:
    """Goal-aware execution system with hierarchical management.

    Manages goals from mission-level down to subtasks, with automatic
    decomposition, progress tracking, dependency management, and
    autonomous goal suggestion.

    Args:
        llm_callback: Async callable for LLM interactions.
            Signature: (prompt: str) -> Awaitable[str]
        db_path: Path to SQLite database.
    """

    def __init__(
        self,
        llm_callback: Callable[[str], Awaitable[str]],
        db_path: str = "goals.db",
    ) -> None:
        self.llm_callback = llm_callback
        self.db_path = db_path
        self._cache: Dict[str, Goal] = {}
        self._init_db()

    def _init_db(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS goals (
                    id TEXT PRIMARY KEY,
                    level TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'proposed',
                    parent_id TEXT,
                    children_ids TEXT DEFAULT '[]',
                    dependencies TEXT DEFAULT '[]',
                    priority REAL DEFAULT 0.5,
                    urgency REAL DEFAULT 0.5,
                    importance REAL DEFAULT 0.5,
                    progress REAL DEFAULT 0.0,
                    blocker_reason TEXT DEFAULT '',
                    acceptance_criteria TEXT DEFAULT '[]',
                    estimated_effort REAL DEFAULT 0.0,
                    actual_effort REAL DEFAULT 0.0,
                    tags TEXT DEFAULT '[]',
                    metadata TEXT DEFAULT '{}',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    completed_at REAL,
                    deadline REAL,
                    FOREIGN KEY (parent_id) REFERENCES goals(id)
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_goals_level ON goals(level)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_goals_parent ON goals(parent_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_goals_priority ON goals(priority DESC)"
            )
            conn.commit()

    async def create_goal(
        self,
        level: GoalLevel,
        title: str,
        description: str = "",
        parent_id: Optional[str] = None,
        acceptance_criteria: Optional[List[str]] = None,
        estimated_effort: float = 0.0,
        deadline: Optional[float] = None,
        tags: Optional[List[str]] = None,
        dependencies: Optional[List[GoalDependency]] = None,
        priority: Optional[float] = None,
        urgency: Optional[float] = None,
        importance: Optional[float] = None,
    ) -> Goal:
        """Create a new goal.

        Args:
            level: Hierarchy level.
            title: Goal title.
            description: Detailed description.
            parent_id: Parent goal ID (if any).
            acceptance_criteria: Criteria for completion.
            estimated_effort: Estimated effort.
            deadline: Optional deadline.
            tags: Categorization tags.
            dependencies: Goal dependencies.
            priority: Priority score (auto-calculated if None).
            urgency: Urgency score (auto-calculated if None).
            importance: Importance score (auto-calculated if None).

        Returns:
            The created Goal.
        """
        if parent_id:
            parent = self.get_goal(parent_id)
            if parent is None:
                raise GoalError(f"Parent goal not found: {parent_id}", parent_id)
            expected_level = parent.children_level
            if expected_level and level != expected_level:
                raise GoalError(
                    f"Invalid level under {parent.level.value}: expected {expected_level.value}, got {level.value}",
                    parent_id,
                )

        if priority is None:
            priority = self._calculate_priority(urgency, importance)

        goal = Goal(
            level=level,
            title=title,
            description=description,
            parent_id=parent_id,
            acceptance_criteria=acceptance_criteria or [],
            estimated_effort=estimated_effort,
            deadline=deadline,
            tags=tags or [],
            dependencies=dependencies or [],
            priority=priority,
            urgency=urgency or 0.5,
            importance=importance or 0.5,
        )

        self._save_goal(goal)

        if parent_id:
            parent = self.get_goal(parent_id)
            if parent:
                parent.children_ids.append(goal.id)
                parent.updated_at = time.time()
                self._save_goal(parent)

        logger.info(
            "Created goal [%s] %s: %s",
            goal.level.value,
            goal.id,
            goal.title[:60],
        )
        return goal

    async def decompose(
        self,
        goal_id: str,
        max_children: int = 7,
        custom_decomposer: Optional[
            Callable[[Goal, int], Awaitable[List[Dict[str, str]]]]
        ] = None,
    ) -> GoalDecomposition:
        """Decompose a goal into child goals.

        Args:
            goal_id: ID of the goal to decompose.
            max_children: Maximum number of children to generate.
            custom_decomposer: Custom decomposition function.

        Returns:
            GoalDecomposition with generated children.
        """
        goal = self.get_goal(goal_id)
        if goal is None:
            raise GoalError(f"Goal not found: {goal_id}", goal_id)

        if goal.children_level is None:
            raise GoalError(
                f"Cannot decompose {goal.level.value} (leaf level)", goal_id
            )

        if custom_decomposer is not None:
            children_data = await custom_decomposer(goal, max_children)
        else:
            children_data = await self._generate_decomposition(goal, max_children)

        children: List[Goal] = []
        for data in children_data:
            child = await self.create_goal(
                level=goal.children_level,
                title=data.get("title", ""),
                description=data.get("description", ""),
                parent_id=goal_id,
                acceptance_criteria=data.get("acceptance_criteria"),
                estimated_effort=data.get("estimated_effort", 0.0),
                tags=data.get("tags"),
            )
            children.append(child)

        completeness = min(1.0, len(children) / max(1, max_children * 0.5))

        return GoalDecomposition(
            parent_id=goal_id,
            children=children,
            completeness=completeness,
        )

    def get_goal(self, goal_id: str) -> Optional[Goal]:
        """Get a goal by ID."""
        if goal_id in self._cache:
            return self._cache[goal_id]

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM goals WHERE id = ?", (goal_id,)
            ).fetchone()

        if row:
            goal = Goal.from_dict(dict(row))
            self._cache[goal_id] = goal
            return goal
        return None

    def get_hierarchy(self, root_id: str) -> Optional[GoalHierarchy]:
        """Get the full hierarchy tree for a root goal.

        Args:
            root_id: ID of the root goal.

        Returns:
            GoalHierarchy or None if root not found.
        """
        root = self.get_goal(root_id)
        if root is None:
            return None

        descendants: List[Goal] = []
        queue = list(root.children_ids)
        max_depth = 0

        while queue:
            child_id = queue.pop(0)
            child = self.get_goal(child_id)
            if child:
                descendants.append(child)
                depth = child.level.depth - root.level.depth
                max_depth = max(max_depth, depth)
                queue.extend(child.children_ids)

        total_progress = self._calculate_subtree_progress(root)

        return GoalHierarchy(
            root=root,
            descendants=descendants,
            depth=max_depth,
            total_progress=total_progress,
        )

    def get_progress(self, goal_id: str) -> Optional[GoalProgress]:
        """Get progress report for a goal and its subtree.

        Args:
            goal_id: ID of the goal.

        Returns:
            GoalProgress or None if goal not found.
        """
        goal = self.get_goal(goal_id)
        if goal is None:
            return None

        children_progress = []
        blockers: List[str] = []
        at_risk: List[str] = []
        completed = 0

        for child_id in goal.children_ids:
            child = self.get_goal(child_id)
            if child:
                if child.status == GoalStatus.COMPLETED:
                    completed += 1
                elif child.status == GoalStatus.BLOCKED:
                    blockers.append(
                        f"{child.title}: {child.blocker_reason or 'blocked'}"
                    )

                if child.deadline and child.status not in (
                    GoalStatus.COMPLETED,
                    GoalStatus.CANCELLED,
                ):
                    if child.deadline < time.time() + 86400:
                        at_risk.append(child.title)

                cp = self.get_progress(child_id)
                if cp:
                    children_progress.append(cp.total_progress)

        subtree_progress = (
            sum(children_progress) / len(children_progress)
            if children_progress
            else 0.0
        )

        if goal.children_ids:
            total = goal.progress * 0.3 + subtree_progress * 0.7
        else:
            total = goal.progress

        estimated_completion = None
        if goal.deadline:
            estimated_completion = goal.deadline
        elif children_progress:
            avg_rate = sum(children_progress) / max(len(children_progress), 1)
            if avg_rate > 0:
                remaining = (1.0 - total) / avg_rate
                estimated_completion = time.time() + remaining * 86400

        return GoalProgress(
            goal_id=goal_id,
            goal_progress=goal.progress,
            subtree_progress=subtree_progress,
            total_progress=total,
            completed_children=completed,
            total_children=len(goal.children_ids),
            blockers=blockers,
            at_risk=at_risk,
            estimated_completion=estimated_completion,
        )

    async def update_progress(
        self, goal_id: str, progress: float, actual_effort: float = 0.0
    ) -> Optional[Goal]:
        """Update a goal's progress.

        Args:
            goal_id: ID of the goal.
            progress: New progress value (0.0-1.0).
            actual_effort: Additional effort spent.

        Returns:
            Updated goal or None if not found.
        """
        goal = self.get_goal(goal_id)
        if goal is None:
            return None

        goal.progress = max(0.0, min(1.0, progress))
        goal.actual_effort += actual_effort
        goal.updated_at = time.time()

        if goal.progress >= 1.0 and goal.status != GoalStatus.COMPLETED:
            goal.status = GoalStatus.COMPLETED
            goal.completed_at = time.time()

        self._save_goal(goal)

        if goal.parent_id:
            await self._propagate_progress(goal.parent_id)

        return goal

    async def update_status(
        self, goal_id: str, status: GoalStatus, reason: str = ""
    ) -> Optional[Goal]:
        """Update a goal's status.

        Args:
            goal_id: ID of the goal.
            status: New status.
            reason: Reason for the change.

        Returns:
            Updated goal or None if not found.
        """
        goal = self.get_goal(goal_id)
        if goal is None:
            return None

        goal.status = status
        goal.updated_at = time.time()

        if status == GoalStatus.BLOCKED:
            goal.blocker_reason = reason
        elif status == GoalStatus.COMPLETED:
            goal.completed_at = time.time()
            goal.progress = 1.0

        self._save_goal(goal)

        if goal.parent_id:
            await self._propagate_progress(goal.parent_id)

        return goal

    def get_prioritized_goals(
        self,
        level: Optional[GoalLevel] = None,
        status: Optional[GoalStatus] = None,
        limit: int = 20,
    ) -> List[Goal]:
        """Get goals sorted by priority.

        Args:
            level: Filter by level.
            status: Filter by status.
            limit: Maximum results.

        Returns:
            List of goals sorted by priority (highest first).
        """
        goals = self.get_all_goals(level=level, status=status)
        goals.sort(key=lambda g: g.priority, reverse=True)
        return goals[:limit]

    def get_all_goals(
        self,
        level: Optional[GoalLevel] = None,
        status: Optional[GoalStatus] = None,
        tag: Optional[str] = None,
    ) -> List[Goal]:
        """Get all goals with optional filters.

        Args:
            level: Filter by level.
            status: Filter by status.
            tag: Filter by tag.

        Returns:
            List of matching goals.
        """
        query = "SELECT * FROM goals WHERE 1=1"
        params: List[Any] = []

        if level:
            query += " AND level = ?"
            params.append(level.value)
        if status:
            query += " AND status = ?"
            params.append(status.value)
        if tag:
            query += " AND tags LIKE ?"
            params.append(f'%"{tag}"%')

        query += " ORDER BY priority DESC, created_at DESC"

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()

        return [Goal.from_dict(dict(r)) for r in rows]

    def trace_ancestry(self, goal_id: str) -> List[Goal]:
        """Trace the full ancestry chain of a goal.

        Args:
            goal_id: ID of the goal.

        Returns:
            List of goals from root to the target goal.
        """
        chain: List[Goal] = []
        current = self.get_goal(goal_id)

        while current:
            chain.append(current)
            if current.parent_id is None:
                break
            current = self.get_goal(current.parent_id)

        chain.reverse()
        return chain

    def get_why(self, goal_id: str) -> str:
        """Get the "why" for a goal by tracing its ancestry.

        Args:
            goal_id: ID of the goal.

        Returns:
            Human-readable explanation of why this goal exists.
        """
        ancestry = self.trace_ancestry(goal_id)
        if not ancestry:
            return "Unknown (goal not found)"

        lines = []
        for goal in ancestry:
            indent = "  " * goal.level.depth
            lines.append(f"{indent}[{goal.level.value}] {goal.title}")
            if goal.description:
                lines.append(f"{indent}  -> {goal.description[:100]}")

        return "\n".join(lines)

    async def verify_completion(self, goal_id: str) -> Tuple[bool, str]:
        """Verify if a goal is truly complete.

        Args:
            goal_id: ID of the goal to verify.

        Returns:
            Tuple of (is_complete, verification_message).
        """
        goal = self.get_goal(goal_id)
        if goal is None:
            return False, "Goal not found"

        if goal.status != GoalStatus.COMPLETED:
            return False, f"Status is {goal.status.value}, not completed"

        if goal.acceptance_criteria:
            prompt = self._build_verification_prompt(goal)
            try:
                text = await self.llm_callback(prompt)
                lower = text.lower()
                if any(kw in lower for kw in ["yes", "confirmed", "complete", "true"]):
                    return True, "All acceptance criteria verified"
                return False, text.strip()
            except Exception as e:
                return False, f"Verification failed: {e}"

        if goal.children_ids:
            progress = self.get_progress(goal_id)
            if progress and progress.total_progress >= 0.95:
                return True, "All children completed"
            return False, f"Children only {progress.total_progress:.0%} complete" if progress else "No progress data"

        return goal.progress >= 0.9, f"Progress: {goal.progress:.0%}"

    async def suggest_goals(
        self, context: str = "", limit: int = 5
    ) -> List[GoalSuggestion]:
        """Autonomously suggest goals based on patterns.

        Args:
            context: Current context or situation.
            limit: Maximum suggestions.

        Returns:
            List of suggested goals.
        """
        recent = self.get_all_goals(status=GoalStatus.COMPLETED, limit=30)
        active = self.get_all_goals(
            status=GoalStatus.ACTIVE, limit=20
        )

        prompt = self._build_suggestion_prompt(context, recent, active)
        try:
            text = await self.llm_callback(prompt)
            return self._parse_suggestions(text, limit)
        except Exception as e:
            logger.warning("Goal suggestion failed: %s", e)
            return []

    def get_stats(self) -> Dict[str, Any]:
        """Get goal system statistics.

        Returns:
            Dict with statistics.
        """
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM goals").fetchone()[0]

            by_level = {}
            for row in conn.execute(
                "SELECT level, COUNT(*) FROM goals GROUP BY level"
            ):
                by_level[row[0]] = row[1]

            by_status = {}
            for row in conn.execute(
                "SELECT status, COUNT(*) FROM goals GROUP BY status"
            ):
                by_status[row[0]] = row[1]

            avg_progress = conn.execute(
                "SELECT AVG(progress) FROM goals"
            ).fetchone()[0] or 0.0

            blocked = conn.execute(
                "SELECT COUNT(*) FROM goals WHERE status = 'blocked'"
            ).fetchone()[0]

        return {
            "total_goals": total,
            "by_level": by_level,
            "by_status": by_status,
            "avg_progress": round(avg_progress, 3),
            "blocked_count": blocked,
            "cache_size": len(self._cache),
        }

    def _save_goal(self, goal: Goal) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO goals (
                    id, level, title, description, status, parent_id,
                    children_ids, dependencies, priority, urgency, importance,
                    progress, blocker_reason, acceptance_criteria,
                    estimated_effort, actual_effort, tags, metadata,
                    created_at, updated_at, completed_at, deadline
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    goal.id,
                    goal.level.value,
                    goal.title,
                    goal.description,
                    goal.status.value,
                    goal.parent_id,
                    json.dumps(goal.children_ids),
                    json.dumps(
                        [
                            {
                                "goal_id": d.goal_id,
                                "depends_on_id": d.depends_on_id,
                                "dependency_type": d.dependency_type,
                            }
                            for d in goal.dependencies
                        ]
                    ),
                    goal.priority,
                    goal.urgency,
                    goal.importance,
                    goal.progress,
                    goal.blocker_reason,
                    json.dumps(goal.acceptance_criteria),
                    goal.estimated_effort,
                    goal.actual_effort,
                    json.dumps(goal.tags),
                    json.dumps(goal.metadata),
                    goal.created_at,
                    goal.updated_at,
                    goal.completed_at,
                    goal.deadline,
                ),
            )
            conn.commit()

        self._cache[goal.id] = goal

    async def _propagate_progress(self, parent_id: str) -> None:
        parent = self.get_goal(parent_id)
        if not parent or not parent.children_ids:
            return

        child_progress = []
        for child_id in parent.children_ids:
            child = self.get_goal(child_id)
            if child:
                child_progress.append(child.progress)

        if child_progress:
            avg = sum(child_progress) / len(child_progress)
            parent.progress = avg
            parent.updated_at = time.time()

            if all(
                self.get_goal(cid)
                and self.get_goal(cid).status == GoalStatus.COMPLETED
                for cid in parent.children_ids
            ):
                parent.status = GoalStatus.COMPLETED
                parent.completed_at = time.time()

            self._save_goal(parent)

            if parent.parent_id:
                await self._propagate_progress(parent.parent_id)

    def _calculate_priority(
        self,
        urgency: Optional[float],
        importance: Optional[float],
    ) -> float:
        u = urgency or 0.5
        i = importance or 0.5
        return (u * 0.4 + i * 0.6)

    def _calculate_subtree_progress(self, goal: Goal) -> float:
        if not goal.children_ids:
            return goal.progress

        child_progress = []
        for child_id in goal.children_ids:
            child = self.get_goal(child_id)
            if child:
                child_progress.append(self._calculate_subtree_progress(child))

        if child_progress:
            return sum(child_progress) / len(child_progress)
        return goal.progress

    async def _generate_decomposition(
        self, goal: Goal, max_children: int
    ) -> List[Dict[str, str]]:
        prompt = self._build_decomposition_prompt(goal, max_children)
        try:
            text = await self.llm_callback(prompt)
            return self._parse_decomposition(text)
        except Exception as e:
            logger.warning("Decomposition generation failed: %s", e)
            return []

    def _build_decomposition_prompt(
        self, goal: Goal, max_children: int
    ) -> str:
        return (
            f"Goal to decompose: {goal.title}\n"
            f"Level: {goal.level.value}\n"
            f"Description: {goal.description}\n\n"
            f"Break this {goal.level.value} into {max_children} or fewer "
            f"{goal.children_level.value if goal.children_level else 'subtasks'} "
            f"that together achieve the parent goal.\n\n"
            f"Each child should be:\n"
            f"- Specific and actionable\n"
            f"- Independently completable\n"
            f"- Together covering the full scope\n\n"
            f"Format:\n"
            f"TITLE: <child title>\n"
            f"DESCRIPTION: <child description>\n"
            f"CRITERIA: <acceptance criteria>\n"
            f"EFFORT: <estimated effort in hours>\n\n"
            f"(repeat for each child)\n"
        )

    def _parse_decomposition(self, text: str) -> List[Dict[str, str]]:
        children: List[Dict[str, str]] = []
        current: Dict[str, str] = {}

        for line in text.strip().split("\n"):
            line = line.strip()
            if line.upper().startswith("TITLE:"):
                if current.get("title"):
                    children.append(current)
                current = {"title": line[6:].strip()}
            elif line.upper().startswith("DESCRIPTION:"):
                current["description"] = line[12:].strip()
            elif line.upper().startswith("CRITERIA:"):
                current["acceptance_criteria"] = line[9:].strip()
            elif line.upper().startswith("EFFORT:"):
                current["estimated_effort"] = line[7:].strip()

        if current.get("title"):
            children.append(current)

        return children

    def _build_verification_prompt(self, goal: Goal) -> str:
        criteria = "\n".join(f"- {c}" for c in goal.acceptance_criteria)
        return (
            f"Goal: {goal.title}\n"
            f"Description: {goal.description}\n\n"
            f"Acceptance criteria:\n{criteria}\n\n"
            f"Has this goal been fully completed? Answer yes or no, "
            f"and explain any criteria that are not met.\n\n"
            f"Answer: "
        )

    def _build_suggestion_prompt(
        self,
        context: str,
        recent: List[Goal],
        active: List[Goal],
    ) -> str:
        lines = [
            "Based on the current state of goals, suggest new goals that"
            " would be valuable to pursue.\n\n",
            f"Context: {context}\n\n",
            "Recently completed goals:",
        ]
        for g in recent[:10]:
            lines.append(f"  - [{g.level.value}] {g.title}")

        lines.append("\nActive goals:")
        for g in active[:10]:
            lines.append(f"  - [{g.level.value}] {g.title} ({g.progress:.0%})")

        lines.append(
            "\n\nSuggest up to 5 new goals. Format:\n"
            "TITLE: <goal title>\n"
            "LEVEL: <mission|objective|task|subtask>\n"
            "DESCRIPTION: <description>\n"
            "REASONING: <why this goal is valuable>\n"
            "CONFIDENCE: <0.0-1.0>\n\n"
            "(repeat for each suggestion)\n"
        )

        return "\n".join(lines)

    def _parse_suggestions(
        self, text: str, limit: int
    ) -> List[GoalSuggestion]:
        suggestions: List[GoalSuggestion] = []
        current: Dict[str, str] = {}

        for line in text.strip().split("\n"):
            line = line.strip()
            if line.upper().startswith("TITLE:"):
                if current.get("title"):
                    suggestions.append(self._build_suggestion_from_dict(current))
                current = {"title": line[6:].strip()}
            elif line.upper().startswith("LEVEL:"):
                current["level"] = line[6:].strip()
            elif line.upper().startswith("DESCRIPTION:"):
                current["description"] = line[12:].strip()
            elif line.upper().startswith("REASONING:"):
                current["reasoning"] = line[10:].strip()
            elif line.upper().startswith("CONFIDENCE:"):
                current["confidence"] = line[11:].strip()

        if current.get("title"):
            suggestions.append(self._build_suggestion_from_dict(current))

        return suggestions[:limit]

    def _build_suggestion_from_dict(
        self, data: Dict[str, str]
    ) -> GoalSuggestion:
        level_str = data.get("level", "task").lower()
        try:
            level = GoalLevel(level_str)
        except ValueError:
            level = GoalLevel.TASK

        try:
            confidence = float(data.get("confidence", "0.5"))
        except ValueError:
            confidence = 0.5

        return GoalSuggestion(
            title=data.get("title", ""),
            description=data.get("description", ""),
            level=level,
            reasoning=data.get("reasoning", ""),
            confidence=confidence,
        )
