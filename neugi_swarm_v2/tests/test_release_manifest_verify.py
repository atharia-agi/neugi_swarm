"""Tests for release manifest verification and tamper detection."""

from __future__ import annotations

import hashlib
import hmac
import json
import subprocess
import tempfile
import time
from pathlib import Path


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _canonical(manifest: dict) -> bytes:
    payload = {
        "version": manifest.get("version", ""),
        "generated_at": manifest.get("generated_at"),
        "all_passed": manifest.get("all_passed"),
        "artifacts": manifest.get("artifacts", {}),
        "checks": manifest.get("checks", []),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def test_manifest_verify_and_tamper_detection():
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "verify_release_manifest.py"

    with tempfile.TemporaryDirectory() as td:
        tdir = Path(td)
        artifact = tdir / "artifact.txt"
        artifact.write_text("hello-neugi", encoding="utf-8")
        key = "test-signing-key"

        manifest = {
            "version": "2.1.3-test",
            "generated_at": time.time(),
            "all_passed": True,
            "artifacts": {str(artifact): _sha256(artifact)},
            "checks": [{"cmd": "dummy", "returncode": 0, "elapsed_ms": 1.0}],
        }
        sig = hmac.new(key.encode("utf-8"), _canonical(manifest), hashlib.sha256).hexdigest()
        manifest["signature"] = {"method": "hmac-sha256", "value": sig}

        manifest_path = tdir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        ok = subprocess.run(
            ["python", str(script), "--manifest", str(manifest_path), "--signing-key", key],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        assert ok.returncode == 0, ok.stdout + "\n" + ok.stderr

        # Tamper artifact -> verify must fail
        artifact.write_text("tampered-content", encoding="utf-8")
        bad = subprocess.run(
            ["python", str(script), "--manifest", str(manifest_path), "--signing-key", key],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        assert bad.returncode != 0

