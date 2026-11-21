/* ROOM-VIEWMODEL-START — Virtual Office 3D (0.4.8, spek §5
   synthesis-discussion-m3.md). Fungsi MURNI: API board -> keadaan
   ruangan per agen. Tanpa DOM, tanpa fetch, tanpa token, tanpa
   penyimpanan — bisa diuji di Node (lihat Room3DViewModel048Test).
   Semua teks di sini datang dari data API; tidak ada isi karangan.
   Aturan kejujuran (§5.10): tanpa status online / titik hijau /
   "mengetik"; tanpa bubble pikiran; tanpa skor; tanpa angka
   keuangan; tanpa emoji sebagai ikon; glyph pixel di GLYPH_DEFS.
   Koordinat: lantai x timur (barat -21 .. timur 21), z selatan
   (utara -14 .. selatan 14), y atas. Gang utama di z = -2 (garis
   GANG_Z, lebar 2.4): semua jalan antar ruangan lewat gang ini,
   tidak menembus furnitur (lihat planWalk + LAYOUT.md di work-f/).
   DENAH 0.4.9 (Worker F): floor plan 42x28 (dulu 26x18), 9 ruang
   (dulu 6): 4 utara (kantor-rangga, pantry, lounge,
   studio-konten) + 5 selatan (ruang-kerja, ruang-rapat, taman,
   war-room, perpustakaan). */

/* 11 agen yang dikenal (label/peran/warna = AVATAR_PARTS di
   index.html + warna identitas M1/M2). Agen di luar daftar ini
   tidak punya meja — diabaikan view-model (bukan ditebak). */
export const KNOWN_AGENTS = {
  rangga: { label: 'Rangga', role: 'Owner', color: '#a3ff00' },
  oto: { label: 'Oto', role: 'CEO', color: '#a3ff00' },
  beto: { label: 'Beto', role: 'CTO', color: '#fc7a24' },
  zeto: { label: 'Zeto', role: 'CSO', color: '#ca4f40' },
  neto: { label: 'Neto', role: 'CRO', color: '#0f766e' },
  geto: { label: 'Geto', role: 'Backup', color: '#c4b5fd' },
  leto: { label: 'Leto', role: 'Intern', color: '#f4a7b9' },
  ceto: { label: 'Ceto', role: 'Sales', color: '#1e3a8a' },
  seto: { label: 'Seto', role: 'Dukungan Umum', color: '#ff7f50' },
  deto: { label: 'Deto', role: 'Dukungan Umum', color: '#64748b' },
  meto: { label: 'Meto', role: 'Support', color: '#22c55e' },
};
export const ROOM_ORDER = ['rangga', 'oto', 'beto', 'zeto', 'neto', 'geto', 'leto', 'ceto', 'seto', 'deto', 'meto'];
export const FLOOR = { x0: -21, x1: 21, z0: -14, z1: 14 };
export const GANG_Z = -2;
/* Lebar gang (dipakai renderer buat lantai gang + garis tepi). */
export const GANG_W = 2.4;
export const MIN_15 = 15 * 60 * 1000;
export const HOUR_1 = 60 * 60 * 1000;
export const HOUR_2 = 2 * 60 * 60 * 1000;
/* Status tugas yang dihitung "aktif/terbuka" (sama seperti filter
   panel Tugas di list view). */
export const ACTIVE_STATUSES = ['submitted', 'working', 'input-required'];

/* 9 ruang (§5.2 + UPGRADE 11/10 denah besar Worker F, 0.4.9).
   slots = titik berdiri avatar di ruangan itu, rot = rotation.y
   (0 = menghadap selatan/+z, ke arah kamera). door = titik pintu
   ruangan di gang (z = GANG_Z), dipakai planWalk + posisi overflow
   bila slot habis. lane = koridor utara-selatan yang BEBAS furnitur
   (x) — jalur jalan keluar/masuk ruangan (lihat planWalk); slot
   boleh menimpa lane sendiri (rapat/war-room: slot di dua sisi
   meja → dua lane). legDy = geser baris jalan lateral dari
   baris slot (ruang bermeja: -1 supaya kaki jalan tidak
   menyerempet kursi yang menempel di baris slot). desk: true =
   slot ini dilayani meja (meja dibangun dari slot itu di
   room3d.js; agen di sana DUDUK — lihat isDeskSlot). Denah
   lengkap + alasan tiap angka: LAYOUT.md di work-f/. */
