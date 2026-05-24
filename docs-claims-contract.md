# Docs Claims Contract

This file defines measurable public claims that must stay in sync with runtime.

## Source of Truth Files

- `README.md`
- `docs.html`
- `neugi_swarm_v2/docs/API.md`
- `neugi_swarm_v2/docs/TUTORIAL.md`

## Runtime Fingerprint (Auto-validated)

- Version: from `neugi_swarm_v2/__init__.py` (`__version__`)
- Top-level CLI commands: from `NeugiCLI._commands` in `neugi_swarm_v2/cli/cli.py`
- Dashboard API endpoints: from `routes` dict in `neugi_swarm_v2/dashboard/server.py`
- Provider catalog entries: from `DEFAULT_PROVIDERS` in `neugi_swarm_v2/provider_catalog.py`
- Test collection count: from `pytest --collect-only -q -p no:anchorpy neugi_swarm_v2/tests`

## Claim Rules

1. Installer one-liner in all public docs must use:
   - `https://neugi.com/install.ps1`
   - `https://neugi.com/install.sh`
2. Public docs must not reference legacy install one-liners:
   - `raw.githubusercontent.com/atharia-agi/neugi_swarm/master/neugi_swarm_v2/install.*`
3. Numeric claims must match runtime values:
   - README `top-level commands`
   - README `REST endpoints`
4. API docs must not reference legacy `/api/v2` path.

## Enforcement Modes

- `advisory`: returns success with warning report.
- `strict`: exits non-zero on first mismatch.
