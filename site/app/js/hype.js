// The hype cycle: where each new technology's public attention stands on Gartner's curve (peak,
// trough, plateau), from its Wikipedia views since 2015, with real adoption beside it where there
// is a measure, and the record of what each phase foretold for the next three months.
// Reads D.hype (built by psychohistory.hype) and, for TimesFM's own four-week view, D.outlook.
(function () {
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const sp = (v) => { if (v === null || v === undefined || !isFinite(v)) return "–"; const r = Math.round(v * 100); return r === 0 ? "0%" : (r > 0 ? "+" : "−") + Math.abs(r) + "%"; };
  const pc = (a, b) => (b ? Math.round((100 * a) / b) + "%" : "–");
  const big = (v) => (v >= 1e4 ? Math.round(v / 1e3) + "k" : v >= 1e3 ? (v / 1e3).toFixed(1) + "k" : Math.round(v));
  const month = (s) => { const d = new Date(String(s).slice(0, 10) + "T12:00:00Z"); return isNaN(d) ? s : d.toLocaleDateString(undefined, { month: "short", year: "numeric", timeZone: "UTC" }); };
  const day = (s) => { const d = new Date(String(s).slice(0, 10) + "T12:00:00Z"); return isNaN(d) ? s : d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }); };
  const CALL = { up: "up", down: "down", flat: "about the same" };
  const PHASE_C = { rising: "var(--t-major, var(--up))", peak: "var(--down)", sliding: "var(--warn)", trough: "var(--tfm)", recovering: "var(--up)", plateau: "var(--tech)" };
  const ORDER = ["rising", "peak", "sliding", "trough", "recovering", "plateau"];
  let D, H;

  // The textbook curve, drawn once: a sharp peak of expectations, a trough, then a slow climb to a plateau.
  const curveY = (x) => 0.06 + 0.82 * Math.exp(-(((x - 0.25) / 0.085) ** 2)) + 0.42 / (1 + Math.exp(-(x - 0.7) / 0.06));
  // Where a technology sits: its phase's spot, spread a little when several share a phase.
  function placed(items) {
    const by = {};
    items.forEach((it) => (by[it.phase] = by[it.phase] || []).push(it));
    return items.map((it) => {
      const g = by[it.phase], k = g.indexOf(it), spread = g.length > 1 ? (k / (g.length - 1) - 0.5) * Math.min(0.16, 0.045 * (g.length - 1)) : 0;
      return { it, x: Math.min(0.97, Math.max(0.03, it.x + spread)) };
    });
  }

  function curve(items) {
    const w = 900, h = 330, padX = 20, top = 64, bottom = 44;
    const X = (x) => padX + x * (w - 2 * padX), Y = (y) => h - bottom - (y / 1.05) * (h - top - bottom);
    let path = "";
    for (let i = 0; i <= 200; i++) { const x = i / 200; path += `${i ? "L" : "M"}${X(x).toFixed(1)} ${Y(curveY(x)).toFixed(1)}`; }
    const marks = [["Climbing", 0.13], ["Peak of expectations", 0.27], ["Sliding", 0.42], ["Trough of disillusionment", 0.555], ["Climbing back", 0.7], ["Plateau", 0.89]];
    // Labels go above or below their dot, on the first row free of every label placed so far.
    const spots = placed(items).sort((a, b) => a.x - b.x);
    const boxes = spots.map(({ x }) => { const cx = X(x), cy = Y(curveY(x)); return [cx - 8, cy - 8, cx + 8, cy + 8]; }), OFFS = [-16, 24, -34, 42, -52, 60, -70, 78, -88, -106, -124, -142];
    const dots = spots.map(({ it, x }) => {
      const cx = X(x), cy = Y(curveY(x)), half = it.name.length * 3.6 + 6;
      let ly = null;
      for (const o of OFFS) {
        const y = cy + o, box = [cx - half, y - 13, cx + half, y + 3];
        if (y < 14 || y > h - bottom + 4) continue;
        if (!boxes.some((q) => box[0] < q[2] && box[2] > q[0] && box[1] < q[3] && box[3] > q[1])) { ly = y; boxes.push(box); break; }
      }
      if (ly === null) ly = cy - 16;
      const up = ly < cy;
      return `<a href="#series/${esc(it.id)}" class="hy-dot" style="--c:${PHASE_C[it.phase]}" aria-label="${esc(it.name)}: ${esc(it.label)}">
        <line x1="${cx.toFixed(1)}" y1="${cy.toFixed(1)}" x2="${cx.toFixed(1)}" y2="${(up ? ly + 4 : ly - 12).toFixed(1)}"/>
        <circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="6.5"/><text x="${cx.toFixed(1)}" y="${ly.toFixed(1)}" text-anchor="middle">${esc(it.name)}</text></a>`;
    }).join("");
    const label = items.map((it) => `${it.name}: ${it.label}`).join("; ");
    return `<div class="hy-scroll"><svg class="hy-curve" viewBox="0 0 ${w} ${h}" role="img" aria-label="The hype cycle. ${esc(label)}">
      <path class="hy-line" d="${path}"/>
      ${marks.map(([t, x]) => `<text class="hy-axis" x="${X(x).toFixed(1)}" y="${h - 14}" text-anchor="middle">${esc(t)}</text>`).join("")}
      <text class="hy-axis" x="${padX}" y="14">Attention</text><text class="hy-axis" x="${w - padX}" y="${h - 30}" text-anchor="end">Time →</text>
      ${dots}</svg></div>`;
  }

  // The real curve: the 90-day mean of daily views since 2015, its peak and today.
  function spark(it, w = 260, h = 64) {
    const pts = (it.curve || []).filter(([, v]) => v !== null);
    if (pts.length < 3) return "";
    const vals = pts.map(([, v]) => v), hi = Math.max(...vals) * 1.06, lo = 0;
    const x = (i) => ((i / (pts.length - 1)) * (w - 8) + 4).toFixed(1), y = (v) => (h - 4 - ((v - lo) / (hi - lo)) * (h - 10)).toFixed(1);
    const peakI = vals.indexOf(Math.max(...vals)), last = pts.length - 1;
    const line = pts.map(([, v], i) => `${i ? "L" : "M"}${x(i)} ${y(v)}`).join("");
    return `<svg class="hy-spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true">
      <path class="area" d="${line}L${x(last)} ${h}L${x(0)} ${h}Z"/><path d="${line}"/>
      <circle class="pk" cx="${x(peakI)}" cy="${y(vals[peakI])}" r="3.5"/><circle class="nw" cx="${x(last)}" cy="${y(vals[last])}" r="3.5"/></svg>`;
  }

  function tfm(it) {
    const o = (D.outlook || []).find((x) => x.id === it.id);
    if (!o || o.change === undefined || o.change === null) return "";
    const agree = (it.call === "up" && o.change > 0.03) || (it.call === "down" && o.change < -0.03) || (it.call === "flat" && Math.abs(o.change) <= 0.03);
    return `<li><span>TimesFM, next 4 weeks</span><b>${sp(o.change)}</b><small>${agree ? "agrees" : "differs"}</small></li>`;
  }

  function card(it) {
    const a = it.adoption;
    const adopt = a ? `<p class="hy-adopt${it.faded ? " faded" : ""}"><span>Adoption</span> ${esc(a.title)}: <b>${esc(String(+a.last.toPrecision(3)))}</b> in ${a.year}${a.change !== null && a.change !== undefined ? ` (${sp(a.change)} since ${a.since})` : ""}${it.faded ? "<em>Attention faded while adoption grew: the hype cycle's signature.</em>" : ""}</p>` : "";
    return `<a class="hy-card" href="#series/${esc(it.id)}" style="--c:${PHASE_C[it.phase]}">
      <div class="hy-top"><b>${esc(it.name)}</b><span class="hy-pill">${esc(it.label)}</span></div>
      ${spark(it)}
      <div class="hy-axis2"><span>${esc(month(it.since))}</span><span>peak ${esc(month(it.peak_date))}</span><span>${esc(month(it.last))}</span></div>
      <ul class="hy-facts">
        <li><span>Against its peak</span><b>${Math.round(it.level * 100)}%</b><small>${big(it.now)} vs ${big(it.peak)} views a day</small></li>
        <li><span>Last 90 days vs the 90 before</span><b>${sp(Math.expm1(it.slope))}</b></li>
        <li><span>The phase says, next 90 days</span><b>${esc(CALL[it.call])}</b></li>
        ${it.burst ? `<li><span>The burst rule says</span><b>${esc(CALL[it.burst])}</b><small>${it.burst === "flat" ? `no move of ${Math.round(H.rules.burst * 100)}% or more to undo` : `a ${Math.round(H.rules.burst * 100)}%+ move tends to reverse`}</small></li>` : ""}
        ${tfm(it)}
      </ul>${adopt}</a>`;
  }

  function record() {
    const R = H.record;
    if (!R) return `<section class="block"><header class="bh"><div><h2>Did the phases know anything?</h2></div></header>
      <div class="empty"><b>Not enough history yet.</b>The record needs at least ${Math.round((((H.rules || {}).min_history || 365) + ((H.rules || {}).window || 90)) / 30)} months of views per technology; the next forecast run fills it from the full history since 2015.</div></section>`;
    const rows = ORDER.filter((p) => R.by_phase[p]).map((p) => {
      const g = R.by_phase[p], r = H.rules.phases[p];
      return `<tr><th scope="row"><span class="hy-sw" style="--c:${PHASE_C[p]}"></span>${esc(r.label)}</th><td>${g.n}</td><td>${esc(CALL[r.call])}</td>
        <td><b>${pc(g.hit, g.n)}</b></td><td>${pc(g.momentum, g.n)}</td><td>${g.burst !== undefined ? pc(g.burst, g.n) : "–"}</td><td>${g.up} up · ${g.down} down</td><td>${sp(g.median_change)}</td></tr>`;
    }).join("");
    const ap = R.after_peak;
    const tiles = [["hype", "the hype cycle right", "the phase's call"], ["momentum", "momentum right", "the last 90 days' direction carries on"],
      ["reversal", "reversal right", "the last 90 days' direction turns"],
      ["burst", "the burst rule right", `a ${Math.round(H.rules.burst * 100)}%+ move reverses, else no change; read off this backtest`], ["flat", "\"no change\" right", `within ±${Math.round(H.rules.flat * 100)}%`]]
      .filter(([k]) => R[k] !== undefined);
    const top = Math.max(...tiles.map(([k]) => R[k]));
    return `<section class="block" aria-labelledby="hyr-h"><header class="bh"><div><h2 id="hyr-h">Did the phases know anything?</h2>
      <p>Once a month from ${esc(month(R.first))} to ${esc(month(R.last))}, each technology's phase was read from the views up to that day only, and its call checked against the next 90 days (flat means within ±${Math.round(H.rules.flat * 100)}%).</p></div></header>
      <div class="hy-score">
        ${tiles.map(([k, t, sm]) => `<div${R[k] === top ? ' class="best"' : ""}><b>${pc(R[k], R.n)}</b><span>${esc(t)}</span><small>${esc(sm)}</small></div>`).join("")}
        ${ap.n ? `<div><b>${pc(ap.fell, ap.n)}</b><span>fell after a peak</span><small>against ${Math.round(ap.base * 100)}% of all windows${ap.p !== null && ap.p !== undefined ? `, p ${ap.p < 0.001 ? "< 0.001" : ap.p.toFixed(3)}` : ""}</small></div>` : ""}
      </div>
      <p class="hy-verdict">${esc(H.verdict)}</p>
      <div class="table-wrap"><table class="ev-table hy-table"><thead><tr><th>Phase</th><th>Calls</th><th>Says</th><th>Right</th><th>Momentum right</th><th>Burst rule right</th><th>What happened</th><th>Median next 90 days</th></tr></thead>
      <tbody>${rows}</tbody></table></div></section>${bursts(R)}`;
  }

  // What the next 90 days did after attention had jumped, eased or held: big moves tend to fade.
  function bursts(R) {
    if (!R.bursts || !R.bursts.length) return "";
    const pv = (p) => (p === null || p === undefined ? "" : p < 0.001 ? "p < 0.001" : `p ${p.toFixed(2)}`);
    const rows = R.bursts.map((b) => {
      const w = (k) => (100 * b[k]) / b.n;
      return `<li class="${b.back ? "" : "mid"}"><span class="hy-bl">${esc(b.label)}<small>${b.n} calls</small></span>
        <span class="hy-bar" role="img" aria-label="${esc(b.label)}: next 90 days rose ${pc(b.up, b.n)}, flat ${pc(b.flat, b.n)}, fell ${pc(b.down, b.n)}">
          <i class="u" style="width:${w("up").toFixed(1)}%">${w("up") >= 12 ? pc(b.up, b.n) : ""}</i><i class="f" style="width:${w("flat").toFixed(1)}%">${w("flat") >= 12 ? pc(b.flat, b.n) : ""}</i><i class="d" style="width:${w("down").toFixed(1)}%">${w("down") >= 12 ? pc(b.down, b.n) : ""}</i></span>
        <span class="hy-bm"><b>${sp(b.median_change)}</b><small>${b.back ? `${b.back === "down" ? "fell" : "rose"} back · ${pv(b.p)}` : "median"}</small></span></li>`;
    }).join("");
    const sf = R.since_found;
    const fair = sf ? (sf.n ? `Since ${esc(day(sf.from))}, the fair test: the burst rule right ${sf.burst} times in ${sf.n} settled calls (${pc(sf.burst, sf.n)}), "no change" ${pc(sf.flat, sf.n)}.`
      : `The burst rule was read off this same record, so it is sure to look good here. The fair test counts only calls made from ${esc(day(sf.from))}; the first ones settle 90 days later.`) : "";
    return `<section class="block" aria-labelledby="hyb-h"><header class="bh"><div><h2 id="hyb-h">Big moves fade</h2>
      <p>What the next 90 days did after attention had moved by so much over the last 90. The p-value asks whether the move reversed more often than attention moves that way at all, counted on a third of the calls because the windows overlap.</p></div></header>
      <ul class="hy-bursts">${rows}</ul>
      <p class="hy-legend"><span><i class="u"></i>rose 10%+</span><span><i class="f"></i>within 10%</span><span><i class="d"></i>fell 10%+</span></p>
      <p class="hy-verdict">${fair}</p></section>`;
  }

  function page() {
    const items = H.items;
    const first = items.reduce((m, it) => (it.since < m ? it.since : m), items[0].since);
    const count = ORDER.map((p) => [p, items.filter((it) => it.phase === p).length]).filter(([, n]) => n);
    return `<section class="hero-t hy-hero"><div class="orb" aria-hidden="true"></div>
      <p class="eyebrow">Wikipedia views since ${esc(month(first))} · ${items.length} technologies · ${esc(H.made_on)}</p>
      <h1 id="hype-h">The hype cycle: <span class="grad">peak, trough, plateau.</span></h1>
      <p class="lede">Gartner's hype cycle says attention to a new technology races to a peak, slides into a trough and climbs back to a plateau while real use keeps growing. Here is where each technology's public attention stands today, and whether that has ever said anything about the next three months.</p>
      <p class="hy-count">${count.map(([p, n]) => `<span style="--c:${PHASE_C[p]}"><i></i>${esc(H.rules.phases[p].label)} <b>${n}</b></span>`).join("")}</p></section>
      <section class="block hy-curve-wrap" aria-labelledby="hyc-h"><header class="bh"><div><h2 id="hyc-h">Where each one stands</h2>
        <p>Placed by phase on the textbook curve; the cards below show each one's real views.</p></div></header>${curve(items)}</section>
      <section class="block" aria-labelledby="hyt-h"><header class="bh"><div><h2 id="hyt-h">Each technology</h2>
        <p>The line is the 90-day mean of daily views. Red dot: the highest it has been. Ringed dot: today.</p></div></header>
        <div class="hy-cards">${ORDER.flatMap((p) => items.filter((it) => it.phase === p)).map(card).join("")}</div></section>
      ${record()}
      <p class="note">How a phase is read: <b>level</b> is the last 90 days' mean views against the highest 90-day mean so far; <b>trend</b> is the last 90 days against the 90 before. Climbing to a peak: within ${Math.round(H.rules.at_peak * 100)}% of the peak and up more than ${Math.round(H.rules.flat * 100)}%. At or near the peak: within ${Math.round(H.rules.near_peak * 100)}%. Then sliding (down), climbing back (up), in the trough (below ${Math.round(H.rules.deep * 100)}% and flat) or on a plateau. Views to all of Wikipedia have drifted down for years, so "below the peak" partly measures that. Monthly windows overlap, so the counts above are not independent. After Fenn and Raskino (2008); data from the Wikimedia pageviews API and Our World in Data.</p>`;
  }

  function render(root, data) {
    D = data; H = data.hype;
    if (!H || !H.items || !H.items.length) {
      root.innerHTML = `<section class="hero-t"><h1 id="hype-h">The hype cycle</h1></section><div class="empty"><b>No technology attention data yet.</b>Run <code>psychohistory fetch --domain tech</code> and <code>psychohistory export</code>.</div>`;
      return;
    }
    root.innerHTML = page();
  }

  window.WPHype = { render, curveY, placed };
})();