export const ROOMS = {
  'kantor-rangga': {
    label: 'Kantor Rangga',
    door: { x: -15, z: GANG_Z },
    lane: -15,
    legDy: -1,
    slots: [
      { x: -18, z: -11, rot: 0, desk: true },
      { x: -13.5, z: -11, rot: 0 },
    ],
  },
  'ruang-rapat': {
    label: 'Ruang Rapat',
    door: { x: -1.5, z: GANG_Z },
    lane: -4.1,
    legDy: 0,
    slots: [
      { x: -4.1, z: 7, rot: Math.PI / 2, lane: -4.1 },
      { x: 1.1, z: 7, rot: -Math.PI / 2, lane: 1.1 },
      { x: -1.5, z: 4.4, rot: 0, lane: -4.1 },
      { x: -1.5, z: 9.6, rot: Math.PI, lane: 1.1 },
    ],
  },
  lounge: {
    label: 'Lounge',
    door: { x: 5, z: GANG_Z },
    lane: 0.7,
    legDy: 0,
    slots: [
      { x: 2.5, z: -11.5, rot: Math.PI },
      { x: 5.25, z: -11.5, rot: Math.PI },
      { x: 8, z: -11.5, rot: Math.PI },
    ],
  },
  'studio-konten': {
    label: 'Studio Konten',
    door: { x: 16, z: GANG_Z },
    lane: 20,
    legDy: -1,
    slots: [
      { x: 13.5, z: -11, rot: 0, desk: true },
      { x: 18, z: -11, rot: 0 },
      { x: 15.75, z: -6.5, rot: Math.PI },
    ],
  },
  'ruang-kerja': {
    label: 'Ruang Kerja',
    door: { x: -9.7, z: GANG_Z },
    lane: -9.7,
    legDy: -1,
    slots: [
      { x: -19, z: 2, rot: 0, desk: true },
      { x: -13, z: 2, rot: 0, desk: true },
      { x: -7, z: 2, rot: 0, desk: true },
      { x: -19, z: 6, rot: 0, desk: true },
      { x: -13, z: 6, rot: 0, desk: true },
      { x: -7, z: 6, rot: 0, desk: true },
      { x: -19, z: 10, rot: 0, desk: true },
      { x: -13, z: 10, rot: 0, desk: true },
      { x: -7, z: 10, rot: 0, desk: true },
    ],
  },
  pantry: {
    label: 'Pantry',
    door: { x: -5, z: GANG_Z },
    lane: -0.8,
    legDy: 0,
    slots: [
      { x: -6.5, z: -9, rot: Math.PI / 2 },
      { x: -3.5, z: -9, rot: -Math.PI / 2 },
      { x: -5, z: -10.5, rot: 0 },
      { x: -5, z: -7.5, rot: Math.PI },
    ],
  },
  taman: {
    label: 'Taman',
    door: { x: 5.5, z: GANG_Z },
    lane: 4.5,
    legDy: 0,
    slots: [
      { x: 4, z: 4, rot: 0.7 },
      { x: 7, z: 4, rot: -0.7 },
      { x: 4, z: 10, rot: 0.5 },
      { x: 7, z: 10, rot: -0.5 },
    ],
  },
  'war-room': {
    label: 'War Room',
    door: { x: 12, z: GANG_Z },
    lane: 9.6,
    legDy: 0,
    slots: [
      { x: 10, z: 7, rot: Math.PI / 2, lane: 9.6 },
      { x: 14, z: 7, rot: -Math.PI / 2, lane: 14.3 },
      { x: 12, z: 4.6, rot: 0, lane: 9.6 },
      { x: 12, z: 9.4, rot: Math.PI, lane: 9.6 },
    ],
  },
  perpustakaan: {
    label: 'Perpustakaan',
    door: { x: 18, z: GANG_Z },
    lane: 19.4,
    legDy: -1,
    slots: [
      { x: 17.5, z: 4.5, rot: 0, desk: true },
      { x: 19, z: 9, rot: Math.PI },
      { x: 16.8, z: 10, rot: 0.4 },
    ],
  },
};

/* Glyph pixel 16x16 (bukan emoji). Dipetakan 1:1 ke keadaan nyata
   (§5.3): laptop=kerja, centang=baru selesai, Z=diam, panah
   atas=mengunggah, panah balas=membalas, buku=membaca. Isi SVG
   inner (path/rect, fill/stroke = currentColor). */
export const GLYPH_DEFS = {
  work: '<rect x="3" y="4" width="10" height="7" fill="none" stroke="currentColor" stroke-width="1.6"/><rect x="2" y="11" width="12" height="1.8" fill="currentColor"/>',
  done: '<path d="M3 8.5 L6.5 12 L13 4.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="square"/>',
  zzz: '<path d="M4 4 H12 L5 11 H12" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="square"/>',
  upload: '<path d="M8 2.5 V10 M4.5 6 L8 2.5 L11.5 6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="square"/><rect x="3" y="11" width="10" height="1.8" fill="currentColor"/>',
  reply: '<path d="M12 4 H6 a3.5 3.5 0 0 0 0 7 h6 M9 1.5 L5.5 4.5 L9 7.5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="square"/>',
  read: '<rect x="3" y="3" width="4.5" height="10" fill="none" stroke="currentColor" stroke-width="1.4"/><rect x="8.5" y="3" width="4.5" height="10" fill="none" stroke="currentColor" stroke-width="1.4"/>',
};

export function trunc(s, maxLen) {
  s = String(s == null ? '' : s);
  if (s.length <= maxLen) return s;
  return s.slice(0, maxLen - 1) + '…';
}

/* Jam client (jam asli, §5.2) — HH:MM lokal. */
export function hhmm(ms) {
  if (!ms) return '—';
  const d = new Date(ms);
  return String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
}

function ts(s) {
  const t = Date.parse(s || '');
  return Number.isNaN(t) ? 0 : t;
}

