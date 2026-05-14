# Dependencies Reference

## Runtime Dependencies (from pyproject.toml)

### Core
- `toml >= 0.10.2` - TOML config parsing
- `httpx >= 0.23.0` - HTTP client for API calls
- `websockets >= 12.0` - WebSocket support for event streaming

### Plugin System
- `pydantic >= 2.5.0` - Data validation for plugin manifests
- `packaging >= 23.0` - Version handling

### Observability
- `psutil >= 5.9.0` - System monitoring (memory, CPU)

### Optional (for specific plugins)
- `sentence-transformers >= 2.2.0` - Vector embeddings (Autonomous Security Harness)
- `whoosh >= 2.7.4` - Full-text search (Cybersecurity Expert)
- `langgraph >= 0.0.50` - Stateful workflows (Autonomous Security Harness)
- `psycopg2-binary >= 2.9.0` - PostgreSQL adapter (LangGraph checkpoints)

## Test Dependencies
- `pytest >= 7.0.0` - Testing framework
- `pytest-asyncio >= 0.21.0` - Async test support

## Dev Dependencies
- `black >= 23.0` - Code formatting
- `isort >= 5.12.0` - Import sorting
- `mypy >= 1.5.0` - Type checking
- `bandit >= 1.7.0` - Security linting
- `semgrep >= 1.50.0` - Static analysis

## Installation Commands

```bash
# Core only
pip install toml httpx websockets pydantic packaging psutil

# With cybersecurity features
pip install sentence-transformers whoosh langgraph psycopg2-binary

# With test tools
pip install pytest pytest-asyncio

# Full development setup
pip install -e ".[dev]"