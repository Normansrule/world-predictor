// Share a sealed forecast as a picture: a 1200 x 630 PNG (the size social sites preview) with the
// series, the chance it ends higher, the middle forecast and its 80% range, three months of history
// with the forecast fan, the day it was sealed and the day it will be judged, and where to check it.
// Drawn on a canvas from D.outlook, so it works offline and sends nothing anywhere.
(function () {
  const W = 1200, H = 630;
  const pct = (p) => (p < 0.01 ? "<1%" : p > 0.99 ? ">99%" : Math.round(p * 100) + "%");
  const sp = (v) => (v >= 0 ? "+" : "−") + Math.abs(v * 100).toFixed(1) + "%";
  const day = (s) => new Date(String(s).slice(0, 10) + "T12:00:00Z").toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });

  function colors() {
    const cs = getComputedStyle(document.documentElement), v = (k, d) => (cs.getPropertyValue(k) || "").trim() || d;
    return { bg: v("--bg", "#272c48"), panel: v("--panel", "#30365a"), ink: v("--ink", "#f4f5fc"), ink2: v("--ink-2", "#c6cbe6"),
      line: v("--line", "#464e7a"), tfm: v("--tfm", "#93b6ff"), up: v("--up", "#52ef9d"), down: v("--down", "#ff929e"), seal: v("--seal", "#d9413f") };
  }

  function wrap(ctx, text, x, y, max, lh, lines = 2) {
    const words = String(text).split(/\s+/); let line = "", n = 0;
    for (let i = 0; i < words.length; i++) {
      const test = line ? line + " " + words[i] : words[i];
      if (ctx.measureText(test).width > max && line) {
        if (++n === lines) { ctx.fillText(line.replace(/\s*\S*$/, "") + "…", x, y); return y + lh; }
        ctx.fillText(line, x, y); y += lh; line = words[i];
      } else line = test;
    }
    ctx.fillText(line, x, y); return y + lh;
  }

  function draw(o, url, model) {
    const c = document.createElement("canvas"); c.width = W; c.height = H;
    const ctx = c.getContext("2d"), C = colors();
    ctx.fillStyle = C.bg; ctx.fillRect(0, 0, W, H);
    const g = ctx.createRadialGradient(W * 0.85, 0, 40, W * 0.85, 0, 700); g.addColorStop(0, "rgba(147,182,255,.22)"); g.addColorStop(1, "rgba(147,182,255,0)");
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    const sans = "system-ui, -apple-system, 'Segoe UI', sans-serif";
    // Left: the words.
    ctx.fillStyle = C.ink2; ctx.font = `600 22px ${sans}`; ctx.fillText(`WORLD PREDICTOR · SEALED ${o.made_on}`, 60, 80);
    ctx.fillStyle = C.ink; ctx.font = `700 46px ${sans}`;
    let y = wrap(ctx, o.title, 60, 140, 520, 54);
    ctx.font = `800 120px ${sans}`; ctx.fillStyle = o.p_up >= 0.55 ? C.up : o.p_up <= 0.45 ? C.down : C.ink; ctx.fillText(pct(o.p_up), 56, y + 100);
    ctx.font = `500 26px ${sans}`; ctx.fillStyle = C.ink2;
    ctx.fillText(`chance it ends higher by ${day(o.target_date)}`, 60, y + 146);
    ctx.fillStyle = C.ink; ctx.font = `600 26px ${sans}`;
    ctx.fillText(`Middle ${sp(o.change)} · 80% range ${sp(o.low)} to ${sp(o.high)}`, 60, y + 196);
    ctx.fillStyle = C.ink2; ctx.font = `500 20px ${sans}`;
    ctx.fillText(`Forecast by ${model}, sealed before it happened and scored against reality.`, 60, H - 78);
    ctx.fillText(url, 60, H - 48);
    // Right: three months of history and the fan.
    const x0 = 640, x1 = W - 60, y0 = 110, y1 = H - 140;
    ctx.fillStyle = C.panel; roundRect(ctx, x0 - 24, y0 - 30, x1 - x0 + 48, y1 - y0 + 70, 20); ctx.fill();
    const hist = (o.history || []).slice(-63), fan = o.fan || [];
    const t = (s) => Date.parse(String(s).slice(0, 10));
    const pts = hist.map(([d, v]) => [t(d), v]).concat(fan.flatMap(([d, a, , b]) => [[t(d), a], [t(d), b]]));
    if (pts.length > 1) {
      const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
      const ta = Math.min(...xs), tb = Math.max(...xs), va = Math.min(...ys), vb = Math.max(...ys), pad = (vb - va) * 0.08 || 1;
      const sx = (v) => x0 + (x1 - x0) * (v - ta) / Math.max(1, tb - ta), sy = (v) => y1 - (y1 - y0) * (v - va + pad) / (vb - va + 2 * pad);
      if (fan.length) {
        ctx.fillStyle = "rgba(147,182,255,.28)"; ctx.beginPath();
        fan.forEach(([d, a], i) => (i ? ctx.lineTo(sx(t(d)), sy(a)) : ctx.moveTo(sx(t(d)), sy(a))));
        fan.slice().reverse().forEach(([d, , , b]) => ctx.lineTo(sx(t(d)), sy(b))); ctx.closePath(); ctx.fill();
        ctx.strokeStyle = C.tfm; ctx.lineWidth = 3; ctx.setLineDash([8, 6]); ctx.beginPath();
        fan.forEach(([d, , m], i) => (i ? ctx.lineTo(sx(t(d)), sy(m)) : ctx.moveTo(sx(t(d)), sy(m)))); ctx.stroke(); ctx.setLineDash([]);
      }
      ctx.strokeStyle = C.ink; ctx.lineWidth = 3; ctx.beginPath();
      hist.forEach(([d, v], i) => (i ? ctx.lineTo(sx(t(d)), sy(v)) : ctx.moveTo(sx(t(d)), sy(v)))); ctx.stroke();
      const last = hist[hist.length - 1];
      if (last) { ctx.fillStyle = C.seal; ctx.beginPath(); ctx.arc(sx(t(last[0])), sy(last[1]), 7, 0, 7); ctx.fill(); }
      ctx.fillStyle = C.ink2; ctx.font = `500 18px ${sans}`;
      ctx.fillText("Last three months", x0, y1 + 30);
      ctx.textAlign = "right"; ctx.fillText("80% range ahead", x1, y1 + 30); ctx.textAlign = "left";
    }
    return c;
  }

  function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
  }

  // Saves the card; on a phone that can share files, offers the share sheet instead.
  async function save(o, D) {
    const model = /^timesfm/.test(D.meta.model) ? "TimesFM" : D.meta.model;
    const url = (D.meta.repo && /normansrule/i.test(D.meta.repo) ? "normansrule.github.io/world-predictor" : location.host || "World Predictor") + `/app/#series/${o.id}`;
    const canvas = draw(o, url, model);
    const blob = await new Promise((r) => canvas.toBlob(r, "image/png"));
    const name = `world-predictor-${o.id}-${o.made_on}.png`;
    try {
      const file = new File([blob], name, { type: "image/png" });
      if (navigator.canShare && navigator.canShare({ files: [file] })) { await navigator.share({ files: [file], title: o.title }); return "shared"; }
    } catch (e) { /* fall back to a download */ }
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = name;
    document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500);
    return "saved";
  }

  window.WPShare = { draw, save };
})();
