// World events: what is likely to happen next in the news, with probabilities.
// Reads D.worldevents (built by psychohistory.worldevents): for every news, politics and technology
// topic, the chance its coverage flares up (a one-in-ten-days high), fades (a one-in-ten-days low) or
// grows, a week and four weeks ahead, from sealed forecasts, with the wire's headlines beside them.
(function () {
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const NAMES = { "timesfm-2.5": "TimesFM", radiant: "Radiant", "chronos-bolt": "Chronos-Bolt", seldon: "Seldon", "seldon-laws": "Seldon laws",
    "radiant-core": "Radiant core", climatology: "One day in ten", persistence: "Stays as it is" };
  const SHORT = { news_composite: "World news", news_war: "War", news_election: "Elections", news_inflation: "Inflation", news_climate: "Climate change",
    news_pandemic: "Pandemics", news_protest: "Protests", politics_composite: "Political crises", politics_sanctions: "Sanctions", politics_tariffs: "Tariffs",
    politics_ceasefire: "Ceasefires", politics_coup: "Coups", politics_impeachment: "Impeachment", politics_referendum: "Referendums",
    tech_composite: "New technology", wiki_ai: "Artificial intelligence", wiki_llm: "Language models", wiki_quantum: "Quantum computing", wiki_crispr: "CRISPR",
    wiki_ev: "Electric vehicles", wiki_fusion: "Fusion energy", wiki_humanoid: "Humanoid robots", wiki_battery: "Batteries", wiki_gene_therapy: "Gene therapy",
    wiki_self_driving: "Self-driving cars", wiki_starship: "Starship" };
  const AREA = { news: "World news", politics: "Politics", tech: "Technology" };
    const state = { frame: "week", open: null, area: "all" };
  let D, W;

  const name = (it) => SHORT[it.id] || it.title;
  const pct = (p) => (p === null || p === undefined ? "–" : p < 0.01 ? "<1%" : p > 0.99 ? ">99%" : Math.round(p * 100) + "%");
  const num = (v) => (v === null || v === undefined ? "–" : esc(Number(v).toPrecision(3)));
  const sp = (v) => (v === null || v === undefined || !isFinite(v) ? "–" : (v >= 0 ? "+" : "−") + Math.abs(v * 100).toFixed(0) + "%");
  const day = (s) => { const d = new Date(String(s).slice(0, 10) + "T12:00:00Z"); return isNaN(d) ? s : d.toLocaleDateString(undefined, { day: "numeric", month: "short", timeZone: "UTC" }); };
  const frameWord = () => (state.frame === "week" ? "next week" : "in four weeks");
  const target = (it) => (state.frame === "week" ? it.week_target : it.month_target);
  const odds = (it, k) => ((it[state.frame] || {})[k]);
  const items = () => W.items.filter((it) => state.area === "all" || it.area === state.area);

  // The sentence for each event, in words a reader would use.
  const KEEP = new Set(["CRISPR", "Starship"]);
  const lc = (s) => (KEEP.has(s) ? s : s.charAt(0).toLowerCase() + s.slice(1));
  const subject = (it) => (it.area === "tech" ? `Interest in ${lc(name(it))}` : `Coverage of ${lc(name(it))}`);
  const said = {
    spike: (it) => `${subject(it)} hits a one-in-ten-days high by ${day(target(it))}`,
    lull: (it) => `${subject(it)} drops to a one-in-ten-days low by ${day(target(it))}`,
    higher: (it) => `${subject(it)} is higher on ${day(target(it))} than now`,
  };

  // A small chart of the last three months with the flare-up and fade lines.
  function spark(it, w = 220, h = 54) {
    const pts = (it.trend || []).map(([, v]) => v).filter((v) => v !== null);
    if (pts.length < 5) return "";
    const lines = [it.cut.spike, it.cut.lull].filter((v) => v !== null && v !== undefined);
    const lo = Math.min(...pts, ...lines), hi = Math.max(...pts, ...lines), pad = (hi - lo) * 0.08 || 1;
    const y = (v) => (h - 4 - ((v - lo + pad) / (hi - lo + 2 * pad)) * (h - 8)).toFixed(1);
    const x = (i) => ((i / (pts.length - 1)) * (w - 2) + 1).toFixed(1);
    const path = pts.map((v, i) => `${i ? "L" : "M"}${x(i)} ${y(v)}`).join("");
    const cut = (v, cls) => (v === null || v === undefined ? "" : `<line x1="0" x2="${w}" y1="${y(v)}" y2="${y(v)}" class="${cls}"/>`);
    return `<svg class="ev-spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true">${cut(it.cut.spike, "hi")}${cut(it.cut.lull, "lo")}
      <path d="${path}"/><circle cx="${x(pts.length - 1)}" cy="${y(pts[pts.length - 1])}" r="3"/></svg>`;
  }
  function meter(p, cls) {
    return `<span class="ev-meter ${cls}" role="img" aria-label="${pct(p)}"><i style="width:${Math.max(2, Math.round((p || 0) * 100))}%"></i></span>`;
  }
  function momentum(it) {
    if (it.momentum === null || it.momentum === undefined) return "";
    const m = it.momentum, word = m > 0.25 ? "heating up" : m < -0.2 ? "cooling" : "steady";
    return `<span class="ev-mom ${m > 0.25 ? "up" : m < -0.2 ? "down" : ""}" title="Last 7 days against the 4 weeks before">${word} ${sp(m)}</span>`;
  }

  function card(it, kind) {
    const p = odds(it, kind), base = kind === "higher" ? 0.5 : 0.1;
    const lift = p !== undefined && p !== null ? p / base : null;
    const news = (it.news || []).slice(0, 2).map((a) => `<li><a href="${esc(a.url)}" target="_blank" rel="noopener noreferrer">${esc(a.title)}</a><small>${esc(a.domain || "")}</small></li>`).join("");
    return `<article class="ev-card ${kind}" data-open="${esc(it.id)}" tabindex="0" role="button" aria-label="${esc(said[kind](it))}: ${pct(p)}">
      <div class="ev-top"><span class="ev-area">${esc(AREA[it.area] || it.area)}</span>${momentum(it)}</div>
      <div class="ev-p"><b>${pct(p)}</b><span>${kind === "higher" ? "chance" : lift && lift >= 1.5 ? `${lift.toFixed(lift >= 10 ? 0 : 1)}× the usual 10%` : "chance; usually 10%"}</span></div>
      <p class="ev-said">${esc(said[kind](it))}</p>
      ${spark(it)}
      ${news ? `<ul class="ev-news">${news}</ul>` : '<p class="ev-nonews">No headlines from the wire for this topic this week.</p>'}
    </article>`;
  }

  function lane(kind, title, blurb) {
    const list = items().filter((it) => odds(it, kind) !== undefined && odds(it, kind) !== null)
      .sort((a, b) => odds(b, kind) - odds(a, kind)).slice(0, 6);
    const shown = list.filter((it) => odds(it, kind) >= (kind === "higher" ? 0.6 : 0.15));
    return `<section class="block" aria-labelledby="ev-${kind}"><header class="bh"><div><h2 id="ev-${kind}">${title}</h2><p>${blurb}</p></div></header>
      ${shown.length ? `<div class="ev-cards">${shown.map((it) => card(it, kind)).join("")}</div>`
        : `<p class="dim">Nothing stands out ${frameWord()}: no topic is above ${kind === "higher" ? "60%" : "15%"}.</p>`}</section>`;
  }

  function table() {
    const rows = items().slice().sort((a, b) => (odds(b, "spike") || 0) - (odds(a, "spike") || 0)).map((it) => {
      const open = state.open === it.id;
      return `<tr class="${open ? "open" : ""}" data-open="${esc(it.id)}" tabindex="0"><th><b>${esc(name(it))}</b><small>${esc(AREA[it.area] || it.area)}</small></th>
        <td>${meter(odds(it, "spike"), "hi")}<span>${pct(odds(it, "spike"))}</span></td>
        <td>${meter(odds(it, "lull"), "lo")}<span>${pct(odds(it, "lull"))}</span></td>
        <td>${meter(odds(it, "higher"), "up")}<span>${pct(odds(it, "higher"))}</span></td>
        <td class="ev-m">${momentum(it) || "–"}</td><td class="ev-n">${(it.news || []).length || "–"}</td></tr>
        ${open ? `<tr class="ev-detail"><td colspan="6">${detail(it)}</td></tr>` : ""}`;
    }).join("");
    return `<section class="block" aria-labelledby="ev-all"><header class="bh"><div><h2 id="ev-all">Every topic</h2>
      <p>Tap a topic for every forecaster's odds, the base rates and the headlines.</p></div></header>
      <div class="table-wrap"><table class="ev-table"><thead><tr><th>Topic</th><th>Flares up</th><th>Fades</th><th>Grows</th><th>Last 7 days</th><th>Headlines</th></tr></thead>
      <tbody>${rows}</tbody></table></div></section>`;
  }

  function detail(it) {
    const M = (it.models || {})[state.frame] || {};
    const who = [...new Set(Object.values(M).flatMap((o) => Object.keys(o || {})))].filter((m) => !/^(climatology|persistence)$/.test(m));
    const lead = W.lead || {};
    const row = (m) => `<tr><th>${esc(NAMES[m] || m)}${m === lead.spike ? ' <em>speaks</em>' : ""}</th><td>${pct((M.spike || {})[m])}</td><td>${pct((M.lull || {})[m])}</td></tr>`;
    const base = state.frame === "month" ? `<tr class="dim"><th>Stays as it is</th><td>${pct(((it.base || {}).spike || {}).persistence)}</td><td>${pct(((it.base || {}).lull || {}).persistence)}</td></tr>` : "";
    const news = (it.news || []).map((a) => `<li><a href="${esc(a.url)}" target="_blank" rel="noopener noreferrer">${esc(a.title)}</a><small>${esc(a.domain || "")}${a.seen ? " · " + esc(day(a.seen)) : ""}</small></li>`).join("");
    return `<div class="ev-d">
      <div><h4>Every forecaster, ${frameWord()}</h4><table class="ev-mini"><thead><tr><th></th><th>Flares up</th><th>Fades</th></tr></thead>
        <tbody>${who.map(row).join("")}<tr class="dim"><th>One day in ten</th><td>10%</td><td>10%</td></tr>${base}</tbody></table>
        <p class="note">Now ${num(it.last)} on ${esc(day(it.last_date))}; flare-up line ${num(it.cut.spike)}, fade line ${num(it.cut.lull)}.
          The middle forecast says ${sp((it[state.frame] || {}).mid)} by ${esc(day(target(it)))}.</p>
        <p><a href="#terminal/${esc(it.id)}">Open in the World terminal</a> · <a href="#series/${esc(it.id)}">The full forecast</a></p></div>
      <div><h4>What the news says</h4>${news ? `<ul class="ev-news">${news}</ul>` : '<p class="dim">No headlines from the wire for this topic this week.</p>'}
        ${spark(it, 320, 80)}<p class="ev-key"><span class="k-hi"></span>flare-up line <span class="k-lo"></span>fade line</p></div></div>`;
  }

  function record() {
    const R = W.record || {}, lead = W.lead || {};
    const part = (ev, word) => {
      const r = R[ev] || {}, m = NAMES[lead[ev]] || lead[ev];
      const one = (x, when) => (x ? `${when}: ${x[0] >= 0 ? `${Math.round(x[0] * 100)}% better` : `${Math.round(-x[0] * 100)}% worse`} than "one day in ten" (${x[1]} past forecasts)` : "");
      const bits = [one(r.week, "a week ahead"), one(r.month, "four weeks ahead")].filter(Boolean);
      return bits.length ? `<li><b>${esc(word)}</b>, by ${esc(m)}: ${bits.join("; ")}.</li>` : "";
    };
    const lines = part("spike", "Flare-up odds") + part("lull", "Fade odds");
    return `<section class="block ev-rec"><header class="bh"><div><h2>How good are these odds?</h2>
      <p>Brier skill on every past backtest window, against simply saying "it happens one day in ten". The forecaster that speaks for each event is the one with the best record.</p></div></header>
      ${lines ? `<ul>${lines}</ul>` : '<p class="dim">The record appears after the first full backtest.</p>'}
      <p class="note">These are odds about <b>coverage</b>, the share of the world's news that mentions a topic (GDELT) or how many people read about it (Wikipedia), not about the events themselves.
      A flare-up in coverage is how the world notices something happening. The four-week odds are sealed in the event ledger and scored in the Monitor; the one-week odds are read from the same sealed forecasts. Headlines are context: no model reads them.</p></section>`;
  }

  // What people with money on it expect to actually happen (D.bets, built by psychohistory.bets).
  function bets() {
    const B = D.bets;
    const all = (B && B.items) || [];
    const list = all.filter((b) => state.area === "all" || b.area === state.area).slice(0, 12);
    const AR = { ...AREA, markets: "Markets", weather: "Weather" };
    const moved = (b) => {
      const parts = [];
      if (Math.abs(b.wk) >= 0.01) parts.push(`<span class="${b.wk > 0 ? "up" : "down"}">${b.wk > 0 ? "▲" : "▼"} ${Math.round(Math.abs(b.wk) * 100)} pt${Math.round(Math.abs(b.wk) * 100) === 1 ? "" : "s"} this week</span>`);
      if (b.since !== B.made_on && Math.abs(b.p - b.p0) >= 0.01) parts.push(`<span>${pct(b.p0)} when first sealed ${esc(day(b.since))}</span>`);
      return parts.join(" · ");
    };
    const money = (v) => (v >= 1e6 ? `$${(v / 1e6).toFixed(v >= 1e7 ? 0 : 1)}M` : `$${Math.round(v / 1e3)}k`);
    const rows = list.map((b) => {
      const m = moved(b);
      return `<li class="bet">
        <div class="bet-p"><b>${pct(b.p)}</b>${meter(b.p, "up")}</div>
        <div class="bet-q"><a href="${esc(b.url)}" target="_blank" rel="noopener noreferrer">${esc(b.q)}</a>
          <small><span class="ev-area">${esc(AR[b.area] || b.area)}</span> settles ${esc(day(b.end))} · ${money(b.vol)} traded${m ? " · " + m : ""}</small></div></li>`;
    }).join("");
    const R = (B && B.record) || {}, week = (R.calls || []).find((c) => c.call === "a week out");
    const rec = week ? `So far ${R.settled} sealed question${R.settled === 1 ? " has" : "s have"} settled. A week out, the bettors' favourite won ${Math.round(week.favourite_won * 100)}% of the time
        (Brier ${week.brier.toFixed(3)}, ${week.skill_vs_coin >= 0 ? `${Math.round(week.skill_vs_coin * 100)}% better` : `${Math.round(-week.skill_vs_coin * 100)}% worse`} than a coin flip).`
      : "None of the sealed questions has settled yet, so the bettors have no record here yet.";
    const body = !B ? `<p class="dim">The first prices are sealed on the next forecast run (<code>psychohistory bets</code>).</p>`
      : list.length ? `<ol class="bets">${rows}</ol>` : `<p class="dim">No question in this area among the most-traded ones today.</p>`;
    return `<section class="block ev-bets" aria-labelledby="ev-bets"><header class="bh"><div><h2 id="ev-bets">What people are betting will happen</h2>
      <p>The most-traded open questions on Polymarket, a prediction market: the price of "yes" is the crowd's chance. ${B ? `Sealed ${esc(B.made_on)}, ${B.days} day${B.days === 1 ? "" : "s"} on record.` : ""}</p></div></header>
      ${body}
      <p class="note">${rec} Every day's prices are sealed with a SHA-256 fingerprint in <code>predictions/bet_ledger.csv</code> and scored when each question settles.
      These are other people's odds about the events themselves, shown beside ours about coverage; no model here reads them.${B && B.seals ? ` Fingerprints: ${B.seals.ok} of ${B.seals.batches} days match.` : ""}</p></section>`;
  }

  function page() {
    const n = W.items.length, top = W.items.slice().sort((a, b) => (odds(b, "spike") || 0) - (odds(a, "spike") || 0))[0];
    const seg = (key, opts) => `<div class="seg" role="group">${opts.map(([k, l]) => `<button class="seg-b" data-${key}="${k}" aria-pressed="${state[key] === k}">${l}</button>`).join("")}</div>`;
    return `<section class="hero-t ev-hero"><div class="orb" aria-hidden="true"></div>
      <p class="eyebrow">Sealed ${esc(W.made_on)} · ${n} topics · headlines ${esc(W.wire ? String(W.wire).slice(0, 10) : "not fetched yet")}</p>
      <h1 id="events-h">What the world is likely <span class="grad">to talk about next.</span></h1>
      <p class="lede">For every topic in world news, politics and technology: the chance it flares up, fades or grows ${frameWord()}, from sealed forecasts, with this week's headlines beside them.${top && odds(top, "spike") >= 0.15 ? ` Likeliest flare-up: <b>${esc(name(top))}</b>, ${pct(odds(top, "spike"))}.` : ""}</p>
      <div class="ev-tools">${seg("frame", [["week", "Next week"], ["month", "Next 4 weeks"]])}${seg("area", [["all", "All"], ["news", "World news"], ["politics", "Politics"], ["tech", "Technology"]])}</div></section>
      ${lane("spike", "Likely to flare up", `Coverage reaching a level it reaches only one day in ten, ${frameWord()}. On a normal day the chance is 10%.`)}
      ${lane("lull", "Likely to fade", `Coverage falling to a low it reaches only one day in ten, ${frameWord()}.`)}
      ${lane("higher", "Likely to grow", `More coverage ${frameWord()} than now, at 60% or better.`)}
      ${bets()}${table()}${record()}`;
  }

  function render(host, data) {
    D = data; W = D.worldevents;
    if (!W || !W.items || !W.items.length) {
      host.innerHTML = `<div class="empty"><b>No world event odds yet.</b>They appear after the next forecast run, from the sealed forecasts of world news, politics and technology.</div>`;
      return;
    }
    host.innerHTML = page();
    host.onclick = (e) => {
      if (e.target.closest("a")) return;
      const b = e.target.closest("[data-frame],[data-area]"), o = e.target.closest("[data-open]");
      if (b) { if (b.dataset.frame) state.frame = b.dataset.frame; if (b.dataset.area) state.area = b.dataset.area; repaint(host); }
      else if (o) {
        state.open = state.open === o.dataset.open ? null : o.dataset.open; repaint(host);
        const row = host.querySelector(`tr[data-open="${CSS.escape(o.dataset.open)}"]`);
        if (row && o.tagName === "ARTICLE") row.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    };
    host.onkeydown = (e) => { if ((e.key === "Enter" || e.key === " ") && e.target.matches("[data-open]")) { e.preventDefault(); e.target.click(); } };
  }
  function repaint(host) { const y = scrollY; host.innerHTML = page(); scrollTo(0, y); }

  // For Today: the three likeliest flare-ups next week.
  function teaser(data) {
    const W2 = data.worldevents;
    if (!W2 || !W2.items) return "";
    const top = W2.items.filter((it) => (it.week || {}).spike >= 0.15).sort((a, b) => b.week.spike - a.week.spike).slice(0, 3);
    if (!top.length) return "";
    return `<section class="block ev-teaser" aria-labelledby="evt-h"><header class="bh"><div><h2 id="evt-h">In the world next week</h2>
      <p>The likeliest flare-ups in world news, politics and technology. On a normal day the chance is 10%.</p></div><a class="icon-b" href="#events">All world events</a></header>
      <div class="ev-chips">${top.map((it) => `<a class="ev-chip" href="#events"><b>${pct(it.week.spike)}</b><span>${esc(SHORT[it.id] || it.title)}: a one-in-ten-days high</span>${(it.news || [])[0] ? `<small>${esc(it.news[0].title)}</small>` : ""}</a>`).join("")}</div></section>`;
  }

  window.WPEvents = { render, teaser };
})();
