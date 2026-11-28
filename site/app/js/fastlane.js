// The fast lane: does anything we follow move before markets do? Loaded when the Markets page opens.
(function () {
  "use strict";
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const pct = (x, d = 0) => (x == null ? "–" : `${(x * 100).toFixed(d)}%`);
  const LAG = ["the next day", "two days on", "three days on"];
  let cache = null, open = false;

  function load() {
    if (!cache) cache = fetch("data/fastlane.json", { cache: "no-cache" }).then((r) => (r.ok ? r.json() : null)).catch(() => null);
    return cache;
  }
  const nm = (p, id) => esc((p.names && p.names[id]) || id);
  const year = (d) => String(d || "").slice(0, 4);

  function scanCard(p) {
    const s = p.scan;
    const held = (s.held_links || []).slice(0, 5);
    return `<div class="fl-c"><h3>Lead-lag scan</h3>
      <p class="fl-big"><b>${s.held}</b> <span>of ${s.tested.toLocaleString()} links held</span></p>
      <p class="fl-s">Every news, politics and Wikipedia series and every other market was tried as an early signal for each market, one, two and three days on. ${s.showed.toLocaleString()} looked real before ${year(p.test_from)}; ${s.held} still held after it, against about ${Math.round(s.expected)} by luck alone.</p>
      <p class="fl-v">${s.held <= s.expected * 2.5 ? "Plainly: by the close, news, attention and other markets are already in the price. Nothing here learns faster than the market." : "A few links carry real early information."}</p>
      ${held.length ? `<ul class="fl-l">${held.map((l) => `<li><b>${nm(p, l.source)}</b> → ${nm(p, l.target)}, ${LAG[l.lag] || `${l.lag + 1} days on`}<small>${l.ic_train > 0 ? "same way" : "opposite way"} · ${l.ic_train.toFixed(2)} before, ${l.ic_test.toFixed(2)} after</small></li>`).join("")}</ul>` : ""}</div>`;
  }

  function fearCard(p) {
    const f = p.fear;
    if (!f) return "";
    const lo = Math.min(f.now, f.normal, f.week) * 0.85, hi = Math.max(f.now, f.normal, f.week) * 1.15;
    const x = (v) => (((v - lo) / (hi - lo)) * 100).toFixed(1);
    return `<div class="fl-c"><h3>Fear clock</h3>
      <p class="fl-big"><b>${f.now}</b> <span>VIX on ${esc(f.date)} · normal about ${f.normal}</span></p>
      <div class="fl-g" aria-hidden="true"><i class="n" style="left:${x(f.normal)}%"></i><i class="w" style="left:${x(f.week)}%"></i><i class="t" style="left:${x(f.now)}%"></i></div>
      <p class="fl-s">Fear overreacts and then fades: half the gap to normal closes in about <b>${f.half_life ?? "–"} trading days</b>. Expected in a week: <b>${f.week}</b>; in a month: <b>${f.month}</b>, so fear should ${f.falls ? "fall" : "rise"}.</p>
      <table class="fl-t"><thead><tr><th>Ahead</th><th>Right</th><th>95% range</th><th>Surest quarter</th></tr></thead><tbody>
      ${f.record.map((r) => `<tr><td>${r.h === 1 ? "1 day" : r.h === 5 ? "1 week" : "1 month"}</td><td><b>${pct(r.hit, 1)}</b></td><td>${pct(r.lo)}–${pct(r.hi)}</td><td>${pct(r.strong)}</td></tr>`).join("")}</tbody></table>
      <p class="fl-n">${f.record[0] ? f.record[0].n.toLocaleString() : ""} days since ${year(p.test_from)}, each scored from a fit on the three years before it. The range is a block bootstrap, so it stays honest about runs of similar days.</p></div>`;
  }

  function sizeCard(p) {
    const rows = p.sizing || [];
    if (!rows.length) return "";
    const shown = open ? rows : rows.slice(0, 8);
    const inside = rows.reduce((a, r) => a + r.inside, 0) / rows.length, better = rows.filter((r) => r.gain > 0.002).length;
    return `<div class="fl-c fl-wide"><h3>Risk first: how big a move to expect this week</h3>
      <p class="fl-s">Before the direction, the size. Each range is meant to hold 8 weeks in 10, and since ${year(p.test_from)} they held <b>${pct(inside)}</b>. Fear (the VIX) and attention spikes join a market's own swings only where they made its range better on earlier years: they did for ${better} of ${rows.length}.</p>
      <table class="fl-t fl-sz"><thead><tr><th>Market</th><th>Next week, 8 in 10</th><th>Held since ${year(p.test_from)}</th><th>Reads</th></tr></thead><tbody>
      ${shown.map((r) => `<tr><td><a href="#series/${esc(r.id)}">${nm(p, r.id)}</a></td><td><span class="fl-bar"><i style="width:${Math.min(100, (r.move / rows[0].move) * 100).toFixed(1)}%"></i></span> ±${pct(r.move, 1)}</td><td>${pct(r.inside)}</td><td>${r.uses_now.length ? r.uses_now.map((u) => `<span class="fl-tag">${u.startsWith("vix") ? "fear" : u === "attn" ? "attention" : "market"}</span>`).filter((v, i, a) => a.indexOf(v) === i).join("") : '<span class="dim">its own swings</span>'}</td></tr>`).join("")}</tbody></table>
      ${rows.length > 8 ? `<button class="btn small" data-fl-more>${open ? "Show fewer" : `Show all ${rows.length}`}</button>` : ""}</div>`;
  }

  function linksTable(p) {
    const L = (p.scan.links || []).slice(0, 15);
    if (!L.length) return "";
    return `<details class="fl-d"><summary>The strongest links before ${year(p.test_from)}, and what became of them</summary>
      <table class="fl-t"><thead><tr><th>Early signal</th><th>Market</th><th>Days on</th><th>Before</th><th>After</th><th></th></tr></thead><tbody>
      ${L.map((l) => `<tr><td>${nm(p, l.source)}</td><td>${nm(p, l.target)}</td><td>${l.lag + 1}</td><td>${l.ic_train.toFixed(2)}</td><td>${l.ic_test == null ? "–" : l.ic_test.toFixed(2)}</td><td><span class="fl-vd ${l.verdict}">${l.verdict}</span></td></tr>`).join("")}</tbody></table>
      <p class="fl-n">Numbers are rank correlations with the market's next day. "Faded" kept its sign but lost its strength; "flipped" turned around. This is why a link that looks good in the past is not trusted until it holds on days it never saw.</p></details>`;
  }

  function html(p) {
    return `<header class="ph"><h2>Fast lane: does anything move before markets do?</h2><span class="pm">scored on days no fit had seen, since ${esc(p.test_from)} · data through ${esc(p.through)}</span></header>
      <div class="fl-grid">${scanCard(p)}${fearCard(p)}${sizeCard(p)}</div>${linksTable(p)}`;
  }

  function hydrate(root) {
    const box = root && root.querySelector("[data-fast]");
    if (!box) return;
    box.hidden = true;
    load().then((p) => {
      if (!p || !p.scan) return;
      const paint = () => { box.innerHTML = html(p); box.hidden = false; };
      paint();
      box.onclick = (e) => { if (e.target.closest("[data-fl-more]")) { open = !open; paint(); } };
    });
  }

  window.WPFast = { hydrate, html };
})();
