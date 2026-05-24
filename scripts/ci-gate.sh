#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../neugi_swarm_v2"

python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

python -m neugi_swarm_v2.cli.cli doctor --json --strict
python -m neugi_swarm_v2.cli.cli quickstart --ci
python -m neugi_swarm_v2.cli.cli smoke --json --strict

ruff check .
ruff format --check .
bandit -r . -c pyproject.toml
mypy . --ignore-missing-imports
python -m pytest tests/ -q --tb=short -p no:anchorpy