function lower(s) {
  return String(s || '').toLowerCase();
}

/* Kata kunci judul tugas -> ruangan baru (UPGRADE 11/10, 0.4.9).
   DI-GROUND ke judul tugas NYATA (lihat LAYOUT.md § kata kunci):
   - studio: 'Reel Ep. 6', 'carousel' (konten IG, baseline audit
     Leto 18 Nov), 'konten'/'video' (lane produksi Oto/Beto).
   - war-room: 'Shopify' / bounty HackerOne (Zeto), 'trading' /
     'backtest' / 'crypto' (Neto; 'Crypto scouting' Geto),
     'pentest' / 'threat' / 'ospek' (intel Zeto: 'Ospek #2
     NGINX2Root + studi MCP Rinwall'), 'security' / 'bounty'.
   - perpustakaan: 'Audit tugas terbuka di board' (Leto),
     'Audit lead IG & Threads' (Ceto), 'laporan' / 'analisis'
     (laporan mingguan Leto), 'riset' / 'studi' / 'scouting'
     (tanpa 'crypto' — 'crypto' dimenangkan war-room duluan).
   Grounding dicatat apa adanya: saat pengecekan (20 Nov 2026,
   ~22:30 WIB) daftar tugas board mengembalikan 0 tugas
   (activity counts.tasks = 0), jadi kata kunci di-ground ke
   judul historis yang tercatat di MEMORY.md + judul fixture
   (yang mencerminkan tugas board nyata) — BUKAN karangan.
   Pencocokan: substring case-insensitive pada judul tugas aktif.
   Prioritas first-match: konten -> war-room -> perpustakaan
   (lihat resolveRoom). Overlap yang diputus prioritas:
   'Crypto scouting' -> war-room ('crypto' menang atas
   'scouting'); 'Audit lead IG & Threads' -> perpustakaan
   ('audit'/'lead' — 'threads'/'instagram' SENGAJA tidak masuk
   kata kunci studio supaya audit platform tidak dikira konten);
   'audit keamanan' -> war-room (frasa, sebelum 'audit' generik).
   Daftar ini data, bukan tebakan: tambah kata kunci baru hanya
   dengan contoh judul nyata. */
export const ROOM_KEYWORDS = {
  'studio-konten': ['konten', 'reel', 'carousel', 'video', 'caption',
    'posting', 'thumbnail', 'smar', 'shorts', 'tiktok'],
  'war-room': ['audit keamanan', 'bounty', 'pentest', 'security',
    'shopify', 'hackerone', 'bugcrowd', 'trading', 'crypto',
    'backtest', 'binance', 'threat', 'ospek', 'nginx', 'mcp'],
  perpustakaan: ['audit', 'riset', 'research', 'baca', 'scouting',
    'analisis', 'analytics', 'laporan', 'studi', 'lead', 'intel',
    'evaluasi', 'review', 'dokumentasi'],
};

/* Ruangan baru dari judul tugas aktif (null bila tidak cocok).
   Urutan = prioritas first-match. Murni; judul null/kosong -> null. */
export function roomForTask(title) {
  const t = lower(title);
  if (!t) return null;
  for (const roomId of ['studio-konten', 'war-room', 'perpustakaan']) {
    if (ROOM_KEYWORDS[roomId].some((k) => t.includes(k))) return roomId;
  }
  return null;
}

/* Pemetaan ruang deterministik (§5.2 + ruangan baru 0.4.9),
   urutan prioritas:
   1. rangga -> Kantor Rangga (selalu)
   2. membalas @mention <15 mnt -> Ruang rapat
   3. tugas aktif bertema konten -> Studio Konten
   4. tugas aktif bertema security/bounty/trading -> War Room
   5. tugas aktif bertema riset/baca -> Perpustakaan
   6. tugas aktif + aktivitas <1 jam -> Ruang kerja
   7. aktivitas <15 mnt tanpa tugas aktif -> Lounge
      (ADAPTASI JUJUR: read_state per agen TIDAK terekspos API
      board — tidak ada endpoint yang mengembalikan last_seen_at
      agen lain. Aturan 7 spek ("read receipt <15 mnt") di sini
      memakai proksi aktivitas teramati terakhir <15 mnt: pesan /
      tugas / file / audit. Jadi agen yang baru posting pesan pun
      masuk Lounge bila tanpa tugas aktif — Lounge adalah ruang
      sosial, bukan klaim "sedang membaca".)
   8. tanpa aktivitas 1-2 jam -> Pantry
   9. >2 jam / tanpa sinyal -> Taman
   Aturan 3-5 TIDAK memakai batas umur: status tugas 'aktif' di
   board adalah sinyalnya (tugas basi tetap bertema — lihat
   staleApi 'Audit lead' di tes: tetap Perpustakaan, glyph Z).
   HOME BASE OTO (21 Nov 2026, perintah Rangga 17:09 WIB:
   "tugas lo monitoring masa jauh dari workspace"). Blok
   `if (name === 'oto')` di bawah mengesampingkan aturan 2-7
   KHUSUS buat Oto: rapat HANYA bila @all nyata (<15 mnt,
   s.allMeeting — dihitung buildRoomState khusus buat cabang ini;
   view-model lama tidak punya cabang @all sama sekali, dan agen
   lain tetap tidak membacanya); tugas aktif apa pun temanya ->
   Ruang Kerja (judul tugas monitoring Oto mengandung 'baca' yang
   tanpa ini melemparnya ke Perpustakaan via roomForTask); idle
   segar <15 mnt tanpa tugas -> Ruang Kerja (bukan Lounge).
   Idle 15 mnt-2 jam -> Pantry, >2 jam -> Taman tetap berlaku
   buat Oto. Agen lain tidak masuk blok itu — perilaku mereka
   tidak berubah. */
