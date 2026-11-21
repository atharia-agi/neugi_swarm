/* neugi.com - viewer loader.
   Tries to mount the interactive 3D office (office/room-showcase.js + office/snapshot.json).
   If either is missing, the static roster fallback already in the page stays visible.
   No network calls to any live service. No tokens. Read-only.
   FIX (showcase Maximum Level, wire homepage): room-showcase.js is an
   ES module — it MUST be loaded with type="module". The old loader used
   a classic <script src>, which fails on the module's `import`
   statements, so the viewer never mounted and both pages kept showing
   the static fallback ("dalam persiapan" / "Viewer interaktif sudah
   live" as a placeholder). mount() is called with proper opts
   ({ snapshotUrl }) into #office-viewer-slot; the fallback is hidden
   with style.display (the `hidden` attribute loses to the
   .viewer-fallback { display: grid } rule). */
(function () {
  "use strict";

  function basePath() {
    // index.html and kantor.html both live at site root, so office/ is a sibling.
    return "office/";
  }

  function mount() {
    var viewer = document.getElementById("office-viewer");
    if (!viewer) return;
    var slot = document.getElementById("office-viewer-slot") || viewer;
    var fallback = viewer.querySelector("[data-fallback]");
    var base = basePath();

    fetch(base + "snapshot.json", { cache: "no-store" })
      .then(function (res) {
        if (!res.ok) throw new Error("snapshot missing: " + res.status);
        return res.json();
      })
      .then(function () {
        var script = document.createElement("script");
        script.type = "module";
        script.src = base + "room-showcase.js";
        script.onload = function () {
          if (window.__neugiShowcase && typeof window.__neugiShowcase.mount === "function") {
            if (fallback) fallback.style.display = "none";
            window.__neugiShowcase.mount(slot, { snapshotUrl: base + "snapshot.json" });
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
