#!/usr/bin/env python3
"""Lint fakta neugi.com terhadap facts.json (kanonik).

Cara pakai (dari root repo):
  python3 site/data/lint_facts.py
Atau dari site/data/:
  python3 lint_facts.py

Cek:
  (a) Jumlah agen/avatar di HTML sama dengan facts.json (12 agen + 1 owner
      = 13 orang). Menolak angka lain ("10 avatar", "11 agen", "13 agen")
      dan peran lama ("Wakil CEO").
  (b) Frasa blokir tidak muncul di halaman publik: "KB v", "akun<N>"
      (nomor akun internal), "free tier", "Remotion", "VoxCPM2",
      "Modal T4" / "Modal L4" / "di Modal", "tanpa backend".
  (c) Judul bagian <h2> yang sama tidak dipakai di 2+ artikel riset.

Dikecualikan: site/smar.html (keep as is per keputusan Rangga 24 Nov 2026),
site/office/ (viewer JS, teksnya di-render browser), site/assets/.

Keluar 0 kalau lolos, 1 kalau ada temuan.
"""

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITE = HERE.parent
FACTS = HERE / "facts.json"

# Frasa blokir (b): pola regex, case-insensitive.
BLOCKED = [
    (r"KB\s+v", '"KB v" (penanda internal knowledge base)'),
    (r"akun\d", '"akun<N>" (nomor akun internal)'),
    (r"free tier", '"free tier"'),
    (r"Remotion", '"Remotion" (tooling internal)'),
    (r"VoxCPM2", '"VoxCPM2" (tooling internal)'),
    (r"Modal\s+(T4|L4)", '"Modal T4/L4" (nama provider)'),
    (r"di\s+Modal", '"di Modal" (nama provider)'),
    (r"app\s+Modal", '"app Modal" (nama aplikasi internal)'),
    (r"tanpa backend", '"tanpa backend" (klaim basi; satu-satunya backend adalah Buku Tamu)'),
]

# File yang tidak dicek.
EXCLUDE_FILES = {"smar.html"}
EXCLUDE_DIRS = {"office", "assets", "data"}


def iter_html_files():
    """Semua .html di site/, kecuali yang dikecualikan."""
    for path in sorted(SITE.rglob("*.html")):
        rel = path.relative_to(SITE)
        if rel.name in EXCLUDE_FILES:
            continue
        if any(part in EXCLUDE_DIRS for part in rel.parts):
            continue
        yield path


def check_counts(text, rel, expected_agents, problems):
    """(a) Angka agen/avatar harus sama dengan facts.json."""
    for m in re.finditer(r"(\d+)\s+avatar", text, re.IGNORECASE):
        if int(m.group(1)) != expected_agents:
            problems.append(f"{rel}: jumlah avatar salah: '{m.group(0)}' "
                            f"(harusnya {expected_agents})")
    for m in re.finditer(r"(\d+)\s+agen", text, re.IGNORECASE):
        if int(m.group(1)) != expected_agents:
            problems.append(f"{rel}: jumlah agen salah: '{m.group(0)}' "
                            f"(harusnya {expected_agents})")
    if re.search(r"Wakil CEO", text):
        problems.append(f"{rel}: peran lama 'Wakil CEO' masih muncul "
                        f"(harusnya 'Asisten CEO')")


def check_blocked(text, rel, problems):
    """(b) Frasa blokir tidak boleh muncul."""
    for pattern, label in BLOCKED:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            line = text[:m.start()].count("\n") + 1
            problems.append(f"{rel}:{line}: frasa blokir {label}: "
                            f"'{m.group(0)}'")


def check_duplicate_h2(problems):
    """(c) Judul <h2> yang sama tidak boleh dipakai di 2+ artikel riset."""
    seen = {}
    riset = SITE / "riset"
    for path in sorted(riset.glob("*.html")):
        if path.name in ("index.html", "artikel.html"):
            continue
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(r"<h2[^>]*>(.*?)</h2>", text, re.DOTALL):
            title = re.sub(r"<[^>]+>", "", m.group(1))
            title = re.sub(r"\s+", " ", title).strip()
            key = title.lower()
            if not key:
                continue
            if key in seen:
                problems.append(
                    f"riset/{path.name}: judul <h2> '{title}' sudah dipakai di "
                    f"riset/{seen[key]} (duplikat)")
            else:
                seen[key] = path.name


def main():
    facts = json.loads(FACTS.read_text(encoding="utf-8"))
    expected_agents = facts["squad"]["agents_total"]
    problems = []

    for path in iter_html_files():
        rel = path.relative_to(SITE)
        text = path.read_text(encoding="utf-8")
        check_counts(text, rel, expected_agents, problems)
        check_blocked(text, rel, problems)

    check_duplicate_h2(problems)

    if problems:
        print(f"GAGAL: {len(problems)} temuan:")
        for p in problems:
            print(f"  - {p}")
        return 1

    print(f"LOLOS: 0 temuan "
          f"({expected_agents} agen + {facts['squad']['owner_total']} owner, "
          f"frasa blokir bersih, judul <h2> riset unik).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