export function resolveRoom(name, s, nowMs) {
  const age = s.lastActiveMs > 0 ? nowMs - s.lastActiveMs : Infinity;
  if (name === 'rangga') return 'kantor-rangga';
  /* HOME BASE OTO (CEO) — perintah Rangga 21 Nov 2026 17:09 WIB:
     "tugas lo monitoring masa jauh dari workspace". Oto default di
     Ruang Kerja; ke Ruang Rapat HANYA saat rapat nyata (@all).
     - @all <15 mnt -> rapat (rapat nyata; satu-satunya jalan Oto
       ke rapat — membalas @mention biasa BUKAN rapat buat Oto,
       itu rutinitas jawabannya sebagai orchestrator).
     - tugas aktif (apa pun temanya) -> Ruang Kerja: judul tugas
       monitoring Oto mengandung 'baca' yang tanpa pengecualian
       ini melemparnya ke Perpustakaan via roomForTask.
     - idle segar <15 mnt tanpa tugas -> Ruang Kerja (bukan
       Lounge): masih monitoring.
     - idle 15 mnt-2 jam -> Pantry, >2 jam -> Taman: tetap,
       karena itu bukan lagi monitoring (jujur: dia memang pergi).
     Blok ini KHUSUS Oto (name === 'oto'); agen lain tidak masuk
     ke sini dan perilakunya tidak berubah. */
  if (name === 'oto') {
    if (s.allMeeting) return 'ruang-rapat';
    if (s.activeTask) return 'ruang-kerja';
    if (age < MIN_15) return 'ruang-kerja';
    if (age < HOUR_2) return 'pantry';
    return 'taman';
  }
  if (s.replying) return 'ruang-rapat';
  if (s.activeTask) {
    const themed = roomForTask(s.activeTask.title);
    if (themed) return themed;
    if (age < HOUR_1) return 'ruang-kerja';
  }
  if (!s.activeTask && age < MIN_15) return 'lounge';
  if (age < HOUR_2) return 'pantry';
  return 'taman';
}

export function glyphFor(s, nowMs) {
  if (s.recentFile) return 'upload';
  if (s.replying) return 'reply';
  if (s.justCompletedMs && nowMs - s.justCompletedMs <= MIN_15) return 'done';
  /* Tugas aktif yang basi >2 jam = glyph Z (proxy jujur "blocked",
     §5.10), bukan laptop — agennya diam walau tugas masih terbuka. */
  if (s.activeTask && nowMs - s.lastActiveMs <= HOUR_2) return 'work';
  /* Aktivitas <15 mnt tanpa tugas aktif = sedang di board
     (membaca/mengobrol) — buku. Di bawah itu = diam (Z). */
  if (s.lastActiveMs && nowMs - s.lastActiveMs <= MIN_15) return 'read';
  return 'zzz';
}

/* Micro-expression (§5.7): HANYA ke keadaan nyata — fokus (tugas
   aktif), senyum (baru selesai <15 mnt), netral (tidak ada
   keduanya). Tanpa wajah blocked, tanpa emosi ditebak. */
export function faceFor(s, nowMs) {
  if (s.activeTask) return 'fokus';
  if (s.justCompletedMs && nowMs - s.justCompletedMs <= MIN_15) return 'senyum';
  return 'netral';
}

/* Bagi slot meja di tiap ruangan secara deterministik (urut
   ROOM_ORDER). Bila agen melebihi slot, sisanya berdiri di dekat
   pintu ruangan (overflow) — tidak ada dua agen di satu slot. */
export function assignSlots(agentStates) {
  const byRoom = {};
  for (const st of agentStates) {
    (byRoom[st.room] = byRoom[st.room] || []).push(st);
  }
  const out = {};
  for (const roomId of Object.keys(byRoom)) {
    const room = ROOMS[roomId];
    const list = byRoom[roomId].slice().sort(
      (a, b) => ROOM_ORDER.indexOf(a.name) - ROOM_ORDER.indexOf(b.name));
    list.forEach((st, i) => {
      if (i < room.slots.length) {
        out[st.name] = { x: room.slots[i].x, z: room.slots[i].z, rot: room.slots[i].rot };
      } else {
        const k = i - room.slots.length;
        out[st.name] = { x: room.door.x + ((k % 3) - 1) * 0.9, z: GANG_Z - 0.6, rot: 0 };
      }
    });
  }
  return out;
}

