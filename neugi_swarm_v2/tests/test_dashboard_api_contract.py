"""Dashboard frontend/backend API contract tests.

Ensures every API call referenced by dashboard.html is served by dashboard server routes.
"""

from __future__ import annotations

import re
from pathlib import Path


def _normalize_frontend_path(path: str) -> str:
    p = path.strip()
    p = re.sub(r"\$\{[^}]+\}", "{id}", p)
    p = p.split("?", 1)[0]
    p = p.replace("{id}", "{id}")
    return p


def _extract_frontend_api_calls(html: str) -> set[tuple[str, str]]:
    calls: set[tuple[str, str]] = set()
    pattern = re.compile(r"api\(\s*([`\"'])(.+?)\1(?P<rest>\s*,\s*\{.*?\})?\s*\)", re.S)
    for m in pattern.finditer(html):
        path = m.group(2)
        if "/api/" not in path:
            continue
        rest = m.group("rest") or ""
        method_match = re.search(r"method\s*:\s*['\"]([A-Z]+)['\"]", rest)
        method = method_match.group(1) if method_match else "GET"
        calls.add((method, _normalize_frontend_path(path)))
    return calls


def _extract_server_routes(server_py: str) -> set[tuple[str, str]]:
    routes: set[tuple[str, str]] = set()
    for method, path in re.findall(r"\"(GET|POST|PUT|DELETE) (/api/[^\"]+)\"", server_py):
        routes.add((method, path))
    return routes


def test_dashboard_frontend_api_contract() -> None:
    root = Path(__file__).resolve().parents[2]
    dashboard_html = (root / "dashboard.html").read_text(encoding="utf-8")
    server_py = (root / "neugi_swarm_v2" / "dashboard" / "server.py").read_text(encoding="utf-8")

    frontend_calls = _extract_frontend_api_calls(dashboard_html)
    server_routes = _extract_server_routes(server_py)

    # Map normalized dynamic frontend placeholders to server templated paths.
    normalized_server_routes = set()
    for method, path in server_routes:
        normalized_path = re.sub(r"\{[^/{}]+\}", "{id}", path)
        normalized_server_routes.add((method, normalized_path))

    missing = sorted(frontend_calls - normalized_server_routes)
    assert not missing, f"Dashboard API contract mismatch, missing backend routes: {missing}"

