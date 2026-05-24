"""Runtime entrypoint for NEUGI dashboard server."""

from __future__ import annotations

import logging
import os
import signal
import sys
from pathlib import Path

from neugi_swarm_v2 import NeugiSwarmV2
from neugi_swarm_v2.dashboard.server import DashboardServer


def _pid_path() -> Path:
    return Path.home() / ".neugi" / "dashboard.pid"


def _write_pid() -> None:
    path = _pid_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(os.getpid()), encoding="utf-8")


def _clear_pid() -> None:
    path = _pid_path()
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass


def main() -> int:
    """Start NEUGI swarm + dashboard server in blocking mode."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    swarm = NeugiSwarmV2()
    server = DashboardServer(swarm=swarm)
    _write_pid()

    def _shutdown(_sig: int, _frame: object) -> None:
        try:
            server.stop()
        finally:
            try:
                swarm.close()
            finally:
                _clear_pid()
                sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _shutdown)

    try:
        server.start(blocking=True)
    finally:
        _clear_pid()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
