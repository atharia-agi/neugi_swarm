# NEUGI v2 Deployment Guide

## Quick Start

### Local (Development)

```bash
# Clone
git clone https://github.com/atharia-agi/neugi_swarm.git
cd neugi_swarm/neugi_swarm_v2

# Install
pip install -e .

# Run
neugi wizard      # Interactive setup
neugi chat        # Start chatting
neugi dashboard   # Launch web UI
```

### One-Liner Install

**macOS / Linux:**
```bash
curl -fsSL https://raw.githubusercontent.com/atharia-agi/neugi_swarm/main/neugi_swarm_v2/install.sh | bash
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/atharia-agi/neugi_swarm/main/neugi_swarm_v2/install.bat | iex
```

## Docker

### Single Container

```bash
docker build -t neugi:v2 .
docker run -p 8080:8080 -v neugi-data:/data neugi:v2
```

### Docker Compose (Full Stack)

```bash
docker-compose up -d
```

Services:
- `neugi-core` — Main application
- `neugi-dashboard` — Web UI
- `neugi-gateway` — WebSocket RPC
- `ollama` — Local LLM (optional)
- `redis` — Cache / message broker (optional)

## Cloud Deployment

### Vercel (Dashboard Only)

```bash
neugi deploy --target vercel
```

### Railway

```bash
neugi deploy --target railway
```

### Render

```bash
neugi deploy --target render
```

### Fly.io

```bash
neugi deploy --target fly
```

### Self-Hosted (VPS / Bare Metal)

```bash
# Copy files
rsync -avz ./neugi_swarm_v2/ user@server:/opt/neugi/

# On server
cd /opt/neugi
pip install -r requirements.txt
pip install -e .

# Systemd service
cp deploy/neugi.service /etc/systemd/system/
systemctl enable --now neugi
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NEUGI_DATA_DIR` | `~/.neugi` | Data directory |
| `NEUGI_LLM_PROVIDER` | `ollama` | LLM provider |
| `NEUGI_LLM_MODEL` | `qwen2.5-coder:7b` | Default model |
| `NEUGI_OLLAMA_URL` | `http://localhost:11434` | Ollama endpoint |
| `NEUGI_API_KEY` | — | Cloud provider key |
| `NEUGI_DASHBOARD_PORT` | `8080` | Dashboard port |
| `NEUGI_LOG_LEVEL` | `INFO` | Logging level |
| `NEUGI_SANDBOX_ENABLED` | `true` | Enable sandbox |

## Production Checklist

- [ ] Set strong `NEUGI_API_KEY` or use secret manager
- [ ] Enable sandbox (`NEUGI_SANDBOX_ENABLED=true`)
- [ ] Configure resource limits in sandbox
- [ ] Set up immutable audit logging
- [ ] Enable approval gates for destructive operations
- [ ] Configure backup for `~/.neugi` directory
- [ ] Set up log rotation
- [ ] Enable HTTPS for dashboard (reverse proxy)
- [ ] Configure firewall rules
- [ ] Set up monitoring (Prometheus metrics at `/metrics`)

## Scaling

### Horizontal (Multi-Agent)

```bash
# Start multiple agent workers
neugi agent worker --role builder --count 4
neugi agent worker --role analyst --count 2
```

### Vertical (Multi-Core)

NEUGI automatically uses thread pools for:
- Memory queries (SQLite concurrent reads)
- Tool execution (parallel where safe)
- Skill matching (in-memory, no locks)

### Gateway Clustering

```bash
# Primary gateway
neugi gateway --port 8081 --mode primary

# Secondary gateways
neugi gateway --port 8082 --mode secondary --primary ws://host1:8081
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Ollama not found | Run `neugi wizard` to configure provider |
| Port conflict | Set `NEUGI_DASHBOARD_PORT` |
| Permission denied | Check sandbox config or run with `--no-sandbox` (dev only) |
| Out of memory | Reduce `max_tokens` or enable context compaction |
| Slow startup | Disable unused plugins with `neugi plugin disable <name>` |

## Health Checks

```bash
# CLI
curl http://localhost:8080/api/v2/health

# Expected response
{"status": "ok", "version": "2.0.0", "subsystems": 17}
```
