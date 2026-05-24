"""
Router for Autonomous Security Harness.
Determines the next step after the recon node.
"""


def route_after_recon(state: dict) -> str:
    """
    Determine the next step after the recon node based on the state.

    Args:
        state: The current workflow state

    Returns:
        The name of the next node to execute.
    """
    # We'll look at the recon findings to decide whether to do web scan, network scan, or both.
    # For simplicity, we'll do both if we have any targets, but we can make it more sophisticated.

    # In a real implementation, you might check:
    # - If web ports (80, 443, 8080, etc.) are open, then do web scan.
    # - If other ports are open, then do network scan.
    # - If no open ports, then maybe skip scanning and go to compliance or report.

    # We'll also check the state for any open ports found by recon (if the recon node stored them in state['findings'])
    # But note: the recon node we wrote above stores open ports in state['findings'] as type 'open_port'.
    open_port_findings = [f for f in state.get('findings', []) if f.get('type') == 'open_port']

    # If we have any open ports, we can decide to do both web and network scan?
    # Or we can split: if port 80, 443, 8080, etc. are open -> web scan; else -> network scan.
    # For simplicity, we'll do both if there are any open ports.
    if open_port_findings:
        # We have open ports, so we can do both web and network scan.
        # But the LangGraph conditional edge only allows one next node.
        # We can change the workflow to have a parallel split, but for simplicity, we'll choose one.
        # Let's say we do web scan first, then network scan, or vice versa.
        # We'll choose to do web scan if we find common web ports, otherwise network scan.

        web_ports = {'80', '443', '8080', '8443', '8000', '8888'}
        has_web_port = False
        for finding in open_port_findings:
            ports = finding.get('ports', [])
            for port in ports:
                if str(port) in web_ports:
                    has_web_port = True
                    break
            if has_web_port:
                break

        if has_web_port:
            return "web_scan"
        else:
            return "network_scan"
    else:
        # No open ports found, so we skip scanning and go directly to compliance check.
        # But note: we might still want to run compliance check on the targets (e.g., for configuration).
        # We'll go to compliance.
        return "compliance"
