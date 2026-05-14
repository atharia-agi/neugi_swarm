"""Validate targets against authorized scope before scanning."""
import ipaddress, re
from typing import Any, Dict, List, Optional
logger = __import__("logging").getLogger(__name__)

ALLOWED_SCOPES = [
    {"type": "domain", "pattern": r"^localhost$", "label": "localhost"},
    {"type": "ip", "address": "127.0.0.1", "label": "localhost"},
    {"type": "cidr", "network": "10.0.0.0/8", "label": "internal network"},
    {"type": "cidr", "network": "172.16.0.0/12", "label": "internal network"},
    {"type": "cidr", "network": "192.168.0.0/16", "label": "internal network"},
]

BLOCKED_DOMAINS = [r"\.gov$", r"\.mil$", r"\.int$", r"\.local$"]
BLOCKED_IPS = []

def validate_targets(targets: List[str],
                     allowed_scopes: Optional[List[Dict]] = None) -> Dict[str, Any]:
    """Validate that targets are within authorized scope.

    Args:
        targets: List of target domains/IPs
        allowed_scopes: Override default allowed scopes

    Returns:
        Validation result with valid flag and warnings
    """
    scopes = allowed_scopes or ALLOWED_SCOPES
    warnings = []
    errors = []
    valid = []

    for target in targets:
        target = target.strip()
        if _is_blocked(target):
            errors.append(f"Target blocked: {target} (restricted domain/IP range)")
            continue
        if _in_scope(target, scopes):
            valid.append(target)
        else:
            warnings.append(f"Target not in authorized scope: {target}")

    return {
        "valid": len(errors) == 0,
        "warnings": warnings,
        "errors": errors,
        "valid_targets": valid,
        "blocked_targets": [t for t in targets if _is_blocked(t.strip())],
        "reason": "; ".join(errors + warnings) if errors or warnings else "All targets in scope",
    }

def _is_blocked(target: str) -> bool:
    for pat in BLOCKED_DOMAINS:
        if re.search(pat, target, re.IGNORECASE):
            return True
    try:
        ip = ipaddress.ip_address(target)
        for block in BLOCKED_IPS:
            if ip in ipaddress.ip_network(block, strict=False):
                return True
    except ValueError:
        pass
    return False

def _in_scope(target: str, scopes: List[Dict]) -> bool:
    for scope in scopes:
        if scope["type"] == "domain" and re.match(scope["pattern"], target, re.IGNORECASE):
            return True
        if scope["type"] == "ip":
            try:
                if ipaddress.ip_address(target) == ipaddress.ip_address(scope["address"]):
                    return True
            except ValueError:
                pass
        if scope["type"] == "cidr":
            try:
                if ipaddress.ip_address(target) in ipaddress.ip_network(scope["network"], strict=False):
                    return True
            except (ValueError, TypeError):
                pass
    return False