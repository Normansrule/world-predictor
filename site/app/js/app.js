// World Predictor terminal: reads window.WP_DATA (written by `psychohistory site` / `psychohistory app`)
// and draws every view with the small SVG kit in charts.js. Views render on first visit and redraw on resize.
(function () {
  const D = window.WP_DATA;
  const { plot, bars, legend, fmt, icon, council, councilBar } = window.WPCharts;
  const $ = (id) => document.getElementById(id);
  const AREAS = [["news", "World news", "GDELT attention"], ["politics", "Politics", "sanctions, tariffs, coups, votes"], ["markets", "Markets", "stocks, gold, silver, oil"], ["tech", "Technology", "Wikipedia and adoption"], ["weather", "Weather and Earth", "temperature, sea ice, quakes"]];
  const AREA = Object.fromEntries(AREAS.map(([d, n]) => [d, n]));
  // Each area has its own colour, always next to its name.
  const hue = (d) => (AREA[d] ? `var(--${d})` : "var(--ink-3)");
  const tag = (d) => `<span class="tag" style="--c:${hue(d)}">${esc(AREA[d] || d)}</span>`;
  const UNIT = { news: "days", politics: "days", markets: "trading days", tech: "days", weather: "days" };
  const VIEWS = ["today", "terminal", "desk", "markets", "monitor", "year", "lab", "studio", "outlook", "trace", "replay", "horizon", "odds", "vault", "crowd", "series", "about"];
  const KEYS = { h: "today", H: "today", w: "terminal", W: "terminal", m: "markets", M: "markets", r: "monitor", R: "monitor", y: "year", Y: "year", 1: "desk", 2: "lab", 3: "studio", 4: "outlook", 5: "trace", 6: "replay", 7: "horizon", 8: "odds", 9: "vault", 0: "series", "?": "about" };
  const NAMES = { today: "Today", terminal: "World terminal", desk: "Desk", markets: "Markets desk", monitor: "Monitor", year: "Year ledger", lab: "Lab", studio: "Forecast Studio", outlook: "Outlook", trace: "Follow a result", replay: "Replay", horizon: "How far ahead", odds: "Honest odds",
    vault: "Time Vault", crowd: "Crowd lab", series: "All series", about: "About" };
  // The workflow's schedule: new forecasts sealed Monday 06:00 UTC, live refresh every weekday 22:30 UTC.
  function nextRun(now = new Date()) {
    for (let k = 0; k < 8 * 48; k++) {
      const t = new Date(Math.ceil(now.getTime() / 18e5) * 18e5 + k * 18e5), d = t.getUTCDay(), hm = t.getUTCHours() * 60 + t.getUTCMinutes();
      if (d === 1 && hm === 360) return "Mon 06:00 UTC · new forecasts";
      if (d >= 1 && d <= 5 && hm === 1350) return t.toLocaleString("en", { weekday: "short", timeZone: "UTC" }) + " 22:30 UTC · refresh";
    }
    return "Mon 06:00 UTC";
  }
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const reduce = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

  if (!D) {
    $("main").innerHTML = '<div class="empty"><b>No data file found.</b>Run <code>psychohistory site</code> to build it, or <code>psychohistory app --demo</code> to explore with demo data.</div>';
    return;
  }
  const model = D.meta.model;
  const modelName = /^timesfm/.test(model) ? "TimesFM" : model;
  const COLORS = { seldon: "var(--seldon)", "seldon-laws": "var(--hypo)", radiant: "var(--radiant)", "chronos-bolt": "var(--rival)", naive: "var(--ink-2)" };
  const NAMES_OF = { seldon: "Seldon", "seldon-laws": "Seldon laws", radiant: "Radiant", "radiant-core": "Radiant core", "chronos-bolt": "Chronos-Bolt",
    "auto-ets": "AutoETS", ensemble: "Ensemble", naive: "No change", drift: "Drift", mean: "Seasonal mean", bass: "Bass curve" };
  const colorOf = (m) => (m === model || /^timesfm/.test(m) ? "var(--tfm)" : COLORS[m] || "var(--ink)");
  const nameOf = (m) => (m === model ? modelName : NAMES_OF[m] || m);
  const skillCls = (v) => (v === null || v === undefined ? "dim" : Math.abs(v) < 0.02 ? "dim" : v > 0 ? "pos" : "neg");
  const signed = (v) => { const r = Math.round(v * 100); return r === 0 ? "0%" : (r > 0 ? "+" : "−") + Math.abs(r) + "%"; };

  // ---------- chrome: status readouts, tape, footer ----------
  const lab = D.lab;
  $("readouts").innerHTML = [
    [D.meta.demo ? "demo" : "live", "Data", D.meta.demo ? "Demo · synthetic" : "Recorded run"],
    ["", "Updated", D.meta.generated],
    ["", "Next run", nextRun()],
  ].map(([c, k, v]) => `<div class="${c}"><dt>${k}</dt><dd>${esc(v)}</dd></div>`).join("");
  $("tape").innerHTML = D.outlook.map((o) => {
    const p = o.p_up, cls = p === null ? "flat" : p > 0.55 ? "up" : p < 0.45 ? "down" : "flat";
    const arrow = cls === "up" ? "▲" : cls === "down" ? "▼" : "■";
    const last = o.history[o.history.length - 1][1];
    return `<a href="#outlook/${esc(o.id)}" style="--c:${hue(o.domain)}" title="${esc(o.title)}: ${fmt.pct(p)} chance it ends higher by ${esc(o.target_date)}"><b>${esc(ticker(o))}</b>${fmt.num(last)}<span class="${cls}">${arrow} ${fmt.pct(p)}</span></a>`;
  }).join("");
  function ticker(o) { return o.id.replace(/_composite$/, "").replace(/_/g, " ").toUpperCase().slice(0, 12); }
  if (D.meta.demo) {
    $("demo").innerHTML = '<div class="demo-banner"><b>Demo data.</b><span>These charts use made-up series and simple models so you can explore the terminal. ' +
      "Real TimesFM forecasts replace them after the first weekly run.</span></div>";
  }
  $("footer").innerHTML = `World Predictor ${esc(D.meta.version)} · model <b>${esc(model)}</b> · data generated ${esc(D.meta.generated)} · ` +
    `<a href="${esc(D.meta.repo)}">source</a> · maintained by <a href="https://github.com/Normansrule">@Normansrule</a> · Apache-2.0 · not financial advice`;
  ["tp-restart", "tp-back", "tp-next"].forEach((id, i) => ($(id).innerHTML = icon(["restart", "prev", "next"][i])));

  // ---------- theme ----------
  function toggleTheme() {
    const root = document.documentElement;
    const light = root.dataset.theme === "light";
    root.dataset.theme = light ? "slate" : "light";
    try { localStorage.setItem("wp-theme", root.dataset.theme); } catch (e) {}
    toast(light ? "Slate" : "Light");
  }
  $("theme").addEventListener("click", toggleTheme);
  let toastTimer;
  function toast(text) {
    const t = $("toast"); t.textContent = text; t.classList.add("on");
    clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove("on"), 1400);
  }

  // ---------- the views ----------
  const views = {
    desk() {
      // Scoreboard: TimesFM and Seldon against "no change", per area. A backtest run since Seldon
      // joined carries its own rows; for older runs the Lab's scoring stands in: Seldon run at export
      // on the same past windows, from the data up to each window's start.
      const fromRun = D.domains.some((r) => r.model === "seldon");
      const pick = (d, m) => {
        if (fromRun || !lab) { const r = D.domains.find((x) => x.domain === d && x.model === m); return r && { skill: r.skill, inside: r.coverage80, direction: r.direction, series: r.series }; }
        return (lab.board || []).find((x) => x.domain === d && x.model === m);
      };
      const areas = AREAS.filter(([d]) => pick(d, model));
      if (!areas.length) {
        $("board").innerHTML = '<tr><td><div class="empty"><b>No backtest yet.</b>The scoreboard fills in after the first forecast run.</div></td></tr>';
      } else {
        const skill = (r) => {
          if (!r || r.skill === null || r.skill === undefined) return "–";
          const v = Math.max(-0.5, Math.min(0.5, r.skill)), w = Math.abs(v) * 48;
          return `<span class="cell-skill"><span class="${skillCls(r.skill)}">${fmt.signedPct(r.skill)}</span><i style="--w:${w}px;--dx:${v < 0 ? -100 : 0}%;--c:${r.skill >= 0 ? "var(--up)" : "var(--down)"}"></i></span>`;
        };
        const cov = (r) => (r && r.inside !== null && r.inside !== undefined ? `${Math.round(r.inside * 100)}%` : "–");
        const near = (r) => (r && r.inside !== null && r.inside !== undefined ? Math.abs(r.inside - 0.8) : 9);
        $("board").innerHTML = `<thead><tr><th>Area</th><th class="m"><span class="who" style="--c:var(--tfm)">${esc(modelName)}</span></th><th><span class="who" style="--c:var(--seldon)">Seldon</span></th>
          <th class="m">In range · ${esc(modelName)}</th><th>In range · Seldon</th><th class="m">Right direction</th><th>Series</th></tr></thead><tbody>` +
          areas.map(([d, name, sub]) => {
            const a = pick(d, model), b = pick(d, "seldon");
            const lead = b && a && b.skill !== null && a.skill !== null ? (b.skill > a.skill + 0.001 ? "s" : a.skill > b.skill + 0.001 ? "m" : "") : "";
            const clead = b && a ? (near(b) < near(a) - 0.005 ? "s" : near(a) < near(b) - 0.005 ? "m" : "") : "";
            return `<tr><td class="area" style="--c:${hue(d)}">${name}<small>${sub}</small></td>
              <td class="m${lead === "m" ? " lead" : ""}" style="--c:var(--tfm)">${skill(a)}</td><td class="${lead === "s" ? "lead" : ""}" style="--c:var(--seldon)">${skill(b)}</td>
              <td class="m${clead === "m" ? " lead" : ""}" style="--c:var(--tfm)">${cov(a)}</td><td class="${clead === "s" ? "lead" : ""}" style="--c:var(--seldon)">${cov(b)}</td>
              <td class="m">${fmt.pct(a && a.direction)}</td><td>${a ? a.series : "–"}</td></tr>`;
          }).join("") + "</tbody>";
        $("board-meta").textContent = fromRun ? "backtest, every series" : "past windows, every series";
        $("board-note").innerHTML = `Skill is how much less error than "no change" (median across series; within ±2% counts as no edge). In range is how often reality landed inside the 80% range: the target is 80%, not 100%.
          An underline marks the better of the two. ${fromRun ? "" : "This run predates Seldon's place in the backtest, so its numbers are Seldon run afterwards on the same past windows, from only the data before each one. It has no pretraining to leak the answer, but the next backtest makes it official."}`;
      }
      duel();
      leaderboard();
      record();
      $("plain-body").innerHTML = D.headlines.length ? "<ul>" + D.headlines.map((h) => `<li>${esc(h)}</li>`).join("") + "</ul>"
        : '<p class="note" style="margin:0">The findings appear after the first forecast run.</p>';
      // The model, its challenger, and at most two rivals; simple baselines stay in the tables.
      const PREFER = ["radiant", "chronos-bolt"];  // the project's own forecaster and the strongest rival come first
      const others = [...new Set(D.domains.map((r) => r.model))].filter((m) => ![model, "seldon", "naive", "drift", "mean"].includes(m))
        .sort((a, b) => ((PREFER.indexOf(a) + 1 || 99) - (PREFER.indexOf(b) + 1 || 99)) || a.localeCompare(b)).slice(0, 2);
      const models = [model, ...(D.domains.some((r) => r.model === "seldon") ? ["seldon"] : []), ...others];
      const RIVAL = ["var(--ink-3)", "var(--line-2)"];
      const groups = AREAS.filter(([d]) => D.domains.some((r) => r.domain === d));
      if (!groups.length) { $("skill-chart").innerHTML = '<div class="empty"><b>No backtest yet.</b>Appears after the first forecast run.</div>'; }
      else {
        const series = models.map((m) => ({ name: nameOf(m), color: others.includes(m) && !COLORS[m] ? RIVAL[others.indexOf(m)] : colorOf(m), values: groups.map(([d]) => (D.domains.find((r) => r.domain === d && r.model === m) || {}).skill ?? null) }));
        if (!models.includes("seldon") && lab) series.splice(1, 0, { name: "Seldon", color: "var(--seldon)", values: groups.map(([d]) => (pick(d, "seldon") || {}).skill ?? null) });
        const host = $("skill-chart"), card = host.closest(".card"), side = card.nextElementSibling;
        const draw = (height) => bars(host, { groups: groups.map((g) => g[1]), series, yFormat: fmt.pct, label: "Skill by area", height });
        $("skill-legend").innerHTML = ""; legend($("skill-legend"), series);
        draw(260);
        // Side by side, grow the chart to the column next to it rather than leave the panel half empty.
        card.style.alignSelf = "start";  // measure the panel's own height, not the stretched one
        const spare = side && side.offsetTop === card.offsetTop ? side.offsetHeight - card.offsetHeight : 0;
        card.style.alignSelf = "";
        if (spare > 24) draw(Math.min(560, 260 + spare));
      }
      const rows = D.outlook.slice(0, 10);
      $("sealed").innerHTML = rows.length ? `<thead><tr><th>Series</th><th>Area</th><th>Last</th><th>${esc(modelName)} middle</th><th>Radiant middle</th><th>Seldon middle</th><th>Chance higher</th><th>Opens</th></tr></thead><tbody>` +
        rows.map((o) => {
          const s = o.seldon && o.seldon.fan && o.seldon.fan.length ? o.seldon.fan[o.seldon.fan.length - 1][2] / o.history[o.history.length - 1][1] - 1 : null;
          const r = o.radiant && o.radiant.length ? o.radiant[o.radiant.length - 1][2] / o.history[o.history.length - 1][1] - 1 : null;
          return `<tr><td><a href="#outlook/${esc(o.id)}">${esc(o.title)}</a></td><td>${tag(o.domain)}</td><td>${fmt.num(o.history[o.history.length - 1][1])}</td>
          <td>${fmt.signedPct(o.change)}</td><td style="color:var(--radiant)">${r === null ? "–" : fmt.signedPct(r)}</td><td>${s === null ? "–" : fmt.signedPct(s)}</td>
          <td class="p"><span class="pbar" style="--p:${Math.round((o.p_up || 0) * 100)}%;--c:${o.p_up > 0.55 ? "var(--up)" : o.p_up < 0.45 ? "var(--down)" : "var(--ink-3)"}"><i></i>${fmt.pct(o.p_up)}</span></td><td>${esc(o.target_date)}</td></tr>`;
        }).join("") + "</tbody>"
        : '<tr><td><div class="empty"><b>Nothing sealed yet.</b>Forecasts appear after the first run of <code>psychohistory predict</code>.</div></td></tr>';
    },

    markets(arg) { window.WPMarkets.render($("markets-root"), D, arg); },

    monitor() { window.WPMonitor.render($("monitor-root"), D); },
    year() { window.WPYear.render($("year-root"), D); },

    today(arg) { window.WPToday.render($("today-root"), D, arg); },

    terminal(arg) { window.WPTerminal.render($("terminal-root"), D, arg); },

    studio(arg) { window.WPStudio.render($("studio-root"), D, { start: arg, onSeal: () => rendered.delete("desk") }); },

    lab(arg) { window.WPLab.render($("lab-root"), D, { start: arg, onScore: () => rendered.delete("desk") }); },

    outlook(arg) {
      const items = D.outlook || [];
      if (!items.length) { $("odetail").innerHTML = '<div class="empty"><b>Nothing sealed yet.</b>Forecasts appear after the first run of <code>psychohistory predict</code>.</div>'; $("olist").innerHTML = ""; return; }
      const st = views.outlook.st || (views.outlook.st = { filter: "all", id: items[0].id });
      if (arg && items.some((o) => o.id === arg)) { st.id = arg; st.filter = "all"; }
      const chips = [["all", "All"], ...AREAS.filter(([d]) => items.some((o) => o.domain === d)).map(([d, n]) => [d, n])];
      $("outlook-filter").innerHTML = chips.map(([k, l]) => `<button class="chip" data-k="${k}" style="--c:${k === "all" ? "var(--tfm)" : hue(k)}" aria-pressed="${k === st.filter}">${l}</button>`).join("");
      $("outlook-filter").onclick = (e) => { const b = e.target.closest("button"); if (!b) return; st.filter = b.dataset.k; const first = shown()[0]; if (first && !shown().some((o) => o.id === st.id)) st.id = first.id; views.outlook(); };
      const shown = () => items.filter((o) => st.filter === "all" || o.domain === st.filter);
      $("olist").innerHTML = `<thead><tr><th>Series</th><th>Higher</th><th>Middle</th></tr></thead><tbody>` + shown().map((o) =>
        `<tr data-id="${esc(o.id)}" style="--c:${hue(o.domain)}" tabindex="0" aria-selected="${o.id === st.id}"><td>${esc(o.title)}<small>${esc(ticker(o))} · ${esc(o.target_date)}</small></td>
          <td class="${o.p_up > 0.55 ? "pos" : o.p_up < 0.45 ? "neg" : "dim"}">${fmt.pct(o.p_up)}</td><td>${fmt.signedPct(o.change)}</td></tr>`).join("") + "</tbody>";
      const choose = (id, focus) => {
        st.id = id; history.replaceState(null, "", "#outlook/" + id);
        $("olist").querySelectorAll("tr[data-id]").forEach((tr) => tr.setAttribute("aria-selected", tr.dataset.id === id));
        if (focus) { const tr = $("olist").querySelector(`tr[data-id="${CSS.escape(id)}"]`); if (tr) { tr.focus(); tr.scrollIntoView({ block: "nearest" }); } }
        detail(items.find((o) => o.id === id));
      };
      $("olist").onclick = (e) => { const tr = e.target.closest("tr[data-id]"); if (tr) choose(tr.dataset.id); };
      $("olist").onkeydown = (e) => {
        const tr = e.target.closest("tr[data-id]"); if (!tr) return;
        if (e.key === "ArrowDown" || e.key === "ArrowUp") {
          e.preventDefault();
          const sib = e.key === "ArrowDown" ? tr.nextElementSibling : tr.previousElementSibling;
          if (sib) choose(sib.dataset.id, true);
        } else if (e.key === "Enter") choose(tr.dataset.id);
      };
      detail(items.find((o) => o.id === st.id) || shown()[0]);
    },

    replay() {
      const R = D.replay;
      if (!R) { $("replay-chart").innerHTML = '<div class="empty"><b>No replay yet.</b>It appears after the first backtest.</div>'; return; }
      $("replay-title").textContent = R.title;
      const slider = $("replay-slider"); slider.max = R.forecasts.length - 1;
      const xDomain = [R.history[0][0], R.history[R.history.length - 1][0]];
      const yDomain = padDomain(R.history.map((p) => p[1]).concat(R.forecasts.flatMap((g) => g.path.flatMap((p) => [p[1], p[3]]))));
      const draw = (i) => {
        const f = R.forecasts[i], origin = Date.parse(f.origin);
        const seen = R.history.filter((p) => Date.parse(p[0]) <= origin);
        const ghosts = R.forecasts.slice(0, i).map((g) => ({ points: g.path.map((p) => [p[0], p[2]]), color: "var(--tfm)", width: 1, opacity: 0.3 }));
        const known = f.path.filter((p) => p[4] !== null);
        const inside = known.filter((p) => p[4] >= p[1] && p[4] <= p[3]).length / Math.max(1, known.length);
        plot($("replay-chart"), {
          x: "date", xDomain, yDomain, label: "Replay of past forecasts",
          bands: [{ points: f.path.map((p) => [p[0], p[1], p[3]]) }],
          lines: [{ points: seen, color: "var(--ink)", width: 1.6, name: "seen" }, ...ghosts, { points: f.path.map((p) => [p[0], p[2]]), color: "var(--tfm)", width: 2.2, name: "guess" }],
          dots: [{ points: f.path.map((p) => [p[0], p[4]]), color: "var(--ink)", r: 2.6, name: "actual" }],
          refs: [{ x: f.origin, label: "forecast made" }],
        });
        $("replay-readout").textContent = `${fmt.date(origin)} · ${Math.round(inside * 100)}% of reality inside the range`;
        slider.value = i; slider.setAttribute("aria-valuetext", `Forecast of ${fmt.date(origin)}`);
      };
      let timer = null;
      const playBtn = $("replay-play");
      const stop = () => { clearInterval(timer); timer = null; playBtn.innerHTML = icon("play") + "Play"; };
      playBtn.innerHTML = icon("play") + "Play";
      playBtn.onclick = () => {
        if (timer) return stop();
        playBtn.innerHTML = icon("pause") + "Pause";
        let i = +slider.value >= R.forecasts.length - 1 ? 0 : +slider.value;
        draw(i);
        timer = setInterval(() => { i += 1; if (i >= R.forecasts.length) return stop(); draw(i); }, 1000);
      };
      views.replay.stop = stop;
      slider.oninput = () => { stop(); draw(+slider.value); };
      draw(+slider.value || 0);
      $("replay-legend").innerHTML = "";
      legend($("replay-legend"), [{ name: "What it could see", color: "var(--ink)" }, { name: "Its 80% range", color: "var(--tfm)", kind: "band" },
        { name: "Its best guess", color: "var(--tfm)" }, { name: "What really happened", color: "var(--ink)", kind: "dot" }]);
    },

    horizon() {
      const DASH = { news: undefined, politics: "8 3 2 3", markets: "6 4", tech: "2 3", weather: "1 3" };
      const lines = AREAS.filter(([d]) => D.horizon.some((r) => r.domain === d)).map(([d, name]) => ({
        name, label: name, color: hue(d), dash: DASH[d], width: 2,
        points: D.horizon.filter((r) => r.domain === d).map((r) => [r.step, r.skill]),
      }));
      if (!lines.length) { $("horizon-chart").innerHTML = '<div class="empty"><b>No backtest yet.</b>Appears after the first backtest.</div>'; return; }
      $("horizon-meta").textContent = `${modelName} · median skill per step`;
      plot($("horizon-chart"), { x: "num", lines, right: 96, xFormat: (v) => (Number.isInteger(v) ? String(v) : ""), refs: [{ y: 0, label: 'no better than "no change"' }], yFormat: fmt.pct, xTitle: "Steps ahead", label: "Skill by steps ahead" });
    },

    odds() {
      const STYLE = Object.fromEntries(AREAS.map(([d]) => [d, { color: `var(--${d})` }]));
      const dots = AREAS.filter(([d]) => D.calibration.some((r) => r.domain === d)).map(([d, name]) => ({
        name, r: 5.5, ...STYLE[d], stroke: STYLE[d].stroke || "var(--panel)", points: D.calibration.filter((r) => r.domain === d).map((r) => [r.said, r.happened]),
      }));
      if (!dots.length) { $("odds-chart").innerHTML = '<div class="empty"><b>No backtest yet.</b>Appears after the first backtest.</div>'; return; }
      plot($("odds-chart"), {
        x: "num", xDomain: [0, 1], yDomain: [0, 1], yFormat: fmt.pct, xFormat: fmt.pct, dots,
        lines: [{ points: [[0, 0], [1, 1]], color: "var(--ink-2)", width: 1, dash: "2 4", name: "honest" }],
        xTitle: "Chance of rising it gave", label: "Calibration",
      });
      $("odds-legend").innerHTML = ""; legend($("odds-legend"), dots.map((d) => ({ name: d.name, color: d.color, kind: "dot" })).concat([{ name: "Honest odds", color: "var(--ink-2)", kind: "dash" }]));
    },

    vault() {
      const V = D.vault || [];
      if (!V.length) {
        $("vault-inside").innerHTML = $("vault-brier").innerHTML = '<div class="empty"><b>The vault is still sealed.</b>It opens as the first sealed predictions come due.</div>';
        return;
      }
      plot($("vault-inside"), { x: "date", yDomain: [0, 1], yFormat: fmt.pct, lines: [{ points: V.map((r) => [r.date, r.inside80]), color: "var(--tfm)", name: "inside" }],
        dots: [{ points: V.map((r) => [r.date, r.inside80]), color: "var(--tfm)", r: 3 }], refs: [{ y: 0.8, label: "target 80%", color: "var(--ink-2)" }], height: 260 });
      plot($("vault-brier"), { x: "date", yDomain: [0, Math.max(0.4, ...V.map((r) => r.brier || 0))], yFormat: (v) => v.toFixed(2),
        lines: [{ points: V.map((r) => [r.date, r.brier]), color: "var(--tfm)", name: "score" }], dots: [{ points: V.map((r) => [r.date, r.brier]), color: "var(--tfm)", r: 3 }],
        refs: [{ y: 0.25, label: "coin flip", color: "var(--ink-2)" }], height: 260 });
      const last = V[V.length - 1];
      opened();
      $("vault-note").textContent = `${last.opened.toLocaleString()} sealed predictions opened so far. ` +
        `${fmt.pct(last.inside80)} landed inside the 80% range; odds score ${last.brier.toFixed(3)} (a coin flip scores 0.250).`;
    },

    crowd() {
      const C = D.crowd, slider = $("crowd-slider"); slider.max = C.sizes.length - 1;
      const t = C.tide.map((_, i) => i);
      const span = Math.max(...C.people[0].map(Math.abs)) * 1.05;
      const draw = (i) => {
        const n = C.sizes[i];
        const people = C.people.slice(0, Math.min(n, 12)).map((p) => ({ points: p.map((v, k) => [t[k], v]), color: "var(--ink-2)", width: 0.8, opacity: 0.3 }));
        plot($("crowd-chart"), {
          x: "num", yDomain: [-span, span], xFormat: () => "", hover: false, label: "Crowd simulation",
          lines: [...people, { points: C.averages[String(n)].map((v, k) => [t[k], v]), color: "var(--hypo)", width: 2.2 },
            { points: C.tide.map((v, k) => [t[k], v]), color: "var(--ink)", width: 1.6, dash: "6 4" }],
        });
        const share = C.share[String(n)];
        $("crowd-share").textContent = share > 0.99 ? ">99%" : Math.round(share * 100) + "%";
        $("crowd-label").textContent = n === 1 ? "one person" : `a crowd of ${n.toLocaleString()}`;
        slider.setAttribute("aria-valuetext", $("crowd-label").textContent);
      };
      slider.oninput = () => draw(+slider.value);
      draw(+slider.value || 0);
      $("crowd-legend").innerHTML = "";
      legend($("crowd-legend"), [{ name: "Crowd average (simulated)", color: "var(--hypo)" }, { name: "Shared tide (the predictable part)", color: "var(--ink)", kind: "dash" },
        { name: "Individual people", color: "var(--ink-2)" }]);
    },

    series(arg) {
      // #series/<id> is that series' own page; #series alone is the sortable table of all of them.
      const page = $("series-page"), all = $("series-all");
      const known = arg && ((D.track || {})[arg] || D.series.some((r) => r.id === arg) || D.outlook.some((o) => o.id === arg));
      page.hidden = !known; all.hidden = !!known;
      if (known) {
        window.WPSeries.render(page, D, arg);
        const r = D.series.find((x) => x.id === arg) || D.outlook.find((x) => x.id === arg);
        document.title = `${r ? r.title : arg} · World Predictor`;
        return;
      }
      if (views.series.drawn) return;
      views.series.drawn = true;
      const rows = D.series || [];
      if (!rows.length) { $("series-table").innerHTML = '<tr><td><div class="empty"><b>No backtest yet.</b>Appears after the first backtest.</div></td></tr>'; return; }
      const cols = [["title", "Series"], ["domain", "Area"], ["scale", "Scale"], ["skill", "Skill"], ["direction", "Right direction"], ["coverage80", "In 80% range"], ["brier", "Odds score"]];
      const st = views.series.st || (views.series.st = { key: "skill", dir: -1 });
      const draw = () => {
        const sorted = rows.slice().sort((a, b) => ((a[st.key] ?? -1e9) > (b[st.key] ?? -1e9) ? 1 : -1) * st.dir);
        $("series-table").innerHTML = "<thead><tr>" + cols.map(([k, l]) => `<th aria-sort="${k === st.key ? (st.dir > 0 ? "ascending" : "descending") : "none"}"><button data-k="${k}">${l}${k === st.key ? (st.dir > 0 ? " ▲" : " ▼") : ""}</button></th>`).join("") + "</tr></thead><tbody>" +
          sorted.map((r) => `<tr><td><a href="#series/${esc(r.id)}">${esc(r.title)}</a></td><td>${tag(r.domain)}</td><td>${esc(r.scale)}</td>` +
            `<td><span class="${skillCls(r.skill)}">${fmt.pct(r.skill)}</span><span class="bar" style="width:${Math.min(60, Math.abs(r.skill || 0) * 240)}px;background:${(r.skill || 0) >= 0 ? "var(--up)" : "var(--down)"}"></span></td>` +
            `<td>${fmt.pct(r.direction)}</td><td>${fmt.pct(r.coverage80)}</td><td>${r.brier === null ? "–" : r.brier.toFixed(3)}</td></tr>`).join("") + "</tbody>";
      };
      $("series-table").onclick = (e) => { const b = e.target.closest("button[data-k]"); if (!b) return; const k = b.dataset.k; st.dir = st.key === k ? -st.dir : -1; st.key = k; draw(); const again = $("series-table").querySelector(`button[data-k="${k}"]`); if (again) again.focus(); };
      draw();
    },

    // The walkthrough lives in trace.js; it keeps its own state across redraws.
    trace(arg) { if (window.WPTrace) window.WPTrace.render(D, arg); },

    about() {},
  };

  // The Time Vault's receipts: each opened forecast of the real future, newest first.
  function opened() {
    const rows = (D.opened || []).filter((r) => r[1] === model);
    const host = $("vault-opened");
    if (!rows.length) { host.innerHTML = '<tr><td><div class="empty"><b>Nothing opened yet.</b>Sealed forecasts appear here as their dates arrive.</div></td></tr>'; return; }
    const titleOf = (id) => ((D.series.find((r) => r.id === id) || D.outlook.find((o) => o.id === id) || {}).title || id);
    const areaOf = (id) => ((D.series.find((r) => r.id === id) || D.outlook.find((o) => o.id === id) || {}).domain);
    const inside = (r) => r[8] !== null && r[8] >= r[5] && r[8] <= r[7];
    const called = (r) => (r[9] === null || r[10] === null || Math.abs(r[9] - 0.5) < 0.005 ? null : (r[9] > 0.5) === (r[10] === 1));
    const st = opened.st || (opened.st = { area: "all" });
    const areas = [...new Set(rows.map((r) => areaOf(r[0])))].filter(Boolean);
    $("vault-filter").innerHTML = [["all", "All"], ...AREAS.filter(([d]) => areas.includes(d))].map(([k, l]) =>
      `<button class="chip" data-k="${k}" style="--c:${k === "all" ? "var(--tfm)" : hue(k)}" aria-pressed="${k === st.area}">${l}</button>`).join("");
    $("vault-filter").onclick = (e) => { const b = e.target.closest("button"); if (!b) return; st.area = b.dataset.k; opened(); };
    const shown = rows.filter((r) => st.area === "all" || areaOf(r[0]) === st.area);
    const n = shown.length, hit = shown.filter(inside).length, dir = shown.map(called).filter((v) => v !== null);
    $("vault-opened-meta").textContent = `${hit} of ${n} inside the 80% range · direction right ${dir.filter(Boolean).length} of ${dir.length}`;
    host.innerHTML = `<thead><tr><th>Series</th><th>Date</th><th>Sealed</th><th>80% range</th><th>Actual</th><th>Range</th><th>Direction</th></tr></thead><tbody>` +
      shown.map((r) => {
        const c = called(r);
        return `<tr style="--c:${hue(areaOf(r[0]))}"><td><a href="#series/${esc(r[0])}">${esc(titleOf(r[0]))}</a></td><td>${esc(r[3])}</td><td>${esc(r[2])}<small>${r[11] ? "before release †" : `${r[4]} step${r[4] === 1 ? "" : "s"} ahead`}</small></td>
          <td>${fmt.num(r[5])} to ${fmt.num(r[7])}</td><td>${fmt.num(r[8])}</td>
          <td>${inside(r) ? '<span class="pos">✓ in</span>' : '<span class="neg">✗ out</span>'}</td><td>${c === null ? '<span class="dim">–</span>' : c ? '<span class="pos">✓ right</span>' : '<span class="neg">✗ wrong</span>'}</td></tr>`;
      }).join("") + "</tbody>";
    $("vault-lag").hidden = !shown.some((r) => r[11]);
  }

  // The duel: who won more series, TimesFM or Seldon, on exactly the same backtest windows. The full
  // Seldon first, then its crowd laws alone (no TimesFM vote), when the run has both.
  function duel() {
    const rows = D.duel || [], host = $("duel");
    if (!host) return;
    if (!rows.length) {
      host.innerHTML = `<div class="duel-head"><span class="who" style="--c:var(--tfm)">${esc(modelName)}</span><b>vs</b><span class="who" style="--c:var(--seldon)">Seldon</span></div>
        <p class="note" style="margin:0">${esc(council(null))} The head-to-head count appears after the next backtest.</p>`;
      return;
    }
    const laws = D.duel_laws || [], rad = D.duel_radiant || [];
    host.innerHTML = (rad.length ? duelBlock(rad, "Radiant", "Radiant: " + modelName + ", Chronos-Bolt, the crowd laws, a behavioural core and no change, mixed by weights each area earned", false, "radiant") : "")
      + duelBlock(rows, "Seldon", "The full Seldon: crowd laws and " + modelName + " in one council", rad.length > 0)
      + (laws.length ? duelBlock(laws, "Laws", "The crowd laws alone, without " + modelName, true) : "")
      + `<p class="note" style="margin:10px 0 0">A series goes to whichever had the lower average absolute error on the same windows (so the count can differ from the leaderboard's, which goes by percentage miss); ties are left out. Seldon is our own forecaster: ${esc(modelName)} and four laws of crowd behaviour (inertia, drift, momentum, reversion, on top of the weekly rhythm) in one council, the laws' share of the vote learned per area from finished windows. Where the laws have not yet earned a share, Seldon follows ${esc(modelName)} and the series is a tie.</p>`;
  }

  function duelBlock(rows, who, label, second, challenger = "seldon") {
    const all = rows.find((r) => r.domain === "all"), areas = rows.filter((r) => r.domain !== "all");
    if (!all) return "";
    const name = (w) => (w === "tie" ? "Tie" : w === model ? modelName : who);
    const ties = all.series - all.wins - all.losses, tieText = ties ? `, ${ties} tied` : "";
    const verdict = all.wins > all.losses ? `${who} won ${all.wins} of ${all.series} series, ${modelName} ${all.losses}${tieText}.`
      : all.losses > all.wins ? `${modelName} won ${all.losses} of ${all.series} series, ${who} ${all.wins}${tieText}.` : `Dead heat: ${all.wins} series each${tieText}.`;
    return `<div class="duel-block${second ? " second" : ""}" style="--cc:${colorOf(challenger)}"><div class="duel-head"><span class="who" style="--c:var(--tfm)">${esc(modelName)}</span><b>vs</b><span class="who" style="--c:var(--cc)">${esc(who)}</span>
        <small class="duel-label">${esc(label)}</small><p class="duel-verdict">${esc(verdict)}</p></div>
      <div class="duel-areas">${areas.map((r) => {
        const a = AREAS.find(([d]) => d === r.domain), share = r.series ? r.wins / r.series : 0;
        const won = r.winner !== "tie" && r.winner !== model;
        return `<div class="duel-area" style="--c:${hue(r.domain)}"><span>${a ? a[1] : esc(r.domain)}</span>
          <span class="duel-bar" style="--s:${(share * 100).toFixed(1)}%" title="${esc(who)} won ${r.wins}, ${esc(modelName)} won ${r.losses}"><i></i></span>
          <small>${esc(who)} ${r.wins} · ${esc(modelName)} ${r.losses}</small><b class="${won ? "s" : r.winner === "tie" ? "" : "m"}">${esc(name(r.winner))}</b></div>`;
      }).join("")}</div></div>`;
  }

  // Every model of the newest backtest on one board, best first. Reads D.leaderboard (web.leaderboard_payload).
  function leaderboard() {
    const L = D.leaderboard, host = $("leader");
    if (!host) return;
    if (!L || !L.rows.length) { host.innerHTML = '<div class="empty"><b>No backtest yet.</b>The leaderboard fills in after the first full forecast run.</div>'; return; }
    const AREA_NAMES = { markets: "Markets", news: "News", politics: "Politics", tech: "Tech", weather: "Weather", yearly: "Yearly" };
    const best = (k) => Math.min(...L.rows.map((r) => (k ? r.areas[k] : r.smape)).filter((v) => v !== null && v !== undefined));
    const cell = (v, k) => (v === null || v === undefined ? '<td class="dim">–</td>' : `<td class="${v === best(k) ? "lead" : ""}">${(v * 100).toFixed(2)}%</td>`);
    const top = L.rows[0].smape, worst = Math.max(...L.rows.map((r) => r.smape));
    host.innerHTML = `<div class="table-wrap"><table class="leader"><thead><tr><th>#</th><th>Model</th><th>Average miss</th>${L.areas.map((a) => `<th>${AREA_NAMES[a] || esc(a)}</th>`).join("")}<th>Skill</th><th>In range</th><th title="series where its average percentage miss was lower">Closer than ${esc(modelName)}</th></tr></thead><tbody>
      ${L.rows.map((r, i) => `<tr class="${r.model === "radiant" ? "ours" : ""}" style="--c:${colorOf(r.model)}"><td class="rank">${i + 1}</td><th scope="row"><span class="who" style="--c:${colorOf(r.model)}">${esc(nameOf(r.model))}</span>${r.model === "radiant" || r.model === "seldon" ? '<small>this project</small>' : ""}</th>
        <td class="miss${r.smape === top ? " lead" : ""}"><span class="lb-bar" style="--w:${(r.smape / worst).toFixed(3)}"></span>${(r.smape * 100).toFixed(2)}%</td>
        ${L.areas.map((a) => cell(r.areas[a], a)).join("")}<td class="${skillCls(r.skill)}">${r.skill === null ? "–" : fmt.signedPct(r.skill)}</td>
        <td>${r.coverage80 === null ? "–" : Math.round(r.coverage80 * 100) + "%"}</td><td>${r.beats === null ? '<span class="dim">the benchmark</span>' : `${r.beats} of ${r.of}`}</td></tr>`).join("")}</tbody></table></div>
      <p class="note">Average sMAPE (symmetric mean absolute percentage error) of each model's most likely value, per series and then averaged, on the same blind backtest windows; lower is better and the best in each column is underlined. Yearly is the three yearly adoption curves (solar, wind, internet), which Radiant learns apart from the daily series. Skill is the median reduction in error against "no change"; in range is how often reality landed inside the 80% range (80% is honest).</p>`;
  }

  function record() {
    const t = window.WPLab ? window.WPLab.tally() : null;
    const calls = window.WPStudio ? window.WPStudio.calls() : [];
    const live = calls.length ? `<p class="note" style="margin:12px 0 0">${calls.length} call${calls.length === 1 ? "" : "s"} sealed on the real future in the <a href="#studio">Forecast Studio</a>.</p>` : "";
    $("you-record").innerHTML = (!lab ? '<p class="note" style="margin:0">The Lab opens after the first backtest.</p>'
      : t && t.played ? `<dl class="record-grid">
          <div><dt>Rounds</dt><dd>${t.played}</dd></div><div><dt>Range hit</dt><dd>${Math.round((t.inside / t.played) * 100)}%</dd></div>
          <div><dt>Beat ${esc(modelName)}</dt><dd>${t.beatModel}/${t.played}</dd></div><div><dt>Beat Seldon</dt><dd>${t.beatSeldon}/${t.played}</dd></div></dl>
          <a class="btn" href="#lab">Play another round</a>`
      : `<p class="note" style="margin:0 0 16px">${lab.series.length} series, ${D.meta.demo ? "demo" : "real"} past windows, the ending hidden. Make your call, seal it, and see whether you beat ${esc(modelName)}.</p>
          <a class="btn primary" href="#lab">Make a call</a>`) + live;
  }

  // Outlook detail: TimesFM's sealed range and Seldon's beside it.
  function detail(o) {
    if (!o) { $("odetail").innerHTML = '<div class="empty">Nothing in this area.</div>'; return; }
    const last = o.history[o.history.length - 1], S = o.seldon && o.seldon.fan && o.seldon.fan.length ? o.seldon : null;
    const sEnd = S ? S.fan[S.fan.length - 1] : null, rel = (v) => v / last[1] - 1;
    const Rf = o.radiant && o.radiant.length ? o.radiant : null, rEnd = Rf ? Rf[Rf.length - 1] : null;
    $("odetail").innerHTML = `<header class="ph"><h2>${esc(o.title)}</h2><span class="pm">sealed ${esc(o.made_on)} · opens ${esc(o.target_date)}</span></header>
      <dl class="facts">
        <div><dt>Chance higher</dt><dd class="big ${o.p_up > 0.55 ? "pos" : o.p_up < 0.45 ? "neg" : ""}">${fmt.pct(o.p_up)}</dd></div>
        <div><dt>Last value</dt><dd>${fmt.num(last[1])}</dd></div>
        <div><dt>${esc(modelName)} middle</dt><dd style="color:var(--tfm)">${fmt.signedPct(o.change)}</dd></div>
        <div><dt>${esc(modelName)} 80% range</dt><dd>${fmt.signedPct(o.low)} to ${fmt.signedPct(o.high)}</dd></div>
        <div><dt>Radiant middle</dt><dd style="color:var(--radiant)">${Rf ? fmt.signedPct(rel(rEnd[2])) : "–"}</dd></div>
        <div><dt>Radiant 80% range</dt><dd>${Rf ? `${fmt.signedPct(rel(rEnd[1]))} to ${fmt.signedPct(rel(rEnd[3]))}` : "–"}</dd></div>
        <div><dt>Seldon middle</dt><dd style="color:var(--seldon)">${S ? fmt.signedPct(rel(sEnd[2])) : "–"}</dd></div>
        <div><dt>Seldon 80% range</dt><dd>${S ? `${fmt.signedPct(rel(sEnd[1]))} to ${fmt.signedPct(rel(sEnd[3]))}` : "–"}</dd></div>
      </dl>
      <div id="ochart"></div><div id="olegend"></div>
      <p class="note">${esc((o.description || "").replace(/([^.])$/, "$1."))}${S ? " " + esc(seldonNote(S)) : ""}</p>${S ? councilBar(S.council) : ""}
      <div class="actions"><a class="btn" href="#studio/${esc(o.id)}">Ask about a level or seal your own call</a>
        <a class="btn" href="#series/${esc(o.id)}">Its track record</a></div>`;
    const hist = o.history.slice(-Math.max(60, 3 * o.fan.length));
    const bandsS = S ? [{ points: [[last[0], last[1], last[1]]].concat(S.fan.map((f) => [f[0], f[1], f[3]])), color: "transparent", stroke: "var(--seldon)", hatch: false, edge: "2 3" }] : [];
    plot($("ochart"), {
      x: "date", height: 340, left: 56, right: 72, label: `${o.title}: history and forecasts`,
      bands: [{ points: [[last[0], last[1], last[1]]].concat(o.fan.map((f) => [f[0], f[1], f[3]])) }, ...bandsS],
      lines: [{ points: hist, color: "var(--ink)", width: 1.7, name: "value" },
        { points: [[last[0], last[1]]].concat(o.fan.map((f) => [f[0], f[2]])), color: "var(--tfm)", width: 2, name: modelName, label: modelName },
        ...(Rf ? [{ points: [[last[0], last[1]]].concat(Rf.map((f) => [f[0], f[2]])), color: "var(--radiant)", width: 2, name: "Radiant", label: "Radiant" }] : []),
        ...(S ? [{ points: [[last[0], last[1]]].concat(S.fan.map((f) => [f[0], f[2]])), color: "var(--seldon)", width: 2, name: "Seldon", label: "Seldon" }] : [])],
      refs: [{ x: last[0], label: "sealed" }],
    });
    legend($("olegend"), [{ name: "History", color: "var(--ink)" }, { name: `${modelName} 80% range`, color: "var(--tfm)", kind: "band" },
      ...(Rf ? [{ name: "Radiant middle", color: "var(--radiant)" }] : []),
      ...(S ? [{ name: "Seldon 80% range", color: "var(--seldon)", kind: "dash" }] : [])]);
  }
  function seldonNote(S) {
    return council(S.council) + (S.source === "computed" ? " This run predates Seldon's sealed forecasts, so its range was computed afterwards from the same data TimesFM had; from the next weekly run Seldon is sealed in the ledger on its own." : "");
  }

  function padDomain(values) {
    const v = values.filter((x) => x !== null && isFinite(x)); const lo = Math.min(...v), hi = Math.max(...v), pad = (hi - lo || 1) * 0.05;
    return [lo - pad, hi + pad];
  }

  // ---------- command palette ----------
  const cmd = $("cmd"), list = $("cmd-list");
  const entries = VIEWS.map((v) => ({ label: NAMES[v], hint: "view", go: "#" + v }))
    .concat(D.outlook.map((o) => ({ label: `${o.title}: every time frame`, hint: "today", go: "#today/" + o.id })))
    .concat(D.outlook.map((o) => ({ label: o.title, hint: ticker(o), go: "#outlook/" + o.id })))
    .concat(D.outlook.map((o) => ({ label: `Ask about ${o.title}`, hint: "studio", go: "#studio/" + o.id })))
    .concat(D.outlook.map((o) => ({ label: `${o.title} in the World terminal`, hint: "terminal", go: "#terminal/" + o.id })))
    .concat(D.outlook.filter((o) => o.domain === "markets").map((o) => ({ label: `${o.title} on the Markets desk`, hint: "markets", go: "#markets/" + o.id })))
    .concat(D.series.map((r) => ({ label: `${r.title} track record`, hint: "series page", go: "#series/" + r.id })))
    .concat(lab ? lab.series.map((s) => ({ label: `${s.title} in the Lab`, hint: "lab", go: "#lab/" + s.id })) : []);
  let hits = [], sel = 0;
  function search() {
    const q = cmd.value.trim().toLowerCase();
    const words = q.split(/\s+/).filter(Boolean);  // every word must appear, in any order
    hits = (q ? entries.filter((e) => { const t = (e.label + " " + e.hint).toLowerCase(); return words.every((w) => t.includes(w)); }) : entries.slice(0, VIEWS.length)).slice(0, 9);
    sel = 0; paint();
  }
  function paint() {
    list.hidden = !hits.length || document.activeElement !== cmd;
    cmd.setAttribute("aria-expanded", String(!list.hidden));
    list.innerHTML = hits.map((h, i) => `<li role="option" id="cmd-${i}" aria-selected="${i === sel}" data-i="${i}">${esc(h.label)}<small>${esc(h.hint)}</small></li>`).join("");
    cmd.setAttribute("aria-activedescendant", hits.length ? "cmd-" + sel : "");
  }
  function run(h) {
    if (!h) return;
    cmd.value = ""; list.hidden = true; cmd.blur();
    if (location.hash === h.go) show(h.go.slice(1)); else location.hash = h.go;
    $("main").focus({ preventScroll: true });
  }
  cmd.addEventListener("input", search);
  cmd.addEventListener("focus", search);
  cmd.addEventListener("blur", () => setTimeout(() => { list.hidden = true; cmd.setAttribute("aria-expanded", "false"); }, 120));
  cmd.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { sel = Math.min(hits.length - 1, sel + 1); paint(); e.preventDefault(); }
    else if (e.key === "ArrowUp") { sel = Math.max(0, sel - 1); paint(); e.preventDefault(); }
    else if (e.key === "Enter") { run(hits[sel]); e.preventDefault(); }
    else if (e.key === "Escape") { cmd.value = ""; cmd.blur(); }
  });
  list.addEventListener("pointerdown", (e) => { const li = e.target.closest("li"); if (li) { e.preventDefault(); run(hits[+li.dataset.i]); } });

  // ---------- keys ----------
  document.addEventListener("keydown", (e) => {
    if (e.metaKey || e.ctrlKey || e.altKey || /INPUT|SELECT|TEXTAREA/.test(e.target.tagName)) return;
    if (e.key === "/") { e.preventDefault(); cmd.focus(); return; }
    if (e.key === "?") { e.preventDefault(); help(); return; }
    if (e.key === "t" || e.key === "T") { toggleTheme(); return; }
    if (KEYS[e.key] !== undefined && !(e.target.closest && e.target.closest(".lab-stage"))) { location.hash = "#" + KEYS[e.key]; }
  });

  // ---------- shortcut help ----------
  function help() {
    const dlg = $("help"); if (!dlg) return;
    const keys = Object.entries(KEYS).filter(([k]) => k !== "?" && !(k.length === 1 && k !== k.toLowerCase() && KEYS[k.toLowerCase()] === KEYS[k]));
    dlg.querySelector(".help-keys").innerHTML = [["/", "Search every series and view"], ["?", "This list"], ["T", "Light or dusk theme"], ["Esc", "Close"]]
      .concat(keys.map(([k, v]) => [k.toUpperCase(), NAMES[v]]))
      .map(([k, n]) => `<div><kbd>${esc(k)}</kbd><span>${esc(n)}</span></div>`).join("");
    if (dlg.open) dlg.close(); else dlg.showModal();
  }
  const helpBtn = $("help-btn");
  if (helpBtn) helpBtn.onclick = help;
  const dlg = $("help");
  if (dlg) dlg.addEventListener("click", (e) => { if (e.target === dlg || e.target.closest("[data-close]")) dlg.close(); });

  // ---------- routing ----------
  const rendered = new Set();
  let current = "today";
  function show(route) {
    let [name, arg] = String(route).split("/");
    if (name === "overview") name = "desk"; // old links
    if (!views[name]) name = "today";
    if (name !== "trace" && window.WPTrace) window.WPTrace.stop();
    if (name !== "replay" && views.replay.stop) views.replay.stop();
    current = name;
    document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === "view-" + name));
    document.querySelectorAll(".rail a").forEach((a) => (a.getAttribute("href") === "#" + name ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current")));
    const cur = document.querySelector('.rail a[aria-current="page"]');
    const more = document.querySelector(".more-nav");
    if (more) more.open = !!(cur && more.contains(cur)) && !matchMedia("(max-width: 860px)").matches;  // on a phone the sheet closes after a choice
    if (more) more.classList.toggle("here", !!(cur && more.contains(cur)));
    if (cur && matchMedia("(max-width: 860px)").matches) cur.scrollIntoView({ block: "nearest", inline: "nearest" });
    document.title = `${NAMES[name]} · World Predictor`;
    if (!rendered.has(name) || arg || name === "series") { views[name](arg); rendered.add(name); }
  }
  window.addEventListener("hashchange", () => {
    const go = () => { show(location.hash.slice(1)); window.scrollTo(0, 0); };
    // A view opened by a key opens at once (it happens dozens of times a session); a click gets a short crossfade.
    if (document.startViewTransition && !reduce() && lastInput === "pointer") document.startViewTransition(go); else go();
  });
  let lastInput = "pointer";
  document.addEventListener("keydown", () => (lastInput = "key"), true);
  document.addEventListener("pointerdown", () => (lastInput = "pointer"), true);
  let resizeTimer, lastW = innerWidth;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => { if (Math.abs(innerWidth - lastW) < 8) return; lastW = innerWidth; rendered.clear(); views.series.drawn = false; show(current === "series" ? location.hash.slice(1) : current); }, 180);
  });
  // Settle any of your sealed calls whose day is in this data file, so your book outlives the data.
  if (window.WPTerminal && !D.meta.demo) try { window.WPTerminal.settleAll(D); } catch (e) {}
  show(location.hash.slice(1) || "today");
  // Panels settle in on the first view only; after that, switching views is instant.
  setTimeout(() => document.documentElement.classList.add("settled"), 900);

  // A soft light follows the pointer across panels (drawn by .card::after in app.css).
  if (matchMedia("(hover: hover)").matches && !reduce()) {
    document.addEventListener("pointermove", (e) => {
      const card = e.target.closest && e.target.closest(".card");
      if (!card) return;
      const r = card.getBoundingClientRect();
      card.style.setProperty("--mx", e.clientX - r.left + "px"); card.style.setProperty("--my", e.clientY - r.top + "px");
    }, { passive: true });
  }

  // Offline support on the web (service workers need http(s), so this is skipped for file://).
  if ("serviceWorker" in navigator && location.protocol.startsWith("http")) navigator.serviceWorker.register("../sw.js").catch(() => {});
})();
