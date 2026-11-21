/* ROOM-SHOWCASE-START — Showcase publik kantor 3D (neugi.com).
   Varian read-only dari room3d.js 0.4.9 — HANYA file ini yang
   diubah; room3d.js produksi tidak disentuh. Three.js minimal
   (core + GLTFLoader + DRACOLoader) DIVENDOR ke repo, tanpa CDN,
   tanpa build step, tanpa import map. Render-on-demand: canvas
   HANYA render saat ada perubahan state / transisi / interaksi;
   saat diam tidak ada frame baru (preserveDrawingBuffer: true).
   SATU-SATUNYA request jaringan viewer ini: snapshot.json
   (same origin, polling 60 detik). TIDAK ADA fetch ke layanan
   lain, TIDAK ADA URL absolut ke layanan lain di mana pun (kode,
   data, komentar). TANPA login, TANPA composer, TANPA posting,
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

/* --- state ----------------------------------------------------- */
/* Showcase: elemen di-bind ULANG oleh mount() — di office/index.html
   struktur sudah ada saat modul dimuat; di host page (kantor.html)
   struktur baru dibuat oleh mount() sebelum init(). */
let wrap = document.getElementById('roomCanvas');
let bubbleLayer = document.getElementById('roomBubbles');
let statusEl = document.getElementById('roomStatus');
let cardsEl = document.getElementById('roomCards');
function bindShowcaseEls() {
  wrap = document.getElementById('roomCanvas') || wrap;
  bubbleLayer = document.getElementById('roomBubbles') || bubbleLayer;
  statusEl = document.getElementById('roomStatus') || statusEl;
  cardsEl = document.getElementById('roomCards') || cardsEl;
}

let renderer = null;
let scene = null;
let camera = null;       /* kamera AKTIF (overview ortho / follow perspektif) */
let orthoCam = null;     /* overview */
let perspCam = null;     /* follow TPS */
let keyLight = null;     /* AAA L1: directional hangat (key) — dipakai L3 untuk shadow */
let azimuth = Math.PI / 4; /* kamera isometrik default (tenggara) */
let camZoom = 1;
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
const avatarGroups = {};   /* name -> THREE.Group (mesh + bayangan + wajah) */
const avatarMeshes = {};   /* name -> inner mesh (buat tilt/kerja) */
const avatarPos = {};      /* name -> {x, z} posisi kaki saat ini */
const avatarRoom = {};     /* name -> room id saat ini */
const walks = {};          /* name -> {token, raf} */
let anyWalking = false;
const faceSprites = {};    /* name -> {sprite, canvas, ctx, tex, face} */
let starPlumbob = null;
let plumbob = null;          /* plumbob agen aktif (§5.12) */
let currentActiveAgent = null;
let lastBubblesShown = 0;
const dynamicPanels = {};  /* key -> {texObj, redraw} */
let mentionGroup = null;
let handoverGroup = null;
const clickables = [];     /* mesh dg userData.agent / userData.action / userData.deskSlot */
const raycaster = new THREE.Raycaster();
const pointerNDC = new THREE.Vector2();

/* --- pose rigged (0.4.9, Upgrade 11/10 → 100/10) ------------------ */
/* JOINT_ROLES dari materials/joint-map-v2.md/.json (cari joint dari
   ROLE, jangan hardcode nomor bone di luar tabel ini). Seto (29):
   shoulder_L bone_7 (rantai kepala 3 tulang menggeser lengan),
   head = bone_6 (head1 bone_5 tidak dipakai pose); chest_extra
   15/16 (duri bahu) JANGAN diputar sebagai lengan; ekor Seto/Deto
   tidak punya tulang → tidak ada animasi ekor. Deto (34) seperti
   Oto/Beto. L/R = kiri/kanan karakter sendiri. */
