// Year ledger: every day of the year, each model's most likely value against what really happened.
// One table per tracked series, grouped (gold, silver, bonds, indices, stocks, oil and copper, Bitcoin,
// world news, technology), from 1 January to 31 December; days nobody forecast, or that have not
// happened yet, are dashes. Reads D.year (src/psychohistory/yearbook.py).
(function () {
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const state = { group: "gold", grain: "week" };
  let D = null, host = null, Y = null;
  const DAY = 864e5;
  const COLORS = { seldon: "var(--seldon)", "seldon-laws": "var(--hypo)", radiant: "var(--radiant)" };
  const color = (m) => COLORS[m] || "var(--tfm)";
  const label = (m) => (m === "seldon" ? "Seldon" : m === "seldon-laws" ? "Crowd laws" : m === "radiant" ? "Radiant" : /^timesfm/.test(m) ? "TimesFM" : m);
  const dash = '<span class="yr-dash">–</span>';

  function dateOf(i) { return new Date(Date.parse(Y.start) + i * DAY).toISOString().slice(0, 10); }
  function num(v) {
    if (v === null || v === undefined) return dash;
    const a = Math.abs(v);
    return a >= 1e4 ? Math.round(v).toLocaleString("en") : a >= 100 ? v.toFixed(1) : a >= 1 ? v.toFixed(2) : v.toPrecision(3);
  }
  function pct(v, cls = true) {
    if (v === null || v === undefined || !isFinite(v)) return dash;
    const s = (v >= 0 ? "+" : "−") + Math.abs(v * 100).toFixed(Math.abs(v) < 0.1 ? 2 : 1) + "%";
    return cls ? `<span class="${Math.abs(v) < 0.005 ? "" : v > 0 ? "pos" : "neg"}">${s}</span>` : s;
  }
  const off = (f, a) => (f === null || a === null || !a ? null : (f - a) / Math.abs(a));

  // The rows to show: every day, or one per week or month (the last day in it with a real value,
  // else the last with a forecast, else its last day).
  function rowsOf(t) {
    const n = t.a.length, all = [...Array(n).keys()];
    if (state.grain === "day") return all;
    const key = (i) => { const d = dateOf(i); if (state.grain === "month") return d.slice(0, 7); const w = new Date(Date.parse(d)); return Math.floor((w.getTime() / DAY + 3) / 7); };
    const groups = new Map();
    all.forEach((i) => { const k = key(i); groups.set(k, [...(groups.get(k) || []), i]); });
    return [...groups.values()].map((ix) => {
      const withA = ix.filter((i) => t.a[i] !== null), withF = ix.filter((i) => Y.models.some((m) => t[m][i] !== null));
      return (withA.length ? withA : withF.length ? withF : ix).slice(-1)[0];
    });
  }

  function closest(t, i) {
    const a = t.a[i];
    if (a === null) return null;
    let best = null, err = Infinity;
    Y.models.forEach((m) => { const f = t[m][i]; if (f !== null && Math.abs(f - a) < err) { err = Math.abs(f - a); best = m; } });
    return best;
  }

  // The year at a glance: one cell per day, coloured by the model that came closest.
  function strip(item) {
    const t = item.table, n = t.a.length, today = Math.round((Date.parse(Y.today) - Date.parse(Y.start)) / DAY);
    const w = 3, gap = 0, H = 22;
    let cells = "";
    for (let i = 0; i < n; i++) {
      const m = closest(t, i), has = Y.models.some((k) => t[k][i] !== null);
      const fill = m ? color(m) : has ? "var(--line-2)" : "var(--panel-2)";
      const op = i > today ? 0.45 : 1;
      cells += `<rect x="${i * (w + gap)}" y="0" width="${w}" height="${H}" fill="${fill}" opacity="${op}" data-i="${i}"><title>${dateOf(i)}${m ? ": " + label(m) + " closest" : has ? ": forecast, real value not in yet" : ": not tracked"}</title></rect>`;
    }
    const months = [...Array(12).keys()].map((k) => { const i = Math.round((Date.UTC(Y.year, k, 1) - Date.parse(Y.start)) / DAY);
      return `<text x="${i * w + 2}" y="${H + 12}">${new Date(Date.UTC(Y.year, k, 1)).toLocaleString("en", { month: "short", timeZone: "UTC" })}</text>`; }).join("");
    const mark = today >= 0 && today < n ? `<line x1="${today * w + 1.5}" x2="${today * w + 1.5}" y1="-3" y2="${H + 3}" class="yr-today"/>` : "";
    return `<svg class="yr-strip" viewBox="0 -4 ${n * w} ${H + 18}" preserveAspectRatio="none" role="img" aria-label="${esc(item.title)}: the closest model on each day of ${Y.year}">${cells}${mark}${months}</svg>`;
  }

  // Is the gap to TimesFM real? A Diebold-Mariano test, cut for testing every series at once.
  function verdict(x) {
    if (x.p === null || x.p === undefined) return "";
    const p = x.p < 0.001 ? "p < 0.001" : `p ${x.p.toFixed(x.p < 0.01 ? 3 : 2)}`;
    return x.real ? ` <span class="yr-real" title="Diebold-Mariano test, Benjamini-Hochberg cut across series">real · ${p}</span>`
      : ` <span class="yr-luck" title="Diebold-Mariano test: not distinguishable from luck after the cut for many series">could be luck · ${p}</span>`;
  }

  function stats(item) {
    const s = item.stats || {};
    if (!s.days) return '<p class="yr-stats dim">Not tracked yet this year: the next weekly run fetches it and starts sealing forecasts.</p>';
    const base = s.models[Y.models[0]].mape;
    return `<dl class="yr-stats">${Y.models.map((m) => { const x = s.models[m];
      return `<div><dt><i style="background:${color(m)}"></i>${esc(label(m))}</dt><dd><b>${(x.mape * 100).toFixed(2)}%</b> average miss${m !== Y.models[0] ? ` <span class="${x.mape < base ? "pos" : "neg"}">${x.mape < base ? "beats" : "behind"} TimesFM</span>${verdict(x)}` : ""}<small>closest on ${Math.round(x.closest * 100)}% of days · bias ${pct(x.bias, false)}</small></dd></div>`; }).join("")}
      <div><dt>Compared on</dt><dd><b>${s.days}</b> days<small>where all of them forecast and the real value is in</small></dd></div></dl>`;
  }

  function table(item) {
    const t = item.table, today = Date.parse(Y.today);
    const rows = rowsOf(t).map((i) => {
      const d = dateOf(i), a = t.a[i], o = t.o[i], future = Date.parse(d) > today, best = closest(t, i), src = t.src[i];
      const cells = Y.models.map((m) => { const f = t[m][i];
        return `<td class="${best === m ? "yr-best" : ""}">${num(f)}${f !== null && o ? `<small>${pct(f / o - 1, false)}</small>` : ""}</td><td>${pct(off(f, a), false)}</td>`; }).join("");
      return `<tr class="${future ? "yr-future" : ""}${d === Y.today ? " yr-now" : ""}" data-i="${i}"><th scope="row">${d}</th><td>${num(a)}</td><td>${a !== null && o ? pct(a / o - 1) : dash}</td>${cells}
        <td>${best ? `<span class="yr-who" style="--c:${color(best)}">${esc(label(best))}</span>` : dash}</td><td>${src === "s" ? '<span class="yr-seal" title="sealed before the day">sealed</span>' : src === "b" ? '<span class="dim" title="replayed rolling-origin backtest">backtest</span>' : dash}</td></tr>`;
    }).join("");
    return `<div class="yr-scroll"><table class="yr-table"><thead><tr><th>Date</th><th>Real</th><th title="the real change since the forecast was made">Real move</th>
      ${Y.models.map((m) => `<th><i style="background:${color(m)}"></i>${esc(label(m))}</th><th>Off</th>`).join("")}<th>Closest</th><th>Source</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  }

  // The race: each model's average miss so far, day by day through the year, on the days all of
  // them forecast and the real value is in (the same days the leaderboard counts).
  function race(items) {
    const sum = Object.fromEntries(Y.models.map((m) => [m, 0])), out = Object.fromEntries(Y.models.map((m) => [m, []]));
    let n = 0;
    for (let i = 0; i < 366; i++) {
      let hit = false;
      items.forEach((it) => {
        const t = it.table, a = t.a[i];
        if (a === undefined || a === null || !a || Y.models.some((m) => t[m][i] === null || t[m][i] === undefined)) return;
        if (t.by && Y.models.some((m) => t.by[m] && t.by[m][i] !== t.by[Y.models[0]][i])) return;  // like with like, as the leaderboard
        Y.models.forEach((m) => { sum[m] += Math.abs(t[m][i] - a) / Math.abs(a); });
        n++; hit = true;
      });
      if (hit) Y.models.forEach((m) => out[m].push([dateOf(i), sum[m] / n]));
    }
    return out;
  }

  // Drawn as the gap to TimesFM, in points of average miss: below the line is beating it.
  function drawRace(el, items, height) {
    const R = race(items), { plot } = window.WPCharts, base = Y.models[0], skip = 14;
    const lines = Y.models.slice(1).map((m, k) => ({
      points: R[m].slice(skip).map(([d, v], j) => [d, (v - R[base][j + skip][1]) * 100]), color: color(m), name: label(m), label: label(m), width: 2.2, delay: 0.2 * k }));
    if (!lines.some((l) => l.points.length > 1)) { el.innerHTML = ""; return; }
    const ext = Math.max(0.2, ...lines.flatMap((l) => l.points.map((p) => Math.abs(p[1]))));
    plot(el, { x: "date", height, yDomain: [-ext, ext], yFormat: (v) => (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v).toFixed(Math.abs(v) < 1 ? 2 : 1) + " pt",
      xDomain: [Y.start, `${Y.year}-12-31`], refs: [{ y: 0, label: "TimesFM", color: color(base) }, { x: Y.today, label: "today" }], lines });
  }

  // How Radiant splits its vote: per area, the weights now (a bar) and how they moved after each
  // finished backtest window (a stacked band, oldest left). Reads D.radiant_vote (web.radiant_vote_payload).
  const EXPERT_COLORS = { model: "var(--tfm)", laws: "var(--hypo)", core: "var(--radiant)", naive: "var(--ink-3)", rival: "var(--rival)" };
  function vote() {
    const V = D.radiant_vote;
    if (!V || !V.areas || !V.areas.length) return "";
    const name = (k) => V.experts[V.keys.indexOf(k)];
    const lead = (w) => V.keys[w.indexOf(Math.max(...w))];
    const flow = (a) => {
      const pts = a.points, n = pts.length, W = 300, H = 72;
      if (n < 2) return "";
      const x = (i) => (i / (n - 1)) * W;
      let bands = "", below = new Array(n).fill(0);
      V.keys.forEach((k, j) => {
        if (pts.every((p) => !p[1][j])) return;
        const top = below.map((b, i) => b + (pts[i][1][j] || 0));
        const up = top.map((t, i) => `${x(i).toFixed(1)},${(H - t * H).toFixed(1)}`).join(" ");
        const down = below.map((b, i) => `${x(i).toFixed(1)},${(H - b * H).toFixed(1)}`).reverse().join(" ");
        bands += `<polygon points="${up} ${down}" fill="${EXPERT_COLORS[k]}" opacity=".85"><title>${esc(name(k))}</title></polygon>`;
        below = top;
      });
      return `<svg class="rv-flow" viewBox="0 0 ${W} ${H + 12}" preserveAspectRatio="none" role="img" aria-label="${esc(a.title)}: Radiant's weights after each finished window, ${esc(pts[0][0])} to ${esc(pts[n - 1][0])}">${bands}
        <text x="0" y="${H + 11}">${esc(pts[0][0].slice(0, 7))}</text><text x="${W}" y="${H + 11}" text-anchor="end">${esc(pts[n - 1][0].slice(0, 7))}</text></svg>`;
    };
    const areas = V.areas.map((a) => {
      const top = lead(a.now), share = Math.round(Math.max(...a.now) * 100);
      const bar = V.keys.map((k, j) => (a.now[j] >= 0.005 ? `<span style="width:${(a.now[j] * 100).toFixed(1)}%;background:${EXPERT_COLORS[k]};animation-delay:${j * 60}ms" title="${esc(name(k))} ${Math.round(a.now[j] * 100)}%"></span>` : "")).join("");
      const moved = top === "model" ? "TimesFM has kept the vote" : `${esc(name(top))} has earned the largest share`;
      return `<div class="rv-area"><h3>${esc(a.title)}</h3><p>${moved}: ${share}% now, after ${a.windows} finished windows${a.rival ? "" : " (Chronos has not run here yet)"}.</p>
        <div class="rv-now" role="img" aria-label="${esc(V.keys.map((k, j) => `${name(k)} ${Math.round(a.now[j] * 100)}%`).join(", "))}">${bar}</div>${flow(a)}</div>`;
    }).join("");
    return `<div class="card"><header class="ph"><h2>How Radiant splits its vote</h2><span class="pm">exponential weights, learned per area from finished windows</span></header>
      <p class="lede">Radiant starts with most of its weight on TimesFM. After every forecast window that finishes, each expert is charged its miss against TimesFM's and its weight shrinks by e<sup>−${V.eta} × charge</sup>, so a share has to be earned on forecasts the expert never saw. The bar is the split in use now, which this week's sealed Radiant forecasts were mixed with; the band below is how it moved.</p>
      <div class="rv-grid">${areas}</div>
      <p class="rv-legend">${V.keys.map((k) => `<span><i style="background:${EXPERT_COLORS[k]}"></i>${esc(name(k))}</span>`).join("")}</p></div>`;
  }

  function leaders() {
    const L = Y.leaders || [], base = L.find((x) => x.model === Y.models[0]);
    if (!base || !base.days) return '<div class="empty">No day of this year has both a forecast and a real value yet.</div>';
    const best = L.filter((x) => x.mape !== null).sort((a, b) => a.mape - b.mape)[0];
    const verdict = best.model === base.model
      ? `TimesFM leads ${Y.year} so far: its most likely value missed reality by ${(base.mape * 100).toFixed(2)}% on an average day. Radiant, Seldon and the crowd laws are still chasing it.`
      : `${label(best.model)} leads ${Y.year} so far, missing by ${(best.mape * 100).toFixed(2)}% on an average day against TimesFM's ${(base.mape * 100).toFixed(2)}%.`;
    return `<p class="yr-verdict">${esc(verdict)}</p>
      <div class="table-wrap"><table class="yr-board"><thead><tr><th>Model</th><th>Average miss</th><th>Closest on</th><th>Beats TimesFM on</th><th title="Diebold-Mariano test on each series, Benjamini-Hochberg cut">Clearly better · worse</th><th>Days compared</th></tr></thead><tbody>
      ${L.map((x) => `<tr><th scope="row"><i style="background:${color(x.model)}"></i>${esc(label(x.model))}</th><td><span class="yr-bar" style="--w:${Math.min(100, (x.mape / Math.max(...L.map((q) => q.mape || 0))) * 100).toFixed(1)}%;--c:${color(x.model)}"></span>${(x.mape * 100).toFixed(2)}%</td>
        <td>${Math.round(x.closest * 100)}% of days</td><td>${x.beats === null ? '<span class="dim">the benchmark</span>' : `${x.beats} of ${x.series} series`}</td><td>${x.better === null || x.better === undefined ? '<span class="dim">–</span>' : `<span class="pos">${x.better}</span> · <span class="neg">${x.worse}</span>`}</td><td>${x.days.toLocaleString("en")}</td></tr>`).join("")}</tbody></table></div>`;
  }

  // The books for one series as a CSV: every day of the year, empty where the app shows a dash.
  function download(item) {
    const t = item.table, cell = (v) => (v === null || v === undefined ? "" : String(v));
    const head = ["date", "actual"].concat(...Y.models.map((m) => [m, m + "_off_pct"]), ["closest", "source"]);
    const lines = [head.join(",")];
    for (let i = 0; i < t.a.length; i++) {
      const a = t.a[i], best = closest(t, i);
      lines.push([dateOf(i), cell(a)].concat(...Y.models.map((m) => { const o = off(t[m][i], a); return [cell(t[m][i]), o === null ? "" : (o * 100).toFixed(3)]; }),
        [best || "", { s: "sealed", b: "backtest" }[t.src[i]] || ""]).join(","));
    }
    const url = URL.createObjectURL(new Blob([lines.join("\n") + "\n"], { type: "text/csv" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: `year-ledger-${Y.year}-${item.id}.csv` });
    document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function render(root, data) {
    D = data; host = root; Y = D.year;
    if (!Y || !Y.groups) { host.innerHTML = '<div class="vhead"><h1 id="year-h">Year ledger</h1></div><div class="card"><div class="empty"><b>No year ledger in this data.</b>It is built from the backtest and the sealed ledger by <code>psychohistory export</code>.</div></div>'; return; }
    if (!Y.groups.some((g) => g.key === state.group)) state.group = Y.groups[0].key;
    const g = Y.groups.find((x) => x.key === state.group);
    host.innerHTML = `
      <div class="vhead"><h1 id="year-h">Year ledger ${Y.year}</h1>
        <p class="lede">Every day from 1 January to 31 December: what TimesFM, Radiant, Seldon and Seldon's crowd laws said was most likely, what really happened, and how far off each one was. Dashes are days nobody forecast or that have not happened yet. The goal: a forecaster of our own that beats TimesFM.</p></div>
      <div class="card"><header class="ph"><h2>Who is closest to reality in ${Y.year}</h2><span class="pm">every tracked series, on days all ${Y.models.length} forecast</span></header>${leaders()}
        <h3 class="yr-sub">The race through ${Y.year}: average miss so far, against TimesFM (below the line is beating it)</h3><div class="yr-race" id="yr-race-all"></div></div>
      ${vote()}
      <div class="yr-bar-row">
        <div class="chips" role="group" aria-label="What is tracked" id="yr-groups">${Y.groups.map((x) => `<button class="chip" data-g="${esc(x.key)}" aria-pressed="${x.key === state.group}">${esc(x.title)}</button>`).join("")}</div>
        <div class="chips" role="group" aria-label="Rows" id="yr-grain">${[["day", "Every day"], ["week", "Weekly"], ["month", "Monthly"]].map(([k, l]) => `<button class="chip" data-k="${k}" aria-pressed="${k === state.grain}">${l}</button>`).join("")}</div>
      </div>
      ${g.series.map((item) => `<section class="card yr-card" id="yr-${esc(item.id)}"><header class="ph"><h2>${esc(item.title)}</h2><span class="pm"><a href="#series/${esc(item.id)}">every forecast</a> · <a href="#terminal/${esc(item.id)}">terminal</a> · <button class="linkish" data-csv="${esc(item.id)}">CSV</button></span></header>
        ${stats(item)}<div class="yr-race small" data-race="${esc(item.id)}"></div>${strip(item)}
        <p class="yr-key">${Y.models.map((m) => `<span><i style="background:${color(m)}"></i>${esc(label(m))} closest</span>`).join("")}<span><i style="background:var(--line-2)"></i>forecast, real value not in</span><span><i style="background:var(--panel-2)"></i>not tracked</span></p>
        ${table(item)}</section>`).join("")}
      <p class="note">Most likely means the median of each model's forecast. Off is (forecast − real) / real. Real move is the real change since the forecast was made, and the small figure under each forecast is the change it expected. A sealed forecast was written into the ledger before its day; a backtest one was made from the data up to its origin and replayed later. Closest compares them on each day. "Real" or "could be luck" is a Diebold-Mariano test of the daily misses against TimesFM, allowing for overlapping forecasts, cut with Benjamini-Hochberg for testing every series at once. Research, not investment advice.</p>`;
    drawRace(host.querySelector("#yr-race-all"), Y.groups.flatMap((x) => x.series), 230);
    host.querySelectorAll("[data-race]").forEach((el) => drawRace(el, g.series.filter((x) => x.id === el.dataset.race), 150));
    host.querySelectorAll("[data-csv]").forEach((b) => (b.onclick = () => download(g.series.find((x) => x.id === b.dataset.csv))));
    host.querySelector("#yr-groups").onclick = (e) => { const b = e.target.closest("button"); if (b) { state.group = b.dataset.g; render(host, D); } };
    host.querySelector("#yr-grain").onclick = (e) => { const b = e.target.closest("button"); if (b) { state.grain = b.dataset.k; render(host, D); } };
    // A day on the strip jumps to its row (showing every day if the row is hidden).
    host.querySelectorAll(".yr-strip").forEach((svg) => (svg.onclick = (e) => {
      const r = e.target.closest("rect[data-i]"); if (!r) return;
      const card = svg.closest(".yr-card"); let row = card.querySelector(`tr[data-i="${r.dataset.i}"]`);
      if (!row) { state.grain = "day"; render(host, D); row = host.querySelector(`#${CSS.escape(card.id)} tr[data-i="${r.dataset.i}"]`); }
      if (row) { const box = row.closest(".yr-scroll"); box.scrollTop = row.offsetTop - box.clientHeight / 2; row.classList.add("yr-flash"); setTimeout(() => row.classList.remove("yr-flash"), 1200); }
    }));
    // Each table opens at today's row.
    host.querySelectorAll(".yr-scroll").forEach((box) => {
      const rows = [...box.querySelectorAll("tbody tr")], now = rows.findIndex((r) => r.classList.contains("yr-future"));
      const at = rows[Math.max(0, (now < 0 ? rows.length : now) - 4)];
      if (at) box.scrollTop = at.offsetTop - 40;
    });
  }

  window.WPYear = { render };
})();
