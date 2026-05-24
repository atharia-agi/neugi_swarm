"""Synthetic dashboard endpoint monitoring.

Usage:
  python scripts/synthetic_dashboard_monitor.py --base-url http://localhost:17901 --threshold-ms 1200
"""

from __future__ import annotations

import argparse
import gzip
import json
import time
import urllib.error
import urllib.request
from pathlib import Path


ENDPOINTS = [
    "/api/health",
    "/api/agents",
    "/api/sessions",
    "/api/skills",
    "/api/memory/stats",
    "/api/governance/profile",
    "/api/providers",
    "/api/config",
]


def fetch(base_url: str, path: str, timeout: float = 12.0) -> dict:
    started = time.perf_counter()
    req = urllib.request.Request(f"{base_url}{path}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            latency_ms = (time.perf_counter() - started) * 1000.0
            raw = resp.read()
            encoding = (resp.headers.get("Content-Encoding") or "").lower()
            if encoding == "gzip":
                raw = gzip.decompress(raw)
            body = raw.decode("utf-8", errors="replace")
            try:
                payload = json.loads(body)
            except Exception:
                payload = {}
            return {
                "path": path,
                "ok": resp.status == 200,
                "status": int(resp.status),
                "latency_ms": round(latency_ms, 2),
                "request_id": payload.get("request_id"),
            }
    except urllib.error.HTTPError as exc:
        latency_ms = (time.perf_counter() - started) * 1000.0
        return {
            "path": path,
            "ok": False,
            "status": int(exc.code),
            "latency_ms": round(latency_ms, 2),
            "request_id": None,
        }
    except Exception:
        latency_ms = (time.perf_counter() - started) * 1000.0
        return {
            "path": path,
            "ok": False,
            "status": -1,
            "latency_ms": round(latency_ms, 2),
            "request_id": None,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:17901")
    parser.add_argument("--threshold-ms", type=float, default=3500.0)
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    results = []
    base = args.base_url.rstrip("/")
    for p in ENDPOINTS:
        attempt_rows = [fetch(base, p) for _ in range(max(1, int(args.attempts)))]
        ok_rows = [r for r in attempt_rows if r["ok"]]
        best = min(ok_rows, key=lambda r: r["latency_ms"]) if ok_rows else attempt_rows[-1]
        best["attempts"] = len(attempt_rows)
        results.append(best)
    failures = [r for r in results if (not r["ok"]) or (r["latency_ms"] > args.threshold_ms)]
    summary = {
        "base_url": args.base_url,
        "threshold_ms": args.threshold_ms,
        "checked": len(results),
        "failures": len(failures),
        "results": results,
        "generated_at": time.time(),
    }

    out_path = Path(args.output) if args.output else Path.home() / ".neugi" / "reports" / "synthetic_dashboard_monitor.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"monitor report: {out_path}")
    print(f"checked={len(results)} failures={len(failures)} threshold_ms={args.threshold_ms}")
    for row in results:
        print(f"{row['status']:>3} {row['latency_ms']:>7.2f}ms {row['path']}")

    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