/* Slot meja (UPGRADE 11/10, §5.11 + denah besar 0.4.9):
   slot dengan flag `desk: true` di ROOMS — semua 9 slot
   'ruang-kerja' (grid 3x3, spasi x 6 / z 4), slot pertama
   'kantor-rangga' {x:-18, z:-11}, slot pertama 'studio-konten'
   {x:13.5, z:-11}, slot pertama 'perpustakaan' {x:17.5, z:4.5}.
   Di sanalah kursi + laptop/meja berada, jadi agen di slot itu
   DUDUK. Slot lain (lounge/pantry/taman/ruang-rapat/war-room/
   slot kedua kantor-rangga/overflow dekat pintu) = berdiri.
   Toleransi 0.01 (pembulatan assignSlots/planWalk). */
export function isDeskSlot(roomId, slot) {
  if (!slot || typeof slot.x !== 'number' || typeof slot.z !== 'number') return false;
  if (!ROOMS[roomId]) return false;
  const close = (a, b) => Math.abs(a.x - b.x) <= 0.01 && Math.abs(a.z - b.z) <= 0.01;
  return ROOMS[roomId].slots.some((s) => s.desk && close(s, slot));
}

/* Aktivitas idle (UPGRADE 11/10, §5.11) — HANYA dari keadaan
   nyata: 'coffee' = di pantry tanpa tugas aktif; 'phone' = di
   meja kerja tapi tugasnya basi atau tanpa tugas aktif (scroll HP,
   bukan mengetik — animasi mengetik dilarang spek); selain itu
   null. Dipisah jadi fungsi murni supaya aturan ini bisa diuji
   langsung: lewat buildRoomState, cabang 'phone' tidak terjangkau
   karena resolveRoom hanya menaruh agen bertugas segar (<1 jam)
   di ruang-kerja (lihat NOTES.md worker A). */
export function activityFor(room, hasActiveTask, stale) {
  if (room === 'pantry' && !hasActiveTask) return 'coffee';
  if (room === 'ruang-kerja' && (stale || !hasActiveTask)) return 'phone';
  return null;
}

/* Pilih bubble yang tampil (UPGRADE 11/10, §5.12): maks `max`
   entri, ucapan (speech) dulu lalu status, masing-masing terbaru
   dulu (ts desc). candidates = [{kind:'speech'|'status', name,
   ts}] — ts = milidetik recency (speech = waktu pesan, status =
   lastActiveMs). Murni: array masuk tidak diubah. */
export function selectVisibleBubbles(candidates, max = 3) {
  const n = Math.max(0, max == null ? 3 : max);
  const list = (candidates || []).slice();
  const speech = list.filter((c) => c && c.kind === 'speech')
    .sort((a, b) => b.ts - a.ts);
  const status = list.filter((c) => c && c.kind === 'status')
    .sort((a, b) => b.ts - a.ts);
  return speech.concat(status).slice(0, n);
}

/* Agen aktif buat plumbob (UPGRADE 11/10, §5.12): lastActiveMs
   terbesar, KECUALI 'rangga' (dia sudah punya bintang volt).
   Seri → paling awal di ROOM_ORDER. Tidak ada lastActiveMs>0 →
   null. Murni; urutan array masuk tidak memengaruhi hasil. */
export function activeAgentName(agents) {
  const byName = {};
  for (const a of agents || []) {
    if (a && a.name) byName[a.name] = a;
  }
  let best = null;
  for (const name of ROOM_ORDER) {
    if (name === 'rangga') continue;
    const a = byName[name];
    if (!a) continue;
    const ms = a.lastActiveMs || 0;
    if (ms <= 0) continue;
    if (!best || ms > best.lastActiveMs) best = a;
  }
  return best ? best.name : null;
}

/* Jalur jalan antar ruangan (§5.6 + denah besar 0.4.9): dari
   posisi lama ke posisi baru LEWAT gang (z = GANG_Z), bukan
   menembus furnitur. Dalam satu ruangan yang sama: langsung
   (tanpa waypoint). Titik berurutan yang sama digabung.
   Rute antar ruangan (L-shape, data-driven dari ROOMS):
   (1) geser vertikal pendek ke baris jalan (from.z + legDy
   ruangan asal — ruang bermeja: -1 supaya tidak menyerempet
   kursi di baris slot); (2) lateral ke lane ruangan asal
   (koridor bebas furnitur; slot boleh punya lane sendiri —
   rapat/war-room); (3) vertikal di lane ke gang; (4) lateral
   di gang ke lane ruangan tujuan; (5) vertikal di lane ke
   baris jalan tujuan; (6) lateral ke slot tujuan. Semua
   waypoint dihitung dari data ROOMS — tanpa angka hardcode.
   CATATAN JUJUR (dulu): planWalk 0.4.8 langsung menarik garis
   dari slot ke gang di x yang sama — di ruang-kerja lama itu
   menembus 3 meja + kursi (slot (-11,5.9) ke gang melewati
   meja z=4.5/2.0/-0.5). Rute lane ini memperbaikinya;
   verifikasi tabrakan ada di test-fragment-viewmodel-v2.py
   (semua pasangan slot antar ruangan vs kotak furnitur). */
function slotLane(room, pt) {
  if (!room || !room.slots) return room && room.lane;
  for (const s of room.slots) {
    if (Math.abs(s.x - pt.x) <= 0.01 && Math.abs(s.z - pt.z) <= 0.01) {
      return s.lane !== undefined ? s.lane : room.lane;
    }
  }
  return room.lane;
}

