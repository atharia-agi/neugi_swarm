#!/usr/bin/env python3
"""Cek pasca-deploy neugi.com: bandingkan string kunci di halaman LIVE.

Cara pakai:
  python3 site/data/check_live.py
  python3 site/data/check_live.py --base https://neugi.com

Mengambil halaman live (dengan cache-busting ?v=<timestamp>) dan
memastikan string kunci ronde audit ada / tidak ada di sana.
Jalankan SETELAH deploy, bukan sebelum — situs live baru berubah
setelah Vercel selesai deploy.

Juga dijalankan otomatis harian oleh GitHub Actions
(.github/workflows/check-live.yml). TIDAK dijalankan pada push/PR:
situs live belum berubah saat push masuk, jadi cek live di CI push
akan gagal palsu. Gerbang push/PR adalah lint_facts.py (statis).

Keluar 0 kalau semua cocok, 1 kalau ada yang tidak cocok.
Hanya stdlib Python. User-Agent browser (Vercel memblokir UA default
urllib di sebagian endpoint).
"""

import argparse
import base64
import re
import sys
import time
import urllib.error
import urllib.request

BASE_DEFAULT = "https://neugi.com"
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
TIMEOUT = 20

# Setiap entri: halaman + string yang HARUS ada + string yang TIDAK BOLEH
# ada + string yang HARUS ada di dalam blok <footer>.
CHECKS = [
    {"url": "",
     "present": ["Asisten CEO"],
     "absent": ["Wakil CEO", "10 avatar"],
     "footer": ["Buku Tamu"]},
    {"url": "kantor.html",
     "present": ["Viewer 3D · snapshot"],
     "absent": ["Viewer 3D · live"],
     "footer": ["Buku Tamu"]},
    {"url": "proyek.html",
     "present": ["12 avatar rigged", "12 dari 12",
                 "sudah bisa dibuka di halaman Kantor"],
     "absent": ["sudah live di halaman Kantor", "sedang disiapkan"],
     "footer": ["Buku Tamu"]},
    {"url": "tentang.html",
     "present": ["satu-satunya bagian yang punya backend adalah Buku Tamu"],
     "absent": ["tanpa backend"],
     "footer": ["Buku Tamu"]},
    {"url": "arsip.html",
     "present": ["deploy sempat gagal setelah merge"],
     "absent": ["deploy sempat tertunda"],
     "footer": ["Buku Tamu"]},
    {"url": "guestbook/",
     "present": ["12 agen + owner"],
     "absent": ["13 agen", "KB v2026", "Tinggalkan jejakmu di bawah",
                "(biarkan kosong)"],
     "footer": ["Buku Tamu"]},
    {"url": "riset/index.html",
     "present": [],
     "absent": [],
     "footer": ["Buku Tamu"]},
    {"url": "riset/agen-openai-email.html",
     "present": ["alignment.openai.com/misalignment-reports"],
     "absent": [],
     "footer": ["Buku Tamu"]},
    {"url": "riset/decision-model-liquid.html",
     "present": ["angka vendor, belum diverifikasi independen",
                 "blogs.windows.com/msedgedev", "blog.google"],
     "absent": [],
     "footer": ["Buku Tamu"]},
    {"url": "riset/higgsfield-mcp.html",
     "present": ["higgsfield.ai/mcp"],
     "absent": ["Benarkah Bisa Bikin Agent Editing Video Sekelas Manusia?"],
     "footer": ["Buku Tamu"]},
    {"url": "riset/model-kecil-q3-2026.html",
     "present": ["Tidak ada satu pun model Q3 2026 yang mengalahkan Qwen3.5-2B"],
     "absent": ["Benchmark Model Kecil Ronde 2: Hanya Q3 2026"],
     "footer": ["Buku Tamu"]},
    {"url": "riset/nemotron-sigma.html",
     "present": ["Nemotron-Labs-Sigma",
                 "huggingface.co/nvidia/Nemotron-Labs-Sigma-3B"],
     "absent": ["Nemotron-Sigma LM diffusion"],
     "footer": ["Buku Tamu"]},
    {"url": "riset/prime-intellect.html",
     "present": ["1 dari 100 prompt ditolak", "2 dari 313", "0 dari 240"],
     "absent": ["Insiden Prime Intellect: DeepSeek v4.1-flash diganti"],
     "footer": ["Buku Tamu"]},
    {"url": "riset/video-open-source-vs-flow.html",
     "present": ["Kling 3.0 720p yang 1099",
                 "artificialanalysis.ai/video/leaderboard/text-to-video",
                 "arena.ai/leaderboard/text-to-video",
                 "Belum ada model video open source yang menyamai Seedance 2.5"],
     "absent": ["patokan Kling 3.0 yang 1000",
                "Model Video Generatif Open Source vs Google Flow, Seedance, Kling"],
     "footer": ["Buku Tamu"]},
]


