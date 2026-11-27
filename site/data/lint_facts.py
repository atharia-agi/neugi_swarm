#!/usr/bin/env python3
"""Lint fakta neugi.com terhadap facts.json (kanonik).

Cara pakai (dari root repo):
  python3 site/data/lint_facts.py
Atau dari site/data/:
  python3 lint_facts.py
Juga dijalankan otomatis oleh GitHub Actions (.github/workflows/lint.yml)
pada setiap push ke master dan setiap pull request.

Cek:
  (a) Jumlah agen/avatar di HTML sama dengan facts.json (12 agen + 1 owner
      = 13 orang). Menolak angka lain ("10 avatar", "11 agen", "13 agen")
      dan peran lama ("Wakil CEO").
  (b) Frasa blokir tidak muncul di halaman publik: "KB v", "akun<N>"
      (nomor akun internal), "free tier", "Remotion", "VoxCPM2",
      "Modal T4" / "Modal L4" / "di Modal", "tanpa backend".
  (c) Judul bagian <h2> yang sama tidak dipakai di 2+ artikel riset.
  (d) Kata "live" tidak muncul di teks terlihat halaman publik, KECUALI
      frasa yang memang benar-benar bukan klaim viewer live (daftar
      LIVE_ALLOWLIST di bawah: "bukan live", "tanpa koneksi live",
      "tidak ada koneksi live", "tidak ada animasi mengetik live",
      "metrik live" (fitur produk), "situs live" (situs produksi)).
      Viewer 3D menampilkan snapshot, bukan live — jadi klaim "live"
      untuk viewer selalu salah. Cek juga meta description (muncul di
      hasil pencarian).
  (e) Pola "bukan ... melainkan" maksimal 1x per artikel riset.
  (f) <title> artikel riset harus cocok dengan H1 (judul <title> tanpa
      sufiks " · NEUGI" harus terkandung di H1, atau sebaliknya).
  (g) Footer semua halaman harus memuat tautan "Buku Tamu".

Dikecualikan: site/smar.html (keep as is per keputusan Rangga 24 Nov 2026),
site/office/ (viewer JS, teksnya di-render browser), site/assets/.
Aturan (g) juga mengecualikan smar.html.

Keluar 0 kalau lolos, 1 kalau ada temuan. Hanya stdlib Python.
"""

import html as html_lib
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

