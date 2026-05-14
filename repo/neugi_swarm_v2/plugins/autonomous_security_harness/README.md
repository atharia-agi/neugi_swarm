# Autonomous Security Harness Plugin for NEUGI Swarm

Advanced LangGraph-based autonomous security assessment harness with Docker sandbox, safety middleware, and immutable audit logging.

## Features

- **LangGraph Workflow Engine**: Stateful security assessment workflow with checkpointing
- **Docker Sandbox Execution**: Secure tool execution with resource limits and privilege dropping
- **Semantic Knowledge Base**: Vector-enhanced search using sentence-transformers for conceptual security knowledge retrieval
- **Safety Middleware**: 
  - Scope validation (target allowlisting, CIDR support, private IP control)
  - Authorization gates for high-risk tools (sqlmap, metasploit, etc.)
  - Immutable audit logging with hash chaining for tamper detection
- **Compliance Checking**: Automatic mapping of findings to security frameworks (NIST, ISO 27001, OWASP, etc.)
- **Modular Design**: Easy extension with additional security tools and scanning techniques
- **NEUGI Integration**: Works as a native plugin with zero core modifications

## Architecture

### Workflow Flow
```
recon → [web_scan OR network_scan] → compliance → report
```
- **Recon**: Network discovery (nmap) to identify open ports and services
- **Conditional Routing**: Based on recon findings:
  - Web ports (80, 443, 8080, etc.) → Web application scanning (nuclei, nikto)
  - Other ports → Network vulnerability scanning (nikto, etc.)
- **Compliance**: Map findings to security frameworks
- **Report**: Generate comprehensive security assessment report

### Security Controls
1. **Scope Validation**: All targets checked against allowlist before any tool execution
2. **Authorization Gates**: High-risk tools require explicit approval (simulated in this version)
3. **Docker Sandbox**: 
   - Read-only filesystem (except /tmp)
   - Privilege dropping (no-new-privileges, capability dropping)
   - Resource limits (2GB RAM, 1 CPU core)
   - Network isolation (outbound only)
4. **Audit Trail**: Immutable log with hash chaining for all security-relevant events

## Installation

```bash
# From the NEUGI root directory
neugi plugin install ./plugins/autonomous_security_harness
```

### Dependencies
The plugin requires the following additional Python packages:
- langgraph
- docker
- psycopg2-binary (for PostgreSQL checkpointing)
- whoosh
- sentence-transformers

Install with:
```bash
pip install langgraph docker psycopg2-binary whoosh sentence-transformers
```

### Tool Images
The plugin expects Docker images for security tools:
- `cybersec/nmap:latest`
- `cybersec/nuclei:latest`
- `cybersec/sqlmap:latest`
- `cybersec/nikto:latest`

You can build these using the provided Dockerfiles or use existing images.

## Configuration

Add to `~/.neugi/config.json`:

```json
{
  "autonomous_security_harness": {
    "kb_path": "/opt/neugi/security-knowledge-base",
    "index_path": "/var/lib/neugi/security_kb_index",
    "use_vectors": true,
    "scope": {
      "allowed_targets": ["example.com", "10.0.0.0/24", "192.168.1.100"],
      "allow_private_ips": false,
      "allowed_ports": [80, 443, 8080, 8443, 22, 443, 3306, 5432, 6379, 9200, 9300]
    },
    "audit_log_path": "/var/log/neugi/security_audit.jsonl",
    "checkpoint_db_url": "postgresql://neugi:password@localhost/neugi_checkpoints"
  }
}
```

### Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `kb_path` | Path to directory containing security knowledge base markdown files | `~/.neugi/knowledge` |
| `index_path` | Path where the search index will be stored | `~/.neugi/data/kb_index` |
| `use_vectors` | Whether to use vector embeddings for semantic search | `true` |
| `scope.allowed_targets` | List of allowed targets (IPs, hostnames, CIDR ranges) | `[]` |
| `scope.allow_private_ips` | Whether to allow scanning of private IP addresses (RFC 1918) | `false` |
| `scope.allowed_ports` | List of allowed port numbers | `[1-65535]` |
| `audit_log_path` | Path to immutable audit log file | `~/.neugi/data/audit.jsonl` |
| `checkpoint_db_url` | PostgreSQL connection string for workflow checkpoints | `sqlite:///:memory:` (in-memory) |

## Usage

### Via NEUGI Chat Interface
```python
from neugi_swarm_v2 import NeugiSwarmV2

swarm = NeugiSwarmV2()
# Tools are auto-registered via plugin system
result = swarm.chat("Perform a security assessment on example.com and 10.0.0.0/24")
```

### Direct Plugin Usage
```python
from plugins.autonomous_security_harness import AutonomousSecurityHarnessPlugin

# Initialize plugin
plugin = AutonomousSecurityHarnessPlugin()

# Run assessment
result = plugin.tool_security_assessment(
    targets=["example.com", "10.0.0.0/24"],
    options={
        "scope": {
            "allowed_targets": ["example.com", "10.0.0.0/24"],
            "allow_private_ips": false,
            "allowed_ports": [80, 443, 8080, 22]
        }
    }
)

print(json.dumps(result, indent=2))
```

