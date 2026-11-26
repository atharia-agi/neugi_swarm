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
- `snapshot.json` — FIXTURE (11 agen) untuk pengujian. File asli
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
- `agents[].id`: salah satu dari 11 id yang dikenal
  (`rangga, oto, beto, zeto, neto, geto, leto, ceto, seto, deto, meto`).
  PENTING: generator snapshot Oto HARUS memasukkan Meto (id `meto`)
  agar Meto tampil live — bila tidak ada di snapshot, Meto tidak
  ditampilkan (jujur, bukan ditebak).
  Agen yang TIDAK ada di snapshot TIDAK ditampilkan (jujur, bukan
  ditebak). Id yang tidak dikenal dilewati.
- `room`: id ruangan. Ruangan yang dikenal: `kantor-rangga`,
  `ruang-rapat`, `ruang-kerja`, `lounge`, `pantry`, `taman`,
  `studio-konten`, `war-room`, `lab-ai`. Id ruangan lain yang
  valid tetap diterima apa adanya (viewer tidak mengarang posisi).
- `state`: `working` | `meeting` | `idle` | `away`. Nilai lain =
  `idle`.
- `task`: judul tugas aktif (maks 40 karakter) atau `null`.
- `color`: hex `#rrggbb` (dipakai untuk plumbob/border; bila tidak
  valid, dipakai warna identitas bawaan). `name`/`role`: bila ada dan
  tidak kosong, dipakai dari snapshot (generator Oto memakai nilai
  kanonis yang sama dengan view-model, jadi hasilnya identik); bila
  kosong/tidak ada, dipakai label/role dari view-model.

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
- **Status bar**: "Snapshot per HH:MM:SS · N agen bekerja · polling
  60 detik" + penanda "snapshot basi" bila umur ≥15 menit. N = jumlah
  agen yang sedang bekerja (state `working`/`meeting` di snapshot;
  dihitung dari `face === 'fokus'`, karena snapshotToState tidak
  menyimpan string state mentah) — BUKAN jumlah tugas terbuka ruangan
  (snapshot hanya membawa 1 tugas aktif per agen; angka tugas terbuka
  ruangan ada di footer room, dari `/api/tasks`).
- **Snapshot gagal dimuat**: fetch snapshot dibatasi timeout 10 detik
  per percobaan, retry 2x (total 3 percobaan) sebelum menyerah. Bila
  pemuatan pertama gagal (timeout / HTTP error / jaringan), status bar
  menampilkan "Snapshot gagal dimuat — coba lagi (alasan)" + tombol
  **Coba lagi** (bukan diam-diam mentok di "Memuat snapshot kantor…");
  polling 60 detik tetap mencoba pulih sendiri di belakang.
- **Ruangan kosong dulu**: canvas ditempel + ruangan kosong di-render
  SEBELUM menunggu snapshot — bila fetch snapshot stall/timeout,
  pengunjung tetap melihat ruangan (tanpa agen), bukan hitam total;
  agen diisi saat snapshot datang.
- **Tanpa WebGL**: halaman tetap menampilkan kartu agen + status
  (fallback jujur, tanpa canvas).

## Mount API (embed di halaman lain)

`room-showcase.js` mengekspos `window.__neugiShowcase.mount(targetEl, opts)`
supaya halaman lain (mis. slot hero `kantor.html`) bisa me-mount viewer
ke sebuah elemen, tanpa memakai `office/index.html`:

```html
<div id="heroSlot"></div>
<script type="module">
  import '/office/room-showcase.js';
  await window.__neugiShowcase.mount(document.getElementById('heroSlot'), {
    snapshotUrl: 'office/snapshot.json',
  });
</script>
```

- `targetEl`: elemen DOM (slot hero) tempat viewer dipasang.
- `opts.snapshotUrl`: path snapshot (default: `snapshot.json` di samping
  modul, mis. `/office/snapshot.json` bila modul di `/office/`). Relatif
  terhadap halaman pemanggil — dari `kantor.html` di root, isi
  `'office/snapshot.json'`.
- `opts.autoRotate`: hero auto-rotate (default `true`; diabaikan bila
  `prefers-reduced-motion`).
- Mount mengembalikan `Promise<boolean>`: `true` bila viewer terpasang,
  `false` bila sudah terpasang sebelumnya (mount kedua = no-op).