export function planWalk(from, to, fromRoom, toRoom) {
  const pts = [];
  const push = (p) => {
    const last = pts[pts.length - 1];
    if (!last || Math.hypot(p.x - last.x, p.z - last.z) > 0.01) {
      pts.push({ x: Math.round(p.x * 100) / 100, z: Math.round(p.z * 100) / 100 });
    }
  };
  if (fromRoom === toRoom) {
    push(to);
    return pts;
  }
  const rf = ROOMS[fromRoom] || {};
  const rt = ROOMS[toRoom] || {};
  const laneF = slotLane(rf, from);
  const laneT = slotLane(rt, to);
  const legF = from.z + (rf.legDy || 0);
  const legT = to.z + (rt.legDy || 0);
  push({ x: from.x, z: legF });
  push({ x: laneF, z: legF });
  push({ x: laneF, z: GANG_Z });
  push({ x: laneT, z: GANG_Z });
  push({ x: laneT, z: legT });
  push({ x: to.x, z: legT });
  push(to);
  return pts;
}

/* Satu panggilan API board -> keadaan ruangan lengkap.
   api = { agents, messages, tasks, files, audit, threads,
           activity, self, isExample } — semua opsional kecuali
   yang dipakai; field yang hilang = "tidak ada sinyal", bukan
   ditebak. nowMs = Date.now() (diinjeksikan supaya bisa diuji). */
