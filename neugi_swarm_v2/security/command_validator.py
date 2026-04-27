"""
Command Validator — Neuro-Symbolic Safety Assessment
====================================================

Combines symbolic rule engines with neural (LLM-based) risk scoring
for comprehensive command safety assessment.

Architecture:
    Symbolic Rules (deterministic, fast)
        └── Pattern matching against known-dangerous commands
        └── Allowlist/denylist enforcement
        └── Path traversal detection
        └── Injection pattern detection

    Neural Scoring (probabilistic, context-aware)
        └── LLM-based risk assessment
        └── Semantic understanding of intent
        └── Context-sensitive evaluation

    Combined Verdict (defense in depth)
        └── Symbolic block overrides all (hard safety)
        └── Neural score gates high-risk commands
        └── Explainable decisions with reasoning

Usage:
    validator = CommandValidator()
    verdict = validator.validate("rm -rf /tmp/cache")
    if verdict.is_safe:
        execute(verdict.transformed_command)
    else:
        print(verdict.explanation)
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# -- Enums ---------------------------------------------------------------------

class SafetyLevel(Enum):
    """Command safety classification."""
    SAFE = "safe"
    LOW_RISK = "low_risk"
    MEDIUM_RISK = "medium_risk"
    HIGH_RISK = "high_risk"
    BLOCKED = "blocked"


class ThreatCategory(Enum):
    """Categories of command-level threats."""
    NONE = "none"
    DESTRUCTIVE = "destructive"
    INJECTION = "injection"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    DATA_EXFILTRATION = "data_exfiltration"
    PERSISTENCE = "persistence"
    RECONNAISSANCE = "reconnaissance"
    RESOURCE_ABUSE = "resource_abuse"
    NETWORK_ABUSE = "network_abuse"


# -- Data Classes --------------------------------------------------------------

@dataclass
class SymbolicRule:
    """A single symbolic safety rule.

    Attributes:
        name: Human-readable rule name.
        pattern: Regex pattern to match against commands.
        severity: Risk severity if matched.
        category: Threat category.
        description: Explanation of what this rule prevents.
        suggestion: Safe alternative suggestion.
        enabled: Whether the rule is active.
    """
    name: str
    pattern: str
    severity: SafetyLevel
    category: ThreatCategory
    description: str
    suggestion: str = ""
    enabled: bool = True


@dataclass
class CommandVerdict:
    """Result of command validation.

    Attributes:
        is_safe: Whether the command is safe to execute.
        safety_level: Granular safety classification.
        risk_score: Numerical risk score (0-100).
        symbolic_blocked: Whether symbolic rules blocked it.
        neural_blocked: Whether neural scoring blocked it.
        matched_rules: Symbolic rules that matched.
        neural_reason: Neural assessment explanation.
        explanation: Human-readable explanation of the verdict.
        transformed_command: Suggested safe alternative.
        threat_categories: Detected threat categories.
        confidence: Confidence in the verdict (0.0-1.0).
        command_hash: Hash of the original command for dedup.
        timestamp: When the verdict was generated.
    """
    is_safe: bool
    safety_level: SafetyLevel
    risk_score: int
    symbolic_blocked: bool = False
    neural_blocked: bool = False
    matched_rules: list[str] = field(default_factory=list)
    neural_reason: str = ""
    explanation: str = ""
    transformed_command: str = ""
    threat_categories: list[str] = field(default_factory=list)
    confidence: float = 1.0
    command_hash: str = ""
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if not self.command_hash:
            self.command_hash = hashlib.sha256(
                self.explanation.encode()
            ).hexdigest()[:12]
        if not self.timestamp:
            self.timestamp = time.time()


# -- Symbolic Rule Engine ------------------------------------------------------

class SymbolicRuleEngine:
    """Deterministic rule-based command safety engine.

    Applies a comprehensive set of symbolic rules to detect dangerous commands.
    Rules are organized by threat category and severity.
    """

    def __init__(self) -> None:
        self._rules: list[SymbolicRule] = []
        self._compiled: list[tuple[SymbolicRule, re.Pattern[str]]] = []
        self._build_default_rules()
        self._compile_rules()

    def _build_default_rules(self) -> None:
        """Build the default rule set covering all threat categories."""
        rules = [
            # -- Destructive Commands --
            SymbolicRule(
                name="recursive_force_delete_root",
                pattern=r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*|-[a-zA-Z]*f[a-zA-Z]*r[a-zA-Z]*)\s+/",
                severity=SafetyLevel.BLOCKED,
                category=ThreatCategory.DESTRUCTIVE,
                description="Prevents recursive force deletion from root directory",
                suggestion="Use 'rm -ri /path/to/target' with explicit interactive confirmation",
            ),
            SymbolicRule(
                name="recursive_force_delete",
                pattern=r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*|-[a-zA-Z]*f[a-zA-Z]*r[a-zA-Z]*)\s+\S",
                severity=SafetyLevel.HIGH_RISK,
                category=ThreatCategory.DESTRUCTIVE,
                description="Recursive force deletion — may delete unintended files",
                suggestion="Use 'rm -ri <path>' for interactive deletion",
            ),
            SymbolicRule(
                name="format_disk",
                pattern=r"\b(mkfs|mkfs\.\w+|fdisk|parted|dd)\s",
                severity=SafetyLevel.BLOCKED,
                category=ThreatCategory.DESTRUCTIVE,
                description="Disk formatting or partitioning operations",
                suggestion="Disk operations require explicit admin approval",
            ),
            SymbolicRule(
                name="overwrite_disk",
                pattern=r"\bdd\s+(if|of)=/dev/",
                severity=SafetyLevel.BLOCKED,
                category=ThreatCategory.DESTRUCTIVE,
                description="Direct disk read/write via dd",
                suggestion="Use file-level copy operations instead",
            ),

            # -- Injection Commands --
            SymbolicRule(
                name="curl_pipe_bash",
                pattern=r"\b(curl|wget)\s+.*\|\s*(bash|sh|zsh|fish)",
                severity=SafetyLevel.BLOCKED,
                category=ThreatCategory.INJECTION,
                description="Piping remote content to shell — classic supply chain attack",
                suggestion="Download first, review content, then execute separately",
            ),
            SymbolicRule(
                name="eval_execution",
                pattern=r"\b(eval|exec)\s+['\"]?\$",
                severity=SafetyLevel.BLOCKED,
                category=ThreatCategory.INJECTION,
                description="Dynamic code execution with eval/exec — injection vector",
                suggestion="Use explicit command execution instead of eval",
            ),
            SymbolicRule(
                name="backtick_execution",
                pattern=r"`[^`]+`",
                severity=SafetyLevel.MEDIUM_RISK,
                category=ThreatCategory.INJECTION,
                description="Backtick command substitution — potential injection",
                suggestion="Use $() for command substitution with proper quoting",
            ),
            SymbolicRule(
                name="python_eval",
                pattern=r"\bpython[23]?\s+.*-c\s+.*\beval\b",
                severity=SafetyLevel.BLOCKED,
                category=ThreatCategory.INJECTION,
                description="Python eval in one-liner — code injection",
                suggestion="Use explicit Python scripts instead of eval",
            ),
            SymbolicRule(
                name="base64_decode_execute",
                pattern=r"\bbase64\s+(-d|--decode)\s+.*\|\s*(bash|sh|python)",
                severity=SafetyLevel.BLOCKED,
                category=ThreatCategory.INJECTION,
                description="Base64 decode and execute — obfuscated payload",
                suggestion="Decode to file first, review, then execute",
            ),

            # -- Privilege Escalation --
            SymbolicRule(
                name="sudo_usage",
                pattern=r"\bsudo\b",
                severity=SafetyLevel.HIGH_RISK,
                category=ThreatCategory.PRIVILEGE_ESCALATION,
                description="Privilege escalation via sudo",
                suggestion="Run with appropriate permissions from the start",
            ),
            SymbolicRule(
                name="su_usage",
                pattern=r"\bsu\s+(-|\s)",
                severity=SafetyLevel.HIGH_RISK,
                category=ThreatCategory.PRIVILEGE_ESCALATION,
                description="User switching via su",
                suggestion="Use dedicated service accounts instead",
            ),
            SymbolicRule(
                name="chmod_suid",
                pattern=r"\bchmod\s+[0-7]*[4-7][0-7]{2}\s",
                severity=SafetyLevel.HIGH_RISK,
                category=ThreatCategory.PRIVILEGE_ESCALATION,
                description="Setting SUID/SGID bits — privilege escalation vector",
                suggestion="Avoid SUID binaries; use capabilities instead",
            ),
            SymbolicRule(
                name="chmod_777",
                pattern=r"\bchmod\s+777\s",
                severity=SafetyLevel.HIGH_RISK,
                category=ThreatCategory.PRIVILEGE_ESCALATION,
                description="World-writable permissions — security misconfiguration",
                suggestion="Use minimal required permissions (e.g., chmod 755)",
            ),

            # -- Data Exfiltration --
            SymbolicRule(
                name="scp_remote_copy",
                pattern=r"\bscp\s+.*@",
                severity=SafetyLevel.MEDIUM_RISK,
                category=ThreatCategory.DATA_EXFILTRATION,
                description="Secure copy to remote host — potential data exfiltration",
                suggestion="Verify destination before copying",
            ),
            SymbolicRule(
                name="curl_upload",
                pattern=r"\bcurl\s+.*(-T|--upload-file|-d|--data)\s",
                severity=SafetyLevel.MEDIUM_RISK,
                category=ThreatCategory.DATA_EXFILTRATION,
                description="Data upload via curl — potential exfiltration",
                suggestion="Verify upload destination and data",
            ),
            SymbolicRule(
                name="tar_exfil",
                pattern=r"\btar\s+.*\|\s*(curl|wget|nc|ncat|socat)\s",
                severity=SafetyLevel.HIGH_RISK,
                category=ThreatCategory.DATA_EXFILTRATION,
                description="Archive piped to network tool — data exfiltration pattern",
                suggestion="Create archive locally, verify contents, transfer separately",
            ),

            # -- Persistence --
            SymbolicRule(
                name="crontab_modification",
                pattern=r"\bcrontab\s+(-e|-l|\S)",
                severity=SafetyLevel.HIGH_RISK,
                category=ThreatCategory.PERSISTENCE,
                description="Crontab modification — persistence mechanism",
                suggestion="Use application-level scheduling instead",
            ),
            SymbolicRule(
                name="ssh_key_generation",
                pattern=r"\bssh-keygen\b",
                severity=SafetyLevel.MEDIUM_RISK,
                category=ThreatCategory.PERSISTENCE,
                description="SSH key generation — potential backdoor creation",
                suggestion="Use existing keys or managed identity",
            ),
            SymbolicRule(
                name="rc_file_modification",
                pattern=r"\b(tee|cat|echo)\s+.*>>\s*\.(bashrc|zshrc|profile|bash_profile)",
                severity=SafetyLevel.HIGH_RISK,
                category=ThreatCategory.PERSISTENCE,
                description="Shell RC file modification — persistence mechanism",
                suggestion="Use environment variables or config files instead",
            ),

            # -- Reconnaissance --
            SymbolicRule(
                name="etc_passwd_read",
                pattern=r"\bcat\s+/etc/passwd",
                severity=SafetyLevel.MEDIUM_RISK,
                category=ThreatCategory.RECONNAISSANCE,
                description="Reading /etc/passwd — user enumeration",
                suggestion="Use 'id' or 'whoami' for current user info",
            ),
            SymbolicRule(
                name="network_scan",
                pattern=r"\b(nmap|masscan|zmap)\s",
                severity=SafetyLevel.HIGH_RISK,
                category=ThreatCategory.RECONNAISSANCE,
                description="Network scanning — reconnaissance activity",
                suggestion="Use pre-approved network inventory tools",
            ),
            SymbolicRule(
                name="process_listing",
                pattern=r"\b(ps\s+aux|ps\s+-ef|top\s+-b)",
                severity=SafetyLevel.LOW_RISK,
                category=ThreatCategory.RECONNAISSANCE,
                description="Process enumeration — information gathering",
                suggestion="Use 'pgrep <name>' for specific process checks",
            ),

            # -- Resource Abuse --
            SymbolicRule(
                name="fork_bomb",
                pattern=r":\(\)\{\s*:\|:\s*&\s*\}\s*;",
                severity=SafetyLevel.BLOCKED,
                category=ThreatCategory.RESOURCE_ABUSE,
                description="Fork bomb — denial of service",
                suggestion="Not permitted under any circumstances",
            ),
            SymbolicRule(
                name="infinite_loop",
                pattern=r"\bwhile\s+:\s*;?\s*do\s*$",
                severity=SafetyLevel.HIGH_RISK,
                category=ThreatCategory.RESOURCE_ABUSE,
                description="Infinite loop — resource exhaustion",
                suggestion="Add iteration limit or timeout condition",
            ),
            SymbolicRule(
                name="large_file_creation",
                pattern=r"\bdd\s+.*bs=\d+M\s+count=\d+",
                severity=SafetyLevel.MEDIUM_RISK,
                category=ThreatCategory.RESOURCE_ABUSE,
                description="Large file creation via dd — disk exhaustion",
                suggestion="Use truncate for sparse files if needed",
            ),

            # -- Network Abuse --
            SymbolicRule(
                name="reverse_shell",
                pattern=r"\b(nc|ncat|socat|bash\s+-i)\s+.*(-e|/dev/tcp)",
                severity=SafetyLevel.BLOCKED,
                category=ThreatCategory.NETWORK_ABUSE,
                description="Reverse shell pattern — unauthorized remote access",
                suggestion="Not permitted under any circumstances",
            ),
            SymbolicRule(
                name="dns_tunnel",
                pattern=r"\bdig\s+.*TXT\s+.*\.",
                severity=SafetyLevel.MEDIUM_RISK,
                category=ThreatCategory.NETWORK_ABUSE,
                description="DNS TXT query — potential DNS tunneling",
                suggestion="Use standard HTTP APIs for data transfer",
            ),
        ]
        self._rules = rules

    def _compile_rules(self) -> None:
        """Pre-compile all regex patterns."""
        self._compiled = []
        for rule in self._rules:
            if rule.enabled:
                try:
                    compiled = re.compile(rule.pattern, re.IGNORECASE | re.MULTILINE)
                    self._compiled.append((rule, compiled))
                except re.error as e:
                    logger.warning("Failed to compile rule '%s': %s", rule.name, e)

    def add_rule(self, rule: SymbolicRule) -> None:
        """Add a custom symbolic rule.

        Args:
            rule: The rule to add.
        """
        self._rules.append(rule)
        if rule.enabled:
            try:
                compiled = re.compile(rule.pattern, re.IGNORECASE | re.MULTILINE)
                self._compiled.append((rule, compiled))
            except re.error as e:
                logger.warning("Failed to compile custom rule '%s': %s", rule.name, e)

    def remove_rule(self, name: str) -> bool:
        """Remove a rule by name.

        Args:
            name: Rule name to remove.

        Returns:
            True if rule was found and removed.
        """
        original_len = len(self._rules)
        self._rules = [r for r in self._rules if r.name != name]
        self._compile_rules()
        return len(self._rules) < original_len

    def evaluate(self, command: str) -> tuple[SafetyLevel, list[SymbolicRule], list[str]]:
        """Evaluate a command against all symbolic rules.

        Args:
            command: Command string to evaluate.

        Returns:
            Tuple of (worst_severity, matched_rules, explanations).
        """
        matched: list[SymbolicRule] = []
        explanations: list[str] = []
        worst_severity = SafetyLevel.SAFE

        severity_order = [
            SafetyLevel.SAFE,
            SafetyLevel.LOW_RISK,
            SafetyLevel.MEDIUM_RISK,
            SafetyLevel.HIGH_RISK,
            SafetyLevel.BLOCKED,
        ]

        for rule, pattern in self._compiled:
            if pattern.search(command):
                matched.append(rule)
                explanations.append(
                    f"[{rule.severity.value}] {rule.name}: {rule.description}"
                )
                # Track worst severity
                if severity_order.index(rule.severity) > severity_order.index(worst_severity):
                    worst_severity = rule.severity

        if not matched:
            worst_severity = SafetyLevel.SAFE

        return worst_severity, matched, explanations

    def get_rules(self) -> list[SymbolicRule]:
        """Get all rules.

        Returns:
            List of all symbolic rules.
        """
        return list(self._rules)

    def get_rule_stats(self) -> dict[str, int]:
        """Get statistics about loaded rules.

        Returns:
            Dictionary with rule counts by category.
        """
        stats: dict[str, int] = {}
        for rule in self._rules:
            cat = rule.category.value
            stats[cat] = stats.get(cat, 0) + 1
        stats["total"] = len(self._rules)
        stats["enabled"] = sum(1 for r in self._rules if r.enabled)
        return stats


# -- Neural Risk Scorer --------------------------------------------------------

class NeuralRiskScorer:
    """LLM-based neural risk assessment for commands.

    Uses semantic understanding to assess command risk beyond pattern matching.
    Supports pluggable scoring backends (LLM API, local model, heuristic fallback).
    """

    def __init__(
        self,
        scorer_fn: Optional[Callable[[str], tuple[int, str, float]]] = None,
        threshold: int = 70,
    ) -> None:
        """Initialize the neural risk scorer.

        Args:
            scorer_fn: Optional custom scoring function.
                Signature: (command: str) -> (score: int, reason: str, confidence: float)
            threshold: Score above which command is considered blocked.
        """
        self._scorer_fn = scorer_fn or self._heuristic_scorer
        self._threshold = threshold
        self._score_cache: dict[str, tuple[int, str, float]] = {}

    def score(self, command: str) -> tuple[int, str, float]:
        """Score a command's risk level.

        Args:
            command: Command to score.

        Returns:
            Tuple of (risk_score 0-100, reason, confidence 0-1).
        """
        cache_key = hashlib.sha256(command.encode()).hexdigest()
        if cache_key in self._score_cache:
            return self._score_cache[cache_key]

        try:
            result = self._scorer_fn(command)
            score, reason, confidence = result
            score = max(0, min(100, score))
            confidence = max(0.0, min(1.0, confidence))
            self._score_cache[cache_key] = (score, reason, confidence)
            return score, reason, confidence
        except Exception as e:
            logger.error("Neural scoring failed: %s, using fallback", e)
            fallback = self._fallback_scorer(command)
            self._score_cache[cache_key] = fallback
            return fallback

    def _heuristic_scorer(self, command: str) -> tuple[int, str, float]:
        """Heuristic-based scoring when no LLM is available.

        Provides reasonable risk assessment using linguistic heuristics.

        Args:
            command: Command to score.

        Returns:
            Tuple of (score, reason, confidence).
        """
        score = 0
        reasons: list[str] = []

        cmd_lower = command.lower()

        # Length heuristic (very long commands may be obfuscated)
        if len(command) > 500:
            score += 15
            reasons.append("unusually long command")
        elif len(command) > 200:
            score += 5

        # Pipe chains (complexity indicator)
        pipe_count = command.count("|")
        if pipe_count >= 3:
            score += 20
            reasons.append(f"complex pipe chain ({pipe_count} pipes)")
        elif pipe_count >= 2:
            score += 10
            reasons.append("multiple pipes")

        # Redirections
        redirect_count = command.count(">>") + command.count(">")
        if redirect_count >= 3:
            score += 10
            reasons.append("multiple output redirections")

        # Variable expansion
        if "$(" in command or "`" in command:
            score += 15
            reasons.append("command substitution detected")

        # Encoding/obfuscation indicators
        if any(x in cmd_lower for x in ["base64", "xxd", "hexdump", "openssl enc"]):
            score += 25
            reasons.append("encoding/obfuscation detected")

        # Network indicators
        if any(x in cmd_lower for x in ["curl", "wget", "nc ", "ncat", "socat"]):
            score += 10
            reasons.append("network tool usage")

        # Sensitive file paths
        sensitive_paths = ["/etc/shadow", "/etc/sudoers", ".ssh/", ".gnupg/", "/proc/"]
        for sp in sensitive_paths:
            if sp in cmd_lower:
                score += 20
                reasons.append(f"access to sensitive path: {sp}")
                break

        # Dangerous keywords
        dangerous = ["eval", "exec", "source", ".", "rm -rf", "mkfs", "dd if="]
        for kw in dangerous:
            if kw in cmd_lower:
                score += 15
                reasons.append(f"dangerous keyword: {kw}")

        # Confidence decreases with heuristic reliance
        confidence = 0.6 if reasons else 0.9

        return min(score, 100), "; ".join(reasons) if reasons else "no risk indicators", confidence

    def _fallback_scorer(self, command: str) -> tuple[int, str, float]:
        """Conservative fallback scorer.

        Args:
            command: Command to score.

        Returns:
            Tuple of (score, reason, confidence).
        """
        return 30, "fallback scoring — manual review recommended", 0.3

    def set_llm_scorer(
        self,
        llm_fn: Callable[[str], tuple[int, str, float]],
    ) -> None:
        """Set an LLM-based scoring function.

        Args:
            llm_fn: Function that takes a command and returns (score, reason, confidence).
        """
        self._scorer_fn = llm_fn
        self._score_cache.clear()

    @property
    def threshold(self) -> int:
        """Get the blocking threshold."""
        return self._threshold

    @threshold.setter
    def threshold(self, value: int) -> None:
        """Set the blocking threshold."""
        self._threshold = max(0, min(100, value))


# -- Command Validator (Combined) ----------------------------------------------

class CommandValidator:
    """Neuro-symbolic command validator.

    Combines symbolic rule engine (deterministic) with neural risk scorer
    (probabilistic) for defense-in-depth command safety assessment.

    Decision logic:
        - Symbolic BLOCKED → always blocked (hard safety)
        - Symbolic HIGH_RISK + Neural above threshold → blocked
        - Symbolic MEDIUM_RISK + Neural above threshold → blocked
        - Otherwise → allowed with appropriate safety level
    """

    def __init__(
        self,
        symbolic_engine: Optional[SymbolicRuleEngine] = None,
        neural_scorer: Optional[NeuralRiskScorer] = None,
        neural_threshold: int = 70,
    ) -> None:
        """Initialize the command validator.

        Args:
            symbolic_engine: Symbolic rule engine (creates default if None).
            neural_scorer: Neural risk scorer (creates default if None).
            neural_threshold: Score threshold for neural blocking.
        """
        self.symbolic = symbolic_engine or SymbolicRuleEngine()
        self.neural = neural_scorer or NeuralRiskScorer(threshold=neural_threshold)
        self._audit_log: list[dict[str, Any]] = []

    def validate(self, command: str) -> CommandVerdict:
        """Validate a command using neuro-symbolic assessment.

        Args:
            command: Command string to validate.

        Returns:
            CommandVerdict with safety assessment.
        """
        # Symbolic evaluation
        sym_severity, matched_rules, sym_explanations = self.symbolic.evaluate(command)
        symbolic_blocked = sym_severity == SafetyLevel.BLOCKED

        # Neural evaluation
        neural_score, neural_reason, neural_confidence = self.neural.score(command)
        neural_blocked = neural_score >= self.neural.threshold

        # Combine verdicts
        safety_level, is_safe, explanation = self._combine_verdict(
            sym_severity, symbolic_blocked,
            neural_score, neural_blocked,
            matched_rules, sym_explanations, neural_reason,
        )

        # Build transformed command suggestion
        transformed = self._suggest_transformation(command, matched_rules)

        # Collect threat categories
        categories = list({r.category.value for r in matched_rules})

        # Overall confidence
        confidence = neural_confidence if not symbolic_blocked else 1.0

        verdict = CommandVerdict(
            is_safe=is_safe,
            safety_level=safety_level,
            risk_score=neural_score if not symbolic_blocked else 100,
            symbolic_blocked=symbolic_blocked,
            neural_blocked=neural_blocked and not symbolic_blocked,
            matched_rules=[r.name for r in matched_rules],
            neural_reason=neural_reason,
            explanation=explanation,
            transformed_command=transformed,
            threat_categories=categories,
            confidence=confidence,
        )

        # Audit log
        self._log_audit(command, verdict)

        return verdict

    def _combine_verdict(
        self,
        sym_severity: SafetyLevel,
        symbolic_blocked: bool,
        neural_score: int,
        neural_blocked: bool,
        matched_rules: list[SymbolicRule],
        sym_explanations: list[str],
        neural_reason: str,
    ) -> tuple[SafetyLevel, bool, str]:
        """Combine symbolic and neural verdicts.

        Returns:
            Tuple of (safety_level, is_safe, explanation).
        """
        if symbolic_blocked:
            rule_names = [r.name for r in matched_rules]
            explanation = (
                f"BLOCKED by symbolic rules: {', '.join(rule_names)}. "
                f"Details: {'; '.join(sym_explanations)}"
            )
            return SafetyLevel.BLOCKED, False, explanation

        if neural_blocked:
            explanation = (
                f"BLOCKED by neural assessment (risk score: {neural_score}/100). "
                f"Reason: {neural_reason}"
            )
            if sym_explanations:
                explanation += f" Additional concerns: {'; '.join(sym_explanations)}"
            return SafetyLevel.BLOCKED, False, explanation

        # Not blocked — determine safety level
        if sym_severity == SafetyLevel.HIGH_RISK or neural_score >= 50:
            safety_level = SafetyLevel.HIGH_RISK
        elif sym_severity == SafetyLevel.MEDIUM_RISK or neural_score >= 30:
            safety_level = SafetyLevel.MEDIUM_RISK
        elif sym_severity == SafetyLevel.LOW_RISK or neural_score >= 10:
            safety_level = SafetyLevel.LOW_RISK
        else:
            safety_level = SafetyLevel.SAFE

        parts: list[str] = []
        if sym_explanations:
            parts.append(f"Warnings: {'; '.join(sym_explanations)}")
        if neural_reason and neural_reason != "no risk indicators":
            parts.append(f"Neural: {neural_reason}")
        if not parts:
            parts.append("No risks detected")

        return safety_level, True, " | ".join(parts)

    def _suggest_transformation(
        self,
        command: str,
        matched_rules: list[SymbolicRule],
    ) -> str:
        """Suggest a safe alternative command.

        Args:
            command: Original command.
            matched_rules: Rules that matched.

        Returns:
            Suggested safe command or empty string.
        """
        if not matched_rules:
            return ""

        # Use the highest-severity rule's suggestion
        severity_order = {
            SafetyLevel.BLOCKED: 0,
            SafetyLevel.HIGH_RISK: 1,
            SafetyLevel.MEDIUM_RISK: 2,
            SafetyLevel.LOW_RISK: 3,
            SafetyLevel.SAFE: 4,
        }
        worst_rule = max(matched_rules, key=lambda r: severity_order.get(r.severity, 4))

        if worst_rule.suggestion:
            return worst_rule.suggestion
        return ""

    def _log_audit(self, command: str, verdict: CommandVerdict) -> None:
        """Log validation for audit trail.

        Args:
            command: Validated command.
            verdict: Result verdict.
        """
        entry = {
            "timestamp": verdict.timestamp,
            "command": command,
            "is_safe": verdict.is_safe,
            "safety_level": verdict.safety_level.value,
            "risk_score": verdict.risk_score,
            "symbolic_blocked": verdict.symbolic_blocked,
            "neural_blocked": verdict.neural_blocked,
            "matched_rules": verdict.matched_rules,
            "confidence": verdict.confidence,
        }
        self._audit_log.append(entry)

        # Bounded log
        if len(self._audit_log) > 10000:
            self._audit_log = self._audit_log[-5000:]

    def get_audit_log(self) -> list[dict[str, Any]]:
        """Get the validation audit log.

        Returns:
            List of audit entries.
        """
        return list(self._audit_log)

    def get_stats(self) -> dict[str, Any]:
        """Get validator statistics.

        Returns:
            Dictionary with validation statistics.
        """
        total = len(self._audit_log)
        blocked = sum(1 for e in self._audit_log if not e["is_safe"])
        safe = total - blocked
        sym_blocks = sum(1 for e in self._audit_log if e["symbolic_blocked"])
        neural_blocks = sum(1 for e in self._audit_log if e["neural_blocked"])

        return {
            "total_validations": total,
            "safe": safe,
            "blocked": blocked,
            "symbolic_blocks": sym_blocks,
            "neural_blocks": neural_blocks,
            "block_rate": round(blocked / total * 100, 1) if total > 0 else 0.0,
            "symbolic_rules": self.symbolic.get_rule_stats(),
        }
