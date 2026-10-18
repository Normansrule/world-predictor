// World Predictor service worker: the app works offline after one visit.
// App files are served cache-first; the data file is network-first so new forecasts show up.
const CACHE = "world-predictor-v1";
const SHELL = ["./", "index.html", "manifest.webmanifest", "assets/icon.svg", "assets/banner-light.svg", "assets/banner-dark.svg",
  "app/", "app/index.html", "app/css/app.css", "app/js/charts.js", "app/js/app.js", "app/data/data.js"];

self.addEventListener("install", (e) => e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())));
self.addEventListener("activate", (e) => e.waitUntil(
  caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim())));
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  if (url.pathname.endsWith("/data/data.js")) {
    e.respondWith(fetch(e.request).then((r) => { const copy = r.clone(); caches.open(CACHE).then((c) => c.put(e.request, copy)); return r; })
      .catch(() => caches.match(e.request)));
    return;
  }
  e.respondWith(caches.match(e.request).then((hit) => hit || fetch(e.request)));
});
