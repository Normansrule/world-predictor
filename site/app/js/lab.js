// The Lab: make a blind call on a real past window, seal it, break the seal, and see how you did
// against TimesFM and Seldon (our own forecaster from five laws of crowd behaviour, see src/psychohistory/seldon.py).
// Reads window.WP_DATA.lab, built from the backtest paths by web.lab_payload. Both models made their
// calls from the same history the visitor sees; nothing after the cut is drawn until the seal breaks.
// Used by the app (#lab) and, in compact form, by the landing page's hero.
(function () {
  const STORE = "wp-lab-v1";
  const HOLD_MS = 480;
  const AREA = { news: "World news", markets: "Markets", tech: "Technology" };
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const reduce = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  const instances = new Map();

  // ---------- the visitor's running tally, kept in this browser only ----------
  function tally() {
    try { return Object.assign(blank(), JSON.parse(localStorage.getItem(STORE)) || {}); } catch (e) { return blank(); }
  }
  function blank() { return { played: 0, beatModel: 0, beatSeldon: 0, beatNaive: 0, inside: 0, done: {} }; }
  function save(t) { try { localStorage.setItem(STORE, JSON.stringify(t)); } catch (e) {} }

  // ---------- one round: what is shown, what is hidden ----------
  function roundOf(s, r) {
    const ctxFrom = Math.max(0, r.at - Math.max(2 * s.horizon, 24));
    const context = s.history.slice(ctxFrom, r.at);
    const answer = s.history.slice(r.at, r.at + s.horizon);
    const last = context[context.length - 1][1];
    // Typical move over one horizon in the visible history: the starting width of the visitor's range.
    const moves = [];
    for (let i = s.horizon; i < context.length; i++) moves.push(Math.abs(context[i][1] - context[i - s.horizon][1]));
    moves.sort((a, b) => a - b);
    const typical = moves.length ? moves[Math.floor(moves.length / 2)] : Math.abs(last) * 0.03;
    return { s, r, context, answer, last, dates: answer.map((p) => p[0]), typical: typical || Math.abs(last) * 0.02 || 1 };
  }

  // The visitor's path: a straight line from the last value to their end value, with a range that
  // widens with the square root of the steps ahead, the way uncertainty usually grows.
  function yourPath(R, end, width) {
    const h = R.dates.length;
    return R.dates.map((d, i) => {
      const k = (i + 1) / h, mid = R.last + (end - R.last) * k, hw = width * Math.sqrt(k);
      return [d, mid - hw, mid, mid + hw];
    });
  }

  function score(R, path) {
    const a = R.answer.map((p) => p[1]), L = R.last, n = a.length;
    const scale = Math.abs(L) || 1;
    const out = (p) => {
      const mids = p ? p.map((x) => x[2]) : a.map(() => L);
      const err = mids.reduce((t, m, i) => t + Math.abs(m - a[i]), 0) / n / scale;
      const inside = p ? p.reduce((t, x, i) => t + (a[i] >= x[1] && a[i] <= x[3] ? 1 : 0), 0) / n : null;
      const said = Math.sign(mids[n - 1] - L), did = Math.sign(a[n - 1] - L);
      return { err, inside, direction: p && said && did ? said === did : null, end: mids[n - 1] };
    };
    return out;
  }

  // ---------- mount / render ----------
  function render(host, D, opts = {}) {
    const L = D && D.lab;
    if (!L || !L.series || !L.series.length) {
      host.innerHTML = `<div class="empty"><b>The Lab opens after the first backtest.</b>It needs past forecast windows to hide and reveal.
        Run <code>psychohistory backtest</code>, or wait for the monthly run on GitHub Actions.</div>`;
      return;
    }
    let me = instances.get(host);
    if (!me) { me = create(host, D, L, opts); instances.set(host, me); }
    if (opts.start && me.goto(opts.start)) return;
    me.draw(false);
  }

  function create(host, D, L, opts) {
    const { plot, fmt, icon, council, councilBar } = window.WPCharts;
    const compact = !!opts.compact;
    const modelName = L.model === "timesfm-2.5" ? "TimesFM" : L.model;
    const series = L.series.filter((s) => s.rounds.length);
    const st = { si: 0, ri: 0, end: 0, width: 0, phase: "call", justSealed: false, justRevealed: false, focus: null };

    // Start where the visitor left off; on the landing page, on the S&P 500's newest round.
    let startId = opts.start;
    try { startId = startId || localStorage.getItem(STORE + "-at"); } catch (e) {}
    const found = series.findIndex((s) => s.id === (startId || "").split("|")[0]);
    st.si = found >= 0 ? found : Math.max(0, series.findIndex((s) => s.id === "sp500"));
    st.ri = series[st.si].rounds.length - 1;

    host.innerHTML = compact ? `
      <div class="card lab-card">
        <header class="ph"><h2 id="lab-title-${uid()}"></h2><span class="pm lab-meta"></span></header>
        <div class="lab-stage" tabindex="-1"></div>
        <div class="lab-act"></div>
        <div class="scores-wrap"></div>
      </div>` : `
      <div class="lab">
        <div class="card lab-card">
          <div class="lab-pick">
            <select class="lab-series" aria-label="Series"></select>
            <div class="rounds" role="group" aria-label="Past window"></div>
            <button class="btn lab-random" title="Random round">${icon("shuffle")}Random</button>
          </div>
          <header class="ph"><h2></h2><span class="pm lab-meta"></span></header>
          <div class="lab-stage" tabindex="-1"></div>
          <p class="lab-hint"><span>Drag the violet dot to set where it ends, and the ring to set how sure you are.</span>
            <span class="keyhint"><kbd>↑</kbd><kbd>↓</kbd> move · <kbd>[</kbd><kbd>]</kbd> range · hold <kbd>Space</kbd> to seal · <kbd>N</kbd> next</span></p>
          <div class="lab-act"></div>
          <div class="scores-wrap"></div>
        </div>
        <div class="side">
          <div class="card"><header class="ph"><h2>Your record</h2><button class="btn small lab-reset" style="margin:0">Reset</button></header><div class="lab-tally"></div></div>
          <div class="card"><header class="ph"><h2>${esc(modelName)} vs Seldon</h2><span class="pm">every past window</span></header><div class="lab-board"></div></div>
          <div class="card prose"><header class="ph"><h2>Who is Seldon?</h2></header>
            <p class="learned">Our own forecaster, built to compete with TimesFM. Hari Seldon bet that crowds follow a few simple laws,
              so Seldon has five: <b>inertia</b> (tomorrow looks like today), <b>drift</b> (the long-run course holds), <b>momentum</b>
              (a move keeps going, then fades), <b>reversion</b> (excitement wears off) and the <b>weekly rhythm</b> of news and attention. Before each forecast it
              replays the series' own past, gives each law a vote by how well it did, and sets its range from its own past misses.
              No neural network, no pretraining. It is scored on the same windows as TimesFM and it is allowed to lose.</p></div>
        </div>
      </div>`;
    const q = (sel) => host.querySelector(sel);
    const stage = q(".lab-stage");
    let geo = null, R = null;

    function uid() { return Math.random().toString(36).slice(2, 7); }

    // ---------- choosing a round ----------
    function setRound(si, ri) {
      st.si = si; st.ri = ri; st.phase = "call"; st.justSealed = st.justRevealed = false;
      R = roundOf(series[si], series[si].rounds[ri]);
      st.end = R.last; st.width = R.typical * 1.1;
      try { localStorage.setItem(STORE + "-at", series[si].id + "|" + ri); } catch (e) {}
      if (!compact) pickers();
      draw(true);
    }
    function pickers() {
      const sel = q(".lab-series");
      const groups = [...new Set(series.map((s) => s.domain))];
      sel.innerHTML = groups.map((g) => `<optgroup label="${esc(AREA[g] || g)}">` + series.map((s, i) => s.domain === g
        ? `<option value="${i}"${i === st.si ? " selected" : ""}>${esc(s.title)}</option>` : "").join("") + "</optgroup>").join("");
      const t = tally(), s = series[st.si];
      q(".rounds").innerHTML = s.rounds.map((r, i) => `<button aria-pressed="${i === st.ri}" data-r="${i}" class="${t.done[s.id + "|" + r.origin] ? "done" : ""}"
        title="Window starting ${esc(r.origin)}">${esc(r.origin.slice(0, 7))}</button>`).join("");
    }
    function random() {
      const t = tally(), open = [];
      series.forEach((s, si) => s.rounds.forEach((r, ri) => { if (!t.done[s.id + "|" + r.origin] && !(si === st.si && ri === st.ri)) open.push([si, ri]); }));
      const pool = open.length ? open : series.flatMap((s, si) => s.rounds.map((_, ri) => [si, ri]));
      const [si, ri] = pool[Math.floor(Math.random() * pool.length)];
      setRound(si, ri);
    }
    function next() {
      const s = series[st.si];
      if (st.ri < s.rounds.length - 1) setRound(st.si, st.ri + 1);
      else random();
    }

    // ---------- drawing ----------
    function domain(path) {
      const vals = R.context.map((p) => p[1]);
      if (st.phase === "revealed") {
        vals.push(...R.answer.map((p) => p[1]), ...R.r.model.flatMap((x) => [x[0], x[2]]), ...R.r.seldon.flatMap((x) => [x[0], x[2]]),
          ...path.flatMap((x) => [x[1], x[3]]));
      }
      let lo = Math.min(...vals), hi = Math.max(...vals);
      if (st.phase !== "revealed") {
        // Room above and below the last value, the same both ways, so the frame gives nothing away.
        const room = Math.max(hi - lo, 3 * R.typical) * 0.9;
        lo = Math.min(lo, R.last - room); hi = Math.max(hi, R.last + room);
      }
      const pad = (hi - lo || Math.abs(hi) || 1) * 0.06;
      return [lo - pad, hi + pad];
    }

    function draw(fresh) {
      if (!R) { setRound(st.si, st.ri); return; }
      const s = R.s, revealed = st.phase === "revealed", path = yourPath(R, st.end, st.width);
      host.querySelectorAll(".ph h2")[0].textContent = s.title;
      host.querySelector(".lab-meta").textContent = `${AREA[s.domain] || s.domain} · ${s.horizon} steps · window from ${R.r.origin}`;
      const cut = R.context[R.context.length - 1][0];
      // On a phone, less history and a shorter frame leave room to make the call.
      const narrow = stage.clientWidth < 560, ctx = narrow ? R.context.slice(-Math.max(R.s.horizon, 15)) : R.context;
      const spec = {
        x: "date", height: narrow ? 280 : compact ? 300 : 400, left: narrow ? 44 : 56, right: narrow ? 60 : 84, hover: revealed, animate: false,
        label: `${s.title}: ${revealed ? "your call, both models and what really happened" : "history up to the cut; the rest is hidden"}`,
        xDomain: [ctx[0][0], R.dates[R.dates.length - 1]], yDomain: domain(path),
        spans: revealed ? [] : [{ from: cut, to: R.dates[R.dates.length - 1], label: "hidden" }],
        refs: [{ x: cut, label: revealed ? "the cut" : "you are here", color: "var(--ink-2)" }],
        bands: [], lines: [{ points: ctx, color: "var(--ink)", width: 1.8, name: "history" }], dots: [],
      };
      const yourLine = [[cut, R.last]].concat(path.map((p) => [p[0], p[2]]));
      // Once the seal breaks, your range keeps only its outline so the models' ranges stay readable.
      spec.bands.push({ points: [[cut, R.last, R.last]].concat(path.map((p) => [p[0], p[1], p[3]])), color: revealed ? "transparent" : "var(--band-y)", stroke: "var(--you)", hatch: false, edge: "1 0", fade: false });
      if (revealed) {
        const anim = st.justRevealed && !reduce(), d = (t) => (anim ? t : undefined);
        const m = R.r.model.map((x, i) => [R.dates[i], x[0], x[1], x[2]]), sd = R.r.seldon.map((x, i) => [R.dates[i], x[0], x[1], x[2]]);
        spec.bands.unshift(
          { points: [[cut, R.last, R.last]].concat(m.map((p) => [p[0], p[1], p[3]])), color: "var(--band)", stroke: "var(--tfm)", fade: anim, delay: d(0.75) },
          { points: [[cut, R.last, R.last]].concat(sd.map((p) => [p[0], p[1], p[3]])), color: "transparent", stroke: "var(--seldon)", hatch: false, edge: "2 3", fade: anim, delay: d(1.15) });
        spec.lines.push(
          { points: [[cut, R.last]].concat(m.map((p) => [p[0], p[2]])), color: "var(--tfm)", width: 2, name: modelName, draw: anim, delay: d(0.75) },
          { points: [[cut, R.last]].concat(sd.map((p) => [p[0], p[2]])), color: "var(--seldon)", width: 2, name: "Seldon", draw: anim, delay: d(1.15) },
          { points: yourLine, color: "var(--you)", width: 2, name: "you" },
          { points: [[cut, R.last]].concat(R.answer), color: "var(--ink)", width: 2.4, name: "reality", draw: anim, delay: d(0) });
      } else {
        spec.lines.push({ points: yourLine, color: "var(--you)", width: 2, name: "you" });
      }
      const box = stage;
      box.classList.toggle("revealed", revealed);
      const hint = q(".lab-hint"); if (hint) hint.hidden = st.phase !== "call";
      geo = plot(box, spec);
      labels(revealed, path);
      if (!revealed) handles(path);
      if (st.phase !== "call") stamp(path);
      act(path);
      scores(path);
      if (!compact) side();
      st.justSealed = st.justRevealed = false;
      if (fresh && st.focus) { const h = stage.querySelector(`.handle.${st.focus}`); if (h) h.focus(); }
    }

    // Names at the right edge, nudged apart so they never sit on top of each other.
    function labels(revealed, path) {
      const NS = "http://www.w3.org/2000/svg", x = geo.width - geo.m.r + 8, endY = (v) => geo.sy(v);
      const items = [{ t: "You", c: "var(--you)", y: endY(path[path.length - 1][2]) }];
      if (revealed) {
        items.push({ t: "Reality", c: "var(--ink)", y: endY(R.answer[R.answer.length - 1][1]) },
          { t: modelName, c: "var(--tfm)", y: endY(R.r.model[R.r.model.length - 1][1]) },
          { t: "Seldon", c: "var(--seldon)", y: endY(R.r.seldon[R.r.seldon.length - 1][1]) });
      }
      items.sort((a, b) => a.y - b.y);
      for (let i = 1; i < items.length; i++) items[i].y = Math.max(items[i].y, items[i - 1].y + 15);
      const g = document.createElementNS(NS, "g");
      items.forEach((it) => {
        const t = document.createElementNS(NS, "text");
        t.setAttribute("x", x); t.setAttribute("y", it.y + 4); t.setAttribute("class", "end"); t.style.fill = it.c; t.textContent = it.t;
        g.appendChild(t);
      });
      geo.svg.appendChild(g);
    }

    function handles(path) {
      if (st.phase !== "call") return;
      const NS = "http://www.w3.org/2000/svg", last = path[path.length - 1], x = geo.sx(last[0]);
      const make = (kind, y, label, now) => {
        const g = document.createElementNS(NS, "g");
        g.setAttribute("class", "handle " + kind); g.setAttribute("tabindex", "0"); g.setAttribute("role", "slider");
        g.setAttribute("aria-label", label); g.setAttribute("aria-valuetext", now);
        g.innerHTML = `<circle class="hit" cx="${x}" cy="${y}" r="20"/><circle class="dot" cx="${x}" cy="${y}" r="6.5"/>`;
        g.addEventListener("focus", () => (st.focus = kind));
        geo.svg.appendChild(g);
      };
      make("range", geo.sy(last[3]), "How sure you are: the top of your 80% range", `plus or minus ${pctOf(last[3] - last[2])}`);
      make("end", geo.sy(last[2]), "Where you think it ends", `${fmt.num(last[2])}, ${signedOf(last[2] - R.last)}`);
    }

    function stamp(path) {
      const NS = "http://www.w3.org/2000/svg", last = path[path.length - 1];
      const g = document.createElementNS(NS, "g");
      g.setAttribute("transform", `translate(${geo.sx(last[0])} ${geo.sy(last[2])})`);
      const anim = st.phase === "sealed" ? (st.justSealed ? "stamp" : "") : st.justRevealed ? "crack" : "gone";
      if (anim === "gone") return;
      g.innerHTML = `<g class="${anim}" ${anim ? "" : 'transform="rotate(-8)"'}><circle r="24"/><circle r="19" fill="none" stroke="var(--on-seal)" stroke-opacity=".5" stroke-dasharray="2 2"/>
        <text text-anchor="middle" y="-2">SEALED</text><text text-anchor="middle" y="10" style="font-size:8px;letter-spacing:.02em">${esc(R.context[R.context.length - 1][0].slice(2))}</text></g>`;
      geo.svg.appendChild(g);
    }

    const pctOf = (v) => (Math.abs(v / (R.last || 1)) * 100).toFixed(1) + "%";
    const signedOf = (v) => fmt.signedPct(v / (Math.abs(R.last) || 1));

    // ---------- the action row: your call, and the seal ----------
    function act(path) {
      const last = path[path.length - 1], phase = st.phase;
      const label = phase === "call" ? "Hold to seal your call" : phase === "sealed" ? "Hold to break the seal" : "Next round";
      const cls = phase === "call" ? "" : phase === "sealed" ? " break" : " next";
      q(".lab-act").innerHTML = `<dl class="your-call">
          <div><dt>Your end value</dt><dd>${fmt.num(last[2])}</dd></div>
          <div><dt>Change</dt><dd>${signedOf(last[2] - R.last)}</dd></div>
          <div><dt>80% range</dt><dd>± ${pctOf(last[3] - last[2])}</dd></div>
        </dl>
        <button class="seal-btn${cls}" aria-describedby="${phase === "revealed" ? "" : "hold-why"}">
          ${phase === "revealed" ? "" : '<svg class="ring" viewBox="0 0 24 24" aria-hidden="true"><circle class="track" cx="12" cy="12" r="9" pathLength="1"/><circle class="fill" cx="12" cy="12" r="9" pathLength="1"/></svg>'}
          ${label}${phase === "revealed" ? " <kbd>N</kbd>" : ""}</button>
        <span id="hold-why" class="sr">Press and hold, or hold the space bar, so a call is never sealed by accident.</span>`;
      const btn = q(".seal-btn");
      if (phase === "revealed") { btn.onclick = () => (compact ? random() : next()); return; }
      holdable(btn, phase === "call" ? seal : reveal);
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
      // Assistive technology clicks without pressing anything: act at once.
      btn.addEventListener("click", (e) => { if (e.detail === 0 && !byKey) done(); });
      btn.hold = { start, cancel };
    }

    function seal() { st.phase = "sealed"; st.justSealed = true; draw(false); q(".seal-btn").focus(); }
    function reveal() {
      st.phase = "revealed"; st.justRevealed = true;
      const s = series[st.si], key = s.id + "|" + R.r.origin, t = tally();
      if (!t.done[key]) {
        const sc = results(yourPath(R, st.end, st.width));
        t.played += 1; t.done[key] = 1;
        t.beatModel += sc.you.err < sc.model.err ? 1 : 0; t.beatSeldon += sc.you.err < sc.seldon.err ? 1 : 0;
        t.beatNaive += sc.you.err < sc.naive.err ? 1 : 0; t.inside += sc.you.inside;
        save(t);
        if (opts.onScore) opts.onScore(t);
        if (!compact) pickers();
      }
      draw(false);
      const b = q(".seal-btn"); if (b) b.focus();
    }

    function results(path) {
      const f = score(R, path);
      return {
        you: f(path), naive: f(null),
        model: f(R.r.model.map((x, i) => [R.dates[i], x[0], x[1], x[2]])),
        seldon: f(R.r.seldon.map((x, i) => [R.dates[i], x[0], x[1], x[2]])),
      };
    }

    // ---------- after the reveal ----------
    function scores(path) {
      const wrap = q(".scores-wrap"), card = host.querySelector(".lab-card");
      card.classList.toggle("revealed-panel", st.phase === "revealed");
      if (st.phase !== "revealed") { wrap.innerHTML = ""; return; }
      const sc = results(path), rows = [["You", "var(--you)", sc.you], [modelName, "var(--tfm)", sc.model], ["Seldon", "var(--seldon)", sc.seldon], ['"No change"', "var(--ink-2)", sc.naive]];
      const best = rows.reduce((b, r) => (r[2].err < b[2].err ? r : b));
      const real = R.answer[R.answer.length - 1][1];
      const youBest = best[0] === "You", beat = [sc.model, sc.seldon].filter((x) => sc.you.err < x.err).length;
      const verdict = youBest ? (beat === 2 ? `You beat ${modelName} and Seldon.` : "You were closest.")
        : best[0] === '"No change"' ? `"No change" won: nobody's move paid off.` : `${best[0]} was closest${beat ? `, but you beat ${sc.you.err < sc.model.err ? modelName : "Seldon"}` : ""}.`;
      const learned = esc(council(R.r.council)) + councilBar(R.r.council);
      const dir = (d) => (d === null ? '<span class="dim">no call</span>' : d ? '<span class="pos">right</span>' : '<span class="neg">wrong</span>');
      wrap.innerHTML = `<div class="lab-result">
        <p class="verdict">${esc(verdict)}</p>
        <p class="verdict-sub">It ended at <b>${fmt.num(real)}</b> (${signedOf(real - R.last)}). ${learned}</p>
        <div class="table-wrap"><table class="scores"><thead><tr><th>Forecaster</th><th>Average miss</th><th>vs "no change"</th><th>Inside its range</th><th>Direction</th></tr></thead><tbody>
        ${rows.map(([n, col, r]) => `<tr class="${r === best[2] ? "win" : ""}"><td><span class="who" style="--c:${col}">${esc(n)}</span></td>
          <td>${(r.err * 100).toFixed(2)}%</td><td>${r === sc.naive ? "–" : signedPctSkill(1 - r.err / (sc.naive.err || 1e-12))}</td>
          <td>${r.inside === null ? "–" : Math.round(r.inside * 100) + "%"}</td><td>${r === sc.naive ? "–" : dir(r.direction)}</td></tr>`).join("")}
        </tbody></table></div>
        <p class="note">Average miss is the mean distance from reality over the ${R.dates.length} steps, as a share of the last value. Ranges are 80% ranges: a good one catches reality about 8 times in 10.</p>
        </div>`;
    }
    const signedPctSkill = (v) => `<span class="${Math.abs(v) < 0.02 ? "dim" : v > 0 ? "pos" : "neg"}">${fmt.signedPct(v)}</span>`;

    function side() {
      const t = tally(), n = t.played;
      q(".lab-tally").innerHTML = n ? `<dl class="tally">
          <div><dt>Rounds</dt><dd>${n}</dd></div>
          <div><dt>Range hit</dt><dd>${Math.round((t.inside / n) * 100)}%<small>of days</small></dd></div>
          <div><dt>Beat ${esc(modelName)}</dt><dd>${t.beatModel}<small>of ${n}</small></dd></div>
          <div><dt>Beat Seldon</dt><dd>${t.beatSeldon}<small>of ${n}</small></dd></div>
        </dl><p class="note">Kept in this browser only. Beating means a smaller average miss on that round.</p>`
        : '<p class="note" style="margin:0">No rounds yet. Make a call on the left, seal it, then break the seal.</p>';
      const rows = {};
      (L.board || []).forEach((b) => ((rows[b.domain] = rows[b.domain] || {})[b.model === L.model ? "m" : "s"] = b));
      const cell = (v) => (v === null || v === undefined ? "–" : `<span class="${Math.abs(v) < 0.02 ? "dim" : v > 0 ? "pos" : "neg"}">${fmt.signedPct(v)}</span>`);
      q(".lab-board").innerHTML = Object.keys(rows).length ? `<div class="table-wrap"><table class="board-mini"><thead><tr><th>Area</th><th>Skill</th><th>In range</th></tr></thead><tbody>` +
        Object.entries(rows).map(([d, r]) => `<tr><td>${esc(AREA[d] || d)}</td>
          <td><span class="who" style="--c:var(--tfm)">${cell(r.m && r.m.skill)}</span><br><span class="who" style="--c:var(--seldon)">${cell(r.s && r.s.skill)}</span></td>
          <td>${r.m ? Math.round(r.m.inside * 100) + "%" : "–"}<br>${r.s ? Math.round(r.s.inside * 100) + "%" : "–"}</td></tr>`).join("") +
        `</tbody></table></div><p class="note">Median skill per series against "no change", and how often reality fell inside the 80% range (aim: 80%).
          <span class="who" style="--c:var(--tfm)">${esc(modelName)}</span> above, <span class="who" style="--c:var(--seldon)">Seldon</span> below.</p>`
        : '<p class="note" style="margin:0">Appears after the first backtest.</p>';
    }

    // ---------- input: drag, keys ----------
    let drag = null;
    stage.addEventListener("pointerdown", (e) => {
      if (st.phase !== "call" || !geo || e.button !== 0) return;
      const r = geo.svg.getBoundingClientRect(), k = geo.width / r.width;
      const px = (e.clientX - r.left) * k, py = (e.clientY - r.top) * k;
      if (px < geo.sx(R.context[R.context.length - 1][0]) - 12) return; // the past is not draggable
      const onRange = e.target.closest && e.target.closest(".handle.range");
      drag = { kind: onRange ? "range" : "end", k, top: r.top };
      st.focus = drag.kind;
      stage.setPointerCapture(e.pointerId);
      move(py);
      e.preventDefault();
    });
    stage.addEventListener("pointermove", (e) => {
      if (!drag) return;
      const r = geo.svg.getBoundingClientRect();
      move((e.clientY - r.top) * (geo.width / r.width));
    });
    const end = () => { drag = null; };
    stage.addEventListener("pointerup", end); stage.addEventListener("pointercancel", end);
    function move(py) {
      const v = geo.inv(py), [lo, hi] = [geo.y0, geo.y1];
      if (drag.kind === "end") st.end = Math.min(hi, Math.max(lo, v));
      else st.width = Math.max((hi - lo) * 0.004, Math.abs(v - st.end));
      draw(false);
    }
    stage.addEventListener("keydown", (e) => {
      if (st.phase !== "call" || !geo) return;
      const span = geo.y1 - geo.y0, step = span / (e.shiftKey ? 20 : 100);
      const kind = (e.target.closest && e.target.closest(".handle.range")) ? "range" : "end";
      if (e.key === "ArrowUp" || e.key === "ArrowDown") {
        const s = e.key === "ArrowUp" ? step : -step;
        if (kind === "end") st.end = Math.min(geo.y1, Math.max(geo.y0, st.end + s)); else st.width = Math.max(span * 0.004, st.width + s);
        st.focus = kind;
      } else if (e.key === "[" || e.key === "]") {
        st.width = Math.max(span * 0.004, st.width * (e.key === "]" ? 1.15 : 0.87));
      } else return;
      e.preventDefault();
      draw(true);
    });

    // Keys that work anywhere in the Lab view (the app only; the landing page has its own page keys).
    if (!compact) {
      q(".lab-series").onchange = (e) => setRound(+e.target.value, series[+e.target.value].rounds.length - 1);
      q(".rounds").onclick = (e) => { const b = e.target.closest("button"); if (b) setRound(st.si, +b.dataset.r); };
      q(".lab-random").onclick = random;
      q(".lab-reset").onclick = () => { save(blank()); pickers(); side(); if (opts.onScore) opts.onScore(tally()); };
      document.addEventListener("keydown", (e) => {
        if (!host.offsetParent || /INPUT|SELECT|TEXTAREA/.test(e.target.tagName) || e.metaKey || e.ctrlKey || e.altKey) return;
        const btn = q(".seal-btn");
        if (e.key === " " && !e.repeat && st.phase !== "revealed" && e.target === document.body) { e.preventDefault(); btn && btn.hold && btn.hold.start(); }
        else if ((e.key === "n" || e.key === "N") && st.phase === "revealed") { e.preventDefault(); next(); }
        else if ((e.key === "ArrowUp" || e.key === "ArrowDown" || e.key === "[" || e.key === "]") && e.target === document.body && st.phase === "call") {
          const h = stage.querySelector(".handle.end"); if (h) { h.focus(); h.dispatchEvent(new KeyboardEvent("keydown", { key: e.key, shiftKey: e.shiftKey, bubbles: true })); e.preventDefault(); }
        }
      });
      document.addEventListener("keyup", (e) => { if (e.key === " " && e.target === document.body) { const btn = q(".seal-btn"); if (btn && btn.hold) btn.hold.cancel(); } });
    }

    function goto(id) {
      const i = series.findIndex((s) => s.id === id);
      if (i < 0 || i === st.si) return false;
      setRound(i, series[i].rounds.length - 1);
      return true;
    }

    return { draw: (fresh) => draw(fresh), next, random, goto };
  }

  window.WPLab = { render, tally };
})();