const JOINT_ROLES = {
  rangga: { shoulderL: 6, shoulderR: 10, thighL: 14, thighR: 18, shinL: 15, shinR: 19, spine: 2, neck: 4, head: 5, forearmL: 8, forearmR: 12, handL: 9, handR: 13, fingerL: null, fingerR: null },
  zeto: { shoulderL: 6, shoulderR: 13, thighL: 20, thighR: 24, shinL: 21, shinR: 25, spine: 2, neck: 4, head: 5, forearmL: 8, forearmR: 15, handL: 9, handR: 16, fingerL: null, fingerR: null },
  neto: { shoulderL: 6, shoulderR: 13, thighL: 20, thighR: 24, shinL: 21, shinR: 25, spine: 2, neck: 4, head: 5, forearmL: 8, forearmR: 15, handL: 9, handR: 16, fingerL: null, fingerR: null },
  leto: { shoulderL: 6, shoulderR: 13, thighL: 20, thighR: 24, shinL: 21, shinR: 25, spine: 2, neck: 4, head: 5, forearmL: 8, forearmR: 15, handL: 9, handR: 16, fingerL: null, fingerR: null },
  ceto: { shoulderL: 6, shoulderR: 13, thighL: 20, thighR: 24, shinL: 21, shinR: 25, spine: 2, neck: 4, head: 5, forearmL: 8, forearmR: 15, handL: 9, handR: 16, fingerL: null, fingerR: null },
  beto: { shoulderL: 6, shoulderR: 16, thighL: 26, thighR: 30, shinL: 27, shinR: 31, spine: 2, neck: 4, head: 5, forearmL: 8, forearmR: 18, handL: 9, handR: 19, fingerL: [10, 11, 12, 13, 14, 15], fingerR: [20, 21, 22, 23, 24, 25] },
  oto: { shoulderL: 6, shoulderR: 16, thighL: 26, thighR: 30, shinL: 27, shinR: 31, spine: 2, neck: 4, head: 5, forearmL: 8, forearmR: 18, handL: 9, handR: 19, fingerL: [10, 11, 12, 13, 14, 15], fingerR: [20, 21, 22, 23, 24, 25] },
  geto: { shoulderL: 6, shoulderR: 10, thighL: 14, thighR: 19, shinL: 15, shinR: 20, spine: 2, neck: 4, head: 5, forearmL: 8, forearmR: 12, handL: 9, handR: 13, fingerL: null, fingerR: null },
  seto: { shoulderL: 7, shoulderR: 11, thighL: 19, thighR: 24, shinL: 20, shinR: 25, spine: 2, neck: 4, head: 6, forearmL: 9, forearmR: 13, handL: 10, handR: 14, fingerL: null, fingerR: null },
  deto: { shoulderL: 6, shoulderR: 16, thighL: 26, thighR: 30, shinL: 27, shinR: 31, spine: 2, neck: 4, head: 5, forearmL: 8, forearmR: 18, handL: 9, handR: 19, fingerL: [10, 11, 12, 13, 14, 15], fingerR: [20, 21, 22, 23, 24, 25] },
  /* FEET FIX 2026-11-21 — Meto (joint-map-11-avatars.json, file_0216):
     22 joint, pola sama seperti Rangga/Geto (thigh 14/18, shin 15/19).
     Tanpa entri ini Meto tidak dapat pose duduk (captureBoneBase lewati),
     jadi kakinya tidak pernah terukur saat duduk. */
  meto: { shoulderL: 6, shoulderR: 10, thighL: 14, thighR: 18, shinL: 15, shinR: 19, spine: 2, neck: 4, head: 5, forearmL: 8, forearmR: 12, handL: 9, handR: 13, fingerL: null, fingerR: null },
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
  rangga: 0.239, oto: 0.052, beto: 0.128, zeto: 0.000, neto: 0.000,
  geto: 0.234, leto: 0.187, ceto: 0.142, deto: 0.000, seto: 0.163, meto: 0.169,
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

/* sitting/activity per agen: pakai st.* bila view-model sudah
   menyediakannya (Worker A), bila belum hitung dari keadaan nyata
   yang sama seperti kontrak view-model. */
function agentSitting(st) {
  if (typeof st.sitting === 'boolean') return st.sitting;
  return isDeskSlotFn(st.room, st.slot);
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

/* Delta aktivitas pada saat nowMs (performance.now()). Kopi =
   siklus ~8 dtk: angkat 1.5 dtk, tahan 1 dtk (+ head tilt
   belakang sedikit), turun 1 dtk, istirahat ~4.5 dtk — angkat/turun
   dengan easing smoothstep (bukan linear robotik). HP = pose
   statis (head menunduk 15°, lengan kiri sedikit maju) + sesekali
   head tilt kecil (tiap siklus 6 dtk, 1.2 dtk pertama).
   Tangan menggenggam: jari sedikit menekuk (Oto/Beto/Deto pakai
   finger_L/R; avatar lain goyang hand kecil). */
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
  const deltas = [];
  if (anim.sittingW > 0.001) {
    for (const d of sitDeltas(name, roles)) deltas.push({ ...d, deg: d.deg * anim.sittingW });
  }
  if (anim.activityW > 0.001 && anim.activity) {
    for (const d of activityDeltas(name, anim.activity, nowMs)) {
      deltas.push({ ...d, deg: d.deg * anim.activityW });
    }
  }
  if (deltas.length) addBoneDeltas(name, deltas);
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
        /* Tinggi grup mengikuti bobot duduk (tidak pop vertikal). */
        const g = avatarGroups[name];
        if (g) g.position.y = -sitDropFor(name) * anim.sittingW;
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

/* Plumbob agen aktif: posisi + warna identitas; sembunyi bila
   tidak ada agen aktif. Bintang volt Rangga (starPlumbob) JANGAN
   diubah — itu mesh terpisah. Bob mengambang pelan (±0.05, ~4 dtk)
   dihitung dari jam SAAT RENDER (render-on-demand: tanpa timer
   sendiri — plumbob ikut bergerak saat ada render lain, diam saat
   ruangan diam). Lerp halus saat target pindah ditangani
   animatePlumbobTo. */
let plumbobAnimRaf = 0;
function plumbobBobY() {
  return Math.sin(performance.now() * Math.PI * 2 / 4000) * 0.05;
}
function plumbobTargetY(walkBob) {
  return 2.6 + (walkBob || 0) + plumbobBobY();
}
function updatePlumbob() {
  if (!plumbob) return;
  const active = currentActiveAgent;
  const pos = active ? avatarPos[active] : null;
  if (!active || !pos || !avatarGroups[active] || !avatarGroups[active].visible) {
    plumbob.visible = false;
    return;
  }
  plumbob.material.color.set(KNOWN_AGENTS[active].color);
  plumbob.position.set(pos.x, plumbobTargetY(0), pos.z);
  plumbob.visible = true;
}
/* Lerp halus plumbob ke posisi baru (~300 ms, easeOut) — dipakai
   saat agen aktif pindah (bukan saat jalan: jalan update tiap
   frame). */
function animatePlumbobTo(x, y, z) {
  if (!plumbob) return;
  if (plumbobAnimRaf) cancelAnimationFrame(plumbobAnimRaf);
  const from = plumbob.position.clone();
  const to = new THREE.Vector3(x, y, z);
  if (from.distanceTo(to) < 0.01) { plumbob.position.copy(to); return; }
  const start = performance.now();
  const step = (t) => {
    const k = Math.min(1, (t - start) / 300);
    const e = 1 - Math.pow(1 - k, 3);
    plumbob.position.lerpVectors(from, to, e);
    requestRender();
    if (k < 1) plumbobAnimRaf = requestAnimationFrame(step);
    else plumbobAnimRaf = 0;
  };
  plumbobAnimRaf = requestAnimationFrame(step);
}

/* Showcase: tanpa login/token — data hanya dari snapshot.json. */
function requestRender() {
  if (!renderer || !webglOK) return;
  render();
}
function render() {
  if (cameraMode === 'follow') updateFollowCamera();
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
function updateCamera() {
  if (!orthoCam) return;
  const el = 0.62; /* elevasi ~35,5 derajat (isometrik) */
  const d = 42;
  const b = computePlanBounds();
  orthoCam.position.set(
    b.cx + Math.sin(azimuth) * Math.cos(el) * d,
    Math.sin(el) * d,
    b.cz + Math.cos(azimuth) * Math.cos(el) * d);
  orthoCam.lookAt(b.cx, 0, b.cz);
  orthoCam.zoom = camZoom;
  orthoCam.updateProjectionMatrix();
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
  const size = Math.min(40, Math.max(projH, projW / aspect));
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
/* Posisi kamera follow dari posisi + arah hadap agen saat ini
   (turn.rotation.y; saat jalan = arah gerak): di belakang bahu
   (followYaw), di atas (followPitch), jarak followDist; anchor =
   torso agen + pan. Pitch di-clamp [0.08, 1.25] supaya kamera
   tidak masuk bawah lantai; posisi x/z di-clamp ke bounds + 4
   supaya tidak nyangkut jauh di luar dinding.
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
function updateFollowCamera() {
  if (!perspCam || !followName) return;
  const pos = avatarPos[followName];
  const g = avatarGroups[followName];
  if (!pos || !g || !g.visible) return;
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
  perspCam.position.set(cx, cy, cz);
  perspCam.lookAt(anchor);
  perspCam.updateProjectionMatrix();
  /* Marker wajah agen yang diikuti DISEMBUNYIKAN (TPS: wajah sendiri
     tak terlihat; sprite billboard selalu menghadap kamera dan akan
     menutupi layar bila dibiarkan). Agen lain tetap terlihat. */
  for (const n of ROOM_ORDER) {
    const f = faceSprites[n];
    if (f) f.sprite.visible = (n !== followName);
  }
}
function enterFollow(name) {
  if (!KNOWN_AGENTS[name] || !avatarGroups[name] || !avatarGroups[name].visible) return false;
  fsSeq++; /* follow baru — fullscreenchange basi dari exit lama abaikan */
  if (!perspCam) return false;
  followName = name;
  followYaw = 0;
  followPitch = 0.32;
  followDist = 4.0;
  followPan = { x: 0, z: 0 };
  cameraMode = 'follow';
  camera = perspCam;
  updateFollowCamera();
  refreshFollowCard();
  requestRender();
  return true;
}
function exitFollow() {
  if (cameraMode !== 'follow') return false;
  cameraMode = 'overview';
  followName = null;
  camera = orthoCam;
  /* Kembalikan semua marker wajah. */
  for (const n of ROOM_ORDER) {
    const f = faceSprites[n];
    if (f) f.sprite.visible = true;
  }
  updateCamera();
  fitCamera();
  hideFollowCard();
  requestRender();
  return true;
}
function getCameraMode() {
  return cameraMode;
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
  scene.add(place(box(42.6, 0.9, 0.3, C.wall), 0, 0.45, 14.15));      /* selatan (rendah) */
  scene.add(place(box(0.25, 1.0, 10, C.divider), -10.5, 0.5, -9));     /* kantor | rapat */
  scene.add(place(box(0.25, 1.0, 10, C.divider), 0, 0.5, -9));         /* rapat | lounge */
  scene.add(place(box(0.25, 1.0, 10, C.divider), 10.5, 0.5, -9));      /* lounge | studio */
  scene.add(place(box(0.25, 1.0, 14, C.divider), -5, 0.5, 7));         /* kerja | pantry */
  scene.add(place(box(0.25, 1.0, 14, C.divider), 2, 0.5, 7));          /* pantry | taman */
  scene.add(place(box(0.25, 1.0, 14, C.divider), 9, 0.5, 7));          /* taman | war-room */
  scene.add(place(box(0.25, 1.0, 14, C.divider), 15, 0.5, 7));         /* war-room | perpustakaan */

  buildWallPanels();
  buildWorkRoom();
  buildMeetingRoom();
  buildLounge();
  buildPantry();
  buildGarden();
  buildRanggaOffice();
  buildStudioKonten();
  buildWarRoom();
  buildPerpustakaan();

  mentionGroup = new THREE.Group();
  handoverGroup = new THREE.Group();
  scene.add(mentionGroup);
  scene.add(handoverGroup);

  /* Plumbob agen aktif (§5.12): satu octahedron warna identitas
     agen aktif; posisi + visibilitas diatur updatePlumbob(). */
  plumbob = new THREE.Mesh(
    new THREE.OctahedronGeometry(0.22),
    new THREE.MeshBasicMaterial({ color: VOLT }));
  plumbob.visible = false;
  scene.add(plumbob);

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
     tidak acne pada bidangnya sendiri). MeshBasic (panel, plumbob,
     blob, teks) dilewati — tidak ikut shadow. Blob ellipse per agen
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
  wallPanel(5, 2.3, -13.92, 0, 3.4, 1.8, wbTex, 'thread');

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
  wallPanel(0, 1.3, 13.92, Math.PI, 5, 1.6, doorTex, 'thread');

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
  /* Monitor: layar menghadap kamera (selatan) supaya judul tugas
     kebaca dari tampilan isometrik; dudukan kecil di belakang. */
  const monTex = textTexture(256, 128, () => {});
  const mon = box(1.0, 0.62, 0.06, 0x111111);
  mon.position.set(0.25, DESK_TOP_Y + 0.31, -0.12);
  mon.rotation.x = -0.22;
  g.add(mon);
  const monScreen = panelPlane(0.92, 0.54, monTex);
  /* Layar NEMPEL di bodi (celah ~0.004, dulu 0.011): dari depan
     layar duduk rapi di bodi, dari samping/belakang tidak tampak
     seperti kartu mengambang; tetap di depan muka bodi supaya
     tidak z-fighting. Posisi y disamakan dengan pusat bodi. */
  monScreen.position.set(0.25, DESK_TOP_Y + 0.31, -0.086);
  monScreen.rotation.x = -0.22;
  g.add(monScreen);
  const monStand = box(0.08, 0.32, 0.08, 0x111111);
  monStand.position.set(0.25, DESK_TOP_Y + 0.05, -0.12);
  g.add(monStand);
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

function buildWorkRoom() {
  /* 9 meja ruang kerja (3 kolom x 3 baris). */
  const slots = ROOMS['ruang-kerja'].slots;
  for (const s of slots) buildDesk(s.x, s.z + 1.1, 2.2);
}

function buildMeetingRoom() {
  /* Meja rapat tengah + karpet (pusat (-5,-9); meja 3.6x1.8 —
     lebih kecil dari lama supaya koridor barat/timur lega
     untuk lane jalan x=-9.5 / x=-0.7). */
  const carpetEdge = new THREE.Mesh(new THREE.PlaneGeometry(7.6, 5.2), mat('carpetEdge', C.carpetEdge));
  carpetEdge.rotation.x = -Math.PI / 2;
  carpetEdge.position.set(-5, 0.008, -9);
  scene.add(carpetEdge);
  const carpet = new THREE.Mesh(new THREE.PlaneGeometry(7.2, 4.8), mat('carpet', C.carpet));
  carpet.rotation.x = -Math.PI / 2;
  carpet.position.set(-5, 0.012, -9);
  scene.add(carpet);
  const table = box(3.6, 0.14, 1.8, C.deskTop);
  table.position.set(-5, DESK_TOP_Y - 0.07, -9);
  scene.add(table);
  for (const [lx, lz] of [[-6.5, -9.7], [-3.5, -9.7], [-6.5, -8.3], [-3.5, -8.3]]) {
    scene.add(place(box(0.14, DESK_TOP_Y - 0.12, 0.14, C.desk), lx, (DESK_TOP_Y - 0.12) / 2, lz));
  }
  /* Pad lesehan di KEEMPAT slot rapat (Item 3) — dipusatkan di slot,
     bukan meleset 0.75 (utara/selatan) / 1.2 (barat/timur, ke utara
     slot, bukan ke arah meja) seperti kursi lama. Pad rata lantai
     (0.10) tidak menutup koridor lane mana pun (LAYOUT.md §5). */
  scene.add(place(box(0.7, 0.1, 0.7, C.chair), -5, PAD_TOP - 0.05, -11.6));  /* utara */
  scene.add(place(box(0.7, 0.1, 0.7, C.chair), -5, PAD_TOP - 0.05, -6.4));   /* selatan */
  scene.add(place(box(0.7, 0.1, 0.7, C.chair), -7.6, PAD_TOP - 0.05, -9));   /* barat */
  scene.add(place(box(0.7, 0.1, 0.7, C.chair), -2.4, PAD_TOP - 0.05, -9));   /* timur */
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
}

function buildPantry() {
  /* Meja pantry + pad (pusat (-1.5,7) dari ROOMS). */
  const table = box(2.4, 0.12, 1.4, C.deskTop);
  table.position.set(-1.5, DESK_TOP_Y - 0.06, 7);
  scene.add(table);
  for (const [lx, lz] of [[-2.5, 6.5], [-0.5, 6.5], [-2.5, 7.5], [-0.5, 7.5]]) {
    scene.add(place(box(0.1, DESK_TOP_Y - 0.12, 0.1, C.desk), lx, (DESK_TOP_Y - 0.12) / 2, lz));
  }
  /* Pad lesehan di KEEMPAT slot pantry (Item 3) — dipusatkan di slot
     (dulu kursi 0.75 meleset dari slot). */
  scene.add(place(box(0.65, 0.1, 0.65, C.chair), -3, PAD_TOP - 0.05, 7));
  scene.add(place(box(0.65, 0.1, 0.65, C.chair), 0, PAD_TOP - 0.05, 7));
  scene.add(place(box(0.65, 0.1, 0.65, C.chair), -1.5, PAD_TOP - 0.05, 5.5));
  scene.add(place(box(0.65, 0.1, 0.65, C.chair), -1.5, PAD_TOP - 0.05, 8.5));
  /* Meja kopi (counter) + mesin kopi + rak camilan. Rak pindah
     ke z=11 (dulu z=1.5): rak lama menghalangi lane x=1.3. */
  scene.add(place(box(0.8, 1.0, 6, C.desk), -4.6, 0.5, 7));
  scene.add(place(box(0.5, 0.5, 0.4, 0x111111), -4.6, 1.25, 5.5));
  scene.add(place(cyl(0.12, 0.12, 0.18, 0xf5f5f0), -4.6, 1.15, 6.1));
  const shelf = box(0.7, 2.0, 2.5, C.desk);
  shelf.position.set(1.6, 1.0, 11);
  scene.add(shelf);
  const snackColors = [0xca4f40, 0x0f766e, 0xfc7a24, 0xc4b5fd, 0xf4a7b9, 0x1e3a8a];
  snackColors.forEach((col, i) => {
    scene.add(place(box(0.5, 0.3, 0.4, col), 1.6, 0.4 + Math.floor(i / 3) * 0.8, 10.2 + (i % 3) * 0.8));
  });
}

function buildGarden() {
  /* Tanaman (pot + daun bola), bangku, lampu (pusat taman (5.5,7);
     tanaman di 4 sudut ruangan, bangku di selatan, lampu di utara). */
  for (const [px, pz] of [[3, 1], [8, 1], [3, 13], [8, 13]]) {
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
}

function buildRanggaOffice() {
  /* Meja Rangga dipisah + lebih besar di ujung (utara-barat) —
     DITURUNKAN dari ROOMS['kantor-rangga'].slots[0] (bukan
     hardcode): meja di depan slot avatar Rangga (x, z+1.1). */
  const s0 = ROOMS['kantor-rangga'].slots[0];
  buildDesk(s0.x, s0.z + 1.1, 3.4);
  /* Bintang volt permanen di atas Rangga (plumbob, §5.4.5). */
  starPlumbob = new THREE.Mesh(
    new THREE.OctahedronGeometry(0.28),
    new THREE.MeshBasicMaterial({ color: VOLT }));
  starPlumbob.scale.set(1, 1.5, 1);
  starPlumbob.position.set(s0.x, 2.6, s0.z);
  scene.add(starPlumbob);
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
  /* Papan besar menempel sekat timur (x=15) + bidang putih. */
  scene.add(place(box(0.1, 2.2, 4.5, C.panel), 14.82, 1.6, 7));
  const board = new THREE.Mesh(
    new THREE.PlaneGeometry(4.3, 2.0),
    new THREE.MeshBasicMaterial({ color: 0xf5f5f0 }));
  board.position.set(14.76, 1.6, 7);
  board.rotation.y = -Math.PI / 2;
  scene.add(board);
}

function buildPerpustakaan() {
  /* Rak buku di sekat barat + timur (dengan buku warna-warni)
     + meja baca dari slot bermeja (data-driven) + tanaman. */
  for (const rx of [15.4, 20.5]) {
    const rak = box(0.7, 2.2, 9, C.desk);
    rak.position.set(rx, 1.1, 7);
    scene.add(rak);
  }
  const bookColors = [0xca4f40, 0x0f766e, 0xfc7a24, 0xc4b5fd, 0xf4a7b9, 0x1e3a8a];
  bookColors.forEach((col, i) => {
    const z = 3.6 + i * 1.3;
    scene.add(place(box(0.18, 0.5, 0.6, col), 15.82, 0.7 + (i % 3) * 0.6, z));
    scene.add(place(box(0.18, 0.5, 0.6, col), 20.18, 0.7 + ((i + 1) % 3) * 0.6, z));
  });
  const room = ROOMS.perpustakaan;
  for (const s of room.slots) {
    if (s.desk) buildDesk(s.x, s.z + 1.1, 2.2);
  }
  scene.add(place(cyl(0.45, 0.35, 0.5, C.pot), 20, 0.25, 13));
  scene.add(place(sph(0.55, C.plant), 20, 1.0, 13));
  scene.add(place(sph(0.35, C.plantDark), 20.2, 1.45, 12.9));
}

/* --- avatar GLB -------------------------------------------------- */
/* GLB 10/10 di public/models/ (10 rigged Draco + WebP,
   total ~1,38 MB / 1.445.116 B).
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
   SHOWCASE: tabel 11 avatar termasuk Meto (joint-map-11-avatars.json).
*/
const IDLE_ARM_DELTAS = {
  rangga: {
    shoulderL: { axis: [-0.5745, 0.0703, -0.8155], deg: 66.15 },
    shoulderR: { axis: [-0.5745, -0.0703, 0.8155], deg: 66.15 },
    forearmL: { axis: [-0.9763, -0.0252, 0.2149], deg: 13.94 },
    forearmR: { axis: [-0.9762, 0.0252, -0.2154], deg: 14.00 },
  },
  oto: {
    shoulderL: { axis: [-0.6306, 0.0000, -0.7761], deg: 78.52 },
    shoulderR: { axis: [-0.6306, 0.0000, 0.7761], deg: 78.52 },
    forearmL: { axis: [-0.9939, 0.0000, 0.1104], deg: 3.48 },
    forearmR: { axis: [-0.9939, 0.0000, -0.1104], deg: 3.48 },
  },
  beto: {
    shoulderL: { axis: [-0.7511, 0.0172, -0.6600], deg: 77.88 },
    shoulderR: { axis: [-0.7513, -0.0168, 0.6598], deg: 78.02 },
    forearmL: { axis: [-0.9748, -0.0317, -0.2207], deg: 4.28 },
    forearmR: { axis: [-0.9736, 0.0301, 0.2264], deg: 4.13 },
  },
  zeto: {
    shoulderL: { axis: [-0.8124, 0.0580, -0.5803], deg: 73.96 },
    shoulderR: { axis: [-0.8240, 0.1007, 0.5575], deg: 73.98 },
    forearmL: { axis: [-0.9487, -0.1897, 0.2530], deg: 10.90 },
    forearmR: { axis: [-0.8772, -0.1136, -0.4664], deg: 11.21 },
  },
  neto: {
    shoulderL: { axis: [-0.7499, 0.0235, -0.6611], deg: 81.12 },
    shoulderR: { axis: [-0.7499, -0.0235, 0.6611], deg: 81.12 },
    forearmL: { axis: [-0.9440, 0.0245, 0.3290], deg: 3.30 },
    forearmR: { axis: [-0.9440, -0.0245, -0.3290], deg: 3.30 },
  },
  geto: {
    shoulderL: { axis: [-0.4650, -0.1147, -0.8778], deg: 78.37 },
    shoulderR: { axis: [-0.4650, 0.1147, 0.8778], deg: 78.37 },
    forearmL: { axis: [0.0207, -0.0855, 0.9961], deg: 11.21 },
    forearmR: { axis: [0.0207, 0.0855, -0.9961], deg: 11.21 },
  },
  leto: {
    shoulderL: { axis: [-0.6402, 0.0000, -0.7682], deg: 75.79 },
    shoulderR: { axis: [-0.6402, 0.0000, 0.7682], deg: 75.79 },
    forearmL: { axis: [-0.8781, 0.0194, 0.4781], deg: 4.67 },
    forearmR: { axis: [-0.8781, -0.0194, -0.4781], deg: 4.67 },
  },
  ceto: {
    shoulderL: { axis: [-0.6017, 0.0190, -0.7985], deg: 71.34 },
    shoulderR: { axis: [-0.6017, -0.0190, 0.7985], deg: 71.34 },
    forearmL: { axis: [-0.9109, -0.0349, 0.4111], deg: 9.12 },
    forearmR: { axis: [-0.9109, 0.0349, -0.4111], deg: 9.12 },
  },
  deto: {
    shoulderL: { axis: [-0.6444, -0.0010, -0.7646], deg: 75.12 },
    shoulderR: { axis: [-0.6456, 0.0023, 0.7637], deg: 74.87 },
    forearmL: { axis: [-0.2238, -0.0147, 0.9745], deg: 11.83 },
    forearmR: { axis: [-0.2443, 0.0134, -0.9696], deg: 11.82 },
  },
  seto: {
    shoulderL: { axis: [-0.6319, -0.6782, -0.3753], deg: 75.17 },
    shoulderR: { axis: [-0.6319, 0.6782, 0.3753], deg: 75.17 },
    forearmL: { axis: [-0.0035, -0.1671, 0.9859], deg: 44.53 },
    forearmR: { axis: [-0.0035, 0.1671, -0.9859], deg: 44.53 },
  },
  meto: {
    shoulderL: { axis: [-0.7180, -0.0187, -0.6958], deg: 72.91 },
    shoulderR: { axis: [-0.7182, 0.0191, 0.6955], deg: 72.62 },
    forearmL: { axis: [-0.5971, -0.0346, 0.8014], deg: 8.92 },
    forearmR: { axis: [-0.6260, 0.0289, -0.7793], deg: 9.13 },
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
    gltfLoader.load(
      MODULE_BASE + 'models/' + name + '.glb',
      (gltf) => { clearTimeout(timer); const obj = normalizeAvatar(gltf.scene); fixAvatarMaterials(obj); applyIdlePose(obj, name); captureBoneBase(obj, name); finish(obj); },
      undefined,
      () => { clearTimeout(timer); console.warn('GLB gagal dimuat, pakai stand-in:', name); finish(fallbackAvatar(name)); });
  });
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
    /* Wajah pixel (§5.7): GLB wajahnya sudah di-bake, jadi varian
       wajah ditampilkan sebagai marker pixel kecil di atas kepala
       (bukan ganti mesh) — fokus/senyum/netral, sesuai keadaan. */
    const face = makeFaceSprite(name);
    face.sprite.position.y = 2.05;
    avatarGroups[name].add(face.sprite);
    faceSprites[name] = face;
  });
}

/* Marker wajah 16x16 piksel (canvas -> sprite, selalu menghadap
   kamera). Fokus = mata kotak + mulut datar; senyum = mata + busur;
   netral = mata + garis. Bukan emoji, bukan emosi ditebak. */
function makeFaceSprite(name) {
  const canvas = document.createElement('canvas');
  canvas.width = 32; canvas.height = 32;
  const ctx = canvas.getContext('2d');
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false }));
  sprite.scale.set(0.55, 0.55, 1);
  const face = { sprite, canvas, ctx, tex, face: null };
  drawFace(face, 'netral');
  return face;
}
function drawFace(face, variant) {
  if (face.face === variant) return;
  face.face = variant;
  const g = face.ctx;
  g.clearRect(0, 0, 32, 32);
  g.fillStyle = '#0f1115';
  g.beginPath(); g.arc(16, 16, 15, 0, Math.PI * 2); g.fill();
  g.fillStyle = '#e6e6e6';
  g.fillRect(9, 11, 4, 4); g.fillRect(19, 11, 4, 4); /* mata */
  g.strokeStyle = '#e6e6e6'; g.lineWidth = 2;
  g.beginPath();
  if (variant === 'senyum') { g.arc(16, 17, 6, 0.15 * Math.PI, 0.85 * Math.PI); }
  else if (variant === 'fokus') { g.moveTo(11, 22); g.lineTo(21, 22); g.moveTo(11, 25); g.lineTo(21, 25); }
  else { g.moveTo(12, 23); g.lineTo(20, 23); }
  g.stroke();
  face.tex.needsUpdate = true;
}

