/* neugi.com - hamburger nav toggle.
   Tanpa dependensi. Satu tombol di masthead (mobile ≤820px) membuka
   panel menu di bawah bar header; di desktop nav tetap inline. */
(function () {
  "use strict";
  var btn = document.querySelector(".nav-toggle");
  var masthead = document.querySelector(".masthead");
  var nav = document.getElementById("main-nav");
  if (!btn || !masthead || !nav) return;
  function setOpen(open) {
    masthead.classList.toggle("nav-open", open);
    btn.setAttribute("aria-expanded", open ? "true" : "false");
    btn.setAttribute("aria-label", open ? "Tutup menu" : "Buka menu");
  }
  btn.addEventListener("click", function () {
    setOpen(!masthead.classList.contains("nav-open"));
  });
  nav.addEventListener("click", function (e) {
    if (e.target.closest("a")) setOpen(false);
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") setOpen(false);
  });
})();
