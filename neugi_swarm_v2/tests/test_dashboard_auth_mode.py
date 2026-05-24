"""Auth-mode checks for dashboard API."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from dashboard.server import DashboardConfig, DashboardServer


def _request_json(url: str, api_key: str | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(url)
    if api_key:
        req.add_header("X-API-Key", api_key)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            code = int(resp.getcode())
            body = json.loads(resp.read().decode("utf-8"))
            return code, body
    except urllib.error.HTTPError as exc:
        body = {}
        try:
            body = json.loads(exc.read().decode("utf-8"))
        except Exception:
            body = {"error": "decode_failed"}
        return int(exc.code), body


def test_dashboard_auth_mode_requires_api_key():
    port = 17919
    cfg = DashboardConfig(
        host="127.0.0.1",
        port=port,
        enable_auth=True,
        api_key="test-auth-key",
    )
    server = DashboardServer(swarm=None, config=cfg)
    server.start(blocking=False)
    time.sleep(0.75)
    try:
        code_no_auth, body_no_auth = _request_json(f"http://127.0.0.1:{port}/api/health")
        assert code_no_auth == 401
        assert body_no_auth.get("error") == "Authentication required"

        code_auth, body_auth = _request_json(
            f"http://127.0.0.1:{port}/api/health",
            api_key="test-auth-key",
        )
        assert code_auth == 200
        assert body_auth.get("status") == "ok"
        assert body_auth.get("request_id")
        assert body_auth.get("latency_ms") is not None
    finally:
        server.stop()
