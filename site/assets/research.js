/* research.js — render riset dari research.json di R2 (CMS).
   Daftar statis di HTML tetap jadi fallback (SEO + tanpa JS + R2 mati):
   daftar HANYA diganti bila fetch JSON berhasil. Item baru (url null)
   dibuka lewat template riset/artikel.html?slug=. Item lama punya url
   file statisnya sendiri dan tetap dibuka dari sana. Hanya item
   status published yang tampil. Tanpa dependensi, tanpa build step. */
(function () {
  var RESEARCH_URL = 'https://pub-20982401ea5a4ebdb76f3b502b7074d7.r2.dev/research.json';
  var MONTHS_SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun',
    'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'];

  function shortDate(iso) {
    var p = iso.split('-');
    return parseInt(p[2], 10) + ' ' + MONTHS_SHORT[parseInt(p[1], 10) - 1] + ' ' + p[0];
  }

  function articleHref(item) {
    return item.url || ('/riset/artikel.html?slug=' + encodeURIComponent(item.slug));
  }

  function fetchResearch() {
    return fetch(RESEARCH_URL, { cache: 'no-store' })
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function (d) {
        return (d.items || []).filter(function (it) { return it.status === 'published'; });
      })
      .catch(function () { return null; });
  }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function renderList(ul, items) {
    var limit = parseInt(ul.getAttribute('data-research-limit') || '0', 10);
    var show = limit > 0 ? items.slice(0, limit) : items;
    ul.textContent = '';
    show.forEach(function (item, i) {
      var li = el('li');
      li.appendChild(el('span', 'num', ('0' + (i + 1)).slice(-2)));
      li.appendChild(el('span', 'date', shortDate(item.date)));
      var div = el('div');
      var h3 = el('h3');
      var a = el('a', null, item.title);
      a.setAttribute('href', articleHref(item));
      h3.appendChild(a);
      div.appendChild(h3);
      div.appendChild(el('p', null, item.dek || ''));
      li.appendChild(div);
      li.appendChild(el('span', 'arrow', '→'));
      ul.appendChild(li);
    });
  }

  function renderArticle() {
    var slug = new URLSearchParams(location.search).get('slug');
    var body = document.querySelector('[data-research-body]');
    if (!slug || !body) return;
    fetchResearch().then(function (items) {
      var notFound = document.querySelector('[data-research-notfound]');
      if (!items) {
        if (notFound) notFound.hidden = false;
        return;
      }
      var item = null;
      items.forEach(function (it) { if (it.slug === slug) item = it; });
      if (!item) {
        if (notFound) notFound.hidden = false;
        return;
      }
      if (item.url) { location.replace(item.url); return; }
      document.title = (item.short_title || item.title) + ' · NEUGI';
      var kicker = document.querySelector('[data-research-kicker]');
      var h1 = document.querySelector('[data-research-title]');
      var meta = document.querySelector('[data-research-date]');
      if (kicker) kicker.textContent = item.kicker || 'Riset';
      if (h1) h1.textContent = item.title;
      if (meta) meta.textContent = item.date_label || shortDate(item.date);
      /* body_html berasal dari JSON yang ditulis Oto sendiri (sama
         tingkat kepercayaannya dengan file statis) — sengaja innerHTML. */
      body.innerHTML = item.body_html;
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    var lists = document.querySelectorAll('[data-research-list]');
    if (lists.length) {
      fetchResearch().then(function (items) {
        if (!items) return; /* gagal: biarkan daftar statis */
        lists.forEach(function (ul) { renderList(ul, items); });
      });
    }
    renderArticle();
  });
})();
