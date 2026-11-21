# README.md — Showcase Kantor 3D (neugi.com)

Showcase publik kantor virtual 3D — tampilan read-only dari kantor tim.
BASE: room 3D kantor v0.4.9.1 + CORS (repo agent-hq), diubah jadi varian
terpisah `room-showcase.js`. File produksi (`room3d.js`, `index.html`
produksi) TIDAK disentuh.

## Yang dijamin (syarat keras)

1. **Alamat asli kantor TIDAK bisa ketahuan dari file ini.** Viewer
   hanya me-request `snapshot.json` (same origin, path relatif) — tidak
   ada fetch/URL ke sistem lain di mana pun (kode, data, komentar).
   Audit (berlaku untuk file kode + data, bukan file dokumen ini):
   `grep -ri "backroom\|vercel\|/api/\|http" index.html room-showcase.js
   room-viewmodel.js snapshot.json` harus kosong.
2. **Read-only.** Tanpa login, tanpa composer, tanpa posting.
   Klik avatar = kartu info + follow kamera saja.
3. **Data dari `snapshot.json` statis** (Oto yang generate + update
   berkala). Viewer poll tiap 60 detik. Bila snapshot basi (>15 menit),
   status bar menandainya; bila >2 jam, bubble agen ditandai stale.

## File

- `index.html` — hero mini display (auto-rotate) + overlay fullscreen.
  Klik ruangan = layar penuh; klik agen di fullscreen = follow.
- `room-showcase.js` — viewer (0.4.9.1-showcase). Satu-satunya request
  jaringan: `fetch('snapshot.json')`.
- `room-viewmodel.js` — view-model murni (salinan 0.4.9).
- `snapshot.json` — FIXTURE (10 agen) untuk pengujian. File asli
  digenerate Oto — lihat kontrak di bawah.
- `ASSETS.md` — manifest aset biner (GLB + three.js + Draco) + sha256.
- `vendor/`, `models/` — disalin dari agent-hq (lihat ASSETS.md).

## Kontrak `snapshot.json` (untuk generator Oto)

```json
{
  "generated_at": "2026-11-21T07:55:11+07:00",
  "agents": [
    {
      "id": "beto", "name": "Beto", "role": "CTO",
      "color": "#fc7a24",
      "room": "ruang-kerja",
      "state": "working",
      "task": "Maximum Level room program"
    }
  ]
}
```

- `generated_at`: ISO 8601 + offset (dipakai status bar + penanda basi).
- `agents[].id`: salah satu dari 10 id yang dikenal
  (`rangga, oto, beto, zeto, neto, geto, leto, ceto, seto, deto`).
  Agen yang TIDAK ada di snapshot TIDAK ditampilkan (jujur, bukan
  ditebak). Id yang tidak dikenal dilewati.
- `room`: id ruangan. Ruangan yang dikenal: `kantor-rangga`,
  `ruang-rapat`, `ruang-kerja`, `lounge`, `pantry`, `taman`,
  `studio-konten`, `war-room`, `perpustakaan`. Id ruangan lain yang
  valid tetap diterima apa adanya (viewer tidak mengarang posisi).
- `state`: `working` | `meeting` | `idle` | `away`. Nilai lain =
  `idle`.
- `task`: judul tugas aktif (maks 40 karakter) atau `null`.
- `color`: hex `#rrggbb` (dipakai untuk plumbob/border; bila tidak
  valid, dipakai warna identitas bawaan). `name`/`role` di snapshot
  diabaikan viewer — yang dipakai label/role dari view-model
  (identitas kanonis), supaya snapshot tidak bisa mengubah identitas.

## Perilaku viewer

- **Hero**: canvas kecil di halaman, auto-rotate lambat (±50 detik/
  putaran), berhenti saat fullscreen / tab tersembunyi / reduced-motion.
  Klik ruangan di hero = layar penuh (overview). Klik agen di hero =
  layar penuh + follow agen itu.
