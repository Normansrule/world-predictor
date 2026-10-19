// World Predictor app: reads window.WP_DATA (written by `psychohistory site` / `psychohistory app`)
// and draws every view with the small SVG kit in charts.js. Views render lazily on first visit.
(function () {
  const D = window.WP_DATA;
  const { plot, bars, legend, fmt } = window.WPCharts;
  const $ = (id) => document.getElementById(id);
  const DOMAINS = [["news", "📰", "World news"], ["markets", "📈", "Markets"], ["tech", "🚀", "Technology"]];
  const UNIT = { news: "days", markets: "trading days", tech: "days" };
  const COLORS = ["var(--forecast)", "var(--cat2)", "var(--cat3)", "var(--cat4)"];
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  if (!D) {
    document.querySelector("main").innerHTML = '<div class="empty">No data file found. Run <code>psychohistory site</code> to build it.</div>';
    return;
  }

  // Theme toggle (remembered per browser).
  $("theme").addEventListener("click", () => {
    const root = document.documentElement;
    const dark = root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    root.dataset.theme = dark ? "light" : "dark";
    try { localStorage.setItem("wp-theme", root.dataset.theme); } catch (e) {}
    rendered.clear(); show(current);
  });

  const model = D.meta.model;
  if (D.meta.demo) {
    $("demo").innerHTML = '<div class="demo-banner"><b>Demo data.</b> These charts use made-up series and simple models so you can explore the app. ' +
      "Real TimesFM forecasts replace them after the first weekly run.</div>";
  }
  $("footer").innerHTML = `World Predictor ${esc(D.meta.version)} · model <b>${esc(model)}</b> · data generated ${esc(D.meta.generated)} · ` +
    `<a href="${esc(D.meta.repo)}">source</a> · Maintained by <a href="https://github.com/Normansrule">@Normansrule</a> · Apache-2.0 · Not financial advice.`;
  $("repo-link").href = D.meta.repo;

  // ---------- views ----------
  const views = {
    overview() {
      $("tiles").innerHTML = DOMAINS.map(([d, icon, name]) => {
        const c = D.scorecard[d] || {};
        const has = c.skill !== null && c.skill !== undefined;
        const flat = has && Math.abs(c.skill) < 0.02; // under 2% is noise, the same rule as the report
        const cls = !has || flat ? "none" : c.skill > 0 ? "good" : "bad";
        const big = !has ? "?" : signed(c.skill);
        const cap = !has ? "after the first forecast run" : flat ? "about the same error as the simple guess"
          : c.skill > 0 ? "less error than the simple guess" : "more error than the simple guess";
        const sees = c.edge === null || c.edge === undefined ? "–" : c.edge === 0 ? "no edge" : `about ${c.edge} ${UNIT[d]}`;
        return `<div class="card tile"><div class="name">${icon} ${name}</div><div class="big ${cls}" data-count="${has ? c.skill : ""}">${big}</div>
          <div class="cap">${cap}</div><dl><dt>Sees ahead</dt><dd>${sees}</dd><dt>Right direction</dt><dd>${fmt.pct(c.direction)}</dd>
          <dt>Forecasts scored</dt><dd>${c.forecasts ?? "–"}</dd></dl></div>`;
      }).join("");
      countUp();
      $("plain").innerHTML = "<h2>In plain English</h2>" + (D.headlines.length
        ? "<ul>" + D.headlines.map((h) => `<li>${esc(h)}</li>`).join("") + "</ul>"
        : '<p class="caption">The findings appear after the first forecast run.</p>');
      const models = [...new Set(D.domains.map((r) => r.model))].filter((m) => m !== "naive");
      models.sort((a, b) => (a === model ? -1 : b === model ? 1 : a.localeCompare(b)));
      const groups = DOMAINS.filter(([d]) => D.domains.some((r) => r.domain === d));
      if (!groups.length) { $("skill-chart").innerHTML = '<div class="empty">No backtest yet.</div>'; return; }
      const series = models.slice(0, 4).map((m, i) => ({
        name: m, color: COLORS[i],
        values: groups.map(([d]) => (D.domains.find((r) => r.domain === d && r.model === m) || {}).skill ?? null),
      }));
      bars($("skill-chart"), { groups: groups.map((g) => g[2]), series, yFormat: fmt.pct, label: "Skill by domain" });
      $("skill-legend").innerHTML = ""; legend($("skill-legend"), series);
    },

    replay() {
      const R = D.replay;
      if (!R) { $("replay-chart").innerHTML = '<div class="empty">The replay appears after the first backtest.</div>'; return; }
      $("replay-title").textContent = R.title;
      const slider = $("replay-slider"); slider.max = R.forecasts.length - 1;
      const xDomain = [R.history[0][0], R.history[R.history.length - 1][0]];
      const draw = (i) => {
        const f = R.forecasts[i], origin = Date.parse(f.origin);
        const seen = R.history.filter((p) => Date.parse(p[0]) <= origin);
        const ghosts = R.forecasts.slice(0, i).map((g) => ({ points: g.path.map((p) => [p[0], p[2]]), color: "var(--forecast)", width: 1, opacity: 0.25 }));
        const inside = f.path.filter((p) => p[4] !== null && p[4] >= p[1] && p[4] <= p[3]).length / Math.max(1, f.path.filter((p) => p[4] !== null).length);
        plot($("replay-chart"), {
          x: "date", xDomain, label: "Replay of past forecasts",
          yDomain: padDomain(R.history.map((p) => p[1]).concat(R.forecasts.flatMap((g) => g.path.flatMap((p) => [p[1], p[3]])))),
          bands: [{ points: f.path.map((p) => [p[0], p[1], p[3]]) }],
          lines: [{ points: seen, color: "var(--observed)", name: "seen" }, ...ghosts, { points: f.path.map((p) => [p[0], p[2]]), color: "var(--forecast)", width: 2.5, name: "guess" }],
          dots: [{ points: f.path.map((p) => [p[0], p[4]]), color: "var(--text)", r: 3, name: "actual" }],
          refs: [{ x: f.origin, label: "forecast made" }],
        });
        $("replay-readout").textContent = `${fmt.date(origin)} · ${Math.round(inside * 100)}% of reality inside its range`;
        slider.value = i;
      };
      let timer = null;
      const stop = () => { clearInterval(timer); timer = null; $("replay-play").textContent = "▶ Play"; };
      $("replay-play").onclick = () => {
        if (timer) return stop();
        $("replay-play").textContent = "❚❚ Pause";
        let i = +slider.value >= R.forecasts.length - 1 ? 0 : +slider.value;
        draw(i);
        timer = setInterval(() => { i += 1; if (i >= R.forecasts.length) return stop(); draw(i); }, 1100);
      };
      slider.oninput = () => { stop(); draw(+slider.value); };
      draw(+slider.value || 0);
      $("replay-legend").innerHTML = "";
      legend($("replay-legend"), [{ name: "What it could see", color: "var(--observed)" }, { name: "Its 80% range", color: "var(--forecast)", kind: "band" },
        { name: "Its best guess", color: "var(--forecast)" }, { name: "What really happened", color: "var(--text)", kind: "dot" }]);
    },

    outlook() {
      const items = D.outlook || [];
      if (!items.length) { $("outlook-grid").innerHTML = '<div class="empty">Forecasts appear after the first run of <code>psychohistory predict</code>.</div>'; return; }
      let filter = "all";
      const chips = [["all", "All"], ...DOMAINS.map(([d, icon, name]) => [d, icon + " " + name])];
      $("outlook-filter").innerHTML = chips.map(([k, l]) => `<button class="chip" data-k="${k}" aria-pressed="${k === filter}">${l}</button>`).join("");
      const draw = () => {
        const shown = items.filter((o) => filter === "all" || o.domain === filter);
        $("outlook-grid").innerHTML = shown.map((o, i) => `<div class="card mini"><div class="head"><h3>${esc(o.title)}</h3><span class="pill">${esc(o.domain)}</span></div>
          <div class="odds"><b>${fmt.pct(o.p_up)}</b> chance higher by ${esc(o.target_date)} · best guess <b>${fmt.signedPct(o.change)}</b></div><div id="mini-${i}"></div></div>`).join("");
        shown.forEach((o, i) => plot($("mini-" + i), {
          x: "date", height: 170, left: 44, hover: true, label: o.title,
          bands: [{ points: o.fan.map((p) => [p[0], p[1], p[3]]) }],
          lines: [{ points: o.history, color: "var(--observed)", width: 1.6, name: "value" }, { points: o.fan.map((p) => [p[0], p[2]]), color: "var(--forecast)", name: "guess" }],
          refs: [{ x: o.history[o.history.length - 1][0] }],
        }));
      };
      $("outlook-filter").onclick = (e) => {
        const k = e.target.dataset && e.target.dataset.k; if (!k) return;
        filter = k; [...$("outlook-filter").children].forEach((c) => c.setAttribute("aria-pressed", c.dataset.k === k)); draw();
      };
      draw();
    },

    horizon() {
      const lines = DOMAINS.filter(([d]) => D.horizon.some((r) => r.domain === d)).map(([d, , name], i) => ({
        name, color: COLORS[i], points: D.horizon.filter((r) => r.domain === d).map((r) => [r.step, r.skill]),
      }));
      if (!lines.length) { $("horizon-chart").innerHTML = '<div class="empty">Appears after the first backtest.</div>'; return; }
      plot($("horizon-chart"), { x: "num", lines, xFormat: (v) => (Number.isInteger(v) ? String(v) : ""), refs: [{ y: 0, label: "no better than naive" }], yFormat: fmt.pct, xTitle: "Steps ahead", label: "Skill by steps ahead" });
      $("horizon-legend").innerHTML = ""; legend($("horizon-legend"), lines);
    },

    odds() {
      const dots = DOMAINS.filter(([d]) => D.calibration.some((r) => r.domain === d)).map(([d, , name], i) => ({
        name, color: COLORS[i], r: 6, stroke: "var(--surface)", points: D.calibration.filter((r) => r.domain === d).map((r) => [r.said, r.happened]),
      }));
      if (!dots.length) { $("odds-chart").innerHTML = '<div class="empty">Appears after the first backtest.</div>'; return; }
      plot($("odds-chart"), {
        x: "num", xDomain: [0, 1], yDomain: [0, 1], yFormat: fmt.pct, xFormat: fmt.pct, dots,
        lines: [{ points: [[0, 0], [1, 1]], color: "var(--muted)", width: 1, dash: "3 4", name: "honest" }],
        xTitle: "Chance of rising it gave", label: "Calibration",
      });
      $("odds-legend").innerHTML = ""; legend($("odds-legend"), dots.map((d) => ({ ...d, kind: "dot" })));
    },

    vault() {
      const V = D.vault || [];
      if (!V.length) {
        $("vault-inside").innerHTML = $("vault-brier").innerHTML = '<div class="empty">The vault opens as the first sealed predictions come due.</div>';
        return;
      }
      plot($("vault-inside"), { x: "date", yDomain: [0, 1], yFormat: fmt.pct, lines: [{ points: V.map((r) => [r.date, r.inside80]), color: "var(--accent)", name: "inside" }],
        refs: [{ y: 0.8, label: "target 80%", color: "var(--muted)" }], height: 260 });
      plot($("vault-brier"), { x: "date", yDomain: [0, Math.max(0.4, ...V.map((r) => r.brier || 0))], yFormat: (v) => v.toFixed(2),
        lines: [{ points: V.map((r) => [r.date, r.brier]), color: "var(--accent)", name: "score" }],
        refs: [{ y: 0.25, label: "coin flip", color: "var(--muted)" }], height: 260 });
      const last = V[V.length - 1];
      $("vault-note").textContent = `${last.opened.toLocaleString()} sealed predictions opened so far. ` +
        `${fmt.pct(last.inside80)} landed inside the 80% range; odds score ${last.brier.toFixed(3)} (coin flip 0.250).`;
    },

    crowd() {
      const C = D.crowd, slider = $("crowd-slider"); slider.max = C.sizes.length - 1;
      const t = C.tide.map((_, i) => i);
      const span = Math.max(...C.people[0].map(Math.abs)) * 1.05;
      const draw = (i) => {
        const n = C.sizes[i];
        const people = C.people.slice(0, Math.min(n, 12)).map((p) => ({ points: p.map((v, k) => [t[k], v]), color: "var(--muted)", width: 0.8, opacity: 0.25 }));
        plot($("crowd-chart"), {
          x: "num", yDomain: [-span, span], xFormat: () => "", hover: false, label: "Crowd simulation",
          lines: [...people, { points: C.averages[String(n)].map((v, k) => [t[k], v]), color: "var(--hypo)", width: 2.4 },
            { points: C.tide.map((v, k) => [t[k], v]), color: "var(--text)", width: 2, dash: "6 4" }],
        });
        const share = C.share[String(n)];
        $("crowd-share").textContent = share > 0.99 ? ">99%" : Math.round(share * 100) + "%";
        $("crowd-label").textContent = `predictable · ${n === 1 ? "one person" : "a crowd of " + n.toLocaleString()}`;
      };
      slider.oninput = () => draw(+slider.value);
      draw(+slider.value || 0);
      $("crowd-legend").innerHTML = "";
      legend($("crowd-legend"), [{ name: "Crowd average (simulated)", color: "var(--hypo)" }, { name: "Shared tide (the predictable part)", color: "var(--text)" },
        { name: "Individual people", color: "var(--muted)" }]);
    },

    series() {
      const rows = D.series || [];
      if (!rows.length) { $("series-table").innerHTML = '<tr><td class="empty">Appears after the first backtest.</td></tr>'; return; }
      const cols = [["title", "Series"], ["domain", "Area"], ["scale", "Scale"], ["skill", "Skill"], ["direction", "Right direction"], ["coverage80", "In 80% range"], ["brier", "Odds score"]];
      let key = "skill", dir = -1;
      const draw = () => {
        const sorted = rows.slice().sort((a, b) => ((a[key] ?? -1e9) > (b[key] ?? -1e9) ? 1 : -1) * dir);
        $("series-table").innerHTML = "<thead><tr>" + cols.map(([k, l]) => `<th data-k="${k}">${l}${k === key ? (dir > 0 ? " ▲" : " ▼") : ""}</th>`).join("") + "</tr></thead><tbody>" +
          sorted.map((r) => `<tr><td>${esc(r.title)}</td><td>${esc(r.domain)}</td><td>${esc(r.scale)}</td>` +
            `<td>${fmt.pct(r.skill)}<span class="bar" style="width:${Math.min(60, Math.abs(r.skill || 0) * 300)}px;background:${(r.skill || 0) >= 0 ? "var(--green)" : "var(--coral)"}"></span></td>` +
            `<td>${fmt.pct(r.direction)}</td><td>${fmt.pct(r.coverage80)}</td><td>${r.brier === null ? "–" : r.brier.toFixed(3)}</td></tr>`).join("") + "</tbody>";
      };
      $("series-table").onclick = (e) => { const k = e.target.dataset && e.target.dataset.k; if (!k) return; dir = key === k ? -dir : -1; key = k; draw(); };
      draw();
    },

    // The walkthrough lives in trace.js; it keeps its own state across redraws.
    trace(arg) { if (window.WPTrace) window.WPTrace.render(D, arg); },

    about() {},
  };

  // "+12%", "−3%", or "0%" when it rounds to nothing (no misleading "−0%").
  function signed(v) {
    const r = Math.round(v * 100);
    return r === 0 ? "0%" : (r > 0 ? "+" : "−") + Math.abs(r) + "%";
  }

  function padDomain(values) {
    const v = values.filter((x) => x !== null && isFinite(x)); const lo = Math.min(...v), hi = Math.max(...v), pad = (hi - lo || 1) * 0.05;
    return [lo - pad, hi + pad];
  }

  function countUp() {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    document.querySelectorAll(".tile .big[data-count]").forEach((node) => {
      const target = parseFloat(node.dataset.count); if (!isFinite(target)) return;
      const start = performance.now();
      const step = (now) => {
        const k = Math.min(1, (now - start) / 900), v = target * (1 - Math.pow(1 - k, 3));
        node.textContent = signed(v);
        if (k < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    });
  }

  // ---------- routing ----------
  const rendered = new Set();
  let current = "overview";
  function show(route) {
    let [name, arg] = String(route).split("/");
    if (!views[name]) name = "overview";
    if (name !== "trace" && window.WPTrace) window.WPTrace.stop();
    current = name;
    document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === "view-" + name));
    document.querySelectorAll(".tabs a").forEach((a) => (a.getAttribute("href") === "#" + name ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current")));
    if (!rendered.has(name) || arg) { views[name](arg); rendered.add(name); }
  }
  // Morph between views where the browser supports View Transitions; swap instantly elsewhere.
  window.addEventListener("hashchange", () => {
    const go = () => show(location.hash.slice(1));
    if (document.startViewTransition && !matchMedia("(prefers-reduced-motion: reduce)").matches) document.startViewTransition(go);
    else go();
  });
  // The archive-lamp light on cards follows the pointer.
  document.addEventListener("pointermove", (ev) => {
    const card = ev.target.closest && ev.target.closest(".card");
    if (!card) return;
    const r = card.getBoundingClientRect();
    card.style.setProperty("--mx", ev.clientX - r.left + "px");
    card.style.setProperty("--my", ev.clientY - r.top + "px");
  }, { passive: true });
  let resizeTimer;
  window.addEventListener("resize", () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(() => { rendered.clear(); show(current); }, 200); });
  show(location.hash.slice(1) || "overview");

  // Offline support on the web (service workers need http(s), so this is skipped for file://).
  if ("serviceWorker" in navigator && location.protocol.startsWith("http")) {
    navigator.serviceWorker.register("../sw.js").catch(() => {});
  }
})();
