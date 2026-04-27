#!/usr/bin/env python3
"""
NEUGI v2 - Strategic Planner
=============================

Long-term multi-step planning with milestone tracking, resource allocation,
risk assessment, plan adaptation, and text-based visualization.

Key features:
- Long-term planning (multi-step, multi-day)
- Milestone tracking with progress monitoring
- Resource allocation planning
- Risk assessment and mitigation strategies
- Plan adaptation based on new information
- Plan visualization (text-based Gantt chart)
- Plan quality scoring

Usage:
    planner = StrategicPlanner(llm_callback, db_path="plans.db")
    plan = await planner.create_plan(
        title="Launch new product feature",
        description="Build and ship user authentication system",
        horizon_days=30,
    )
    await planner.add_milestone(plan.id, "Design complete", day=5)
    risk = await planner.assess_risks(plan.id)
    chart = planner.visualize(plan.id)
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk severity level."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def numeric(self) -> int:
        return {"low": 1, "medium": 2, "high": 3, "critical": 4}[self.value]

    @property
    def color(self) -> str:
        return {"low": "green", "medium": "yellow", "high": "red", "critical": "red"}[
            self.value
        ]


class PlanPhase(Enum):
    """Phase of a plan's lifecycle."""

    DRAFT = "draft"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class PlanError(Exception):
    """Error in strategic planning operations."""

    def __init__(self, message: str, plan_id: Optional[str] = None) -> None:
        super().__init__(message)
        self.plan_id = plan_id


