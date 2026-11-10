// Offline mode. Three ways to read World Predictor without a connection:
//  1. The web app (GitHub Pages or `psychohistory app`): after one visit a service worker keeps every
//     app file and the newest data, so it opens with no connection and says which forecasts it shows.
//  2. The offline copy: the whole app and its data in one HTML file (world-predictor-offline.html),
//     saved from the ? sheet and opened by double-click. window.WP_OFFLINE marks it.
//  3. `psychohistory offline`: the same file built from your own results.
// Only the World terminal's live headlines need the network; everything else is in the data file.
(function () {
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const COPY = window.WP_OFFLINE || null;                      // set only inside the one-file copy
  const WEB = location.protocol.startsWith("http");
  const D = window.WP_DATA || { meta: {} };
  const sealed = () => ((D.outlook || [])[0] || {}).made_on || D.meta.generated || "";
  let cached = false;                                          // the service worker holds the app

  function toast(html, ms = 4200) {
    const t = $("toast"); if (!t) return;
    t.innerHTML = html; t.classList.add("on");
    clearTimeout(toast.t); if (ms) toast.t = setTimeout(() => t.classList.remove("on"), ms);
  }

  // The pill in the status bar: hidden while online on the web, "Offline" without a connection,
  // "Offline copy" inside the one-file copy.
  function pill() {
    const b = $("net"); if (!b) return;
    const off = !navigator.onLine;
    b.hidden = !(COPY || off);
    b.classList.toggle("off", off);
    b.querySelector("span").textContent = COPY ? "Offline copy" : "Offline";
    b.title = COPY ? `Built ${COPY.built}; forecasts sealed ${sealed()}` : `No connection: showing forecasts sealed ${sealed()}`;
    document.documentElement.classList.toggle("is-offline", off);
  }

  // The Offline part of the ? sheet: where this copy came from and how to keep one.
  function box() {
    const el = $("offline-box"); if (!el) return;
    const state = COPY
      ? `<p class="ob-state ok"><b>You are in the offline copy.</b> Built ${esc(COPY.built)}, forecasts sealed ${esc(sealed())}. Everything works from this file; live headlines need a connection.</p>
         <p><a class="btn" href="${esc(COPY.web)}" target="_blank" rel="noopener">Open the live app</a> to see newer forecasts, then save a fresh copy there.</p>`
      : `<p class="ob-state ${cached ? "ok" : ""}"><b>${cached ? "Ready offline." : WEB ? "Getting ready for offline use…" : "Opened from a file."}</b>
           ${cached ? "This browser keeps the app and the newest forecasts, so it opens without a connection." : WEB ? "Keep this page open a moment and it will work without a connection next time." : ""}
           Forecasts on screen were sealed ${esc(sealed())}.</p>
         <p><a class="btn" id="save-copy" href="../world-predictor-offline.html" download="world-predictor-offline.html">Save the offline copy</a>
           One HTML file with the whole app and this data. Double-click it on any computer, no internet needed.</p>`;
    if (COPY) document.querySelectorAll("#follow-box [data-web]").forEach((a) => (a.href = COPY.web + a.dataset.web)); // a lone file has no feed next to it
    el.innerHTML = `<h3>Offline</h3>${state}<p class="dim">Your own copy from your own results: <code>psychohistory offline</code>.</p>`;
    const save = $("save-copy");
    if (save && WEB) save.onclick = async (e) => {
      // The local app and Pages both serve it; check before the browser saves an error page.
      try { const r = await fetch(save.href, { method: "HEAD", cache: "no-store" }); if (r.ok) return; } catch (err) { /* offline: try the cache below */ }
      e.preventDefault();
      toast(navigator.onLine ? "This server has no offline copy yet. Run <code>psychohistory offline</code>, or save it from the live app." : "Saving the copy needs a connection once; the app itself already works offline.");
    };
  }

  function register() {
    if (!("serviceWorker" in navigator) || !WEB) return;
    const hadController = !!navigator.serviceWorker.controller;
    navigator.serviceWorker.register("../sw.js").then((reg) => {
      reg.addEventListener("updatefound", () => {
        const w = reg.installing; if (!w) return;
        w.addEventListener("statechange", () => {
          if (w.state !== "activated") return;
          cached = true; box();
          // A returning visitor gets a nudge; a first visit only learns it now works offline.
          if (hadController) toast('A newer version is ready. <button class="btn" data-reload>Reload</button>', 0);
          else toast("Ready offline: this app now opens without a connection.");
        });
      });
      return navigator.serviceWorker.ready;
    }).then(() => caches.keys()).then((keys) => { cached = keys.some((k) => k.startsWith("world-predictor")); box(); }).catch(() => {});
  }

  document.addEventListener("click", (e) => {
    if (e.target.closest && e.target.closest("[data-reload]")) location.reload();
    if (e.target.closest && e.target.closest("#net")) { const h = $("help-btn"); if (h) h.click(); }
  });
  window.addEventListener("offline", () => { pill(); toast(`You are offline. Showing the forecasts sealed ${esc(sealed())}; everything but live headlines still works.`); });
  window.addEventListener("online", () => { pill(); toast("Back online."); });

  pill(); box(); register();
  window.WPOffline = { box, copy: COPY };
})();
