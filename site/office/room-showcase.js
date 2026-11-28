/* ROOM-SHOWCASE-START — Showcase publik kantor 3D (neugi.com).
   Varian read-only dari room3d.js 0.4.9 — HANYA file ini yang
   diubah; room3d.js produksi tidak disentuh. Three.js minimal
   (core + GLTFLoader + DRACOLoader) DIVENDOR ke repo, tanpa CDN,
   tanpa build step, tanpa import map. Render-on-demand: canvas
   HANYA render saat ada perubahan state / transisi / interaksi;
   saat diam tidak ada frame baru (preserveDrawingBuffer: true).
   Request jaringan viewer ini: snapshot.json (same origin,
   polling 60 detik) + infra-status.json (R2 publik, polling
   5 menit, layar monitor infra di lobi — read-only, tanpa
   kredensial). TIDAK ADA fetch ke layanan lain, TIDAK ADA URL
   absolut ke layanan lain di mana pun (kode, data, komentar).
   TANPA login, TANPA composer, TANPA posting,
   TANPA klik-untuk-chat: klik avatar = kartu info saja di hero,
   dan kamera follow third-person di mode fullscreen. Semua teks
   dari snapshot dimasukkan ke DOM lewat textContent dan ke canvas
   lewat fillText — bukan innerHTML (kecuali avatarVoxel yang
   membangun dari data tetap + esc). Canvas WebGL dibuat dulu, tapi
   baru ditempel ke DOM setelah render pertama (GLB selesai dimuat
   / fallback). Hero = mini display auto-rotate pelan; klik hero =
   fullscreen overlay dengan room penuh + orbit/zoom + follow. */

import * as THREE from './vendor/three/three.module.js';
import { GLTFLoader } from './vendor/three/GLTFLoader.js';
import { DRACOLoader } from './vendor/three/DRACOLoader.js';
import {
  KNOWN_AGENTS, ROOM_ORDER, ROOMS, FLOOR, GANG_Z, GLYPH_DEFS,
  planWalk, assignSlots, trunc, hhmm,
} from './room-viewmodel.js';
/* SHOWCASE: avatar voxel (dulu blok <script> inline di index.html)
   dipindah ke avatar-voxel.js dan diimpor di sini — supaya viewer yang
   di-mount dari halaman lain (kantor.html, tanpa index.html) tetap
   punya avatar di strip portrait, kartu agen, dan chip follow. Tanpa
   impor ini window.avatarVoxel undefined di host page dan semua
   portrait tampil kosong (temuan saat verifikasi mount API). Impor
   relatif terhadap modul, jadi jalan dari host page mana pun. */
import './avatar-voxel.js';
/* Namespace import: fungsi baru Worker A (selectVisibleBubbles,
   activeAgentName) dipakai BILA sudah diekspor view-model; bila
   belum (BASE 0.4.8.4), fallback lokal di bawah yang mengimplementasi
   spek kontrak yang sama persis dipakai — perilaku identik, dan
   koordinator boleh menghapus fallback saat integrasi. Named import
   langsung akan gagal load bila nama belum diekspor, jadi cara ini
   yang aman. */
import * as VM from './room-viewmodel.js';

const VERSION = '0.4.9.1-showcase';
const VOLT = 0xa3ff00;
const VOLT_CSS = '#a3ff00';
const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/* Palet kantor TERANG + volt (§5.1). Tanpa gradien ungu/biru.
   BRIGHTEN 21 Nov 2026 (perintah Rangga: "officenya gelap, ganti
   warna bangunan jadi lebih cerah"): lantai kayu terang hangat,
   dinding pucat hangat, furnitur kayu terang + kain sage redup.
   Satu aksen kuat tetap volt #A3FF00. */
const C = {
  floor: 0xcfa878, gang: 0xe6dcc8, grid: 0xa08b6d,
  wall: 0xf3eee2, wallDark: 0xddd3bf, divider: 0xd9cfb9,
  desk: 0x9c7c55, deskTop: 0xc99f66, chair: 0x7a8b7d,
  carpet: 0xcbb693, carpetEdge: 0xa68f6c,
  panel: 0xefe8d6, panelEdge: 0x9a8a6f,
  sofa: 0x7a8b7d, plant: 0x22c55e, plantDark: 0x16a34a,
  pot: 0x6b4a2f, bench: 0xa07d52, lamp: 0xffd97a,
  shadow: 0x000000,
};

/* Material dishare (props primitif saja: Box/Cylinder/Sphere,
   flat shading, tanpa tekstur, tanpa shadow map). */
const MAT = {};
function mat(name, color, opts = {}) {
  const key = name + ':' + color + ':' + JSON.stringify(opts);
  if (!MAT[key]) MAT[key] = new THREE.MeshLambertMaterial({ color, ...opts });
  return MAT[key];
}
function box(w, h, d, color, opts) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat('box', color, opts));
  return m;
}
function cyl(rt, rb, h, color, opts, seg = 12) {
  return new THREE.Mesh(new THREE.CylinderGeometry(rt, rb, h, seg), mat('cyl', color, opts));
}
function sph(r, color, opts) {
  return new THREE.Mesh(new THREE.SphereGeometry(r, 12, 10), mat('sph', color, opts));
}
function place(obj, x, y, z, ry = 0) {
  obj.position.set(x, y, z);
  if (ry) obj.rotation.y = ry;
  return obj;
}

/* --- tekstur canvas (teks dibuat dari kode, 0 KB aset) -------- */
function textTexture(w, h, draw) {
  const canvas = document.createElement('canvas');
  canvas.width = w; canvas.height = h;
  const ctx = canvas.getContext('2d');
  draw(ctx, w, h);
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  return { canvas, ctx, tex };
}
function panelPlane(w, h, texObj) {
  const m = new THREE.Mesh(
    new THREE.PlaneGeometry(w, h),
    new THREE.MeshBasicMaterial({ map: texObj.tex }));
  m.userData.texObj = texObj;
  return m;
}

/* --- tekstur mozaik ground luar (rumput + concrete) --------------- */
/* Palet ground luar (27 Nov 2026, perintah Rangga 22:38): rumput
   mozaik campur tanah concrete, kontras sama lantai office (kayu
   hangat 0xcfa878 + krem). Satu canvas 512x512 = 8x8 petak; dipakai
   ulang di halaman, lapangan rumput, trotoar samping + utara/
   selatan, dan tanah dasar kota — masing-masing clone dengan
   repeat = ukuran meter / 16 supaya tiap petak = 2 m. Parkir
   (concrete 0x4a4e54) dan jalan TIDAK diubah.
   PERBAIKAN 28 Nov 2026 (Rangga: "mozaik ga pernah keliatan"):
   mozaik lama TIDAK hilang dari kode (tekstur terpasang di 5 bidang)
   tapi tidak kebaca mata — petak 1 m (~6 px di HP overview) +
   nat 2 px (3 cm, sub-pixel) + jarak luminansi rumput-concrete
   cuma ~23 (skala 0-255) + cahaya scene sangat terang + mipmap
   meratakan pola dari jauh = rata jadi abu-hijau datar. Perbaikan:
   petak 2 m (~12 px), nat 6 px (19 cm, warna gelap), hijau lebih
   gelap + concrete lebih terang (jarak luminansi ~96, 4x lipat). */
const MOSAIC_GRASS = [0x2e5c26, 0x3f7031, 0x4a7d3a, 0x5c8f45];
const MOSAIC_CONCRETE = [0xc8c8c0, 0xb8b8b0, 0xd8d8d0];
let mosaicBaseTex = null;
function mosaicGroundTex() {
  if (mosaicBaseTex) return mosaicBaseTex;
  const rnd = seededRand(20261127);
  const t = textTexture(512, 512, (g2) => {
    const S = 64; /* 512 / 8 petak */
    for (let ty = 0; ty < 8; ty++) {
      for (let tx = 0; tx < 8; tx++) {
        const grass = rnd() < 0.55;
        const pal = grass ? MOSAIC_GRASS : MOSAIC_CONCRETE;
        const col = pal[Math.floor(rnd() * pal.length)];
        g2.fillStyle = '#' + col.toString(16).padStart(6, '0');
        g2.fillRect(tx * S, ty * S, S, S);
        /* Variasi terang-gelap per petak (nuansa buatan tangan). */
        g2.fillStyle = rnd() < 0.5 ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.12)';
        g2.fillRect(tx * S, ty * S, S, S);
      }
    }
    /* Nat antar petak (mozaik kebaca) — 6 px, gelap, supaya batas
       petak kebaca dari jauh (yang 2 px dulu sub-pixel). */
    g2.strokeStyle = '#2f3a2c';
    g2.lineWidth = 6;
    for (let i = 0; i <= 8; i++) {
      g2.beginPath(); g2.moveTo(i * S, 0); g2.lineTo(i * S, 512); g2.stroke();
      g2.beginPath(); g2.moveTo(0, i * S); g2.lineTo(512, i * S); g2.stroke();
    }
  });
  t.tex.wrapS = THREE.RepeatWrapping;
  t.tex.wrapT = THREE.RepeatWrapping;
  mosaicBaseTex = t.tex;
  return mosaicBaseTex;
}
function mosaicMat(w, h) {
  /* Clone tekstur dasar (berbagi canvas) + repeat supaya tiap
     petak = 2 m di dunia nyata (28 Nov 2026: 1 m terlalu kecil,
     pola hilang di overview/HP — lihat komentar palet di atas). */
  const t = mosaicGroundTex().clone();
  t.needsUpdate = true;
  t.repeat.set(w / 16, h / 16);
  return new THREE.MeshLambertMaterial({ map: t });
}

/* --- state ----------------------------------------------------- */
/* Showcase: elemen di-bind ULANG oleh mount() — di office/index.html
   struktur sudah ada saat modul dimuat; di host page (kantor.html)
   struktur baru dibuat oleh mount() sebelum init(). */
let wrap = document.getElementById('roomCanvas');
let bubbleLayer = document.getElementById('roomBubbles');
let statusEl = document.getElementById('roomStatus');
function bindShowcaseEls() {
  wrap = document.getElementById('roomCanvas') || wrap;
  bubbleLayer = document.getElementById('roomBubbles') || bubbleLayer;
  statusEl = document.getElementById('roomStatus') || statusEl;
}

let renderer = null;
let scene = null;
let camera = null;       /* kamera AKTIF (overview ortho / follow perspektif) */
let orthoCam = null;     /* overview */
let perspCam = null;     /* follow TPS */
let keyLight = null;     /* AAA L1: directional hangat (key) — dipakai L3 untuk shadow */
let azimuth = Math.PI / 4; /* kamera isometrik default (tenggara) */
let camZoom = 1;
let camElev = 0.62; /* elevasi overview (rad) — drag vertikal, clamp [0.25, 1.25] (Tugas 5) */
let camPan = { x: 0, z: 0 }; /* geser target overview (2 jari / Shift+drag), dijepit ke bounds denah via clampCamPan (FREE CAM 2026-11-27: batas = jalan raya) */
let heroLastInteract = 0; /* ms interaksi user terakhir di hero — jeda auto-rotate 5 dtk (Tugas 5) */
let webglOK = false;
/* Kamera Sims 4: mode 'overview' | 'follow'. Follow = perspektif
   TPS di belakang/di atas bahu agen + mengikuti saat jalan. */
let cameraMode = 'overview';
let followName = null;
let followYaw = 0;       /* offset yaw dari arah hadap agen */
let followPitch = 0.32;  /* elevasi kamera follow (rad) */
let followDist = 4.0;    /* jarak kamera follow (0.4.9: 3.2 -> 4.0 —
  avatar chibi berambut besar: di 3.2 rambut memenuhi ~40% frame;
  di 4.0 + anchor torso, seluruh badan masuk frame) */
let followPan = { x: 0, z: 0 }; /* geser anchor (Sims-style pan) */
let followCardEl = null; /* kartu info agen saat follow */
let state = null;          /* RoomState terakhir */
let prevState = null;
let displayMode = 'hero';  /* 'hero' | 'fullscreen' — tampilan showcase */
let snapLoaded = false;    /* snapshot.json sudah berhasil dimuat */
let snapGeneratedMs = 0;   /* generated_at snapshot terakhir (ms) */
let snapSource = 'R2';
let infraData = null;      /* infra-status.json terakhir (layar lobi) */
let infraLoaded = false;   /* infra-status.json sudah berhasil dimuat */
let infraGeneratedMs = 0;  /* updated_at infra terakhir (ms) */
let infraFailed = false;   /* fetch terakhir gagal & belum ada data */
let infraFlashUntil = 0;   /* performance.now() akhir kilau refresh */
let infraScreen = null;    /* {texObj, lastDrawMs} — layar lobi */
let infraPollTimer = null;     /* sumber snapshot terakhir: 'R2' | 'lokal' */
let fsFallback = false;    /* fullscreen API tak tersedia -> overlay CSS */
let fsSeq = 0;             /* naik tiap enter/exit/follow fullscreen (penjaga race Esc) */
let fsExitSeq = -1;        /* fsSeq saat exit dimulai (-1 = tak ada exit) */
let fsExiting = false;     /* exit fullscreen sedang berjalan (async) */
const MODULE_BASE = new URL('.', import.meta.url).href;
/* Basis aset relatif terhadap MODUL (bukan dokumen): model GLB,
   decoder Draco, dan snapshot default dimuat dari folder tempat
   room-showcase.js berada — jadi mount() dari halaman lain
   (kantor.html di root) tetap menemukan asetnya. */
let pollTimer = null;
let lastFetchMs = 0;
let seenSpeech = new Set();
let seenFileFlash = null;
let seenCompleted = new Set();
let workPhase = 0;
let workTimer = null;
let clockTimer = null;
const avatarGroups = {};   /* name -> THREE.Group (mesh + bayangan) */
const avatarMeshes = {};   /* name -> inner mesh (buat tilt/kerja) */
const avatarPos = {};      /* name -> {x, z} posisi kaki saat ini */
const avatarRoom = {};     /* name -> room id saat ini */
const walks = {};          /* name -> {token, raf} */
let anyWalking = false;
let currentActiveAgent = null;
let lastBubblesShown = 0;
const dynamicPanels = {};  /* key -> {texObj, redraw} */
let mentionGroup = null;
let handoverGroup = null;
const clickables = [];     /* mesh dg userData.agent / userData.action / userData.deskSlot */
const raycaster = new THREE.Raycaster();
const pointerNDC = new THREE.Vector2();

/* --- pose rigged (0.4.9, Upgrade 11/10 → 100/10) ------------------ */
/* CHIBI BATCH 2026-11-25 (Hunyuan3D-2.0, Draco+WebP, 13 avatar):
   JOINT_ROLES dari joint_map_<nama>.json (cari joint dari ROLE,
   jangan hardcode nomor bone di luar tabel ini). Jumlah joints
   variabel per avatar (22/28/34/46) — viewer resolve by role.
   Sumber: output/chibi/<nama>/joint_map_<nama>.json (oto v3,
   beto v3) + joint_map_chibi.json (rangga pilot).
   Joints: rangga 34, oto 46, beto 28, geto 22, ceto 34, leto 34,
   seto 22, deto 22, zeto 28, neto 28, meto 22, reto 34,
   atharia 28. Deploy ini sekaligus memperbaiki ketukaran live
   ceto/leto (file chibi Ceto pink + Leto lavender sudah benar).
   Ekor Seto/Deto tidak punya tulang → tidak ada animasi ekor.
   L/R = kiri/kanan karakter sendiri. */
const JOINT_ROLES = {
  /* RANGGA pilot chibi (Hunyuan3D-2.0, 2026-11-25, QC lolos):
     34 joints, pola SAMA seperti v6 (shoulderR 16, thigh 26/30,
     jari 10-15 / 20-25). Delta lengan terukur (IDLE_ARM_DELTAS)
     keyed by ROLE, jadi tetap berlaku — applyIdlePose resolve
     indeks lewat tabel ini. */
  rangga: { shoulderL: 6, shoulderR: 16, thighL: 26, thighR: 30, shinL: 27, shinR: 31, spine: 2, neck: 4, head: 5, forearmL: 8, forearmR: 18, handL: 9, handR: 19, fingerL: [10, 11, 12, 13, 14, 15], fingerR: [20, 21, 22, 23, 24, 25] },
  zeto: { shoulderL: 6, shoulderR: 13, thighL: 20, thighR: 24, shinL: 21, shinR: 25, spine: 2, neck: 4, head: 5, forearmL: 8, forearmR: 15, handL: 9, handR: 16, fingerL: null, fingerR: null },
  neto: { shoulderL: 6, shoulderR: 13, thighL: 20, thighR: 24, shinL: 21, shinR: 25, spine: 2, neck: 4, head: 5, forearmL: 8, forearmR: 15, handL: 9, handR: 16, fingerL: null, fingerR: null },
  leto: { shoulderL: 6, shoulderR: 16, thighL: 26, thighR: 30, shinL: 27, shinR: 31, spine: 2, neck: 4, head: 5, forearmL: 8, forearmR: 18, handL: 9, handR: 19, fingerL: [10, 11, 12, 13, 14, 15], fingerR: [20, 21, 22, 23, 24, 25] },
  ceto: { shoulderL: 6, shoulderR: 16, thighL: 26, thighR: 30, shinL: 27, shinR: 31, spine: 2, neck: 4, head: 5, forearmL: 8, forearmR: 18, handL: 9, handR: 19, fingerL: [10, 11, 12, 13, 14, 15], fingerR: [20, 21, 22, 23, 24, 25] },
  beto: { shoulderL: 6, shoulderR: 13, thighL: 20, thighR: 24, shinL: 21, shinR: 25, spine: 2, neck: 4, head: 5, forearmL: 8, forearmR: 15, handL: 9, handR: 16, fingerL: null, fingerR: null },
  oto: { shoulderL: 6, shoulderR: 22, thighL: 38, thighR: 42, shinL: 39, shinR: 43, spine: 2, neck: 4, head: 5, forearmL: 8, forearmR: 24, handL: 9, handR: 25, fingerL: [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21], fingerR: [26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37] },
  geto: { shoulderL: 6, shoulderR: 10, thighL: 14, thighR: 18, shinL: 15, shinR: 19, spine: 2, neck: 4, head: 5, forearmL: 8, forearmR: 12, handL: 9, handR: 13, fingerL: null, fingerR: null },
  seto: { shoulderL: 6, shoulderR: 10, thighL: 14, thighR: 18, shinL: 15, shinR: 19, spine: 2, neck: 4, head: 5, forearmL: 8, forearmR: 12, handL: 9, handR: 13, fingerL: null, fingerR: null },
  deto: { shoulderL: 6, shoulderR: 10, thighL: 14, thighR: 18, shinL: 15, shinR: 19, spine: 2, neck: 4, head: 5, forearmL: 8, forearmR: 12, handL: 9, handR: 13, fingerL: null, fingerR: null },
  /* FEET FIX 2026-11-21 — Meto (22 joint, pola Geto: thigh 14/18,
     shin 15/19). Tanpa entri ini Meto tidak dapat pose duduk
     (captureBoneBase lewati), jadi kakinya tidak pernah terukur
     saat duduk. */
  meto: { shoulderL: 6, shoulderR: 10, thighL: 14, thighR: 18, shinL: 15, shinR: 19, spine: 2, neck: 4, head: 5, forearmL: 8, forearmR: 12, handL: 9, handR: 13, fingerL: null, fingerR: null },
  /* ATHARIA + RETO — delta lengan kini TERUKUR (batch chibi
     2026-11-25, measure_<nama>.json), bukan lagi fallback Z +-75. */
  atharia: { shoulderL: 6, shoulderR: 13, thighL: 20, thighR: 24, shinL: 21, shinR: 25, spine: 2, neck: 4, head: 5, forearmL: 8, forearmR: 15, handL: 9, handR: 16, fingerL: null, fingerR: null },
  reto: { shoulderL: 6, shoulderR: 16, thighL: 26, thighR: 30, shinL: 27, shinR: 31, spine: 2, neck: 4, head: 5, forearmL: 8, forearmR: 18, handL: 9, handR: 19, fingerL: [10, 11, 12, 13, 14, 15], fingerR: [20, 21, 22, 23, 24, 25] },
};
/* DUDUK LESEHAN 2026-11-21 (Item 2+3) — grup turun sebesar drop saat
   duduk supaya PANAT menyentuh permukaan pad (PAD_TOP 0.10).
   ROOT CAUSE drop lama SALAH UKUR: drop lama = minY bbox KESELURUHAN
   saat duduk — untuk Rangga/Oto itu ujung TANGAN/JARI yang menjuntai
   (0.255 / 0.077), bukan kaki/pantat. Akibatnya pinggul Rangga di
   0.49-0.255 = 0.24 — 0.26 DI BAWAH dudukan kursi 0.50 — avatar
   tenggelam menembus kursi (sandaran di depan wajah, dudukan
   memotong dada; lihat README work-B-sitting). Drop baru DIUKUR
   per avatar di harness (pose duduk baru: paha sumbu-X dunia -90,
   betis lokal +170, grup di y=0): seatUnder = titik terendah massa
   duduk di dekat pinggul (vertex dominan bone pelvis 0 / paha,
   dalam 0.18 dari sendi pinggul — jendela ini membuang ekor
   Deto/Seto + perut Neto dari ukur); drop = seatUnder - PAD_TOP,
   dijepit [0, 0.35]. Nilai 0.000 (zeto/neto/deto) = seatUnder sudah
   di/bawah PAD_TOP saat grup y=0 (kaki pendek + badan rendah) —
   grup tidak dinaikkan; pantat/badan rendah mereka menekan pad
   (zabuton) alih-alih melayang. Puncak kepala duduk 1.31–1.60
   (di atas monitor 0.98), lutut ke depan (+0.07..+0.27),
   ujung kaki terlipat di belakang lutut 0.05-0.24 di atas lantai. */
const SIT_DROPS = {
  rangga: 0.207, oto: 0.188, beto: 0.273, zeto: 0.136, neto: 0.181,
  geto: 0.205, leto: 0.294, ceto: 0.281, deto: 0.155, seto: 0.175, meto: 0.260,
  atharia: 0.350, reto: 0.350, /* 0.350 = ter-clamp di maks formula
    (seatUnder reto 0.459 / atharia 0.491) — verifikasi visual saat duduk */
};
const SIT_DROP_DEFAULT = 0.12; /* avatar baru tanpa ukur: tengah-tengah */
function sitDropFor(name) {
  const v = SIT_DROPS[name];
  return typeof v === 'number' ? v : SIT_DROP_DEFAULT;
}
/* LESEHAN 2026-11-21 (Item 2+3) — pose duduk ditulis ulang dari ukur harness:
   - Paha HARUS tentang sumbu-X DUNIA (bukan sumbu-X lokal bone).
     Bukti: thigh +90 lokal (kode lama) mengayun lutut ke (±0.25, -0.11)
     — menyebar ke samping + sedikit ke BELAKANG pinggul, bukan ke depan;
     klaim lama "thigh +90 = paha ke depan (terverifikasi)" SALAH arah
     (yang terverifikasi dulu cuma besar sudutnya, 90.0°, bukan arahnya).
     Rotasi -90° tentang sumbu-X dunia menaruh lutut di (±lebar pinggul,
     tinggi pinggul, +0.07..+0.27 ke depan) untuk 11/11 avatar — paha
     lurus ke arah meja. Sumbu lokalnya dihitung per bone dari base
     quaternion (sitWorldAxis, di-cache di sitThighAxis saat load).
   - Betis +170° (sumbu-X lokal, dulu -90): betis terlipat ke belakang
     di bawah paha, ujung kaki di belakang pantat ~0.05-0.26 di atas
     lantai (tidak menembus lantai); -90 lama membuat betis tegak ke
     bawah (kaki menggantung di samping badan). */
const SIT_THIGH_DEG = -90;  /* paha ke depan, tentang sumbu-X DUNIA */
const SIT_SHIN_DEG = 170;   /* betis terlipat ke belakang, sumbu-X lokal */
const PAD_TOP = 0.10;       /* permukaan pad lesehan (zabuton 0.7 x 0.10 x 0.7) */
const DESK_TOP_Y = 0.36;    /* permukaan meja rendah ala chabudai (lihat buildDesk) */
const SIT_SPINE_DEG = 10;   /* badan condong ke depan */
const SIT_HEAD_DEG = 10;    /* kepala menunduk sedikit */
/* Easing 100/10: semua transisi pose ~400 ms (easeInOutCubic),
   jangan snap. */
const POSE_BLEND_MS = 400;
function easeInOutCubic(t) {
  const x = Math.min(1, Math.max(0, t));
  return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
}
function smoothstep(t) {
  const x = Math.min(1, Math.max(0, t));
  return x * x * (3 - 2 * x);
}

const boneRefs = {};        /* name -> Map(boneIndex -> bone) */
const boneBase = {};        /* name -> Map(boneIndex -> quaternion clone sesudah applyIdlePose) */
const avatarSkeletons = {}; /* name -> THREE.Skeleton (atau undefined) */
const avatarBaseY = {};     /* name -> 0 | -sitDropFor(name) */
const avatarSlotRot = {};  /* name -> rot slot penempatan (arah hadap
  "duduk/berdiri di slot", BUKAN tatapan bos — dipakai kamera follow;
  tatapan bos (§5.4.5) memutar badan ke meja Rangga, tapi kursi/meja
  agen tetap menghadap slot.rot; kamera TPS harus di belakang KURSI,
  bukan di belakang tatapan, supaya monitor tidak menutupi agen. */
const poseState = {};       /* name -> {sitting: bool, activity: 'coffee'|'phone'|null} (target) */
const poseAnim = {};        /* name -> {sittingW, activityW, activity} (bobot render saat ini) */
const activityProps = {};   /* name -> {cup, phone} (child of hand bone) */
const activityStartedAt = {}; /* name -> performance.now() saat activity berubah */
const activityPoseCache = {}; /* name -> signature pose aktivitas terakhir */
let poseBlendRaf = 0;       /* rAF driver blend pose (0 = tidak jalan) */

/* Fallback lokal (dipakai HANYA bila view-model belum mengekspor
   fungsi Worker A — lihat catatan di import VM di atas). Semua
   mengimplementasi kontrak kata per kata. */
function fallbackIsDeskSlot(room, slot) {
  if (!slot) return false;
  if (room === 'ruang-kerja') {
    return ROOMS['ruang-kerja'].slots.some((s) =>
      Math.abs(s.x - slot.x) < 0.01 && Math.abs(s.z - slot.z) < 0.01);
  }
  if (room === 'kantor-rangga') return Math.abs(slot.x - (-10)) < 0.01 && Math.abs(slot.z - (-7.2)) < 0.01;
  return false;
}
function fallbackSelectVisibleBubbles(candidates, max = 3) {
  const speech = candidates.filter((c) => c.kind === 'speech').sort((a, b) => b.ts - a.ts);
  const status = candidates.filter((c) => c.kind === 'status').sort((a, b) => b.ts - a.ts);
  return speech.concat(status).slice(0, max);
}
function fallbackActiveAgentName(agents) {
  let best = null;
  let bestMs = 0;
  for (const name of ROOM_ORDER) {
    const a = agents.find((x) => x.name === name);
    if (!a || a.name === 'rangga') continue;
    const ms = a.lastActiveMs || 0;
    if (ms > bestMs) { bestMs = ms; best = a.name; }
  }
  return bestMs > 0 ? best : null;
}
const selectVisibleBubbles = typeof VM.selectVisibleBubbles === 'function'
  ? VM.selectVisibleBubbles : fallbackSelectVisibleBubbles;
const activeAgentName = typeof VM.activeAgentName === 'function'
  ? VM.activeAgentName : fallbackActiveAgentName;
const isDeskSlotFn = typeof VM.isDeskSlot === 'function'
  ? VM.isDeskSlot : fallbackIsDeskSlot;
/* Fallback pad lesehan (2026-11-27): slot dengan flag pad di
   ROOMS mana pun (bukan hardcode ruangan) — dipakai bila VM
   belum mengekspor isPadSlot. */
function fallbackIsPadSlot(room, slot) {
  if (!slot || !ROOMS[room]) return false;
  return ROOMS[room].slots.some((s) => s.pad
    && Math.abs(s.x - slot.x) < 0.01 && Math.abs(s.z - slot.z) < 0.01);
}
const isPadSlotFn = typeof VM.isPadSlot === 'function'
  ? VM.isPadSlot : fallbackIsPadSlot;
/* Hash FNV-1a (2026-11-27, idle acak): dipakai bila VM belum
   mengekspor hashStr — rumus sama persis supaya hasilnya identik. */
function fallbackHashStr(str) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); }
  return h >>> 0;
}
const hashStrFn = typeof VM.hashStr === 'function' ? VM.hashStr : fallbackHashStr;
/* Ruangan tempat sebuah slot berada (2026-11-27, idle mengembara):
   dipakai bila VM belum mengekspor slotRoom. */
function fallbackSlotRoom(slot) {
  if (!slot || typeof slot.x !== 'number' || typeof slot.z !== 'number') return null;
  for (const roomId of Object.keys(ROOMS)) {
    const room = ROOMS[roomId];
    if (!room || !room.slots) continue;
    for (const s of room.slots) {
      if (Math.abs(s.x - slot.x) <= 0.01 && Math.abs(s.z - slot.z) <= 0.01) return roomId;
    }
  }
  return null;
}
const slotRoomFn = typeof VM.slotRoom === 'function' ? VM.slotRoom : fallbackSlotRoom;
const IDLE_WANDER_MS_V = (typeof VM.IDLE_WANDER_MS === 'number') ? VM.IDLE_WANDER_MS : 15 * 60 * 1000;
const activityForFn = typeof VM.activityFor === 'function' ? VM.activityFor : null;

/* sitting/activity per agen: pakai st.* bila view-model sudah
   menyediakannya (Worker A), bila belum hitung dari keadaan nyata
   yang sama seperti kontrak view-model. */
function agentSitting(st) {
  if (typeof st.sitting === 'boolean') return st.sitting;
  return isDeskSlotFn(st.room, st.slot) || isPadSlotFn(st.room, st.slot);
}
function agentActivity(st) {
  if (st.activity !== undefined) return st.activity;
  if (st.room === 'pantry' && !st.activeTask) return 'coffee';
  if (st.room === 'ruang-kerja' && (st.stale || !st.activeTask)) return 'phone';
  return null;
}

/* --- helper pose ------------------------------------------------- */
function deltaQuat(axis, deg) {
  return new THREE.Quaternion().setFromAxisAngle(
    new THREE.Vector3(axis[0], axis[1], axis[2]).normalize(),
    THREE.MathUtils.degToRad(deg));
}
/* Tangkap base = quaternion tiap bone JOINT_ROLES SESUDAH
   applyIdlePose (dipanggil dari loadOneAvatar). */
function captureBoneBase(obj, name) {
  const roles = JOINT_ROLES[name];
  if (!roles) return;
  const refs = new Map();
  const bases = new Map();
  obj.traverse((o) => {
    if (!o.isSkinnedMesh || !o.skeleton) return;
    if (!avatarSkeletons[name]) avatarSkeletons[name] = o.skeleton;
    for (const idx of new Set(Object.values(roles).flatMap((v) => (Array.isArray(v) ? v : [v])))) {
      if (idx == null) continue;
      const bone = o.skeleton.bones[idx];
      if (bone && !refs.has(idx)) {
        refs.set(idx, bone);
        bases.set(idx, bone.quaternion.clone());
      }
    }
  });
  if (refs.size) {
    boneRefs[name] = refs; boneBase[name] = bases;
    /* Sumbu-X dunia untuk paha (dipakai sitDeltas) — dari base
       quaternion tiap paha; bahu idle tidak menyentuh paha, jadi
       sumbu ini = bind orientation, stabil. */
    sitThighAxis[name] = {
      L: sitWorldAxis(name, roles.thighL),
      R: sitWorldAxis(name, roles.thighR),
    };
  }
}
/* Kontrak: deltas = [{bone, axis:[x,y,z], deg}] — set
   bone.quaternion = base.clone().multiply(deltaQ). Tanpa skeleton
   (fallback) diam-diam lewati. */
function applyBoneDeltas(name, deltas) {
  const refs = boneRefs[name];
  const bases = boneBase[name];
  if (!refs || !bases) return;
  for (const d of deltas) {
    const bone = refs.get(d.bone);
    const base = bases.get(d.bone);
    if (!bone || !base) continue;
    bone.quaternion.copy(base).multiply(deltaQuat(d.axis, d.deg));
  }
}
/* Kalikan delta ke quaternion saat ini (dipakai applyPose untuk
   menyusun duduk + aktivitas pada bone yang sama, mis. head). */
function addBoneDeltas(name, deltas) {
  const refs = boneRefs[name];
  if (!refs) return;
  for (const d of deltas) {
    const bone = refs.get(d.bone);
    if (!bone) continue;
    bone.quaternion.multiply(deltaQuat(d.axis, d.deg));
  }
}
/* Kembalikan semua bone pose ke base (idle pose). */
function resetBones(name) {
  const refs = boneRefs[name];
  const bases = boneBase[name];
  if (!refs || !bases) return;
  for (const [idx, bone] of refs) {
    const base = bases.get(idx);
    if (base) bone.quaternion.copy(base);
  }
}

/* Sumbu-X dunia dalam frame lokal sebuah bone: delta quaternion
   diterapkan di frame lokal bone (base * delta), jadi rotasi tentang
   sumbu dunia harus dikonjugasi dengan base quaternion bone itu
   (local = base^-1 * world). Dihitung sekali per avatar di
   captureBoneBase; fallback [1,0,0] (perilaku lama) bila bone belum
   dimuat (stand-in tanpa skeleton — applyBoneDeltas no-op). */
const sitThighAxis = {};    /* name -> {L:[x,y,z], R:[x,y,z]} */
function sitWorldAxis(name, boneIdx) {
  const bases = boneBase[name];
  if (!bases) return [1, 0, 0];
  const base = bases.get(boneIdx);
  if (!base) return [1, 0, 0];
  const v = new THREE.Vector3(1, 0, 0).applyQuaternion(base.clone().invert());
  return [v.x, v.y, v.z];
}
function sitDeltas(name, roles) {
  const ax = sitThighAxis[name] || {};
  const axL = ax.L || [1, 0, 0];
  const axR = ax.R || [1, 0, 0];
  return [
    { bone: roles.thighL, axis: axL, deg: SIT_THIGH_DEG },
    { bone: roles.thighR, axis: axR, deg: SIT_THIGH_DEG },
    { bone: roles.shinL, axis: [1, 0, 0], deg: SIT_SHIN_DEG },
    { bone: roles.shinR, axis: [1, 0, 0], deg: SIT_SHIN_DEG },
    { bone: roles.spine, axis: [1, 0, 0], deg: SIT_SPINE_DEG },
    { bone: roles.head, axis: [1, 0, 0], deg: SIT_HEAD_DEG },
  ];
}

/* --- Perbaikan tangan buntung + pose mengetik (2026-11-21, FK terukur)
   AKAR MASALAH (fk-out.json; validasi skinning err 0 — angka tepercaya):
   sendi tangan idle/duduk BERADA DI DALAM kotak torso pada 8/11 avatar
   (clearance -0.03..-0.46; mis. Rangga -0.087, Oto -0.094, Deto -0.457):
   bahu menempel sumbu tubuh (shoulderHalfW 0.02..0.13) sementara torso
   chibi lebar (halfW 0.13..0.58) + lengan pendek (0.25..0.56) — tangan
   menggantung DI DALAM badan, bukan di sisinya. Itu "buntung"-nya.
   SWEEP SUDUT (fk-sweep-out.json): bahu maju 25° (world-X) membuat
   permukaan luar tangan keluar dari kotak torso pada 11/11 avatar
   (margin terburuk +0.035, Zeto). f25_a0 dipilih — sudut terkecil yang
   lolos semua; f35 memberi margin lebih tapi lengan terlalu maju.
   POSE MENGETIK (fk-sweep2-out.json, two-phase): bahu maju total 75°
   + siku tekuk -30° + condong spine total 25° + geser duduk 0.15 ke
   meja — hanya Seto yang tangannya mendarat DI ATAS keyboard (lengan
   0.496 terpanjang); 9 avatar lain tangannya maju jelas di atas meja,
   jari mencapai tepi dekat keyboard (jarak sendi ke pusat keyboard
   0.27..0.47); Geto (lengan 0.251 — setengah normal) tidak bisa
   mencapai keyboard dengan kode room (butuh re-rig, lihat laporan).
   Lutut TIDAK menembus meja pada slide 0.15 (terukur 0 di semua avatar).
   ANTI-TEMBUS: pendekatan yang dipilih = CONSTRAINT POSE (a) — sudut
   lengan dihitung supaya tangan selalu di luar volume torso (terukur
   di FK, bukan ditebak). Guard runtime (b) tidak dipakai: clamp
   per-frame pada skinned mesh butuh skinning ulang tiap frame dan
   melawan render-on-demand; collider (c) juga tidak — pose constraint
   yang terverifikasi angka sudah mencapai hasil yang sama dengan biaya
   nol saat diam. Tangan vs meja/keyboard dijaga oleh pose yang sama
   (tangan di atas permukaan keyboard, y > 0.39). */
const ARM_FIX_FWD_DEG = 25;   /* bahu maju (world-X), semua pose */
/* Tambahan sudut untuk avatar bertorso lebar / tangan kecil (supaya
   tangan belakang saat jalan tetap keluar torso — fk-out3: Neto
   -0.047 dan Zeto -0.012 pada ayun mundur 5° dengan fix 25°;
   dengan fix 30° keduanya lolos, margin ≥ +0.035). */
const ARM_FIX_FWD_EXTRA = { neto: 5, zeto: 5 };
const TYPE_SPINE_DEG = 15;    /* tambahan condong (sit +10 -> total 25) */
const TYPE_SPINE_EXTRA = { rangga: 5, zeto: 10, neto: 5, geto: 5 };
/* condong ekstra mengetik per avatar (chibi reach; lain 0) */
const TYPE_HEAD_DEG = -10.5;  /* kompensasi kepala (sit +10 -> total ~0) */
const TYPE_SHOULDER_DEG = 50; /* tambahan maju bahu (fix 25 + 50 = 75 total) */
const TYPE_SHOULDER_FWD_EXTRA = { rangga: 15, oto: 20, beto: 15, zeto: 25, neto: 15, geto: 15, leto: 20, ceto: 15, seto: 20, deto: 15, meto: 20, atharia: 10, reto: 20 };
/* maju bahu ekstra mengetik per avatar (chibi reach: lengan pendek + sit drop besar) */
const TYPE_FOREARM_DEG = -30; /* siku tekuk (forearm lokal X) */
const DESK_SLIDE = 0.25;      /* geser duduk ke arah meja saat di meja
   (0.15 -> 0.25, chibi 2026-11-25: tangan mencapai keyboard; per-avatar di bawah) */
const DESK_SLIDE_EXTRA = { ceto: -0.05, neto: 0.05, leto: 0.05, meto: 0.10, beto: 0.10 };
/* slide akhir: rangga/oto/zeto/geto/seto/deto/atharia/reto 0.25, ceto 0.20,
   neto/leto 0.30, meto/beto 0.35 (lutut tetap clear >= 0.06 dari meja) */
/* --- Tugas 1: tangan mengetik (FK probe fk-hands.json, v7) ---
   Telapak harus menghadap bawah (palm 0.0-0.05 deg) + tangan
   terpisah >= 0.25 (separasi 0.265-0.304). Rotasi pergelangan
   SAJA tidak cukup (pronasi mentok residu ~30 deg karena sumbu
   lengan bawah ~54-65 deg dari vertikal); perlu bahu ke luar
   (TYPE_SHOULDER_OUT_DEG) + satu rotasi axis-angle per tangan
   (TYPE_HAND_SOL, frame lokal hand bone, diselesaikan dari
   orientasi saat ini -> telapak (0,-1,0), jari (0,0,1)).
   Anomali: Zeto/Leto fingerFwd ~59 deg = artefak proxy (pusat
   mesh tangan hampir di pergelangan, |f| ~0.02-0.05); palm tetap
   0.0 deg. Geto butuh out 35 deg (lengan 0.251 + bahu setengah
   lebar 0.02). Seto R dinormalisasi +121.8 deg (dulu 238.2; sumbu
   dibalik + sudut jadi 238.2-360+360=+121.8 — JANGAN -121.8:
   flip sumbu DAN kurangi 360 sekaligus itu transformasi ganda,
   hasilnya rotasi yang salah 243.6 deg). */
const TYPE_SHOULDER_OUT_DEG = { rangga: 15, oto: 10, beto: 10, zeto: 20, neto: 15, geto: 20, leto: 15, ceto: 20, seto: 10, deto: 15, meto: 15, atharia: 10, reto: 10 };
/* diukur ulang fk-hands 2026-11-25 pada skeleton chibi (dulu skeleton lama; beto 0 -> 10 stlh perbaikan delta bahu R) */
const TYPE_HAND_SOL = {
  rangga: { axisL: [0.785, -0.218, 0.58], degL: 84.804, axisR: [0.363, -0.334, -0.87], degR: 88.593 },
  oto: { axisL: [0.165, 0.985, 0.059], degL: 121.079, axisR: [0.159, -0.986, -0.056], degR: 122.051 },
  beto: { axisL: [0.304, 0.384, 0.872], degL: 100.323, axisR: [0.447, -0.603, -0.66], degR: 132.114 },
  zeto: { axisL: [0.22, 0.974, 0.054], degL: 110.31, axisR: [0.456, -0.86, -0.229], degR: 114.663 },
  neto: { axisL: [0.631, 0.703, 0.327], degL: 128.38, axisR: [0.855, 0.081, -0.513], degR: 177.642 },
  geto: { axisL: [0.144, 0.989, -0.02], degL: 114.749, axisR: [0.178, -0.984, -0.013], degR: 114.516 },
  leto: { axisL: [0.153, 0.984, 0.089], degL: 119.761, axisR: [0.164, -0.982, -0.095], degR: 119.874 },
  ceto: { axisL: [0.058, 0.998, -0.021], degL: 114.167, axisR: [0.066, -0.998, 0.015], degR: 115.366 },
  seto: { axisL: [0.112, 0.988, 0.104], degL: 111.886, axisR: [0.046, -0.998, -0.052], degR: 113.103 },
  deto: { axisL: [0.155, 0.988, 0.018], degL: 120.942, axisR: [0.146, -0.989, -0.01], degR: 117.722 },
  meto: { axisL: [0.032, 0.999, 0.023], degL: 122.774, axisR: [0.041, -0.999, -0.028], degR: 122.803 },
  atharia: { axisL: [0.875, -0.247, 0.417], degL: 90.671, axisR: [0.72, -0.078, -0.69], degR: 87.459 },
  reto: { axisL: [0.832, -0.499, -0.241], degL: 119.767, axisR: [0.842, 0.498, 0.209], degR: 119.528 },
};
const TYPE_FINGER_CURL_DEG = 20; /* tekuk jari mengetik, hanya yang punya finger bones
   (chibi batch: Rangga/Oto/Ceto/Leto/Reto — Beto/Deto tidak punya) */
/* --- Tugas 3+4: idle berdiri ---
   Siku tekuk 16 deg (sudut siku ~167 deg, tidak lurus kaku),
   spine condong 3 deg, bahu abduksi 15 deg (lengan keluar dari
   torso — Meto/Ceto/Seto tadinya keluar lewat depan dada; lihat
   RINGKASAN.md Tugas 4). Hanya saat berdiri (lihat applyPoseWeighted). */
const IDLE_STAND_ELBOW_DEG = 16;
const IDLE_STAND_SPINE_DEG = 3;
const IDLE_STAND_ABD_DEG = 15;
const IDLE_STAND_ABD_EXTRA = { rangga: 10, oto: 10, beto: 10, zeto: 15, neto: 20, geto: 20, leto: 10, ceto: 15, seto: 20, deto: 25, atharia: 10 };
/* abduksi ekstra idle berdiri per avatar (chibi 2026-11-25: torso lebar, lengan
   menggantung di depan perut pada 15 deg; total: rangga/oto/beto/leto/atharia 25,
   zeto/ceto 30, neto/geto/seto 35, deto 40, meto/reto 15) */
/* --- Gerak hidup prosedural (2026-11-25) --------------------------------
   Rangga: avatar berdiri "mematung" dan tangan mengetik diam — ruangan
   terasa mati. Lapisan ini menambah gerak KECIL di atas pose yang sudah
   terverifikasi angkanya, TANPA mengubah pose dasarnya:
   - Berdiri: napas (spine X ±1.5°, periode 4.5-6 dtk), goyang beban
     (spine Z ±1.2° dunia, 7-10 dtk + twist Y ±1° + kompensasi bahu
     2.0° di sisi yang terancam, supaya lengan tetap di luar torso),
     kepala melayang pelan (yaw ±13° dari 2 sinus tak sinkron +
     sesekali melirik ±22° dgn ease in/out), lengan ikut napas
     open-only (bahu +0.6° / siku +0.8° hanya saat membuka — lengan
     tidak pernah menutup di bawah posisi diam, supaya gate idle
     tetap lolos di semua fase).
   - Mengetik: tiap tangan mengangkat lalu mengetuk kembali ke posisi
     diam (LIFT-ONLY: tangan TIDAK PERNAH turun di bawah posisi diam,
     karena jarak tangan ke keys cuma 0.002-0.028 — turun 2 mm saja
     sudah menembus keyboard). L/R bergantian, ritme beda per avatar.
   Semua murni fungsi waktu (nowMs) + seed dari nama — tanpa state,
   tanpa akumulasi; pose disusun ulang dari base tiap panggilan
   (applyPoseWeighted), jadi gerak ini hilang sendiri saat avatar
   duduk (bukan mengetik) / berjalan / beraktivitas. Amplitudo dijaga
   supaya gate idle (exit side/side, siku 160-174) dan gate mengetik
   (inKb, palm ≤20°, separasi ≥0.25) tetap lolos di semua fase —
   terverifikasi harness (lihat REPORT-idle-life.md). REDUCED
   (prefers-reduced-motion): timer tidak jalan, pose kembali statis
   seperti semula. */
const LIFE_BREATH_DEG = 1.5;   /* napas: spine X */
const LIFE_SWAY_DEG = 1.2;     /* goyang beban: spine Z (dunia) — 1.5°
   terbukti makan margin tangan sampai 0.014 (harness idle-life);
   1.2° + kompensasi bahu di bawah cukup */
const LIFE_SWAY_COMP_DEG = 2.0; /* kompensasi goyang: bahu sisi yang
   terancam membuka ekstra (half-wave, searah abduksi) supaya lengan
   tetap di luar torso saat badan miring — lengan "menggantung"
   vertikal sementara torso miring, seperti orang sungguhan */
const LIFE_ARM_BIAS_DEG = 0.5; /* bias abduksi konstan selama idle
   hidup: lengan menggantung 0.5° lebih terbuka dari pose diam
   terverifikasi (+0.003 margin) — menutupi sisa efek napas/twist
   (±0.001-0.002, mis. Seto R sempat 0.010 = tepat di gate tanpa
   ini). Tidak terlihat (0.5° ≈ 3 mm di tangan), dan hanya aktif
   saat idle hidup (diskala standW) — pose diam tetap seperti semula. */
const LIFE_SWAY_COMP_MIN_DEG = 0.5; /* kompensasi kecil sisi "aman":
   permukaan torso di tinggi tangan ikut bergeser saat miring
   (Atharia R sempat 0.009 < gate 0.01 tanpa ini) — 0.5° menambah
   margin ~0.003 di sisi yang tidak terancam */
const LIFE_TWIST_DEG = 1.0;    /* twist: spine Y (dunia) */
const LIFE_SHOULDER_DEG = 0.6; /* lengan ikut napas: bahu Z (dunia) */
const LIFE_ELBOW_DEG = 0.8;    /* lengan ikut napas: siku X lokal */
const LIFE_HEAD_DRIFT_DEG = 8; /* kepala melayang: sinus 1 */
const LIFE_HEAD_DRIFT2_DEG = 5; /* kepala melayang: sinus 2 */
const LIFE_HEAD_PITCH_DEG = 3; /* kepala: angguk pelan */
const LIFE_GLANCE_DEG = 22;    /* lirikan maks (dibatasi total ±25°) */
const LIFE_GLANCE_PERIOD_S = 26; /* satu lirikan tiap ~26 dtk per avatar */
const TYPE_LIFT_FOREARM_DEG = -2.0; /* ketik: angkat tangan via siku
   (negatif = searah tekuk -30°, tangan naik ~0.009; JANGAN positif:
   tangan malah turun menembus keys — terverifikasi harness) */
const TYPE_LIFT_HAND_DEG = 1.0;  /* ketik: kompensasi setengah pitch
   pergelangan supaya telapak tetap menghadap bawah */
const TYPE_LIFT_FINGER_DEG = 8;  /* ketik: jari mengangkat (uncurl,
   lawan dari TYPE_FINGER_CURL_DEG +20) lalu mengetuk kembali */
/* Seed deterministik dari nama (FNV-1a) — tiap avatar punya fase,
   periode dan amplitudo sendiri, tidak pernah sinkron. */
function lifeSeed(str) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); }
  return ((h >>> 0) % 10000) / 10000;
}
/* Delta hidup idle berdiri (skala oleh standW di pemanggil). */
function idleLifeDeltas(name, nowMs) {
  const roles = JOINT_ROLES[name];
  if (!roles) return [];
  const t = nowMs / 1000;
  const W = Math.PI * 2;
  const sA = lifeSeed(name), sB = lifeSeed(name + '#2'), sC = lifeSeed(name + '#3'), sD = lifeSeed(name + '#4');
  const breathT = 4.5 + sA * 1.5; /* 4.5-6 dtk */
  const swayT = 7 + sB * 3;       /* 7-10 dtk */
  const breath = Math.sin(W * t / breathT + sA * W);
  const sway = Math.sin(W * t / swayT + sB * W);
  const twist = Math.sin(W * t / (swayT + 1.7) + sC * W);
  /* Napas lengan open-only: lengan hanya MEMBUKA dari posisi diam,
     tidak pernah menutup ke arah torso (menutup 0.6° saja sudah
     makan margin 0.004; siku Beto R yang rest-nya 160.39° juga
     tidak boleh menutup — gate siku min 160°). */
  const breathOpen = Math.max(0, breath);   /* dada naik: lengan buka */
  const breathOpenElb = Math.max(0, -breath); /* dada turun: siku buka */
  /* Kompensasi goyang (half-wave per sisi): +sway mengancam tangan
     kanan, -sway mengancam tangan kiri — sisi yang terancam saja
     yang membuka ekstra. */
  const swayCompL = LIFE_SWAY_COMP_DEG * Math.max(0, -sway) + LIFE_SWAY_COMP_MIN_DEG * Math.max(0, sway);
  const swayCompR = LIFE_SWAY_COMP_DEG * Math.max(0, sway) + LIFE_SWAY_COMP_MIN_DEG * Math.max(0, -sway);
  /* Kepala: drift 2 sinus (11 + 17 dtk) + lirikan terjadwal. */
  const headDrift = LIFE_HEAD_DRIFT_DEG * Math.sin(W * t / 11 + sC * W)
    + LIFE_HEAD_DRIFT2_DEG * Math.sin(W * t / 17 + sD * W);
  const gp = LIFE_GLANCE_PERIOD_S;
  const gIdx = Math.floor(t / gp + sD);
  const gPhase = (t / gp + sD) - gIdx; /* 0..1 dalam satu periode lirikan */
  const gOff = 0.1 + 0.7 * lifeSeed(name + '#g' + gIdx); /* posisi jendela */
  const gTarget = (lifeSeed(name + '#t' + gIdx) - 0.5) * 2 * LIFE_GLANCE_DEG;
  let glance = 0;
  if (gPhase >= gOff && gPhase <= gOff + 3 / gp) {
    const k = (gPhase - gOff) / (3 / gp);
    glance = gTarget * (k < 0.5 ? smoothstep(k * 2) : smoothstep((1 - k) * 2));
  }
  const headYaw = Math.max(-25, Math.min(25, headDrift + glance));
  const headPitch = LIFE_HEAD_PITCH_DEG * Math.sin(W * t / 13 + sA * W);
  return [
    { bone: roles.spine, axis: [1, 0, 0], deg: LIFE_BREATH_DEG * breath },
    { bone: roles.spine, axis: worldAxisLocal(name, roles.spine, [0, 0, 1]), deg: LIFE_SWAY_DEG * sway },
    { bone: roles.spine, axis: worldAxisLocal(name, roles.spine, [0, 1, 0]), deg: LIFE_TWIST_DEG * twist },
    { bone: roles.shoulderL, axis: worldAxisLocal(name, roles.shoulderL, [0, 0, 1]), deg: LIFE_ARM_BIAS_DEG + LIFE_SHOULDER_DEG * breathOpen + swayCompL },
    { bone: roles.shoulderR, axis: worldAxisLocal(name, roles.shoulderR, [0, 0, 1]), deg: -LIFE_ARM_BIAS_DEG - LIFE_SHOULDER_DEG * breathOpen - swayCompR },
    { bone: roles.forearmL, axis: [1, 0, 0], deg: LIFE_ELBOW_DEG * breathOpenElb },
    { bone: roles.forearmR, axis: [1, 0, 0], deg: LIFE_ELBOW_DEG * breathOpenElb },
    { bone: roles.head, axis: worldAxisLocal(name, roles.head, [0, 1, 0]), deg: headYaw },
    { bone: roles.head, axis: worldAxisLocal(name, roles.head, [1, 0, 0]), deg: headPitch },
  ];
}
/* Delta gerak mengetik (skala oleh typeW di pemanggil). Lift-only:
   tiap tangan mengangkat (bump sin^2, 60% siklus) lalu kembali ke
   posisi diam — tidak pernah di bawah diam. */
function typingLifeDeltas(name, nowMs) {
  const roles = JOINT_ROLES[name];
  if (!roles) return [];
  const t = nowMs / 1000;
  const sA = lifeSeed(name), sB = lifeSeed(name + '#2');
  const period = 1.1 + sA * 0.8; /* 1.1-1.9 dtk per siklus tangan */
  const tap = (ph) => {
    const u = (((t / period + ph) % 1) + 1) % 1;
    return u < 0.6 ? Math.sin(Math.PI * u / 0.6) ** 2 : 0;
  };
  const liftL = tap(sB);       /* tangan kiri */
  const liftR = tap(sB + 0.5); /* kanan setengah siklus beda */
  const out = [
    { bone: roles.forearmL, axis: [1, 0, 0], deg: TYPE_LIFT_FOREARM_DEG * liftL },
    { bone: roles.forearmR, axis: [1, 0, 0], deg: TYPE_LIFT_FOREARM_DEG * liftR },
    { bone: roles.handL, axis: [1, 0, 0], deg: TYPE_LIFT_HAND_DEG * liftL },
    { bone: roles.handR, axis: [1, 0, 0], deg: TYPE_LIFT_HAND_DEG * liftR },
  ];
  if (roles.fingerL) for (const b of roles.fingerL) out.push({ bone: b, axis: [1, 0, 0], deg: -TYPE_LIFT_FINGER_DEG * liftL });
  if (roles.fingerR) for (const b of roles.fingerR) out.push({ bone: b, axis: [1, 0, 0], deg: -TYPE_LIFT_FINGER_DEG * liftR });
  return out;
}
/* Sumbu dunia sembarang dalam frame lokal sebuah bone (konjugasi
   dengan base quaternion — seperti sitWorldAxis tapi umum). */
function worldAxisLocal(name, boneIdx, worldAxis) {
  const bases = boneBase[name];
  if (!bases) return [1, 0, 0];
  const base = bases.get(boneIdx);
  if (!base) return [1, 0, 0];
  const v = new THREE.Vector3(worldAxis[0], worldAxis[1], worldAxis[2])
    .applyQuaternion(base.clone().invert());
  return [v.x, v.y, v.z];
}
/* Sumbu dunia dalam frame lokal bone dari quaternion SAAT INI
   (dipakai fase 2 pose mengetik: sumbu bahu dihitung SESUDAH condong
   spine, supaya "maju 75°" benar-benar maju di dunia — sesuai
   fk-sweep2 two-phase). */
function worldAxisFromCurrent(name, boneIdx, worldAxis) {
  const refs = boneRefs[name];
  if (!refs) return [1, 0, 0];
  const bone = refs.get(boneIdx);
  if (!bone) return [1, 0, 0];
  const v = new THREE.Vector3(worldAxis[0], worldAxis[1], worldAxis[2])
    .applyQuaternion(bone.quaternion.clone().invert());
  return [v.x, v.y, v.z];
}
/* Apakah agen duduk di meja (bukan pad)? — dari ruangan + slot logis. */
function agentAtDesk(name) {
  const room = avatarRoom[name];
  const pos = avatarPos[name];
  if (!room || !pos) return false;
  return isDeskSlotFn(room, pos);
}
/* Delta perbaikan lengan (selalu aktif, semua pose): bahu maju 25°
   tentang sumbu-X dunia (30° untuk Neto/Zeto — lihat atas). */
function armFixDeltas(name, roles) {
  const fwd = ARM_FIX_FWD_DEG + (ARM_FIX_FWD_EXTRA[name] || 0);
  return [
    { bone: roles.shoulderL, axis: worldAxisLocal(name, roles.shoulderL, [1, 0, 0]), deg: -fwd },
    { bone: roles.shoulderR, axis: worldAxisLocal(name, roles.shoulderR, [1, 0, 0]), deg: -fwd },
  ];
}
/* Bobot pose mengetik: duduk di meja dan TIDAK sedang beraktivitas
   (kopi/HP) — aktivitas mengambil alih lengan. */
function typingWeight(name) {
  const anim = poseAnim[name];
  if (!anim || anim.sittingW <= 0.001) return 0;
  if (!agentAtDesk(name)) return 0;
  return anim.sittingW * (1 - (anim.activityW || 0));
}

/* Delta aktivitas pada saat nowMs (performance.now()). Kopi =
   siklus ~8 dtk: angkat 1.5 dtk, tahan 1 dtk (+ head tilt
   belakang sedikit), turun 1 dtk, istirahat ~4.5 dtk — angkat/turun
   dengan easing smoothstep (bukan linear robotik). HP = pose
   statis (head menunduk 15°, lengan kiri sedikit maju) + sesekali
   head tilt kecil (tiap siklus 6 dtk, 1.2 dtk pertama).
   Tangan menggenggam: jari sedikit menekuk (yang punya finger_L/R
   pakai jari; avatar lain goyang hand kecil). */
function activityDeltas(name, activity, nowMs) {
  const roles = JOINT_ROLES[name];
  if (!roles || !activity) return [];
  const grip = (fingerBones, handBone, deg) => {
    const out = [];
    if (fingerBones) {
      for (const b of fingerBones) out.push({ bone: b, axis: [1, 0, 0], deg });
    } else if (handBone != null) {
      out.push({ bone: handBone, axis: [1, 0, 0], deg: deg * 0.3 });
    }
    return out;
  };
  if (activity === 'coffee') {
    const t = ((nowMs - (activityStartedAt[name] || nowMs)) % 8000 + 8000) % 8000;
    let f = 0;
    if (t < 1500) f = smoothstep(t / 1500);
    else if (t < 2500) f = 1;
    else if (t < 3500) f = 1 - smoothstep((t - 2500) / 1000);
    else f = 0;
    const out = [
      { bone: roles.shoulderR, axis: [1, 0, 0], deg: 30 * f },
      { bone: roles.forearmR, axis: [1, 0, 0], deg: 70 * f },
      ...grip(roles.fingerR, roles.handR, 25 * f),
    ];
    if (f >= 1) out.push({ bone: roles.head, axis: [1, 0, 0], deg: -8 });
    return out;
  }
  if (activity === 'phone') {
    const t = ((nowMs - (activityStartedAt[name] || nowMs)) % 6000 + 6000) % 6000;
    const out = [
      { bone: roles.head, axis: [1, 0, 0], deg: 15 },
      { bone: roles.shoulderL, axis: [1, 0, 0], deg: 20 },
      { bone: roles.forearmL, axis: [1, 0, 0], deg: 10 },
      ...grip(roles.fingerL, roles.handL, 20),
    ];
    if (t < 1200) out.push({ bone: roles.head, axis: [0, 0, 1], deg: 5 });
    return out;
  }
  return [];
}

/* Delta tangan mengetik (Tugas 1): bahu ke luar (world-Z) + satu
   rotasi axis-angle per tangan (TYPE_HAND_SOL, frame lokal hand
   bone) + tekuk jari 20 deg (hanya yang punya finger bones).
   axisFn = worldAxisFromCurrent (fase 2 applyPoseWeighted) atau
   worldAxisLocal (walk, single-phase). includeOut=false bila bahu
   ke luar sudah ada di array yang sama (fase 2a) — sumbu out HARUS
   dihitung dari quat fase 1 (SEBELUM bahu maju), seperti probe
   fk-hands: semua sumbu fase 2 dihitung sebelum aplikasi, jadi
   komposisi dunia = Rx_fwd * Rz. Sumbu post-fwd (panggilan
   terpisah) memberi komutator ~16 deg dan merusak solusi tangan. */
function typingHandDeltas(name, roles, typeW, axisFn, includeOut = true) {
  const sol = TYPE_HAND_SOL[name];
  if (!sol) return [];
  const deltas = [];
  if (includeOut) {
    const out = TYPE_SHOULDER_OUT_DEG[name] || 0;
    deltas.push(
      { bone: roles.shoulderL, axis: axisFn(name, roles.shoulderL, [0, 0, 1]), deg: out * typeW },
      { bone: roles.shoulderR, axis: axisFn(name, roles.shoulderR, [0, 0, 1]), deg: -out * typeW });
  }
  deltas.push(
    { bone: roles.handL, axis: sol.axisL, deg: sol.degL * typeW },
    { bone: roles.handR, axis: sol.axisR, deg: sol.degR * typeW });
  if (roles.fingerL) for (const b of roles.fingerL) deltas.push({ bone: b, axis: [1, 0, 0], deg: TYPE_FINGER_CURL_DEG * typeW });
  if (roles.fingerR) for (const b of roles.fingerR) deltas.push({ bone: b, axis: [1, 0, 0], deg: TYPE_FINGER_CURL_DEG * typeW });
  return deltas;
}

/* Susun pose lengkap agen dari base dengan bobot blend:
   duduk × sittingW + aktivitas × activityW. Selalu dari base —
   tidak pernah akumulasi. Dilewati bila agen sedang jalan (walk
   yang mengatur bone). */
function applyPoseWeighted(name, nowMs = performance.now()) {
  if (walks[name]) return;
  const roles = JOINT_ROLES[name];
  if (!roles) return;
  resetBones(name);
  const anim = poseAnim[name] || { sittingW: 0, activityW: 0, activity: null };
  const typeW = typingWeight(name);
  const deltas = [];
  /* Fase 1 (sumbu dikonjugasi terhadap base): perbaikan lengan +
     duduk + condong/kompensasi kepala mengetik + aktivitas. */
  for (const d of armFixDeltas(name, roles)) deltas.push(d);
  /* Idle berdiri (Tugas 3+4): HANYA saat berdiri, tidak mengetik,
     diskalakan (1-activityW) supaya aktivitas mengambil alih.
     Siku tekuk 16 deg (sudut siku ~167 deg), spine condong 3 deg,
     bahu abduksi 15 deg (lengan keluar dari torso). */
  const standW = (anim.sittingW <= 0.001 && typeW <= 0.001) ? (1 - (anim.activityW || 0)) : 0;
  if (standW > 0.001) {
    deltas.push({ bone: roles.shoulderL, axis: worldAxisLocal(name, roles.shoulderL, [0, 0, 1]), deg: (IDLE_STAND_ABD_DEG + (IDLE_STAND_ABD_EXTRA[name] || 0)) * standW });
    deltas.push({ bone: roles.shoulderR, axis: worldAxisLocal(name, roles.shoulderR, [0, 0, 1]), deg: -(IDLE_STAND_ABD_DEG + (IDLE_STAND_ABD_EXTRA[name] || 0)) * standW });
    deltas.push({ bone: roles.forearmL, axis: [1, 0, 0], deg: -IDLE_STAND_ELBOW_DEG * standW });
    deltas.push({ bone: roles.forearmR, axis: [1, 0, 0], deg: -IDLE_STAND_ELBOW_DEG * standW });
    deltas.push({ bone: roles.spine, axis: [1, 0, 0], deg: IDLE_STAND_SPINE_DEG * standW });
    /* Gerak hidup idle (napas/goyang/kepala) — hanya saat berdiri,
       diskala standW seperti delta idle lainnya. */
    for (const d of idleLifeDeltas(name, nowMs)) deltas.push({ ...d, deg: d.deg * standW });
  }
  if (anim.sittingW > 0.001) {
    for (const d of sitDeltas(name, roles)) deltas.push({ ...d, deg: d.deg * anim.sittingW });
  }
  if (typeW > 0.001) {
    deltas.push({ bone: roles.spine, axis: [1, 0, 0], deg: (TYPE_SPINE_DEG + (TYPE_SPINE_EXTRA[name] || 0)) * typeW });
    deltas.push({ bone: roles.head, axis: [1, 0, 0], deg: TYPE_HEAD_DEG * typeW });
  }
  if (anim.activityW > 0.001 && anim.activity) {
    for (const d of activityDeltas(name, anim.activity, nowMs)) {
      deltas.push({ ...d, deg: d.deg * anim.activityW });
    }
  }
  if (deltas.length) addBoneDeltas(name, deltas);
  /* Fase 2 (sumbu bahu dari quat saat ini, sesudah condong):
     bahu maju tambahan + siku tekuk mengetik. */
  if (typeW > 0.001) {
    addBoneDeltas(name, [
      { bone: roles.shoulderL, axis: worldAxisFromCurrent(name, roles.shoulderL, [1, 0, 0]), deg: -(TYPE_SHOULDER_DEG + (TYPE_SHOULDER_FWD_EXTRA[name] || 0)) * typeW },
      { bone: roles.shoulderR, axis: worldAxisFromCurrent(name, roles.shoulderR, [1, 0, 0]), deg: -(TYPE_SHOULDER_DEG + (TYPE_SHOULDER_FWD_EXTRA[name] || 0)) * typeW },
      { bone: roles.forearmL, axis: [1, 0, 0], deg: TYPE_FOREARM_DEG * typeW },
      { bone: roles.forearmR, axis: [1, 0, 0], deg: TYPE_FOREARM_DEG * typeW },
      /* Tugas 1: bahu ke luar — sumbu dihitung di array yang SAMA
         ini (dari quat fase 1, sebelum bahu maju), seperti probe
         fk-hands. Jangan pindah ke panggilan terpisah (lihat
         typingHandDeltas). */
      { bone: roles.shoulderL, axis: worldAxisFromCurrent(name, roles.shoulderL, [0, 0, 1]), deg: (TYPE_SHOULDER_OUT_DEG[name] || 0) * typeW },
      { bone: roles.shoulderR, axis: worldAxisFromCurrent(name, roles.shoulderR, [0, 0, 1]), deg: -(TYPE_SHOULDER_OUT_DEG[name] || 0) * typeW },
    ]);
    /* Fase 2b: rotasi tangan + tekuk jari (sumbu lokal konstan —
       tidak tergantung urutan; out sudah di fase 2a). */
    addBoneDeltas(name, typingHandDeltas(name, roles, typeW, worldAxisFromCurrent, false));
  }
  /* Fase 3: gerak mengetik (lift-only, di atas pose mengetik yang
     sudah ter-solve — tidak pernah di bawah posisi diam). */
  if (typeW > 0.001) {
    const lifeD = typingLifeDeltas(name, nowMs);
    for (const d of lifeD) d.deg *= typeW;
    addBoneDeltas(name, lifeD);
  }
}
/* Jalur cepat: samakan bobot render dengan target SEKETIKA (dipakai
   penempatan awal/initial + akhir jalan yang sudah di-blend). */
function snapPoseWeights(name) {
  const ps = poseState[name] || { sitting: false, activity: null };
  const prev = poseAnim[name];
  if (!prev || prev.activity !== ps.activity) {
    activityStartedAt[name] = performance.now();
    delete activityPoseCache[name];
  }
  poseAnim[name] = {
    sittingW: ps.sitting ? 1 : 0,
    activityW: ps.activity ? 1 : 0,
    activity: ps.activity,
  };
  applyPoseWeighted(name);
}
/* Driver blend pose ~400 ms (easeInOutCubic): animasikan bobot
   render menuju target; jalan hanya selama ada yang berubah,
   lalu berhenti (render-on-demand tetap). Ganti aktivitas =
   fade-out 200 ms → ganti nama → fade-in 200 ms. Transisi
   dimulai startPoseTransition (dipanggil saat poseState berubah);
   bobot awal = bobot render saat ini (bukan snap). */
const poseTrans = {}; /* name -> {sitFrom, sitTo, sitT0, actFrom, actT0, actPhase, actPending} */
function startPoseTransition(name) {
  const ps = poseState[name];
  if (!ps || walks[name]) return;
  const anim = poseAnim[name] || (poseAnim[name] = { sittingW: 0, activityW: 0, activity: null });
  const tr = poseTrans[name] || (poseTrans[name] = {});
  const now = performance.now();
  const targetSitW = ps.sitting ? 1 : 0;
  if (Math.abs(anim.sittingW - targetSitW) > 0.001) {
    tr.sitFrom = anim.sittingW;
    tr.sitTo = targetSitW;
    tr.sitT0 = now;
  }
  if (anim.activity !== ps.activity) {
    tr.actPhase = 'out';
    tr.actFrom = anim.activityW;
    tr.actT0 = now;
    tr.actPending = ps.activity;
  } else if (ps.activity && anim.activityW < 0.999) {
    tr.actPhase = 'in';
    tr.actFrom = anim.activityW;
    tr.actT0 = now;
    tr.actPending = ps.activity;
  } else if (!ps.activity && anim.activityW > 0.001) {
    tr.actPhase = 'out';
    tr.actFrom = anim.activityW;
    tr.actT0 = now;
    tr.actPending = null;
  }
  ensurePoseBlend();
}
function ensurePoseBlend() {
  if (poseBlendRaf) return;
  const tick = (t) => {
    let anyActive = false;
    let anyChanged = false;
    for (const name of ROOM_ORDER) {
      if (walks[name]) continue;
      const tr = poseTrans[name];
      const anim = poseAnim[name];
      if (!tr || !anim) continue;
      let changed = false;
      if (tr.sitFrom !== undefined) {
        const k = (t - tr.sitT0) / POSE_BLEND_MS;
        if (k >= 1) {
          anim.sittingW = tr.sitTo;
          delete tr.sitFrom;
        } else {
          anim.sittingW = tr.sitFrom + (tr.sitTo - tr.sitFrom) * easeInOutCubic(k);
          anyActive = true;
        }
        changed = true;
      }
      if (tr.actPhase === 'out') {
        const k = (t - tr.actT0) / 200;
        if (k >= 1) {
          anim.activityW = 0;
          if (tr.actPending) {
            anim.activity = tr.actPending;
            activityStartedAt[name] = performance.now();
            delete activityPoseCache[name];
            tr.actPhase = 'in';
            tr.actFrom = 0;
            tr.actT0 = t;
            anyActive = true;
          } else {
            anim.activity = null;
            delete tr.actPhase;
          }
        } else {
          anim.activityW = tr.actFrom * (1 - easeInOutCubic(k));
          anyActive = true;
        }
        changed = true;
      } else if (tr.actPhase === 'in') {
        const k = (t - tr.actT0) / 200;
        if (k >= 1) {
          anim.activityW = 1;
          delete tr.actPhase;
        } else {
          anim.activityW = tr.actFrom + (1 - tr.actFrom) * easeInOutCubic(k);
          anyActive = true;
        }
        changed = true;
      }
      if (changed) {
        /* Tinggi grup mengikuti bobot duduk (tidak pop vertikal);
           geser duduk ke meja mengikuti bobot yang sama (halus). */
        const g = avatarGroups[name];
        if (g) {
          g.position.y = -sitDropFor(name) * anim.sittingW;
          const pos = avatarPos[name];
          if (pos && agentAtDesk(name)) {
            const rot = avatarSlotRot[name] || 0;
            g.position.x = pos.x + Math.sin(rot) * (DESK_SLIDE + (DESK_SLIDE_EXTRA[name] || 0)) * anim.sittingW;
            g.position.z = pos.z + Math.cos(rot) * (DESK_SLIDE + (DESK_SLIDE_EXTRA[name] || 0)) * anim.sittingW;
          } else if (pos) {
            g.position.x = pos.x;
            g.position.z = pos.z;
          }
        }
        applyPoseWeighted(name, t);
        anyChanged = true;
      }
      if (tr.sitFrom !== undefined || tr.actPhase) anyActive = true;
    }
    if (anyChanged) requestRender();
    poseBlendRaf = anyActive ? requestAnimationFrame(tick) : 0;
  };
  poseBlendRaf = requestAnimationFrame(tick);
}

/* Props aktivitas primitif kode, ditempel ke BONE tangan (child of
   hand bone — ikut gerak tangan): cangkir di hand_R, HP di hand_L.
   Disembunyikan default; visibilitas diatur updateActivityProps. */
function attachActivityProps(name) {
  const roles = JOINT_ROLES[name];
  const refs = boneRefs[name];
  if (!roles || !refs) return;
  const handR = refs.get(roles.handR);
  const handL = refs.get(roles.handL);
  const props = {};
  if (handR) {
    const cup = cyl(0.05, 0.04, 0.09, 0xf5f5f0);
    cup.position.set(0, -0.09, 0.03);
    cup.visible = false;
    handR.add(cup);
    props.cup = cup;
  }
  if (handL) {
    const phone = box(0.09, 0.16, 0.02, 0x111111);
    phone.position.set(0, -0.09, 0.02);
    phone.visible = false;
    handL.add(phone);
    props.phone = phone;
  }
  if (props.cup || props.phone) activityProps[name] = props;
}
function updateActivityProps(name) {
  const props = activityProps[name];
  if (!props) return;
  const act = (poseState[name] || {}).activity || null;
  if (props.cup) props.cup.visible = act === 'coffee';
  if (props.phone) props.phone.visible = act === 'phone';
}

/* Penanda oktahedron di atas kepala agen aktif DIHAPUS 28 Nov 2026
   (perintah Rangga: hapus penanda untuk semua agen). Agen aktif
   tetap ditandai class 'active' di portrait strip + kartu follow. */

/* Showcase: tanpa login/token — data hanya dari snapshot.json. */
function requestRender() {
  if (!renderer || !webglOK) return;
  render();
}
function render() {
  /* Selama animasi masuk follow, kamera digerakkan animasi (bukan
     updateFollowCamera) supaya tidak loncat ke pose akhir. */
  if (cameraMode === 'follow' && !(camAnim && camAnim.kind === 'enter')) updateFollowCamera();
  /* Tugas 6: perbarui matriks kamera SEBELUM memproyeksikan bubble —
     Vector3.project memakai camera.matrixWorldInverse, yang baru
     diperbarui di dalam renderer.render(); tanpa ini bubble memakai
     matriks SATU FRAME sebelumnya dan membeku di proyeksi lama saat
     drag berhenti (render-on-demand) — sumber drift saat rotate. */
  if (camera) camera.updateMatrixWorld();
  updateBubbles();
  renderer.render(scene, camera);
}

/* --- kamera ---------------------------------------------------- */
/* Framing overview DATA-DRIVEN: bounds dari ROOMS (semua slot +
   door, margin 2) — bukan angka denah hardcode — supaya framing
   otomatis mengikuti floor plan baru (Worker F). */
function computePlanBounds() {
  let minX = Infinity;
  let maxX = -Infinity;
  let minZ = Infinity;
  let maxZ = -Infinity;
  for (const roomId of Object.keys(ROOMS)) {
    const room = ROOMS[roomId];
    const pts = [...(room.slots || [])];
    if (room.door) pts.push(room.door);
    for (const p of pts) {
      if (p.x < minX) minX = p.x;
      if (p.x > maxX) maxX = p.x;
      if (p.z < minZ) minZ = p.z;
      if (p.z > maxZ) maxZ = p.z;
    }
  }
  const m = 2;
  minX -= m; maxX += m; minZ -= m; maxZ += m;
  return {
    minX, maxX, minZ, maxZ,
    cx: (minX + maxX) / 2,
    cz: (minZ + maxZ) / 2,
    w: maxX - minX,
    d: maxZ - minZ,
  };
}
/* Tugas 5: elevasi + pan overview bisa diubah user (dulu elevasi
   tetap 0.62, azimuth di-clamp ±1.1 rad, tidak ada pan overview). */
function updateCamera() {
  if (!orthoCam) return;
  const el = camElev;
  const d = 42;
  const b = computePlanBounds();
  const cx = b.cx + camPan.x;
  const cz = b.cz + camPan.z;
  orthoCam.position.set(
    cx + Math.sin(azimuth) * Math.cos(el) * d,
    Math.sin(el) * d,
    cz + Math.cos(azimuth) * Math.cos(el) * d);
  orthoCam.lookAt(cx, 0, cz);
  orthoCam.zoom = camZoom;
  orthoCam.updateProjectionMatrix();
}
/* FREE CAM 2026-11-27 (Rangga: orbit 360, batas = jalan raya):
   pan overview dijepit ke bounds denah (kantor + luar sampai
   jalan), bukan angka hardcode ±12 — target kamera tidak boleh
   keluar denah. Bounds data-driven dari ROOMS via
   computePlanBounds (x -22..22, z -13.5..36 sesudah ekspansi
   luar; jalan di z 30.5-37.5). */
function clampCamPan() {
  const b = computePlanBounds();
  camPan.x = Math.min(b.maxX - b.cx, Math.max(b.minX - b.cx, camPan.x));
  camPan.z = Math.min(b.maxZ - b.cz, Math.max(b.minZ - b.cz, camPan.z));
}
function fitCamera() {
  if (!orthoCam || !wrap) return;
  const w = wrap.clientWidth || 800;
  const h = wrap.clientHeight || 600;
  const aspect = w / Math.max(h, 1);
  /* Frustum dari bounds denah (bukan angka hardcode): lebar
     proyeksi iso ≈ (w+d)/√2, tinggi ≈ lebar * sin(el) + margin
     dinding/avatar. HP portrait (aspect kecil) tetap ter-crop
     samping seperti sebelumnya (dibatasi 40) — mode utama HP
     adalah daftar kartu vertikal di bawah canvas. */
  const b = computePlanBounds();
  const el = 0.62;
  const projW = (b.w + b.d) / Math.SQRT2;
  const projH = projW * Math.sin(el) + 3;
  /* FREE CAM 2026-11-27: cap 40 -> 70 supaya framing default
     memuat SELURUH scene yang membesar (kantor + halaman +
     parkir + jalan; butuh ~41.4 di landscape). Portrait tetap
     dibatasi (cap 70) supaya tidak mengecil berlebihan. */
  const size = Math.min(70, Math.max(projH, projW / aspect));
  orthoCam.left = -size * aspect / 2;
  orthoCam.right = size * aspect / 2;
  orthoCam.top = size / 2;
  orthoCam.bottom = -size / 2;
  orthoCam.near = 0.1;
  orthoCam.far = 200;
  orthoCam.updateProjectionMatrix();
  if (perspCam) {
    perspCam.aspect = aspect;
    perspCam.updateProjectionMatrix();
  }
}

/* --- kamera follow TPS ------------------------------------------- */
/* Pose kamera follow (posisi + anchor + FOV) TANPA menerapkannya —
   dipakai updateFollowCamera tiap frame DAN animasi masuk follow
   (transisi smooth, Rangga 27 Nov 21:12). Posisi kamera follow dari
   posisi + arah hadap agen saat ini (turn.rotation.y; saat jalan =
   arah gerak): di belakang bahu (followYaw), di atas (followPitch),
   jarak followDist; anchor = torso agen + pan. Pitch di-clamp
   [0.08, 1.25] supaya kamera tidak masuk bawah lantai; posisi x/z
   di-clamp ke bounds + 4 supaya tidak nyangkut jauh di luar dinding.
   ARAH HADAP (0.4.9): saat agen DIAM, pakai avatarSlotRot (arah
   hadap slot — kursi menghadap meja) BUKAN turn.rotation.y:
   tatapan bos (§5.4.5) memutar badan ke meja Rangga saat
   bossActive, sehingga "belakang badan" jatuh di sisi meja dan
   monitor menutupi agen (temuan verifikasi 0.4.9: beto duduk
   terhalang monitornya sendiri). Saat JALAN, pakai
   turn.rotation.y (= arah gerak) supaya kamera tetap di belakang
   agen yang berjalan. Anchor = torso (1.1), bukan kepala (1.5):
   kamera mengunci ke kepala + rambut chibi yang besar membuat
   rambut memenuhi frame; torso membuat seluruh badan terlihat. */
function followCamPose() {
  if (!perspCam || !followName) return null;
  const pos = avatarPos[followName];
  const g = avatarGroups[followName];
  if (!pos || !g || !g.visible) return null;
  const turn = avatarMeshes[followName];
  /* Diam = hadap slot (kursi -> meja); jalan = arah gerak. */
  const walkingNow = !!(walks[followName] && !walks[followName].cancelled);
  const facing = walkingNow
    ? (turn ? turn.rotation.y : 0)
    : (avatarSlotRot[followName] !== undefined
      ? avatarSlotRot[followName]
      : (turn ? turn.rotation.y : 0));
  const yaw = facing + Math.PI + followYaw;
  /* Arah hadap agen = (sin(rotY), cos(rotY)); kamera di belakang
     = arah berlawanan (rotY + π). followYaw memutar di sekitar. */
  const pitch = Math.min(1.25, Math.max(0.08, followPitch));
  const dist = Math.min(6, Math.max(2.2, followDist));
  /* Anchor = torso agen (ikut turun bila duduk). */
  const anchorY = 1.1 + (avatarBaseY[followName] || 0);
  const anchor = new THREE.Vector3(pos.x + followPan.x, anchorY, pos.z + followPan.z);
  const horiz = dist * Math.cos(pitch);
  /* SHOWCASE FIX (follow Rangga = layar hitam, Oto msg_0349): kamera
     follow TIDAK boleh keluar denah. Posisi di belakang agen yang
     duduk di tepi utara (slot rot 0, mis. Rangga (-18,-11)) jatuh di
     luar dinding utara (z=-14.15) sehingga dinding menutupi agen —
     layar hitam total (mean luminance 4.8, 100% piksel <16), hanya
     label DOM yang melayang. Jepit ke dalam FLOOR dengan margin 0.6
     dari muka dalam dinding; jarak efektif mengecil tapi agen tetap
     terlihat. (Bug yang sama ada di produksi room3d.js — ranah
     Maximum Level tahap (b), bukan showcase.) */
  const cx = Math.min(FLOOR.x1 - 0.6, Math.max(FLOOR.x0 + 0.6,
    anchor.x + Math.sin(yaw) * horiz));
  const cz = Math.min(FLOOR.z1 - 0.6, Math.max(FLOOR.z0 + 0.6,
    anchor.z + Math.cos(yaw) * horiz));
  const cy = Math.max(0.5, anchor.y + dist * Math.sin(pitch));
  /* FOV portrait lebih lebar (Fase 2, port dari Beto msg_0394): di layar
     portrait (aspect < 1) kamera follow memakai FOV 80 — avatar tidak lagi
     memenuhi frame. Desktop tetap 55. */
  const fov = (perspCam.aspect || 1.6) < 1 ? 80 : 55;
  return { pos: new THREE.Vector3(cx, cy, cz), anchor, fov };
}
function updateFollowCamera() {
  const pose = followCamPose();
  if (!pose) return;
  if (perspCam.fov !== pose.fov) perspCam.fov = pose.fov;
  perspCam.position.copy(pose.pos);
  perspCam.lookAt(pose.anchor);
  perspCam.updateProjectionMatrix();
  /* Tugas 6: pill indikator agen yang di-follow disembunyikan di
     updateBubbles (dulu sprite wajah disembunyikan di sini). */
}
function enterFollow(name) {
  if (!KNOWN_AGENTS[name] || !avatarGroups[name] || !avatarGroups[name].visible) return false;
  fsSeq++; /* follow baru — fullscreenchange basi dari exit lama abaikan */
  if (!perspCam) return false;
  /* Pindah antar agen (A -> B): kamera TERBANG LANGSUNG dari POV A ke
     POV B, TANPA zoom out ke overview (Rangga 27 Nov 22:27). Tangkap
     pose awal dari posisi kamera SAAT INI (di belakang A), bukan dari
     posisi overview orthoCam — dari situlah "zoom out mendadak" itu
     berasal. */
  const switching = cameraMode === 'follow' && followName && followName !== name;
  const wasEntering = !!(camAnim && camAnim.kind === 'enter');
  const wasExiting = !!(camAnim && camAnim.kind === 'exit');
  let fromPos = null;
  let fromAnchor = null;
  if (switching) {
    fromPos = perspCam.position.clone();
    if (!wasEntering) {
      /* Follow sudah settle: anchor eksak = pose follow A. */
      const oldPose = followCamPose();
      if (oldPose) fromAnchor = oldPose.anchor.clone();
    }
    if (!fromAnchor) {
      /* Masih di tengah animasi masuk: anchor dari arah pandang
         kamera saat ini (posisi + arah pandang * jarak follow). */
      const dir = new THREE.Vector3();
      perspCam.getWorldDirection(dir);
      fromAnchor = fromPos.clone().addScaledVector(dir, 4);
    }
  }
  stopCamAnim();
  /* Simpan overview saat ini supaya exitFollow bisa zoom out mulus
     kembali ke framing yang sama. JANGAN timpa saat pindah antar agen
     atau saat memotong animasi keluar — overview tersimpan harus tetap
     overview ASLI, bukan nilai tengah-tengah animasi. */
  if (!switching && !wasExiting) {
    prevOverview = { camZoom, camPan: { x: camPan.x, z: camPan.z }, azimuth, camElev };
  }
  followName = name;
  followYaw = 0;
  followPitch = 0.32;
  followDist = 4.0;
  /* Follow portrait (Fase 2, port dari Beto msg_0394): kamera lebih jauh +
     lebih mendatar bila aspect < 1. Desktop tetap 0.32 / 4.0. */
  if ((perspCam.aspect || 1.6) < 1) {
    followPitch = 0.25;
    followDist = 6.0;
  }
  followPan = { x: 0, z: 0 };
  cameraMode = 'follow';
  camera = perspCam;
  /* Transisi smooth: masuk baru = terbang dari posisi overview ke
     belakang agen; pindah antar agen = terbang langsung POV -> POV
     (REDUCED = langsung ke pose akhir). */
  animateEnterFollow(fromPos, fromAnchor);
  refreshFollowCard();
  requestRender();
  return true;
}
function exitFollow() {
  if (cameraMode !== 'follow') return false;
  stopCamAnim();
  /* Nama agen disimpan dulu: animasi zoom out mulai dari agen. */
  const name = followName;
  cameraMode = 'overview';
  followName = null;
  camera = orthoCam;
  fitCamera();
  hideFollowCard();
  /* Zoom out smooth ke overview tersimpan (REDUCED = langsung). */
  animateExitFollow(name);
  requestRender();
  return true;
}
function getCameraMode() {
  return cameraMode;
}

/* --- transisi kamera smooth (Rangga 27 Nov 21:12, 22:22, 22:27) ----- */
/* SEMUA transisi kamera smooth, satu easing (~700 ms, easeInOutCubic):
   - masuk follow = terbang mulus dari posisi overview ke belakang agen
     (zoom in);
   - pindah antar agen = terbang LANGSUNG POV -> POV, TANPA zoom out ke
     overview (Rangga 22:27 — "kameranya yg moving");
   - keluar follow = zoom out mulus (ortho zoom + pan) kembali ke
     overview. Zoom out HANYA di sini, bukan saat pindah antar agen.
   REDUCED (prefers-reduced-motion) = transisi instan. Semua
   transisi memakai pola rAF yang sama. */
let prevOverview = null; /* {camZoom, camPan{x,z}, azimuth, camElev} saat enterFollow */
let camAnimRaf = 0;
let camAnim = null; /* {kind: 'enter'|'exit'} */
/* easeInOutCubic sudah ada (dipakai transisi pose) — dipakai ulang
   di sini, jangan dideklarasi dua kali. */
function stopCamAnim() {
  if (camAnimRaf) { cancelAnimationFrame(camAnimRaf); camAnimRaf = 0; }
  camAnim = null;
}
function animateEnterFollow(fromPos, fromAnchor) {
  /* Terbang mulus ke pose follow. Pose target dihitung ulang tiap frame
     (followCamPose) supaya agen yang jalan / drag user selama terbang
     tetap diikuti. Titik awal:
     - masuk baru: posisi overview (ortho, jauh, wide shot) -> zoom in;
     - pindah antar agen: fromPos/fromAnchor yang diteruskan enterFollow
       (posisi + anchor kamera SAAT INI di belakang agen lama) -> terbang
       langsung POV -> POV, TANPA zoom out ke overview (Rangga 22:27). */
  const first = followCamPose();
  if (!first) return;
  if (REDUCED) { updateFollowCamera(); return; }
  if (!fromPos || !fromAnchor) {
    fromPos = orthoCam ? orthoCam.position.clone() : first.pos.clone();
    const b = computePlanBounds();
    fromAnchor = new THREE.Vector3(b.cx + camPan.x, 0, b.cz + camPan.z);
  }
  const fromFov = perspCam.fov;
  /* Terapkan pose awal SEBELUM frame pertama supaya render pertama
     sudah di posisi overview, bukan posisi follow lama. */
  perspCam.position.copy(fromPos);
  perspCam.lookAt(fromAnchor);
  perspCam.updateProjectionMatrix();
  stopCamAnim();
  const t0 = performance.now();
  const dur = 700;
  camAnim = { kind: 'enter' };
  const step = (now) => {
    const pose = followCamPose();
    if (!pose || !camAnim || camAnim.kind !== 'enter') {
      camAnimRaf = 0; camAnim = null;
      updateFollowCamera(); requestRender();
      return;
    }
    const t = Math.min(1, (now - t0) / dur);
    const k = easeInOutCubic(t);
    perspCam.position.lerpVectors(fromPos, pose.pos, k);
    const anchor = new THREE.Vector3().lerpVectors(fromAnchor, pose.anchor, k);
    perspCam.lookAt(anchor);
    perspCam.fov = fromFov + (pose.fov - fromFov) * k;
    perspCam.updateProjectionMatrix();
    requestRender();
    if (t < 1) {
      camAnimRaf = requestAnimationFrame(step);
    } else {
      camAnimRaf = 0; camAnim = null;
      updateFollowCamera();
      requestRender();
    }
  };
  camAnimRaf = requestAnimationFrame(step);
}
function animateExitFollow(agentName) {
  /* Zoom out mulus ke overview: ortho zoom 2.2 (agen besar, dekat)
     -> zoom overview tersimpan; pan dari posisi agen -> pan
     tersimpan. Mulai dari agen supaya frame pertama masih
     menampilkan agen yang baru ditinggalkan. */
  const target = prevOverview || { camZoom, camPan: { x: camPan.x, z: camPan.z }, azimuth, camElev };
  const b = computePlanBounds();
  const pos = agentName ? avatarPos[agentName] : null;
  let fromPan = { x: target.camPan.x, z: target.camPan.z };
  if (pos) {
    fromPan = {
      x: Math.min(b.maxX - b.cx, Math.max(b.minX - b.cx, pos.x - b.cx)),
      z: Math.min(b.maxZ - b.cz, Math.max(b.minZ - b.cz, pos.z - b.cz)),
    };
  }
  const fromZoom = 2.2;
  camZoom = fromZoom;
  camPan.x = fromPan.x;
  camPan.z = fromPan.z;
  azimuth = target.azimuth;
  camElev = target.camElev;
  updateCamera();
  if (REDUCED) {
    camZoom = target.camZoom;
    camPan.x = target.camPan.x;
    camPan.z = target.camPan.z;
    updateCamera();
    return;
  }
  stopCamAnim();
  const t0 = performance.now();
  const dur = 700;
  camAnim = { kind: 'exit' };
  const step = (now) => {
    if (!camAnim || camAnim.kind !== 'exit') { camAnimRaf = 0; camAnim = null; return; }
    const t = Math.min(1, (now - t0) / dur);
    const k = easeInOutCubic(t);
    camZoom = fromZoom + (target.camZoom - fromZoom) * k;
    camPan.x = fromPan.x + (target.camPan.x - fromPan.x) * k;
    camPan.z = fromPan.z + (target.camPan.z - fromPan.z) * k;
    updateCamera();
    requestRender();
    if (t < 1) {
      camAnimRaf = requestAnimationFrame(step);
    } else {
      camAnimRaf = 0; camAnim = null;
      camZoom = target.camZoom;
      camPan.x = target.camPan.x;
      camPan.z = target.camPan.z;
      updateCamera();
      requestRender();
    }
  };
  camAnimRaf = requestAnimationFrame(step);
}

/* AAA-DETAIL-START — Lapis detail + material AAA (Worker D, 0.4.9).
   FRAGMEN — bukan file utuh: disisipkan (splice) ke room3d.js oleh
   koordinator, tepat SEBELUM `function buildScene()`, dan SATU baris
   hook dipanggil di akhir buildScene (lihat SPLICE.md).
   Bergantung pada scope modul room3d.js: THREE, renderer, scene, C,
   place, desks, ROOMS, FLOOR, VOLT. Tanpa import/CDN baru, tanpa
   sentuh pose/lighting/kamera/shadow/loop render. Palet TERANG
   (brighten 21 Nov 2026): semua warna dibaca dari material lama / palet C.
   ANTI-HARDCODE DENAH (layout Worker F berubah): tidak ada satu pun
   koordinat/ukuran denah lama di blok ini — grid + skirting diturunkan
   dari mesh lantai di scene, props meja dari array `desks` (dibangun
   buildDesk dari ROOMS.slots — ruangan baru otomatis ikut), karpet
   dari bbox klaster meja per ruangan, meja pantry dari centroid slot
   pantry, meja kopi lounge dari slot lounge. Yang tersisa sebagai
   konstanta DESAIN (bukan denah): ukuran prop (buku/mug), tinggi
   trim (1,02), step grid 0,5 m, margin karpet. Bila data sumber
   tidak ditemukan (ruangan dihapus/di-rename), bagian itu dilewati
   diam-diam — lihat NOTES.md.
   Anggaran node: +67 (BASE preview 564 -> ~631; batas 800).
   Aman dipanggil sekali; pemanggilan kedua jadi no-op (material
   sudah Standard; env map hanya dipasang bila belum ada). */

/* Saklar env map prosedural (lihat aaaApplyEnvironment). HASIL UJI
   (harness SwiftShader, 20 Nov 2026): env ON tidak terlihat lebih
   baik dari env OFF (screenshot berdampingan nyaris identik —
   ruangan didominasi ambient/hemi/dir), TAPI membuat harness 2-3x
   lebih lambat (241 dtk vs ~75 dtk) dan avatar GLB di HP fallback
   2 dari 2 run (nodeCount 352 vs 631). Karena itu default OFF.
   Fungsi tetap ada + terdokumentasi — koordinator boleh menyalakan
   lagi di perangkat keras nyata (PMREM di GPU asli murah) bila
   pengujian di sana menunjukkan keuntungan visual. */
const AAA_ENV = false;

/* Cache material Standard baru (terpisah dari cache Lambert MAT). */
const AAA_STD = new Map();
function aaaStd(color, roughness, metalness = 0) {
  const key = color + ':' + roughness + ':' + metalness;
  if (!AAA_STD.has(key)) {
    AAA_STD.set(key, new THREE.MeshStandardMaterial({
      color, roughness, metalness, envMapIntensity: 0.4,
    }));
  }
  return AAA_STD.get(key);
}
function aaaBox(w, h, d, color, roughness, metalness = 0) {
  return new THREE.Mesh(new THREE.BoxGeometry(w, h, d), aaaStd(color, roughness, metalness));
}
function aaaCyl(rt, rb, h, color, roughness, metalness = 0, seg = 12) {
  return new THREE.Mesh(new THREE.CylinderGeometry(rt, rb, h, seg), aaaStd(color, roughness, metalness));
}

/* Roughness/metalness PER PERMUKAAN (dibedakan, bukan satu angka).
   Kunci = warna palet C (diperbarui saat brighten 21 Nov 2026 —
   nilai lama 0x333d49/0x2b323c/dll. sudah tidak ada di palet). */
function aaaRoughness(hex) {
  switch (hex) {
    case 0xc99f66: return 0.55; /* meja kayu dipernis */
    case 0xa07d52: return 0.55; /* bangku kayu */
    case 0x9c7c55: return 0.75; /* desk/sofa/rak — cat satin (satu warna, kompromi) */
    case 0x9a8a6f: return 0.7;  /* trim/panelEdge */
    case 0x555555: return 0.35; /* tiang lampu — metal */
    case 0x6b4a2f: return 0.85; /* pot terakota */
    case 0x22c55e: case 0x16a34a: return 0.9; /* tanaman */
    case 0x7a8b7d: return 0.95; /* kursi/sofa — kain */
    case 0xe6dcc8: case 0xa68f6c: case 0xcbb693: return 0.95; /* gang/karpet/tepi karpet — matte */
    case 0xca4f40: case 0x0f766e: case 0xfc7a24:
    case 0xc4b5fd: case 0xf4a7b9: case 0x1e3a8a: return 0.6; /* kemasan camilan — plastik */
    default: return 0.88;       /* lantai/dinding/panel — matte */
  }
}
function aaaMetalness(hex) {
  if (hex === 0x555555) return 0.7;
  if (hex === 0x9a8a6f) return 0.2;
  return 0;
}

/* Bounds lantai DARI MESH LANTAI di scene (bukan FLOOR hardcode).
   Lantai = satu-satunya mesh PlaneGeometry warna C.floor. Fallback
   ke FLOOR bila tidak ketemu. */
function aaaFloorBounds(scene) {
  scene.updateMatrixWorld(true);
  let floor = null;
  scene.traverse((o) => {
    if (floor || !o.isMesh || !o.geometry || o.geometry.type !== 'PlaneGeometry') return;
    if (o.material && o.material.color && o.material.color.getHex() === C.floor) floor = o;
  });
  if (!floor) return { x0: FLOOR.x0, x1: FLOOR.x1, z0: FLOOR.z0, z1: FLOOR.z1, y: 0 };
  const b = new THREE.Box3().setFromObject(floor);
  return { x0: b.min.x, x1: b.max.x, z0: b.min.z, z1: b.max.z, y: b.min.y };
}

/* Ukuran + tinggi permukaan meja DARI GRUP MEJA (bukan angka tetap):
   permukaan = BoxGeometry terlebar di grup (top meja buildDesk). */
function aaaDeskTopSize(group) {
  let top = null;
  group.traverse((o) => {
    if (!o.isMesh || !o.geometry || o.geometry.type !== 'BoxGeometry') return;
    const p = o.geometry.parameters;
    if (!p || typeof p.width !== 'number') return;
    if (!top || p.width > top.geometry.parameters.width) top = o;
  });
  if (!top) return { w: 2.2, d: 0.9, topY: DESK_TOP_Y };
  const p = top.geometry.parameters;
  return { w: p.width, d: p.depth, topY: top.position.y + p.height / 2 };
}

/* Meja dikelompokkan per ruangan: slot meja dicocokkan ke
   ROOMS[roomId].slots (toleransi 0,01 — sama seperti refreshDesks).
   Ini sumber kebenaran yang sama dengan buildDesk, jadi ruangan
   baru Worker F yang mejanya lewat buildDesk OTOMATIS ikut —
   tanpa perlu update daftar nama ruangan di sini. (Catatan:
   isDeskSlot Worker A meng-hardcode 'ruang-kerja' +
   'kantor-rangga' saja, jadi TIDAK dipakai — lihat NOTES.md.) */
function aaaDesksByRoom() {
  const byRoom = new Map();
  for (const d of desks) {
    for (const [roomId, room] of Object.entries(ROOMS)) {
      const hit = (room.slots || []).some((s) =>
        Math.abs(s.x - d.slotX) <= 0.01 && Math.abs(s.z - d.slotZ) <= 0.01);
      if (hit) {
        if (!byRoom.has(roomId)) byRoom.set(roomId, []);
        byRoom.get(roomId).push(d);
        break;
      }
    }
  }
  return byRoom;
}

/* 1. MATERIAL LEBIH KAYA — Lambert -> Standard, warna dipertahankan.
   DIKELUARKAN (jangan disentuh):
   - material avatar GLB (di dalam avatarGroups; GLB juga belum
     dimuat saat hook ini jalan, tapi guard tetap ada),
   - strip volt (color VOLT 0xa3ff00 — dipakai flashFileShelf),
   - material emissive (lampu taman; monitor/TV = MeshBasicMaterial,
     memang bukan Lambert jadi lolos otomatis),
   - badan monitor/stand/TV (0x111111, nyaris hitam — tidak ada
     nilai tambah di-upgrade, dan "monitor emissive" jangan disentuh).
   Material dishare (cache MAT) dikonversi SEKALI via Map dedupe,
   jadi sharing tetap terjaga. envMapIntensity dijaga rendah (0,35)
   supaya palet tetap terang bersih bila env map aktif. */
function upgradeAAAMaterials(scene) {
  const converted = new Map(); /* oldMaterial -> newMaterial */
  const avatarRoots = new Set(Object.values(avatarGroups));
  scene.traverse((o) => {
    if (!o.isMesh || !o.material || !o.material.isMeshLambertMaterial) return;
    /* Lewati apa pun di bawah grup avatar. */
    let p = o;
    while (p) {
      if (avatarRoots.has(p)) return;
      p = p.parent;
    }
    const m = o.material;
    const hex = m.color ? m.color.getHex() : 0;
    if (hex === VOLT) return;               /* strip volt */
    if (hex === 0x111111) return;           /* badan monitor / TV */
    if (m.emissive && m.emissive.getHex() !== 0x000000) return; /* lampu */
    if (converted.has(m)) { o.material = converted.get(m); return; }
    const std = new THREE.MeshStandardMaterial({
      color: m.color ? m.color.clone() : 0xffffff,
      roughness: aaaRoughness(hex),
      metalness: aaaMetalness(hex),
      emissive: m.emissive ? m.emissive.clone() : 0x000000,
      emissiveIntensity: m.emissiveIntensity !== undefined ? m.emissiveIntensity : 1,
      transparent: !!m.transparent,
      opacity: m.opacity !== undefined ? m.opacity : 1,
      envMapIntensity: 0.35,
    });
    converted.set(m, std);
    o.material = std;
  });
}

/* 1b. ENV MAP PROSEDURAL — scene.environment dari scene kecil buatan
   kode (tanpa aset eksternal): softbox hangat di atas, fill dingin
   di samping, aksen volt kecil, lantai gelap. Sekali di buildScene,
   0 node scene. Bila renderer tidak ada / PMREM gagal, lanjut tanpa
   env (try/catch) — ruangan tetap jalan seperti tanpa env.
   Catatan jujur: env map juga menyentuh material Standard GLB avatar
   (envMapIntensity default 1 di material GLB) — env-nya dibuat REDUP
   supaya efeknya lembut, bukan wash-out. Verifikasi visual di
   screenshot: bila avatar terlihat lebih buruk, set AAA_ENV = false. */
function aaaApplyEnvironment(scene) {
  if (!AAA_ENV || scene.environment) return;
  if (typeof renderer === 'undefined' || !renderer) return;
  try {
    const env = new THREE.Scene();
    env.background = new THREE.Color(0x11141a);
    const warm = new THREE.Mesh(
      new THREE.PlaneGeometry(6, 6),
      new THREE.MeshBasicMaterial({ color: 0xfff1d6 }));
    warm.position.set(0, 5, 1);
    warm.rotation.x = Math.PI / 2; /* menghadap ke bawah */
    env.add(warm);
    const cool = new THREE.Mesh(
      new THREE.PlaneGeometry(8, 4),
      new THREE.MeshBasicMaterial({ color: 0x9db8d6 }));
    cool.position.set(-6, 2, 0);
    cool.rotation.y = Math.PI / 2; /* menghadap +x */
    env.add(cool);
    const volt = new THREE.Mesh(
      new THREE.PlaneGeometry(3, 0.5),
      new THREE.MeshBasicMaterial({ color: 0xa3ff00 }));
    volt.position.set(0, 1, -6); /* aksen volt di utara */
    env.add(volt);
    const fl = new THREE.Mesh(
      new THREE.PlaneGeometry(12, 12),
      new THREE.MeshBasicMaterial({ color: 0x0c0e11 }));
    fl.rotation.x = -Math.PI / 2;
    fl.position.y = -1;
    env.add(fl);
    const pmrem = new THREE.PMREMGenerator(renderer);
    const rt = pmrem.fromScene(env, 0.04);
    scene.environment = rt.texture;
    pmrem.dispose();
    env.traverse((o) => {
      if (o.isMesh) { o.geometry.dispose(); o.material.dispose(); }
    });
  } catch (e) {
    console.warn('AAA env map gagal, lanjut tanpa env:', e);
  }
}

/* 2. DETAIL LANTAI — grid 0,5 m dari bounds lantai (lapis halus di
   bawah grid 1 m BASE — tidak diduplikasi, supaya tidak z-fight),
   ambang pintu tiap ruangan (dari ROOMS[].door), + karpet di bawah
   tiap klaster meja (ruangan dengan >= 2 meja). Karpet tipis
   (y ~0,02, seperti karpet rapat BASE) — avatar berdiri DI ATASNYA,
   slot tidak tertutup: tepi utara karpet berhenti 0,25 sebelum
   baris slot paling utara. */
function addAAAFloorDetail(scene) {
  const fb = aaaFloorBounds(scene);
  /* Grid halus 0,5 m, warna di antara lantai (0xcfa878) dan grid
     1 m (0xa08b6d): terbaca sebagai ubin kecil, tetap sopan. */
  const pts = [];
  for (let x = fb.x0; x <= fb.x1 + 0.001; x += 0.5) pts.push(x, fb.y + 0.005, fb.z0, x, fb.y + 0.005, fb.z1);
  for (let z = fb.z0; z <= fb.z1 + 0.001; z += 0.5) pts.push(fb.x0, fb.y + 0.005, z, fb.x1, fb.y + 0.005, z);
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
  scene.add(new THREE.LineSegments(geo, new THREE.LineBasicMaterial({ color: 0xa08b6d })));

  /* Ambang pintu: strip melintang gang di tiap pintu ruangan. */
  for (const room of Object.values(ROOMS)) {
    if (!room.door) continue;
    scene.add(place(aaaBox(1.8, 0.02, 0.5, C.panelEdge, 0.7), room.door.x, fb.y + 0.025, room.door.z));
  }

  /* Karpet per klaster meja (>= 2 meja di satu ruangan). */
  for (const [, roomDesks] of aaaDesksByRoom()) {
    if (roomDesks.length < 2) continue;
    let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity, minSlotZ = Infinity;
    let w = 2.2, d = 0.9;
    for (const dk of roomDesks) {
      const ts = aaaDeskTopSize(dk.group);
      w = ts.w; d = ts.d;
      minX = Math.min(minX, dk.x); maxX = Math.max(maxX, dk.x);
      minZ = Math.min(minZ, dk.z); maxZ = Math.max(maxZ, dk.z);
      minSlotZ = Math.min(minSlotZ, dk.slotZ);
    }
    const x0 = minX - w / 2 - 0.4, x1 = maxX + w / 2 + 0.4;
    const z0 = minSlotZ + 0.25, z1 = maxZ + d / 2 + 0.4;
    const cx = (x0 + x1) / 2, cz = (z0 + z1) / 2;
    const edge = new THREE.Mesh(
      new THREE.PlaneGeometry(x1 - x0 + 0.3, z1 - z0 + 0.3), aaaStd(0xa68f6c, 0.95));
    edge.rotation.x = -Math.PI / 2;
    edge.position.set(cx, fb.y + 0.018, cz);
    scene.add(edge);
    const rug = new THREE.Mesh(
      new THREE.PlaneGeometry(x1 - x0, z1 - z0), aaaStd(0xcbb693, 0.95));
    rug.rotation.x = -Math.PI / 2;
    rug.position.set(cx, fb.y + 0.022, cz);
    scene.add(rug);
  }
}

/* 3. DETAIL DINDING — skirting di kaki dinding cutaway + garis trim
   horizontal halus, keduanya dari bounds lantai (bukan angka denah).
   Trim di y +1,02 — di bawah semua panel dinding BASE (panel
   terendah mulai y 1,2). Dinding cutaway TETAP: tidak ada dinding
   penuh baru. Kaki sekat diturunkan dari mesh sekat di scene
   (BoxGeometry warna C.divider) — bukan koordinat sekat hardcode. */
function addAAAWallDetail(scene) {
  const fb = aaaFloorBounds(scene);
  const y = fb.y;
  const wLen = (fb.x1 - fb.x0) + 0.6, dLen = (fb.z1 - fb.z0) + 0.6;
  /* Skirting 4 dinding luar (muka dalam dinding). */
  scene.add(place(aaaBox(wLen, 0.14, 0.06, C.grid, 0.9), (fb.x0 + fb.x1) / 2, y + 0.07, fb.z0 + 0.02));
  scene.add(place(aaaBox(0.06, 0.14, dLen, C.grid, 0.9), fb.x0 + 0.02, y + 0.07, (fb.z0 + fb.z1) / 2));
  scene.add(place(aaaBox(0.06, 0.14, dLen, C.grid, 0.9), fb.x1 - 0.02, y + 0.07, (fb.z0 + fb.z1) / 2));
  scene.add(place(aaaBox(wLen, 0.14, 0.06, C.grid, 0.9), (fb.x0 + fb.x1) / 2, y + 0.07, fb.z1 - 0.02));
  /* Trim horizontal (utara/barat/timur saja — dinding selatan rendah). */
  scene.add(place(aaaBox(wLen, 0.05, 0.05, C.panelEdge, 0.7), (fb.x0 + fb.x1) / 2, y + 1.02, fb.z0 + 0.02));
  scene.add(place(aaaBox(0.05, 0.05, dLen, C.panelEdge, 0.7), fb.x0 + 0.02, y + 1.02, (fb.z0 + fb.z1) / 2));
  scene.add(place(aaaBox(0.05, 0.05, dLen, C.panelEdge, 0.7), fb.x1 - 0.02, y + 1.02, (fb.z0 + fb.z1) / 2));
  /* Kaki sekat antar-ruang (dari mesh sekat yang ada di scene). */
  scene.traverse((o) => {
    if (!o.isMesh || !o.geometry || o.geometry.type !== 'BoxGeometry') return;
    if (!o.material || !o.material.color || o.material.color.getHex() !== C.divider) return;
    const b = new THREE.Box3().setFromObject(o);
    const sx = b.max.x - b.min.x, sz = b.max.z - b.min.z;
    scene.add(place(
      aaaBox(sx + 0.06, 0.14, sz + 0.06, C.grid, 0.9),
      (b.min.x + b.max.x) / 2, y + 0.07, (b.min.z + b.max.z) / 2));
  });
}

/* 4. DETAIL PROPS — primitif kode, warna muted, kecil.
   Meja kerja (semua entri `desks` — posisi + tinggi permukaan
   dibaca dari grup meja masing-masing, jadi ikut layout baru):
   tumpukan 3 buku tipis di sudut depan-kiri + 1 mug. Buku di
   z +0,18 (di belakang pelat nama yang di z +0,47 — pelat tetap
   di depan, tidak tertutup dari kamera default tenggara);
   monitor di x +0,25, buku di x -0,72 — tidak menutupi monitor.
   Slot avatar di utara meja (z -1,1), jauh dari props. */
const AAA_BOOK_COLORS = [0x4a3b32, 0x33404d, 0x3d4a3a, 0x54423a, 0x2f3a44];
const AAA_MUG_COLORS = [0x6b5a44, 0x44586b, 0x5a6b4a, 0x715a5a];
function addAAADeskProps(scene) {
  let tableTopY = DESK_TOP_Y; /* fallback = konvensi buildDesk/buildPantry */
  desks.forEach((d, i) => {
    const g = d.group;
    const ts = aaaDeskTopSize(g);
    tableTopY = ts.topY;
    const b1 = AAA_BOOK_COLORS[i % AAA_BOOK_COLORS.length];
    const b2 = AAA_BOOK_COLORS[(i + 2) % AAA_BOOK_COLORS.length];
    const b3 = AAA_BOOK_COLORS[(i + 4) % AAA_BOOK_COLORS.length];
    g.add(place(aaaBox(0.34, 0.035, 0.24, b1, 0.75), -0.72, ts.topY + 0.0175, 0.18));
    g.add(place(aaaBox(0.30, 0.035, 0.22, b2, 0.75), -0.71, ts.topY + 0.0525, 0.17, 0.12));
    g.add(place(aaaBox(0.26, 0.03, 0.20, b3, 0.75), -0.72, ts.topY + 0.085, 0.19, -0.08));
    g.add(place(aaaCyl(0.055, 0.05, 0.11, AAA_MUG_COLORS[i % AAA_MUG_COLORS.length], 0.45), -0.36, ts.topY + 0.055, 0.20));
  });

  /* Meja pantry: tengah meja = centroid slot pantry (meja dikelilingi
     slot di 4 sisi — lihat ROOMS.pantry.slots). 2 cangkir + 1 piring
     di tengah meja, jauh dari kursi di tepi meja. */
  const pn = ROOMS.pantry;
  if (pn && pn.slots && pn.slots.length) {
    const cx = pn.slots.reduce((n, s) => n + s.x, 0) / pn.slots.length;
    const cz = pn.slots.reduce((n, s) => n + s.z, 0) / pn.slots.length;
    scene.add(place(aaaCyl(0.05, 0.045, 0.10, 0xd8d8d0, 0.45), cx - 0.2, tableTopY + 0.05, cz - 0.15));
    scene.add(place(aaaCyl(0.05, 0.045, 0.10, 0x8a7a68, 0.45), cx + 0.2, tableTopY + 0.05, cz + 0.12));
    scene.add(place(aaaCyl(0.13, 0.13, 0.02, 0xcfcfc8, 0.5), cx, tableTopY + 0.01, cz));
  }

  /* Lounge: meja kopi kecil + tumpukan 3 buku, di depan sofa.
     Posisi diturunkan dari slot lounge: tengah-x = rata-rata slot,
     z = 1,6 ke selatan dari baris slot paling utara (sofa berada di
     utara slot di BASE — asumsi ini dicatat di NOTES.md). Karpet
     lounge mengikuti posisi yang sama. Catatan: jalur jalan avatar
     ke slot lounge memang sudah menembus sofa di BASE (tanpa
     collision) — meja ini tidak menambah masalah baru. */
  const lg = ROOMS.lounge;
  if (lg && lg.slots && lg.slots.length) {
    const xs = lg.slots.map((s) => s.x);
    const minSlotZ = Math.min(...lg.slots.map((s) => s.z));
    const cx = (Math.min(...xs) + Math.max(...xs)) / 2;
    const cz = minSlotZ + 1.6;
    const rw = (Math.max(...xs) - Math.min(...xs)) + 1.6;
    const fb = aaaFloorBounds(scene);
    const edge = new THREE.Mesh(new THREE.PlaneGeometry(rw + 0.3, 3.1), aaaStd(0xa68f6c, 0.95));
    edge.rotation.x = -Math.PI / 2;
    edge.position.set(cx, fb.y + 0.018, cz);
    scene.add(edge);
    const rug = new THREE.Mesh(new THREE.PlaneGeometry(rw, 2.8), aaaStd(0xcbb693, 0.95));
    rug.rotation.x = -Math.PI / 2;
    rug.position.set(cx, fb.y + 0.022, cz);
    scene.add(rug);
    scene.add(place(aaaBox(1.6, 0.08, 0.8, 0xc99f66, 0.6), cx, 0.42, cz));
    scene.add(place(aaaBox(0.08, 0.42, 0.7, 0x9c7c55, 0.75), cx - 0.7, 0.21, cz));
    scene.add(place(aaaBox(0.08, 0.42, 0.7, 0x9c7c55, 0.75), cx + 0.7, 0.21, cz));
    scene.add(place(aaaBox(0.34, 0.035, 0.24, 0x33404d, 0.75), cx - 0.2, 0.478, cz));
    scene.add(place(aaaBox(0.30, 0.035, 0.22, 0x4a3b32, 0.75), cx - 0.19, 0.513, cz + 0.01, 0.1));
    scene.add(place(aaaBox(0.26, 0.03, 0.20, 0x3d4a3a, 0.75), cx - 0.2, 0.545, cz - 0.01, -0.06));
  }
}

/* HOOK (satu baris, di akhir buildScene — lihat SPLICE.md):
   upgradeAAAMaterials(scene); aaaApplyEnvironment(scene); addAAAFloorDetail(scene); addAAAWallDetail(scene); addAAADeskProps(scene); */
/* AAA-DETAIL-END */

/* --- bangun ruangan -------------------------------------------- */
function buildScene() {
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0xe8e2d4);
  orthoCam = new THREE.OrthographicCamera(-10, 10, 10, -10, 0.1, 200);
  perspCam = new THREE.PerspectiveCamera(55, 1.6, 0.1, 200);
  camera = orthoCam;
  /* AAA L1 — lighting rig proper, palet TERANG (brighten 21 Nov
     2026): key directional HANGAT dari depan-atas, fill
     hemisphere/ambient HANGAT TERANG, rim directional halus dari
     belakang (pemisah siluet dari dinding — intensitas diturunkan
     supaya dinding pucat tidak kena bias biru). Volt Rangga
     (#a3ff00) harus tetap menyala — jangan kejar terang sampai
     volt mati.
     SHOWCASE OVERRIDE (0.4.9.1-showcase): ruangan publik harus jelas
     di layar HP (umpan balik Rangga: 0.4.9 "gelap kayak blackout",
     mean luminance ~20/255; lalu 21 Nov: "officenya gelap").
     Ambient/hemisphere/key dinaikkan + palet bangunan diterangkan
     di varian ini saja; produksi tetap gelap sampai Maximum Level
     merge — saat re-sync, pakai nilai Maximum Level. */
  scene.add(new THREE.AmbientLight(0xfff3e0, 1.6));
  scene.add(new THREE.HemisphereLight(0xfff6e6, 0x9a8a70, 2.0));
  const dir = new THREE.DirectionalLight(0xffe3c0, 3.4);
  dir.position.set(10, 20, 8);
  scene.add(dir);
  keyLight = dir;
  /* AAA L3 — bayangan nyata dari key light SAJA (map 1024, PCFSoft;
     frustum shadow mengikuti bounds denah data-driven supaya ikut
     floor plan baru Worker F). Bias + normalBias di-tune tanpa acne. */
  dir.castShadow = true;
  dir.shadow.mapSize.set(1024, 1024);
  const sb = computePlanBounds();
  dir.shadow.camera.left = -(sb.w / 2 + 3);
  dir.shadow.camera.right = sb.w / 2 + 3;
  dir.shadow.camera.top = sb.d / 2 + 3;
  dir.shadow.camera.bottom = -(sb.d / 2 + 3);
  dir.shadow.camera.near = 1;
  dir.shadow.camera.far = 60;
  dir.shadow.bias = -0.0004;
  dir.shadow.normalBias = 0.02;
  const rim = new THREE.DirectionalLight(0x7fb2ff, 0.7);
  rim.position.set(-8, 12, -14);
  scene.add(rim);

  /* Lantai + grid + gang — DENAH BESAR 0.4.9 (42x28, gang 2.4):
     lantai x -21..21, z -14..14; gang z -3.2..-0.8 (pusat GANG_Z).
     Sekat utara (panjang 10, pusat z=-9): x -10.5 / 0 / 10.5.
     Sekat selatan (panjang 14, pusat z=7): x -5 / 2 / 9 / 15.
     Celah 0.8 di ujung sekat (z -4..-3.2 utara, z -0.8..0 selatan)
     = pintu tiap ruangan ke gang. */
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(42, 28), mat('floor', C.floor));
  floor.rotation.x = -Math.PI / 2;
  scene.add(floor);
  const gridPts = [];
  for (let x = -21; x <= 21; x++) gridPts.push(x, 0, -14, x, 0, 14);
  for (let z = -14; z <= 14; z++) gridPts.push(-21, 0, z, 21, 0, z);
  const gridGeo = new THREE.BufferGeometry();
  gridGeo.setAttribute('position', new THREE.Float32BufferAttribute(gridPts, 3));
  scene.add(new THREE.LineSegments(gridGeo, new THREE.LineBasicMaterial({ color: C.grid })));
  const gang = new THREE.Mesh(new THREE.PlaneGeometry(42, 2.4), mat('gang', C.gang));
  gang.rotation.x = -Math.PI / 2;
  gang.position.set(0, 0.015, GANG_Z);
  scene.add(gang);
  for (const z of [GANG_Z - 1.22, GANG_Z + 1.22]) {
    scene.add(place(box(42, 0.02, 0.06, C.panelEdge), 0, 0.03, z));
  }

  /* Dinding luar + pemisah antar ruang (rendah, supaya denah
     tetap kebaca dari kamera isometrik). */
  scene.add(place(box(42.6, 2.2, 0.3, C.wall), 0, 1.1, -14.15));      /* utara */
  scene.add(place(box(0.3, 2.2, 28.6, C.wallDark), -21.15, 1.1, 0));   /* barat */
  scene.add(place(box(0.3, 2.2, 28.6, C.wall), 21.15, 1.1, 0));       /* timur */
  /* selatan (rendah) — DIBAGI 27 Nov 2026: celah 2,4 m di sumbu pintu
     kaca (x=-1,5) supaya pintu terbaca sebagai bukaan bersih, tanpa
     sisa tembok di ambang pintu. Segmen barat x -21,3..-2,7 (18,6 m,
     pusat -12,0); segmen timur x -0,3..21,3 (21,6 m, pusat 10,5). */
  scene.add(place(box(18.6, 0.9, 0.3, C.wall), -12.0, 0.45, 14.15));  /* selatan barat */
  scene.add(place(box(21.6, 0.9, 0.3, C.wall), 10.5, 0.45, 14.15));   /* selatan timur */
  scene.add(place(box(0.25, 1.0, 10, C.divider), -10.5, 0.5, -9));     /* kantor | pantry */
  scene.add(place(box(0.25, 1.0, 10, C.divider), 0, 0.5, -9));         /* pantry | lounge */
  scene.add(place(box(0.25, 1.0, 10, C.divider), 10.5, 0.5, -9));      /* lounge | studio */
  scene.add(place(box(0.25, 1.0, 14, C.divider), -5, 0.5, 7));         /* kerja | rapat */
  scene.add(place(box(0.25, 1.0, 14, C.divider), 2, 0.5, 7));          /* rapat | taman */
  scene.add(place(box(0.25, 1.0, 14, C.divider), 9, 0.5, 7));          /* taman | war-room */
  scene.add(place(box(0.25, 1.0, 14, C.divider), 15, 0.5, 7));         /* war-room | lab-ai */

  buildWallPanels();
  buildWorkRoom();
  buildFrontOffice();
  buildInfraScreen();
  buildGlassDoor();
  buildLounge();
  buildPantry();
  buildGarden();
  buildOutdoor();
  buildCity();
  buildHills();
  buildRanggaOffice();
  buildStudioKonten();
  buildWarRoom();
  buildWarRoomProps();
  buildLabAI();
  buildRoomLabels();

  mentionGroup = new THREE.Group();
  handoverGroup = new THREE.Group();
  scene.add(mentionGroup);
  scene.add(handoverGroup);

  /* Blob shadow disiapkan per agen (ellipse gelap, gaya Sims). */
  for (const name of ROOM_ORDER) {
    const g = new THREE.Group();
    const shadow = new THREE.Mesh(
      new THREE.CircleGeometry(0.55, 20),
      new THREE.MeshBasicMaterial({ color: C.shadow, transparent: true, opacity: 0.35 }));
    shadow.rotation.x = -Math.PI / 2;
    shadow.scale.set(1, 0.55, 1);
    shadow.position.y = 0.02;
    g.add(shadow);
    g.visible = false; /* lobby kosong: belum ada data */
    scene.add(g);
    avatarGroups[name] = g;
    avatarPos[name] = null;
    avatarRoom[name] = null;
  }
  /* AAA hook (Worker D, 0.4.9): material + detail lantai/dinding/props. */
  upgradeAAAMaterials(scene); aaaApplyEnvironment(scene); addAAAFloorDetail(scene); addAAAWallDetail(scene); addAAADeskProps(scene);
  /* AAA L3 — mesh Lambert/Standard: meja/props/dinding menjatuhkan
     + menerima bayangan; lantai hanya menerima (tanpa cast supaya
     tidak acne pada bidangnya sendiri). MeshBasic (panel, blob,
     teks) dilewati — tidak ikut shadow. Blob ellipse per agen
     DIPERTAHANKAN (keputusan: bayangan nyata jatuh miring ke
     samping, blob menjaga grounding tepat di bawah avatar — tidak
     dobel-gelap karena opacity blob hanya 0.35). */
  scene.traverse((o) => {
    if (!o.isMesh) return;
    const m = o.material;
    if (!m || m.isMeshBasicMaterial || m.isSpriteMaterial) return;
    o.castShadow = true;
    o.receiveShadow = true;
  });
  floor.castShadow = false;
  updateCamera();
  fitCamera();
}

/* Panel dinding (§5.2): Papan Tugas utara, Rak File barat,
   Papan Pesan timur, Pintu Thread selatan, whiteboard rapat,
   jam dinding (jam asli), poster pixel SMAR. */
function wallPanel(x, y, z, ry, w, h, texObj, action) {
  const g = new THREE.Group();
  const back = box(w + 0.16, h + 0.16, 0.12, C.panel);
  g.add(back);
  /* Strip volt tiap panel punya material SENDIRI (bukan dishare)
     supaya kedip rak file (§5.4.4) tidak ikut mengedipkan panel
     lain. */
  const strip = new THREE.Mesh(
    new THREE.BoxGeometry(0.07, h + 0.16, 0.14),
    new THREE.MeshLambertMaterial({ color: VOLT }));
  strip.position.set(-w / 2 - 0.04, 0, 0);
  g.add(strip);
  g.userData.strip = strip;
  const screen = panelPlane(w, h, texObj);
  screen.position.z = 0.07;
  g.add(screen);
  g.position.set(x, y, z);
  g.rotation.y = ry;
  if (action) {
    g.userData.action = action;
    g.traverse((o) => { o.userData.action = action; clickables.push(o); });
  }
  scene.add(g);
  return g;
}

function buildWallPanels() {
  /* Papan Tugas (utara) — 3 tugas terbuka terbaru. */
  const taskTex = textTexture(512, 256, () => {});
  dynamicPanels.taskBoard = { texObj: taskTex, redraw(tasks, isExample) {
    const g = taskTex.ctx;
    g.fillStyle = '#161b22'; g.fillRect(0, 0, 512, 256);
    g.fillStyle = '#e6e6e6'; g.font = 'bold 30px ui-monospace, monospace';
    g.fillText('PAPAN TUGAS' + (isExample ? ' · contoh' : ''), 20, 42);
    g.font = '24px ui-monospace, monospace'; g.fillStyle = '#9aa0a6';
    tasks.forEach((t, i) => {
      g.fillStyle = '#e6e6e6';
      g.fillText('› ' + trunc(t.title, 34), 20, 92 + i * 52);
      g.fillStyle = '#9aa0a6';
      g.fillText('  ' + t.assignee, 20, 118 + i * 52);
    });
    if (!tasks.length) { g.fillStyle = '#9aa0a6'; g.fillText('Belum ada tugas terbuka.', 20, 92); }
    taskTex.tex.needsUpdate = true;
  } };
  dynamicPanels.taskBoard.redraw([], false);
  wallPanel(-5, 2.3, -13.92, 0, 4.4, 2.2, taskTex, 'tasks');

  /* Whiteboard rapat — nama thread diskusi aktif (data nyata). */
  const wbTex = textTexture(384, 192, () => {});
  dynamicPanels.whiteboard = { texObj: wbTex, redraw(threadId, count, isExample) {
    const g = wbTex.ctx;
    g.fillStyle = '#f5f5f0'; g.fillRect(0, 0, 384, 192);
    g.fillStyle = '#16181c'; g.font = 'bold 26px ui-monospace, monospace';
    g.fillText('WHITEBOARD' + (isExample ? ' · contoh' : ''), 18, 40);
    g.font = '24px ui-monospace, monospace';
    g.fillText('#' + trunc(threadId, 22), 18, 90);
    g.fillStyle = '#555'; g.fillText(count + ' pesan', 18, 130);
    wbTex.tex.needsUpdate = true;
  } };
  dynamicPanels.whiteboard.redraw('blackboard-umum', 0, false);
  /* DIPINDAH 27 Nov 2026 (x 5 -> -0,5): di x 5 tertutup TV dinamis
     (5,25, 2,4) ~85% + TV statis lounge. Posisi baru = di atas
     ruang rapat (x -5..2), jelas dari Papan Tugas (x -7,2..-2,8)
     dan dari TV (x 3,8..6,7). */
  wallPanel(-0.5, 2.3, -13.92, 0, 3.4, 1.8, wbTex, 'thread');

  /* Jam dinding — jam asli (jam client), digambar ulang tiap polling. */
  const clockTex = textTexture(128, 128, () => {});
  dynamicPanels.clock = { texObj: clockTex, redraw() {
    const g = clockTex.ctx;
    const now = new Date();
    g.fillStyle = '#161b22'; g.fillRect(0, 0, 128, 128);
    g.strokeStyle = '#e6e6e6'; g.lineWidth = 4;
    g.beginPath(); g.arc(64, 64, 54, 0, Math.PI * 2); g.stroke();
    const ang = (v, max) => (v / max) * Math.PI * 2 - Math.PI / 2;
    const hand = (a, len, w) => {
      g.strokeStyle = '#a3ff00'; g.lineWidth = w;
      g.beginPath(); g.moveTo(64, 64);
      g.lineTo(64 + Math.cos(a) * len, 64 + Math.sin(a) * len); g.stroke();
    };
    hand(ang(now.getHours() % 12 + now.getMinutes() / 60, 12), 30, 5);
    hand(ang(now.getMinutes(), 60), 44, 3);
    hand(ang(now.getSeconds(), 60), 48, 2);
    clockTex.tex.needsUpdate = true;
  } };
  dynamicPanels.clock.redraw();
  wallPanel(15.75, 3.1, -13.92, 0, 1.1, 1.1, clockTex, null);

  /* Poster pixel maskot SMAR (dekoratif, digambar dari kode). */
  const posterTex = textTexture(256, 256, (g) => {
    g.fillStyle = '#161b22'; g.fillRect(0, 0, 256, 256);
    g.fillStyle = '#a3ff00';
    g.fillRect(58, 70, 140, 110);            /* badan slime */
    g.fillRect(78, 50, 100, 30);             /* kepala */
    g.fillStyle = '#0f1115';
    g.fillRect(88, 66, 18, 18); g.fillRect(150, 66, 18, 18); /* mata */
    g.fillRect(108, 96, 40, 10);             /* mulut */
    g.fillStyle = '#e6e6e6'; g.font = 'bold 22px ui-monospace, monospace';
    g.fillText('SMAR', 96, 220);
  });
  wallPanel(-16, 2.5, -13.92, 0, 2.0, 2.0, posterTex, null);

  /* Rak File (barat) — nama file terbaru. */
  const fileTex = textTexture(384, 256, () => {});
  dynamicPanels.fileShelf = { texObj: fileTex, redraw(files, isExample) {
    const g = fileTex.ctx;
    g.fillStyle = '#161b22'; g.fillRect(0, 0, 384, 256);
    g.fillStyle = '#e6e6e6'; g.font = 'bold 28px ui-monospace, monospace';
    g.fillText('RAK FILE' + (isExample ? ' · contoh' : ''), 18, 40);
    g.font = '22px ui-monospace, monospace'; g.fillStyle = '#9aa0a6';
    files.slice(0, 4).forEach((f, i) => {
      g.fillStyle = '#e6e6e6';
      g.fillText(trunc(f.name, 24), 18, 82 + i * 40);
      g.fillStyle = '#9aa0a6';
      g.fillText(Math.round(f.size_bytes / 1024) + ' KB', 18, 104 + i * 40);
    });
    if (!files.length) { g.fillStyle = '#9aa0a6'; g.fillText('Belum ada file.', 18, 82); }
    fileTex.tex.needsUpdate = true;
  } };
  dynamicPanels.fileShelf.redraw([], false);
  const fileShelfGroup = wallPanel(-20.92, 1.8, 0, Math.PI / 2, 4.4, 2.6, fileTex, 'files');
  dynamicPanels.fileShelf.strip = fileShelfGroup.userData.strip;

  /* Papan Pesan (timur) — 5 pesan terbaru. */
  const msgTex = textTexture(384, 320, () => {});
  dynamicPanels.msgBoard = { texObj: msgTex, redraw(messages, isExample) {
    const g = msgTex.ctx;
    g.fillStyle = '#161b22'; g.fillRect(0, 0, 384, 320);
    g.fillStyle = '#e6e6e6'; g.font = 'bold 28px ui-monospace, monospace';
    g.fillText('PAPAN PESAN' + (isExample ? ' · contoh' : ''), 18, 40);
    g.font = '21px ui-monospace, monospace';
    messages.slice(-5).forEach((m, i) => {
      g.fillStyle = '#a3ff00';
      g.fillText(trunc(m.author, 10) + ':', 18, 82 + i * 44);
      g.fillStyle = '#e6e6e6';
      g.fillText(trunc(m.body, 22), 18, 104 + i * 44);
    });
    if (!messages.length) { g.fillStyle = '#9aa0a6'; g.fillText('Belum ada pesan.', 18, 82); }
    msgTex.tex.needsUpdate = true;
  } };
  dynamicPanels.msgBoard.redraw([], false);
  wallPanel(20.92, 1.8, 0, -Math.PI / 2, 4.4, 3.2, msgTex, 'messages');

  /* Pintu Thread (selatan) — thread + jumlah pesan. */
  const doorTex = textTexture(512, 160, () => {});
  dynamicPanels.threadDoor = { texObj: doorTex, redraw(threadId, count, unread, isExample) {
    const g = doorTex.ctx;
    g.fillStyle = '#161b22'; g.fillRect(0, 0, 512, 160);
    g.fillStyle = '#e6e6e6'; g.font = 'bold 28px ui-monospace, monospace';
    g.fillText('PINTU THREAD' + (isExample ? ' · contoh' : ''), 18, 42);
    g.font = '24px ui-monospace, monospace'; g.fillStyle = '#9aa0a6';
    g.fillText('#' + trunc(threadId, 24) + ' · ' + count + ' pesan', 18, 86);
    g.fillText(unread ? unread + ' belum dibaca' : 'tidak ada yang belum dibaca', 18, 122);
    doorTex.tex.needsUpdate = true;
  } };
  dynamicPanels.threadDoor.redraw('blackboard-umum', 0, 0, false);
  /* DIPINDAH 27 Nov 2026 (x 5,25 -> -13, perintah Rangga: blackboard
     geser ke area workstation). Posisi baru = tengah dinding selatan
     ruang kerja [x -21..-5, pusat -13], menghadap utara ke 9 meja
     kerja (agen duduk menghadap selatan, papan terbaca dari semua
     baris meja). Tidak ada aset dinding lain di bentang ini; jarak
     bersih 2,8 m dari baris meja selatan (z=11,1) + jauh dari
     tanaman front office (-4,5,13). Tetap di dinding selatan
     (pola sama seperti posisi lama) + tetap bisa diklik ('thread'). */
  wallPanel(-13, 1.3, 13.92, Math.PI, 5, 1.6, doorTex, 'thread');

  /* TV Lounge — pesan board terbaru (data nyata). */
  const tvTex = textTexture(512, 256, () => {});
  dynamicPanels.tv = { texObj: tvTex, redraw(tv, isExample) {
    const g = tvTex.ctx;
    g.fillStyle = '#0a0a0a'; g.fillRect(0, 0, 512, 256);
    if (tv) {
      g.fillStyle = '#a3ff00'; g.font = 'bold 26px ui-monospace, monospace';
      g.fillText(trunc(tv.author, 12) + ' · ' + tv.hhmm, 20, 44);
      g.fillStyle = '#e6e6e6'; g.font = '26px ui-monospace, monospace';
      wrapText(g, tv.text, 20, 90, 472, 34);
    } else {
      g.fillStyle = '#555'; g.font = '26px ui-monospace, monospace';
      g.fillText('Belum ada pesan.', 20, 90);
    }
    if (isExample) { g.fillStyle = '#9aa0a6'; g.font = '20px ui-monospace, monospace'; g.fillText('contoh', 20, 232); }
    tvTex.tex.needsUpdate = true;
  } };
  dynamicPanels.tv.redraw(null, false);
  const tvBack = box(2.9, 1.7, 0.12, 0x111111);
  tvBack.position.set(5.25, 2.4, -13.9);
  scene.add(tvBack);
  const tvScreen = panelPlane(2.7, 1.5, tvTex);
  tvScreen.position.set(5.25, 2.4, -13.82);
  scene.add(tvScreen);
}

function wrapText(g, text, x, y, maxW, lh) {
  const words = String(text).split(' ');
  let line = '';
  let yy = y;
  for (const w of words) {
    const test = line ? line + ' ' + w : w;
    if (g.measureText(test).width > maxW && line) {
      g.fillText(line, x, yy);
      line = w;
      yy += lh;
    } else line = test;
  }
  if (line) g.fillText(line, x, yy);
}

/* Meja kerja: permukaan + kaki + pad + monitor (layar judul
   tugas aktif, data nyata) + pelat nama di sisi depan (nama ·
   jumlah tugas · terakhir aktif HH:MM, §5.5). Monitor + pelat
   milik MEJA (tetap di tempat); applyState mengisinya dengan data
   agen yang sedang duduk di slot meja itu (atau redup/kosong bila
   mejanya kosong) — lihat refreshDesks(). */
const desks = []; /* {x, z, slotX, slotZ, monTex, plateTex, group} */
function buildDesk(x, z, w) {
  const g = new THREE.Group();
  /* Meja rendah ala chabudai (Item 3): permukaan DESK_TOP_Y 0.36
     (dulu 0.81) + kaki panel pendek mengikuti. Warna/material sama. */
  const top = box(w, 0.12, 0.9, C.deskTop);
  top.position.y = DESK_TOP_Y - 0.06;
  g.add(top);
  for (const sx of [-w / 2 + 0.08, w / 2 - 0.08]) {
    const leg = box(0.1, DESK_TOP_Y - 0.12, 0.8, C.desk);
    leg.position.set(sx, (DESK_TOP_Y - 0.12) / 2, 0);
    g.add(leg);
  }
  /* Pad lesehan (zabuton) MENGGANTIKAN kursi berkaki (Item 3).
     ROOT CAUSE kursi lama: dudukan di z -0.75 (0.35 di DEPAN slot)
     + sandaran di z -1.05 (0.05 di depan avatar, bukan di belakang)
     sehingga sandaran memotong wajah + dudukan memotong dada avatar
     yang duduk di slot (z -1.1) — terverifikasi visual harness.
     Pad dipusatkan TEPAT di slot (z -1.1) supaya pantat avatar di
     tengah pad; tanpa sandaran, avatar tidak menembus apa pun. */
  const pad = box(0.7, 0.1, 0.7, C.chair);
  pad.position.set(0, PAD_TOP - 0.05, -1.1);
  g.add(pad);
  /* Monitor: layar menghadap AVATAR yang duduk (utara), bukan kamera.
     ROTASI 2026-11-21 (Rangga: "Rotate semua monitornya bro"):
     bodi + layar + dudukan dibungkus SATU subgrup monitor dan diputar
     180° (rotation.y = Math.PI) supaya kode (tekstur, nesting di
     layar) ikut berputar bersama sebagai satu unit. Subgrup diposisikan
     di x=0.25 (sumbu putar = sumbu vertikal monitor sendiri) supaya
     monitor tetap di sisi yang sama (tidak pindah ke x=-0.25 dan
     menabrak tumpukan buku di x=-0.72); hanya z yang berbalik
     (-0.12 -> +0.12) dan layar menghadap utara. Miring layar
     (rotation.x=-0.22, condong ke belakang) tetap benar sesudah
     diputar: atas layar condong ke selatan = menjauhi avatar yang
     melihat dari utara. Konsekuensi yang Rangga terima: kode tidak
     lagi kebaca dari kamera default selatan — kebaca dari utara
     (orbit / follow di belakang avatar). */
  const monGroup = new THREE.Group();
  monGroup.position.set(0.25, 0, 0);
  monGroup.rotation.y = Math.PI;
  const monTex = textTexture(256, 128, () => {});
  const mon = box(1.0, 0.62, 0.06, 0x111111);
  mon.position.set(0, DESK_TOP_Y + 0.31, -0.12);
  mon.rotation.x = -0.22;
  monGroup.add(mon);
  const monScreen = panelPlane(0.92, 0.54, monTex);
  /* Layar NEMPEL di bodi (celah ~0.004, dulu 0.011): dari depan
     layar duduk rapi di bodi, dari samping/belakang tidak tampak
     seperti kartu mengambang; tetap di depan muka bodi supaya
     tidak z-fighting. Posisi y disamakan dengan pusat bodi. */
  monScreen.position.set(0, DESK_TOP_Y + 0.31, -0.086);
  monScreen.rotation.x = -0.22;
  monGroup.add(monScreen);
  const monStand = box(0.08, 0.32, 0.08, 0x111111);
  monStand.position.set(0, DESK_TOP_Y + 0.05, -0.12);
  monGroup.add(monStand);
  g.add(monGroup);
  /* KEYBOARD 2026-11-21 (Rangga: "Tambahin keyboard di mejanya"):
     di atas meja, di depan monitor (yang sudah menghadap utara),
     di antara slot duduk avatar (z=-1.1) dan monitor (z=+0.12):
     pusat z=-0.28, slab 0.62x0.03x0.28 + 3 baris x 8 tombol kecil.
     Warna gelap netral, primitif kode, tanpa tekstur (gaya ruangan).
     Posisi tangan mengetik (pose) mendarat di atas keyboard ini. */
  const kbGroup = new THREE.Group();
  const kbSlab = box(0.62, 0.03, 0.28, 0x2a2a2e);
  kbSlab.position.set(0, DESK_TOP_Y + 0.015, -0.28);
  kbGroup.add(kbSlab);
  for (let r = 0; r < 3; r++) {
    for (let k = 0; k < 8; k++) {
      const key = box(0.055, 0.012, 0.06, 0x3d3d42);
      key.position.set(-0.245 + k * 0.07, DESK_TOP_Y + 0.036, -0.355 + r * 0.075);
      kbGroup.add(key);
    }
  }
  g.add(kbGroup);
  /* Pelat nama di sisi depan meja (menghadap kamera). RATA (tanpa
     miring) dan MUAT di depan meja: pelat 1.7x0.34, kanvas 320x64
     (aspek 5:1) — dulu 1.7x0.42 miring -0.35, ujung atasnya masuk
     ke dalam slab meja (terpotong) dan ujung bawahnya menembus
     lantai; teks baris 2 juga meluber dari kanvas 256 (angka
     terakhir terpotong). Posisi y 0.18 = tengah depan meja 0.36. */
  const plateTex = textTexture(320, 64, () => {});
  const plate = panelPlane(1.7, 0.34, plateTex);
  plate.position.set(0, 0.18, 0.47);
  plate.rotation.x = 0;
  g.add(plate);
  g.position.set(x, 0, z);
  scene.add(g);
  /* Slot avatar yang dilayani meja ini = 1.1 di utara meja. */
  const rec = { x, z, slotX: x, slotZ: z - 1.1, monTex, plateTex, group: g };
  desks.push(rec);
  g.traverse((o) => { o.userData.deskSlot = { x: rec.slotX, z: rec.slotZ }; clickables.push(o); });
  return g;
}

/* --- animasi monitor: mengetik kode (Item 6 punch list, 2026-11-21)
   Layar monitor workspace BUKAN lagi judul tugas statis: monitor di
   meja yang penghuninya sedang bekerja menampilkan kode yang
   "diketik" — baris muncul karakter demi karakter, jendela 5 baris
   bergeser pelan ke atas saat baris baru mulai diketik, kursor blok
   hijau berkedip. Judul tugas nyata tetap kebaca sebagai baris
   komentar paling atas layar. Meja kosong / agen tanpa tugas tetap
   layar redup statis seperti dulu (tidak ada timer, tidak ada
   render). TV + papan dinding TIDAK disentuh — hanya monitor
   buildDesk (semua 12 meja memakai pola yang sama).
   Biaya: SATU interval global 250 ms (bukan rAF, bukan loop 60 fps);
   tiap tick hanya menggambar ulang kanvas 256x128 milik meja yang
   sedang beranimasi + SATU requestRender — dan hanya bila tab
   terlihat, bukan REDUCED, dan ada meja beranimasi. Bila semua meja
   kosong/idle: 0 render/detik dari timer ini. REDUCED
   (prefers-reduced-motion): timer tidak jalan, monitor menampilkan
   satu frame kode penuh yang statis. */
const MONITOR_TICK_MS = 250;
const MONITOR_CHARS_PER_TICK = 2;
const MONITOR_VISIBLE_LINES = 5;
const MONITOR_HOLD_TICKS = 8; /* ~2 dtk tahan frame penuh sebelum ganti snippet */
const MONITOR_FONT = '12px ui-monospace, monospace';
const MONITOR_HEAD_FONT = '12px ui-monospace, monospace';
const MONITOR_CODE_Y0 = 36; /* baseline baris kode pertama */
const MONITOR_CODE_LH = 17; /* jarak antar baris kode */
/* Potongan kode generik yang masuk akal (JS + 1 Python), tiap baris
   maks 30 karakter supaya muat di kanvas 256 px pada font 12 px
   (1 karakter monospace ~7,2 px -> 30 karakter ~217 px + margin 8). */
const MONITOR_SNIPPETS = [
  [
    'const res = await fetch(',
    "  '/api/tasks');",
    'const data = await res.json();',
    'for (const t of data.tasks) {',
    "  if (t.status === 'done')",
    '    continue;',
    '  renderCard(t);',
    '}',
  ],
  [
    'function planWalk(agent) {',
    '  const path = [];',
    '  for (const s of slots) {',
    '    if (s.busy) continue;',
    '    path.push(s);',
    '  }',
    '  return path;',
    '}',
  ],
  [
    'def snapshot_state(agents):',
    '    rows = []',
    '    for a in agents:',
    '        if not a.task:',
    '            continue',
    '        rows.append(a.name)',
    '    return rows',
  ],
  [
    'const open = tasks.filter(',
    '  t => t.open);',
    'open.sort((a, b) =>',
    '  a.priority - b.priority);',
    'const next = open[0];',
    'if (next) assign(next);',
    'console.log(next.id);',
  ],
];
/* Pewarna sintaks sederhana: string #ce9178, keyword #569cd6,
   angka #b5cea8, nama fungsi (kata diikuti '(') #dcdcaa, sisanya
   #d4d4d4. Grup regex: 1=string, 2=keyword, 3=angka, 4=nama fungsi. */
const MON_TOKEN_RE = /('[^'\n]*'|"[^"\n]*")|\b(const|let|var|function|return|if|else|for|of|in|await|async|import|from|class|def|continue|break)\b|\b(\d+)\b|([A-Za-z_$][\w$]*)(?=\()/g;
let monitorTimer = null;

function monitorSnippetStats(idx) {
  const lines = MONITOR_SNIPPETS[idx];
  const offsets = [];
  let off = 0;
  for (const ln of lines) { offsets.push(off); off += ln.length; }
  return { totalChars: off, lineOffsets: offsets };
}

function newMonitorAnim(st, key) {
  let h = 0;
  for (let i = 0; i < st.name.length; i++) h = (h + st.name.charCodeAt(i)) % MONITOR_SNIPPETS.length;
  const stats = monitorSnippetStats(h);
  const a = {
    key,
    title: st.activeTask.title,
    snippetIdx: h,
    typed: 0,
    hold: 0,
    cursorOn: false,
    totalChars: stats.totalChars,
    lineOffsets: stats.lineOffsets,
  };
  if (REDUCED) { a.typed = a.totalChars; a.cursorOn = false; }
  return a;
}

/* Gambar satu baris kode (prefix yang sudah "diketik") dengan warna
   sintaks; mengembalikan x akhir teks (dipakai posisi kursor). */
/* Bungkus teks ke maks `maxLines` baris di batas kata (ukur lebar
   kanvas; font harus sudah di-set sebelum memanggil). Bila teks
   tidak muat, baris terakhir dipotong di batas kata + '…'. JANGAN
   potong tengah kata (judul tugas monitor, 2026-11-21). */
function wrapLines(g, text, maxW, maxLines) {
  const words = String(text).split(' ');
  const lines = [];
  let line = '';
  for (const w of words) {
    const test = line ? line + ' ' + w : w;
    if (g.measureText(test).width > maxW && line) {
      lines.push(line);
      line = w;
    } else line = test;
  }
  if (line) lines.push(line);
  if (lines.length <= maxLines) return lines;
  const out = lines.slice(0, maxLines);
  let last = out[maxLines - 1];
  while (last && g.measureText(last + ' …').width > maxW) {
    const idx = last.lastIndexOf(' ');
    if (idx < 0) { last = ''; break; }
    last = last.slice(0, idx);
  }
  out[maxLines - 1] = last ? last + ' …' : '…';
  return out;
}

function drawMonitorCodeLine(g, text, x, y) {
  g.font = MONITOR_FONT;
  let cx = x;
  let last = 0;
  MON_TOKEN_RE.lastIndex = 0;
  let m;
  while ((m = MON_TOKEN_RE.exec(text)) !== null) {
    if (m.index > last) {
      g.fillStyle = '#d4d4d4';
      const seg = text.slice(last, m.index);
      g.fillText(seg, cx, y);
      cx += g.measureText(seg).width;
    }
    const tok = m[0];
    if (m[1] !== undefined) g.fillStyle = '#ce9178';
    else if (m[2] !== undefined) g.fillStyle = '#569cd6';
    else if (m[3] !== undefined) g.fillStyle = '#b5cea8';
    else g.fillStyle = '#dcdcaa';
    g.fillText(tok, cx, y);
    cx += g.measureText(tok).width;
    last = m.index + tok.length;
  }
  if (last < text.length) {
    g.fillStyle = '#d4d4d4';
    const seg = text.slice(last);
    g.fillText(seg, cx, y);
    cx += g.measureText(seg).width;
  }
  return cx;
}

function drawMonitorFrame(d) {
  const a = d.monAnim;
  if (!a) return;
  const g = d.monTex.ctx;
  const lines = MONITOR_SNIPPETS[a.snippetIdx];
  g.fillStyle = '#0d1a05';
  g.fillRect(0, 0, 256, 128);
  /* Baris komentar = judul tugas nyata, dibungkus ke maks 2 baris
     di batas kata (jangan potong tengah kata). Bila 2 baris, pemisah
     + kode digeser ke bawah supaya tidak tabrakan. */
  g.font = MONITOR_HEAD_FONT;
  g.fillStyle = '#6a9955';
  const titleLines = wrapLines(g, '// ' + a.title, 240, 2);
  let ty = 15;
  for (const tl of titleLines) { g.fillText(tl, 8, ty); ty += 13; }
  const codeY0 = titleLines.length > 1 ? MONITOR_CODE_Y0 + 13 : MONITOR_CODE_Y0;
  g.fillStyle = '#2d333b';
  g.fillRect(8, ty - 8, 240, 1);
  /* Baris yang sedang diketik = baris pertama yang belum penuh;
     bila semua penuh, baris terakhir (kursor di ujung kode). */
  let cur = lines.length - 1;
  for (let i = 0; i < lines.length; i++) {
    if (a.typed < a.lineOffsets[i] + lines[i].length) { cur = i; break; }
  }
  /* Jendela 5 baris: baris aktif selalu jadi baris terbawah, jadi
     jendela bergeser pelan ke atas saat baris baru mulai diketik. */
  const winStart = Math.max(0, cur - (MONITOR_VISIBLE_LINES - 1));
  let cursorX = 8;
  let cursorY = codeY0;
  for (let r = 0; r < MONITOR_VISIBLE_LINES; r++) {
    const li = winStart + r;
    if (li > cur) break;
    const revealed = Math.max(0, Math.min(lines[li].length, a.typed - a.lineOffsets[li]));
    const y = codeY0 + r * MONITOR_CODE_LH;
    const endX = drawMonitorCodeLine(g, lines[li].slice(0, revealed), 8, y);
    if (li === cur) { cursorX = endX; cursorY = y; }
  }
  /* Kursor blok berkedip (periode 500 ms = 2 tick). */
  if (a.cursorOn) {
    g.fillStyle = '#a3ff00';
    g.fillRect(cursorX + 1, cursorY - 11, 7, 13);
  }
  d.monTex.tex.needsUpdate = true;
}

function drawMonitor(texObj, st) {
  const g = texObj.ctx;
  const d = desks.find((dd) => dd.monTex === texObj);
  if (!st || !st.activeTask) {
    /* Meja kosong / tanpa tugas: layar redup STATIS seperti dulu. */
    if (d) d.monAnim = null;
    g.fillStyle = '#111111';
    g.fillRect(0, 0, 256, 128);
    g.font = '22px ui-monospace, monospace';
    g.fillStyle = '#555';
    g.fillText('— layar redup —', 12, 60);
    texObj.tex.needsUpdate = true;
    return;
  }
  if (!d) {
    /* Bukan meja buildDesk (tidak terjadi saat ini): judul statis. */
    g.fillStyle = '#0d1a05';
    g.fillRect(0, 0, 256, 128);
    g.font = '22px ui-monospace, monospace';
    g.fillStyle = '#a3ff00';
    wrapText(g, trunc(st.activeTask.title, 44), 12, 34, 232, 28);
    texObj.tex.needsUpdate = true;
    return;
  }
  /* Penghuni/tugas sama -> lanjutkan ketikan yang sedang berjalan
     (jangan reset tiap refreshDesks/poll 60 dtk); penghuni atau
     judul tugas berubah -> mulai snippet baru dari karakter 0. */
  const key = st.name + '|' + st.activeTask.title;
  if (!d.monAnim || d.monAnim.key !== key) d.monAnim = newMonitorAnim(st, key);
  drawMonitorFrame(d);
}

function startMonitorTimer() {
  if (monitorTimer || REDUCED) return;
  monitorTimer = setInterval(() => {
    if (document.hidden || !state || !renderer || !webglOK) return;
    let changed = false;
    for (const d of desks) {
      const a = d.monAnim;
      if (!a) continue; /* meja kosong / tanpa tugas: tidak digambar */
      a.cursorOn = !a.cursorOn;
      if (a.hold > 0) {
        a.hold--;
        if (a.hold === 0 && a.typed >= a.totalChars) {
          /* Frame penuh sudah ditahan ~2 dtk: ganti snippet. */
          a.snippetIdx = (a.snippetIdx + 1) % MONITOR_SNIPPETS.length;
          const stats = monitorSnippetStats(a.snippetIdx);
          a.typed = 0;
          a.totalChars = stats.totalChars;
          a.lineOffsets = stats.lineOffsets;
        }
      } else if (a.typed < a.totalChars) {
        a.typed = Math.min(a.totalChars, a.typed + MONITOR_CHARS_PER_TICK);
        if (a.typed >= a.totalChars) a.hold = MONITOR_HOLD_TICKS;
      }
      drawMonitorFrame(d);
      changed = true;
    }
    if (changed) requestRender();
  }, MONITOR_TICK_MS);
}

function drawPlate(texObj, name, st) {
  const g = texObj.ctx;
  g.fillStyle = '#161b22'; g.fillRect(0, 0, 320, 64);
  if (!name) {
    g.fillStyle = '#555'; g.font = '20px ui-monospace, monospace';
    g.fillText('— kosong —', 10, 38);
    texObj.tex.needsUpdate = true;
    return;
  }
  g.fillStyle = KNOWN_AGENTS[name].color;
  g.font = 'bold 22px ui-monospace, monospace';
  g.fillText(KNOWN_AGENTS[name].label.toUpperCase() + ' · ' + KNOWN_AGENTS[name].role.toUpperCase(), 10, 26);
  g.fillStyle = '#9aa0a6'; g.font = '20px ui-monospace, monospace';
  const open = st ? st.openCount : 0;
  const last = st ? st.lastActiveLabel : '—';
  g.fillText(open + ' tugas · aktif ' + last, 10, 52);
  texObj.tex.needsUpdate = true;
}

/* --- props ruangan (Tugas 2) -------------------------------------- */
/* Warna tanaman BARU pakai palet brief (0x5a7d4a daun + 0x8a5a3b pot)
   — lebih kalem dari C.plant/C.pot yang sudah ada; tanaman lama
   tidak diubah. Semua props primitif kode, tanpa GLB/texture baru. */
const PROP_LEAF = 0x5a7d4a;
const PROP_POT = 0x8a5a3b;

function buildWorkRoom() {
  /* 9 meja ruang kerja (3 kolom x 3 baris). */
  const slots = ROOMS['ruang-kerja'].slots;
  for (const s of slots) buildDesk(s.x, s.z + 1.1, 2.2);
  /* Tugas 2: isi BEBERAPA meja saja (variasi) — ujung barat meja
     (desk-lokal x=-0.75, z=+0.15), jauh dari monitor (x -0.25..0.75,
     z +0.12) + keyboard (x ±0.31, z -0.42..-0.14). */
  scene.add(place(box(0.5, 0.06, 0.35, 0xca4f40), -19.75, 0.39, 3.25));
  scene.add(place(box(0.45, 0.05, 0.32, 0x0f766e), -19.75, 0.445, 3.25, 0.15));
  scene.add(place(cyl(0.06, 0.05, 0.12, 0xfc7a24), -13.75, 0.42, 7.25));
  scene.add(place(cyl(0.09, 0.07, 0.12, PROP_POT), -7.75, 0.42, 11.25));
  scene.add(place(sph(0.13, PROP_LEAF), -7.75, 0.56, 11.25));
  scene.add(place(box(0.5, 0.06, 0.35, 0x1e3a8a), -7.75, 0.39, 3.25));
  scene.add(place(box(0.42, 0.05, 0.3, 0xf4a7b9), -7.75, 0.445, 3.25, -0.2));
  /* Tanaman sudut utara (isi strip kosong z -0,8..2, jauh dari lane
     x=-9,7 + pintu (-9,7, GANG_Z) + baris meja utara (z=3,1)). */
  for (const [px, pz] of [[-20, 0.5], [-6, 0.5]]) {
    scene.add(place(cyl(0.45, 0.35, 0.5, C.pot), px, 0.25, pz));
    scene.add(place(sph(0.55, C.plant), px, 1.0, pz));
    scene.add(place(sph(0.35, C.plantDark), px + 0.2, 1.45, pz - 0.1));
  }
}

function buildFrontOffice() {
  /* FRONT OFFICE (27 Nov 2026, perintah Rangga: "meja pad dkt pintu
     masuk kosongin, ganti dgn pajangan2 layaknya front office").
     Ruang rapat lama (meja tengah + 4 pad lesehan + karpet besar +
     whiteboard + layar proyektor + gelas) DIHAPUS — ruangan ini tepat
     di balik pintu masuk utama (x=0, z=14), jadi dijadikan area
     sambut tamu: meja resepsionis + papan selamat datang + karpet
     sambut + tanaman + bangku tunggu + papan direktori. Slot agen
     (ROOMS 'ruang-rapat', 4 slot BERDIRI) DIPERTAHANKAN — agen yang
     membalas/@all berkumpul di sini sambil berdiri; tidak ada pad,
     tidak ada yang duduk di atas pajangan. Semua pajangan dijauhkan
     dari keempat slot ((-4.1,7), (1.1,7), (-1.5,4.4), (-1.5,9.6))
     + lane jalan (x=-4.1 / x=1.1). Dinding selatan TIDAK dipakai
     (panel Pintu Thread (0,13.92) milik buildWallPanels — jangan
     tumpang tindih); papan selamat datang menempel di depan meja. */
  /* Meja resepsionis (pusat (-1.5,11.5), menghadap selatan/pintu):
     badan + top overhang + strip volt di depan. */
  scene.add(place(box(2.4, 1.1, 0.9, C.desk), -1.5, 0.55, 11.5));
  scene.add(place(box(2.6, 0.08, 1.0, C.deskTop), -1.5, 1.14, 11.5));
  scene.add(place(box(2.4, 0.06, 0.02, VOLT), -1.5, 0.92, 11.96));
  /* Papan selamat datang di depan meja (menghadap selatan). */
  const welcomeTex = textTexture(512, 128, (g2) => {
    g2.fillStyle = '#161b22'; g2.fillRect(0, 0, 512, 128);
    g2.fillStyle = '#a3ff00'; g2.font = 'bold 46px sans-serif';
    g2.textAlign = 'center'; g2.textBaseline = 'middle';
    g2.fillText('SELAMAT DATANG', 256, 44);
    g2.fillStyle = '#e6e6e6'; g2.font = 'bold 38px sans-serif';
    g2.fillText('NEUGI', 256, 96);
  });
  scene.add(place(panelPlane(2.0, 0.5, welcomeTex), -1.5, 0.58, 11.97));
  /* Pajangan di atas meja: vas + buku + lampu meja. */
  scene.add(place(cyl(0.07, 0.05, 0.22, 0xca4f40), -2.4, 1.29, 11.7));
  scene.add(place(sph(0.06, PROP_LEAF), -2.4, 1.44, 11.7));
  scene.add(place(box(0.3, 0.05, 0.22, 0x1e3a8a), -1.5, 1.205, 11.4));
  scene.add(place(box(0.26, 0.05, 0.2, 0xfc7a24), -1.5, 1.255, 11.4));
  scene.add(place(cyl(0.09, 0.11, 0.05, 0x555555), -0.6, 1.205, 11.7));
  scene.add(place(cyl(0.02, 0.02, 0.3, 0x555555), -0.6, 1.38, 11.7));
  scene.add(place(sph(0.09, C.lamp, { emissive: 0xffd97a, emissiveIntensity: 0.6 }), -0.6, 1.56, 11.7));
  /* Karpet sambut DIPINDAH 27 Nov 2026 (z 10,4 -> 12,7): posisi lama
     ada di sisi STAFF (utara meja), padahal karpet sambut harus di
     sisi PENGUNJUNG (selatan meja, antara pintu kaca dan meja).
     Posisi baru = sumbu front office (x=-1,5), sejajar pintu kaca
     -> karpet -> meja resepsionis. Disempitkan (3,0 -> 2,6) supaya
     tidak menyentuh tiang papan direktori (-3,15,12,8); tidak
     menutupi slot mana pun (slot terdekat (-1,5,9,6) 2,6 m jauhnya). */
  const matEdge = new THREE.Mesh(new THREE.PlaneGeometry(2.6, 1.0), mat('foMatEdge', C.carpetEdge));
  matEdge.rotation.x = -Math.PI / 2;
  matEdge.position.set(-1.5, 0.008, 12.7);
  scene.add(matEdge);
  const matIn = new THREE.Mesh(new THREE.PlaneGeometry(2.4, 0.8), mat('foMat', C.carpet));
  matIn.rotation.x = -Math.PI / 2;
  matIn.position.set(-1.5, 0.012, 12.7);
  scene.add(matIn);
  /* Tanaman sudut selatan (pot + daun) — mengapit pintu masuk.
     Sudut utara SENGAJA kosong: zona masuk dari gang + lane jalan
     (x=-4.1 / x=1.1) lewat di sana, tanaman akan menabrak jalur. */
  for (const [px, pz] of [[-4.5, 13], [1.5, 13]]) {
    scene.add(place(cyl(0.3, 0.24, 0.35, PROP_POT), px, 0.175, pz));
    scene.add(place(sph(0.4, PROP_LEAF), px, 0.7, pz));
    scene.add(place(sph(0.25, PROP_LEAF), px + 0.2, 1.0, pz - 0.1));
  }
  /* Bangku tunggu ramping di dinding barat (menghadap timur) —
     dibuat tipis (duduk 0.35) supaya tidak masuk koridor lane
     barat (x=-4.1, koridor -4.4..-3.8) dan tidak menabrak divider. */
  scene.add(place(box(0.06, 0.7, 2.0, C.bench), -4.82, 0.9, 4.5));
  scene.add(place(box(0.35, 0.12, 2.0, C.bench), -4.65, 0.5, 4.5));
  scene.add(place(box(0.3, 0.5, 0.08, C.bench), -4.65, 0.25, 3.7));
  scene.add(place(box(0.3, 0.5, 0.08, C.bench), -4.65, 0.25, 5.3));
  /* Papan direktori berdiri di dekat pintu (barat jalur masuk):
     NEUGI + arah ruangan (barat=kiri, timur=kanan dari pintu). */
  const dirTex = textTexture(256, 384, (g2) => {
    g2.fillStyle = '#161b22'; g2.fillRect(0, 0, 256, 384);
    g2.fillStyle = '#a3ff00'; g2.font = 'bold 40px sans-serif';
    g2.textAlign = 'center'; g2.textBaseline = 'middle';
    g2.fillText('NEUGI', 128, 44);
    g2.fillStyle = '#e6e6e6'; g2.font = '26px sans-serif';
    g2.fillText('Ruang Kerja  \u2190', 128, 120);
    g2.fillText('Pantry  \u2190', 128, 170);
    g2.fillText('Lab AI  \u2192', 128, 220);
    g2.fillText('Taman  \u2192', 128, 270);
    g2.fillStyle = '#9aa0a6'; g2.font = '22px sans-serif';
    g2.fillText('Front Office', 128, 340);
  });
  scene.add(place(box(0.08, 1.5, 0.08, 0x555555), -3.85, 0.75, 12.8));
  scene.add(place(box(0.08, 1.5, 0.08, 0x555555), -3.15, 0.75, 12.8));
  scene.add(place(panelPlane(0.8, 1.2, dirTex), -3.5, 1.15, 12.8));
}

/* Layar monitor infra di dinding barat Front Office (28 Nov 2026) --
   Rangga: "Layar aja tp yg keren d lobby". Satu layar dinding di
   lobi, ONLY VISUAL, tanpa akses apa pun. Pola layar status War
   Room (panel gelap + bidang canvas) tapi isinya data infra live.
   Posisi: bidang di x=-4,86 (0,01 di depan muka timur sekat x=-5),
   menghadap timur (rotation.y = PI/2); panel belakang di x=-4,92.
   Rentang z 9,4..12,6, y 0,95..2,45 — tidak menyentuh papan
   direktori (-3,5, 12,8), tanaman (-4,5/1,5, 13), slot terdekat
   (-4,1, 10), atau lane x=-4,1. BUKAN objek klik: tanpa
   userData.action/agent/deskSlot, tidak masuk clickables. */
function buildInfraScreen() {
  const texObj = textTexture(INFRA_W, INFRA_H, (g, w, h) => {
    drawInfraScreen(g, w, h, 0);
  });
  const back = box(0.1, 1.66, 3.36, C.panel);
  back.position.set(-4.92, 1.7, 11);
  scene.add(back);
  const screen = panelPlane(3.2, 1.5, texObj);
  screen.position.set(-4.86, 1.7, 11);
  screen.rotation.y = Math.PI / 2;
  scene.add(screen);
  infraScreen = { texObj, lastDrawMs: 0 };
}

/* --- label nama ruangan di lantai (28 Nov 2026) ------------------ */
/* Rangga: list ruangan di page DIHAPUS (halaman kepanjangan) — nama
   ruangan pindah ke label di scene 3D. Satu pelat gelap per ruangan
   (9 ruangan dalam), di lantai tepat di dalam pintu (1,4 m dari
   sumbu pintu ke arah dalam ruangan) — zona masuk yang bebas
   furnitur + slot di semua ruangan (cek harness: tidak ada slot /
   furnitur dalam rect label). Pola sama seperti papan direktori /
   plakat sambutan: textTexture + panelPlane, pelat gelap #161b22 +
   teks terang + garis volt. Pelat 3,0 x 0,75 m, y=0,02 (di atas
   lantai, di bawah kaki avatar) — tidak menghalangi jalan
   (planWalk tidak membaca pelat) dan tidak menutupi slot. Teks
   menghadap selatan (terbaca dari overview default, kamera SE). */
const ROOM_LABELS = [
  { room: 'kantor-rangga', x: -15, z: -3.4 },
  { room: 'ruang-rapat', x: -1.5, z: -0.6 },
  { room: 'lounge', x: 5, z: -3.4 },
  { room: 'studio-konten', x: 16, z: -3.4 },
  { room: 'ruang-kerja', x: -9.7, z: -0.6 },
  { room: 'pantry', x: -5, z: -3.4 },
  { room: 'taman', x: 5.5, z: -0.6 },
  { room: 'war-room', x: 12, z: -0.6 },
  { room: 'lab-ai', x: 18, z: -0.6 },
];
function buildRoomLabels() {
  for (const { room, x, z } of ROOM_LABELS) {
    const label = ROOMS[room] ? ROOMS[room].label : room;
    const tex = textTexture(512, 128, (g2) => {
      g2.fillStyle = '#161b22'; g2.fillRect(0, 0, 512, 128);
      g2.fillStyle = '#e6e6e6'; g2.font = 'bold 58px sans-serif';
      g2.textAlign = 'center'; g2.textBaseline = 'middle';
      g2.fillText(label, 256, 56);
      g2.fillStyle = '#a3ff00'; g2.fillRect(166, 104, 180, 8);
    });
    const plate = panelPlane(3.0, 0.75, tex);
    plate.rotation.x = -Math.PI / 2;
    plate.position.set(x, 0.02, z);
    scene.add(plate);
  }
}

/* PINTU KACA (27 Nov 2026, perintah Rangga: "Pintu gerbang harusnya
   pintu kaca dan sejajar sm layout front office"). Pintu ganda
   (double door) di sumbu front office (x=-1,5 — sejajar meja
   resepsionis + karpet sambut + papan direktori), di bidang
   dinding selatan (z=14). Dua panel kaca transparan + bingkai
   gelap + gagang + strip volt di header. Dinding selatan rendah
   (0,9) — pintu menjulang di atasnya, gaya sama seperti panel
   dinding. Kaca = MeshBasicMaterial (bukan Lambert) supaya tidak
   ikut shadow traverse (kaca transparan tidak boleh menjatuhkan
   bayangan solid) dan tidak dikonversi AAA. Pintu murni dekoratif:
   jalur jalan agen (planWalk) tidak pernah lewat z=14, jadi tidak
   menghalangi gerakan agen. */
function buildGlassDoor() {
  const cx = -1.5, cz = 14.0;
  const W = 2.4, H = 2.2; /* lebar total, tinggi (samakan dinding utara) */
  const postW = 0.08;
  /* Bingkai: 2 tiang samping + header + ambang. */
  scene.add(place(box(postW, H, 0.12, 0x2e2a26), cx - W / 2 + postW / 2, H / 2, cz));
  scene.add(place(box(postW, H, 0.12, 0x2e2a26), cx + W / 2 - postW / 2, H / 2, cz));
  scene.add(place(box(W, 0.1, 0.12, 0x2e2a26), cx, H - 0.05, cz));
  scene.add(place(box(W, 0.06, 0.3, C.panelEdge), cx, 0.03, cz));
  /* Mullion tengah. */
  scene.add(place(box(0.06, H - 0.1, 0.1, 0x2e2a26), cx, H / 2, cz));
  /* Dua panel kaca (transparan, tidak cast shadow). */
  const glassMat = new THREE.MeshBasicMaterial({ color: 0xbfd9e8, transparent: true, opacity: 0.3 });
  for (const s of [-1, 1]) {
    const pane = new THREE.Mesh(new THREE.BoxGeometry(1.08, H - 0.16, 0.04), glassMat);
    pane.position.set(cx + s * 0.6, H / 2, cz);
    scene.add(pane);
  }
  /* Gagang vertikal di dekat tengah (tiap daun, sisi pengunjung). */
  for (const s of [-1, 1]) {
    scene.add(place(cyl(0.025, 0.025, 0.5, 0x555555), cx + s * 0.14, 1.05, cz + 0.06));
  }
  /* Strip volt di header (aksen, selaras meja resepsionis). */
  scene.add(place(box(W - 0.16, 0.04, 0.02, VOLT), cx, H - 0.12, cz + 0.07));
}

function buildLounge() {
  const sofa = new THREE.Group();
  const base = box(3.6, 0.5, 1.3, C.sofa); base.position.y = 0.25; sofa.add(base);
  const back = box(3.6, 0.9, 0.35, C.sofa); back.position.set(0, 0.7, -0.48); sofa.add(back);
  for (const sx of [-1.62, 1.62]) {
    const arm = box(0.35, 0.75, 1.3, C.sofa); arm.position.set(sx, 0.6, 0); sofa.add(arm);
  }
  sofa.position.set(5.25, 0, -12.8);
  scene.add(sofa);
  /* Meja kopi rendah di depan sofa (selatan sofa, utara slot —
     tidak memotong baris jalan slot z=-11.5) + tanaman sudut. */
  const coffee = box(2.0, 0.1, 1.0, C.deskTop);
  coffee.position.set(5.25, 0.45, -10.6);
  scene.add(coffee);
  for (const [lx, lz] of [[4.4, -10.2], [6.1, -10.2], [4.4, -11.0], [6.1, -11.0]]) {
    scene.add(place(box(0.08, 0.45, 0.08, C.desk), lx, 0.225, lz));
  }
  scene.add(place(cyl(0.45, 0.35, 0.5, C.pot), 9.8, 0.25, -13));
  scene.add(place(sph(0.55, C.plant), 9.8, 1.0, -13));
  scene.add(place(sph(0.35, C.plantDark), 10.0, 1.45, -13.1));
  /* Tugas 2: TV di dinding utara di atas sofa (slot lounge menghadap
     selatan ke meja kopi + pusat ruangan, sejak 27 Nov 2026 — dulu
     menghadap utara ke TV/dinding, avatar kelihatan ngadep tembok)
     + mug di meja kopi + rak buku kecil di dinding timur. */
  /* TV statis DIHAPUS 27 Nov 2026: redundan dengan TV dinamis
     (5,25, 2,4, tampil pesan board terbaru) dan layar statisnya
     menutupi bagian bawah TV dinamis + whiteboard rapat. */
  scene.add(place(cyl(0.06, 0.05, 0.12, 0xfc7a24), 4.7, 0.56, -10.6));
  scene.add(place(cyl(0.06, 0.05, 0.12, 0x0f766e), 5.8, 0.56, -10.6));
  /* Karpet area duduk (27 Nov 2026): di bawah sofa + slot lounge,
     tepi selatan karpet (z=-11,3) tidak sampai ke meja kopi
     (z=-11,1) supaya kaki meja tidak menembus karpet. */
  const rugEdge = new THREE.Mesh(new THREE.PlaneGeometry(4.0, 1.8), mat('loungeRugEdge', C.carpetEdge));
  rugEdge.rotation.x = -Math.PI / 2;
  rugEdge.position.set(5.25, 0.008, -12.2);
  scene.add(rugEdge);
  const rugIn = new THREE.Mesh(new THREE.PlaneGeometry(3.8, 1.6), mat('loungeRug', C.carpet));
  rugIn.rotation.x = -Math.PI / 2;
  rugIn.position.set(5.25, 0.012, -12.2);
  scene.add(rugIn);
  scene.add(place(box(0.6, 1.8, 2.0, C.desk), 10.4, 0.9, -6));
  const loungeBooks = [0xfc7a24, 0xc4b5fd, 0xca4f40];
  loungeBooks.forEach((col, i) => {
    scene.add(place(box(0.14, 0.42, 0.32, col), 10.4, 2.01, -6.6 + i * 0.5));
  });
}

function buildPantry() {
  /* Meja pantry + pad (pusat (-5,-9) dari ROOMS). */
  const table = box(2.4, 0.12, 1.4, C.deskTop);
  table.position.set(-5, DESK_TOP_Y - 0.06, -9);
  scene.add(table);
  for (const [lx, lz] of [[-6, -9.5], [-4, -9.5], [-6, -8.5], [-4, -8.5]]) {
    scene.add(place(box(0.1, DESK_TOP_Y - 0.12, 0.1, C.desk), lx, (DESK_TOP_Y - 0.12) / 2, lz));
  }
  /* Pad lesehan di KEEMPAT slot pantry (Item 3) — dipusatkan di slot
     (dulu kursi 0.75 meleset dari slot). */
  scene.add(place(box(0.65, 0.1, 0.65, C.chair), -6.5, PAD_TOP - 0.05, -9));
  scene.add(place(box(0.65, 0.1, 0.65, C.chair), -3.5, PAD_TOP - 0.05, -9));
  scene.add(place(box(0.65, 0.1, 0.65, C.chair), -5, PAD_TOP - 0.05, -10.5));
  scene.add(place(box(0.65, 0.1, 0.65, C.chair), -5, PAD_TOP - 0.05, -7.5));
  /* Meja kopi (counter) + mesin kopi + rak camilan. Rak pindah
     ke z=-5 (dulu z=1.5): rak lama menghalangi lane x=1.3. */
  scene.add(place(box(0.8, 1.0, 6, C.desk), -8.1, 0.5, -9));
  scene.add(place(box(0.5, 0.5, 0.4, 0x111111), -8.1, 1.25, -10.5));
  scene.add(place(cyl(0.12, 0.12, 0.18, 0xf5f5f0), -8.1, 1.15, -9.9));
  const shelf = box(0.7, 2.0, 2.5, C.desk);
  shelf.position.set(-1.9, 1.0, -5);
  scene.add(shelf);
  const snackColors = [0xca4f40, 0x0f766e, 0xfc7a24, 0xc4b5fd, 0xf4a7b9, 0x1e3a8a];
  snackColors.forEach((col, i) => {
    scene.add(place(box(0.5, 0.3, 0.4, col), -1.9, 0.4 + Math.floor(i / 3) * 0.8, -5.8 + (i % 3) * 0.8));
  });
  /* Tugas 2: kulkas kecil di ujung utara counter + microwave di atas
     counter (ujung selatan, jauh dari mesin kopi z=-10.5). */
  scene.add(place(box(0.9, 1.7, 0.8, 0xf5f5f0), -8.3, 0.85, -13.2));
  scene.add(place(box(0.06, 0.5, 0.06, 0x555555), -7.82, 1.0, -13.0));
  scene.add(place(box(0.6, 0.35, 0.4, 0x2a2a2e), -8.1, 1.175, -7.5));
  scene.add(place(box(0.02, 0.25, 0.3, 0x111111), -7.78, 1.18, -7.5));
}

function buildGarden() {
  /* Tanaman (pot + daun bola), bangku, lampu (pusat taman (5.5,7);
     tanaman di 4 sudut ruangan, bangku di selatan, lampu di utara). */
  /* DIPINDAH 27 Nov 2026 (z 13 -> 11, 2 tanaman selatan): daunnya
     menutupi sudut bawah blackboard yang pindah ke x 5,25. */
  for (const [px, pz] of [[3, 1], [8, 1], [3, 11], [8, 11]]) {
    scene.add(place(cyl(0.45, 0.35, 0.5, C.pot), px, 0.25, pz));
    scene.add(place(sph(0.55, C.plant), px, 1.0, pz));
    scene.add(place(sph(0.35, C.plantDark), px + 0.2, 1.45, pz - 0.1));
  }
  const bench = new THREE.Group();
  const seat = box(2.2, 0.12, 0.7, C.bench); seat.position.y = 0.5; bench.add(seat);
  const bback = box(2.2, 0.7, 0.1, C.bench); bback.position.set(0, 0.9, 0.32); bench.add(bback);
  for (const sx of [-0.9, 0.9]) {
    const leg = box(0.1, 0.5, 0.6, C.bench); leg.position.set(sx, 0.25, 0); bench.add(leg);
  }
  bench.position.set(5.5, 0, 12.5);
  scene.add(bench);
  scene.add(place(cyl(0.06, 0.08, 2.2, 0x555555), 5.5, 1.1, 1.5));
  const bulb = sph(0.22, C.lamp, { emissive: 0xffd97a, emissiveIntensity: 0.6 });
  bulb.position.set(5.5, 2.3, 1.5);
  scene.add(bulb);
  /* Tugas 2: klaster bunga di tengah barat/timur (jauh dari slot +
     lane x=4.5) + air mancur kecil di tengah (5.5,7). */
  const flowerColors = [0xf4a7b9, 0xfc7a24, 0xc4b5fd];
  for (const [fx, fz] of [[3, 7], [8, 7]]) {
    flowerColors.forEach((col, i) => {
      const ox = [0, 0.22, -0.2][i];
      const oz = [0, 0.18, 0.2][i];
      scene.add(place(cyl(0.02, 0.02, 0.35, PROP_LEAF), fx + ox, 0.175, fz + oz));
      scene.add(place(sph(0.09, col), fx + ox, 0.4, fz + oz));
    });
  }
  scene.add(place(cyl(0.7, 0.75, 0.25, C.panelEdge), 5.5, 0.125, 7));
  scene.add(place(cyl(0.55, 0.55, 0.06, 0x5b9bd5), 5.5, 0.24, 7));
  scene.add(place(cyl(0.1, 0.12, 0.5, C.panel), 5.5, 0.45, 7));
  scene.add(place(sph(0.14, 0x5b9bd5), 5.5, 0.75, 7));
}

/* --- ekspansi luar (27 Nov 2026, perintah Rangga: BILLBOARD) ---- */
/* Halaman + parkir + jalan di selatan kantor (z > 14.15), dengan
   2 billboard besar (NEUGI + webiz.id) di trotoar antara parkir
   dan jalan, dan mobil lalu lalang di jalan. Semua di luar denah
   dalam (z -14..14) — tidak menimpa objek yang sudah ada.
   Billboard = papan 3D (box + tiang + footing) + logo sebagai
   tekstur di kedua sisi, logo dipakai APA ADANYA dari aset repo
   (bukan digambar ulang, bukan hasil image-to-3D — lihat catatan
   di bawah buildBillboard). Satu aksen kuat tetap volt. */
let trafficCars = [];
let trafficTimer = 0;
let trafficLast = 0;

function buildCar(color) {
  /* Mobil simpel (box + kabin + 4 roda + lampu). Depan = +x. */
  const g = new THREE.Group();
  const body = box(4.0, 0.6, 1.8, color);
  body.position.y = 0.75; g.add(body);
  const cabin = box(2.0, 0.55, 1.6, 0x2a2f33);
  cabin.position.set(-0.2, 1.3, 0); g.add(cabin);
  const wheelGeo = new THREE.CylinderGeometry(0.32, 0.32, 0.25, 10);
  const wheelMat = mat('wheel', 0x1a1a1a);
  for (const [wx, wz] of [[1.35, 0.85], [1.35, -0.85], [-1.35, 0.85], [-1.35, -0.85]]) {
    const w = new THREE.Mesh(wheelGeo, wheelMat);
    w.rotation.x = Math.PI / 2;
    w.position.set(wx, 0.32, wz);
    g.add(w);
  }
  for (const hz of [-0.55, 0.55]) {
    const hl = box(0.08, 0.14, 0.3, 0xffe9a8, { emissive: 0xffd97a, emissiveIntensity: 0.8 });
    hl.position.set(2.0, 0.75, hz); g.add(hl);
    const tl = box(0.08, 0.14, 0.3, 0xca4f40, { emissive: 0xca4f40, emissiveIntensity: 0.6 });
    tl.position.set(-2.0, 0.75, hz); g.add(tl);
  }
  return { group: g };
}

function buildBillboard(x, z, spec) {
  /* Billboard 3D: papan + tiang + footing, logo sebagai tekstur.
     CATATAN METODE (27 Nov 2026): Hunyuan 3D image-to-3D TIDAK
     dipakai di sini — image-to-3D merekonstruksi OBJEK 3D dari
     foto, dan pada logo datar (teks di atas latar hitam) hasilnya
     relief meleleh yang menghancurkan huruf. Billboard yang benar
     adalah papan 3D dengan logo sebagai tekstur: logo tampil
     piksel-sempurna apa adanya (aset repo yang sama dengan logo
     footer), papan + tiang + footing memberi bentuk 3D-nya, tanpa
     biaya GPU dan tanpa upload GLB biner. */
  const g = new THREE.Group();
  const { w, h, poleH, url } = spec;
  const cy = poleH + h / 2;
  const back = box(w + 0.3, h + 0.3, 0.22, 0x16181c);
  back.position.y = cy; g.add(back);
  const strip = box(w + 0.3, 0.09, 0.24, VOLT);
  strip.position.y = cy + h / 2 + 0.12; g.add(strip);
  const loader = new THREE.TextureLoader();
  const tex = loader.load(url,
    () => requestRender(),
    undefined,
    () => console.warn('Billboard: logo gagal dimuat:', url));
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  const faceMat = new THREE.MeshBasicMaterial({ map: tex });
  const front = new THREE.Mesh(new THREE.PlaneGeometry(w, h), faceMat);
  front.position.set(0, cy, 0.13); g.add(front);
  const backFace = new THREE.Mesh(new THREE.PlaneGeometry(w, h), faceMat);
  backFace.position.set(0, cy, -0.13); backFace.rotation.y = Math.PI; g.add(backFace);
  for (const sx of [-1, 1]) {
    const px = sx * (w / 2 - 0.8);
    const pole = cyl(0.16, 0.2, poleH, 0x555555);
    pole.position.set(px, poleH / 2, 0); g.add(pole);
    const foot = box(0.8, 0.35, 0.8, 0x9a8a6f);
    foot.position.set(px, 0.175, 0); g.add(foot);
  }
  g.position.set(x, 0, z);
  scene.add(g);
  return g;
}

function buildOutdoor() {
  /* Halaman (z 14.3..20) — mozaik rumput + concrete (27 Nov 2026,
     perintah Rangga 22:38) + walkway dari pintu. */
  const yard = new THREE.Mesh(new THREE.PlaneGeometry(42, 5.7), mosaicMat(42, 5.7));
  yard.rotation.x = -Math.PI / 2; yard.position.set(0, 0.01, 17.15); scene.add(yard);
  const walk = new THREE.Mesh(new THREE.PlaneGeometry(3, 5.7), mat('walk', 0xcbb693));
  walk.rotation.x = -Math.PI / 2; walk.position.set(-1.5, 0.02, 17.15); scene.add(walk);
  for (const sx of [-3.0, 0.0]) {
    scene.add(place(box(0.08, 0.02, 5.7, VOLT), sx, 0.03, 17.15));
  }
  /* Kanopi pintu masuk selatan — center x=-1,5 (sumbu pintu kaca),
     BUKAN x=0 (sumbu gerbang/driveway). */
  const canopy = box(6, 0.15, 2.5, 0xefe8d6);
  canopy.position.set(-1.5, 2.7, 15.5); scene.add(canopy);
  const canopyEdge = box(6, 0.06, 0.08, VOLT);
  canopyEdge.position.set(-1.5, 2.7, 16.72); scene.add(canopyEdge);
  for (const sx of [-4.2, 1.2]) {
    scene.add(place(cyl(0.09, 0.09, 2.7, 0x555555), sx, 1.35, 16.5));
  }
  /* Tanaman halaman (gaya taman dalam: pot + bola daun) + 2 pohon. */
  /* Tanaman halaman — simetris terhadap sumbu pintu (x=-1,5). */
  for (const [px, pz] of [[-5.5, 16], [2.5, 16], [-5.5, 19], [2.5, 19]]) {
    scene.add(place(cyl(0.45, 0.35, 0.5, C.pot), px, 0.25, pz));
    scene.add(place(sph(0.55, C.plant), px, 1.0, pz));
  }
  for (const [tx, tz] of [[-19, 18], [19, 18]]) {
    scene.add(place(cyl(0.12, 0.16, 1.4, 0x6b4a2f), tx, 0.7, tz));
    scene.add(place(sph(0.9, C.plant), tx, 1.9, tz));
    scene.add(place(sph(0.6, C.plantDark), tx + 0.3, 2.5, tz));
  }
  /* Parkir (z 20..29) — aspal + garis petak (4 petak tiap sisi). */
  const park = new THREE.Mesh(new THREE.PlaneGeometry(42, 9), mat('park', 0x4a4e54));
  park.rotation.x = -Math.PI / 2; park.position.set(0, 0.01, 24.5); scene.add(park);
  for (const bx of [-20, -17, -14, -11, -8, 8, 11, 14, 17, 20]) {
    scene.add(place(box(0.08, 0.02, 4.5, 0xf5f5f0), bx, 0.02, 22.75));
  }
  /* Trotoar utara + selatan — mozaik rumput + concrete (27 Nov 2026). */
  for (const sz of [29.75, 38.25]) {
    const sw = new THREE.Mesh(new THREE.PlaneGeometry(84, 1.5), mosaicMat(84, 1.5));
    sw.rotation.x = -Math.PI / 2; sw.position.set(0, 0.01, sz); scene.add(sw);
  }
  /* Jalan (z 30.5..37.5) — aspal + garis tepi + marka tengah. */
  const road = new THREE.Mesh(new THREE.PlaneGeometry(84, 7), mat('road', 0x3a3e42));
  road.rotation.x = -Math.PI / 2; road.position.set(0, 0.01, 34); scene.add(road);
  for (const ez of [30.7, 37.3]) {
    scene.add(place(box(84, 0.02, 0.12, 0xf5f5f0), 0, 0.02, ez));
  }
  for (let dx = -40; dx <= 40; dx += 4) {
    scene.add(place(box(2, 0.02, 0.14, 0xf5f5f0), dx, 0.02, 34));
  }
  /* Rambu P di pintu parkir (kanan driveway tengah). */
  const pTex = textTexture(128, 128, (g2) => {
    g2.fillStyle = '#1d4ed8'; g2.fillRect(0, 0, 128, 128);
    g2.fillStyle = '#ffffff'; g2.font = 'bold 84px sans-serif';
    g2.textAlign = 'center'; g2.textBaseline = 'middle';
    g2.fillText('P', 64, 70);
  });
  /* Rambu P di pintu parkir — DIPINDAH 27 Nov 2026 (x 3,5 -> 6,5)
     supaya tidak menabrak pilar gerbang kantor (x ±4,2, z 29,5). */
  const pSign = panelPlane(0.7, 0.7, pTex);
  pSign.position.set(6.5, 2.0, 29.75); scene.add(pSign);
  scene.add(place(cyl(0.06, 0.06, 2.2, 0x555555), 6.5, 1.1, 29.75));
  /* Billboard (logo apa adanya, menghadap jalan/+z). NEUGI 6x4
     (logo 1536x1024 = 1.5:1), webiz 9x2.4 (logo 1129x300).
     Posisi di trotoar (z 29.75), mengapit driveway — TIDAK di
     belakang mobil parkir (mobil parkir digeser ke petak di luar
     bayangan billboard). */
  buildBillboard(-13, 29.75, { url: MODULE_BASE + '../assets/neugi-logo.jpg', w: 6.0, h: 4.0, poleH: 2.4 });
  buildBillboard(13, 29.75, { url: MODULE_BASE + '../assets/webiz-logo.webp', w: 9.0, h: 2.4, poleH: 2.2 });
  /* Mobil parkir (statis, menghadap selatan/aisle). */
  const parked = [
    { x: -18.5, z: 22.75, color: 0xf5f5f0 },
    { x: -9.5, z: 22.75, color: 0x3a3f44 },
    { x: 18.5, z: 22.75, color: 0xca4f40 },
    { x: -12.5, z: 22.75, color: 0x1e3a8a },
    { x: 15.5, z: 22.75, color: 0x0f766e },
  ];
  for (const p of parked) {
    const car = buildCar(p.color);
    car.group.position.set(p.x, 0, p.z);
    car.group.rotation.y = -Math.PI / 2;
    scene.add(car.group);
  }
  /* Mobil lalu lalang (2 lajur, setir kiri Indonesia: lajur utara
     ke timur, lajur selatan ke barat; 1 lajur = 1 kecepatan supaya
     tidak saling kejar). */
  const moving = [
    { x: -30, z: 32.5, dir: 1, speed: 6, color: VOLT },
    { x: 5, z: 32.5, dir: 1, speed: 6, color: 0xf5f5f0 },
    { x: -15, z: 32.5, dir: 1, speed: 6, color: 0x1e3a8a },
    { x: 25, z: 35.5, dir: -1, speed: 5.5, color: 0x3a3f44 },
    { x: -10, z: 35.5, dir: -1, speed: 5.5, color: 0xca4f40 },
    { x: 30, z: 35.5, dir: -1, speed: 5.5, color: 0xf5f5f0 },
  ];
  for (const m of moving) {
    const car = buildCar(m.color);
    car.group.position.set(m.x, 0, m.z);
    if (m.dir < 0) car.group.rotation.y = Math.PI;
    scene.add(car.group);
    trafficCars.push({ group: car.group, dir: m.dir, speed: m.speed });
  }
}

/* --- KOTA SIBUK (27 Nov 2026, perintah Rangga: isi area luar yang
   masih kosong ala kota sibuk. KOREKSI 20:42: TANPA pejalan kaki.
   KOREKSI 21:03: area depan gerbang (seberang jalan) HANYA jalan
   + hamparan rumput/semak — TIDAK ADA gedung; gedung HANYA di
   kiri-kanan kantor. Skyline + toko + halte seberang jalan
   DIHAPUS, diganti hamparan rumput + semak.)
   Elemen: gedung samping (kiri-kanan), gerbang kantor, lampu
   jalan, lampu lalu lintas, zebra cross, hamparan rumput + semak
   seberang jalan, pohon, bangku, tempat sampah, papan nama jalan,
   mobil tambahan. Semua primitif sederhana + material dishare
   (mat()), tanpa aset baru — fasad jendela digambar di canvas
   (0 KB aset). Animasi hemat: lampu lalu lintas ikut loop
   setInterval lalu lintas yang sudah ada (tanpa timer baru);
   hormat document.hidden + prefers-reduced-motion lewat loop itu. */
let trafficLamps = null; /* {red, yellow, green} bahan lampu lalin */
let trafficPhase = 0;
let supercomp = null; /* {leds, flow, strip, screen, lastChase, lastScreenMs} — superkomputer Lab AI (§5.4.6) */

function seededRand(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

function facadeMaterial(w, h, base, seed) {
  /* Fasad gedung: canvas 128x192, jendela menyala kuning hangat,
     sesekali volt (aksen hemat, ~3% jendela). */
  const cols = Math.max(3, Math.round(w / 1.2));
  const rows = Math.max(4, Math.round(h / 1.6));
  const rnd = seededRand(seed);
  const t = textTexture(128, 192, (g2) => {
    g2.fillStyle = base; g2.fillRect(0, 0, 128, 192);
    const cw = 128 / cols, ch = 192 / rows;
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const lit = rnd();
        if (lit < 0.55) g2.fillStyle = '#ffd97a';
        else if (lit < 0.58) g2.fillStyle = '#a3ff00';
        else g2.fillStyle = 'rgba(255,255,255,0.14)';
        g2.fillRect(c * cw + 3, r * ch + 4, cw - 6, ch - 8);
      }
    }
  });
  return new THREE.MeshBasicMaterial({ map: t.tex });
}

function buildCityBuilding(x, z, w, h, d, color, seed, faces) {
  /* Gedung kotak + fasad jendela di sisi yang diminta (n/s/e/w)
     + atap sedikit lebih gelap. */
  const g = new THREE.Group();
  const body = box(w, h, d, color);
  body.position.y = h / 2; g.add(body);
  const roof = box(w + 0.2, 0.25, d + 0.2, 0x2a2f33);
  roof.position.y = h + 0.12; g.add(roof);
  const bases = ['#3a3f44', '#46403a', '#39424a'];
  const fmat = facadeMaterial(w, h, bases[seed % 3], seed);
  const mk = (pw, ph, px, py, pz, ry) => {
    const f = new THREE.Mesh(new THREE.PlaneGeometry(pw, ph), fmat);
    f.position.set(px, py, pz); f.rotation.y = ry; g.add(f);
  };
  if (faces.includes('s')) mk(w, h, 0, h / 2, d / 2 + 0.06, 0);
  if (faces.includes('n')) mk(w, h, 0, h / 2, -d / 2 - 0.06, Math.PI);
  if (faces.includes('e')) mk(d, h, w / 2 + 0.06, h / 2, 0, Math.PI / 2);
  if (faces.includes('w')) mk(d, h, -w / 2 - 0.06, h / 2, 0, -Math.PI / 2);
  g.position.set(x, 0, z);
  scene.add(g);
  return g;
}

function shopSignTex(name, bg, fg) {
  /* Papan nama toko: canvas 320x64, ukuran font menyesuaikan
     panjang nama supaya tidak meluber. */
  const fs = name.length <= 8 ? 36 : name.length <= 11 ? 30 : 25;
  return textTexture(320, 64, (g2) => {
    g2.fillStyle = bg; g2.fillRect(0, 0, 320, 64);
    g2.fillStyle = fg; g2.font = 'bold ' + fs + 'px sans-serif';
    g2.textAlign = 'center'; g2.textBaseline = 'middle';
    g2.fillText(name, 160, 34);
  });
}

function buildKiosk(x, z, name, bodyColor, awningColor, faceDir) {
  /* Kios kecil (3,2 x 2,6 x 3 m): badan + atap + strip volt +
     awning miring + etalase kaca + meja display + papan nama dua
     sisi. faceDir +1 = menghadap +x (sisi barat, ke arah kantor),
     -1 = menghadap -x (sisi timur). */
  const g = new THREE.Group();
  const body = box(3.2, 2.6, 3, bodyColor);
  body.position.y = 1.3; g.add(body);
  const roof = box(3.5, 0.15, 3.3, 0x2a2f33);
  roof.position.y = 2.68; g.add(roof);
  const strip = box(3.5, 0.07, 3.32, VOLT);
  strip.position.y = 2.58; g.add(strip);
  const awn = box(3.0, 0.06, 1.1, awningColor);
  awn.position.set(0, 2.35, 1.85); awn.rotation.x = 0.45; g.add(awn);
  const glass = new THREE.Mesh(new THREE.PlaneGeometry(2.4, 1.0),
    new THREE.MeshBasicMaterial({ color: 0xbfd9e8 }));
  glass.position.set(0, 1.35, 1.53); g.add(glass);
  const table = box(2.2, 0.8, 0.6, C.deskTop);
  table.position.set(0, 0.4, 1.9); g.add(table);
  const sign = shopSignTex(name, '#16181c', '#f3eee2');
  for (const sz of [1, -1]) {
    const s = panelPlane(2.75, 0.55, sign);
    s.position.set(0, 2.15, sz * 1.56);
    if (sz < 0) s.rotation.y = Math.PI;
    g.add(s);
  }
  g.position.set(x, 0, z);
  g.rotation.y = faceDir > 0 ? Math.PI / 2 : -Math.PI / 2;
  scene.add(g);
}

function buildRuko(x, z, name, color1, color2, seed, faceDir) {
  /* Ruko 2 lantai (4,2 x 6,5 x 4 m): lantai dasar toko (etalase
     kaca + pintu + papan nama di antara lantai) + lantai atas
     (fasad jendela menyala) + atap. faceDir sama seperti
     buildKiosk. */
  const g = new THREE.Group();
  const ground = box(4.2, 3.0, 4, color1);
  ground.position.y = 1.5; g.add(ground);
  const upper = box(4.2, 3.2, 4, color2);
  upper.position.y = 4.6; g.add(upper);
  const roof = box(4.4, 0.2, 4.2, 0x2a2f33);
  roof.position.y = 6.3; g.add(roof);
  const glass = new THREE.Mesh(new THREE.PlaneGeometry(3.4, 2.0),
    new THREE.MeshBasicMaterial({ color: 0xbfd9e8 }));
  glass.position.set(0, 1.4, 2.03); g.add(glass);
  const door = box(0.8, 2.0, 0.05, 0x2a2f33);
  door.position.set(-1.3, 1.0, 2.06); g.add(door);
  const sign = shopSignTex(name, '#16181c', '#a3ff00');
  const s = panelPlane(3.5, 0.7, sign);
  s.position.set(0, 2.65, 2.08); g.add(s);
  const fac = new THREE.Mesh(new THREE.PlaneGeometry(4.2, 3.2),
    facadeMaterial(4.2, 3.2, '#3a3f44', seed));
  fac.position.set(0, 4.6, 2.06); g.add(fac);
  g.position.set(x, 0, z);
  g.rotation.y = faceDir > 0 ? Math.PI / 2 : -Math.PI / 2;
  scene.add(g);
}

function buildStreetLamp(x, z, armDir) {
  /* Tiang lampu jalan: lengan mengarah ke jalan (armDir +1 = +z,
     -1 = -z), kepala menyala kuning hangat (emissive). */
  const g = new THREE.Group();
  const pole = cyl(0.07, 0.09, 3.4, 0x3a3f44);
  pole.position.y = 1.7; g.add(pole);
  const arm = box(0.08, 0.08, 0.9, 0x3a3f44);
  arm.position.set(0, 3.35, armDir * 0.45); g.add(arm);
  const head = box(0.5, 0.12, 0.28, 0x2a2f33, { emissive: 0xffd97a, emissiveIntensity: 0.9 });
  head.position.set(0, 3.28, armDir * 0.85); g.add(head);
  g.position.set(x, 0, z);
  scene.add(g);
}

function buildTrafficLight(x, z) {
  /* Lampu lalu lintas di mulut driveway: kepala di kedua sisi
     (menghadap jalan + kantor), 3 lampu per sisi. Bahan lampu
     dishare di trafficLamps supaya siklus hijau-kuning-merah
     cukup ubah 3 warna (di loop startTraffic). */
  const g = new THREE.Group();
  const pole = cyl(0.08, 0.1, 3.4, 0x2a2f33);
  pole.position.y = 1.7; g.add(pole);
  const head = box(0.42, 1.05, 0.42, 0x16181c);
  head.position.y = 3.35; g.add(head);
  const geo = new THREE.SphereGeometry(0.1, 10, 8);
  const ys = [3.68, 3.35, 3.02], keys = ['red', 'yellow', 'green'];
  for (const sz of [1, -1]) {
    ys.forEach((y, i) => {
      const lamp = new THREE.Mesh(geo, trafficLamps[keys[i]]);
      lamp.position.set(0, y, sz * 0.22); g.add(lamp);
    });
  }
  g.position.set(x, 0, z);
  scene.add(g);
}

function buildGate() {
  /* Gerbang kantor di mulut driveway (x 0, z 29,5): 2 pilar +
     balok gapura + papan nama NEUGI. TERBUKA (tanpa daun pintu)
     — mobil + walkway lewat bebas di celah 7,7 m. Pilar di
     x ±4,2 supaya tidak menabrak rambu P (dipindah ke x 6,5)
     dan billboard (x ±13). */
  const g = new THREE.Group();
  for (const sx of [-1, 1]) {
    const foot = box(1.0, 0.3, 1.0, 0x9a8a6f);
    foot.position.set(sx * 4.2, 0.15, 0); g.add(foot);
    const pil = box(0.7, 3.6, 0.7, C.wall);
    pil.position.set(sx * 4.2, 1.8, 0); g.add(pil);
    const cap = box(0.85, 0.18, 0.85, VOLT);
    cap.position.set(sx * 4.2, 3.69, 0); g.add(cap);
  }
  const beam = box(9.1, 0.9, 0.5, 0x2a2f33);
  beam.position.set(0, 4.23, 0); g.add(beam);
  const strip = box(9.1, 0.08, 0.52, VOLT);
  strip.position.set(0, 3.82, 0); g.add(strip);
  const signTex = textTexture(512, 128, (g2) => {
    g2.fillStyle = '#16181c'; g2.fillRect(0, 0, 512, 128);
    g2.fillStyle = '#a3ff00'; g2.font = 'bold 84px sans-serif';
    g2.textAlign = 'center'; g2.textBaseline = 'middle';
    g2.fillText('NEUGI', 256, 68);
  });
  for (const sz of [1, -1]) {
    const sign = panelPlane(3.6, 0.9, signTex);
    sign.position.set(0, 4.23, sz * 0.28);
    if (sz < 0) sign.rotation.y = Math.PI;
    g.add(sign);
  }
  g.position.set(0, 0, 29.5);
  scene.add(g);
}

function buildCityTree(x, z) {
  /* Pohon trotoar (gaya taman dalam: batang + 2 bola daun). */
  const g = new THREE.Group();
  const trunk = cyl(0.12, 0.16, 1.4, 0x6b4a2f);
  trunk.position.y = 0.7; g.add(trunk);
  const c1 = sph(0.9, C.plant);
  c1.position.y = 1.9; g.add(c1);
  const c2 = sph(0.6, C.plantDark);
  c2.position.set(0.3, 2.5, 0); g.add(c2);
  g.position.set(x, 0, z);
  scene.add(g);
}

function buildShrub(x, z, s, color) {
  /* Semak rendah di hamparan rumput: 2 bola pipih (tinggi total
     0,4-0,9 m), warna hijau variasi. Statis, tanpa animasi. */
  const g = new THREE.Group();
  const b1 = sph(0.7 * s, color);
  b1.scale.set(1, 0.55, 1); b1.position.y = 0.35 * s; g.add(b1);
  const b2 = sph(0.45 * s, C.plant);
  b2.scale.set(1, 0.6, 1); b2.position.set(0.3 * s, 0.45 * s, 0.1 * s); g.add(b2);
  g.position.set(x, 0, z);
  scene.add(g);
}

function buildBench(x, z) {
  /* Bangku trotoar menghadap jalan (+z). */
  const g = new THREE.Group();
  const seat = box(1.8, 0.1, 0.5, C.bench);
  seat.position.set(0, 0.45, 0); g.add(seat);
  const back = box(1.8, 0.5, 0.08, C.bench);
  back.position.set(0, 0.75, -0.22); g.add(back);
  for (const sx of [-0.8, 0.8]) {
    const leg = box(0.08, 0.45, 0.45, 0x3a3f44);
    leg.position.set(sx, 0.225, 0); g.add(leg);
  }
  g.position.set(x, 0, z);
  scene.add(g);
}

function buildBin(x, z) {
  const b = cyl(0.25, 0.22, 0.6, 0x3a3f44);
  b.position.set(x, 0.3, z);
  scene.add(b);
}

function buildStreetSign(x, z) {
  /* Papan nama jalan JL. NEUGI (kedua sisi). */
  const pole = cyl(0.06, 0.06, 2.8, 0x555555);
  pole.position.set(x, 1.4, z); scene.add(pole);
  const t = textTexture(256, 96, (g2) => {
    g2.fillStyle = '#166534'; g2.fillRect(0, 0, 256, 96);
    g2.fillStyle = '#ffffff'; g2.font = 'bold 44px sans-serif';
    g2.textAlign = 'center'; g2.textBaseline = 'middle';
    g2.fillText('JL. NEUGI', 128, 50);
  });
  for (const sz of [1, -1]) {
    const s = panelPlane(1.3, 0.49, t);
    s.position.set(x, 2.55, z + sz * 0.06);
    if (sz < 0) s.rotation.y = Math.PI;
    scene.add(s);
  }
}

function buildCity() {
  /* Tanah dasar kota (y -0,01, DI BAWAH lantai kantor y=0 dan
     bidang luar y 0,01-0,02 — hanya tampil di area kosong:
     samping kantor + seberang jalan + belakang kantor sampai
     z -50, tempat perbukitan). Mozaik rumput + concrete
     (27 Nov 2026, perintah Rangga 22:38). */
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(140, 120), mosaicMat(140, 120));
  ground.rotation.x = -Math.PI / 2;
  ground.position.set(0, -0.01, 10);
  scene.add(ground);

  /* Hamparan rumput seberang jalan (KOREKSI 21:03: depan gerbang
     HANYA jalan + rumput/semak, tanpa gedung). Bidang mozaik
     rumput + concrete z 39..56 (27 Nov 2026, perintah Rangga
     22:38; di selatan trotoar seberang z 38,25, y 0,005 — di atas
     tanah dasar y -0,01, tidak menabrak trotoar y 0,01)
     + 28 semak rendah tersebar; koridor x -3..3 dibiarkan kosong
     supaya sumbu driveway/gerbang tetap terbuka. */
  const field = new THREE.Mesh(new THREE.PlaneGeometry(72, 17), mosaicMat(72, 17));
  field.rotation.x = -Math.PI / 2;
  field.position.set(0, 0.005, 47.5);
  scene.add(field);
  const shrubRnd = seededRand(77);
  const shrubCols = [C.plantDark, 0x6f8f5f, 0x5d7d52];
  for (const [sx, sz] of [[-32, 42], [-24, 42], [-16, 42], [-8, 42], [8, 42], [16, 42], [24, 42], [32, 42], [-28, 46], [-20, 46], [-12, 46], [12, 46], [20, 46], [28, 46], [-34, 50], [-26, 50], [-18, 50], [-10, 50], [10, 50], [18, 50], [26, 50], [34, 50], [-30, 54], [-22, 54], [-14, 54], [14, 54], [22, 54], [30, 54]]) {
    buildShrub(sx, sz, 0.6 + shrubRnd() * 0.5, shrubCols[Math.floor(shrubRnd() * 3)]);
  }

  /* Gedung samping kantor (membingkai denah dari timur-barat). */
  buildCityBuilding(-27, 4, 6, 8, 5, 0x8a7f70, 301, 'nsew');
  buildCityBuilding(-27, 16, 6, 6, 5, 0x7a8b7d, 307, 'nsew');
  buildCityBuilding(27, 0, 6, 7, 5, 0x9c8a76, 311, 'nsew');
  buildCityBuilding(27, 20, 6, 9, 5, 0x6e6a63, 317, 'nsew');

  /* Trotoar samping (x ±24..30, z -13..29): alas mozaik rumput +
     concrete (27 Nov 2026) di bawah deretan kios/ruko kiri-kanan
     kantor, menyambung trotoar utara (z 29) tanpa menabrak parkir
     (x ±21) atau bukit (z -16,4). */
  for (const sx of [-1, 1]) {
    const sw = new THREE.Mesh(new THREE.PlaneGeometry(6, 42), mosaicMat(6, 42));
    sw.rotation.x = -Math.PI / 2;
    sw.position.set(sx * 27, 0.005, 8);
    scene.add(sw);
  }

  /* Deretan kios + ruko di kiri-kanan kantor (27 Nov 2026, perintah
     Rangga 21:22: yang belum tinggal bangunan, kios, ruko samping
     kanan-kiri kantor). Semua menghadap ke kantor (fasad ke sumbu
     x 0). Mengisi sela di antara 4 gedung yang sudah ada + ujung
     utara/selatan deret; TIDAK masuk depan gerbang (z > 30) atau
     belakang kantor (z < -14, perbukitan). */
  // Barat (x -27, menghadap +x).
  buildKiosk(-27, -11, 'WARUNG KOPI', 0x9c8a76, VOLT, 1);
  buildRuko(-27, -5, 'TOKO BANGUNAN', 0x8a7f70, 0x7a8b7d, 401, 1);
  buildKiosk(-27, 10, 'WARTEG', 0x7a8b7d, 0x2dd4bf, 1);
  buildRuko(-27, 22, 'APOTEK SEHAT', 0x9c8a76, 0x8a7f70, 407, 1);
  buildKiosk(-27, 27, 'ES TEH', 0xa08b6d, 0xf97316, 1);
  // Timur (x 27, menghadap -x).
  buildRuko(27, -10, 'LAUNDRY', 0x6e6a63, 0x9c8a76, 411, -1);
  buildKiosk(27, -5, 'ROTI BAKAR', 0x8a7f70, 0xea580c, -1);
  buildKiosk(27, 6, 'BUAH SEGAR', 0x7a8b7d, 0x22c55e, -1);
  buildRuko(27, 10.5, 'BARBERSHOP', 0x9c8a76, 0x6e6a63, 417, -1);
  buildKiosk(27, 15, 'PULSA', 0x8a7f70, 0x3b82f6, -1);
  buildKiosk(27, 26, 'SATE AYAM', 0x6e6a63, 0xef4444, -1);

  /* Gerbang kantor. */
  buildGate();

  /* Lampu jalan: trotoar utara (lengan ke jalan/+z) + trotoar
     seberang (lengan ke jalan/-z). Dihindari: billboard x ±13,
     rambu P (x 6,5), gerbang (x ±4,2), bangku (x ±20). */
  for (const x of [-26, -6, 26]) buildStreetLamp(x, 29.75, 1);
  for (const x of [-30, -14, -2, 6, 18, 30]) buildStreetLamp(x, 38.25, -1);

  /* Lampu lalu lintas di mulut driveway (x ±4,5, z 30,8) + zebra
     cross (7 garis, x -3,5..3,5). */
  trafficLamps = {
    red: new THREE.MeshBasicMaterial({ color: 0x3a3a3a }),
    yellow: new THREE.MeshBasicMaterial({ color: 0x3a3a3a }),
    green: new THREE.MeshBasicMaterial({ color: 0x34c759 }),
  };
  trafficPhase = 0;
  buildTrafficLight(-4.5, 30.8);
  buildTrafficLight(4.5, 30.8);
  for (let z = 31; z <= 37; z++) {
    scene.add(place(box(7, 0.02, 0.5, 0xf5f5f0), 0, 0.02, z));
  }

  /* Pohon trotoar seberang (tetap — bagian vegetasi, bukan
     bangunan; di selatan trotoar, tepi utara hamparan rumput). */
  for (const x of [-36, -28, -12, 2, 14, 28, 36]) buildCityTree(x, 39.3);

  /* Bangku trotoar utara + tempat sampah + papan nama jalan. */
  buildBench(-20, 29.75);
  buildBench(20, 29.75);
  buildBin(-8, 29.75);
  buildBin(10, 38.25);
  buildBin(-24, 39.3);
  buildStreetSign(-7, 38.25);
}

/* Perbukitan + hutan di belakang kantor (27 Nov 2026, perintah
   Rangga: isi area belakang yang kosong dengan perbukitan dan
   pohon). Dua deret: dekat RENDAH (tinggi 2,5-3,5 m, tepi selatan
   z -16,4..-16,8 — 2,4 m lebih dari dinding utara kantor z -14,
   supaya tidak menutupi kantor dari sudut default) dan jauh
   TINGGI (5-9 m, puncak mengintip dari balik deret dekat sebagai
   latar). Bukit = 1 bola pipih (SphereGeometry, skala y/z),
   pusat di y=0 jadi hanya kubah atas yang tampil; warna hijau
   tanah redup selaras palet hangat kantor. Pohon duduk DI
   permukaan bukit (y = hillGroundY), bukan melayang/terbenam. */
const HILLS = [
  /* Deret dekat: x, z, r, sx, sy, sz, warna. Tinggi = r*sy. */
  { x: -32, z: -21, r: 7, sx: 1.2, sy: 0.45, sz: 0.6, c: 0x6f8f5f },
  { x: -20, z: -22, r: 8, sx: 1.1, sy: 0.4, sz: 0.65, c: 0x5d7d52 },
  { x: -8, z: -20, r: 6, sx: 1.2, sy: 0.5, sz: 0.6, c: 0x7d9b6a },
  { x: 4, z: -22, r: 8, sx: 1.15, sy: 0.42, sz: 0.65, c: 0x6f8f5f },
  { x: 16, z: -21, r: 7, sx: 1.1, sy: 0.48, sz: 0.6, c: 0x5d7d52 },
  { x: 28, z: -22, r: 8, sx: 1.2, sy: 0.4, sz: 0.65, c: 0x7d9b6a },
  /* Deret jauh (di luar bounds kamera, mengintip dari balik). */
  { x: -36, z: -31, r: 9, sx: 1.2, sy: 0.7, sz: 0.8, c: 0x55794c },
  { x: -24, z: -33, r: 10, sx: 1.15, sy: 0.8, sz: 0.8, c: 0x6f8f5f },
  { x: -10, z: -30, r: 9, sx: 1.2, sy: 0.65, sz: 0.75, c: 0x5d7d52 },
  { x: 4, z: -33, r: 11, sx: 1.1, sy: 0.75, sz: 0.8, c: 0x55794c },
  { x: 18, z: -31, r: 9, sx: 1.2, sy: 0.7, sz: 0.8, c: 0x7d9b6a },
  { x: 32, z: -33, r: 10, sx: 1.15, sy: 0.85, sz: 0.8, c: 0x5d7d52 },
];
/* Tinggi permukaan bukit di (x, z): 0 bila di luar semua kubah. */
function hillGroundY(x, z) {
  let y = 0;
  for (const h of HILLS) {
    const dx = (x - h.x) / h.sx, dz = (z - h.z) / h.sz;
    const q = 1 - (dx * dx + dz * dz) / (h.r * h.r);
    if (q > 0) y = Math.max(y, h.r * h.sy * Math.sqrt(q));
  }
  return y;
}
function buildForestTree(x, z, s) {
  /* Pohon hutan: gaya pohon trotoar (batang + 2 bola daun),
     diperbesar s. Statis, tanpa animasi. */
  const g = new THREE.Group();
  const trunk = cyl(0.12 * s, 0.16 * s, 1.4 * s, 0x6b4a2f);
  trunk.position.y = 0.7 * s; g.add(trunk);
  const c1 = sph(0.9 * s, C.plant);
  c1.position.y = 1.9 * s; g.add(c1);
  const c2 = sph(0.6 * s, C.plantDark);
  c2.position.set(0.3 * s, 2.5 * s, 0); g.add(c2);
  g.position.set(x, hillGroundY(x, z), z);
  scene.add(g);
}
function buildHills() {
  for (const h of HILLS) {
    const m = sph(h.r, h.c);
    m.scale.set(h.sx, h.sy, h.sz);
    m.position.set(h.x, 0, h.z);
    scene.add(m);
  }
  /* 2 pohon per bukit, di lereng atas (radius 0,45r dari pusat),
     sudut beda per bukit supaya tidak berbaris. */
  HILLS.forEach((h, i) => {
    const a1 = 0.6 + i * 0.37, a2 = a1 + 2.4;
    const rr = h.r * 0.45;
    for (const a of [a1, a2]) {
      const tx = h.x + Math.cos(a) * rr * h.sx;
      const tz = h.z + Math.sin(a) * rr * h.sz;
      buildForestTree(tx, tz, i < 6 ? 1.1 + (i % 3) * 0.15 : 1.3 + (i % 3) * 0.2);
    }
  });
  /* 4 pohon di lembah antar bukit (tanah datar, y=0). */
  for (const [x, z, s] of [[-26, -17.5, 1.2], [-2, -18, 1.4], [22, -17.5, 1.2], [34, -19, 1.5]]) {
    buildForestTree(x, z, s);
  }
}

/* Layar status inference superkomputer Lab AI: judul + token/s +
   GPU + bar progres. `t` = performance.now() — nilai dibuat
   deterministik dari waktu (pseudo-acak stabil), supaya layar
   berubah hidup tanpa state tambahan. */
function drawSupercompScreen(g, w, h, t) {
  const s = Math.floor(t / 500);
  const rnd = seededRand(1234 + s);
  const tok = 96 + Math.floor(rnd() * 64);
  const gpu = 72 + Math.floor(rnd() * 26);
  const pct = Math.floor(((t / 9000) % 1) * 100);
  g.fillStyle = '#0f1115'; g.fillRect(0, 0, w, h);
  g.strokeStyle = '#a3ff00'; g.lineWidth = 4; g.strokeRect(3, 3, w - 6, h - 6);
  g.fillStyle = '#a3ff00'; g.font = 'bold 20px ui-monospace, monospace';
  g.textAlign = 'left'; g.textBaseline = 'middle';
  g.fillText('AI INFERENCE', 12, 18);
  g.fillStyle = '#e6e6e6'; g.font = '16px ui-monospace, monospace';
  g.fillText('TOKENS/S ' + tok, 12, 46);
  g.fillText('GPU ' + gpu + '%', 12, 68);
  g.fillStyle = '#2e2a26'; g.fillRect(12, 86, w - 24, 14);
  g.fillStyle = '#a3ff00'; g.fillRect(12, 86, (w - 24) * pct / 100, 14);
  g.fillStyle = '#9aa0a6'; g.font = '13px ui-monospace, monospace';
  g.fillText('BATCH ' + pct + '%', 12, 114);
}

/* Layar status klaster superkomputer pot lab (28 Nov 2026): sama
   seperti layar utara (TOKENS/S + GPU + BATCH) tapi judul
   "AI CLUSTER" + seed beda supaya angkanya beda dari layar utara.
   Dipakai dua layar di atas rak #3 + #5 (berbagi satu tekstur). */
function drawClusterScreen(g, w, h, t) {
  const s = Math.floor(t / 500);
  const rnd = seededRand(5678 + s);
  const tok = 120 + Math.floor(rnd() * 80);
  const gpu = 68 + Math.floor(rnd() * 30);
  const pct = Math.floor(((t / 11000) % 1) * 100);
  g.fillStyle = '#0f1115'; g.fillRect(0, 0, w, h);
  g.strokeStyle = '#a3ff00'; g.lineWidth = 4; g.strokeRect(3, 3, w - 6, h - 6);
  g.fillStyle = '#a3ff00'; g.font = 'bold 20px ui-monospace, monospace';
  g.textAlign = 'left'; g.textBaseline = 'middle';
  g.fillText('AI CLUSTER', 12, 18);
  g.fillStyle = '#e6e6e6'; g.font = '16px ui-monospace, monospace';
  g.fillText('TOKENS/S ' + tok, 12, 46);
  g.fillText('GPU ' + gpu + '%', 12, 68);
  g.fillStyle = '#2e2a26'; g.fillRect(12, 86, w - 24, 14);
  g.fillStyle = '#a3ff00'; g.fillRect(12, 86, (w - 24) * pct / 100, 14);
  g.fillStyle = '#9aa0a6'; g.font = '13px ui-monospace, monospace';
  g.fillText('BATCH ' + pct + '%', 12, 114);
}

/* Animasi inference superkomputer (dipanggil dari loop lalu lintas
   startTraffic, 50 ms — TANPA timer baru). Hormat document.hidden
   + prefers-reduced-motion lewat loop itu. */
function updateSupercomp(now) {
  if (!supercomp) return;
  /* LED chase: pola berubah tiap 250 ms; hanya ubah warna bila
     pola berganti (hemat render). */
  const chase = Math.floor(now / 250) % 4;
  if (chase !== supercomp.lastChase) {
    supercomp.lastChase = chase;
    const cols = [VOLT, 0xffd97a, 0x0f766e, 0x3a3a3a];
    supercomp.leds.forEach((m, i) => {
      m.color.set(cols[(i + chase) % 4]);
    });
  }
  /* Titik data mengalir turun di muka rak (siklus 2,4 dtk). */
  for (const f of supercomp.flow) {
    const k = ((now / 2400) + f.off) % 1;
    f.mesh.position.y = 1.9 - k * 1.6;
    f.mesh.visible = k < 0.92;
  }
  /* Strip volt berdenyut (MeshBasicMaterial: denyut via warna). */
  const pulse = 0.55 + 0.45 * Math.sin(now / 600);
  supercomp.strip.color.setRGB(0.64 * pulse, 1.0 * pulse, 0);
  /* Layar status: gambar ulang maks tiap 500 ms (layar utara +
     layar klaster pot). */
  if (now - supercomp.lastScreenMs > 500) {
    supercomp.lastScreenMs = now;
    drawSupercompScreen(supercomp.screen.ctx, 256, 128, now);
    supercomp.screen.tex.needsUpdate = true;
    if (supercomp.screen2) {
      drawClusterScreen(supercomp.screen2.ctx, 256, 128, now);
      supercomp.screen2.tex.needsUpdate = true;
    }
  }
}

function startTraffic() {
  /* Loop lalu lintas ringan (pola setInterval heroRotate, 50 ms).
     Hormati tab tersembunyi + prefers-reduced-motion (mobil diam). */
  if (trafficTimer || REDUCED || !trafficCars.length) return;
  trafficLast = performance.now();
  trafficTimer = setInterval(() => {
    if (document.hidden || !renderer || !webglOK) return;
    const now = performance.now();
    const dt = Math.min((now - trafficLast) / 1000, 0.2);
    trafficLast = now;
    for (const c of trafficCars) {
      c.group.position.x += c.dir * c.speed * dt;
      if (c.dir > 0 && c.group.position.x > 44) c.group.position.x = -44;
      if (c.dir < 0 && c.group.position.x < -44) c.group.position.x = 44;
    }
    /* Siklus lampu lalu lintas (4 dtk per fase: hijau-kuning-
       merah). Hanya ubah warna bila fase berganti — render
       tetap 1x per tick seperti biasa. */
    if (trafficLamps) {
      const phase = Math.floor(now / 4000) % 3;
      if (phase !== trafficPhase) {
        trafficPhase = phase;
        trafficLamps.red.color.set(phase === 2 ? 0xff3b30 : 0x3a3a3a);
        trafficLamps.yellow.color.set(phase === 1 ? 0xffcc00 : 0x3a3a3a);
        trafficLamps.green.color.set(phase === 0 ? 0x34c759 : 0x3a3a3a);
      }
    }
    /* Animasi inference superkomputer Lab AI (tanpa timer baru). */
    updateSupercomp(now);
    /* Animasi layar infra lobi — denyut dot/garis + bar aktivitas. */
    updateInfraScreen(now);
    requestRender();
  }, 50);
}

function buildRanggaOffice() {
  /* Meja Rangga dipisah + lebih besar di ujung (utara-barat) —
     DITURUNKAN dari ROOMS['kantor-rangga'].slots[0] (bukan
     hardcode): meja di depan slot avatar Rangga (x, z+1.1). */
  const s0 = ROOMS['kantor-rangga'].slots[0];
  buildDesk(s0.x, s0.z + 1.1, 3.4);
  /* Tugas 2: rak buku di dinding barat (buku di atas rak) + lampu
     meja di ujung barat meja Rangga (desk-lokal x=-1.35, jauh dari
     keyboard/monitor) + tanaman sudut timur-laut + piagam di
     dinding utara. */
  scene.add(place(box(0.6, 1.8, 2.5, C.desk), -20.6, 0.9, -6));
  const shelfBooks = [0xca4f40, 0x0f766e, 0x1e3a8a];
  shelfBooks.forEach((col, i) => {
    scene.add(place(box(0.14, 0.42, 0.32, col), -20.6, 2.01, -6.9 + i * 0.5));
  });
  scene.add(place(cyl(0.09, 0.11, 0.05, 0x555555), -19.35, 0.385, -10.0));
  scene.add(place(cyl(0.025, 0.025, 0.35, 0x555555), -19.35, 0.55, -10.0));
  scene.add(place(cyl(0.07, 0.15, 0.14, C.lamp, { emissive: 0xffd97a, emissiveIntensity: 0.5 }), -19.35, 0.75, -10.0));
  scene.add(place(cyl(0.3, 0.24, 0.35, PROP_POT), -13.8, 0.175, -13.2));
  scene.add(place(sph(0.4, PROP_LEAF), -13.8, 0.7, -13.2));
  scene.add(place(sph(0.25, PROP_LEAF), -13.6, 1.0, -13.3));
  scene.add(place(box(1.0, 0.8, 0.06, C.panelEdge), -16, 1.6, -13.9));
  const frame = new THREE.Mesh(new THREE.PlaneGeometry(0.85, 0.65), new THREE.MeshBasicMaterial({ color: 0xf5f5f0 }));
  scene.add(place(frame, -16, 1.6, -13.81));
  /* Whiteboard di dinding timur (27 Nov 2026, Rangga: isi Kantor
     Rangga) — bingkai + bidang putih menghadap barat; jauh dari
     lane x=-15, baris jalan z=-12, meja Rangga, dan slot (-13,5,-11). */
  scene.add(place(box(0.06, 1.5, 2.5, C.panelEdge), -10.68, 1.5, -8));
  const wbRangga = new THREE.Mesh(
    new THREE.PlaneGeometry(2.3, 1.3),
    new THREE.MeshBasicMaterial({ color: 0xf5f5f0 }));
  wbRangga.position.set(-10.74, 1.5, -8);
  wbRangga.rotation.y = -Math.PI / 2;
  scene.add(wbRangga);
  /* Sudut meeting kecil di tenggara ruangan: meja kecil + 2 pad
     menghadap meja. Jauh dari pintu (-15,-2), lane x=-15, dan
     posisi overflow (-15,18,-4,19). */
  const meetTable = box(1.2, 0.1, 1.2, C.deskTop);
  meetTable.position.set(-12.5, 0.67, -4.5);
  scene.add(meetTable);
  for (const [lx, lz] of [[-12.9, -4.9], [-12.1, -4.9], [-12.9, -4.1], [-12.1, -4.1]]) {
    scene.add(place(box(0.08, 0.72, 0.08, C.desk), lx, 0.36, lz));
  }
  scene.add(place(box(0.65, 0.1, 0.65, C.chair), -13.5, PAD_TOP - 0.05, -4.5));
  scene.add(place(box(0.65, 0.1, 0.65, C.chair), -11.5, PAD_TOP - 0.05, -4.5));
}

/* --- ruangan baru 0.4.9 (Worker F) ------------------------------ */
function buildStudioKonten() {
  /* Meja konten dari slot bermeja (data-driven, seperti
     buildWorkRoom) + ring light primitif + tanaman sudut. */
  const room = ROOMS['studio-konten'];
  for (const s of room.slots) {
    if (s.desk) buildDesk(s.x, s.z + 1.1, 2.2);
  }
  /* Ring light: tiang + cincin (torus) menghadap selatan. */
  scene.add(place(cyl(0.06, 0.09, 1.8, 0x555555), 18.5, 0.9, -9.5));
  const ring = new THREE.Mesh(
    new THREE.TorusGeometry(0.5, 0.05, 10, 24),
    mat('ring', 0xf5f5f0, { emissive: 0xffd97a, emissiveIntensity: 0.4 }));
  ring.position.set(18.5, 1.9, -9.5);
  scene.add(ring);
  /* Tanaman sudut (jauh dari lane x=20). */
  scene.add(place(cyl(0.45, 0.35, 0.5, C.pot), 11.5, 0.25, -13.5));
  scene.add(place(sph(0.55, C.plant), 11.5, 1.0, -13.5));
  scene.add(place(sph(0.35, C.plantDark), 11.7, 1.45, -13.6));
  /* Tugas 2: 2 kamera tripod menghadap slot panggung (15.75,-6.5)
     + mikrofon boom di meja editing + backdrop hijau di utara
     panggung. Tripod di z=-5.5, jauh dari lane x=20 + jalur
     barat ke slot (z=-6.5). */
  const tripod = (tx, tz) => {
    scene.add(place(cyl(0.04, 0.05, 1.5, 0x555555), tx, 0.75, tz));
    for (const a of [0, 2.1, 4.2]) {
      scene.add(place(box(0.5, 0.05, 0.08, 0x555555), tx, 0.03, tz, a));
    }
    scene.add(place(box(0.35, 0.25, 0.3, 0x111111), tx, 1.55, tz));
    const lens = cyl(0.09, 0.09, 0.18, 0x222222);
    lens.rotation.x = Math.PI / 2;
    scene.add(place(lens, tx, 1.55, tz - 0.22));
  };
  tripod(14.5, -5.5);
  tripod(17, -5.5);
  /* Mikrofon boom di ujung timur meja editing (13.5,-9.9) — tiang
     di meja, lengan ke barat, mic menggantung di atas meja
     (jauh dari monitor z=-9.78 + keyboard x 13.19..13.81). */
  scene.add(place(cyl(0.03, 0.03, 0.9, 0x555555), 14.45, 0.81, -10.2));
  scene.add(place(box(0.5, 0.04, 0.04, 0x555555), 14.2, 1.24, -10.2));
  scene.add(place(cyl(0.06, 0.08, 0.18, 0x222222), 13.95, 1.12, -10.2));
  scene.add(place(sph(0.07, 0x555555), 13.95, 1.0, -10.2));
  /* Backdrop hijau di utara panggung (menghadap selatan). */
  scene.add(place(box(0.06, 2.2, 0.06, 0x555555), 14.3, 1.1, -8.4));
  scene.add(place(box(0.06, 2.2, 0.06, 0x555555), 17.2, 1.1, -8.4));
  const backdrop = new THREE.Mesh(new THREE.PlaneGeometry(3.0, 2.2), new THREE.MeshBasicMaterial({ color: C.plant }));
  scene.add(place(backdrop, 15.75, 1.15, -8.4));
  /* Teleprompter di depan slot panggung (27 Nov 2026, Rangga: isi
     Studio) — tiang + layar menghadap selatan ke presenter.
     Posisi z=-8,0 (0,5 m di utara baris jalan z=-7,5) supaya tidak
     menghalangi jalur jalan ke slot panggung; 0,4 m di selatan
     backdrop (z=-8,4). */
  scene.add(place(cyl(0.05, 0.07, 1.4, 0x555555), 15.75, 0.7, -8.0));
  scene.add(place(box(0.3, 0.05, 0.3, 0x555555), 15.75, 0.025, -8.0));
  const tpFrame = box(0.78, 0.53, 0.04, 0x555555);
  tpFrame.position.set(15.75, 1.5, -8.03);
  scene.add(tpFrame);
  const tpScreen = new THREE.Mesh(
    new THREE.PlaneGeometry(0.7, 0.45),
    new THREE.MeshBasicMaterial({ color: 0x16181c }));
  tpScreen.position.set(15.75, 1.5, -8.0);
  scene.add(tpScreen);
  /* Rak properti di dinding barat (27 Nov 2026) — panel belakang +
     3 tingkat, kotak prop warna-warni; jauh dari meja editing,
     tripod, dan jalur barat ke slot. */
  scene.add(place(box(0.08, 2.0, 2.0, C.desk), 10.68, 1.0, -7));
  for (const sy of [0.4, 0.95, 1.5]) {
    scene.add(place(box(0.45, 0.05, 1.9, C.deskTop), 10.95, sy, -7));
  }
  const propColors = [0xca4f40, 0x0f766e, 0xfc7a24, 0xc4b5fd, 0xf4a7b9, 0x1e3a8a];
  propColors.forEach((col, i) => {
    const sy = [0.4, 0.95, 1.5][Math.floor(i / 2)];
    scene.add(place(box(0.35, 0.3, 0.5, col), 10.95, sy + 0.175, -7.6 + (i % 2) * 1.0));
  });
}

function buildWarRoom() {
  /* Meja operasi tengah + papan besar di dinding timur + pad
     utara/selatan saja. Pad barat/timur SENGAJA tidak ada:
     koridor lane di kedua sisi meja (x=9.6 / x=14.3) harus
     tetap lega (LAYOUT.md §5). */
  const table = box(3.2, 0.14, 2.0, C.deskTop);
  table.position.set(12, DESK_TOP_Y - 0.07, 7);
  scene.add(table);
  for (const [lx, lz] of [[10.7, 6.3], [13.3, 6.3], [10.7, 7.7], [13.3, 7.7]]) {
    scene.add(place(box(0.14, DESK_TOP_Y - 0.12, 0.14, C.desk), lx, (DESK_TOP_Y - 0.12) / 2, lz));
  }
  /* Pad lesehan di dua slot utara/selatan (Item 3) — dipusatkan di slot
     (dulu kursi 0.75 meleset). Slot barat/timur tetap tanpa alas:
     koridor lane di kedua sisi meja (x=9.6 / x=14.3) harus tetap lega. */
  scene.add(place(box(0.7, 0.1, 0.7, C.chair), 12, PAD_TOP - 0.05, 4.6));
  scene.add(place(box(0.7, 0.1, 0.7, C.chair), 12, PAD_TOP - 0.05, 9.4));
  /* Tanaman sudut barat-daya (27 Nov 2026): isi sudut kosong,
     jauh dari slot (12,9,4) + lane x=9,6/14,3 + sekat barat. */
  scene.add(place(cyl(0.45, 0.35, 0.5, C.pot), 9.7, 0.25, 13));
  scene.add(place(sph(0.55, C.plant), 9.7, 1.0, 13));
  scene.add(place(sph(0.35, C.plantDark), 9.9, 1.45, 12.9));
  /* Papan besar menempel sekat timur (x=15) + bidang putih. */
  scene.add(place(box(0.1, 2.2, 4.5, C.panel), 14.82, 1.6, 7));
  const board = new THREE.Mesh(
    new THREE.PlaneGeometry(4.3, 2.0),
    new THREE.MeshBasicMaterial({ color: 0xf5f5f0 }));
  board.position.set(14.76, 1.6, 7);
  board.rotation.y = -Math.PI / 2;
  scene.add(board);
  /* Layar status kedua di dinding barat (27 Nov 2026, Rangga: isi
     War Room) — cermin papan timur, tapi layar gelap + strip volt
     (bukan papan tulis putih). Muka di x=9,12 menghadap timur;
     lane barat x=9,6 berjarak 0,48 m; segmen jalan z=4,6/9,4 tidak
     tersentuh (layar z 4,75..9,25). */
  scene.add(place(box(0.1, 2.2, 4.5, C.panel), 9.18, 1.6, 7));
  /* PERBAIKAN 28 Nov 2026 (props War Room): bidang gelap lama di
     x=9,12 TERSEMBUNYI di balik panel (panel x 9,13..9,23) + strip
     volt lama box(4,3, 0,09, 0,02) menjorok 4,3 m ke timur
     (tembus sekat ke taman + di atas meja) — w/d tertukar. Bidang
     dipindah ke timur panel (x=9,24), strip diputar memanjang
     sumbu z di atas layar. Posisi/ukuran/warna layar tidak berubah. */
  const statusBoard = new THREE.Mesh(
    new THREE.PlaneGeometry(4.3, 2.0),
    new THREE.MeshBasicMaterial({ color: 0x16181c }));
  statusBoard.position.set(9.24, 1.6, 7);
  statusBoard.rotation.y = Math.PI / 2;
  scene.add(statusBoard);
  const statusStrip = box(0.02, 0.09, 4.3, VOLT);
  statusStrip.position.set(9.25, 2.7, 7);
  scene.add(statusStrip);
  /* Kabinet samping di dinding selatan (x=12, z=13,4) — 3,75 m di
     selatan pad selatan (12,9,4), jauh dari lane + segmen jalan
     mana pun; cermin tanaman sudut barat-daya (9,7,13). */
  scene.add(place(box(1.2, 1.2, 0.5, C.desk), 12, 0.6, 13.4));
  scene.add(place(box(1.2, 0.06, 0.5, C.deskTop), 12, 1.23, 13.4));
  /* Pad lesehan tambahan mengapit pad utara/selatan (3 kursi tiap
     sisi meja operasi). Pad di baris jalan z=4,6/9,4: avatar menuju
     pad tengah sempat melintas di atas pad sisi (0,10 m, singkat)
     — diterima demi 6 kursi (lihat catatan). */
  for (const [px, pz] of [[10.6, 4.6], [13.4, 4.6], [10.6, 9.4], [13.4, 9.4]]) {
    scene.add(place(box(0.7, 0.1, 0.7, C.chair), px, PAD_TOP - 0.05, pz));
  }
}

/* Props War Room per lane (28 Nov 2026, Rangga: "Props war room
   sepi amat, sesuai lane terkait lah") — semua MENEMPEL dinding
   (tanpa tapak lantai): tidak menyentuh slot agen, lane x=9,6/
   14,3, meja operasi, maupun jalur planWalk, jadi pipeline
   snapshot + FURNITURE test_board.py TIDAK perlu diubah.
   - Zeto (security/audit): papan SECURITY di dinding barat segmen
     utara — batang sinyal abstrak (volt/krem, tanpa angka).
   - Neto (trading/revenue): papan REVENUE di dinding timur segmen
     selatan — batang chart abstrak (volt/krem, tanpa angka).
   - Neto (market): papan MARKET di dinding selatan segmen timur —
     garis langkah abstrak (titik volt, tanpa angka).
   ATURAN KERAS: tanpa metrik palsu — batang/titik hanya bentuk,
   label hanya kata, TIDAK ada angka harga/persen/jumlah. */
function buildWarRoomProps() {
  /* Label kanvas kecil: teks volt di atas gelap (pola yang sama
     dengan buildRoomLabels). */
  function warLabel(text, w, h) {
    const tex = textTexture(512, 128, (g) => {
      g.fillStyle = '#16181c'; g.fillRect(0, 0, 512, 128);
      g.fillStyle = '#a3ff00'; g.font = 'bold 64px ui-monospace, monospace';
      g.textAlign = 'center'; g.textBaseline = 'middle';
      g.fillText(text, 256, 64);
    });
    return panelPlane(w, h, tex);
  }
  /* --- A. SECURITY (Zeto) — dinding barat, segmen utara, menghadap
     timur. Panel z 0,9..3,5: 1,1 m di utara baris pad utara (z=4,6),
     0,42 m dari lane barat (x=9,6), sama seperti layar status.
     Bidang layar di timur panel (x=9,24) supaya tidak tersembunyi
     di balik panel (pelajaran dari layar status lama). */
  scene.add(place(box(0.1, 1.5, 2.6, C.panel), 9.18, 1.65, 2.2));
  const secScreen = new THREE.Mesh(
    new THREE.PlaneGeometry(2.4, 1.3),
    new THREE.MeshBasicMaterial({ color: 0x16181c }));
  secScreen.position.set(9.24, 1.65, 2.2);
  secScreen.rotation.y = Math.PI / 2;
  scene.add(secScreen);
  /* Batang sinyal abstrak: 7 batang, tinggi acak, alas y=1,05. */
  const secHeights = [0.35, 0.7, 0.5, 0.95, 0.6, 0.85, 0.4];
  secHeights.forEach((hh, i) => {
    const col = i % 2 === 0 ? VOLT : 0xf3eee2;
    scene.add(place(box(0.04, hh, 0.22, col), 9.26, 1.05 + hh / 2, 1.3 + i * 0.3));
  });
  scene.add(place(box(0.02, 0.03, 2.2, 0xf3eee2), 9.26, 1.05, 2.2));
  const secLabel = warLabel('SECURITY', 0.9, 0.18);
  secLabel.position.set(9.25, 2.22, 2.2);
  secLabel.rotation.y = Math.PI / 2;
  scene.add(secLabel);
  const secStrip = box(0.02, 0.06, 2.4, VOLT);
  secStrip.position.set(9.25, 2.42, 2.2);
  scene.add(secStrip);
  /* --- B. REVENUE (Neto) — dinding timur, segmen selatan,
     menghadap barat. Panel z 10,5..13,1: 1,1 m di selatan baris pad
     selatan (z=9,4), 0,5 m dari lane timur (x=14,3). */
  scene.add(place(box(0.1, 1.5, 2.6, C.panel), 14.82, 1.65, 11.8));
  const revScreen = new THREE.Mesh(
    new THREE.PlaneGeometry(2.4, 1.3),
    new THREE.MeshBasicMaterial({ color: 0x16181c }));
  revScreen.position.set(14.76, 1.65, 11.8);
  revScreen.rotation.y = -Math.PI / 2;
  scene.add(revScreen);
  /* Batang chart abstrak: 8 batang, tinggi acak, alas y=1,05. */
  const revHeights = [0.5, 0.8, 0.65, 1.0, 0.75, 0.9, 0.55, 0.7];
  revHeights.forEach((hh, i) => {
    const col = i % 2 === 0 ? VOLT : 0xf3eee2;
    scene.add(place(box(0.04, hh, 0.2, col), 14.74, 1.05 + hh / 2, 10.85 + i * 0.27));
  });
  scene.add(place(box(0.02, 0.03, 2.2, 0xf3eee2), 14.74, 1.05, 11.8));
  const revLabel = warLabel('REVENUE', 0.9, 0.18);
  revLabel.position.set(14.75, 2.22, 11.8);
  revLabel.rotation.y = -Math.PI / 2;
  scene.add(revLabel);
  const revStrip = box(0.02, 0.06, 2.4, VOLT);
  revStrip.position.set(14.75, 2.42, 11.8);
  scene.add(revStrip);
  /* --- C. MARKET (Neto) — dinding selatan, segmen timur, menghadap
     utara. Panel x 12,7..14,5: 0,1 m di timur kabinet (x 11,4..12,6),
     jauh dari pad selatan (z=9,4) + lane timur (papan menempel
     dinding, tebal 0,1 m). */
  scene.add(place(box(1.8, 1.1, 0.1, C.panel), 13.6, 1.75, 13.85));
  const mktScreen = new THREE.Mesh(
    new THREE.PlaneGeometry(1.6, 0.9),
    new THREE.MeshBasicMaterial({ color: 0x16181c }));
  mktScreen.position.set(13.6, 1.75, 13.79);
  mktScreen.rotation.y = Math.PI;
  scene.add(mktScreen);
  /* Garis langkah abstrak: 6 titik volt naik-turun, alas y=1,35. */
  const mktHeights = [1.5, 1.7, 1.6, 1.9, 1.75, 2.0];
  mktHeights.forEach((yy, i) => {
    scene.add(place(box(0.12, 0.12, 0.04, VOLT), 12.95 + i * 0.26, yy, 13.77));
  });
  scene.add(place(box(1.5, 0.03, 0.02, 0xf3eee2), 13.6, 1.35, 13.77));
  const mktLabel = warLabel('MARKET', 0.7, 0.16);
  mktLabel.position.set(13.6, 2.14, 13.78);
  mktLabel.rotation.y = Math.PI;
  scene.add(mktLabel);
  const mktStrip = box(1.6, 0.06, 0.02, VOLT);
  mktStrip.position.set(13.6, 2.32, 13.78);
  scene.add(mktStrip);
}

/* Meja lab: permukaan + kaki panel (tanpa monitor — gantinya
   alat lab di atas meja). Dipakai Lab AI (meja utama + bench
   kedua). */
function buildLabBench(x, z, w, d, topY) {
  const top = box(w, 0.12, d, C.deskTop);
  top.position.set(x, topY - 0.06, z);
  scene.add(top);
  for (const sx of [-w / 2 + 0.08, w / 2 - 0.08]) {
    const leg = box(0.1, topY - 0.12, d - 0.1, C.desk);
    leg.position.set(x + sx, (topY - 0.12) / 2, z);
    scene.add(leg);
  }
}

/* Lab AI (overhaul 26 Nov 2026; dulu Perpustakaan): rak server di
   sekat barat (strip LED volt) + rak reagen/botol lab di sekat
   timur + meja lab dari slot bermeja + bench inkubator di strip
   utara. Palet krem dipertahankan; aksen cyberpunk HANYA via LED
   volt #a3ff00 + lampu hangat — TANPA neon biru/ungu. Semua
   primitif kode, tanpa GLB baru. */
function buildLabAI() {
  /* Rak barat (x=15.4): rak server — badan gelap hangat + unit
     + strip LED volt di tepi atas + titik status. */
  const rackW = box(0.7, 2.2, 9, 0x2e2a26);
  rackW.position.set(15.4, 1.1, 7);
  scene.add(rackW);
  for (let i = 0; i < 4; i++) {
    const unit = box(0.1, 0.42, 8.6, 0x3a352f);
    unit.position.set(15.78, 0.35 + i * 0.52, 7);
    scene.add(unit);
    for (let j = 0; j < 5; j++) {
      const dot = box(0.06, 0.06, 0.06, 0xa3ff00,
        { emissive: 0xa3ff00, emissiveIntensity: 0.9 });
      dot.position.set(15.84, 0.35 + i * 0.52, 3.6 + j * 1.6);
      scene.add(dot);
    }
  }
  const ledStrip = box(0.06, 0.06, 9, 0xa3ff00,
    { emissive: 0xa3ff00, emissiveIntensity: 1.0 });
  ledStrip.position.set(15.78, 2.16, 7);
  scene.add(ledStrip);
  /* Rak timur (x=20.5): rak reagen — badan kayu + botol-botol lab
     (silinder + leher sempit, warna hangat). */
  const rackE = box(0.7, 2.2, 9, C.desk);
  rackE.position.set(20.5, 1.1, 7);
  scene.add(rackE);
  const bottleColors = [0xd9a441, 0x0f766e, 0xca4f40, 0xf3eee2, 0x7fb069, 0xfc7a24];
  bottleColors.forEach((col, i) => {
    const z = 3.6 + i * 1.3;
    scene.add(place(cyl(0.09, 0.11, 0.45, col), 20.04, 0.68, z));
    scene.add(place(cyl(0.04, 0.04, 0.16, col), 20.04, 0.98, z));
    scene.add(place(cyl(0.09, 0.11, 0.45, col), 20.04, 1.28, z + 0.6));
    scene.add(place(cyl(0.04, 0.04, 0.16, col), 20.04, 1.58, z + 0.6));
  });
  /* Rak reagen YANG KELIHATAN (cek visual 26 Nov 2026): botol lama
     setengah tertanam di muka rak datar (x=20.18, muka rak 20.15)
     tanpa papan — kebaca pajangan dinding. Sekarang: papan belakang
     gelap + 2 papan rak menonjol + braket, botol digeser ke barat
     (x=20.04) supaya berdiri DI ATAS papan, bukan di dalam dinding. */
  scene.add(place(box(0.04, 1.5, 8.4, 0x7a5c38), 20.14, 1.0, 7));
  for (const shelfY of [0.42, 1.02]) {
    scene.add(place(box(0.34, 0.06, 8.0, 0x7a5c38), 20.08, shelfY, 7));
    for (const bz of [3.6, 7.0, 10.4]) {
      scene.add(place(box(0.34, 0.14, 0.1, 0x7a5c38), 20.08, shelfY - 0.1, bz));
    }
  }
  /* Meja lab utama dari slot bermeja (data-driven) + pad duduk. */
  const room = ROOMS['lab-ai'];
  for (const s of room.slots) {
    if (s.desk) {
      buildLabBench(s.x, s.z + 1.1, 2.2, 0.9, DESK_TOP_Y);
      scene.add(place(box(0.7, 0.1, 0.7, C.chair), s.x, PAD_TOP - 0.05, s.z));
    }
  }
  /* Alat di atas meja lab utama: mikroskop di sisi timur supaya
     tidak menutup wajah agen yang duduk; rak tabung reaksi +
     labu di sisi barat/tengah. */
  const benchY = DESK_TOP_Y;
  scene.add(place(cyl(0.09, 0.11, 0.06, 0x2e2a26), 18.15, benchY + 0.03, 5.6));
  const microArm = cyl(0.03, 0.03, 0.32, 0x555555);
  microArm.rotation.z = -0.6;
  scene.add(place(microArm, 18.15, benchY + 0.18, 5.6));
  const microTube = cyl(0.05, 0.05, 0.26, 0x222222);
  microTube.rotation.z = -0.6;
  scene.add(place(microTube, 18.28, benchY + 0.32, 5.6));
  scene.add(place(box(0.4, 0.06, 0.14, C.desk), 16.9, benchY + 0.03, 5.6));
  [0xd9a441, 0x0f766e, 0xca4f40, 0x7fb069].forEach((col, i) => {
    scene.add(place(cyl(0.035, 0.035, 0.24, col), 16.78 + i * 0.09, benchY + 0.18, 5.6));
  });
  scene.add(place(sph(0.12, 0xd9a441), 17.5, benchY + 0.12, 5.95));
  scene.add(place(cyl(0.04, 0.04, 0.16, 0xd9a441), 17.5, benchY + 0.28, 5.95));
  /* Bench kedua — island di tengah ruangan (17.9, 7.5), tempat
     kerja berdiri bersama (tanpa pad). Posisi di antara dua slot
     berdiri (17.9, 9.6) DITOLAK tes tabrakan: bench di sana
     menutup jalur masuk slot (16.8, 10) — lihat FURNITURE di
     test_board.py. */
  buildLabBench(17.9, 7.5, 1.2, 0.8, 0.5);
  scene.add(place(box(0.4, 0.06, 0.14, C.desk), 17.6, 0.53, 7.5));
  [0x0f766e, 0xd9a441, 0xca4f40].forEach((col, i) => {
    scene.add(place(cyl(0.035, 0.035, 0.24, col), 17.48 + i * 0.09, 0.65, 7.5));
  });
  scene.add(place(sph(0.12, 0x0f766e), 18.15, 0.62, 7.5));
  scene.add(place(cyl(0.04, 0.04, 0.16, 0x0f766e), 18.15, 0.78, 7.5));
  /* Inkubator di strip utara (16.3, 1.0) — jauh dari pintu (x=18)
     + lane (x=19.4). DIAGNOSIS cek visual 26 Nov 2026 (tidak
     kelihatan dari depan maupun setelah orbit 180°): badan lama
     1.4x1.3 arang gelap 0x2e2a26 + pintu PlaneGeometry satu-sisi
     (hilang dari belakang) — terlalu kecil + terlalu gelap di
     skala overview. PERBAIKAN: badan KREM (kelihatan dari semua
     sisi), lebih tinggi (1.7), pintu GELAP sebagai kotak (bukan
     plane), aksen volt: strip LED atas + gagang + display.
     Footprint TETAP 1.4x0.9 (rect tabrakan test_board.py
     (15.6, 0.55, 17.0, 1.45) tetap berlaku). Display: angka
     "37.0°C" dari canvas texture (cek visual 26 Nov 2026:
     kotak volt polos lama tidak terbaca) — gelap + digit volt,
     tetap dalam palet krem/volt. */
  const incubator = box(1.4, 1.7, 0.9, 0xf3eee2);
  incubator.position.set(16.3, 0.85, 1.0);
  scene.add(incubator);
  const incubatorCap = box(1.44, 0.08, 0.94, 0x2e2a26);
  incubatorCap.position.set(16.3, 1.74, 1.0);
  scene.add(incubatorCap);
  const incubatorDoor = box(1.0, 1.1, 0.06, 0x2e2a26);
  incubatorDoor.position.set(16.3, 0.82, 1.48);
  scene.add(incubatorDoor);
  const incubatorLed = box(1.4, 0.08, 0.06, 0xa3ff00,
    { emissive: 0xa3ff00, emissiveIntensity: 1.0 });
  incubatorLed.position.set(16.3, 1.62, 1.48);
  scene.add(incubatorLed);
  const incubatorHandle = box(0.07, 0.55, 0.05, 0xa3ff00,
    { emissive: 0xa3ff00, emissiveIntensity: 0.8 });
  incubatorHandle.position.set(16.68, 0.82, 1.53);
  scene.add(incubatorHandle);
  const incubatorDisplayTex = textTexture(256, 128, (g, w, h) => {
    g.fillStyle = '#0f1115'; g.fillRect(0, 0, w, h);
    g.strokeStyle = '#a3ff00'; g.lineWidth = 6; g.strokeRect(5, 5, w - 10, h - 10);
    g.fillStyle = '#a3ff00'; g.font = 'bold 58px ui-monospace, monospace';
    g.textAlign = 'center'; g.textBaseline = 'middle';
    g.fillText('37.0°C', w / 2, h / 2 + 4);
  });
  const incubatorDisplay = panelPlane(0.44, 0.22, incubatorDisplayTex);
  incubatorDisplay.position.set(16.05, 1.22, 1.545);
  scene.add(incubatorDisplay);
  /* Tanaman sudut tetap. */
  scene.add(place(cyl(0.45, 0.35, 0.5, C.pot), 20, 0.25, 13));
  scene.add(place(sph(0.55, C.plant), 20, 1.0, 13));
  scene.add(place(sph(0.35, C.plantDark), 20.2, 1.45, 12.9));
  /* Superkomputer AI di strip utara (27 Nov 2026, perintah Rangga:
     "Utara lab kasih super computer ai bro drpd kosong gt, bikin
     animasi2 ala2 inference ai"). 3 rak server di tepi utara lab
     (z -0,76..0), barat pintu (x=18) + lane (x=19,4) — tidak
     menghalangi jalan masuk/lane/slot/meja/inkubator. Muka rak
     menghadap selatan (+z) ke dalam ruangan. Palet krem/volt sama
     seperti rak server barat. Animasi inference (LED chase + titik
     data mengalir + layar status + strip volt berdenyut) ikut loop
     setInterval lalu lintas yang sudah ada (startTraffic, 50 ms) —
     TANPA timer baru; hormat document.hidden + prefers-reduced-
     motion lewat loop itu (REDUCED = loop tidak jalan, mesin tetap
     tampil statis menyala). Footprint rect tabrakan test_board.py:
     (15.46, -0.76, 17.24, 0.0). */
  const scX = [15.75, 16.35, 16.95];
  const scZ = -0.4;
  const scLeds = [];
  const scFlow = [];
  for (const [i, x] of scX.entries()) {
    /* Badan rak gelap hangat + tutup. */
    scene.add(place(box(0.55, 2.0, 0.7, 0x2e2a26), x, 1.0, scZ));
    scene.add(place(box(0.57, 0.06, 0.72, 0x3a352f), x, 2.03, scZ));
    /* 4 unit di muka selatan: panel tipis + slot ventilasi. */
    for (let u = 0; u < 4; u++) {
      const uy = 0.35 + u * 0.5;
      scene.add(place(box(0.45, 0.4, 0.02, 0x3a352f), x, uy, scZ + 0.36));
      scene.add(place(box(0.4, 0.03, 0.02, 0x16130f), x, uy - 0.18, scZ + 0.37));
    }
    /* Kolom LED status di muka (kanan tiap rak): 4 titik, bahan
       SENDIRI per titik supaya chase bisa ubah warna per titik. */
    for (let d = 0; d < 4; d++) {
      const ledMat = new THREE.MeshBasicMaterial({ color: 0x3a3a3a });
      const led = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.05, 0.03), ledMat);
      led.position.set(x + 0.2, 0.35 + d * 0.5, scZ + 0.38);
      scene.add(led);
      scLeds.push(ledMat);
    }
    /* Titik data mengalir: 2 per rak, turun di muka rak. */
    for (let f = 0; f < 2; f++) {
      const dot = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.05, 0.03),
        new THREE.MeshBasicMaterial({ color: VOLT }));
      dot.position.set(x - 0.15 + f * 0.12, 1.9, scZ + 0.38);
      scene.add(dot);
      scFlow.push({ mesh: dot, off: (i * 2 + f) * 0.33 });
    }
  }
  /* Strip volt panjang di tepi atas muka rak (berdenyut). */
  const scStripMat = new THREE.MeshBasicMaterial({ color: VOLT });
  scene.add(place(new THREE.Mesh(new THREE.BoxGeometry(1.75, 0.05, 0.03), scStripMat), 16.35, 1.98, scZ + 0.37));
  /* Layar status inference di atas rak tengah (miring ke belakang,
     menghadap selatan): canvas texture yang digambar ulang di loop
     animasi (maks 2 Hz). */
  const scScreenTex = textTexture(256, 128, (g, w, h) => {
    drawSupercompScreen(g, w, h, 0);
  });
  const scScreen = panelPlane(0.9, 0.45, scScreenTex);
  scScreen.position.set(16.35, 2.38, scZ - 0.05);
  scScreen.rotation.x = -0.15;
  scene.add(scScreen);
  /* Penyangga layar: plat + tiang di atas rak tengah. */
  scene.add(place(box(0.3, 0.04, 0.2, 0x2e2a26), 16.35, 2.08, scZ - 0.05));
  scene.add(place(box(0.06, 0.25, 0.06, 0x2e2a26), 16.35, 2.22, scZ - 0.05));
  /* Kabel lantai (datar 0,02, tidak menghalangi jalan): dari bawah
     rak ke arah inkubator, berhenti sebelum badan inkubator. */
  scene.add(place(box(0.08, 0.02, 0.55, 0x16130f), 15.75, 0.01, 0.22));
  scene.add(place(box(0.08, 0.02, 0.55, 0x16130f), 16.95, 0.01, 0.22));
  supercomp = { leds: scLeds, flow: scFlow, strip: scStripMat, screen: scScreenTex, screen2: null, lastChase: -1, lastScreenMs: 0 };
  /* Rak superkomputer ke-2 disamping pot lab — DIPERLEBAR 28 Nov
     2026 (perintah Rangga: "Supercomputer dkt pot lab krg lebar
     brooo, jgn ada space kosong"). 1 rak di barat pot sudut (20,
     13) — pusat (19.0125, 13), muka menghadap utara (-z) ke dalam
     ruangan (ke arah meja lab + pintu). Lebar 0,775 m (x 18.625..
     19.40): tepi timur 0,05 m dari bola daun (tepi barat x=19,45,
     pusat (20, 1.0, 13), r=0,55) dan 0,15 m dari silinder pot
     (tepi barat x=19,55) — LEBAR MAKSIMAL tanpa menyentuh tanaman.
     Dalam 0,7 x 2,0 m, palet sama dengan rak utara. 4 unit (baris)
     + 4 LED tetap (terikat tinggi 2,0 m, satu per baris 0,5 m);
     panel unit + strip volt memanjang ikut lebar; titik data 2 -> 3
     tersebar di muka yang lebih lebar. LED + titik data ikut array
     supercomp yang sudah ada (chase + aliran sama, tanpa fungsi
     animasi baru); strip volt pakai bahan scStripMat yang sama
     (denyut serentak). Footprint rect tabrakan test_board.py:
     (18.625, 12.65, 19.40, 13.35). */
  const scPotX = 19.0125, scPotZ = 13, scPotW = 0.775;
  scene.add(place(box(scPotW, 2.0, 0.7, 0x2e2a26), scPotX, 1.0, scPotZ));
  scene.add(place(box(scPotW + 0.02, 0.06, 0.72, 0x3a352f), scPotX, 2.03, scPotZ));
  /* 4 unit di muka utara: panel tipis + slot ventilasi. */
  for (let u = 0; u < 4; u++) {
    const uy = 0.35 + u * 0.5;
    scene.add(place(box(scPotW - 0.1, 0.4, 0.02, 0x3a352f), scPotX, uy, scPotZ - 0.36));
    scene.add(place(box(scPotW - 0.15, 0.03, 0.02, 0x16130f), scPotX, uy - 0.18, scPotZ - 0.37));
  }
  /* Kolom LED status di muka utara (kanan bila dilihat dari utara):
     4 titik, bahan SENDIRI per titik — ikut chase supercomp. */
  for (let d = 0; d < 4; d++) {
    const ledMat = new THREE.MeshBasicMaterial({ color: 0x3a3a3a });
    const led = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.05, 0.03), ledMat);
    led.position.set(scPotX - scPotW / 2 + 0.075, 0.35 + d * 0.5, scPotZ - 0.38);
    scene.add(led);
    scLeds.push(ledMat);
  }
  /* Titik data mengalir: 3 titik, turun di muka utara (tersebar di
     muka yang lebih lebar). */
  for (let f = 0; f < 3; f++) {
    const dot = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.05, 0.03),
      new THREE.MeshBasicMaterial({ color: VOLT }));
    dot.position.set(scPotX - 0.25 + f * 0.25, 1.9, scPotZ - 0.38);
    scene.add(dot);
    scFlow.push({ mesh: dot, off: 0.5 + f * 0.5 });
  }
  /* Strip volt di tepi atas muka utara (denyut, bahan sama). */
  scene.add(place(new THREE.Mesh(new THREE.BoxGeometry(scPotW, 0.05, 0.03), scStripMat), scPotX, 1.98, scPotZ - 0.37));
  /* Klaster superkomputer di samping pot lab (28 Nov 2026, perintah
     Rangga: "Deket pot jadi cluster supercomouter monitor ai dll").
     3 rak baru (#3, #4, #5) di barat rak pot #2, sebaris di dinding
     selatan (z 13), muka menghadap utara — deret 4 rak x 16.24..19.40
     tanpa celah (gap 0,02 m antar rak), lalu pot (19,45). 2 layar
     status "AI CLUSTER" di atas rak #3 + #5 + kabel lantai. Palet +
     animasi sama seperti rak utara/pot (LED chase + titik data ikut
     array supercomp yang ada; strip volt pakai scStripMat; TANPA
     timer baru). Footprint rect tabrakan test_board.py:
     (16.24, 12.65, 19.40, 13.35) — satu rect untuk deret 4 rak. */
  const scClusterX = [18.2175, 17.4225, 16.6275];
  const scClusterZ = 13, scClusterW = 0.775;
  for (const [ci, cx] of scClusterX.entries()) {
    /* Badan + tutup (palet sama). */
    scene.add(place(box(scClusterW, 2.0, 0.7, 0x2e2a26), cx, 1.0, scClusterZ));
    scene.add(place(box(scClusterW + 0.02, 0.06, 0.72, 0x3a352f), cx, 2.03, scClusterZ));
    /* 4 unit di muka utara: panel + slot ventilasi. */
    for (let u = 0; u < 4; u++) {
      const uy = 0.35 + u * 0.5;
      scene.add(place(box(scClusterW - 0.1, 0.4, 0.02, 0x3a352f), cx, uy, scClusterZ - 0.36));
      scene.add(place(box(scClusterW - 0.15, 0.03, 0.02, 0x16130f), cx, uy - 0.18, scClusterZ - 0.37));
    }
    /* Kolom LED status di muka utara (kanan bila dilihat dari
       utara): 4 titik, bahan SENDIRI — ikut chase supercomp. */
    for (let d = 0; d < 4; d++) {
      const ledMat = new THREE.MeshBasicMaterial({ color: 0x3a3a3a });
      const led = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.05, 0.03), ledMat);
      led.position.set(cx - scClusterW / 2 + 0.075, 0.35 + d * 0.5, scClusterZ - 0.38);
      scene.add(led);
      scLeds.push(ledMat);
    }
    /* Titik data mengalir: 3 per rak, turun di muka utara (fase
       tersebar antar rak). */
    for (let f = 0; f < 3; f++) {
      const dot = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.05, 0.03),
        new THREE.MeshBasicMaterial({ color: VOLT }));
      dot.position.set(cx - 0.25 + f * 0.25, 1.9, scClusterZ - 0.38);
      scene.add(dot);
      scFlow.push({ mesh: dot, off: (ci * 3 + f) * 0.25 });
    }
    /* Strip volt di tepi atas muka utara (denyut, bahan sama). */
    scene.add(place(new THREE.Mesh(new THREE.BoxGeometry(scClusterW, 0.05, 0.03), scStripMat), cx, 1.98, scClusterZ - 0.37));
  }
  /* 2 layar status "AI CLUSTER" di atas rak #3 + #5 (berbagi satu
     tekstur; digambar ulang di updateSupercomp, maks 2 Hz).
     Dinding selatan rendah (0,9 m) jadi layar tidak bisa di dinding
     — di atas rak seperti layar utara. */
  const scClusterTex = textTexture(256, 128, (g, w, h) => {
    drawClusterScreen(g, w, h, 0);
  });
  for (const sx of [18.2175, 16.6275]) {
    const scClusterScreen = panelPlane(0.9, 0.45, scClusterTex);
    scClusterScreen.position.set(sx, 2.38, 12.95);
    scClusterScreen.rotation.set(0.15, Math.PI, 0);
    scene.add(scClusterScreen);
    /* Penyangga layar: plat + tiang di atas rak. */
    scene.add(place(box(0.3, 0.04, 0.2, 0x2e2a26), sx, 2.08, 12.95));
    scene.add(place(box(0.06, 0.25, 0.06, 0x2e2a26), sx, 2.22, 12.95));
  }
  supercomp.screen2 = scClusterTex;
  /* Kabel lantai (datar 0,02, tidak menghalangi jalan): sepanjang
     muka deret rak + dari deret ke utara menuju bench island. */
  scene.add(place(box(2.9, 0.02, 0.08, 0x16130f), 17.82, 0.01, 12.5));
  scene.add(place(box(0.08, 0.02, 4.5, 0x16130f), 17.8, 0.01, 10.25));
}

/* --- avatar GLB -------------------------------------------------- */
/* GLB 13/13 di public/models/ (13 rigged Draco + WebP, chibi
   batch 2026-11-25, total ~21,1 MB / 22.118.208 B).
   Skala tiap file belum tentu sama — dinormalisasi ke tinggi 1.6
   dari bounding box, kaki di y=0. Gagal/timeout -> stand-in
   primitif warna agen (ruangan tetap tampil, bukan halaman kosong).
   DRACOLoader memakai Blob-URL worker — CSP di app.py sudah
   mengizinkan worker-src 'self' blob: (lihat README §10.7). */
const gltfLoader = new GLTFLoader();
const dracoLoader = new DRACOLoader();
dracoLoader.setDecoderPath(MODULE_BASE + 'vendor/draco/');
dracoLoader.setWorkerLimit(2);
gltfLoader.setDRACOLoader(dracoLoader);

/* FEET FIX 2026-11-21 — kaki avatar nempel lantai (y=0).
   ROOT CAUSE: Box3.setFromObject(obj) di sini mengukur bbox SKINNED
   lewat object.matrixWorld — untuk GLB TRELLIS, matrixWorld mesh masih
   membawa skala armature (Geto: 0.53x) sehingga bbox terkompresi
   (0.45–0.70, bukan ~1.0) dan skala jadi 2.3–3.6x (kaki −0.6, avatar
   raksasa). Terukur harness: PROD s=2.29–3.57 semua 10 avatar.
   FIX: ukur bbox mesh-LOCAL langsung dari SkinnedMesh.computeBoundingBox
   (tanpa mengalikan matrixWorld), sesudah updateWorldMatrix(true, true)
   + invalidate cache boundingBox. Terukur: s=1.600 untuk 11/11 avatar
   (Geto 3.018→1.600), kaki berdiri di y=0.000. */
function normalizeAvatar(obj) {
  obj.updateWorldMatrix(true, true);
  const box3 = new THREE.Box3();
  let found = false;
  obj.traverse((o) => {
    if (o.isSkinnedMesh) {
      o.boundingBox = null; /* paksa hitung ulang dari bone matrixWorld saat ini */
      o.computeBoundingBox();
      box3.union(o.boundingBox);
      found = true;
    }
  });
  if (!found) box3.setFromObject(obj); /* fallback: tanpa skinned mesh */
  const size = new THREE.Vector3();
  box3.getSize(size);
  const center = new THREE.Vector3();
  box3.getCenter(center);
  const s = 1.6 / Math.max(size.y, 0.01);
  obj.scale.setScalar(s);
  obj.position.set(-center.x * s, -box3.min.y * s, -center.z * s);
  return obj;
}

/* LIGHTING FIX 2026-11-21 (item 4 punch list — muka/pundak menghitam).
   ROOT CAUSE (terukur harness, bukan tebakan): GLB TRELLIS hanya menyimpan
   baseColorTexture — TANPA metallicFactor/roughnessFactor — sehingga
   GLTFLoader memakai default glTF: metalness=1, roughness=1. Material
   metal MURNI tidak punya diffuse: ambient/hemisphere/key TIDAK BISA
   meneranginya (terukur: ambient-only, hemi-only, dan ambient+hemi =
   luminance 0 di muka & pundak; lantai Standard yang sama = 154-227).
   Tanpa scene.environment (AAA_ENV=false) tidak ada yang bisa dipantulkan
   avatar → hitam. Hipotesis Rangga BENAR secara efek ("ga ada global
   light yang kena pundak") — mekanismenya di material, bukan di lampu:
   menaikkan ambient/hemi (V5/V10) dan exposure (V8) terukur NOL efek.
   FIX (V18 = usulan riset independen + emissive): metalness=0 (diffuse
   kembali; cahaya global yang SUDAH ADA — ambient 1.6 + hemi 2.0 +
   key 3.4 — langsung bekerja: muka Rangga 15→152, pundak 0→144) +
   roughness 0.75 (vinyl lembut; terukur ≈ metal0 saja — diffuse tidak
   dipengaruhi roughness) + envMapIntensity 0.35 (samakan dengan material
   ruangan aaaStd; no-op tanpa scene.environment, jaga-jaga bila AAA_ENV
   suatu saat dinyalakan) + emissive kecil = warna rata-rata tekstur
   × 0.15 untuk mengangkat area albedo gelap (hoodie hitam Rangga)
   tanpa bikin flat (V18 vs V17: pundak +10–20, muka tetap kontras).
   Tanpa lampu baru, tanpa update per-frame — render-on-demand tetap
   hemat. Palet/warna tidak disentuh.
   (V14 env-map-only DITOLAK: muka cuma 15→20; V4 emissive saja DITOLAK:
   flat, muka ≈ pundak; V2/V3 fill light DITOLAK: pundak tetap ~0
   selama metalness=1.) */
const AVATAR_EMISSIVE_LIFT = 0.15;
function avatarTextureAverage(tex) {
  try {
    const img = tex && tex.image;
    if (!img || !img.width || !img.height) return null;
    const c = document.createElement('canvas');
    c.width = 32; c.height = 32;
    const ctx = c.getContext('2d', { willReadFrequently: true });
    if (!ctx) return null;
    ctx.drawImage(img, 0, 0, 32, 32);
    const d = ctx.getImageData(0, 0, 32, 32).data;
    let r = 0, g = 0, b = 0, n = 0;
    for (let i = 0; i < d.length; i += 4) {
      if (d[i + 3] < 128) continue;
      r += d[i]; g += d[i + 1]; b += d[i + 2]; n++;
    }
    if (!n) return null;
    return new THREE.Color(r / n / 255, g / n / 255, b / n / 255);
  } catch (e) { return null; }
}
function fixAvatarMaterials(obj) {
  const seen = new Set();
  obj.traverse((o) => {
    if (!o.isMesh || !o.material || !o.material.isMeshStandardMaterial) return;
    const m = o.material;
    if (seen.has(m.uuid)) return;
    seen.add(m.uuid);
    m.metalness = 0; /* TRELLIS default 1 = cermin hitam tanpa env map */
    m.roughness = 0.75; /* vinyl lembut (usulan riset independen) */
    m.envMapIntensity = 0.35; /* samakan dgn material ruangan */
    const avg = avatarTextureAverage(m.map) || m.color.clone();
    m.emissive.copy(avg).multiplyScalar(AVATAR_EMISSIVE_LIFT);
  });
}

/* Pose idle: lengan turun dari T-pose (joint-map.json).
   SHOULDER FIX 2026-11-21 (Item A punch list) — ROOT CAUSE TERUKUR:
   kode lama memutar bahu +-75 deg pada sumbu Z LOKAL bone. Sumbu Z
   lokal itu BUKAN sumbu frontal: bind quaternion TRELLIS tiap GLB
   non-identity, jadi sumbu Z lokal menunjuk miring ke depan/atas/
   luar (contoh rangga: Z lokal = [-0.45, 0.39, 0.81] di dunia).
   Akibatnya 75 deg itu bocor ke bidang sagital (+-5..20 deg, Geto
   -19.5 / Zeto +19.8) dan kurang di bidang frontal — lengan atas
   idle terukur 9.4..25.1 deg dari vertikal (tangan 0.11..0.24 di
   luar bahu), bukan ~15 deg yang diharapkan; Seto paling parah
   (55.5 deg frontal, -65.9 sagital — sumbu Z lokalnya hampir
   sejajar lengan, jadi rotasi lama hampir tidak menurunkan lengan).
   Lengan bawah ikut miring 17..41 deg. Hasilnya postur huruf A.
   FIX: delta quaternion per-avatar per-sendi, DIUKUR di harness
   (solve.html): sumbu+ sudut di frame lokal bone yang memetakan
   arah lengan bind ke target — lengan atas 5 deg ke luar dari
   vertikal, lengan bawah 8 deg ke luar, sagital 0. Terverifikasi
   harness: semua 11 avatar tepat 5.00/8.00/0.00 deg (L/R).
   Delta diterapkan dgn pola lama yang sama (base.multiply(delta),
   frame lokal bone) + guard Set supaya satu bone tidak kena dua
   kali bila GLB punya >1 SkinnedMesh dgn skeleton yang sama.
   Tanpa entri di tabel (avatar baru tanpa ukur): fallback ke
   perilaku lama Z +-75 di bahu saja. Nomor bone TIDAK ditulis di
   tabel ini — diambil dari JOINT_ROLES (satu sumber).
   CHIBI BATCH 2026-11-25: tabel 13 avatar (termasuk Atharia + Reto
   yang kini terukur — dulu fallback Z +-75). Sumber per avatar:
   output/chibi/<nama>/measure_<nama>.json (oto v3, beto v3)
   + measure_chibi.json (rangga pilot). Fixed arms terverifikasi
   harness: semua 13 avatar tepat 5.00/8.00/0.00 deg (L/R).
*/
const IDLE_ARM_DELTAS = {
  rangga: {
    shoulderL: { axis: [-0.6178, -0.0000, -0.7863], deg: 52.99 },
    shoulderR: { axis: [-0.6178, 0.0000, 0.7863], deg: 52.99 },
    forearmL: { axis: [0.9447, -0.1694, -0.2808], deg: 20.99 },
    forearmR: { axis: [0.9525, 0.1790, 0.2464], deg: 19.15 },
  },
  oto: {
    shoulderL: { axis: [-0.6585, -0.0000, -0.7526], deg: 65.82 },
    shoulderR: { axis: [-0.6585, -0.0000, 0.7526], deg: 65.82 },
    forearmL: { axis: [0.9874, -0.1165, -0.1068], deg: 17.30 },
    forearmR: { axis: [0.9826, 0.1544, 0.1035], deg: 17.30 },
  },
  beto: {
    shoulderL: { axis: [-0.7071, -0.0000, -0.7071], deg: 49.09 },
    shoulderR: { axis: [-0.974, -0.197, 0.11], deg: 64.187 }, /* DIPERBAIKI 2026-11-25:
       delta lama salah ukur — lengan R menggantung 46.9 deg menyimpang dari cermin L
       (upperFrontal 67 deg, tangan R 0.09 lebih tinggi); delta baru = cermin L (err 0.02 deg) */
    forearmL: { axis: [0.2836, 0.1169, -0.9518], deg: 15.30 },
    forearmR: { axis: [0.9423, 0.0770, -0.3259], deg: 6.79 },
  },
  zeto: {
    shoulderL: { axis: [-0.6331, -0.0766, -0.7703], deg: 73.37 },
    shoulderR: { axis: [-0.6331, 0.0766, 0.7703], deg: 73.37 },
    forearmL: { axis: [0.6056, -0.2043, 0.7691], deg: 25.70 },
    forearmR: { axis: [0.6056, 0.2043, -0.7691], deg: 25.70 },
  },
  neto: {
    shoulderL: { axis: [-0.6549, -0.0000, -0.7557], deg: 63.20 },
    shoulderR: { axis: [-0.6549, 0.0000, 0.7557], deg: 63.20 },
    forearmL: { axis: [0.9682, -0.0816, -0.2367], deg: 15.50 },
    forearmR: { axis: [0.9611, 0.1517, 0.2310], deg: 15.50 },
  },
  geto: {
    shoulderL: { axis: [-0.5408, -0.0000, -0.8412], deg: 53.17 },
    shoulderR: { axis: [-0.5408, 0.0000, 0.8412], deg: 52.26 },
    forearmL: { axis: [0.9295, -0.2468, 0.2741], deg: 6.83 },
    forearmR: { axis: [0.9658, 0.2512, -0.0638], deg: 3.79 },
  },
  leto: {
    shoulderL: { axis: [-0.6317, 0.0702, -0.7720], deg: 52.99 },
    shoulderR: { axis: [-0.6317, -0.0702, 0.7720], deg: 52.99 },
    forearmL: { axis: [0.9597, -0.1975, 0.2000], deg: 6.85 },
    forearmR: { axis: [0.9597, 0.1975, -0.2000], deg: 6.85 },
  },
  ceto: {
    shoulderL: { axis: [-0.5787, 0.0235, -0.8152], deg: 55.48 },
    shoulderR: { axis: [-0.6199, -0.0257, 0.7843], deg: 54.64 },
    forearmL: { axis: [0.9420, -0.1175, -0.3144], deg: 9.02 },
    forearmR: { axis: [0.9473, 0.1791, 0.2657], deg: 8.27 },
  },
  deto: {
    shoulderL: { axis: [-0.6459, 0.0000, -0.7634], deg: 61.37 },
    shoulderR: { axis: [-0.6281, -0.0231, 0.7778], deg: 61.38 },
    forearmL: { axis: [0.6707, -0.2453, 0.6999], deg: 28.36 },
    forearmR: { axis: [0.7050, 0.2339, -0.6695], deg: 24.41 },
  },
  seto: {
    shoulderL: { axis: [-0.6038, -0.0327, -0.7964], deg: 65.11 },
    shoulderR: { axis: [-0.6502, 0.0504, 0.7581], deg: 65.06 },
    forearmL: { axis: [0.7553, -0.4371, 0.4883], deg: 24.29 },
    forearmR: { axis: [0.7299, 0.4505, -0.5140], deg: 22.27 },
  },
  meto: {
    shoulderL: { axis: [-0.5987, 0.0665, -0.7982], deg: 55.64 },
    shoulderR: { axis: [-0.5987, -0.0665, 0.7982], deg: 55.64 },
    forearmL: { axis: [0.9757, -0.2116, 0.0561], deg: 13.46 },
    forearmR: { axis: [0.9757, 0.2116, -0.0561], deg: 13.46 },
  },
  atharia: {
    shoulderL: { axis: [-0.6533, 0.0901, -0.7518], deg: 41.06 },
    shoulderR: { axis: [-0.6533, -0.0901, 0.7518], deg: 41.06 },
    forearmL: { axis: [0.8568, -0.2066, -0.4724], deg: 13.71 },
    forearmR: { axis: [0.8568, 0.2066, 0.4724], deg: 13.71 },
  },
  reto: {
    shoulderL: { axis: [-0.6851, 0.0028, -0.7284], deg: 40.99 },
    shoulderR: { axis: [-0.6868, -0.0005, 0.7269], deg: 40.14 },
    forearmL: { axis: [0.9654, -0.2485, -0.0789], deg: 33.57 },
    forearmR: { axis: [0.9695, 0.2444, 0.0173], deg: 31.59 },
  },
};
function applyIdlePose(obj, name) {
  const roles = JOINT_ROLES[name];
  if (!roles) return;
  const deltas = IDLE_ARM_DELTAS[name];
  const applied = new Set(); /* bone yang sudah diputar (anti double-apply antar mesh) */
  obj.traverse((o) => {
    if (!o.isSkinnedMesh || !o.skeleton) return;
    const bones = {};
    o.skeleton.bones.forEach((b) => { bones[b.name] = b; });
    const apply = (boneIdx, axis, deg) => {
      const b = bones['bone_' + boneIdx];
      if (!b || applied.has(b)) return;
      applied.add(b);
      b.quaternion.multiply(deltaQuat(axis, deg));
    };
    if (deltas) {
      apply(roles.shoulderL, deltas.shoulderL.axis, deltas.shoulderL.deg);
      apply(roles.shoulderR, deltas.shoulderR.axis, deltas.shoulderR.deg);
      apply(roles.forearmL, deltas.forearmL.axis, deltas.forearmL.deg);
      apply(roles.forearmR, deltas.forearmR.axis, deltas.forearmR.deg);
    } else {
      /* Fallback avatar tanpa delta terukur: perilaku lama Z +-75 di bahu saja.
         (IDLE_SHOULDER_* dihapus Item A — nomor bone dari JOINT_ROLES.) */
      apply(roles.shoulderL, [0, 0, 1], -75);
      apply(roles.shoulderR, [0, 0, 1], 75);
    }
  });
}
function fallbackAvatar(name) {
  const g = new THREE.Group();
  const col = new THREE.Color(KNOWN_AGENTS[name].color);
  const body = cyl(0.32, 0.38, 0.95, col.getHex());
  body.position.y = 0.75;
  g.add(body);
  const head = sph(0.34, 0xf2c89b);
  head.position.y = 1.45;
  g.add(head);
  const cap = cyl(0.36, 0.36, 0.12, col.getHex());
  cap.position.y = 1.72;
  g.add(cap);
  return g;
}

function loadOneAvatar(name) {
  return new Promise((resolve) => {
    let done = false;
    const finish = (obj) => {
      if (done) return;
      done = true;
      resolve(obj);
    };
    const timer = setTimeout(() => {
      console.warn('GLB timeout, pakai stand-in:', name);
      finish(fallbackAvatar(name));
    }, 8000);
    /* 2026-11-28 (Rangga: leto & ceto ketukar): file GLB sudah
       benar sejak batch chibi 25 Nov (ceto = blazer pink, leto =
       hoodie lavender, terverifikasi dari tekstur), tapi URL-nya
       tidak berubah sehingga browser yang menyimpan cache lama
       masih menampilkan model tertukar. Query ?v= memaksa fetch
       baru; naikkan angkanya setiap kali file GLB diganti. */
    gltfLoader.load(
      MODULE_BASE + 'models/' + name + '.glb?v=20261128',
      (gltf) => {
        clearTimeout(timer);
        try {
          const obj = normalizeAvatar(gltf.scene);
          fixAvatarMaterials(obj);
          applyIdlePose(obj, name);
          captureBoneBase(obj, name);
          if (done) {
            /* Telat tapi berhasil: ganti stand-in dengan GLB asli
               (dulu finish() mengabaikannya — akar silinder permanen). */
            replaceAvatarInner(name, obj);
          } else {
            finish(obj);
          }
        } catch (err) {
          /* Dulu: throw di post-processing bikin promise gantung sampai
             timeout 8 dtk baru fallback. Sekarang fallback langsung. */
          finish(fallbackAvatar(name));
        }
      },
      undefined,
      (err) => { clearTimeout(timer); console.warn('GLB gagal dimuat, pakai stand-in:', name); finish(fallbackAvatar(name)); });
  });
}

/* GLB yang selesai SETELAH timeout 8 dtk: ganti stand-in dengan model
   asli di tempat. Dulu hasil telat ini dibuang diam-diam oleh finish()
   — akar silinder permanen di browser lambat: 13 decode antre 2 worker,
   total ~14 dtk, semua kena timeout dulu baru OK. */
function replaceAvatarInner(name, obj) {
  const turn = avatarMeshes[name];
  if (!turn) return;
  const old = turn.children[0];
  if (old) {
    old.traverse((o) => {
      const i = clickables.indexOf(o);
      if (i >= 0) clickables.splice(i, 1);
    });
    turn.remove(old);
  }
  obj.traverse((o) => {
    o.userData.agent = name; clickables.push(o);
    if (o.isMesh) o.castShadow = true;
  });
  turn.add(obj);
  attachActivityProps(name);
  requestRender();
}

async function loadAvatars() {
  const results = await Promise.all(ROOM_ORDER.map(loadOneAvatar));
  ROOM_ORDER.forEach((name, i) => {
    const inner = results[i];
    /* AAA L3 — avatar menjatuhkan bayangan nyata (receive mati
       supaya tidak acne pada mesh chibi; grounding dibantu blob). */
    inner.traverse((o) => {
      o.userData.agent = name; clickables.push(o);
      if (o.isMesh) o.castShadow = true;
    });
    /* turn = sub-group khusus rotasi (arah hadap + tilt + goyang
       kerja). Grup luar (avatarGroups) TIDAK dirotasi supaya blob
       shadow tetap sejajar sumbu-x. */
    const turn = new THREE.Group();
    turn.add(inner);
    avatarMeshes[name] = turn;
    avatarGroups[name].add(turn);
    /* Props aktivitas ditempel ke bone tangan (bila ada skeleton). */
    attachActivityProps(name);
    /* Tugas 6: wajah pixel 3D (drawFace) DIHAPUS — indikator di atas
       kepala kini hanya ikon aktivitas (lihat updateBubbles);
       gambar smile/disc mood DIHAPUS 27 Nov 2026 (perintah Rangga:
       cukup ikon aktivitas saja). */
  });
}

/* --- indikator gabungan (overlay HTML, Tugas 6 revisi) ----------- */
/* SATU pill per agen di atas kepala: HANYA ikon aktivitas (glyph
   pixel 16x16, GLYPH_DEFS) + teks status/ucapan bila ada. Gambar
   smile/disc mood DIHAPUS 27 Nov 2026 (perintah Rangga: cukup ikon
   aktivitas saja). Prioritas teks: speech (15 dtk) > status (kerja)
   > ikon saja. Pill SELALU terpasang (ikon saja tidak pernah
   hilang); perubahan konten di-cache (signature) + fade opacity
   0.25 dtk, jadi tidak lompat/kedip/muncul-hilang kasar. Anchor
   tunggal y = 2.05 + posisi grup (ikut saat duduk); proyeksi memakai
   matriks kamera yang baru (render() memanggil
   camera.updateMatrixWorld() dulu — perbaikan drift). Maks 3 pill
   ber-TEKS (speech/status, §5.12); pill ikon saja tampil untuk
   semua 13 agen. Di bawah 700px hanya ikon + nama (teks lengkap
   pindah ke kartu agen). Pass anti-tumpuk: bila dua pill bertumpuk,
   yang kedua digeser ke atas. */
const bubbleEls = {}; /* name -> {el, sig} */
function glyphSvg(glyph) {
  return '<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">'
    + (GLYPH_DEFS[glyph] || '') + '</svg>';
}
/* moodFaceSvg (disc smile volt + mata/mulut) DIHAPUS 27 Nov 2026 —
   perintah Rangga: cukup ikon aktivitas saja (GLYPH_DEFS). */
function ensureBubbles() {
  for (const name of ROOM_ORDER) {
    if (bubbleEls[name]) continue;
    const el = document.createElement('div');
    el.className = 'bubble indicator';
    el.dataset.agent = name;
    el.style.display = 'none';
    el.style.transition = 'opacity .25s ease';
    el.innerHTML = '<span class="glyph"></span><span class="nm"></span><span class="txt"></span><span class="time" style="display:none"></span>';
    /* Klik namecard = POV agen (Rangga 27 Nov 21:12): sama seperti
       klik avatar — hero -> fullscreen + follow, fullscreen -> follow.
       Layer #roomBubbles pointer-events:none, tapi .bubble
       pointer-events:auto (lihat SHOWCASE_CSS), jadi klik di pill
       mendarat di sini, bukan tembus ke canvas. */
    el.addEventListener('click', (ev) => {
      ev.stopPropagation();
      if (displayMode === 'hero') { enterFullscreen(); }
      enterFollow(name);
    });
    bubbleLayer.appendChild(el);
    bubbleEls[name] = { el, sig: '' };
  }
}

function projectToScreen(x, y, z) {
  const v = new THREE.Vector3(x, y, z).project(camera);
  const w = wrap.clientWidth || 800;
  const h = wrap.clientHeight || 600;
  return { x: (v.x * 0.5 + 0.5) * w, y: (-v.y * 0.5 + 0.5) * h, behind: v.z > 1 };
}

function updateBubbles() {
  if (!state || !camera || !bubbleLayer) return;
  /* Kelas ukuran pill (cek visual 26 Nov 2026): overview = pill
     tugas dikecilkan (max-width 150px, CSS); zoom jauh (camZoom
     < 0.9) = teks tugas disembunyikan — pill kecil tidak menumpuk
     jauh di atas avatarnya. */
  const farZoom = cameraMode !== 'follow' && camZoom < 0.9;
  const w = wrap.clientWidth || 800;
  const h = wrap.clientHeight || 600;
  bubbleLayer.classList.toggle('overview', cameraMode !== 'follow');
  bubbleLayer.classList.toggle('far-zoom', farZoom);
  /* Batas tampil (§5.12 / 11/10): maks 3 pill ber-TEKS di canvas —
     speech dulu (terbaru), lalu status (terbaru). Pill ikon saja
     tidak dihitung (tampil untuk semua agen). */
  const candidates = [];
  for (const st of state.agents) {
    if (st.statusText) {
      candidates.push({ kind: 'status', name: st.name, ts: st.lastActiveMs || 0 });
    }
    const els0 = bubbleEls[st.name];
    if (els0 && els0.el.dataset.show === '1' && st.speech) {
      candidates.push({ kind: 'speech', name: st.name, ts: (st.lastMessage && st.lastMessage.createdAtMs) || 0 });
    }
  }
  const shown = new Set(selectVisibleBubbles(candidates, 3).map((c) => c.kind + ':' + c.name));
  lastBubblesShown = shown.size;
  const placed = [];
  for (const st of state.agents) {
    const entry = bubbleEls[st.name];
    if (!entry) continue;
    const el = entry.el;
    const pos = avatarPos[st.name];
    const g = avatarGroups[st.name];
    /* Pill agen yang di-follow disembunyikan (dulu sprite wajah
       disembunyikan di updateFollowCamera). */
    if (!pos || !g.visible || (cameraMode === 'follow' && followName === st.name)) {
      el.style.display = 'none';
      continue;
    }
    /* Mode teks: speech > status > ikon saja. Ikon aktivitas SELALU
       tampil (semua mode); saat agen sedang berjalan antar ruangan,
       ikon diganti jejak langkah. */
    let mode = 'icon';
    if (el.dataset.show === '1' && st.speech && shown.has('speech:' + st.name)) mode = 'speech';
    else if (st.statusText && shown.has('status:' + st.name)) mode = 'status';
    const walking = !!(walks[st.name] && !walks[st.name].cancelled);
    const glyph = walking ? 'walk' : (st.glyph || 'zzz');
    const text = mode === 'speech' ? st.speech.text : mode === 'status' ? (st.statusText || '').replace(/^Mengerjakan: /, '').replace(/^— /, '') : ''; /* pill: judul tugas saja, prefix sudah diwakili glyph kerja */
    const time = mode === 'speech' ? st.speech.hhmm : null;
    const stale = mode === 'status' && !!st.stale;
    const boss = mode === 'status' && st.name === 'rangga' && state.bossActive;
    const sig = mode + '|' + glyph + '|' + text + '|' + (time || '') + '|' + (stale ? 1 : 0) + '|' + (boss ? 1 : 0);
    /* Opacity akhir = 0.55 bila stale (cermin .bubble.status.stale
       di host CSS — opacity inline menimpa class, jadi nilainya
       ditulis eksplisit di sini). */
    const targetOpacity = stale ? 0.55 : 1;
    if (sig !== entry.sig) {
      /* Transisi halus: fade out -> ganti konten -> fade in ke
         opacity akhir. Fade hanya saat konten berubah, bukan tiap
         frame (render-on-demand: updateBubbles jalan tiap render). */
      const first = entry.sig === '';
      const apply = () => {
        const gEl = el.querySelector('.glyph');
        gEl.innerHTML = glyphSvg(glyph);
        const nmEl = el.querySelector('.nm');
        if (nmEl) nmEl.textContent = st.label || st.name;
        const tEl = el.querySelector('.txt');
        tEl.textContent = text;
        tEl.style.display = text ? '' : 'none';
        const tmEl = el.querySelector('.time');
        if (time) { tmEl.textContent = time; tmEl.style.display = ''; } else { tmEl.style.display = 'none'; }
        el.classList.toggle('status', mode === 'status');
        el.classList.toggle('speech', mode === 'speech');
        el.classList.toggle('icon', mode === 'icon');
        el.classList.toggle('stale', stale);
        el.classList.toggle('boss', boss);
        el.style.opacity = targetOpacity;
      };
      entry.sig = sig;
      if (first) apply();
      else { el.style.opacity = 0; requestAnimationFrame(apply); }
    }
    el.style.display = 'flex';
    /* Anchor tunggal 2.05 + posisi grup (ikut saat duduk) — sama
       seperti posisi sprite lama; 0.45 di atas puncak kepala (1.6),
       jadi tidak menutupi wajah. */
    const p = projectToScreen(pos.x, 2.05 + (g.position.y || 0), pos.z);
    /* Follow mode (cek visual 26 Nov 2026, perbaikan 12:30 WIB):
       pill agen JAUH yang anchornya jatuh di luar layar JANGAN
       dijepit ke tepi (clamp lama menumpuk semua label jauh di
       tepi atas/kanan, lepas dari avatarnya) — sembunyikan saja.
       Pill di belakang kamera juga tidak ikut pass anti-tumpuk
       (koordinat proyeksinya terbalik, dulu ikut mendorong pill
       lain). Di overview semua agen memang di dalam frustum, jadi
       aturan ini praktis hanya kena follow mode. Oklusi dinding:
       tidak ada dinding interior (ruangan open-plan, cuma 4
       dinding luar) — agen di ruangan lain tidak tertutup dinding,
       hanya bisa jauh/off-screen, sudah ditangkap aturan ini. */
    if (p.behind || (cameraMode === 'follow' && (p.x < -24 || p.x > w + 24 || p.y < -24 || p.y > h + 24))) {
      el.style.display = 'none';
      continue;
    }
    el.dataset.px = p.x.toFixed(1);
    el.dataset.py = p.y.toFixed(1);
    el.style.left = p.x + 'px';
    el.style.top = p.y + 'px';
    el.style.visibility = 'visible';
    placed.push(el);
  }
/* Anti-tumpuk berbasis RECT + tinggi pill ASLI (cek visual 26 Nov
   2026, perbaikan 12:30 WIB): vGap tetap 36px dulu menumpuk karena
   pill ber-TEKS bisa ~48px tingginya — dua pill yang top-nya 42px
   tetap saling menimpa. Sekarang tiap pill diukur
   (offsetWidth/offsetHeight) dan diuji tumpang-tindih sebagai rect
   (anchor = tengah-bawah pill, translate(-50%,-100%)); yang
   bertabrakan digeser ke ATAS sampai bersih, maks 150px di atas
   anchornya; bila mentok, geser ke BAWAH rect yang ditabrak.
   Tinggi asli otomatis menangkap pill yang mengecil di far-zoom
   (teks tugas disembunyikan) — tanpa angka khusus lagi. Clamp
   kiri/kanan memakai setengah lebar pill, bukan 95px tetap. */
  const GAP = 4; /* celah antar pill */
  const MAX_UP = 150; /* geser ke atas maks di atas anchor */
  const placedRects = [];
  const ordered = placed.slice().sort((a, b) => parseFloat(a.dataset.py) - parseFloat(b.dataset.py));
  for (const el of ordered) {
    const pw = el.offsetWidth || 190;
    const ph = el.offsetHeight || 28;
    let x = Math.min(Math.max(parseFloat(el.dataset.px), pw / 2 + GAP), Math.max(pw / 2 + GAP, w - pw / 2 - GAP));
    let y = Math.min(Math.max(parseFloat(el.dataset.py), ph + GAP), h - GAP);
    const anchorY = y;
    const rectOf = () => ({ x0: x - pw / 2, x1: x + pw / 2, y0: y - ph, y1: y });
    const hits = (r) => placedRects.filter((q) => r.x0 < q.x1 + GAP && r.x1 > q.x0 - GAP && r.y0 < q.y1 + GAP && r.y1 > q.y0 - GAP);
    let guard = 0;
    let clash = hits(rectOf());
    while (clash.length && guard < 24) {
      guard++;
      /* Kolom = semua pill yang tumpang-tindih horizontal dengan
         pill ini (x tidak berubah selama loop). Pindah ke atas
         SEMUA rect kolom, atau — bila itu terlalu jauh dari anchor
         — ke bawah SEMUA rect kolom. Kedua posisi dijamin bebas
         tabrakan dengan kolom (bukan cuma dengan yang sedang
         ditabrak — itu bisa osilasi naik-turun), jadi loop
         berhenti. */
      const column = placedRects.filter((q) => rectOf().x0 < q.x1 + GAP && rectOf().x1 > q.x0 - GAP);
      const upY = Math.min(...column.map((q) => q.y0 - GAP));
      const downY = Math.max(...column.map((q) => q.y1 + GAP + ph));
      /* Urutan: naik dekat anchor dulu; kalau tidak muat, turun;
         kalau turun mentok tepi bawah, naik JAUH (lewat MAX_UP)
         daripada menumpuk — pill jauh dari avatar masih terbaca,
         pill yang menumpuk tidak (27 Nov 2026: 8 pill numpuk di
         Front Office, turunnya mentok clamp bawah lalu guard
         menyerah dengan overlap). */
      const upNear = upY >= ph + GAP && (anchorY - upY <= MAX_UP);
      const downFits = downY <= h - GAP;
      if (upNear) y = upY;
      else if (downFits) y = downY;
      else if (upY >= ph + GAP) y = upY;
      else y = downY;
      y = Math.min(Math.max(y, ph + GAP), h - GAP);
      clash = hits(rectOf());
    }
    placedRects.push(rectOf());
    el.style.left = x + 'px';
    el.style.top = y + 'px';
  }
}

/* Miniatur avatar voxel — SATU-SATUNYA tempat room3d.js memanggil
   avatarVoxel (tes 0.4.8 menghitung kemunculan string itu = 1):
   portrait strip, kartu info follow, dan kartu agen vertikal HP
   semuanya lewat helper ini. */
function miniAvatarHTML(name) {
  return window.avatarVoxel ? window.avatarVoxel(name) : '';
}

/* --- portrait strip (§5.12) -------------------------------------- */
/* renderPortraits() mengisi #roomPortraits (container + CSS dibuat
   Worker C di index.html; bila elemen belum ada, diam-diam lewati).
   Satu tombol per agen (ROOM_ORDER): miniatur avatarVoxel + nama +
   role; agen aktif dapat class 'active' +
   border warna identitas (style inline borderColor). Klik →
   fullscreen + follow agen itu. Tanpa snapshot: semua portrait
   redup, tanpa highlight. */
function renderPortraits() {
  const el = document.getElementById('roomPortraits');
  if (!el) return;
  el.textContent = '';
  const noSnap = !snapLoaded || !state;
  for (const name of ROOM_ORDER) {
    const info = KNOWN_AGENTS[name];
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'portrait';
    btn.dataset.agent = name;
    const mini = document.createElement('span');
    mini.className = 'mini-avatar';
    mini.innerHTML = miniAvatarHTML(name);
    btn.appendChild(mini);
    const nm = document.createElement('span');
    nm.className = 'portrait-name';
    nm.textContent = info.label;
    btn.appendChild(nm);
    const rl = document.createElement('span');
    rl.className = 'portrait-role';
    rl.textContent = info.role;
    btn.appendChild(rl);
    if (noSnap) {
      btn.classList.add('dim');
      btn.style.opacity = '0.55';
    } else if (name === currentActiveAgent) {
      btn.classList.add('active');
      btn.style.borderColor = info.color;
    }
    btn.addEventListener('click', () => { enterFullscreen(); enterFollow(name); });
    el.appendChild(btn);
  }
}

/* --- kartu info agen saat follow (chip "Mengikuti <nama>") -------- */
/* Dibuat dinamis di room-showcase.js: panel kecil di sudut canvas
   saat follow — chip "Mengikuti <nama> · <peran>" + ruangan saat
   ini + status/tugas aktif + tombol tutup (× = lepas follow).
   Read-only: TANPA tombol lompat (tidak ada pesan/tugas untuk
   dilompati). Semua teks via textContent.
   LEBAR 28 Nov 2026 (Rangga: kartu Mengikuti sempit, nama ke-wrap
   3 baris): maxWidth 340px + media query min(340px, 100vw-16px),
   dan status/meta TIDAK lagi disembunyikan di HP (aturan lama
   display:none dihapus) — info agen pindah ke sini setelah list
   ruangan di page dihapus. */
function ensureFollowCard() {
  if (followCardEl) return followCardEl;
  if (!wrap) return null;
  const el = document.createElement('div');
  el.id = 'roomFollowCard';
  el.style.position = 'absolute';
  el.style.left = '8px';
  el.style.bottom = '8px';
  el.style.zIndex = '5';
  el.style.maxWidth = '340px';
  el.style.background = 'rgba(22, 27, 34, .95)';
  el.style.border = '1px solid #2d333b';
  el.style.borderRadius = '8px';
  el.style.padding = '.5rem .7rem';
  el.style.color = '#e6e6e6';
  el.style.fontSize = '.85rem';
  el.style.lineHeight = '1.4';
  el.style.display = 'none';
  const head = document.createElement('div');
  head.style.display = 'flex';
  head.style.gap = '.5rem';
  head.style.alignItems = 'center';
  const mini = document.createElement('span');
  mini.className = 'mini-avatar';
  head.appendChild(mini);
  const nm = document.createElement('b');
  nm.style.flex = '1 1 auto';
  nm.style.minWidth = '0';
  head.appendChild(nm);
  const close = document.createElement('button');
  close.type = 'button';
  close.textContent = '×'; /* U+00D7 (bukan emoji — tes 0.4.8 melarang
    blok Dingbats U+2600–U+27BF). */
  close.setAttribute('aria-label', 'Keluar follow');
  close.style.marginLeft = 'auto';
  close.style.flexShrink = '0';
  close.style.background = 'transparent';
  close.style.border = 'none';
  close.style.color = '#9aa0a6';
  close.style.cursor = 'pointer';
  close.style.fontSize = '1rem';
  close.addEventListener('click', () => exitFollow());
  head.appendChild(close);
  el.appendChild(head);
  const room = document.createElement('div');
  room.className = 'follow-room';
  room.style.color = '#9aa0a6';
  room.style.fontSize = '.8rem';
  room.style.overflowWrap = 'break-word';
  el.appendChild(room);
  const status = document.createElement('div');
  status.className = 'follow-status';
  status.style.overflowWrap = 'break-word';
  el.appendChild(status);
  const meta = document.createElement('div');
  meta.className = 'follow-meta';
  meta.style.color = '#9aa0a6';
  meta.style.fontSize = '.8rem';
  meta.style.overflowWrap = 'break-word';
  el.appendChild(meta);
  /* Showcase read-only: tanpa tombol lompat. Chip follow = kartu ini. */
  el.userData = { mini, nm, room, status, meta };
  wrap.appendChild(el);
  followCardEl = el;
  return el;
}
function refreshFollowCard() {
  if (cameraMode !== 'follow' || !followName) { hideFollowCard(); return; }
  const el = ensureFollowCard();
  if (!el) return;
  const u = el.userData;
  const info = KNOWN_AGENTS[followName];
  const st = state && state.agents.find((a) => a.name === followName);
  u.mini.innerHTML = miniAvatarHTML(followName);
  u.nm.textContent = 'Mengikuti ' + info.label + ' · ' + info.role;
  el.style.borderColor = info.color;
  /* Ruangan SAAT INI dari state snapshot (bukan home lane): st.room
     diisi snapshotToState + diperbarui saat agen pindah (wander). */
  u.room.textContent = st && st.room ? ('Ruangan: ' + (ROOMS[st.room] ? ROOMS[st.room].label : st.room)) : '';
  u.status.textContent = st ? (st.statusText || '— mode otonom —') : '—';
  u.meta.textContent = st ? ('aktif ' + st.lastActiveLabel + ' · ' + st.openCount + ' tugas') : '';
  el.style.display = 'block';
}
function hideFollowCard() {
  if (followCardEl) followCardEl.style.display = 'none';
}

/* --- gerakan ------------------------------------------------------- */
/* Jalan antar ruangan (§5.6): HANYA transisi antar dua keadaan
   nyata, 2-3 detik, lewat gang (planWalk). Bila keadaan berubah
   lagi saat jalan, jalan lama dibatalkan dan mulai dari posisi
   terakhir. Tanpa rigging kaki: translasi mesh utuh + bob + tilt.
   Oto: hop slime (squash + stretch). prefers-reduced-motion:
   pindah instan. */
function setAvatarPos(name, slot, room, sitting = false, opts = {}) {
  const g = avatarGroups[name];
  const baseY = sitting ? -sitDropFor(name) : 0;
  avatarBaseY[name] = baseY;
  /* Simpan arah hadap slot (untuk kamera follow saat diam). */
  avatarSlotRot[name] = (slot && typeof slot.rot === 'number') ? slot.rot : 0;
  const ps = poseState[name] || (poseState[name] = { sitting: false, activity: null });
  ps.sitting = !!sitting;
  g.position.x = slot.x;
  g.position.z = slot.z;
  /* Geser duduk ke meja (DESK_SLIDE) bila duduk di meja: avatar
     "nyurung" mendekati meja supaya tangan mencapai keyboard
     (fk-sweep2: lutut tidak menembus meja pada 0.15; chibi 2026-11-25: slide 0.20-0.35,
     lutut tetap clear >= 0.06 dari meja). Posisi logis
     (avatarPos) tetap di slot; hanya posisi render yang digeser. */
  if (sitting && isDeskSlotFn(room, slot)) {
    const rot = (slot && typeof slot.rot === 'number') ? slot.rot : 0;
    g.position.x += Math.sin(rot) * (DESK_SLIDE + (DESK_SLIDE_EXTRA[name] || 0));
    g.position.z += Math.cos(rot) * (DESK_SLIDE + (DESK_SLIDE_EXTRA[name] || 0));
  }
  g.scale.set(1, 1, 1);
  const turn = avatarMeshes[name];
  if (turn) {
    turn.rotation.x = 0;
    turn.rotation.z = 0;
    /* Perintah bos (§5.4.5): bila Rangga baru posting, semua avatar
       menoleh ke meja Rangga — bukan ke arah slotnya. Titik meja
       diambil dari ROOMS (slot pertama kantor-rangga), BUKAN
       hardcode — Worker F memindah kantor Rangga di layout baru
       (42×28) dan tatapan harus ikut pindah. */
    const bossSlot = ROOMS['kantor-rangga'] && ROOMS['kantor-rangga'].slots
      ? ROOMS['kantor-rangga'].slots[0] : null;
    turn.rotation.y = (state && state.bossActive && name !== 'rangga' && bossSlot)
      ? Math.atan2(bossSlot.x - slot.x, bossSlot.z - slot.z)
      : slot.rot;
  }
  avatarPos[name] = { x: slot.x, z: slot.z };
  avatarRoom[name] = room;
  /* Pose: snap langsung bila penempatan awal/teleport fixture;
     bila tidak, blend ~400 ms dari bobot saat ini (100/10). */
  if (opts.snap || !poseAnim[name]) {
    snapPoseWeights(name);
    g.position.y = baseY;
  } else {
    startPoseTransition(name);
  }
}

function walkBobY(name, p) {
  if (name === 'oto') return Math.abs(Math.sin(p * Math.PI * 4)) * 0.14;
  return Math.abs(Math.sin(p * Math.PI * 3)) * 0.05;
}

function updateHookWalking() {
  if (window.__showcasePreview) window.__showcasePreview.walking = anyWalking;
}

function walkAgent(name, toSlot, toRoom, opts = {}) {
  return new Promise((resolve) => {
    const g = avatarGroups[name];
    /* Berangkat dari posisi render saat ini (bisa 0.15 tergeser ke
       meja saat duduk) — bukan dari slot logis — supaya tidak ada
       lompatan 0.15 di frame pertama jalan. */
    const from = g ? { x: g.position.x, z: g.position.z }
      : (avatarPos[name] ? { ...avatarPos[name] } : { ...toSlot });
    const fromRoom = avatarRoom[name];
    if (REDUCED || !avatarPos[name]) {
      setAvatarPos(name, toSlot, toRoom, !!opts.sitting, { snap: true });
      requestRender();
      resolve(true);
      return;
    }
    if (walks[name]) {
      walks[name].cancelled = true;
      cancelAnimationFrame(walks[name].raf);
    }
    const path = planWalk(from, toSlot, fromRoom, toRoom);
    let total = 0;
    for (let i = 1; i < path.length; i++) {
      total += Math.hypot(path[i].x - path[i - 1].x, path[i].z - path[i - 1].z);
    }
    if (total < 0.01) {
      setAvatarPos(name, toSlot, toRoom, !!opts.sitting, { snap: true });
      requestRender();
      resolve(true);
      return;
    }
    /* Awal jalan: bobot duduk awal = bobot render saat ini (biasanya
       1 bila berangkat dari kursi, 0 bila berdiri); target duduk =
       tujuan. Transisi duduk ↔ berdiri di-blend DI DALAM jalan
       (15% awal/akhir), bukan snap. Driver blend pose dilewati
       selama jalan (walk yang mengatur bone). */
    const targetSit = !!opts.sitting;
    const sitWStart = poseAnim[name] ? poseAnim[name].sittingW : (poseState[name] && poseState[name].sitting ? 1 : 0);
    delete poseTrans[name];
    /* Durasi jalan dari PANJANG path — rumus BASE (cap 2–3 dtk,
       lantai 2 dtk): rute pendek tetap 2 dtk, rute terpanjang di
       denah baru (~40 satuan) kena cap 3 dtk → ~14 satuan/dtk.
       Fase ayun kaki tetap dari jarak tempuh (tidak selip). */
    const dur0 = Math.min(3000, Math.max(2000, 1200 + total * 350));
    /* opts.slow (hanya dari hook preview): walk 3x lebih lambat supaya
       harness sempat menangkap banyak frame di SwiftShader (screenshot
       saat walk ~1 detik/frame). Walk produksi/live SELALU 2-3 detik. */
    const dur = opts.slow ? dur0 * 3 : dur0;
    const start = performance.now();
    const token = { cancelled: false, raf: 0 };
    walks[name] = token;
    anyWalking = true;
    updateHookWalking();
    const inner = avatarMeshes[name];
    const roles = JOINT_ROLES[name];
    const stride = 0.9;
    const step = (t) => {
      if (token.cancelled) {
        delete walks[name];
        anyWalking = Object.values(walks).some((w) => !w.cancelled);
        updateHookWalking();
        resolve(false);
        return;
      }
      const p = Math.min(1, (t - start) / dur);
      /* 100/10: progress easeInOutCubic (akselerasi/deselerasi
         halus); fase ayun dari JARAK TEMPUH (pe * total) supaya
         sinambung tanpa lompat fase di awal. */
      const pe = easeInOutCubic(p);
      const d = pe * total;
      let acc = 0;
      let seg = { a: path[path.length - 1], b: path[path.length - 1], f: 0 };
      for (let i = 1; i < path.length; i++) {
        const len = Math.hypot(path[i].x - path[i - 1].x, path[i].z - path[i - 1].z);
        if (d <= acc + len) { seg = { a: path[i - 1], b: path[i], f: len ? (d - acc) / len : 0 }; break; }
        acc += len;
      }
      const x = seg.a.x + (seg.b.x - seg.a.x) * seg.f;
      const z = seg.a.z + (seg.b.z - seg.a.z) * seg.f;
      const moving = Math.hypot(seg.b.x - seg.a.x, seg.b.z - seg.a.z) > 0.01;
      /* Fade ayun di 15% awal/akhir + bobot duduk yang menyatu:
         berangkat duduk → berdiri pelan (15% awal), tiba → duduk
         pelan (15% akhir). Tinggi grup = bob jalan + tinggi duduk
         terbobot (tanpa pop vertikal). */
      const fadeIn = smoothstep(p / 0.15);
      const fadeOut = 1 - smoothstep((p - 0.85) / 0.15);
      const swingAmp = fadeIn * fadeOut;
      const sitW = sitWStart * (1 - fadeIn) + (targetSit ? 1 : 0) * smoothstep((p - 0.85) / 0.15);
      g.position.set(x, walkBobY(name, pe) - sitDropFor(name) * sitW, z);
      if (inner) {
        inner.rotation.y = moving
          ? Math.atan2(seg.b.x - seg.a.x, seg.b.z - seg.a.z)
          : toSlot.rot;
        inner.rotation.x = 0;
      }
      /* Jalan rigged: ayunan bone dari base (ganti tilt mesh utuh).
         Fase = jarak tempuh * 2π / stride. Paha ±25° sin berlawanan,
         betis setengah amplitudo (±12°) sefase tertinggal, bahu
         berlawanan dengan kaki seberang (bahu L lawan kaki R).
         LENGAN HANYA MENGAYUN MAJU (2026-11-21): ayun maju 15°,
         ayun mundur 0° — ayun mundur sempat membawa tangan belakang
         MASUK ke dalam kotak torso pada Neto (fk-out4: -0.006 pada
         mundur 5°, padahal sudah fix 30°); dengan mundur 0°, tangan
         belakang tetap pada posisi idle-fix (margin ≥ +0.035 di semua
         avatar, terukur). Duduk disusun di atasnya dengan bobot sitW
         (bone yang sama dikalikan berurutan dari base — tidak
         akumulasi antar frame). */
      if (roles) {
        const phase = (d * Math.PI * 2) / stride;
        const s = Math.sin(phase);
        const sLag = Math.sin(phase - 0.7);
        const deltas = [
          { bone: roles.thighL, axis: [1, 0, 0], deg: 25 * s * swingAmp },
          { bone: roles.thighR, axis: [1, 0, 0], deg: -25 * s * swingAmp },
          { bone: roles.shinL, axis: [1, 0, 0], deg: -12 * sLag * swingAmp },
          { bone: roles.shinR, axis: [1, 0, 0], deg: 12 * sLag * swingAmp },
          { bone: roles.shoulderL, axis: [1, 0, 0], deg: Math.max(0, 15 * s) * swingAmp },
          { bone: roles.shoulderR, axis: [1, 0, 0], deg: Math.max(0, -15 * s) * swingAmp },
        ];
        if (sitW > 0.001) {
          for (const sd of sitDeltas(name, roles)) deltas.push({ ...sd, deg: sd.deg * sitW });
        }
        /* Perbaikan lengan (anti-buntung) + pose mengetik (bila tiba
           di meja): disusun di atas base seperti pose lain. Mengetik
           memudar bersama sitW di 15% akhir jalan. Sumbu bahu di sini
           dikonjugasi terhadap base (satu fase) — cukup untuk transisi;
           pose akhir yang persis (two-phase) diterapkan di akhir jalan
           lewat applyPoseWeighted. */
        for (const d of armFixDeltas(name, roles)) deltas.push(d);
        const typeW = (targetSit && isDeskSlotFn(toRoom, toSlot))
          ? sitW * (1 - ((poseAnim[name] && poseAnim[name].activityW) || 0)) : 0;
        if (typeW > 0.001) {
          deltas.push({ bone: roles.spine, axis: [1, 0, 0], deg: (TYPE_SPINE_DEG + (TYPE_SPINE_EXTRA[name] || 0)) * typeW });
          deltas.push({ bone: roles.head, axis: [1, 0, 0], deg: TYPE_HEAD_DEG * typeW });
          deltas.push({ bone: roles.shoulderL, axis: worldAxisLocal(name, roles.shoulderL, [1, 0, 0]), deg: -(TYPE_SHOULDER_DEG + (TYPE_SHOULDER_FWD_EXTRA[name] || 0)) * typeW });
          deltas.push({ bone: roles.shoulderR, axis: worldAxisLocal(name, roles.shoulderR, [1, 0, 0]), deg: -(TYPE_SHOULDER_DEG + (TYPE_SHOULDER_FWD_EXTRA[name] || 0)) * typeW });
          deltas.push({ bone: roles.forearmL, axis: [1, 0, 0], deg: TYPE_FOREARM_DEG * typeW });
          deltas.push({ bone: roles.forearmR, axis: [1, 0, 0], deg: TYPE_FOREARM_DEG * typeW });
          /* Tugas 1 (transien, single-phase — pose akhir persis
             disetel applyPoseWeighted saat jalan selesai). */
          for (const d of typingHandDeltas(name, roles, typeW, worldAxisLocal)) deltas.push(d);
        }
        resetBones(name);
        addBoneDeltas(name, deltas);
      }
      if (name === 'oto') {
        const hop = Math.abs(Math.sin(pe * Math.PI * 4));
        g.scale.set(1 + hop * 0.06, 1 + hop * 0.12, 1 + hop * 0.06);
      }
      avatarPos[name] = { x, z };
      render();
      if (p < 1) {
        token.raf = requestAnimationFrame(step);
      } else {
        delete walks[name];
        anyWalking = Object.values(walks).some((w) => !w.cancelled);
        updateHookWalking();
        /* Akhir jalan: bobot render sudah = target (disusun di
           step terakhir) — samakan poseAnim supaya driver blend
           tidak menganimasikan ulang; lalu setAvatarPos (blend
           hanya bila aktivitas ikut berubah). */
        if (poseAnim[name]) poseAnim[name].sittingW = targetSit ? 1 : 0;
        avatarBaseY[name] = targetSit ? -sitDropFor(name) : 0;
        setAvatarPos(name, toSlot, toRoom, targetSit);
        /* Tetapkan pose akhir yang persis (perbaikan lengan +
           mengetik two-phase): driver blend tidak selalu memanggil
           applyPoseWeighted bila tidak ada perubahan bobot. */
        applyPoseWeighted(name);
        requestRender();
        resolve(true);
      }
    };
    token.raf = requestAnimationFrame(step);
  });
}

/* Ambient bob 2px (§5.6): DEKORATIF, timer acak 20-60 detik,
   tanpa requestAnimationFrame. Tidak mengklaim online/mengetik. */
function scheduleAmbient(name) {
  setTimeout(() => {
    scheduleAmbient(name);
    if (REDUCED || document.hidden) return;
    const g = avatarGroups[name];
    if (!g || !g.visible || walks[name]) return;
    const baseY = avatarBaseY[name] || 0;
    g.position.y = baseY + 0.09; /* napas: 0,03 lama tidak terlihat (review 20 Nov) */
    requestRender();
    setTimeout(() => { g.position.y = baseY; requestRender(); }, 450);
  }, 20000 + Math.random() * 40000);
}
function startAmbient() {
  for (const name of ROOM_ORDER) scheduleAmbient(name);
}

/* Gerakan kerja (§5.6): 2 frame, 1 siklus / 2 detik, selama tugas
   aktif — penanda STATE, bukan feed live. */
function startWorkTimer() {
  if (workTimer) return;
  workTimer = setInterval(() => {
    if (REDUCED || document.hidden || !state) return;
    const working = state.agents.filter((a) => a.activeTask && !walks[a.name]);
    if (!working.length) return;
    workPhase ^= 1;
    for (const st of working) {
      const inner = avatarMeshes[st.name];
      if (inner) inner.rotation.z = workPhase ? 0.035 : -0.035;
    }
    requestRender();
  }, 1000);
}

function startClockTimer() {
  if (clockTimer) return;
  clockTimer = setInterval(() => {
    dynamicPanels.clock.redraw();
    requestRender();
  }, 60000);
}

/* Timer aktivitas (interval 500 ms, seperti workTimer): pose kopi
   berubah mengikuti siklus ~8 dtk, pose HP berubah saat tilt
   sesekali. Hanya requestRender bila ada perubahan. Tanpa animasi
   mengetik. */
let activityTimer = null;
function startActivityTimer() {
  if (activityTimer) return;
  activityTimer = setInterval(() => {
    if (REDUCED || document.hidden || !state) return;
    const now = performance.now();
    let changed = false;
    for (const st of state.agents) {
      const act = (poseState[st.name] || {}).activity;
      if (!act || walks[st.name]) continue;
      const anim = poseAnim[st.name];
      if (!anim || anim.activity !== act) continue;
      const deltas = activityDeltas(st.name, act, now);
      const sig = act + ':' + deltas.map((d) => d.bone + '=' + d.deg.toFixed(1)).join(',');
      if (activityPoseCache[st.name] !== sig) {
        activityPoseCache[st.name] = sig;
        applyPoseWeighted(st.name, now);
        changed = true;
      }
    }
    if (changed) requestRender();
  }, 500);
}

/* Timer hidup (interval 250 ms, seperti monitor): napas/idle + ketik
   berubah terus, jadi pose harus disusun ulang berkala. Hanya
   requestRender bila ada perubahan (signature per avatar, seperti
   activityTimer). Tidak jalan saat REDUCED / tab tersembunyi / tidak
   ada agen yang berdiri atau mengetik — 0 render/detik bila semua
   diam atau duduk. 250 ms (bukan 500) supaya ketikan ~1.5 dtk
   tersampel 5-6x per siklus; napas ~5 dtk tersampel ~20x. */
let lifeTimer = null;
const lifePoseCache = {}; /* name -> signature gerak hidup terakhir */
function startLifeTimer() {
  if (lifeTimer) return;
  lifeTimer = setInterval(() => {
    if (REDUCED || document.hidden || !state) return;
    const now = performance.now();
    let changed = false;
    for (const st of state.agents) {
      const name = st.name;
      if (walks[name]) continue;
      const anim = poseAnim[name];
      if (!anim) continue;
      const typeW = typingWeight(name);
      const standW = (anim.sittingW <= 0.001 && typeW <= 0.001) ? (1 - (anim.activityW || 0)) : 0;
      if (standW <= 0.001 && typeW <= 0.001) {
        if (lifePoseCache[name] !== '') lifePoseCache[name] = '';
        continue;
      }
      const sigParts = [];
      if (standW > 0.001) for (const d of idleLifeDeltas(name, now)) sigParts.push(d.bone + '=' + (d.deg * standW).toFixed(1));
      if (typeW > 0.001) for (const d of typingLifeDeltas(name, now)) sigParts.push(d.bone + '=' + (d.deg * typeW).toFixed(1));
      const sig = sigParts.join(',');
      if (lifePoseCache[name] !== sig) {
        lifePoseCache[name] = sig;
        applyPoseWeighted(name, now);
        changed = true;
      }
    }
    if (changed) requestRender();
  }, 250);
}

/* Pose selebrasi (§5.4.3, bonus): lompat kecil 3x saat tugas
   selesai terdeteksi di polling. */
function celebrate(name) {
  if (REDUCED) return;
  const g = avatarGroups[name];
  if (!g || !g.visible) return;
  const baseY = avatarBaseY[name] || 0;
  for (let i = 0; i < 3; i++) {
    setTimeout(() => { if (!walks[name]) { g.position.y = baseY + 0.22; requestRender(); } }, i * 220);
    setTimeout(() => { if (!walks[name]) { g.position.y = baseY; requestRender(); } }, i * 220 + 110);
  }
}

/* Kedip rak file (§5.4.4): strip volt rak file berdenyut saat
   ada file baru. */
function flashFileShelf() {
  if (REDUCED) return;
  const strip = dynamicPanels.fileShelf && dynamicPanels.fileShelf.strip;
  if (!strip) return;
  const m = strip.material;
  m.emissive = new THREE.Color(VOLT);
  for (let i = 0; i < 6; i++) {
    setTimeout(() => {
      m.emissiveIntensity = i % 2 === 0 ? 0.9 : 0.05;
      requestRender();
    }, i * 300);
  }
  setTimeout(() => { m.emissiveIntensity = 0; requestRender(); }, 6 * 300);
}

/* --- interaksi (§5.4) -------------------------------------------- */
function rebuildLines() {
  if (!state) return;
  while (mentionGroup.children.length) {
    const c = mentionGroup.children.pop();
    c.geometry.dispose();
    c.material.dispose();
  }
  while (handoverGroup.children.length) {
    const c = handoverGroup.children.pop();
    c.geometry.dispose();
    c.material.dispose();
  }
  /* Garis putus-putus balasan @mention. */
  for (const line of state.mentionLines) {
    const a = avatarPos[line.from];
    const b = avatarPos[line.to];
    if (!a || !b) continue;
    const geo = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(a.x, 1.3, a.z),
      new THREE.Vector3(b.x, 1.3, b.z),
    ]);
    const matLine = new THREE.LineDashedMaterial({
      color: new THREE.Color(KNOWN_AGENTS[line.from].color),
      dashSize: 0.35, gapSize: 0.25,
    });
    const l = new THREE.Line(geo, matLine);
    l.computeLineDistances();
    mentionGroup.add(l);
  }
  /* Busur kecil serah terima tugas. */
  for (const h of state.handovers) {
    const a = avatarPos[h.from];
    const b = avatarPos[h.to];
    if (!a || !b) continue;
    const mid = new THREE.Vector3((a.x + b.x) / 2, 2.4, (a.z + b.z) / 2);
    const curve = new THREE.QuadraticBezierCurve3(
      new THREE.Vector3(a.x, 1.0, a.z), mid, new THREE.Vector3(b.x, 1.0, b.z));
    const geo = new THREE.BufferGeometry().setFromPoints(curve.getPoints(24));
    handoverGroup.add(new THREE.Line(geo, new THREE.LineBasicMaterial({ color: VOLT })));
  }
}

/* --- terapkan state ---------------------------------------------- */
function refreshDesks() {
  if (!state) return;
  for (const d of desks) {
    const occupant = state.agents.find((a) =>
      Math.abs(a.slot.x - d.slotX) < 0.01 && Math.abs(a.slot.z - d.slotZ) < 0.01);
    if (occupant) {
      drawMonitor(d.monTex, occupant);
      drawPlate(d.plateTex, occupant.name, occupant);
    } else {
      drawMonitor(d.monTex, null);
      drawPlate(d.plateTex, null, null);
    }
  }
}

function setStatusText(extra) {
  if (!statusEl) return;
  if (!snapLoaded) {
    /* Pemuatan pertama gagal (timeout/jaringan/status): tampilkan error +
       tombol coba lagi, bukan "Memuat…" selamanya. */
    if (snapErrorMsg) { showSnapError(); return; }
    statusEl.textContent = 'Memuat snapshot kantor…';
    return;
  }
  const gen = new Date(snapGeneratedMs);
  const hhmmss = [gen.getHours(), gen.getMinutes(), gen.getSeconds()]
    .map((n) => String(n).padStart(2, '0')).join(':');
  /* SHOWCASE FIX (label jujur, Oto msg_0354): snapshot hanya membawa
     1 tugas aktif per agen — jumlah "tugas terbuka" ruangan TIDAK bisa
     dihitung dari snapshot (angka tugas terbuka ruangan ada di footer
     room, dari endpoint tugas). Label di
     sini hitung AGEN yang sedang bekerja, bukan tugas. snapshotToState
     menyimpan keadaan itu sebagai glyph 'work'/'meeting'; hitung
     dari situ (ikon smile/face sudah dihapus 27 Nov 2026). */
  const working = state ? state.agents.filter((a) => a.glyph === 'work' || a.glyph === 'meeting').length : 0;
  const ageMin = Math.round((Date.now() - snapGeneratedMs) / 60000);
  let text = 'Snapshot per ' + hhmmss + ' · ' + working + ' agen bekerja · polling 60 detik · via ' + snapSource;
  if (ageMin >= 120) text += ' · snapshot basi (' + ageMin + ' mnt)';
  if (extra) text += ' · ' + extra;
  statusEl.textContent = text;
}

function applyState(ns, opts = {}) {
  const initial = !!opts.initial;
  const prev = state;
  state = ns;
  currentActiveAgent = activeAgentName(ns.agents);
  /* Panel dinding (data nyata). */
  dynamicPanels.taskBoard.redraw(ns.taskBoard, ns.isExample);
  dynamicPanels.whiteboard.redraw(ns.whiteboardThread, ns.threadMessageCount, ns.isExample);
  dynamicPanels.msgBoard.redraw(ns.recentMessages, ns.isExample);
  dynamicPanels.fileShelf.redraw(ns.recentFiles, ns.isExample);
  dynamicPanels.threadDoor.redraw(ns.whiteboardThread, ns.threadMessageCount,
    ns.unreadSelf || 0, ns.isExample);
  dynamicPanels.tv.redraw(ns.tv, ns.isExample);
  dynamicPanels.clock.redraw();
  refreshDesks();
  /* Avatar (ikon aktivitas kini di pill indikator — lihat updateBubbles). */
  for (const st of ns.agents) {
    const g = avatarGroups[st.name];
    g.visible = true;
    /* Pose per agen (duduk + aktivitas) — dicatat dulu, dipakai
       setAvatarPos/walkAgent/applyPose + visibilitas prop. */
    const sitting = agentSitting(st);
    const activity = agentActivity(st);
    poseState[st.name] = { sitting, activity };
    updateActivityProps(st.name);
    const moved = !prev || !avatarPos[st.name]
      || avatarRoom[st.name] !== st.room
      || Math.abs(avatarPos[st.name].x - st.slot.x) > 0.01
      || Math.abs(avatarPos[st.name].z - st.slot.z) > 0.01;
    if (initial || !moved) {
      setAvatarPos(st.name, st.slot, st.room, sitting, { snap: initial });
    } else {
      walkAgent(st.name, st.slot, st.room, { sitting });
    }
    /* Ucapan event: tampil 15 detik saat pesan baru terdeteksi. */
    const els = bubbleEls[st.name];
    if (st.speech && !seenSpeech.has(st.speech.id)) {
      seenSpeech.add(st.speech.id);
      if (seenSpeech.size > 200) seenSpeech.clear();
      if (els) {
        els.el.dataset.show = '1';
        setTimeout(() => { els.el.dataset.show = '0'; requestRender(); }, 15000);
      }
    }
    /* Selebrasi saat tugas baru selesai. */
    if (st.justCompletedMs && Date.now() - st.justCompletedMs <= 15 * 60 * 1000) {
      const key = st.name + ':' + st.justCompletedMs;
      if (!seenCompleted.has(key)) {
        seenCompleted.add(key);
        celebrate(st.name);
      }
    }
  }
  /* Kedip rak file saat file baru. */
  if (ns.fileFlash && ns.fileFlash.id !== seenFileFlash) {
    seenFileFlash = ns.fileFlash.id;
    flashFileShelf();
  }
  rebuildLines();
  renderPortraits();
  refreshFollowCard();
  setStatusText();
  requestRender();
}

function applyEmpty() {
  state = null;
  currentActiveAgent = null;
  if (cameraMode === 'follow') exitFollow();
  hideFollowCard();
  for (const name of ROOM_ORDER) {
    avatarGroups[name].visible = false;
    const els = bubbleEls[name];
    if (els) {
      els.el.style.display = 'none';
      els.el.style.opacity = '';
      els.sig = ''; /* konten di-render ulang segar saat state kembali */
    }
  }
  dynamicPanels.taskBoard.redraw([], false);
  dynamicPanels.whiteboard.redraw('blackboard-umum', 0, false);
  dynamicPanels.msgBoard.redraw([], false);
  dynamicPanels.fileShelf.redraw([], false);
  dynamicPanels.threadDoor.redraw('blackboard-umum', 0, 0, false);
  dynamicPanels.tv.redraw(null, false);
  for (const d of desks) { drawMonitor(d.monTex, null); drawPlate(d.plateTex, null, null); }
  renderPortraits();
  setStatusText();
  requestRender();
}

/* --- snapshot (showcase): satu-satunya sumber data ----------------- */
/* Skema snapshot.json (Oto yang generate):
   { generated_at: ISO, agents: [{ id, name, role, color, room, state, task }] }
   state: working | meeting | idle | away. room: id ruangan (6 asli;
   id ruangan lain yang valid juga diterima). task: judul maks 40
   karakter atau null. SATU-SATUNYA request jaringan viewer ini
   adalah snapshot.json — UTAMA dari R2 (Cloudflare, update tiap
   15 menit TANPA deploy Vercel), FALLBACK snapshot.json same-origin
   di repo bila R2 gagal (boleh basi). */
const SNAPSHOT_R2_URL = 'https://pub-20982401ea5a4ebdb76f3b502b7074d7.r2.dev/snapshot.json';
const SNAPSHOT_LOCAL_URL = new URL('snapshot.json', MODULE_BASE).href;
let SNAPSHOT_URL = SNAPSHOT_R2_URL; /* default: R2; mount({snapshotUrl}) override */
const SNAPSHOT_POLL_MS = 60000;
const SNAPSHOT_STALE_MS = 15 * 60 * 1000;
const SNAPSHOT_OLD_MS = 2 * 60 * 60 * 1000;

function validHexColor(c) {
  return typeof c === 'string' && /^#[0-9a-fA-F]{6}$/.test(c);
}
/* Snapshot -> RoomState (bentuk yang sama dengan buildRoomState agar
   applyState/panel/kartu bisa dipakai ulang apa adanya). Room dari
   snapshot bersifat otoritatif; agen yang tidak ada di snapshot
   TIDAK ditampilkan (bukan ditebak). Glyph/face eksplisit dari
   state snapshot: working/meeting = kerja, idle/away = diam. */
function snapshotToState(snap, nowMs) {
  const genMs = Date.parse(snap.generated_at || '') || nowMs;
  const byId = {};
  for (const a of (snap.agents || [])) {
    if (a && typeof a.id === 'string') byId[a.id.toLowerCase()] = a;
  }
  const agents = [];
  for (const name of ROOM_ORDER) {
    const info = KNOWN_AGENTS[name];
    const a = byId[name];
    if (!a) continue; /* tidak ada di snapshot = tidak ditampilkan */
    const room = ROOMS[a.room] ? a.room : 'taman';
    const st = typeof a.state === 'string' ? a.state.toLowerCase() : '';
    const taskTitle = typeof a.task === 'string' && a.task.trim()
      ? trunc(a.task.trim(), 40) : null;
    const working = st === 'working';
    const meeting = st === 'meeting';
    const staleSnap = nowMs - genMs > SNAPSHOT_OLD_MS;
    const agentState = {
      name,
      label: typeof a.name === 'string' && a.name.trim() ? a.name.trim() : info.label,
      role: typeof a.role === 'string' && a.role.trim() ? a.role.trim() : info.role,
      color: validHexColor(a.color) ? a.color : info.color,
      room,
      activeTask: taskTitle ? { id: 'snapshot:' + name, title: taskTitle, status: 'working' } : null,
      openCount: taskTitle ? 1 : 0,
      justCompletedMs: 0,
      recentFile: null,
      replying: false,
      lastActiveMs: genMs,
      lastActiveLabel: hhmm(genMs),
      statusText: taskTitle ? 'Mengerjakan: ' + taskTitle
        : (meeting ? 'Rapat' : null),
      stale: staleSnap,
      speech: null,
      lastMessage: null,
      lastTask: null,
    };
    /* Ikon aktivitas ditentukan di loop kedua (butuh st.activity +
       room + state snapshot); placeholder sampai di sana. */
    agentState.glyph = 'zzz';
    agents.push(agentState);
  }
  /* 2026-11-28 (Rangga: idle stuck di 1 node): bucket dihitung
     dari jam nyata (nowMs), BUKAN generated_at snapshot —
     pipeline hanya push snapshot bila state berubah (atau >90
     menit), jadi genMs bisa beku sampai 90 menit dan idle tidak
     pernah pindah. Dengan nowMs, penempatan idle stabil di dalam
     satu bucket 15 menit lalu pindah ke node acak lain di bucket
     berikut; viewer me-refresh snapshot tiap 60 detik, dan
     applyState akan MENJALANKAN mereka ke sana (walkAgent),
     bukan teleport. */
  const bucket = Math.floor(nowMs / IDLE_WANDER_MS_V);
  const slots = assignSlots(agents, nowMs);
  for (const st of agents) {
    st.slot = slots[st.name];
    /* Ruangan agen idle = ruangan PENEMPATAN (bukan logis) supaya
       jalur jalan + aktivitas memakai lokasi nyata. Agen kerja /
       rapat tidak mengembara. */
    if (!st.activeTask && st.room !== 'ruang-rapat') {
      st.room = slotRoomFn(st.slot) || st.room;
    }
    st.sitting = isDeskSlotFn(st.room, st.slot) || isPadSlotFn(st.room, st.slot);
    if (activityForFn) {
      st.activity = activityForFn(st.room, !!st.activeTask, st.stale, st.name, bucket);
    } else {
      /* Fallback (viewmodel lama): pantry kopi, ruang-kerja HP,
         idle lain acak HP ~1/3. */
      st.activity = st.room === 'pantry' && !st.activeTask ? 'coffee'
        : (st.room === 'ruang-kerja' && !st.activeTask ? 'phone'
        : (!st.activeTask && hashStrFn(st.name + '#act#' + bucket) % 3 === 0 ? 'phone' : null));
    }
    /* Ikon aktivitas (27 Nov 2026 — smile/face dihapus, cukup ikon):
       urutan = baru selesai > rapat > kerja > kopi > HP > away
       (daun, taman) > diam (Z). Data basi (>2 jam) selalu Z.
       snapSt = state mentah snapshot; st.room = ruangan penempatan
       (idle mengembara) — daun pakai ruangan penempatan. */
    const snapSt = (byId[st.name] && byId[st.name].state) || '';
    const justDone = !!(byId[st.name] && byId[st.name].justCompleted);
    st.glyph = st.stale ? 'zzz'
      : justDone ? 'done'
      : snapSt === 'meeting' ? 'meeting'
      : snapSt === 'working' ? 'work'
      : st.activity === 'coffee' ? 'coffee'
      : st.activity === 'phone' ? 'phone'
      : st.room === 'taman' ? 'leaf'
      : 'zzz';
  }
  const taskBoard = agents.filter((a) => a.activeTask)
    .slice(0, 3)
    .map((a) => ({ id: a.activeTask.id, title: a.activeTask.title, assignee: a.name }));
  return {
    nowMs,
    isExample: false,
    self: null,
    agents,
    taskBoard,
    tv: null,
    whiteboardThread: 'blackboard-umum',
    threadMessageCount: 0,
    recentMessages: [],
    recentFiles: [],
    mentionLines: [],
    handovers: [],
    fileFlash: null,
    bossActive: false,
    unreadSelf: null,
    generatedMs: genMs,
  };
}
/* Timeout + retry pemuatan snapshot (Zeto msg_0356, Oto msg_0357):
   fetch TANPA timeout menggantung selamanya bila koneksi stall — viewer
   mentok di "Memuat snapshot kantor…" tanpa error (tanpa canvas, daftar
   agen kosong). loadAvatars sudah punya timeout 8 detik per GLB, jadi
   fetch snapshot inilah satu-satunya await tanpa batas sebelum render
   pertama. Batas ~10 detik per percobaan (endpoint sehat 0,5–0,75 dtk;
   first paint halaman bisa lambat ~60 dtk, tapi itu beban modul+GLB,
   bukan fetch snapshot) + retry 2x (total 3 percobaan, jeda 800 ms)
   sebelum menyerah dan tampilkan error + tombol coba lagi. */
const SNAPSHOT_TIMEOUT_MS = 10000;
const SNAPSHOT_MAX_ATTEMPTS = 3; /* percobaan awal + 2 retry */
let snapErrorMsg = ''; /* alasan gagal memuat snapshot terakhir ('' = tak ada error) */
async function fetchSnapshotFrom(url) {
  for (let attempt = 1; attempt <= SNAPSHOT_MAX_ATTEMPTS; attempt++) {
    const ctrl = new AbortController();
    const to = setTimeout(() => ctrl.abort(), SNAPSHOT_TIMEOUT_MS);
    try {
      const r = await fetch(url, { cache: 'no-store', signal: ctrl.signal });
      if (!r.ok) {
        snapErrorMsg = 'status ' + r.status;
      } else {
        const snap = await r.json();
        if (!snap || typeof snap !== 'object' || !Array.isArray(snap.agents)) {
          snapErrorMsg = 'snapshot rusak (bukan JSON agen yang valid)';
        } else {
          snapErrorMsg = '';
          return snap;
        }
      }
    } catch (e) {
      snapErrorMsg = (e && e.name === 'AbortError')
        ? 'timeout ' + (SNAPSHOT_TIMEOUT_MS / 1000) + ' detik — server tidak merespons'
        : 'jaringan bermasalah (' + (e && e.message ? e.message : 'fetch gagal') + ')';
      console.warn('showcase: gagal memuat snapshot:', e);
    } finally {
      clearTimeout(to);
    }
    if (attempt < SNAPSHOT_MAX_ATTEMPTS) {
      console.warn('showcase: snapshot gagal (percobaan ' + attempt + '/' + SNAPSHOT_MAX_ATTEMPTS + '), coba lagi:', snapErrorMsg);
      await new Promise((r) => setTimeout(r, 800));
    }
  }
  return null;
}
async function fetchSnapshot() {
  /* Utama: R2 (SNAPSHOT_URL, bisa di-override mount({snapshotUrl})).
     Gagal (404/timeout/rusak) -> fallback snapshot.json same-origin
     di repo. R2 404 langsung gagal cepat (tanpa nunggu timeout),
     jadi fallback tidak bikin first paint lambat. */
  const primary = await fetchSnapshotFrom(SNAPSHOT_URL);
  if (primary) { snapSource = 'R2'; return primary; }
  if (SNAPSHOT_URL !== SNAPSHOT_LOCAL_URL) {
    console.warn('showcase: snapshot R2 gagal (' + (snapErrorMsg || '?') + '), fallback ke snapshot.json lokal');
    const local = await fetchSnapshotFrom(SNAPSHOT_LOCAL_URL);
    if (local) { snapSource = 'lokal'; return local; }
  }
  return null;
}
async function refreshSnapshot() {
  if (document.hidden) return false;
  const snap = await fetchSnapshot();
  if (!snap) {
    /* Galat jaringan/snapshot rusak/timeout: pertahankan state lama
       bila ada. Bila ini pemuatan PERTAMA (belum ada state), tampilkan
       error + tombol coba lagi — viewer tidak boleh diam-diam mentok
       di "Memuat snapshot kantor…". */
    if (!state) { showSnapError(); }
    else setStatusText('snapshot gagal dimuat — menampilkan data terakhir');
    return false;
  }
  hideSnapError();
  const first = !state;
  lastFetchMs = Date.now();
  snapLoaded = true;
  snapGeneratedMs = Date.parse(snap.generated_at || '') || lastFetchMs;
  const ns = snapshotToState(snap, Date.now());
  applyState(ns, { initial: first });
  syncPresence(ns);
  setStatusText();
  return true;
}

/* --- Layar monitor infra di lobi (28 Nov 2026) -------------------- */
/* Rangga: "Layar aja tp yg keren d lobby" + label seragam "OTO-VM"
/  "LAB-VM" (huruf besar + hyphen) + efek inference supaya layar
   hidup. Data dari infra-status.json publik di R2 (pipeline
   infra_status.py, refresh 5 menit) — read-only, tanpa kredensial.
   Bila JSON basi (>15 menit) atau fetch gagal, layar menampilkan
   "DATA BASI" / "DATA TIDAK TERSEDIA" yang jelas — JANGAN pernah
   hijau palsu. ATURAN JUJUR: efek inference (dot berdenyut saat UP,
   garis volt berdenyut, bar aktivitas, kilau saat refresh) HANYA
   menandakan layar hidup/refresh — JANGAN memalsukan metrik (tidak
   ada angka token/detik, uptime, atau grafik yang bukan dari data
   nyata infra-status.json). Nama VM diambil dari JSON (field name);
   id teknis tidak pernah ditampilkan. */
const INFRA_R2_URL = 'https://pub-20982401ea5a4ebdb76f3b502b7074d7.r2.dev/infra-status.json';
const INFRA_POLL_MS = 5 * 60 * 1000;
const INFRA_STALE_MS = 15 * 60 * 1000;
const INFRA_TIMEOUT_MS = 15000;
const INFRA_W = 1024, INFRA_H = 480;
/* Label pendek monitor OTO-VM (9 monitor Kuma) — nama lengkap dari
   JSON dipetakan ke label mungil supaya muat di kartu. */
const INFRA_MON_SHORT = {
  'neugi.com': 'neugi.com', 'Backroom': 'Backroom',
  'Evolution API (WA)': 'Evo API',
  'Evolution API instance (WA)': 'Evo inst',
  'R2 snapshot.json': 'R2 snap', 'R2 research.json': 'R2 res',
  'R2 guestbook.json': 'R2 guest', 'webiz.id': 'webiz.id',
  'smar.neugi.com': 'smar.neugi',
};
function infraShort(name) {
  return INFRA_MON_SHORT[name] || trunc(String(name), 10);
}
function infraHHMM(iso) {
  /* Jam WIB dari ISO +07:00 — pakai zona Asia/Jakarta supaya benar
     di browser pengunjung mana pun (bukan jam lokal pengunjung). */
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return '--:--';
    return d.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Jakarta' });
  } catch (e) { return '--:--'; }
}
function infraVm(data, name) {
  const vms = (data && Array.isArray(data.vms)) ? data.vms : [];
  return vms.find((v) => v && v.name === name) || null;
}
function infraWrap(g, text, maxW) {
  const words = String(text || '').split(/\s+/).filter(Boolean);
  const lines = [];
  let cur = '';
  for (const w of words) {
    const next = cur ? cur + ' ' + w : w;
    if (g.measureText(next).width <= maxW || !cur) cur = next;
    else { lines.push(cur); cur = w; }
  }
  if (cur) lines.push(cur);
  return lines;
}
function drawInfraScreen(g, w, h, t) {
  const DARK = '#161b22', VOLT = '#a3ff00', CREAM = '#f3eee2',
    MUTED = '#9aa0a6', GREEN = '#34c759', RED = '#ff6b5e',
    AMBER = '#ffb020', TRACK = '#2e2a26';
  g.fillStyle = DARK; g.fillRect(0, 0, w, h);
  /* Garis atas volt 3px — satu-satunya aksen kuat; berdenyut halus
     (alpha 0,75..1,0) supaya layar terasa hidup. */
  const voltPulse = 0.75 + 0.25 * Math.sin(t / 600);
  g.globalAlpha = voltPulse;
  g.fillStyle = VOLT; g.fillRect(0, 0, w, 3);
  g.globalAlpha = 1;
  const mono = (px, bold) => (bold ? 'bold ' : '') + px + 'px ui-monospace, monospace';
  g.textBaseline = 'middle';
  /* Header: judul kiri, indikator kanan. */
  g.fillStyle = VOLT; g.font = mono(34, true); g.textAlign = 'left';
  g.fillText('STATUS INFRA', 24, 40);
  const stale = !infraData || (Date.now() - infraGeneratedMs > INFRA_STALE_MS);
  g.textAlign = 'right';
  if (!infraData) {
    g.fillStyle = AMBER; g.font = mono(24, true);
    g.fillText(infraFailed ? 'DATA TIDAK TERSEDIA' : 'MEMUAT…', w - 24, 40);
  } else if (stale) {
    g.fillStyle = AMBER; g.font = mono(24, true);
    g.fillText('DATA BASI', w - 24, 40);
  } else {
    /* Dot LIVE berdenyut (sama ritme dengan garis volt). */
    g.globalAlpha = voltPulse;
    g.fillStyle = GREEN;
    g.beginPath(); g.arc(w - 92, 40, 8, 0, Math.PI * 2); g.fill();
    g.globalAlpha = 1;
    g.fillStyle = GREEN; g.font = mono(24, true);
    g.fillText('LIVE', w - 24, 40);
  }
  /* Pembatas halus di bawah header. */
  g.fillStyle = TRACK; g.fillRect(24, 66, w - 48, 1);
  g.textAlign = 'center';
  if (!infraData) {
    /* Belum ada data sama sekali: memuat atau gagal — tanpa status. */
    if (infraFailed) {
      g.fillStyle = AMBER; g.font = mono(32, true);
      g.fillText('DATA TIDAK TERSEDIA', w / 2, 210);
      g.fillStyle = MUTED; g.font = mono(22, false);
      g.fillText('Menunggu pembaruan otomatis.', w / 2, 258);
    } else {
      g.fillStyle = CREAM; g.font = mono(32, true);
      g.fillText('MEMUAT STATUS…', w / 2, 210);
      g.fillStyle = MUTED; g.font = mono(22, false);
      g.fillText('Mengambil data infra publik.', w / 2, 258);
    }
  } else if (stale) {
    /* Data basi: JANGAN tampilkan status VM (bisa hijau palsu). */
    g.fillStyle = CREAM; g.font = mono(32, true);
    g.fillText('Data status belum diperbarui.', w / 2, 200);
    g.fillStyle = MUTED; g.font = mono(24, false);
    g.fillText('Terakhir: ' + infraHHMM(infraData.updated_at) + ' WIB', w / 2, 250);
    g.fillText('Menunggu pembaruan otomatis.', w / 2, 288);
  } else {
    /* Dua kartu VM berdampingan (OTO-VM | LAB-VM). */
    const cardW = 484, cardY = 78;
    g.fillStyle = TRACK; g.fillRect(511, cardY + 8, 1, 332);
    const cards = [
      { x: 16, vm: infraVm(infraData, 'OTO-VM') },
      { x: 524, vm: infraVm(infraData, 'LAB-VM') },
    ];
    for (const { x, vm } of cards) {
      const up = !!(vm && vm.status === 'up');
      /* Nama VM + lokasi. */
      g.fillStyle = CREAM; g.font = mono(38, true); g.textAlign = 'left';
      g.fillText(vm ? vm.name : '—', x, 108);
      g.fillStyle = MUTED; g.font = mono(22, false); g.textAlign = 'right';
      g.fillText(vm ? (vm.location || '') : '', x + cardW, 108);
      /* Kata status BESAR (merah hemat, hanya untuk DOWN). */
      g.textAlign = 'left';
      g.fillStyle = up ? VOLT : RED; g.font = mono(54, true);
      g.fillText(up ? 'ONLINE' : 'DOWN', x, 176);
      const mons = (vm && Array.isArray(vm.monitors)) ? vm.monitors : [];
      if (mons.length > 0) {
        /* Baris dot monitor (2 baris: 5 + 4) — dot hijau berdenyut
           halus saat UP (fase beda tiap dot, gelombang lembut),
           merah solid saat DOWN. */
        for (let i = 0; i < mons.length; i++) {
          const m = mons[i];
          const row = i < 5 ? 0 : 1;
          const col = i < 5 ? i : i - 5;
          const ix = x + col * 96;
          const iy = row === 0 ? 232 : 272;
          const mUp = m && m.status === 'up';
          g.globalAlpha = mUp ? 0.55 + 0.45 * Math.sin(t / 600 + i * 0.7) : 1;
          g.fillStyle = mUp ? GREEN : RED;
          g.beginPath(); g.arc(ix + 6, iy, 6, 0, Math.PI * 2); g.fill();
          g.globalAlpha = 1;
          g.fillStyle = MUTED; g.font = mono(13, false); g.textAlign = 'left';
          g.fillText(infraShort(m ? m.name : ''), ix + 16, iy);
        }
        /* Ringkasan monitor (data nyata dari JSON, bukan metrik). */
        const downN = mons.filter((m) => !m || m.status !== 'up').length;
        g.fillStyle = downN > 0 ? RED : MUTED; g.font = mono(20, false);
        g.fillText(mons.length + ' MONITOR · ' + (downN > 0 ? downN + ' DOWN' : 'SEMUA ONLINE'), x, 322);
      } else {
        /* Tanpa monitor: tampilkan note (maks 2 baris) + penjelas. */
        g.font = mono(20, false); g.fillStyle = MUTED; g.textAlign = 'left';
        const lines = infraWrap(g, vm ? (vm.note || '') : 'Tidak ada data.', cardW).slice(0, 2);
        lines.forEach((ln, li) => g.fillText(ln, x, 232 + li * 40));
        g.fillStyle = MUTED; g.font = mono(20, false);
        g.fillText('Belum ada monitor.', x, 322);
      }
      /* Pembatas + footer jam update (dari updated_at, WIB). */
      g.fillStyle = TRACK; g.fillRect(x, 372, cardW, 1);
      g.fillStyle = MUTED; g.font = mono(18, false); g.textAlign = 'left';
      g.fillText('DIPERBARUI ' + infraHHMM(infraData.updated_at) + ' WIB', x, 400);
    }
  }
  /* Bar aktivitas tipis di bawah — segmen volt menyapu kiri-kanan
     (ping-pong 6 detik), penanda layar hidup, bukan grafik data. */
  g.fillStyle = TRACK; g.fillRect(24, 452, w - 48, 4);
  const span = w - 48 - 60;
  const p = (t % 6000) / 6000;
  const frac = p < 0.5 ? p * 2 : (1 - p) * 2;
  g.fillStyle = VOLT; g.globalAlpha = 0.9;
  g.fillRect(24 + frac * span, 452, 60, 4);
  g.globalAlpha = 1;
  /* Kilau refresh: layar berkedip halus sekali saat JSON baru masuk
     (infraFlashUntil diset +700 ms saat refreshInfra berhasil). */
  if (t < infraFlashUntil) {
    g.globalAlpha = 0.10 * Math.max(0, (infraFlashUntil - t) / 700);
    g.fillStyle = VOLT; g.fillRect(0, 0, w, h);
    g.globalAlpha = 1;
  }
}
async function fetchInfraFrom() {
  const ctrl = new AbortController();
  const to = setTimeout(() => ctrl.abort(), INFRA_TIMEOUT_MS);
  try {
    const r = await fetch(INFRA_R2_URL, { cache: 'no-store', signal: ctrl.signal });
    if (!r.ok) return null;
    const data = await r.json();
    if (!data || typeof data !== 'object' || !Array.isArray(data.vms)) return null;
    return data;
  } catch (e) {
    console.warn('showcase: gagal memuat infra-status:', e);
    return null;
  } finally { clearTimeout(to); }
}
function drawInfraScreenNow(t) {
  if (!infraScreen) return;
  drawInfraScreen(infraScreen.texObj.ctx, INFRA_W, INFRA_H, t);
  infraScreen.texObj.tex.needsUpdate = true;
}
async function refreshInfra() {
  if (document.hidden) return false;
  const data = await fetchInfraFrom();
  if (!data) {
    infraFailed = !infraData;
    drawInfraScreenNow(performance.now());
    return false;
  }
  infraFailed = false;
  infraData = data;
  infraLoaded = true;
  infraGeneratedMs = Date.parse(data.updated_at || '') || Date.now();
  infraFlashUntil = performance.now() + 700;
  drawInfraScreenNow(performance.now());
  return true;
}
function updateInfraScreen(now) {
  /* Dipanggil dari loop 50 ms (startTraffic) — gambar ulang maks
     tiap 500 ms (denyut dot/garis + bar aktivitas + kilau refresh),
     pola sama dengan updateSupercomp. Hormat REDUCED lewat loop. */
  if (!infraScreen) return;
  if (now - (infraScreen.lastDrawMs || 0) > 500) {
    infraScreen.lastDrawMs = now;
    drawInfraScreenNow(now);
    requestRender();
  }
}
function startInfraPolling() {
  if (infraPollTimer) return;
  infraPollTimer = setInterval(() => { if (!document.hidden) refreshInfra(); }, INFRA_POLL_MS);
}

/* Error state pemuatan snapshot (Zeto msg_0356): pesan jelas + tombol
   coba lagi. Tombol dibuat sekali, dipakai ulang; gaya inline supaya
   jalan juga di viewer ter-mount (tanpa CSS template). Polling 60 detik
   tetap jalan di belakang — viewer bisa pulih sendiri tanpa klik. */
function showSnapError() {
  if (!statusEl) return;
  statusEl.textContent = 'Snapshot gagal dimuat — coba lagi (' + (snapErrorMsg || 'tidak diketahui') + '). ';
  let btn = document.getElementById('btnRetrySnap');
  if (!btn) {
    btn = document.createElement('button');
    btn.id = 'btnRetrySnap';
    btn.type = 'button';
    btn.textContent = 'Coba lagi';
    btn.style.font = 'inherit';
    btn.style.fontSize = '.9rem';
    btn.style.padding = '.3rem .6rem';
    btn.style.marginLeft = '.4rem';
    btn.style.border = '1px solid #2d333b';
    btn.style.borderRadius = '6px';
    btn.style.background = '#21262d';
    btn.style.color = '#e6e6e6';
    btn.style.cursor = 'pointer';
    btn.addEventListener('click', () => retrySnapshot());
  }
  statusEl.appendChild(btn);
}
function hideSnapError() {
  const btn = document.getElementById('btnRetrySnap');
  if (btn) btn.remove();
  snapErrorMsg = '';
}
async function retrySnapshot() {
  hideSnapError();
  if (statusEl) statusEl.textContent = 'Memuat snapshot kantor…';
  try {
    await refreshSnapshot(); /* gagal -> showSnapError lagi; sukses -> status normal */
  } catch (e) {
    console.warn('showcase: coba lagi gagal:', e);
    snapErrorMsg = 'gagal memuat ulang (' + (e && e.message ? e.message : 'error') + ')';
  }
  if (!snapLoaded) showSnapError();
}
function syncPresence(ns) {
  const present = new Set(ns.agents.map((a) => a.name));
  for (const name of ROOM_ORDER) {
    if (present.has(name)) continue;
    const g = avatarGroups[name];
    if (g) g.visible = false;
    const els = bubbleEls[name];
    if (els) {
      els.el.style.display = 'none';
      els.el.style.opacity = '';
      els.sig = '';
    }
  }
}
function startPolling() {
  if (pollTimer) return;
  pollTimer = setInterval(() => { if (!document.hidden) refreshSnapshot(); }, SNAPSHOT_POLL_MS);
}

/* --- hero auto-rotate + fullscreen --------------------------------- */
/* Hero: kamera orbit berputar pelan (satu putaran ~50 detik).
   Berhenti saat fullscreen / tab hidden / prefers-reduced-motion. */
let heroTimer = null;
let heroRotateEnabled = true; /* mount({autoRotate:false}) mematikan */
let heroRotateDir = 1; /* arah auto-rotate hero — putaran penuh 360° searah (FREE CAM 2026-11-27; dulu bolak-balik di clamp azimuth ±1.15) */
function startHeroRotate() {
  if (heroTimer || REDUCED || !heroRotateEnabled) return;
  heroTimer = setInterval(() => {
    if (displayMode !== 'hero' || document.hidden) return;
    /* Tugas 5: jeda 5 dtk sesudah interaksi user — auto-rotate
       tidak boleh melawan drag di hero. */
    if (Date.now() - heroLastInteract < 5000) return;
    azimuth += 0.015 * heroRotateDir;
    /* FREE CAM: putaran penuh tanpa clamp — normalisasi ke
       [0, 2π) supaya angka tidak membesar tanpa batas. */
    if (azimuth >= Math.PI * 2) azimuth -= Math.PI * 2;
    else if (azimuth < 0) azimuth += Math.PI * 2;
    updateCamera();
    requestRender();
  }, 120);
}
function stopHeroRotate() {
  if (heroTimer) { clearInterval(heroTimer); heroTimer = null; }
}
const heroStage = () => document.getElementById('stageHero');
const fsOverlay = () => document.getElementById('fsOverlay');
const fsStage = () => document.getElementById('stageFs');
const roomWrapEl = () => document.getElementById('roomWrap');
function moveRoomWrap(to) {
  const w = roomWrapEl();
  if (w && to) to.appendChild(w);
}
/* Resize renderer ke ukuran wrap — TANPA clear buffer bila ukuran sudah
   sama. setSize selalu mengosongkan buffer canvas; selama transisi
   fullscreen ResizeObserver menembak berkali-kali dan tiap clear = satu
   kedip hitam di atas background gelap (Rangga 27 Nov 22:28). Guard
   ini + background hangat di bawah membuat transisi tidak pernah
   menampilkan hitam. */
function resizeRendererToWrap() {
  if (!renderer || !wrap) return;
  const w = wrap.clientWidth || 800;
  const h = wrap.clientHeight || 600;
  const pr = renderer.getPixelRatio() || 1;
  const bw = Math.round(renderer.domElement.width / pr);
  const bh = Math.round(renderer.domElement.height / pr);
  if (bw !== w || bh !== h) renderer.setSize(w, h, false);
  fitCamera();
  updateCamera();
}
async function enterFullscreen() {
  /* Penjaga race Esc: bila exit sedang berjalan (fsExiting), jangan
     early-return — entri baru mengambil alih; fullscreenchange basi
     dari exit lama diabaikan (fsSeq maju). */
  if (displayMode === 'fullscreen' && !fsExiting && (document.fullscreenElement || fsFallback)) return true;
  fsSeq++; fsExiting = false;
  const overlay = fsOverlay();
  if (!overlay) return false;
  moveRoomWrap(fsStage());
  overlay.hidden = false;
  displayMode = 'fullscreen';
  stopHeroRotate();
  /* ANTI-KEDIP (Rangga 22:28): isi buffer dengan frame ukuran fullscreen
     SEBELUM browser memulai transisi fullscreen — overlay (position:
     fixed inset:0) sudah seukuran viewport begitu di-unhide, jadi
     resize + render sinkron di sini; tanpa ini kanvas tampil kecil di
     tengah overlay hitam selama transisi. */
  if (renderer) { resizeRendererToWrap(); requestRender(); }
  try {
    if (overlay.requestFullscreen) {
      await overlay.requestFullscreen().catch(() => { fsFallback = true; });
    } else {
      fsFallback = true;
    }
  } catch (_) { fsFallback = true; }
  if (fsFallback) overlay.classList.add('fs-fallback');
  /* Ukuran final baru pasti setelah transisi; resize terjaga (no-op
     bila sudah sama) + render ulang. */
  if (renderer) { resizeRendererToWrap(); }
  requestRender();
  return true;
}
function exitFullscreenCleanup() {
  if (displayMode !== 'fullscreen') return;
  if (cameraMode === 'follow') exitFollow();
  moveRoomWrap(heroStage());
  const overlay = fsOverlay();
  if (overlay) { overlay.hidden = true; overlay.classList.remove('fs-fallback'); }
  fsFallback = false;
  displayMode = 'hero';
  startHeroRotate();
  if (renderer) { resizeRendererToWrap(); }
  requestRender();
}
function exitFullscreen() {
  if (displayMode !== 'fullscreen') return;
  if (document.fullscreenElement) { fsExiting = true; fsSeq++; fsExitSeq = fsSeq; document.exitFullscreen().catch(() => { fsExiting = false; }); return; }
  exitFullscreenCleanup();
}
function bindShowcaseChrome() {
  const btnFs = document.getElementById('btnEnterFs');
  if (btnFs) btnFs.addEventListener('click', () => { enterFullscreen(); });
  const btnExit = document.getElementById('btnExitFs');
  if (btnExit) btnExit.addEventListener('click', () => { exitFullscreen(); });
}
function bindInput() {
  const canvas = renderer.domElement;
  canvas.style.touchAction = 'none';
  canvas.style.display = 'block';
  canvas.style.width = '100%';
  canvas.style.height = '100%';
  const pointers = new Map();
  let dragLast = null;
  let dragMoved = 0;
  let lastPinch = 0;
  let panLast = null;
  let panMode = false; /* Shift+drag satu jari = pan overview (Tugas 5) */
  const pinchDist = () => {
    const [a, b] = [...pointers.values()];
    return Math.hypot(a.x - b.x, a.y - b.y);
  };
  /* Cegah mouse kompatibel dari tap sentuh (0.4.9.1): sesudah tap,
     browser mengirim mousedown/mouseup/click susulan ke elemen di
     titik tap — karena tap sudah memindah view ke Pesan, klik
     susulan itu jatuh di elemen lain (mis. H2) dan default-nya
     mencuri fokus dari textarea composer (temuan diag 0.4.9.1).
     Canvas hanya memakai pointer event, jadi menahan touchstart
     aman (butuh { passive: false } supaya preventDefault jalan). */
  canvas.addEventListener('touchstart', (e) => { e.preventDefault(); }, { passive: false });
  canvas.addEventListener('pointerdown', (e) => {
    /* Tugas 5: interaksi apa pun di hero menjeda auto-rotate 5 dtk. */
    heroLastInteract = Date.now();
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    try { canvas.setPointerCapture(e.pointerId); } catch (_) { /* abaikan */ }
    if (pointers.size === 1) {
      dragLast = { x: e.clientX, y: e.clientY };
      dragMoved = 0;
      panMode = !!e.shiftKey;
    } else if (pointers.size === 2) {
      lastPinch = pinchDist();
      const [a, b] = [...pointers.values()];
      panLast = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
    }
  });
  canvas.addEventListener('pointermove', (e) => {
    if (!pointers.has(e.pointerId)) return;
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pointers.size === 1 && dragLast) {
      const dx = e.clientX - dragLast.x;
      const dy = e.clientY - dragLast.y;
      dragMoved += Math.abs(dx) + Math.abs(dy);
      if (cameraMode === 'follow') {
        /* followYaw SENGAJA tanpa clamp (cek visual 26 Nov 2026):
           clamp akan mengunci kamera ke setengah-belakang agen
           (followYaw=0 = di belakang agen) sehingga wajah/depan
           agen tidak pernah terlihat — padahal follow memang untuk
           melihat agen. Sejak FREE CAM 2026-11-27, azimuth
           overview juga tanpa clamp; kamera follow tetap dijepit
           ke dalam denah (updateFollowCamera). */
        followYaw -= dx * 0.005;
        followPitch = Math.min(1.25, Math.max(0.08, followPitch + dy * 0.003));
      } else if (panMode) {
        /* Tugas 5: Shift+drag = pan overview. Konten ikut jari
           (ala Sims): kanan layar = (cos az, 0, -sin az), bawah
           layar = (sin az, 0, cos az); skala = unit dunia per px
           dari frustum ortho (1:1 dengan jari). */
        const rect = canvas.getBoundingClientRect();
        const k = (orthoCam.top - orthoCam.bottom) / Math.max(rect.height, 1);
        const rx = Math.cos(azimuth);
        const rz = -Math.sin(azimuth);
        const fx = Math.sin(azimuth);
        const fz = Math.cos(azimuth);
        camPan.x += dx * k * rx + dy * k * fx;
        camPan.z += dx * k * rz + dy * k * fz;
        clampCamPan();
        updateCamera();
      } else {
        /* FREE CAM 2026-11-27 (Rangga: orbit 360, batas = jalan
           raya): clamp azimuth ±1.15 DIHAPUS — kamera boleh muter
           penuh mengelilingi scene. Alasan clamp lama (orbit bebas
           menampilkan sisi belakang gedung: dinding utara putih
           kosong + punggung TV hitam, cek visual 26 Nov 2026)
           sudah tidak berlaku sebagai pembatas: Rangga minta free
           cam, dan batas gerak sekarang jalan raya (pan dijepit
           clampCamPan). Azimuth dinormalisasi ke [0, 2π). Tilt:
           drag vertikal mengubah elevasi [0.25, 1.25] (dari atas
           sampai hampir horizontal, kamera tidak masuk bawah
           lantai), konvensi sama seperti followPitch (drag bawah
           = kamera naik). */
        azimuth -= dx * 0.005;
        if (azimuth >= Math.PI * 2) azimuth -= Math.PI * 2;
        else if (azimuth < 0) azimuth += Math.PI * 2;
        camElev = Math.min(1.25, Math.max(0.25, camElev + dy * 0.003));
        updateCamera();
      }
      dragLast = { x: e.clientX, y: e.clientY };
      requestRender();
    } else if (pointers.size === 2) {
      const d = pinchDist();
      if (cameraMode === 'follow') {
        /* Pinch = jarak follow; gerak 2 jari bersamaan = pan anchor. */
        if (lastPinch > 0 && d > 0) {
          followDist = Math.min(6, Math.max(2.2, followDist * (lastPinch / d)));
        }
        const [a, b] = [...pointers.values()];
        const mid = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
        if (panLast) {
          const mdx = mid.x - panLast.x;
          const mdy = mid.y - panLast.y;
          dragMoved += Math.abs(mdx) + Math.abs(mdy);
          /* Pan di bidang lantai, relatif arah kamera follow. */
          const turn = avatarMeshes[followName];
          const facing = turn ? turn.rotation.y : 0;
          const yaw = facing + Math.PI + followYaw;
          const k = 0.01 * followDist;
          const rx = Math.cos(yaw);
          const rz = -Math.sin(yaw);
          const fx = Math.sin(yaw);
          const fz = Math.cos(yaw);
          /* Konten ikut jari (ala Sims): geser kanan → anchor ke
             kanan layar; geser bawah → anchor ke bawah layar. */
          followPan.x = Math.min(6, Math.max(-6, followPan.x + mdx * k * rx + mdy * k * fx));
          followPan.z = Math.min(6, Math.max(-6, followPan.z + mdx * k * rz + mdy * k * fz));
        }
        panLast = mid;
      } else {
        /* Tugas 5: pinch = zoom (lama) + gerak 2 jari bersamaan =
           pan overview (baru, matematika sama seperti Shift+drag). */
        if (lastPinch > 0 && d > 0) {
          camZoom = Math.max(0.6, Math.min(2.2, camZoom * (d / lastPinch)));
        }
        const [a, b] = [...pointers.values()];
        const mid = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
        if (panLast) {
          const mdx = mid.x - panLast.x;
          const mdy = mid.y - panLast.y;
          dragMoved += Math.abs(mdx) + Math.abs(mdy);
          const rect = canvas.getBoundingClientRect();
          const k = (orthoCam.top - orthoCam.bottom) / Math.max(rect.height, 1);
          const rx = Math.cos(azimuth);
          const rz = -Math.sin(azimuth);
          const fx = Math.sin(azimuth);
          const fz = Math.cos(azimuth);
          camPan.x += mdx * k * rx + mdy * k * fx;
          camPan.z += mdx * k * rz + mdy * k * fz;
          clampCamPan();
        }
        panLast = mid;
        updateCamera();
      }
      lastPinch = d;
      requestRender();
    }
  });
  const up = (e) => {
    /* Tap vs drag: HANYA gerakan yang menentukan (bukan durasi).
       Durasi sengaja TIDAK dipakai: di renderer lambat (SwiftShader
       / HP kentang) pengiriman pointerup untuk tap sentuh bisa
       tertunda berdetik walau tap pengguna sekejap (temuan diag
       0.4.9.1: pointerdown->pointerup 4,6 detik — di mata Date.now()
       MAUPUN e.timeStamp — sehingga ambang 400 ms menolak tap yang
       sah). Gerakan < 6px sudah cukup membedakan tap dari orbit /
       pinch / pan (semuanya bergerak jauh lebih besar). */
    const wasTap = pointers.size === 1 && dragMoved < 6;
    pointers.delete(e.pointerId);
    if (pointers.size < 2) panLast = null;
    if (wasTap) handleTap(e);
    dragLast = null;
  };
  canvas.addEventListener('pointerup', up);
  canvas.addEventListener('pointercancel', (e) => { pointers.delete(e.pointerId); dragLast = null; panLast = null; });
  canvas.addEventListener('wheel', (e) => {
    /* Scroll halaman MENANG (cek visual 26 Nov 2026): wheel biasa
       dulu preventDefault + zoom — scroll halaman mati di atas
       kanvas. Sekarang wheel biasa dibiarkan ke halaman (tanpa
       preventDefault, tanpa zoom). Zoom hanya via Ctrl/Cmd+wheel
       (gestur pinch trackpad) atau pinch 2 jari di layar sentuh. */
    if (!e.ctrlKey && !e.metaKey) return;
    e.preventDefault();
    heroLastInteract = Date.now(); /* Tugas 5: jeda auto-rotate hero */
    if (cameraMode === 'follow') {
      followDist = Math.min(6, Math.max(2.2, followDist * Math.exp(e.deltaY * 0.001)));
    } else {
      camZoom = Math.max(0.6, Math.min(2.2, camZoom * Math.exp(-e.deltaY * 0.001)));
      updateCamera();
    }
    requestRender();
  }, { passive: false });
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (cameraMode === 'follow') exitFollow();
      else if (displayMode === 'fullscreen') exitFullscreen();
    }
  });
}

function pickAt(clientX, clientY) {
  const rect = renderer.domElement.getBoundingClientRect();
  pointerNDC.set(
    ((clientX - rect.left) / rect.width) * 2 - 1,
    -((clientY - rect.top) / rect.height) * 2 + 1);
  raycaster.setFromCamera(pointerNDC, camera);
  const hits = raycaster.intersectObjects(clickables, false);
  return hits.length ? hits[0].object : null;
}

/* Agen yang akan diaktifkan tap di titik layar ini (logika yang sama
   seperti handleTap, tanpa efek samping) — dipakai avatarScreenPos
   buat verifikasi titik tap. */
function agentAtPoint(clientX, clientY) {
  const hit = pickAt(clientX, clientY);
  if (!hit) return null;
  const u = hit.userData || {};
  if (u.agent) return u.agent;
  if (u.deskSlot && state) {
    const occupant = state.agents.find((a) =>
      Math.abs(a.slot.x - u.deskSlot.x) < 0.01 && Math.abs(a.slot.z - u.deskSlot.z) < 0.01);
    if (occupant) return occupant.name;
  }
  return null;
}

/* mentionInComposer DIHAPUS di showcase: tidak ada composer
   (read-only) — klik avatar = follow, bukan isi pesan. */

function handleTap(e) {
  const hit = pickAt(e.clientX, e.clientY);
  if (!hit) {
    /* Tap area kosong: di fullscreen keluar follow (tetap fullscreen);
       di hero buka fullscreen (overview). */
    if (cameraMode === 'follow') { exitFollow(); return; }
    if (displayMode === 'hero') { enterFullscreen(); }
    return;
  }
  const u = hit.userData || {};
  if (u.action) return; /* Props showcase: tanpa aksi (read-only). */
  /* Tap avatar/meja: di hero -> fullscreen + follow agen itu;
     di fullscreen -> follow (atau pindah follow ke agen itu). */
  if (u.agent) {
    if (displayMode === 'hero') { enterFullscreen(); }
    enterFollow(u.agent);
    return;
  }
  if (u.deskSlot && state) {
    const occupant = state.agents.find((a) =>
      Math.abs(a.slot.x - u.deskSlot.x) < 0.01 && Math.abs(a.slot.z - u.deskSlot.z) < 0.01);
    if (occupant) {
      if (displayMode === 'hero') { enterFullscreen(); }
      enterFollow(occupant.name);
    }
  }
}

/* jumpToAgent DIHAPUS di showcase: read-only, tidak ada pesan/tugas
   untuk dilompati. Klik avatar = kartu info (hero) / follow (fullscreen). */

/* --- hook showcase (selaras harness) ------------------------------- */
/* window.__showcasePreview = { ready, walking, walk, triggerWalk,
   getState, enterFullscreen, exitFullscreen, follow, refresh,
   displayMode } — harness memakai getState/enterFullscreen/follow
   untuk verifikasi hero + fullscreen + follow. walk/triggerWalk
   menggerakkan agen (dipakai tes transisi). */
function slotInRoom(agent, roomId) {
  if (!state) return null;
  const copy = state.agents.map((a) => (a.name === agent ? { ...a, room: roomId } : a));
  return assignSlots(copy)[agent] || null;
}
/* Sitting untuk slot tujuan (dipakai hook walk): slot meja =
   semua slot ruang-kerja + slot kantor Rangga (-10, -7.2). */
function sittingForSlot(roomId, slot) {
  return isDeskSlotFn(roomId, slot) || isPadSlotFn(roomId, slot);
}

const showcaseHook = {
  ready: false,
  walking: false,
  getCameraMode() { return getCameraMode(); },
  displayMode() { return displayMode; },
  enterFullscreen() { return enterFullscreen(); },
  exitFullscreen() { return exitFullscreen(); },
  enterFollow(name) { return enterFollow(name); },
  exitFollow() { return exitFollow(); },
  follow(name) { if (displayMode === 'hero') enterFullscreen(); return enterFollow(name); },
  refresh() { return refreshSnapshot(); },
  walk(fromRoom, toRoom, opts = {}) {
    /* Harness: gerakkan Beto dari fromRoom ke toRoom. Bila Beto
       belum di fromRoom, reposisi dulu (bukan transisi nyata —
       supaya harness menangkap jalan yang sebenarnya, bukan
       teleport). opts.slow = walk 3x lebih lambat (tes saja;
       walk snapshot tetap 2-3 detik). */
    const name = 'beto';
    if (!state || !ROOMS[fromRoom] || !ROOMS[toRoom]) return Promise.resolve(false);
    if (avatarRoom[name] !== fromRoom) {
      const slot = slotInRoom(name, fromRoom);
      if (!slot) return Promise.resolve(false);
      setAvatarPos(name, slot, fromRoom, sittingForSlot(fromRoom, slot), { snap: true });
      const st = state.agents.find((a) => a.name === name);
      if (st) { st.room = fromRoom; st.slot = slot; }
      requestRender();
    }
    const target = slotInRoom(name, toRoom);
    if (!target) return Promise.resolve(false);
    return walkAgent(name, target, toRoom, { ...opts, sitting: sittingForSlot(toRoom, target) });
  },
  triggerWalk(agent, room) {
    if (!state || !ROOMS[room] || !KNOWN_AGENTS[agent]) return Promise.resolve(false);
    const target = slotInRoom(agent, room);
    if (!target) return Promise.resolve(false);
    return walkAgent(agent, target, room, { sitting: sittingForSlot(room, target) });
  },
  getBones(name) {
    const skel = avatarSkeletons[name];
    if (!skel) return null;
    const out = {};
    for (const b of skel.bones) {
      const q = b.quaternion;
      out[b.name] = [q.x, q.y, q.z, q.w];
    }
    return out;
  },
  avatarScreenPos(name) {
    /* Harness-only (diambil dari 0.4.9.1): cari titik layar yang
       BENERAN mengenai avatar saat di-tap — coba beberapa tinggi
       (fraksi bounding box) dan verifikasi tiap kandidat dengan
       agentAtPoint (raycast yang sama seperti handleTap), supaya
       titik yang dikembalikan dijamin mengenai agen ini. Perlu
       karena bounding box GLB rigged mengikuti bind pose (T-pose):
       titik 80% tinggi jatuh DI ATAS kepala avatar yang sedang
       duduk, sehingga tap meleset. null bila tidak ada kandidat
       yang mengenai (agen di luar frame / terhalang). */
    if (!KNOWN_AGENTS[name] || !state) return null;
    const g = avatarGroups[name];
    if (!g || !g.visible || !camera || !renderer) return null;
    const box = new THREE.Box3().setFromObject(g);
    if (box.isEmpty()) return null;
    const rect = renderer.domElement.getBoundingClientRect();
    const cx = (box.min.x + box.max.x) / 2;
    const cz = (box.min.z + box.max.z) / 2;
    for (const f of [0.85, 0.7, 0.55, 0.4, 0.25]) {
      const c = new THREE.Vector3(
        cx, box.min.y + (box.max.y - box.min.y) * f, cz);
      c.project(camera);
      if (c.z > 1) continue;
      const x = rect.left + (c.x * 0.5 + 0.5) * rect.width;
      const y = rect.top + (-c.y * 0.5 + 0.5) * rect.height;
      if (agentAtPoint(x, y) === name) return { x, y };
    }
    return null;
  },
  getState() {
    let nodes = 0;
    if (scene) scene.traverse(() => { nodes++; });
    return {
      version: VERSION,
      ready: showcaseHook.ready,
      walking: anyWalking,
      displayMode,
      cameraMode,
      camera: camera ? { mode: cameraMode, follow: followName, pos: camera.position.toArray().map((v) => +v.toFixed(2)) } : null,
      activeAgent: currentActiveAgent,
      bubblesShown: lastBubblesShown,
      agents: state ? state.agents.map((a) => ({
        name: a.name, room: a.room, glyph: a.glyph,
        sitting: poseState[a.name] ? poseState[a.name].sitting : agentSitting(a),
        activity: agentActivity(a),
        activityProp: (() => {
          const props = activityProps[a.name];
          if (!props) return null;
          if (props.cup && props.cup.visible) return 'coffee';
          if (props.phone && props.phone.visible) return 'phone';
          return null;
        })(),
        x: avatarPos[a.name] ? avatarPos[a.name].x : null,
        z: avatarPos[a.name] ? avatarPos[a.name].z : null,
        rotY: avatarMeshes[a.name] ? +avatarMeshes[a.name].rotation.y.toFixed(3) : null,
      })) : [],
      rooms: Object.keys(ROOMS),
      nodeCount: nodes,
    };
  },
};
window.__showcasePreview = showcaseHook;
window.__showcase = showcaseHook;

/* --- mount API (embed di halaman lain, mis. hero kantor.html) ------- */
/* window.__neugiShowcase.mount(targetEl, opts):
   - targetEl: elemen DOM (slot hero) tempat viewer dipasang.
   - opts.snapshotUrl: path snapshot (default: snapshot.json di
     samping modul). Relatif terhadap HALAMAN pemanggil.
   - opts.autoRotate: hero auto-rotate (default true; diabaikan bila
     prefers-reduced-motion).
   Bila struktur viewer (#roomCanvas dkk.) belum ada di dokumen,
   mount() membuatnya di dalam targetEl (+ CSS penting) lalu init().
   Bila struktur sudah ada (office/index.html), mount() hanya init
   bila belum jalan. Mount kedua = no-op (return false). */
let showcaseMounted = false;
const SHOWCASE_CSS = `
#stageHero{position:relative;height:480px;border:1px solid #2d333b;border-radius:8px;overflow:hidden;cursor:pointer;background:#e8e2d4}
#roomWrap{position:relative;width:100%;height:100%;background:#e8e2d4}
#roomCanvas{position:absolute;inset:0}
#roomCanvas canvas{display:block;width:100%;height:100%;touch-action:none}
#roomBubbles{position:absolute;inset:0;overflow:hidden;pointer-events:none}
.bubble{position:absolute;transform:translate(-50%,-100%);max-width:240px;display:flex;gap:.3rem;align-items:center;background:rgba(22,27,34,.94);border:1px solid #2d333b;border-radius:6px;padding:.15rem .4rem;font-size:.8rem;line-height:1.3;color:#e6e6e6;white-space:nowrap;overflow:hidden;pointer-events:auto;cursor:pointer}
.bubble .txt{overflow:hidden;text-overflow:ellipsis}
.bubble .nm{display:none;font-weight:700;flex:none}
.bubble.status .nm,.bubble.speech .nm{display:inline} /* pill ber-TEKS selalu bawa nama pemilik tugas (desktop) */
.bubble .glyph{color:#a3ff00;flex:none;display:flex}
.bubble .time{color:#9aa0a6;font-size:.75rem;flex:none}
#roomStatus{font-size:.9rem;color:#9aa0a6;padding:.4rem .8rem;border:1px solid #2d333b;border-top:none;background:#161b22;border-radius:0 0 8px 8px;display:flex;gap:.6rem;align-items:center;flex-wrap:wrap}
#roomStatus span{flex:1;min-width:0}
.hero-actions{display:flex;gap:.6rem;align-items:center;flex-wrap:wrap;margin-top:.6rem}
.hint{font-size:.9rem;color:#9aa0a6;margin:0}
#btnEnterFs,#btnExitFs{font:inherit;font-size:1rem;padding:.5rem .6rem;border:1px solid #2d333b;border-radius:6px;background:#21262d;color:#e6e6e6;min-height:44px;cursor:pointer}
#fsOverlay{position:fixed;inset:0;z-index:50;background:#e8e2d4}
#fsOverlay[hidden]{display:none}
#stageFs{position:absolute;inset:0}
#btnExitFs{position:absolute;top:.6rem;right:.6rem;z-index:60}
#roomPortraits{display:flex;gap:.5rem;overflow-x:auto;padding:.45rem .8rem;background:#161b22;border:1px solid #2d333b;border-radius:8px;margin-top:.8rem}
#roomPortraits .portrait{flex:none;display:flex;flex-direction:column;align-items:center;gap:.15rem;min-width:64px;padding:.3rem .2rem .25rem;background:transparent;color:#e6e6e6;border:1px solid #2d333b;border-radius:8px;cursor:pointer}
#roomPortraits .portrait .mini-avatar svg{width:56px;height:60px;display:block}
#roomPortraits .portrait .portrait-name{font-size:10px;line-height:1.2;color:#e6e6e6}
#roomPortraits .portrait .portrait-role{font-size:10px;line-height:1.2;color:#9aa0a6}
@media (max-width:700px){#stageHero{height:340px}.bubble .txt,.bubble .time{display:none}.bubble .nm{display:inline}.hero-actions{flex-direction:column;align-items:flex-start}#roomFollowCard{max-width:min(340px,calc(100vw - 16px)) !important}}
`;
function ensureShowcaseCss() {
  if (document.getElementById('neugi-showcase-css')) return;
  const st = document.createElement('style');
  st.id = 'neugi-showcase-css';
  st.textContent = SHOWCASE_CSS;
  document.head.appendChild(st);
}
function ensureShowcaseDom(targetEl) {
  if (document.getElementById('roomCanvas') && document.getElementById('roomWrap')
      && document.getElementById('stageHero')) return false; /* struktur sudah ada */
  const root = (targetEl && targetEl instanceof Element) ? targetEl : document.body;
  const mk = (tag, id, cls, text) => {
    const el = document.createElement(tag);
    if (id) el.id = id;
    if (cls) el.className = cls;
    if (text !== undefined && text !== null) el.textContent = text;
    return el;
  };
  const stage = mk('div', 'stageHero', 'stage');
  const wrapEl = mk('div', 'roomWrap');
  wrapEl.appendChild(mk('div', 'roomCanvas'));
  const bub = mk('div', 'roomBubbles');
  bub.setAttribute('aria-hidden', 'true');
  wrapEl.appendChild(bub);
  stage.appendChild(wrapEl);
  root.appendChild(stage);
  const status = mk('div', 'roomStatus');
  status.appendChild(mk('span', null, null, 'Memuat snapshot kantor…'));
  root.appendChild(status);
  const actions = mk('div', null, 'hero-actions');
  const btnFs = mk('button', 'btnEnterFs', null, 'Layar penuh');
  btnFs.type = 'button';
  actions.appendChild(btnFs);
  const isTouch = ('ontouchstart' in window) || (navigator.maxTouchPoints > 0);
  actions.appendChild(mk('p', null, 'hint', isTouch ? 'Klik ruangan untuk layar penuh · klik agen untuk mengikuti · seret untuk orbit, cubit untuk zoom' : 'Klik ruangan untuk layar penuh · klik agen untuk mengikuti · seret untuk orbit, scroll untuk zoom'));
  root.appendChild(actions);
  const portraits = mk('div', 'roomPortraits');
  portraits.setAttribute('aria-label', 'Portrait agen');
  root.appendChild(portraits);
  /* Overlay fullscreen menempel di <body> (bukan di slot) supaya tidak
     terpotong overflow slot + position:fixed selalu relatif viewport. */
  if (!document.getElementById('fsOverlay')) {
    const ov = mk('div', 'fsOverlay');
    ov.hidden = true;
    ov.appendChild(mk('div', 'stageFs', 'stage'));
    const btnX = mk('button', 'btnExitFs', null, '× Keluar ');
    btnX.type = 'button';
    btnX.setAttribute('aria-label', 'Keluar layar penuh');
    btnX.appendChild(mk('span', null, 'key', 'Esc'));
    ov.appendChild(btnX);
    document.body.appendChild(ov);
  }
  return true;
}
async function mountShowcase(targetEl, opts = {}) {
  if (showcaseMounted) return false;
  showcaseMounted = true;
  const created = ensureShowcaseDom(targetEl);
  if (created) ensureShowcaseCss();
  if (opts.snapshotUrl) {
    SNAPSHOT_URL = new URL(opts.snapshotUrl, document.baseURI).href;
  }
  if (opts.autoRotate === false) heroRotateEnabled = false;
  bindShowcaseEls();
  await init();
  return true;
}
window.__neugiShowcase = { mount: mountShowcase, version: VERSION };

/* --- init ---------------------------------------------------------- */
function showFallback(msg) {
  const div = document.createElement('div');
  div.className = 'room-fallback';
  div.textContent = msg;
  wrap.appendChild(div);
}

/* Mount canvas terpisah dari snapshot (Oto msg_0357, item 3): canvas
   ditempel + ruangan kosong di-render SEBELUM menunggu snapshot, supaya
   halaman tidak pernah hitam total bila fetch snapshot stall. Sebelumnya
   canvas baru ditempel di markReady() — di ujung init(), setelah
   refreshSnapshot — jadi stall snapshot = tanpa canvas = hitam total. */
function attachCanvas() {
  const c = renderer && renderer.domElement;
  if (c && !c.parentElement) wrap.appendChild(c);
  render();
}
function markReady() {
  attachCanvas();
  showcaseHook.ready = true;
}

async function init() {
  ensureBubbles();
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
  } catch (e) {
    console.warn('showcase: WebGL tidak tersedia:', e);
    showFallback('WebGL tidak tersedia di browser ini — daftar kartu di bawah tetap menampilkan data.');
    await buildSceneFallbackOnly();
    showcaseHook.ready = true;
    return;
  }
  webglOK = true;
  /* AAA L2 — tone mapping ACESFilmic; exposure 1.15. */
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.35;
  /* AAA L3 — shadow map lembut PCFSoft (key light saja, 1024). */
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  const isMobile = window.matchMedia('(max-width: 900px)').matches;
  if (isMobile) camZoom = 1.5;
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, isMobile ? 1.5 : 2));
  renderer.setSize(wrap.clientWidth || 800, wrap.clientHeight || 600, false);
  buildScene();
  bindInput();
  bindShowcaseChrome();
  new ResizeObserver(() => {
    if (!renderer) return;
    resizeRendererToWrap();
    requestRender();
  }).observe(wrap);
  await loadAvatars();
  /* Ruangan kosong dulu: canvas nempel + render pertama SEBELUM snapshot
     (lihat attachCanvas) — bila fetch snapshot stall/timeout, pengunjung
     tetap melihat ruangan, bukan hitam total; agen diisi applyState
     saat snapshot datang (atau error + tombol coba lagi bila gagal).
     applyEmpty aman dipanggil di sini: semua yang dilakukannya
     (sembunyikan avatar, kartu kosong, status "Memuat…") dibatalkan
     applyState saat snapshot berhasil. */
  applyEmpty();
  attachCanvas();
  await refreshSnapshot();
  startPolling();
  refreshInfra();
  startInfraPolling();
  startHeroRotate();
  startAmbient();
  startTraffic();
  startWorkTimer();
  startActivityTimer();
  startLifeTimer();
  startClockTimer();
  startMonitorTimer();
  markReady();
}

/* Fallback tanpa WebGL: portrait strip + status tetap dibangun dari
   snapshot (tanpa scene); tanpa login, tanpa lobby. (List ruangan
   dihapus 28 Nov 2026 — kartu tidak lagi dibangun di mana pun.) */
async function buildSceneFallbackOnly() {
  const snap = await fetchSnapshot();
  if (snap) {
    snapLoaded = true;
    snapGeneratedMs = Date.parse(snap.generated_at || '') || Date.now();
    lastFetchMs = Date.now();
    state = snapshotToState(snap, Date.now());
  }
  renderPortraits();
  setStatusText();
}

document.addEventListener('visibilitychange', () => {
  if (!document.hidden && snapLoaded && Date.now() - lastFetchMs > 60000) refreshSnapshot();
});
document.addEventListener('fullscreenchange', () => {
  /* Esc browser keluar fullscreen: rapikan state (kembali ke hero).
     Abaikan event BASI: bila sesuatu terjadi sejak exit dimulai
     (enter baru / follow baru — fsSeq sudah maju dari fsExitSeq),
     jangan batalkan follow/entry yang baru. Bila tak ada exit yang
     dimulai (fsExitSeq -1, mis. Esc browser saat follow), tetap
     rapikan — follow sudah dilepas keydown lebih dulu. */
  if (!document.fullscreenElement && displayMode === 'fullscreen' && !fsFallback) {
    if (fsExitSeq === -1 || fsSeq === fsExitSeq) { fsExiting = false; fsExitSeq = -1; exitFullscreenCleanup(); }
  } else if (document.fullscreenElement && displayMode === 'fullscreen') {
    /* Masuk fullscreen (ukuran final baru pasti di event ini):
       resize terjaga + render ulang supaya tidak ada frame kosong. */
    if (renderer) { resizeRendererToWrap(); requestRender(); }
  }
});

/* Auto-init HANYA bila struktur viewer sudah ada di dokumen
   (office/index.html). Di host page (kantor.html) struktur belum
   ada — modul hanya mengekspos window.__neugiShowcase.mount. */
if (document.getElementById('roomCanvas')) { mountShowcase(document.body, {}); }
