/* neugi.com - viewer loader.
   Tries to mount the interactive 3D office (office/room-showcase.js + office/snapshot.json).
   If either is missing, the static roster fallback already in the page stays visible.
   No network calls to any live service. No tokens. Read-only. */
(function () {
  "use strict";

  function basePath() {
    // index.html and kantor.html both live at site root, so office/ is a sibling.
    return "office/";
  }

  function mount() {
    var slot = document.getElementById("office-viewer");
    if (!slot) return;
    var fallback = slot.querySelector("[data-fallback]");
    var base = basePath();

    fetch(base + "snapshot.json", { cache: "no-store" })
      .then(function (res) {
        if (!res.ok) throw new Error("snapshot missing: " + res.status);
        return res.json();
      })
      .then(function (snapshot) {
        var script = document.createElement("script");
        script.src = base + "room-showcase.js";
        script.onload = function () {
          if (window.__neugiShowcase && typeof window.__neugiShowcase.mount === "function") {
            if (fallback) fallback.hidden = true;
            window.__neugiShowcase.mount(slot, snapshot);
          }
        };
        script.onerror = function () {
          /* viewer JS not ready yet; fallback stays visible */
        };
        document.head.appendChild(script);
      })
      .catch(function () {
        /* snapshot not published yet; fallback roster stays visible */
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})();
