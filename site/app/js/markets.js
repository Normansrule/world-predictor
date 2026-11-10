// Markets desk: the forecasts for every market on one screen, the way an analyst works. A watchlist
// at the chosen horizon (expected move, 80% range, chance of rising, TimesFM and Seldon side by side,
// the volatility each implies against what the market has shown, and each model's record on that
// asset), a detail panel with the fan chart, price ladder and an odds calculator, a comparison of
// up to four markets rebased to 100, and CSV / JSON export of everything on screen.
// Reads D.outlook (sealed fans), D.markets (tickers and every model's record per asset), D.series,
// D.track and D.evidence (past windows). Chances between and beyond the 10th / 50th / 90th
// percentiles a fan keeps are read off a split log-normal curve through them.
(function () {
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const HORIZONS = [[1, "1D"], [5, "1W"], [10, "2W"], [20, "1M"]];
  const Z90 = 1.2815516, Z75 = 0.6744898;
  const COMPARE = ["var(--tfm)", "var(--seldon)", "var(--markets)", "var(--you)"];
  const state = { id: null, h: 20, who: "model", compare: [], sort: null, dir: -1, level: null, fstep: 20 };
  let D = null, host = null;

  // ---------- numbers ----------
  const erf = (x) => { // Abramowitz-Stegun 7.1.26, |error| < 1.5e-7
    const t = 1 / (1 + 0.3275911 * Math.abs(x));
    const y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-x * x);
    return x >= 0 ? y : -y;
  };
  const cdf = (z) => 0.5 * (1 + erf(z / Math.SQRT2));
  const logs = (q) => q.every((v) => v > 0);
  // Chance the value ends above `level`, from one step's [lo, mid, hi] (10th, 50th, 90th percentiles).
  function pAbove(q, level) {
    const [lo, mid, hi] = q, useLog = logs(q) && level > 0;
    const f = useLog ? Math.log : (v) => v;
    const sd = (level >= mid ? f(hi) - f(mid) : f(mid) - f(lo)) / Z90;
    if (!(sd > 0)) return level > mid ? 0.02 : 0.98;
    return Math.min(0.98, Math.max(0.02, 1 - cdf((f(level) - f(mid)) / sd)));
  }
  // Any percentile from the three kept, on the same curve (25th and 75th for the ladder).
  function quantile(q, z) {
    const [lo, mid, hi] = q, useLog = logs(q), f = useLog ? Math.log : (v) => v, g = useLog ? Math.exp : (v) => v;
    const sd = (z >= 0 ? f(hi) - f(mid) : f(mid) - f(lo)) / Z90;
    return g(f(mid) + z * sd);
  }
  const perYear = (id) => (((D.markets || {})[id] || {}).freq === "D" ? 365 : 252);
  function realizedVol(o) {
    const v = o.history.map((p) => p[1]).filter((x) => x > 0);
    if (v.length < 5) return null;
    const r = v.slice(1).map((x, i) => Math.log(x / v[i]));
    const m = r.reduce((a, b) => a + b, 0) / r.length;
    return Math.sqrt(r.reduce((a, b) => a + (b - m) ** 2, 0) / (r.length - 1) * perYear(o.id));
  }
  const impliedVol = (q, steps, id) => (logs(q) && steps > 0 ? (Math.log(q[2]) - Math.log(q[0])) / (2 * Z90) / Math.sqrt(steps) * Math.sqrt(perYear(id)) : null);

  // ---------- data ----------
  const modelName = () => (/^timesfm/.test(D.meta.model) ? "TimesFM" : D.meta.model);
  const short = (m) => (m === D.meta.model ? modelName() : m === "seldon" ? "Seldon" : m === "seldon-laws" ? "Laws" : m === "chronos-bolt" ? "Chronos" : m === "auto-ets" ? "ETS" : m === "naive" ? "No chg." : m);
  const display = (m) => (m === D.meta.model ? modelName() : m === "seldon" ? "Seldon" : m === "seldon-laws" ? "Seldon laws" : m === "naive" ? '"No change"' : m);
  function assets() {
    return (D.outlook || []).filter((o) => o.domain === "markets" && o.fan && o.fan.length).map((o) => {
      const meta = (D.markets || {})[o.id] || {}, row = (D.series || []).find((r) => r.id === o.id) || {};
      const last = o.history[o.history.length - 1];
      const S = o.seldon && o.seldon.fan && o.seldon.fan.length ? o.seldon.fan : null;
      const k = Math.min(state.h, o.fan.length) - 1;
      const qm = o.fan[k].slice(1, 4), qs = S ? S[Math.min(k, S.length - 1)].slice(1, 4) : null;
      const models = meta.models || [];
      const best = models.find((m) => m[0] !== "naive") || null;
      const mine = models.find((m) => m[0] === D.meta.model), sel = models.find((m) => m[0] === "seldon");
      return {
        o, id: o.id, title: o.title, ticker: meta.ticker || o.id.toUpperCase(), last: last[1], lastDate: last[0],
        date: o.fan[k][0], steps: k + 1, qm, qs, S,
        move: qm[1] / last[1] - 1, lo: qm[0] / last[1] - 1, hi: qm[2] / last[1] - 1, up: pAbove(qm, last[1]),
        sMove: qs ? qs[1] / last[1] - 1 : null, sUp: qs ? pAbove(qs, last[1]) : null,
        rv: realizedVol(o), iv: impliedVol(qm, k + 1, o.id), sv: qs ? impliedVol(qs, k + 1, o.id) : null,
        skill: row.skill ?? (mine ? mine[1] : null), cover: row.coverage80 ?? (mine ? mine[3] : null), dir: row.direction ?? null,
        sSkill: sel ? sel[1] : null, best, models,
      };
    });
  }
  function marketsVerdict() {
    const m = (D.domains || []).find((r) => r.domain === "markets" && r.model === D.meta.model);
    const laws = (D.duel_laws || []).find((r) => r.domain === "markets");
    let text = m && m.skill !== null ? `on the backtest ${modelName()} removed ${m.skill > 0 ? (m.skill * 100).toFixed(1) + "%" : "none"} of the error of "no change" in markets` : "";
    if (laws && laws.series) text += `${text ? ", and " : ""}Seldon's crowd laws had less error than ${modelName()} on ${laws.wins} of ${laws.series} market series`;
    return text ? text + "." : "";
  }
  const pick = (a) => (state.who === "seldon" && a.qs ? { q: a.qs, move: a.sMove, up: a.sUp, vol: a.sv } : { q: a.qm, move: a.move, up: a.up, vol: a.iv });

  // ---------- render ----------
  function render(root, data, arg) {
    D = data; host = root;
    const [id, h] = String(arg || "").split(":");
    const list = assets();
    if (!list.length) {
      host.innerHTML = '<div class="vhead"><h1 id="markets-h">Markets desk</h1></div><div class="card"><div class="empty"><b>No market forecasts sealed yet.</b>They appear after the first run of <code>psychohistory predict</code>.</div></div>';
      return;
    }
    if (h && HORIZONS.some(([n]) => n === +h)) state.h = +h;
    if (id && list.some((a) => a.id === id)) state.id = id;
    if (!list.some((a) => a.id === state.id)) state.id = list[0].id;
    if (!state.compare.length) state.compare = list.slice(0, 3).map((a) => a.id);
    const maxSteps = Math.max(...list.map((a) => a.o.fan.length));
    host.innerHTML = `
      <div class="vhead">
        <h1 id="markets-h">Markets desk</h1>
        <p class="lede">Every market's sealed forecast at the horizon you choose, ${esc(modelName())} and Seldon side by side, with the volatility each one implies and how each model has done on that asset before. Sealed ${esc(list[0].o.made_on)}; data through ${esc(list[0].lastDate)}.</p>
      </div>
      <div class="mk-bar">
        <div class="chips" role="group" aria-label="Horizon" id="mk-h">${HORIZONS.filter(([n]) => n <= maxSteps).map(([n, l]) =>
          `<button class="chip" data-h="${n}" aria-pressed="${n === state.h}" title="${n} trading day${n > 1 ? "s" : ""} ahead">${l}</button>`).join("")}</div>
        <div class="chips" role="group" aria-label="Forecaster" id="mk-who">
          <button class="chip" data-who="model" aria-pressed="${state.who === "model"}"><span class="who" style="--c:var(--tfm)">${esc(modelName())}</span></button>
          <button class="chip" data-who="seldon" aria-pressed="${state.who === "seldon"}"><span class="who" style="--c:var(--seldon)">Seldon</span></button></div>
        <span class="mk-spacer"></span>
        <button class="btn small" id="mk-csv" title="The watchlist at this horizon, as a spreadsheet">Export CSV</button>
        <button class="btn small" id="mk-json" title="Every market's full fan, both forecasters, every step">Export JSON</button>
        <button class="btn small" id="mk-link" title="Copy a link to this asset and horizon">Copy link</button>
      </div>
      <div class="card"><header class="ph"><h2>Watchlist</h2><span class="pm">click a row for the detail · tick up to four to compare</span></header>
        <div class="table-wrap"><table class="mk-watch" id="mk-watch"></table></div>
        <p class="note">Move and range are the forecast's middle and 80% range at the horizon, against the last close. Vol is annualised: the forecast's own (read off its 80% range) against the market's last three months. Record is ${esc(modelName())}'s skill against "no change" on this asset's past windows, with the share of reality that landed inside its 80% range; Trust is the model with the least error there.</p></div>
      <div class="mk-grid">
        <div class="card detail mk-detail" id="mk-detail"></div>
        <div class="card" id="mk-side"></div>
      </div>
      <div class="mk-grid">
        <div class="card" id="mk-models"></div>
        <div class="card" id="mk-windows"></div>
      </div>
      <div class="card" id="mk-vol"></div>
      <div class="card" id="mk-compare"></div>
      <div class="card" id="mk-follow"></div>
      <p class="note">Forecasts are research, not investment advice. Markets sit close to a random walk: ${esc(marketsVerdict())} Chances beyond the forecast's 10th and 90th percentiles are a normal-shaped guess, capped at 2% and 98%.</p>`;
    host.querySelector("#mk-h").onclick = (e) => { const b = e.target.closest("button"); if (b) { state.h = +b.dataset.h; go(); } };
    host.querySelector("#mk-who").onclick = (e) => { const b = e.target.closest("button"); if (b) { state.who = b.dataset.who; go(); } };
    host.querySelector("#mk-csv").onclick = () => exportCsv(list);
    host.querySelector("#mk-json").onclick = () => exportJson();
    host.querySelector("#mk-link").onclick = (e) => copyLink(e.currentTarget);
    watch(list);
    detail(list.find((a) => a.id === state.id));
    compare(list);
    follow();
  }
  // Would following the forecasts have made money? (D.follow, built by psychohistory.follow)
  function follow() {
    const box = host.querySelector("#mk-follow"), F = D.follow;
    if (!F || !F.rows || !F.rows.length) { box.innerHTML = '<header class="ph"><h2>Would following the forecasts have made money?</h2></header><div class="empty">This appears after the first full backtest.</div>'; return; }
    const { fmt } = window.WPCharts;
    const steps = [...new Set(F.rows.map((r) => r.step))].sort((a, b) => a - b);
    if (!steps.includes(state.fstep)) state.fstep = steps[steps.length - 1];
    const W = { radiant: "Radiant", "timesfm-2.5": "TimesFM", seldon: "Seldon", "chronos-bolt": "Chronos-Bolt" };
    const C = { radiant: "var(--radiant)", "timesfm-2.5": "var(--tfm)", seldon: "var(--seldon)", "chronos-bolt": "var(--rival)" };
    const rows = F.rows.filter((r) => r.step === state.fstep).sort((a, b) => b.follow - a.follow);
    const oos = (F.oos || []).filter((r) => r.step === state.fstep);
    const word = (n) => (n === 5 ? "a week" : n === 20 ? "a month" : `${n} trading days`);
    const sp = (v) => `<span class="${v > 0.0005 ? "pos" : v < -0.0005 ? "neg" : ""}">${fmt.signedPct(v)}</span>`;
    const hold = rows.length ? rows[0].hold : 0;
    const luck = (t) => (t === null || t === undefined ? "–" : Math.abs(t) >= 2 ? `<b>${t.toFixed(1)}</b>` : `${t.toFixed(1)} <small class="dim">luck</small>`);
    box.innerHTML = `<header class="ph"><h2>Would following the forecasts have made money?</h2><span class="pm">${F.markets} markets · backtest ${esc(F.first)} to ${esc(F.last)} · ${fmt.pct(F.cost)} cost each way</span></header>
      <div class="mk-bar"><div class="chips" role="group" aria-label="Holding period" id="mk-fstep">${steps.map((n) =>
        `<button class="chip" data-fstep="${n}" aria-pressed="${n === state.fstep}">Hold ${word(n)}</button>`).join("")}</div></div>
      <p class="mk-verdict">${esc(F.verdict)}</p>
      <div id="mk-fchart"></div>
      <div class="table-wrap"><table class="mk-voltab"><thead><tr><th>Follow</th><th>Right</th><th>Per window</th><th>Long/short</th><th>vs holding (t)</th></tr></thead><tbody>
        <tr><td><span class="who" style="--c:var(--ink-3)">Hold every market</span></td><td class="dim">–</td><td>${sp(hold)}</td><td class="dim">–</td><td class="dim">yardstick</td></tr>
        ${rows.map((r) => `<tr><td><span class="who" style="--c:${C[r.model] || "var(--ink-2)"}">${esc(W[r.model] || r.model)}</span></td><td>${fmt.pct(r.hit)}</td><td>${sp(r.follow)}</td><td>${sp(r.longshort)}</td><td>${luck(r.t)}</td></tr>`).join("")}
      </tbody></table></div>
      ${oos.length ? `<p class="note"><b>Out of sample.</b> Choosing the odds needed to buy (50%, 55% or 60%) on the first half of the backtest and trading the second half: ${oos.map((r) => `${esc(W[r.model] || r.model)} ${sp(r.follow)}`).join(", ")} a window, against ${sp(oos[0].hold)} for holding.</p>` : ""}
      <p class="note">Each backtest window, every forecaster either held a market (its chance of a rise above 50%) or stayed in cash, paying ${fmt.pct(F.cost)} each way; long/short also bet against the markets it called lower. "Right" is how often it called the direction. The chart adds up what $100 staked on every window made. A t below 2 in size means the gap from holding could be luck. Following a forecast pays only if it is right more often than the market rises on its own: research, not investment advice.</p>`;
    box.querySelector("#mk-fstep").onclick = (e) => { const b = e.target.closest("button"); if (b) { state.fstep = +b.dataset.fstep; follow(); } };
    const curve = (F.curves || {})[String(state.fstep)] || {};
    const dates = curve.dates || [];
    const line = (k, color, label, dash) => ({ points: dates.map((d, i) => [d, curve[k][i]]), color, label, dash, width: k === "hold" ? 2.5 : 2 });
    const chart = box.querySelector("#mk-fchart");
    window.WPCharts.plot(chart, { x: "date", height: 240, right: 96, yFormat: (v) => `$${Math.round(v)}`,
      refs: [{ y: 0 }],
      lines: [line("hold", "var(--ink-2)", "Hold", "5 4"), ...Object.keys(W).filter((m) => curve[m]).map((m) => line(m, C[m], W[m]))] });
  }
  function go() { history.replaceState(null, "", `#markets/${state.id}:${state.h}`); render(host, D); }

  function watch(list) {
    const { fmt } = window.WPCharts;
    const cols = [["title", "Market"], ["last", "Last"], ["move", "Move"], ["range", "80% range"], ["up", "Chance up"],
      ["other", state.who === "seldon" ? modelName() : "Seldon"], ["vol", "Vol: fcst / real"], ["skill", "Record"], ["trust", "Trust"], ["cmp", "+"]];
    const val = (a, k) => ({ title: a.title, last: a.last, move: pick(a).move, range: pick(a).q[2] / pick(a).q[0], up: pick(a).up,
      other: state.who === "seldon" ? a.move : a.sMove, vol: pick(a).vol, skill: a.skill, trust: a.best ? a.best[1] : null }[k]);
    if (state.sort) list = list.slice().sort((x, y) => { const p = val(x, state.sort), q = val(y, state.sort); return (p > q ? 1 : p < q ? -1 : 0) * state.dir; });
    const cls = (v, edge = 0) => (v === null || v === undefined || Math.abs(v) < edge ? "dim" : v > 0 ? "pos" : "neg");
    const t = host.querySelector("#mk-watch");
    t.innerHTML = `<thead><tr>${cols.map(([k, l]) => k === "cmp" ? `<th>${l}</th>` : `<th><button data-k="${k}" aria-sort="${state.sort === k ? (state.dir > 0 ? "ascending" : "descending") : "none"}">${l}${state.sort === k ? (state.dir > 0 ? " ▲" : " ▼") : ""}</button></th>`).join("")}</tr></thead><tbody>` +
      list.map((a) => {
        const p = pick(a), other = state.who === "seldon" ? a.move : a.sMove;
        const agree = other !== null && Math.sign(other) === Math.sign(p.move);
        const span = Math.max(0.0001, Math.abs(p.q[0] / a.last - 1), Math.abs(p.q[2] / a.last - 1));
        const x = (v) => (50 + (v / a.last - 1) / span * 46).toFixed(1) + "%";
        return `<tr data-id="${esc(a.id)}" tabindex="0" aria-selected="${a.id === state.id}">
          <td><b>${esc(a.title)}</b><small>${esc(a.ticker)}</small></td>
          <td>${fmt.num(a.last)}</td>
          <td class="${cls(p.move, 0.0005)}">${fmt.signedPct(p.move)}</td>
          <td><span class="mk-range" title="${fmt.num(p.q[0])} to ${fmt.num(p.q[2])}"><i style="left:${x(p.q[0])};right:calc(100% - ${x(p.q[2])})"></i><b style="left:${x(p.q[1])}"></b></span>${fmt.signedPct(p.q[0] / a.last - 1).replace("%", "")} / ${fmt.signedPct(p.q[2] / a.last - 1)}</td>
          <td class="p"><span class="pbar" style="--p:${Math.round(p.up * 100)}%;--c:${p.up > 0.55 ? "var(--up)" : p.up < 0.45 ? "var(--down)" : "var(--ink-3)"}"><i></i>${fmt.pct(p.up)}</span></td>
          <td class="${cls(other, 0.0005)}" title="${agree ? "Both expect the same direction" : "The two disagree on direction"}">${fmt.signedPct(other)} ${other === null ? "" : agree ? '<span class="dim">✓</span>' : '<span class="neg">≠</span>'}</td>
          <td>${p.vol === null ? "–" : fmt.pct(p.vol)} / ${a.rv === null ? "–" : fmt.pct(a.rv)}</td>
          <td><span class="${cls(a.skill, 0.02)}">${fmt.signedPct(a.skill)}</span> <span class="dim">· ${fmt.pct(a.cover)}</span></td>
          <td>${a.best ? `<span class="who" style="--c:${a.best[0] === D.meta.model ? "var(--tfm)" : /^seldon/.test(a.best[0]) ? "var(--seldon)" : "var(--ink-3)"}" title="${esc(display(a.best[0]))}: ${fmt.signedPct(a.best[1])} against &quot;no change&quot;">${esc(short(a.best[0]))}</span>` : "–"}</td>
          <td><input type="checkbox" data-cmp="${esc(a.id)}" aria-label="Compare ${esc(a.title)}" ${state.compare.includes(a.id) ? "checked" : ""}></td></tr>`;
      }).join("") + "</tbody>";
    t.onclick = (e) => {
      const b = e.target.closest("button[data-k]");
      if (b) { const k = b.dataset.k; state.dir = state.sort === k ? -state.dir : -1; state.sort = k; watch(assets()); return; }
      const c = e.target.closest("input[data-cmp]");
      if (c) {
        const id = c.dataset.cmp;
        state.compare = c.checked ? [...state.compare.filter((x) => x !== id), id].slice(-4) : state.compare.filter((x) => x !== id);
        watch(assets()); compare(assets()); return;
      }
      const tr = e.target.closest("tr[data-id]");
      if (tr) choose(tr.dataset.id);
    };
    t.onkeydown = (e) => {
      const tr = e.target.closest("tr[data-id]");
      if (!tr) return;
      if (e.key === "Enter") choose(tr.dataset.id);
      else if (e.key === "ArrowDown" || e.key === "ArrowUp") { const sib = e.key === "ArrowDown" ? tr.nextElementSibling : tr.previousElementSibling; if (sib) sib.focus(); e.preventDefault(); }
    };
  }
  function choose(id) {
    state.id = id; state.level = null;
    history.replaceState(null, "", `#markets/${id}:${state.h}`);
    host.querySelectorAll("#mk-watch tr[data-id]").forEach((tr) => tr.setAttribute("aria-selected", tr.dataset.id === id));
    detail(assets().find((a) => a.id === id));
  }

  function detail(a) {
    const { plot, legend, fmt } = window.WPCharts;
    const o = a.o, last = [a.lastDate, a.last], name = modelName();
    const box = host.querySelector("#mk-detail");
    box.innerHTML = `<header class="ph"><h2>${esc(a.title)} <span class="dim">${esc(a.ticker)}</span></h2><span class="pm">${a.steps} step${a.steps > 1 ? "s" : ""} ahead · ${esc(a.date)}</span></header>
      <dl class="facts">
        <div><dt>Last close</dt><dd>${fmt.num(a.last)}</dd></div>
        <div><dt>${esc(name)} middle</dt><dd style="color:var(--tfm)">${fmt.num(a.qm[1])} <small>${fmt.signedPct(a.move)}</small></dd></div>
        <div><dt>Seldon middle</dt><dd style="color:var(--seldon)">${a.qs ? `${fmt.num(a.qs[1])} <small>${fmt.signedPct(a.sMove)}</small>` : "–"}</dd></div>
        <div><dt>Chance up · ${esc(name)} / Seldon</dt><dd>${fmt.pct(a.up)} / ${a.sUp === null ? "–" : fmt.pct(a.sUp)}</dd></div>
        <div><dt>Downside, 1 in 10</dt><dd class="neg">${fmt.signedPct(a.lo)}</dd></div>
      </dl>
      <div id="mk-chart"></div><div id="mk-legend"></div>
      <div class="actions"><a class="btn small" href="#series/${esc(a.id)}">Every past forecast for ${esc(a.title)}</a> <a class="btn small" href="#studio/${esc(a.id)}">Seal your own call</a></div>`;
    const hist = o.history.slice(-Math.max(60, 3 * o.fan.length));
    const fan = o.fan, S = a.S;
    plot(box.querySelector("#mk-chart"), {
      x: "date", height: 320, left: 58, right: 80, label: `${a.title}: history and forecasts`,
      bands: [{ points: [[last[0], last[1], last[1]]].concat(fan.map((f) => [f[0], f[1], f[3]])) },
        ...(S ? [{ points: [[last[0], last[1], last[1]]].concat(S.map((f) => [f[0], f[1], f[3]])), color: "transparent", stroke: "var(--seldon)", hatch: false, edge: "2 3" }] : [])],
      lines: [{ points: hist, color: "var(--ink)", width: 1.6, name: "close" },
        { points: [last].concat(fan.map((f) => [f[0], f[2]])), color: "var(--tfm)", width: 2, name, label: name },
        ...(S ? [{ points: [last].concat(S.map((f) => [f[0], f[2]])), color: "var(--seldon)", width: 2, name: "Seldon", label: "Seldon" }] : [])],
      refs: [{ x: a.date, label: HORIZONS.find(([n]) => n === state.h) ? HORIZONS.find(([n]) => n === state.h)[1] : "" },
        ...(state.level ? [{ y: state.level, label: fmt.num(state.level), color: "var(--you)" }] : [])],
    });
    legend(box.querySelector("#mk-legend"), [{ name: "Close", color: "var(--ink)" }, { name: `${name} 80% range`, color: "var(--tfm)", kind: "band" },
      ...(S ? [{ name: "Seldon 80% range", color: "var(--seldon)", kind: "dash" }] : [])]);
    side(a); models(a); windows(a); vol(a);
  }

  // How far the market is likely to swing: GARCH, EWMA, last month's and what each range implies,
  // with each forecaster's volatility record on this asset (QLIKE skill against last month's).
  function bestText(best, name) {
    const [w, m] = best.map((b) => (b ? b[0] : null));
    if (w && w === m) return `${esc(name(w))} has the best record here, a week and a month ahead`;
    const parts = [[w, "week"], [m, "month"]].filter(([b]) => b).map(([b, sp]) => `${esc(name(b))} has the best ${sp}-ahead record here`);
    return parts.join(", ") || "no forecaster has enough windows here yet";
  }
  function vol(a) {
    const { fmt } = window.WPCharts;
    const box = host.querySelector("#mk-vol"), V = ((D.volatility || {}).markets || {})[a.id] || {};
    const now = V.now, spans = ["1 week", "1 month"];
    if (!now) { box.innerHTML = '<header class="ph"><h2>Volatility outlook</h2></header><div class="empty">No volatility forecast for this market yet.</div>'; return; }
    const fc = {}; // model -> span -> annualised vol
    now.rows.forEach(([m, sp, v]) => ((fc[m] = fc[m] || {})[sp] = v));
    now.steps.forEach((n, i) => {
      const k = Math.min(n, a.o.fan.length) - 1;
      if (k >= 0) (fc[D.meta.model] = fc[D.meta.model] || {})[spans[i]] = impliedVol(a.o.fan[k].slice(1, 4), k + 1, a.id);
      if (a.S && k < a.S.length) (fc.seldon = fc.seldon || {})[spans[i]] = impliedVol(a.S[k].slice(1, 4), k + 1, a.id);
    });
    const rec = {};
    (V.record || []).forEach(([m, sp, sk, n, miss]) => ((rec[m] = rec[m] || {})[sp] = [sk, n, miss]));
    const order = ["garch", "ewma", D.meta.model, "seldon", "last-month"].filter((m) => fc[m]);
    const name = (m) => (m === "garch" ? "GARCH(1,1)" : m === "ewma" ? "EWMA (λ 0.94)" : m === "last-month" ? "Last month's" : display(m) + " range");
    const col = (m) => (m === D.meta.model ? "var(--tfm)" : m === "seldon" ? "var(--seldon)" : m === "garch" ? "var(--markets)" : m === "ewma" ? "var(--you)" : "var(--ink-3)");
    const top = Math.max(...order.flatMap((m) => spans.map((sp) => fc[m][sp] || 0)), a.rv || 0) || 1;
    const bar = (v, c) => (v === null || v === undefined ? '<span class="dim">–</span>' : `<span class="mk-vbar"><i style="width:${(100 * v / top).toFixed(1)}%;background:${c}"></i></span><b>${fmt.pct(v)}</b>`);
    const k = (v) => (v === null || v === undefined ? "dim" : Math.abs(v) < 0.02 ? "" : v > 0 ? "pos" : "neg");
    const skill = (m, sp) => { const r = (rec[m] || {})[sp]; return r ? `<span class="${k(r[0])}">${m === "last-month" ? "baseline" : fmt.signedPct(r[0])}</span> <small class="dim">${r[1]}</small>` : '<span class="dim">–</span>'; };
    const best = spans.map((sp) => Object.entries(rec).filter(([m, r]) => r[sp] && m !== "last-month" && r[sp][1] >= 8).sort((x, y) => y[1][sp][0] - x[1][sp][0])[0]);
    box.innerHTML = `<header class="ph"><h2>Volatility outlook for ${esc(a.title)}</h2><span class="pm">annualised · data through ${esc(now.date)}</span></header>
      <div class="table-wrap"><table class="mk-voltab"><thead><tr><th>Forecaster</th><th>Next week</th><th>Next month</th><th>Record, week</th><th>Record, month</th></tr></thead><tbody>${
        order.map((m) => `<tr><td><span class="who" style="--c:${col(m)}">${esc(name(m))}</span></td><td>${bar(fc[m]["1 week"], col(m))}</td><td>${bar(fc[m]["1 month"], col(m))}</td><td>${skill(m, "1 week")}</td><td>${skill(m, "1 month")}</td></tr>`).join("")}</tbody></table></div>
      <p class="note">Prices are close to a random walk, but how much they swing is not: calm follows calm and storms follow storms, so volatility is the part of a market that can be forecast. Record is each forecaster's QLIKE skill against last month's volatility on this market's past windows (small grey number: how many); ${bestText(best, name)}. Every week these forecasts are sealed and scored in the <a href="#monitor">Monitor</a>.</p>`;
  }

  // Price ladder and the odds calculator for the selected market at the chosen horizon.
  function side(a) {
    const { fmt } = window.WPCharts;
    const box = host.querySelector("#mk-side"), name = modelName();
    const rungs = [[Z90, "90th"], [Z75, "75th"], [0, "50th"], [-Z75, "25th"], [-Z90, "10th"]];
    const level = state.level ?? Number((a.last * 1.05).toPrecision(4));
    box.innerHTML = `<header class="ph"><h2>Price ladder</h2><span class="pm">${esc(a.date)}</span></header>
      <table class="mk-ladder"><thead><tr><th>Percentile</th><th style="color:var(--tfm)">${esc(name)}</th><th style="color:var(--seldon)">Seldon</th></tr></thead><tbody>${
        rungs.map(([z, l]) => `<tr><td>${l}${z === 0 ? " (middle)" : ""}</td><td>${fmt.num(quantile(a.qm, z))}</td><td>${a.qs ? fmt.num(quantile(a.qs, z)) : "–"}</td></tr>`).join("")}</tbody></table>
      <header class="ph" style="margin-top:14px"><h2>Odds calculator</h2></header>
      <label class="mk-calc">Chance it closes above <input type="number" id="mk-level" step="any" value="${level}" aria-label="Price level"></label>
      <div class="mk-odds" id="mk-odds"></div>
      <div class="chips mk-moves" role="group" aria-label="Quick levels">${[-0.1, -0.05, 0.05, 0.1].map((m) => `<button class="chip" data-m="${m}">${m > 0 ? "+" : "−"}${Math.abs(m * 100)}%</button>`).join("")}</div>`;
    const input = box.querySelector("#mk-level");
    const paint = () => {
      const L = parseFloat(input.value);
      if (!isFinite(L)) { box.querySelector("#mk-odds").innerHTML = ""; return; }
      const pm = pAbove(a.qm, L), ps = a.qs ? pAbove(a.qs, L) : null;
      box.querySelector("#mk-odds").innerHTML = `<p><span class="who" style="--c:var(--tfm)">${esc(name)}</span> <b>${fmt.pct(pm)}</b></p>
        <p><span class="who" style="--c:var(--seldon)">Seldon</span> <b>${ps === null ? "–" : fmt.pct(ps)}</b></p>
        <p class="note" style="margin:4px 0 0">${fmt.signedPct(L / a.last - 1)} from the last close, by ${esc(a.date)}. Below it: ${fmt.pct(1 - pm)}${ps === null ? "" : " / " + fmt.pct(1 - ps)}.</p>`;
    };
    input.oninput = paint;
    input.onchange = () => { state.level = parseFloat(input.value) || null; detail(a); };
    box.querySelector(".mk-moves").onclick = (e) => { const b = e.target.closest("button"); if (!b) return; state.level = Number((a.last * (1 + +b.dataset.m)).toPrecision(5)); detail(a); };
    paint();
  }

  // Every model's record on this asset: whom to trust here.
  function models(a) {
    const { fmt } = window.WPCharts;
    const box = host.querySelector("#mk-models");
    const rows = a.models;
    box.innerHTML = `<header class="ph"><h2>Who to trust on ${esc(a.title)}</h2><span class="pm">backtest on its past windows</span></header>` + (rows.length
      ? `<div class="table-wrap"><table><thead><tr><th>Model</th><th>Skill</th><th>Range skill</th><th>In 80% range</th><th>Direction</th><th>Brier</th></tr></thead><tbody>${rows.map((r) => {
          const c = r[0] === D.meta.model ? "var(--tfm)" : /^seldon/.test(r[0]) ? "var(--seldon)" : "var(--ink-3)";
          const k = (v, e = 0.02) => (v === null ? "dim" : Math.abs(v) < e ? "" : v > 0 ? "pos" : "neg");
          return `<tr><td><span class="who" style="--c:${c}">${esc(display(r[0]))}</span></td><td class="${k(r[1])}">${fmt.signedPct(r[1])}</td><td class="${k(r[2])}">${fmt.signedPct(r[2])}</td>
            <td>${fmt.pct(r[3])}</td><td>${fmt.pct(r[4])}</td><td>${r[5] === null ? "–" : r[5].toFixed(3)}</td></tr>`;
        }).join("")}</tbody></table></div>
        <p class="note">Skill is the share of error removed against "no change" (above +2% counts as an edge); range skill scores the whole forecast range; an honest 80% range catches about 80%; a Brier score of 0.25 is a coin flip.</p>`
      : '<div class="empty">No backtest for this market yet.</div>');
  }

  // The newest past windows on this asset: what the model said and what happened.
  function windows(a) {
    const { fmt } = window.WPCharts;
    const box = host.querySelector("#mk-windows"), T = (D.track || {})[a.id];
    if (!T || !T.windows.length) { box.innerHTML = '<header class="ph"><h2>Recent calls</h2></header><div class="empty">No past windows yet.</div>'; return; }
    const ev = Object.fromEntries(((D.evidence || {})[a.id] || []).map((r) => [r[0], r]));
    const rows = T.windows.slice(-6).reverse().map(([origin, at, q10, q50, q90]) => {
      const n = q50.length, before = at > 0 ? T.actual[at - 1] : null, end = T.actual[at + n - 1];
      const act = T.actual.slice(at, at + n), inside = act.filter((v, i) => v !== null && v >= q10[i] && v <= q90[i]).length / Math.max(1, act.length);
      const e = ev[origin] || [], said = before ? q50[n - 1] / before - 1 : null, did = before && end !== null ? end / before - 1 : null;
      const called = e[3] === undefined || e[4] === undefined || e[3] === null || e[4] === null ? null : (e[3] > 0.5) === (e[4] === 1);
      return `<tr><td>${esc(origin)}</td><td>${fmt.signedPct(said)}</td><td class="${did > 0 ? "pos" : did < 0 ? "neg" : ""}">${fmt.signedPct(did)}</td><td>${fmt.pct(inside)}</td>
        <td>${called === null ? '<span class="dim">–</span>' : called ? '<span class="pos">✓</span>' : '<span class="neg">✗</span>'}</td></tr>`;
    });
    box.innerHTML = `<header class="ph"><h2>Recent calls</h2><span class="pm">${esc(modelName())}, newest first</span></header>
      <div class="table-wrap"><table><thead><tr><th>Made</th><th>Said</th><th>Did</th><th>In range</th><th>Dir.</th></tr></thead><tbody>${rows.join("")}</tbody></table></div>`;
  }

  // Up to four markets, each rebased to 100 at its last close: history and expected path.
  function compare(list) {
    const { plot, legend } = window.WPCharts;
    const box = host.querySelector("#mk-compare");
    const chosen = state.compare.map((id) => list.find((a) => a.id === id)).filter(Boolean);
    box.innerHTML = `<header class="ph"><h2>Compare</h2><span class="pm">rebased to 100 at the last close · ${state.who === "seldon" ? "Seldon" : esc(modelName())}'s middle and 80% range</span></header>` +
      (chosen.length ? '<div id="mk-cmp-chart"></div><div id="mk-cmp-legend"></div>' : '<div class="empty">Tick up to four markets in the watchlist to compare them.</div>');
    if (!chosen.length) return;
    const lines = [], bands = [];
    chosen.forEach((a, i) => {
      const base = a.last, color = COMPARE[i], fan = state.who === "seldon" && a.S ? a.S : a.o.fan;
      const hist = a.o.history.slice(-40).map((p) => [p[0], (p[1] / base) * 100]);
      const k = Math.min(state.h, fan.length);
      lines.push({ points: hist, color, width: 1.4, opacity: 0.55, name: a.title });
      lines.push({ points: [[a.lastDate, 100]].concat(fan.slice(0, k).map((f) => [f[0], (f[2] / base) * 100])), color, width: 2.2, name: a.title, label: a.ticker });
      bands.push({ points: [[a.lastDate, 100, 100]].concat(fan.slice(0, k).map((f) => [f[0], (f[1] / base) * 100, (f[3] / base) * 100])), color: "transparent", stroke: color, hatch: false, edge: "2 3" });
    });
    plot(box.querySelector("#mk-cmp-chart"), { x: "date", height: 300, left: 48, right: 84, label: "Markets compared, rebased to 100", lines, bands, refs: [{ y: 100, color: "var(--line-2)" }] });
    legend(box.querySelector("#mk-cmp-legend"), chosen.map((a, i) => ({ name: `${a.title} (${a.ticker})`, color: COMPARE[i] })));
  }

  // ---------- export ----------
  function download(name, text, type) {
    const url = URL.createObjectURL(new Blob([text], { type }));
    const link = Object.assign(document.createElement("a"), { href: url, download: name });
    document.body.append(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  const csvCell = (v) => (v === null || v === undefined ? "" : typeof v === "number" ? String(+v.toPrecision(8)) : /[",\n]/.test(v) ? `"${String(v).replace(/"/g, '""')}"` : String(v));
  function exportCsv(list) {
    const head = ["market", "ticker", "last_date", "last", "target_date", "steps", "model", "q10", "q50", "q90", "move", "p_up", "seldon_q10", "seldon_q50", "seldon_q90", "seldon_move", "seldon_p_up", "implied_vol", "realized_vol", "backtest_skill", "backtest_in_range", "most_trusted"];
    const rows = list.map((a) => [a.title, a.ticker, a.lastDate, a.last, a.date, a.steps, D.meta.model, ...a.qm, a.move, a.up,
      ...(a.qs || [null, null, null]), a.sMove, a.sUp, a.iv, a.rv, a.skill, a.cover, a.best ? a.best[0] : null]);
    download(`world-predictor-markets-${list[0].o.made_on}-${state.h}d.csv`, [head, ...rows].map((r) => r.map(csvCell).join(",")).join("\n") + "\n", "text/csv");
  }
  function exportJson() {
    const out = assets().map((a) => ({ market: a.title, ticker: a.ticker, sealed: a.o.made_on, last_date: a.lastDate, last: a.last,
      model: D.meta.model, fan: a.o.fan.map(([d, lo, mid, hi]) => ({ date: d, q10: lo, q50: mid, q90: hi })),
      seldon: a.S ? a.S.map(([d, lo, mid, hi]) => ({ date: d, q10: lo, q50: mid, q90: hi })) : null,
      record: a.models.map((r) => ({ model: r[0], skill: r[1], range_skill: r[2], in_range: r[3], direction: r[4], brier: r[5] })) }));
    download(`world-predictor-markets-${D.meta.generated}.json`, JSON.stringify({ generated: D.meta.generated, demo: !!D.meta.demo, markets: out }, null, 1), "application/json");
  }
  function copyLink(btn) {
    const url = location.href.split("#")[0] + `#markets/${state.id}:${state.h}`;
    const done = () => { const t = btn.textContent; btn.textContent = "Copied"; setTimeout(() => (btn.textContent = t), 1400); };
    if (navigator.clipboard) navigator.clipboard.writeText(url).then(done, () => prompt("Copy this link", url)); else prompt("Copy this link", url);
  }

  window.WPMarkets = { render, pAbove, quantile };
})();
