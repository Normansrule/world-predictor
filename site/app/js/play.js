// Call It: a forecasting game on real data. A real chart, the ending hidden; call it higher or lower,
// then watch what really happened, beside what TimesFM, Seldon and Radiant said at that same moment.
// Rounds come from the race files (app/data/race/<id>.json): every past window there was forecast by the
// models from only the data before it, so the player and the machines face exactly the same blind spot.
// Quick runs and the daily five are practice on the past; live calls are on the real future and settle
// when the data arrives. Everything you do is kept in this browser only.
(function () {
  "use strict";
  const STORE = "wp-play-v1", SOUND_KEY = "wp-sound";
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const M = () => window.WPMotion || { count: (e, v) => e && (e.textContent = v), enter() {}, pop() {}, shake() {}, grow: (e, s) => e && (e.style.width = s * 100 + "%"), tween: (a, b, ms, f, d) => { f(b); d && d(); }, burst() {}, calm: () => true };
  const AREA = { news: "World news", politics: "Politics", markets: "Markets", tech: "Technology", weather: "Weather and Earth" };
  const MODELS = [["timesfm-2.5", "TimesFM", "--tfm"], ["seldon", "Seldon", "--seldon"], ["radiant", "Radiant", "--radiant"]];
  const CONF = [[1, "Lean", "×1"], [2, "Sure", "×2"], [3, "All in", "×3"]];
  const LEVELS = ["Coin flipper", "Hunch", "Chartist", "Analyst", "Strategist", "Forecaster", "Superforecaster", "Oracle", "Seldon's heir"];
  const BADGES = [
    ["first", "First call", "Finish a run"], ["streak5", "On fire", "Five right in a row"], ["beatboth", "Machine breaker", "Beat TimesFM and Seldon in one run"],
    ["perfect", "Clean sheet", "Every call right in a run"], ["bullseye", "Bullseye", "Land within a tenth of a typical move"], ["allin", "Nerves of steel", "Win an All-in call"],
    ["daily3", "Habit", "Play the daily five three days running"], ["live", "On the record", "Make a call on the real future"], ["settled", "Called it", "Get a live call right"],
  ];
  const LIMIT = { dir: 15, eye: 22 };
  const t = (d) => Date.parse(d + "T00:00:00Z");
  const today = () => new Date().toISOString().slice(0, 10);
  const day = (d) => new Date(d + "T12:00:00Z").toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
  const num = (v) => { if (v == null || !Number.isFinite(v)) return "–"; const a = Math.abs(v); return a >= 1e6 ? (v / 1e6).toFixed(2) + "M" : a >= 1e4 ? (v / 1e3).toFixed(1) + "k" : a >= 100 ? v.toFixed(0) : a >= 1 ? v.toFixed(2) : v.toPrecision(3); };
  const pctTxt = (v) => (v >= 0 ? "+" : "−") + Math.abs(v * 100).toFixed(Math.abs(v) < 0.1 ? 1 : 0) + "%";

  // ---------- this browser's record ----------
  function blank() { return { xp: 0, runs: 0, best: 0, bestDaily: 0, you: [0, 0], tfm: [0, 0], seldon: [0, 0], badges: {}, daily: {}, seen: [], live: [], streakBest: 0, history: [] }; }
  function load() { try { return Object.assign(blank(), JSON.parse(localStorage.getItem(STORE)) || {}); } catch (e) { return blank(); } }
  function save() { try { localStorage.setItem(STORE, JSON.stringify(P)); } catch (e) {} }
  let P = load();
  const level = (xp) => { let n = 0, need = 120; while (xp >= need && n < LEVELS.length - 1) { xp -= need; n++; need = Math.round(need * 1.45); } return { n, name: LEVELS[n], into: xp, need }; };

  // ---------- sound: a few synthesised notes, no files ----------
  const Sound = {
    ctx: null,
    get on() { try { return localStorage.getItem(SOUND_KEY) !== "off"; } catch (e) { return true; } },
    set on(v) { try { localStorage.setItem(SOUND_KEY, v ? "on" : "off"); } catch (e) {} },
    ready() {
      if (!this.on) return null;
      try { if (!this.ctx) this.ctx = new (window.AudioContext || window.webkitAudioContext)(); if (this.ctx.state === "suspended") this.ctx.resume(); } catch (e) { return null; }
      return this.ctx;
    },
    tone(f, dur, type = "sine", gain = 0.07, at = 0, to = null) {
      const c = this.ready(); if (!c) return;
      const o = c.createOscillator(), g = c.createGain(), s = c.currentTime + at;
      o.type = type; o.frequency.setValueAtTime(f, s); if (to) o.frequency.exponentialRampToValueAtTime(to, s + dur);
      g.gain.setValueAtTime(0.0001, s); g.gain.exponentialRampToValueAtTime(gain, s + 0.012); g.gain.exponentialRampToValueAtTime(0.0001, s + dur);
      o.connect(g).connect(c.destination); o.start(s); o.stop(s + dur + 0.02);
    },
    click() { this.tone(720, 0.06, "triangle", 0.05); },
    tick() { this.tone(1500, 0.03, "square", 0.018); },
    right(combo) { [523.25, 659.25, 783.99].concat(combo > 1 ? [1046.5] : []).forEach((f, i) => this.tone(f, 0.22, "triangle", 0.07, i * 0.07)); },
    wrong() { this.tone(240, 0.32, "sawtooth", 0.05, 0, 110); this.tone(180, 0.32, "square", 0.025, 0.02, 90); },
    reveal() { this.tone(330, 0.5, "sine", 0.04, 0, 660); },
    win() { [392, 523.25, 659.25, 783.99, 1046.5].forEach((f, i) => this.tone(f, 0.35, "triangle", 0.07, i * 0.09)); this.tone(1318.5, 0.6, "sine", 0.05, 0.5); },
  };

  // ---------- rounds from the race files ----------
  const files = {};
  function file(id) {
    if (!files[id]) files[id] = fetch(`data/race/${encodeURIComponent(id)}.json`).then((r) => (r.ok ? r.json() : null)).catch(() => null).then((J) => J || labFile(id));
    return files[id];
  }
  // Offline, or before the race files exist, the Lab's own past windows (inside data.js) stand in:
  // shorter, but forecast the same honest way, from only the data before each one.
  function labFile(id) {
    const s = Dref && Dref.lab && (Dref.lab.series || []).find((x) => x.id === id);
    if (!s || !s.history || !s.rounds) return null;
    const dates = s.history.map((p) => p[0]), actual = s.history.map((p) => p[1]), n = dates.length;
    const m = { "timesfm-2.5": new Array(n).fill(null), seldon: new Array(n).fill(null) }, origins = [];
    s.rounds.slice().sort((a, b) => +a.at - +b.at).forEach((r) => {
      const at = +r.at; if (!(at > 0 && at < n)) return;
      origins.push(dates[at - 1]);
      (r.model || []).forEach((q, k) => { if (at + k < n) m["timesfm-2.5"][at + k] = q[1]; });
      (r.seldon || []).forEach((q, k) => { if (at + k < n) m.seldon[at + k] = q[1]; });
    });
    return { id, dates, actual, origins, m, minSeen: 15 };
  }
  function pool(D) {
    const meta = {};
    (D.series || []).forEach((s) => (meta[s.id] = { title: s.title, domain: s.domain }));
    (D.outlook || []).forEach((o) => (meta[o.id] = { title: o.title, domain: o.domain }));
    // Plain names where the tally has them: "War in the news", "Apple stock", "Interest in AI".
    const N = (D.tally && D.tally.names) || {};
    for (const id in meta) {
      const n = N[id]; if (!n) continue;
      meta[id].title = n[1] === "talk" ? `${n[0]} in the news` : n[1] === "interest" ? `${n[0]} (Wikipedia views)` : n[1] === "temp" ? `${n[0]}: daily high °C` : n[0];
    }
    const race = Object.keys(D.race || {}), labIds = ((D.lab && D.lab.series) || []).map((s) => s.id);
    const ids = [...new Set(race.length ? race : labIds)].filter((id) => meta[id] && !/^rain_|quake/.test(id)).sort();
    return { ids, meta };
  }
  // Every past window of one series that can be played: at least 60 days seen, at least 5 steps hidden.
  function windows(J) {
    if (J._w) return J._w;
    const d = J.dates, a = J.actual, O = J.origins || [], out = [];
    let li = -1;
    for (let k = 0; k < O.length; k++) {
      while (li + 1 < d.length && d[li + 1] <= O[k]) li++;
      if (li < (J.minSeen || 70)) continue;
      let end = li;
      const next = O[k + 1];
      while (end + 1 < d.length && (next ? d[end + 1] < next : end - li < 22)) end++;
      end = Math.min(end, li + 26);
      while (end > li + 5 && !MODELS.some(([m]) => J.m[m] && J.m[m][end] != null)) end--;
      if (end - li < 5 || a[li] == null || a[end] == null || a[end] === a[li]) continue;
      if (!MODELS.some(([m]) => J.m[m] && J.m[m][end] != null)) continue;
      out.push({ li, end });
    }
    return (J._w = out);
  }
  function build(J, w, meta, kind) {
    const d = J.dates, a = J.actual, ctxFrom = Math.max(0, w.li - 89);
    const ctx = []; for (let i = ctxFrom; i <= w.li; i++) if (a[i] != null) ctx.push([d[i], a[i]]);
    const ans = []; for (let i = w.li + 1; i <= w.end; i++) if (a[i] != null) ans.push([d[i], a[i]]);
    const last = a[w.li], end = a[w.end], H = w.end - w.li;
    const moves = []; for (let i = H; i < ctx.length; i++) moves.push(Math.abs(ctx[i][1] - ctx[i - H][1]));
    moves.sort((x, y) => x - y);
    const typical = moves.length ? moves[Math.floor(moves.length / 2)] : Math.abs(last) * 0.04;
    const models = {};
    MODELS.forEach(([m, name, color]) => {
      const v = J.m[m]; if (!v || v[w.end] == null) return;
      const path = []; for (let i = w.li + 1; i <= w.end; i++) if (v[i] != null) path.push([d[i], v[i]]);
      models[m] = { name, color, path, end: v[w.end], call: v[w.end] > last ? 1 : v[w.end] < last ? -1 : 0 };
    });
    const days = Math.round((t(d[w.end]) - t(d[w.li])) / 864e5);
    return { id: J.id, key: `${J.id}@${d[w.li]}`, title: meta.title, domain: meta.domain, ctx, ans, last, end, up: end > last ? 1 : -1, typical: typical || Math.abs(last) * 0.02 || 1,
      models, days, from: d[w.li], to: d[w.end], kind, change: (end - last) / (Math.abs(last) || 1) };
  }
  function rng(seed) { let s = seed >>> 0; return () => { s += 0x6d2b79f5; let x = Math.imul(s ^ (s >>> 15), 1 | s); x ^= x + Math.imul(x ^ (x >>> 7), 61 | x); return ((x ^ (x >>> 14)) >>> 0) / 4294967296; }; }
  const hash = (str) => { let h = 2166136261; for (const ch of str) h = Math.imul(h ^ ch.charCodeAt(0), 16777619); return h >>> 0; };

  // Draw n rounds: spread over the areas, never the same series twice, no window seen in the last 300.
  async function deal(D, n, rand, eyes, avoidSeen) {
    const { ids, meta } = pool(D);
    const byArea = {};
    ids.forEach((id) => (byArea[meta[id].domain] = byArea[meta[id].domain] || []).push(id));
    const areas = Object.keys(byArea).sort();
    const order = [], used = new Set();
    for (let k = 0; order.length < Math.min(n * 3, ids.length) && k < 2000; k++) {
      const list = byArea[areas[Math.floor(rand() * areas.length)]];
      const id = list[Math.floor(rand() * list.length)];
      if (!used.has(id)) { used.add(id); order.push(id); }
    }
    const seen = new Set(avoidSeen ? P.seen : []), out = [];
    for (const id of order) {
      if (out.length >= n) break;
      const J = await file(id);
      if (!J) continue;
      const W = windows(J).filter((w) => !seen.has(`${id}@${J.dates[w.li]}`));
      if (!W.length) continue;
      const kind = eyes.includes(out.length) ? "eye" : "dir";
      out.push(build(J, W[Math.floor(rand() * W.length)], meta[id], kind));
    }
    return out;
  }

  // ---------- the chart ----------
  function chart(R, o) {
    const W = Math.max(300, o.w), H = Math.round(Math.min(400, Math.max(230, W * 0.42)));
    const L = 8, Rr = W < 560 ? 52 : 70, T = 18, B = 26;
    const n = R.ctx.length + R.ans.length, cut = R.ctx.length - 1;
    const X = (i) => L + (i / (n - 1)) * (W - L - Rr);
    const [y0, y1] = o.dom;
    const Y = (v) => T + (1 - (Math.min(Math.max(v, y0 - (y1 - y0) * 0.3), y1 + (y1 - y0) * 0.3) - y0) / (y1 - y0 || 1)) * (H - T - B);
    const path = (pts, i0) => pts.map((p, k) => `${k ? "L" : "M"}${X(i0 + k).toFixed(1)},${Y(p[1]).toFixed(1)}`).join("");
    const ctxD = path(R.ctx, 0);
    const area = ctxD + `L${X(cut).toFixed(1)},${H - B}L${X(0).toFixed(1)},${H - B}Z`;
    const grid = [0.2, 0.4, 0.6, 0.8].map((k) => { const v = y0 + (y1 - y0) * (1 - k); return `<line x1="${L}" x2="${W - Rr + 6}" y1="${Y(v)}" y2="${Y(v)}" class="g"/><text x="${W - Rr + 10}" y="${Y(v) + 4}" class="gl">${num(v)}</text>`; }).join("");
    const zx = X(cut), zw = X(n - 1) - zx, nowY = Y(R.last);
    const answer = o.reveal ? (() => {
      const pts = [[R.ctx[cut][0], R.last]].concat(R.ans);
      const d = path(pts, cut);
      const col = R.up > 0 ? "var(--up)" : "var(--down)";
      const ends = MODELS.filter(([m]) => R.models[m]).map(([m, name, c], k) => {
        const md = R.models[m], mp = path([[R.ctx[cut][0], R.last]].concat(md.path), cut);
        const ey = Y(md.end);
        return `<path d="${mp}" class="mp draw" pathLength="1" style="--c:var(${c});--d:${0.25 + k * 0.18}s"/><circle cx="${X(n - 1)}" cy="${ey}" r="4.5" class="me" style="--c:var(${c});--d:${0.9 + k * 0.18}s"/>`;
      }).join("");
      const you = o.guess != null ? `<line x1="${zx}" x2="${X(n - 1) + 8}" y1="${Y(o.guess)}" y2="${Y(o.guess)}" class="yl"/><circle cx="${X(n - 1)}" cy="${Y(o.guess)}" r="7" class="yd"/>` : "";
      return `${ends}${you}<path d="${d}" class="ans draw" pathLength="1" style="--c:${col}"/><circle cx="${X(n - 1)}" cy="${Y(R.end)}" r="7" class="ae" style="--c:${col}"/>`;
    })() : "";
    const hidden = o.reveal ? "" : `<g class="q"><rect x="${zx}" y="${T - 6}" width="${zw}" height="${H - T - B + 6}" rx="10" class="hz"/>
      <text x="${zx + zw / 2}" y="${(H - B + T) / 2 + 16}" class="qm">?</text><text x="${zx + zw / 2}" y="${H - B - 10}" class="ql">hidden</text></g>`;
    const eye = o.eye != null ? `<line x1="${zx}" x2="${X(n - 1) + 8}" y1="${Y(o.eye)}" y2="${Y(o.eye)}" class="yl"/><circle cx="${X(n - 1)}" cy="${Y(o.eye)}" r="10" class="yd grab"/><text x="${X(n - 1) - 14}" y="${Y(o.eye) - 14}" class="yt" text-anchor="end">${num(o.eye)}</text>` : "";
    const dir = o.dir ? `<path d="M${zx + 18},${nowY} l${zw * 0.55},${-o.dir * Math.min(70, (H - T - B) * 0.25)}" class="arrow" marker-end="url(#pl-ah)"/>` : "";
    return `<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" role="img" aria-label="${esc(R.title)}: the last ${R.ctx.length} values, ending hidden" class="pl-svg">
      <defs><linearGradient id="pl-area" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="var(--you)" stop-opacity=".34"/><stop offset="1" stop-color="var(--you)" stop-opacity="0"/></linearGradient>
      <pattern id="pl-hatch" width="10" height="10" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="10" class="ht"/></pattern>
      <marker id="pl-ah" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10z" fill="var(--you)"/></marker></defs>
      ${grid}<path d="${area}" fill="url(#pl-area)" class="ar"/><path d="${ctxD}" class="cl"/>
      ${hidden}<line x1="${zx}" x2="${zx}" y1="${T - 6}" y2="${H - B}" class="now"/>${dir}${answer}${eye}
      <circle cx="${zx}" cy="${nowY}" r="5" class="nd"/><circle cx="${zx}" cy="${nowY}" r="5" class="np"/>
      <text x="${zx - 8}" y="${H - 8}" text-anchor="end" class="xl">now · ${num(R.last)}</text>${W < 560 ? "" : `<text x="${X(n - 1)}" y="${H - 8}" text-anchor="end" class="xl">${R.days >= 10 ? `about ${Math.round(R.days / 7)} weeks later` : `${R.days} days later`}</text>`}</svg>`;
  }
  function domainOf(R, withAnswer) {
    const v = R.ctx.map((p) => p[1]);
    if (withAnswer) { R.ans.forEach((p) => v.push(p[1])); Object.values(R.models).forEach((m) => m.path.forEach((p) => v.push(p[1]))); }
    let lo = Math.min(...v), hi = Math.max(...v);
    // Before the reveal the window must not hint at the answer: pad both sides by the same typical move.
    const pad = withAnswer ? (hi - lo || 1) * 0.08 : Math.max((hi - lo) * 0.16, R.typical * 1.7);
    return [lo - pad, hi + pad];
  }

  // ---------- the game ----------
  const G = { screen: "lobby", busy: false };
  let root = null, Dref = null;

  function startRun(mode) {
    Sound.click();
    const isDaily = mode === "daily";
    const n = isDaily ? 5 : 10, eyes = isDaily ? [4] : [4, 9];
    const seed = isDaily ? hash("call-it-" + today()) : (Math.random() * 2 ** 32) >>> 0;
    Object.assign(G, { screen: "load", mode, n, rounds: [], i: 0, score: 0, streak: 0, best: 0, conf: 1, log: [], tally: { you: 0, tfm: 0, seldon: 0, radiant: 0, dirs: 0 } });
    paint();
    deal(Dref, n, rng(seed), eyes, !isDaily).then((R) => {
      if (!R.length) { G.screen = "empty"; paint(); return; }
      G.rounds = R; G.n = R.length; G.screen = "round"; begin();
    });
  }
  function begin() {
    const R = G.rounds[G.i];
    Object.assign(G, { phase: "call", dir: 0, eye: R.kind === "eye" ? R.last : null, dom: domainOf(R, false), left: LIMIT[R.kind], verdict: null });
    paint();
    clock();
  }
  let timer = null, tickAt = 0;
  function clock() {
    cancelAnimationFrame(timer);
    const total = G.left, t0 = performance.now();
    const ring = root.querySelector(".pl-ring i"), lab = root.querySelector(".pl-ring b");
    const step = (now) => {
      if (G.phase !== "call" || G.screen !== "round") return;
      if (document.hidden) { timer = requestAnimationFrame(step); return; }
      const left = Math.max(0, total - (now - t0) / 1000);
      G.left = left;
      if (ring) ring.style.setProperty("--k", (left / LIMIT[G.rounds[G.i].kind]).toFixed(4));
      if (lab) lab.textContent = Math.ceil(left);
      if (left <= 5 && Math.ceil(left) !== tickAt) { tickAt = Math.ceil(left); if (left > 0) Sound.tick(); }
      if (left <= 0) { settle(true); return; }
      timer = requestAnimationFrame(step);
    };
    timer = requestAnimationFrame(step);
  }

  function settle(timeout) {
    if (G.phase !== "call") return;
    cancelAnimationFrame(timer);
    const R = G.rounds[G.i], conf = timeout ? 1 : G.conf, v = { timeout, conf, models: {} };
    MODELS.forEach(([m]) => { const md = R.models[m]; if (md) v.models[m] = md.call === R.up; });
    if (R.kind === "dir") {
      v.right = !timeout && G.dir === R.up;
      G.tally.dirs++;
      if (v.models["timesfm-2.5"]) G.tally.tfm++;
      if (v.models.seldon) G.tally.seldon++;
      if (v.models.radiant) G.tally.radiant++;
    } else {
      const err = Math.abs(G.eye - R.end), close = Math.max(0, 1 - err / (2 * R.typical));
      v.err = err; v.close = close;
      v.beat = MODELS.filter(([m]) => R.models[m]).map(([m, name]) => [name, Math.abs(R.models[m].end - R.end) > err]);
      v.right = !timeout && (close >= 0.5 || v.beat.some((b) => b[0] === "TimesFM" && b[1]));
      v.models = {};
    }
    if (v.right) { G.streak++; G.best = Math.max(G.best, G.streak); if (R.kind === "dir") G.tally.you++; } else G.streak = 0;
    const combo = G.streak >= 8 ? 3 : G.streak >= 5 ? 2 : G.streak >= 3 ? 1.5 : 1;
    let pts;
    if (R.kind === "dir") pts = v.right ? Math.round((100 * conf + Math.round(50 * (G.left / LIMIT.dir))) * combo) : -50 * (conf - 1) * 2;
    else pts = timeout ? 0 : Math.round((300 * v.close + 150 * v.beat.filter((b) => b[1]).length) * (v.right ? combo : 1));
    v.pts = pts; v.combo = combo;
    G.score = Math.max(0, G.score + pts);
    G.log.push({ kind: R.kind, right: v.right, close: v.close, conf, timeout });
    if (v.right && conf === 3 && R.kind === "dir") award("allin");
    if (G.streak >= 5) award("streak5");
    if (v.close >= 0.95) award("bullseye");
    P.seen = P.seen.concat([R.key]).slice(-300);
    G.verdict = v; G.phase = "reveal";
    // Rescale to fit the answer first, then draw it in.
    const from = G.dom, to = domainOf(R, true);
    M().tween(0, 1, 380, (k) => { G.dom = [from[0] + (to[0] - from[0]) * k, from[1] + (to[1] - from[1]) * k]; const host = root.querySelector(".pl-chart"); if (host) host.innerHTML = chart(R, { w: host.clientWidth, dom: G.dom, dir: G.dir, eye: R.kind === "eye" ? G.eye : null }); }, () => {
      paint();
      const card = root.querySelector(".pl-stage");
      setTimeout(() => {
        if (v.right) { Sound.right(combo); const b = card.getBoundingClientRect(), e = root.querySelector(".pl-verdict"); const r = e ? e.getBoundingClientRect() : b; M().burst(card, r.left - b.left + r.width / 2, r.top - b.top + 20, { count: combo > 1 ? 110 : 70 }); }
        else { Sound.wrong(); M().shake(card); }
        M().pop(root.querySelector(".pl-verdict"));
        M().count(root.querySelector("[data-score]"), G.score, { from: Math.max(0, G.score - pts) });
      }, 520);
    });
  }

  function next() {
    if (G.phase !== "reveal") return;
    Sound.click();
    if (G.i + 1 < G.rounds.length) { G.i++; begin(); return; }
    finish();
  }

  function award(k) { if (!P.badges[k]) { P.badges[k] = today(); (G.fresh = G.fresh || []).push(k); } }

  function finish() {
    const T = G.tally, beatT = T.you > T.tfm, beatS = T.you > T.seldon;
    P.runs++; P.you[0] += T.you; P.you[1] += T.dirs; P.tfm[0] += T.tfm; P.tfm[1] += T.dirs; P.seldon[0] += T.seldon; P.seldon[1] += T.dirs;
    P.streakBest = Math.max(P.streakBest, G.best);
    const before = level(P.xp);
    const gain = 20 + Math.round(G.score / 10) + (beatT ? 25 : 0) + (beatS ? 25 : 0);
    P.xp += gain;
    award("first");
    if (beatT && beatS) award("beatboth");
    if (T.dirs && T.you === T.dirs) award("perfect");
    const newBest = G.mode === "daily" ? G.score > P.bestDaily : G.score > P.best;
    if (G.mode === "daily") {
      P.bestDaily = Math.max(P.bestDaily, G.score);
      if (!P.daily[today()]) P.daily[today()] = { score: G.score, grid: grid(), you: T.you, tfm: T.tfm, seldon: T.seldon, n: T.dirs };
      const d = new Date(); let run = 0;
      for (let k = 0; k < 30; k++) { const key = new Date(d.getTime() - k * 864e5).toISOString().slice(0, 10); if (P.daily[key]) run++; else break; }
      if (run >= 3) award("daily3");
    } else P.best = Math.max(P.best, G.score);
    P.history = (P.history || []).concat([{ d: today(), s: G.score, m: G.mode, y: T.you, t: T.tfm, n: T.dirs }]).slice(-24);
    save();
    Object.assign(G, { screen: "end", gain, before, after: level(P.xp), newBest });
    paint();
    Sound.win();
    const s = root.querySelector(".pl-end");
    M().count(root.querySelector("[data-final]"), G.score, { duration: 1100 });
    M().enter(root.querySelectorAll(".pl-sq"), { stagger: 60, y: 8, scale: 0.6, delay: 250 });
    root.querySelectorAll("[data-bar]").forEach((b, k) => M().grow(b, +b.dataset.bar, { delay: 300 + k * 120 }));
    const xb = root.querySelector("[data-xp]"); if (xb) M().grow(xb, +xb.dataset.xp, { delay: 700, from: (G.before.n === G.after.n ? (G.before.into / G.before.need) * 100 : 0) + "%" });
    M().enter(root.querySelectorAll(".pl-badge.new"), { stagger: 120, y: 0, scale: 0.4, delay: 900 });
    if (s && (beatT || G.newBest)) setTimeout(() => M().burst(s, s.clientWidth / 2, 90, { count: 140, power: 9 }), 500);
  }
  const grid = () => G.log.map((l) => (l.kind === "eye" ? (l.close >= 0.75 ? "🎯" : l.right ? "🟨" : "⬛") : l.timeout ? "⬜" : l.right ? "🟩" : "🟥")).join("");

  // ---------- live calls on the real future ----------
  function liveCandidates(D) {
    const pick = (D.outlook || []).filter((o) => o.history && o.history.length > 5 && o.fan && o.fan.length > 4 && !/^rain_|quake/.test(o.id));
    const order = ["markets", "news", "politics", "tech", "weather"];
    pick.sort((a, b) => order.indexOf(a.domain) - order.indexOf(b.domain));
    const out = [], per = {};
    for (const o of pick) { per[o.domain] = (per[o.domain] || 0) + 1; if (per[o.domain] <= (o.domain === "markets" ? 3 : 1)) out.push(o); if (out.length >= 7) break; }
    return out;
  }
  function settleLive(D) {
    let changed = false;
    P.live.forEach((c) => {
      if (c.result != null) return;
      const o = (D.outlook || []).find((x) => x.id === c.id);
      const h = o && o.history.find((p) => p[0] >= c.due);
      if (!h) return;
      c.actual = h[1]; c.actualDate = h[0];
      c.result = (h[1] > c.base ? 1 : h[1] < c.base ? -1 : 0) === c.call;
      c.tfmRight = c.tfm != null ? (h[1] > c.base ? 1 : -1) === c.tfm : null;
      if (c.result) award("settled");
      changed = true;
    });
    if (changed) save();
  }
  function callLive(id, dir) {
    const o = (Dref.outlook || []).find((x) => x.id === id); if (!o) return;
    const last = o.history[o.history.length - 1], f = o.fan[Math.min(4, o.fan.length - 1)];
    if (P.live.some((c) => c.id === id && c.result == null)) return;
    P.live.unshift({ id, title: o.title, domain: o.domain, base: last[1], baseDate: last[0], due: f[0], call: dir, tfm: f[2] > last[1] ? 1 : -1, made: today() });
    P.live = P.live.slice(0, 60);
    award("live"); save(); Sound.click(); paint();
  }

  // ---------- screens ----------
  function hud() {
    const R = G.rounds[G.i];
    const dots = G.rounds.map((r, k) => `<i class="${k < G.log.length ? (G.log[k].right ? "ok" : "no") : k === G.i ? "at" : ""}${r.kind === "eye" ? " eye" : ""}"></i>`).join("");
    const combo = G.streak >= 8 ? 3 : G.streak >= 5 ? 2 : G.streak >= 3 ? 1.5 : 1;
    return `<div class="pl-hud"><button class="pl-x" data-act="quit" aria-label="Leave this run">✕</button><div class="pl-dots" aria-label="Round ${G.i + 1} of ${G.rounds.length}">${dots}</div>
      <div class="pl-stat"><small>Score</small><b data-score>${G.score.toLocaleString()}</b></div>
      <div class="pl-stat pl-combo ${combo > 1 ? "hot" : ""}"><small>Streak</small><b>${G.streak}${combo > 1 ? ` <em>×${combo}</em>` : ""}</b></div>
      <div class="pl-ring" style="--k:1" aria-hidden="${G.phase !== "call"}"><i></i><b>${G.phase === "call" ? Math.ceil(G.left) : "✓"}</b></div></div>`;
  }
  function roundView() {
    const R = G.rounds[G.i], v = G.verdict, rev = G.phase === "reveal";
    const ask = R.kind === "eye" ? `Bullseye: where will it be, ${R.days >= 10 ? `about ${Math.round(R.days / 7)} weeks` : `${R.days} days`} later?` : `Higher or lower, ${R.days >= 10 ? `about ${Math.round(R.days / 7)} weeks` : `${R.days} days`} later?`;
    const head = `<div class="pl-q"><span class="tag" style="--c:var(--${R.domain})">${esc(AREA[R.domain] || R.domain)}</span><h2>${esc(R.title)}</h2>
      <p>${rev ? `${day(R.from)} to ${day(R.to)}: it went ${R.up > 0 ? "up" : "down"} <b class="${R.up > 0 ? "up" : "down"}">${R.domain === "weather" ? `${R.end > R.last ? "+" : "−"}${Math.abs(R.end - R.last).toFixed(1)} °C` : pctTxt(R.change)}</b>` : `A real stretch from the past, dates hidden. ${esc(ask)}`}</p></div>`;
    const ctrl = rev ? reveal(R, v) : R.kind === "eye"
      ? `<div class="pl-ctl eye"><p class="pl-hint">Drag the dot on the right, or use <kbd>↑</kbd> <kbd>↓</kbd>. Closer than TimesFM and Seldon pays more.</p>
         <div class="pl-eyeval"><small>Your call</small><b data-eyev>${num(G.eye)}</b><span data-eyec>${pctTxt((G.eye - R.last) / (Math.abs(R.last) || 1))}</span></div>
         <button class="pl-go" data-act="lock">Lock it in <kbd>Enter</kbd></button></div>`
      : `<div class="pl-ctl"><div class="pl-conf" role="radiogroup" aria-label="How sure">${CONF.map(([k, name, x]) => `<button role="radio" aria-checked="${G.conf === k}" data-conf="${k}"><b>${name}</b><small>${x}${k > 1 ? ` · lose ${100 * (k - 1)}` : " · no risk"}</small></button>`).join("")}</div>
         <div class="pl-call"><button class="pl-dn" data-dir="-1"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12l7 7 7-7"/></svg>Lower<kbd>←</kbd></button>
         <button class="pl-up" data-dir="1"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 19V5M5 12l7-7 7 7"/></svg>Higher<kbd>→</kbd></button></div></div>`;
    return `<div class="pl-stage ${rev ? (v.right ? "won" : "lost") : ""}">${hud()}${head}<div class="pl-chart"></div>${ctrl}</div>`;
  }
  function reveal(R, v) {
    const chips = MODELS.filter(([m]) => R.models[m]).map(([m, name, c]) => {
      const md = R.models[m];
      if (R.kind === "eye") { const b = v.beat.find((x) => x[0] === name); return `<span class="pl-chip" style="--c:var(${c})"><i></i>${name} said ${num(md.end)} <b class="${b && b[1] ? "up" : "down"}">${b && b[1] ? "you were closer" : "closer than you"}</b></span>`; }
      return `<span class="pl-chip" style="--c:var(${c})"><i></i>${name} said ${md.call > 0 ? "higher" : "lower"} <b class="${v.models[m] ? "up" : "down"}">${v.models[m] ? "✓" : "✗"}</b></span>`;
    }).join("");
    const title = v.timeout ? "Time's up" : R.kind === "eye" ? (v.close >= 0.9 ? "Bullseye!" : v.close >= 0.6 ? "Close!" : v.right ? "Not bad" : "Way off") : v.right ? (v.combo > 1 ? `Right! Streak ×${v.combo}` : "Right!") : "Wrong";
    const sub = R.kind === "eye" ? `You said ${num(G.eye)}; it was ${num(R.end)}.` : v.timeout ? "No call made." : `You said ${G.dir > 0 ? "higher" : "lower"}${v.conf > 1 ? `, ${CONF[v.conf - 1][1].toLowerCase()}` : ""}.`;
    return `<div class="pl-ctl rev"><div class="pl-verdict ${v.right ? "up" : "down"}"><b>${title}</b><span>${v.pts >= 0 ? "+" : "−"}${Math.abs(v.pts)}</span></div><p class="pl-sub">${esc(sub)}</p>
      <div class="pl-chips">${chips}</div><button class="pl-go" data-act="next">${G.i + 1 < G.rounds.length ? "Next round" : "See your score"} <kbd>Enter</kbd></button></div>`;
  }
  function lobby() {
    settleLive(Dref);
    const L = level(P.xp), lt = (a) => (a[1] ? Math.round((a[0] / a[1]) * 100) + "%" : "–");
    const dailyDone = P.daily[today()];
    const pending = P.live.filter((c) => c.result == null).length;
    const badges = BADGES.map(([k, name, how]) => `<div class="pl-badge ${P.badges[k] ? "got" : ""}" title="${esc(how)}"><i aria-hidden="true">${P.badges[k] ? "★" : "☆"}</i><b>${esc(name)}</b><small>${esc(how)}</small></div>`).join("");
    const life = [["You", P.you, "--you"], ["TimesFM", P.tfm, "--tfm"], ["Seldon", P.seldon, "--seldon"]]
      .map(([n, a, c]) => `<div class="pl-life" style="--c:var(${c})"><span>${n}</span><i><s style="width:${a[1] ? (a[0] / a[1]) * 100 : 0}%"></s></i><b>${lt(a)}</b></div>`).join("");
    return `<div class="pl-lobby">
      <section class="pl-hero"><svg class="pl-wave" viewBox="0 0 600 160" preserveAspectRatio="none" aria-hidden="true"><path d="M0,110 C40,100 60,60 100,70 S160,130 200,100 S260,30 300,50 S360,120 400,90 S460,20 500,40 S570,90 600,60"/><path d="M0,120 C50,115 70,90 110,95 S170,135 210,115 S270,70 310,80 S370,130 410,105 S470,60 510,70 S570,110 600,90"/></svg>
        <p class="pl-kicker">A game on real data</p><h1 class="pl-title">Call <em>It</em></h1>
        <p class="pl-lede">A real chart, the ending hidden. Call it higher or lower, then watch what really happened, and what TimesFM and Seldon said at that same moment. Can you beat the machines?</p>
        <div class="pl-cta"><button class="pl-go big" data-act="quick">Play a quick run <small>10 rounds · about 3 minutes</small></button>
        <button class="pl-ghost" data-act="daily" ${dailyDone ? "aria-describedby=pl-dd" : ""}>${dailyDone ? `Today's five: ${dailyDone.score} pts · play again for fun` : "Today's daily five"}<small id="pl-dd">${dailyDone ? "the first try counts" : "the same five for everyone today"}</small></button></div>
        <div class="pl-sound"><button data-act="sound" aria-pressed="${Sound.on}">${Sound.on ? "Sound on" : "Sound off"}</button></div></section>
      <div class="pl-grid">
        <section class="card pl-card"><header class="ph"><h2>Your record</h2><span class="pm">kept in this browser</span></header>
          <div class="pl-level"><div class="pl-lv"><b>${L.n + 1}</b><small>level</small></div><div><p><b>${esc(L.name)}</b>${L.n + 1 < LEVELS.length ? ` · next: ${esc(LEVELS[L.n + 1])}` : ""}</p><i class="pl-xp"><s style="width:${(L.into / L.need) * 100}%"></s></i><small>${L.into} of ${L.need} XP · best run ${P.best.toLocaleString()} · best streak ${P.streakBest}</small></div></div>
          <h3 class="pl-h3">Up or down, right so far</h3>${life}
          <h3 class="pl-h3">Your last runs</h3>${runs()}
          <p class="pl-note">Same windows, same blind spot: the models forecast each one from only the data before it.</p></section>
        <section class="card pl-card"><header class="ph"><h2>Call the real future</h2><span class="pm">${pending ? `${pending} waiting` : "settles as data arrives"}</span></header>${liveView()}</section>
        <section class="card pl-card pl-wide"><header class="ph"><h2>Badges</h2><span class="pm">${Object.keys(P.badges).length} of ${BADGES.length}</span></header><div class="pl-badges">${badges}</div></section>
        <section class="card pl-card pl-wide"><header class="ph"><h2>How to play</h2></header><ol class="pl-how">
          <li><b>Read the chart.</b> Ninety real days of a market, a news topic, a technology or the weather. The dates stay hidden until the end, so hindsight can't help.</li>
          <li><b>Make your call.</b> Higher or lower when the hidden stretch ends. Lean risks nothing; Sure and All in pay double and triple but cost you if wrong. Fast answers earn a bonus, and streaks multiply.</li>
          <li><b>Bullseye rounds</b> ask for a number: drag the dot to where you think it ends. Beat TimesFM's and Seldon's error for extra points.</li>
          <li><b>Watch it play out</b> beside the models. Keys: <kbd>←</kbd> lower, <kbd>→</kbd> higher, <kbd>1</kbd> <kbd>2</kbd> <kbd>3</kbd> how sure, <kbd>Enter</kbd> next.</li></ol></section>
      </div></div>`;
  }
  function runs() {
    const H = P.history || [];
    if (!H.length) return '<p class="pl-runs-empty">Your scores appear here after your first run.</p>';
    const top = Math.max(...H.map((h) => h.s), 1);
    return `<div class="pl-runs" aria-label="Your last ${H.length} scores">${H.map((h) => `<i class="${h.s === top ? "best" : h.m === "daily" ? "daily" : ""}" style="height:${Math.max(4, (h.s / top) * 100)}%" title="${esc(day(h.d))}: ${h.s} points, ${h.y} of ${h.n} right (TimesFM ${h.t})"></i>`).join("")}</div>`;
  }
  function liveView() {
    const cands = liveCandidates(Dref);
    const open = new Set(P.live.filter((c) => c.result == null).map((c) => c.id));
    const rows = cands.map((o) => {
      const last = o.history[o.history.length - 1], f = o.fan[Math.min(4, o.fan.length - 1)];
      if (open.has(o.id)) { const c = P.live.find((x) => x.id === o.id && x.result == null); return `<li><span class="tag" style="--c:var(--${o.domain})">${esc(AREA[o.domain])}</span><b>${esc(o.title)}</b><small>you said ${c.call > 0 ? "higher" : "lower"} than ${num(c.base)} by ${day(c.due)} · TimesFM said ${c.tfm > 0 ? "higher" : "lower"}</small><em class="pl-wait">waiting</em></li>`; }
      return `<li><span class="tag" style="--c:var(--${o.domain})">${esc(AREA[o.domain])}</span><b>${esc(o.title)}</b><small>now ${num(last[1])} · by ${day(f[0])}</small><span class="pl-mini"><button data-live="${esc(o.id)}" data-ld="-1" aria-label="${esc(o.title)} lower">▼</button><button data-live="${esc(o.id)}" data-ld="1" aria-label="${esc(o.title)} higher">▲</button></span></li>`;
    }).join("");
    const done = P.live.filter((c) => c.result != null).slice(0, 5).map((c) => `<li class="${c.result ? "ok" : "no"}"><span class="tag" style="--c:var(--${c.domain})">${esc(AREA[c.domain] || "")}</span><b>${esc(c.title)}</b><small>${num(c.base)} → ${num(c.actual)} by ${day(c.actualDate)} · you ${c.result ? "✓" : "✗"} · TimesFM ${c.tfmRight ? "✓" : "✗"}</small></li>`).join("");
    return `<ul class="pl-live">${rows}</ul>${done ? `<h3 class="pl-h3">Settled</h3><ul class="pl-live">${done}</ul>` : ""}<p class="pl-note">Call higher or lower for about a week out. TimesFM's sealed call is shown once you have made yours, and both are settled against what really happens.</p>`;
  }
  function endView() {
    const T = G.tally, n = T.dirs || 1;
    const acc = T.dirs ? T.you / T.dirs : 0;
    const grade = acc >= 0.9 ? "Oracle" : acc >= 0.75 ? "Superforecaster" : acc >= 0.6 ? "Sharp" : acc >= 0.5 ? "Coin with an opinion" : "Contrarian (try flipping)";
    const rows = [["You", T.you, "--you"], ["TimesFM", T.tfm, "--tfm"], ["Seldon", T.seldon, "--seldon"], ["Radiant", T.radiant, "--radiant"]]
      .map(([name, k, c]) => `<div class="pl-vs" style="--c:var(${c})"><span>${name}</span><i><s data-bar="${k / n}"></s></i><b>${k}/${T.dirs}</b></div>`).join("");
    const fresh = (G.fresh || []).map((k) => { const b = BADGES.find((x) => x[0] === k); return `<div class="pl-badge got new"><i>★</i><b>${esc(b[1])}</b><small>${esc(b[2])}</small></div>`; }).join("");
    G.fresh = [];
    const L = G.after, up = G.after.n > G.before.n;
    const sq = G.log.map((l) => `<span class="pl-sq ${l.kind === "eye" ? (l.close >= 0.75 ? "eye" : l.right ? "mid" : "no") : l.timeout ? "out" : l.right ? "ok" : "no"}"></span>`).join("");
    const verdict = T.you > T.tfm && T.you > T.seldon ? "You beat both machines." : T.you > T.tfm ? "You beat TimesFM." : T.you > T.seldon ? "You beat Seldon." : T.you === T.tfm ? "Level with TimesFM." : "The machines win this one.";
    return `<div class="pl-end card"><p class="pl-kicker">${G.mode === "daily" ? `Daily five · ${day(today())}` : "Quick run"} · ${esc(grade)}</p>
      <h1 class="pl-final"><b data-final>0</b><small>points${G.newBest ? " · new best!" : ""}</small></h1><div class="pl-sqs">${sq}</div>
      <p class="pl-say">${esc(verdict)} Best streak ${G.best}.</p><div class="pl-vsw">${rows}</div>
      <div class="pl-level slim"><div class="pl-lv"><b>${L.n + 1}</b><small>level</small></div><div><p><b>+${G.gain} XP</b>${up ? ` · level up: <b>${esc(L.name)}</b>` : ` · ${esc(L.name)}`}</p><i class="pl-xp"><s data-xp="${L.into / L.need}"></s></i></div></div>
      ${fresh ? `<div class="pl-badges">${fresh}</div>` : ""}
      <div class="pl-cta"><button class="pl-go" data-act="again">Play again <kbd>Enter</kbd></button><button class="pl-ghost" data-act="share">Share</button><button class="pl-ghost" data-act="lobby">Back</button></div>
      <p class="pl-note">Practice on the past: TimesFM, Seldon and Radiant made these calls from only the data before each window. Not financial advice.</p></div>`;
  }

  function paint() {
    if (!root) return;
    if (G.screen === "lobby") root.innerHTML = lobby();
    else if (G.screen === "load") root.innerHTML = `<div class="pl-load card"><div class="pl-spin"></div><p>Dealing real charts…</p></div>`;
    else if (G.screen === "empty") root.innerHTML = `<div class="empty"><b>No rounds to deal.</b>Call It reads the race files, which load with the app online. <button class="pl-ghost" data-act="lobby">Back</button></div>`;
    else if (G.screen === "end") root.innerHTML = endView();
    else {
      root.innerHTML = roundView();
      const R = G.rounds[G.i], host = root.querySelector(".pl-chart");
      host.innerHTML = chart(R, { w: host.clientWidth, dom: G.dom, reveal: G.phase === "reveal", dir: G.phase === "call" ? 0 : G.dir, eye: G.phase === "call" && R.kind === "eye" ? G.eye : null, guess: G.phase === "reveal" && R.kind === "eye" ? G.eye : null });
      if (G.phase === "call") { M().enter([root.querySelector(".pl-q"), host, root.querySelector(".pl-ctl")], { stagger: 70, y: 10 }); if (R.kind === "eye") drag(host, R); }
    }
    if (G.screen === "lobby") { M().enter(root.querySelectorAll(".pl-hero > *, .pl-card"), { stagger: 50 }); }
  }

  function drag(host, R) {
    const set = (clientY) => {
      const svg = host.querySelector("svg"); if (!svg) return;
      const r = svg.getBoundingClientRect(), H = +svg.getAttribute("height"), T = 18, B = 26;
      const k = (clientY - r.top) / r.height * H;
      const [y0, y1] = G.dom;
      G.eye = y0 + (1 - (k - T) / (H - T - B)) * (y1 - y0);
      redrawEye(R);
    };
    let on = false;
    host.onpointerdown = (e) => { on = true; host.setPointerCapture(e.pointerId); set(e.clientY); };
    host.onpointermove = (e) => { if (on) set(e.clientY); };
    host.onpointerup = host.onpointercancel = () => (on = false);
  }
  function redrawEye(R) {
    const host = root.querySelector(".pl-chart");
    host.innerHTML = chart(R, { w: host.clientWidth, dom: G.dom, eye: G.eye });
    const v = root.querySelector("[data-eyev]"), c = root.querySelector("[data-eyec]");
    if (v) v.textContent = num(G.eye);
    if (c) c.textContent = pctTxt((G.eye - R.last) / (Math.abs(R.last) || 1));
  }
  function call(dir) {
    if (G.phase !== "call" || G.rounds[G.i].kind !== "dir") return;
    G.dir = dir; Sound.click(); settle(false);
  }
  function share() {
    const T = G.tally;
    const text = `Call It${G.mode === "daily" ? " · daily five " + today() : ""} · ${G.score} pts\n${grid()}\nMe ${T.you}/${T.dirs} · TimesFM ${T.tfm}/${T.dirs} · Seldon ${T.seldon}/${T.dirs}\n${location.href.split("#")[0]}#play`;
    const done = () => window.WPToast ? window.WPToast("Copied, ready to paste") : null;
    if (navigator.share && matchMedia("(pointer: coarse)").matches) navigator.share({ text }).catch(() => {});
    else if (navigator.clipboard) navigator.clipboard.writeText(text).then(done, () => prompt("Copy your result", text));
  }

  function onClick(e) {
    const b = e.target.closest("button"); if (!b || !root.contains(b)) return;
    const act = b.dataset.act;
    if (b.dataset.conf) { G.conf = +b.dataset.conf; Sound.click(); root.querySelectorAll("[data-conf]").forEach((x) => x.setAttribute("aria-checked", String(+x.dataset.conf === G.conf))); return; }
    if (b.dataset.dir) return call(+b.dataset.dir);
    if (b.dataset.live) return callLive(b.dataset.live, +b.dataset.ld);
    if (act === "quick" || act === "again") return startRun(act === "again" ? G.mode : "quick");
    if (act === "daily") return startRun("daily");
    if (act === "lock") { Sound.click(); return settle(false); }
    if (act === "next") return next();
    if (act === "share") return share();
    if (act === "sound") { Sound.on = !Sound.on; if (Sound.on) Sound.click(); b.setAttribute("aria-pressed", String(Sound.on)); b.textContent = Sound.on ? "Sound on" : "Sound off"; return; }
    if (act === "quit" || act === "lobby") { cancelAnimationFrame(timer); G.screen = "lobby"; paint(); }
  }
  function onKey(e) {
    if (!root || !location.hash.startsWith("#play") || e.metaKey || e.ctrlKey || e.altKey || /INPUT|SELECT|TEXTAREA/.test(e.target.tagName)) return;
    if (G.screen === "round" && G.phase === "call") {
      const R = G.rounds[G.i];
      if (R.kind === "dir") {
        if (e.key === "ArrowLeft" || e.key === "ArrowDown") { e.preventDefault(); e.stopPropagation(); call(-1); }
        else if (e.key === "ArrowRight" || e.key === "ArrowUp") { e.preventDefault(); e.stopPropagation(); call(1); }
        else if (/^[123]$/.test(e.key)) { e.preventDefault(); e.stopPropagation(); const b = root.querySelector(`[data-conf="${e.key}"]`); if (b) b.click(); }
      } else if (e.key === "ArrowUp" || e.key === "ArrowDown") {
        e.preventDefault(); e.stopPropagation(); G.eye += (e.key === "ArrowUp" ? 1 : -1) * R.typical * (e.shiftKey ? 0.5 : 0.1); redrawEye(R);
      } else if (e.key === "Enter") { e.preventDefault(); e.stopPropagation(); settle(false); }
    } else if (e.key === "Enter" || e.key === " ") {
      if (G.screen === "round" && G.phase === "reveal") { e.preventDefault(); next(); }
      else if (G.screen === "end" && e.key === "Enter") { e.preventDefault(); startRun(G.mode); }
    }
  }
  // Swipe up or down on the chart to call it on a phone.
  let sy0 = null;
  function onTouch(e) {
    if (G.screen !== "round" || G.phase !== "call" || G.rounds[G.i].kind !== "dir" || !e.target.closest(".pl-chart")) return;
    if (e.type === "touchstart") sy0 = e.touches[0].clientY;
    else if (sy0 != null) { const dy = e.changedTouches[0].clientY - sy0; sy0 = null; if (Math.abs(dy) > 50) call(dy < 0 ? 1 : -1); }
  }

  function render(host, D) {
    Dref = D;
    if (root !== host) {
      root = host;
      host.addEventListener("click", onClick);
      document.addEventListener("keydown", onKey, true);
      host.addEventListener("touchstart", onTouch, { passive: true });
      host.addEventListener("touchend", onTouch, { passive: true });
    }
    if (G.screen === "round" && G.phase === "call") { paint(); clock(); } else paint();
  }

  window.WPPlay = { render, _test: { windows, build, domainOf, level, rng, hash, pool } };
})();
