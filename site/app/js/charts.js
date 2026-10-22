// Tiny SVG chart kit for World Predictor: line/fan charts, grouped bars, and a hover readout.
// No dependencies, so the app stays a few tens of kilobytes and works offline from disk.
(function () {
  const NS = "http://www.w3.org/2000/svg";
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  let uid = 0;

  function el(tag, attrs, parent) {
    const node = document.createElementNS(NS, tag);
    for (const k in attrs || {}) if (attrs[k] !== undefined && attrs[k] !== null) node.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(node);
    return node;
  }

  // "Nice" tick values covering [lo, hi].
  function ticks(lo, hi, count) {
    if (!isFinite(lo) || !isFinite(hi)) return [];
    if (lo === hi) { lo -= 1; hi += 1; }
    const span = hi - lo, raw = span / Math.max(1, count);
    const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => span / s <= count) || 10 * mag;
    const out = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) out.push(+v.toFixed(10));
    return out;
  }

  const toTime = (d) => (typeof d === "number" ? d : Date.parse(d));
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  function dateTicks(lo, hi, count) {
    const day = 864e5, span = (hi - lo) / day, out = [];
    if (span > 500) {
      const start = new Date(lo); let y = start.getUTCFullYear() + 1, stepY = Math.max(1, Math.round(span / 365 / count));
      for (; Date.UTC(y, 0, 1) <= hi; y += stepY) out.push([Date.UTC(y, 0, 1), String(y)]);
    } else if (span > 60) {
      const stepM = Math.max(1, Math.round(span / 30 / count));
      const d = new Date(lo); let y = d.getUTCFullYear(), m = d.getUTCMonth() + 1;
      for (; Date.UTC(y, m, 1) <= hi; m += stepM) {
        const t = Date.UTC(y, m, 1), dd = new Date(t);
        out.push([t, MONTHS[dd.getUTCMonth()] + (dd.getUTCMonth() === 0 ? " " + dd.getUTCFullYear() : "")]);
      }
    } else {
      const stepD = Math.max(1, Math.round(span / count));
      for (let t = lo; t <= hi; t += stepD * day) { const dd = new Date(t); out.push([t, MONTHS[dd.getUTCMonth()] + " " + dd.getUTCDate()]); }
    }
    return out;
  }

  const fmt = {
    pct: (v) => (v === null || v === undefined ? "–" : (v * 100).toFixed(Math.abs(v) < 0.1 ? 1 : 0) + "%"),
    signedPct: (v) => (v === null || v === undefined ? "–" : Math.abs(v) < 0.0005 ? "0.0%" : (v > 0 ? "+" : "−") + Math.abs(v * 100).toFixed(1) + "%"),
    num: (v) => {
      if (v === null || v === undefined) return "–";
      const a = Math.abs(v);
      if (a >= 1e6) return (v / 1e6).toFixed(1) + "M";
      if (a >= 1e4) return (v / 1e3).toFixed(0) + "k";
      if (a >= 100) return v.toFixed(0);
      if (a >= 1) return v.toFixed(2).replace(/\.?0+$/, "");
      return v.toPrecision(2);
    },
    date: (t) => { const d = new Date(t); return MONTHS[d.getUTCMonth()] + " " + d.getUTCDate() + ", " + d.getUTCFullYear(); },
  };

  /**
   * plot(container, spec): an XY chart.
   * spec.lines: [{points: [[x, y]], color, width, dash, name, label, draw, delay}]
   *   label: written at the line's last point (direct labelling instead of a legend)
   *   draw / delay: trace this line in now, after ``delay`` seconds, even on a redraw
   * spec.bands: [{points: [[x, lo, hi]], color, stroke, edge, fade, delay}]   (forecast ranges)
   *   stroke: colour of the hatching; edge: dash pattern for an outline of the range
   * spec.dots:  [{points: [[x, y]], color, r, name}]
   * spec.refs:  [{y, label, color}] or [{x, label}]       (dashed reference lines)
 * spec.spans: [{from, to, color, label}]               (shaded stretch of the x axis)
 * spec.marks: [{x, y, color}]                           (a ring around one selected point)
 * spec.onPick(point): called with the nearest {x, y, name} when the chart is clicked
   * spec.x: "date" | "num"; spec.yFormat: fn; spec.yDomain / spec.xDomain: [lo, hi]
   */
  function plot(container, spec) {
    container.innerHTML = "";
    container.classList.add("chart");
    const width = Math.max(260, container.clientWidth || 600);
    const height = spec.height || Math.round(Math.min(420, Math.max(200, width * 0.45)));
    const m = { t: 12, r: spec.right || 16, b: spec.x === "date" ? 26 : 34, l: spec.left || 48 };
    const isDate = spec.x === "date";
    const X = (v) => (isDate ? toTime(v) : v);
    let xs = [], ys = [];
    (spec.lines || []).forEach((s) => s.points.forEach((p) => { xs.push(X(p[0])); ys.push(p[1]); }));
    (spec.bands || []).forEach((s) => s.points.forEach((p) => { xs.push(X(p[0])); ys.push(p[1], p[2]); }));
    (spec.dots || []).forEach((s) => s.points.forEach((p) => { xs.push(X(p[0])); ys.push(p[1]); }));
    (spec.refs || []).forEach((r) => (r.y !== undefined ? ys.push(r.y) : xs.push(X(r.x))));
    xs = xs.filter((v) => v !== null && isFinite(v)); ys = ys.filter((v) => v !== null && isFinite(v));
    if (!xs.length) { container.innerHTML = '<div class="empty">No data yet.</div>'; return; }
    let [x0, x1] = spec.xDomain ? spec.xDomain.map(X) : [Math.min(...xs), Math.max(...xs)];
    let [y0, y1] = spec.yDomain || [Math.min(...ys), Math.max(...ys)];
    if (!spec.yDomain) { const pad = (y1 - y0 || Math.abs(y1) || 1) * 0.06; y0 -= pad; y1 += pad; }
    if (x0 === x1) { x0 -= 1; x1 += 1; }
    const sx = (v) => m.l + ((X(v) - x0) / (x1 - x0)) * (width - m.l - m.r);
    const sy = (v) => height - m.b - ((v - y0) / (y1 - y0)) * (height - m.t - m.b);
    const svg = el("svg", { viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": spec.label || "chart" }, container);
    // Animate only the first drawing of a chart, so sliders and resizes redraw instantly.
    const animate = spec.animate === true || (spec.animate !== false && !container.dataset.drawn);
    container.dataset.drawn = "1";
    const defs = el("defs", {}, svg);
    const hatch = (color) => {
      const id = "wp-hatch-" + (++uid);
      const pattern = el("pattern", { id, width: 6, height: 6, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)", class: "hatch" }, defs);
      el("line", { x1: 0, y1: 0, x2: 0, y2: 6, stroke: color }, pattern);
      return id;
    };
    const delayed = (s) => (s.delay !== undefined ? `--delay:${s.delay}s` : undefined);

    const grid = el("g", { class: "grid" }, svg);
    const yf = spec.yFormat || fmt.num;
    ticks(y0, y1, spec.yTicks || 5).forEach((v) => {
      if (v < y0 || v > y1) return;
      el("line", { x1: m.l, x2: width - m.r, y1: sy(v), y2: sy(v), class: v === 0 && y0 < 0 ? "zero" : undefined }, grid);
      el("text", { x: m.l - 8, y: sy(v) + 4, "text-anchor": "end" }, svg).textContent = yf(v);
    });
    const xt = isDate ? dateTicks(x0, x1, Math.max(2, Math.floor(width / 110)))
      : ticks(x0, x1, Math.max(2, Math.floor(width / 80))).map((v) => [v, (spec.xFormat || fmt.num)(v)]);
    xt.forEach(([v, label]) => {
      if (v < x0 || v > x1) return;
      el("text", { x: sx(v), y: height - m.b + 16, "text-anchor": "middle" }, svg).textContent = label;
    });
    if (spec.xTitle) el("text", { x: (m.l + width - m.r) / 2, y: height - 2, "text-anchor": "middle" }, svg).textContent = spec.xTitle;

    (spec.spans || []).forEach((s) => {
      const a = sx(s.from), b = sx(s.to);
      el("rect", { x: Math.min(a, b), y: m.t, width: Math.max(1, Math.abs(b - a)), height: height - m.t - m.b,
        fill: s.color || "var(--glow)", rx: 6, class: "span" }, svg);
      if (s.label) el("text", { x: Math.min(a, b) + 6, y: height - m.b - 8, class: "span-label" }, svg).textContent = s.label;
    });
    (spec.bands || []).forEach((b) => {
      const pts = b.points.filter((p) => p[1] !== null && p[2] !== null);
      if (!pts.length) return;
      const d = pts.map((p, i) => (i ? "L" : "M") + sx(p[0]).toFixed(1) + "," + sy(p[2]).toFixed(1)).join("")
        + pts.slice().reverse().map((p) => "L" + sx(p[0]).toFixed(1) + "," + sy(p[1]).toFixed(1)).join("") + "Z";
      const cls = b.fade || (animate && b.fade !== false) ? "fade" : undefined, style = delayed(b);
      el("path", { d, fill: b.color || "var(--band)", stroke: "none", class: cls, style }, svg);
      if (b.hatch !== false) el("path", { d, fill: `url(#${hatch(b.stroke || "var(--tfm)")})`, stroke: "none", class: cls, style }, svg);
      if (b.edge) {
        const edge = (k) => pts.map((p, i) => (i ? "L" : "M") + sx(p[0]).toFixed(1) + "," + sy(p[k]).toFixed(1)).join("");
        [1, 2].forEach((k) => el("path", { d: edge(k), fill: "none", stroke: b.stroke, "stroke-width": 1.2, "stroke-dasharray": b.edge, class: cls, style }, svg));
      }
    });
    (spec.refs || []).forEach((r) => {
      const color = r.color || "var(--muted)";
      if (r.y !== undefined) {
        el("line", { class: "ref", x1: m.l, x2: width - m.r, y1: sy(r.y), y2: sy(r.y), stroke: color }, svg);
        if (r.label) el("text", { x: width - m.r, y: sy(r.y) - 5, "text-anchor": "end", style: `fill:${color}` }, svg).textContent = r.label;
      } else {
        el("line", { class: "ref", x1: sx(r.x), x2: sx(r.x), y1: m.t, y2: height - m.b, stroke: color }, svg);
        if (r.label) el("text", { x: sx(r.x) + 4, y: m.t + 10, style: `fill:${color}` }, svg).textContent = r.label;
      }
    });
    const endLabels = [];
    (spec.lines || []).forEach((s) => {
      const pts = s.points.filter((p) => p[1] !== null && p[1] !== undefined);
      if (!pts.length) return;
      const d = pts.map((p, i) => (i ? "L" : "M") + sx(p[0]).toFixed(1) + "," + sy(p[1]).toFixed(1)).join("");
      const draw = s.draw || (animate && !s.dash && s.draw !== false);
      el("path", { d, fill: "none", stroke: s.color, "stroke-width": s.width || 2, "stroke-dasharray": s.dash,
        "stroke-linejoin": "round", "stroke-linecap": "round", opacity: s.opacity,
        class: draw ? "draw" : undefined, pathLength: draw ? 1 : undefined, style: delayed(s) }, svg);
      if (s.label) {
        const p = pts[pts.length - 1];
        endLabels.push(el("text", { x: sx(p[0]) + 6, y: sy(p[1]) + 4, class: "end" + (draw ? " fade" : ""), style: `fill:${s.color};${delayed(s) || ""}` }, svg));
        endLabels[endLabels.length - 1].textContent = s.label;
      }
    });
    // Direct labels that would overlap are nudged apart, keeping their order.
    endLabels.sort((a, b) => a.getAttribute("y") - b.getAttribute("y"));
    for (let i = 1; i < endLabels.length; i++) {
      const prev = +endLabels[i - 1].getAttribute("y");
      if (+endLabels[i].getAttribute("y") < prev + 14) endLabels[i].setAttribute("y", prev + 14);
    }
    (spec.dots || []).forEach((s) => {
      s.points.forEach((p) => {
        if (p[1] === null || p[1] === undefined) return;
        el("circle", { cx: sx(p[0]), cy: sy(p[1]), r: s.r || 3, fill: s.color, stroke: s.stroke, "stroke-width": s.stroke ? 2 : undefined,
          class: s.fade ? "fade" : undefined, style: delayed(s) }, svg);
      });
    });

    (spec.marks || []).forEach((k) => {
      if (k.y === null || k.y === undefined) return;
      el("circle", { cx: sx(k.x), cy: sy(k.y), r: 7, fill: "none", stroke: k.color || "var(--text)", "stroke-width": 2, class: "mark" }, svg);
    });

    // Hover readout along the first line (or the dots when there are no lines).
    const hoverSrc = (spec.lines || []).concat(spec.dots || []).filter((s) => s.points.length);
    const all = [];
    hoverSrc.forEach((s) => s.points.forEach((p) => { if (p[1] !== null && p[1] !== undefined) all.push({ x: X(p[0]), y: p[1], s }); }));
    const nearest = (ev) => {
      const r = svg.getBoundingClientRect(), px = ((ev.clientX - r.left) / r.width) * width;
      const xv = x0 + ((px - m.l) / (width - m.l - m.r)) * (x1 - x0);
      let best = null;
      all.forEach((a) => { if (!best || Math.abs(a.x - xv) < Math.abs(best.x - xv)) best = a; });
      return best;
    };
    if (spec.onPick) {
      svg.style.cursor = "pointer";
      svg.addEventListener("click", (ev) => { const b = nearest(ev); if (b) spec.onPick({ x: b.x, y: b.y, name: b.s.name }); });
    }
    if (spec.hover !== false && hoverSrc.length) {
      const tip = document.createElement("div"); tip.className = "tip"; container.appendChild(tip);
      const cross = el("line", { y1: m.t, y2: height - m.b, stroke: "var(--ink-2)", "stroke-width": 1, "stroke-dasharray": "2 3", opacity: 0 }, svg);
      svg.addEventListener("pointermove", (ev) => {
        const best = nearest(ev);
        if (!best) return;
        const near = all.filter((a) => a.x === best.x);
        const label = (isDate ? fmt.date(best.x) : (spec.xFormat || fmt.num)(best.x)) + "  " +
          near.map((a) => (a.s.name ? a.s.name + ": " : "") + yf(a.y)).join(" · ");
        tip.textContent = label;
        tip.style.left = (sx(best.x) / width) * 100 + "%";
        tip.style.top = (sy(best.y) / height) * 100 + "%";
        tip.style.opacity = 1; cross.setAttribute("x1", sx(best.x)); cross.setAttribute("x2", sx(best.x)); cross.setAttribute("opacity", 0.4);
      });
      svg.addEventListener("pointerleave", () => { tip.style.opacity = 0; cross.setAttribute("opacity", 0); });
    }
    const inv = (py) => y0 + ((height - m.b - py) / (height - m.t - m.b)) * (y1 - y0);
    return { svg, sx, sy, inv, m, width, height, y0, y1 };
  }

  /** bars(container, {groups: [label], series: [{name, color, values: [v per group]}], yFormat}) */
  function bars(container, spec) {
    container.innerHTML = ""; container.classList.add("chart");
    const width = Math.max(260, container.clientWidth || 600), height = spec.height || 300;
    const m = { t: 12, r: 12, b: 30, l: 52 };
    const vals = spec.series.flatMap((s) => s.values).filter((v) => v !== null && isFinite(v)).concat([0]);
    let y0 = Math.min(...vals), y1 = Math.max(...vals); const pad = (y1 - y0 || 1) * 0.12; y0 -= y0 < 0 ? pad : 0; y1 += pad;
    const sy = (v) => height - m.b - ((v - y0) / (y1 - y0)) * (height - m.t - m.b);
    const svg = el("svg", { viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": spec.label || "bar chart" }, container);
    const animate = spec.animate !== false && !container.dataset.drawn;
    container.dataset.drawn = "1";
    const grid = el("g", { class: "grid" }, svg), yf = spec.yFormat || fmt.num;
    ticks(y0, y1, 5).forEach((v) => {
      el("line", { x1: m.l, x2: width - m.r, y1: sy(v), y2: sy(v) }, grid);
      el("text", { x: m.l - 8, y: sy(v) + 4, "text-anchor": "end" }, svg).textContent = yf(v);
    });
    el("line", { x1: m.l, x2: width - m.r, y1: sy(0), y2: sy(0), stroke: "var(--ink-2)" }, svg);
    const gw = (width - m.l - m.r) / spec.groups.length, n = spec.series.length;
    const bw = Math.min(42, (gw * 0.72) / n);
    const tip = document.createElement("div"); tip.className = "tip"; container.appendChild(tip);
    spec.groups.forEach((g, gi) => {
      const cx = m.l + gw * (gi + 0.5);
      el("text", { x: cx, y: height - 10, "text-anchor": "middle" }, svg).textContent = g;
      spec.series.forEach((s, si) => {
        const v = s.values[gi]; if (v === null || v === undefined) return;
        const x = cx - (n * bw) / 2 + si * bw + 1, y = Math.min(sy(v), sy(0)), h = Math.max(1, Math.abs(sy(v) - sy(0)));
        const rect = el("rect", { x, y, width: bw - 2, height: h, rx: 1, fill: s.color,
          class: animate ? "grow" : undefined, style: `transform-origin: 0 ${sy(0)}px; --k: ${gi * n + si}` }, svg);
        rect.addEventListener("pointerenter", () => {
          tip.textContent = `${g} · ${s.name}: ${yf(v)}`; tip.style.left = ((x + bw / 2) / width) * 100 + "%";
          tip.style.top = (y / height) * 100 + "%"; tip.style.opacity = 1;
        });
        rect.addEventListener("pointerleave", () => (tip.style.opacity = 0));
      });
    });
  }

  function legend(container, items) {
    const box = document.createElement("div"); box.className = "legend";
    items.forEach((it) => {
      const s = document.createElement("span"); s.textContent = it.name; s.style.setProperty("--c", it.color);
      if (it.kind) s.classList.add(it.kind); box.appendChild(s);
    });
    container.appendChild(box);
  }

  // One small icon set, drawn in a single 2px stroke so every control matches.
  const ICONS = {
    play: '<path d="M7 4.5v15l12-7.5z" fill="currentColor" stroke="none"/>',
    pause: '<path d="M8 5v14M16 5v14"/>',
    restart: '<path d="M4 12a8 8 0 1 0 2.4-5.7"/><path d="M4 4v4.5h4.5"/>',
    prev: '<path d="M15 5l-7 7 7 7"/>',
    next: '<path d="M9 5l7 7-7 7"/>',
    shuffle: '<path d="M4 7h3.5c4 0 5 10 9 10H20"/><path d="M4 17h3.5c1.6 0 2.7-1.6 3.6-3.5"/><path d="M13 9.5c.9-1.4 2-2.5 3.5-2.5H20"/><path d="M17.5 4.5 20 7l-2.5 2.5"/><path d="M17.5 14.5 20 17l-2.5 2.5"/>',
  };
  const icon = (name) => `<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICONS[name]}</svg>`;

  // Seldon's council (src/psychohistory/seldon.py): which laws it trusted for one forecast.
  const LAW_TEXT = { inertia: "inertia", drift: "drift", momentum: "momentum", reversion: "reversion" };
  function council(c) {
    if (!c) return "Seldon is our own forecaster: four laws of crowd behaviour voting by how well each predicted this series before, plus its weekly rhythm.";
    if (!c.replays) return "Seldon had too little history to replay here, so every law got an equal vote.";
    const votes = Object.entries(c.weights).sort((a, b) => b[1] - a[1]).map(([k, w]) => `${LAW_TEXT[k] || k} ${Math.round(w * 100)}%`).join(", ");
    const mood = c.vol < 0.95 ? "calmer than usual, so its range is narrower" : c.vol > 1.05 ? "wilder than usual, so its range is wider" : "about as calm as usual";
    const rhythm = c.cycle ? `, with the weekly rhythm laid on top` : "";
    return `Seldon replayed ${c.replays} earlier dates of this series and split its vote: ${votes}${rhythm}. Right now the series is ${mood} (${c.vol.toFixed(2)}×).`;
  }
  function councilBar(c) {
    if (!c || !c.weights) return "";
    const parts = Object.entries(c.weights).sort((a, b) => b[1] - a[1]);
    return `<span class="council" role="img" aria-label="${esc(council(c))}">` + parts.map(([k, w], i) =>
      `<i style="--w:${(w * 100).toFixed(1)}%;--o:${(1 - i * 0.17).toFixed(2)}" title="${esc(LAW_TEXT[k] || k)} ${Math.round(w * 100)}%"><b>${esc(LAW_TEXT[k] || k)}</b></i>`).join("") + "</span>";
  }
  function esc(s) { return String(s).replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch])); }

  window.WPCharts = { plot, bars, legend, fmt, css, icon, council, councilBar };
})();
