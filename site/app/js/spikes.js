// Spike watch: news, politics and technology attention that jumped to twice its usual level or
// more, where three plain rules and TimesFM say it will be four weeks on, and how every past spike
// actually landed. Reads D.spikes (built by psychohistory.spikes).
(function () {
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const day = (s) => { const d = new Date(String(s).slice(0, 10) + "T12:00:00Z"); return isNaN(d) ? s : d.toLocaleDateString(undefined, { day: "numeric", month: "short", timeZone: "UTC" }); };
  const month = (s) => { const d = new Date(String(s).slice(0, 10) + "T12:00:00Z"); return isNaN(d) ? s : d.toLocaleDateString(undefined, { month: "short", year: "numeric", timeZone: "UTC" }); };
  const x = (v) => (v === null || v === undefined || !isFinite(v) ? "–" : (v >= 10 ? Math.round(v) : v.toFixed(v >= 2 ? 1 : 2)) + "×");
  const miss = (m) => (m === null || m === undefined ? "–" : Math.round(Math.expm1(m) * 100) + "%");
  const pc = (a, b) => (b ? Math.round((100 * a) / b) + "%" : "–");
  const AREA = { news: "World news", politics: "Politics", tech: "Technology" };
  const HUE = { news: "var(--news)", politics: "var(--politics)", tech: "var(--tech)" };
  const RULE = { "old level": "Old level", "past spikes": "Past spikes", "no change": "No change", timesfm: "TimesFM" };
  const RULE_C = { "old level": "var(--ink-2)", "past spikes": "var(--warn)", "no change": "var(--down)", timesfm: "var(--tfm)" };
  let S;

  // One spike: the 28 days before it, the peak and since, on a log scale against the old level,
  // with each rule's call for four weeks after the newest day as a dot on the right.
  function chart(it, w = 340, h = 150) {
    const pts = (it.recent || []).map(([t, v]) => [Date.parse(t + "T12:00:00Z"), v / it.base]).filter(([, r]) => r > 0);
    if (pts.length < 3) return "";
    const t0 = pts[0][0], t1 = Date.parse(it.target + "T12:00:00Z");
    const calls = Object.entries(it.calls).filter(([, v]) => v !== null && v > 0);
    const all = pts.map(([, r]) => r).concat(calls.map(([, v]) => v), [1]);
    const lo = Math.log(Math.min(...all) * 0.85), hi = Math.log(Math.max(...all) * 1.15);
    const X = (t) => (8 + ((t - t0) / (t1 - t0)) * (w - 44)).toFixed(1), Y = (r) => (h - 18 - ((Math.log(r) - lo) / (hi - lo)) * (h - 30)).toFixed(1);
    const line = pts.map(([t, r], i) => `${i ? "L" : "M"}${X(t)} ${Y(r)}`).join("");
    const last = pts[pts.length - 1], peakT = Date.parse(it.peak_date + "T12:00:00Z");
    const dots = calls.map(([k, v], i) => `<circle cx="${(+X(t1) + (i - (calls.length - 1) / 2) * 7).toFixed(1)}" cy="${Y(v)}" r="4.5" style="fill:${RULE_C[k]}"><title>${esc(RULE[k])}: ${x(v)}</title></circle>`).join("");
    return `<svg class="sk-chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(it.title)}: ${x(it.ratio)} its usual level on ${esc(day(it.peak_date))}, ${x(it.now)} now">
      <line class="base" x1="8" x2="${w - 8}" y1="${Y(1)}" y2="${Y(1)}"/><text class="lab" x="10" y="${+Y(1) - 5}">old level</text>
      <line class="today" x1="${X(last[0])}" x2="${X(last[0])}" y1="10" y2="${h - 18}"/>
      <path d="${line}"/><circle class="pk" cx="${X(peakT)}" cy="${Y(it.ratio)}" r="4"/>
      <line class="ahead" x1="${X(last[0])}" x2="${X(t1)}" y1="${Y(last[1])}" y2="${Y(last[1])}"/>
      ${dots}
      <text class="lab" x="8" y="${h - 4}">${esc(day(it.recent[0][0]))}</text><text class="lab" x="${X(last[0])}" y="${h - 4}" text-anchor="middle">today</text><text class="lab" x="${w - 8}" y="${h - 4}" text-anchor="end">${esc(day(it.target))}</text></svg>`;
  }

  function card(it) {
    const c = it.calls, tf = it.timesfm_from;
    const facts = Object.keys(RULE).filter((k) => k in c).map((k) => `<li style="--r:${RULE_C[k]}"><span><i></i>${esc(RULE[k])}</span><b>${x(c[k])}</b></li>`).join("");
    return `<a class="hy-card sk-card" href="#series/${esc(it.id)}" style="--c:${HUE[it.domain]}">
      <div class="hy-top"><b>${esc(it.title)}</b><span class="hy-pill">${esc(AREA[it.domain] || it.domain)}</span></div>
      <p class="sk-big"><b>${x(it.ratio)}</b> its usual level on ${esc(day(it.peak_date))} · now <b>${x(it.now)}</b> · ${it.halved ? `halved back by ${esc(day(it.halved))}` : "not halved yet"}</p>
      ${chart(it)}
      <p class="sk-q">Four weeks on, ${esc(day(it.target))}, against the old level:</p>
      <ul class="hy-facts sk-calls">${facts}</ul>
      ${c.timesfm === null ? `<small class="sk-note">TimesFM's call comes with the next weekly forecast.</small>` : tf ? `<small class="sk-note">TimesFM from the forecast sealed ${esc(day(tf.made_on))}, for ${esc(day(tf.target_date))}.</small>` : ""}</a>`;
  }

  // The typical spike: the median ratio to the old level on each of the 60 days after a peak.
  function typical() {
    const cv = S.curve || [], pts = cv.map((v, i) => [i + 1, v]).filter(([, v]) => v !== null);
    if (pts.length < 5) return "";
    const w = 1200, h = 240, top = 16, bottom = 30, left = 52, right = 16;
    const hi = Math.max(...pts.map(([, v]) => v), 1.2) * 1.1, lo = Math.min(...pts.map(([, v]) => v), 0.9) * 0.95;
    const X = (d) => (left + ((d - 1) / 59) * (w - left - right)).toFixed(1), Y = (v) => (h - bottom - ((v - lo) / (hi - lo)) * (h - top - bottom)).toFixed(1);
    const path = pts.map(([d, v], i) => `${i ? "L" : "M"}${X(d)} ${Y(v)}`).join("");
    const ticks = [1, 7, 14, 21, 28, 42, 60].map((d) => `<text class="lab" x="${X(d)}" y="${h - 10}" text-anchor="middle">${d === 1 ? "day 1" : d}</text>`).join("");
    const H = S.rules.horizon + S.rules.lag, at = cv[H - 1];
    return `<section class="block" aria-labelledby="skt-h"><header class="bh"><div><h2 id="skt-h">The typical spike</h2>
      <p>The median ratio to the old level on each day after a peak, over every spike in the history.${at ? ` By day ${H}, the day the backtest checks, it is ${x(at)}.` : ""}</p></div></header>
      <div class="hy-scroll"><svg class="sk-typical" viewBox="0 0 ${w} ${h}" role="img" aria-label="The typical spike's ratio to its old level by day after the peak">
      <line class="base" x1="${left}" x2="${w - right}" y1="${Y(1)}" y2="${Y(1)}"/><text class="lab" x="${left - 6}" y="${+Y(1) + 4}" text-anchor="end">1×</text>
      <text class="lab" x="${left - 6}" y="${+Y(pts[0][1]) + 4}" text-anchor="end">${x(pts[0][1])}</text>
      ${at ? `<line class="today" x1="${X(H)}" x2="${X(H)}" y1="${top}" y2="${h - bottom}"/>` : ""}
      <path d="${path}"/>${ticks}</svg></div></section>`;
  }

  function record() {
    const R = S.record;
    if (!R) return `<section class="block"><header class="bh"><div><h2>How past spikes landed</h2></div></header>
      <div class="empty"><b>Not enough history yet.</b>The record needs a few months of daily attention with spikes in it; the next forecast run fills it from the full history.</div></section>`;
    const rules = R.rules || {}, fair = R.timesfm_fair || {};
    const order = ["old level", "past spikes", "no change"].filter((k) => rules[k]);
    const best = order.reduce((b, k) => (!b || rules[k].median_miss < rules[b].median_miss ? k : b), null);
    const tile = (k, s, note) => `<div${k === best ? ' class="best"' : ""}><b>${miss(s.median_miss)}</b><span>${esc(RULE[k])} missed by</span><small>${s.close} of ${s.n} within 25%${note ? "; " + esc(note) : ""}</small></div>`;
    const areas = Object.entries(R.by_domain || {}).map(([d, g]) => `<tr><th scope="row"><span class="hy-sw" style="--c:${HUE[d]}"></span>${esc(AREA[d] || d)}</th><td>${g.n}</td><td>${g.half === null ? "–" : g.half + " day" + (g.half === 1 ? "" : "s")}</td><td>${x(g.after)}</td><td>${pc(g.back, g.n)}</td></tr>`).join("");
    const tfm = fair.timesfm;
    return `<section class="block" aria-labelledby="skr-h"><header class="bh"><div><h2 id="skr-h">How past spikes landed</h2>
      <p>${R.n} spikes from ${esc(month(R.first))} to ${esc(month(R.last))}. Each was forecast the day after its peak, for four weeks on (day ${R.days_after}), using only spikes seen by then. A miss is the gap between forecast and outcome either way.</p></div></header>
      <div class="hy-score">
        <div><b>${R.half === null ? "–" : R.half}</b><span>median days to halve</span><small>${R.half_1} of ${R.n} halved the next day</small></div>
        <div><b>${pc(R.back, R.n)}</b><span>back within 25%</span><small>of the old level on day ${R.days_after}</small></div>
        ${order.map((k) => tile(k, rules[k])).join("")}
        ${tfm && tfm.n >= 3 ? `<div><b>${miss(tfm.median_miss)}</b><span>TimesFM missed by</span><small>on the ${tfm.n} spikes it forecast within a week of the peak; old level ${miss((fair["old level"] || {}).median_miss)} on those</small></div>` : ""}
      </div>
      <p class="hy-verdict">${esc(S.verdict)}</p>
      <div class="table-wrap"><table class="ev-table sk-table"><thead><tr><th>Area</th><th>Spikes</th><th>Median days to halve</th><th>Median on day ${R.days_after}</th><th>Back within 25%</th></tr></thead><tbody>${areas}</tbody></table></div></section>`;
  }

  // Do spikes move markets? Each market's median move over the next week after a spike, against usual.
  function markets() {
    const M = S.markets;
    if (!M || !M.rows || !M.rows.length) return "";
    const groups = [...new Set(M.rows.map((r) => r.group))], names = [...new Set(M.rows.map((r) => r.name))];
    const cell = (g, n) => {
      const r = M.rows.find((q) => q.group === g && q.name === n);
      if (!r) return "<td>–</td>";
      const t = Math.max(-1, Math.min(1, Math.log(r.ratio) / Math.log(2)));
      const pv = (v) => (v < 0.001 ? "< 0.001" : v.toFixed(2));
      const era = r.p_era != null ? `<small class="sk-era">same quarters ${r.ratio_era.toFixed(2)}× · p ${pv(r.p_era)}</small>` : "";
      return `<td class="sk-heat${r.passes ? " pass" : ""}" style="--t:${t.toFixed(3)}" title="${r.n} spikes; median move ${(r.size * 100).toFixed(1)}% against ${(r.usual * 100).toFixed(1)}% usually; shuffle p ${r.p.toFixed(3)}${r.p_era != null ? `; against days from the same quarters ${r.ratio_era.toFixed(2)}×, p ${r.p_era.toFixed(3)}` : ""}">
        <b>${r.ratio.toFixed(2)}×</b><small>${(r.size * 100).toFixed(1)}% vs ${(r.usual * 100).toFixed(1)}% · p ${pv(r.p)}${r.passes ? " ✓" : ""}</small>${era}</td>`;
    };
    const label = (g) => M.rows.find((r) => r.group === g).group_label;
    const strict = M.rows.some((r) => r.p_era != null);  // results from before the same-quarter test have only the plain one
    return `<section class="block" aria-labelledby="skm-h"><header class="bh"><div><h2 id="skm-h">Do spikes move markets?</h2>
      <p>The median size of each market's move over the ${M.after} trading days after a spike (from the close before it), against its median over every week. Above 1× means bigger moves than usual. The p-value is how often ${M.shuffles.toLocaleString()} random sets of as many days did as well. ${strict ? `Markets have calm and wild years, so the second line draws each random day from the same quarter as its spike instead; a ✓ means that stricter test passed the Benjamini-Hochberg cut for testing all ${M.tests} pairs at once.` : `A ✓ means it passed the Benjamini-Hochberg cut for testing all ${M.tests} pairs at once. These results come from before the stricter same-quarter test; the next weekly run adds it.`}</p></div></header>
      <div class="table-wrap"><table class="ev-table sk-mk"><thead><tr><th>Market</th>${groups.map((g) => `<th>After ${esc(label(g).toLowerCase())} spikes<small>${M.rows.find((r) => r.group === g).n} days</small></th>`).join("")}</tr></thead>
      <tbody>${names.map((n) => `<tr><th scope="row">${esc(n)}</th>${groups.map((g) => cell(g, n)).join("")}</tr>`).join("")}</tbody></table></div>
      <p class="hy-verdict">${esc(S.markets_verdict)}</p></section>`;
  }

  function sealed() {
    const L = S.live || { n: 0, open: 0 };
    const rules = L.rules || {};
    const rows = (L.calls || []).map((c) => `<tr><td>${esc(c.series_id)}</td><td>${esc(day(c.peak_date))}</td><td>${esc(day(c.target_date))}</td>
      ${["old level", "past spikes", "no change", "timesfm"].map((k) => `<td>${x(c[k])}</td>`).join("")}<td><b>${x(c.actual)}</b></td></tr>`).join("");
    return `<section class="block" aria-labelledby="sks-h"><header class="bh"><div><h2 id="sks-h">Sealed calls</h2>
      <p>On the first weekly forecast after a peak, every rule's call and TimesFM's are written to <code>predictions/spike_ledger.csv</code>, once per spike, and checked when their day comes.</p></div></header>
      ${L.n ? `<p class="hy-verdict">${L.n} settled, ${L.open} still open. Median miss: ${Object.entries(rules).map(([k, s]) => `${esc(RULE[k])} ${miss(s.median_miss)}`).join(" · ")}.</p>
        <div class="table-wrap"><table class="ev-table"><thead><tr><th>Series</th><th>Peak</th><th>Day</th><th>Old level</th><th>Past spikes</th><th>No change</th><th>TimesFM</th><th>What happened</th></tr></thead><tbody>${rows}</tbody></table></div>`
        : `<div class="empty"><b>${L.open ? `${L.open} call${L.open === 1 ? "" : "s"} sealed, none settled yet.` : "No call sealed yet."}</b>Each settles four weeks after the forecast that sealed it.</div>`}</section>`;
  }

  function page() {
    const items = S.items || [], R = S.record;
    return `<section class="hero-t sk-hero"><div class="orb" aria-hidden="true"></div>
      <p class="eyebrow">${items.length} live spike${items.length === 1 ? "" : "s"}${R ? ` · ${R.n} in the history` : ""}${S.made_on ? ` · ${esc(S.made_on)}` : ""}</p>
      <h1 id="spikes-h">Spike watch: <span class="grad">where a burst lands.</span></h1>
      <p class="lede">When a news topic or a technology's Wikipedia page gets at least ${S.rules.spike}× its usual attention in a day, the peak is easy to see. The hard question comes a few days later: four weeks from now, how far above its old level will it be? Three plain rules and TimesFM answer it, and every past spike shows who was right.</p></section>
      <section class="block" aria-labelledby="skl-h"><header class="bh"><div><h2 id="skl-h">Live spikes</h2>
        <p>Peaks in the last three weeks. The dashed line is the old level (the median of the ${S.rules.base_days} days before); the dots on the right are each forecast for four weeks after the newest day.</p></div></header>
        ${items.length ? `<p class="sk-legend">${Object.keys(RULE).map((k) => `<span><i style="background:${RULE_C[k]}"></i>${esc(RULE[k])}</span>`).join("")}</p><div class="hy-cards">${items.map(card).join("")}</div>`
          : `<div class="empty"><b>No spike in the last three weeks.</b>A day at ${S.rules.spike}× the usual level or more starts one.</div>`}</section>
      ${typical()}${record()}${markets()}${sealed()}
      <p class="note">How a spike is found: a day at least ${S.rules.spike}× the median of the ${S.rules.base_days} days before it starts one; its peak is the highest day in the week from there, and a series has at most one spike in ${S.rules.gap} days. <b>Old level</b> says attention goes back to that median; <b>past spikes</b> says it sits where earlier spikes sat at the same distance from their peak (pooled over all series, needing ${S.rules.min_past} of them); <b>no change</b> says it stays where it is. Composite indexes are left out, as they average the series already shown. After Lorenz-Spreen et al. (2019) on how collective attention fades.</p>`;
  }

  function render(root, data) {
    S = data.spikes;
    if (!S || (!(S.items || []).length && !S.record)) {
      root.innerHTML = `<section class="hero-t"><h1 id="spikes-h">Spike watch</h1></section><div class="empty"><b>No attention data yet.</b>Run <code>psychohistory fetch</code> and <code>psychohistory export</code>.</div>`;
      return;
    }
    root.innerHTML = page();
  }

  // Today's strip: the biggest live spikes, and where TimesFM and the past say each lands.
  function teaser(data) {
    const T = data.spikes, items = ((T && T.items) || []).filter((it) => !it.halved || it.days <= 7).slice(0, 3);
    if (!items.length) return "";
    const row = (it) => {
      const c = it.calls, tf = c.timesfm, past = c["past spikes"];
      return `<li><a href="#spikes" style="--c:${HUE[it.domain]}"><span class="sk-t-x">${x(it.ratio)}</span>
        <span class="sk-t-b"><b>${esc(it.title)}</b><small>${esc(AREA[it.domain] || it.domain)} · peak ${esc(day(it.peak_date))} · now ${x(it.now)}</small></span>
        <span class="sk-t-c"><small>in 4 weeks</small>${tf !== null ? `TimesFM <b>${x(tf)}</b>` : past !== null ? `past spikes <b>${x(past)}</b>` : `old level <b>1×</b>`}</span></a></li>`;
    };
    return `<section class="block sk-teaser" aria-labelledby="skt2-h"><header class="bh"><div><h2 id="skt2-h">Spiking now</h2>
      <p>Attention at ${T.rules.spike}× its usual level or more in the last few weeks, against its old level.</p></div><a class="icon-b" href="#spikes">Spike watch</a></header>
      <ol class="sk-t">${items.map(row).join("")}</ol></section>`;
  }

  window.WPSpikes = { render, teaser, x, miss };
})();
