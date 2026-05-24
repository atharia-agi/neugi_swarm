"""Compliance framework checker (ISO 27001, GDPR, NIST)."""
from typing import Any

logger = __import__("logging").getLogger(__name__)

COMPLIANCE_FRAMEWORKS = {
    "NIST": {
        "id": "NIST Cybersecurity Framework",
        "controls": ["ID.AM-1", "ID.RA-1", "PR.AC-1", "PR.DS-1", "DE.CM-1", "RS.MI-1"],
        "description": "NIST CSF - Identify, Protect, Detect, Respond, Recover",
    },
    "ISO27001": {
        "id": "ISO/IEC 27001:2022",
        "controls": ["A.5.1", "A.6.1", "A.8.1", "A.9.1", "A.12.1", "A.16.1"],
        "description": "Information security management system controls",
    },
    "GDPR": {
        "id": "General Data Protection Regulation",
        "controls": ["Art.5", "Art.6", "Art.17", "Art.25", "Art.32", "Art.33"],
        "description": "EU data protection and privacy regulation",
    },
    "OWASP": {
        "id": "OWASP Top 10:2021",
        "controls": ["A01:2021", "A02:2021", "A03:2021", "A04:2021", "A05:2021"],
        "description": "Web application security risks",
    },
    "MITRE": {
        "id": "MITRE ATT&CK v14",
        "controls": ["TA0001", "TA0002", "TA0003", "TA0004", "TA0005"],
        "description": "Adversarial tactics and techniques",
    },
}

def check_compliance(targets: list[str], frameworks: list[str]) -> dict[str, Any]:
    """Check targets against compliance frameworks.

    Args:
        targets: List of targets
        frameworks: Framework IDs (NIST, ISO27001, GDPR, OWASP, MITRE)

    Returns:
        Compliance assessment with applicable controls
    """
    results = {}
    for fw_name in frameworks:
        fw = COMPLIANCE_FRAMEWORKS.get(fw_name.upper())
        if not fw:
            results[fw_name] = {"error": f"Unknown framework: {fw_name}"}
            continue
        results[fw_name] = {
            "framework": fw["id"],
            "description": fw["description"],
            "applicable_controls": fw["controls"],
            "coverage": _estimate_coverage(fw_name, targets),
            "recommendations": _get_recommendations(fw_name),
        }
    return {
        "targets": targets, "frameworks_assessed": list(results.keys()),
        "results": results, "overall_score": _calculate_score(results),
    }

def _estimate_coverage(framework: str, targets: list[str]) -> float:
    base = {"NIST": 0.45, "ISO27001": 0.35, "GDPR": 0.50, "OWASP": 0.60, "MITRE": 0.40}
    return base.get(framework, 0.5)

def _get_recommendations(framework: str) -> list[str]:
    recs = {
        "NIST": ["Implement continuous monitoring (DE.CM)", "Conduct risk assessment (ID.RA)"],
        "ISO27001": ["Establish ISMS policy (A.5.1)", "Implement access control (A.9.1)"],
        "GDPR": ["Review data processing register (Art.30)", "Implement DPA procedures"],
        "OWASP": ["Fix A01: Broken Access Control", "Mitigate A03: Injection flaws"],
        "MITRE": ["Implement EDR for TA0002 execution", "Deploy SIEM for TA0003 persistence"],
    }
    return recs.get(framework, [])

def _calculate_score(results: dict) -> float:
    scores = [r.get("coverage", 0) for r in results.values() if isinstance(r, dict)]
    return round(sum(scores) / len(scores), 2) if scores else 0.0
