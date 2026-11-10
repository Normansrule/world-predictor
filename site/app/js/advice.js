// What the odds suggest, and whether that has ever worked. A market forecast's chance of ending higher
// reads as a lean: 60% or more leans "buy or keep holding", 40% or less leans "sell now and buy back
// lower later", anything between is no lean. Before that lean is shown as advice, it is checked
// against the record: every backtest window on every market where the forecast leaned the same way,
// and how often the market really went that way. Only a lean that was right clearly more often than a
// coin flip (one-sided binomial test, p < 0.05, at least 20 windows) is passed on; otherwise the advice
// is "hold", and the card says why. Research, not financial advice.
(function () {
  const BUY = 0.6, SELL = 0.4, MIN = 20, ALPHA = 0.05;

  const tierOf = (p) => (p === null || p === undefined ? null : p >= BUY ? "buy" : p <= SELL ? "sell" : "hold");

  // P(X >= k) for X ~ Binomial(n, 1/2), summed in logs so large n stays exact enough.
  function binomTail(k, n) {
    if (k <= 0) return 1;
    let lf = [0]; for (let i = 1; i <= n; i++) lf[i] = lf[i - 1] + Math.log(i);
    let s = 0; for (let i = k; i <= n; i++) s += Math.exp(lf[n] - lf[i] - lf[n - i] - n * Math.LN2);
    return Math.min(1, s);
  }

  // Every market backtest window of the run's model: the chance higher it gave and what really happened.
  function windows(D) {
    const markets = new Set((D.series || []).filter((s) => s.domain === "markets").map((s) => s.id));
    const out = [];
    markets.forEach((id) => {
      const T = (D.track || {})[id]; if (!T) return;
      const ev = Object.fromEntries(((D.evidence || {})[id] || []).map((r) => [r[0], r]));
      T.windows.forEach(([origin, at, , q50]) => {
        const p = (ev[origin] || [])[3], n = q50.length, before = at > 0 ? T.actual[at - 1] : null, end = T.actual[at + n - 1];
        if (p === null || p === undefined || !before || end === null || end === undefined) return;
        out.push({ id, p, move: end / before - 1 });
      });
    });
    return out;
  }

  // The record of each lean: how many windows, how many went the way it leaned, the average move, and
  // whether that beats a coin flip. Cached per data object.
  function record(D) {
    if (record.D === D) return record.R;
    const W = windows(D), all = W.length ? W.reduce((t, w) => t + w.move, 0) / W.length : null;
    const R = { n: W.length, allMove: all, horizon: null };
    ["buy", "hold", "sell"].forEach((t) => {
      const ws = W.filter((w) => tierOf(w.p) === t);
      const right = t === "sell" ? ws.filter((w) => w.move < 0).length : ws.filter((w) => w.move > 0).length;
      const p = t === "hold" ? null : binomTail(right, ws.length);
      R[t] = { n: ws.length, right, move: ws.length ? ws.reduce((s, w) => s + w.move, 0) / ws.length : null, p, works: t !== "hold" && ws.length >= MIN && p < ALPHA };
    });
    record.D = D; record.R = R;
    return R;
  }

  // The advice for one chance-higher figure on a market: the lean, the record behind it, and what to do.
  function advise(D, pUp) {
    const tier = tierOf(pUp); if (!tier) return null;
    const R = record(D), r = R[tier];
    const lean = { buy: "Buy or keep holding", hold: "No lean either way", sell: "Sell now, buy back lower later" }[tier];
    const action = tier === "hold" ? "Hold" : r.works ? lean : "Hold";
    return { tier, lean, action, backed: tier !== "hold" && r.works, record: r, all: R };
  }

  const pc = (v) => (v === null || v === undefined ? "–" : (v >= 0 ? "+" : "−") + Math.abs(v * 100).toFixed(1) + "%");

  // One sentence on why: what the record says about this lean.
  function why(a) {
    if (!a) return "";
    const r = a.record;
    if (a.tier === "hold") return `The chance is between ${SELL * 100}% and ${BUY * 100}%, so the forecast does not lean either way.`;
    const way = a.tier === "buy" ? "rose" : "fell";
    if (!r.n) return "There is no backtest record for this lean yet, so the advice stays at hold.";
    const rate = Math.round((r.right / r.n) * 100);
    return a.backed
      ? `When the forecast was this sure, the market ${way} ${r.right} of ${r.n} times (${rate}%), more often than chance would give.`
      : `When the forecast was this sure, the market ${way} only ${r.right} of ${r.n} times (${rate}%)${r.n < MIN ? ", too few to trust" : rate < 50 ? ", less often than a coin flip" : ", not clearly better than a coin flip"}, so the advice stays at hold.`;
  }

  window.WPAdvice = { advise, record, tierOf, why, binomTail, pc, BUY, SELL, MIN, ALPHA };
})();
