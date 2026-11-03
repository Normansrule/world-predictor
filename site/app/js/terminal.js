// World terminal: the whole world on one screen, run from a command line.
// Every series the project forecasts with its last value, how unusual its latest move is, the sealed
// forecast, both models' record on it and the newest headlines about it; a focus panel for one series
// where you can seal your own call; your book of calls, each settled for good once the real value
// arrives, so the record holds for years (export it to keep it, import it on another device); and
// the sealed forecasts as they open, against what really happened.
// Reads D.outlook, D.series, D.markets, D.opened, D.monitor, D.volatility, D.wire and D.events.
(function () {
  const STORE = "wp-calls-v1"; // shared with the Forecast Studio
  const WATCH = "wp-watch-v1";
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const AREAS = { news: "NEWS", markets: "MKT", tech: "TECH" };
  const CODES = { sp500: "SPX", msci_world: "MXWO", nasdaq100: "NDX", gold: "XAU", silver: "XAG", oil_wti: "WTI", copper: "HG", bitcoin: "BTC", us10y: "UST10", tlt: "TLT", vix: "VIX",
    news_composite: "N:ALL", tech_composite: "T:ALL", adoption_internet: "T:NET", adoption_solar: "T:SOLAR", adoption_wind: "T:WIND" };
  const SETTLE_DAYS = 7; // a call settles on the first real value within a week of its date
  const state = { area: "all", focus: null, watchOnly: false, msg: "", allOdds: false };
  let D = null, host = null;

  // ---------- storage ----------
  const read = (key, blank) => { try { return JSON.parse(localStorage.getItem(key)) ?? blank; } catch (e) { return blank; } };
  const write = (key, v) => { try { localStorage.setItem(key, JSON.stringify(v)); return true; } catch (e) { return false; } };

  // ---------- numbers ----------
  const code = (o) => CODES[o.id] || o.id.replace(/^news_/, "N:").replace(/^wiki_/, "T:").toUpperCase();
  const name = () => (/^timesfm/.test(D.meta.model) ? "TimesFM" : D.meta.model);
  const lastOf = (o) => o.history[o.history.length - 1];
  const perWeek = (o) => (((D.markets || {})[o.id] || {}).freq === "B" ? 5 : 7);
  // Yearly series (adoption curves) have no "latest week".
  const yearly = (o) => o.history.length > 1 && Date.parse(lastOf(o)[0]) - Date.parse(o.history[o.history.length - 2][0]) > 200 * 864e5;
  function change(o, n) {
    const h = o.history, a = h[h.length - 1 - n], b = h[h.length - 1];
    return a && a[1] ? b[1] / a[1] - 1 : null;
  }
  // How unusual the latest week is, in standard deviations: a market's weekly return against its
  // own weekly volatility, an attention series' level against its previous four weeks.
  function sigma(o) {
    const v = o.history.map((p) => p[1]).filter((x) => x !== null);
    const n = perWeek(o);
    if (v.length < 30) return null;
    if (o.domain === "markets") {
      const r = v.slice(1).map((x, i) => Math.log(x / v[i])).filter(isFinite);
      const sd = Math.sqrt(r.reduce((a, b) => a + b * b, 0) / r.length);
      const week = Math.log(v[v.length - 1] / v[v.length - 1 - n]);
      return sd > 0 ? week / (sd * Math.sqrt(n)) : null;
    }
    const base = v.slice(-29, -1), m = base.reduce((a, b) => a + b, 0) / base.length;
    const sd = Math.sqrt(base.reduce((a, b) => a + (b - m) ** 2, 0) / (base.length - 1));
    return sd > 0 ? (v[v.length - 1] - m) / sd : null;
  }
  function rows() {
    const watch = new Set(read(WATCH, []));
    return (D.outlook || []).filter((o) => o.history && o.history.length && o.fan && o.fan.length).map((o) => {
      const s = (D.series || []).find((r) => r.id === o.id) || {}, f = o.fan[o.fan.length - 1], last = lastOf(o)[1];
      const opened = (D.opened || []).filter((r) => r[0] === o.id && r[1] === D.meta.model);
      const wire = ((D.wire || {}).topics || {})[o.id];
      return { o, id: o.id, code: code(o), title: o.title, area: o.domain, last, w: yearly(o) ? null : change(o, perWeek(o)), z: yearly(o) ? null : sigma(o),
        mid: f[2] / last - 1, lo: f[1] / last - 1, hi: f[3] / last - 1, by: f[0], up: o.p_up, skill: s.skill ?? null, cover: s.coverage80 ?? null,
        live: opened.length ? opened.filter((r) => r[10]).length / opened.length : null, liveN: opened.length,
        news: wire ? wire.articles.length : 0, watched: watch.has(o.id) };
    });
  }

  // ---------- your book ----------
  function book() { return read(STORE, []); }
  // Settle every open call whose date has a real value in this data file, and keep the result in the
  // call itself: next year's data file will no longer carry this week's values, but the book will.
  function settle(calls, data = D) {
    let changed = false;
    calls.forEach((c) => {
      if (c.settled) return;
      const o = (data.outlook || []).find((x) => x.id === c.series);
      const hit = o && o.history.find((p) => p[0] >= c.date);
      if (!hit || (Date.parse(hit[0]) - Date.parse(c.date)) / 864e5 > SETTLE_DAYS) return;
      c.settled = { actual: hit[1], on: hit[0], data: data.meta.generated };
      changed = true;
    });
    if (changed) write(STORE, calls);
    return calls;
  }
  function verdict(c) {
    if (!c.settled) return null;
    const a = c.settled.actual, err = (v) => Math.abs(v - a), inside = (r) => a >= r[0] && a <= r[2];
    const out = { actual: a, on: c.settled.on, you: err(c.value), tfm: err(c.tfm[1]), seldon: c.seldon ? err(c.seldon[1]) : null,
      youIn: inside([c.lo, c.value, c.hi]), tfmIn: inside(c.tfm), seldonIn: c.seldon ? inside(c.seldon) : null };
    out.best = [["You", out.you], [name(), out.tfm], ["Seldon", out.seldon]].filter((x) => x[1] !== null).reduce((p, q) => (q[1] < p[1] ? q : p))[0];
    return out;
  }
  async function digest(text) {
    try {
      const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
      return [...new Uint8Array(buf)].slice(0, 6).map((b) => b.toString(16).padStart(2, "0")).join("");
    } catch (e) {
      let h = 0x811c9dc5;
      for (let i = 0; i < text.length; i++) { h ^= text.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; }
      return h.toString(16).padStart(8, "0");
    }
  }
  // The call as it was sealed, in the order the Studio and the terminal write it.
  const sealedPart = (c) => ({ series: c.series, title: c.title, date: c.date, step: c.step, made_on: c.made_on, last: c.last,
    value: c.value, lo: c.lo, hi: c.hi, tfm: c.tfm, seldon: c.seldon, sealed_at: c.sealed_at });
  async function intact(c) { return (await digest(JSON.stringify(sealedPart(c)))) === c.fingerprint; }

  // ---------- render ----------
  function render(root, data, arg) {
    D = data; host = root;
    const all = rows();
    if (!all.length) { host.innerHTML = '<div class="vhead"><h1 id="terminal-h">World terminal</h1></div><div class="card"><div class="empty"><b>Nothing sealed yet.</b>The terminal opens after the first run of <code>psychohistory predict</code>.</div></div>'; return; }
    if (arg) { const hit = find(arg); if (hit) state.focus = hit.id; }
    if (!all.some((r) => r.id === state.focus)) state.focus = (all.find((r) => r.id === "sp500") || all[0]).id;
    const M = D.monitor || {}, wire = D.wire || {};
    host.innerHTML = `
      <div class="vhead tm-head">
        <h1 id="terminal-h">World terminal</h1>
        <p class="lede">The world on one screen: every series ${esc(name())} and Seldon forecast, what moved, what the news says, and every call you seal, scored against reality for as long as you keep the book.</p>
      </div>
      <div class="tm">
        <form class="tm-cmd" id="tm-cmd" autocomplete="off">
          <label for="tm-in"><span class="tm-prompt">WP&gt;</span></label>
          <input id="tm-in" spellcheck="false" placeholder="type a code and press Enter: GOLD, SPX, N:WAR, BOOK, HELP" aria-describedby="tm-msg">
          <button class="tm-go" type="submit">GO</button>
          <div class="tm-keys" role="group" aria-label="Screens">${[["all", "WORLD"], ["markets", "MKT"], ["news", "NEWS"], ["tech", "TECH"]].map(([k, l]) =>
            `<button type="button" class="tm-key" data-area="${k}" aria-pressed="${state.area === k && !state.watchOnly}">${l}</button>`).join("")}
            <button type="button" class="tm-key" data-watch="1" aria-pressed="${state.watchOnly}">WATCH</button>
            <button type="button" class="tm-key" data-cmd="ODDS">ODDS</button><button type="button" class="tm-key" data-cmd="BOOK">BOOK</button><button type="button" class="tm-key" data-cmd="HELP">HELP</button></div>
        </form>
        <p class="tm-msg" id="tm-msg" aria-live="polite">${esc(state.msg || `Data through ${lastOf(all[0].o)[0]} · forecasts sealed ${all[0].o.made_on} · ${(M.forecasts || 0).toLocaleString("en")} sealed forecasts scored so far · wire ${wire.fetched ? "fetched " + wire.fetched : "not fetched yet"}`)}</p>
        <div class="tm-grid">
          <div class="tm-pane tm-board"><header><h2>World monitor</h2><span id="tm-board-sub"></span></header><div class="table-wrap"><table id="tm-table"></table></div></div>
          <div class="tm-pane tm-side"><header><h2>Movers</h2><span>latest week, in σ</span></header><div id="tm-movers"></div>
            <header class="tm-sub"><h2>Just opened</h2><span>sealed forecasts against what happened</span></header><div id="tm-opened"></div></div>
          <div class="tm-pane tm-focus" id="tm-focus"></div>
          <div class="tm-pane tm-wire" id="tm-wire"></div>
          <div class="tm-pane tm-events" id="tm-events"></div>
          <div class="tm-pane tm-book" id="tm-book"></div>
          <div class="tm-pane tm-score" id="tm-score"></div>
        </div>
        <p class="note">Research, not investment advice. σ compares the latest week with the series' own usual week. Record is ${esc(name())}'s backtest skill against "no change" (above +2% is an edge); Live is the share of its sealed forecasts so far that landed inside their 80% range. Your book lives in this browser: export it now and then, and import it anywhere, to keep your record for years.</p>
      </div>`;
    const form = host.querySelector("#tm-cmd"), input = host.querySelector("#tm-in");
    form.onsubmit = (e) => { e.preventDefault(); run(input.value); input.value = ""; };
    form.querySelector(".tm-keys").onclick = (e) => {
      const b = e.target.closest("button"); if (!b) return;
      if (b.dataset.area) { state.area = b.dataset.area; state.watchOnly = false; state.msg = ""; render(host, D); }
      else if (b.dataset.watch) { state.watchOnly = !state.watchOnly; render(host, D); }
      else run(b.dataset.cmd);
    };
    board(all); movers(all); opened(); focus(all.find((r) => r.id === state.focus)); eventsPane(); scoreboard(); paintBook();
  }

  function find(text) {
    const q = String(text).trim().toUpperCase();
    return rows().find((r) => r.code === q || r.id.toUpperCase() === q || r.title.toUpperCase() === q)
      || rows().find((r) => r.title.toUpperCase().includes(q) || r.code.includes(q));
  }
  function say(text) { state.msg = text; const m = host.querySelector("#tm-msg"); if (m) m.textContent = text; }
  function run(raw) {
    const text = String(raw || "").trim(), [head, ...rest] = text.toUpperCase().split(/\s+/);
    if (!head) return;
    const area = { WORLD: "all", ALL: "all", MKT: "markets", MARKETS: "markets", NEWS: "news", TECH: "tech" }[head];
    if (area) { state.area = area; state.watchOnly = false; state.msg = ""; render(host, D); return; }
    if (head === "HELP" || head === "?") { say("Codes: SPX NDX MXWO AAPL NVDA TSLA XOM XAU XAG WTI HG BTC UST10 TLT VIX · N:WAR N:ELECTION … · T:AI T:LLM … · screens WORLD MKT NEWS TECH WATCH · ODDS (event odds) · WATCH / UNWATCH the focus · CALL <value> fills your call · BOOK · MON (monitor) · DESK (Markets desk) · <code> GO"); return; }
    if (head === "ODDS" || head === "EVENTS") { host.querySelector("#tm-events").scrollIntoView({ behavior: "smooth", block: "start" }); return; }
    if (head === "BOOK") { host.querySelector("#tm-book").scrollIntoView({ behavior: "smooth", block: "start" }); return; }
    if (head === "MON" || head === "MONITOR") { location.hash = "#monitor"; return; }
    if (head === "DESK") { location.hash = "#markets" + (rows().find((r) => r.id === state.focus && r.area === "markets") ? "/" + state.focus + ":20" : ""); return; }
    if (head === "WATCH" || head === "UNWATCH") {
      const id = rest.length ? (find(rest.join(" ")) || {}).id : state.focus, list = new Set(read(WATCH, []));
      if (!id) { say(`No series called ${rest.join(" ")}.`); return; }
      head === "WATCH" ? list.add(id) : list.delete(id); write(WATCH, [...list]);
      state.msg = `${head === "WATCH" ? "Watching" : "No longer watching"} ${code(rows().find((r) => r.id === id).o)}.`; render(host, D); return;
    }
    if (head === "CALL") {
      const v = parseFloat(rest[0]);
      const box = host.querySelector("#tm-value");
      if (box && isFinite(v)) { box.value = v; box.dispatchEvent(new Event("input")); say(`Your call is set to ${v}; press SEAL to seal it.`); } else say("CALL needs a number, e.g. CALL 4200.");
      return;
    }
    const hit = find(rest.length && head === "GO" ? rest.join(" ") : text);
    if (hit) { state.focus = hit.id; state.msg = `${hit.code} · ${hit.title}`; render(host, D); history.replaceState(null, "", "#terminal/" + hit.id); return; }
    say(`Unknown code "${text}". Type HELP.`);
  }

  function board(all) {
    const { fmt } = window.WPCharts;
    const list = all.filter((r) => (state.watchOnly ? r.watched : state.area === "all" || r.area === state.area));
    host.querySelector("#tm-board-sub").textContent = state.watchOnly ? `your watchlist · ${list.length}` : `${list.length} series · click a row, or ↑ ↓ and Enter`;
    const hasWire = Object.keys((D.wire || {}).topics || {}).length > 0;
    const tone = (v, e = 0) => (v === null ? "dim" : v > e ? "pos" : v < -e ? "neg" : "");
    const z = (v) => (v === null ? '<span class="dim">–</span>' : `<span class="tm-z ${Math.abs(v) >= 2 ? "hot" : Math.abs(v) >= 1 ? "warm" : ""}">${v > 0 ? "+" : "−"}${Math.abs(v).toFixed(1)}σ</span>`);
    const range = (r) => {
      const span = Math.max(0.02, Math.abs(r.lo), Math.abs(r.hi)), x = (v) => 50 + 50 * v / span;
      return `<span class="tm-range" title="80% range ${fmt.signedPct(r.lo)} to ${fmt.signedPct(r.hi)}"><i style="left:${x(r.lo).toFixed(1)}%;width:${(x(r.hi) - x(r.lo)).toFixed(1)}%"></i><b style="left:${x(r.mid).toFixed(1)}%"></b></span>`;
    };
    if (!list.length) { host.querySelector("#tm-table").innerHTML = '<tbody><tr><td><div class="empty">Nothing here yet. Type WATCH in the command line to add the series in focus.</div></td></tr></tbody>'; return; }
    host.querySelector("#tm-table").innerHTML = `<thead><tr><th>Code</th><th>Name</th><th>Last</th><th>1W</th><th>σ</th><th>Forecast</th><th>80% range</th><th>P(up)</th><th>Record</th><th>Live</th>${hasWire ? "<th>Wire</th>" : ""}</tr></thead><tbody>${
      list.map((r) => `<tr data-id="${esc(r.id)}" tabindex="0" aria-selected="${r.id === state.focus}">
        <td><span class="tm-code" style="--c:var(--${esc(r.area)})">${r.watched ? "★ " : ""}${esc(r.code)}</span></td><td class="tm-name">${esc(r.title)}</td>
        <td>${fmt.num(r.last)}</td><td class="${tone(r.w)}">${fmt.signedPct(r.w)}</td><td>${z(r.z)}</td>
        <td class="${tone(r.mid, 0.002)}">${fmt.signedPct(r.mid)} <small>${esc(r.by.slice(5))}</small></td><td>${range(r)}</td>
        <td>${fmt.pct(r.up)}</td><td class="${tone(r.skill, 0.02)}">${fmt.signedPct(r.skill)}</td>
        <td>${r.live === null ? '<span class="dim">–</span>' : `${fmt.pct(r.live)} <small>${r.liveN}</small>`}</td>${hasWire ? `<td>${r.news ? `<span class="tm-dot"></span>${r.news}` : '<span class="dim">–</span>'}</td>` : ""}</tr>`).join("")}</tbody>`;
    const table = host.querySelector("#tm-table");
    table.onclick = (e) => { const tr = e.target.closest("tr[data-id]"); if (tr) pick(tr.dataset.id); };
    table.onkeydown = (e) => {
      const tr = e.target.closest("tr[data-id]"); if (!tr) return;
      if (e.key === "Enter") { pick(tr.dataset.id); }
      else if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); const next = e.key === "ArrowDown" ? tr.nextElementSibling : tr.previousElementSibling; if (next) next.focus(); }
    };
  }
  function pick(id) {
    state.focus = id;
    history.replaceState(null, "", "#terminal/" + id);
    host.querySelectorAll("#tm-table tr[data-id]").forEach((tr) => tr.setAttribute("aria-selected", tr.dataset.id === id));
    focus(rows().find((r) => r.id === id));
  }

  function movers(all) {
    const top = all.filter((r) => r.z !== null).sort((a, b) => Math.abs(b.z) - Math.abs(a.z)).slice(0, 6);
    const { fmt } = window.WPCharts;
    host.querySelector("#tm-movers").innerHTML = `<ul class="tm-list">${top.map((r) => `<li><button type="button" data-id="${esc(r.id)}"><span class="tm-code" style="--c:var(--${esc(r.area)})">${esc(r.code)}</span>
      <span class="tm-z ${Math.abs(r.z) >= 2 ? "hot" : "warm"}">${r.z > 0 ? "+" : "−"}${Math.abs(r.z).toFixed(1)}σ</span><span class="dim">${fmt.signedPct(r.w)} in a week</span></button></li>`).join("")}</ul>`;
    host.querySelector("#tm-movers").onclick = (e) => { const b = e.target.closest("button[data-id]"); if (b) pick(b.dataset.id); };
  }

  function opened() {
    const { fmt } = window.WPCharts;
    const list = (D.opened || []).filter((r) => r[1] === D.meta.model).sort((a, b) => (a[3] < b[3] ? 1 : -1)).slice(0, 7);
    const title = (id) => { const o = D.outlook.find((x) => x.id === id); return o ? code(o) : id; };
    host.querySelector("#tm-opened").innerHTML = list.length ? `<ul class="tm-list">${list.map((r) => `<li><span class="tm-code">${esc(title(r[0]))}</span>
      <span>said ${fmt.num(r[6])}, was <b>${fmt.num(r[8])}</b></span><span class="${r[10] ? "pos" : "neg"}">${r[10] ? "✓ in range" : "✗ outside"}</span><small class="dim">${esc(r[3])}</small></li>`).join("")}</ul>`
      : '<div class="empty">No sealed forecast has opened yet.</div>';
  }

  function focus(r) {
    const { plot, fmt } = window.WPCharts;
    const box = host.querySelector("#tm-focus"), o = r.o, last = lastOf(o), S = o.seldon && o.seldon.fan && o.seldon.fan.length ? o.seldon.fan : null;
    const V = (((D.volatility || {}).markets || {})[o.id] || {}).now;
    const vol = V ? Object.fromEntries(V.rows.filter((x) => x[1] === "1 month").map((x) => [x[0], x[2]])) : null;
    const f = o.fan[o.fan.length - 1];
    const month = o.history.length > 22 && !yearly(o) ? change(o, perWeek(o) === 5 ? 21 : 28) : null;
    box.innerHTML = `<header><h2><span class="tm-code" style="--c:var(--${esc(o.domain)})">${esc(r.code)}</span> ${esc(o.title)}</h2><span>${esc(AREAS[o.domain])} · ${esc(o.description || "")}</span></header>
      <dl class="tm-stats">
        <div><dt>Last</dt><dd>${fmt.num(last[1])} <small>${esc(last[0])}</small></dd></div>
        <div><dt>1W · 1M</dt><dd><span class="${r.w > 0 ? "pos" : r.w < 0 ? "neg" : ""}">${fmt.signedPct(r.w)}</span> · <span class="${month > 0 ? "pos" : month < 0 ? "neg" : ""}">${fmt.signedPct(month)}</span></dd></div>
        <div><dt>${esc(name())} by ${esc(f[0])}</dt><dd style="color:var(--tfm)">${fmt.num(f[2])} <small>${fmt.num(f[1])}–${fmt.num(f[3])}</small></dd></div>
        <div><dt>Seldon</dt><dd style="color:var(--seldon)">${S ? `${fmt.num(S[S.length - 1][2])} <small>${fmt.num(S[S.length - 1][1])}–${fmt.num(S[S.length - 1][3])}</small>` : "–"}</dd></div>
        <div><dt>Chance up</dt><dd>${fmt.pct(r.up)}</dd></div>
        <div><dt>Record · live</dt><dd>${fmt.signedPct(r.skill)} · ${r.live === null ? "–" : fmt.pct(r.live)}</dd></div>
        ${odds(o.id)}
        ${vol ? `<div><dt>Vol 1M · GARCH / last</dt><dd>${fmt.pct(vol.garch)} / ${fmt.pct(vol["last-month"])}</dd></div>` : ""}
      </dl>
      <div id="tm-chart"></div>
      <form class="tm-call" id="tm-call">
        <span class="tm-call-h">Your call</span>
        <label>on <select id="tm-date">${o.fan.map((p, i) => `<option value="${i}"${i === o.fan.length - 1 ? " selected" : ""}>${esc(p[0])}</option>`).join("")}</select></label>
        <label>value <input id="tm-value" type="number" step="any" inputmode="decimal"></label>
        <label>± <input id="tm-width" type="number" step="any" min="0" inputmode="decimal"> %</label>
        <button class="tm-seal" type="submit">SEAL</button>
        <span class="tm-call-note" id="tm-call-note"></span>
      </form>
      <div class="tm-links"><a href="#series/${esc(o.id)}">Every past forecast</a>${o.domain === "markets" ? ` · <a href="#markets/${esc(o.id)}:20">Markets desk</a>` : ""} · <a href="#studio/${esc(o.id)}">Forecast Studio</a> · <button type="button" class="linkish" id="tm-watch">${r.watched ? "Unwatch" : "Watch"}</button></div>`;
    const hist = o.history.slice(-63), dateSel = box.querySelector("#tm-date"), val = box.querySelector("#tm-value"), wid = box.querySelector("#tm-width");
    const draw = () => {
      const k = +dateSel.value, v = parseFloat(val.value), w = parseFloat(wid.value) / 100;
      plot(box.querySelector("#tm-chart"), {
        x: "date", height: 230, left: 52, right: 60, label: `${o.title}: history, forecasts and your call`, animate: false,
        bands: [{ points: [[last[0], last[1], last[1]]].concat(o.fan.map((p) => [p[0], p[1], p[3]])) },
          ...(S ? [{ points: [[last[0], last[1], last[1]]].concat(S.map((p) => [p[0], p[1], p[3]])), color: "transparent", stroke: "var(--seldon)", hatch: false, edge: "2 3" }] : [])],
        lines: [{ points: hist, color: "var(--ink)", width: 1.5, name: "actual" },
          { points: [last].concat(o.fan.map((p) => [p[0], p[2]])), color: "var(--tfm)", width: 1.8, name: name(), label: name() },
          ...(S ? [{ points: [last].concat(S.map((p) => [p[0], p[2]])), color: "var(--seldon)", width: 1.6, name: "Seldon" }] : [])],
        dots: isFinite(v) ? [{ points: [[o.fan[k][0], v]], color: "var(--you)", r: 5, name: "you" }] : [],
        refs: (isFinite(v) && isFinite(w) && w > 0 ? [{ y: v * (1 + w), color: "var(--you)" }, { y: v * (1 - w), color: "var(--you)" }] : [])
          .concat(((D.events || {}).now || []).filter((e) => e[0] === o.id).map((e) => ({ y: e[2], color: e[1] === "spike" ? "var(--warn)" : "var(--ink-3)", label: e[1] }))),
      });
    };
    const reset = () => { const p = o.fan[+dateSel.value]; val.value = Number(p[2].toPrecision(5)); wid.value = Math.max(0.1, ((p[3] - p[1]) / 2 / p[2]) * 100).toFixed(1); draw(); };
    dateSel.onchange = reset; val.oninput = draw; wid.oninput = draw;
    reset();
    box.querySelector("#tm-call").onsubmit = (e) => { e.preventDefault(); seal(o, +dateSel.value, parseFloat(val.value), parseFloat(wid.value) / 100); };
    box.querySelector("#tm-watch").onclick = () => run(r.watched ? "UNWATCH" : "WATCH");
    wirePane(o);
  }

  // ---------- event odds ----------
  // D.events.now: [series, event, threshold, last, target date, {model: odds}], from the newest sealed forecasts.
  const EVENT_WORDS = { spike: "Spike", lull: "Lull" };
  function seldonKey(p) { return p.seldon !== undefined ? "seldon" : p["seldon-laws"] !== undefined ? "seldon-laws" : null; }
  function odds(id) {
    const { fmt } = window.WPCharts;
    const mine = ((D.events || {}).now || []).filter((r) => r[0] === id);
    if (!mine.length) return "";
    const tf = D.meta.model, by = Object.fromEntries(mine.map((r) => [r[1], r[5]]));
    const one = (e) => (by[e] && by[e][tf] !== undefined ? fmt.pct(by[e][tf]) : "–");
    return `<div><dt>Spike · lull odds</dt><dd>${one("spike")} · ${one("lull")} <small>usual 10%</small></dd></div>`;
  }
  function eventsPane() {
    const { fmt } = window.WPCharts;
    const box = host.querySelector("#tm-events"), E = D.events || {}, tf = D.meta.model;
    const titleOf = (id) => { const x = D.outlook.find((q) => q.id === id); return x ? [code(x), x.title, x.domain] : [id, id, ""]; };
    let list = (E.now || []).filter((r) => state.area === "all" || titleOf(r[0])[2] === state.area);
    const sk = list.length ? seldonKey(list[0][5]) : null;
    list = list.slice().sort((a, b) => (b[5][tf] ?? 0) - (a[5][tf] ?? 0));
    const total = list.length;
    if (!state.allOdds) list = list.slice(0, 10);
    const rec = (r) => { const x = ((E.series || {})[r[0]] || {})[r[1] + "|" + tf]; return x ? fmt.signedPct(x[0]) : "–"; };
    const all = (E.backtest || []).filter((r) => r[0] === "all" && r[2] === tf);
    const line = all.map((r) => `${EVENT_WORDS[r[1]].toLowerCase()} ${fmt.signedPct(r[7])} against climatology, ${fmt.signedPct(r[8])} against persistence`).join("; ");
    box.innerHTML = `<header><h2>Event odds</h2><span>${E.made_on ? `${E.sealed ? "sealed" : "from the forecasts sealed"} ${esc(E.made_on)} · the chance of a level seen one day in ten, four weeks ahead` : "news and technology"}</span></header>
      ${state.area === "markets" ? '<div class="empty">Event odds cover world news and technology attention. For a market, the Markets desk gives the chance of closing above any level you choose.</div>'
        : list.length ? `<div class="table-wrap"><table class="tm-ev"><thead><tr><th>Code</th><th>Event</th><th>Threshold</th><th>Last</th><th>By</th><th>${esc(name())}</th>${sk ? `<th>${sk === "seldon" ? "Seldon" : "Seldon laws"}</th>` : ""}<th>Persistence</th><th>Record</th></tr></thead><tbody>
          ${list.map((r) => { const [c] = titleOf(r[0]), p = r[5], t = p[tf];
            return `<tr data-id="${esc(r[0])}" tabindex="0"><td><span class="tm-code" style="--c:var(--${esc(titleOf(r[0])[2])})">${esc(c)}</span></td>
              <td class="tm-ev-${esc(r[1])}">${EVENT_WORDS[r[1]]}</td><td>${r[1] === "spike" ? "&gt;" : "&lt;"} ${fmt.num(r[2])}</td><td>${fmt.num(r[3])}</td><td><small>${esc(r[4])}</small></td>
              <td><span class="tm-odds" style="--p:${Math.round((t ?? 0) * 100)}%">${t === undefined ? "–" : fmt.pct(t)}</span></td>
              ${sk ? `<td>${p[sk] === undefined ? "–" : fmt.pct(p[sk])}</td>` : ""}<td>${p.persistence === undefined ? "–" : fmt.pct(p.persistence)}</td><td>${rec(r)}</td></tr>`; }).join("")}
          </tbody></table></div>${total > 10 ? `<button type="button" class="btn small" id="tm-more">${state.allOdds ? "Top ten only" : `All ${total} events`}</button>` : ""}`
        : '<div class="empty">Event odds appear with the first sealed news or technology forecasts.</div>'}
      <p class="note">A spike is the value on the target date above the 90th percentile of the last two years; a lull, below the 10th. Climatology says 10% for both. Persistence is how often the series was past the line four weeks after a day like today. Record is ${esc(name())}'s Brier skill against climatology on this series' backtest${line ? `; across all of them: ${esc(line)}` : ""}. Odds, not advice.</p>`;
    const more = box.querySelector("#tm-more");
    if (more) more.onclick = (e) => { e.stopPropagation(); state.allOdds = !state.allOdds; eventsPane(); };
    const open = (tr) => { pick(tr.dataset.id); host.querySelector("#tm-focus").scrollIntoView({ block: "nearest" }); };
    box.onclick = (e) => { const tr = e.target.closest("tr[data-id]"); if (tr) open(tr); };
    box.onkeydown = (e) => { const tr = e.target.closest("tr[data-id]"); if (tr && e.key === "Enter") open(tr); };
  }

  async function seal(o, k, value, width) {
    const note = host.querySelector("#tm-call-note");
    if (!isFinite(value) || !isFinite(width) || width < 0) { note.textContent = "Give a value and a range."; return; }
    const p = o.fan[k], S = o.seldon && o.seldon.fan && o.seldon.fan.length ? o.seldon.fan[Math.min(k, o.seldon.fan.length - 1)] : null, last = lastOf(o)[1];
    const call = { series: o.id, title: o.title, date: p[0], step: k + 1, made_on: o.made_on, last,
      value, lo: value * (1 - width), hi: value * (1 + width), tfm: [p[1], p[2], p[3]], seldon: S ? [S[1], S[2], S[3]] : null,
      sealed_at: new Date().toISOString() };
    call.fingerprint = await digest(JSON.stringify(call));
    const calls = book().filter((c) => !(c.series === call.series && c.date === call.date && c.made_on === call.made_on));
    calls.unshift(call);
    const ok = write(STORE, calls);
    note.innerHTML = ok ? `Sealed <code>${esc(call.fingerprint)}</code>. It opens on ${esc(call.date)}.` : "Not saved: this browser blocks storage. Export will not include it.";
    paintBook();
  }

  function wirePane(o) {
    const box = host.querySelector("#tm-wire"), W = D.wire || {}, topic = (W.topics || {})[o.id];
    const items = topic ? topic.articles : [];
    const others = Object.entries(W.topics || {}).filter(([id]) => id !== o.id).flatMap(([id, t]) => t.articles.slice(0, 1).map((a) => [id, a]))
      .sort((a, b) => (a[1][4] < b[1][4] ? 1 : -1)).slice(0, 6);
    const line = (a, tag) => `<li><a href="${esc(a[1])}" target="_blank" rel="noopener noreferrer">${esc(a[0])}</a><small>${tag ? `<span class="tm-code">${esc(tag)}</span> ` : ""}${esc(a[2])}${a[3] ? " · " + esc(a[3]) : ""}${a[4] ? " · " + esc(a[4].replace("T", " ")) : ""}</small></li>`;
    const tagOf = (id) => { const x = D.outlook.find((q) => q.id === id); return x ? code(x) : id; };
    box.innerHTML = `<header><h2>World wire</h2><span>${W.fetched ? `GDELT · ${esc(W.fetched)}${topic && topic.stale ? " · last week's" : ""}` : "GDELT"}</span></header>
      ${items.length ? `<ul class="tm-news">${items.map((a) => line(a)).join("")}</ul>`
        : `<div class="empty">${W.fetched ? `No recent headlines for ${esc(o.title)}.` : "The weekly run adds the newest headlines for every topic (<code>psychohistory wire</code>)."}</div>`}
      <button type="button" class="btn small" id="tm-live">Load live headlines for ${esc(code(o))}</button>
      ${others.length ? `<header class="tm-sub"><h2>Elsewhere</h2></header><ul class="tm-news">${others.map(([id, a]) => line(a, tagOf(id))).join("")}</ul>` : ""}
      <p class="note">Headlines are context, not inputs: no model reads them.</p>`;
    box.querySelector("#tm-live").onclick = () => live(o, box);
  }
  // Straight from GDELT in your browser, for the series in focus (one request; GDELT asks for at most one every five seconds).
  async function live(o, box) {
    const btn = box.querySelector("#tm-live"), q = LIVE_QUERY(o);
    if (!q) { btn.textContent = "No news query for this series"; return; }
    btn.disabled = true; btn.textContent = "Loading…";
    try {
      const url = "https://api.gdeltproject.org/api/v2/doc/doc?" + new URLSearchParams({ query: q + " sourcelang:english", mode: "ArtList", format: "json", maxrecords: "8", timespan: "2d", sort: "DateDesc" });
      const res = await fetch(url);
      const data = await res.json();
      const arts = (data.articles || []).filter((a) => /^https?:\/\//.test(a.url || "") && a.title);
      const seen = (s) => (s && s.length >= 13 ? `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)} ${s.slice(9, 11)}:${s.slice(11, 13)}Z` : "");
      const list = document.createElement("ul"); list.className = "tm-news";
      list.innerHTML = arts.length ? arts.map((a) => `<li><a href="${esc(a.url)}" target="_blank" rel="noopener noreferrer">${esc(a.title)}</a><small>${esc(a.domain || "")}${a.sourcecountry ? " · " + esc(a.sourcecountry) : ""} · ${esc(seen(a.seendate))}</small></li>`).join("") : "<li>No articles in the last two days.</li>";
      btn.replaceWith(list);
    } catch (e) { btn.disabled = false; btn.textContent = "GDELT did not answer; try again in a few seconds"; }
  }
  const LIVE_QUERY = (o) => ({ sp500: '"S&P 500"', msci_world: '"global stocks"', nasdaq100: "Nasdaq", aapl: '("Apple Inc" OR iPhone)', nvda: "Nvidia", tsla: "Tesla", xom: '"Exxon Mobil"',
    gold: '"gold price"', silver: '"silver price"', oil_wti: '"oil prices"', copper: '"copper price"', bitcoin: "bitcoin", news_war: '"war"', news_election: '"election"', news_inflation: '"inflation"',
    news_climate: '"climate change"', news_pandemic: "(pandemic OR outbreak OR epidemic)", news_protest: "(protest OR protests)", wiki_llm: '"language model"', wiki_ai: '"artificial intelligence"',
    wiki_quantum: '"quantum computing"', wiki_crispr: "CRISPR", wiki_ev: '"electric vehicles"', wiki_fusion: '"fusion energy"', wiki_humanoid: '"humanoid robot"', adoption_solar: '"solar power"', adoption_wind: '"wind power"' }[o.id]);

  function paintBook() {
    const { plot, fmt } = window.WPCharts;
    const box = host.querySelector("#tm-book"), calls = settle(book());
    const done = calls.map((c) => [c, verdict(c)]).filter((x) => x[1]), open = calls.filter((c) => !c.settled);
    const sum = (k) => done.reduce((a, [, v]) => a + v[k], 0);
    const skill = done.length && sum("tfm") > 0 ? 1 - sum("you") / sum("tfm") : null;
    const share = (k) => (done.length ? done.filter(([, v]) => v[k]).length / done.length : null);
    const wins = done.filter(([, v]) => v.best === "You").length;
    const first = calls.length ? calls.map((c) => c.sealed_at.slice(0, 10)).sort()[0] : null;
    box.innerHTML = `<header><h2>Your book</h2><span>${calls.length ? `${calls.length} call${calls.length > 1 ? "s" : ""} since ${esc(first)}` : "kept in this browser"}</span></header>
      <dl class="tm-stats">
        <div><dt>Open · settled</dt><dd>${open.length} · ${done.length}</dd></div>
        <div><dt>Skill vs ${esc(name())}</dt><dd class="${skill > 0.02 ? "pos" : skill < -0.02 ? "neg" : ""}">${fmt.signedPct(skill)}</dd></div>
        <div><dt>In your range · ${esc(name())}'s</dt><dd>${fmt.pct(share("youIn"))} · ${fmt.pct(share("tfmIn"))}</dd></div>
        <div><dt>Closest of the three</dt><dd>${done.length ? `${wins} of ${done.length}` : "–"}</dd></div>
      </dl>
      <div id="tm-book-chart"></div>
      <div class="table-wrap"><table class="tm-calls">${calls.length ? `<thead><tr><th>Code</th><th>Date</th><th>You</th><th>${esc(name())}</th><th>Actual</th><th>Closest</th><th>Seal</th></tr></thead><tbody>${
        calls.slice(0, 12).map((c) => { const v = verdict(c), o = D.outlook.find((x) => x.id === c.series);
          const days = Math.ceil((Date.parse(c.date) - Date.now()) / 864e5);
          return `<tr><td><span class="tm-code">${esc(o ? code(o) : c.series)}</span></td><td>${esc(c.date)}</td><td style="color:var(--you)">${fmt.num(c.value)}</td><td>${fmt.num(c.tfm[1])}</td>
            <td>${v ? `<b>${fmt.num(v.actual)}</b>` : `<span class="dim">${days > 0 ? `in ${days}d` : "next run"}</span>`}</td>
            <td>${v ? `<span class="${v.best === "You" ? "pos" : ""}">${esc(v.best)}</span>${v.youIn ? " ✓" : ""}` : ""}</td><td><code data-fp="${esc(c.fingerprint)}">${esc(c.fingerprint)}</code></td></tr>`; }).join("")}</tbody>`
        : '<tbody><tr><td><div class="empty"><b>No calls yet.</b>Set a value and a range in the focus panel and press SEAL. Each call is scored against both models when its day comes, and stays in your book after the data has moved on.</div></td></tr></tbody>'}</table></div>
      <div class="tm-actions"><button type="button" class="btn small" id="tm-export"${calls.length ? "" : " disabled"}>Export book</button>
        <label class="btn small">Import book<input type="file" id="tm-import" accept="application/json,.json" hidden></label>
        <span class="tm-call-note" id="tm-book-note"></span></div>`;
    if (done.length >= 2) {
      const sorted = done.slice().sort((a, b) => (a[1].on < b[1].on ? -1 : 1));
      let you = 0, tfm = 0;
      const pts = sorted.map(([, v]) => { you += v.you; tfm += v.tfm; return [v.on, tfm > 0 ? 1 - you / tfm : 0]; });
      plot(box.querySelector("#tm-book-chart"), { x: "date", height: 150, left: 52, right: 40, label: "Your running skill against the model", animate: false,
        lines: [{ points: pts, color: "var(--you)", width: 2, name: "you", label: "you" }], refs: [{ y: 0, label: name() }] });
    }
    const note = box.querySelector("#tm-book-note");
    box.querySelector("#tm-export").onclick = () => {
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([JSON.stringify({ kind: "world-predictor-book", exported: new Date().toISOString(), calls }, null, 1)], { type: "application/json" }));
      a.download = `world-predictor-book-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(a); a.click(); a.remove();
    };
    box.querySelector("#tm-import").onchange = async (e) => {
      const file = e.target.files[0]; if (!file) return;
      try {
        const data = JSON.parse(await file.text()), incoming = Array.isArray(data) ? data : data.calls;
        if (!Array.isArray(incoming)) throw new Error("not a book");
        const ok = incoming.filter((c) => c && c.series && c.date && isFinite(c.value) && Array.isArray(c.tfm) && c.fingerprint && c.sealed_at);
        let edited = 0;
        for (const c of ok) if (!(await intact(c))) edited++;
        const have = new Map(book().map((c) => [c.fingerprint, c]));
        ok.forEach((c) => { if (!have.has(c.fingerprint)) have.set(c.fingerprint, c); else if (c.settled && !have.get(c.fingerprint).settled) have.set(c.fingerprint, c); });
        const merged = [...have.values()].sort((a, b) => (a.sealed_at < b.sealed_at ? 1 : -1));
        write(STORE, merged);
        paintBook();
        host.querySelector("#tm-book-note").textContent = `Imported ${ok.length} call${ok.length === 1 ? "" : "s"}${edited ? `; ${edited} no longer match${edited === 1 ? "es" : ""} its seal (edited after sealing)` : ", every seal intact"}.`;
      } catch (err) { note.textContent = "That file is not a World Predictor book."; }
    };
  }

  function scoreboard() {
    const { fmt } = window.WPCharts;
    const box = host.querySelector("#tm-score"), M = D.monitor || {}, V = D.volatility || {};
    const mine = (M.overall || []).find((r) => r[0] === D.meta.model && r[1] === "all");
    const test = (M.tests || []).find((r) => r[0] === D.meta.model && r[1] === "all");
    const exp = (M.expected || []).find((r) => r[0] === D.meta.model && r[1] === "all");
    const vbest = (V.backtest || []).filter((r) => r[1] === "1 month" && r[0] !== "last-month").sort((a, b) => b[2] - a[2])[0];
    const alarms = (M.alarms || []).length, seals = M.seals;
    box.innerHTML = `<header><h2>Scoreboard</h2><span>${esc(name())}, sealed forecasts against reality</span></header>
      <dl class="tm-kv">
        <div><dt>Scored</dt><dd>${mine ? `${mine[2].toLocaleString("en")} in ${mine[3]} weekly batches` : "none yet"}</dd></div>
        <div><dt>Skill vs "no change"</dt><dd class="${mine && mine[5] > 0.02 ? "pos" : mine && mine[5] < -0.02 ? "neg" : ""}">${mine ? fmt.signedPct(mine[5]) : "–"} <small>backtest ${exp ? fmt.signedPct(exp[2]) : "–"}</small></dd></div>
        <div><dt>In its 80% range</dt><dd>${mine ? fmt.pct(mine[6]) : "–"} <small>aim 80%</small></dd></div>
        <div><dt>Right direction</dt><dd>${mine ? fmt.pct(mine[7]) : "–"}</dd></div>
        <div><dt>Real or luck?</dt><dd>${test ? esc(test[6]) : "–"}</dd></div>
        <div><dt>Drift alarms</dt><dd class="${alarms ? "neg" : "pos"}">${alarms ? `${alarms} raised` : "none"}</dd></div>
        <div><dt>Ledger seals</dt><dd class="${seals && seals.bad.length ? "neg" : ""}">${seals ? `${seals.ok} of ${seals.batches} match` : "–"}</dd></div>
        <div><dt>Best volatility, 1M</dt><dd>${vbest ? `${esc(vbest[0] === "garch" ? "GARCH" : vbest[0] === "ewma" ? "EWMA" : vbest[0])} ${fmt.signedPct(vbest[2])}` : "–"}</dd></div>
      </dl>
      <div class="tm-links"><a href="#monitor">The full monitor</a> · <a href="#vault">Time Vault</a> · <a href="#markets">Markets desk</a></div>`;
  }

  window.WPTerminal = { render, settle, settleAll: (data) => settle(read(STORE, []), data), verdict, sigma, find: (data, text) => { D = data; return find(text); } };
})();
