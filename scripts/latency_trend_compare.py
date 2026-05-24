"""Compare current synthetic latency report against baseline/history."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _results_map(report: dict) -> dict[str, float]:
    out: dict[str, float] = {}
    for row in report.get("results", []):
        path = str(row.get("path", ""))
        latency = float(row.get("latency_ms", 0.0))
        if path:
            out[path] = latency
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--current", default=str(Path.home() / ".neugi" / "reports" / "synthetic_dashboard_monitor.json"))
    parser.add_argument("--baseline", default=str(Path.home() / ".neugi" / "reports" / "latency_baseline.json"))
    parser.add_argument("--regression-pct", type=float, default=25.0)
    parser.add_argument("--output", default=str(Path.home() / ".neugi" / "reports" / "latency_trend_report.json"))
    args = parser.parse_args()

    current_path = Path(args.current)
    baseline_path = Path(args.baseline)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not current_path.exists():
        print(f"current report missing: {current_path}")
        return 1

    current = _load_json(current_path)
    current_map = _results_map(current)

    if not baseline_path.exists():
        baseline = {
            "generated_at": time.time(),
            "results": [{"path": k, "latency_ms": v} for k, v in sorted(current_map.items())],
        }
        baseline_path.write_text(json.dumps(baseline, indent=2), encoding="utf-8")
        report = {
            "status": "initialized",
            "message": "Baseline initialized from current report.",
            "baseline_path": str(baseline_path),
            "regressions": [],
        }
        output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"trend report: {output_path}")
        return 0

    baseline = _load_json(baseline_path)
    baseline_map = _results_map(baseline)

    regressions = []
    comparisons = []
    for path, curr in sorted(current_map.items()):
        prev = float(baseline_map.get(path, curr))
        pct = ((curr - prev) / prev * 100.0) if prev > 0 else 0.0
        row = {"path": path, "current_ms": round(curr, 2), "baseline_ms": round(prev, 2), "delta_pct": round(pct, 2)}
        comparisons.append(row)
        if pct > float(args.regression_pct):
            regressions.append(row)

    # rolling baseline update (EWMA style)
    alpha = 0.2
    updated = {}
    for path, curr in current_map.items():
        prev = float(baseline_map.get(path, curr))
        updated[path] = round((alpha * curr) + ((1.0 - alpha) * prev), 4)
    baseline_updated = {
        "generated_at": time.time(),
        "results": [{"path": k, "latency_ms": v} for k, v in sorted(updated.items())],
    }
    baseline_path.write_text(json.dumps(baseline_updated, indent=2), encoding="utf-8")

    report = {
        "status": "ok" if not regressions else "regression_detected",
        "regression_threshold_pct": float(args.regression_pct),
        "regression_count": len(regressions),
        "comparisons": comparisons,
        "regressions": regressions,
        "baseline_path": str(baseline_path),
        "generated_at": time.time(),
    }
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"trend report: {output_path}")
    print(f"regressions: {len(regressions)}")
    return 0 if not regressions else 1


if __name__ == "__main__":
    raise SystemExit(main())

