// Compare: up to four series' newest sealed forecasts on one chart. Every line is drawn as the change
// from the value on the day its forecast was sealed, so gold, Bitcoin and a news index on very
// different scales line up, and the 80% ranges ahead can be compared by eye. Below the chart, the
// numbers side by side. Reads D.outlook; the picks live in the address (#compare/gold,silver).
(function () {
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const pct = (p) => (p === null || p === undefined ? "–" : p < 0.01 ? "<1%" : p > 0.99 ? ">99%" : Math.round(p * 100) + "%");
  const sp = (v) => (v === null || v === undefined || !isFinite(v) ? "–" : (v >= 0 ? "+" : "−") + Math.abs(v * 100).toFixed(1) + "%");
  const COLORS = ["var(--tfm)", "var(--radiant)", "var(--seldon)", "var(--you)"];
  const MAX = 4;
  const AREAS = { markets: "Markets", news: "World news", politics: "Politics", tech: "Technology", weather: "Weather and Earth" };
  let D, host, picks = [], batch = null, who = null;

  // Which forecasters have sealed forecasts that already came due, and the weeks they were sealed.
  const NAMES = { seldon: "Seldon", radiant: "Radiant", "chronos-bolt": "Chronos-Bolt" };
  const nameOf = (m) => (/^timesfm/.test(m) ? "TimesFM" : NAMES[m] || m);
  function modelsOpened(data) { const main = data.meta.model; return [...new Set((data.opened || []).map((r) => r[1]))].sort((a, b) => (a === main ? -1 : b === main ? 1 : a < b ? -1 : 1)); }
  function batchesOf(data, model, ids) { return [...new Set((data.opened || []).filter((r) => r[1] === model && (!ids || ids.includes(r[0]))).map((r) => r[2]))].sort(); }

  // One sealed batch of one series, with what really happened: the value it was sealed from (the
  // last one before its first due day), each due day's 80% range and middle, the real value and
  // whether it landed inside. Values are the series' own units. Null when that batch has none due.
  function sealedBatch(data, id, model, madeOn) {
    const rows = (data.opened || []).filter((r) => r[0] === id && r[1] === model && r[2] === madeOn && r[8] !== null).sort((a, b) => (a[3] < b[3] ? -1 : 1));
    if (!rows.length) return null;
    const o = (data.outlook || []).find((x) => x.id === id), hist = (o && o.history) || [];
    const before = hist.filter(([d]) => d < rows[0][3]);
    const start = before.length ? before[before.length - 1] : null;
    const days = rows.map((r) => ({ date: r[3], lo: r[5], mid: r[6], hi: r[7], actual: r[8], step: r[4], inside: r[8] >= r[5] && r[8] <= r[7], pUp: r[9], up: r[10] }));
    // What really happened: the history the app carries, and any due-day values beyond its end.
    const end = hist.length ? hist[hist.length - 1][0] : "";
    const real = hist.concat(days.filter((d) => d.date > end).map((d) => [d.date, d.actual]));
    const last = days[days.length - 1];
    const base = start ? start[1] : null;
    return {
      id, model, madeOn, start, days, real, hits: days.filter((d) => d.inside).length,
      said: base ? last.mid / base - 1 : null, did: base ? last.actual / base - 1 : null,
      // Direction as the table shows it: did the middle forecast and reality move the same way?
      called: !base || Math.abs(last.mid / base - 1) < 5e-4 ? null : (last.mid > base) === (last.actual > base),
    };
  }

  function fromHash() {
    const parts = decodeURIComponent((location.hash.split("/")[1] || "")).split("~");
    batch = parts[1] || null; who = parts[2] || null;
    const want = (parts[0] || "").split(",").filter(Boolean);
    const ids = new Set((D.outlook || []).map((o) => o.id));
    const got = want.filter((id) => ids.has(id)).slice(0, MAX);
    return got.length ? got : (D.outlook || []).slice(0, 3).map((o) => o.id);
  }

  function toHash() {
    const h = "#compare/" + picks.map(encodeURIComponent).join(",") + (batch ? "~" + batch + (who && who !== D.meta.model ? "~" + encodeURIComponent(who) : "") : "");
    if (location.hash !== h) history.replaceState(null, "", h);
  }

  // A series as change from its last value before sealing: history, the 80% fan and the middle.
  function relative(o) {
    const hist = (o.history || []).slice(-63), last = hist.length ? hist[hist.length - 1] : null;
    const base = last && last[1] ? last[1] : null;
    if (!base) return null;
    const rel = (v) => (v === null || v === undefined ? null : v / base - 1);
    return {
      hist: hist.map(([d, v]) => [d, rel(v)]),
      band: [[last[0], 0, 0]].concat((o.fan || []).map(([d, a, , b]) => [d, rel(a), rel(b)])),
      mid: [[last[0], 0]].concat((o.fan || []).map(([d, , m]) => [d, rel(m)])),
    };
  }

  function render(root, data) {
    D = data; host = root; picks = fromHash();
    const all = D.outlook || [];
    if (!all.length) {
      host.innerHTML = `<div class="vhead"><h1 id="compare-h" tabindex="-1">Compare</h1></div><div class="empty"><b>Nothing sealed yet.</b>Compare fills in after the first forecast run.</div>`;
      return;
    }
    const byArea = {};
    all.forEach((o) => (byArea[o.domain] = byArea[o.domain] || []).push(o));
    host.innerHTML = `
      <div class="vhead"><h1 id="compare-h" tabindex="-1">Compare</h1>
        <p class="lede">Up to ${MAX} series' newest sealed forecasts on one chart, each drawn as the change from the day it was sealed, so very different series line up.</p></div>
      <div class="card cmp-pick"><header class="ph"><h2>Pick series</h2><span class="pm" id="cmp-count"></span></header>
        ${Object.entries(byArea).map(([a, list]) => `<div class="cmp-area"><span class="cmp-area-name">${esc(AREAS[a] || a)}</span>
          ${list.map((o) => `<button type="button" class="chip" data-id="${esc(o.id)}" aria-pressed="false">${esc(o.title)}</button>`).join("")}</div>`).join("")}
      </div>
      <div class="card"><header class="ph"><h2 id="cmp-title">Change from the day each was sealed</h2><span class="pm" id="cmp-pm"></span></header>
        <div class="cmp-when"><span class="cmp-area-name">Sealed</span><div class="chips" id="cmp-batch" role="group" aria-label="Which sealed forecasts to show"></div></div>
        <div class="cmp-when" id="cmp-who-row"><span class="cmp-area-name">Forecaster</span><div class="chips" id="cmp-who" role="group" aria-label="Which forecaster"></div></div>
        <p class="cmp-verdict" id="cmp-verdict" aria-live="polite"></p>
        <div id="cmp-chart"></div><div id="cmp-legend"></div>
        <p class="note" id="cmp-note"></p></div>
      <div class="card"><header class="ph"><h2>Side by side</h2></header>
        <div class="table-wrap"><table class="dense cmp-table" id="cmp-table"></table></div></div>`;
    host.querySelectorAll(".cmp-pick .chip").forEach((b) => (b.onclick = () => toggle(b.dataset.id)));
    host.querySelector("#cmp-batch").onclick = (e) => { const b = e.target.closest("button"); if (!b) return; batch = b.dataset.k === "new" ? null : b.dataset.k; toHash(); draw(); };
    host.querySelector("#cmp-who").onclick = (e) => { const b = e.target.closest("button"); if (!b) return; who = b.dataset.k; toHash(); draw(); };
    // With no week in the address, open on the newest week whose forecasts have come due, so the
    // first thing on screen is a forecast next to what really happened.
    // (The week with the most due days for these series; the newest of those if several tie.)
    if (!batch && !/~/.test(location.hash)) {
      const count = {}; (D.opened || []).forEach((r) => { if (r[1] === D.meta.model && picks.includes(r[0]) && r[8] !== null) count[r[2]] = (count[r[2]] || 0) + 1; });
      const best = Object.entries(count).sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? 1 : -1))[0];
      if (best) batch = best[0];
    }
    draw();
  }

  function toggle(id) {
    if (picks.includes(id)) { if (picks.length > 1) picks = picks.filter((x) => x !== id); }
    else picks = picks.concat(id).slice(-MAX);  // a fifth pick replaces the oldest
    toHash(); draw();
  }

  function controls() {
    const models = modelsOpened(D);
    if (!who || !models.includes(who)) who = models[0] || D.meta.model;
    const weeks = batchesOf(D, who, null);
    if (batch && !weeks.includes(batch)) batch = weeks.length ? weeks[weeks.length - 1] : null;
    const short = (d) => new Date(d + "T00:00:00Z").toLocaleString("en", { month: "short", day: "numeric", timeZone: "UTC" });
    host.querySelector("#cmp-batch").innerHTML = weeks.map((w) => `<button class="chip" data-k="${w}" aria-pressed="${w === batch}">${short(w)}</button>`).join("") +
      `<button class="chip" data-k="new" aria-pressed="${!batch}">Newest · not due yet</button>`;
    host.querySelector("#cmp-who").innerHTML = models.map((m) => `<button class="chip" data-k="${esc(m)}" aria-pressed="${m === who}">${esc(nameOf(m))}</button>`).join("");
    host.querySelector("#cmp-who-row").hidden = !batch || models.length < 2;
  }

  function draw() {
    const { plot, legend } = window.WPCharts;
    const items = picks.map((id) => (D.outlook || []).find((o) => o.id === id)).filter(Boolean);
    host.querySelectorAll(".cmp-pick .chip").forEach((b) => {
      const i = picks.indexOf(b.dataset.id);
      b.setAttribute("aria-pressed", String(i >= 0));
      b.style.setProperty("--c", i >= 0 ? COLORS[i] : "var(--line-2)");
    });
    host.querySelector("#cmp-count").textContent = `${items.length} of ${MAX} picked`;
    controls();
    if (batch) return drawJudged(items);
    host.querySelector("#cmp-title").textContent = "Change from the day each was sealed";
    host.querySelector("#cmp-pm").textContent = "last three months · 80% range ahead";
    host.querySelector("#cmp-verdict").textContent = "";
    host.querySelector("#cmp-note").textContent = "Solid lines are what happened up to the sealing day, dashed lines the middle forecast and the shaded areas the 80% ranges ahead. These have not come due yet; pick an earlier week above to see forecasts next to what really happened.";
    const lines = [], bands = [];
    items.forEach((o, i) => {
      const r = relative(o); if (!r) return;
      const c = COLORS[i];
      bands.push({ points: r.band, color: `color-mix(in srgb, ${c} 16%, transparent)`, hatch: false, edge: "3 4", stroke: c });
      lines.push({ points: r.hist, color: c, width: 2, name: o.title });
      lines.push({ points: r.mid, color: c, width: 2, dash: "6 5", draw: false });
    });
    const sealed = items.length ? items[0].history[items[0].history.length - 1][0] : null;
    plot(host.querySelector("#cmp-chart"), {
      x: "date", height: 340, left: 56, bands, lines, yFormat: (v) => sp(v),
      refs: [{ y: 0, color: "var(--line-2)" }].concat(sealed ? [{ x: sealed, label: "sealed", color: "var(--seal)" }] : []),
      label: "Change from the day each forecast was sealed: " + items.map((o) => o.title).join(", "),
    });
    const lg = host.querySelector("#cmp-legend"); lg.innerHTML = "";
    legend(lg, items.map((o, i) => ({ name: o.title, color: COLORS[i] })));
    host.querySelector("#cmp-table").innerHTML = `<thead><tr><th>Series</th><th>Chance higher</th><th>Middle</th><th>80% range</th><th>Judged</th></tr></thead><tbody>` +
      items.map((o, i) => `<tr><th scope="row"><span class="dot" style="--c:${COLORS[i]}"></span><a href="#series/${esc(o.id)}">${esc(o.title)}</a></th>
        <td><span class="pbar" style="--w:${Math.round(o.p_up * 100)}%;--c:${COLORS[i]}"></span><b class="num">${pct(o.p_up)}</b></td>
        <td class="num">${sp(o.change)}<small class="rng-m">${sp(o.low)} to ${sp(o.high)}</small></td><td class="num">${sp(o.low)} to ${sp(o.high)}</td><td class="num">${esc(o.target_date)}</td></tr>`).join("") + "</tbody>";
  }


  // An earlier week's sealed forecasts next to what really happened. Every line is the change from
  // the value it was sealed from; the solid line runs on past the sealing day, and each due day gets
  // a dot: filled green inside the 80% range, red outside.
  function drawJudged(items) {
    const { plot, legend } = window.WPCharts;
    const fmtD = (d) => new Date(d + "T00:00:00Z").toLocaleString("en", { month: "short", day: "numeric", timeZone: "UTC" });
    const lines = [], bands = [], hit = [], miss = [], rows = [];
    let from = null, to = null;
    items.forEach((o, i) => {
      const c = COLORS[i], B = sealedBatch(D, o.id, who, batch);
      rows.push({ o, c, B });
      if (!B || !B.start) return;
      const base = B.start[1], rel = (v) => v / base - 1, d0 = B.start[0], d1 = B.days[B.days.length - 1].date;
      const span = Math.max(7, (Date.parse(d1) - Date.parse(d0)) / 864e5);  // as much history before as forecast after
      const lead = new Date(Date.parse(d0) - span * 864e5).toISOString().slice(0, 10);
      from = from && from < lead ? from : lead; to = to && to > d1 ? to : d1;
      bands.push({ points: [[d0, 0, 0]].concat(B.days.map((d) => [d.date, rel(d.lo), rel(d.hi)])), color: `color-mix(in srgb, ${c} 14%, transparent)`, hatch: false, edge: "3 4", stroke: c });
      lines.push({ points: B.real.filter(([d]) => d >= lead && d <= d1).map(([d, v]) => [d, rel(v)]), color: c, width: 2.4, name: `${o.title}: what happened` });
      lines.push({ points: [[d0, 0]].concat(B.days.map((d) => [d.date, rel(d.mid)])), color: c, width: 1.6, dash: "6 5", draw: false, name: `${o.title}: middle forecast` });
      B.days.forEach((d) => (d.inside ? hit : miss).push([d.date, rel(d.actual)]));
    });
    const got = rows.filter((r) => r.B && r.B.start);
    host.querySelector("#cmp-title").textContent = `Sealed ${fmtD(batch)}: forecast against what really happened`;
    host.querySelector("#cmp-pm").textContent = `${nameOf(who)} · change from the day it was sealed`;
    const n = got.reduce((t, r) => t + r.B.days.length, 0), h = got.reduce((t, r) => t + r.B.hits, 0);
    host.querySelector("#cmp-verdict").innerHTML = got.length
      ? `<b>${h} of ${n}</b> due days landed inside ${esc(nameOf(who))}'s 80% range (${Math.round((h / Math.max(1, n)) * 100)}%; an honest range catches about 80%).`
      : `None of these series had a ${esc(nameOf(who))} forecast sealed on ${fmtD(batch)} that has come due. Pick another week or other series.`;
    plot(host.querySelector("#cmp-chart"), {
      x: "date", height: 360, left: 56, bands, lines, xDomain: from ? [from, to] : undefined, yFormat: (v) => sp(v),
      dots: [{ points: hit, color: "var(--up)", r: 3.6, stroke: "var(--panel)", name: "inside its range" }, { points: miss, color: "var(--down)", r: 3.6, stroke: "var(--panel)", name: "outside its range" }],
      refs: [{ y: 0, color: "var(--line-2)" }].concat(got.length ? [{ x: got[0].B.start[0], label: "sealed", color: "var(--seal)" }] : []),
      label: `Forecasts sealed ${batch} against what happened: ` + items.map((o) => o.title).join(", "),
    });
    const lg = host.querySelector("#cmp-legend"); lg.innerHTML = "";
    legend(lg, items.map((o, i) => ({ name: o.title, color: COLORS[i] })).concat([
      { name: "Real value inside the 80% range", color: "var(--up)", kind: "dot" }, { name: "Outside it", color: "var(--down)", kind: "dot" }]));
    host.querySelector("#cmp-note").textContent = "Solid lines are what really happened, before and after the sealing day. Dashed lines are the middle forecast and the shaded areas its 80% range, written down before those days arrived. A green dot is a due day reality landed inside the range, a red dot one it missed.";
    const mark = (v) => (v === null ? '<span class="dim">–</span>' : v ? '<span class="pos">✓ right</span>' : '<span class="neg">✗ wrong</span>');
    host.querySelector("#cmp-table").innerHTML = `<thead><tr><th>Series</th><th>Middle said</th><th>Really did</th><th>Inside its range</th><th>Direction</th><th>Last due</th></tr></thead><tbody>` +
      rows.map(({ o, c, B }) => `<tr><th scope="row"><span class="dot" style="--c:${c}"></span><a href="#series/${esc(o.id)}">${esc(o.title)}</a></th>` +
        (B && B.start ? `<td class="num">${sp(B.said)}</td><td class="num"><b>${sp(B.did)}</b></td>
          <td class="num ${B.hits / B.days.length >= 0.7 ? "pos" : B.hits / B.days.length < 0.5 ? "neg" : ""}">${B.hits} of ${B.days.length}</td><td>${mark(B.called)}</td><td class="num">${esc(B.days[B.days.length - 1].date)}</td>`
        : `<td colspan="5" class="dim">Nothing sealed that week has come due</td>`) + "</tr>").join("") + "</tbody>";
  }

  window.WPCompare = { render, relative, sealedBatch, batchesOf, modelsOpened, nameOf };
})();
