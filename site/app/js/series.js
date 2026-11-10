// Series pages: one page per series with every backtest window it was tested on, what each window
// said against what really happened, its newest sealed forecast, and every sealed forecast whose
// date has already arrived. Reads D.track (past windows) and D.opened (scored sealed forecasts).
(function () {
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const AREA_NAMES = { news: "World news", politics: "Politics", markets: "Markets", tech: "Technology", weather: "Weather and Earth" };
  const hue = (d) => (AREA_NAMES[d] ? `var(--${d})` : "var(--ink-3)");
  const DAY = 864e5;
  const state = { id: null, k: null };

  // The windows of one series, unpacked: dates, actual values, and per window its percentiles.
  function windowsOf(D, id) {
    const T = (D.track || {})[id];
    if (!T || !T.windows.length) return null;
    const t0 = Date.parse(T.start);
    const dates = T.days.map((d) => new Date(t0 + d * DAY).toISOString().slice(0, 10));
    const ev = Object.fromEntries(((D.evidence || {})[id] || []).map((r) => [r[0], r]));
    const list = T.windows.map(([origin, at, q10, q50, q90]) => {
      const n = q50.length, before = at > 0 ? T.actual[at - 1] : null, end = T.actual[at + n - 1];
      const actual = T.actual.slice(at, at + n);
      const inside = actual.filter((a, i) => a !== null && a >= q10[i] && a <= q90[i]).length / Math.max(1, actual.filter((a) => a !== null).length);
      const e = ev[origin] || [];
      const pUp = e[3] ?? null, rose = e[4] ?? null;
      return {
        origin, at, n, q10, q50, q90, actual, inside, pUp, rose, mase: e[1] ?? null,
        said: before ? q50[n - 1] / before - 1 : null, did: before && end !== null ? end / before - 1 : null,
        called: pUp === null || rose === null || Math.abs(pUp - 0.5) < 0.005 ? null : (pUp > 0.5) === (rose === 1),
        dates: dates.slice(at, at + n),
      };
    });
    return { dates, actual: T.actual, list };
  }

  // Markets only: what the newest forecast's chance of rising suggests doing, the backtest record of
  // that suggestion, and the advice that survives it (advice.js). Research, not financial advice.
  function adviceCard(D, o, domain, modelName) {
    const A = window.WPAdvice;
    if (!A || !o || domain !== "markets") return "";
    const a = A.advise(D, o.p_up); if (!a) return "";
    const R = a.all, row = (t, label) => { const r = R[t]; return `<tr${t === a.tier ? ' aria-current="true"' : ""}><th scope="row">${label}</th><td class="num">${r.n}</td>
      <td class="num">${t === "hold" ? "–" : r.n ? `${r.right} of ${r.n} (${Math.round((r.right / r.n) * 100)}%)` : "–"}</td><td class="num">${A.pc(r.move)}</td>
      <td>${t === "hold" ? '<span class="dim">no lean</span>' : r.works ? '<span class="pos">beat a coin flip</span>' : '<span class="neg">did not</span>'}</td></tr>`; };
    return `<div class="card advice advice-${a.action === "Hold" ? "hold" : a.tier}">
      <header class="ph"><h2>What the odds suggest</h2><span class="pm">research, not financial advice</span></header>
      <div class="adv-top">
        <div><span class="adv-k">${esc(modelName)} says</span><b class="adv-p">${Math.round(o.p_up * 100)}%</b><span class="adv-s">chance higher by ${esc(o.target_date)}</span></div>
        <div><span class="adv-k">Read on its own</span><b class="adv-lean">${esc(a.lean)}</b><span class="adv-s">60% or more leans buy, 40% or less leans sell</span></div>
        <div><span class="adv-k">After checking the record</span><b class="adv-act">${esc(a.action)}</b><span class="adv-s">${a.backed ? "the record backs this lean" : a.tier === "hold" ? "nothing to act on" : "the record does not back the lean"}</span></div>
      </div>
      <p class="adv-why">${esc(A.why(a))}</p>
      <div class="table-wrap"><table class="dense adv-table"><thead><tr><th>Lean</th><th>Backtest windows</th><th>Went that way</th><th>Average real move</th><th>Record</th></tr></thead><tbody>
        ${row("buy", "Buy or hold (60%+ higher)")}${row("hold", "No lean (between 40% and 60%)")}${row("sell", "Sell, buy back later (40% or less)")}</tbody></table></div>
      <p class="note">Every ${esc(modelName)} backtest window on every market, about a month ahead each. "Went that way" counts rises for the buy lean and falls for the sell lean; a lean is passed on only if it beat a coin flip in at least ${A.MIN} windows (one-sided binomial test, p &lt; ${A.ALPHA}). Holding every market moved ${A.pc(R.allMove)} on average over the same windows. An earlier test found following the forecasts trailed simply holding (Markets desk). This is a research tool, not financial advice.</p>
    </div>`;
  }

  // An <iframe> showing this series' newest sealed forecast as a small card (app/embed.html), served by
  // GitHub Pages so it updates by itself after every run. From a local copy it still points at Pages.
  function embedCode(id, title) {
    const web = /^https?:$/.test(location.protocol) && !/^(localhost|127\.|\[::1\])/.test(location.hostname)
      ? location.href.replace(/[#?].*$/, "").replace(/index\.html$/, "") : "https://normansrule.github.io/world-predictor/app/";
    return `<iframe src="${web}embed.html#${encodeURIComponent(id)}" width="460" height="250" style="border:0;border-radius:12px;max-width:100%" loading="lazy" title="${esc(title)}: World Predictor forecast"></iframe>`;
  }

  const MODEL_NAMES = { "timesfm-2.5": "TimesFM", radiant: "Radiant", "radiant-core": "Radiant core", "chronos-bolt": "Chronos-Bolt", seldon: "Seldon", "seldon-laws": "Seldon laws" };
  const MODEL_HUES = { "timesfm-2.5": "var(--tfm)", radiant: "var(--radiant)", "radiant-core": "var(--radiant)", "chronos-bolt": "var(--rival)", seldon: "var(--seldon)", "seldon-laws": "var(--seldon)" };
  const mname = (m) => MODEL_NAMES[m] || (/^timesfm/.test(m) ? "TimesFM" : m);

  // Every forecaster's backtest record on this one series (D.champions, from champions.py), best first,
  // with the honest answer to "should I then use the top one here?" from the hold-out test.
  function champions(D, id) {
    const C = D.champions, rows = C && C.series && C.series[id];
    if (!rows || !rows.length) return "";
    const worst = Math.max(...rows.map((r) => r[1])), H = C.holdout;
    const bars = rows.map(([m, e, inside, n], i) => `<tr${i === 0 ? ' class="top"' : ""}>
        <th scope="row"><span class="dot" style="--c:${MODEL_HUES[m] || "var(--ink-3)"}"></span>${esc(mname(m))}${i === 0 ? ' <span class="tag" style="--c:var(--up)">lowest error</span>' : ""}</th>
        <td class="bar-cell"><span class="hbar" style="--w:${(100 * e / worst).toFixed(1)}%;--c:${MODEL_HUES[m] || "var(--ink-3)"}"></span><span class="num">${(e * 100).toFixed(2)}%</span>${i ? `<span class="more">+${((e / rows[0][1] - 1) * 100).toFixed(1)}% more</span>` : ""}</td>
        <td class="num">${Math.round(inside * 100)}%</td><td class="num win">${n}</td></tr>`).join("");
    const verdict = H ? `<p class="note champ-verdict"><b>Should you just use the top model on each series?</b> We tested it: picking each series' best model on its first half of windows and using it on the second half
        was better than using ${esc(mname(H.default))} everywhere on ${H.better} of ${H.series} series and worse on ${H.worse}
        (average error ${(H.pick_smape * 100).toFixed(2)}% against ${(H.default_smape * 100).toFixed(2)}%). The early winner was still the winner only ${H.kept} times in ${H.series}.
        ${H.pick_smape < H.default_smape && Math.abs(H.t) >= 2 ? "So the top row is worth following here." : "So treat the top row as history, not a tip: a lead on one series rarely lasts."}</p>` : "";
    return `<div class="card champs"><header class="ph"><h2>Which model has been best here</h2><span class="pm">backtest · lower error is better</span></header>
      <div class="table-wrap"><table class="dense champ-table"><thead><tr><th>Model</th><th class="bar-cell">Average error</th><th>Inside 80%</th><th class="win">Windows</th></tr></thead><tbody>${bars}</tbody></table></div>
      ${verdict}</div>`;
  }

  function render(host, D, id) {
    const { plot, legend, fmt } = window.WPCharts;
    const model = D.meta.model, modelName = /^timesfm/.test(model) ? "TimesFM" : model;
    const row = (D.series || []).find((r) => r.id === id);
    const o = (D.outlook || []).find((x) => x.id === id);
    const W = windowsOf(D, id);
    const domain = (row || o || {}).domain, title = (row || o || { title: id }).title;
    if (state.id !== id) { state.id = id; state.k = W ? W.list.length - 1 : null; }
    const opened = (D.opened || []).filter((r) => r[0] === id);
    const mine = opened.filter((r) => r[1] === model), seldonRows = opened.filter((r) => r[1] === "seldon");
    const hits = mine.filter((r) => r[8] !== null && r[8] >= r[5] && r[8] <= r[7]).length;
    const trace = (D.outlook || []).some((x) => x.id === id);
    const lab = D.lab && D.lab.series.some((s) => s.id === id);

    const fact = (k, v, cls = "") => `<div><dt>${k}</dt><dd class="${cls}">${v}</dd></div>`;
    const skillCls = (v) => (v === null || v === undefined || Math.abs(v) < 0.02 ? "" : v > 0 ? "pos" : "neg");
    host.innerHTML = `
      <a class="back" href="#series">All series</a>
      <div class="vhead">
        <p class="flags"><span class="tag" style="--c:${hue(domain)}">${esc(AREA_NAMES[domain] || domain || "Series")}</span>${row ? `<span class="tag" style="--c:var(--ink-3)">${esc(row.scale)}</span>` : ""}</p>
        <h1 id="sp-h" tabindex="-1">${esc(title)}</h1>
        <p class="lede">${esc((o && o.description) || "")}${o && o.description ? ". " : ""}Every forecast ${esc(modelName)} made for it, and what really happened.</p>
      </div>
      <div class="card detail"><dl class="facts">
        ${fact('Skill vs "no change"', row ? fmt.signedPct(row.skill) : "–", row ? skillCls(row.skill) : "")}
        ${fact("Right direction", row ? fmt.pct(row.direction) : "–")}
        ${fact("Inside its 80% range", row ? fmt.pct(row.coverage80) : "–")}
        ${fact("Odds score", row && row.brier !== null ? row.brier.toFixed(3) : "–")}
        ${fact("Past windows tested", W ? String(W.list.length) : "–")}
        ${fact("Real forecasts opened", mine.length ? `${hits} of ${mine.length} in range` : "none yet")}
      </dl><p class="note" style="margin:0">Skill is error removed against "tomorrow looks like today". The range should catch reality about 8 times in 10, and an odds score of 0.25 is a coin flip.</p></div>
      ${adviceCard(D, o, domain, modelName)}
      ${champions(D, id)}

      <div class="card">
        <header class="ph"><h2>Every past forecast against what happened</h2><span class="pm">backtest · ${W ? W.list.length : 0} windows</span></header>
        ${W ? `<div class="controls">
          <input type="range" id="sp-slider" min="0" max="${W.list.length - 1}" value="${state.k}" aria-label="Past forecast window">
          <span class="note" id="sp-readout" aria-live="polite"></span></div>
          <div id="sp-chart"></div><div id="sp-legend"></div>
          <div class="table-wrap opened-wrap"><table class="dense olist sp-windows" id="sp-table"></table></div>`
        : '<div class="empty"><b>No backtest for this series yet.</b>It appears after the next forecast run.</div>'}
      </div>

      <div class="two">
        <div class="card"><header class="ph"><h2>Sealed on the real future</h2><span class="pm" id="sp-fan-pm"></span></header>
          ${o ? `<div class="cmp-when" id="sp-weeks-row"><span class="cmp-area-name">Sealed</span><div class="chips" id="sp-weeks" role="group" aria-label="Which sealed forecast to show"></div></div>
            <p class="cmp-verdict" id="sp-fan-verdict" aria-live="polite"></p>
            <div id="sp-fan"></div><div id="sp-fan-legend"></div>
            <p class="note" id="sp-fan-note"></p>`
          : '<div class="empty"><b>Nothing sealed for this series yet.</b>The next weekly run seals a forecast for it.</div>'}
        </div>
        <div class="card"><header class="ph"><h2>Opened so far</h2><span class="pm">sealed, not a backtest</span></header>
          ${mine.length ? `<div class="table-wrap opened-wrap"><table class="dense opened" id="sp-opened"></table></div>
            ${mine.some((r) => r[11]) ? `<p class="note">† Sealed after its date but before the source published that value, so ${esc(modelName)} never saw it.</p>` : ""}`
          : `<div class="empty"><b>No sealed forecast has reached its date yet.</b>${o ? `The first step of this week's opens on ${esc(o.fan[0][0])}.` : "They open as their dates arrive."}</div>`}
        </div>
      </div>
      <div class="actions">
        ${o ? `<a class="btn primary" href="#studio/${esc(id)}">Ask about a level</a>` : ""}
        ${lab ? `<a class="btn" href="#lab/${esc(id)}">Make a blind call in the Lab</a>` : ""}
        ${trace ? `<a class="btn" href="#trace/${esc(id)}">Follow this forecast to its source</a>` : ""}
        ${o && window.WPShare ? `<button class="btn" id="sp-share" title="A 1200 × 630 picture of this sealed forecast, to post or send">Share as image</button>` : ""}
        ${o ? `<a class="btn" href="#compare/${esc(id)}">Compare with others</a>` : ""}
        ${o ? `<button class="btn" id="sp-embed" title="Copy the code that shows this forecast as a live card on any web page">Embed</button>` : ""}
      </div>`;
    const share = host.querySelector("#sp-share");
    const embed = host.querySelector("#sp-embed");
    if (embed) embed.onclick = async () => {
      const code = embedCode(id, title);
      try { await navigator.clipboard.writeText(code); embed.textContent = "Code copied"; setTimeout(() => (embed.textContent = "Embed"), 2400); }
      catch (e) { window.prompt("Copy this code into your web page:", code); }
    };
    if (share) share.onclick = async () => { share.disabled = true; const how = await window.WPShare.save(o, D); share.textContent = how === "shared" ? "Shared" : "Image saved"; setTimeout(() => { share.disabled = false; share.textContent = "Share as image"; }, 2400); };

    if (W) {
      const draw = () => {
        const w = W.list[state.k];
        const pts = W.dates.map((d, i) => [d, W.actual[i]]);
        plot(host.querySelector("#sp-chart"), {
          x: "date", height: 320, left: 56, label: `${title}: every past forecast and what happened`,
          bands: W.list.map((v, i) => ({ points: v.dates.map((d, j) => [d, v.q10[j], v.q90[j]]), color: i === state.k ? "var(--band)" : "var(--band-faint)", hatch: i === state.k, fade: false })),
          lines: [{ points: pts, color: "var(--ink)", width: 1.5, name: "what happened" },
            ...W.list.map((v, i) => ({ points: v.dates.map((d, j) => [d, v.q50[j]]), color: "var(--tfm)", width: i === state.k ? 2.4 : 1, opacity: i === state.k ? 1 : 0.4, draw: false, name: modelName }))],
          dots: [{ points: w.dates.map((d, j) => [d, w.actual[j]]), color: "var(--ink)", r: 2.4 }],
          refs: [{ x: w.dates[0] }],  // the readout names the date; a label here runs off the edge for the newest window
        });
        const verdict = w.called === null ? "" : w.called ? " It called the direction right." : " It called the direction wrong.";
        host.querySelector("#sp-readout").textContent = `Made ${fmt.date(Date.parse(w.origin))}: the middle said ${fmt.signedPct(w.said)}, reality went ${fmt.signedPct(w.did)}, and ${Math.round(w.inside * 100)}% of the days landed inside the range.${verdict}`;
        const slider = host.querySelector("#sp-slider");
        slider.value = state.k; slider.setAttribute("aria-valuetext", `Forecast made ${w.origin}`);
        host.querySelectorAll("#sp-table tr[data-k]").forEach((tr) => tr.setAttribute("aria-selected", String(+tr.dataset.k === state.k)));
      };
      const mark = (v) => (v === null ? '<span class="dim">–</span>' : v ? '<span class="pos">✓ right</span>' : '<span class="neg">✗ wrong</span>');
      host.querySelector("#sp-table").innerHTML = `<thead><tr><th>Made</th><th>Middle said</th><th>Reality</th><th>In range</th><th>Chance higher</th><th>Direction</th></tr></thead><tbody>` +
        W.list.map((w, k) => `<tr data-k="${k}" tabindex="0" style="--c:var(--tfm)"><td>${esc(w.origin)}</td><td>${fmt.signedPct(w.said)}</td><td>${fmt.signedPct(w.did)}</td>
          <td class="${w.inside >= 0.7 ? "" : "neg"}">${Math.round(w.inside * 100)}%</td><td>${fmt.pct(w.pUp)}</td><td>${mark(w.called)}</td></tr>`).reverse().join("") + "</tbody>";
      const table = host.querySelector("#sp-table");
      const pick = (k, focus) => {
        state.k = Math.max(0, Math.min(W.list.length - 1, k)); draw();
        if (focus) { const tr = table.querySelector(`tr[data-k="${state.k}"]`); if (tr) { tr.focus(); tr.scrollIntoView({ block: "nearest" }); } }
      };
      table.onclick = (e) => { const tr = e.target.closest("tr[data-k]"); if (tr) pick(+tr.dataset.k); };
      table.onkeydown = (e) => {
        const tr = e.target.closest("tr[data-k]"); if (!tr) return;
        // Rows run newest first, so the row below is the older window.
        if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); pick(+tr.dataset.k + (e.key === "ArrowDown" ? -1 : 1), true); }
        else if (e.key === "Enter") pick(+tr.dataset.k);
      };
      host.querySelector("#sp-slider").oninput = (e) => pick(+e.target.value);
      draw();
      legend(host.querySelector("#sp-legend"), [{ name: "What really happened", color: "var(--ink)" }, { name: `${modelName}'s middle guess`, color: "var(--tfm)" },
        { name: "Its 80% range (chosen window)", color: "var(--tfm)", kind: "band" }, { name: "When it was made", color: "var(--ink-2)", kind: "dash" }]);
    }

    if (o) {
      // The newest sealed forecast (not due yet), or any earlier week's next to what really happened.
      const C = window.WPCompare, weeks = C ? C.batchesOf(D, model, [id]) : [];
      if (state.week === undefined || state.weekId !== id) { state.weekId = id; state.week = null; }
      const short = (d) => new Date(d + "T00:00:00Z").toLocaleString("en", { month: "short", day: "numeric", timeZone: "UTC" });
      const drawFan = () => {
        host.querySelector("#sp-weeks-row").hidden = !weeks.length;
        host.querySelector("#sp-weeks").innerHTML = weeks.length ? weeks.map((w) => `<button class="chip" data-k="${w}" aria-pressed="${w === state.week}">${short(w)}</button>`).join("") +
          `<button class="chip" data-k="new" aria-pressed="${!state.week}">Newest · not due yet</button>` : "";
        const verdict = host.querySelector("#sp-fan-verdict"), note = host.querySelector("#sp-fan-note"), pm = host.querySelector("#sp-fan-pm");
        if (state.week) {
          const B = C.sealedBatch(D, id, model, state.week), SB = C.sealedBatch(D, id, "seldon", state.week);
          const d0 = B.start ? B.start[0] : B.days[0].date, d1 = B.days[B.days.length - 1].date;
          const span = Math.max(7, (Date.parse(d1) - Date.parse(d0)) / 864e5), lead = new Date(Date.parse(d0) - span * 864e5).toISOString().slice(0, 10);
          const s0 = B.start ? [[B.start[0], B.start[1], B.start[1]]] : [];
          plot(host.querySelector("#sp-fan"), {
            x: "date", height: 260, left: 56, right: 16, label: `${title}: forecast sealed ${state.week} against what really happened`,
            bands: [{ points: s0.concat(B.days.map((d) => [d.date, d.lo, d.hi])) }],
            lines: [{ points: B.real.filter(([d]) => d >= lead && d <= d1), color: "var(--ink)", width: 2.2, name: "what really happened" },
              { points: (B.start ? [[B.start[0], B.start[1]]] : []).concat(B.days.map((d) => [d.date, d.mid])), color: "var(--tfm)", width: 1.8, dash: "6 5", name: `${modelName} middle` },
              ...(SB ? [{ points: (SB.start ? [[SB.start[0], SB.start[1]]] : []).concat(SB.days.map((d) => [d.date, d.mid])), color: "var(--seldon)", width: 1.6, dash: "2 4", name: "Seldon middle" }] : [])],
            dots: [{ points: B.days.filter((d) => d.inside).map((d) => [d.date, d.actual]), color: "var(--up)", r: 3.6, stroke: "var(--panel)", name: "inside its range" },
              { points: B.days.filter((d) => !d.inside).map((d) => [d.date, d.actual]), color: "var(--down)", r: 3.6, stroke: "var(--panel)", name: "outside its range" }],
            refs: B.start ? [{ x: B.start[0], label: "sealed" }] : [],
          });
          const box = host.querySelector("#sp-fan-legend"); box.innerHTML = "";
          legend(box, [{ name: "What really happened", color: "var(--ink)" }, { name: `${modelName} middle forecast`, color: "var(--tfm)", kind: "dash" }, { name: `${modelName} 80% range`, color: "var(--tfm)", kind: "band" },
            ...(SB ? [{ name: "Seldon middle forecast", color: "var(--seldon)", kind: "dash" }] : []), { name: "Inside the range", color: "var(--up)", kind: "dot" }, { name: "Outside it", color: "var(--down)", kind: "dot" }]);
          pm.textContent = `sealed ${state.week} · ${B.days.length} day${B.days.length === 1 ? "" : "s"} due so far`;
          verdict.innerHTML = `<b>${B.hits} of ${B.days.length}</b> due days landed inside ${esc(modelName)}'s 80% range.` +
            (B.said !== null ? ` By ${esc(d1)} its middle forecast said ${fmt.signedPct(B.said)}; it really went ${fmt.signedPct(B.did)}${B.called === null ? "." : B.called ? ", the same way." : ", the other way."}` : "") +
            (SB ? ` Seldon's range caught ${SB.hits} of ${SB.days.length}.` : "");
          note.textContent = "The solid line is the real value, before and after the sealing day; the dashed lines and shaded range were written down before those days arrived. Dots mark the due days: green inside the 80% range, red outside.";
        } else {
          const last = o.history[o.history.length - 1], S = o.seldon && o.seldon.fan && o.seldon.fan.length ? o.seldon : null;
          plot(host.querySelector("#sp-fan"), {
            x: "date", height: 260, left: 56, right: 64, label: `${title}: newest sealed forecast`,
            bands: [{ points: [[last[0], last[1], last[1]]].concat(o.fan.map((f) => [f[0], f[1], f[3]])) },
              ...(S ? [{ points: [[last[0], last[1], last[1]]].concat(S.fan.map((f) => [f[0], f[1], f[3]])), color: "transparent", stroke: "var(--seldon)", hatch: false, edge: "2 3" }] : [])],
            lines: [{ points: o.history.slice(-90), color: "var(--ink)", width: 1.6, name: "value" },
              { points: [[last[0], last[1]]].concat(o.fan.map((f) => [f[0], f[2]])), color: "var(--tfm)", width: 2, dash: "6 5", name: modelName, label: modelName },
              ...(S ? [{ points: [[last[0], last[1]]].concat(S.fan.map((f) => [f[0], f[2]])), color: "var(--seldon)", width: 2, dash: "2 4", name: "Seldon", label: "Seldon" }] : [])],
            refs: [{ x: last[0], label: "sealed" }],
          });
          const box = host.querySelector("#sp-fan-legend"); box.innerHTML = "";
          legend(box, [{ name: "What really happened (up to sealing)", color: "var(--ink)" }, { name: `${modelName} middle forecast`, color: "var(--tfm)", kind: "dash" }, { name: `${modelName} 80% range`, color: "var(--tfm)", kind: "band" },
            ...(S ? [{ name: "Seldon 80% range", color: "var(--seldon)", kind: "dash" }] : [])]);
          pm.textContent = `sealed ${o.made_on} · opens ${o.target_date}`;
          verdict.innerHTML = "";
          note.textContent = `A forecast, not a result: the middle guess is ${fmt.signedPct(o.change)} by ${o.target_date}, the 80% range ${fmt.signedPct(o.low)} to ${fmt.signedPct(o.high)}, and a ${fmt.pct(o.p_up)} chance it ends higher. Reality is judged when that day arrives${weeks.length ? "; pick an earlier week above to see how past forecasts did" : ""}.`;
        }
      };
      host.querySelector("#sp-weeks").onclick = (e) => { const b = e.target.closest("button"); if (!b) return; state.week = b.dataset.k === "new" ? null : b.dataset.k; drawFan(); };
      drawFan();
    }

    if (mine.length) {
      const both = seldonRows.length > 0;
      host.querySelector("#sp-opened").innerHTML = `<thead><tr>${both ? "<th>Model</th>" : ""}<th>Date</th><th>Sealed</th><th>80% range</th><th>Actual</th><th>Result</th></tr></thead><tbody>` +
        (both ? opened : mine).map((r) => {
          const inside = r[8] !== null && r[8] >= r[5] && r[8] <= r[7];
          const name = r[1] === "seldon" ? "Seldon" : modelName, c = r[1] === "seldon" ? "var(--seldon)" : "var(--tfm)";
          return `<tr>${both ? `<td style="color:${c}">${name}</td>` : ""}<td>${esc(r[3])}</td><td>${esc(r[2])}<small>${r[11] ? "before release †" : `${r[4]} step${r[4] === 1 ? "" : "s"} ahead`}</small></td>
            <td>${fmt.num(r[5])} to ${fmt.num(r[7])}</td><td>${fmt.num(r[8])}</td><td>${inside ? '<span class="pos">✓ in range</span>' : '<span class="neg">✗ outside</span>'}</td></tr>`;
        }).join("") + "</tbody>";
    }
  }

  window.WPSeries = { render, windowsOf };
})();
