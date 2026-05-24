#!/usr/bin/env python3
from __future__ import annotations

from datetime import date
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from neugi_swarm_v2.provider_catalog import get_all_providers

OUT = ROOT / "neugi_swarm_v2" / "docs" / "PROVIDER_MATRIX.md"


def main() -> int:
    providers = get_all_providers()
    lines: list[str] = []
    lines.append("# Provider Matrix (Runtime-Generated)")
    lines.append("")
    lines.append(f"Generated: {date.today().isoformat()}")
    lines.append("")
    lines.append("Source: `neugi_swarm_v2/provider_catalog.py`")
    lines.append("")
    lines.append("| Provider | Runtime Key | Compatibility | Auth | Models (Curated) |")
    lines.append("|---|---|---|---|---:|")
    for p in providers:
        auth = p.auth_type if p.auth_type else "bearer_header"
        lines.append(
            f"| {p.display_name} | `{p.name}` | `{p.compatibility}` | `{auth}` | {len(p.models)} |"
        )
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- This matrix is generated from runtime catalog, not maintained manually.")
    lines.append("- Custom providers are represented by compatibility entries and may expose any model IDs.")
    lines.append("")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
