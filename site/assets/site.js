// World Predictor landing page: fills the page with real numbers from app/data/data.js, mounts the
// Lab in the hero and runs the scroll effects. Plain JavaScript, no libraries; everything still reads without it.
(function () {
  const D = window.WP_DATA;
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const $ = (s, root = document) => root.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const pct = (v) => (v === null || v === undefined ? "–" : Math.round(v * 100) + "%");
  const signed = (v) => (v === null || v === undefined ? "–" : Math.abs(v) < 0.0005 ? "0.0%" : (v > 0 ? "+" : "−") + Math.abs(v * 100).toFixed(1) + "%");
  const cls = (v) => (v === null || v === undefined || Math.abs(v) < 0.02 ? "dim" : v > 0 ? "pos" : "neg");

  // Theme toggle shared with the terminal.
  const toggle = $("#theme");
  if (toggle) toggle.addEventListener("click", () => {
    const root = document.documentElement;
    const light = root.dataset.theme === "light";
    root.dataset.theme = light ? "slate" : "light";
    try { localStorage.setItem("wp-theme", root.dataset.theme); } catch (e) {}
  });

  if (D) {
    const model = D.meta.model, name = /^timesfm/.test(model) ? "TimesFM" : model, sc = D.scorecard || {};
    // Tape: every sealed forecast, the chance it ends higher.
    $("#tape").innerHTML = D.outlook.map((o) => {
      const p = o.p_up, c = p === null ? "flat" : p > 0.55 ? "up" : p < 0.45 ? "down" : "flat";
      return `<a href="app/#outlook/${esc(o.id)}" style="--c:var(--${esc(o.domain)})" title="${esc(o.title)}"><b>${esc(o.id.replace(/_composite$/, "").replace(/_/g, " ").toUpperCase().slice(0, 12))}</b>` +
        `<span class="${c}">${c === "up" ? "▲" : c === "down" ? "▼" : "■"} ${pct(p)}</span></a>`;
    }).join("");
    $("#hero-facts").innerHTML = [
      [String(D.series.length), "series backtested", D.meta.demo ? "demo data" : "news, markets, technology"],
      [techSkill(D, model, sc), `${name} in technology`, 'less error than "no change"'],
      [String(D.outlook.length), "sealed this week", `scored from ${D.outlook[0] ? D.outlook[0].fan[0][0] : "–"}`],
    ].map(([v, k, s]) => `<div><dt>${k}</dt><dd>${esc(v)}<small>${esc(s)}</small></dd></div>`).join("");
    if (window.WPLab) window.WPLab.render($("#hero-lab"), D, { compact: true, start: "sp500" });
    board(D, model, name);
  }

  // The same number the scoreboard shows, so the hero and the table never disagree.
  function techSkill(D, model, sc) {
    const r = pick(D, "tech", model);
    const v = r ? r.skill : sc.tech ? sc.tech.skill : null;
    return v === null || v === undefined ? "–" : signed(v);
  }

  // One row per area and model: the backtest when it already scored Seldon, else the Lab's board.
  function pick(D, d, m) {
    if (D.domains.some((r) => r.model === "seldon") || !D.lab) { const r = D.domains.find((x) => x.domain === d && x.model === m); return r && { skill: r.skill, inside: r.coverage80 }; }
    return (D.lab.board || []).find((x) => x.domain === d && x.model === m);
  }

  // Scoreboard: TimesFM and Seldon against "no change", one row per area.
  function board(D, model, name) {
    const host = $("#board"); if (!host) return;
    const areas = [["news", "World news", "GDELT attention"], ["markets", "Markets", "stocks, gold, silver, oil"], ["tech", "Technology", "Wikipedia and adoption"]].filter(([d]) => pick(D, d, model));
    if (!areas.length) { host.innerHTML = '<tr><td><div class="empty"><b>No backtest yet.</b>The scoreboard fills in after the first forecast run.</div></td></tr>'; return; }
    const cell = (r, k) => (!r || r[k] === null || r[k] === undefined ? "–" : k === "skill" ? `<span class="${cls(r.skill)}">${signed(r.skill)}</span>` : pct(r[k]));
    host.innerHTML = `<thead><tr><th>Area</th><th class="m"><span class="who" style="--c:var(--tfm)">${esc(name)} skill</span></th><th><span class="who" style="--c:var(--seldon)">Seldon skill</span></th>
      <th class="m">In range · ${esc(name)}</th><th>In range · Seldon</th></tr></thead><tbody>` +
      areas.map(([d, n, sub]) => { const a = pick(D, d, model), b = pick(D, d, "seldon");
        return `<tr><td class="area">${n}<small>${sub}</small></td><td class="m">${cell(a, "skill")}</td><td>${cell(b, "skill")}</td><td class="m">${cell(a, "inside")}</td><td>${cell(b, "inside")}</td></tr>`; }).join("") + "</tbody>";
  }

  // The exploded forecast: browsers without scroll-driven animations get --spread from here.
  const engine = $(".explode");
  if (engine && !reduce && !(window.CSS && CSS.supports("animation-timeline: view()"))) {
    const stage = $(".explode__stage", engine);
    const shape = (p) => (p < 0.1 ? 0 : p < 0.42 ? (p - 0.1) / 0.32 : p < 0.68 ? 1 : p < 0.92 ? 1 - (p - 0.68) / 0.24 : 0);
    let ticking = false;
    const update = () => {
      const r = engine.getBoundingClientRect();
      const p = Math.min(1, Math.max(0, -r.top / Math.max(1, r.height - innerHeight)));
      const s = shape(p);
      stage.style.setProperty("--spread", (s * s * (3 - 2 * s)).toFixed(3));
      ticking = false;
    };
    addEventListener("scroll", () => { if (!ticking) { ticking = true; requestAnimationFrame(update); } }, { passive: true });
    update();
  }

  // The terminal preview tilts flat as it reaches the middle of the screen.
  const preview = $(".preview img");
  if (preview && !reduce) {
    let ticking = false;
    const tilt = () => {
      const r = preview.getBoundingClientRect();
      const k = Math.min(1, Math.max(0, (innerHeight - r.top) / (innerHeight * 0.75)));
      preview.style.setProperty("--tilt", (14 * (1 - k)).toFixed(2) + "deg");
      preview.style.setProperty("--scale", (0.95 + 0.05 * k).toFixed(3));
      ticking = false;
    };
    addEventListener("scroll", () => { if (!ticking) { ticking = true; requestAnimationFrame(tilt); } }, { passive: true });
    tilt();
  }

  // ---------- v4: depth and motion ----------

  // Headline, word by word. The words keep their spaces, so copying the heading still reads normally.
  const h1 = $(".hero h1.split");
  if (h1) {
    h1.setAttribute("aria-label", h1.textContent);
    h1.innerHTML = h1.textContent.split(/(\s+)/).map((w, i) => (/^\s+$/.test(w) ? w
      : `<span class="w${/^sealed/i.test(w) ? " hl" : ""}" style="--w:${i / 2}" aria-hidden="true">${esc(w)}</span>`)).join("");
  }

  // The tape glides: two copies side by side, moving half their width, so the loop has no seam.
  const tape = $("#tape");
  if (tape && tape.children.length && !reduce) {
    const items = tape.innerHTML;
    tape.innerHTML = `<div class="run">${items}<span class="copy" aria-hidden="true" style="display:contents">${items}</span></div>`;
    tape.querySelectorAll(".copy a").forEach((a) => a.setAttribute("tabindex", "-1"));
    tape.classList.add("glide");
    tape.style.setProperty("--glide", Math.max(30, tape.children[0].scrollWidth / 2 / 40) + "s");  // about 40px a second
  }

  // Hero field: sample paths fanning out of one point, like a forecast's possible futures. A few dozen
  // lines on a canvas, redrawn only while the hero is on screen and the tab is visible.
  const canvas = $("#hero-field");
  if (canvas && canvas.getContext && !reduce) {
    const ctx = canvas.getContext("2d");
    const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
    let W = 0, H = 0, dpr = 1, paths = [], visible = true, raf = 0, mx = 0, my = 0;
    const N = 46, STEPS = 90;
    const fresh = (k) => {
      const pts = [0], vol = 0.6 + Math.random() * 0.9, drift = (Math.random() - 0.45) * 0.05;
      for (let i = 1; i < STEPS; i++) pts.push(pts[i - 1] + drift + (Math.random() - 0.5) * vol * 0.22);
      return { pts, born: performance.now() - Math.random() * 6000 * (k === undefined ? 1 : 0), life: 5200 + Math.random() * 3800,
        hue: Math.random() < 0.62 ? "--tfm" : Math.random() < 0.6 ? "--seldon" : "--you" };
    };
    const size = () => {
      const r = canvas.getBoundingClientRect(); dpr = Math.min(2, devicePixelRatio || 1);
      W = r.width; H = r.height; canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
    };
    const draw = (now) => {
      raf = 0;
      if (!visible || document.hidden) return;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, W, H);
      const ox = W * 0.02 + mx * 10, oy = H * 0.86 + my * 8, span = W * 0.9, scaleY = H * 0.16;
      const colors = { "--tfm": css("--tfm"), "--seldon": css("--seldon"), "--you": css("--you") };
      paths.forEach((p, k) => {
        const age = (now - p.born) / p.life;
        if (age > 1) { paths[k] = fresh(k); return; }
        const shown = Math.min(1, age * 1.6), fade = age < 0.75 ? 1 : 1 - (age - 0.75) / 0.25;
        const n = Math.max(2, Math.floor(shown * STEPS));
        ctx.beginPath();
        for (let i = 0; i < n; i++) {
          const x = ox + (i / (STEPS - 1)) * span, y = oy - p.pts[i] * scaleY * (0.4 + i / STEPS);
          i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
        }
        ctx.strokeStyle = colors[p.hue]; ctx.globalAlpha = 0.26 * fade; ctx.lineWidth = 1.1; ctx.stroke();
      });
      ctx.globalAlpha = 1; ctx.fillStyle = css("--seal");
      ctx.beginPath(); ctx.arc(ox, oy, 3.5, 0, Math.PI * 2); ctx.fill();
      raf = requestAnimationFrame(draw);
    };
    const kick = () => { if (!raf && visible && !document.hidden) raf = requestAnimationFrame(draw); };
    size(); paths = Array.from({ length: N }, () => fresh());
    addEventListener("resize", () => { size(); kick(); });
    addEventListener("pointermove", (e) => { mx = e.clientX / innerWidth - 0.5; my = e.clientY / innerHeight - 0.5; }, { passive: true });
    document.addEventListener("visibilitychange", kick);
    new IntersectionObserver(([e]) => { visible = e.isIntersecting; kick(); }).observe(canvas);
    kick();
  }

  // The story: the newest finished past forecast, sealed and scored as you scroll through four steps.
  const story = $("#story");
  if (story && D) {
    const svgNS = "http://www.w3.org/2000/svg";
    const mk = (tag, attrs, parent) => { const n = document.createElementNS(svgNS, tag); for (const k in attrs) n.setAttribute(k, attrs[k]); if (parent) parent.appendChild(n); return n; };
    const R = D.replay, f = R && R.forecasts.filter((g) => g.path.every((p) => p[4] !== null)).pop();
    if (!f) { story.hidden = true; }
    else {
      const name = /^timesfm/.test(D.meta.model) ? "TimesFM" : D.meta.model;
      const t = (d) => Date.parse(d);
      const hist = R.history.filter((p) => t(p[0]) <= t(f.origin)).slice(-Math.max(40, 2 * f.path.length));  // enough past to read the trend, the future still a third of the chart
      const path = f.path, n = path.length, inside = path.filter((p) => p[4] >= p[1] && p[4] <= p[3]).length;
      // Drawn at the size it shows, so the labels stay readable on a phone.
      const svgEl = $("#story-chart"), W = Math.round(Math.min(900, Math.max(340, svgEl.getBoundingClientRect().width || 800)));
      const H = Math.round(Math.max(240, W * 0.52)), m = { l: 52, r: 14, t: 18, b: 28 };
      const x0 = t(hist[0][0]), x1 = t(path[n - 1][0]);
      const ys = hist.map((p) => p[1]).concat(path.flatMap((p) => [p[1], p[3], p[4]]));
      let y0 = Math.min(...ys), y1 = Math.max(...ys); const pad = (y1 - y0) * 0.08; y0 -= pad; y1 += pad;
      const sx = (d) => m.l + ((t(d) - x0) / (x1 - x0)) * (W - m.l - m.r), sy = (v) => H - m.b - ((v - y0) / (y1 - y0)) * (H - m.t - m.b);
      const svg = svgEl; svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
      const grid = mk("g", { class: "grid" }, svg);
      const raw = (y1 - y0) / 4, mag = Math.pow(10, Math.floor(Math.log10(raw)));
      const step = [1, 2, 2.5, 5, 10].map((q) => q * mag).find((q) => q >= raw);
      for (let v = Math.ceil(y0 / step) * step; v <= y1; v += step) {
        const y = sy(v);
        mk("line", { x1: m.l, x2: W - m.r, y1: y, y2: y }, grid);
        mk("text", { x: m.l - 8, y: y + 4, "text-anchor": "end" }, svg).textContent = window.WPCharts ? window.WPCharts.fmt.num(v) : Math.round(v);
      }
      const line = (pts) => pts.map((p, i) => (i ? "L" : "M") + sx(p[0]).toFixed(1) + "," + sy(p[1]).toFixed(1)).join("");
      const last = hist[hist.length - 1];
      const cut = sx(last[0]);
      const clip = mk("clipPath", { id: "story-clip" }, mk("defs", {}, svg));
      const reveal = mk("rect", { x: cut, y: 0, width: 0, height: H }, clip);
      const band = [[last[0], last[1], last[1]]].concat(path.map((p) => [p[0], p[1], p[3]]));
      mk("path", { d: band.map((p, i) => (i ? "L" : "M") + sx(p[0]).toFixed(1) + "," + sy(p[2]).toFixed(1)).join("") +
        band.slice().reverse().map((p) => "L" + sx(p[0]).toFixed(1) + "," + sy(p[1]).toFixed(1)).join("") + "Z", fill: "var(--band)", stroke: "var(--tfm)", "stroke-opacity": ".35", "clip-path": "url(#story-clip)" }, svg);
      mk("path", { d: line([[last[0], last[1]]].concat(path.map((p) => [p[0], p[2]]))), fill: "none", stroke: "var(--tfm)", "stroke-width": 2.4, "stroke-dasharray": "6 5", "clip-path": "url(#story-clip)" }, svg);
      const histPath = mk("path", { d: line(hist), fill: "none", stroke: "var(--ink)", "stroke-width": 2, "stroke-linejoin": "round", pathLength: 1, "stroke-dasharray": 1, "stroke-dashoffset": 1 }, svg);
      const cutLine = mk("line", { x1: cut, x2: cut, y1: m.t, y2: H - m.b, stroke: "var(--seal)", "stroke-dasharray": "3 4", opacity: 0 }, svg);
      const sealG = mk("g", { class: "seal-mark", opacity: 0 }, svg);
      mk("circle", { cx: cut, cy: m.t + 22, r: 15, fill: "var(--seal)" }, sealG);
      mk("text", { x: cut, y: m.t + 26, "text-anchor": "middle", style: "fill:var(--on-seal);font-weight:600;font-size:10px" }, sealG).textContent = "SEAL";
      const tag = (x, y, text, cls) => { const g = mk("g", { opacity: 0 }, svg); mk("text", { x, y, class: cls || "" }, g).textContent = text; return g; };
      const seen = tag(m.l + 6, m.t + 12, "what it could see");
      const ahead = tag(cut + 22, H - m.b - 10, "sealed range");
      const score = mk("g", { opacity: 0 }, svg);
      mk("rect", { x: m.l + 8, y: m.t + 4, width: 160, height: 46, rx: 10, fill: "color-mix(in srgb, var(--up) 16%, var(--panel))", stroke: "var(--up)", "stroke-opacity": ".5" }, score);
      mk("text", { x: m.l + 88, y: m.t + 34, "text-anchor": "middle", style: "fill:var(--up);font:600 22px var(--display)" }, score).textContent = `${inside} / ${n} inside`;
      const dots = path.map((p) => mk("circle", { cx: sx(p[0]), cy: sy(p[4]), r: 4, opacity: 0,
        fill: p[4] >= p[1] && p[4] <= p[3] ? "var(--up)" : "var(--down)", stroke: "var(--panel)", "stroke-width": 1.5 }, svg));
      const when = window.WPCharts ? window.WPCharts.fmt.date(t(f.origin)) : f.origin;
      $("#story-name").textContent = R.title;
      $("#story-when").textContent = `${name} · sealed ${when} · ${n} trading days`;
      $("#story-t1").textContent = `On ${when}, ${name} gave a middle guess and an 80% range for each of the next ${n} days, sealed with that date.`;
      $("#story-score").textContent = `${inside} of ${n} days inside the range.`;
      $("#story-t3").textContent = `This is the newest finished window, not a hand-picked one. Every window counts, in the order they happened, and the honest target is 8 in 10.`;
      const steps = [...story.querySelectorAll(".story__steps li")], bar = $("#story-progress"), view = $(".story__view", story);
      const clamp = (v) => Math.min(1, Math.max(0, v)), seg = (p, a, b) => clamp((p - a) / (b - a));
      const ease = (v) => 1 - Math.pow(1 - v, 3);
      const paint = (p) => {
        const a = seg(p, 0.02, 0.22), b = seg(p, 0.28, 0.46), c = seg(p, 0.52, 0.78);
        histPath.setAttribute("stroke-dashoffset", (1 - ease(a)).toFixed(3));
        reveal.setAttribute("width", ((W - m.r - cut) * ease(b)).toFixed(1));
        cutLine.setAttribute("opacity", b > 0 ? 1 : 0);
        sealG.setAttribute("opacity", b > 0.15 ? 1 : 0);
        sealG.style.transform = `scale(${b > 0.15 ? 1 : 1.8})`; sealG.style.transition = reduce ? "none" : "transform .45s var(--ease)";
        const shown = Math.round(c * n);
        dots.forEach((d, i) => d.setAttribute("opacity", i < shown ? 1 : 0));
        seen.setAttribute("opacity", a > 0.5 && p <= 0.8 ? 1 : 0); ahead.setAttribute("opacity", b > 0.6 ? 1 : 0);
        score.setAttribute("opacity", p > 0.8 ? 1 : 0);
        const at = p < 0.25 ? 0 : p < 0.5 ? 1 : p < 0.8 ? 2 : 3;
        steps.forEach((li, i) => { li.classList.toggle("on", i === at); li.classList.toggle("past", i < at); });
        bar.style.setProperty("--p", p.toFixed(3));
      };
      if (reduce) { paint(1); steps.forEach((li) => li.classList.add("on")); }
      else {
        let ticking = false;
        const update = () => {
          ticking = false;
          const r = story.getBoundingClientRect();
          paint(clamp(-r.top / Math.max(1, r.height - innerHeight)));
          view.style.setProperty("--enter", ease(clamp((innerHeight - r.top) / innerHeight)).toFixed(3));
        };
        addEventListener("scroll", () => { if (!ticking) { ticking = true; requestAnimationFrame(update); } }, { passive: true });
        addEventListener("resize", update);
        update();
      }
    }
  }

  // The record in big numbers, counted up once when they come into view. Every figure is from the data file.
  if (D) {
    const opened = (D.opened || []).filter((r) => r[1] === D.meta.model);
    const inside = opened.filter((r) => r[8] !== null && r[8] >= r[5] && r[8] <= r[7]).length;
    const windows = Object.values(D.track || {}).reduce((a, s) => a + s.windows.length, 0);
    const set = (id, v) => { const el = $(id); if (el) { el.dataset.count = v; el.textContent = reduce ? v + (el.dataset.suffix || "") : "0" + (el.dataset.suffix || ""); } };
    set("#n-series", D.series.length); set("#n-windows", windows); set("#n-opened", opened.length);
    set("#n-inside", opened.length ? Math.round((inside / opened.length) * 100) : 0);
    if (!opened.length) { const el = $("#n-inside"); if (el) el.closest(".num").hidden = true; }
    const band = $("#numbers");
    if (band && !reduce) {
      new IntersectionObserver((entries, obs) => {
        if (!entries[0].isIntersecting) return; obs.disconnect();
        band.querySelectorAll("b[data-count]").forEach((el) => {
          const target = +el.dataset.count, start = performance.now(), dur = 1400;
          const tick = (now) => { const k = Math.min(1, (now - start) / dur), v = Math.round(target * (1 - Math.pow(1 - k, 4)));
            el.textContent = v.toLocaleString() + (el.dataset.suffix || ""); if (k < 1) requestAnimationFrame(tick); };
          requestAnimationFrame(tick);
        });
      }, { threshold: 0.4 }).observe(band);
    }
  }

  // Sections rise into place as they scroll in.
  if (!reduce && "IntersectionObserver" in window) {
    const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } }), { rootMargin: "0px 0px -8% 0px" });
    document.querySelectorAll("section.block h2.title, section.block p.intro, section.block .card, .views li, .numbers .num, .credits")
      .forEach((el, i, all) => { el.classList.add("reveal"); el.style.setProperty("--d", String([...el.parentElement.children].indexOf(el) % 6)); io.observe(el); });
  }

  // Spotlight that follows the pointer across cards, and primary buttons that lean towards it.
  document.querySelectorAll(".card, .numbers .num, .views a, .story__view").forEach((el) => el.classList.add("spot"));
  if (matchMedia("(hover: hover)").matches && !reduce) {
    document.addEventListener("pointermove", (e) => {
      const el = e.target.closest && e.target.closest(".spot");
      if (el) { const r = el.getBoundingClientRect(); el.style.setProperty("--mx", e.clientX - r.left + "px"); el.style.setProperty("--my", e.clientY - r.top + "px"); }
    }, { passive: true });
    document.querySelectorAll(".btn.big").forEach((b) => {
      b.classList.add("magnet");
      b.addEventListener("pointermove", (e) => { const r = b.getBoundingClientRect();
        b.style.setProperty("--bx", ((e.clientX - r.left - r.width / 2) * 0.18).toFixed(1) + "px"); b.style.setProperty("--by", ((e.clientY - r.top - r.height / 2) * 0.3).toFixed(1) + "px"); });
      b.addEventListener("pointerleave", () => { b.style.setProperty("--bx", "0px"); b.style.setProperty("--by", "0px"); });
    });
  }

  if ("serviceWorker" in navigator && location.protocol.startsWith("http")) navigator.serviceWorker.register("sw.js").catch(() => {});
})();
