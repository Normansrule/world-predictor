// Coming up: every sealed forecast, world-event odd, betting question and your own sealed calls, by
// the day each one is settled against reality. Reads D.frames (every series at each time frame),
// D.worldevents, D.bets and the calls you sealed in Forecast Studio (this browser only). "Add to
// calendar" downloads the list as an .ics file any calendar app opens, so the day a forecast is
// judged lands in your own diary.
(function () {
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const pct = (p) => (p === null || p === undefined ? "–" : p < 0.01 ? "<1%" : p > 0.99 ? ">99%" : Math.round(p * 100) + "%");
  const sp = (v) => (v === null || v === undefined || !isFinite(v) ? "–" : (v >= 0 ? "+" : "−") + Math.abs(v * 100).toFixed(1) + "%");
  const DAY = 86400000;
  const KINDS = [["all", "Everything"], ["forecast", "Forecasts"], ["event", "World events"], ["bet", "Bets"], ["yours", "Your calls"]];
  const TAG = { forecast: "Forecast", event: "World event", bet: "Bet", yours: "Your call" };
  const FRAMES = { week: "next week", month: "next month", year: "next year" };   // "next day" is tomorrow: no diary needed
  const SHOWN = 5;                                                                   // per day, before "more"
  const state = { kind: "all", span: 90, open: {} };
  let D, host;

  const iso = (s) => String(s || "").slice(0, 10);
  const when = (s) => { const d = new Date(iso(s) + "T12:00:00Z"); return isNaN(d) ? null : d; };
  const nice = (d, o) => d.toLocaleDateString(undefined, { timeZone: "UTC", ...o });

  function today() {
    // The app's own "now": the newest sealed day, so a saved offline copy still reads sensibly.
    const sealed = ((D.outlook || [])[0] || {}).made_on || D.meta.generated;
    const real = new Date(new Date().toISOString().slice(0, 10) + "T12:00:00Z");
    const s = when(sealed);
    return s && s > real ? s : real;
  }

  function model(f) {
    const g = f || {}, keys = Object.keys(g);
    return [D.meta.model, "radiant", "seldon", keys[0]].find((k) => k && g[k]);
  }

  // Everything that settles on a known day, as {date, kind, title, said, p, href, ext}.
  function entries() {
    const out = [];
    const F = D.frames || {};
    (F.items || []).forEach((it) => {
      Object.entries(FRAMES).forEach(([key, word]) => {
        const fr = (it.frames || {})[key]; const m = model(fr); const c = m && fr[m];
        if (!c || !c.date) return;
        out.push({ date: iso(c.date), kind: "forecast", title: it.title, area: it.area,
          said: `${pct(c.p)} chance it is higher than now (${word}); middle ${sp(c.mid)}, 80% range ${sp(c.low)} to ${sp(c.high)}`,
          p: c.p, href: `#series/${it.id}`, sure: c.sure });
      });
    });
    const W = D.worldevents;
    ((W && W.items) || []).forEach((it) => {
      [["week", it.week_target], ["month", it.month_target]].forEach(([k, date]) => {
        const p = ((it[k] || {}).spike);
        if (!date || p === undefined || p === null || p < 0.15) return;   // only the flare-ups worth a note
        out.push({ date: iso(date), kind: "event", title: it.title, area: it.area,
          said: `${pct(p)} chance coverage hits a one-in-ten-days high by then (usually 10%)`, p, href: "#events" });
      });
    });
    ((D.bets && D.bets.items) || []).forEach((b) => out.push({ date: iso(b.end), kind: "bet", title: b.q, area: b.area,
      said: `Bettors on Polymarket give it ${pct(b.p)}`, p: b.p, href: b.url, ext: true }));
    let mine = [];
    try { mine = JSON.parse(localStorage.getItem("wp-calls-v1")) || []; } catch (e) { mine = []; }
    mine.forEach((c) => out.push({ date: iso(c.date), kind: "yours", title: c.title,
      said: `You said ${Number(c.value).toPrecision(4)}, between ${Number(c.lo).toPrecision(4)} and ${Number(c.hi).toPrecision(4)}`, href: "#studio" }));
    return out.filter((e) => when(e.date)).sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : a.kind.localeCompare(b.kind)));
  }

  function visible(all) {
    const t0 = today().getTime(), t1 = t0 + state.span * DAY;
    return all.filter((e) => (state.kind === "all" || e.kind === state.kind) && when(e.date).getTime() >= t0 - DAY / 2 && when(e.date).getTime() <= t1);
  }

  // Calendar weeks starting Monday, so "this week" means what it says.
  function bucket(d) {
    const t0 = today(), monday = new Date(t0.getTime() - ((t0.getUTCDay() + 6) % 7) * DAY);
    const days = Math.floor((d - monday) / DAY);
    if (days < 7) return "This week";
    if (days < 14) return "Next week";
    if (d.getUTCMonth() === t0.getUTCMonth() && d.getUTCFullYear() === t0.getUTCFullYear()) return "Later this month";
    return nice(d, { month: "long", year: "numeric" });
  }

  function row(e) {
    const link = e.ext ? `href="${esc(e.href)}" target="_blank" rel="noopener noreferrer"` : `href="${esc(e.href)}"`;
    return `<li class="cal-row k-${e.kind}"><span class="cal-tag">${TAG[e.kind]}</span>
      <div class="cal-what"><a ${link}>${esc(e.title)}</a><small>${esc(e.said)}</small></div>
      ${e.p !== undefined && e.p !== null ? `<b class="cal-p">${pct(e.p)}</b>` : "<span></span>"}</li>`;
  }

  // Within a day: your calls and bets first, then the boldest forecasts (furthest from even odds).
  const rank = (e) => (e.kind === "yours" ? -2 : e.kind === "bet" ? -1 : -Math.abs((e.p ?? 0.5) - 0.5));
  const shown = (d) => { const all = d.items.slice().sort((a, b) => rank(a) - rank(b)); return state.open[d.date] ? all : all.slice(0, SHOWN); };
  const more = (d) => (d.items.length > SHOWN ? `<button class="linkish cal-more" data-day="${esc(d.date)}" aria-expanded="${!!state.open[d.date]}">${state.open[d.date] ? "Show fewer" : `Show ${d.items.length - SHOWN} more`}</button>` : "");

  function page() {
    const all = entries(), list = visible(all);
    const groups = [];
    list.forEach((e) => {
      const d = when(e.date), b = bucket(d);
      let g = groups[groups.length - 1];
      if (!g || g.name !== b) groups.push((g = { name: b, days: [] }));
      let day = g.days[g.days.length - 1];
      if (!day || day.date !== e.date) g.days.push((day = { date: e.date, items: [] }));
      day.items.push(e);
    });
    const counts = Object.fromEntries(KINDS.map(([k]) => [k, visible(all.filter((e) => k === "all" || e.kind === k)).length]));
    const seg = (key, opts) => `<div class="seg" role="group">${opts.map(([k, l, n]) => `<button class="seg-b" data-${key}="${k}" aria-pressed="${String(state[key]) === String(k)}">${l}${n !== undefined ? ` <small>${n}</small>` : ""}</button>`).join("")}</div>`;
    const next = list[0];
    return `<section class="hero-t cal-hero"><div class="orb" aria-hidden="true"></div>
      <p class="eyebrow">Sealed ${esc(((D.outlook || [])[0] || {}).made_on || D.meta.generated)} · ${list.length} settle in the next ${state.span} days</p>
      <h1 id="calendar-h">Coming up: <span class="grad">the days reality answers.</span></h1>
      <p class="lede">Every sealed forecast, world-event odd and bet, and the calls you sealed yourself, on the day each one is settled against what really happened.${next ? ` Next: <b>${esc(next.title)}</b>, ${esc(nice(when(next.date), { weekday: "long", day: "numeric", month: "long" }))}.` : ""}</p>
      <div class="ev-tools">${seg("kind", KINDS.map(([k, l]) => [k, l, counts[k]]))}${seg("span", [[14, "2 weeks"], [90, "3 months"], [400, "A year"]])}
        <button class="btn small" id="cal-ics" ${list.length ? "" : "disabled"} title="Download these as an .ics file for Google Calendar, Apple Calendar or Outlook">Add to calendar</button></div></section>
      ${groups.length ? groups.map((g) => `<section class="block cal-group"><header class="bh"><div><h2>${esc(g.name)}</h2></div></header>
        ${g.days.map((d) => { const dt = when(d.date); return `<div class="cal-day"><div class="cal-date"><b>${nice(dt, { day: "numeric" })}</b><span>${nice(dt, { weekday: "short" })}</span><small>${nice(dt, { month: "short" })}</small></div>
          <ol class="cal-list">${shown(d).map(row).join("")}</ol>${more(d)}</div>`; }).join("")}</section>`).join("")
        : `<div class="empty"><b>Nothing settles in this window.</b>Try a longer span, or seal a call of your own in the <a href="#studio">Forecast Studio</a>.</div>`}
      <p class="note">Forecasts are each series' sealed call at the next day, week, month and year (${esc(model(((D.frames || {}).items || [{}])[0]?.frames?.month) || D.meta.model)}); world events show only flare-ups at 15% or more; bets settle on the day Polymarket says, which can move. Your calls live in this browser only.</p>`;
  }

  // RFC 5545 calendar file: one all-day event per entry, stable ids so a re-import updates instead of duplicating.
  function ics(list) {
    const fold = (s) => s.replace(/[\\;,]/g, (c) => "\\" + c).replace(/\n/g, "\\n");
    const stamp = new Date().toISOString().replace(/[-:]/g, "").slice(0, 15) + "Z";
    const base = location.href.split("#")[0];
    const lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//World Predictor//Coming up//EN", "CALSCALE:GREGORIAN", "X-WR-CALNAME:World Predictor"];
    list.forEach((e) => {
      const d = e.date.replace(/-/g, ""), end = new Date(when(e.date).getTime() + DAY).toISOString().slice(0, 10).replace(/-/g, "");
      const uid = `${e.kind}-${d}-${e.title}`.toLowerCase().replace(/[^a-z0-9]+/g, "-").slice(0, 80) + "@world-predictor";
      const url = e.ext ? e.href : base + e.href;
      lines.push("BEGIN:VEVENT", `UID:${uid}`, `DTSTAMP:${stamp}`, `DTSTART;VALUE=DATE:${d}`, `DTEND;VALUE=DATE:${end}`,
        `SUMMARY:${fold(`${TAG[e.kind]}: ${e.title}`)}`, `DESCRIPTION:${fold(`${e.said}\nSettled against reality on this day.\n${url}`)}`, `URL:${url}`, "TRANSP:TRANSPARENT", "END:VEVENT");
    });
    lines.push("END:VCALENDAR");
    // Lines longer than 75 octets are folded (RFC 5545 3.1); 60 characters keeps multi-byte text inside it.
    const wrap = (l) => { const out = []; for (let i = 0; i < l.length; i += 60) out.push((i ? " " : "") + l.slice(i, i + 60)); return out.join("\r\n"); };
    return lines.map(wrap).join("\r\n") + "\r\n";
  }

  function render(root, data) {
    D = data; host = root;
    host.innerHTML = page();
    host.onclick = (e) => {
      const m = e.target.closest("[data-day]");
      if (m) { state.open[m.dataset.day] = !state.open[m.dataset.day]; const y = scrollY; render(host, D); scrollTo(0, y); return; }
      const b = e.target.closest("[data-kind],[data-span]");
      if (b) { if (b.dataset.kind) state.kind = b.dataset.kind; if (b.dataset.span) state.span = +b.dataset.span; render(host, D); return; }
      if (e.target.closest("#cal-ics")) {
        const blob = new Blob([ics(visible(entries()))], { type: "text/calendar" });
        const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "world-predictor-coming-up.ics";
        document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500);
      }
    };
  }

  // For Today: the next three things to be settled.
  function teaser(data) {
    D = data;
    const t0 = today().getTime();
    const soon = entries().filter((e) => when(e.date).getTime() >= t0 - DAY / 2 && when(e.date).getTime() <= t0 + 45 * DAY);   // whatever the calendar's filter
    const strong = soon.filter((e) => e.kind !== "forecast" || e.sure);
    const pick = (strong.length ? strong : soon).slice(0, 3);
    if (!pick.length) return "";
    return `<section class="block cal-teaser" aria-labelledby="calt-h"><header class="bh"><div><h2 id="calt-h">Coming up</h2>
      <p>The next sealed calls reality will answer.</p></div><a class="icon-b" href="#calendar">The calendar</a></header>
      <ol class="cal-list">${pick.map((e) => row({ ...e, said: `${nice(when(e.date), { weekday: "short", day: "numeric", month: "short" })} · ${e.said}` })).join("")}</ol></section>`;
  }

  window.WPCalendar = { render, teaser, entries: () => entries(), ics };
})();
