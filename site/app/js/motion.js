// Motion for World Predictor: a thin layer over anime.js (MIT, vendor/anime.umd.min.js) with plain fallbacks,
// so every animation still lands on its final state when the library is missing or motion is reduced.
// Rules taken from the GSAP and anime.js guides: move only transform and opacity, keep entrances under
// half a second, never animate what the reader is trying to read, and honour prefers-reduced-motion.
(function () {
  const A = () => window.anime || null;
  const calm = () => matchMedia("(prefers-reduced-motion: reduce)").matches || document.documentElement.dataset.motion === "calm";

  // A number that runs up to its value: 0 → 1,284 in about two thirds of a second.
  function count(el, to, opts = {}) {
    if (!el) return;
    const f = opts.format || ((v) => Math.round(v).toLocaleString());
    const from = opts.from ?? 0;
    if (calm() || !A()) { el.textContent = f(to); return; }
    const o = { v: from };
    A().animate(o, { v: to, duration: opts.duration || 700, ease: "outExpo", onUpdate: () => (el.textContent = f(o.v)), onComplete: () => (el.textContent = f(to)) });
  }

  // Children that arrive one after another, rising a few pixels.
  function enter(nodes, opts = {}) {
    const list = Array.from(typeof nodes === "string" ? document.querySelectorAll(nodes) : nodes || []);
    if (!list.length || calm() || !A()) return;
    const a = A();
    a.animate(list, { opacity: [0, 1], translateY: [opts.y ?? 14, 0], scale: [opts.scale ?? 1, 1], duration: opts.duration || 520,
      delay: a.stagger(opts.stagger ?? 45, { start: opts.delay || 0 }), ease: "outExpo" });
  }

  // A short spring pop for a verdict, a badge or a score.
  function pop(el, opts = {}) {
    if (!el || calm() || !A()) return;
    A().animate(el, { scale: [opts.from ?? 0.6, 1], opacity: [0, 1], duration: opts.duration || 620, ease: "outElastic(1, .55)" });
  }

  // A sideways shake for a wrong answer.
  function shake(el) {
    if (!el || calm() || !A()) return;
    A().animate(el, { translateX: [0, -9, 8, -6, 4, -2, 0], duration: 420, ease: "inOutQuad" });
  }

  // A width that grows to a share: XP bars and score bars.
  function grow(el, share, opts = {}) {
    if (!el) return;
    const w = Math.max(0, Math.min(1, share)) * 100 + "%";
    if (calm() || !A()) { el.style.width = w; return; }
    A().animate(el, { width: [opts.from || "0%", w], duration: opts.duration || 900, delay: opts.delay || 0, ease: "outExpo" });
  }

  // Tween any number with a callback (used to rescale charts smoothly).
  function tween(from, to, ms, step, done) {
    if (calm()) { step(to); if (done) done(); return; }
    const t0 = performance.now(), ease = (k) => 1 - Math.pow(1 - k, 4);
    const tick = (now) => {
      const k = Math.min(1, (now - t0) / ms);
      step(from + (to - from) * ease(k));
      if (k < 1) requestAnimationFrame(tick); else if (done) done();
    };
    requestAnimationFrame(tick);
  }

  // Confetti from a point, in the app's own colours, on a canvas laid over a host element.
  function burst(host, x, y, opts = {}) {
    if (!host || calm()) return;
    const c = document.createElement("canvas");
    c.className = "burst";
    const r = host.getBoundingClientRect(), dpr = Math.min(2, devicePixelRatio || 1);
    c.width = r.width * dpr; c.height = r.height * dpr;
    host.appendChild(c);
    const g = c.getContext("2d"); g.scale(dpr, dpr);
    const css = getComputedStyle(document.documentElement);
    const cols = (opts.colors || ["--up", "--you", "--tfm", "--seldon", "--markets", "--politics"]).map((v) => css.getPropertyValue(v).trim() || "#fff");
    const n = opts.count || 70, P = [];
    for (let i = 0; i < n; i++) {
      const a = Math.random() * Math.PI * 2, s = 2 + Math.random() * (opts.power || 7);
      P.push({ x, y, vx: Math.cos(a) * s, vy: Math.sin(a) * s - 3, r: 2 + Math.random() * 3.5, c: cols[i % cols.length], life: 1, spin: Math.random() * 6, w: Math.random() > 0.5 });
    }
    const t0 = performance.now();
    const tick = (now) => {
      g.clearRect(0, 0, r.width, r.height);
      let alive = 0;
      for (const p of P) {
        p.vy += 0.22; p.vx *= 0.985; p.x += p.vx; p.y += p.vy; p.life -= 0.012; p.spin += 0.2;
        if (p.life <= 0) continue;
        alive++;
        g.globalAlpha = Math.max(0, p.life); g.fillStyle = p.c;
        g.save(); g.translate(p.x, p.y); g.rotate(p.spin);
        if (p.w) g.fillRect(-p.r, -p.r / 2.5, p.r * 2, p.r / 1.25); else { g.beginPath(); g.arc(0, 0, p.r / 1.4, 0, 7); g.fill(); }
        g.restore();
      }
      if (alive && now - t0 < 2600) requestAnimationFrame(tick); else c.remove();
    };
    requestAnimationFrame(tick);
  }

  window.WPMotion = { count, enter, pop, shake, grow, tween, burst, calm };
})();
