"""Execute security tools via NEUGI's existing ToolExecutor."""
import logging
from typing import Any, Dict, List, Optional
logger = logging.getLogger(__name__)

def run_security_tools(targets: List[str], tools: List[str], depth: str = "standard") -> Dict[str, Any]:
    """Run security tools via ToolExecutor and return structured results.

    Args:
        targets: List of target domains/IPs
        tools: List of tools (nmap, nuclei, sqlmap, etc.)
        depth: scan depth: basic, standard, deep

    Returns:
        Dict with tool results and vulnerability summary
    """
    from neugi_swarm_v2.tools.tool_executor import ToolExecutor
    from neugi_swarm_v2.tools.tool_registry import ToolRegistry

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    results = []
    all_vulns = []

    for tool in tools:
        for target in targets:
            params = {"targets": [target]}
            if tool == "nmap":
                ports = {"basic": "80,443,22", "standard": "1-5000", "deep": "1-65535"}.get(depth, "1-5000")
                params["ports"] = ports
            elif tool == "sqlmap":
                params["risk"] = 2 if depth == "deep" else 1
                params["level"] = 3 if depth == "deep" else 1
            elif tool == "nuclei":
                params["severity"] = "critical,high,medium" if depth != "basic" else "critical"
            try:
                result = executor.execute(tool, **params)
                vulns = getattr(result, "vulnerabilities_found", []) or result.get("parsed", {}).get("vulnerabilities", [])
                all_vulns.extend(vulns)
                results.append({
                    "tool": tool, "target": target, "status": "completed",
                    "vulnerabilities": len(vulns), "duration": getattr(result, "duration_ms", 0),
                })
            except Exception as e:
                results.append({"tool": tool, "target": target, "status": "error", "error": str(e)})
                logger.warning("Tool %s failed on %s: %s", tool, target, e)

    severity_map = {"critical": [], "high": [], "medium": [], "low": []}
    for v in all_vulns:
        sev = (v.get("severity", v.get("risk", "medium")) or "medium").lower()
        severity_map.get(sev, []).append(v)

    return {
        "targets": targets, "tools_executed": len(results), "total_vulnerabilities": len(all_vulns),
        "severity_breakdown": {k: len(v) for k, v in severity_map.items()},
        "vulnerabilities": all_vulns[:100],
        "results": results,
        "risk_score": len(all_vulns) * 1.5 + severity_map.get("critical", []) * 5,
        "summary": f"Scanned {len(targets)} target(s) with {len(tools)} tool(s). Found {len(all_vulns)} findings.",
    }