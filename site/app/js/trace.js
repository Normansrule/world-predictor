// "Follow one result": one forecast, followed back through every pipeline stage to its source.
// Reads window.WP_DATA (this run's numbers) and window.WP_PIPELINE (the stage inventory generated
// from src/psychohistory/inventory.py). Every panel is drawn from one state object, so the
// pipeline, chart, caption, timeline and drawer always agree on the series, stage and record.
(function () {
  const STEPS = ["catalog", "fetch", "context", "model", "seldon", "seal", "score", "backtest", "publish"];
  const LIVE = ["catalog", "fetch", "context", "model", "seldon", "seal", "score", "publish"];
  const SOURCE = { gdelt: "the GDELT Project", yahoo: "Yahoo Finance", wikipedia: "Wikimedia pageviews", owid: "Our World in Data", composite: "its member series" };
  const STALE_DAYS = { daily: 3, "trading days": 4, yearly: 800 };
  const CHECKPOINT = { "timesfm-2.5": "google/timesfm-2.5-200m-pytorch" };
  const GLYPH = { done: "✓", partial: "◐", failed: "!", waiting: "…", unreached: "–" };
  const WORD = { done: "Done", partial: "Partly done", failed: "No output", waiting: "Waiting", unreached: "Not reached" };
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const $ = (id) => document.getElementById(id);
  const reduce = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

  const state = { id: null, step: 0, focus: null, pick: null, playing: false, speed: 1 };
  let D, P, pool, fmt, plot, legend, timer = null, wired = false;

  function render(data, arg) {
    D = data; P = window.WP_PIPELINE; ({ fmt, plot, legend } = window.WPCharts);
    if (!P) { $("view-trace").querySelector(".trace-grid").innerHTML = '<div class="empty">Pipeline inventory missing (app/data/pipeline.js).</div>'; return; }
    // Demo data covers a handful of example series; a real run is checked against the whole catalog.
    pool = D.meta.demo ? P.catalog.filter((c) => outlook(c.id) || result(c.id)) : P.catalog;
    const ids = pool.map((c) => c.id);
    const first = (D.outlook[0] && D.outlook[0].id) || ids[0];
    if (arg && ids.includes(arg) && arg !== state.id) { stop(); Object.assign(state, { id: arg, step: 0, pick: null, focus: null }); }
    if (!state.id) state.id = first;
    if (!wired) wire();
    $("trace-series").innerHTML = pool.map((c) => {
      const s = status(c.id);
      return `<option value="${c.id}"${c.id === state.id ? " selected" : ""}>${esc(title(c.id))}${s.seal === "done" ? "" : " · no forecast this run"}</option>`;
    }).join("");
    $("tp-scrub").max = STEPS.length - 1;
    draw();
    coverage();
  }

  // ---------- what this run produced for one series ----------
  const spec = (id) => P.catalog.find((c) => c.id === id);
  const outlook = (id) => D.outlook.find((o) => o.id === id);
  const result = (id) => D.series.find((s) => s.id === id);
  const title = (id) => (outlook(id) || result(id) || {}).title || spec(id).description;
  function reason(id, stage) {
    const st = (D.run && D.run.stages) || {};
    for (const k of stage ? [stage] : ["fetch", "predict", "backtest"]) if (st[k] && st[k].skipped && st[k].skipped[id]) return st[k].skipped[id];
    return null;
  }
  function status(id) {
    const o = outlook(id), s = result(id), opened = (D.vault || []).length > 0;
    const live = o ? "done" : "unreached";
    return {
      catalog: "done",
      fetch: o ? "done" : s ? "partial" : "failed",
      context: live, model: live, seldon: o ? (o.seldon ? "done" : "partial") : "unreached",
      seal: o ? "done" : s ? "failed" : "unreached",
      score: o ? (opened ? "partial" : "waiting") : "unreached",
      backtest: s ? "done" : "failed",
      publish: o || s ? "done" : "unreached",
    };
  }
  function freshness(id) {
    const o = outlook(id); if (!o) return ["Unavailable", "warn"];
    const last = Date.parse(o.history[o.history.length - 1][0]), run = Date.parse(o.made_on.slice(0, 10)) || Date.parse(D.meta.generated);
    if (!isFinite(run)) return ["Unknown", "muted"];
    const days = (run - last) / 864e5, limit = STALE_DAYS[spec(id).freq] || 7;
    return days > limit ? [`Stale (${Math.round(days)} days old)`, "warn"] : ["Current", "ok"];
  }
  const commit = () => (P.commit && !P.commit.startsWith("__") ? P.commit : "main");
  const codeUrl = (c) => `${P.repo}/blob/${commit()}/${c.path}${c.line ? "#L" + c.line : ""}`;
  const testUrl = (t) => `${P.repo}/blob/${commit()}/tests/test_pipeline.py${t.line ? "#L" + t.line : ""}`;
  const signed = (v) => fmt.signedPct(v);

  // ---------- one render of every panel from the state ----------
  function draw() {
    const id = state.id, c = spec(id), o = outlook(id), st = status(id), stage = STEPS[state.step];
    $("trace-title").textContent = title(id);
    $("tp-scrub").value = state.step;
    $("tp-scrub").setAttribute("aria-valuetext", `Stage ${state.step + 1} of ${STEPS.length}: ${stageInfo(stage).name}`);
    $("tp-play").innerHTML = state.playing ? WPCharts.icon("pause") + "Pause" : WPCharts.icon("play") + "Play";
    $("tp-play").setAttribute("aria-label", state.playing ? "Pause" : "Play");
    flags(id);
    times(id);
    pipe(id, st);
    chart(id, c, o);
    $("trace-caption").innerHTML = `<b>${state.step + 1}/${STEPS.length} · ${esc(stageInfo(stage).name)}.</b> ${caption(stage, id)}`;
    drawer(id);
  }

  const stageInfo = (sid) => P.stages.find((s) => s.id === sid);

  function flags(id) {
    const demo = D.meta.demo, stage = STEPS[state.step];
    const picked = state.pick, future = picked ? picked.kind === "forecast" : ["model", "seldon", "seal", "score", "publish"].includes(stage);
    const [fresh, freshCls] = freshness(id);
    const run = D.run && D.run.run_id ? ` #${esc(D.run.run_id)}` : "";
    const mode = demo ? '<span class="flag warn" title="Made-up series and simple models">Demo · synthetic data</span>'
      : `<span class="flag ok" title="Numbers from a real forecast run, saved to the repository">Recorded run${run}</span>`;
    if (!outlook(id)) {
      $("trace-flags").innerHTML = mode + '<span class="flag warn">No forecast for this series in this run</span>';
      return;
    }
    $("trace-flags").innerHTML = [
      mode,
      `<span class="flag" title="Where this value comes from">Origin: ${demo ? "synthetic" : future ? "derived by the model" : "observed"}</span>`,
      `<span class="flag${future ? " forecast" : ""}" title="How to read it">${future ? "Forecast, not a fact" : "Measured value"}</span>`,
      `<span class="flag ${freshCls}" title="Newest input compared with the forecast date">Input: ${fresh}</span>`,
    ].join("");
  }

  function times(id) {
    const o = outlook(id), c = spec(id);
    const last = o ? o.history[o.history.length - 1][0] : "–";
    const rows = [
      ["Newest observation", last],
      ["Forecast sealed", o ? o.made_on : "–"],
      ["Horizon", o ? `${o.target_date} · ${c.horizon} ${c.freq === "trading days" ? "trading days" : c.freq === "yearly" ? "years" : "days"}` : "–"],
      ["Published", D.meta.generated],
      ["Collected", "weekly (Mondays)"],
    ];
    $("trace-times").innerHTML = rows.map(([k, v]) => `<div><dt>${k}</dt><dd>${esc(v)}</dd></div>`).join("");
  }

  // ---------- pipeline explorer ----------
  function pipe(id, st) {
    const box = $("trace-pipe");
    const w = 340, nh = 46, gap = 16, mainW = 208, row = nh + gap;
    const pos = {}; LIVE.forEach((sid, i) => (pos[sid] = { x: 4, y: 4 + i * row, w: mainW }));
    pos.backtest = { x: mainW + 26, y: 4 + 2 * row, w: w - mainW - 30 };
    const H = 4 + LIVE.length * row;
    const activeIdx = state.step, active = state.focus || STEPS[activeIdx];
    const reached = new Set(STEPS.slice(0, activeIdx + 1));
    const edge = ([a, b]) => {
      const A = pos[a], B = pos[b];
      let d;
      if (a === "fetch" && b === "backtest") d = `M${A.x + A.w},${A.y + nh / 2} H${B.x + B.w / 2} V${B.y}`;
      else if (a === "backtest") d = `M${A.x + A.w / 2},${A.y + nh} V${B.y + nh / 2} H${B.x + B.w}`;
      else d = `M${A.x + 40},${A.y + nh} V${B.y}`;
      const on = reached.has(b) && reached.has(a), flowing = on && b === STEPS[activeIdx] && !reduce();
      return `<path class="edge${on ? " on" : ""}${flowing ? " flowing" : ""}" d="${d}" marker-end="url(#tp-arrow)"/>`;
    };
    const node = (sid) => {
      const p = pos[sid], s = stageInfo(sid), stt = st[sid], file = s.code[0].path.split("/").pop();
      const cls = ["node", sid, stt, reached.has(sid) ? "reached" : "", sid === active ? "active" : ""].join(" ");
      return `<g class="${cls}" data-stage="${sid}" tabindex="0" role="button" aria-label="${esc(s.name)}: ${WORD[stt]}" transform="translate(${p.x} ${p.y})">
        <rect width="${p.w}" height="${nh}" rx="3"/>${stt === "failed" ? `<rect class="hatch-fill" width="${p.w}" height="${nh}" rx="3"/>` : ""}
        <text class="n" x="12" y="20">${esc(s.name)}</text><text class="f" x="12" y="36">${esc(sid === "backtest" ? "backtest.py" : file)}</text>
        <text class="g" x="${p.w - 12}" y="28" text-anchor="end">${GLYPH[stt]}</text></g>`;
    };
    box.innerHTML = `<svg viewBox="0 0 ${w} ${H}" role="group" aria-label="Pipeline stages">
      <defs><marker id="tp-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z"/></marker>
      <pattern id="tp-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="6"/></pattern></defs>
      ${P.edges.map(edge).join("")}${STEPS.map(node).join("")}</svg>
      <div class="pipe-key"><span class="k done">✓ done</span><span class="k waiting">… waiting</span><span class="k failed">! no output</span><span class="k unreached">– not reached</span></div>`;
  }

  // ---------- chart ----------
  function chart(id, c, o) {
    const box = $("trace-chart"), stage = STEPS[state.step], at = (sid) => state.step >= STEPS.indexOf(sid);
    $("trace-legend").innerHTML = "";
    if (!o) {
      const r = reason(id), s = status(id);
      box.classList.remove("chart"); box.removeAttribute("data-drawn");
      box.innerHTML = `<div class="failure"><b>No forecast reached the chart for this series in this run.</b>
        <p>It stopped at <b>${s.fetch === "failed" ? "Fetch and cache" : "Seal the forecast"}</b>${r ? `: ${esc(r)}` : "."}</p>
        ${s.backtest === "done" ? "<p>Its backtest did run, so its past record is still in the drawer below.</p>" : ""}
        <p class="caption">${D.run && D.run.recorded ? esc(D.run.recorded) : "The next weekly run tries every series again."}</p></div>`;
      return;
    }
    if (stage === "catalog") {
      box.classList.remove("chart"); box.removeAttribute("data-drawn");
      box.innerHTML = `<div class="spec-card"><div class="mono">catalog.py · ${esc(c.id)}</div><dl>
        <dt>What</dt><dd>${esc(c.description)}</dd><dt>Source</dt><dd>${esc(SOURCE[c.source])}</dd>
        <dt>Asks for</dt><dd class="mono">${esc(JSON.stringify(c.params))}</dd><dt>Steps</dt><dd>${esc(c.freq)}</dd>
        <dt>Forecasts</dt><dd>${c.horizon} steps ahead</dd><dt>Scale</dt><dd>${esc(c.scale)}</dd></dl></div>`;
      return;
    }
    const hist = o.history, last = hist[hist.length - 1];
    const fan = o.fan;
    const spec2 = {
      x: "date", height: 340, left: 56, label: `${o.title}: the stages so far`,
      xDomain: [hist[0][0], fan[fan.length - 1][0]],
      yDomain: pad(hist.map((p) => p[1]).concat(fan.flatMap((f) => [f[1], f[3]]))),
      lines: [{ points: hist, color: "var(--observed)", width: 2, name: "observed" }],
      dots: [], bands: [], refs: [], spans: [], marks: [],
      onPick: (p) => pick(p),
    };
    if (at("context")) spec2.spans.push({ from: hist[0][0], to: last[0], label: "context (latest part)" });
    if (at("model")) {
      spec2.refs.push({ x: last[0], label: at("seal") ? "sealed" : "now" });
      spec2.bands.push({ points: fan.map((f) => [f[0], f[1], f[3]]) });
      spec2.lines.push({ points: [[last[0], last[1]]].concat(fan.map((f) => [f[0], f[2]])), color: "var(--tfm)", width: 2.2, name: "forecast" });
    }
    const S = o.seldon && o.seldon.fan && o.seldon.fan.length ? o.seldon : null;
    if (at("seldon") && S) {
      spec2.bands.push({ points: S.fan.map((f) => [f[0], f[1], f[3]]), color: "transparent", stroke: "var(--seldon)", hatch: false, edge: "2 3" });
      spec2.lines.push({ points: [[last[0], last[1]]].concat(S.fan.map((f) => [f[0], f[2]])), color: "var(--seldon)", width: 2, name: "seldon" });
    }
    if (at("score")) spec2.refs.push({ x: o.target_date, label: "opens", color: "var(--warn)" });
    if (state.pick) spec2.marks.push({ x: state.pick.x, y: state.pick.y, color: state.pick.kind === "forecast" ? "var(--forecast)" : "var(--text)" });
    else if (stage === "fetch") spec2.marks.push({ x: Date.parse(last[0]), y: last[1] });
    box.classList.add("chart");
    plot(box, spec2);
    const items = [{ name: "Observed", color: "var(--ink)" }];
    if (at("model")) items.push({ name: "TimesFM 80% range (hatched: the future)", color: "var(--tfm)", kind: "band" }, { name: "TimesFM middle guess", color: "var(--tfm)" });
    if (at("seldon") && S) items.push({ name: "Seldon 80% range", color: "var(--seldon)", kind: "dash" });
    legend($("trace-legend"), items);
  }
  function pad(values) {
    const v = values.filter((x) => x !== null && isFinite(x)); const lo = Math.min(...v), hi = Math.max(...v), p = (hi - lo || 1) * 0.06;
    return [lo - p, hi + p];
  }

  function pick(p) {
    const o = outlook(state.id); if (!o) return;
    const date = new Date(p.x).toISOString().slice(0, 10);
    const kind = p.name === "forecast" ? "forecast" : "observed";
    const row = kind === "forecast" ? o.fan.find((f) => f[0] === date) : o.history.find((h) => h[0] === date);
    state.pick = { x: p.x, y: p.y, kind, date, row };
    state.focus = kind === "forecast" ? "seal" : "fetch";
    state.step = Math.max(state.step, STEPS.indexOf(state.focus));
    stop(); draw();
  }

  // ---------- captions and drawer ----------
  function caption(stage, id) {
    const c = spec(id), o = outlook(id), s = result(id), st = status(id)[stage], ev = (D.evidence || {})[id] || [];
    if (st === "failed") return `No output here in this run${reason(id) ? ": " + esc(reason(id)) : "."}`;
    if (st === "unreached") return "Not reached in this run, because an earlier stage had no output for this series.";
    const last = o && o.history[o.history.length - 1];
    switch (stage) {
      case "catalog": return `Catalog entry <code>${esc(c.id)}</code>: ${esc(c.description)}, from ${esc(SOURCE[c.source])}, ${esc(c.freq)}, forecast ${c.horizon} steps ahead.`;
      case "fetch": return o ? `Fetched from ${esc(SOURCE[c.source])}. Newest value ${fmt.num(last[1])} on ${esc(last[0])}; the chart shows the last ${o.history.length} values.`
        : "Loaded for the backtest, but not when the forecast was made.";
      case "context": return `The model may read up to 1,024 past values and nothing after ${esc(last[0])}. The shaded stretch is the most recent part of what it read.`;
      case "model": return `${esc(D.meta.model)}${CHECKPOINT[D.meta.model] ? ` (${esc(CHECKPOINT[D.meta.model])})` : ""} turns that history into a range for each of the next ${c.horizon} steps. Only what went in and came out is shown, not its inner workings.`;
      case "seldon": {
        if (!o.seldon) return "No Seldon correction in this run.";
        const k = o.seldon.learned;
        return k.windows < 2 ? `Seldon had ${k.windows} finished window${k.windows === 1 ? "" : "s"} to learn from, too few to correct anything, so its forecast is TimesFM's.`
          : `Seldon read ${k.windows} finished backtest windows: it keeps ${Math.round(k.shrink * 100)}% of TimesFM's predicted move and scales the range ${k.spread.toFixed(2)}× (dotted).`
            + (o.seldon.source === "derived" ? " This run's Seldon range is derived from the sealed TimesFM range." : "");
      }
      case "seal": return `Sealed on ${esc(o.made_on)}: middle guess ${signed(o.change)} by ${esc(o.target_date)}, 80% range ${signed(o.low)} to ${signed(o.high)}, ${fmt.pct(o.p_up)} chance it ends higher.`;
      case "score": return (D.vault || []).length ? `Its steps open from ${esc(o.fan[0][0])} to ${esc(o.target_date)}; opened forecasts so far are in the Time Vault.`
        : `Not scored yet: the first step opens on ${esc(o.fan[0][0])} and the last on ${esc(o.target_date)}. Until then there is no evidence either way.`;
      case "backtest": {
        if (!s) return "No backtest for this series in this run.";
        const flat = Math.abs(s.skill) < 0.02;
        return `In ${ev.length} past windows it had ${flat ? "about the same error as" : (s.skill > 0 ? signed(s.skill) + " less error than" : signed(-s.skill) + " more error than")} the simple guess, and reality landed inside its 80% range ${fmt.pct(s.coverage80)} of the time.`;
      }
      case "publish": return `Published in app/data/data.js on ${esc(D.meta.generated)}. Every number on this page comes from that file.`;
    }
    return "";
  }

  function example(stage, id) {
    const c = spec(id), o = outlook(id), s = result(id), ev = (D.evidence || {})[id] || [];
    const kv = (rows) => "<dl class=\"kv\">" + rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("") + "</dl>";
    const src = c.url ? `<a href="${esc(c.url)}" rel="noopener">Open the public source</a>` : "Built from its member series.";
    switch (stage) {
      case "catalog": return kv([["id", `<code>${esc(c.id)}</code>`], ["source", esc(c.source)], ["params", `<code>${esc(JSON.stringify(c.params))}</code>`], ["steps", esc(c.freq)], ["horizon", c.horizon], ["scale", esc(c.scale)]]);
      case "fetch": return o ? `<table class="mini-t"><tr><th>date</th><th>value</th></tr>${o.history.slice(-3).map((h) => `<tr><td>${h[0]}</td><td>${fmt.num(h[1])}</td></tr>`).join("")}</table><p>${src}</p>`
        : `<p>${esc(reason(id, "predict") || reason(id) || "No values loaded.")}</p><p>${src}</p>`;
      case "context": return o ? kv([["values drawn", o.history.length], ["newest", esc(o.history[o.history.length - 1][0])], ["model may read", "up to 1,024"]]) : "";
      case "model": return kv([["model", esc(D.meta.model)], ["weights", esc(CHECKPOINT[D.meta.model] || "a simple baseline (demo)")], ["output", "middle path + 9 deciles per step"]]);
      case "seal": {
        if (!o) return "";
        const f0 = o.fan[0], fN = o.fan[o.fan.length - 1];
        return `<table class="mini-t"><tr><th>target</th><th>10%</th><th>middle</th><th>90%</th></tr>${[f0, fN].map((f) => `<tr><td>${f[0]}</td><td>${fmt.num(f[1])}</td><td>${fmt.num(f[2])}</td><td>${fmt.num(f[3])}</td></tr>`).join("")}</table>`
          + kv([["sealed", esc(o.made_on)], ["chance higher", fmt.pct(o.p_up)]]);
      }
      case "seldon": {
        if (!o || !o.seldon) return "";
        const k = o.seldon.learned, e = o.seldon.fan[o.seldon.fan.length - 1];
        return kv([["windows learned from", k.windows], ["share of the move kept", Math.round(k.shrink * 100) + "%"], ["range scale", k.spread.toFixed(2) + "×"],
          ["last step", `${fmt.num(e[1])} / ${fmt.num(e[2])} / ${fmt.num(e[3])}`], ["in the ledger", o.seldon.source === "sealed" ? "sealed as model seldon" : "derived for this run"]]);
      }
      case "score": return o ? kv([["first step opens", esc(o.fan[0][0])], ["last step opens", esc(o.target_date)], ["opened so far", (D.vault || []).length ? "see the Time Vault" : "none yet"]]) : "";
      case "backtest": return s ? kv([["windows", ev.length], ["skill vs simple guess", fmt.pct(s.skill)], ["inside 80% range", fmt.pct(s.coverage80)], ["right direction", fmt.pct(s.direction)], ["odds score (Brier)", s.brier === null ? "–" : s.brier.toFixed(3)]]) + '<div id="trace-evidence"></div>' : "";
      case "publish": return kv([["file", "app/data/data.js"], ["generated", esc(D.meta.generated)], ["model", esc(D.meta.model)], ["code version", `<a href="${P.repo}/tree/${commit()}">${esc(commit().slice(0, 7))}</a>`]]);
    }
    return "";
  }

  function drawer(id) {
    const sid = state.focus || STEPS[state.step], s = stageInfo(sid), st = status(id)[sid];
    let html = `<div class="drawer-head"><h2>${esc(s.name)}</h2><span class="flag ${st === "done" ? "ok" : st === "failed" ? "warn" : ""}">${WORD[st]}</span><span class="flag">Implemented</span></div>
      <p class="plain-line">${esc(s.plain)}</p>`;
    if (state.pick && state.pick.row) {
      const p = state.pick, r = p.row, c = spec(id);
      html += `<div class="record ${p.kind}"><h3>Selected record</h3>` + (p.kind === "forecast"
        ? `<dl class="kv"><dt>target date</dt><dd>${r[0]}</dd><dt>10% / middle / 90%</dt><dd>${fmt.num(r[1])} / ${fmt.num(r[2])} / ${fmt.num(r[3])}</dd><dt>origin</dt><dd>derived by ${esc(D.meta.model)}</dd><dt>reading</dt><dd>a forecast, not a fact</dd></dl>`
        : `<dl class="kv"><dt>date</dt><dd>${r[0]}</dd><dt>value</dt><dd>${fmt.num(r[1])}</dd><dt>origin</dt><dd>${D.meta.demo ? "synthetic (demo)" : "observed, from " + esc(SOURCE[c.source])}</dd></dl>${c.url ? `<a href="${esc(c.url)}" rel="noopener">Check it at the source</a>` : ""}`)
        + `<button class="btn small" id="tp-unpick">Clear selection</button></div>`;
    }
    const mine = st === "unreached" ? "<p>Nothing for this series at this stage in this run.</p>" : st === "failed" ? `<p>${esc(reason(id) || "No output in this run.")}</p>` : example(sid, id);
    html += `<div class="drawer-grid"><div><h3>This result</h3>${mine}</div><div><h3>How it works</h3><dl class="kv">
      <dt>Takes</dt><dd>${esc(s.input)}</dd><dt>Gives</dt><dd>${esc(s.output)}</dd><dt>Rule</dt><dd>${esc(s.rule)}</dd>
      <dt>When</dt><dd>${esc(s.cadence)}</dd><dt>If it fails</dt><dd>${esc(s.failure)}</dd><dt>Runs in</dt><dd>${esc(s.runs)}</dd></dl></div>
      <div><h3>Code</h3><ul class="links">${s.code.map((c) => `<li><a href="${codeUrl(c)}" rel="noopener"><code>${esc(c.path)}</code>${c.symbol ? " · " + esc(c.symbol) : ""}</a></li>`).join("")}</ul>
      <h3>Tests</h3><ul class="links">${s.tests.map((t) => `<li><a href="${testUrl(t)}" rel="noopener"><code>${esc(t.name)}</code></a></li>`).join("")}</ul></div></div>`;
    $("trace-drawer").innerHTML = html;
    const un = $("tp-unpick"); if (un) un.onclick = () => { state.pick = null; state.focus = null; draw(); };
    const evBox = $("trace-evidence"), ev = (D.evidence || {})[id];
    if (evBox && ev && ev.length) {
      plot(evBox, { x: "date", height: 150, left: 40, yDomain: [0, 1], yFormat: fmt.pct, label: "Inside the 80% range, per backtest window",
        dots: [{ points: ev.map((w) => [w[0], w[2]]), color: "var(--accent)", r: 4, name: "inside 80%" }], refs: [{ y: 0.8, label: "target 80%" }] });
      evBox.insertAdjacentHTML("beforeend", '<p class="caption">Each dot is one past window: the share of days reality fell inside the 80% range.</p>');
    }
  }

  // ---------- coverage of the whole run (the failure state) ----------
  function coverage() {
    const cols = [["fetch", "Fetched"], ["backtest", "Backtested"], ["seal", "Sealed"], ["score", "Scored"], ["publish", "Shown"]];
    const rows = pool.map((c) => [c, status(c.id)]);
    const sealed = rows.filter(([, s]) => s.seal === "done").length;
    $("cover-note").textContent = `${D.meta.demo ? "Demo data: " : ""}${sealed} of ${rows.length} series have a sealed forecast from this run. Gaps are shown as gaps, with the reason when the run recorded one; nothing is filled in.`;
    $("cover-table").innerHTML = "<thead><tr><th>Series</th><th>Area</th>" + cols.map(([, l]) => `<th>${l}</th>`).join("") + "</tr></thead><tbody>" +
      rows.map(([c, s]) => `<tr data-id="${c.id}" tabindex="0"${c.id === state.id ? ' class="current"' : ""}><td>${esc(title(c.id))}</td><td>${esc(c.domain)}</td>` +
        cols.map(([k]) => `<td class="cell ${s[k]}" title="${esc(s[k] === "failed" ? reason(c.id) || WORD[s[k]] : WORD[s[k]])}">${GLYPH[s[k]]} ${WORD[s[k]]}</td>`).join("") + "</tr>").join("") + "</tbody>";
  }

  // ---------- playback ----------
  function go(step) { state.step = Math.max(0, Math.min(STEPS.length - 1, step)); state.focus = null; draw(); }
  function stop() { clearTimeout(timer); timer = null; state.playing = false; }
  function tick() {
    if (state.step >= STEPS.length - 1) { stop(); draw(); return; }
    go(state.step + 1);
    timer = setTimeout(tick, 2400 / state.speed);
  }
  function play() {
    if (state.playing) { stop(); draw(); return; }
    state.playing = true; state.pick = null;
    if (state.step >= STEPS.length - 1) state.step = 0;
    draw(); timer = setTimeout(tick, 2400 / state.speed);
  }
  function select(id) { stop(); state.id = id; state.step = 0; state.pick = null; state.focus = null; history.replaceState(null, "", "#trace/" + id); draw(); coverage(); }

  function wire() {
    wired = true;
    $("tp-play").onclick = play;
    $("tp-back").onclick = () => { stop(); go(state.step - 1); };
    $("tp-next").onclick = () => { stop(); go(state.step + 1); };
    $("tp-restart").onclick = () => { stop(); state.pick = null; go(0); };
    $("tp-scrub").oninput = (e) => { stop(); go(+e.target.value); };
    $("tp-speed").onchange = (e) => { state.speed = +e.target.value; if (state.playing) { clearTimeout(timer); timer = setTimeout(tick, 2400 / state.speed); } };
    $("trace-series").onchange = (e) => select(e.target.value);
    const nodeAct = (e) => {
      const g = e.target.closest && e.target.closest("[data-stage]"); if (!g) return;
      stop(); state.step = STEPS.indexOf(g.dataset.stage); state.focus = g.dataset.stage; draw();
      const again = document.querySelector(`#trace-pipe [data-stage="${g.dataset.stage}"]`); if (again && e.type === "keydown") again.focus();
    };
    $("trace-pipe").addEventListener("click", nodeAct);
    $("trace-pipe").addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); nodeAct(e); } });
    const rowAct = (e) => { const tr = e.target.closest && e.target.closest("tr[data-id]"); if (tr) { select(tr.dataset.id); $("trace-series").value = tr.dataset.id; window.scrollTo({ top: 0, behavior: reduce() ? "auto" : "smooth" }); } };
    $("cover-table").addEventListener("click", rowAct);
    $("cover-table").addEventListener("keydown", (e) => { if (e.key === "Enter") rowAct(e); });
    document.addEventListener("keydown", (e) => {
      if (!$("view-trace").classList.contains("active") || /INPUT|SELECT|TEXTAREA|BUTTON/.test(e.target.tagName) || e.target.closest("[data-stage],tr[data-id]")) return;
      if (e.key === " ") { e.preventDefault(); play(); }
      else if (e.key === "ArrowRight") { stop(); go(state.step + 1); }
      else if (e.key === "ArrowLeft") { stop(); go(state.step - 1); }
      else if (e.key === "Home") { stop(); go(0); }
    });
  }

  window.WPTrace = { render, stop };
})();