- Bila struktur viewer belum ada di dokumen, mount() membuatnya di
  dalam `targetEl` (+ CSS penting ikut di-inject); overlay fullscreen
  menempel di `<body>`. Aset (model GLB, decoder Draco, snapshot
  default) selalu dimuat relatif terhadap modul, jadi host page di path
  mana pun tetap jalan. Avatar portrait/kartu/chip follow ikut jalan
  tanpa langkah tambahan — `room-showcase.js` mengimpor
  `avatar-voxel.js` sendiri (dulu blok inline di `index.html`). Di
  `office/index.html` sendiri, viewer
  auto-mount saat modul dimuat (struktur sudah ada) — `mount()` tidak
  perlu dipanggil.

## Deploy (Oto)

1. Salin 7 file kiriman board ke `office/` di repo neugi.com.
2. Salin aset biner dari agent-hq sesuai `ASSETS.md` (cek sha256).
   `meto.glb` (file_20261121_0218, sha `41b66682…`, 151.220 B) JUGA
   harus ikut di deploy backroom berikutnya sebagai
   `public/models/meto.glb` (deploy source agent-blackboard sudah
   ada versi baru) — tanpa file ini, viewer backroom tidak bisa
   memuat avatar Meto.
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
(5) `avatarScreenPos` di hook harness (edit 15, dari 0.4.9.1);
(6) kamera follow dijepit ke dalam denah (edit 23; follow Rangga =
    layar hitam karena kamera jatuh di luar dinding utara);
(7) mount API `window.__neugiShowcase.mount` + aset relatif terhadap
    modul + binding elemen lazy + auto-init kondisional (edit 24–25);
(8) dok `name`/`role` snapshot disamakan dengan kode (dipakai bila
    ada, fallback ke view-model);
(9) label status jujur — "N agen bekerja" (jumlah agen state working,
    bukan "N tugas terbuka": snapshot cuma bawa 1 tugas aktif per
    agen; angka tugas terbuka ruangan ada di footer room dari
    `/api/tasks`) (edit 26, Oto msg_0354);
(10) avatar voxel dipindah dari blok inline `index.html` ke
    `avatar-voxel.js` + diimpor `room-showcase.js` (edit 27) — viewer
    ter-mount dari halaman lain tetap beravatar; `index.html` tanpa
    blok inline lagi;
(11) timeout pemuatan snapshot 10 detik per percobaan + retry 2x
    (total 3 percobaan) + error state "Snapshot gagal dimuat — coba
    lagi" + tombol "Coba lagi" (edit 28, Zeto msg_0356 + Oto msg_0357 —
    `/office` hitam intermittent: `fetch` tanpa timeout menggantung
    selamanya bila koneksi stall; `loadAvatars` sudah punya timeout
    8 detik per GLB, jadi fetch snapshot satu-satunya await tanpa
    batas sebelum render pertama; endpoint snapshot sehat, 0,5–0,75
    dtk);
(12) ruangan kosong dulu — canvas ditempel + di-render SEBELUM
    snapshot via `attachCanvas()` + urutan init diubah (edit 29, Oto
    msg_0357 item 3): halaman tidak pernah hitam total bila fetch
    snapshot stall; agen diisi `applyState` saat snapshot datang.
(13) integrasi avatar Meto (Oto msg_0367 + msg_0373): `meto.glb`
    file_20261121_0218 (151.220 B, sha `41b66682…`, dicet: grill emas
    + belakang helm hijau) + joint map 11 avatar file_20261121_0216.
    Wiring seperti 10 avatar lain: `KNOWN_AGENTS` + `ROOM_ORDER`
    (view-model copy) + `AVATAR_PARTS` (avatar-voxel.js, warna
    identitas `#22c55e`) + `IDLE_SHOULDER_R` `meto: 10` (edit 30;
    shoulder_L bone_6 = default; joint map tervalidasi 10/10 cocok
    dengan tabel BASE) + `models/meto.glb` + fixture snapshot 11
    agen. Total 11 GLB 1.596.336 B (di bawah budget 4 MB).
    CATATAN re-sync: patch view-model (`KNOWN_AGENTS`/`ROOM_ORDER`
    Meto) hidup di salinan showcase ini — saat re-sync dari BASE
    baru, terapkan ulang patch itu ke salinan view-model yang baru
    (atau pastikan BASE produksi sudah mengenal Meto).
