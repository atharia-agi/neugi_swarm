/* avatar-voxel.js — avatar voxel SVG (10 agen) untuk showcase neugi.com.
   Diekstrak dari blok <script> inline di index.html (AVATAR-VOXEL,
   Virtual Office Milestone 1): data + fungsi murni, tanpa DOM, tanpa
   fetch, tanpa token. Dipindah ke modul sendiri supaya viewer yang
   di-mount dari halaman lain (kantor.html) tetap punya avatar —
   room-showcase.js mengimpor file ini (relatif terhadap modul).
   Satu-satunya global yang diekspos: window.avatarVoxel. */

function esc(s) {
  return String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

/* AVATAR-VOXEL-START — Virtual Office Milestone 1 (Tugas 1 spek):
   part spec 8 avatar + renderer kubus isometrik SVG. Blok ini hanya
   data + fungsi murni (tanpa DOM, tanpa fetch, tanpa penyimpanan
   token di browser); ruangan (Tugas 2) dan wiring toggle (Tugas 5)
   milestone berikut. Satu balok = kubus isometrik 3 sisi (atas,
   kiri, kanan) dengan shading datar; urutan gambar painter's
   algorithm (belakang ke depan, kunci x0+y0+z0). Koordinat dalam
   unit balok: x kanan, y dalam, z atas, lantai z=0. Proyeksi:
   layarX = ox + (x-y)*hw, layarY = oy + (x+y)*hh - z*vh. */
const VOXEL_VIEW = { "w": 160, "h": 172, "ox": 80, "oy": 150, "hw": 8, "hh": 4, "vh": 8 };
  /* Worker C (0.4.9): Seto + Deto belum ada di AVATAR_PARTS BASE
     (0.4.8.4) sehingga fungsi voxel mengembalikan '' dan strip
     portrait mereka kosong. Warna identitas dari KNOWN_AGENTS di
     room-viewmodel.js (seto #ff7f50, deto #64748b — serigala
     biru-abu, ditandai telinga serigala di detail Deto). */
const AVATAR_PARTS = {
  "rangga": {
    "label": "Rangga", "role": "Owner", "color": "#a3ff00",
    "parts": [
      { "id": "head", "box": [-2.5, -2.25, 8, 2.5, 2.25, 12.5], "color": "#f2c89b", "pivot": "neck" },
      { "id": "torso", "box": [-2, -1.25, 4, 2, 1.25, 8], "color": "#16181c", "pivot": "waist" },
      { "id": "armL", "box": [-3.4, -0.7, 4.5, -2, 0.7, 7.5], "color": "#16181c", "pivot": "shoulderL" },
      { "id": "armR", "box": [2, -0.7, 4.5, 3.4, 0.7, 7.5], "color": "#16181c", "pivot": "shoulderR" },
      { "id": "legL", "box": [-1.8, -0.8, 1, -0.2, 0.8, 4], "color": "#2a2e35", "pivot": "hipL" },
      { "id": "legR", "box": [0.2, -0.8, 1, 1.8, 0.8, 4], "color": "#2a2e35", "pivot": "hipR" },
      { "id": "shoeL", "box": [-2, -1.5, 0, 0, 1.5, 1], "color": "#111111", "pivot": "ankleL" },
      { "id": "shoeR", "box": [0, -1.5, 0, 2, 1.5, 1], "color": "#111111", "pivot": "ankleR" }
    ],
    "details": [
      { "id": "handL", "box": [-3.4, -0.7, 3.5, -2, 0.7, 4.5], "color": "#f2c89b" },
      { "id": "handR", "box": [2, -0.7, 3.5, 3.4, 0.7, 4.5], "color": "#f2c89b" },
      { "id": "glassesR", "box": [2.5, -1.8, 11.0, 2.68, 2.25, 11.8], "color": "#111111" },
      { "id": "glassesL", "box": [-1.8, 2.25, 11.0, 2.25, 2.43, 11.8], "color": "#111111" },
      { "id": "mustache", "box": [1.9, 1.9, 9.7, 2.68, 2.43, 10.2], "color": "#3a2a1a" },
      { "id": "hair", "box": [-2.5, -2.25, 12.5, 2.5, 2.25, 13.3], "color": "#141414" },
      { "id": "hairSpike1", "box": [-2.0, -1.5, 13.3, -0.5, 0.5, 14.2], "color": "#141414" },
      { "id": "hairSpike2", "box": [0.5, -1.0, 13.3, 2.0, 1.0, 14.0], "color": "#141414" },
      { "id": "zipper", "box": [1.8, 1.25, 4.2, 2.18, 1.43, 7.8], "color": "#a3ff00" }
    ]
  },
  "oto": {
    "label": "Oto", "role": "CEO", "color": "#a3ff00",
    "parts": [
      { "id": "head", "box": [-2.5, -2.25, 8, 2.5, 2.25, 12.5], "color": "#f5f5f0", "pivot": "neck" },
      { "id": "torso", "box": [-2, -1.25, 4, 2, 1.25, 8], "color": "#a3ff00", "pivot": "waist" },
      { "id": "armL", "box": [-3.4, -0.7, 3.5, -2, 0.7, 7.5], "color": "#a3ff00", "pivot": "shoulderL" },
      { "id": "armR", "box": [2, -0.7, 3.5, 3.4, 0.7, 7.5], "color": "#a3ff00", "pivot": "shoulderR" },
      { "id": "legL", "box": [-1.8, -0.8, 1, -0.2, 0.8, 4], "color": "#a3ff00", "pivot": "hipL" },
      { "id": "legR", "box": [0.2, -0.8, 1, 1.8, 0.8, 4], "color": "#a3ff00", "pivot": "hipR" },
      { "id": "shoeL", "box": [-2, -1.5, 0, 0, 1.5, 1], "color": "#1a1a1a", "pivot": "ankleL" },
      { "id": "shoeR", "box": [0, -1.5, 0, 2, 1.5, 1], "color": "#1a1a1a", "pivot": "ankleR" }
    ],
    "details": [
      { "id": "eyeR", "box": [2.5, 0.9, 10.9, 2.68, 1.7, 11.7], "color": "#111111" },
      { "id": "eyeL", "box": [0.9, 2.25, 10.9, 1.7, 2.43, 11.7], "color": "#111111" },
      { "id": "mouth", "box": [1.9, 1.9, 9.7, 2.68, 2.43, 10.2], "color": "#111111" }
    ]
  },
  "beto": {
    "label": "Beto", "role": "CTO", "color": "#fc7a24",
    "parts": [
      { "id": "head", "box": [-2.5, -2.25, 8, 2.5, 2.25, 12.5], "color": "#f8dcb1", "pivot": "neck" },
      { "id": "torso", "box": [-2, -1.25, 4, 2, 1.25, 8], "color": "#f8dcb1", "pivot": "waist" },
      { "id": "armL", "box": [-3.4, -0.7, 4.5, -2, 0.7, 7.5], "color": "#1a1a1a", "pivot": "shoulderL" },
      { "id": "armR", "box": [2, -0.7, 4.5, 3.4, 0.7, 7.5], "color": "#1a1a1a", "pivot": "shoulderR" },
      { "id": "legL", "box": [-1.8, -0.8, 1, -0.2, 0.8, 4], "color": "#1a1a1a", "pivot": "hipL" },
      { "id": "legR", "box": [0.2, -0.8, 1, 1.8, 0.8, 4], "color": "#1a1a1a", "pivot": "hipR" },
      { "id": "shoeL", "box": [-2, -1.5, 0, 0, 1.5, 1], "color": "#111111", "pivot": "ankleL" },
      { "id": "shoeR", "box": [0, -1.5, 0, 2, 1.5, 1], "color": "#111111", "pivot": "ankleR" }
    ],
    "details": [
      { "id": "handL", "box": [-3.4, -0.7, 3.5, -2, 0.7, 4.5], "color": "#14808a" },
      { "id": "handR", "box": [2, -0.7, 3.5, 3.4, 0.7, 4.5], "color": "#14808a" },
      { "id": "eyeR", "box": [2.5, 0.9, 10.3, 2.68, 1.7, 11.1], "color": "#111111" },
      { "id": "eyeL", "box": [0.9, 2.25, 10.3, 1.7, 2.43, 11.1], "color": "#111111" },
      { "id": "mouth", "box": [1.9, 1.9, 9.4, 2.68, 2.43, 9.9], "color": "#111111" },
      { "id": "dome", "box": [-2.5, -2.25, 11.3, 2.5, 2.25, 12.9], "color": "#fc7a24" },
      { "id": "headsetBand", "box": [-2.5, -0.6, 12.9, 2.5, 0.6, 13.5], "color": "#111111" },
      { "id": "cupL", "box": [-2.68, -0.8, 10.8, -2.5, 0.8, 12.0], "color": "#111111" },
      { "id": "cupR", "box": [2.5, -0.8, 10.8, 2.68, 0.8, 12.0], "color": "#111111" },
      { "id": "micBoom", "box": [2.5, 0.6, 10.0, 2.68, 2.43, 10.4], "color": "#111111" },
      { "id": "chestPanel", "box": [1.6, 1.25, 5.2, 2.18, 1.43, 7.4], "color": "#3a3f44" }
    ]
  },
  "zeto": {
    "label": "Zeto", "role": "CSO", "color": "#ca4f40",
    "parts": [
      { "id": "head", "box": [-2.5, -2.25, 8, 2.5, 2.25, 12.5], "color": "#f8ead0", "pivot": "neck" },
      { "id": "torso", "box": [-2, -1.25, 4, 2, 1.25, 8], "color": "#23272e", "pivot": "waist" },
      { "id": "armL", "box": [-3.4, -0.7, 3.5, -2, 0.7, 7.5], "color": "#23272e", "pivot": "shoulderL" },
      { "id": "armR", "box": [2, -0.7, 3.5, 3.4, 0.7, 7.5], "color": "#23272e", "pivot": "shoulderR" },
      { "id": "legL", "box": [-1.8, -0.8, 1, -0.2, 0.8, 4], "color": "#23272e", "pivot": "hipL" },
      { "id": "legR", "box": [0.2, -0.8, 1, 1.8, 0.8, 4], "color": "#23272e", "pivot": "hipR" },
      { "id": "shoeL", "box": [-2, -1.5, 0, 0, 1.5, 1], "color": "#1a1a1a", "pivot": "ankleL" },
      { "id": "shoeR", "box": [0, -1.5, 0, 2, 1.5, 1], "color": "#1a1a1a", "pivot": "ankleR" }
    ],
    "details": [
      { "id": "eyeR", "box": [2.5, 0.9, 10.9, 2.68, 1.7, 11.7], "color": "#111111" },
      { "id": "eyeL", "box": [0.9, 2.25, 10.9, 1.7, 2.43, 11.7], "color": "#111111" },
      { "id": "cap1", "box": [-4, -4, 12.5, 4, 4, 13.2], "color": "#ca4f40" },
      { "id": "cap2", "box": [-3.25, -3.25, 13.2, 3.25, 3.25, 13.9], "color": "#ca4f40" },
      { "id": "cap3", "box": [-2.5, -2.5, 13.9, 2.5, 2.5, 14.6], "color": "#ca4f40" },
      { "id": "cap4", "box": [-1.75, -1.75, 14.6, 1.75, 1.75, 15.3], "color": "#ca4f40" },
      { "id": "cap5", "box": [-1, -1, 15.3, 1, 1, 15.9], "color": "#ca4f40" },
      { "id": "spotR", "box": [4, 0.5, 12.6, 4.18, 1.8, 13.1], "color": "#f2f2f2" },
      { "id": "spotL", "box": [0.5, 4, 12.6, 1.8, 4.18, 13.1], "color": "#f2f2f2" },
      { "id": "headbandR", "box": [2.5, -1.8, 11.8, 2.68, 2.25, 12.5], "color": "#111111" },
      { "id": "headbandL", "box": [-1.8, 2.25, 11.8, 2.25, 2.43, 12.5], "color": "#111111" },
      { "id": "foreheadPlate", "box": [1.7, 1.7, 11.9, 2.68, 2.43, 12.4], "color": "#c0c0c0" },
      { "id": "maskR", "box": [2.5, -1.8, 8.8, 2.68, 2.25, 10.0], "color": "#1a1a1a" },
      { "id": "maskL", "box": [-1.8, 2.25, 8.8, 2.25, 2.43, 10.0], "color": "#1a1a1a" }
    ]
  },
  "neto": {
    "label": "Neto", "role": "CRO", "color": "#0f766e",
    "parts": [
      { "id": "head", "box": [-3, -2.75, 8, 3, 2.75, 13], "color": "#d9a066", "pivot": "neck" },
      { "id": "torso", "box": [-2.2, -1.4, 4, 2.2, 1.4, 8], "color": "#5b6068", "pivot": "waist" },
      { "id": "armL", "box": [-3.6, -0.75, 4.5, -2.2, 0.75, 7.5], "color": "#5b6068", "pivot": "shoulderL" },
      { "id": "armR", "box": [2.2, -0.75, 4.5, 3.6, 0.75, 7.5], "color": "#5b6068", "pivot": "shoulderR" },
      { "id": "legL", "box": [-1.8, -0.8, 1, -0.2, 0.8, 4], "color": "#d9a066", "pivot": "hipL" },
      { "id": "legR", "box": [0.2, -0.8, 1, 1.8, 0.8, 4], "color": "#d9a066", "pivot": "hipR" },
      { "id": "shoeL", "box": [-2, -1.5, 0, 0, 1.5, 1], "color": "#d9a066", "pivot": "ankleL" },
      { "id": "shoeR", "box": [0, -1.5, 0, 2, 1.5, 1], "color": "#d9a066", "pivot": "ankleR" }
    ],
    "details": [
      { "id": "pawL", "box": [-3.6, -0.75, 3.5, -2.2, 0.75, 4.5], "color": "#d9a066" },
      { "id": "pawR", "box": [2.2, -0.75, 3.5, 3.6, 0.75, 4.5], "color": "#d9a066" },
      { "id": "earL", "box": [-2.7, -2.5, 13, -1.5, -1.3, 14.3], "color": "#d9a066" },
      { "id": "earR", "box": [1.5, -2.5, 13, 2.7, -1.3, 14.3], "color": "#d9a066" },
      { "id": "glassesR", "box": [3, -1.8, 11.6, 3.18, 2.75, 12.5], "color": "#111111" },
      { "id": "glassesL", "box": [-1.8, 2.75, 11.6, 2.75, 2.93, 12.5], "color": "#111111" },
      { "id": "eyeR", "box": [3, 0.9, 10.6, 3.18, 1.7, 11.3], "color": "#111111" },
      { "id": "eyeL", "box": [0.9, 2.75, 10.6, 1.7, 2.93, 11.3], "color": "#111111" },
      { "id": "muzzle", "box": [2.2, 2.2, 9.6, 3.9, 3.9, 11.0], "color": "#f3e2c2" },
      { "id": "nose", "box": [3.3, 3.3, 10.3, 4.15, 4.15, 11.0], "color": "#8a5a3b" },
      { "id": "tie", "box": [1.7, 1.4, 4.3, 2.38, 1.58, 7.6], "color": "#0f766e" }
    ]
  },
  "geto": {
    "label": "Geto", "role": "Backup", "color": "#c4b5fd",
    "parts": [
      { "id": "head", "box": [-2.5, -2.25, 8, 2.5, 2.25, 12.5], "color": "#fbe3d0", "pivot": "neck" },
      { "id": "torso", "box": [-2, -1.25, 4, 2, 1.25, 8], "color": "#c4b5fd", "pivot": "waist" },
      { "id": "armL", "box": [-3.4, -0.7, 4.5, -2, 0.7, 7.5], "color": "#c4b5fd", "pivot": "shoulderL" },
      { "id": "armR", "box": [2, -0.7, 4.5, 3.4, 0.7, 7.5], "color": "#c4b5fd", "pivot": "shoulderR" },
      { "id": "legL", "box": [-1.8, -0.8, 1, -0.2, 0.8, 4], "color": "#efe6d0", "pivot": "hipL" },
      { "id": "legR", "box": [0.2, -0.8, 1, 1.8, 0.8, 4], "color": "#efe6d0", "pivot": "hipR" },
      { "id": "shoeL", "box": [-2, -1.5, 0, 0, 1.5, 1], "color": "#f5f5f5", "pivot": "ankleL" },
      { "id": "shoeR", "box": [0, -1.5, 0, 2, 1.5, 1], "color": "#f5f5f5", "pivot": "ankleR" }
    ],
    "details": [
      { "id": "handL", "box": [-3.4, -0.7, 3.5, -2, 0.7, 4.5], "color": "#fbe3d0" },
      { "id": "handR", "box": [2, -0.7, 3.5, 3.4, 0.7, 4.5], "color": "#fbe3d0" },
      { "id": "eyeR", "box": [2.5, 0.7, 10.7, 2.68, 1.9, 11.9], "color": "#7c5cd6" },
      { "id": "eyeL", "box": [0.7, 2.25, 10.7, 1.9, 2.43, 11.9], "color": "#7c5cd6" },
      { "id": "mouth", "box": [1.9, 1.9, 9.7, 2.68, 2.43, 10.2], "color": "#1c1c22" },
      { "id": "hairBlack", "box": [-2.5, -2.25, 12.5, 2.5, 2.25, 13.2], "color": "#1c1c22" },
      { "id": "hairLavender", "box": [0, -2.25, 13.2, 2.5, 2.25, 13.6], "color": "#c4b5fd" },
      { "id": "spikeLavender", "box": [1.2, -1.0, 13.6, 2.3, 0.8, 14.4], "color": "#c4b5fd" },
      { "id": "spikeBlack", "box": [-2.3, -1.2, 13.2, -1.0, 0.6, 14.1], "color": "#1c1c22" },
      { "id": "drawstrings", "box": [1.8, 1.25, 4.4, 2.18, 1.43, 7.2], "color": "#1c1c22" }
    ]
  },
  "leto": {
    "label": "Leto", "role": "Intern", "color": "#f4a7b9",
    "parts": [
      { "id": "head", "box": [-2.5, -2.25, 8, 2.5, 2.25, 12.5], "color": "#fbe0c8", "pivot": "neck" },
      { "id": "torso", "box": [-2, -1.25, 4, 2, 1.25, 8], "color": "#f4a7b9", "pivot": "waist" },
      { "id": "armL", "box": [-3.4, -0.7, 4.5, -2, 0.7, 7.5], "color": "#f4a7b9", "pivot": "shoulderL" },
      { "id": "armR", "box": [2, -0.7, 4.5, 3.4, 0.7, 7.5], "color": "#f4a7b9", "pivot": "shoulderR" },
      { "id": "legL", "box": [-1.8, -0.8, 1, -0.2, 0.8, 4], "color": "#e8dcc4", "pivot": "hipL" },
      { "id": "legR", "box": [0.2, -0.8, 1, 1.8, 0.8, 4], "color": "#e8dcc4", "pivot": "hipR" },
      { "id": "shoeL", "box": [-2, -1.5, 0, 0, 1.5, 1], "color": "#f5f5f5", "pivot": "ankleL" },
      { "id": "shoeR", "box": [0, -1.5, 0, 2, 1.5, 1], "color": "#f5f5f5", "pivot": "ankleR" }
    ],
    "details": [
      { "id": "handL", "box": [-3.4, -0.7, 3.5, -2, 0.7, 4.5], "color": "#fbe0c8" },
      { "id": "handR", "box": [2, -0.7, 3.5, 3.4, 0.7, 4.5], "color": "#fbe0c8" },
      { "id": "eyeR", "box": [2.5, 0.7, 10.7, 2.68, 1.9, 11.9], "color": "#5b3a1e" },
      { "id": "eyeL", "box": [0.7, 2.25, 10.7, 1.9, 2.43, 11.9], "color": "#5b3a1e" },
      { "id": "mouth", "box": [1.9, 1.9, 9.7, 2.68, 2.43, 10.2], "color": "#5b3a1e" },
      { "id": "hair", "box": [-2.5, -2.25, 12.5, 2.5, 2.25, 13.2], "color": "#1a1a1a" },
      { "id": "bun", "box": [-2.6, -3.4, 10.6, -1.2, -2.25, 12.1], "color": "#1a1a1a" },
      { "id": "lanyard", "box": [1.7, 1.25, 5.0, 2.18, 1.43, 7.6], "color": "#2563eb" },
      { "id": "badge", "box": [-0.9, 1.25, 5.8, 0.0, 1.43, 6.9], "color": "#f8fafc" }
    ]
  },
  "ceto": {
    "label": "Ceto", "role": "Sales", "color": "#1e3a8a",
    "parts": [
      { "id": "head", "box": [-2.5, -2.25, 8, 2.5, 2.25, 12.5], "color": "#f6c89f", "pivot": "neck" },
      { "id": "torso", "box": [-2, -1.25, 4, 2, 1.25, 8], "color": "#1e3a8a", "pivot": "waist" },
      { "id": "armL", "box": [-3.4, -0.7, 4.5, -2, 0.7, 7.5], "color": "#1e3a8a", "pivot": "shoulderL" },
      { "id": "armR", "box": [2, -0.7, 4.5, 3.4, 0.7, 7.5], "color": "#1e3a8a", "pivot": "shoulderR" },
      { "id": "legL", "box": [-1.8, -0.8, 1, -0.2, 0.8, 4], "color": "#9aa0a6", "pivot": "hipL" },
      { "id": "legR", "box": [0.2, -0.8, 1, 1.8, 0.8, 4], "color": "#9aa0a6", "pivot": "hipR" },
      { "id": "shoeL", "box": [-2, -1.5, 0, 0, 1.5, 1], "color": "#f5f5f5", "pivot": "ankleL" },
      { "id": "shoeR", "box": [0, -1.5, 0, 2, 1.5, 1], "color": "#f5f5f5", "pivot": "ankleR" }
    ],
    "details": [
      { "id": "handL", "box": [-3.4, -0.7, 3.5, -2, 0.7, 4.5], "color": "#f6c89f" },
      { "id": "handR", "box": [2, -0.7, 3.5, 3.4, 0.7, 4.5], "color": "#f6c89f" },
      { "id": "eyeR", "box": [2.5, 0.9, 10.9, 2.68, 1.7, 11.7], "color": "#111111" },
      { "id": "eyeL", "box": [0.9, 2.25, 10.9, 1.7, 2.43, 11.7], "color": "#111111" },
      { "id": "mouth", "box": [1.9, 1.9, 9.7, 2.68, 2.43, 10.2], "color": "#111111" },
      { "id": "capSlab", "box": [-2.5, -2.25, 12.5, 2.5, 2.25, 13.2], "color": "#1e3a8a" },
      { "id": "capDome", "box": [-2.0, -1.8, 13.2, 2.0, 1.8, 13.7], "color": "#1e3a8a" },
      { "id": "hairR", "box": [2.5, -2.0, 11.0, 2.68, -0.5, 12.5], "color": "#1a1a1a" },
      { "id": "hairL", "box": [-0.5, 2.25, 11.0, 1.0, 2.43, 12.5], "color": "#1a1a1a" },
      { "id": "chain", "box": [1.7, 1.25, 7.4, 2.18, 1.43, 7.9], "color": "#d4af37" }
    ]
  },
  "seto": {
    "label": "Seto", "role": "Dukungan Umum", "color": "#ff7f50",
    "parts": [
      { "id": "head", "box": [-2.5, -2.25, 8, 2.5, 2.25, 12.5], "color": "#f2c89b", "pivot": "neck" },
      { "id": "torso", "box": [-2, -1.25, 4, 2, 1.25, 8], "color": "#ff7f50", "pivot": "waist" },
      { "id": "armL", "box": [-3.4, -0.7, 4.5, -2, 0.7, 7.5], "color": "#ff7f50", "pivot": "shoulderL" },
      { "id": "armR", "box": [2, -0.7, 4.5, 3.4, 0.7, 7.5], "color": "#ff7f50", "pivot": "shoulderR" },
      { "id": "legL", "box": [-1.8, -0.8, 1, -0.2, 0.8, 4], "color": "#2a2e35", "pivot": "hipL" },
      { "id": "legR", "box": [0.2, -0.8, 1, 1.8, 0.8, 4], "color": "#2a2e35", "pivot": "hipR" },
      { "id": "shoeL", "box": [-2, -1.5, 0, 0, 1.5, 1], "color": "#111111", "pivot": "ankleL" },
      { "id": "shoeR", "box": [0, -1.5, 0, 2, 1.5, 1], "color": "#111111", "pivot": "ankleR" }
    ],
    "details": [
      { "id": "handL", "box": [-3.4, -0.7, 3.5, -2, 0.7, 4.5], "color": "#f2c89b" },
      { "id": "handR", "box": [2, -0.7, 3.5, 3.4, 0.7, 4.5], "color": "#f2c89b" },
      { "id": "eyeR", "box": [2.5, 0.9, 10.9, 2.68, 1.7, 11.7], "color": "#111111" },
      { "id": "eyeL", "box": [0.9, 2.25, 10.9, 1.7, 2.43, 11.7], "color": "#111111" },
      { "id": "mouth", "box": [1.9, 1.9, 9.7, 2.68, 2.43, 10.2], "color": "#111111" },
      { "id": "hair", "box": [-2.5, -2.25, 12.5, 2.5, 2.25, 13.2], "color": "#1a1a1a" }
    ]
  },
  "deto": {
    "label": "Deto", "role": "Dukungan Umum", "color": "#64748b",
    "parts": [
      { "id": "head", "box": [-2.5, -2.25, 8, 2.5, 2.25, 12.5], "color": "#f6c89f", "pivot": "neck" },
      { "id": "torso", "box": [-2, -1.25, 4, 2, 1.25, 8], "color": "#64748b", "pivot": "waist" },
      { "id": "armL", "box": [-3.4, -0.7, 4.5, -2, 0.7, 7.5], "color": "#64748b", "pivot": "shoulderL" },
      { "id": "armR", "box": [2, -0.7, 4.5, 3.4, 0.7, 7.5], "color": "#64748b", "pivot": "shoulderR" },
      { "id": "legL", "box": [-1.8, -0.8, 1, -0.2, 0.8, 4], "color": "#9aa0a6", "pivot": "hipL" },
      { "id": "legR", "box": [0.2, -0.8, 1, 1.8, 0.8, 4], "color": "#9aa0a6", "pivot": "hipR" },
      { "id": "shoeL", "box": [-2, -1.5, 0, 0, 1.5, 1], "color": "#f5f5f5", "pivot": "ankleL" },
      { "id": "shoeR", "box": [0, -1.5, 0, 2, 1.5, 1], "color": "#f5f5f5", "pivot": "ankleR" }
    ],
    "details": [
      { "id": "handL", "box": [-3.4, -0.7, 3.5, -2, 0.7, 4.5], "color": "#f6c89f" },
      { "id": "handR", "box": [2, -0.7, 3.5, 3.4, 0.7, 4.5], "color": "#f6c89f" },
      { "id": "eyeR", "box": [2.5, 0.9, 10.9, 2.68, 1.7, 11.7], "color": "#111111" },
      { "id": "eyeL", "box": [0.9, 2.25, 10.9, 1.7, 2.43, 11.7], "color": "#111111" },
      { "id": "mouth", "box": [1.9, 1.9, 9.7, 2.68, 2.43, 10.2], "color": "#111111" },
      { "id": "earL", "box": [-2.3, -0.6, 12.5, -1.2, 0.6, 13.6], "color": "#475569" },
      { "id": "earR", "box": [1.2, -0.6, 12.5, 2.3, 0.6, 13.6], "color": "#475569" }
    ]
  }
};

function shadeHex(hex, f) {
  const n = parseInt(hex.slice(1), 16);
  const r = Math.min(255, Math.round(((n >> 16) & 255) * f));
  const g = Math.min(255, Math.round(((n >> 8) & 255) * f));
  const b = Math.min(255, Math.round((n & 255) * f));
  return '#' + [r, g, b].map(v => v.toString(16).padStart(2, '0')).join('');
}

function isoPoint(x, y, z) {
  return [VOXEL_VIEW.ox + (x - y) * VOXEL_VIEW.hw,
          VOXEL_VIEW.oy + (x + y) * VOXEL_VIEW.hh - z * VOXEL_VIEW.vh];
}

function boxPolys(box) {
  const [x0, y0, z0, x1, y1, z1] = box;
  const P = (x, y, z) => isoPoint(x, y, z);
  return {
    top: [P(x0, y0, z1), P(x1, y0, z1), P(x1, y1, z1), P(x0, y1, z1)],
    left: [P(x0, y1, z0), P(x1, y1, z0), P(x1, y1, z1), P(x0, y1, z1)],
    right: [P(x1, y0, z0), P(x1, y1, z0), P(x1, y1, z1), P(x1, y0, z1)]
  };
}

function polyPoints(pts) {
  return pts.map(p => p[0].toFixed(1) + ',' + p[1].toFixed(1)).join(' ');
}

function avatarVoxel(name) {
  const spec = AVATAR_PARTS[name];
  if (!spec) return '';
  const boxes = spec.parts.concat(spec.details);
  boxes.sort((a, b) => (a.box[0] + a.box[1] + a.box[2]) - (b.box[0] + b.box[1] + b.box[2])
    || a.box[2] - b.box[2] || a.box[0] - b.box[0]);
  let inner = '';
  for (const p of boxes) {
    const f = boxPolys(p.box);
    inner += `<polygon class="vox-top" points="${polyPoints(f.top)}" fill="${p.color}"/>`
      + `<polygon class="vox-left" points="${polyPoints(f.left)}" fill="${shadeHex(p.color, 0.78)}"/>`
      + `<polygon class="vox-right" points="${polyPoints(f.right)}" fill="${shadeHex(p.color, 0.6)}"/>`;
  }
  return `<svg class="avatar-voxel" viewBox="0 0 ${VOXEL_VIEW.w} ${VOXEL_VIEW.h}" width="80" height="86" role="img" aria-label="Avatar ${esc(spec.label)} (${esc(spec.role)})"><g class="avatar" data-agent="${esc(name)}">${inner}</g></svg>`;
}
/* AVATAR-VOXEL-END */

/* Diekspos sebagai global karena room-showcase.js (BASE 0.4.9.1) memanggil
   window.avatarVoxel; modul ini juga mengekspornya untuk pemakaian langsung. */
window.avatarVoxel = avatarVoxel;
export { avatarVoxel };
