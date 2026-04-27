"""
NEUGI v2 Approval Gates
========================

Configurable approval workflow system for controlling autonomous agent actions
based on action type, cost, risk level, and other criteria.

Features:
    - Configurable approval rules (by action type, cost, risk level)
    - Approval workflow (pending, approved, rejected, escalated)
    - Auto-approval for low-risk actions
    - Multi-level approval chains
    - Approval timeout (auto-reject after N minutes)
    - Approval history and audit trail

Usage:
    from neugi_swarm_v2.governance.approval import ApprovalGate, ApprovalRule

    gate = ApprovalGate(db_path="governance.db")

    # Add approval rules
    gate.add_rule(ApprovalRule(
        name="high_cost_approval",
        action_type="*",
        min_cost=10.0,
        requires_approval=True,
        approvers=["admin", "finance"],
        timeout_minutes=30,
    ))

    # Request approval for an action
    request = gate.request_approval(
        agent_id="aurora",
        action="execute_code",
        description="Run database migration",
        cost_estimate=15.0,
        risk_level="high",
    )

    # Approve or reject
    gate.approve(request.request_id, approver="admin")
    gate.reject(request.request_id, approver="admin", reason="Too risky")
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


# -- Enums -------------------------------------------------------------------

class ApprovalStatus(str, Enum):
    """Approval request status."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    EXPIRED = "expired"
    AUTO_APPROVED = "auto_approved"


