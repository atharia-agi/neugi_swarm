"""
NEUGI v2 Budget Tracking System
================================

Hierarchical budget tracking for token usage and cost management across
swarm, agent, and task levels with real-time monitoring, warning thresholds,
and hard stops.

Features:
    - Token budget per agent/task/session
    - Cost tracking (token count * model price)
    - Warning thresholds (50%, 75%, 90%)
    - Hard stops (absolute limits)
    - Budget allocation hierarchy (swarm > agent > task)
    - Budget rollover/expiration
    - Real-time budget monitoring
    - Budget reports and analytics

Usage:
    from neugi_swarm_v2.governance.budget import BudgetTracker, ModelPricing

    pricing = ModelPricing({"gpt-4": 0.00003, "gpt-3.5": 0.000001})
    tracker = BudgetTracker(db_path="governance.db", model_pricing=pricing)

    # Set budgets at different levels
    tracker.set_budget("swarm:main", token_limit=1_000_000, cost_limit=30.0)
    tracker.set_budget("agent:aurora", token_limit=200_000, cost_limit=6.0,
                       parent_id="swarm:main")

    # Record usage
    tracker.record_usage("agent:aurora", input_tokens=1500, output_tokens=500,
                         model="gpt-4")

    # Check status
    status = tracker.get_status("agent:aurora")
    print(status.usage_pct)  # 1.0%
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# -- Enums -------------------------------------------------------------------

class BudgetLevel(str, Enum):
    """Budget hierarchy levels."""
    SWARM = "swarm"
    AGENT = "agent"
    TASK = "task"
    SESSION = "session"


class BudgetStatus(str, Enum):
    """Budget health status."""
    OK = "ok"
    WARNING_50 = "warning_50"
    WARNING_75 = "warning_75"
    WARNING_90 = "warning_90"
    EXCEEDED = "exceeded"
    EXPIRED = "expired"


# -- Data Classes ------------------------------------------------------------

@dataclass
class ModelPricing:
    """Model pricing configuration (per token).

    Attributes:
        prices: Mapping of model name to price per token.
        default_price: Fallback price for unknown models.
    """

    prices: dict[str, float] = field(default_factory=dict)
    default_price: float = 0.00001

    def get_price(self, model: str) -> float:
        """Get price per token for a model.

        Args:
            model: Model name (e.g., 'gpt-4', 'claude-3-opus').

        Returns:
            Price per token in USD.
        """
        return self.prices.get(model, self.default_price)

    def set_price(self, model: str, price: float) -> None:
        """Set price per token for a model.

        Args:
            model: Model name.
            price: Price per token in USD.
        """
        self.prices[model] = price

    @classmethod
    def defaults(cls) -> ModelPricing:
        """Create with common model prices.

        Returns:
            ModelPricing with preset prices for popular models.
        """
        return cls(prices={
            "gpt-4": 0.00003,
            "gpt-4-turbo": 0.00001,
            "gpt-4o": 0.000005,
            "gpt-3.5-turbo": 0.0000015,
            "claude-3-opus": 0.000015,
            "claude-3-sonnet": 0.000003,
            "claude-3-haiku": 0.00000025,
            "llama-3-70b": 0.0000009,
            "llama-3-8b": 0.0000003,
            "qwen2.5-coder:7b": 0.0,
            "ollama": 0.0,
        })


@dataclass
class BudgetThreshold:
    """Threshold configuration for budget warnings.

    Attributes:
        warning_50: Trigger warning at 50% usage.
        warning_75: Trigger warning at 75% usage.
        warning_90: Trigger warning at 90% usage.
        hard_stop: Hard stop at 100% (no override).
        soft_limit: Soft limit that can be overridden with approval.
    """

    warning_50: float = 0.50
    warning_75: float = 0.75
    warning_90: float = 0.90
    hard_stop: float = 1.0
    soft_limit: Optional[float] = None


@dataclass
class BudgetWarning:
    """A budget threshold warning.

    Attributes:
        budget_id: Budget that triggered the warning.
        threshold: Threshold percentage that was crossed.
        usage_pct: Current usage percentage.
        message: Human-readable warning message.
        timestamp: When the warning was triggered.
    """

    budget_id: str
    threshold: float
    usage_pct: float
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class BudgetExceededError(Exception):
    """Raised when a budget hard stop is reached.

    Attributes:
        budget_id: Budget that was exceeded.
        usage_pct: Current usage percentage.
        limit_type: Type of limit exceeded ('token' or 'cost').
        message: Human-readable error message.
    """

    budget_id: str
    usage_pct: float
    limit_type: str
    message: str = ""

    def __post_init__(self) -> None:
        if not self.message:
            self.message = (
                f"Budget '{self.budget_id}' exceeded: "
                f"{self.usage_pct:.1%} of {self.limit_type} limit reached"
            )


@dataclass
class CostEntry:
    """A single cost/usage entry.

    Attributes:
        budget_id: Budget this entry applies to.
        input_tokens: Number of input/prompt tokens.
        output_tokens: Number of output/completion tokens.
        total_tokens: Total tokens (input + output).
        cost_usd: Cost in USD.
        model: Model name used.
        timestamp: When the usage occurred.
        metadata: Additional context (task_id, action, etc.).
    """

    budget_id: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    model: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class UsageRecord:
    """Aggregated usage for a budget.

    Attributes:
        budget_id: Budget identifier.
        total_input_tokens: Sum of input tokens.
        total_output_tokens: Sum of output tokens.
        total_tokens: Sum of all tokens.
        total_cost_usd: Sum of all costs.
        entry_count: Number of usage entries.
        first_usage: Timestamp of first usage.
        last_usage: Timestamp of last usage.
    """

    budget_id: str
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    entry_count: int = 0
    first_usage: Optional[datetime] = None
    last_usage: Optional[datetime] = None


@dataclass
class BudgetAllocation:
    """A budget allocation at any level.

    Attributes:
        budget_id: Unique identifier (e.g., 'swarm:main', 'agent:aurora').
        level: Hierarchy level (swarm, agent, task, session).
        token_limit: Maximum tokens allowed.
        cost_limit: Maximum cost in USD allowed.
        parent_id: Parent budget ID for hierarchy.
        thresholds: Warning/hard-stop thresholds.
        rollover: Whether unused budget rolls over to next period.
        expiration: When this budget expires (None = never).
        created_at: Creation timestamp.
        metadata: Additional context.
    """

    budget_id: str
    level: BudgetLevel = BudgetLevel.AGENT
    token_limit: int = 100_000
    cost_limit: float = 10.0
    parent_id: Optional[str] = None
    thresholds: BudgetThreshold = field(default_factory=BudgetThreshold)
    rollover: bool = False
    expiration: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BudgetReport:
    """Comprehensive budget report.

    Attributes:
        budget_id: Budget being reported on.
        allocation: The budget allocation.
        usage: Aggregated usage.
        status: Current budget status.
        usage_pct_token: Token usage percentage.
        usage_pct_cost: Cost usage percentage.
        remaining_tokens: Tokens remaining.
        remaining_cost: Cost remaining.
        warnings: List of triggered warnings.
        children: Child budget reports (if any).
        generated_at: Report generation timestamp.
    """

    budget_id: str
    allocation: BudgetAllocation
    usage: UsageRecord
    status: BudgetStatus
    usage_pct_token: float
    usage_pct_cost: float
    remaining_tokens: int
    remaining_cost: float
    warnings: list[BudgetWarning] = field(default_factory=list)
    children: list[BudgetReport] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# -- Budget Tracker ----------------------------------------------------------

class BudgetTracker:
    """Hierarchical budget tracker for token usage and cost management.

    Manages budgets at swarm, agent, task, and session levels with
    configurable thresholds, real-time monitoring, and cost tracking.

    Args:
        db_path: Path to SQLite database for persistence.
        model_pricing: Model pricing configuration.
        auto_warn: Automatically log warnings when thresholds crossed.

    Attributes:
        db_path: Database file path.
        model_pricing: Active model pricing.
        auto_warn: Whether to auto-log warnings.
        _lock: Thread safety lock.
    """

    def __init__(
        self,
        db_path: str = "governance.db",
        model_pricing: Optional[ModelPricing] = None,
        auto_warn: bool = True,
    ) -> None:
        self.db_path = db_path
        self.model_pricing = model_pricing or ModelPricing.defaults()
        self.auto_warn = auto_warn
        self._lock = threading.Lock()
        self._init_db()

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
                CREATE TABLE IF NOT EXISTS budget_allocations (
                    budget_id TEXT PRIMARY KEY,
                    level TEXT NOT NULL DEFAULT 'agent',
                    token_limit INTEGER NOT NULL DEFAULT 100000,
                    cost_limit REAL NOT NULL DEFAULT 10.0,
                    parent_id TEXT,
                    thresholds_json TEXT,
                    rollover INTEGER NOT NULL DEFAULT 0,
                    expiration TEXT,
                    created_at TEXT NOT NULL,
                    metadata_json TEXT,
                    FOREIGN KEY (parent_id) REFERENCES budget_allocations(budget_id)
                );

                CREATE TABLE IF NOT EXISTS usage_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    budget_id TEXT NOT NULL,
                    input_tokens INTEGER NOT NULL DEFAULT 0,
                    output_tokens INTEGER NOT NULL DEFAULT 0,
                    total_tokens INTEGER NOT NULL,
                    cost_usd REAL NOT NULL,
                    model TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    metadata_json TEXT,
                    FOREIGN KEY (budget_id) REFERENCES budget_allocations(budget_id)
                );

                CREATE INDEX IF NOT EXISTS idx_usage_budget
                    ON usage_entries(budget_id);
                CREATE INDEX IF NOT EXISTS idx_usage_timestamp
                    ON usage_entries(timestamp);

                CREATE TABLE IF NOT EXISTS budget_warnings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    budget_id TEXT NOT NULL,
                    threshold REAL NOT NULL,
                    usage_pct REAL NOT NULL,
                    message TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    acknowledged INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (budget_id) REFERENCES budget_allocations(budget_id)
                );

                CREATE INDEX IF NOT EXISTS idx_warnings_budget
                    ON budget_warnings(budget_id);
            """)

    def set_budget(
        self,
        budget_id: str,
        token_limit: int = 100_000,
        cost_limit: float = 10.0,
        level: BudgetLevel = BudgetLevel.AGENT,
        parent_id: Optional[str] = None,
        thresholds: Optional[BudgetThreshold] = None,
        rollover: bool = False,
        expiration: Optional[datetime] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> BudgetAllocation:
        """Create or update a budget allocation.

        Args:
            budget_id: Unique identifier for the budget.
            token_limit: Maximum tokens allowed.
            cost_limit: Maximum cost in USD.
            level: Hierarchy level.
            parent_id: Parent budget for hierarchy.
            thresholds: Warning/hard-stop thresholds.
            rollover: Whether unused budget rolls over.
            expiration: Expiration datetime.
            metadata: Additional context.

        Returns:
            The created/updated BudgetAllocation.

        Raises:
            ValueError: If parent_id references non-existent budget.
        """
        thresholds = thresholds or BudgetThreshold()

        if parent_id:
            existing = self.get_allocation(parent_id)
            if existing is None:
                raise ValueError(f"Parent budget '{parent_id}' does not exist")

        allocation = BudgetAllocation(
            budget_id=budget_id,
            level=level,
            token_limit=token_limit,
            cost_limit=cost_limit,
            parent_id=parent_id,
            thresholds=thresholds,
            rollover=rollover,
            expiration=expiration,
            metadata=metadata or {},
        )

        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO budget_allocations
                    (budget_id, level, token_limit, cost_limit, parent_id,
                     thresholds_json, rollover, expiration, created_at, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        allocation.budget_id,
                        allocation.level.value,
                        allocation.token_limit,
                        allocation.cost_limit,
                        allocation.parent_id,
                        json.dumps({
                            "warning_50": allocation.thresholds.warning_50,
                            "warning_75": allocation.thresholds.warning_75,
                            "warning_90": allocation.thresholds.warning_90,
                            "hard_stop": allocation.thresholds.hard_stop,
                            "soft_limit": allocation.thresholds.soft_limit,
                        }),
                        1 if allocation.rollover else 0,
                        allocation.expiration.isoformat() if allocation.expiration else None,
                        allocation.created_at.isoformat(),
                        json.dumps(allocation.metadata),
                    ),
                )

        logger.info("Budget set: %s (tokens=%s, cost=$%.2f)", budget_id, token_limit, cost_limit)
        return allocation

    def get_allocation(self, budget_id: str) -> Optional[BudgetAllocation]:
        """Get a budget allocation by ID.

        Args:
            budget_id: Budget identifier.

        Returns:
            BudgetAllocation if found, None otherwise.
        """
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM budget_allocations WHERE budget_id = ?",
                (budget_id,),
            ).fetchone()

        if row is None:
            return None

        thresholds_data = json.loads(row["thresholds_json"]) if row["thresholds_json"] else {}
        return BudgetAllocation(
            budget_id=row["budget_id"],
            level=BudgetLevel(row["level"]),
            token_limit=row["token_limit"],
            cost_limit=row["cost_limit"],
            parent_id=row["parent_id"],
            thresholds=BudgetThreshold(
                warning_50=thresholds_data.get("warning_50", 0.50),
                warning_75=thresholds_data.get("warning_75", 0.75),
                warning_90=thresholds_data.get("warning_90", 0.90),
                hard_stop=thresholds_data.get("hard_stop", 1.0),
                soft_limit=thresholds_data.get("soft_limit"),
            ),
            rollover=bool(row["rollover"]),
            expiration=datetime.fromisoformat(row["expiration"]) if row["expiration"] else None,
            created_at=datetime.fromisoformat(row["created_at"]),
            metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else {},
        )

    def delete_budget(self, budget_id: str, cascade: bool = False) -> bool:
        """Delete a budget allocation.

        Args:
            budget_id: Budget to delete.
            cascade: Also delete child budgets.

        Returns:
            True if deleted, False if not found.
        """
        with self._lock:
            with self._get_conn() as conn:
                if cascade:
                    children = conn.execute(
                        "SELECT budget_id FROM budget_allocations WHERE parent_id = ?",
                        (budget_id,),
                    ).fetchall()
                    for child in children:
                        self.delete_budget(child["budget_id"], cascade=True)

                cursor = conn.execute(
                    "DELETE FROM budget_allocations WHERE budget_id = ?",
                    (budget_id,),
                )
                conn.execute(
                    "DELETE FROM usage_entries WHERE budget_id = ?",
                    (budget_id,),
                )
                conn.execute(
                    "DELETE FROM budget_warnings WHERE budget_id = ?",
                    (budget_id,),
                )

                return cursor.rowcount > 0

    def record_usage(
        self,
        budget_id: str,
        input_tokens: int,
        output_tokens: int,
        model: str = "unknown",
        metadata: Optional[dict[str, Any]] = None,
    ) -> CostEntry:
        """Record token usage and compute cost.

        Checks budget limits before recording. Raises BudgetExceededError
        if hard stop is reached.

        Args:
            budget_id: Budget to charge.
            input_tokens: Number of input tokens.
            output_tokens: Number of output tokens.
            model: Model name for pricing.
            metadata: Additional context.

        Returns:
            CostEntry with computed cost.

        Raises:
            BudgetExceededError: If budget hard stop is reached.
            ValueError: If budget does not exist.
        """
        allocation = self.get_allocation(budget_id)
        if allocation is None:
            raise ValueError(f"Budget '{budget_id}' does not exist")

        total_tokens = input_tokens + output_tokens
        price_per_token = self.model_pricing.get_price(model)
        cost_usd = total_tokens * price_per_token

        entry = CostEntry(
            budget_id=budget_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            model=model,
            metadata=metadata or {},
        )

        with self._lock:
            with self._get_conn() as conn:
                usage = self._get_usage(conn, budget_id)

                new_token_total = usage.total_tokens + total_tokens
                new_cost_total = usage.total_cost_usd + cost_usd

                token_pct = new_token_total / allocation.token_limit if allocation.token_limit > 0 else 0
                cost_pct = new_cost_total / allocation.cost_limit if allocation.cost_limit > 0 else 0

                if token_pct >= allocation.thresholds.hard_stop or cost_pct >= allocation.thresholds.hard_stop:
                    limit_type = "token" if token_pct >= cost_pct else "cost"
                    usage_pct = max(token_pct, cost_pct)
                    raise BudgetExceededError(
                        budget_id=budget_id,
                        usage_pct=usage_pct,
                        limit_type=limit_type,
                    )

                conn.execute(
                    """
                    INSERT INTO usage_entries
                    (budget_id, input_tokens, output_tokens, total_tokens,
                     cost_usd, model, timestamp, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry.budget_id,
                        entry.input_tokens,
                        entry.output_tokens,
                        entry.total_tokens,
                        entry.cost_usd,
                        entry.model,
                        entry.timestamp.isoformat(),
                        json.dumps(entry.metadata),
                    ),
                )

            self._check_thresholds(budget_id, allocation)

        logger.debug(
            "Usage recorded: %s +%d tokens ($%.4f, model=%s)",
            budget_id, total_tokens, cost_usd, model,
        )
        return entry

    def _get_usage(self, conn: sqlite3.Connection, budget_id: str) -> UsageRecord:
        """Get aggregated usage for a budget.

        Args:
            conn: Database connection.
            budget_id: Budget identifier.

        Returns:
            UsageRecord with aggregated totals.
        """
        row = conn.execute(
            """
            SELECT
                COALESCE(SUM(input_tokens), 0) as total_input,
                COALESCE(SUM(output_tokens), 0) as total_output,
                COALESCE(SUM(total_tokens), 0) as total_tokens,
                COALESCE(SUM(cost_usd), 0) as total_cost,
                COUNT(*) as entry_count,
                MIN(timestamp) as first_ts,
                MAX(timestamp) as last_ts
            FROM usage_entries
            WHERE budget_id = ?
            """,
            (budget_id,),
        ).fetchone()

        return UsageRecord(
            budget_id=budget_id,
            total_input_tokens=row["total_input"],
            total_output_tokens=row["total_output"],
            total_tokens=row["total_tokens"],
            total_cost_usd=row["total_cost"],
            entry_count=row["entry_count"],
            first_usage=datetime.fromisoformat(row["first_ts"]) if row["first_ts"] else None,
            last_usage=datetime.fromisoformat(row["last_ts"]) if row["last_ts"] else None,
        )

    def _check_thresholds(
        self,
        budget_id: str,
        allocation: BudgetAllocation,
    ) -> list[BudgetWarning]:
        """Check and record threshold warnings.

        Args:
            budget_id: Budget to check.
            allocation: Budget allocation.

        Returns:
            List of new warnings triggered.
        """
        usage = self._get_usage(self._get_conn(), budget_id)
        token_pct = usage.total_tokens / allocation.token_limit if allocation.token_limit > 0 else 0
        cost_pct = usage.total_cost_usd / allocation.cost_limit if allocation.cost_limit > 0 else 0
        usage_pct = max(token_pct, cost_pct)

        warnings = []
        thresholds = [
            (allocation.thresholds.warning_90, "90%"),
            (allocation.thresholds.warning_75, "75%"),
            (allocation.thresholds.warning_50, "50%"),
        ]

        for threshold, label in thresholds:
            if usage_pct >= threshold:
                existing = self._get_last_warning(budget_id, threshold)
                if existing is None or (datetime.now(timezone.utc) - existing).hours > 1:
                    warning = BudgetWarning(
                        budget_id=budget_id,
                        threshold=threshold,
                        usage_pct=usage_pct,
                        message=f"Budget '{budget_id}' at {label} usage ({usage_pct:.1%})",
                    )
                    self._record_warning(warning)
                    warnings.append(warning)

                    if self.auto_warn:
                        logger.warning(warning.message)

        return warnings

    def _get_last_warning(self, budget_id: str, threshold: float) -> Optional[datetime]:
        """Get timestamp of last warning for a threshold.

        Args:
            budget_id: Budget identifier.
            threshold: Threshold level.

        Returns:
            Timestamp of last warning, or None.
        """
        with self._get_conn() as conn:
            row = conn.execute(
                """
                SELECT MAX(timestamp) as last_ts
                FROM budget_warnings
                WHERE budget_id = ? AND threshold = ?
                """,
                (budget_id, threshold),
            ).fetchone()
            return datetime.fromisoformat(row["last_ts"]) if row["last_ts"] else None

    def _record_warning(self, warning: BudgetWarning) -> None:
        """Record a budget warning.

        Args:
            warning: Warning to record.
        """
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO budget_warnings
                (budget_id, threshold, usage_pct, message, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    warning.budget_id,
                    warning.threshold,
                    warning.usage_pct,
                    warning.message,
                    warning.timestamp.isoformat(),
                ),
            )

    def get_status(self, budget_id: str) -> BudgetStatus:
        """Get current budget status.

        Args:
            budget_id: Budget identifier.

        Returns:
            BudgetStatus enum value.

        Raises:
            ValueError: If budget does not exist.
        """
        allocation = self.get_allocation(budget_id)
        if allocation is None:
            raise ValueError(f"Budget '{budget_id}' does not exist")

        if allocation.expiration and datetime.now(timezone.utc) > allocation.expiration:
            return BudgetStatus.EXPIRED

        usage = self._get_usage(self._get_conn(), budget_id)
        token_pct = usage.total_tokens / allocation.token_limit if allocation.token_limit > 0 else 0
        cost_pct = usage.total_cost_usd / allocation.cost_limit if allocation.cost_limit > 0 else 0
        usage_pct = max(token_pct, cost_pct)

        if usage_pct >= allocation.thresholds.hard_stop:
            return BudgetStatus.EXCEEDED
        elif usage_pct >= allocation.thresholds.warning_90:
            return BudgetStatus.WARNING_90
        elif usage_pct >= allocation.thresholds.warning_75:
            return BudgetStatus.WARNING_75
        elif usage_pct >= allocation.thresholds.warning_50:
            return BudgetStatus.WARNING_50
        else:
            return BudgetStatus.OK

    def get_usage(self, budget_id: str) -> UsageRecord:
        """Get aggregated usage for a budget.

        Args:
            budget_id: Budget identifier.

        Returns:
            UsageRecord with aggregated totals.

        Raises:
            ValueError: If budget does not exist.
        """
        if self.get_allocation(budget_id) is None:
            raise ValueError(f"Budget '{budget_id}' does not exist")

        return self._get_usage(self._get_conn(), budget_id)

    def get_remaining(self, budget_id: str) -> tuple[int, float]:
        """Get remaining budget (tokens, cost).

        Args:
            budget_id: Budget identifier.

        Returns:
            Tuple of (remaining_tokens, remaining_cost_usd).

        Raises:
            ValueError: If budget does not exist.
        """
        allocation = self.get_allocation(budget_id)
        if allocation is None:
            raise ValueError(f"Budget '{budget_id}' does not exist")

        usage = self._get_usage(self._get_conn(), budget_id)
        remaining_tokens = max(0, allocation.token_limit - usage.total_tokens)
        remaining_cost = max(0.0, allocation.cost_limit - usage.total_cost_usd)
        return remaining_tokens, remaining_cost

    def can_spend(self, budget_id: str, tokens: int, cost: float = 0.0) -> bool:
        """Check if a budget can afford a proposed spend.

        Args:
            budget_id: Budget to check.
            tokens: Proposed token spend.
            cost: Proposed cost spend.

        Returns:
            True if budget can afford the spend.
        """
        try:
            remaining_tokens, remaining_cost = self.get_remaining(budget_id)
            return remaining_tokens >= tokens and remaining_cost >= cost
        except ValueError:
            return False

    def get_hierarchy(self, budget_id: str) -> list[BudgetAllocation]:
        """Get the full hierarchy chain from budget to root.

        Args:
            budget_id: Starting budget.

        Returns:
            List of allocations from leaf to root.
        """
        chain = []
        current_id = budget_id

        while current_id:
            allocation = self.get_allocation(current_id)
            if allocation is None:
                break
            chain.append(allocation)
            current_id = allocation.parent_id

        return chain

    def get_children(self, budget_id: str) -> list[BudgetAllocation]:
        """Get direct child budgets.

        Args:
            budget_id: Parent budget.

        Returns:
            List of child allocations.
        """
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM budget_allocations WHERE parent_id = ?",
                (budget_id,),
            ).fetchall()

        children = []
        for row in rows:
            thresholds_data = json.loads(row["thresholds_json"]) if row["thresholds_json"] else {}
            children.append(BudgetAllocation(
                budget_id=row["budget_id"],
                level=BudgetLevel(row["level"]),
                token_limit=row["token_limit"],
                cost_limit=row["cost_limit"],
                parent_id=row["parent_id"],
                thresholds=BudgetThreshold(
                    warning_50=thresholds_data.get("warning_50", 0.50),
                    warning_75=thresholds_data.get("warning_75", 0.75),
                    warning_90=thresholds_data.get("warning_90", 0.90),
                    hard_stop=thresholds_data.get("hard_stop", 1.0),
                    soft_limit=thresholds_data.get("soft_limit"),
                ),
                rollover=bool(row["rollover"]),
                expiration=datetime.fromisoformat(row["expiration"]) if row["expiration"] else None,
                created_at=datetime.fromisoformat(row["created_at"]),
                metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else {},
            ))

        return children

    def generate_report(self, budget_id: str, include_children: bool = True) -> BudgetReport:
        """Generate a comprehensive budget report.

        Args:
            budget_id: Budget to report on.
            include_children: Include child budget reports.

        Returns:
            BudgetReport with full analysis.

        Raises:
            ValueError: If budget does not exist.
        """
        allocation = self.get_allocation(budget_id)
        if allocation is None:
            raise ValueError(f"Budget '{budget_id}' does not exist")

        usage = self._get_usage(self._get_conn(), budget_id)
        status = self.get_status(budget_id)

        token_pct = usage.total_tokens / allocation.token_limit if allocation.token_limit > 0 else 0
        cost_pct = usage.total_cost_usd / allocation.cost_limit if allocation.cost_limit > 0 else 0

        remaining_tokens = max(0, allocation.token_limit - usage.total_tokens)
        remaining_cost = max(0.0, allocation.cost_limit - usage.total_cost_usd)

        warnings = self._get_warnings(budget_id)

        report = BudgetReport(
            budget_id=budget_id,
            allocation=allocation,
            usage=usage,
            status=status,
            usage_pct_token=token_pct,
            usage_pct_cost=cost_pct,
            remaining_tokens=remaining_tokens,
            remaining_cost=remaining_cost,
            warnings=warnings,
        )

        if include_children:
            for child in self.get_children(budget_id):
                child_report = self.generate_report(child.budget_id, include_children=True)
                report.children.append(child_report)

        return report

    def _get_warnings(self, budget_id: str) -> list[BudgetWarning]:
        """Get all warnings for a budget.

        Args:
            budget_id: Budget identifier.

        Returns:
            List of BudgetWarning objects.
        """
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM budget_warnings
                WHERE budget_id = ?
                ORDER BY timestamp DESC
                """,
                (budget_id,),
            ).fetchall()

        return [
            BudgetWarning(
                budget_id=row["budget_id"],
                threshold=row["threshold"],
                usage_pct=row["usage_pct"],
                message=row["message"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
            )
            for row in rows
        ]

    def get_usage_history(
        self,
        budget_id: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[CostEntry]:
        """Get usage history for a budget.

        Args:
            budget_id: Budget identifier.
            since: Start time filter.
            until: End time filter.
            limit: Maximum entries to return.

        Returns:
            List of CostEntry objects.
        """
        query = "SELECT * FROM usage_entries WHERE budget_id = ?"
        params: list[Any] = [budget_id]

        if since:
            query += " AND timestamp >= ?"
            params.append(since.isoformat())
        if until:
            query += " AND timestamp <= ?"
            params.append(until.isoformat())

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with self._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()

        return [
            CostEntry(
                budget_id=row["budget_id"],
                input_tokens=row["input_tokens"],
                output_tokens=row["output_tokens"],
                total_tokens=row["total_tokens"],
                cost_usd=row["cost_usd"],
                model=row["model"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else {},
            )
            for row in rows
        ]

    def reset_usage(self, budget_id: str, since: Optional[datetime] = None) -> int:
        """Reset usage entries for a budget.

        Args:
            budget_id: Budget to reset.
            since: Only reset entries since this time (for rollover).

        Returns:
            Number of entries deleted.
        """
        with self._lock:
            with self._get_conn() as conn:
                if since:
                    cursor = conn.execute(
                        "DELETE FROM usage_entries WHERE budget_id = ? AND timestamp >= ?",
                        (budget_id, since.isoformat()),
                    )
                else:
                    cursor = conn.execute(
                        "DELETE FROM usage_entries WHERE budget_id = ?",
                        (budget_id,),
                    )
                return cursor.rowcount

    def get_analytics(
        self,
        budget_id: Optional[str] = None,
        period: str = "24h",
    ) -> dict[str, Any]:
        """Get budget analytics.

        Args:
            budget_id: Specific budget, or None for all.
            period: Time period ('1h', '24h', '7d', '30d').

        Returns:
            Dictionary with analytics data.
        """
        period_map = {
            "1h": timedelta(hours=1),
            "24h": timedelta(hours=24),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30),
        }
        delta = period_map.get(period, timedelta(hours=24))
        since = datetime.now(timezone.utc) - delta

        query = """
            SELECT
                budget_id,
                COUNT(*) as entries,
                SUM(input_tokens) as total_input,
                SUM(output_tokens) as total_output,
                SUM(total_tokens) as total_tokens,
                SUM(cost_usd) as total_cost,
                MIN(timestamp) as first_ts,
                MAX(timestamp) as last_ts
            FROM usage_entries
            WHERE timestamp >= ?
        """
        params: list[Any] = [since.isoformat()]

        if budget_id:
            query += " AND budget_id = ?"
            params.append(budget_id)

        query += " GROUP BY budget_id"

        with self._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()

        analytics: dict[str, Any] = {
            "period": period,
            "since": since.isoformat(),
            "budgets": {},
            "totals": {
                "entries": 0,
                "total_input": 0,
                "total_output": 0,
                "total_tokens": 0,
                "total_cost": 0.0,
            },
        }

        for row in rows:
            budget_data = {
                "entries": row["entries"],
                "total_input": row["total_input"],
                "total_output": row["total_output"],
                "total_tokens": row["total_tokens"],
                "total_cost": row["total_cost"],
                "first_usage": row["first_ts"],
                "last_usage": row["last_ts"],
            }
            analytics["budgets"][row["budget_id"]] = budget_data
            analytics["totals"]["entries"] += row["entries"]
            analytics["totals"]["total_input"] += row["total_input"] or 0
            analytics["totals"]["total_output"] += row["total_output"] or 0
            analytics["totals"]["total_tokens"] += row["total_tokens"] or 0
            analytics["totals"]["total_cost"] += row["total_cost"] or 0

        return analytics

    def close(self) -> None:
        """Close database connections (no-op for sqlite3, but good practice)."""
        pass

    def __enter__(self) -> "BudgetTracker":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