@dataclass
class Milestone:
    """A significant checkpoint in a plan.

    Args:
        id: Unique identifier.
        plan_id: ID of the parent plan.
        title: Milestone title.
        description: Detailed description.
        target_day: Target day number (from plan start).
        actual_day: Actual completion day (if completed).
        status: Current status.
        deliverables: Expected deliverables.
        dependencies: IDs of milestones this depends on.
        progress: Completion progress (0.0-1.0).
        notes: Additional notes.
        created_at: Creation timestamp.
        completed_at: Completion timestamp.
    """

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    plan_id: str = ""
    title: str = ""
    description: str = ""
    target_day: int = 0
    actual_day: Optional[int] = None
    status: str = "pending"
    deliverables: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    progress: float = 0.0
    notes: str = ""
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    @property
    def is_overdue(self) -> bool:
        if self.status in ("completed", "cancelled"):
            return False
        return False

    @property
    def is_on_track(self) -> bool:
        if self.status == "completed":
            return True
        if self.target_day > 0:
            expected_progress = min(1.0, self.target_day / max(1, self.target_day))
            return self.progress >= expected_progress * 0.8
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "plan_id": self.plan_id,
            "title": self.title,
            "description": self.description,
            "target_day": self.target_day,
            "actual_day": self.actual_day,
            "status": self.status,
            "deliverables": json.dumps(self.deliverables),
            "dependencies": json.dumps(self.dependencies),
            "progress": self.progress,
            "notes": self.notes,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Milestone":
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

        return cls(
            id=data.get("id", ""),
            plan_id=data.get("plan_id", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            target_day=int(data.get("target_day", 0)),
            actual_day=data.get("actual_day"),
            status=data.get("status", "pending"),
            deliverables=_parse_json("deliverables", []),
            dependencies=_parse_json("dependencies", []),
            progress=float(data.get("progress", 0.0)),
            notes=data.get("notes", ""),
            created_at=float(data.get("created_at", time.time())),
            completed_at=data.get("completed_at"),
        )


@dataclass
class ResourceAllocation:
    """Resource allocation for a plan.

    Args:
        resource_type: Type of resource (human, compute, budget, etc.).
        name: Resource name.
        allocation: Amount allocated.
        unit: Unit of measurement.
        start_day: Start day of allocation.
        end_day: End day of allocation.
        utilization: Current utilization (0.0-1.0).
        notes: Additional notes.
    """

    resource_type: str = ""
    name: str = ""
    allocation: float = 0.0
    unit: str = ""
    start_day: int = 0
    end_day: int = 0
    utilization: float = 0.0
    notes: str = ""


@dataclass
class RiskAssessment:
    """Risk assessment for a plan.

    Args:
        risk_id: Unique identifier.
        plan_id: ID of the parent plan.
        description: Description of the risk.
        category: Risk category.
        probability: Probability of occurrence (0.0-1.0).
        impact: Impact severity if it occurs (0.0-1.0).
        risk_level: Computed risk level.
        mitigation: Mitigation strategy.
        contingency: Contingency plan.
        owner: Responsible party.
        status: Current status.
        created_at: Creation timestamp.
    """

    risk_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    plan_id: str = ""
    description: str = ""
    category: str = ""
    probability: float = 0.0
    impact: float = 0.0
    risk_level: RiskLevel = RiskLevel.LOW
    mitigation: str = ""
    contingency: str = ""
    owner: str = ""
    status: str = "identified"
    created_at: float = field(default_factory=time.time)

    @property
    def risk_score(self) -> float:
        return self.probability * self.impact

    @classmethod
    def from_probability_impact(
        cls,
        plan_id: str,
        description: str,
        probability: float,
        impact: float,
        **kwargs,
    ) -> "RiskAssessment":
        score = probability * impact
        if score >= 0.7:
            level = RiskLevel.CRITICAL
        elif score >= 0.4:
            level = RiskLevel.HIGH
        elif score >= 0.15:
            level = RiskLevel.MEDIUM
        else:
            level = RiskLevel.LOW

        return cls(
            plan_id=plan_id,
            description=description,
            probability=probability,
            impact=impact,
            risk_level=level,
            **kwargs,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk_id": self.risk_id,
            "plan_id": self.plan_id,
            "description": self.description,
            "category": self.category,
            "probability": self.probability,
            "impact": self.impact,
            "risk_level": self.risk_level.value,
            "mitigation": self.mitigation,
            "contingency": self.contingency,
            "owner": self.owner,
            "status": self.status,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RiskAssessment":
        level_str = data.get("risk_level", "low")
        try:
            level = RiskLevel(level_str)
        except ValueError:
            level = RiskLevel.LOW

        return cls(
            risk_id=data.get("risk_id", ""),
            plan_id=data.get("plan_id", ""),
            description=data.get("description", ""),
            category=data.get("category", ""),
            probability=float(data.get("probability", 0.0)),
            impact=float(data.get("impact", 0.0)),
            risk_level=level,
            mitigation=data.get("mitigation", ""),
            contingency=data.get("contingency", ""),
            owner=data.get("owner", ""),
            status=data.get("status", "identified"),
            created_at=float(data.get("created_at", time.time())),
        )


@dataclass
class StrategicPlan:
    """A strategic plan with milestones, resources, and risks.

    Args:
        id: Unique identifier.
        title: Plan title.
        description: Detailed description.
        phase: Current phase.
        horizon_days: Total planning horizon in days.
        start_date: Plan start date (epoch timestamp).
        current_day: Current day number.
        milestones: List of milestones.
        resources: List of resource allocations.
        risks: List of risk assessments.
        metadata: Arbitrary metadata.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
        completed_at: Completion timestamp.
    """

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    title: str = ""
    description: str = ""
    phase: PlanPhase = PlanPhase.DRAFT
    horizon_days: int = 30
    start_date: float = field(default_factory=time.time)
    current_day: int = 0
    milestones: List[Milestone] = field(default_factory=list)
    resources: List[ResourceAllocation] = field(default_factory=list)
    risks: List[RiskAssessment] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    @property
    def progress(self) -> float:
        if not self.milestones:
            return 0.0
        completed = sum(1 for m in self.milestones if m.status == "completed")
        return completed / len(self.milestones)

    @property
    def days_remaining(self) -> int:
        return max(0, self.horizon_days - self.current_day)

    @property
    def is_overdue(self) -> bool:
        return self.current_day > self.horizon_days and self.phase not in (
            PlanPhase.COMPLETED,
            PlanPhase.CANCELLED,
        )


@dataclass
class PlanQualityReport:
    """Quality assessment of a strategic plan.

    Args:
        plan_id: ID of the assessed plan.
        overall_score: Overall quality score (0.0-1.0).
        completeness: How complete the plan is.
        specificity: How specific and actionable the plan is.
        risk_coverage: How well risks are identified and mitigated.
        resource_alignment: How well resources match plan needs.
        milestone_spacing: How well milestones are distributed.
        issues: List of quality issues found.
        recommendations: List of improvement recommendations.
    """

    plan_id: str
    overall_score: float = 0.0
    completeness: float = 0.0
    specificity: float = 0.0
    risk_coverage: float = 0.0
    resource_alignment: float = 0.0
    milestone_spacing: float = 0.0
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class PlanVisualization:
    """Text-based visualization of a plan.

    Args:
        plan_id: ID of the plan.
        gantt_chart: Text-based Gantt chart representation.
        summary: Text summary of the plan.
        risk_heatmap: Text-based risk heatmap.
    """

    plan_id: str
    gantt_chart: str = ""
    summary: str = ""
    risk_heatmap: str = ""


class StrategicPlanner:
    """Strategic planning system for long-term multi-step planning.

    Creates and manages strategic plans with milestones, resource allocation,
    risk assessment, and plan adaptation. Supports text-based visualization
    and quality scoring.

    Args:
        llm_callback: Async callable for LLM interactions.
            Signature: (prompt: str) -> Awaitable[str]
        db_path: Path to SQLite database.
    """

    def __init__(
        self,
        llm_callback: Callable[[str], Awaitable[str]],
        db_path: str = "plans.db",
    ) -> None:
        self.llm_callback = llm_callback
        self.db_path = db_path
        self._plan_cache: Dict[str, StrategicPlan] = {}
        self._init_db()

    def _init_db(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS plans (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    phase TEXT NOT NULL DEFAULT 'draft',
                    horizon_days INTEGER DEFAULT 30,
                    start_date REAL NOT NULL,
                    current_day INTEGER DEFAULT 0,
                    metadata TEXT DEFAULT '{}',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    completed_at REAL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS milestones (
                    id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    target_day INTEGER DEFAULT 0,
                    actual_day INTEGER,
                    status TEXT DEFAULT 'pending',
                    deliverables TEXT DEFAULT '[]',
                    dependencies TEXT DEFAULT '[]',
                    progress REAL DEFAULT 0.0,
                    notes TEXT DEFAULT '',
                    created_at REAL NOT NULL,
                    completed_at REAL,
                    FOREIGN KEY (plan_id) REFERENCES plans(id)
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_milestones_plan ON milestones(plan_id)"
            )
            conn.execute("""
                CREATE TABLE IF NOT EXISTS resources (
                    id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    allocation REAL DEFAULT 0.0,
                    unit TEXT DEFAULT '',
                    start_day INTEGER DEFAULT 0,
                    end_day INTEGER DEFAULT 0,
                    utilization REAL DEFAULT 0.0,
                    notes TEXT DEFAULT '',
                    FOREIGN KEY (plan_id) REFERENCES plans(id)
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_resources_plan ON resources(plan_id)"
            )
            conn.execute("""
                CREATE TABLE IF NOT EXISTS risks (
                    risk_id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    description TEXT NOT NULL,
                    category TEXT DEFAULT '',
                    probability REAL DEFAULT 0.0,
                    impact REAL DEFAULT 0.0,
                    risk_level TEXT DEFAULT 'low',
                    mitigation TEXT DEFAULT '',
                    contingency TEXT DEFAULT '',
                    owner TEXT DEFAULT '',
                    status TEXT DEFAULT 'identified',
                    created_at REAL NOT NULL,
                    FOREIGN KEY (plan_id) REFERENCES plans(id)
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_risks_plan ON risks(plan_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_risks_level ON risks(risk_level)"
            )
            conn.commit()

    async def create_plan(
        self,
        title: str,
        description: str = "",
        horizon_days: int = 30,
        milestones: Optional[List[Dict[str, Any]]] = None,
        resources: Optional[List[ResourceAllocation]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> StrategicPlan:
        """Create a new strategic plan.

        Args:
            title: Plan title.
            description: Detailed description.
            horizon_days: Planning horizon in days.
            milestones: Initial milestones.
            resources: Initial resource allocations.
            metadata: Arbitrary metadata.

        Returns:
            The created StrategicPlan.
        """
        plan = StrategicPlan(
            title=title,
            description=description,
            horizon_days=horizon_days,
            start_date=time.time(),
            metadata=metadata or {},
        )

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO plans (
                    id, title, description, phase, horizon_days,
                    start_date, current_day, metadata, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan.id,
                    plan.title,
                    plan.description,
                    plan.phase.value,
                    plan.horizon_days,
                    plan.start_date,
                    plan.current_day,
                    json.dumps(plan.metadata),
                    plan.created_at,
                    plan.updated_at,
                ),
            )

            if milestones:
                for m_data in milestones:
                    m = Milestone(
                        plan_id=plan.id,
                        title=m_data.get("title", ""),
                        description=m_data.get("description", ""),
                        target_day=m_data.get("target_day", 0),
                        deliverables=m_data.get("deliverables", []),
                        dependencies=m_data.get("dependencies", []),
                    )
                    self._save_milestone(m)
                    plan.milestones.append(m)

            if resources:
                for r in resources:
                    r_id = uuid.uuid4().hex[:12]
                    conn.execute(
                        """
                        INSERT INTO resources (
                            id, plan_id, resource_type, name, allocation,
                            unit, start_day, end_day, utilization, notes
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            r_id,
                            plan.id,
                            r.resource_type,
                            r.name,
                            r.allocation,
                            r.unit,
                            r.start_day,
                            r.end_day,
                            r.utilization,
                            r.notes,
                        ),
                    )
                    plan.resources.append(r)

            conn.commit()

        self._plan_cache[plan.id] = plan
        logger.info("Created plan [%s] %s", plan.id, plan.title[:60])
        return plan

    async def generate_plan(
        self,
        objective: str,
        context: str = "",
        horizon_days: int = 30,
        custom_generator: Optional[
            Callable[[str, str, int], Awaitable[Dict[str, Any]]]
        ] = None,
    ) -> StrategicPlan:
        """Generate a strategic plan from an objective using LLM.

        Args:
            objective: What needs to be achieved.
            context: Additional context.
            horizon_days: Planning horizon.
            custom_generator: Custom plan generation function.

        Returns:
            Generated StrategicPlan.
        """
        if custom_generator is not None:
            plan_data = await custom_generator(objective, context, horizon_days)
        else:
            plan_data = await self._llm_generate_plan(objective, context, horizon_days)

        title = plan_data.get("title", objective[:80])
        description = plan_data.get("description", objective)
        milestones_data = plan_data.get("milestones", [])
        resources_data = plan_data.get("resources", [])
        risks_data = plan_data.get("risks", [])

        resources = [
            ResourceAllocation(
                resource_type=r.get("resource_type", ""),
                name=r.get("name", ""),
                allocation=r.get("allocation", 0.0),
                unit=r.get("unit", ""),
                start_day=r.get("start_day", 0),
                end_day=r.get("end_day", 0),
                utilization=r.get("utilization", 0.0),
                notes=r.get("notes", ""),
            )
            for r in resources_data
        ]

        plan = await self.create_plan(
            title=title,
            description=description,
            horizon_days=horizon_days,
            milestones=milestones_data,
            resources=resources,
        )

        for r_data in risks_data:
            risk = RiskAssessment.from_probability_impact(
                plan_id=plan.id,
                description=r_data.get("description", ""),
                probability=r_data.get("probability", 0.3),
                impact=r_data.get("impact", 0.3),
                category=r_data.get("category", ""),
                mitigation=r_data.get("mitigation", ""),
                contingency=r_data.get("contingency", ""),
            )
            self._save_risk(risk)
            plan.risks.append(risk)

        return plan

    async def add_milestone(
        self,
        plan_id: str,
        title: str,
        target_day: int,
        description: str = "",
        deliverables: Optional[List[str]] = None,
        dependencies: Optional[List[str]] = None,
    ) -> Milestone:
        """Add a milestone to a plan.

        Args:
            plan_id: ID of the plan.
            title: Milestone title.
            target_day: Target day number.
            description: Description.
            deliverables: Expected deliverables.
            dependencies: Dependent milestone IDs.

        Returns:
            The created Milestone.
        """
        plan = self.get_plan(plan_id)
        if plan is None:
            raise PlanError(f"Plan not found: {plan_id}", plan_id)

        milestone = Milestone(
            plan_id=plan_id,
            title=title,
            description=description,
            target_day=target_day,
            deliverables=deliverables or [],
            dependencies=dependencies or [],
        )

        self._save_milestone(milestone)
        plan.milestones.append(milestone)
        plan.updated_at = time.time()
        self._update_plan(plan)

        return milestone

    async def update_milestone_progress(
        self, milestone_id: str, progress: float
    ) -> Optional[Milestone]:
        """Update milestone progress.

        Args:
            milestone_id: ID of the milestone.
            progress: New progress (0.0-1.0).

        Returns:
            Updated milestone or None.
        """
        milestone = self._get_milestone(milestone_id)
        if milestone is None:
            return None

        milestone.progress = max(0.0, min(1.0, progress))
        if progress >= 1.0 and milestone.status != "completed":
            milestone.status = "completed"
            milestone.completed_at = time.time()
            milestone.actual_day = milestone.target_day

        self._save_milestone(milestone)
        return milestone

    async def advance_day(self, plan_id: str, days: int = 1) -> Optional[StrategicPlan]:
        """Advance the plan's current day.

        Args:
            plan_id: ID of the plan.
            days: Number of days to advance.

        Returns:
            Updated plan or None.
        """
        plan = self.get_plan(plan_id)
        if plan is None:
            return None

        plan.current_day += days
        plan.updated_at = time.time()

        if plan.current_day >= plan.horizon_days:
            if plan.progress >= 0.95:
                plan.phase = PlanPhase.COMPLETED
                plan.completed_at = time.time()
            else:
                plan.phase = PlanPhase.FAILED

        self._update_plan(plan)
        return plan

    async def assess_risks(
        self,
        plan_id: str,
        custom_assessor: Optional[
            Callable[[StrategicPlan], Awaitable[List[Dict[str, Any]]]]
        ] = None,
    ) -> List[RiskAssessment]:
        """Assess risks for a plan.

        Args:
            plan_id: ID of the plan.
            custom_assessor: Custom risk assessment function.

        Returns:
            List of risk assessments.
        """
        plan = self.get_plan(plan_id)
        if plan is None:
            raise PlanError(f"Plan not found: {plan_id}", plan_id)

        if custom_assessor is not None:
            risk_data = await custom_assessor(plan)
        else:
            risk_data = await self._llm_assess_risks(plan)

        risks: List[RiskAssessment] = []
        for r_data in risk_data:
            risk = RiskAssessment.from_probability_impact(
                plan_id=plan_id,
                description=r_data.get("description", ""),
                probability=r_data.get("probability", 0.3),
                impact=r_data.get("impact", 0.3),
                category=r_data.get("category", ""),
                mitigation=r_data.get("mitigation", ""),
                contingency=r_data.get("contingency", ""),
                owner=r_data.get("owner", ""),
            )
            self._save_risk(risk)
            risks.append(risk)
            plan.risks.append(risk)

        plan.updated_at = time.time()
        self._update_plan(plan)
        return risks

    async def adapt_plan(
        self,
        plan_id: str,
        new_information: str,
        custom_adapter: Optional[
            Callable[[StrategicPlan, str], Awaitable[Dict[str, Any]]]
        ] = None,
    ) -> Optional[StrategicPlan]:
        """Adapt a plan based on new information.

        Args:
            plan_id: ID of the plan.
            new_information: New information affecting the plan.
            custom_adapter: Custom adaptation function.

        Returns:
            Adapted plan or None.
        """
        plan = self.get_plan(plan_id)
        if plan is None:
            return None

        if custom_adapter is not None:
            adaptation = await custom_adapter(plan, new_information)
        else:
            adaptation = await self._llm_adapt_plan(plan, new_information)

        if adaptation.get("phase_change"):
            try:
                plan.phase = PlanPhase(adaptation["phase_change"])
            except (ValueError, KeyError):
                pass

        if adaptation.get("new_milestones"):
            for m_data in adaptation["new_milestones"]:
                await self.add_milestone(
                    plan_id,
                    m_data.get("title", ""),
                    m_data.get("target_day", plan.horizon_days),
                    m_data.get("description", ""),
                )

        if adaptation.get("milestone_changes"):
            for change in adaptation["milestone_changes"]:
                m_id = change.get("milestone_id")
                if m_id:
                    m = self._get_milestone(m_id)
                    if m:
                        if "target_day" in change:
                            m.target_day = change["target_day"]
                        if "status" in change:
                            m.status = change["status"]
                        self._save_milestone(m)

        if adaptation.get("risk_updates"):
            for r_data in adaptation["risk_updates"]:
                r_id = r_data.get("risk_id")
                if r_id:
                    r = self._get_risk(r_id)
                    if r:
                        if "probability" in r_data:
                            r.probability = r_data["probability"]
                        if "impact" in r_data:
                            r.impact = r_data["impact"]
                        if "mitigation" in r_data:
                            r.mitigation = r_data["mitigation"]
                        r.risk_level = RiskAssessment.from_probability_impact(
                            r.plan_id, r.description, r.probability, r.impact
                        ).risk_level
                        self._save_risk(r)

        plan.updated_at = time.time()
        self._update_plan(plan)
        return plan

    def get_plan(self, plan_id: str) -> Optional[StrategicPlan]:
        """Get a plan by ID."""
        if plan_id in self._plan_cache:
            plan = self._plan_cache[plan_id]
            plan.milestones = self._get_milestones(plan_id)
            plan.resources = self._get_resources(plan_id)
            plan.risks = self._get_risks(plan_id)
            return plan

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM plans WHERE id = ?", (plan_id,)
            ).fetchone()

        if row:
            data = dict(row)
            plan = StrategicPlan(
                id=data["id"],
                title=data["title"],
                description=data["description"],
                phase=PlanPhase(data["phase"]),
                horizon_days=data["horizon_days"],
                start_date=data["start_date"],
                current_day=data["current_day"],
                metadata=json.loads(data["metadata"]) if data["metadata"] else {},
                created_at=data["created_at"],
                updated_at=data["updated_at"],
                completed_at=data["completed_at"],
            )
            plan.milestones = self._get_milestones(plan_id)
            plan.resources = self._get_resources(plan_id)
            plan.risks = self._get_risks(plan_id)
            self._plan_cache[plan_id] = plan
            return plan
        return None

    def get_all_plans(
        self, phase: Optional[PlanPhase] = None, limit: int = 50
    ) -> List[StrategicPlan]:
        """Get all plans with optional filter.

        Args:
            phase: Filter by phase.
            limit: Maximum results.

        Returns:
            List of plans.
        """
        query = "SELECT * FROM plans"
        params: List[Any] = []

        if phase:
            query += " WHERE phase = ?"
            params.append(phase.value)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()

        plans = []
        for row in rows:
            data = dict(row)
            plan = StrategicPlan(
                id=data["id"],
                title=data["title"],
                description=data["description"],
                phase=PlanPhase(data["phase"]),
                horizon_days=data["horizon_days"],
                start_date=data["start_date"],
                current_day=data["current_day"],
                metadata=json.loads(data["metadata"]) if data["metadata"] else {},
                created_at=data["created_at"],
                updated_at=data["updated_at"],
                completed_at=data["completed_at"],
            )
            plan.milestones = self._get_milestones(plan.id)
            plan.resources = self._get_resources(plan.id)
            plan.risks = self._get_risks(plan.id)
            plans.append(plan)

        return plans

    def visualize(self, plan_id: str) -> PlanVisualization:
        """Create a text-based visualization of a plan.

        Args:
            plan_id: ID of the plan.

        Returns:
            PlanVisualization with Gantt chart, summary, and risk heatmap.
        """
        plan = self.get_plan(plan_id)
        if plan is None:
            return PlanVisualization(plan_id=plan_id)

        gantt = self._build_gantt_chart(plan)
        summary = self._build_summary(plan)
        heatmap = self._build_risk_heatmap(plan)

        return PlanVisualization(
            plan_id=plan_id,
            gantt_chart=gantt,
            summary=summary,
            risk_heatmap=heatmap,
        )

    def quality_score(self, plan_id: str) -> PlanQualityReport:
        """Score the quality of a plan.

        Args:
            plan_id: ID of the plan.

        Returns:
            PlanQualityReport with scores and recommendations.
        """
        plan = self.get_plan(plan_id)
        if plan is None:
            return PlanQualityReport(plan_id=plan_id)

        issues: List[str] = []
        recommendations: List[str] = []

        completeness = self._score_completeness(plan, issues, recommendations)
        specificity = self._score_specificity(plan, issues, recommendations)
        risk_coverage = self._score_risk_coverage(plan, issues, recommendations)
        resource_alignment = self._score_resource_alignment(
            plan, issues, recommendations
        )
        milestone_spacing = self._score_milestone_spacing(
            plan, issues, recommendations
        )

        overall = (
            completeness * 0.25
            + specificity * 0.2
            + risk_coverage * 0.25
            + resource_alignment * 0.15
            + milestone_spacing * 0.15
        )

        return PlanQualityReport(
            plan_id=plan_id,
            overall_score=overall,
            completeness=completeness,
            specificity=specificity,
            risk_coverage=risk_coverage,
            resource_alignment=resource_alignment,
            milestone_spacing=milestone_spacing,
            issues=issues,
            recommendations=recommendations,
        )

    def _get_milestones(self, plan_id: str) -> List[Milestone]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM milestones WHERE plan_id = ? ORDER BY target_day",
                (plan_id,),
            ).fetchall()
        return [Milestone.from_dict(dict(r)) for r in rows]

    def _get_milestone(self, milestone_id: str) -> Optional[Milestone]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM milestones WHERE id = ?", (milestone_id,)
            ).fetchone()
        if row:
            return Milestone.from_dict(dict(row))
        return None

    def _get_resources(self, plan_id: str) -> List[ResourceAllocation]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM resources WHERE plan_id = ?", (plan_id,)
            ).fetchall()

        resources = []
        for r in rows:
            data = dict(r)
            resources.append(
                ResourceAllocation(
                    resource_type=data["resource_type"],
                    name=data["name"],
                    allocation=data["allocation"],
                    unit=data["unit"],
                    start_day=data["start_day"],
                    end_day=data["end_day"],
                    utilization=data["utilization"],
                    notes=data["notes"],
                )
            )
        return resources

    def _get_risks(self, plan_id: str) -> List[RiskAssessment]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM risks WHERE plan_id = ? ORDER BY probability * impact DESC",
                (plan_id,),
            ).fetchall()
        return [RiskAssessment.from_dict(dict(r)) for r in rows]

    def _get_risk(self, risk_id: str) -> Optional[RiskAssessment]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM risks WHERE risk_id = ?", (risk_id,)
            ).fetchone()
        if row:
            return RiskAssessment.from_dict(dict(row))
        return None

    def _save_milestone(self, milestone: Milestone) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO milestones (
                    id, plan_id, title, description, target_day, actual_day,
                    status, deliverables, dependencies, progress, notes,
                    created_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    milestone.id,
                    milestone.plan_id,
                    milestone.title,
                    milestone.description,
                    milestone.target_day,
                    milestone.actual_day,
                    milestone.status,
                    json.dumps(milestone.deliverables),
                    json.dumps(milestone.dependencies),
                    milestone.progress,
                    milestone.notes,
                    milestone.created_at,
                    milestone.completed_at,
                ),
            )
            conn.commit()

    def _save_risk(self, risk: RiskAssessment) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO risks (
                    risk_id, plan_id, description, category, probability,
                    impact, risk_level, mitigation, contingency, owner,
                    status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    risk.risk_id,
                    risk.plan_id,
                    risk.description,
                    risk.category,
                    risk.probability,
                    risk.impact,
                    risk.risk_level.value,
                    risk.mitigation,
                    risk.contingency,
                    risk.owner,
                    risk.status,
                    risk.created_at,
                ),
            )
            conn.commit()

    def _update_plan(self, plan: StrategicPlan) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE plans SET
                    title = ?, description = ?, phase = ?, horizon_days = ?,
                    current_day = ?, metadata = ?, updated_at = ?,
                    completed_at = ?
                WHERE id = ?
                """,
                (
                    plan.title,
                    plan.description,
                    plan.phase.value,
                    plan.horizon_days,
                    plan.current_day,
                    json.dumps(plan.metadata),
                    plan.updated_at,
                    plan.completed_at,
                    plan.id,
                ),
            )
            conn.commit()

    async def _llm_generate_plan(
        self, objective: str, context: str, horizon_days: int
    ) -> Dict[str, Any]:
        prompt = (
            f"Objective: {objective}\n\n"
            f"Context: {context}\n\n"
            f"Horizon: {horizon_days} days\n\n"
            f"Create a strategic plan with:\n"
            f"- A concise title\n"
            f"- A detailed description\n"
            f"- 5-8 milestones spread across the timeline\n"
            f"- Resource requirements\n"
            f"- Key risks\n\n"
            f"Format as JSON:\n"
            f'{{"title": "...", "description": "...", "milestones": ['
            f'{{"title": "...", "description": "...", "target_day": N, "deliverables": ["..."]}}'
            f'], "resources": ['
            f'{{"resource_type": "...", "name": "...", "allocation": N, "unit": "...", "start_day": N, "end_day": N}}'
            f'], "risks": ['
            f'{{"description": "...", "category": "...", "probability": 0.X, "impact": 0.X, "mitigation": "..."}}'
            f']}}\n'
        )

        try:
            text = await self.llm_callback(prompt)
            return self._parse_json_response(text)
        except Exception as e:
            logger.warning("LLM plan generation failed: %s", e)
            return {
                "title": objective[:80],
                "description": objective,
                "milestones": [],
                "resources": [],
                "risks": [],
            }

    async def _llm_assess_risks(
        self, plan: StrategicPlan
    ) -> List[Dict[str, Any]]:
        milestones_text = "\n".join(
            f"  Day {m.target_day}: {m.title}" for m in plan.milestones
        )

        prompt = (
            f"Plan: {plan.title}\n"
            f"Description: {plan.description}\n"
            f"Horizon: {plan.horizon_days} days\n\n"
            f"Milestones:\n{milestones_text}\n\n"
            f"Identify the top 5 risks for this plan. For each:\n"
            f"- description: What could go wrong\n"
            f"- category: technical, schedule, resource, external, quality\n"
            f"- probability: 0.0-1.0\n"
            f"- impact: 0.0-1.0\n"
            f"- mitigation: How to reduce the risk\n"
            f"- contingency: What to do if it happens\n\n"
            f"Format as JSON array.\n"
        )

        try:
            text = await self.llm_callback(prompt)
            data = self._parse_json_response(text)
            if isinstance(data, list):
                return data
            return data.get("risks", [])
        except Exception as e:
            logger.warning("LLM risk assessment failed: %s", e)
            return []

    async def _llm_adapt_plan(
        self, plan: StrategicPlan, new_information: str
    ) -> Dict[str, Any]:
        prompt = (
            f"Current plan: {plan.title}\n"
            f"Current day: {plan.current_day}/{plan.horizon_days}\n"
            f"Progress: {plan.progress:.0%}\n\n"
            f"Milestones:\n"
            + "\n".join(
                f"  Day {m.target_day}: {m.title} ({m.status}, {m.progress:.0%})"
                for m in plan.milestones
            )
            + f"\n\n"
            f"New information: {new_information}\n\n"
            f"How should the plan be adapted? Respond with JSON:\n"
            f'{{"phase_change": "...", "new_milestones": [], "milestone_changes": [], "risk_updates": []}}\n'
        )

        try:
            text = await self.llm_callback(prompt)
            return self._parse_json_response(text)
        except Exception as e:
            logger.warning("LLM plan adaptation failed: %s", e)
            return {}

    def _build_gantt_chart(self, plan: StrategicPlan) -> str:
        if not plan.milestones:
            return "No milestones to display."

        width = min(60, plan.horizon_days)
        lines = [
            f"Gantt Chart: {plan.title}",
            f"{'=' * (len(lines[0]) if lines else 40)}",
            f"Day 0{' ' * (width - 8)}Day {plan.horizon_days}",
            f"{'|' + '-' * width + '|'}",
        ]

        for m in sorted(plan.milestones, key=lambda x: x.target_day):
            pos = int((m.target_day / max(plan.horizon_days, 1)) * width)
            pos = min(pos, width - 1)

            if m.status == "completed":
                marker = "✓"
            elif m.status == "blocked":
                marker = "✗"
            elif m.progress > 0:
                marker = "▓"
            else:
                marker = "○"

            bar = " " * pos + marker
            status_tag = f" [{m.status}]"
            lines.append(f"{m.title[:25]:<25} |{bar:<{width}}|{status_tag} Day {m.target_day}")

        current_pos = int((plan.current_day / max(plan.horizon_days, 1)) * width)
        current_pos = min(current_pos, width - 1)
        lines.append(f"{'Current':<25} |{' ' * current_pos}▲{' ' * (width - current_pos - 1)}| Day {plan.current_day}")

        return "\n".join(lines)

    def _build_summary(self, plan: StrategicPlan) -> str:
        lines = [
            f"Plan: {plan.title}",
            f"Phase: {plan.phase.value}",
            f"Progress: {plan.progress:.0%}",
            f"Timeline: Day {plan.current_day}/{plan.horizon_days} ({plan.days_remaining} remaining)",
            f"Milestones: {sum(1 for m in plan.milestones if m.status == 'completed')}/{len(plan.milestones)} completed",
            f"Resources: {len(plan.resources)} allocated",
            f"Risks: {len(plan.risks)} identified",
        ]

        critical_risks = [r for r in plan.risks if r.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)]
        if critical_risks:
            lines.append(f"\nCritical Risks:")
            for r in critical_risks:
                lines.append(f"  [{r.risk_level.value.upper()}] {r.description[:60]}")

        blocked = [m for m in plan.milestones if m.status == "blocked"]
        if blocked:
            lines.append(f"\nBlocked Milestones:")
            for m in blocked:
                lines.append(f"  - {m.title}: {m.notes or 'No reason given'}")

        return "\n".join(lines)

    def _build_risk_heatmap(self, plan: StrategicPlan) -> str:
        if not plan.risks:
            return "No risks identified."

        lines = [
            "Risk Heatmap",
            "=" * 40,
            f"{'Risk':<30} {'Prob':>6} {'Impact':>7} {'Score':>6} {'Level':<10}",
            "-" * 60,
        ]

        for r in sorted(plan.risks, key=lambda x: x.risk_score, reverse=True):
            icon = {"low": "🟢", "medium": "🟡", "high": "🔴", "critical": "🔴"}.get(
                r.risk_level.value, "⚪"
            )
            lines.append(
                f"{r.description[:28]:<30} {r.probability:>6.2f} {r.impact:>7.2f} "
                f"{r.risk_score:>6.2f} {icon} {r.risk_level.value:<10}"
            )

        return "\n".join(lines)

    def _score_completeness(
        self,
        plan: StrategicPlan,
        issues: List[str],
        recommendations: List[str],
    ) -> float:
        score = 0.3

        if plan.description:
            score += 0.1
        else:
            issues.append("Plan has no description")
            recommendations.append("Add a detailed plan description")

        if plan.milestones:
            score += 0.2
        else:
            issues.append("Plan has no milestones")
            recommendations.append("Add at least 3 milestones")

        if plan.resources:
            score += 0.2
        else:
            issues.append("Plan has no resource allocations")
            recommendations.append("Define resource requirements")

        if plan.risks:
            score += 0.2
        else:
            issues.append("Plan has no risk assessment")
            recommendations.append("Identify and document key risks")

        return min(1.0, score)

    def _score_specificity(
        self,
        plan: StrategicPlan,
        issues: List[str],
        recommendations: List[str],
    ) -> float:
        if not plan.milestones:
            return 0.0

        score = 0.0
        milestones_with_deliverables = sum(
            1 for m in plan.milestones if m.deliverables
        )
        milestones_with_descriptions = sum(
            1 for m in plan.milestones if m.description
        )

        if milestones_with_deliverables > len(plan.milestones) * 0.5:
            score += 0.5
        else:
            issues.append("Many milestones lack deliverables")
            recommendations.append("Define specific deliverables for each milestone")

        if milestones_with_descriptions > len(plan.milestones) * 0.7:
            score += 0.5
        else:
            issues.append("Many milestones lack descriptions")
            recommendations.append("Add detailed descriptions to milestones")

        return score

    def _score_risk_coverage(
        self,
        plan: StrategicPlan,
        issues: List[str],
        recommendations: List[str],
    ) -> float:
        if not plan.risks:
            issues.append("No risks identified")
            recommendations.append("Perform risk assessment")
            return 0.0

        score = 0.3

        if len(plan.risks) >= 3:
            score += 0.2

        risks_with_mitigation = sum(1 for r in plan.risks if r.mitigation)
        if risks_with_mitigation > len(plan.risks) * 0.5:
            score += 0.3
        else:
            issues.append("Many risks lack mitigation strategies")
            recommendations.append("Define mitigation strategies for each risk")

        risks_with_contingency = sum(1 for r in plan.risks if r.contingency)
        if risks_with_contingency > len(plan.risks) * 0.3:
            score += 0.2
        else:
            recommendations.append("Add contingency plans for high-impact risks")

        return min(1.0, score)

    def _score_resource_alignment(
        self,
        plan: StrategicPlan,
        issues: List[str],
        recommendations: List[str],
    ) -> float:
        if not plan.resources:
            return 0.3

        score = 0.5
        if len(plan.resources) >= 2:
            score += 0.2

        for r in plan.resources:
            if r.end_day > plan.horizon_days:
                issues.append(f"Resource '{r.name}' extends beyond plan horizon")
                recommendations.append(
                    f"Adjust '{r.name}' allocation to fit within {plan.horizon_days} days"
                )
                score -= 0.1

        return max(0.0, min(1.0, score))

    def _score_milestone_spacing(
        self,
        plan: StrategicPlan,
        issues: List[str],
        recommendations: List[str],
    ) -> float:
        if len(plan.milestones) < 2:
            return 0.5

        days = [m.target_day for m in plan.milestones if m.target_day > 0]
        if not days:
            return 0.3

        days.sort()
        gaps = [days[i + 1] - days[i] for i in range(len(days) - 1)]

        if not gaps:
            return 0.5

        avg_gap = sum(gaps) / len(gaps)
        variance = sum((g - avg_gap) ** 2 for g in gaps) / len(gaps)
        cv = (variance**0.5) / max(avg_gap, 1)

        if cv < 0.5:
            return 1.0
        elif cv < 1.0:
            return 0.7
        else:
            issues.append("Milestones are unevenly spaced")
            recommendations.append("Distribute milestones more evenly across the timeline")
            return 0.4

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        text = text.strip()

        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            for start in ["{", "["]:
                idx = text.find(start)
                if idx >= 0:
                    for end_idx in range(len(text), idx, -1):
                        try:
                            return json.loads(text[idx:end_idx])
                        except json.JSONDecodeError:
                            continue
        return {}
