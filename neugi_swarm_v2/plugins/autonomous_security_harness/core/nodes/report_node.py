"""
Report Node for Autonomous Security Harness.
Generates a final report from the state.
"""
from __future__ import annotations

import time
from typing import Any


async def report_node(state: dict[str, Any], tool_executor: Any, knowledge_searcher: Any, scope_validator: Any, auth_gate: Any, audit_logger: Any) -> dict[str, Any]:
    """
    Execute reporting phase.

    Args:
        state: The current workflow state
        tool_executor: ToolExecutor instance
        knowledge_searcher: KnowledgeSearcher instance
        scope_validator: ScopeValidator instance
        auth_gate: AuthGate instance (can be None)
        audit_logger: ImmutableAuditLogger instance

    Returns:
        Updated state (with a final_report field)
    """
    # Log the start of report node
    if audit_logger:
        audit_logger.log({
            'task_id': state['task_id'],
            'action': 'report_start',
            'findings_count': len(state.get('findings', []))
        })

    # Generate a report based on the state
    # We'll create a simple dictionary report, but in reality, this could be JSON, PDF, etc.
    report = {
        'task_id': state['task_id'],
        'user_id': state.get('user_id'),
        'timestamp': time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        'targets': state.get('targets', []),
        'scope': state.get('scope', {}),
        'findings': state.get('findings', []),
        'recon_findings': state.get('recon_findings', []),
        'web_findings': state.get('web_findings', []),
        'network_findings': state.get('network_findings', []),
        'compliance_tags': state.get('compliance_tags', []),
        'audit_trail': state.get('audit_trail', []),
        'error': state.get('error'),
        'summary': {
            'total_findings': len(state.get('findings', [])),
            'open_ports_total': sum(len(f.get('ports', [])) for f in state.get('findings', []) if f.get('type') == 'open_port'),
            'vulnerabilities_total': len([f for f in state.get('findings', []) if f.get('type') == 'vulnerability']),
            'compliance_frameworks': list(set(state.get('compliance_tags', [])))
        }
    }

    # Optionally, we could generate a more formatted report (e.g., markdown, HTML, PDF)
    # For now, we'll just store the report in the state.
    state['final_report'] = report

    # Log the end of report node
    if audit_logger:
        audit_logger.log({
            'task_id': state['task_id'],
            'action': 'report_complete',
            'report_size': len(str(report))
        })

    # Set next to END (the workflow will end after this node)
    state['next'] = 'END'

    return state
