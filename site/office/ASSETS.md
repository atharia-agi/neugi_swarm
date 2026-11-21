# ASSETS.md — Showcase Kantor 3D (neugi.com)

File-file di folder `office/` ini adalah yang DIKIRIM lewat board.
Aset biner (GLB + three.js + Draco) TIDAK ikut dikirim — Oto menyalinnya
dari repo agent-hq (BASE 0.4.9.1 + CORS) ke folder yang sama.
Semua ukuran + sha256 di bawah diukur langsung dari BASE 0.4.9.1.

## File yang dikirim (7 file, via board)

| File | Ukuran | Keterangan |
|---|---|---|
| `index.html` | ~7 KB | Halaman showcase: hero mini display + overlay fullscreen |
| `room-showcase.js` | ~152 KB | Varian viewer (0.4.9.1-showcase); JANGAN edit `room3d.js` produksi |
| `avatar-voxel.js` | ~22 KB | Avatar voxel SVG 11 agen (dulu blok inline di index.html; diimpor `room-showcase.js`, jadi viewer ter-mount tetap beravatar) |
| `room-viewmodel.js` | ~30 KB | View-model murni (salinan verbatim 0.4.9, 2 baris komentar disesuaikan) |
| `snapshot.json` | ~1,4 KB | FIXTURE untuk pengujian — diganti `snapshot.json` asli oleh Oto |
| `ASSETS.md` | — | File ini |
| `README.md` | — | Panduan deploy + kontrak snapshot |

## Aset yang disalin Oto dari agent-hq (bukan dari board)

Sumber: repo `ragetalamus-agent/agent-hq`, branch `main`, folder `public/`
(versi 0.4.9.1 + CORS).

### Vendor three.js — `office/vendor/three/`

| File | Ukuran | sha256 |
|---|---|---|
| `three.module.js` | 1.272.972 B | `76dea8151bc9352aef3528b4262e249b2604f62543828328db978d060d61a495` |
| `GLTFLoader.js` | 108.533 B | `d121e14073ae2470396644531763400d9c4d0137252c63835411ef9feeefb018` |
| `DRACOLoader.js` | 13.640 B | `e4348b2c255e7d851df790cafb93bcdd7ac0d2a1a6916038b43580b1e6d6c3fb` |

### Decoder Draco — `office/vendor/draco/`

| File | Ukuran | sha256 |
|---|---|---|
| `draco_decoder.js` | 512.465 B | `8625489da79a805f4f2a7d511c3e52d8b4085608a9d2a4d5f4f9de5db0aea04f` |
| `draco_decoder.wasm` | 192.420 B | `a680d927bed9cb864ddbd63521868891af2bfbe755092761b4837487618df8ac` |
| `draco_wasm_wrapper.js` | 58.456 B | `8bb2952d2ba7d67e1414f8df819410cb0434a666be53f671fff75f68843d76f6` |

### Model GLB — `office/models/` (total 1.596.336 B, budget 4 MB)

| File | Ukuran | sha256 |
|---|---|---|
| `rangga.glb` | 131.588 B | `65d828a6a0b6bc7e8d595953892d2108e9f36f17ba23cd482b2b0f901c1bd03d` |
| `oto.glb` | 116.012 B | `27947c1abb3a12aa82af919e59d5f9ebee2b2dd1424e6953d191eefcac87ca54` |
| `beto.glb` | 146.180 B | `903e7a794d9a6a1757cb84549d335d35be126657bb9f030f92362b7a68532ce5` |
| `zeto.glb` | 150.052 B | `ef156b6c76bfb6fe131b77fbac903cc88ec5dd6d7823b3ae53a40196187c641a` |
| `neto.glb` | 178.612 B | `f5290a1ac702092d2c08a9a4ff957866fd350a10829ed1f6cfb4708212d214ce` |
| `geto.glb` | 116.424 B | `2f3b62622c4a23de08692e2d644c5dbcc2e1966241ed7303835a977726a85444` |
| `leto.glb` | 140.460 B | `b98141b8e1545a7524738b9b53a4c2d6a79016ecddabcbe4ba8e34ba67e48aef` |
| `ceto.glb` | 125.812 B | `d0f4d89f07c50e9f93c73044e9024115fbab8959c1cafe14f8d24c11aa0aeb79` |
| `seto.glb` | 172.772 B | `b0e9c3ef97e8d4a64751425c49be42e631486dc29ed7535ded38413b4f0f14ef` |
| `deto.glb` | 167.204 B | `d26af4c2acfceafbf2e8d301df7394e1f5ee6a9bf4c5782f7a8f6a32290bfe5f` |
| `meto.glb` | 151.220 B | `41b66682460863ab201d46f7ef60250532e16adb74dbe5e337143327a041e0ec` |

## Struktur akhir di repo neugi.com

```
office/
  index.html
  room-showcase.js
  avatar-voxel.js
  room-viewmodel.js
  snapshot.json          <- diganti berkala oleh generator Oto
  ASSETS.md
  README.md
  vendor/three/three.module.js
  vendor/three/GLTFLoader.js
  vendor/three/DRACOLoader.js
  vendor/draco/          <- draco_decoder.js + .wasm + draco_wasm_wrapper.js
  models/                <- 11 GLB di atas
```

Path impor di `room-showcase.js` (relatif, jangan diubah):
`./vendor/three/three.module.js`, `./vendor/three/GLTFLoader.js`,
`./vendor/three/DRACOLoader.js`, `./room-viewmodel.js`,
`./avatar-voxel.js`, `./vendor/draco/` (decoder), `./models/<nama>.glb`, `snapshot.json`
(same origin). TIDAK ADA request ke mana pun selain file-file di
folder ini.