def _maybe_b64decode(raw):
    """Egress dari VM ini mengembalikan body HTTP ter-encode base64
    (teks maupun biner). Deteksi + decode; kalau bukan base64 yang
    menghasilkan HTML, kembalikan apa adanya."""
    text = raw.strip()
    if len(text) < 100 or len(text) % 4 != 0:
        return raw
    try:
        ascii_text = text.decode("ascii")
    except UnicodeDecodeError:
        return raw
    if not re.fullmatch(r"[A-Za-z0-9+/=]+", ascii_text):
        return raw
    try:
        dec = base64.b64decode(ascii_text, validate=True)
    except Exception:
        return raw
    head = dec[:2000].lower()
    if (b"<html" in head or dec[:15].lower().startswith(b"<!doctype")
            or dec[:4] == b"\x00\x00\x01\x00"  # ICO
            or dec[:8] == b"\x89PNG\r\n\x1a\n"  # PNG
            or dec[:3] == b"\xff\xd8\xff"):  # JPEG
        return dec
    return raw


def fetch(url):
    """Ambil satu URL live (cache-busting), kembalikan teks UTF-8."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        if resp.status != 200:
            raise urllib.error.HTTPError(url, resp.status, "HTTP %s" % resp.status,
                                         resp.headers, None)
        raw = resp.read()
    raw = _maybe_b64decode(raw)
    return raw.decode("utf-8", errors="replace")


def footer_block(html):
    """Isi blok <footer>...</footer>, atau '' kalau tidak ada."""
    m = re.search(r"<footer[^>]*>(.*?)</footer>", html,
                  re.DOTALL | re.IGNORECASE)
    return m.group(1) if m else ""


def check_favicon(base, stamp, failures):
    """Favicon: /favicon.ico harus 200 + ICO valid, dan halaman beranda
    harus memuat ketiga link favicon."""
    for path, magic in (("favicon.ico", b"\x00\x00\x01\x00"),
                        ("favicon-32x32.png", b"\x89PNG"),
                        ("apple-touch-icon.png", b"\x89PNG")):
        url = "%s/%s?v=%d" % (base, path, stamp)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                if resp.status != 200:
                    failures.append(f"{path}: HTTP {resp.status} (harap 200)")
                    continue
                raw = _maybe_b64decode(resp.read())
        except Exception as exc:  # noqa: BLE001 - laporkan apa pun yang gagal
            failures.append(f"{path}: gagal diambil ({exc})")
            continue
        if not raw.startswith(magic):
            failures.append(f"{path}: bukan file yang valid "
                            f"(magic bytes tidak cocok)")
    try:
        home = fetch("%s/?v=%d" % (base, stamp))
    except Exception as exc:  # noqa: BLE001
        failures.append(f"(beranda): gagal diambil untuk cek favicon ({exc})")
        return
    for link in ('href="/favicon.ico"', 'href="/favicon-32x32.png"',
                 'href="/apple-touch-icon.png"'):
        if link not in home:
            failures.append(f"(beranda): link favicon tidak ada: {link}")


def main():
    ap = argparse.ArgumentParser(description="Cek string kunci di neugi.com live.")
    ap.add_argument("--base", default=BASE_DEFAULT,
                    help="basis URL (default %(default)s)")
    args = ap.parse_args()
    base = args.base.rstrip("/")
    stamp = int(time.time())
    failures = []

    check_favicon(base, stamp, failures)

    for check in CHECKS:
        url = "%s/%s?v=%d" % (base, check["url"], stamp)
        label = check["url"] or "(beranda)"
        try:
            html = fetch(url)
        except Exception as exc:  # noqa: BLE001 - laporkan apa pun yang gagal
            failures.append(f"{label}: gagal diambil ({exc})")
            continue
        for s in check.get("present", []):
            if s not in html:
                failures.append(f"{label}: HARUS ADA tapi tidak ada: '{s}'")
        for s in check.get("absent", []):
            if s in html:
                failures.append(f"{label}: TIDAK BOLEH ADA tapi masih ada: '{s}'")
        fb = footer_block(html)
        for s in check.get("footer", []):
            if s not in fb:
                failures.append(f"{label}: footer belum memuat '{s}'")

    if failures:
        print(f"GAGAL: {len(failures)} ketidakcocokan di situs live:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print(f"LOLOS: {len(CHECKS)} halaman live cocok "
          f"(string kunci ronde 1 + ronde 2 ada, string lama tidak ada, "
          f"footer memuat 'Buku Tamu').")
    return 0


if __name__ == "__main__":
    sys.exit(main())
