"""
NEUGI v2 Security Sandbox
=========================

Neuro-symbolic security system for agentic AI — combining symbolic rule engines
with neural risk assessment for defense-in-depth.

Subsystems:
    sandbox: Execution sandbox with resource limits and isolation
    command_validator: Neuro-symbolic command safety assessment
    secret_manager: Encrypted secret lifecycle management

Usage:
    from neugi_swarm_v2.security import (
        ExecutionSandbox,
        CommandValidator,
        SecretManager,
    )
"""

from security.command_validator import (
    CommandValidator,
    CommandVerdict,
    SafetyLevel,
)
from security.sandbox import ExecutionSandbox, SandboxConfig, SandboxViolation
from security.secret_manager import (
    SecretClass,
    SecretDecryptionError,
    SecretEntry,
    SecretManager,
    SecretNotFoundError,
    SecretStatus,
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
    # Secret Manager
    "SecretManager",
    "SecretEntry",
    "SecretClass",
    "SecretStatus",
    "SecretNotFoundError",
    "SecretDecryptionError",
]