export function buildRoomState(api, nowMs) {
  const now = nowMs;
  const messages = (api.messages || []).filter((m) => !m.deleted)
    /* Jangan andalkan urutan API: urutkan menaik supaya "terakhir"
       selalu = elemen terakhir (per agen + global). */
    .sort((a, b) => ts(a.created_at) - ts(b.created_at));
  const tasks = api.tasks || [];
  const files = api.files || [];
  const audit = api.audit || [];
  const byId = {};
  for (const m of messages) byId[m.id] = m;

  /* Meeting @all (khusus home-base Oto — lihat resolveRoom):
     pesan apa pun yang me-mention 'all' <15 mnt. Dihitung di sini
     supaya Oto bisa ikut rapat nyata; HANYA cabang Oto yang
     membaca s.allMeeting — agen lain tidak terpengaruh (di
     view-model lama tidak ada cabang @all sama sekali). */
  const allMeeting = messages.some(
    (m) => now - ts(m.created_at) <= MIN_15
      && (m.mentions || []).map((x) => lower(x)).includes('all'));

  const agents = [];
  for (const name of ROOM_ORDER) {
    const myMsgs = messages.filter((m) => lower(m.author) === name);
    const lastMsg = myMsgs.length ? myMsgs[myMsgs.length - 1] : null;
    const lastMsgMs = lastMsg ? ts(lastMsg.created_at) : 0;
    const myTasks = tasks.filter((t) => lower(t.assignee) === name);
    const activeList = myTasks
      .filter((t) => ACTIVE_STATUSES.includes(t.status))
      .sort((a, b) => ts(b.updated_at || b.created_at) - ts(a.updated_at || a.created_at));
    const activeTask = activeList.length ? activeList[0] : null;
    const openCount = activeList.length;
    const completedList = myTasks
      .filter((t) => t.status === 'completed')
      .sort((a, b) => ts(b.updated_at || b.created_at) - ts(a.updated_at || a.created_at));
    const justCompletedMs = completedList.length
      ? ts(completedList[0].updated_at || completedList[0].created_at) : 0;
    const lastTaskMs = Math.max(0, ...myTasks.map((t) => ts(t.updated_at || t.created_at)));
    const myFiles = files.filter((f) => lower(f.uploaded_by) === name);
    const lastFileMs = Math.max(0, ...myFiles.map((f) => ts(f.created_at)));
    const recentFile = myFiles
      .filter((f) => now - ts(f.created_at) <= MIN_15)
      .sort((a, b) => ts(b.created_at) - ts(a.created_at))[0] || null;
    const lastAuditMs = Math.max(0, ...audit
      .filter((e) => lower(e.agen) === name).map((e) => ts(e.waktu)));
    const lastActiveMs = Math.max(lastMsgMs, lastTaskMs, lastFileMs, lastAuditMs);

    let replying = false;
    if (lastMsg && lastMsg.reply_to && now - lastMsgMs <= MIN_15) {
      const parent = byId[lastMsg.reply_to];
      if (parent && (parent.mentions || []).map((m) => lower(m)).includes(name)) {
        replying = true;
      }
    }

    const partial = { activeTask, lastActiveMs, lastMsgMs, replying, allMeeting };
    const room = resolveRoom(name, partial, now);
    const st = {
      name,
      label: KNOWN_AGENTS[name].label,
      role: KNOWN_AGENTS[name].role,
      color: KNOWN_AGENTS[name].color,
      room,
      activeTask: activeTask
        ? { id: activeTask.id, title: activeTask.title, status: activeTask.status } : null,
      openCount,
      justCompletedMs,
      recentFile: recentFile
        ? { id: recentFile.id, name: recentFile.name } : null,
      replying,
      lastActiveMs,
      lastActiveLabel: hhmm(lastActiveMs),
      /* Bubble status persisten (§5.3): judul tugas aktif maks 40
         karakter; null bila tanpa tugas aktif. Redup bila basi
         >2 jam (tugas aktif + tanpa aktivitas >2 jam = proxy
         jujur "blocked", §5.10: jangan ditebak). */
      statusText: activeTask ? 'Mengerjakan: ' + trunc(activeTask.title, 40) : null,
      stale: !!activeTask && now - lastActiveMs > HOUR_2,
      /* Ucapan event (§5.3): 60 karakter pertama pesan terakhir
         + jam. Renderer menampilkannya 15 detik saat pesan baru
         terdeteksi (bukan loop). */
      speech: lastMsg && now - lastMsgMs <= MIN_15
        ? { id: lastMsg.id, text: trunc(lastMsg.body, 60), hhmm: hhmm(lastMsgMs) } : null,
      lastMessage: lastMsg
        ? { id: lastMsg.id, thread_id: lastMsg.thread_id, createdAtMs: lastMsgMs } : null,
      lastTask: myTasks.length
        ? myTasks.slice().sort((a, b) => ts(b.updated_at || b.created_at) - ts(a.updated_at || a.created_at))[0] : null,
    };
    st.glyph = glyphFor(st, now);
    st.face = faceFor(st, now);
    agents.push(st);
  }

  const slots = assignSlots(agents);
  for (const st of agents) {
    st.slot = slots[st.name];
    /* UPGRADE 11/10: duduk bila di slot meja; aktivitas idle
       hanya dari keadaan nyata (lihat activityFor). */
    st.sitting = isDeskSlot(st.room, st.slot);
    st.activity = activityFor(st.room, !!st.activeTask, st.stale);
  }

  /* Papan tugas dinding (§5.5): 3 tugas terbuka terbaru lintas tim. */
  const openTasks = tasks
    .filter((t) => ACTIVE_STATUSES.includes(t.status))
    .sort((a, b) => ts(b.updated_at || b.created_at) - ts(a.updated_at || a.created_at))
    .slice(0, 3)
    .map((t) => ({ id: t.id, title: trunc(t.title, 40), assignee: t.assignee || '—' }));

  /* TV Lounge: pesan board terbaru (data nyata). */
  const latestMsg = messages.length ? messages[messages.length - 1] : null;
  const tv = latestMsg
    ? { text: trunc(latestMsg.body, 60), author: latestMsg.author, hhmm: hhmm(ts(latestMsg.created_at)) }
    : null;

  /* Garis @mention (§5.4.1): pesan <15 mnt yang me-mention agen
     dikenal (dari field mentions server, bukan tebak dari teks). */
  const mentionLines = [];
  const seenMention = new Set();
  for (const m of messages) {
    if (now - ts(m.created_at) > MIN_15) continue;
    for (const to of (m.mentions || []).map((x) => lower(x))) {
      if (!KNOWN_AGENTS[to] || lower(m.author) === to) continue;
      const key = lower(m.author) + '>' + to;
      if (seenMention.has(key)) continue;
      seenMention.add(key);
      mentionLines.push({ from: lower(m.author), to, messageId: m.id });
    }
  }

  /* Busur serah terima (§5.4.2): audit task_update/task_create
     <15 mnt yang mengubah assignee (ringkasan "assignee=X") oleh
     agen lain. Pemberi = agen audit, penerima = assignee baru. */
  const handovers = [];
  for (const e of audit) {
    if (!['task_update', 'task_create'].includes(e.aksi)) continue;
    if (now - ts(e.waktu) > MIN_15) continue;
    const m = /assignee=([A-Za-z0-9_-]+)/.exec(e.ringkasan || '');
    if (!m) continue;
    const to = lower(m[1]);
    const from = lower(e.agen);
    if (!KNOWN_AGENTS[to] || !KNOWN_AGENTS[from] || from === to) continue;
    handovers.push({ from, to, taskId: e.id_objek });
  }

  /* Kedip rak file (§5.4.4): file terbaru <15 mnt. */
  const latestFile = files.length
    ? files.slice().sort((a, b) => ts(b.created_at) - ts(a.created_at))[0] : null;
  const fileFlash = latestFile && now - ts(latestFile.created_at) <= MIN_15
    ? { id: latestFile.id, name: latestFile.name, uploaded_by: latestFile.uploaded_by } : null;

  const rangga = agents.find((a) => a.name === 'rangga');
  const bossActive = !!(rangga && rangga.lastMessage
    && now - rangga.lastMessage.createdAtMs <= MIN_15);

  /* Lencana belum dibaca (§5.8): HANYA untuk agen yang login
     (api.self) — activity mengembalikan hitungan untuk
     pemanggil saja; read_state agen lain tidak terekspos API,
     jadi agen lain mendapat null (bukan angka karangan). */
  const unreadSelf = api.activity && api.activity.counts
    ? api.activity.counts.messages : null;

  return {
    nowMs: now,
    isExample: !!api.isExample,
    self: api.self || null,
    agents,
    taskBoard: openTasks,
    tv,
    whiteboardThread: latestMsg ? latestMsg.thread_id : 'blackboard-umum',
    threadMessageCount: latestMsg
      ? messages.filter((m) => (m.thread_id || 'blackboard-umum') === latestMsg.thread_id).length : 0,
    /* Data mentah buat panel dinding (bukan state turunan): 5 pesan
       + 4 file terbaru, apa adanya dari API. */
    recentMessages: messages.slice(-5).map((m) => ({ author: m.author, body: m.body })),
    recentFiles: files.slice().sort((a, b) => ts(b.created_at) - ts(a.created_at)).slice(0, 4)
      .map((f) => ({ name: f.name, size_bytes: f.size_bytes || 0 })),
    mentionLines,
    handovers,
    fileFlash,
    bossActive,
    unreadSelf,
  };
}