- **Fullscreen**: orbit bebas (seret), zoom (pinch/scroll), pan.
  Klik agen = kamera third-person follow (terkunci di belakang agen,
  mengikuti saat agen berjalan). Chip "Mengikuti \<Nama\>" + tombol
  lepas di kartu info. Keluar follow: klik lantai kosong / Esc /
  tombol X / klik agen lain (pindah follow). Esc saat tidak follow =
  keluar fullscreen.
- **Mobile (360px)**: tap agen = follow, tap X = lepas. Kartu agen
  vertikal di bawah hero (mode utama HP) — klik kartu = fullscreen +
  follow. Portrait strip di atas kartu — klik portrait = fullscreen +
  follow.
- **Status bar**: "Snapshot per HH:MM:SS · N tugas terbuka · polling
  60 detik" + penanda "snapshot basi" bila umur ≥15 menit.
- **Tanpa WebGL**: halaman tetap menampilkan kartu agen + status
  (fallback jujur, tanpa canvas).

## Deploy (Oto)

1. Salin 6 file kiriman board ke `office/` di repo neugi.com.
2. Salin aset biner dari agent-hq sesuai `ASSETS.md` (cek sha256).
3. Ganti `snapshot.json` fixture dengan hasil generator Oto.
4. Buka `office/index.html` via server statis apa pun (atau langsung
   dari repo) — tidak butuh server khusus, tidak butuh build.
5. Cek: hero berputar, klik = fullscreen, klik agen = chip
   "Mengikuti …" muncul, Esc = keluar, tidak ada request keluar
   dari folder `office/` di tab Network.

## Re-sync dengan Maximum Level

Perbaikan Maximum Level (pencahayaan, kaki di lantai, kamera) juga
berlaku untuk showcase — saat Maximum Level merge, buat ulang varian
ini dari `room3d.js` terbaru dengan `transform.py` yang sama
(`~/workspace/showcase-neugi/transform.py`) lalu kirim ulang
`room-showcase.js` via board. Semua penyesuaian showcase hidup DI
DALAM `transform.py` (bukan edit manual hasil transform), jadi
re-sync = jalankan ulang transform dari BASE baru:
(1) `renderPortraits` — `mode` → `noSnap`, klik portrait →
fullscreen + follow (edit 20);
(2) pencahayaan showcase — Ambient 0.55→1.0, Hemisphere 0.9→1.5,
Directional 2.2→2.8, rim 0.7→1.0, exposure 1.15→1.35 (edit 21;
ruangan publik harus jelas di HP; produksi tetap gelap sampai
Maximum Level merge — saat re-sync, pakai nilai Maximum Level);
(3) penjaga race Esc — `fsSeq`/`fsExitSeq`/`fsExiting` supaya
fullscreenchange basi tidak membatalkan follow/entry baru (edit 22);
(4) `mentionInComposer` dihapus (edit 12b, read-only);
(5) `avatarScreenPos` di hook harness (edit 15, dari 0.4.9.1).

## Integrasi home/kantor (catatan Oto, 2026-11-21)

- Varian ini adalah halaman standalone (`office/index.html`) — itu yang
  di-deploy sekarang. `site/kantor.html` menautkan ke halaman ini.
- `site/assets/viewer.js` (slot hero di home + kantor) mengharapkan
  `window.__neugiShowcase.mount(slot, snapshot)`; varian ini BELUM
  menyediakan mount API itu (modul ES auto-boot + `init()`), jadi slot
  hero tetap menampilkan fallback statis sampai mount API ditambahkan
  (tindak lanjut ke Beto via board, di `transform.py`).
- `snapshot.json` di sini BUKAN fixture — digenerate Oto dari data live
  board (`~/workspace/neugi-audit/snapshot-gen/`); snapshot basi >15
  menit ditandai viewer. Regenerasi berkala (cron) masih disiapkan.
