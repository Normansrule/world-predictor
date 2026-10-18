// Tiny SVG chart kit for World Predictor: line/fan charts, grouped bars, and a hover readout.
// No dependencies, so the app stays a few tens of kilobytes and works offline from disk.
(function () {
  const NS = "http://www.w3.org/2000/svg";
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

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
    signedPct: (v) => (v === null || v === undefined ? "–" : (v >= 0 ? "+" : "−") + Math.abs(v * 100).toFixed(1) + "%"),
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
   * spec.lines: [{points: [[x, y]], color, width, dash, name}]
   * spec.bands: [{points: [[x, lo, hi]], color}]          (forecast ranges)
   * spec.dots:  [{points: [[x, y]], color, r, name}]
   * spec.refs:  [{y, label, color}] or [{x, label}]       (dashed reference lines)
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

    const grid = el("g", { class: "grid" }, svg);
    const yf = spec.yFormat || fmt.num;
    ticks(y0, y1, spec.yTicks || 5).forEach((v) => {
      if (v < y0 || v > y1) return;
      el("line", { x1: m.l, x2: width - m.r, y1: sy(v), y2: sy(v) }, grid);
      el("text", { x: m.l - 8, y: sy(v) + 4, "text-anchor": "end" }, svg).textContent = yf(v);
    });
    const xt = isDate ? dateTicks(x0, x1, Math.max(2, Math.floor(width / 110)))
      : ticks(x0, x1, Math.max(2, Math.floor(width / 80))).map((v) => [v, (spec.xFormat || fmt.num)(v)]);
    xt.forEach(([v, label]) => {
      if (v < x0 || v > x1) return;
      el("text", { x: sx(v), y: height - m.b + 16, "text-anchor": "middle" }, svg).textContent = label;
    });
    if (spec.xTitle) el("text", { x: (m.l + width - m.r) / 2, y: height - 2, "text-anchor": "middle" }, svg).textContent = spec.xTitle;

    (spec.bands || []).forEach((b) => {
      const pts = b.points.filter((p) => p[1] !== null && p[2] !== null);
      if (!pts.length) return;
      const d = pts.map((p, i) => (i ? "L" : "M") + sx(p[0]).toFixed(1) + "," + sy(p[2]).toFixed(1)).join("")
        + pts.slice().reverse().map((p) => "L" + sx(p[0]).toFixed(1) + "," + sy(p[1]).toFixed(1)).join("") + "Z";
      el("path", { d, fill: b.color || "var(--band)", stroke: "none" }, svg);
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
    (spec.lines || []).forEach((s) => {
      const pts = s.points.filter((p) => p[1] !== null && p[1] !== undefined);
      if (!pts.length) return;
      const d = pts.map((p, i) => (i ? "L" : "M") + sx(p[0]).toFixed(1) + "," + sy(p[1]).toFixed(1)).join("");
      el("path", { d, fill: "none", stroke: s.color, "stroke-width": s.width || 2, "stroke-dasharray": s.dash,
        "stroke-linejoin": "round", "stroke-linecap": "round", opacity: s.opacity }, svg);
    });
    (spec.dots || []).forEach((s) => {
      s.points.forEach((p) => {
        if (p[1] === null || p[1] === undefined) return;
        el("circle", { cx: sx(p[0]), cy: sy(p[1]), r: s.r || 3, fill: s.color, stroke: s.stroke, "stroke-width": s.stroke ? 2 : undefined }, svg);
      });
    });

    // Hover readout along the first line (or the dots when there are no lines).
    const hoverSrc = (spec.lines || []).concat(spec.dots || []).filter((s) => s.points.length);
    if (spec.hover !== false && hoverSrc.length) {
      const tip = document.createElement("div"); tip.className = "tip"; container.appendChild(tip);
      const cross = el("line", { y1: m.t, y2: height - m.b, stroke: "var(--muted)", "stroke-width": 1, opacity: 0 }, svg);
      const all = [];
      hoverSrc.forEach((s) => s.points.forEach((p) => { if (p[1] !== null) all.push({ x: X(p[0]), y: p[1], s }); }));
      svg.addEventListener("pointermove", (ev) => {
        const r = svg.getBoundingClientRect(), px = ((ev.clientX - r.left) / r.width) * width;
        const xv = x0 + ((px - m.l) / (width - m.l - m.r)) * (x1 - x0);
        let best = null;
        all.forEach((a) => { if (!best || Math.abs(a.x - xv) < Math.abs(best.x - xv)) best = a; });
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
    return { svg, sx, sy };
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
    const grid = el("g", { class: "grid" }, svg), yf = spec.yFormat || fmt.num;
    ticks(y0, y1, 5).forEach((v) => {
      el("line", { x1: m.l, x2: width - m.r, y1: sy(v), y2: sy(v) }, grid);
      el("text", { x: m.l - 8, y: sy(v) + 4, "text-anchor": "end" }, svg).textContent = yf(v);
    });
    el("line", { x1: m.l, x2: width - m.r, y1: sy(0), y2: sy(0), stroke: "var(--muted)" }, svg);
    const gw = (width - m.l - m.r) / spec.groups.length, n = spec.series.length;
    const bw = Math.min(42, (gw * 0.72) / n);
    const tip = document.createElement("div"); tip.className = "tip"; container.appendChild(tip);
    spec.groups.forEach((g, gi) => {
      const cx = m.l + gw * (gi + 0.5);
      el("text", { x: cx, y: height - 10, "text-anchor": "middle" }, svg).textContent = g;
      spec.series.forEach((s, si) => {
        const v = s.values[gi]; if (v === null || v === undefined) return;
        const x = cx - (n * bw) / 2 + si * bw + 1, y = Math.min(sy(v), sy(0)), h = Math.max(1, Math.abs(sy(v) - sy(0)));
        const rect = el("rect", { x, y, width: bw - 2, height: h, rx: 3, fill: s.color }, svg);
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

  window.WPCharts = { plot, bars, legend, fmt, css };
})();