/* Data contoh berlabel buat mode ?preview=1 (tanpa login, tanpa
   polling). Semua created_at relatif terhadap nowMs supaya keadaan
   (ruang, glyph, ucapan) stabil di screenshot apa pun jamnya.
   Dipakai HANYA di mode preview; renderer + status bar wajib
   menampilkan label "contoh". BUKAN data live. */
export function fixtureData(nowMs) {
  const iso = (minsAgo) => new Date(nowMs - minsAgo * 60 * 1000).toISOString();
  return {
    isExample: true,
    self: null,
    agents: Object.keys(KNOWN_AGENTS),
    messages: [
      { id: 'msg_fx_neto', author: 'neto', thread_id: 'blackboard-umum', type: 'chat', body: '@zeto scope Shopify sudah dikunci?', mentions: ['zeto'], created_at: iso(10) },
      { id: 'msg_fx_oto', author: 'oto', thread_id: 'blackboard-umum', type: 'chat', body: '@beto tolong cek GLB oto v2 sudah masuk repo', mentions: ['beto'], created_at: iso(8) },
      { id: 'msg_fx_zeto', author: 'zeto', thread_id: 'blackboard-umum', type: 'chat', body: 'Sudah dikunci — 20 aset, hanya uji toko sendiri', mentions: [], reply_to: 'msg_fx_neto', created_at: iso(6) },
      { id: 'msg_fx_beto', author: 'beto', thread_id: 'blackboard-umum', type: 'chat', body: 'GLB 8/8 terverifikasi, mulai build 3D', mentions: [], created_at: iso(12) },
      { id: 'msg_fx_geto', author: 'geto', thread_id: 'blackboard-umum', type: 'chat', body: 'Siap menutupi lane kosong', mentions: [], created_at: iso(90) },
      { id: 'msg_fx_ceto', author: 'ceto', thread_id: 'blackboard-umum', type: 'chat', body: 'Audit lead IG selesai, daftar dikirim ke Oto', mentions: [], created_at: iso(150) },
      { id: 'msg_fx_rangga', author: 'rangga', thread_id: 'blackboard-umum', type: 'chat', body: 'Gaspol — spek 3D disetujui, lanjut build', mentions: [], created_at: iso(3) },
    ],
    tasks: [
      { id: 'task_fx_oto', title: 'Virtual Office 3D build', status: 'working', assignee: 'oto', priority: 'high', created_at: iso(300), updated_at: iso(2) },
      { id: 'task_fx_beto', title: 'Room 3D: scene + bubble', status: 'working', assignee: 'beto', priority: 'high', created_at: iso(300), updated_at: iso(2) },
      { id: 'task_fx_leto', title: 'Audit tugas terbuka di board', status: 'completed', assignee: 'leto', priority: 'normal', created_at: iso(300), updated_at: iso(5) },
      { id: 'task_fx_geto', title: 'Crypto scouting: 3 peluang testnet', status: 'completed', assignee: 'geto', priority: 'normal', created_at: iso(300), updated_at: iso(90) },
      { id: 'task_fx_ceto', title: 'Audit lead IG & Threads', status: 'working', assignee: 'ceto', priority: 'normal', created_at: iso(300), updated_at: iso(150) },
    ],
    files: [
      { id: 'file_fx_beto', name: 'room3d-preview.png', size_bytes: 123456, uploaded_by: 'beto', created_at: iso(4) },
      { id: 'file_fx_oto', name: 'synthesis-discussion-m3.md', size_bytes: 12345, uploaded_by: 'oto', created_at: iso(30) },
    ],
    audit: [
      { waktu: iso(7), agen: 'oto', aksi: 'task_update', jenis_objek: 'task', id_objek: 'task_fx_beto', ringkasan: 'assignee=beto, status=working' },
      { waktu: iso(5), agen: 'leto', aksi: 'task_update', jenis_objek: 'task', id_objek: 'task_fx_leto', ringkasan: 'status=completed' },
      { waktu: iso(4), agen: 'beto', aksi: 'file_upload', jenis_objek: 'file', id_objek: 'file_fx_beto', ringkasan: 'file_upload room3d-preview.png' },
    ],
    threads: [
      { thread_id: 'blackboard-umum', message_count: 58, unread: 0 },
    ],
    activity: { counts: { messages: 0, tasks: 0, files: 0 } },
  };
}
/* ROOM-VIEWMODEL-END */
