// World Predictor landing page: fills the story with real numbers from app/data/data.js and runs
// the scroll effects. Plain JavaScript, no libraries; everything still reads without it.
(function () {
  const D = window.WP_DATA;
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const $ = (s, root = document) => root.querySelector(s);
  const pct = (v) => (v === null || v === undefined ? "–" : Math.round(v * 100) + "%");
  const signed = (v) => (Math.abs(v) < 0.005 ? "0%" : (v > 0 ? "+" : "−") + Math.abs(Math.round(v * 100)) + "%");

  // Theme toggle shared with the app.
  const toggle = $("#theme");
  if (toggle) toggle.addEventListener("click", () => {
    const root = document.documentElement;
    const dark = root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    root.dataset.theme = dark ? "light" : "dark";
    try { localStorage.setItem("wp-theme", root.dataset.theme); } catch (e) {}
  });

  // Nav sharpens after the first scroll.
  const nav = $(".nav");
  const onScroll = () => nav && nav.classList.toggle("scrolled", scrollY > 8);
  addEventListener("scroll", onScroll, { passive: true }); onScroll();

  // Split the headline into words that rise in turn.
  document.querySelectorAll("[data-split]").forEach((h) => {
    let n = 0;
    const walk = (node) => [...node.childNodes].forEach((c) => {
      if (c.nodeType === 3) {
        const frag = document.createDocumentFragment();
        c.textContent.split(/(\s+)/).forEach((part) => {
          if (!part.trim()) { frag.appendChild(document.createTextNode(part)); return; }
          const w = document.createElement("span"); w.className = "w"; w.style.setProperty("--n", n++); w.textContent = part; frag.appendChild(w);
        });
        c.replaceWith(frag);
      } else walk(c);
    });
    walk(h); h.classList.add("split");
  });

  if (D) {
    const sc = D.scorecard || {};
    const live = $("#live-text");
    if (live) live.textContent = `${D.meta.demo ? "Demo data" : "Last forecast run"} ${D.meta.generated} · ${D.series.length} series · ${D.meta.model}`;
    const set = (id, value, cls) => { const el = $(id); if (el) { el.dataset.count = value; if (cls) el.classList.add(cls); } };
    set("#stat-series", D.series.length);
    set("#stat-news", sc.news && sc.news.skill, "good");
    set("#stat-tech", sc.tech && sc.tech.skill, "good");
    set("#stat-markets", sc.markets && sc.markets.skill);
    set("#stat-sealed", D.outlook.length, "warm");
    hero(D);
    board(D);
  }

  // Count numbers up when they come into view (Web Animations-free: one rAF loop per number).
  function countUp(el) {
    const raw = el.dataset.count; if (raw === undefined || raw === "") return;
    const v = Number(raw), isPct = el.dataset.kind === "pct";
    const show = (x) => (el.textContent = isPct ? signed(x) : Math.round(x).toLocaleString());
    if (reduce) return show(v);
    const t0 = performance.now(), dur = 1400;
    const step = (t) => { const k = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - k, 4); show(v * e); if (k < 1) requestAnimationFrame(step); };
    requestAnimationFrame(step);
  }

  // Reveal sections, count numbers and grow bars as they enter.
  const io = new IntersectionObserver((entries) => entries.forEach((e) => {
    if (!e.isIntersecting) return;
    e.target.classList.add("in");
    e.target.querySelectorAll("[data-count]").forEach(countUp);
    io.unobserve(e.target);
  }), { threshold: 0.2 });
  document.querySelectorAll("[data-reveal], .stats, .board").forEach((el) => io.observe(el));

  // The exploded engine: browsers without scroll-driven animations get --spread from here.
  const engine = $(".explode");
  if (engine && !reduce && !(window.CSS && CSS.supports("animation-timeline: view()"))) {
    const stage = $(".explode__stage", engine);
    const shape = (p) => (p < 0.1 ? 0 : p < 0.42 ? (p - 0.1) / 0.32 : p < 0.68 ? 1 : p < 0.92 ? 1 - (p - 0.68) / 0.24 : 0);
    let ticking = false;
    const update = () => {
      const r = engine.getBoundingClientRect();
      const p = Math.min(1, Math.max(0, -r.top / Math.max(1, r.height - innerHeight)));
      const s = shape(p), eased = s * s * (3 - 2 * s);
      stage.style.setProperty("--spread", eased.toFixed(3));
      ticking = false;
    };
    addEventListener("scroll", () => { if (!ticking) { ticking = true; requestAnimationFrame(update); } }, { passive: true });
    update();
  }

  // App preview tilts flat as it scrolls into the middle of the screen.
  const preview = $(".preview img");
  if (preview && !reduce) {
    let ticking = false;
    const tilt = () => {
      const r = preview.getBoundingClientRect();
      const k = Math.min(1, Math.max(0, (innerHeight - r.top) / (innerHeight * 0.75)));
      preview.style.setProperty("--tilt", (18 * (1 - k)).toFixed(2) + "deg");
      preview.style.setProperty("--scale", (0.94 + 0.06 * k).toFixed(3));
      ticking = false;
    };
    addEventListener("scroll", () => { if (!ticking) { ticking = true; requestAnimationFrame(tilt); } }, { passive: true });
    tilt();
  }

  // Lamp light on cards.
  document.addEventListener("pointermove", (ev) => {
    const card = ev.target.closest && ev.target.closest(".card"); if (!card) return;
    const r = card.getBoundingClientRect();
    card.style.setProperty("--mx", ev.clientX - r.left + "px"); card.style.setProperty("--my", ev.clientY - r.top + "px");
  }, { passive: true });

  // The hero oracle: the newest sealed forecast for the first headline series, drawn with the app's chart kit.
  function hero(D) {
    const box = $("#oracle-chart"); if (!box || !window.WPCharts || !D.outlook.length) return;
    const o = D.outlook[0];
    $("#oracle-title").textContent = o.title;
    $("#oracle-made").textContent = `sealed ${o.made_on} · scored ${o.target_date}`;
    $("#oracle-odds").textContent = pct(o.p_up);
    $("#oracle-cap").textContent = `chance it ends higher by ${o.target_date}. Middle guess ${signed(o.change)}, 80% range ${signed(o.low)} to ${signed(o.high)}.`;
    const history = o.history.slice(-60);
    const now = history[history.length - 1];
    WPCharts.plot(box, {
      x: "date", height: 300, left: 52, label: `${o.title}: history and forecast`,
      bands: [{ points: o.fan.map((f) => [f[0], f[1], f[3]]) }],
      lines: [
        { points: history, color: "var(--text)", width: 2.2, name: "history" },
        { points: [[now[0], now[1]]].concat(o.fan.map((f) => [f[0], f[2]])), color: "var(--orange)", width: 2.4, name: "forecast" },
      ],
      refs: [{ x: now[0], label: "now" }],
    });
  }

  // Scoreboard: TimesFM's skill against the simple guess, one bar per area, zero in the middle.
  function board(D) {
    const host = $("#board"); if (!host) return;
    const areas = [["news", "World news", "GDELT attention"], ["markets", "Markets", "stocks, gold, silver, oil"], ["tech", "Technology", "Wikipedia and adoption"]];
    const rows = areas.map(([d, name, sub]) => {
      const s = D.scorecard[d] && D.scorecard[d].skill;
      if (s === null || s === undefined) return "";
      const lo = -0.5, hi = 0.5, x = (v) => ((Math.max(lo, Math.min(hi, v)) - lo) / (hi - lo)) * 100;
      const left = Math.min(x(0), x(s)), width = Math.abs(x(s) - x(0));
      const flat = Math.abs(s) < 0.02;
      return `<div class="row"><div class="name">${name}<small>${sub}</small></div>
        <div class="track" style="--z:${x(0)}%"><span class="zero"></span><span class="bar ${flat ? "flat" : "model"}" style="left:${left}%;width:${Math.max(0.6, width)}%"></span></div>
        <div class="val" data-count="${s}" data-kind="pct">${signed(s)}</div></div>`;
    });
    host.innerHTML = rows.join("");
  }

  if ("serviceWorker" in navigator && location.protocol.startsWith("http")) navigator.serviceWorker.register("sw.js").catch(() => {});
})();
