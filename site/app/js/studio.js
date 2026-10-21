// Forecast Studio: ask TimesFM and Seldon about any level on any date of their newest sealed forecast,
// then seal your own call beside theirs. Your calls are kept in this browser and scored against both
// models as soon as a later data file contains the real value for that date.
(function () {
  const STORE = "wp-calls-v1";
  const HOLD_MS = 480;
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const DAY = 864e5;

  // The chance of ending above x, read off the 10th, 50th and 90th percentiles by linear interpolation.
  // Beyond them the forecast says nothing precise, so the tails are capped at 5% and 95%
  // (the same rule as psychohistory.metrics.prob_above).
  function pAbove(q10, q50, q90, x) {
    let cdf;
    if (x <= q10) cdf = 0.05;
    else if (x >= q90) cdf = 0.95;
    else if (x <= q50) cdf = 0.1 + 0.4 * (x - q10) / Math.max(1e-12, q50 - q10);
    else cdf = 0.5 + 0.4 * (x - q50) / Math.max(1e-12, q90 - q50);
    return 1 - cdf;
  }

  function load() { try { return JSON.parse(localStorage.getItem(STORE)) || []; } catch (e) { return []; } }
  function save(calls) { try { localStorage.setItem(STORE, JSON.stringify(calls)); return true; } catch (e) { return false; } }

  // A fingerprint of the call as sealed, so an edited export no longer matches.
  async function fingerprint(text) {
    try {
      const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
      return [...new Uint8Array(buf)].slice(0, 6).map((b) => b.toString(16).padStart(2, "0")).join("");
    } catch (e) {  // no Web Crypto (an old browser, or plain http): a simple checksum instead
      let h = 0x811c9dc5;
      for (let i = 0; i < text.length; i++) { h ^= text.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; }
      return h.toString(16).padStart(8, "0");
    }
  }

  // The real value on the call's date (or the first one after it, for weekends and holidays).
  function outcome(call, D) {
    const o = D.outlook.find((x) => x.id === call.series);
    const hist = o ? o.history : [];
    const hit = hist.find((p) => p[0] >= call.date);
    if (!hit) return null;
    const actual = hit[1], err = (v) => Math.abs(v - actual);
    const inside = (r) => actual >= r[0] && actual <= r[2];
    const you = [call.lo, call.value, call.hi];
    const rows = [["You", err(call.value), inside(you)], ["TimesFM", err(call.tfm[1]), inside(call.tfm)]];
    if (call.seldon) rows.push(["Seldon", err(call.seldon[1]), inside(call.seldon)]);
    const best = rows.reduce((a, b) => (b[1] < a[1] ? b : a));
    return { actual, on: hit[0], rows, best: best[0] };
  }

  function render(host, D, opts = {}) {
    const { plot, legend, fmt } = window.WPCharts;
    const items = (D.outlook || []).filter((o) => o.fan && o.fan.length);
    const modelName = /^timesfm/.test(D.meta.model) ? "TimesFM" : D.meta.model;
    if (!items.length) {
      host.innerHTML = '<div class="card"><div class="empty"><b>Nothing sealed yet.</b>The studio opens after the first run of <code>psychohistory predict</code>.</div></div>';
      return;
    }
    const st = render.st || (render.st = { id: items[0].id, step: null, level: null, you: null, width: null });
    if (opts.start && items.some((o) => o.id === opts.start)) { st.id = opts.start; st.step = st.level = st.you = st.width = null; }

    host.innerHTML = `
      <div class="card studio-bar">
        <label class="field"><span>Series</span><select id="st-series">${items.map((o) => `<option value="${esc(o.id)}">${esc(o.title)}</option>`).join("")}</select></label>
        <label class="field grow"><span>Date <b id="st-date"></b></span><input id="st-step" type="range" min="0" step="1"></label>
        <label class="field"><span>Level <small id="st-rel"></small></span><input id="st-level" type="number" inputmode="decimal" step="any"></label>
        <div class="chips" id="st-presets" role="group" aria-label="Level presets"></div>
      </div>
      <div class="studio-grid">
        <div class="card">
          <header class="ph"><h2 id="st-title"></h2><span class="pm" id="st-meta"></span></header>
          <div id="st-chart"></div><div id="st-legend"></div>
          <p class="note" id="st-hint">Click the chart to ask about that date and level. The models' ranges hold 80% of what they expect.</p>
        </div>
        <div class="studio-side">
          <div class="card odds-card" aria-live="polite">
            <header class="ph"><h2>The odds</h2><span class="pm" id="st-odds-meta"></span></header>
            <div id="st-odds"></div>
          </div>
          <div class="card">
            <header class="ph"><h2>Percentiles</h2><button class="pm linkish" id="st-csv" type="button">Download CSV</button></header>
            <div class="table-wrap"><table class="ladder" id="st-ladder"></table></div>
          </div>
        </div>
      </div>
      <div class="card seal-card">
        <header class="ph"><h2>Seal your own call</h2><span class="pm">kept in this browser, scored when the date arrives</span></header>
        <div class="seal-row">
          <label class="field"><span>Your value</span><input id="st-you" type="number" inputmode="decimal" step="any"></label>
          <label class="field grow"><span>Your 80% range <b id="st-width-out"></b></span><input id="st-width" type="range" min="0.25" max="25" step="0.25"></label>
          <dl class="vs" id="st-vs"></dl>
          <button class="seal-btn" id="st-seal" type="button" aria-describedby="st-seal-why">
            <svg class="ring" viewBox="0 0 24 24" aria-hidden="true"><circle class="track" cx="12" cy="12" r="10" pathLength="1"/><circle class="fill" cx="12" cy="12" r="10" pathLength="1"/></svg>
            Hold to seal</button>
          <span id="st-seal-why" class="sr">Press and hold, or hold the space bar, so a call is never sealed by accident.</span>
        </div>
      </div>
      <div class="card">
        <header class="ph"><h2>Your sealed calls</h2><span class="pm"><button class="linkish" id="st-export" type="button">Export</button> · <button class="linkish" id="st-clear" type="button">Clear</button></span></header>
        <div class="table-wrap"><table class="calls" id="st-calls"></table></div>
      </div>`;
    const $ = (id) => host.querySelector("#" + id);

    const cur = () => items.find((o) => o.id === st.id) || items[0];
    function setSeries(id) {
      st.id = id; const o = cur(), last = o.history[o.history.length - 1][1];
      st.step = o.fan.length - 1; st.level = round(last, last); st.you = null; st.width = null;
    }
    if (st.step === null) setSeries(st.id);

    $("st-series").value = st.id;
    $("st-series").onchange = (e) => { setSeries(e.target.value); paint(); };
    $("st-step").oninput = (e) => { st.step = +e.target.value; paint(); };
    $("st-level").oninput = (e) => { const v = parseFloat(e.target.value); if (isFinite(v)) { st.level = v; paint(false); } };
    $("st-you").oninput = (e) => { const v = parseFloat(e.target.value); if (isFinite(v)) { st.you = v; paint(false); } };
    $("st-width").oninput = (e) => { st.width = +e.target.value / 100; paint(false); };
    $("st-presets").onclick = (e) => {
      const b = e.target.closest("button"); if (!b) return;
      const o = cur(), last = o.history[o.history.length - 1][1];
      st.level = round(last * (1 + +b.dataset.k), last); paint();
    };
    $("st-csv").onclick = () => download(`${st.id}-forecast.csv`, csv(cur()), "text/csv");
    $("st-export").onclick = () => download("world-predictor-calls.json", JSON.stringify(load(), null, 1), "application/json");
    $("st-clear").onclick = () => {
      if (!load().length || !confirm("Remove every call sealed in this browser? Export them first if you want a copy.")) return;
      save([]); paintCalls();
    };
    holdable($("st-seal"), sealCall);

    function round(v, scale) { const a = Math.abs(scale); const d = a >= 1000 ? 0 : a >= 10 ? 1 : a >= 1 ? 2 : 4; return +v.toFixed(d); }

    function paint(redrawChart = true) {
      const o = cur(), last = o.history[o.history.length - 1][1], f = o.fan[st.step];
      const S = o.seldon && o.seldon.fan && o.seldon.fan.length ? o.seldon.fan[st.step] : null;
      if (st.you === null) st.you = round(f[2], last);
      if (st.width === null) st.width = Math.max(0.0025, Math.round(((f[3] - f[1]) / 2 / last) * 400) / 400);
      const lvl = st.level, rel = lvl / last - 1;

      $("st-step").max = o.fan.length - 1; $("st-step").value = st.step;
      $("st-step").setAttribute("aria-valuetext", `${f[0]}, step ${st.step + 1} of ${o.fan.length}`);
      $("st-date").textContent = `${f[0]} · step ${st.step + 1}/${o.fan.length}`;
      if (document.activeElement !== $("st-level")) $("st-level").value = lvl;
      $("st-rel").textContent = `${fmt.signedPct(rel)} from ${fmt.num(last)}`;
      $("st-presets").innerHTML = [[-0.05, "−5%"], [-0.02, "−2%"], [0, "Last value"], [0.02, "+2%"], [0.05, "+5%"]]
        .map(([k, l]) => `<button class="chip" data-k="${k}" aria-pressed="${Math.abs(rel - k) < 1e-4}">${l}</button>`).join("");
      $("st-title").textContent = o.title;
      $("st-meta").textContent = `sealed ${o.made_on} · last value ${fmt.num(last)}`;

      // The odds at this date and level.
      const pT = pAbove(f[1], f[2], f[3], lvl), pS = S ? pAbove(S[1], S[2], S[3], lvl) : null;
      $("st-odds-meta").textContent = f[0];
      const meter = (p, c, who) => `<div class="meter"><span class="who" style="--c:${c}">${who}</span><b>${fmt.pct(p)}</b>
        <span class="track" aria-hidden="true"><i style="width:${(p * 100).toFixed(1)}%;background:${c}"></i></span></div>`;
      const capped = (p) => p <= 0.05 || p >= 0.95;
      // At the last step and today's level this is the tape's question, which was answered from all nine deciles when sealed.
      const sealedNote = st.step === o.fan.length - 1 && Math.abs(lvl - last) < Math.abs(last) * 1e-4 && o.p_up !== null && o.p_up !== undefined
        ? ` The figure sealed in the ledger, read off all nine deciles, is ${fmt.pct(o.p_up)}.` : "";
      $("st-odds").innerHTML = `<p class="q">Chance ${esc(o.title)} is above <b>${fmt.num(lvl)}</b> on ${esc(f[0])}</p>
        ${meter(pT, "var(--tfm)", modelName)}${pS === null ? "" : meter(pS, "var(--seldon)", "Seldon")}
        <p class="note">${capped(pT) || (pS !== null && capped(pS)) ? "That level is outside the 80% range, so the odds are capped at 5% or 95%: the forecast says nothing sharper out there. "
          : ""}Read off the 10th, 50th and 90th percentiles of the sealed forecast.${sealedNote}</p>`;

      // Percentile ladder.
      const row = (k, i, label) => `<tr><th scope="row">${label}</th><td style="--c:var(--tfm)">${fmt.num(f[i])}<small>${fmt.signedPct(f[i] / last - 1)}</small></td>` +
        (S ? `<td>${fmt.num(S[i])}<small>${fmt.signedPct(S[i] / last - 1)}</small></td>` : "") + "</tr>";
      $("st-ladder").innerHTML = `<thead><tr><th>Percentile</th><th><span class="who" style="--c:var(--tfm)">${modelName}</span></th>${S ? '<th><span class="who" style="--c:var(--seldon)">Seldon</span></th>' : ""}</tr></thead>
        <tbody>${row("q90", 3, "90th · high")}${row("q50", 2, "50th · middle")}${row("q10", 1, "10th · low")}</tbody>`;

      // Your call against theirs.
      if (document.activeElement !== $("st-you")) $("st-you").value = st.you;
      $("st-width").value = (st.width * 100).toFixed(2);
      $("st-width-out").textContent = `± ${(st.width * 100).toFixed(2).replace(/\.?0+$/, "")}%`;
      const youLo = st.you - st.width * last, youHi = st.you + st.width * last;
      $("st-vs").innerHTML = [["You", "var(--you)", st.you, youLo, youHi], [modelName, "var(--tfm)", f[2], f[1], f[3]], ...(S ? [["Seldon", "var(--seldon)", S[2], S[1], S[3]]] : [])]
        .map(([n, c, mid, lo, hi]) => `<div><dt><span class="who" style="--c:${c}">${n}</span></dt><dd>${fmt.num(mid)}<small>${fmt.num(lo)} to ${fmt.num(hi)}</small></dd></div>`).join("");

      if (redrawChart) chart(o, last, S); else chart(o, last, S, false);
      paintCalls();
    }

    function chart(o, last, S, animate) {
      const f = o.fan[st.step], hist = o.history.slice(-Math.max(60, 3 * o.fan.length));
      const lastPt = o.history[o.history.length - 1];
      const youLo = st.you - st.width * last, youHi = st.you + st.width * last;
      const res = plot($("st-chart"), {
        x: "date", height: 360, left: 56, right: 72, animate: animate === false ? false : undefined, label: `${o.title}: sealed forecast and your question`,
        bands: [{ points: [[lastPt[0], last, last]].concat(o.fan.map((p) => [p[0], p[1], p[3]])) },
          ...(S ? [{ points: [[lastPt[0], last, last]].concat(o.seldon.fan.map((p) => [p[0], p[1], p[3]])), color: "transparent", stroke: "var(--seldon)", hatch: false, edge: "2 3" }] : [])],
        lines: [{ points: hist, color: "var(--ink)", width: 1.6, name: "value" },
          { points: [[lastPt[0], last]].concat(o.fan.map((p) => [p[0], p[2]])), color: "var(--tfm)", width: 2, name: modelName, label: modelName },
          ...(S ? [{ points: [[lastPt[0], last]].concat(o.seldon.fan.map((p) => [p[0], p[2]])), color: "var(--seldon)", width: 2, name: "Seldon", label: "Seldon" }] : []),
          { points: [[f[0], youLo], [f[0], youHi]], color: "var(--you)", width: 3, name: "your range", draw: false }],
        dots: [{ points: [[f[0], st.you]], color: "var(--you)", r: 5, stroke: "var(--panel)", name: "you" }],
        refs: [{ y: st.level, label: `level ${fmt.num(st.level)}`, color: "var(--ink-2)" }, { x: f[0], label: f[0] }],
        hover: true,
      });
      if (!res) return;
      // Click anywhere in the forecast to ask about that date and level.
      res.svg.style.cursor = "crosshair";
      res.svg.addEventListener("click", (ev) => {
        const r = res.svg.getBoundingClientRect();
        const px = ((ev.clientX - r.left) / r.width) * res.width, py = ((ev.clientY - r.top) / r.height) * res.height;
        let best = 0;
        o.fan.forEach((p, i) => { if (Math.abs(res.sx(p[0]) - px) < Math.abs(res.sx(o.fan[best][0]) - px)) best = i; });
        if (px < res.sx(lastPt[0])) return;  // the past is not a question
        st.step = best; st.level = round(res.inv(py), last); paint(false);
      });
      $("st-legend").innerHTML = "";
      legend($("st-legend"), [{ name: "History", color: "var(--ink)" }, { name: `${modelName} 80% range`, color: "var(--tfm)", kind: "band" },
        ...(S ? [{ name: "Seldon 80% range", color: "var(--seldon)", kind: "dash" }] : []), { name: "You", color: "var(--you)", kind: "dot" },
        { name: "Your level", color: "var(--ink-2)", kind: "dash" }]);
    }

    async function sealCall() {
      const o = cur(), last = o.history[o.history.length - 1][1], f = o.fan[st.step];
      const S = o.seldon && o.seldon.fan && o.seldon.fan.length ? o.seldon.fan[st.step] : null;
      const call = {
        series: o.id, title: o.title, date: f[0], step: st.step + 1, made_on: o.made_on, last,
        value: st.you, lo: st.you - st.width * last, hi: st.you + st.width * last,
        tfm: [f[1], f[2], f[3]], seldon: S ? [S[1], S[2], S[3]] : null,
        sealed_at: new Date().toISOString(),
      };
      call.fingerprint = await fingerprint(JSON.stringify(call));
      const calls = load().filter((c) => !(c.series === call.series && c.date === call.date && c.made_on === call.made_on));
      calls.unshift(call);
      const ok = save(calls);
      const btn = $("st-seal");
      btn.classList.add("done"); btn.lastChild.textContent = ok ? " Sealed" : " Not saved";
      setTimeout(() => { btn.classList.remove("done"); btn.lastChild.textContent = " Hold to seal"; btn.style.setProperty("--hold", 0); }, 1400);
      paintCalls(call);
      if (opts.onSeal) opts.onSeal(call);
    }

    function paintCalls(fresh) {
      const calls = load(), today = Date.now();
      if (!calls.length) {
        $("st-calls").innerHTML = '<tbody><tr><td><div class="empty"><b>No calls sealed yet.</b>Pick a date, set your value and range, then hold the seal button. Your call is scored against ' +
          `${modelName} and Seldon once the real value is in the data.</div></td></tr></tbody>`;
        return;
      }
      $("st-calls").innerHTML = `<thead><tr><th>Series</th><th>Date</th><th>You</th><th>${modelName}</th><th>Seldon</th><th>Status</th><th>Seal</th></tr></thead><tbody>` +
        calls.map((c) => {
          const out = outcome(c, D), days = Math.ceil((Date.parse(c.date) - today) / DAY);
          const status = out ? `<span class="res ${out.best === "You" ? "pos" : ""}">${fmt.num(out.actual)} · closest: ${esc(out.best)}</span>`
            : days > 0 ? `<span class="dim">opens in ${days} day${days === 1 ? "" : "s"}</span>` : '<span class="dim">waiting for the next data run</span>';
          return `<tr class="${fresh && fresh.fingerprint === c.fingerprint ? "fresh" : ""}"><td>${esc(c.title)}</td><td>${esc(c.date)}</td>
            <td style="color:var(--you)">${fmt.num(c.value)}<small>${fmt.num(c.lo)} to ${fmt.num(c.hi)}</small></td>
            <td>${fmt.num(c.tfm[1])}<small>${fmt.num(c.tfm[0])} to ${fmt.num(c.tfm[2])}</small></td>
            <td>${c.seldon ? `${fmt.num(c.seldon[1])}<small>${fmt.num(c.seldon[0])} to ${fmt.num(c.seldon[2])}</small>` : "–"}</td>
            <td>${status}</td><td><code title="Sealed ${esc(c.sealed_at)}">${esc(c.fingerprint)}</code></td></tr>`;
        }).join("") + "</tbody>";
    }

    paint();
  }

  function csv(o) {
    const S = o.seldon && o.seldon.fan && o.seldon.fan.length ? o.seldon.fan : null;
    const head = "date,step,timesfm_q10,timesfm_q50,timesfm_q90" + (S ? ",seldon_q10,seldon_q50,seldon_q90" : "");
    return [head, ...o.fan.map((p, i) => [p[0], i + 1, p[1], p[2], p[3], ...(S ? S[i].slice(1) : [])].join(","))].join("\n") + "\n";
  }

  function download(name, text, type) {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([text], { type })); a.download = name;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  function holdable(btn, done) {
    let raf = 0, t0 = 0, byKey = false;
    const set = (k) => btn.style.setProperty("--hold", k);
    const start = () => {
      if (raf) return;
      t0 = performance.now();
      const step = (t) => { const k = Math.min(1, (t - t0) / HOLD_MS); set(k); if (k < 1) raf = requestAnimationFrame(step); else { raf = 0; done(); } };
      raf = requestAnimationFrame(step);
    };
    const cancel = () => { if (raf) cancelAnimationFrame(raf); raf = 0; set(0); };
    btn.addEventListener("pointerdown", (e) => { if (e.button === 0) { btn.setPointerCapture(e.pointerId); start(); } });
    btn.addEventListener("pointerup", cancel); btn.addEventListener("pointercancel", cancel); btn.addEventListener("lostpointercapture", cancel);
    btn.addEventListener("keydown", (e) => { if ((e.key === " " || e.key === "Enter") && !e.repeat) { e.preventDefault(); byKey = true; start(); } });
    btn.addEventListener("keyup", (e) => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); byKey = false; cancel(); } });
    btn.addEventListener("click", (e) => { if (e.detail === 0 && !byKey) done(); });
  }

  window.WPStudio = { render, pAbove, outcome, calls: load };
})();
