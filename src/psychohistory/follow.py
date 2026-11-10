"""Would following the forecasts have made money?

A forecast can be well calibrated and still be no use to trade on. This module replays the simplest
way to act on the Markets desk: at every backtest origin, hold a market if the forecaster gave it
better than even odds of ending higher at the horizon, and stay in cash otherwise ("follow"); or go
short when it said lower ("long/short"). Every trade pays a cost each way. The yardstick is holding
every market the whole time ("hold"), the same equal-weight basket.

Everything is read from the backtest's saved paths, so no forecast saw the window it is judged on.
The odds threshold is also tested out of sample: chosen on the first half of the origins only, then
judged on the second half, so a lucky threshold cannot flatter the result.

Testing a trading rule with costs, and choosing its settings on training windows only, follows the
research lab of Vibe-Trading (HKUDS, MIT licence); the code here is our own. Research, not advice.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import catalog, events

COST = 0.001                 # 0.1% each way: a liquid ETF or future through a cheap broker
STEPS = (5, 20)              # a week and a month of trading days
MODELS = ("radiant", "timesfm-2.5", "seldon", "chronos-bolt")
THRESHOLDS = (0.5, 0.55, 0.6)
T_EDGE = 2.0                 # |t| a difference must reach before it is called more than luck


def windows(paths: pd.DataFrame | None, data: dict[str, pd.Series] | None = None,
            domains: dict[str, str] | None = None, steps=STEPS, models=MODELS) -> pd.DataFrame:
    """One row per market window: the forecaster's chance of a rise and what the market did."""
    cols = ["series_id", "model", "origin", "step", "last", "p_up", "ret"]
    if paths is None or paths.empty:
        return pd.DataFrame(columns=cols)
    domains = domains or {s.id: s.domain for s in catalog.CATALOG}
    p = paths[paths["series_id"].map(domains).eq("markets") & paths["step"].isin(steps) & paths["model"].isin(models)].copy()
    if p.empty:
        return pd.DataFrame(columns=cols)
    # The close on the origin day: from the data when we have it, else from an earlier window's actual.
    seen = paths[paths["series_id"].isin(p["series_id"].unique())].drop_duplicates(["series_id", "date"]).set_index(["series_id", "date"])["actual"]

    def last(sid, origin):
        s = (data or {}).get(sid)
        if s is not None and len(s):
            v = s[s.index <= pd.Timestamp(origin)]
            if len(v):
                return float(v.iloc[-1])
        return seen.get((sid, str(origin)[:10]), np.nan)
    keys = {(s, o): last(s, o) for s, o in p[["series_id", "origin"]].drop_duplicates().itertuples(index=False)}
    p["last"] = [keys[(s, o)] for s, o in zip(p["series_id"], p["origin"])]
    p = p[np.isfinite(p["last"]) & (p["last"] > 0)]
    p["p_up"] = [events.probability(a, b, c, l, True) for a, b, c, l in zip(p["q10"], p["q50"], p["q90"], p["last"])]
    p = p.dropna(subset=["p_up"])
    p["ret"] = p["actual"] / p["last"] - 1
    return p[cols].reset_index(drop=True)


def trades(w: pd.DataFrame, threshold: float, cost: float) -> pd.DataFrame:
    """Each window's return under hold, follow and long/short."""
    long = w["p_up"] > threshold
    return w.assign(hold=w["ret"], follow=np.where(long, w["ret"] - 2 * cost, 0.0),
                    longshort=np.where(long, 1.0, -1.0) * w["ret"] - 2 * cost, inside=long.astype(float))


def _by_origin(w: pd.DataFrame, threshold: float, cost: float) -> pd.DataFrame:
    """Equal-weight basket returns per origin date (the unit the luck test counts)."""
    return trades(w, threshold, cost).groupby("origin")[["hold", "follow", "longshort", "inside"]].mean().sort_index()


def _t(diff: pd.Series) -> float | None:
    diff = diff.dropna()
    if len(diff) < 3 or diff.std(ddof=1) == 0:
        return None
    return float(diff.mean() / (diff.std(ddof=1) / math.sqrt(len(diff))))


