# NEUGI Swarm v2.1.3 - Deployment Guide

## Prerequisites

### Required
- **Python 3.10+** (tested on 3.13)
- **Docker Desktop** (for sandboxed tool execution)
- **Git** (for repository cloning)

### Optional (Recommended)
- **PostgreSQL 14+** (for LangGraph checkpoint persistence)
- **Redis** (for distributed event bus)

---

## Installation

### 1. Clone Repository
```bash
git clone git@github.com:atharia-agi/neugi_swarm.git
cd neugi_swarm/repo
```

### 2. Setup Virtual Environment
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -e .
```

### 4. Configure Environment
```bash
# Create config from template
copy neugi_swarm_v2/config.py neugi_swarm_v2/config.local.py

# Edit config.local.py with your settings:
# - LLM provider (OpenAI, Anthropic, local)
# - Database path
# - Docker sandbox settings
# - API keys via environment variables
```

---

## Plugin Deployment

### Autonomous Security Harness
```bash
# Verify plugin loads correctly
python -c "
from neugi_swarm_v2.plugins import PluginRegistry
pr = PluginRegistry()
pr.load_all()
harness = pr.get_plugin('autonomous_security_harness')
print(f'Status: {harness.status}')
print(f'Tools: {[t.name for t in harness.tools]}')
"
```

### Cybersecurity Expert
```bash
# Initialize knowledge base
python -c "
from neugi_swarm_v2.plugins.cybersecurity_expert import init_knowledge_base
init_knowledge_base()
print('Knowledge base initialized!')
"
```

---

## Docker Sandbox Setup

### Default Configuration
The Docker sandbox runs with maximum security:
- No network access by default
- Read-only filesystem
- All capabilities dropped
- Resource limits enforced

### Custom Configuration
Edit `neugi_swarm_v2/security/sandbox.py`:
```python
SANDBOX_CONFIG = {
    'network_disabled': True,
    'mem_limit': '512m',
    'cpu_period': 100000,
    'cpu_quota': 50000,
    'read_only': True,
    'cap_drop': ['ALL'],
}
```

---

## Running Services

### Start CLI
```bash
python -m neugi_swarm_v2.cli.cli
```

### Start Dashboard
```bash
python -m neugi_swarm_v2.dashboard.server
# Access at http://localhost:17901
```

### Start Event Bus (standalone)
```bash
python -m neugi_swarm_v2.observability.event_bus
```

---

## Production Considerations

### Environment Variables
| Variable | Description | Required |
|----------|-------------|----------|
| `NEUGI_API_KEY` | Main API key | Yes |
| `NEUGI_LLM_PROVIDER` | AI provider (openai/anthropic/local) | Yes |
| `NEUGI_DB_PATH` | SQLite database path | No (default: ./neugi.db) |
| `NEUGI_DOCKER_ENABLED` | Enable Docker sandbox | No (default: true) |
| `NEUGI_LOG_LEVEL` | Logging level | No (default: INFO) |

### Security Hardening
1. **Rotate API keys** regularly using SecretManager
2. **Enable TLS** for WebSocket connections
3. **Set rate limits** on event bus
4. **Monitor audit logs** for anomalies
5. **Pin Docker images** to specific versions

### Monitoring
- Dashboard: `http://localhost:17901`
- Event bus metrics: `/api/v1/metrics`
- Health check: `/api/v1/health`