### API Endpoints (when integrated with NEUGI API)
- `POST /api/v1/plugins/autonomous_security_harness/assess` - Run security assessment
- `GET /api/v1/plugins/autonomous_security_harness/status` - Get plugin status
- `GET /api/v1/plugins/autonomous_security_harness/history` - Get assessment history

## Knowledge Base

The plugin includes a knowledge base search tool that can be used independently:

```python
from plugins.autonomous_security_harness.core.knowledge.searcher import KnowledgeSearcher

searcher = KnowledgeSearcher("/path/to/index")
results = searcher.search_knowledge("SQL injection prevention techniques", limit=5)
```

The knowledge base should contain markdown files with YAML frontmatter:
```markdown
---
title: SQL Injection Prevention
frameworks: [OWASP, NIST]
severity: [high]
tools: [sqlmap]
---
# SQL Injection Prevention

Use parameterized queries or prepared statements to prevent SQL injection attacks.

## Key Points
- Never concatenate user input with SQL queries
- Use ORM frameworks when possible
- Implement input validation and output encoding
- Regular security testing and code reviews
```

## Output Format

The plugin returns results in a standardized format:

```json
{
  "task_id": "assessment_2targets_1740883200",
  "user_id": "system",
  "targets": ["example.com", "10.0.0.0/24"],
  "scope": {
    "allowed_targets": ["example.com", "10.0.0.0/24"],
    "allow_private_ips": false,
    "allowed_ports": [80, 443, 8080, 22]
  },
  "findings": [
    {
      "type": "open_port",
      "target": "example.com",
      "ports": [80, 443, 22],
      "tool": "nmap",
      "timestamp": "2026-03-01T10:30:00Z"
    },
    {
      "type": "vulnerability",
      "target": "example.com",
      "tool": "nuclei",
      "vuln_id": "cve-2021-12345",
      "severity": "high",
      "description": "SQL injection in login form",
      "timestamp": "2026-03-01T10:35:00Z"
    }
  ],
  "recon_findings": [...],
  "web_findings": [...],
  "network_findings": [...],
  "compliance_tags": [
    "OWASP ASVS 4.0",
    "NIST 800-53 SI-10",
    "ISO 27001 A.14.2.5"
  ],
  "audit_trail": [...],
  "summary": {
    "total_findings": 2,
    "open_ports_total": 3,
    "vulnerabilities_total": 1,
    "compliance_frameworks": [
      "OWASP ASVS 4.0",
      "NIST 800-53 SI-10",
      "ISO 27001 A.14.2.5"
    ]
  }
}
```

## Security Considerations

### Tool Sandboxing
All security tools execute in Docker containers with:
- `--read-only` filesystem (except `/tmp` for temporary files)
- `--security-opt no-new-privileges:true`
- `--cap-drop ALL` with selective `--cap-add` (e.g., `NET_RAW` for nmap SYN scans)
- Memory limit: 2GB
- CPU limit: 1.0 core
- Network mode: `bridge` (outbound connections only, no inbound allowed)

### Data Protection
- Audit logs use hash chaining to detect tampering
- Sensitive data in logs is truncated (first 100k characters of tool output)
- No persistent storage of tool outputs beyond the assessment lifecycle

### Extensibility
To add new security tools:
1. Add Docker image (e.g., `cybersec/newtool:latest`)
2. Update `core/tools/registry.json` with tool specification
3. Create or update output parser in `core/tools/parser.py` (if needed)
4. The tool will be automatically available through the ToolExecutor

## Performance

### Typical Execution Times
- Reconnaissance (nmap top 1000 ports): 30-120 seconds per target
- Web scanning (nuclei): 60-300 seconds per target
- Network scanning (nikto): 30-120 seconds per target
- Compliance checking: <10 seconds
- Report generation: <5 seconds

### Scaling Characteristics
- Horizontal scaling: Multiple instances can assess different targets
- Vertical scaling: Increase Docker resource limits for larger scans
- Knowledge base search: Sub-second response times with vector embeddings
- Workflow persistence: Checkpointing enables recovery from interruptions

## Troubleshooting

### Common Issues

**Docker Permission Errors**
```
docker: permission denied while trying to connect to the Docker daemon socket
```
Solution: Add user to docker group
```bash
sudo usermod -aG docker $USER
newgrp docker  # or log out and back in
```

**Tool Not Found**
```
ValueError: Unknown tool: newtool
```
Solution: Ensure the tool is registered in `core/tools/registry.json` and the Docker image exists

**Knowledge Base Not Found**
```
WARNING: Knowledge base not found: /path/to/kb
```
Solution: Ensure `kb_path` points to a directory with markdown files

**Audit Log Tampering Detected**
If `verify_chain()` returns False, the audit log has been modified and should be investigated immediately.

## Example Assessment

### Command
```bash
neugi chat "Assess the security of our web application at app.example.com and API endpoints at api.example.com"
```

### Expected Output
The plugin will:
1. Validate targets against scope
2. Run nmap reconnaissance on both targets
3. Based on open ports:
   - If ports 80/443 found: Run nuclei and nikto web scans
   - If other ports found: Run appropriate network scans
4. Check findings against compliance frameworks
5. Generate a detailed report with:
   - Executive summary
   - Detailed findings with evidence
   - Compliance mapping
   - Remediation recommendations
   - Audit trail for verification

## License
MIT License - see LICENSE file for details.

## Support
For issues, questions, or contributions, please visit the NEUGI Swarm repository.