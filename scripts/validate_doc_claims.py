#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Finding:
    level: str  # ERROR | WARN | INFO
    message: str


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def extract_version() -> str:
    text = read_text(ROOT / "neugi_swarm_v2" / "__init__.py")
    m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', text)
    if not m:
        raise RuntimeError("Unable to extract __version__")
    return m.group(1)


def count_provider_catalog() -> int:
    mod = ast.parse(read_text(ROOT / "neugi_swarm_v2" / "provider_catalog.py"))
    for node in mod.body:
        target_match = False
        value = None
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "DEFAULT_PROVIDERS":
            target_match = True
            value = node.value
        elif isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == "DEFAULT_PROVIDERS" for t in node.targets):
                target_match = True
                value = node.value
        if target_match and isinstance(value, ast.List):
            return sum(
                1 for item in value.elts
                if isinstance(item, ast.Call) and getattr(item.func, "id", "") == "ProviderInfo"
            )
    raise RuntimeError("DEFAULT_PROVIDERS not found")


def count_dashboard_routes() -> int:
    mod = ast.parse(read_text(ROOT / "neugi_swarm_v2" / "dashboard" / "server.py"))
    for node in mod.body:
        if isinstance(node, ast.ClassDef) and node.name == "DashboardServer":
            for fn in node.body:
                if isinstance(fn, ast.FunctionDef) and fn.name == "_register_routes":
                    for stmt in fn.body:
                        if isinstance(stmt, ast.Assign):
                            has_routes_target = any(isinstance(t, ast.Name) and t.id == "routes" for t in stmt.targets)
                            if has_routes_target and isinstance(stmt.value, ast.Dict):
                                return len(stmt.value.keys)
    raise RuntimeError("Dashboard routes dict not found")


def count_top_level_cli_commands() -> int:
    mod = ast.parse(read_text(ROOT / "neugi_swarm_v2" / "cli" / "cli.py"))
    for node in mod.body:
        if isinstance(node, ast.ClassDef) and node.name == "NeugiCLI":
            for fn in node.body:
                if isinstance(fn, ast.FunctionDef) and fn.name == "_register_commands":
                    for stmt in fn.body:
                        if not isinstance(stmt, ast.Assign):
                            continue
                        for target in stmt.targets:
                            if isinstance(target, ast.Attribute) and target.attr == "_commands" and isinstance(stmt.value, ast.Dict):
                                return len(stmt.value.keys)
    raise RuntimeError("NeugiCLI._commands not found")


def collect_pytest_count() -> int:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "neugi_swarm_v2/tests",
        "--collect-only",
        "-q",
        "-p",
        "no:anchorpy",
    ]
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    output = f"{proc.stdout}\n{proc.stderr}"
    m = re.search(r"collected\s+(\d+)\s+items", output)
    if not m:
        raise RuntimeError("Could not parse pytest collection count")
    return int(m.group(1))


def parse_readme_claim_int(pattern: str, label: str, findings: list[Finding]) -> int | None:
    readme = read_text(ROOT / "README.md")
    m = re.search(pattern, readme, flags=re.IGNORECASE)
    if not m:
        findings.append(Finding("WARN", f"README claim not found for {label}"))
        return None
    return int(m.group(1))


def ensure_no_legacy_install_urls(findings: list[Finding]) -> None:
    targets = [
        ROOT / "README.md",
        ROOT / "docs.html",
        ROOT / "neugi_swarm_v2" / "docs" / "API.md",
        ROOT / "neugi_swarm_v2" / "docs" / "TUTORIAL.md",
    ]
    legacy = re.compile(r"raw\.githubusercontent\.com/atharia-agi/neugi_swarm/master/neugi_swarm_v2/install\.(ps1|sh)")
    for path in targets:
        text = read_text(path)
        if legacy.search(text):
            findings.append(Finding("ERROR", f"Legacy install URL found in {path}"))


def ensure_oneliner_domain(findings: list[Finding]) -> None:
    targets = [
        ROOT / "README.md",
        ROOT / "docs.html",
        ROOT / "neugi_swarm_v2" / "docs" / "TUTORIAL.md",
    ]
    required = ["https://neugi.com/install.ps1", "https://neugi.com/install.sh"]
    for path in targets:
        text = read_text(path)
        for token in required:
            if token not in text:
                findings.append(Finding("ERROR", f"Missing `{token}` in {path}"))


def ensure_no_legacy_api_v2(findings: list[Finding]) -> None:
    targets = [
        ROOT / "docs.html",
        ROOT / "neugi_swarm_v2" / "docs" / "API.md",
        ROOT / "neugi_swarm_v2" / "docs" / "TUTORIAL.md",
    ]
    for path in targets:
        text = read_text(path)
        if "/api/v2" in text:
            findings.append(Finding("ERROR", f"Legacy `/api/v2` reference found in {path}"))


def validate() -> tuple[list[Finding], dict[str, int | str]]:
    findings: list[Finding] = []
    runtime = {
        "version": extract_version(),
        "top_level_commands": count_top_level_cli_commands(),
        "api_endpoints": count_dashboard_routes(),
        "provider_catalog_count": count_provider_catalog(),
        "tests_collected": collect_pytest_count(),
    }

    # Claim checks in README (human-facing high-value claims)
    readme_cmds = parse_readme_claim_int(r"(\d+)\s+top-level commands", "top-level commands", findings)
    if readme_cmds is not None and readme_cmds != runtime["top_level_commands"]:
        findings.append(Finding("ERROR", f"README top-level commands={readme_cmds}, runtime={runtime['top_level_commands']}"))

    readme_routes = parse_readme_claim_int(r"(\d+)\s+REST endpoints", "REST endpoints", findings)
    if readme_routes is not None and readme_routes != runtime["api_endpoints"]:
        findings.append(Finding("ERROR", f"README REST endpoints={readme_routes}, runtime={runtime['api_endpoints']}"))

    ensure_no_legacy_install_urls(findings)
    ensure_oneliner_domain(findings)
    ensure_no_legacy_api_v2(findings)

    findings.append(Finding("INFO", f"Runtime fingerprint: v{runtime['version']} | commands={runtime['top_level_commands']} | api={runtime['api_endpoints']} | providers={runtime['provider_catalog_count']} | tests={runtime['tests_collected']}"))
    return findings, runtime


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate docs claims against runtime values")
    parser.add_argument("--mode", choices=["strict", "advisory"], default="advisory")
    args = parser.parse_args()

    findings, _runtime = validate()
    errors = [f for f in findings if f.level == "ERROR"]

    for f in findings:
        prefix = {"ERROR": "[ERROR]", "WARN": "[WARN]", "INFO": "[INFO]"}[f.level]
        print(f"{prefix} {f.message}")

    if args.mode == "strict" and errors:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
