// World Predictor landing page: fills the page with real numbers from app/data/data.js, mounts the
// Lab in the hero and runs the scroll effects. Plain JavaScript, no libraries; everything still reads without it.
(function () {
  const D = window.WP_DATA;
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const $ = (s, root = document) => root.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const pct = (v) => (v === null || v === undefined ? "–" : Math.round(v * 100) + "%");
  const signed = (v) => (v === null || v === undefined ? "–" : Math.abs(v) < 0.0005 ? "0.0%" : (v > 0 ? "+" : "−") + Math.abs(v * 100).toFixed(1) + "%");
  const cls = (v) => (v === null || v === undefined || Math.abs(v) < 0.02 ? "dim" : v > 0 ? "pos" : "neg");

  // Theme toggle shared with the terminal.
  const toggle = $("#theme");
  if (toggle) toggle.addEventListener("click", () => {
    const root = document.documentElement;
    const dark = root.dataset.theme === "dark";
    root.dataset.theme = dark ? "light" : "dark";
    try { localStorage.setItem("wp-theme", root.dataset.theme); } catch (e) {}
  });

  if (D) {
    const model = D.meta.model, name = /^timesfm/.test(model) ? "TimesFM" : model, sc = D.scorecard || {};
    // Tape: every sealed forecast, the chance it ends higher.
    $("#tape").innerHTML = D.outlook.map((o) => {
      const p = o.p_up, c = p === null ? "flat" : p > 0.55 ? "up" : p < 0.45 ? "down" : "flat";
      return `<a href="app/#outlook/${esc(o.id)}" title="${esc(o.title)}"><b>${esc(o.id.replace(/_composite$/, "").replace(/_/g, " ").toUpperCase().slice(0, 12))}</b>` +
        `<span class="${c}">${c === "up" ? "▲" : c === "down" ? "▼" : "■"} ${pct(p)}</span></a>`;
    }).join("");
    $("#hero-facts").innerHTML = [
      [String(D.series.length), "series backtested", D.meta.demo ? "demo data" : "news, markets, technology"],
      [techSkill(D, model, sc), `${name} in technology`, 'less error than "no change"'],
      [String(D.outlook.length), "sealed this week", `scored from ${D.outlook[0] ? D.outlook[0].fan[0][0] : "–"}`],
    ].map(([v, k, s]) => `<div><dt>${k}</dt><dd>${esc(v)}<small>${esc(s)}</small></dd></div>`).join("");
    if (window.WPLab) window.WPLab.render($("#hero-lab"), D, { compact: true, start: "sp500" });
    board(D, model, name);
  }

  // The same number the scoreboard shows, so the hero and the table never disagree.
  function techSkill(D, model, sc) {
    const r = pick(D, "tech", model);
    const v = r ? r.skill : sc.tech ? sc.tech.skill : null;
    return v === null || v === undefined ? "–" : signed(v);
  }

  // One row per area and model: the backtest when it already scored Seldon, else the Lab's board.
  function pick(D, d, m) {
    if (D.domains.some((r) => r.model === "seldon") || !D.lab) { const r = D.domains.find((x) => x.domain === d && x.model === m); return r && { skill: r.skill, inside: r.coverage80 }; }
    return (D.lab.board || []).find((x) => x.domain === d && x.model === m);
  }

  // Scoreboard: TimesFM and Seldon against "no change", one row per area.
  function board(D, model, name) {
    const host = $("#board"); if (!host) return;
    const areas = [["news", "World news", "GDELT attention"], ["markets", "Markets", "stocks, gold, silver, oil"], ["tech", "Technology", "Wikipedia and adoption"]].filter(([d]) => pick(D, d, model));
    if (!areas.length) { host.innerHTML = '<tr><td><div class="empty"><b>No backtest yet.</b>The scoreboard fills in after the first forecast run.</div></td></tr>'; return; }
    const cell = (r, k) => (!r || r[k] === null || r[k] === undefined ? "–" : k === "skill" ? `<span class="${cls(r.skill)}">${signed(r.skill)}</span>` : pct(r[k]));
    host.innerHTML = `<thead><tr><th>Area</th><th class="m"><span class="who" style="--c:var(--tfm)">${esc(name)} skill</span></th><th><span class="who" style="--c:var(--seldon)">Seldon skill</span></th>
      <th class="m">In range · ${esc(name)}</th><th>In range · Seldon</th></tr></thead><tbody>` +
      areas.map(([d, n, sub]) => { const a = pick(D, d, model), b = pick(D, d, "seldon");
        return `<tr><td class="area">${n}<small>${sub}</small></td><td class="m">${cell(a, "skill")}</td><td>${cell(b, "skill")}</td><td class="m">${cell(a, "inside")}</td><td>${cell(b, "inside")}</td></tr>`; }).join("") + "</tbody>";
  }

  // The exploded forecast: browsers without scroll-driven animations get --spread from here.
  const engine = $(".explode");
  if (engine && !reduce && !(window.CSS && CSS.supports("animation-timeline: view()"))) {
    const stage = $(".explode__stage", engine);
    const shape = (p) => (p < 0.1 ? 0 : p < 0.42 ? (p - 0.1) / 0.32 : p < 0.68 ? 1 : p < 0.92 ? 1 - (p - 0.68) / 0.24 : 0);
    let ticking = false;
    const update = () => {
      const r = engine.getBoundingClientRect();
      const p = Math.min(1, Math.max(0, -r.top / Math.max(1, r.height - innerHeight)));
      const s = shape(p);
      stage.style.setProperty("--spread", (s * s * (3 - 2 * s)).toFixed(3));
      ticking = false;
    };
    addEventListener("scroll", () => { if (!ticking) { ticking = true; requestAnimationFrame(update); } }, { passive: true });
    update();
  }

  // The terminal preview tilts flat as it reaches the middle of the screen.
  const preview = $(".preview img");
  if (preview && !reduce) {
    let ticking = false;
    const tilt = () => {
      const r = preview.getBoundingClientRect();
      const k = Math.min(1, Math.max(0, (innerHeight - r.top) / (innerHeight * 0.75)));
      preview.style.setProperty("--tilt", (14 * (1 - k)).toFixed(2) + "deg");
      preview.style.setProperty("--scale", (0.95 + 0.05 * k).toFixed(3));
      ticking = false;
    };
    addEventListener("scroll", () => { if (!ticking) { ticking = true; requestAnimationFrame(tilt); } }, { passive: true });
    tilt();
  }

  if ("serviceWorker" in navigator && location.protocol.startsWith("http")) navigator.serviceWorker.register("sw.js").catch(() => {});
})();