/* --- bubble (overlay HTML) --------------------------------------- */
/* Bubble diproyeksikan dari posisi 3D ke layar (§5.3): status
   persisten + ucapan 15 detik, maks 1+1 per agen, lebar maks
   180px. Di bawah 700px hanya glyph (teks lengkap pindah ke kartu
   agen). Bubble TIDAK BOLEH menutupi avatar lain/papan tugas —
   pass layout sederhana: bila dua bubble bertumpuk, yang kedua
   digeser ke atas. */
const bubbleEls = {}; /* name -> {status, speech} */
function glyphSvg(glyph) {
  return '<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">'
    + (GLYPH_DEFS[glyph] || '') + '</svg>';
}
function ensureBubbles() {
  for (const name of ROOM_ORDER) {
    if (bubbleEls[name]) continue;
    const status = document.createElement('div');
    status.className = 'bubble status';
    status.dataset.agent = name;
    status.style.display = 'none';
    const speech = document.createElement('div');
    speech.className = 'bubble speech';
    speech.dataset.agent = name;
    speech.style.display = 'none';
    bubbleLayer.append(status, speech);
    bubbleEls[name] = { status, speech };
  }
}
function setBubbleContent(el, glyph, text, timeLabel) {
  el.textContent = '';
  if (glyph) {
    const g = document.createElement('span');
    g.className = 'glyph';
    g.innerHTML = glyphSvg(glyph);
    el.appendChild(g);
  }
  const t = document.createElement('span');
  t.className = 'txt';
  t.textContent = text;
  el.appendChild(t);
  if (timeLabel) {
    const tm = document.createElement('span');
    tm.className = 'time';
    tm.textContent = timeLabel;
    el.appendChild(tm);
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
  /* Batas tampil (§5.12 / 11/10): maks 3 bubble di canvas —
     speech dulu (terbaru), lalu status (terbaru). Sisanya display
     none (teks lengkap tetap ada di kartu agen). */
  const candidates = [];
  for (const st of state.agents) {
    if (st.statusText) {
      candidates.push({ kind: 'status', name: st.name, ts: st.lastActiveMs || 0 });
    }
    const els0 = bubbleEls[st.name];
    if (els0 && els0.speech.dataset.show === '1' && st.speech) {
      candidates.push({ kind: 'speech', name: st.name, ts: (st.lastMessage && st.lastMessage.createdAtMs) || 0 });
    }
  }
  const shown = new Set(selectVisibleBubbles(candidates, 3).map((c) => c.kind + ':' + c.name));
  lastBubblesShown = shown.size;
  const placed = [];
  for (const st of state.agents) {
    const els = bubbleEls[st.name];
    if (!els) continue;
    const pos = avatarPos[st.name];
    const g = avatarGroups[st.name];
    if (!pos || !g.visible) {
      els.status.style.display = 'none';
      els.speech.style.display = 'none';
      continue;
    }
    /* Status persisten (hanya bila ada tugas aktif + terpilih). */
    if (st.statusText && shown.has('status:' + st.name)) {
      setBubbleContent(els.status, st.glyph, st.statusText, null);
      els.status.classList.toggle('stale', !!st.stale);
      els.status.classList.toggle('boss', st.name === 'rangga' && state.bossActive);
      els.status.style.display = 'flex';
      const p = projectToScreen(pos.x, 2.35, pos.z);
      els.status.dataset.px = p.x.toFixed(1);
      els.status.dataset.py = p.y.toFixed(1);
      els.status.style.left = p.x + 'px';
      els.status.style.top = p.y + 'px';
      els.status.style.visibility = p.behind ? 'hidden' : 'visible';
      placed.push(els.status);
    } else {
      els.status.style.display = 'none';
    }
    /* Ucapan event (ditampilkan 15 detik oleh applyState + terpilih). */
    if (els.speech.dataset.show === '1' && st.speech && shown.has('speech:' + st.name)) {
      setBubbleContent(els.speech, null, st.speech.text, st.speech.hhmm);
      els.speech.style.display = 'flex';
      const p = projectToScreen(pos.x, 3.05, pos.z);
      els.speech.dataset.px = p.x.toFixed(1);
      els.speech.dataset.py = p.y.toFixed(1);
      els.speech.style.left = p.x + 'px';
      els.speech.style.top = p.y + 'px';
      els.speech.style.visibility = p.behind ? 'hidden' : 'visible';
      placed.push(els.speech);
    } else {
      els.speech.style.display = 'none';
    }
  }
  /* Anti-tumpuk + clamp (satu pass): tiap bubble ditempatkan berurutan.
     Bila bertumpuk dengan yang sudah ditempatkan, geser ke ATAS 42px;
     bila tidak ada ruang di atas (mentok tepi atas 34px), geser ke
     BAWAH 42px — lebih baik menutupi sebagian kepala avatar sebentar
     daripada dua bubble saling menimpa tak terbaca. Clamp kiri/kanan
     setengah lebar bubble (~95px). */
  const w = wrap.clientWidth || 800;
  const placedXY = [];
  for (const el of placed) {
    let x = Math.min(Math.max(parseFloat(el.dataset.px), 95), Math.max(95, w - 95));
    let y = Math.max(parseFloat(el.dataset.py), 34);
    let guard = 0;
    let moved = true;
    while (moved && guard < 12) {
      moved = false; guard++;
      for (const p of placedXY) {
        if (Math.abs(p.x - x) < 100 && Math.abs(p.y - y) < 36) {
          const up = p.y - 42;
          y = up >= 34 ? up : p.y + 42;
          moved = true;
        }
      }
    }
    placedXY.push({ x, y });
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
   role; agen aktif (sama dengan plumbob) dapat class 'active' +
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
   saat follow — chip "Mengikuti <nama> · <peran>" + status/tugas
   aktif + tombol tutup (× = lepas follow). Read-only: TANPA tombol
   lompat (tidak ada pesan/tugas untuk dilompati). Semua teks via
   textContent. */
function ensureFollowCard() {
  if (followCardEl) return followCardEl;
  if (!wrap) return null;
  const el = document.createElement('div');
  el.id = 'roomFollowCard';
  el.style.position = 'absolute';
  el.style.left = '8px';
  el.style.bottom = '8px';
  el.style.zIndex = '5';
  el.style.maxWidth = '260px';
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
  head.appendChild(nm);
  const close = document.createElement('button');
  close.type = 'button';
  close.textContent = '×'; /* U+00D7 (bukan emoji — tes 0.4.8 melarang
    blok Dingbats U+2600–U+27BF). */
  close.setAttribute('aria-label', 'Keluar follow');
  close.style.marginLeft = 'auto';
  close.style.background = 'transparent';
  close.style.border = 'none';
  close.style.color = '#9aa0a6';
  close.style.cursor = 'pointer';
  close.style.fontSize = '1rem';
  close.addEventListener('click', () => exitFollow());
  head.appendChild(close);
  el.appendChild(head);
  const status = document.createElement('div');
  status.className = 'follow-status';
  el.appendChild(status);
  const meta = document.createElement('div');
  meta.className = 'follow-meta';
  meta.style.color = '#9aa0a6';
  meta.style.fontSize = '.8rem';
  el.appendChild(meta);
  /* Showcase read-only: tanpa tombol lompat. Chip follow = kartu ini. */
  el.userData = { mini, nm, status, meta };
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
  u.status.textContent = st ? (st.statusText || '— tidak ada tugas aktif —') : '—';
  u.meta.textContent = st ? ('aktif ' + st.lastActiveLabel + ' · ' + st.openCount + ' tugas') : '';
  el.style.display = 'block';
}
function hideFollowCard() {
  if (followCardEl) followCardEl.style.display = 'none';
}

/* --- kartu vertikal HP (§5.8, mode utama HP) -------------------- */
/* Dibangun dengan DOM API (textContent) — judul tugas dari API
   tidak pernah masuk innerHTML. avatarVoxel (SVG, data tetap +
   esc) adalah satu-satunya innerHTML di sini, sama seperti
   pemakaian di roomSvg M2. */
function renderCards() {
  if (!cardsEl || !state) return;
  cardsEl.textContent = '';
  const selfName = state.self;
  for (const roomId of Object.keys(ROOMS)) {
    const members = state.agents.filter((a) => a.room === roomId);
    if (!members.length) continue;
    const group = document.createElement('div');
    group.className = 'room-group';
    const h = document.createElement('h4');
    h.textContent = ROOMS[roomId].label + ' · ' + members.length;
    group.appendChild(h);
    for (const st of members) {
      const card = document.createElement('button');
      card.className = 'agent-card';
      card.dataset.agent = st.name;
      card.type = 'button';
      const mini = document.createElement('span');
      mini.className = 'mini-avatar';
      mini.innerHTML = miniAvatarHTML(st.name);
      card.appendChild(mini);
      const main = document.createElement('span');
      main.className = 'card-main';
      const nm = document.createElement('b');
      nm.textContent = st.label + ' · ' + st.role;
      main.appendChild(nm);
      const status = document.createElement('span');
      status.className = 'card-status';
      status.textContent = st.statusText || '— tidak ada tugas aktif —';
      if (st.stale) status.classList.add('stale');
      main.appendChild(status);
      const meta = document.createElement('span');
      meta.className = 'card-meta';
      meta.textContent = 'aktif ' + st.lastActiveLabel + ' · ' + st.openCount + ' tugas';
      main.appendChild(meta);
      card.appendChild(main);
      if (selfName && st.name === selfName && state.unreadSelf != null && state.unreadSelf > 0) {
        const badge = document.createElement('span');
        badge.className = 'badge';
        badge.textContent = String(state.unreadSelf);
        card.appendChild(badge);
      }
      card.addEventListener('click', () => { enterFullscreen(); enterFollow(st.name); });
      group.appendChild(card);
    }
    cardsEl.appendChild(group);
  }
  const note = document.createElement('p');
  note.className = 'cards-note';
  note.textContent = 'Ketuk kartu untuk mengikuti agen itu di layar penuh.';
  cardsEl.appendChild(note);
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
  if (name === 'rangga' && starPlumbob) starPlumbob.position.set(slot.x, 2.6, slot.z);
  /* Pose: snap langsung bila penempatan awal/teleport fixture;
     bila tidak, blend ~400 ms dari bobot saat ini (100/10). */
  if (opts.snap || !poseAnim[name]) {
    snapPoseWeights(name);
    g.position.y = baseY;
  } else {
    startPoseTransition(name);
  }
  if (name === currentActiveAgent) updatePlumbob();
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
    const from = avatarPos[name] ? { ...avatarPos[name] } : { ...toSlot };
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
         betis setengah amplitudo (±12°) sefase tertinggal, bahu ±15°
         berlawanan dengan kaki seberang (bahu L lawan kaki R).
         Duduk disusun di atasnya dengan bobot sitW (bone yang sama
         dikalikan berurutan dari base — tidak akumulasi antar frame). */
      if (roles) {
        const phase = (d * Math.PI * 2) / stride;
        const s = Math.sin(phase);
        const sLag = Math.sin(phase - 0.7);
        const deltas = [
          { bone: roles.thighL, axis: [1, 0, 0], deg: 25 * s * swingAmp },
          { bone: roles.thighR, axis: [1, 0, 0], deg: -25 * s * swingAmp },
          { bone: roles.shinL, axis: [1, 0, 0], deg: -12 * sLag * swingAmp },
          { bone: roles.shinR, axis: [1, 0, 0], deg: 12 * sLag * swingAmp },
          { bone: roles.shoulderL, axis: [1, 0, 0], deg: 15 * s * swingAmp },
          { bone: roles.shoulderR, axis: [1, 0, 0], deg: -15 * s * swingAmp },
        ];
        if (sitW > 0.001) {
          for (const sd of sitDeltas(name, roles)) deltas.push({ ...sd, deg: sd.deg * sitW });
        }
        resetBones(name);
        addBoneDeltas(name, deltas);
      }
      if (name === 'oto') {
        const hop = Math.abs(Math.sin(pe * Math.PI * 4));
        g.scale.set(1 + hop * 0.06, 1 + hop * 0.12, 1 + hop * 0.06);
      }
      if (name === 'rangga' && starPlumbob) starPlumbob.position.set(x, 2.6 + walkBobY(name, pe), z);
      if (name === currentActiveAgent && plumbob) {
        plumbob.position.set(x, plumbobTargetY(walkBobY(name, pe)), z);
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
   mengetik. (Bob plumbob TIDAK di sini — dihitung saat render.) */
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
     tidak menyimpan string state mentah — yang tersisa face 'fokus'
     (state working/meeting) vs 'netral' (idle/away); hitung dari situ. */
  const working = state ? state.agents.filter((a) => a.face === 'fokus').length : 0;
  const ageMin = Math.round((Date.now() - snapGeneratedMs) / 60000);
  let text = 'Snapshot per ' + hhmmss + ' · ' + working + ' agen bekerja · polling 60 detik';
  if (ageMin >= 15) text += ' · snapshot basi (' + ageMin + ' mnt)';
  if (extra) text += ' · ' + extra;
  statusEl.textContent = text;
}

function applyState(ns, opts = {}) {
  const initial = !!opts.initial;
  const prev = state;
  state = ns;
  /* Plumbob agen aktif (tanpa Rangga — dia punya bintang volt).
     Bila agen aktif PINDAH, plumbob lerp halus ke agen baru
     (~300 ms) daripada loncat. */
  const prevActive = currentActiveAgent;
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
  /* Wajah + avatar. */
  for (const st of ns.agents) {
    const face = faceSprites[st.name];
    if (face) drawFace(face, st.face);
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
        els.speech.dataset.show = '1';
        setTimeout(() => { els.speech.dataset.show = '0'; requestRender(); }, 15000);
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
  renderCards();
  renderPortraits();
  refreshFollowCard();
  if (plumbob && currentActiveAgent && currentActiveAgent !== prevActive && prevActive) {
    const pos = avatarPos[currentActiveAgent];
    if (pos) {
      plumbob.material.color.set(KNOWN_AGENTS[currentActiveAgent].color);
      plumbob.visible = true;
      animatePlumbobTo(pos.x, plumbobTargetY(0), pos.z);
    } else {
      updatePlumbob();
    }
  } else {
    updatePlumbob();
  }
  setStatusText();
  requestRender();
}

function applyEmpty() {
  state = null;
  currentActiveAgent = null;
  if (cameraMode === 'follow') exitFollow();
  hideFollowCard();
  updatePlumbob();
  for (const name of ROOM_ORDER) {
    avatarGroups[name].visible = false;
    const els = bubbleEls[name];
    if (els) { els.status.style.display = 'none'; els.speech.style.display = 'none'; }
  }
  dynamicPanels.taskBoard.redraw([], false);
  dynamicPanels.whiteboard.redraw('blackboard-umum', 0, false);
  dynamicPanels.msgBoard.redraw([], false);
  dynamicPanels.fileShelf.redraw([], false);
  dynamicPanels.threadDoor.redraw('blackboard-umum', 0, 0, false);
  dynamicPanels.tv.redraw(null, false);
  for (const d of desks) { drawMonitor(d.monTex, null); drawPlate(d.plateTex, null, null); }
  if (cardsEl) {
    cardsEl.textContent = '';
    const p = document.createElement('p');
    p.className = 'cards-note';
    p.textContent = 'Snapshot belum tersedia — ruangan kosong. Coba lagi sebentar lagi.';
    cardsEl.appendChild(p);
  }
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
   adalah snapshot.json (same origin, relatif). */
let SNAPSHOT_URL = new URL('snapshot.json', MODULE_BASE).href; /* default: snapshot di samping modul; mount({snapshotUrl}) override */
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
    agentState.glyph = (working || meeting) && !staleSnap ? 'work' : 'zzz';
    agentState.face = (working || meeting) ? 'fokus' : 'netral';
    agents.push(agentState);
  }
  const slots = assignSlots(agents);
  for (const st of agents) {
    st.slot = slots[st.name];
    st.sitting = isDeskSlotFn(st.room, st.slot);
    const snapSt = (byId[st.name] && byId[st.name].state) || '';
    st.activity = st.room === 'pantry' && !st.activeTask ? 'coffee'
      : (st.room === 'ruang-kerja' && snapSt === 'idle' ? 'phone' : null);
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
async function fetchSnapshot() {
  for (let attempt = 1; attempt <= SNAPSHOT_MAX_ATTEMPTS; attempt++) {
    const ctrl = new AbortController();
    const to = setTimeout(() => ctrl.abort(), SNAPSHOT_TIMEOUT_MS);
    try {
      const r = await fetch(SNAPSHOT_URL, { cache: 'no-store', signal: ctrl.signal });
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
    if (els) { els.status.style.display = 'none'; els.speech.style.display = 'none'; }
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
function startHeroRotate() {
  if (heroTimer || REDUCED || !heroRotateEnabled) return;
  heroTimer = setInterval(() => {
    if (displayMode !== 'hero' || document.hidden) return;
    azimuth += 0.015;
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
  try {
    if (overlay.requestFullscreen) {
      await overlay.requestFullscreen().catch(() => { fsFallback = true; });
    } else {
      fsFallback = true;
    }
  } catch (_) { fsFallback = true; }
  if (fsFallback) overlay.classList.add('fs-fallback');
  if (renderer) {
    renderer.setSize(roomWrapEl().clientWidth || 800, roomWrapEl().clientHeight || 600, false);
    fitCamera(); updateCamera();
  }
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
  if (renderer) {
    renderer.setSize(roomWrapEl().clientWidth || 800, roomWrapEl().clientHeight || 600, false);
    fitCamera(); updateCamera();
  }
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
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    try { canvas.setPointerCapture(e.pointerId); } catch (_) { /* abaikan */ }
    if (pointers.size === 1) {
      dragLast = { x: e.clientX, y: e.clientY };
      dragMoved = 0;
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
        followYaw -= dx * 0.005;
        followPitch = Math.min(1.25, Math.max(0.08, followPitch + dy * 0.003));
      } else {
        azimuth -= dx * 0.005;
        azimuth = Math.max(Math.PI / 4 - 1.1, Math.min(Math.PI / 4 + 1.1, azimuth));
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
        if (lastPinch > 0 && d > 0) {
          camZoom = Math.max(0.6, Math.min(2.2, camZoom * (d / lastPinch)));
          updateCamera();
        }
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
    e.preventDefault();
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
  return isDeskSlotFn(roomId, slot);
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
        name: a.name, room: a.room, glyph: a.glyph, face: a.face,
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
#stageHero{position:relative;height:480px;border:1px solid #2d333b;border-radius:8px;overflow:hidden;cursor:pointer;background:#0f1115}
#roomWrap{position:relative;width:100%;height:100%;background:#0f1115}
#roomCanvas{position:absolute;inset:0}
#roomCanvas canvas{display:block;width:100%;height:100%;touch-action:none}
#roomBubbles{position:absolute;inset:0;overflow:hidden;pointer-events:none}
.bubble{position:absolute;transform:translate(-50%,-100%);max-width:180px;display:flex;gap:.3rem;align-items:center;background:rgba(22,27,34,.94);border:1px solid #2d333b;border-radius:6px;padding:.15rem .4rem;font-size:.8rem;line-height:1.3;color:#e6e6e6;white-space:nowrap;overflow:hidden}
.bubble .txt{overflow:hidden;text-overflow:ellipsis}
.bubble .glyph{color:#a3ff00;flex:none;display:flex}
.bubble .time{color:#9aa0a6;font-size:.75rem;flex:none}
#roomStatus{font-size:.9rem;color:#9aa0a6;padding:.4rem .8rem;border:1px solid #2d333b;border-top:none;background:#161b22;border-radius:0 0 8px 8px;display:flex;gap:.6rem;align-items:center;flex-wrap:wrap}
#roomStatus span{flex:1;min-width:0}
.hero-actions{display:flex;gap:.6rem;align-items:center;flex-wrap:wrap;margin-top:.6rem}
.hint{font-size:.9rem;color:#9aa0a6;margin:0}
#btnEnterFs,#btnExitFs{font:inherit;font-size:1rem;padding:.5rem .6rem;border:1px solid #2d333b;border-radius:6px;background:#21262d;color:#e6e6e6;min-height:44px;cursor:pointer}
#fsOverlay{position:fixed;inset:0;z-index:50;background:#0f1115}
#fsOverlay[hidden]{display:none}
#stageFs{position:absolute;inset:0}
#btnExitFs{position:absolute;top:.6rem;right:.6rem;z-index:60}
#roomPortraits{display:flex;gap:.5rem;overflow-x:auto;padding:.45rem .8rem;background:#161b22;border:1px solid #2d333b;border-radius:8px;margin-top:.8rem}
#roomPortraits .portrait{flex:none;display:flex;flex-direction:column;align-items:center;gap:.15rem;min-width:64px;padding:.3rem .2rem .25rem;background:transparent;color:#e6e6e6;border:1px solid #2d333b;border-radius:8px;cursor:pointer}
#roomPortraits .portrait .mini-avatar svg{width:56px;height:60px;display:block}
#roomPortraits .portrait .portrait-name{font-size:10px;line-height:1.2;color:#e6e6e6}
#roomPortraits .portrait .portrait-role{font-size:10px;line-height:1.2;color:#9aa0a6}
#roomCards{display:block;padding:.2rem .2rem}
.agent-card{display:flex;gap:.6rem;align-items:center;width:100%;min-height:64px;text-align:left;margin:.3rem 0;padding:.4rem .5rem;border:1px solid #2d333b;border-radius:8px;background:#21262d;color:#e6e6e6;cursor:pointer}
.agent-card .mini-avatar svg{width:44px;height:48px;flex:none}
.agent-card .card-main{flex:1;min-width:0;display:flex;flex-direction:column}
.agent-card .card-status{font-size:.9rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.agent-card .card-meta{font-size:.85rem;color:#9aa0a6}
.cards-note{font-size:.9rem;color:#9aa0a6}
@media (max-width:700px){#stageHero{height:340px}.bubble .txt,.bubble .time{display:none}}
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
  actions.appendChild(mk('p', null, 'hint', 'Klik ruangan untuk layar penuh · klik agen untuk mengikuti · seret untuk orbit, scroll untuk zoom'));
  root.appendChild(actions);
  const portraits = mk('div', 'roomPortraits');
  portraits.setAttribute('aria-label', 'Portrait agen');
  root.appendChild(portraits);
  const cards = mk('div', 'roomCards');
  cards.setAttribute('aria-label', 'Daftar agen per ruangan');
  root.appendChild(cards);
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
    renderer.setSize(wrap.clientWidth || 800, wrap.clientHeight || 600, false);
    fitCamera();
    updateCamera();
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
  startHeroRotate();
  startAmbient();
  startWorkTimer();
  startActivityTimer();
  startClockTimer();
  startMonitorTimer();
  markReady();
}

/* Fallback tanpa WebGL: kartu tetap dibangun dari snapshot
   (tanpa scene); tanpa login, tanpa lobby. */
async function buildSceneFallbackOnly() {
  const snap = await fetchSnapshot();
  if (snap) {
    snapLoaded = true;
    snapGeneratedMs = Date.parse(snap.generated_at || '') || Date.now();
    lastFetchMs = Date.now();
    state = snapshotToState(snap, Date.now());
  }
  renderCards();
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
  }
});

/* Auto-init HANYA bila struktur viewer sudah ada di dokumen
   (office/index.html). Di host page (kantor.html) struktur belum
   ada — modul hanya mengekspos window.__neugiShowcase.mount. */
if (document.getElementById('roomCanvas')) { mountShowcase(document.body, {}); }
