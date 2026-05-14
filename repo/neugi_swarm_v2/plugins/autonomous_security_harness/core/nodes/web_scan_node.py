"""
Web Scan Node for Autonomous Security Harness.
Performs web application security scanning (e.g., nuclei, nikto) on targets.
"""
from typing import Any, Dict, List
import time

async def web_scan_node(state: dict, tool_executor, knowledge_searcher, scope_validator, auth_gate, audit_logger) -> dict:
    """
    Execute web application scanning phase.
    
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
    # Log the start of web scan node
    if audit_logger:
        audit_logger.log({
            'task_id': state['task_id'],
            'action': 'web_scan_start',
            'targets': state['targets']
        })
    
    # We'll run web scan tools on targets that have open ports (from recon) or all targets if recon didn't run
    # For simplicity, we'll run on all targets, but in reality, we might filter based on recon findings.
    web_findings = []
    
    for target in state['targets']:
        # Scope validation
        if not scope_validator.validate_target(target, 'nuclei'):
            if audit_logger:
                audit_logger.log({
                    'task_id': state['task_id'],
                    'action': 'scope_violation',
                    'target': target,
                    'tool': 'nuclei'
                })
            continue
        
        # Auth gate check for nuclei (medium risk)
        if auth_gate:
            try:
                await auth_gate.check_and_wait(state['task_id'], 'nuclei', state['user_id'])
            except Exception as e:
                if audit_logger:
                    audit_logger.log({
                        'task_id': state['task_id'],
                        'action': 'auth_denied',
                        'target': target,
                        'tool': 'nuclei',
                        'error': str(e)
                    })
                continue
        
        # Log tool start
        if audit_logger:
            audit_logger.log({
                'task_id': state['task_id'],
                'action': 'tool_start',
                'tool': 'nuclei',
                'target': target
            })
        
        # Execute nuclei scan
        try:
            start_time = time.time()
            result = await tool_executor.execute('nuclei', {
                'targets': [target],
                'templates': '/tmp/nuclei-templates'  # This would be configured
            }, timeout=300)
            duration = time.time() - start_time
            
            # Log tool completion
            if audit_logger:
                audit_logger.log({
                    'task_id': state['task_id'],
                    'action': 'tool_complete',
                    'tool': 'nuclei',
                    'target': target,
                    'duration_seconds': duration,
                    'exit_code': result.get('exit_code'),
                    'vulnerabilities_found': len(result.get('vulnerabilities', []))
                })
            
            # Process result: extract vulnerabilities from nuclei output
            # Nuclei outputs JSON if we use -json flag
            vulns = []
            if result.get('exit_code') == 0:
                # Parse the JSON output (each line is a JSON object)
                for line in result.get('parsed', {}).get('raw', '').splitlines():
                    if line.strip():
                        try:
                            vuln = json.loads(line)
                            vulns.append(vuln)
                        except:
                            pass
                
                if vulns:
                    web_findings.append({
                        'target': target,
                        'tool': 'nuclei',
                        'vulnerabilities': vulns,
                        'raw_output': result.get('raw_output', '')[:1000],
                        'timestamp': result.get('timestamp')
                    })
                    
                    # Add to state findings
                    for vuln in vulns:
                        state['findings'].append({
                            'type': 'vulnerability',
                            'target': target,
                            'tool': 'nuclei',
                            'vuln_id': vuln.get('template-id', 'unknown'),
                            'severity': vuln.get('info', {}).get('severity', 'unknown'),
                            'description': vuln.get('info', {}).get('description', ''),
                            'timestamp': result.get('timestamp')
                        })
            else:
                if audit_logger:
                    audit_logger.log({
                        'task_id': state['task_id'],
                        'action': 'tool_failed',
                        'tool': 'nuclei',
                        'target': target,
                        'exit_code': result.get('exit_code'),
                        'error': result.get('raw_output', '')[:200]
                    })
        except Exception as e:
            if audit_logger:
                audit_logger.log({
                    'task_id': state['task_id'],
                    'action': 'tool_error',
                    'tool': 'nuclei',
                    'target': target,
                    'error': str(e)
                })
    
    # Update state with web scan findings
    state['web_findings'] = web_findings
    
    # Log the end of web scan node
    if audit_logger:
        audit_logger.log({
            'task_id': state['task_id'],
            'action': 'web_scan_complete',
            'findings_count': len(web_findings)
        })
    
    return state