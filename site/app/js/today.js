// Today: the home screen. Rise alerts in three tiers, every time frame for one series (a day to ten
// years), the history of its past forecasts against what happened, and which forecaster to trust.
// Reads D.frames (built by psychohistory.frames), D.brief (psychohistory.brief), D.track / D.track_radiant and D.leaderboard.
(function () {
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const DAY = 864e5;
  const NAMES = { radiant: "Radiant", "chronos-bolt": "Chronos-Bolt", seldon: "Seldon", "seldon-laws": "Seldon laws", "long-view": "Long view",
    "radiant-core": "Radiant core", "auto-ets": "AutoETS", ensemble: "Ensemble", naive: "No change", drift: "Drift", mean: "Seasonal mean" };
  const AREAS = { markets: "Markets", news: "World news", politics: "Politics", tech: "Technology", weather: "Weather", yearly: "Yearly" };
  const TIER_COPY = {
    world: ["Tell the world", "95% or more chance of going higher"],
    major: ["Big priority", "85% to 95% chance of going higher"],
    watch: ["Priority", "75% to 85% chance of going higher"],
  };
  const state = { frame: "all", id: null, open: {} };
  const WATCH = "wp-watch-v1", TOUR = "wp-tour-v1";  // the watchlist is shared with the World terminal
  const read = (k, blank) => { try { return JSON.parse(localStorage.getItem(k)) ?? blank; } catch (e) { return blank; } };
  const write = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* private mode: nothing kept */ } };
  const FRAMES = [["day", "Next day"], ["week", "Next week"], ["month", "Next month"], ["year", "Next year"], ["y5", "Next 5 years"], ["y10", "Next 10 years"]];
  const TIERS = [[0.95, "world", "Tell the world"], [0.85, "major", "Big priority"], [0.75, "watch", "Priority"]];
  let D, model, modelName;

  const nameOf = (m) => (m === model ? modelName : NAMES[m] || m);
  const colorOf = (m) => (m === model || /^timesfm/.test(m) ? "var(--tfm)" : m === "radiant" ? "var(--radiant)" : m === "chronos-bolt" ? "var(--rival)"
    : m === "seldon" ? "var(--seldon)" : m === "long-view" ? "var(--you)" : "var(--ink-2)");
  const pct = (v) => (v === null || v === undefined ? "–" : Math.round(v * 100) + "%");
  const pm = (v) => (v === null || v === undefined ? "–" : (v * 100).toFixed(1) + "%");
  const sp = (v) => (v === null || v === undefined || !isFinite(v) ? "–" : (v >= 0 ? "+" : "−") + Math.abs(v * 100).toFixed(Math.abs(v) < 0.1 ? 1 : 0) + "%");
  const frameName = (f) => (D.frames.frames.find((x) => x[0] === f) || [f, f])[1];

  // A ring that fills to the chance of going higher; its colour follows the tier.
  function ring(p, size = 76, label = true) {
    const r = size / 2 - 6, c = 2 * Math.PI * r, t = tierOf(p);
    const col = t ? `var(--t-${t})` : p >= 0.5 ? "var(--up)" : "var(--down)";
    const shown = p >= 0.5 ? p : 1 - p;
    return `<svg class="ring" viewBox="0 0 ${size} ${size}" width="${size}" height="${size}" aria-hidden="true">
      <circle cx="${size / 2}" cy="${size / 2}" r="${r}" class="ring-bg"/>
      <circle cx="${size / 2}" cy="${size / 2}" r="${r}" class="ring-fg" style="stroke:${col};--c:${c.toFixed(1)};--o:${(c * (1 - shown)).toFixed(1)}"
        stroke-dasharray="${c.toFixed(1)}" stroke-dashoffset="${(c * (1 - shown)).toFixed(1)}" transform="rotate(-90 ${size / 2} ${size / 2})"/>
      ${label ? `<text x="50%" y="50%" dy=".35em" text-anchor="middle" class="ring-t">${Math.round(shown * 100)}<tspan>%</tspan></text>` : ""}</svg>`;
  }
  function tierOf(p) { for (const [floor, key] of TIERS) if (p >= floor) return key; return null; }

  // ---------- before a run has built D.frames: read this week's sealed forecasts in the browser ----------
  // Same reading as psychohistory.frames.p_up3: straight lines through the 10th, 50th and 90th
  // percentiles, tails capped at 5% and 95%.
  function pUp3(q10, q50, q90, last) {
    const [lo, mid, hi] = [q10, q50, q90].sort((a, b) => a - b);
    const cdf = last <= lo ? 0.05 : last >= hi ? 0.95 : last <= mid ? 0.1 + 0.4 * (last - lo) / (mid - lo || 1) : 0.5 + 0.4 * (last - mid) / (hi - mid || 1);
    return 1 - cdf;
  }
  function fromOutlook(data) {
    const items = (data.outlook || []).filter((o) => o.fan && o.fan.length && o.history && o.history.length).map((o) => {
      const last = o.history[o.history.length - 1][1];
      const yearly = o.fan.length > 1 && Date.parse(o.fan[1][0]) - Date.parse(o.fan[0][0]) > 300 * DAY;
      const business = o.domain === "markets" && o.id !== "bitcoin";
      const steps = yearly ? { year: 1 } : business ? { day: 1, week: 5, month: 21 } : { day: 1, week: 7, month: 28 };
      const cells = {};
      for (const [f, k] of Object.entries(steps)) {
        for (const [m, fan] of [[data.meta.model, o.fan], ["radiant", o.radiant]]) {
          const row = fan && fan[k - 1];
          if (!row || !last) continue;
          (cells[f] = cells[f] || {})[m] = { p: +pUp3(row[1], row[2], row[3], last).toFixed(4), mid: row[2] / last - 1, low: row[1] / last - 1, high: row[3] / last - 1, date: row[0], sure: false };
        }
      }
      return { id: o.id, domain: o.domain, area: yearly ? "yearly" : o.domain, title: o.title, freq: yearly ? "YS" : business ? "B" : "D", frames: cells };
    });
    const alerts = [];
    for (const it of items) for (const [f, cells] of Object.entries(it.frames)) {
      const m = ["radiant", data.meta.model].find((x) => cells[x]); if (!m) continue;
      const c = cells[m], t = TIERS.find(([floor]) => c.p >= floor);
      if (t) alerts.push({ id: it.id, title: it.title, domain: it.domain, frame: f, model: m, tier: t[1], p: c.p, mid: c.mid, low: c.low, high: c.high, sure: false,
        others: Object.fromEntries(Object.entries(cells).filter(([x]) => x !== m).map(([x, v]) => [x, v.p])) });
    }
    const order = { world: 0, major: 1, watch: 2 };
    alerts.sort((a, b) => order[a.tier] - order[b.tier] || b.p - a.p);
    return { frames: FRAMES, tiers: TIERS, target: 0.7, items, alerts, record: { backtest: {}, live: {} }, rules: [], fallback: true };
  }

  // ---------- first visit: three tips, once ----------
  function tour() {
    if (read(TOUR, false)) return "";
    return `<aside class="tour" aria-label="How to read Today"><ol>
      <li><b>Rings are chances.</b> The fuller the ring, the likelier the series ends higher than it is now. Yellow, orange and pink mark 75%, 85% and 95%.</li>
      <li><b>Every call has a record.</b> Each tier says how often calls like it really rose. Trust the record, not the ring.</li>
      <li><b>Tap anything.</b> An alert opens its series below; the star keeps it at the top; <kbd>?</kbd> lists every shortcut.</li></ol>
      <button class="btn" data-tour>Got it</button></aside>`;
  }

  // ---------- your watchlist ----------
  function watchlist(F) {
    const ids = read(WATCH, []).filter((id) => F.items.some((x) => x.id === id));
    if (!ids.length) return "";
    const chip = (id) => {
      const it = F.items.find((x) => x.id === id);
      const f = ["month", "week", "day", "year"].find((k) => it.frames[k]);
      const cells = f ? it.frames[f] : null, m = cells && ["radiant", model, "long-view"].find((k) => cells[k]);
      const c = m ? cells[m] : null;
      return `<button class="wchip ${c && tierOf(c.p) ? "t-" + tierOf(c.p) : ""}" data-pick="${esc(id)}">${c ? ring(c.p, 44) : ""}
        <span><b>${esc(it.title)}</b><small>${c ? `${esc(frameName(f))} · ${sp(c.mid)}` : "nothing sealed"}</small></span></button>`;
    };
    return `<section class="block wl" aria-labelledby="wl-h"><header class="bh"><div><h2 id="wl-h">Your watchlist</h2></div></header>
      <div class="wchips">${ids.map(chip).join("")}</div></section>`;
  }

  // ---------- CSV of every series at every frame ----------
  function csv(F) {
    const rows = [["series_id", "title", "area", "frame", "model", "chance_higher", "middle_change", "low_change", "high_change", "tier"]];
    for (const it of F.items) for (const [f] of F.frames) for (const [m, c] of Object.entries(it.frames[f] || {}))
      rows.push([it.id, it.title, it.area, f, m, c.p, c.mid, c.low, c.high, tierOf(c.p) || ""]);
    const text = rows.map((r) => r.map((v) => (v === null || v === undefined ? "" : /[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : v)).join(",")).join("\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([text], { type: "text/csv" }));
    a.download = `world-predictor-time-frames-${(D.outlook[0] || {}).made_on || D.meta.generated}.csv`;
    document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 0);
  }

  // ---------- hero ----------
  function hero(F) {
    const n = (k) => F.alerts.filter((a) => a.tier === k).length;
    const lb = D.leaderboard, bench = lb && lb.rows.find((r) => r.model === model), rad = lb && lb.rows.find((r) => r.model === "radiant");
    const edge = bench && rad ? `Radiant missed by ${(rad.smape * 100).toFixed(2)}% on average in the newest backtest, ${modelName} by ${(bench.smape * 100).toFixed(2)}%.` : "";
    return `<section class="hero-t">
      <div class="orb" aria-hidden="true"></div>
      <p class="eyebrow">${esc(D.meta.demo ? "Demo data" : "Sealed " + (D.outlook[0] ? D.outlook[0].made_on : D.meta.generated))} · ${F.items.length} series · six time frames</p>
      <h1 id="today-h">What happens next, <span class="grad">and how sure we are.</span></h1>
      <p class="lede">${esc(modelName)}, Radiant and their rivals forecast the world every week. Here is everything they give a 75% or better chance of going higher, from tomorrow to ten years out, and how often calls like these came true. ${esc(edge)}</p>
      <div class="counters" role="list">
        ${["world", "major", "watch"].map((k) => `<a role="listitem" class="counter t-${k}" href="#today" data-jump="${k}"><b data-n="${n(k)}">${n(k)}</b><span>${TIER_COPY[k][0]}</span><small>${TIER_COPY[k][1]}</small></a>`).join("")}
      </div>${F.fallback ? `<p class="fallback">Read in your browser from this week's sealed forecasts. Each tier's record, the 70% club and the year-to-decade frames arrive with the next forecast run.</p>` : ""}</section>`;
  }

  // ---------- alerts ----------
  function record(key) {
    const R = D.frames.record, get = (src, models) => {
      let n = 0, up = 0;
      for (const m of models) { const x = ((R[src][m] || {}).all || {})[key]; if (x) { n += x[0]; up += x[1]; } }
      return [n, up];
    };
    const part = ([n, u], what) => (n ? `<b>${u} of ${n}</b> ${what} (${pct(u / n)})` : "");
    return [part(get("backtest", ["radiant", model]), "past model calls rose"), part(get("backtest", ["long-view"]), "past long-view calls rose"),
      part(get("live", ["radiant", model]), "sealed calls rose")].filter(Boolean).join(" · ") || "No calls in this tier yet.";
  }
  function alertCard(a) {
    const others = Object.entries(a.others || {}).map(([m, p]) => `<span style="--c:${colorOf(m)}">${esc(nameOf(m))} ${pct(p)}</span>`).join("");
    return `<button class="alert t-${a.tier}" data-id="${esc(a.id)}" data-frame="${esc(a.frame)}">
      ${ring(a.p, 64)}
      <span class="al-body"><span class="al-frame">${esc(frameName(a.frame))}</span>
        <b>${esc(a.title)}</b>
        <span class="al-range">middle ${sp(a.mid)} · range ${sp(a.low)} to ${sp(a.high)}</span>
        <span class="al-who"><span style="--c:${colorOf(a.model)}">${esc(nameOf(a.model))}</span>${others}${a.sure ? '<span class="sure" title="This model and area cleared 70% right on earlier windows at this lean">70% club</span>' : ""}</span></span>
    </button>`;
  }
  function alerts(F) {
    const list = F.alerts.filter((a) => state.frame === "all" || a.frame === state.frame);
    const chips = [["all", "All"], ...F.frames.map(([k, n]) => [k, n.replace("Next ", "")])].map(([k, n]) =>
      `<button class="seg-b" aria-pressed="${state.frame === k}" data-frame="${k}">${esc(n[0].toUpperCase() + n.slice(1))}</button>`).join("");
    const lane = (k) => {
      const mine = list.filter((a) => a.tier === k), open = state.open[k], shown = open ? mine : mine.slice(0, 5);
      return `<div class="lane t-${k}" id="lane-${k}"><header><h3>${TIER_COPY[k][0]}</h3><span>${mine.length}</span></header>
        <p class="lane-rec">${record(k)}</p>
        ${shown.length ? shown.map(alertCard).join("") : '<p class="lane-empty">Nothing in this tier for this time frame.</p>'}
        ${mine.length > 5 ? `<button class="more-b" data-lane="${k}">${open ? "Show fewer" : `Show all ${mine.length}`}</button>` : ""}</div>`;
    };
    return `<section class="block" aria-labelledby="al-h"><header class="bh"><div><h2 id="al-h">Alerts</h2>
      <p>Every series and time frame with a 75% or better chance of going higher. Radiant speaks first where it has a forecast, then ${esc(modelName)}, then the long view.</p></div>
      <div class="seg" role="group" aria-label="Time frame">${chips}</div></header>
      <div class="lanes">${lane("world")}${lane("major")}${lane("watch")}</div></section>`;
  }

  // ---------- the brief: what came due, changes of mind, streaks (D.brief, built by psychohistory.brief) ----------
  // A strip for one call that came due: the 80% range as a band, the middle as a tick, what happened as a dot.
  const day = (s) => { const d = new Date(s + "T12:00:00Z"); return isNaN(d) ? s : d.toLocaleDateString(undefined, { day: "numeric", month: "short", timeZone: "UTC" }); };
  function strip(c) {
    const lo = Math.min(c.low, c.actual, 0), hi = Math.max(c.high, c.actual, 0), pad = (hi - lo) * 0.08 || 0.01;
    const x = (v) => (((v - lo + pad) / (hi - lo + 2 * pad)) * 100).toFixed(1) + "%";
    return `<span class="strip" aria-hidden="true"><i class="zero" style="left:${x(0)}"></i>
      <i class="band" style="left:${x(c.low)};width:calc(${x(c.high)} - ${x(c.low)})"></i><i class="mid" style="left:${x(c.mid)}"></i>
      <i class="dot ${c.inside ? "in" : "out"}" style="left:${x(c.actual)}"></i></span>`;
  }
  function dueCall(c, kind, ids) {
    const tag = ids.has(c.id) ? `button data-pick="${esc(c.id)}"` : "div";
    const what = kind === "out" ? `${c.miss.toFixed(1)} range widths outside` : `said ${sp(c.mid)}, was ${sp(c.actual)}`;
    return `<${tag} class="bf-call ${kind}"><span class="bf-t"><b>${esc(c.title)}</b><small>${esc(day(c.target))} · ${what}</small></span>
      ${strip(c)}<span class="sr">range ${sp(c.low)} to ${sp(c.high)}, middle ${sp(c.mid)}, happened ${sp(c.actual)}</span></${tag.split(" ")[0]}>`;
  }
  // Before and after on one 0-100% track, the 50% line in the middle.
  function shiftRow(r, ids) {
    const tag = ids.has(r.id) ? `button data-pick="${esc(r.id)}"` : "div";
    const a = r.p_old * 100, b = r.p_new * 100, up = b >= a;
    return `<${tag} class="bf-rev${r.flip ? " flip" : ""}"><span class="bf-t"><b>${esc(r.title)}</b>
        <small>by ${esc(day(r.target))} · moved ${sp(r.moved)} since${r.flip ? ' · <em>flipped</em>' : ""}</small></span>
      <span class="track" aria-hidden="true"><i class="half"></i><i class="span ${up ? "up" : "down"}" style="left:${Math.min(a, b).toFixed(1)}%;width:${Math.abs(b - a).toFixed(1)}%"></i>
        <i class="was" style="left:${a.toFixed(1)}%"></i><i class="now ${b >= 50 ? "up" : "down"}" style="left:${b.toFixed(1)}%"></i></span>
      <span class="bf-n ${up ? "pos" : "neg"}">${pct(r.p_old)} → <b>${pct(r.p_new)}</b></span></${tag.split(" ")[0]}>`;
  }
  function streakRow(s, hot, ids) {
    const tag = ids.has(s.id) ? `button data-pick="${esc(s.id)}"` : "div";
    const pips = Array.from({ length: Math.min(s.run, 12) }, () => "<i></i>").join("");
    return `<${tag} class="bf-st ${hot ? "hot" : "cold"}"><span class="bf-t"><b>${esc(s.title)}</b><small>${s.right} of ${s.calls} right overall</small></span>
      <span class="pips" aria-label="${s.run} in a row">${pips}<em>${s.run}</em></span></${tag.split(" ")[0]}>`;
  }
  function brief(F) {
    const B = D.brief;
    if (!B) return "";
    const ids = new Set(F.items.map((x) => x.id)), due = B.due, rev = B.revisions, st = B.streaks;
    const cards = [];
    if (due) {
      const lead = due.models.find((r) => r[0] === due.lead) || due.models[0];
      const rows = due.models.slice(0, 5).map(([m, n, , inside, right, skill]) => `<tr><th style="--c:${colorOf(m)}"><span class="who">${esc(nameOf(m))}</span></th>
        <td>${n}</td><td>${pct(inside)}</td><td>${pct(right)}</td><td class="${skill > 0 ? "pos" : skill < 0 ? "neg" : ""}">${sp(skill)}</td></tr>`).join("");
      cards.push(`<article class="bf-card"><h3>Came due</h3>
        <p class="bf-sub">${esc(day(due.since))} to ${esc(day(due.until))}. ${lead ? `${esc(nameOf(lead[0]))}: ${lead[1]} forecasts on ${lead[2]} series, ${pct(lead[4])} with the right direction.` : ""}</p>
        <div class="table-wrap"><table class="bf-t-models"><thead><tr><th></th><th>Calls</th><th>In range</th><th>Direction</th><th>Skill</th></tr></thead><tbody>${rows}</tbody></table></div>
        <h4>Closest calls</h4>${due.nailed.map((c) => dueCall(c, "in", ids)).join("") || '<p class="dim">None this week.</p>'}
        <h4>Surprises</h4>${due.surprises.map((c) => dueCall(c, "out", ids)).join("") || '<p class="dim">Every outcome landed inside its range.</p>'}
        <p class="bf-key"><span class="k-band"></span>80% range <span class="k-mid"></span>middle <span class="k-dot"></span>what happened</p></article>`);
    }
    if (rev && rev.items.length) {
      cards.push(`<article class="bf-card"><h3>Changed its mind</h3>
        <p class="bf-sub">${esc(nameOf(rev.model))} on ${esc(day(rev.new))} against ${esc(day(rev.old))}: the chance of ending above today's level, same date, same question. ${rev.flips} of ${rev.series} series flipped side.</p>
        ${rev.items.map((r) => shiftRow(r, ids)).join("")}</article>`);
    }
    if (st && (st.hot.length || st.cold.length)) {
      cards.push(`<article class="bf-card"><h3>Streaks</h3>
        <p class="bf-sub">${esc(nameOf(st.model))}'s next-step calls, one per sealed batch, ${st.minimum} or more in a row. A short streak is weak evidence; the Monitor tests whether a record is luck.</p>
        <h4>Right in a row</h4>${st.hot.map((s) => streakRow(s, true, ids)).join("") || '<p class="dim">No series right three times running.</p>'}
        <h4>Wrong in a row</h4>${st.cold.map((s) => streakRow(s, false, ids)).join("") || '<p class="dim">No series wrong three times running.</p>'}</article>`);
    }
    if (!cards.length) return "";
    return `<section class="block" aria-labelledby="bf-h"><header class="bh"><div><h2 id="bf-h">Since the last run</h2>
      <p>What came due and how it went, where a forecaster changed its mind, and who is on a streak. Every line is a forecast sealed before its day.</p></div>
      <div class="tf-tools"><button class="icon-b" data-brief title="Copy the brief as Markdown, for a note or a post">Copy as text</button><span class="toast" role="status" aria-live="polite"></span></div></header>
      <div class="bf-grid">${cards.join("")}</div></section>`;
  }

  // ---------- time frames for one series ----------
  function frames(F) {
    const item = F.items.find((x) => x.id === state.id) || F.items[0];
    if (!item) return "";
    state.id = item.id;
    const opts = F.items.map((x) => `<option value="${esc(x.id)}" ${x.id === item.id ? "selected" : ""}>${esc(x.title)}</option>`).join("");
    const why = (f) => (["year", "y5", "y10"].includes(f) ? "Needs six full years of data for the long view." : item.freq === "YS" ? "A yearly series: one value a year."
      : item.domain === "weather" && f === "month" ? "Weather is forecast two weeks ahead, no further." : "Not sealed this week.");
    const tiles = F.frames.map(([f, name]) => {
      const cells = item.frames[f] || {};
      const lead = ["radiant", model, "long-view"].find((m) => cells[m]);
      if (!lead) return `<div class="tile empty-t"><span class="tl-f">${esc(name)}</span><span class="tl-none">–</span><small>${esc(why(f))}</small></div>`;
      const c = cells[lead], up = c.p >= 0.5;
      const rest = Object.entries(cells).filter(([m]) => m !== lead).map(([m, v]) => `<span style="--c:${colorOf(m)}">${esc(nameOf(m))} ${pct(v.p)}</span>`).join("");
      return `<div class="tile ${tierOf(c.p) ? "t-" + tierOf(c.p) : ""}"><span class="tl-f">${esc(name)}</span>${ring(c.p, 84)}
        <span class="tl-dir ${up ? "pos" : "neg"}">${up ? "▲ chance higher" : "▼ chance lower"}</span>
        <span class="tl-mid">${sp(c.mid)}</span><span class="tl-range">${sp(c.low)} to ${sp(c.high)}</span>
        <span class="al-who"><span style="--c:${colorOf(lead)}">${esc(nameOf(lead))}</span>${rest}${c.sure ? '<span class="sure">70% club</span>' : ""}</span></div>`;
    }).join("");
    return `<section class="block" aria-labelledby="tf-h"><header class="bh"><div><h2 id="tf-h">Every time frame</h2>
      <p>Day, week and month come from this week's sealed forecasts. Year, 5 and 10 years come from the long view: the series' own yearly drift and swings, with the doubt about that drift added in.</p></div>
      <div class="tf-tools"><label class="pick"><span class="sr">Series</span><select id="tf-pick">${opts}</select></label>
        <button class="icon-b" data-star aria-pressed="${read(WATCH, []).includes(item.id)}" title="Keep this series on your watchlist">${read(WATCH, []).includes(item.id) ? "★ Watching" : "☆ Watch"}</button>
        <button class="icon-b" data-share title="Copy a link to this series">Copy link</button>
        <button class="icon-b" data-csv title="Every series at every time frame, as a spreadsheet">CSV</button>
        <span class="toast" role="status" aria-live="polite"></span></div></header>
      <div class="tiles">${tiles}</div></section>`;
  }

  // ---------- history: past forecasts against what happened ----------
  function windows(T) {
    if (!T || !T.windows.length) return null;
    const t0 = Date.parse(T.start), dates = T.days.map((d) => new Date(t0 + d * DAY).toISOString().slice(0, 10));
    return { dates, actual: T.actual, list: T.windows.map(([origin, at, q10, q50, q90]) => ({ origin, at, q10, q50, q90, d: dates.slice(at, at + q50.length), a: T.actual.slice(at, at + q50.length), before: at > 0 ? T.actual[at - 1] : null })) };
  }
  function stats(W, bands) {
    let miss = 0, n = 0, inside = 0, right = 0, calls = 0;
    for (const w of W.list) {
      w.a.forEach((a, i) => { if (a === null || !a) return; miss += Math.abs(w.q50[i] - a) / Math.abs(a); n++; if (bands && a >= w.q10[i] && a <= w.q90[i]) inside++; });
      const end = w.a[w.a.length - 1], said = w.q50[w.q50.length - 1];
      if (w.before && end !== null && said !== w.before && end !== w.before) { calls++; if ((said > w.before) === (end > w.before)) right++; }
    }
    return { miss: n ? miss / n : null, inside: bands && n ? inside / n : null, right: calls ? right / calls : null, calls, n };
  }
  function history(F) {
    const W = windows((D.track || {})[state.id]), R = windows((D.track_radiant || {})[state.id]);
    const title = (F.items.find((x) => x.id === state.id) || {}).title || state.id;
    if (!W) return `<section class="block"><header class="bh"><div><h2>How right were they?</h2><p>${esc(title)} has no backtest yet; it appears after the next full run.</p></div></header></section>`;
    // The most certain quarter: windows whose 80% range was narrowest relative to the level.
    const width = W.list.map((w) => w.q50.reduce((s, m, i) => s + (w.q90[i] - w.q10[i]) / Math.max(1e-9, Math.abs(m)), 0) / w.q50.length);
    const cut = [...width].sort((a, b) => a - b)[Math.max(0, Math.floor(width.length / 4) - 1)];
    W.list.forEach((w, i) => (w.sure = width[i] <= cut));
    const s = stats(W, true), r = R ? stats(R, false) : null, sure = stats({ list: W.list.filter((w) => w.sure) }, true);
    const tile = (k, v, sub, c) => `<div class="kpi" style="--c:${c}"><span>${k}</span><b>${v}</b><small>${sub}</small></div>`;
    return `<section class="block" aria-labelledby="hi-h"><header class="bh"><div><h2 id="hi-h">How right were they? ${esc(title)}</h2>
      <p>Every past forecast laid over what really happened, on windows the models never saw. The bright bands are ${esc(modelName)}'s most certain quarter of calls: its narrowest ranges.</p></div></header>
      <div class="kpis">
        ${tile(`${esc(modelName)} average miss`, pm(s.miss), `${s.n} days checked`, "var(--tfm)")}
        ${tile("Reality inside its 80% range", pct(s.inside), "the target is 80%", "var(--tfm)")}
        ${tile("Direction right", pct(s.right), `${s.calls} windows`, "var(--tfm)")}
        ${tile("When it was most sure", pm(sure.miss), `average miss · ${pct(sure.inside)} in range`, "var(--t-world)")}
        ${r ? tile("Radiant average miss", pm(r.miss), `direction right ${pct(r.right)}`, "var(--radiant)") : ""}
      </div>
      <div id="hist-chart"></div><div id="hist-legend"></div></section>`;
  }
  function drawHistory() {
    const host = document.getElementById("hist-chart"); if (!host) return;
    const { plot, legend } = window.WPCharts;
    const W = windows((D.track || {})[state.id]), R = windows((D.track_radiant || {})[state.id]);
    if (!W) return;
    const width = W.list.map((w) => w.q50.reduce((s, m, i) => s + (w.q90[i] - w.q10[i]) / Math.max(1e-9, Math.abs(m)), 0) / w.q50.length);
    const cut = [...width].sort((a, b) => a - b)[Math.max(0, Math.floor(width.length / 4) - 1)];
    plot(host, {
      x: "date", height: 340, left: 60, label: "Past forecasts against what happened",
      bands: W.list.map((w, i) => ({ points: w.d.map((d, j) => [d, w.q10[j], w.q90[j]]), color: width[i] <= cut ? "var(--band-sure)" : "var(--band-faint)", hatch: false, fade: false })),
      lines: [{ points: W.dates.map((d, i) => [d, W.actual[i]]), color: "var(--ink)", width: 2, name: "What happened" },
        ...W.list.map((w) => ({ points: w.d.map((d, j) => [d, w.q50[j]]), color: "var(--tfm)", width: 1.8, draw: false, name: modelName })),
        ...(R ? R.list.map((w) => ({ points: w.d.map((d, j) => [d, w.q50[j]]), color: "var(--radiant)", width: 1.4, dash: "4 3", draw: false, name: "Radiant" })) : [])],
    });
    legend(document.getElementById("hist-legend"), [{ name: "What really happened", color: "var(--ink)" }, { name: `${modelName}'s most likely path`, color: "var(--tfm)" },
      { name: `${modelName}'s 80% range`, color: "var(--tfm)", kind: "band" }, { name: "Its most certain quarter", color: "var(--t-world)", kind: "band" },
      ...(R ? [{ name: "Radiant's most likely path", color: "var(--radiant)", kind: "dash" }] : [])]);
  }

  // ---------- who to trust ----------
  function trust(F) {
    const lb = D.leaderboard, rows = lb ? lb.rows.slice(0, 7) : [];
    const worst = rows.length ? Math.max(...rows.map((r) => r.smape)) : 1;
    const board = rows.map((r, i) => `<li style="--c:${colorOf(r.model)};--w:${(r.smape / worst).toFixed(3)}"><span class="rk">${i + 1}</span><span class="nm">${esc(nameOf(r.model))}</span>
      <span class="bar"><i></i></span><b>${(r.smape * 100).toFixed(2)}%</b><small>${r.model === model ? "the benchmark" : `closer than ${esc(modelName)} on ${r.beats} of ${r.of}`}</small></li>`).join("");
    const rules = F.rules.filter((r) => r.model !== "long-view");
    const areas = [...new Set(rules.map((r) => r.area))], who = [model, "radiant", "chronos-bolt", "seldon"].filter((m) => rules.some((r) => r.model === m));
    const cell = (m, a) => {
      const r = rules.find((x) => x.model === m && x.area === a);
      if (!r || r.late_rate === null) return "<td class=\"dim\">–</td>";
      const ok = r.reached && r.late_rate >= F.target;
      return `<td class="${ok ? "ok" : r.reached ? "" : "no"}" title="lean ${Math.round(r.lean * 100)} points from 50%; ${r.late_calls} of ${r.late_windows} later windows called"><b>${pct(r.late_rate)}</b><small>${pct(r.late_calls / Math.max(1, r.late_windows))} called</small></td>`;
    };
    const lv = F.rules.find((r) => r.model === "long-view");
    return `<section class="block" aria-labelledby="tr-h"><header class="bh"><div><h2 id="tr-h">Who to trust</h2>
      <p>${esc(modelName)} beside every other forecaster on the same windows. Average miss is the sMAPE of the newest full backtest; lower is better.</p></div></header>
      <div class="trust">
        <ol class="board-l">${board || '<li class="dim">The leaderboard fills in after the first full backtest.</li>'}</ol>
        <div class="club"><h3>The 70% club</h3>
          <p>Each model learned, on the earlier half of the backtest, how sure it has to be before its up-or-down calls are right 70% of the time. Below that it stays quiet. These are its scores on the later half, which it never saw.</p>
          ${who.length ? `<div class="table-wrap"><table class="club-t"><thead><tr><th></th>${areas.map((a) => `<th>${esc(AREAS[a] || a)}</th>`).join("")}</tr></thead>
            <tbody>${who.map((m) => `<tr><th style="--c:${colorOf(m)}"><span class="who">${esc(nameOf(m))}</span></th>${areas.map((a) => cell(m, a)).join("")}</tr>`).join("")}</tbody></table></div>
            <p class="note">Green: at or above 70% on the later windows. Red: no level of sureness reached 70% even on the earlier windows; markets' day-to-month direction stays close to a coin toss for every model.${lv ? ` The long view's yearly calls: ${pct(lv.late_rate)} right on ${lv.late_calls} later calls.` : ""}</p>`
          : '<p class="dim">Appears after the first full backtest.</p>'}
        </div></div></section>`;
  }

  // The screen, top to bottom. Every change redraws it in place and keeps the scroll position.
  const page = (F) => tour() + hero(F) + watchlist(F) + (window.WPEvents ? window.WPEvents.teaser(D) : "") + (window.WPCalendar ? window.WPCalendar.teaser(D) : "") + alerts(F) + brief(F) + frames(F) + history(F) + trust(F);
  const link = () => `#today/${state.id}${state.frame !== "all" ? ":" + state.frame : ""}`;

  function render(host, data, arg) {
    D = data; model = D.meta.model; modelName = /^timesfm/.test(model) ? "TimesFM" : model;
    const F = D.frames && D.frames.items && D.frames.items.length ? D.frames : fromOutlook(D);
    if (!F.items.length) { host.innerHTML = '<div class="empty"><b>No forecasts yet.</b>Today fills in after the first weekly run.</div>'; return; }
    D.frames = D.frames && D.frames.items && D.frames.items.length ? D.frames : F;  // frameName reads it
    // A shared link: #today/<series>[:<frame>]
    if (arg) {
      const [id, frame] = decodeURIComponent(arg).split(":");
      if (F.items.some((x) => x.id === id)) state.id = id;
      if (frame && F.frames.some(([k]) => k === frame)) state.frame = frame;
    }
    if (!state.id || !F.items.some((x) => x.id === state.id)) state.id = F.items.some((x) => x.id === "sp500") ? "sp500" : F.items[0].id;
    host.innerHTML = page(F);
    drawHistory();
    host.querySelectorAll(".counter b").forEach(count);
    if (arg) requestAnimationFrame(() => { const h = document.getElementById("tf-h"); if (h) h.scrollIntoView({ block: "start" }); });
    host.onclick = (e) => {
      const t = (sel) => e.target.closest(sel);
      const seg = t(".seg-b"), more = t(".more-b"), al = t(".alert"), jump = t("[data-jump]"), pick = t("[data-pick]");
      if (seg) { state.frame = seg.dataset.frame; repaint(host, F); }
      else if (more) { state.open[more.dataset.lane] = !state.open[more.dataset.lane]; repaint(host, F); }
      else if (al || pick) { state.id = (al || pick).dataset[al ? "id" : "pick"]; repaint(host, F); document.getElementById("tf-h").scrollIntoView({ behavior: "smooth", block: "start" }); }
      else if (jump) { e.preventDefault(); const lane = document.getElementById("lane-" + jump.dataset.jump); if (lane) lane.scrollIntoView({ behavior: "smooth", block: "start" }); }
      else if (t("[data-tour]")) { write(TOUR, true); repaint(host, F); }
      else if (t("[data-star]")) {
        const ids = read(WATCH, []), on = ids.includes(state.id);
        write(WATCH, on ? ids.filter((x) => x !== state.id) : [...ids, state.id]); repaint(host, F);
        say(host, on ? "Removed from your watchlist." : "Added to your watchlist, here and in the World terminal.");
      }
      else if (t("[data-share]")) {
        const url = location.href.split("#")[0] + link();
        const done = () => say(host, "Link copied.");
        if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(url).then(done, () => say(host, url));
        else say(host, url);
      }
      else if (t("[data-csv]")) { csv(F); say(host, "CSV downloaded."); }
      else if (t("[data-brief]")) {
        const text = (D.brief || {}).text || "", el = t("[data-brief]").parentNode;
        const done = () => say(host, "The brief is on your clipboard.", el);
        if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(done, () => say(host, "Copy is blocked here; results/BRIEF.md has the same text.", el));
        else say(host, "Copy is blocked here; results/BRIEF.md has the same text.", el);
      }
    };
    host.onchange = (e) => { if (e.target.id === "tf-pick") { state.id = e.target.value; repaint(host, F); } };
  }
  function say(host, text, near) {
    const tf = host.querySelector("#tf-h"), el = (near || (tf && tf.closest(".block")) || host).querySelector(".toast"); if (!el) return;
    el.textContent = text; el.classList.add("on"); clearTimeout(say.t); say.t = setTimeout(() => el.classList.remove("on"), 2600);
  }
  function repaint(host, F) {
    const y = scrollY;
    host.innerHTML = page(F);
    drawHistory(); scrollTo(0, y);
    window.history.replaceState(null, "", link());  // the address always names what is on screen
  }
  // Counters count up once, unless motion is reduced.
  function count(b) {
    const n = +b.dataset.n; if (!n || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const t0 = performance.now(), dur = 900;
    const step = (t) => { const k = Math.min(1, (t - t0) / dur); b.textContent = Math.round(n * (1 - Math.pow(1 - k, 3))); if (k < 1) requestAnimationFrame(step); };
    requestAnimationFrame(step);
  }
  window.WPToday = { render };
})();
