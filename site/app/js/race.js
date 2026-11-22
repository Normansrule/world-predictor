// The race: what really happened against TimesFM, Radiant and Seldon, over years, with how far
// apart they were and, beside the forecast, how each did in the past and how it is doing now.
// Data: app/data/race/<id>.json (written by `psychohistory race`), loaded when a chart needs it.
(function () {
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const pct = (v, d = 1) => (v == null || !Number.isFinite(v) ? "–" : (v * 100).toFixed(v < 0.1 ? d : 0) + "%");
  const MODELS = [["timesfm-2.5", "TimesFM", "var(--tfm)"], ["radiant", "Radiant", "var(--radiant)"], ["seldon", "Seldon", "var(--seldon)"]];
  const FUTURE = { "timesfm-2.5": (o) => o.fan, radiant: (o) => o.radiant, seldon: (o) => o.seldon && o.seldon.fan };
  const RANGES = [["ytd", "YTD"], ["1y", "1Y"], ["2y", "2Y"], ["5y", "5Y"], ["10y", "10Y"]];
  const t = (s) => Date.parse(s + "T00:00:00Z");
  const month = (s) => new Date(s + "T12:00:00Z").toLocaleDateString(undefined, { month: "short", year: "numeric" });
  const dayL = (s) => new Date(s + "T12:00:00Z").toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
  const num = (v) => { const a = Math.abs(v); return a >= 1e6 ? (v / 1e6).toFixed(1) + "M" : a >= 1e4 ? (v / 1e3).toFixed(0) + "k" : a >= 100 ? v.toFixed(0) : a >= 1 ? v.toFixed(1) : v.toPrecision(2); };
  const cache = {}, state = { range: "1y" };

  function load(id) {
    if (!cache[id]) {
      cache[id] = fetch(`data/race/${encodeURIComponent(id)}.json`).then((r) => (r.ok ? r.json() : null)).catch(() => null);
    }
    return cache[id];
  }

  // The first day shown for a range, counted back from the newest day in the race.
  function cutoff(last, key) {
    const d = new Date(last + "T00:00:00Z");
    if (key === "ytd") return `${d.getUTCFullYear()}-01-01`;
    d.setUTCFullYear(d.getUTCFullYear() - Number(key.replace("y", "")));
    return d.toISOString().slice(0, 10);
  }
  const reaches = (J, key) => key === "ytd" || t(J.dates[0]) <= t(cutoff(J.dates[J.dates.length - 1], key)) + 45 * 864e5;

  // Typical miss (median absolute % gap) of each forecaster on the days shown.
  function typical(J, from) {
    const out = {};
    for (const [m] of MODELS) {
      const v = J.m[m]; if (!v) continue;
      const e = [];
      J.dates.forEach((d, i) => { const a = J.actual[i], q = v[i]; if (d >= from && a && q != null && Number.isFinite(a)) e.push(Math.abs(q - a) / Math.abs(a)); });
      if (e.length) { e.sort((a, b) => a - b); out[m] = { typical: e[Math.floor(e.length / 2)], n: e.length }; }
    }
    return out;
  }

  // A running median of each forecaster's % gap, so the gap panel reads as a race, not as noise.
  function gaps(J, idx, win) {
    const out = {};
    for (const [m] of MODELS) {
      const v = J.m[m]; if (!v) continue;
      const raw = idx.map((i) => (J.actual[i] && v[i] != null ? Math.abs(v[i] - J.actual[i]) / Math.abs(J.actual[i]) : null));
      out[m] = raw.map((_, k) => {
        const w = raw.slice(Math.max(0, k - win + 1), k + 1).filter((x) => x != null);
        if (w.length < Math.min(5, win)) return null;
        w.sort((a, b) => a - b); return w[Math.floor(w.length / 2)];
      });
    }
    return out;
  }

  function svg(J, D, from) {
    const o = (D.outlook || []).find((x) => x.id === J.id);
    const all = J.dates.map((d, i) => i).filter((i) => J.dates[i] >= from);
    if (all.length < 2) return "";
    const step = Math.max(1, Math.ceil(all.length / 700));
    const idx = all.filter((_, k) => k % step === 0 || k === all.length - 1);
    const fut = {};
    for (const [m] of MODELS) { const f = o && FUTURE[m](o); if (f && f.length) fut[m] = f.map((r) => [r[0], r[2]]); }
    const W = 1000, H = 330, G = 120, L = 54, R = 12, Tp = 14, B = 22;
    const last = J.dates[J.dates.length - 1];
    const futDays = Object.values(fut).flat().map((p) => p[0]);
    const x0 = t(J.dates[idx[0]]), x1 = Math.max(t(last), ...futDays.map(t));
    const ys = [];
    idx.forEach((i) => { if (J.actual[i] != null) ys.push(J.actual[i]); for (const [m] of MODELS) if (J.m[m] && J.m[m][i] != null) ys.push(J.m[m][i]); });
    Object.values(fut).flat().forEach((p) => ys.push(p[1]));
    ys.sort((a, b) => a - b);
    let y0 = ys[Math.floor(ys.length * 0.002)], y1 = ys[Math.ceil(ys.length * 0.998) - 1];  // a wild replay day must not flatten the rest
    const pad = (y1 - y0 || Math.abs(y1) || 1) * 0.06; y0 -= pad; y1 += pad;
    const X = (d) => L + ((t(d) - x0) / (x1 - x0 || 1)) * (W - L - R);
    const Y = (v) => Tp + (1 - (Math.min(Math.max(v, y0), y1) - y0) / (y1 - y0)) * (H - Tp - B);
    const line = (pts) => { let s = "", pen = false; for (const [d, v] of pts) { if (v == null || !Number.isFinite(v)) { pen = false; continue; } s += `${pen ? "L" : "M"}${X(d).toFixed(1)},${Y(v).toFixed(1)}`; pen = true; } return s; };
    const xt = []; const span = (x1 - x0) / 864e5;
    for (let k = 0; k <= 4; k++) xt.push(new Date(x0 + ((x1 - x0) * k) / 4).toISOString().slice(0, 10));
    const ticks = [y0 + pad, (y0 + y1) / 2, y1 - pad];
    const live = J.live_from && J.live_from >= J.dates[idx[0]] ? J.live_from : J.live_from && J.live_from < J.dates[idx[0]] ? J.dates[idx[0]] : null;
    const top = `
      ${ticks.map((v) => `<line x1="${L}" x2="${W - R}" y1="${Y(v).toFixed(1)}" y2="${Y(v).toFixed(1)}" class="tr-grid"/><text x="${L - 6}" y="${(Y(v) + 4).toFixed(1)}" text-anchor="end" class="tr-ax">${num(v)}</text>`).join("")}
      ${live ? `<rect x="${X(live).toFixed(1)}" y="${Tp}" width="${(X(last) - X(live)).toFixed(1)}" height="${H - Tp - B}" class="rc-live"/><text x="${(X(live) + 4).toFixed(1)}" y="${H - B - 6}" class="tr-ax">sealed live</text>` : ""}
      ${J.live_from && J.dates[idx[0]] < J.live_from ? `<text x="${L + 4}" y="${H - B - 6}" class="tr-ax">replayed</text>` : ""}
      <line x1="${X(last).toFixed(1)}" x2="${X(last).toFixed(1)}" y1="${Tp}" y2="${H - B}" class="tr-now-l"/>
      ${Object.keys(fut).length ? `<text x="${(X(last) + 4).toFixed(1)}" y="${Tp + 10}" class="tr-ax">forecast →</text>` : ""}
      ${MODELS.map(([m, , c]) => (J.m[m] ? `<path d="${line(idx.map((i) => [J.dates[i], J.m[m][i]]))}" fill="none" stroke="${c}" stroke-width="1.5" stroke-linejoin="round" opacity=".92"/>` : "")).join("")}
      ${MODELS.map(([m, , c]) => (fut[m] ? `<path d="${line([[last, J.m[m] ? J.m[m][J.m[m].length - 1] : null], ...fut[m]].filter((p) => p[1] != null))}" fill="none" stroke="${c}" stroke-width="2" stroke-dasharray="5 4"/>` : "")).join("")}
      <path d="${line(idx.map((i) => [J.dates[i], J.actual[i]]))}" fill="none" stroke="var(--ink)" stroke-width="2.2" stroke-linejoin="round"/>`;
    // The gap panel: how far each forecaster was from what happened, a running median.
    const win = Math.max(5, Math.round(20 / step));
    const gp = gaps(J, idx, win);
    const gv = Object.values(gp).flat().filter((v) => v != null).sort((a, b) => a - b);
    const gmax = gv.length ? Math.max(gv[Math.floor(gv.length * 0.98)] * 1.1, 0.002) : 0.01;
    const GY = (v) => H + 16 + (1 - Math.min(v, gmax) / gmax) * (G - 30);
    const gline = (m) => { let s = "", pen = false; idx.forEach((i, k) => { const v = gp[m][k]; if (v == null) { pen = false; return; } s += `${pen ? "L" : "M"}${X(J.dates[i]).toFixed(1)},${GY(v).toFixed(1)}`; pen = true; }); return s; };
    const bottom = `
      <text x="${L}" y="${H + 8}" class="tr-ax rc-gt">How far each was from what happened (running median, lower is better)</text>
      ${[0, gmax / 2, gmax].map((v) => `<line x1="${L}" x2="${W - R}" y1="${GY(v).toFixed(1)}" y2="${GY(v).toFixed(1)}" class="tr-grid"/><text x="${L - 6}" y="${(GY(v) + 4).toFixed(1)}" text-anchor="end" class="tr-ax">${pct(v)}</text>`).join("")}
      ${Object.keys(gp).map((m) => `<path d="${gline(m)}" fill="none" stroke="${MODELS.find((x) => x[0] === m)[2]}" stroke-width="1.8" stroke-linejoin="round"/>`).join("")}
      ${xt.map((d, i) => `<text x="${X(d).toFixed(1)}" y="${H + G - 2}" text-anchor="${i === 0 ? "start" : i === 4 ? "end" : "middle"}" class="tr-ax">${esc(span > 400 ? month(d) : dayL(d))}</text>`).join("")}`;
    return `<svg class="tr-chart rc-svg" viewBox="0 0 ${W} ${H + G}" role="img" aria-label="${esc(J.id)}: what happened against TimesFM, Radiant and Seldon, and how far apart they were">${top}${bottom}</svg>`;
  }

  // Beside the forecast: how each did in the past (replayed), in the view, and now (sealed).
  function board(J, from) {
    const view = typical(J, from);
    const has = (k) => MODELS.filter(([m]) => J[k] && J[k][m]);
    const best = (get) => { let b = null, v = Infinity; for (const [m] of MODELS) { const x = get(m); if (x != null && x < v) { v = x; b = m; } } return b; };
    const bp = best((m) => J.past[m] && J.past[m].typical), bv = best((m) => view[m] && view[m].typical), bn = best((m) => J.now[m] && J.now[m].typical);
    const cell = (label, v, win, sub) => `<div class="${win ? "win" : ""}"><span>${label}</span><b>${v}</b>${sub ? `<small>${sub}</small>` : ""}</div>`;
    const row = ([m, label, c]) => {
      const p = J.past[m], n = J.now[m], v = view[m];
      return `<li style="--c:${c}"><h4><i></i>${label}</h4><div class="rc-cells">
        ${cell("Past", p ? pct(p.typical) : "–", m === bp, p && p.closest != null ? `closest ${pct(p.closest, 0)} of days` : "")}
        ${cell("In view", v ? pct(v.typical) : "–", m === bv, "")}
        ${cell("Now", n ? pct(n.typical) : "–", m === bn, n && n.calls ? `up/down right ${n.right} of ${n.calls}` : "")}</div></li>`;
    };
    const pastFrom = MODELS.map(([m]) => J.past[m] && J.past[m].from).filter(Boolean).sort()[0];
    const pastTo = MODELS.map(([m]) => J.past[m] && J.past[m].to).filter(Boolean).sort().pop();
    const name = { "timesfm-2.5": "TimesFM", radiant: "Radiant", seldon: "Seldon" };
    return `<aside class="rc-board"><h3>How each has done</h3>
      <p class="dim">Typical miss: the middle of each day's gap from what happened. Lower is better; ✦ marks the closest.</p>
      <p class="rc-when"><b>Past</b> ${pastFrom ? `replayed ${esc(month(pastFrom))} – ${esc(month(pastTo))}` : "no replay yet"} · <b>In view</b> ${esc(month(from))} on · <b>Now</b> ${J.live_from ? `sealed since ${esc(dayL(J.live_from))}` : "no sealed day yet"}</p>
      <ul class="rc-models">${(has("past").length || has("now").length ? MODELS : []).map(row).join("")}</ul>
      <p class="rc-say">${bp ? `Over the past, <b>${name[bp]}</b> was closest overall` : "The replay fills in with the next weekly run"}${bn ? `; now, sealed before each day, <b>${name[bn]}</b> is.` : "."}</p>
      <p class="note">Replayed forecasts run up to a month ahead from where each started; sealed ones are the newest made before each day, often a day or two ahead, so they usually miss by less. “Right” counts up-or-down calls.</p></aside>`;
  }

  function render(el, J, D) {
    if (!reaches(J, state.range) && state.range !== "ytd") state.range = RANGES.map((r) => r[0]).filter((k) => reaches(J, k)).pop() || "ytd";
    const last = J.dates[J.dates.length - 1], from = cutoff(last, state.range);
    const buttons = RANGES.map(([k, l]) => {
      const ok = reaches(J, k);
      return `<button class="chip" data-rc="${k}" aria-pressed="${state.range === k}"${ok ? "" : ` disabled title="The replay reaches back to ${esc(month(J.dates[0]))} so far; it adds a few years with every weekly run until ten years are in."`}>${l}</button>`;
    }).join("");
    el.innerHTML = `<div class="rc-head"><div class="chips" role="group" aria-label="Time range">${buttons}</div>
      <span class="tr-legend">${'<span><i style="background:var(--ink)"></i>What happened</span>' + MODELS.filter(([m]) => J.m[m]).map(([, l, c]) => `<span><i style="background:${c}"></i>${l}</span>`).join("")}<span class="dim">dashes: forecast from now</span></span></div>
      <div class="rc-grid"><div class="rc-plot">${svg(J, D, from)}</div>${board(J, from)}</div>
      ${t(J.dates[0]) > t(cutoff(last, "10y")) + 60 * 864e5 ? `<p class="note">The replay reaches back to ${esc(dayL(J.dates[0]))} so far and grows with each weekly run until it covers ten years; days from now on are added as they settle.</p>` : ""}`;
    el.onclick = (e) => { const b = e.target.closest("[data-rc]"); if (b && !b.disabled) { state.range = b.dataset.rc; document.querySelectorAll("[data-race]").forEach((x) => x._race && render(x, x._race, D)); } };
  }

  // Fill every [data-race] placeholder under root; keep the fallback chart inside it if the race is missing.
  function hydrate(root, D) {
    (root || document).querySelectorAll("[data-race]").forEach(async (el) => {
      const J = await load(el.dataset.race);
      if (!J || !J.dates || J.dates.length < 2 || !el.isConnected) return;
      el._race = J; el.classList.add("rc-on");
      render(el, J, D);
    });
  }

  window.WPRace = { hydrate, load, cutoff, reaches, typical };
})();
