"""
Shield Reasoning — Explainable Security
=======================================

Provides explainable security decisions, risk scoring, threat classification,
and security posture assessment for the NEUGI v2 agentic AI system.

Components:
    RiskScore: Numerical risk assessment with breakdown
    ThreatClassification: Categorization of security threats
    SecurityPosture: Overall security health assessment
    SecurityRecommendation: Actionable security improvements
    ShieldReasoner: Central reasoning engine

Usage:
    reasoner = ShieldReasoner()
    score = reasoner.assess_risk(command, context)
    posture = reasoner.assess_posture()
    recommendations = reasoner.get_recommendations(posture)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


# -- Enums ---------------------------------------------------------------------

class ThreatClassification(Enum):
    """Classification of security threats."""
    INJECTION = "injection"
    EXFILTRATION = "exfiltration"
    ESCALATION = "escalation"
    PERSISTENCE = "persistence"
    RECONNAISSANCE = "reconnaissance"
    RESOURCE_ABUSE = "resource_abuse"
    SUPPLY_CHAIN = "supply_chain"
    SOCIAL_ENGINEERING = "social_engineering"
    MISCONFIGURATION = "misconfiguration"
    NONE = "none"


class RiskLevel(Enum):
    """Risk level classification."""
    MINIMAL = "minimal"       # 0-15
    LOW = "low"               # 16-35
    MODERATE = "moderate"     # 36-55
    HIGH = "high"             # 56-75
    CRITICAL = "critical"     # 76-100


class PostureLevel(Enum):
    """Security posture level."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"


# -- Data Classes --------------------------------------------------------------

@dataclass
class RiskBreakdown:
    """Detailed breakdown of a risk score.

    Attributes:
        factor_name: Name of the risk factor.
        score: Contribution to overall score (0-100).
        weight: Importance weight (0.0-1.0).
        description: Explanation of the factor.
        evidence: Supporting evidence or indicators.
    """
    factor_name: str
    score: int
    weight: float
    description: str
    evidence: list[str] = field(default_factory=list)


@dataclass
class RiskScore:
    """Complete risk assessment result.

    Attributes:
        overall_score: Overall risk score (0-100).
        risk_level: Categorized risk level.
        breakdown: Detailed factor breakdown.
        threat_classifications: Detected threat types.
        confidence: Confidence in the assessment (0.0-1.0).
        explanation: Human-readable explanation.
        timestamp: When the assessment was made.
    """
    overall_score: int
    risk_level: RiskLevel
    breakdown: list[RiskBreakdown] = field(default_factory=list)
    threat_classifications: list[ThreatClassification] = field(default_factory=list)
    confidence: float = 1.0
    explanation: str = ""
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = time.time()

    @property
    def is_acceptable(self) -> bool:
        """Check if risk is within acceptable bounds."""
        return self.overall_score < 50

    @property
    def requires_review(self) -> bool:
        """Check if risk requires manual review."""
        return self.overall_score >= 35


@dataclass
class SecurityRecommendation:
    """Actionable security recommendation.

    Attributes:
        category: Recommendation category.
        priority: Priority level (1=highest).
        title: Short recommendation title.
        description: Detailed explanation.
        action: Specific action to take.
        impact: Expected security impact.
        effort: Implementation effort estimate.
    """
    category: str
    priority: int
    title: str
    description: str
    action: str
    impact: str
    effort: str = "medium"


@dataclass
class SecurityPosture:
    """Overall security posture assessment.

    Attributes:
        level: Overall posture level.
        score: Numerical posture score (0-100, higher = better).
        strengths: Security strengths identified.
        weaknesses: Security weaknesses identified.
        controls_active: Number of active security controls.
        controls_total: Total security controls evaluated.
        last_assessment: Timestamp of last assessment.
        trend: Posture trend (improving/stable/declining).
    """
    level: PostureLevel
    score: int
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    controls_active: int = 0
    controls_total: int = 0
    last_assessment: float = 0.0
    trend: str = "stable"

    def __post_init__(self) -> None:
        if not self.last_assessment:
            self.last_assessment = time.time()


@dataclass
class DecisionExplanation:
    """Explanation of a security decision.

    Attributes:
        decision: The decision made (allow/block/warn).
        reason: Primary reason for the decision.
        factors: Contributing factors.
        confidence: Confidence in the decision.
        alternatives: Alternative actions considered.
        precedent: Similar past decisions.
    """
    decision: str
    reason: str
    factors: list[str] = field(default_factory=list)
    confidence: float = 1.0
    alternatives: list[str] = field(default_factory=list)
    precedent: list[str] = field(default_factory=list)


