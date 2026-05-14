# Migrating from v1 to v2

## Breaking Changes

### Configuration
- v1 used `.env` files; v2 uses `config.json` with structured schema
- Environment variables still supported as overrides

### Memory
- v1 stored memories as flat JSON files
- v2 uses SQLite with hierarchical scopes and FTS5 search
- Migration: Run `neugi migrate memory` to port v1 memories

### Skills
- v1 skills were Python modules in `skills/`
- v2 skills use SKILL.md v3 with YAML frontmatter
- Migration: Run `neugi migrate skills` to auto-convert

### Agents
- v1 agents were loosely defined in JSON
- v2 agents have strict `AgentRole` enum with XP/level progression
- Pre-configured agents now include: Builder, Planner, Analyst, Evaluator, Memory, Communicator

## New Features

| Feature | v1 | v2 |
|---------|-----|-----|
| Subsystems | 5 | 17 |
| Modules | ~30 | 96 |
| Lines of Code | ~8K | 54K+ |
| Built-in Tools | 12 | 61 |
| Memory System | Flat JSON | Hierarchical SQLite + FTS5 |
| Skill Tiers | 1 | 6 |
| Security | Basic denylist | 7-layer sandbox |
| MCP Support | None | Full spec (stdio + HTTP) |
| Channels | None | Telegram, Discord, Slack, WhatsApp |
| Planning | None | Tree of Thoughts + Chain of Verification |
| Auto-Learning | None | Pattern tracking + skill generation |
| Dashboard | None | Glass-morphism HTML + REST + WebSocket |

## Migration Steps

1. **Backup v1 data**
   ```bash
   cp -r ~/.neugi ~/.neugi.v1.backup
   ```

2. **Install v2**
   ```bash
   curl -fsSL https://raw.githubusercontent.com/atharia-agi/neugi_swarm/main/neugi_swarm_v2/install.sh | bash
   ```

3. **Run migration wizard**
   ```bash
   neugi migrate --from-v1
   ```

4. **Verify**
   ```bash
   neugi status
   neugi test
   ```

## CLI Changes

| v1 Command | v2 Equivalent |
|------------|---------------|
| `neugi chat` | `neugi chat` (enhanced with NL CLI) |
| `neugi agent` | `neugi agent` (now with roles + XP) |
| `neugi tool` | `neugi tool` (61 tools vs 12) |
| N/A | `neugi plan` (Tree of Thoughts) |
| N/A | `neugi workflow` (StateGraph builder) |
| N/A | `neugi skill workshop` (auto-generate) |
| N/A | `neugi gateway` (WebSocket RPC) |
| N/A | `neugi deploy` (Docker/Vercel/Railway) |

## API Changes

v1 had no formal API. v2 exposes:
- REST API (20 endpoints)
- WebSocket real-time events
- MCP server (stdio + HTTP)
- Plugin SDK (8 hooks)

See `API.md` for full reference.
