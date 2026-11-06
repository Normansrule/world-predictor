// Monitor: every sealed forecast against what really happened, over weeks, months and years. One
// line per forecaster over time (skill against "no change", the share of reality inside the 80%
// range, direction hit rate or Brier score, for each period or as a running total), the live record
// beside what the backtest led us to expect, a test of whether each forecaster is really better than
// "no change" or just lucky, drift alarms, live calibration, and the ledger's fingerprint check.
// Reads D.monitor (see src/psychohistory/monitor.py).
(function () {
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const AREAS = [["all", "All areas"], ["news", "World news"], ["politics", "Politics"], ["markets", "Markets"], ["tech", "Technology"], ["weather", "Weather"]];
  const METRICS = [["skill", "Skill vs \"no change\""], ["coverage80", "In 80% range"], ["direction", "Right direction"], ["brier", "Brier score"]];
  const OTHER = ["var(--markets)", "var(--you)", "var(--news)", "var(--tech)", "var(--ink-3)"];
  const state = { area: "all", metric: "skill", grain: null, running: true };
  let D = null, host = null;

  const modelName = () => (/^timesfm/.test(D.meta.model) ? "TimesFM" : D.meta.model);
  const display = (m) => (m === D.meta.model ? modelName() : m === "seldon" ? "Seldon" : m === "seldon-laws" ? "Seldon laws" : m === "naive" ? '"No change"' : m);
  function palette(models) {
    let k = 0;
    return Object.fromEntries(models.map((m) => [m, m === D.meta.model ? "var(--tfm)" : m === "seldon" ? "var(--seldon)" : m === "seldon-laws" ? "var(--seldon)" : OTHER[k++ % OTHER.length]]));
  }
  const order = (models) => models.slice().sort((a, b) => rank(a) - rank(b) || a.localeCompare(b));
  const rank = (m) => (m === D.meta.model ? 0 : m === "seldon" ? 1 : m === "seldon-laws" ? 2 : 3);

  function render(root, data) {
    D = data; host = root;
    const M = D.monitor || {};
    // Until there are a few months to draw, the weekly batches say more than one or two monthly dots.
    if (!state.grain) state.grain = new Set((M.months || []).map((r) => r[2])).size >= 3 ? "months" : "weeks";
    const weeks = new Set((M.weeks || []).map((r) => r[2])).size;
    const seals = M.seals;
    host.innerHTML = `
      <div class="vhead">
        <h1 id="monitor-h">Monitor: predictions against reality</h1>
        <p class="lede">Every forecast sealed in the ledger, scored once its date came, week after week and year after year. None of these could have been fitted to the outcome: this is the record that counts.</p>
      </div>
      <div class="card detail"><dl class="facts mo-facts">
        <div><dt>Forecasts scored</dt><dd>${(M.forecasts || 0).toLocaleString("en")}</dd></div>
        <div><dt>Weekly batches</dt><dd>${weeks}</dd></div>
        <div><dt>Due between</dt><dd>${M.first ? `${esc(M.first)} <small>to</small> ${esc(M.last)}` : "–"}</dd></div>
        <div><dt>Ledger fingerprints</dt><dd class="${seals && seals.bad.length ? "neg" : seals ? "pos" : ""}">${seals ? `${seals.ok} of ${seals.batches} match` : "none yet"}</dd></div>
      </dl>
      <p class="note" style="margin-top:0">${esc(depthNote(weeks))} ${seals ? `Every weekly batch is fingerprinted with SHA-256 when it is sealed and checked by every run (<code>psychohistory verify</code>), so an edited forecast cannot pass unseen${seals.bad.length ? `: <b class="neg">${seals.bad.length} batch${seals.bad.length > 1 ? "es" : ""} changed</b>` : ""}.` : ""}</p></div>
      <div class="mo-bar">
        <div class="chips" id="mo-area" role="group" aria-label="Area">${AREAS.map(([k, l]) => `<button class="chip" data-k="${k}" aria-pressed="${k === state.area}">${l}</button>`).join("")}</div>
        <div class="chips" id="mo-metric" role="group" aria-label="Measure">${METRICS.map(([k, l]) => `<button class="chip" data-k="${k}" aria-pressed="${k === state.metric}">${esc(l)}</button>`).join("")}</div>
        <div class="chips" id="mo-grain" role="group" aria-label="Period">
          <button class="chip" data-k="months" aria-pressed="${state.grain === "months"}">By month</button>
          <button class="chip" data-k="weeks" aria-pressed="${state.grain === "weeks"}">By weekly batch</button></div>
        <label class="mo-toggle"><input type="checkbox" id="mo-run" ${state.running ? "checked" : ""} ${state.grain === "weeks" ? "disabled" : ""}> Running total</label>
      </div>
      <div class="card"><header class="ph"><h2 id="mo-title"></h2><span class="pm" id="mo-sub"></span></header><div id="mo-chart"></div><div id="mo-legend"></div><p class="note" id="mo-note"></p></div>
      <div class="card"><header class="ph"><h2>Live record against the backtest</h2><span class="pm" id="mo-board-sub"></span></header><div class="table-wrap"><table id="mo-board"></table></div>
          <p class="note">Live is every sealed forecast that has come due; backtest is what the past windows led us to expect. The test asks whether a forecaster's errors are really smaller than those of "no change", or could just be luck: a Diebold-Mariano test on the weekly batches, with a Newey-West variance because their 28-day horizons overlap, the Harvey-Leybourne-Newbold small-sample correction and Student's t, since a few batches are all it has. It needs four batches before it says anything, and enough of them to carry the overlap.</p></div>
      <div class="mo-grid">
        <div class="card"><header class="ph"><h2>Drift alarms</h2><span class="pm">forecasts due in the last 13 weeks</span></header><div id="mo-alarms"></div></div>
        <div class="card"><header class="ph"><h2>Are the live odds honest?</h2><span class="pm">chance of ending higher, as given against as happened</span></header><div id="mo-cal"></div><div id="mo-cal-legend"></div>
        <p class="note">Each dot is one bucket of sealed forecasts, by the chance of rising they gave. Honest odds sit on the diagonal: of the forecasts that said 70%, about 70% rose. Small buckets wobble; they settle as the ledger grows.</p></div>
      </div>
      <div class="card" id="mo-vol"></div>
      <div class="card" id="mo-events"></div>`;
    const bind = (id, key) => { host.querySelector(id).onclick = (e) => { const b = e.target.closest("button"); if (!b) return; state[key] = b.dataset.k; render(host, D); }; };
    bind("#mo-area", "area"); bind("#mo-metric", "metric"); bind("#mo-grain", "grain");
    host.querySelector("#mo-run").onchange = (e) => { state.running = e.target.checked; render(host, D); };
    chart(M); board(M); alarmList(M); calibration(M); volatility(D.volatility || {}); eventOdds(D.events || {});
  }

  // Volatility: every forecaster against last month's volatility, on the backtest and live.
  function volatility(V) {
    const { fmt } = window.WPCharts;
    const box = host.querySelector("#mo-vol");
    const rows = V.backtest || [];
    if (!rows.length) { box.innerHTML = '<header class="ph"><h2>Volatility forecasts</h2></header><div class="empty">No volatility backtest yet; <code>psychohistory vol --backtest</code> makes one.</div>'; return; }
    const live = {}; (V.live || []).forEach((r) => (live[r[0] + "|" + r[1]] = r));
    const name = (m) => (m === "garch" ? "GARCH(1,1)" : m === "ewma" ? "EWMA" : m === "last-month" ? "Last month's volatility" : (/^timesfm/.test(m) ? "TimesFM" : m === "seldon" ? "Seldon" : m === "seldon-laws" ? "Seldon laws" : m) + " range");
    const col = (m) => (/^timesfm/.test(m) ? "var(--tfm)" : /^seldon/.test(m) ? "var(--seldon)" : m === "garch" ? "var(--markets)" : m === "ewma" ? "var(--you)" : "var(--ink-3)");
    const top = 0.4; // bars run to ±40%; anything beyond is drawn full length
    const bar = (v) => `<span class="mo-sbar"><i class="${v >= 0 ? "up" : "down"}" style="width:${(50 * Math.min(1, Math.abs(v) / top)).toFixed(1)}%"></i></span>`;
    const sealed = Object.values(V.markets || {}).filter((m) => m.sealed).length;
    const seals = V.seals;
    box.innerHTML = `<header class="ph"><h2>Volatility forecasts: how far markets swing</h2><span class="pm">backtest ${esc(V.first || "")} to ${esc(V.last || "")}, all markets</span></header>
      <div class="table-wrap"><table class="mo-voltab"><thead><tr><th>Forecaster</th><th>Ahead</th><th>Windows</th><th>Skill vs last month's</th><th>Beat it in</th><th>Typical miss</th><th>p</th><th>Live, sealed</th></tr></thead><tbody>${
        rows.map((r) => { const L = live[r[0] + "|" + r[1]], base = r[0] === "last-month";
          return `<tr><td><span class="who" style="--c:${col(r[0])}">${esc(name(r[0]))}</span></td><td>${esc(r[1])}</td><td>${r[3]}</td>
            <td>${base ? '<span class="dim">baseline</span>' : `${bar(r[2])}<b class="${Math.abs(r[2]) < 0.02 ? "" : r[2] > 0 ? "pos" : "neg"}">${fmt.signedPct(r[2])}</b>`}</td>
            <td>${base ? "" : `${r[4]} of ${r[5]}`}</td><td>${fmt.pct(r[6])}</td><td>${r[7] === null || base ? "" : r[7].toFixed(2)}</td>
            <td>${L ? `${base ? "" : fmt.signedPct(L[4]) + " · "}<span class="dim">${esc(L[6])}</span>` : '<span class="dim">none due yet</span>'}</td></tr>`; }).join("")}</tbody></table></div>
      <p class="note">Price levels are close to a random walk; the size of the moves is not, so this is where a forecaster can show real skill. Skill is 1 − QLIKE / QLIKE of last month's volatility carried forward, on the same windows (QLIKE ranks volatility forecasts fairly however noisy the realized measure; Patton, 2011). Typical miss is the median distance between forecast and realized volatility. p is a Diebold-Mariano test of that skill; below 0.05 it is unlikely to be luck. ${sealed ? `Volatility forecasts for ${sealed} markets are sealed every week${seals ? ` (${seals.ok} of ${seals.batches} batches match their fingerprints)` : ""} and scored here as their windows pass.` : "From the next weekly run, every market's volatility forecasts are sealed and fingerprinted like the price forecasts, then scored here as their windows pass."}</p>`;
  }

  // Event odds (src/psychohistory/events.py): the chance of a spike or a lull, scored with the Brier
  // score against climatology (10%) and persistence, in the backtest and as the sealed odds come due.
  function eventOdds(E) {
    const { fmt } = window.WPCharts;
    const box = host.querySelector("#mo-events");
    const rows = (E.backtest || []).filter((r) => r[0] === "all");
    if (!rows.length) { box.innerHTML = '<header class="ph"><h2>Event odds</h2></header><div class="empty">No event-odds backtest yet; <code>psychohistory events --backtest</code> makes one.</div>'; return; }
    const live = {}; (E.live || []).forEach((r) => (live[r[0] + "|" + r[1]] = r));
    const name = (m) => (/^timesfm/.test(m) ? "TimesFM" : m === "seldon" ? "Seldon" : m === "seldon-laws" ? "Seldon laws" : m === "climatology" ? "Climatology (10%)" : m === "persistence" ? "Persistence" : m);
    const col = (m) => (/^timesfm/.test(m) ? "var(--tfm)" : /^seldon/.test(m) ? "var(--seldon)" : m === "persistence" ? "var(--you)" : "var(--ink-3)");
    const top = 0.6;
    const bar = (v) => `<span class="mo-sbar"><i class="${v >= 0 ? "up" : "down"}" style="width:${(50 * Math.min(1, Math.abs(v) / top)).toFixed(1)}%"></i></span>`;
    const n = Math.max(...rows.map((r) => r[10] || 0));
    box.innerHTML = `<header class="ph"><h2>Event odds: spikes and lulls in news and technology</h2><span class="pm">backtest, ${n} origins, every news and technology series</span></header>
      <div class="table-wrap"><table class="mo-voltab"><thead><tr><th>Forecaster</th><th>Event</th><th>Forecasts</th><th>Skill vs climatology</th><th>Vs persistence</th><th>Said · happened</th><th>p</th><th>Live, sealed</th></tr></thead><tbody>${
        rows.map((r) => { const L = live[r[1] + "|" + r[2]], base = r[2] === "climatology";
          return `<tr><td><span class="who" style="--c:${col(r[2])}">${esc(name(r[2]))}</span></td><td>${r[1] === "spike" ? "spike" : "lull"}</td><td>${r[3]}</td>
            <td>${base ? '<span class="dim">baseline</span>' : `${bar(r[7])}<b class="${Math.abs(r[7]) < 0.02 ? "" : r[7] > 0 ? "pos" : "neg"}">${fmt.signedPct(r[7])}</b>`}</td>
            <td>${r[2] === "persistence" ? '<span class="dim">baseline</span>' : fmt.signedPct(r[8])}</td><td>${fmt.pct(r[5])} · ${fmt.pct(r[4])}</td><td>${r[9] === null || base ? "" : r[9].toFixed(2)}</td>
            <td>${L ? `${base ? "" : fmt.signedPct(L[4]) + " · "}<span class="dim">${esc(L[6])}</span>` : '<span class="dim">none due yet</span>'}</td></tr>`; }).join("")}</tbody></table></div>
      <p class="note">A spike is a level the series reaches only one day in ten (the 90th percentile of its last two years), a lull a low it falls to one day in ten; both four weeks ahead. Each forecaster's odds are scored with the Brier score; skill is 1 − Brier / Brier of the baseline on the same forecasts, so above zero means better odds than "10%, as usual" (climatology) or "what happened after days like this one" (persistence). p is a Diebold-Mariano test of the edge over climatology. ${E.seals ? `The odds are sealed every week (${E.seals.ok} of ${E.seals.batches} batches match their fingerprints) and scored here as their day passes.` : "From the next weekly run the odds are sealed and fingerprinted every week, and scored here as their day passes."}</p>`;
  }

  function depthNote(weeks) {
    if (!weeks) return "No sealed forecast has come due yet: the first ones open a few days after the first weekly run.";
    if (weeks < 4) return `${weeks} weekly batch${weeks > 1 ? "es" : ""} so far: too few to tell skill from luck. The monitor sharpens every Monday; a year of runs is 52 batches and over 30,000 scored forecasts per forecaster.`;
    if (weeks < 52) return `${weeks} weekly batches so far. The lines get steadier every Monday; after a year the tests can tell a 2% edge from luck.`;
    return `${weeks} weekly batches: ${(weeks / 52).toFixed(1)} years of sealed forecasts.`;
  }

  function chart(M) {
    const { plot, legend, fmt } = window.WPCharts;
    const box = host.querySelector("#mo-chart");
    const metric = METRICS.find(([k]) => k === state.metric)[1], area = AREAS.find(([k]) => k === state.area)[1];
    host.querySelector("#mo-title").textContent = `${metric}: ${area}`;
    const idx = { months: { skill: 4, coverage80: 5, direction: 6, brier: 7 }, running: { skill: 8, coverage80: 9, direction: 10, brier: 11 }, weeks: { skill: 4, coverage80: 5 } };
    let rows, col, dateOf;
    if (state.grain === "weeks") {
      rows = (M.weeks || []).filter((r) => r[1] === state.area); col = idx.weeks[state.metric]; dateOf = (r) => r[2];
      if (col === undefined) { box.innerHTML = '<div class="empty">Direction and Brier are kept by month. Switch to "By month" to see them.</div>'; host.querySelector("#mo-legend").innerHTML = ""; host.querySelector("#mo-note").textContent = ""; host.querySelector("#mo-sub").textContent = ""; return; }
    } else {
      rows = (M.months || []).filter((r) => r[1] === state.area); col = (state.running ? idx.running : idx.months)[state.metric]; dateOf = (r) => r[2] + "-15";
    }
    host.querySelector("#mo-sub").textContent = state.grain === "weeks" ? "each weekly batch, by the day it was sealed" : state.running ? "running total since the first seal, by the month forecasts came due" : "each month on its own, by when forecasts came due";
    if (!rows.length) { box.innerHTML = '<div class="empty"><b>Nothing has come due yet.</b>The lines start once the first sealed forecasts are scored.</div>'; host.querySelector("#mo-legend").innerHTML = ""; host.querySelector("#mo-note").textContent = ""; return; }
    const models = order([...new Set(rows.map((r) => r[0]))]), colors = palette(models);
    const lines = models.map((m) => ({ points: rows.filter((r) => r[0] === m && r[col] !== null).map((r) => [dateOf(r), r[col]]), color: colors[m],
      width: m === D.meta.model || m === "seldon" ? 2.4 : 1.4, dash: m === "seldon-laws" ? "5 4" : undefined, name: display(m), label: display(m) }));
    const dots = models.map((m) => ({ points: rows.filter((r) => r[0] === m && r[col] !== null).map((r) => [dateOf(r), r[col]]), color: colors[m], r: 3 }));
    const pctMetric = state.metric !== "brier";
    const refs = state.metric === "skill" ? [{ y: 0, label: '"no change"', color: "var(--ink-3)" }] : state.metric === "coverage80" ? [{ y: 0.8, label: "honest: 80%", color: "var(--ink-3)" }]
      : state.metric === "brier" ? [{ y: 0.25, label: "coin flip", color: "var(--ink-3)" }] : [{ y: 0.5, label: "coin flip", color: "var(--ink-3)" }];
    const exp = (M.expected || []).find((r) => r[0] === D.meta.model && r[1] === state.area);
    if (exp && (state.metric === "skill" || state.metric === "coverage80")) {
      const v = state.metric === "skill" ? exp[2] : exp[3];
      if (v !== null) refs.push({ y: v, label: `${modelName()} backtest`, color: "var(--tfm)" });
    }
    const single = new Set(rows.map(dateOf)).size === 1;
    plot(box, { x: "date", height: 320, left: 56, right: 96, label: `${metric} over time`, lines, dots, refs,
      yFormat: pctMetric ? fmt.pct : (v) => v.toFixed(2), xDomain: single ? padDomain(dateOf(rows[0])) : undefined });
    legend(host.querySelector("#mo-legend"), models.map((m) => ({ name: display(m), color: colors[m], kind: m === "seldon-laws" ? "dash" : undefined })));
    host.querySelector("#mo-note").textContent = state.metric === "skill" ? 'Above zero: less error than "no change", the guess that tomorrow looks like today. The blue reference line is what the backtest led us to expect from ' + modelName() + "."
      : state.metric === "coverage80" ? "An honest 80% range catches reality about 80% of the time: well below means overconfident, well above means vague."
      : state.metric === "direction" ? "How often the forecast's middle moved the same way the series did, over the whole horizon. 50% is a coin flip."
      : "Squared error of the chance of ending higher: 0 is perfect, 0.25 is a coin flip, lower is better.";
  }
  function padDomain(d) { const t = Date.parse(d); return [new Date(t - 20 * 864e5).toISOString().slice(0, 10), new Date(t + 20 * 864e5).toISOString().slice(0, 10)]; }

  function board(M) {
    const { fmt } = window.WPCharts;
    const rows = (M.overall || []).filter((r) => r[1] === state.area);
    host.querySelector("#mo-board-sub").textContent = AREAS.find(([k]) => k === state.area)[1];
    const t = host.querySelector("#mo-board");
    if (!rows.length) { t.innerHTML = '<tr><td><div class="empty">Nothing has come due yet.</div></td></tr>'; return; }
    const colors = palette(order(rows.map((r) => r[0])));
    const exp = Object.fromEntries((M.expected || []).filter((r) => r[1] === state.area).map((r) => [r[0], r]));
    const test = Object.fromEntries((M.tests || []).filter((r) => r[1] === state.area).map((r) => [r[0], r]));
    const k = (v) => (v === null ? "dim" : Math.abs(v) < 0.02 ? "" : v > 0 ? "pos" : "neg");
    t.innerHTML = `<thead><tr><th>Forecaster</th><th>Forecasts</th><th>Live skill</th><th>Backtest skill</th><th>Live in 80%</th><th>Backtest in 80%</th><th>Direction</th><th>Brier</th><th>Better than "no change"?</th></tr></thead><tbody>` +
      order(rows.map((r) => r[0])).map((m) => {
        const r = rows.find((x) => x[0] === m), e = exp[m], s = test[m];
        const verdict = !s ? "–" : /^better/.test(s[6]) ? `<span class="pos">yes</span> <span class="dim">p ${s[5].toFixed(2)}</span>` : /^worse/.test(s[6]) ? `<span class="neg">worse</span> <span class="dim">p ${s[5].toFixed(2)}</span>`
          : /^too early/.test(s[6]) ? `<span class="dim">too early (${s[2]}/4 batches)</span>` : `<span class="dim">not yet${s[5] !== null ? ", p " + s[5].toFixed(2) : ""}</span>`;
        return `<tr><td><span class="who" style="--c:${colors[m]}">${esc(display(m))}</span></td><td>${r[2].toLocaleString("en")}</td><td class="${k(r[5])}">${fmt.signedPct(r[5])}</td><td class="${e ? k(e[2]) : "dim"}">${e ? fmt.signedPct(e[2]) : "–"}</td>
          <td>${fmt.pct(r[6])}</td><td>${e ? fmt.pct(e[3]) : "–"}</td><td>${fmt.pct(r[7])}</td><td>${r[8] === null ? "–" : r[8].toFixed(3)}</td><td>${verdict}</td></tr>`;
      }).join("") + "</tbody>";
  }

  function alarmList(M) {
    const box = host.querySelector("#mo-alarms");
    const list = (M.alarms || []).filter((r) => state.area === "all" || r[2] === state.area);
    const title = (id) => { const s = (D.series || []).find((x) => x.id === id) || (D.outlook || []).find((x) => x.id === id); return s ? s.title : id; };
    const why = { "range too narrow": "reality left its 80% range far more often than 1 time in 5: the forecaster is overconfident here",
      "range too wide": "reality stayed inside its 80% range almost every time: the range is vaguer than it needs to be",
      "edge lost": "the backtest showed an edge here, the live record does not", "worse than no change": "its recent errors are significantly larger than \"no change\"'s" };
    // One group per kind of alarm, the most serious first; each series once, with the forecasters it rang for.
    const kinds = ["worse than no change", "edge lost", "range too narrow", "range too wide"];
    const groups = kinds.map((k) => [k, list.filter((r) => r[3] === k)]).filter(([, rows]) => rows.length);
    const detail = (r) => r[3].startsWith("range") ? `${Math.round(r[5] * 100)}% inside over ${r[4]} batches`
      : r[3] === "edge lost" ? `live ${(r[5] * 100).toFixed(1)}% against backtest ${(r[6] * 100).toFixed(1)}%` : r[7] !== null ? `p ${r[7].toFixed(3)}, ${r[4]} batches` : "";
    const group = ([kind, rows]) => {
      const bySeries = new Map();
      rows.forEach((r) => bySeries.set(r[1], [...(bySeries.get(r[1]) || []), r]));
      const items = [...bySeries.entries()].sort((a, b) => b[1].length - a[1].length || title(a[0]).localeCompare(title(b[0])));
      return `<li><div class="mo-alarm-h"><b class="neg">${esc(kind)}</b><span>${rows.length} on ${bySeries.size} series</span></div>
        <small>${esc(why[kind] || "")}.</small>
        <ul class="mo-alarm-series">${items.map(([id, rs]) => `<li><a href="#series/${esc(id)}">${esc(title(id))}</a>
          <span>${rs.map((r) => `<span class="mo-who" title="${esc(detail(r))}">${esc(display(r[0]))}</span>`).join("")}</span></li>`).join("")}</ul></li>`;
    };
    box.innerHTML = list.length ? `<p class="mo-alarm-note">${list.length} alarm${list.length > 1 ? "s" : ""}. Every forecaster is tested on every series at once, so only the alarms that pass a false-discovery cut are raised (Benjamini-Hochberg, 5%), and the tests read Student's t, as a few weekly batches are all they have.</p><ul class="mo-alarms">${groups.map(group).join("")}</ul>`
      : `<div class="mo-clear"><b>No alarms.</b><span>${(M.forecasts || 0) ? "No forecaster's range, edge or errors has drifted far enough from its record to rule out chance." : "Alarms need sealed forecasts that have come due."} A forecaster is flagged when its recent 80% range catches reality much less or much more than 80% of the time, when a backtest edge disappears live, or when it turns significantly worse than "no change". Each test needs four weekly batches.</span></div>`;
  }

  function calibration(M) {
    const { plot, legend } = window.WPCharts;
    const rows = M.calibration || [], box = host.querySelector("#mo-cal");
    if (!rows.length) { box.innerHTML = '<div class="empty">Appears once sealed forecasts come due.</div>'; return; }
    const models = order([...new Set(rows.map((r) => r[0]))]), colors = palette(models);
    plot(box, { height: 280, left: 48, right: 24, label: "Live calibration", xDomain: [0, 1], yDomain: [0, 1], xFormat: (v) => Math.round(v * 100) + "%", yFormat: (v) => Math.round(v * 100) + "%",
      xTitle: "chance of rising the forecast gave",
      lines: [{ points: [[0, 0], [1, 1]], color: "var(--line-2)", width: 1, dash: "3 3", name: "honest" },
        ...models.map((m) => ({ points: rows.filter((r) => r[0] === m && r[3] !== null && r[4] !== null).map((r) => [r[3], r[4]]), color: colors[m], width: m === D.meta.model ? 2 : 1.2, opacity: 0.8, name: display(m) }))],
      dots: models.map((m) => ({ points: rows.filter((r) => r[0] === m && r[3] !== null && r[4] !== null).map((r) => [r[3], r[4]]), color: colors[m], r: 4 })) });
    legend(host.querySelector("#mo-cal-legend"), [{ name: "Honest odds", color: "var(--line-2)", kind: "dash" }, ...models.map((m) => ({ name: display(m), color: colors[m] }))]);
  }

  window.WPMonitor = { render };
})();