# -- False Positive Tracker ----------------------------------------------------

class FalsePositiveTracker:
    """Tracks and learns from false positive detections.

    Helps reduce false positives over time by recording
    which rules/patterns triggered incorrectly.
    """

    def __init__(self) -> None:
        self._false_positives: list[dict[str, Any]] = []
        self._rule_fp_counts: dict[str, int] = {}
        self._total_decisions: int = 0
        self._total_false_positives: int = 0

    def record_false_positive(
        self,
        rule_name: str,
        input_text: str,
        expected_verdict: str,
        actual_verdict: str,
    ) -> None:
        """Record a false positive detection.

        Args:
            rule_name: Rule that triggered incorrectly.
            input_text: Input that was misclassified.
            expected_verdict: What the verdict should have been.
            actual_verdict: What the verdict actually was.
        """
        entry = {
            "timestamp": time.time(),
            "rule_name": rule_name,
            "input_hash": hash(input_text) & 0xFFFFFFFF,
            "expected": expected_verdict,
            "actual": actual_verdict,
        }
        self._false_positives.append(entry)
        self._rule_fp_counts[rule_name] = self._rule_fp_counts.get(rule_name, 0) + 1
        self._total_false_positives += 1

    def record_decision(self, was_false_positive: bool) -> None:
        """Record a security decision for statistics.

        Args:
            was_false_positive: Whether the decision was a false positive.
        """
        self._total_decisions += 1
        if was_false_positive:
            self._total_false_positives += 1

    def get_false_positive_rate(self) -> float:
        """Get the overall false positive rate.

        Returns:
            False positive rate (0.0-1.0).
        """
        if self._total_decisions == 0:
            return 0.0
        return self._total_false_positives / self._total_decisions

    def get_problematic_rules(self, threshold: int = 3) -> list[str]:
        """Get rules that have triggered too many false positives.

        Args:
            threshold: Minimum FP count to flag.

        Returns:
            List of rule names to review.
        """
        return [
            name for name, count in self._rule_fp_counts.items()
            if count >= threshold
        ]

    def get_stats(self) -> dict[str, Any]:
        """Get false positive statistics.

        Returns:
            Dictionary with FP statistics.
        """
        return {
            "total_decisions": self._total_decisions,
            "total_false_positives": self._total_false_positives,
            "false_positive_rate": round(self.get_false_positive_rate() * 100, 2),
            "problematic_rules": self.get_problematic_rules(),
            "rule_fp_counts": dict(self._rule_fp_counts),
        }


# -- Shield Reasoner -----------------------------------------------------------