# Frasa "live" yang diizinkan (d): kata "live" di dalamnya merujuk ke
# sesuatu yang memang live / negasi, BUKAN klaim viewer live.
LIVE_ALLOWLIST = [
    "bukan live",
    "tanpa koneksi live",
    "tidak ada koneksi live",
    "tidak ada animasi mengetik live",
    "metrik live",
    "situs live",
    "went live",
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


def iter_riset_articles():
    """7 artikel riset (bukan halaman daftar/template)."""
    riset = SITE / "riset"
    for path in sorted(riset.glob("*.html")):
        if path.name in ("index.html", "artikel.html"):
            continue
        yield path


def _preserve_lines(s):
    """Ganti string dengan spasi, pertahankan jumlah baris."""
    return "".join("\n" if ch == "\n" else " " for ch in s)


def visible_text(html):
    """Teks yang terlihat di halaman: tanpa komentar HTML, blok <script> /
    <style>, dan tanpa tag. Jumlah baris dipertahankan supaya nomor baris
    di laporan tetap akurat."""
    text = re.sub(r"<!--.*?-->", lambda m: _preserve_lines(m.group(0)),
                  html, flags=re.DOTALL)
    text = re.sub(r"<script\b[^>]*>.*?</script>",
                  lambda m: _preserve_lines(m.group(0)),
                  text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style\b[^>]*>.*?</style>",
                  lambda m: _preserve_lines(m.group(0)),
                  text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", lambda m: _preserve_lines(m.group(0)), text)
    return html_lib.unescape(text)


def meta_descriptions(html):
    """Isi meta description (muncul di hasil pencarian) + nomor barisnya."""
    out = []
    for m in re.finditer(r"<meta\b[^>]*>", html, re.IGNORECASE):
        tag = m.group(0)
        if not re.search(r"""name=["']description["']""", tag, re.IGNORECASE):
            continue
        cm = re.search(r"""content=["']([^"']*)["']""", tag, re.IGNORECASE)
        if cm:
            line = html[:m.start()].count("\n") + 1
            out.append((html_lib.unescape(cm.group(1)), line))
    return out


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
    for path in iter_riset_articles():
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


def check_live(text, rel, problems, source_label="teks terlihat",
               base_line=1):
    """(d) Kata "live" hanya boleh muncul dalam frasa allowlist.
    `text` adalah teks yang sudah dibersihkan dari tag; `base_line`
    adalah nomor baris awal teks ini di file (1 untuk teks halaman,
    nomor baris tag <meta> untuk meta description)."""
    low = text.lower()
    allowed_spans = set()
    for phrase in LIVE_ALLOWLIST:
        start = 0
        while True:
            i = low.find(phrase, start)
            if i < 0:
                break
            li = phrase.rfind("live")
            allowed_spans.add((i + li, i + li + len("live")))
            start = i + 1
    for m in re.finditer(r"\blive\b", text, re.IGNORECASE):
        if (m.start(), m.end()) in allowed_spans:
            continue
        line = base_line + text[:m.start()].count("\n")
        ctx = re.sub(r"\s+", " ", text[max(0, m.start() - 45):m.end() + 45]).strip()
        problems.append(f"{rel}:{line}: kata 'live' di {source_label} "
                        f"(viewer menampilkan snapshot, bukan live): "
                        f"'...{ctx}...'")


def check_bukan_melainkan(problems):
    """(e) Pola 'bukan ... melainkan' maksimal 1x per artikel riset."""
    pattern = re.compile(r"bukan\b[^\n.]{0,120}?melainkan",
                         re.IGNORECASE | re.DOTALL)
    for path in iter_riset_articles():
        text = visible_text(path.read_text(encoding="utf-8"))
        matches = pattern.findall(text)
        if len(matches) > 1:
            shown = "; ".join(
                re.sub(r"\s+", " ", m).strip()[:60] for m in matches[:3])
            problems.append(
                f"riset/{path.name}: pola 'bukan ... melainkan' muncul "
                f"{len(matches)}x (maks 1x): {shown}")


def check_title_h1(problems):
    """(f) <title> artikel riset harus cocok dengan H1."""
    for path in iter_riset_articles():
        text = path.read_text(encoding="utf-8")
        tm = re.search(r"<title>(.*?)</title>", text,
                       re.DOTALL | re.IGNORECASE)
        h1m = re.search(r"<h1[^>]*>(.*?)</h1>", text,
                        re.DOTALL | re.IGNORECASE)
        if not tm or not h1m:
            problems.append(f"riset/{path.name}: <title> atau <h1> "
                            f"tidak ditemukan")
            continue
        title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", tm.group(1))).strip()
        h1 = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", h1m.group(1))).strip()
        core = re.sub(r"\s*·\s*NEUGI\s*$", "", title).strip()
        if core.lower() not in h1.lower() and h1.lower() not in core.lower():
            problems.append(f"riset/{path.name}: <title> tidak cocok "
                            f"dengan H1 (title: '{core}' | H1: '{h1}')")


def check_footer(text, rel, problems):
    """(g) Footer harus memuat tautan 'Buku Tamu'."""
    m = re.search(r"<footer[^>]*>(.*?)</footer>", text,
                  re.DOTALL | re.IGNORECASE)
    if not m:
        problems.append(f"{rel}: tidak ada <footer>")
        return
    if "Buku Tamu" not in m.group(1):
        problems.append(f"{rel}: footer belum memuat tautan 'Buku Tamu'")


def main():
    facts = json.loads(FACTS.read_text(encoding="utf-8"))
    expected_agents = facts["squad"]["agents_total"]
    problems = []

    for path in iter_html_files():
        rel = path.relative_to(SITE)
        text = path.read_text(encoding="utf-8")
        check_counts(text, rel, expected_agents, problems)
        check_blocked(text, rel, problems)
        check_live(visible_text(text), rel, problems)
        for desc, line in meta_descriptions(text):
            check_live(desc, rel, problems,
                       source_label="meta description", base_line=line)
        check_footer(text, rel, problems)

    check_duplicate_h2(problems)
    check_bukan_melainkan(problems)
    check_title_h1(problems)

    if problems:
        print(f"GAGAL: {len(problems)} temuan:")
        for p in problems:
            print(f"  - {p}")
        return 1

    print(f"LOLOS: 0 temuan "
          f"({expected_agents} agen + {facts['squad']['owner_total']} owner, "
          f"frasa blokir bersih, judul <h2> riset unik, tanpa 'live' di "
          f"konteks viewer, pola 'bukan ... melainkan' <=1x/artikel, "
          f"<title> cocok H1, footer memuat 'Buku Tamu').")
    return 0


if __name__ == "__main__":
    sys.exit(main())
