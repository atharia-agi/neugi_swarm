"""
NEUGI v2 Governance Layer
=========================

Production-ready governance system combining budget tracking and approval gates
for autonomous multi-agent operations.

Subsystems:
    - budget: Token/cost budget tracking with hierarchical allocation
    - approval: Configurable approval gates with multi-level chains

Usage:
    from neugi_swarm_v2.governance import BudgetTracker, ApprovalGate

    tracker = BudgetTracker(db_path="governance.db")
    gate = ApprovalGate(db_path="governance.db")
"""

from __future__ import annotations

# -- Approval Gates ----------------------------------------------------------
from governance.approval import (
    ApprovalDecision,
    ApprovalGate,
    ApprovalRequest,
    ApprovalRule,
    ApprovalStatus,
    ApprovalTimeoutError,
)

# -- Budget Tracking ---------------------------------------------------------
from governance.budget import (
    BudgetAllocation,
    BudgetExceededError,
    BudgetLevel,
    BudgetReport,
    BudgetStatus,
    BudgetThreshold,
    BudgetTracker,
    BudgetWarning,
    CostEntry,
    ModelPricing,
    UsageRecord,
)

__all__ = [
    # Budget
    "BudgetTracker",
    "BudgetAllocation",
    "BudgetReport",
    "BudgetLevel",
    "BudgetStatus",
    "BudgetThreshold",
    "BudgetExceededError",
    "BudgetWarning",
    "CostEntry",
    "ModelPricing",
    "UsageRecord",
    # Approval
    "ApprovalGate",
    "ApprovalRule",
    "ApprovalRequest",
    "ApprovalDecision",
    "ApprovalStatus",
    "ApprovalTimeoutError",
]
