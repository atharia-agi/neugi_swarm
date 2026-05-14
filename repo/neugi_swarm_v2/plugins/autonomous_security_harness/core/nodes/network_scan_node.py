"""
Network Scan Node for Autonomous Security Harness.
Performs network vulnerability scanning (e.g., nikto) on targets.
"""
from typing import Any, Dict, List
import time

async def network_scan_node(state: dict, tool_executor, knowledge_searcher, scope_validator, auth_gate, audit_logger) -> dict:
    """
    Execute network scanning phase.
    
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
    # Log the start of network scan node
    if audit_logger:
        audit_logger.log({
            'task_id': state['task_id'],
            'action': 'network_scan_start',
            'targets': state['targets']
        })
    
    # We'll run network scan tools on targets
    network_findings = []
    
    for target in state['targets']:
        # Scope validation
        if not scope_validator.validate_target(target, 'nikto'):
            if audit_logger:
                audit_logger.log({
                    'task_id': state['task_id'],
                    'action': 'scope_violation',
                    'target': target,
                    'tool': 'nikto'
                })
            continue
        
        # Auth gate check for nikto (we'll consider it low risk, but let's check anyway)
        if auth_gate:
            try:
                await auth_gate.check_and_wait(state['task_id'], 'nikto', state['user_id'])
            except Exception as e:
                if audit_logger:
                    audit_logger.log({
                        'task_id': state['task_id'],
                        'action': 'auth_denied',
                        'target': target,
                        'tool': 'nikto',
                        'error': str(e)
                    })
                continue
        
        # Log tool start
        if audit_logger:
            audit_logger.log({
                'task_id': state['task_id'],
                'action': 'tool_start',
                'tool': 'nikto',
                'target': target
            })
        
        # Execute nikto scan
        try:
            start_time = time.time()
            result = await tool_executor.execute('nikto', {
                'targets': [target],
                'output_file': '/tmp/nikto_output.json'
            }, timeout=300)
            duration = time.time() - start_time
            
            # Log tool completion
            if audit_logger:
                audit_logger.log({
                    'task_id': state['task_id'],
                    'action': 'tool_complete',
                    'tool': 'nikto',
                    'target': target,
                    'duration_seconds': duration,
                    'exit_code': result.get('exit_code'),
                    'vulnerabilities_found': len(result.get('vulnerabilities', []))
                })
            
            # Process result: nikto can output JSON if we use -output-format json
            # But note: our registry for nikto uses -output and we set output_file to json.
            # We'll assume the output file is JSON and try to parse it.
            vulns = []
            if result.get('exit_code') == 0:
                # Try to parse the output file as JSON
                import json
                output_file = '/tmp/nikto_output.json'
                try:
                    with open(output_file, 'r') as f:
                        data = json.load(f)
                        # Nikto JSON output structure may vary; we'll extract what we can
                        if isinstance(data, dict) and 'vulnerabilities' in data:
                            vulns = data['vulnerabilities']
                        elif isinstance(data, list):
                            vulns = data
                except Exception as e:
                    if audit_logger:
                        audit_logger.log({
                            'task_id': state['task_id'],
                            'action': 'parse_error',
                            'tool': 'nikto',
                            'target': target,
                            'error': str(e)
                        })
                    # Fallback to parsing raw output
                    pass
                
                if vulns:
                    network_findings.append({
                        'target': target,
                        'tool': 'nikto',
                        'vulnerabilities': vulns,
                        'raw_output': result.get('raw_output', '')[:1000],
                        'timestamp': result.get('timestamp')
                    })
                    
                    # Add to state findings
                    for vuln in vulns:
                        # Try to extract common fields
                        vuln_id = vuln.get('id', vuln.get('name', 'unknown'))
                        desc = vuln.get('desc', vuln.get('description', ''))
                        state['findings'].append({
                            'type': 'vulnerability',
                            'target': target,
                            'tool': 'nikto',
                            'vuln_id': str(vuln_id),
                            'description': str(desc)[:200],  # Truncate
                            'timestamp': result.get('timestamp')
                        })
            else:
                if audit_logger:
                    audit_logger.log({
                        'task_id': state['task_id'],
                        'action': 'tool_failed',
                        'tool': 'nikto',
                        'target': target,
                        'exit_code': result.get('exit_code'),
                        'error': result.get('raw_output', '')[:200]
                    })
        except Exception as e:
            if audit_logger:
                audit_logger.log({
                    'task_id': state['task_id'],
                    'action': 'tool_error',
                    'tool': 'nikto',
                    'target': target,
                    'error': str(e)
                })
    
    # Update state with network scan findings
    state['network_findings'] = network_findings
    
    # Log the end of network scan node
    if audit_logger:
        audit_logger.log({
            'task_id': state['task_id'],
            'action': 'network_scan_complete',
            'findings_count': len(network_findings)
        })
    
    return state