"""
Recon Node for Autonomous Security Harness.
Performs initial reconnaissance (e.g., nmap scan) on targets.
"""
from typing import Any, Dict, List
import time

async def recon_node(state: dict, tool_executor, knowledge_searcher, scope_validator, auth_gate, audit_logger) -> dict:
    """
    Execute reconnaissance phase.
    
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
    # Log the start of recon node
    if audit_logger:
        audit_logger.log({
            'task_id': state['task_id'],
            'action': 'recon_start',
            'targets': state['targets']
        })
    
    # For each target, run nmap scan (or other recon tools)
    # We'll start with a simple nmap scan for common ports
    recon_findings = []
    
    for target in state['targets']:
        # Scope validation
        if not scope_validator.validate_target(target, 'nmap'):
            if audit_logger:
                audit_logger.log({
                    'task_id': state['task_id'],
                    'action': 'scope_violation',
                    'target': target,
                    'tool': 'nmap'
                })
            continue
        
        # Auth gate check for nmap (if required)
        if auth_gate:
            try:
                await auth_gate.check_and_wait(state['task_id'], 'nmap', state['user_id'])
            except Exception as e:
                if audit_logger:
                    audit_logger.log({
                        'task_id': state['task_id'],
                        'action': 'auth_denied',
                        'target': target,
                        'tool': 'nmap',
                        'error': str(e)
                    })
                # If auth is denied, we skip this target for nmap
                continue
        
        # Log tool start
        if audit_logger:
            audit_logger.log({
                'task_id': state['task_id'],
                'action': 'tool_start',
                'tool': 'nmap',
                'target': target
            })
        
        # Execute nmap scan
        try:
            start_time = time.time()
            result = await tool_executor.execute('nmap', {
                'targets': [target],
                'ports': '1-1000'  # Default to first 1000 ports
            }, timeout=300)
            duration = time.time() - start_time
            
            # Log tool completion
            if audit_logger:
                audit_logger.log({
                    'task_id': state['task_id'],
                    'action': 'tool_complete',
                    'tool': 'nmap',
                    'target': target,
                    'duration_seconds': duration,
                    'exit_code': result.get('exit_code'),
                    'vulnerabilities_found': len(result.get('vulnerabilities', []))
                })
            
            # Process result
            if result.get('exit_code') == 0:
                # Parse nmap output to extract open ports and services
                # This is a simplified example; in reality, you'd have a parser
                open_ports = []
                for line in result.get('parsed', {}).get('lines', []):
                    if '/open' in line:
                        # Extract port number (simplified)
                        parts = line.split()
                        if parts and parts[0].isdigit() and '/' in parts[0]:
                            port = parts[0].split('/')[0]
                            open_ports.append(port)
                
                if open_ports:
                    recon_findings.append({
                        'target': target,
                        'tool': 'nmap',
                        'open_ports': open_ports,
                        'raw_output': result.get('raw_output', '')[:1000],  # Truncate for storage
                        'timestamp': result.get('timestamp')
                    })
                    
                    # Also add to state findings
                    state['findings'].append({
                        'type': 'open_port',
                        'target': target,
                        'ports': open_ports,
                        'tool': 'nmap',
                        'timestamp': result.get('timestamp')
                    })
            else:
                if audit_logger:
                    audit_logger.log({
                        'task_id': state['task_id'],
                        'action': 'tool_failed',
                        'tool': 'nmap',
                        'target': target,
                        'exit_code': result.get('exit_code'),
                        'error': result.get('raw_output', '')[:200]
                    })
        except Exception as e:
            if audit_logger:
                audit_logger.log({
                    'task_id': state['task_id'],
                    'action': 'tool_error',
                    'tool': 'nmap',
                    'target': target,
                    'error': str(e)
                })
    
    # Update state with recon findings
    state['recon_findings'] = recon_findings
    
    # Log the end of recon node
    if audit_logger:
        audit_logger.log({
            'task_id': state['task_id'],
            'action': 'recon_complete',
            'findings_count': len(recon_findings)
        })
    
    # Determine next step based on findings (this is a simplified example)
    # In a real implementation, you might have more complex logic
    # For now, we'll always go to web scan if we have targets with open ports, else network scan
    # But we'll let the router decide based on the state
    
    return state