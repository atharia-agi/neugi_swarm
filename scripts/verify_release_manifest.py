"""Verify release manifest integrity and signature.

Usage:
  python scripts/verify_release_manifest.py --manifest ~/.neugi/reports/release_manifest_*.json
  python scripts/verify_release_manifest.py --manifest <path> --signing-key <key>
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def canonical_payload(manifest: dict) -> bytes:
    payload = {
        "version": manifest.get("version", ""),
        "generated_at": manifest.get("generated_at"),
        "all_passed": manifest.get("all_passed"),
        "artifacts": manifest.get("artifacts", {}),
        "checks": manifest.get("checks", []),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--signing-key", default="")
    args = parser.parse_args()

    manifest_path = Path(args.manifest).expanduser()
    if not manifest_path.exists():
        print(f"manifest not found: {manifest_path}")
        return 1

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Verify artifact hashes
    artifacts = manifest.get("artifacts", {})
    bad_hashes = []
    for raw_path, expected_hash in artifacts.items():
        p = Path(raw_path).expanduser()
        if not p.exists():
            bad_hashes.append((raw_path, "missing"))
            continue
        actual = sha256_file(p)
        if actual != expected_hash:
            bad_hashes.append((raw_path, "hash_mismatch"))

    # Verify signature if present and key provided
    sig = manifest.get("signature", {}) or {}
    method = sig.get("method", "none")
    sig_ok = True
    sig_reason = "ok"
    if method == "hmac-sha256":
        key = args.signing_key
        if not key:
            sig_ok = False
            sig_reason = "signing_key_required"
        else:
            expected = hmac.new(key.encode("utf-8"), canonical_payload(manifest), hashlib.sha256).hexdigest()
            sig_ok = hmac.compare_digest(expected, str(sig.get("value", "")))
            if not sig_ok:
                sig_reason = "invalid_signature"

    print(f"manifest: {manifest_path}")
    print(f"hash_check: {'ok' if not bad_hashes else 'failed'}")
    if bad_hashes:
        for path, reason in bad_hashes:
            print(f" - {reason}: {path}")
    print(f"signature_check: {'ok' if sig_ok else 'failed'} ({sig_reason})")

    return 0 if (not bad_hashes and sig_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())

