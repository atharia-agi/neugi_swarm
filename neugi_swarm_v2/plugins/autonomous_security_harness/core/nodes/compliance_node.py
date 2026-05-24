"""
Compliance Node for Autonomous Security Harness.
Checks findings against compliance frameworks (e.g., NIST, ISO 27001).
"""

from __future__ import annotations

from typing import Any


async def compliance_node(state: dict[str, Any], tool_executor: Any, knowledge_searcher: Any, scope_validator: Any, auth_gate: Any, audit_logger: Any) -> dict[str, Any]:
    """
    Execute compliance checking phase.

    Args:
        state: The current workflow state
        tool_executor: ToolExecutor instance
        knowledge_searcher: KnowledgeSearcher instance
        scope_validator: ScopeValidator instance
        auth_gate: AuthGate instance (can be None)
        audit_logger: ImmutableAuditLogger instance

    Returns:
        Updated state
    """
    # Log the start of compliance node
    if audit_logger:
        audit_logger.log({
            'task_id': state['task_id'],
            'action': 'compliance_start',
            'findings_count': len(state.get('findings', []))
        })

    # We'll check each finding against relevant knowledge base articles
    # For simplicity, we'll just tag findings with applicable compliance frameworks
    # based on keywords in the finding or the tool used.

    compliance_tags = set()
    findings = state.get('findings', [])

    for finding in findings:
        # Simple mapping: if the finding is about a certain type of vulnerability,
        # we can map it to compliance frameworks.
        # In reality, this would be a more complex lookup in a knowledge base.
        description = finding.get('description', '').lower()

        # Map to compliance frameworks
        # This is a placeholder; in reality, you would have a comprehensive mapping.
        if 'sql' in description or 'injection' in description:
            compliance_tags.add('PCI-DSS')
            compliance_tags.add('NIST 800-53')
            compliance_tags.add('ISO 27001 A.14.2.5')
        if 'xss' in description or 'cross-site' in description:
            compliance_tags.add('OWASP ASVS')
            compliance_tags.add('NIST 800-53')
        if 'config' in description or 'misconfiguration' in description:
            compliance_tags.add('CIS Benchmarks')
            compliance_tags.add('ISO 27001 A.12.1.2')
        if 'auth' in description or 'authentication' in description:
            compliance_tags.add('NIST 800-63')
            compliance_tags.add('ISO 27001 A.9.2.1')
        if 'crypto' in description or 'encryption' in description:
            compliance_tags.add('NIST 800-57')
            compliance_tags.add('ISO 27001 A.10.1.1')
        if 'patch' in description or 'update' in description or 'vulnerability' in description:
            compliance_tags.add('CIS Benchmarks')
            compliance_tags.add('ISO 27001 A.12.6.1')

        # Also check the tool
        tool_name = finding.get('tool', '')
        if tool_name == 'nmap':
            compliance_tags.add('NIST 800-115')  # Technical Guide to Information Security Testing
        if tool_name == 'nuclei':
            compliance_tags.add('OWASP Testing Guide')
        if tool_name == 'nikto':
            compliance_tags.add('OWASP Testing Guide')
        if tool_name == 'sqlmap':
            compliance_tags.add('OWASP Testing Guide')

    # Update state with compliance tags
    state['compliance_tags'] = list(compliance_tags)

    # Also, we could optionally run a tool like `oscp` or use the knowledge base
    # to get more detailed compliance information, but for now, we'll just tag.

    # Log the end of compliance node
    if audit_logger:
        audit_logger.log({
            'task_id': state['task_id'],
            'action': 'compliance_complete',
            'compliance_tags': list(compliance_tags)
        })

    return state
