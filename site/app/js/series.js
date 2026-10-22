// Series pages: one page per series with every backtest window it was tested on, what each window
// said against what really happened, its newest sealed forecast, and every sealed forecast whose
// date has already arrived. Reads D.track (past windows) and D.opened (scored sealed forecasts).
(function () {
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const AREA_NAMES = { news: "World news", markets: "Markets", tech: "Technology" };
  const hue = (d) => (AREA_NAMES[d] ? `var(--${d})` : "var(--ink-3)");
  const DAY = 864e5;
  const state = { id: null, k: null };

  // The windows of one series, unpacked: dates, actual values, and per window its percentiles.
  function windowsOf(D, id) {
    const T = (D.track || {})[id];
    if (!T || !T.windows.length) return null;
    const t0 = Date.parse(T.start);
    const dates = T.days.map((d) => new Date(t0 + d * DAY).toISOString().slice(0, 10));
    const ev = Object.fromEntries(((D.evidence || {})[id] || []).map((r) => [r[0], r]));
    const list = T.windows.map(([origin, at, q10, q50, q90]) => {
      const n = q50.length, before = at > 0 ? T.actual[at - 1] : null, end = T.actual[at + n - 1];
      const actual = T.actual.slice(at, at + n);
      const inside = actual.filter((a, i) => a !== null && a >= q10[i] && a <= q90[i]).length / Math.max(1, actual.filter((a) => a !== null).length);
      const e = ev[origin] || [];
      const pUp = e[3] ?? null, rose = e[4] ?? null;
      return {
        origin, at, n, q10, q50, q90, actual, inside, pUp, rose, mase: e[1] ?? null,
        said: before ? q50[n - 1] / before - 1 : null, did: before && end !== null ? end / before - 1 : null,
        called: pUp === null || rose === null || Math.abs(pUp - 0.5) < 0.005 ? null : (pUp > 0.5) === (rose === 1),
        dates: dates.slice(at, at + n),
      };
    });
    return { dates, actual: T.actual, list };
  }

  function render(host, D, id) {
    const { plot, legend, fmt } = window.WPCharts;
    const model = D.meta.model, modelName = /^timesfm/.test(model) ? "TimesFM" : model;
    const row = (D.series || []).find((r) => r.id === id);
    const o = (D.outlook || []).find((x) => x.id === id);
    const W = windowsOf(D, id);
    const domain = (row || o || {}).domain, title = (row || o || { title: id }).title;
    if (state.id !== id) { state.id = id; state.k = W ? W.list.length - 1 : null; }
    const opened = (D.opened || []).filter((r) => r[0] === id);
    const mine = opened.filter((r) => r[1] === model), seldonRows = opened.filter((r) => r[1] === "seldon");
    const hits = mine.filter((r) => r[8] !== null && r[8] >= r[5] && r[8] <= r[7]).length;
    const trace = (D.outlook || []).some((x) => x.id === id);
    const lab = D.lab && D.lab.series.some((s) => s.id === id);

    const fact = (k, v, cls = "") => `<div><dt>${k}</dt><dd class="${cls}">${v}</dd></div>`;
    const skillCls = (v) => (v === null || v === undefined || Math.abs(v) < 0.02 ? "" : v > 0 ? "pos" : "neg");
    host.innerHTML = `
      <a class="back" href="#series">All series</a>
      <div class="vhead">
        <p class="flags"><span class="tag" style="--c:${hue(domain)}">${esc(AREA_NAMES[domain] || domain || "Series")}</span>${row ? `<span class="tag" style="--c:var(--ink-3)">${esc(row.scale)}</span>` : ""}</p>
        <h1 id="sp-h" tabindex="-1">${esc(title)}</h1>
        <p class="lede">${esc((o && o.description) || "")}${o && o.description ? ". " : ""}Every forecast ${esc(modelName)} made for it, and what really happened.</p>
      </div>
      <div class="card detail"><dl class="facts">
        ${fact('Skill vs "no change"', row ? fmt.signedPct(row.skill) : "–", row ? skillCls(row.skill) : "")}
        ${fact("Right direction", row ? fmt.pct(row.direction) : "–")}
        ${fact("Inside its 80% range", row ? fmt.pct(row.coverage80) : "–")}
        ${fact("Odds score", row && row.brier !== null ? row.brier.toFixed(3) : "–")}
        ${fact("Past windows tested", W ? String(W.list.length) : "–")}
        ${fact("Real forecasts opened", mine.length ? `${hits} of ${mine.length} in range` : "none yet")}
      </dl><p class="note" style="margin:0">Skill is error removed against "tomorrow looks like today". The range should catch reality about 8 times in 10, and an odds score of 0.25 is a coin flip.</p></div>

      <div class="card">
        <header class="ph"><h2>Every past forecast against what happened</h2><span class="pm">backtest · ${W ? W.list.length : 0} windows</span></header>
        ${W ? `<div class="controls">
          <input type="range" id="sp-slider" min="0" max="${W.list.length - 1}" value="${state.k}" aria-label="Past forecast window">
          <span class="note" id="sp-readout" aria-live="polite"></span></div>
          <div id="sp-chart"></div><div id="sp-legend"></div>
          <div class="table-wrap opened-wrap"><table class="dense olist sp-windows" id="sp-table"></table></div>`
        : '<div class="empty"><b>No backtest for this series yet.</b>It appears after the next forecast run.</div>'}
      </div>

      <div class="two">
        <div class="card"><header class="ph"><h2>Sealed on the real future</h2>${o ? `<span class="pm">sealed ${esc(o.made_on)} · opens ${esc(o.target_date)}</span>` : ""}</header>
          ${o ? `<div id="sp-fan"></div><div id="sp-fan-legend"></div>
            <p class="note">Middle guess ${fmt.signedPct(o.change)} by ${esc(o.target_date)}, 80% range ${fmt.signedPct(o.low)} to ${fmt.signedPct(o.high)}, and a ${fmt.pct(o.p_up)} chance it ends higher.</p>`
          : '<div class="empty"><b>Nothing sealed for this series yet.</b>The next weekly run seals a forecast for it.</div>'}
        </div>
        <div class="card"><header class="ph"><h2>Opened so far</h2><span class="pm">sealed, not a backtest</span></header>
          ${mine.length ? `<div class="table-wrap opened-wrap"><table class="dense opened" id="sp-opened"></table></div>
            ${mine.some((r) => r[11]) ? `<p class="note">† Sealed after its date but before the source published that value, so ${esc(modelName)} never saw it.</p>` : ""}`
          : `<div class="empty"><b>No sealed forecast has reached its date yet.</b>${o ? `The first step of this week's opens on ${esc(o.fan[0][0])}.` : "They open as their dates arrive."}</div>`}
        </div>
      </div>
      <div class="actions">
        ${o ? `<a class="btn primary" href="#studio/${esc(id)}">Ask about a level</a>` : ""}
        ${lab ? `<a class="btn" href="#lab/${esc(id)}">Make a blind call in the Lab</a>` : ""}
        ${trace ? `<a class="btn" href="#trace/${esc(id)}">Follow this forecast to its source</a>` : ""}
      </div>`;

    if (W) {
      const draw = () => {
        const w = W.list[state.k];
        const pts = W.dates.map((d, i) => [d, W.actual[i]]);
        plot(host.querySelector("#sp-chart"), {
          x: "date", height: 320, left: 56, label: `${title}: every past forecast and what happened`,
          bands: W.list.map((v, i) => ({ points: v.dates.map((d, j) => [d, v.q10[j], v.q90[j]]), color: i === state.k ? "var(--band)" : "var(--band-faint)", hatch: i === state.k, fade: false })),
          lines: [{ points: pts, color: "var(--ink)", width: 1.5, name: "what happened" },
            ...W.list.map((v, i) => ({ points: v.dates.map((d, j) => [d, v.q50[j]]), color: "var(--tfm)", width: i === state.k ? 2.4 : 1, opacity: i === state.k ? 1 : 0.4, draw: false, name: modelName }))],
          dots: [{ points: w.dates.map((d, j) => [d, w.actual[j]]), color: "var(--ink)", r: 2.4 }],
          refs: [{ x: w.dates[0] }],  // the readout names the date; a label here runs off the edge for the newest window
        });
        const verdict = w.called === null ? "" : w.called ? " It called the direction right." : " It called the direction wrong.";
        host.querySelector("#sp-readout").textContent = `Made ${fmt.date(Date.parse(w.origin))}: the middle said ${fmt.signedPct(w.said)}, reality went ${fmt.signedPct(w.did)}, and ${Math.round(w.inside * 100)}% of the days landed inside the range.${verdict}`;
        const slider = host.querySelector("#sp-slider");
        slider.value = state.k; slider.setAttribute("aria-valuetext", `Forecast made ${w.origin}`);
        host.querySelectorAll("#sp-table tr[data-k]").forEach((tr) => tr.setAttribute("aria-selected", String(+tr.dataset.k === state.k)));
      };
      const mark = (v) => (v === null ? '<span class="dim">–</span>' : v ? '<span class="pos">✓ right</span>' : '<span class="neg">✗ wrong</span>');
      host.querySelector("#sp-table").innerHTML = `<thead><tr><th>Made</th><th>Middle said</th><th>Reality</th><th>In range</th><th>Chance higher</th><th>Direction</th></tr></thead><tbody>` +
        W.list.map((w, k) => `<tr data-k="${k}" tabindex="0" style="--c:var(--tfm)"><td>${esc(w.origin)}</td><td>${fmt.signedPct(w.said)}</td><td>${fmt.signedPct(w.did)}</td>
          <td class="${w.inside >= 0.7 ? "" : "neg"}">${Math.round(w.inside * 100)}%</td><td>${fmt.pct(w.pUp)}</td><td>${mark(w.called)}</td></tr>`).reverse().join("") + "</tbody>";
      const table = host.querySelector("#sp-table");
      const pick = (k, focus) => {
        state.k = Math.max(0, Math.min(W.list.length - 1, k)); draw();
        if (focus) { const tr = table.querySelector(`tr[data-k="${state.k}"]`); if (tr) { tr.focus(); tr.scrollIntoView({ block: "nearest" }); } }
      };
      table.onclick = (e) => { const tr = e.target.closest("tr[data-k]"); if (tr) pick(+tr.dataset.k); };
      table.onkeydown = (e) => {
        const tr = e.target.closest("tr[data-k]"); if (!tr) return;
        // Rows run newest first, so the row below is the older window.
        if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); pick(+tr.dataset.k + (e.key === "ArrowDown" ? -1 : 1), true); }
        else if (e.key === "Enter") pick(+tr.dataset.k);
      };
      host.querySelector("#sp-slider").oninput = (e) => pick(+e.target.value);
      draw();
      legend(host.querySelector("#sp-legend"), [{ name: "What really happened", color: "var(--ink)" }, { name: `${modelName}'s middle guess`, color: "var(--tfm)" },
        { name: "Its 80% range (chosen window)", color: "var(--tfm)", kind: "band" }, { name: "When it was made", color: "var(--ink-2)", kind: "dash" }]);
    }

    if (o) {
      const last = o.history[o.history.length - 1], S = o.seldon && o.seldon.fan && o.seldon.fan.length ? o.seldon : null;
      plot(host.querySelector("#sp-fan"), {
        x: "date", height: 260, left: 56, right: 64, label: `${title}: newest sealed forecast`,
        bands: [{ points: [[last[0], last[1], last[1]]].concat(o.fan.map((f) => [f[0], f[1], f[3]])) },
          ...(S ? [{ points: [[last[0], last[1], last[1]]].concat(S.fan.map((f) => [f[0], f[1], f[3]])), color: "transparent", stroke: "var(--seldon)", hatch: false, edge: "2 3" }] : [])],
        lines: [{ points: o.history.slice(-90), color: "var(--ink)", width: 1.6, name: "value" },
          { points: [[last[0], last[1]]].concat(o.fan.map((f) => [f[0], f[2]])), color: "var(--tfm)", width: 2, name: modelName, label: modelName },
          ...(S ? [{ points: [[last[0], last[1]]].concat(S.fan.map((f) => [f[0], f[2]])), color: "var(--seldon)", width: 2, name: "Seldon", label: "Seldon" }] : [])],
        refs: [{ x: last[0], label: "sealed" }],
      });
      legend(host.querySelector("#sp-fan-legend"), [{ name: "History", color: "var(--ink)" }, { name: `${modelName} 80% range`, color: "var(--tfm)", kind: "band" },
        ...(S ? [{ name: "Seldon 80% range", color: "var(--seldon)", kind: "dash" }] : [])]);
    }

    if (mine.length) {
      const both = seldonRows.length > 0;
      host.querySelector("#sp-opened").innerHTML = `<thead><tr>${both ? "<th>Model</th>" : ""}<th>Date</th><th>Sealed</th><th>80% range</th><th>Actual</th><th>Result</th></tr></thead><tbody>` +
        (both ? opened : mine).map((r) => {
          const inside = r[8] !== null && r[8] >= r[5] && r[8] <= r[7];
          const name = r[1] === "seldon" ? "Seldon" : modelName, c = r[1] === "seldon" ? "var(--seldon)" : "var(--tfm)";
          return `<tr>${both ? `<td style="color:${c}">${name}</td>` : ""}<td>${esc(r[3])}</td><td>${esc(r[2])}<small>${r[11] ? "before release †" : `${r[4]} step${r[4] === 1 ? "" : "s"} ahead`}</small></td>
            <td>${fmt.num(r[5])} to ${fmt.num(r[7])}</td><td>${fmt.num(r[8])}</td><td>${inside ? '<span class="pos">✓ in range</span>' : '<span class="neg">✗ outside</span>'}</td></tr>`;
        }).join("") + "</tbody>";
    }
  }

  window.WPSeries = { render, windowsOf };
})();
