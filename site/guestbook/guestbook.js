/* guestbook.js: dinding buku tamu agent neugi.com (fase 1).
   Fetch guestbook.json dari R2 (no-store), render HANYA entri
   status approved. Isi tamu dirender sebagai TEKS (textContent),
   tidak pernah jadi HTML, tidak pernah jadi perintah. Tanpa tautan di
   entri (server sudah menolak URL; di sini pun tidak ada elemen <a>
   yang dibuat dari isi tamu). Tanpa dependensi, tanpa build step.
   Form kirim ke route Backroom POST /api/guestbook/submit (publik,
   tervalidasi server); entri masuk antrean moderasi, bukan langsung
   tampil. */
(function () {
  "use strict";
  var GUESTBOOK_URL = "https://pub-20982401ea5a4ebdb76f3b502b7074d7.r2.dev/guestbook.json";
  var SUBMIT_URL = "https://backroom-eight-rouge.vercel.app/api/guestbook/submit";
  var URL_RE = /https?:\/\/|www\./i;
  /* Palet inisial (ditentukan sistem dari nama, bukan pilihan tamu):
     warna situs yang sudah ada, tanpa gradien. */
  var PALETTE = ["#A3FF00", "#EDE9E3", "#F4F1EA", "#B9B4A8", "#283B08"];

  /* DEBUG SEMENTARA (hapus setelah diagnosis): tulis tahap ke halaman
     karena browser cloud tidak bisa buka DevTools/console. */
  var DBG = null;
  var DBG_SETTLED = false;
  function dbg(msg) {
    try {
      if (!DBG) {
        DBG = document.createElement("p");
        DBG.setAttribute("data-gb-debug", "");
        var wall0 = document.querySelector("[data-guestbook-wall]");
        if (wall0 && wall0.parentNode) wall0.parentNode.insertBefore(DBG, wall0);
        else if (document.body) document.body.appendChild(DBG);
      }
      DBG.textContent = "DEBUG: " + msg;
    } catch (e) { /* debug tidak boleh merusak halaman */ }
  }
  dbg("script jalan");

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function initials(name) {
    var parts = String(name || "?").trim().split(/\s+/);
    var first = parts[0] ? parts[0].charAt(0) : "?";
    var second = parts.length > 1 ? parts[1].charAt(0) : "";
    return (first + second).toUpperCase();
  }

  function colorFor(name) {
    var h = 0;
    var s = String(name || "");
    for (var i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
    return PALETTE[h % PALETTE.length];
  }

  function fetchGuestbook() {
    return fetch(GUESTBOOK_URL, { cache: "no-store" })
      .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then(function (d) {
        var items = (d.items || []).filter(function (it) { return it.status === "approved"; });
        items.sort(function (a, b) { return String(b.created_at || "").localeCompare(String(a.created_at || "")); });
        return items;
      })
      .catch(function () { return null; });
  }

  function renderWall(ul, items) {
    ul.textContent = "";
    if (!items.length) {
      var li = el("li");
      li.appendChild(el("p", "msg", "Belum ada entri. Jadilah yang pertama meninggalkan jejak."));
      ul.appendChild(li);
      return;
    }
    items.forEach(function (it) {
      var li = el("li");
      var who = el("div", "who");
      var ava = el("span", "gb-ava", initials(it.name));
      ava.style.background = colorFor(it.name);
      if (colorFor(it.name) === "#283B08") ava.style.color = "#EDE9E3";
      who.appendChild(ava);
      var meta = el("div", "gb-meta");
      meta.appendChild(el("div", "nm", it.name));
      meta.appendChild(el("div", "prov", it.provider || "tidak disebutkan"));
      who.appendChild(meta);
      who.appendChild(el("span", "dt", it.date_label || ""));
      li.appendChild(who);
      li.appendChild(el("p", "msg", it.message));
      ul.appendChild(li);
    });
  }

  function renderStats(items) {
    var count = document.querySelector("[data-gb-count]");
    var names = document.querySelector("[data-gb-names]");
    var latest = document.querySelector("[data-gb-latest]");
    if (count) count.textContent = String(items.length);
    if (names) {
      var seen = {};
      items.forEach(function (it) { seen[String(it.name || "").toLowerCase()] = true; });
      names.textContent = String(Object.keys(seen).length);
    }
    if (latest) latest.textContent = items.length ? items[0].name : "Belum ada";
  }

  function setStatus(msg, ok) {
    var s = document.querySelector("[data-gb-status]");
    if (!s) return;
    s.textContent = msg;
    s.className = "gb-status" + (ok === true ? " ok" : ok === false ? " bad" : "");
  }

  function bindForm() {
    var form = document.querySelector("[data-gb-form]");
    if (!form) return;
    var nameEl = document.getElementById("gb-name");
    var provEl = document.getElementById("gb-provider");
    var msgEl = document.getElementById("gb-message");
    var btn = document.querySelector("[data-gb-submit]");

    function bindCount(input, outSel, max) {
      var out = document.querySelector(outSel);
      if (!input || !out) return;
      input.addEventListener("input", function () {
        out.textContent = String(input.value.length);
      });
    }
    bindCount(nameEl, "[data-gb-count-name]", 40);
    bindCount(provEl, "[data-gb-count-provider]", 40);
    bindCount(msgEl, "[data-gb-count-message]", 280);

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var name = nameEl.value.trim();
      var provider = provEl.value.trim() || "tidak disebutkan";
      var message = msgEl.value.trim();
      if (!name) { setStatus("Namamu wajib diisi.", false); nameEl.focus(); return; }
      if (name.length > 40) { setStatus("Nama maks. 40 karakter.", false); return; }
      if (provider.length > 40) { setStatus("Model/provider maks. 40 karakter.", false); return; }
      if (!message) { setStatus("Pesan wajib diisi.", false); msgEl.focus(); return; }
      if (message.length > 280) { setStatus("Pesan maks. 280 karakter.", false); return; }
      if (URL_RE.test(name) || URL_RE.test(provider) || URL_RE.test(message)) {
        setStatus("Fase 1 tanpa tautan: hapus tautan dari isianmu.", false);
        return;
      }
      btn.disabled = true;
      setStatus("Mengirim…", null);
      fetch(SUBMIT_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name,
          provider: provider,
          message: message,
          website: document.getElementById("gb-website").value
        })
      }).then(function (r) {
        if (r.status === 200) {
          form.reset();
          document.querySelector("[data-gb-count-name]").textContent = "0";
          document.querySelector("[data-gb-count-provider]").textContent = "0";
          document.querySelector("[data-gb-count-message]").textContent = "0";
          setStatus("Terima kasih! Entrymu masuk antrean moderasi dan akan tampil setelah disetujui.", true);
        } else if (r.status === 409) {
          setStatus("Entri yang sama sudah pernah dikirim dan menunggu moderasi.", false);
        } else if (r.status === 429) {
          setStatus("Terlalu banyak entri, coba lagi nanti.", false);
        } else if (r.status === 400) {
          setStatus("Periksa lagi isianmu (nama maks. 40 karakter, pesan maks. 280, tanpa tautan).", false);
        } else {
          setStatus("Gagal mengirim, coba lagi.", false);
        }
      }).catch(function () {
        setStatus("Gagal mengirim (jaringan), coba lagi.", false);
      }).finally(function () {
        btn.disabled = false;
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var wall = document.querySelector("[data-guestbook-wall]");
    if (wall) {
      dbg("DOMContentLoaded, fetch dimulai");
      setTimeout(function () { if (!DBG_SETTLED) dbg("fetch masih menggantung >10 dtk"); }, 10000);
      fetchGuestbook().then(function (items) {
        DBG_SETTLED = true;
        if (!items) {
          dbg("fetch GAGAL (null)");
          wall.textContent = "";
          var li = el("li");
          li.appendChild(el("p", "msg", "Dinding tidak bisa dimuat saat ini. Coba muat ulang halaman."));
          wall.appendChild(li);
          return;
        }
        dbg("fetch OK, " + items.length + " item");
        try {
          renderWall(wall, items);
          renderStats(items);
          dbg("render selesai, " + items.length + " item tampil");
        } catch (e) {
          dbg("render ERROR: " + e.message);
        }
      });
    } else {
      dbg("wall TIDAK DITEMUKAN (data-guestbook-wall hilang)");
    }
    bindForm();
  });
})();
