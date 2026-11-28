// Track record: every sealed forecast read as a plain call ("Gold will be higher", 64%) and checked
// against what happened, with the running win-loss tally since the first forecast at the top.
// Also "What it says now" for Today. Reads D.tally (built by psychohistory.tally).
(function () {
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const pct = (v) => (v == null ? "–" : Math.round(v * 100) + "%");
  const AREA = { markets: "Markets", news: "World news", politics: "Politics", tech: "Technology", weather: "Weather" };
  const BAND = { "very likely": "Very likely", likely: "Likely", leans: "Leans", tossup: "Toss-up" };
  const MODEL = { "timesfm-2.5": "TimesFM", seldon: "Seldon", "seldon-laws": "Seldon laws", radiant: "Radiant", "radiant-core": "Radiant core",
    "chronos-bolt": "Chronos-Bolt", "auto-ets": "AutoETS", ensemble: "Ensemble" };
  const day = (s, long) => new Date(s + "T12:00:00Z").toLocaleDateString(undefined, long ? { weekday: "short", day: "numeric", month: "short", year: "numeric" } : { day: "numeric", month: "short" });
  const move = (c) => (c >= 0 ? "+" : "−") + Math.abs(c * 100).toFixed(Math.abs(c) < 0.1 ? 1 : 0) + "%";
  // Temperatures change by degrees, not percent; everything else by percent.
  const change = (c) => (c[9] === "temp" ? (c[10] >= 0 ? "+" : "−") + Math.abs(c[10]).toFixed(1) + "°C"
    : c[9] === "rain" ? c[10].toFixed(1) + " mm" : move(c[5]));
  // The three forecasters drawn against what happened, each in its own colour, every time.
  // A level in its own units, precise enough to check: 5,812 not 6k; °C and mm where they apply.
  const val = (v, kind) => {
    if (v == null) return "–";
    if (kind === "temp") return v.toFixed(1) + "°C";
    if (kind === "rain") return v.toFixed(1) + " mm";
    const a = Math.abs(v);
    return a >= 1e6 ? (v / 1e6).toFixed(2) + "M" : a >= 1e3 ? Math.round(v).toLocaleString() : a >= 100 ? v.toFixed(0) : a >= 1 ? v.toFixed(2) : v.toPrecision(2);
  };
  const span = (lo, hi, kind) => `${val(lo, kind)} – ${val(hi, kind)}`;
  const LINES = [["timesfm-2.5", "TimesFM", "var(--tfm)"], ["radiant", "Radiant", "var(--radiant)"], ["seldon", "Seldon", "var(--seldon)"]];
  const FUTURE = { "timesfm-2.5": (o) => o.fan, radiant: (o) => o.radiant, seldon: (o) => o.seldon && o.seldon.fan };
  const t = (s) => Date.parse(s + "T00:00:00Z");
  const num = (v) => { const a = Math.abs(v); return a >= 1e4 ? (v / 1e3).toFixed(0) + "k" : a >= 100 ? v.toFixed(0) : a >= 1 ? v.toFixed(1) : v.toPrecision(2); };

  function chart(id, data, opts = {}) {
    const W = opts.w || 560, H = opts.h || 220, L = 46, R = 10, Tp = 10, B = 24;
    const T2 = data.tally || {}, item = (T2.lines || {})[id], o = (data.outlook || []).find((x) => x.id === id);
    if (!item && !o) return "";
    const back = opts.back || 45;
    const settled = item ? item.actual : [];
    const firstDay = settled.length ? t(settled[0][0]) : Infinity;
    const hist = o && o.history ? o.history.filter(([d]) => t(d) < firstDay).slice(-back) : [];
    const actual = [...hist, ...settled.filter(([d]) => !hist.length || t(d) > t(hist[hist.length - 1][0]))];
    const series = [{ name: "What happened", color: "var(--ink)", pts: actual, w: 2.6 }];
    for (const [m, label, color] of LINES) {
      const past = item && item.m[m] ? item.m[m] : [];
      const fut = o && FUTURE[m](o) ? FUTURE[m](o).map((r) => [r[0], r[2]]) : [];
      if (past.length || fut.length) series.push({ name: label, color, pts: past, fut, w: 1.8 });
    }
    const all = series.flatMap((s) => [...s.pts, ...(s.fut || [])]);
    if (all.length < 2) return "";
    const xs = all.map((p) => t(p[0])), ys = all.map((p) => p[1]).filter(Number.isFinite);
    let [x0, x1] = [Math.min(...xs), Math.max(...xs)], [y0, y1] = [Math.min(...ys), Math.max(...ys)];
    const pad = (y1 - y0 || Math.abs(y1) || 1) * 0.08; y0 -= pad; y1 += pad;
    const X = (d) => L + ((t(d) - x0) / (x1 - x0 || 1)) * (W - L - R), Y = (v) => Tp + (1 - (v - y0) / (y1 - y0)) * (H - Tp - B);
    const path = (pts) => pts.filter((p) => Number.isFinite(p[1])).map((p, i) => `${i ? "L" : "M"}${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join("");
    const lastSettled = settled.length ? settled[settled.length - 1][0] : null;
    const ticks = [y0 + pad, (y0 + y1) / 2, y1 - pad];
    const xt = [x0, (x0 + x1) / 2, x1].map((v) => new Date(v).toISOString().slice(0, 10));
    const svg = `<svg class="tr-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc((opts.title || id) + ": what happened against TimesFM, Radiant and Seldon")}">
      ${ticks.map((v) => `<line x1="${L}" x2="${W - R}" y1="${Y(v).toFixed(1)}" y2="${Y(v).toFixed(1)}" class="tr-grid"/><text x="${L - 6}" y="${(Y(v) + 4).toFixed(1)}" text-anchor="end" class="tr-ax">${num(v)}</text>`).join("")}
      ${xt.map((d, i) => `<text x="${X(d).toFixed(1)}" y="${H - 6}" text-anchor="${["start", "middle", "end"][i]}" class="tr-ax">${esc(day(d))}</text>`).join("")}
      ${lastSettled ? `<line x1="${X(lastSettled).toFixed(1)}" x2="${X(lastSettled).toFixed(1)}" y1="${Tp}" y2="${H - B}" class="tr-now-l"/><text x="${(X(lastSettled) + 4).toFixed(1)}" y="${Tp + 10}" class="tr-ax">forecast →</text>` : ""}
      ${series.slice(1).map((s) => `<path d="${path(s.pts)}" fill="none" stroke="${s.color}" stroke-width="${s.w}" stroke-linejoin="round"/>
        ${s.pts.map((p) => `<circle cx="${X(p[0]).toFixed(1)}" cy="${Y(p[1]).toFixed(1)}" r="2.2" fill="${s.color}"/>`).join("")}
        ${s.fut && s.fut.length ? `<path d="${path(s.fut)}" fill="none" stroke="${s.color}" stroke-width="${s.w}" stroke-dasharray="5 4"/>` : ""}`).join("")}
      <path d="${path(series[0].pts)}" fill="none" stroke="var(--ink)" stroke-width="2.6" stroke-linejoin="round"/></svg>`;
    const legend = `<div class="tr-legend">${series.map((s) => `<span><i style="background:${s.color}"></i>${esc(s.name)}</span>`).join("")}<span class="dim">dots: what each said for that day · dashes: its forecast from now</span></div>`;
    return `<figure class="tr-fig">${opts.title ? `<figcaption><a href="#series/${encodeURIComponent(id)}">${esc(opts.title)}</a></figcaption>` : ""}${svg}${legend}</figure>`;
  }

  function charts() {
    const T2 = T.lines || {};
    const ids = (D.outlook || []).map((o) => o.id).filter((id) => T2[id] && (state.chart === "all" || (D.outlook.find((o) => o.id === id) || {}).domain === state.chart));
    const chips = [["all", "All"], ...Object.entries(AREA)].map(([k, l]) => `<button class="chip" data-tr-chart="${k}" aria-pressed="${state.chart === k}">${l}</button>`).join("");
    const shown = ids.slice(0, state.charts);
    return `<section class="block" aria-labelledby="trc-h"><header class="bh"><div><h2 id="trc-h">What happened, against each forecaster</h2>
      <p>The white line is what really happened. Each colour is a forecaster: the dots are what its newest sealed forecast said each day would be, and the dashed line is its forecast from now.</p></div></header>
      <div class="chips" role="group" aria-label="Area">${chips}</div>
      <div class="tr-grid-c">${shown.map((id) => chart(id, D, { title: name(id) })).join("")}</div>
      ${ids.length > shown.length ? `<button class="btn" data-tr-charts>Show more charts (${ids.length - shown.length} left)</button>` : ""}</section>`;
  }
  const name = (id) => ((T.now || []).find((c) => c.id === id) || {}).name || ((D.outlook || []).find((o) => o.id === id) || {}).title || id;

  // The calls it stands behind: only those sure enough to have been right 80% of the time before.
  function behind() {
    const C = T.confident;
    if (!C || !C.test) return "";
    const x = C.test;
    return `<section class="block tr-behind" aria-labelledby="trs-h"><header class="bh"><div><h2 id="trs-h">The calls it stands behind</h2>
      <p>Not every call deserves the same trust. The rule: stand behind a call only when it is at least as sure as calls that were right ${pct(C.target)} of the time before. The bar was learned on the days up to ${esc(day(C.split))} and then tested on the later days, which it had not seen.</p></div></header>
      <div class="tr-hero">${ring(x.share, 120)}
        <div class="tr-wl"><p class="tr-big"><span class="w">${x.right}</span> right <span class="sep">–</span> <span class="l">${x.wrong}</span> wrong</p>
        <p class="tr-sub">On the later days, calls at ${pct(x.bar)} sure or more were right <b>${pct(x.share)}</b> of the time, against ${pct(x.all_late.share)} for every call. It stood behind ${pct(x.coverage)} of its calls and said “no call” on the rest.</p>
        ${C.bar != null ? `<p class="tr-sub">From ${esc(day(C.found, true))} the bar is ${pct(C.bar)}, learned on every settled day; ${C.live && C.live.n ? `since then: ${C.live.right}–${C.live.wrong} (${pct(C.live.share)})` : "its first live calls settle in the coming days"}.</p>` : ""}</div></div>
      <div class="tr-areas">${x.areas.map((a) => `<div class="tr-area" style="--c:var(--${a.key})"><h3>${esc(a.label)}</h3>
        ${a.n ? `<p class="tr-score"><b>${pct(a.share)}</b> ${a.right}–${a.wrong}</p><div class="tr-bar"><i style="width:${(a.share * 100).toFixed(1)}%"></i><s></s></div>` : `<p class="tr-score"><b>–</b></p>`}
        <p class="tr-v">Stood behind ${a.n} of ${a.of} calls.${a.key === "markets" && a.n && a.share < 0.6 ? " Even its surest market calls are close to a coin flip." : ""}</p></div>`).join("")}</div></section>`;
  }
  // Range calls: "between X and Y", and how often the day landed inside.
  function rangeBlock() {
    const G = T.ranges;
    if (!G || !G.total || !G.total.n) return "";
    const x = G.total;
    return `<section class="block tr-behind tr-range" aria-labelledby="trr-h"><header class="bh"><div><h2 id="trr-h">Range calls: “between X and Y”</h2>
      <p>Up or down is only half the story. Each forecast also gives a range it expects the value to land in, meant to hold 8 times in 10. The model's own ranges turned out too narrow (they held ${pct(x.raw)}), so each one is widened by what earlier ranges needed, learned only from ranges that had already settled when the call was made.</p></div></header>
      <div class="tr-hero">${ring(x.share, 120).replace(">right<", ">inside<")}
        <div class="tr-wl"><p class="tr-big"><span class="w">${x.inside.toLocaleString()}</span> inside <span class="sep">–</span> <span class="l">${x.outside.toLocaleString()}</span> outside</p>
        <p class="tr-sub">Since ${esc(day(G.since, true))}, over ${G.days} days, the day landed inside the range <b>${pct(x.share)}</b> of the time, against ${pct(x.raw)} for the model's ranges as they came.</p>
        <p class="tr-sub">Honest note: the widening aims at ${pct(G.aim)} on past days, a level picked after seeing these weeks, so the clean test is what happens from ${esc(day(G.found, true))}: ${G.live && G.live.n ? `${G.live.inside} of ${G.live.n} inside so far (${pct(G.live.share)})` : "its first ranges settle in the coming days"}.</p></div></div>
      <div class="tr-areas">${G.areas.map((a) => `<div class="tr-area" style="--c:var(--${a.key})"><h3>${esc(a.label)}</h3>
        <p class="tr-score"><b>${pct(a.share)}</b> ${a.inside} of ${a.n}</p><div class="tr-bar" role="img" aria-label="${pct(a.share)} inside, aim 80%"><i style="width:${(a.share * 100).toFixed(1)}%"></i><s style="left:80%"></s></div>
        <p class="tr-v">${a.key === "weather" ? "Temperatures within a few degrees." : a.width != null ? `A typical range spans ${pct(a.width)} of the level${a.width > 0.4 ? ": attention is hard to pin down, so the ranges are wide." : "."}` : ""}</p></div>`).join("")}</div>
      <p class="note">The line on each bar marks 80%. A range that is right far more often than 80% is wider than it needs to be.</p></section>`;
  }
  // Surprises: the days reality landed outside the range, the furthest out first (measured in range widths).
  function surprises(limit = 8, span14 = 14) {
    const days = (T.days || []).slice(0, span14);
    const ranged = days.flatMap((d) => d.calls.filter((c) => c[11] && c[11].length > 3 && c[11][1] > c[11][0]).map((c) => ({ c, date: d.date })));
    if (ranged.length < 10) return "";
    const held = ranged.filter((x) => x.c[11][2]).length;
    const out = ranged.filter((x) => !x.c[11][2]).map((x) => {
      const [lo, hi, , v] = x.c[11], w = hi - lo;
      return { ...x, lo, hi, v, by: v < lo ? (lo - v) / w : (v - hi) / w, below: v < lo };
    }).filter((x) => x.by > 0).sort((a, b) => b.by - a.by)
      .filter((x, i, all) => all.findIndex((y) => y.c[0] === x.c[0]) === i).slice(0, limit);  // each series once, at its biggest miss
    if (!out.length) return "";
    const bar = (x) => {
      const a = Math.min(x.lo, x.v), b = Math.max(x.hi, x.v), pad = (b - a) * 0.08 || 1, A = a - pad, W = b + pad - A;
      const px = (v) => (((v - A) / W) * 100).toFixed(1);
      return `<span class="tr-sp-bar" aria-hidden="true"><s style="left:${px(x.lo)}%;width:${(px(x.hi) - px(x.lo)).toFixed(1)}%"></s><i style="left:${px(x.v)}%"></i></span>`;
    };
    return `<section class="block" aria-labelledby="trp-h"><header class="bh"><div><h2 id="trp-h">Surprises: where it landed outside the range</h2>
      <p>Over the last ${days.length} days, ${held} of ${ranged.length} ranges held (${pct(held / ranged.length)}). These are the ones that missed by the most (each thing once, at its biggest miss), measured against how wide the range was. The shaded box is the range, the dot is what happened.</p></div></header>
      <div class="tr-sp">${out.map((x) => `<a class="tr-sp-c" href="#series/${esc(x.c[0])}" style="--c:var(--${esc(x.c[1])})">
        <span class="tr-sp-h"><b>${esc(x.c[2])}</b><small>${esc(day(x.date))}</small></span>${bar(x)}
        <span class="tr-sp-t">Landed at <b>${val(x.v, x.c[9])}</b>, ${x.below ? "below" : "above"} its likely ${span(x.lo, x.hi, x.c[9])}</span>
        <span class="tr-sp-k">${x.by >= 1 ? `${x.by.toFixed(1)} range widths out` : `${Math.round(x.by * 100)}% of a range width out`} · the up/down call was ${x.c[4] ? "right" : "wrong"}</span></a>`).join("")}</div></section>`;
  }
  const state = { area: "all", shown: 7, chart: "all", charts: 6 };
  let D, T;

  // A ring filled to the share right; green from 60%, amber around a coin flip, red below it.
  function ring(share, size = 132) {
    const r = size / 2 - 9, c = 2 * Math.PI * r, col = share >= 0.6 ? "var(--up)" : share >= 0.5 ? "var(--warn)" : "var(--down)";
    return `<svg class="tr-ring" viewBox="0 0 ${size} ${size}" width="${size}" height="${size}" role="img" aria-label="${pct(share)} right">
      <circle cx="${size / 2}" cy="${size / 2}" r="${r}" class="ring-bg"/>
      <circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="${col}" stroke-width="12" stroke-linecap="round"
        stroke-dasharray="${c.toFixed(1)}" stroke-dashoffset="${(c * (1 - share)).toFixed(1)}" transform="rotate(-90 ${size / 2} ${size / 2})"/>
      <text x="50%" y="47%" text-anchor="middle" class="tr-ring-n">${Math.round(share * 100)}%</text>
      <text x="50%" y="66%" text-anchor="middle" class="tr-ring-l">right</text></svg>`;
  }

  // One area's verdict in a sentence: coin flip, the best single guess with hindsight, or a real edge.
  function verdict(a) {
    if (a.share <= 0.53) return `No better than a coin flip so far. Always saying “${a.hindsight_call}” would have got ${pct(a.hindsight)}.`;
    if (a.share < a.hindsight + 0.05) return `Better than a coin flip, but about what always saying “${a.hindsight_call}” got (${pct(a.hindsight)}), so no clear edge yet.`;
    return `Better than a coin flip and than always saying “${a.hindsight_call}” (${pct(a.hindsight)}).`;
  }

  function scoreboard() {
    const R = T.record, t = R.total, w = R.week;
    return `<section class="block tr-top" aria-labelledby="tr-h">
      <div class="tr-hero">
        ${ring(t.share)}
        <div class="tr-wl">
          <h2 id="tr-h">Track record</h2>
          <p class="tr-big"><span class="w">${t.right.toLocaleString()}</span> right <span class="sep">–</span> <span class="l">${t.wrong.toLocaleString()}</span> wrong</p>
          <p class="tr-sub">Every call since the first forecast on ${esc(day(R.since, true))}: ${t.n.toLocaleString()} calls on ${R.series} things it follows, over ${R.days} days. A coin flip would get 50%.</p>
          <div class="tr-pills">
            <span><b>Last 7 days</b> ${w.right}–${w.wrong} (${pct(w.share)})</span>
            <span><b>Streak</b> ${R.streak.days} day${R.streak.days === 1 ? "" : "s"} ${R.streak.good ? "with more right than wrong" : "with more wrong than right"}</span>
          </div>
        </div>
      </div>
      <p class="tr-how"><b>How a call is made.</b> Each forecast gives the chance that something will be higher than the last value it saw. The call is the side it gave more than 50%: a 65% chance of gold being higher is the call “Gold will be higher”, and it counts as right if gold was higher on the day. Each day of each thing counts once, using the newest call made before that day.</p>
    </section>`;
  }

  function areas() {
    const A = T.record.areas;
    return `<section class="block" aria-labelledby="tra-h"><header class="bh"><div><h2 id="tra-h">By area</h2>
      <p>Right and wrong for each kind of forecast. The bar is the share right; the line marks a coin flip.</p></div></header>
      <div class="tr-areas">${A.map((a) => `<div class="tr-area" style="--c:var(--${a.key})">
        <h3>${esc(a.label)}</h3>
        <p class="tr-score"><b>${pct(a.share)}</b> ${a.right}–${a.wrong}</p>
        <div class="tr-bar" role="img" aria-label="${pct(a.share)} right, coin flip 50%"><i style="width:${(a.share * 100).toFixed(1)}%"></i><s></s></div>
        <p class="tr-v">${esc(verdict(a))}</p></div>`).join("")}</div>
      ${A.some((a) => a.key === "markets") ? `<p class="note">Markets are the hardest: up or down over a few days is close to a coin flip for every model here, and the <a href="#markets">Markets desk</a> found that trading on the calls would not have beaten simply holding.</p>` : ""}
    </section>`;
  }

  function sureness() {
    const B = T.record.bands;
    return `<section class="block" aria-labelledby="trb-h"><header class="bh"><div><h2 id="trb-h">How sure it was, and how often it was right</h2>
      <p>If the chances are honest, calls made at 90% should be right about 9 times in 10, and toss-ups about half the time.</p></div></header>
      <div class="tr-bands">${B.map((b) => `<div class="tr-band"><span class="tr-bl">${esc(b.label)}</span>
        <div class="tr-pair"><div class="tr-b said" style="width:${(b.said * 100).toFixed(1)}%"><span>said ${pct(b.said)}</span></div>
        <div class="tr-b got" style="width:${(b.share * 100).toFixed(1)}%"><span>right ${pct(b.share)}</span></div></div>
        <span class="tr-bn">${b.right} of ${b.n}</span></div>`).join("")}</div>
      <p class="hy-verdict">${esc(bandsVerdict(B))}</p></section>`;
  }
  function bandsVerdict(B) {
    const top = B.find((b) => b.key === "very likely"), low = B.find((b) => b.key === "tossup");
    const parts = [];
    if (top) parts.push(`When it said “very likely”, it was right ${pct(top.share)} of the time (${top.right} of ${top.n}).`);
    if (low) parts.push(`Its toss-ups really were toss-ups: right ${pct(low.share)}.`);
    parts.push("Trust the confident calls most.");
    return parts.join(" ");
  }

  function models() {
    const M = T.models || [];
    if (M.length < 2) return "";
    return `<details class="block tr-models"><summary><h2>The other forecasters, scored the same way</h2></summary>
      <p class="dim">Each model's own calls on the days it covered (Seldon and Radiant joined later, so they cover fewer days).</p>
      <div class="table-wrap"><table class="ev-table"><thead><tr><th>Forecaster</th><th>Right</th><th>Wrong</th><th>Share right</th></tr></thead>
      <tbody>${M.map((m) => `<tr${m.model === T.model ? ' class="me"' : ""}><td>${esc(MODEL[m.model] || m.model)}${m.model === T.model ? " (the calls above)" : ""}</td><td>${m.right}</td><td>${m.wrong}</td><td><b>${pct(m.share)}</b></td></tr>`).join("")}</tbody></table></div></details>`;
  }

  function log() {
    const days = (T.days || []).map((d) => {
      const calls = state.area === "all" ? d.calls : d.calls.filter((c) => c[1] === state.area);
      const right = calls.filter((c) => c[4]).length;
      return { ...d, calls, right, wrong: calls.length - right };
    }).filter((d) => d.calls.length);
    const chips = [["all", "All"], ...Object.entries(AREA)].map(([k, l]) => `<button class="chip" data-tr-area="${k}" aria-pressed="${state.area === k}">${l}</button>`).join("");
    const shown = days.slice(0, state.shown);
    return `<section class="block" aria-labelledby="trl-h"><header class="bh"><div><h2 id="trl-h">Every day: what it said, and what happened</h2>
      <p>Newest first; tap a day to open or close it. ✓ right, ✗ wrong. The chance is how sure it was when it made the call; “compared with” is the last value it had seen.</p></div></header>
      <div class="chips" role="group" aria-label="Area">${chips}</div>
      ${calendar(days)}
      ${shown.map((d, i) => `<details class="tr-day" id="tr-d-${esc(d.date)}"${i < 2 || d.date === state.open ? " open" : ""}><summary><h3>${esc(day(d.date, true))} <span class="tr-dscore ${d.right >= d.wrong ? "good" : "bad"}">${d.right} right, ${d.wrong} wrong (${pct(d.right / d.calls.length)})</span>
          <span class="tr-strip" aria-hidden="true">${d.calls.map((c) => `<i class="${c[4] ? "ok" : "no"}"></i>`).join("")}</span></h3></summary>
        <ul class="tr-calls">${d.calls.map((c) => `<li class="${c[4] ? "ok" : "no"}"><span class="tr-mark" aria-label="${c[4] ? "right" : "wrong"}">${c[4] ? "✓" : "✗"}</span>
          <span class="tr-call"><b>${esc(c[2])}</b><small>called on ${esc(day(c[6]))}, compared with ${esc(day(c[7]))}</small></span>
          <span class="tr-chance b-${(c[3] >= 0.8 ? "very likely" : c[3] >= 0.7 ? "likely" : c[3] >= 0.6 ? "leans" : "tossup").replace(" ", "-")}">${pct(c[3])}</span>
          <span class="tr-what">${esc(c[8][0].toUpperCase() + c[8].slice(1))} <small>${change(c)}</small>${c[11] ? `<small class="tr-rl ${c[11][2] ? "ok" : "no"}">range ${span(c[11][0], c[11][1], c[9])} ${c[11][2] ? "✓" : "✗"}</small>` : ""}</span></li>`).join("")}</ul></details>`).join("")}
      ${days.length > state.shown ? `<button class="btn" data-tr-more>Show 7 more days (${days.length - state.shown} left)</button>` : ""}
    </section>`;
  }

  // Every day at a glance: one square per day, greener the more calls came true, redder the fewer.
  function calendar(days) {
    if (days.length < 2) return "";
    const byDate = new Map(days.map((d) => [d.date, d]));
    const first = new Date(days[days.length - 1].date + "T00:00:00Z"), last = new Date(days[0].date + "T00:00:00Z");
    const lead = (first.getUTCDay() + 6) % 7;  // Monday first
    const cells = Array.from({ length: lead }, () => `<i class="tr-cal-x"></i>`);
    for (let t = first.getTime(); t <= last.getTime(); t += 864e5) {
      const iso = new Date(t).toISOString().slice(0, 10), d = byDate.get(iso);
      if (!d) { cells.push(`<i class="tr-cal-x tr-cal-none" title="${esc(day(iso, true))}: nothing came due"></i>`); continue; }
      const share = d.right / d.calls.length, k = Math.max(-1, Math.min(1, (share - 0.5) * 2.5));
      const col = k >= 0 ? "var(--up)" : "var(--down)", mix = Math.round(18 + 72 * Math.abs(k));
      cells.push(`<button class="tr-cal-d" data-tr-day="${iso}" style="background:color-mix(in oklab, ${col} ${mix}%, var(--panel-2, var(--panel)))"
        title="${esc(day(iso, true))}: ${d.right} right, ${d.wrong} wrong (${pct(share)})" aria-label="${esc(day(iso, true))}: ${d.right} right, ${d.wrong} wrong"></button>`);
    }
    const ranked = days.filter((d) => d.calls.length >= 5).sort((a, b) => b.right / b.calls.length - a.right / a.calls.length);
    const best = ranked[0], worst = ranked[ranked.length - 1], good = days.filter((d) => d.right > d.wrong).length;
    return `<div class="tr-cal"><div class="tr-cal-g"><span class="tr-cal-w" aria-hidden="true"><b>Mon</b><b></b><b>Wed</b><b></b><b>Fri</b><b></b><b>Sun</b></span>
        <div class="tr-cal-grid" role="group" aria-label="Every day at a glance">${cells.join("")}</div></div>
      <div class="tr-cal-k"><p><b>Every day at a glance.</b> ${good} of ${days.length} days had more right than wrong.${best && worst && best !== worst ? ` Best: ${esc(day(best.date))}, ${best.right} of ${best.calls.length}. Worst: ${esc(day(worst.date))}, ${worst.right} of ${worst.calls.length}.` : ""} Tap a day to open it below.</p>
        <span class="tr-cal-l" aria-hidden="true">fewer right <i style="background:var(--down)"></i><i style="background:color-mix(in oklab, var(--down) 40%, var(--panel))"></i><i style="background:color-mix(in oklab, var(--up) 18%, var(--panel))"></i><i style="background:color-mix(in oklab, var(--up) 55%, var(--panel))"></i><i style="background:var(--up)"></i> more right</span></div></div>`;
  }

  // ---------- What it says now: plain calls for about a week ahead, for Today ----------
  function nowCards(data, limit = 12) {
    const T2 = data.tally;
    if (!T2 || !T2.now || !T2.now.length) return "";
    const pick = [];
    for (const [k] of Object.entries(AREA)) {  // the surest few from every area, so markets are never left out
      pick.push(...T2.now.filter((c) => c.domain === k).slice(0, k === "markets" ? 4 : 2));
    }
    const R = T2.record;
    return `<section class="block tr-now" aria-labelledby="trn-h"><header class="bh"><div><h2 id="trn-h">What it says now</h2>
      <p>About a week ahead, in plain words, with how sure it is and how often it has been right on that one so far.</p></div>
      ${R ? `<a class="pm" href="#record">Its record: ${R.total.right}–${R.total.wrong} (${pct(R.total.share)})</a>` : ""}</header>
      <div class="tr-cards">${pick.slice(0, limit).map((c) => `<a class="tr-card ${c.up ? "up" : "down"}" href="#series/${encodeURIComponent(c.id)}" style="--c:var(--${c.domain})">
        <span class="tr-area-l">${esc(AREA[c.domain] || c.domain)}</span>
        <b>${esc(c.call)}</b>
        <span class="tr-meta"><span class="tr-chance b-${c.band.replace(" ", "-")}">${esc(BAND[c.band] || c.band)} · ${pct(c.chance)}</span>
        ${c.record ? `<span>right ${c.record.right} of ${c.record.n}</span>` : "<span>no record yet</span>"}</span>
        ${c.lo != null ? `<span class="tr-rng"${c.range_record ? ` title="Its ranges here held ${c.range_record[0]} of ${c.range_record[1]} times so far"` : ""}>Likely <b>${span(c.lo, c.hi, c.kind)}</b></span>` : ""}
        <span class="tr-foot"><span>by ${esc(day(c.target))}</span>${T2.confident && T2.confident.bar != null ? (c.chance >= T2.confident.bar ? `<span class="tr-sb yes">✓ stands behind it</span>` : `<span class="tr-sb">a guess, below its ${pct(T2.confident.bar)} bar</span>`) : ""}</span></a>`).join("")}</div></section>`;
  }

  // ---------- Since you last looked: the calls that came due between two visits, for Today ----------
  const LAST = "wp-last-visit-v1";
  let prevVisit;  // read once per page load, so re-rendering Today does not swallow the news
  function since(data) {
    const T2 = data.tally;
    if (!T2 || !T2.days || !T2.days.length) return "";
    const newest = T2.days[0].date;
    if (prevVisit === undefined) {
      try { prevVisit = JSON.parse(localStorage.getItem(LAST)); } catch (e) { prevVisit = null; }
      try { localStorage.setItem(LAST, JSON.stringify({ seen: newest, at: new Date().toISOString().slice(0, 10) })); } catch (e) { /* private mode */ }
    }
    if (!prevVisit || !prevVisit.seen || newest <= prevVisit.seen) return "";
    const fresh = T2.days.filter((d) => d.date > prevVisit.seen);
    const calls = fresh.flatMap((d) => d.calls), right = calls.filter((c) => c[4]).length;
    if (!calls.length) return "";
    const miss = calls.filter((c) => !c[4]).sort((a, b) => b[3] - a[3])[0];
    const hit = calls.filter((c) => c[4]).sort((a, b) => b[3] - a[3])[0];
    return `<section class="tr-since" aria-label="Since you last looked">
      <span class="tr-since-ring">${ring(right / calls.length, 56)}</span>
      <div><p class="tr-since-h"><b>Since you last looked</b>${prevVisit.at ? ` on ${esc(day(prevVisit.at))}` : ""}: ${calls.length} calls came due over ${fresh.length} day${fresh.length === 1 ? "" : "s"}, <span class="w">${right} right</span> and <span class="l">${calls.length - right} wrong</span>.</p>
      <p class="tr-since-s">${hit ? `Surest hit: “${esc(hit[2])}” at ${pct(hit[3])}.` : ""} ${miss ? `Biggest miss: “${esc(miss[2])}” at ${pct(miss[3])}.` : ""} <a href="#record">Every day, right or wrong</a></p></div></section>`;
  }

  // One series in plain words, for its own page: the call now, and its last ten calls right or wrong.
  function seriesCard(data, id) {
    const T2 = data.tally;
    if (!T2) return "";
    const c = (T2.now || []).find((x) => x.id === id);
    const past = [];
    for (const d of T2.days || []) { for (const k of d.calls) if (k[0] === id) past.push([d.date, k]); if (past.length >= 10) break; }
    if (!c && !past.length && !(T2.lines || {})[id]) return "";
    const rec = c && c.record;
    return `<div class="card tr-series"><header class="ph"><h2>In plain words</h2>${rec ? `<span class="pm">its record here: ${rec.right} right, ${rec.wrong} wrong (${pct(rec.share)})</span>` : ""}</header>
      ${c ? `<p class="tr-says ${c.up ? "up" : "down"}"><b>${esc(c.call)}</b> by ${esc(day(c.target))} <span class="tr-chance b-${c.band.replace(" ", "-")}">${esc(BAND[c.band] || c.band)} · ${pct(c.chance)}</span></p>` : ""}
      ${c && c.lo != null ? `<p class="tr-rng big">Likely between <b>${span(c.lo, c.hi, c.kind)}</b> on ${esc(day(c.target))} (aimed at 8 times in 10)${c.range_record ? `. Its ranges here held ${c.range_record[0]} of ${c.range_record[1]} times so far.` : "."}</p>` : ""}
      <div class="rc" data-race="${esc(id)}">${chart(id, data, { w: 1000, h: 300, back: 60 })}</div>
      ${past.length ? `<p class="dim" style="margin:8px 0 4px">Its last ${past.length} calls here, newest first:</p><ul class="tr-calls">${past.map(([dt, k]) => `<li class="${k[4] ? "ok" : "no"}"><span class="tr-mark">${k[4] ? "✓" : "✗"}</span>
        <span class="tr-call"><b>${esc(k[2])}</b><small>for ${esc(day(dt))}</small></span><span class="tr-chance">${pct(k[3])}</span><span class="tr-what">${esc(k[8][0].toUpperCase() + k[8].slice(1))} <small>${change(k)}</small>${k[11] ? `<small class="tr-rl ${k[11][2] ? "ok" : "no"}">range ${span(k[11][0], k[11][1], k[9])} ${k[11][2] ? "✓" : "✗"}</small>` : ""}</span></li>`).join("")}</ul>` : ""}
      <p class="note" style="margin:8px 0 0"><a href="#record">The whole track record</a></p></div>`;
  }

  function page() {
    if (!T || !T.record) {
      return `<section class="block"><h2>Track record</h2><div class="empty"><b>No call has come due yet.</b>The first ones settle a day after the first weekly forecast.</div></section>`;
    }
    return scoreboard() + behind() + rangeBlock() + surprises() + nowCards(D, 12).replace('class="pm" href="#record"', 'class="pm" hidden href="#record"') + charts() + areas() + sureness() + log() + models();
  }

  function render(host, data) {
    D = data; T = data.tally;
    host.innerHTML = page();
    host.onclick = (e) => {
      const a = e.target.closest("[data-tr-area]"), more = e.target.closest("[data-tr-more]"), cal = e.target.closest("[data-tr-day]");
      if (cal) {
        const iso = cal.dataset.trDay, all = (T.days || []).map((d) => d.date), at = all.indexOf(iso);
        state.open = iso; if (at >= state.shown) state.shown = at + 1;
        host.innerHTML = page();
        const el = host.querySelector(`#tr-d-${iso}`);
        if (el) { el.open = true; el.scrollIntoView({ behavior: "smooth", block: "start" }); }
        return;
      }
      const ch = e.target.closest("[data-tr-chart]"), mc = e.target.closest("[data-tr-charts]");
      if (ch || mc) { const y = window.scrollY; if (ch) { state.chart = ch.dataset.trChart; state.charts = 6; } else state.charts += 6; host.innerHTML = page(); window.scrollTo(0, y); return; }
      if (a) { state.area = a.dataset.trArea; state.shown = 7; host.innerHTML = page(); }
      else if (more) { state.shown += 7; const y = window.scrollY; host.innerHTML = page(); window.scrollTo(0, y); }
    };
  }

  window.WPRecord = { render, now: nowCards, since, verdict, seriesCard, chart, surprises: (data, n) => { D = data; T = data.tally; return surprises(n); } };
})();