class RiskLevel(str, Enum):
    """Action risk level."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# -- Data Classes ------------------------------------------------------------

@dataclass
class ApprovalRule:
    """A rule that determines when approval is required.

    Attributes:
        rule_id: Unique rule identifier.
        name: Human-readable rule name.
        action_type: Action type pattern ('*' for all, or specific type).
        agent_role: Agent role pattern ('*' for all).
        min_cost: Minimum cost to trigger rule.
        max_cost: Maximum cost to trigger rule.
        min_risk: Minimum risk level to trigger rule.
        requires_approval: Whether approval is required.
        approvers: List of required approver roles.
        approval_count: Number of approvals needed (0 = all).
        timeout_minutes: Auto-reject after this many minutes.
        auto_approve_below: Auto-approve if cost below this threshold.
        created_at: Rule creation time.
        enabled: Whether rule is active.
    """

    rule_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "unnamed_rule"
    action_type: str = "*"
    agent_role: str = "*"
    min_cost: float = 0.0
    max_cost: float = float("inf")
    min_risk: RiskLevel = RiskLevel.LOW
    requires_approval: bool = True
    approvers: list[str] = field(default_factory=list)
    approval_count: int = 1
    timeout_minutes: float = 60.0
    auto_approve_below: Optional[float] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    enabled: bool = True

    def matches(
        self,
        action_type: str,
        agent_role: str = "",
        cost: float = 0.0,
        risk_level: RiskLevel = RiskLevel.LOW,
    ) -> bool:
        """Check if this rule matches the given action parameters.

        Args:
            action_type: The action type being performed.
            agent_role: The role of the agent performing the action.
            cost: Estimated cost of the action.
            risk_level: Risk level of the action.

        Returns:
            True if the rule applies to this action.
        """
        if not self.enabled:
            return False

        if self.action_type != "*" and self.action_type != action_type:
            return False

        if self.agent_role != "*" and self.agent_role != agent_role:
            return False

        if cost < self.min_cost or cost > self.max_cost:
            return False

        risk_order = {
            RiskLevel.LOW: 0,
            RiskLevel.MEDIUM: 1,
            RiskLevel.HIGH: 2,
            RiskLevel.CRITICAL: 3,
        }
        if risk_order.get(risk_level, 0) < risk_order.get(self.min_risk, 0):
            return False

        return True


@dataclass
class ApprovalDecision:
    """A single approval/rejection decision.

    Attributes:
        request_id: The request this decision applies to.
        approver: Who made the decision.
        decision: 'approved' or 'rejected'.
        reason: Explanation for the decision.
        timestamp: When the decision was made.
    """

    request_id: str
    approver: str
    decision: str
    reason: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ApprovalRequest:
    """An approval request for an action.

    Attributes:
        request_id: Unique request identifier.
        agent_id: Agent requesting approval.
        agent_role: Role of the requesting agent.
        action: Action type being requested.
        description: Human-readable description.
        cost_estimate: Estimated cost of the action.
        risk_level: Assessed risk level.
        status: Current approval status.
        rule_id: Rule that triggered this request.
        decisions: List of decisions made.
        required_approvals: Number of approvals needed.
        timeout_at: When the request expires.
        created_at: When the request was created.
        metadata: Additional context.
    """

    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    agent_role: str = ""
    action: str = ""
    description: str = ""
    cost_estimate: float = 0.0
    risk_level: RiskLevel = RiskLevel.LOW
    status: ApprovalStatus = ApprovalStatus.PENDING
    rule_id: str = ""
    decisions: list[ApprovalDecision] = field(default_factory=list)
    required_approvals: int = 1
    timeout_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        """Check if the request has timed out."""
        if self.timeout_at is None:
            return False
        return datetime.now(timezone.utc) > self.timeout_at

    @property
    def approval_count(self) -> int:
        """Count of approvals received."""
        return sum(1 for d in self.decisions if d.decision == "approved")

    @property
    def has_rejection(self) -> bool:
        """Check if any approver has rejected."""
        return any(d.decision == "rejected" for d in self.decisions)


@dataclass
class ApprovalChain:
    """A multi-level approval chain.

    Attributes:
        chain_id: Unique chain identifier.
        name: Human-readable chain name.
        levels: Ordered list of (level_name, approvers) tuples.
        current_level: Current level index (0-based).
        timeout_minutes: Total timeout for the chain.
    """

    chain_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "unnamed_chain"
    levels: list[tuple[str, list[str]]] = field(default_factory=list)
    current_level: int = 0
    timeout_minutes: float = 120.0

    @property
    def current_approvers(self) -> list[str]:
        """Get approvers for the current level."""
        if 0 <= self.current_level < len(self.levels):
            return self.levels[self.current_level][1]
        return []

    @property
    def is_complete(self) -> bool:
        """Check if all levels have been approved."""
        return self.current_level >= len(self.levels)


@dataclass
class ApprovalTimeoutError(Exception):
    """Raised when an approval request times out.

    Attributes:
        request_id: The timed-out request.
        message: Human-readable error message.
    """

    request_id: str
    message: str = ""

    def __post_init__(self) -> None:
        if not self.message:
            self.message = f"Approval request '{self.request_id}' timed out"


@dataclass
class ApprovalHistory:
    """Complete history for an approval request.

    Attributes:
        request: The original request.
        decisions: All decisions made.
        status_changes: List of (status, timestamp) tuples.
        total_duration: Time from creation to final decision.
    """

    request: ApprovalRequest
    decisions: list[ApprovalDecision] = field(default_factory=list)
    status_changes: list[tuple[str, datetime]] = field(default_factory=list)
    total_duration: Optional[timedelta] = None


# -- Approval Gate -----------------------------------------------------------

class ApprovalGate:
    """Approval gate for controlling autonomous agent actions.

    Manages approval rules, requests, and decisions with support for
    auto-approval, multi-level chains, and timeout handling.

    Args:
        db_path: Path to SQLite database for persistence.
        default_timeout_minutes: Default timeout for approval requests.

    Attributes:
        db_path: Database file path.
        default_timeout: Default timeout in minutes.
        _lock: Thread safety lock.
        _rules: In-memory rule cache.
        _chains: In-memory chain cache.
    """

    def __init__(
        self,
        db_path: str = "governance.db",
        default_timeout_minutes: float = 60.0,
    ) -> None:
        self.db_path = db_path
        self.default_timeout = default_timeout_minutes
        self._lock = threading.Lock()
        self._rules: dict[str, ApprovalRule] = {}
        self._chains: dict[str, ApprovalChain] = {}
        self._init_db()
        self._load_rules()

    def _get_conn(self) -> sqlite3.Connection:
        """Get a database connection with WAL mode.

        Returns:
            SQLite connection with foreign keys enabled.
        """
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS approval_rules (
                    rule_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    action_type TEXT NOT NULL DEFAULT '*',
                    agent_role TEXT NOT NULL DEFAULT '*',
                    min_cost REAL NOT NULL DEFAULT 0.0,
                    max_cost REAL NOT NULL DEFAULT 1e308,
                    min_risk TEXT NOT NULL DEFAULT 'low',
                    requires_approval INTEGER NOT NULL DEFAULT 1,
                    approvers_json TEXT,
                    approval_count INTEGER NOT NULL DEFAULT 1,
                    timeout_minutes REAL NOT NULL DEFAULT 60.0,
                    auto_approve_below REAL,
                    created_at TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS approval_requests (
                    request_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    agent_role TEXT NOT NULL,
                    action TEXT NOT NULL,
                    description TEXT,
                    cost_estimate REAL NOT NULL DEFAULT 0.0,
                    risk_level TEXT NOT NULL DEFAULT 'low',
                    status TEXT NOT NULL DEFAULT 'pending',
                    rule_id TEXT,
                    required_approvals INTEGER NOT NULL DEFAULT 1,
                    timeout_at TEXT,
                    created_at TEXT NOT NULL,
                    metadata_json TEXT
                );

                CREATE TABLE IF NOT EXISTS approval_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    approver TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    reason TEXT,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (request_id) REFERENCES approval_requests(request_id)
                );

                CREATE INDEX IF NOT EXISTS idx_decisions_request
                    ON approval_decisions(request_id);

                CREATE TABLE IF NOT EXISTS approval_status_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (request_id) REFERENCES approval_requests(request_id)
                );

                CREATE INDEX IF NOT EXISTS idx_status_log_request
                    ON approval_status_log(request_id);

                CREATE TABLE IF NOT EXISTS approval_chains (
                    chain_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    levels_json TEXT NOT NULL,
                    current_level INTEGER NOT NULL DEFAULT 0,
                    timeout_minutes REAL NOT NULL DEFAULT 120.0
                );
            """)

    def _load_rules(self) -> None:
        """Load rules from database into memory."""
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM approval_rules WHERE enabled = 1").fetchall()

        for row in rows:
            rule = ApprovalRule(
                rule_id=row["rule_id"],
                name=row["name"],
                action_type=row["action_type"],
                agent_role=row["agent_role"],
                min_cost=row["min_cost"],
                max_cost=row["max_cost"],
                min_risk=RiskLevel(row["min_risk"]),
                requires_approval=bool(row["requires_approval"]),
                approvers=json.loads(row["approvers_json"]) if row["approvers_json"] else [],
                approval_count=row["approval_count"],
                timeout_minutes=row["timeout_minutes"],
                auto_approve_below=row["auto_approve_below"],
                created_at=datetime.fromisoformat(row["created_at"]),
                enabled=bool(row["enabled"]),
            )
            self._rules[rule.rule_id] = rule

    def add_rule(self, rule: ApprovalRule) -> ApprovalRule:
        """Add an approval rule.

        Args:
            rule: Rule to add.

        Returns:
            The added rule.
        """
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO approval_rules
                    (rule_id, name, action_type, agent_role, min_cost, max_cost,
                     min_risk, requires_approval, approvers_json, approval_count,
                     timeout_minutes, auto_approve_below, created_at, enabled)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        rule.rule_id,
                        rule.name,
                        rule.action_type,
                        rule.agent_role,
                        rule.min_cost,
                        rule.max_cost,
                        rule.min_risk.value,
                        1 if rule.requires_approval else 0,
                        json.dumps(rule.approvers),
                        rule.approval_count,
                        rule.timeout_minutes,
                        rule.auto_approve_below,
                        rule.created_at.isoformat(),
                        1 if rule.enabled else 0,
                    ),
                )

            self._rules[rule.rule_id] = rule
            logger.info("Approval rule added: %s", rule.name)
            return rule

    def remove_rule(self, rule_id: str) -> bool:
        """Remove an approval rule.

        Args:
            rule_id: Rule to remove.

        Returns:
            True if removed, False if not found.
        """
        with self._lock:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    "DELETE FROM approval_rules WHERE rule_id = ?",
                    (rule_id,),
                )

            if cursor.rowcount > 0:
                self._rules.pop(rule_id, None)
                logger.info("Approval rule removed: %s", rule_id)
                return True
            return False

    def get_rule(self, rule_id: str) -> Optional[ApprovalRule]:
        """Get an approval rule by ID.

        Args:
            rule_id: Rule identifier.

        Returns:
            ApprovalRule if found, None otherwise.
        """
        return self._rules.get(rule_id)

    def list_rules(self, enabled_only: bool = True) -> list[ApprovalRule]:
        """List all approval rules.

        Args:
            enabled_only: Only return enabled rules.

        Returns:
            List of ApprovalRule objects.
        """
        if enabled_only:
            return [r for r in self._rules.values() if r.enabled]
        return list(self._rules.values())

    def find_matching_rules(
        self,
        action_type: str,
        agent_role: str = "",
        cost: float = 0.0,
        risk_level: RiskLevel = RiskLevel.LOW,
    ) -> list[ApprovalRule]:
        """Find rules that match the given action parameters.

        Args:
            action_type: The action type being performed.
            agent_role: The role of the agent.
            cost: Estimated cost.
            risk_level: Risk level.

        Returns:
            List of matching rules.
        """
        return [
            rule for rule in self._rules.values()
            if rule.matches(action_type, agent_role, cost, risk_level)
        ]

    def requires_approval(
        self,
        action_type: str,
        agent_role: str = "",
        cost: float = 0.0,
        risk_level: RiskLevel = RiskLevel.LOW,
    ) -> tuple[bool, list[ApprovalRule]]:
        """Check if an action requires approval.

        Args:
            action_type: The action type being performed.
            agent_role: The role of the agent.
            cost: Estimated cost.
            risk_level: Risk level.

        Returns:
            Tuple of (requires_approval, matching_rules).
        """
        matching = self.find_matching_rules(action_type, agent_role, cost, risk_level)

        for rule in matching:
            if rule.auto_approve_below is not None and cost < rule.auto_approve_below:
                continue
            if rule.requires_approval:
                return True, matching

        return False, matching

    def request_approval(
        self,
        agent_id: str,
        action: str,
        description: str = "",
        agent_role: str = "",
        cost_estimate: float = 0.0,
        risk_level: RiskLevel = RiskLevel.LOW,
        metadata: Optional[dict[str, Any]] = None,
    ) -> ApprovalRequest:
        """Create an approval request for an action.

        Automatically determines if approval is needed based on rules.
        Low-risk actions may be auto-approved.

        Args:
            agent_id: Agent requesting approval.
            action: Action type being requested.
            description: Human-readable description.
            agent_role: Role of the requesting agent.
            cost_estimate: Estimated cost.
            risk_level: Assessed risk level.
            metadata: Additional context.

        Returns:
            ApprovalRequest with status set.
        """
        needs_approval, matching_rules = self.requires_approval(
            action, agent_role, cost_estimate, risk_level,
        )

        if not needs_approval:
            request = ApprovalRequest(
                agent_id=agent_id,
                agent_role=agent_role,
                action=action,
                description=description,
                cost_estimate=cost_estimate,
                risk_level=risk_level,
                status=ApprovalStatus.AUTO_APPROVED,
                metadata=metadata or {},
            )
            self._persist_request(request)
            logger.info("Auto-approved: %s by %s", action, agent_id)
            return request

        rule = matching_rules[0] if matching_rules else None
        timeout_at = datetime.now(timezone.utc) + timedelta(
            minutes=rule.timeout_minutes if rule else self.default_timeout,
        )

        request = ApprovalRequest(
            agent_id=agent_id,
            agent_role=agent_role,
            action=action,
            description=description,
            cost_estimate=cost_estimate,
            risk_level=risk_level,
            status=ApprovalStatus.PENDING,
            rule_id=rule.rule_id if rule else "",
            required_approvals=rule.approval_count if rule else 1,
            timeout_at=timeout_at,
            metadata=metadata or {},
        )

        self._persist_request(request)
        self._log_status_change(request.request_id, ApprovalStatus.PENDING)
        logger.info(
            "Approval requested: %s by %s (rule=%s)",
            action, agent_id, rule.name if rule else "default",
        )
        return request

    def _persist_request(self, request: ApprovalRequest) -> None:
        """Persist an approval request to the database.

        Args:
            request: Request to persist.
        """
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO approval_requests
                (request_id, agent_id, agent_role, action, description,
                 cost_estimate, risk_level, status, rule_id, required_approvals,
                 timeout_at, created_at, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request.request_id,
                    request.agent_id,
                    request.agent_role,
                    request.action,
                    request.description,
                    request.cost_estimate,
                    request.risk_level.value,
                    request.status.value,
                    request.rule_id,
                    request.required_approvals,
                    request.timeout_at.isoformat() if request.timeout_at else None,
                    request.created_at.isoformat(),
                    json.dumps(request.metadata),
                ),
            )

    def approve(
        self,
        request_id: str,
        approver: str,
        reason: str = "",
    ) -> ApprovalRequest:
        """Approve a pending request.

        Args:
            request_id: Request to approve.
            approver: Who is approving.
            reason: Reason for approval.

        Returns:
            Updated ApprovalRequest.

        Raises:
            ValueError: If request not found or already resolved.
        """
        request = self.get_request(request_id)
        if request is None:
            raise ValueError(f"Request '{request_id}' not found")

        if request.status not in (ApprovalStatus.PENDING, ApprovalStatus.ESCALATED):
            raise ValueError(f"Request '{request_id}' is already {request.status.value}")

        if request.is_expired:
            self._update_status(request, ApprovalStatus.EXPIRED)
            raise ApprovalTimeoutError(request_id)

        decision = ApprovalDecision(
            request_id=request_id,
            approver=approver,
            decision="approved",
            reason=reason,
        )
        request.decisions.append(decision)
        self._persist_decision(decision)

        if request.approval_count >= request.required_approvals:
            self._update_status(request, ApprovalStatus.APPROVED)
            logger.info("Request approved: %s by %s", request_id, approver)
        else:
            logger.info(
                "Partial approval: %s by %s (%d/%d)",
                request_id, approver,
                request.approval_count, request.required_approvals,
            )

        return request

    def reject(
        self,
        request_id: str,
        approver: str,
        reason: str = "",
    ) -> ApprovalRequest:
        """Reject a pending request.

        Args:
            request_id: Request to reject.
            approver: Who is rejecting.
            reason: Reason for rejection.

        Returns:
            Updated ApprovalRequest.

        Raises:
            ValueError: If request not found or already resolved.
        """
        request = self.get_request(request_id)
        if request is None:
            raise ValueError(f"Request '{request_id}' not found")

        if request.status not in (ApprovalStatus.PENDING, ApprovalStatus.ESCALATED):
            raise ValueError(f"Request '{request_id}' is already {request.status.value}")

        decision = ApprovalDecision(
            request_id=request_id,
            approver=approver,
            decision="rejected",
            reason=reason,
        )
        request.decisions.append(decision)
        self._persist_decision(decision)

        self._update_status(request, ApprovalStatus.REJECTED)
        logger.info("Request rejected: %s by %s (%s)", request_id, approver, reason)
        return request

    def escalate(
        self,
        request_id: str,
        reason: str = "",
    ) -> ApprovalRequest:
        """Escalate a pending request to higher authority.

        Args:
            request_id: Request to escalate.
            reason: Reason for escalation.

        Returns:
            Updated ApprovalRequest.

        Raises:
            ValueError: If request not found.
        """
        request = self.get_request(request_id)
        if request is None:
            raise ValueError(f"Request '{request_id}' not found")

        self._update_status(request, ApprovalStatus.ESCALATED)
        logger.info("Request escalated: %s (%s)", request_id, reason)
        return request

    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """Get an approval request by ID.

        Args:
            request_id: Request identifier.

        Returns:
            ApprovalRequest if found, None otherwise.
        """
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM approval_requests WHERE request_id = ?",
                (request_id,),
            ).fetchone()

        if row is None:
            return None

        decisions = self._get_decisions(request_id)
        request = ApprovalRequest(
            request_id=row["request_id"],
            agent_id=row["agent_id"],
            agent_role=row["agent_role"],
            action=row["action"],
            description=row["description"] or "",
            cost_estimate=row["cost_estimate"],
            risk_level=RiskLevel(row["risk_level"]),
            status=ApprovalStatus(row["status"]),
            rule_id=row["rule_id"] or "",
            decisions=decisions,
            required_approvals=row["required_approvals"],
            timeout_at=datetime.fromisoformat(row["timeout_at"]) if row["timeout_at"] else None,
            created_at=datetime.fromisoformat(row["created_at"]),
            metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else {},
        )

        if request.is_expired and request.status == ApprovalStatus.PENDING:
            self._update_status(request, ApprovalStatus.EXPIRED)

        return request

    def _get_decisions(self, request_id: str) -> list[ApprovalDecision]:
        """Get all decisions for a request.

        Args:
            request_id: Request identifier.

        Returns:
            List of ApprovalDecision objects.
        """
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM approval_decisions
                WHERE request_id = ?
                ORDER BY timestamp ASC
                """,
                (request_id,),
            ).fetchall()

        return [
            ApprovalDecision(
                request_id=row["request_id"],
                approver=row["approver"],
                decision=row["decision"],
                reason=row["reason"] or "",
                timestamp=datetime.fromisoformat(row["timestamp"]),
            )
            for row in rows
        ]

    def _persist_decision(self, decision: ApprovalDecision) -> None:
        """Persist a decision to the database.

        Args:
            decision: Decision to persist.
        """
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO approval_decisions
                (request_id, approver, decision, reason, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    decision.request_id,
                    decision.approver,
                    decision.decision,
                    decision.reason,
                    decision.timestamp.isoformat(),
                ),
            )

    def _update_status(self, request: ApprovalRequest, status: ApprovalStatus) -> None:
        """Update request status in database and memory.

        Args:
            request: Request to update.
            status: New status.
        """
        request.status = status
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE approval_requests SET status = ? WHERE request_id = ?",
                (status.value, request.request_id),
            )
        self._log_status_change(request.request_id, status)

    def _log_status_change(self, request_id: str, status: ApprovalStatus) -> None:
        """Log a status change.

        Args:
            request_id: Request identifier.
            status: New status.
        """
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO approval_status_log (request_id, status, timestamp)
                VALUES (?, ?, ?)
                """,
                (request_id, status.value, datetime.now(timezone.utc).isoformat()),
            )

    def get_pending_requests(self, agent_id: Optional[str] = None) -> list[ApprovalRequest]:
        """Get all pending approval requests.

        Args:
            agent_id: Filter by requesting agent.

        Returns:
            List of pending ApprovalRequest objects.
        """
        query = "SELECT request_id FROM approval_requests WHERE status = 'pending'"
        params: list[Any] = []

        if agent_id:
            query += " AND agent_id = ?"
            params.append(agent_id)

        with self._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()

        requests = []
        for row in rows:
            request = self.get_request(row["request_id"])
            if request:
                requests.append(request)

        return requests

    def get_history(self, request_id: str) -> ApprovalHistory:
        """Get complete history for an approval request.

        Args:
            request_id: Request identifier.

        Returns:
            ApprovalHistory with full audit trail.

        Raises:
            ValueError: If request not found.
        """
        request = self.get_request(request_id)
        if request is None:
            raise ValueError(f"Request '{request_id}' not found")

        decisions = self._get_decisions(request_id)

        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT status, timestamp FROM approval_status_log
                WHERE request_id = ?
                ORDER BY timestamp ASC
                """,
                (request_id,),
            ).fetchall()

        status_changes = [
            (row["status"], datetime.fromisoformat(row["timestamp"]))
            for row in rows
        ]

        total_duration = None
        if status_changes and len(status_changes) >= 2:
            total_duration = status_changes[-1][1] - status_changes[0][1]

        return ApprovalHistory(
            request=request,
            decisions=decisions,
            status_changes=status_changes,
            total_duration=total_duration,
        )

    def add_chain(self, chain: ApprovalChain) -> ApprovalChain:
        """Add a multi-level approval chain.

        Args:
            chain: Chain to add.

        Returns:
            The added chain.
        """
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO approval_chains
                    (chain_id, name, levels_json, current_level, timeout_minutes)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        chain.chain_id,
                        chain.name,
                        json.dumps(chain.levels),
                        chain.current_level,
                        chain.timeout_minutes,
                    ),
                )

            self._chains[chain.chain_id] = chain
            logger.info("Approval chain added: %s", chain.name)
            return chain

    def get_chain(self, chain_id: str) -> Optional[ApprovalChain]:
        """Get an approval chain by ID.

        Args:
            chain_id: Chain identifier.

        Returns:
            ApprovalChain if found, None otherwise.
        """
        if chain_id in self._chains:
            return self._chains[chain_id]

        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM approval_chains WHERE chain_id = ?",
                (chain_id,),
            ).fetchone()

        if row is None:
            return None

        chain = ApprovalChain(
            chain_id=row["chain_id"],
            name=row["name"],
            levels=json.loads(row["levels_json"]),
            current_level=row["current_level"],
            timeout_minutes=row["timeout_minutes"],
        )
        self._chains[chain.chain_id] = chain
        return chain

    def advance_chain(self, chain_id: str) -> Optional[ApprovalChain]:
        """Advance an approval chain to the next level.

        Args:
            chain_id: Chain to advance.

        Returns:
            Updated ApprovalChain, or None if not found.
        """
        chain = self.get_chain(chain_id)
        if chain is None:
            return None

        chain.current_level += 1

        with self._get_conn() as conn:
            conn.execute(
                "UPDATE approval_chains SET current_level = ? WHERE chain_id = ?",
                (chain.current_level, chain_id),
            )

        if chain.is_complete:
            logger.info("Approval chain completed: %s", chain.name)
        else:
            logger.info(
                "Approval chain advanced: %s (level %d/%d)",
                chain.name, chain.current_level, len(chain.levels),
            )

        return chain

    def check_timeouts(self) -> list[str]:
        """Check and expire timed-out requests.

        Returns:
            List of request IDs that were expired.
        """
        expired_ids = []

        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT request_id FROM approval_requests
                WHERE status = 'pending' AND timeout_at IS NOT NULL
                AND timeout_at < ?
                """,
                (datetime.now(timezone.utc).isoformat(),),
            ).fetchall()

            for row in rows:
                request_id = row["request_id"]
                self._update_status(
                    ApprovalRequest(request_id=request_id),
                    ApprovalStatus.EXPIRED,
                )
                expired_ids.append(request_id)
                logger.warning("Approval request expired: %s", request_id)

        return expired_ids

    def get_stats(self) -> dict[str, Any]:
        """Get approval gate statistics.

        Returns:
            Dictionary with approval statistics.
        """
        with self._get_conn() as conn:
            row = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
                    SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN status = 'expired' THEN 1 ELSE 0 END) as expired,
                    SUM(CASE WHEN status = 'auto_approved' THEN 1 ELSE 0 END) as auto_approved,
                    SUM(CASE WHEN status = 'escalated' THEN 1 ELSE 0 END) as escalated
                FROM approval_requests
            """).fetchone()

        return {
            "total_requests": row["total"],
            "approved": row["approved"],
            "rejected": row["rejected"],
            "pending": row["pending"],
            "expired": row["expired"],
            "auto_approved": row["auto_approved"],
            "escalated": row["escalated"],
            "approval_rate": (
                row["approved"] / (row["approved"] + row["rejected"])
                if (row["approved"] + row["rejected"]) > 0
                else 0.0
            ),
            "active_rules": len([r for r in self._rules.values() if r.enabled]),
            "active_chains": len(self._chains),
        }

    def close(self) -> None:
        """Close database connections."""
        pass

    def __enter__(self) -> "ApprovalGate":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
