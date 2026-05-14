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

from .command_validator import (
    CommandValidator,
    CommandVerdict,
    NeuralRiskScorer,
    SafetyLevel,
    SymbolicRuleEngine,
)
from .exploit_prevention import (
    DataExfiltrationDetector,
    ExploitPreventionEngine,
    PromptInjectionDetector,
    SupplyChainDetector,
    ThreatReport,
    ThreatVector,
)
from .sandbox import ExecutionSandbox, SandboxConfig, SandboxViolation
from .secret_manager import (
    SecretClass,
    SecretEntry,
    SecretManager,
    SecretStatus,
)
from .shield_reasoning import (
    RiskScore,
    SecurityPosture,
    SecurityRecommendation,
    ShieldReasoner,
    ThreatClassification,
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
