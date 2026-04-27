"""
NEUGI v2 Governance Layer
=========================

Production-ready governance system combining budget tracking, approval gates,
audit logging, and policy enforcement for autonomous multi-agent operations.

Subsystems:
    - budget: Token/cost budget tracking with hierarchical allocation
    - approval: Configurable approval gates with multi-level chains
    - audit: Immutable audit logging with SQLite append-only storage
    - policy: Rule-based policy engine with default-deny semantics

Usage:
    from neugi_swarm_v2.governance import (
        BudgetTracker, ApprovalGate, AuditLogger, PolicyEngine,
    )

    tracker = BudgetTracker(db_path="governance.db")
    gate = ApprovalGate(db_path="governance.db")
    logger = AuditLogger(db_path="governance.db")
    engine = PolicyEngine()
"""

from __future__ import annotations

# -- Budget Tracking ---------------------------------------------------------

from .budget import (
    BudgetTracker,
    BudgetAllocation,
    BudgetReport,
    BudgetLevel,
    BudgetStatus,
    BudgetThreshold,
    BudgetExceededError,
    BudgetWarning,
    CostEntry,
    ModelPricing,
    UsageRecord,
)

# -- Approval Gates ----------------------------------------------------------

from .approval import (
    ApprovalGate,
    ApprovalRule,
    ApprovalRequest,
    ApprovalDecision,
    ApprovalStatus,
    ApprovalChain,
    ApprovalTimeoutError,
    ApprovalHistory,
)

# -- Audit Logging -----------------------------------------------------------

from .audit import (
    AuditLogger,
    AuditEntry,
    AuditEventType,
    AuditExportFormat,
    AuditReport,
    RetentionPolicy,
    ToolCallRecord,
    DecisionRecord,
    SessionAudit,
    AuditError,
)

# -- Policy Engine -----------------------------------------------------------

from .policy import (
    PolicyEngine,
    Policy,
    PolicyRule,
    PolicyEffect,
    PolicyCondition,
    PolicyEvaluation,
    PolicyEvaluationResult,
    PolicyOverride,
    PolicyError,
    ConditionOperator,
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
    "ApprovalChain",
    "ApprovalTimeoutError",
    "ApprovalHistory",
    # Audit
    "AuditLogger",
    "AuditEntry",
    "AuditEventType",
    "AuditExportFormat",
    "AuditReport",
    "RetentionPolicy",
    "ToolCallRecord",
    "DecisionRecord",
    "SessionAudit",
    "AuditError",
    # Policy
    "PolicyEngine",
    "Policy",
    "PolicyRule",
    "PolicyEffect",
    "PolicyCondition",
    "PolicyEvaluation",
    "PolicyEvaluationResult",
    "PolicyOverride",
    "PolicyError",
    "ConditionOperator",
]