def replay(w: pd.DataFrame, cost: float = COST) -> dict:
    """The record per forecaster and horizon, the growth of $100 per strategy, and the out-of-sample
    threshold test."""
    out = {"cost": cost, "rows": [], "curves": {}, "oos": [], "markets": int(w["series_id"].nunique()) if len(w) else 0,
           "first": str(w["origin"].min())[:10] if len(w) else None, "last": str(w["origin"].max())[:10] if len(w) else None}
    if w.empty:
        return out
    for step, ws in w.groupby("step"):
        curve = {}
        for model, wm in ws.groupby("model"):
            t = trades(wm, 0.5, cost)
            g = _by_origin(wm, 0.5, cost)
            diff = g["follow"] - g["hold"]
            out["rows"].append({"model": model, "step": int(step), "origins": int(len(g)), "windows": int(len(wm)),
                                "hit": round(float((wm["p_up"].gt(0.5) == wm["ret"].gt(0)).mean()), 4),
                                "hold": round(float(t["hold"].mean()), 5), "follow": round(float(t["follow"].mean()), 5),
                                "longshort": round(float(t["longshort"].mean()), 5), "inside": round(float(t["inside"].mean()), 3),
                                "t": None if _t(diff) is None else round(_t(diff), 2)})
            # Windows overlap, so returns are added, not compounded: what $100 staked on every window made in total.
            by_day = t.groupby("origin")[["hold", "follow"]].sum().sort_index()
            curve["dates"] = [str(d)[:10] for d in by_day.index]
            curve["hold"] = [round(float(x), 1) for x in 100 * by_day["hold"].cumsum()]
            curve[model] = [round(float(x), 1) for x in 100 * by_day["follow"].cumsum()]
            # Out of sample: pick the threshold on the first half of the origins, judge it on the rest.
            origins = list(g.index)
            if len(origins) >= 8:
                early, late = set(origins[: len(origins) // 2]), set(origins[len(origins) // 2:])
                train = wm[wm["origin"].isin(early)]
                best = max(THRESHOLDS, key=lambda th: _by_origin(train, th, cost)["follow"].mean())
                late_w = wm[wm["origin"].isin(late)]
                test, tt = _by_origin(late_w, best, cost), trades(late_w, best, cost)
                out["oos"].append({"model": model, "step": int(step), "threshold": best, "origins": int(len(test)),
                                   "follow": round(float(tt["follow"].mean()), 5), "hold": round(float(tt["hold"].mean()), 5),
                                   "t": None if _t(test["follow"] - test["hold"]) is None else round(_t(test["follow"] - test["hold"]), 2)})
        out["curves"][str(int(step))] = curve
    out["verdict"] = verdict(out)
    return out


NAMES = {"radiant": "Radiant", "timesfm-2.5": "TimesFM", "seldon": "Seldon", "chronos-bolt": "Chronos-Bolt"}


def verdict(result: dict) -> str:
    rows = result.get("rows") or []
    if not rows:
        return "No market windows to replay yet."
    beat = [r for r in rows if r["follow"] > r["hold"] and (r["t"] or 0) >= T_EDGE]
    lost = [r for r in rows if r["follow"] < r["hold"]]
    if beat:
        names = ", ".join(sorted({r["model"] for r in beat}))
        return f"Following {names} beat holding by more than luck on some horizons; check it holds out of sample."
    text = (f"Following the forecasts did not beat simply holding the markets: it trailed on {len(lost)} of {len(rows)} "
            "forecaster-and-horizon pairs after costs, and no lead was large enough to be more than luck.")
    late = sorted({NAMES.get(r["model"], r["model"]) for r in result.get("oos") or [] if r["follow"] > r["hold"]})
    if late:
        text += (f" In the second half alone, {' and '.join(late)} came out ahead with the odds picked on the first half,"
                 " too few windows yet to tell from luck.")
    return text


def payload(paths: pd.DataFrame | None, data: dict[str, pd.Series] | None = None) -> dict | None:
    w = windows(paths, data)
    return replay(w) if len(w) else None


def describe(result: dict | None) -> str:
    if not result or not result.get("rows"):
        return "No market windows in the backtest yet; run `psychohistory backtest` first."
    lines = [f"Following the forecasts on {result['markets']} markets, {result['cost']:.1%} cost each way (average return per window)", "",
             f"  {'forecaster':<13}{'horizon':>9}{'windows':>9}{'right':>8}{'hold':>9}{'follow':>9}{'long/short':>12}{'t':>7}"]
    for r in sorted(result["rows"], key=lambda r: (r["step"], r["model"])):
        lines.append(f"  {NAMES.get(r['model'], r['model']):<13}{r['step']:>6} d {r['windows']:>9}{r['hit']:>8.0%}{r['hold']:>+9.2%}"
                     f"{r['follow']:>+9.2%}{r['longshort']:>+12.2%}{(r['t'] if r['t'] is not None else float('nan')):>7.1f}")
    if result.get("oos"):
        lines += ["", "  Out of sample (threshold picked on the first half of the origins, judged on the second):"]
        for r in sorted(result["oos"], key=lambda r: (r["step"], r["model"])):
            lines.append(f"  {NAMES.get(r['model'], r['model']):<13}{r['step']:>6} d  above {r['threshold']:.0%}: follow {r['follow']:+.2%}, "
                         f"hold {r['hold']:+.2%} over {r['origins']} origins")
    lines += ["", result["verdict"], "Research, not investment advice."]
    return "\n".join(lines)
