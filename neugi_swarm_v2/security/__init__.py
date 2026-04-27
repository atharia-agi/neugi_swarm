"""
NEUGI v2 Security Sandbox
=========================

Neuro-symbolic security system for agentic AI — combining symbolic rule engines
with neural risk assessment for defense-in-depth exploit prevention.

Subsystems:
    sandbox: Execution sandbox with resource limits and isolation
    command_validator: Neuro-symbolic command safety assessment
    exploit_prevention: Multi-vector attack detection and prevention
    secret_manager: Encrypted secret lifecycle management
    shield_reasoning: Explainable security decisions and posture assessment

Usage:
    from neugi_swarm_v2.security import (
        ExecutionSandbox,
        CommandValidator,
        ExploitPreventionEngine,
        SecretManager,
        ShieldReasoner,
    )
"""

from .sandbox import ExecutionSandbox, SandboxConfig, SandboxViolation
from .command_validator import (
    CommandValidator,
    CommandVerdict,
    SafetyLevel,
    SymbolicRuleEngine,
    NeuralRiskScorer,
)
from .exploit_prevention import (
    ExploitPreventionEngine,
    ThreatVector,
    ThreatReport,
    PromptInjectionDetector,
    DataExfiltrationDetector,
    SupplyChainDetector,
)
from .secret_manager import (
    SecretManager,
    SecretEntry,
    SecretClass,
    SecretStatus,
)
from .shield_reasoning import (
    ShieldReasoner,
    RiskScore,
    ThreatClassification,
    SecurityPosture,
    SecurityRecommendation,
)

__all__ = [
    # Sandbox
    "ExecutionSandbox",
    "SandboxConfig",
    "SandboxViolation",
    # Command Validator
    "CommandValidator",
    "CommandVerdict",
    "SafetyLevel",
    "SymbolicRuleEngine",
    "NeuralRiskScorer",
    # Exploit Prevention
    "ExploitPreventionEngine",
    "ThreatVector",
    "ThreatReport",
    "PromptInjectionDetector",
    "DataExfiltrationDetector",
    "SupplyChainDetector",
    # Secret Manager
    "SecretManager",
    "SecretEntry",
    "SecretClass",
    "SecretStatus",
    # Shield Reasoning
    "ShieldReasoner",
    "RiskScore",
    "ThreatClassification",
    "SecurityPosture",
    "SecurityRecommendation",
]
