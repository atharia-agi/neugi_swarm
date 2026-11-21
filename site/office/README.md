# office/ - slot viewer 3D kantor

Folder ini adalah slot untuk viewer kantor 3D interaktif neugi.com.

## Yang masuk ke sini (disiapkan Beto)

- `room-showcase.js` - varian viewer read-only dari room 3D backroom. Harus menyediakan
  `window.__neugiShowcase.mount(slotElement, snapshot)`.
- `snapshot.json` - snapshot posisi agen + judul tugas, bentuk:
  `{ "generated_at": "...", "agents": [{ "id", "name", "role", "color", "room",
  "state": "working|meeting|idle|away", "task": "<=40 karakter atau null" }] }`

## Aturan

- Tidak ada koneksi live ke backroom. Alamat asli backroom tidak boleh muncul di file mana pun di sini.
- Tidak ada teks pesan, token, atau data login di snapshot. Hanya posisi + judul tugas.
- Sampai kedua file di atas ada, halaman home dan kantor menampilkan daftar agen statis
  (fallback bawaan HTML + `assets/viewer.js`).

Status: placeholder. Viewer sedang disiapkan.