class ShieldReasoner:
    """Central explainable security reasoning engine.

    Provides:
    - Risk scoring with detailed breakdown
    - Threat classification
    - Decision explanation
    - Security posture assessment
    - Recommendation generation
    - False positive tracking
    """

    def __init__(self) -> None:
        self._fp_tracker = FalsePositiveTracker()
        self._assessment_history: list[dict[str, Any]] = []
        self._decision_history: list[DecisionExplanation] = []

    # -- Risk Scoring --------------------------------------------------------

    def assess_risk(
        self,
        command: str = "",
        context: Optional[dict[str, Any]] = None,
        threat_indicators: Optional[list[dict[str, Any]]] = None,
    ) -> RiskScore:
        """Assess the risk level of a command or action.

        Args:
            command: Command or action being assessed.
            context: Additional context (user role, environment, etc.).
            threat_indicators: Pre-detected threat indicators.

        Returns:
            RiskScore with detailed breakdown.
        """
        context = context or {}
        threat_indicators = threat_indicators or []

        breakdown: list[RiskBreakdown] = []
        threat_classes: list[ThreatClassification] = []

        # Factor 1: Command complexity
        complexity_score, complexity_evidence = self._assess_complexity(command)
        breakdown.append(RiskBreakdown(
            factor_name="command_complexity",
            score=complexity_score,
            weight=0.15,
            description="Complexity of the command or action",
            evidence=complexity_evidence,
        ))

        # Factor 2: Destructive potential
        destructive_score, destructive_evidence = self._assess_destructive(command)
        breakdown.append(RiskBreakdown(
            factor_name="destructive_potential",
            score=destructive_score,
            weight=0.25,
            description="Potential for data loss or system damage",
            evidence=destructive_evidence,
        ))

        # Factor 3: Privilege requirements
        privilege_score, privilege_evidence = self._assess_privilege(command, context)
        breakdown.append(RiskBreakdown(
            factor_name="privilege_requirement",
            score=privilege_score,
            weight=0.20,
            description="Level of privilege escalation required",
            evidence=privilege_evidence,
        ))

        # Factor 4: Data sensitivity
        data_score, data_evidence = self._assess_data_sensitivity(command, context)
        breakdown.append(RiskBreakdown(
            factor_name="data_sensitivity",
            score=data_score,
            weight=0.20,
            description="Sensitivity of data being accessed or modified",
            evidence=data_evidence,
        ))

        # Factor 5: Network exposure
        network_score, network_evidence = self._assess_network_exposure(command)
        breakdown.append(RiskBreakdown(
            factor_name="network_exposure",
            score=network_score,
            weight=0.10,
            description="Network exposure and external communication",
            evidence=network_evidence,
        ))

        # Factor 6: Threat indicators
        threat_score, threat_evidence, detected_classes = self._assess_threat_indicators(
            threat_indicators
        )
        breakdown.append(RiskBreakdown(
            factor_name="threat_indicators",
            score=threat_score,
            weight=0.10,
            description="Pre-detected threat indicators",
            evidence=threat_evidence,
        ))
        threat_classes.extend(detected_classes)

        # Calculate weighted score
        overall_score = sum(
            b.score * b.weight for b in breakdown
        )
        overall_score = max(0, min(100, int(overall_score)))

        risk_level = self._score_to_level(overall_score)
        confidence = self._calculate_confidence(breakdown)

        explanation = self._build_risk_explanation(overall_score, risk_level, breakdown)

        score = RiskScore(
            overall_score=overall_score,
            risk_level=risk_level,
            breakdown=breakdown,
            threat_classifications=threat_classes,
            confidence=confidence,
            explanation=explanation,
        )

        self._log_assessment(score, command, context)
        return score

    def _assess_complexity(self, command: str) -> tuple[int, list[str]]:
        """Assess command complexity.

        Args:
            command: Command to assess.

        Returns:
            Tuple of (score, evidence).
        """
        score = 0
        evidence: list[str] = []

        if not command:
            return 0, ["No command provided"]

        # Pipe chains
        pipes = command.count("|")
        if pipes >= 3:
            score += 40
            evidence.append(f"Complex pipe chain: {pipes} pipes")
        elif pipes >= 2:
            score += 20
            evidence.append(f"Multiple pipes: {pipes}")

        # Redirects
        redirects = command.count(">>") + command.count(">")
        if redirects >= 3:
            score += 20
            evidence.append(f"Multiple redirects: {redirects}")

        # Subshells
        if "$(" in command or "`" in command:
            score += 15
            evidence.append("Command substitution detected")

        # Length
        if len(command) > 500:
            score += 15
            evidence.append("Unusually long command")

        return min(score, 100), evidence

    def _assess_destructive(self, command: str) -> tuple[int, list[str]]:
        """Assess destructive potential.

        Args:
            command: Command to assess.

        Returns:
            Tuple of (score, evidence).
        """
        score = 0
        evidence: list[str] = []

        cmd_lower = command.lower()

        destructive_patterns = [
            (r"\brm\s+(-rf|-fr)", 80, "Force recursive deletion"),
            (r"\bmkfs\b", 90, "Filesystem creation/formatting"),
            (r"\bdd\s+.*of=/dev/", 95, "Direct disk write"),
            (r"\bchmod\s+777\b", 60, "World-writable permissions"),
            (r">\s*/dev/sda", 95, "Device overwrite"),
            (r"\bshred\b", 70, "Secure file deletion"),
        ]

        import re
        for pattern, pts, desc in destructive_patterns:
            if re.search(pattern, cmd_lower):
                score = max(score, pts)
                evidence.append(desc)

        return min(score, 100), evidence

    def _assess_privilege(
        self,
        command: str,
        context: dict[str, Any],
    ) -> tuple[int, list[str]]:
        """Assess privilege escalation requirements.

        Args:
            command: Command to assess.
            context: Execution context.

        Returns:
            Tuple of (score, evidence).
        """
        score = 0
        evidence: list[str] = []

        cmd_lower = command.lower()

        if "sudo" in cmd_lower:
            score += 50
            evidence.append("Sudo usage detected")

        if "su " in cmd_lower:
            score += 40
            evidence.append("User switching detected")

        if any(x in cmd_lower for x in ["chmod", "chown", "chgrp"]):
            score += 30
            evidence.append("Permission/ownership change")

        if any(x in cmd_lower for x in ["/etc/shadow", "/etc/sudoers"]):
            score += 60
            evidence.append("System auth file access")

        # Context: user role
        user_role = context.get("user_role", "standard")
        if user_role == "admin":
            score = max(0, score - 20)
            evidence.append("Admin context reduces risk")
        elif user_role == "readonly":
            score += 30
            evidence.append("Read-only user attempting modification")

        return min(score, 100), evidence

    def _assess_data_sensitivity(
        self,
        command: str,
        context: dict[str, Any],
    ) -> tuple[int, list[str]]:
        """Assess data sensitivity.

        Args:
            command: Command to assess.
            context: Execution context.

        Returns:
            Tuple of (score, evidence).
        """
        score = 0
        evidence: list[str] = []

        sensitive_paths = [
            (r"/etc/(shadow|passwd|sudoers)", 70, "System auth files"),
            (r"\.ssh/", 60, "SSH configuration"),
            (r"\.gnupg/", 65, "GPG configuration"),
            (r"\.env\b", 50, "Environment file"),
            (r"(?:aws|gcp|azure).*credentials", 80, "Cloud credentials"),
            (r"(?:password|secret|token|key)\s*[=:]", 60, "Credential assignment"),
        ]

        import re
        for pattern, pts, desc in sensitive_paths:
            if re.search(pattern, command, re.IGNORECASE):
                score = max(score, pts)
                evidence.append(desc)

        # Context: data classification
        data_class = context.get("data_classification", "public")
        class_scores = {"public": 0, "internal": 20, "confidential": 50, "restricted": 80}
        class_score = class_scores.get(data_class, 0)
        if class_score > score:
            score = class_score
            evidence.append(f"Data classification: {data_class}")

        return min(score, 100), evidence

    def _assess_network_exposure(self, command: str) -> tuple[int, list[str]]:
        """Assess network exposure.

        Args:
            command: Command to assess.

        Returns:
            Tuple of (score, evidence).
        """
        score = 0
        evidence: list[str] = []

        network_tools = [
            ("curl", 20), ("wget", 20), ("nc ", 40), ("ncat", 40),
            ("socat", 35), ("ssh", 25), ("scp", 30), ("rsync", 15),
            ("nmap", 50), ("dig", 15), ("nslookup", 15),
        ]

        cmd_lower = command.lower()
        for tool, pts in network_tools:
            if tool in cmd_lower:
                score = max(score, pts)
                evidence.append(f"Network tool: {tool}")

        if "@" in command and any(x in cmd_lower for x in ["scp", "rsync", "ssh"]):
            score += 20
            evidence.append("Remote host targeted")

        return min(score, 100), evidence

    def _assess_threat_indicators(
        self,
        indicators: list[dict[str, Any]],
    ) -> tuple[int, list[str], list[ThreatClassification]]:
        """Assess pre-detected threat indicators.

        Args:
            indicators: List of threat indicator dicts.

        Returns:
            Tuple of (score, evidence, threat_classes).
        """
        if not indicators:
            return 0, ["No threat indicators"], []

        score = 0
        evidence: list[str] = []
        classes: list[ThreatClassification] = []

        for indicator in indicators:
            severity = indicator.get("severity", "low")
            severity_scores = {"info": 5, "low": 20, "medium": 40, "high": 60, "critical": 80}
            pts = severity_scores.get(severity, 10)
            score = max(score, pts)

            desc = indicator.get("description", "Unknown indicator")
            evidence.append(f"{severity.upper()}: {desc}")

            vector = indicator.get("vector", "")
            class_map = {
                "prompt_injection": ThreatClassification.INJECTION,
                "indirect_injection": ThreatClassification.INJECTION,
                "data_exfiltration": ThreatClassification.EXFILTRATION,
                "privilege_escalation": ThreatClassification.ESCALATION,
                "supply_chain": ThreatClassification.SUPPLY_CHAIN,
                "jailbreak": ThreatClassification.SOCIAL_ENGINEERING,
            }
            tc = class_map.get(vector)
            if tc:
                classes.append(tc)

        return min(score, 100), evidence, classes

    def _score_to_level(self, score: int) -> RiskLevel:
        """Convert numerical score to risk level.

        Args:
            score: Risk score (0-100).

        Returns:
            RiskLevel.
        """
        if score >= 76:
            return RiskLevel.CRITICAL
        if score >= 56:
            return RiskLevel.HIGH
        if score >= 36:
            return RiskLevel.MODERATE
        if score >= 16:
            return RiskLevel.LOW
        return RiskLevel.MINIMAL

    def _calculate_confidence(self, breakdown: list[RiskBreakdown]) -> float:
        """Calculate confidence in the risk assessment.

        Args:
            breakdown: Risk factor breakdown.

        Returns:
            Confidence score (0.0-1.0).
        """
        if not breakdown:
            return 0.5

        # Confidence increases with more evidence
        evidence_count = sum(len(b.evidence) for b in breakdown)
        if evidence_count >= 5:
            return 0.9
        if evidence_count >= 3:
            return 0.75
        if evidence_count >= 1:
            return 0.6
        return 0.4

    def _build_risk_explanation(
        self,
        score: int,
        level: RiskLevel,
        breakdown: list[RiskBreakdown],
    ) -> str:
        """Build human-readable risk explanation.

        Args:
            score: Overall risk score.
            level: Risk level.
            breakdown: Factor breakdown.

        Returns:
            Explanation string.
        """
        parts = [f"Risk Level: {level.value.upper()} (score: {score}/100)"]

        # Top contributing factors
        sorted_factors = sorted(breakdown, key=lambda b: b.score * b.weight, reverse=True)
        for factor in sorted_factors[:3]:
            if factor.score > 0:
                parts.append(
                    f"  - {factor.factor_name}: {factor.score}/100 "
                    f"(weight: {factor.weight:.0%}) — {factor.description}"
                )
                for ev in factor.evidence[:2]:
                    parts.append(f"      Evidence: {ev}")

        return "\n".join(parts)

    # -- Decision Explanation ------------------------------------------------

    def explain_decision(
        self,
        decision: str,
        reason: str,
        factors: Optional[list[str]] = None,
        alternatives: Optional[list[str]] = None,
    ) -> DecisionExplanation:
        """Create an explainable security decision.

        Args:
            decision: Decision made (allow/block/warn).
            reason: Primary reason.
            factors: Contributing factors.
            alternatives: Alternative actions considered.

        Returns:
            DecisionExplanation.
        """
        explanation = DecisionExplanation(
            decision=decision,
            reason=reason,
            factors=factors or [],
            confidence=0.8,
            alternatives=alternatives or [],
        )

        # Find similar past decisions
        for past in self._decision_history[-100:]:
            if past.decision == decision and past.reason == reason:
                explanation.precedent.append(
                    f"Similar decision made at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(past.timestamp))}"
                )
                if len(explanation.precedent) >= 3:
                    break

        self._decision_history.append(explanation)
        return explanation

    # -- Security Posture ----------------------------------------------------

    def assess_posture(
        self,
        controls: Optional[dict[str, bool]] = None,
        metrics: Optional[dict[str, Any]] = None,
    ) -> SecurityPosture:
        """Assess overall security posture.

        Args:
            controls: Dictionary of {control_name: is_active}.
            metrics: Security metrics dictionary.

        Returns:
            SecurityPosture assessment.
        """
        controls = controls or {}
        metrics = metrics or {}

        strengths: list[str] = []
        weaknesses: list[str] = []
        active_count = 0
        total_count = len(controls)

        # Evaluate controls
        control_weights = {
            "sandbox_enabled": 0.15,
            "command_validation": 0.15,
            "injection_detection": 0.15,
            "secret_encryption": 0.10,
            "access_logging": 0.10,
            "rate_limiting": 0.10,
            "supply_chain_detection": 0.10,
            "output_scanning": 0.08,
            "auto_rotation": 0.07,
        }

        weighted_score = 0.0
        total_weight = 0.0

        for control_name, is_active in controls.items():
            weight = control_weights.get(control_name, 0.05)
            total_weight += weight

            if is_active:
                active_count += 1
                weighted_score += weight
                strengths.append(f"Control active: {control_name}")
            else:
                weaknesses.append(f"Control inactive: {control_name}")

        # Normalize
        if total_weight > 0:
            normalized_score = int((weighted_score / total_weight) * 100)
        else:
            normalized_score = 50  # Unknown posture

        # Adjust based on metrics
        fp_rate = metrics.get("false_positive_rate", 0.0)
        if fp_rate > 0.3:
            normalized_score -= 10
            weaknesses.append(f"High false positive rate: {fp_rate:.0%}")
        elif fp_rate < 0.05:
            normalized_score += 5
            strengths.append("Low false positive rate")

        threat_rate = metrics.get("threat_detection_rate", 0.0)
        if threat_rate > 0.5:
            weaknesses.append(f"High threat detection rate: {threat_rate:.0%}")
        elif threat_rate < 0.01:
            strengths.append("Low threat incidence")

        normalized_score = max(0, min(100, normalized_score))

        # Determine level
        if normalized_score >= 90:
            level = PostureLevel.EXCELLENT
        elif normalized_score >= 70:
            level = PostureLevel.GOOD
        elif normalized_score >= 50:
            level = PostureLevel.FAIR
        elif normalized_score >= 30:
            level = PostureLevel.POOR
        else:
            level = PostureLevel.CRITICAL

        # Determine trend
        trend = self._calculate_trend()

        return SecurityPosture(
            level=level,
            score=normalized_score,
            strengths=strengths,
            weaknesses=weaknesses,
            controls_active=active_count,
            controls_total=total_count,
            trend=trend,
        )

    def _calculate_trend(self) -> str:
        """Calculate posture trend from assessment history.

        Returns:
            Trend string (improving/stable/declining).
        """
        if len(self._assessment_history) < 2:
            return "stable"

        recent = self._assessment_history[-5:]
        scores = [a.get("score", 50) for a in recent]

        if len(scores) < 2:
            return "stable"

        avg_first = sum(scores[:len(scores)//2]) / (len(scores)//2)
        avg_last = sum(scores[len(scores)//2:]) / (len(scores) - len(scores)//2)

        diff = avg_last - avg_first
        if diff > 5:
            return "improving"
        if diff < -5:
            return "declining"
        return "stable"

    # -- Recommendations -----------------------------------------------------

    def get_recommendations(
        self,
        posture: Optional[SecurityPosture] = None,
    ) -> list[SecurityRecommendation]:
        """Generate security recommendations.

        Args:
            posture: Current security posture (assesses if None).

        Returns:
            List of actionable recommendations.
        """
        if posture is None:
            posture = self.assess_posture()

        recommendations: list[SecurityRecommendation] = []

        # Based on weaknesses
        for weakness in posture.weaknesses:
            rec = self._recommendation_for_weakness(weakness)
            if rec:
                recommendations.append(rec)

        # Based on posture level
        if posture.level in (PostureLevel.POOR, PostureLevel.CRITICAL):
            recommendations.append(SecurityRecommendation(
                category="general",
                priority=1,
                title="Enable all security controls",
                description="Critical security controls are not active",
                action="Review and enable all security subsystems",
                impact="Significant improvement in security posture",
                effort="high",
            ))

        if posture.level == PostureLevel.CRITICAL:
            recommendations.append(SecurityRecommendation(
                category="general",
                priority=1,
                title="Immediate security review required",
                description="Security posture is critically weak",
                action="Conduct full security audit and remediation",
                impact="Prevent potential security incidents",
                effort="high",
            ))

        # Based on false positive rate
        fp_rate = self._fp_tracker.get_false_positive_rate()
        if fp_rate > 0.2:
            recommendations.append(SecurityRecommendation(
                category="tuning",
                priority=2,
                title="Reduce false positive rate",
                description=f"Current FP rate is {fp_rate:.0%}, target < 5%",
                action="Review and tune detection rules flagged by FP tracker",
                impact="Improved detection accuracy and reduced alert fatigue",
                effort="medium",
            ))

        # Sort by priority
        recommendations.sort(key=lambda r: r.priority)

        return recommendations

    def _recommendation_for_weakness(
        self,
        weakness: str,
    ) -> Optional[SecurityRecommendation]:
        """Generate a recommendation for a specific weakness.

        Args:
            weakness: Weakness description.

        Returns:
            SecurityRecommendation or None.
        """
        rec_map = {
            "Control inactive: sandbox_enabled": SecurityRecommendation(
                category="controls", priority=1,
                title="Enable execution sandbox",
                description="Command execution is not sandboxed",
                action="Initialize ExecutionSandbox with appropriate config",
                impact="Prevents destructive command execution",
                effort="low",
            ),
            "Control inactive: command_validation": SecurityRecommendation(
                category="controls", priority=1,
                title="Enable command validation",
                description="Commands are not validated before execution",
                action="Initialize CommandValidator with symbolic and neural engines",
                impact="Blocks dangerous commands before execution",
                effort="low",
            ),
            "Control inactive: injection_detection": SecurityRecommendation(
                category="controls", priority=1,
                title="Enable injection detection",
                description="Prompt injection attacks are not detected",
                action="Initialize ExploitPreventionEngine with injection detection",
                impact="Prevents prompt injection attacks",
                effort="low",
            ),
            "Control inactive: secret_encryption": SecurityRecommendation(
                category="controls", priority=2,
                title="Enable secret encryption",
                description="Secrets are stored without encryption",
                action="Configure SecretManager with a strong master key",
                impact="Protects secrets at rest",
                effort="low",
            ),
            "Control inactive: access_logging": SecurityRecommendation(
                category="controls", priority=2,
                title="Enable access logging",
                description="Secret access is not being logged",
                action="Verify SecretManager access logging is active",
                impact="Provides audit trail for compliance",
                effort="low",
            ),
            "Control inactive: rate_limiting": SecurityRecommendation(
                category="controls", priority=2,
                title="Enable rate limiting",
                description="API rate limiting is not configured",
                action="Configure APIAbuseDetector with appropriate limits",
                impact="Prevents API abuse and resource exhaustion",
                effort="low",
            ),
            "Control inactive: supply_chain_detection": SecurityRecommendation(
                category="controls", priority=2,
                title="Enable supply chain detection",
                description="Malicious package detection is not active",
                action="Initialize SupplyChainDetector in ExploitPreventionEngine",
                impact="Prevents supply chain attacks",
                effort="low",
            ),
            "Control inactive: output_scanning": SecurityRecommendation(
                category="controls", priority=3,
                title="Enable output scanning",
                description="Agent output is not scanned for leaks",
                action="Use SecretManager.scan_for_leaks() on agent output",
                impact="Prevents accidental secret exposure",
                effort="low",
            ),
            "Control inactive: auto_rotation": SecurityRecommendation(
                category="controls", priority=3,
                title="Enable secret auto-rotation",
                description="Secrets are not automatically rotated",
                action="Configure auto_rotate_days in SecretManager",
                impact="Reduces risk of long-lived credential exposure",
                effort="medium",
            ),
        }

        return rec_map.get(weakness)

    # -- False Positive Management -------------------------------------------

    def record_false_positive(
        self,
        rule_name: str,
        input_text: str,
        expected: str,
        actual: str,
    ) -> None:
        """Record a false positive for learning.

        Args:
            rule_name: Rule that triggered incorrectly.
            input_text: Input text.
            expected: Expected verdict.
            actual: Actual verdict.
        """
        self._fp_tracker.record_false_positive(
            rule_name, input_text, expected, actual
        )

    def get_fp_stats(self) -> dict[str, Any]:
        """Get false positive statistics.

        Returns:
            Dictionary with FP statistics.
        """
        return self._fp_tracker.get_stats()

    # -- Logging -------------------------------------------------------------

    def _log_assessment(
        self,
        score: RiskScore,
        command: str,
        context: dict[str, Any],
    ) -> None:
        """Log a risk assessment.

        Args:
            score: Risk assessment result.
            command: Assessed command.
            context: Assessment context.
        """
        entry = {
            "timestamp": score.timestamp,
            "score": score.overall_score,
            "level": score.risk_level.value,
            "confidence": score.confidence,
            "command_hash": hash(command) & 0xFFFFFFFF,
            "context_keys": list(context.keys()),
        }
        self._assessment_history.append(entry)

        # Bounded history
        if len(self._assessment_history) > 10000:
            self._assessment_history = self._assessment_history[-5000:]

    def get_assessment_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent assessment history.

        Args:
            limit: Maximum entries to return.

        Returns:
            List of assessment entries.
        """
        return self._assessment_history[-limit:]
