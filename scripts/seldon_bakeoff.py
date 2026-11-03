"""The bake-off: can any way of combining TimesFM, the crowd laws and "no change" beat TimesFM?

Replays every recorded daily backtest window (results/backtest_paths.csv). Each combiner forecasts a
window using only the windows that had finished before its origin, from the same area (markets,
news, technology), so nothing peeks. Scored as the year ledger scores: the absolute percentage miss
of the median on every day, averaged. Also split at 1 April 2026 so a rule that only wins in one half
shows up as such.

    python scripts/seldon_bakeoff.py

Ten combiners were tried in November 2026; none beat TimesFM overall. Radiant (radiant.py) was
added to the same bake-off afterwards. The share rule that came
closest replaced Seldon's old one (see README, "The bake-off").
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from rebuild_app_data import rebuild_series  # noqa: E402

from psychohistory import catalog, radiant, seldon  # noqa: E402

GRID = np.round(np.linspace(0, 1, 11), 1)
SPLIT = pd.Timestamp("2026-04-01")


def windows() -> list[dict]:
    paths = pd.read_csv(ROOT / "results" / "backtest_paths.csv", parse_dates=["origin", "date"])
    text = (ROOT / "results" / "web" / "data.js").read_text()
    series = rebuild_series(paths, "timesfm-2.5", json.loads(text[text.index("{"): text.rindex("}") + 1]))
    domain = {s.id: s.domain for s in catalog.CATALOG if s.source != "owid"}  # yearly series have 3 steps
    laws = {k: g.sort_values("step") for k, g in paths[paths["model"] == "seldon"].groupby(["series_id", "origin"])}
    out = []
    for (sid, origin), g in paths[paths["model"] == "timesfm-2.5"].groupby(["series_id", "origin"]):
        g, l = g.sort_values("step"), laws.get((sid, origin))
        if sid not in domain or l is None or len(l) != len(g):
            continue
        before = series[sid][series[sid].index <= origin]
        if not len(before):
            continue
        out.append({"sid": sid, "dom": domain[sid], "origin": origin, "end": g["date"].max(), "tfm": g["q50"].to_numpy(float),
                    "laws": l["q50"].to_numpy(float), "a": g["actual"].to_numpy(float), "last": float(before.iloc[-1])})
    return out


W = windows()


def _radiant_paths() -> dict:
    """Radiant replayed on the same recorded windows (radiant.replay: weights from finished windows only)."""
    paths = pd.read_csv(ROOT / "results" / "backtest_paths.csv", parse_dates=["origin", "date"])
    text = (ROOT / "results" / "web" / "data.js").read_text()
    series = rebuild_series(paths, "timesfm-2.5", json.loads(text[text.index("{"): text.rindex("}") + 1]))
    rows = radiant.replay(paths, series, "timesfm-2.5", radiant.domains_of(catalog.CATALOG))
    return {k: g.sort_values("step")["q50"].to_numpy(float) for k, g in rows.groupby(["series_id", "origin"])}


RADIANT = _radiant_paths()
_TEXT = (ROOT / "results" / "web" / "data.js").read_text()
SERIES = rebuild_series(pd.read_csv(ROOT / "results" / "backtest_paths.csv", parse_dates=["origin", "date"]), "timesfm-2.5",
                        json.loads(_TEXT[_TEXT.index("{"): _TEXT.rindex("}") + 1]))


def past(w: dict) -> list[dict]:
    return [v for v in W if v["end"] <= w["origin"] and v["dom"] == w["dom"]]


def naive(v):
    return np.full(len(v["a"]), v["last"])


def miss(f, v):
    return np.abs(f - v["a"]) / np.abs(v["a"])


def pooled(d, f):
    return float(np.mean(np.concatenate([miss(f(v), v) for v in d])))


def rel(f, v):
    return np.mean(np.abs(f - v["a"])) / max(np.mean(np.abs(v["last"] - v["a"])), 1e-12)


def old_rule(w):  # Seldon to October 2026: error against "no change", five windows, 2% margin
    d = past(w)
    if len(d) < 5:
        return w["tfm"]
    e = [np.mean([rel((1 - s) * v["tfm"] + s * v["laws"], v) for v in d]) for s in GRID]
    i = int(np.argmin(e))
    s = GRID[i] if e[i] <= e[0] * 0.98 else 0.0
    return (1 - s) * w["tfm"] + s * w["laws"]


def new_rule(w):  # Seldon from November 2026: seldon.learn_share as shipped
    s = seldon.learn_share([seldon.Window(v["dom"], v["end"], v["last"], v["tfm"], v["laws"], v["a"]) for v in past(w)])
    return (1 - s) * w["tfm"] + s * w["laws"]


def shrink_move(w):
    d = past(w)
    if len(d) < 5:
        return w["tfm"]
    ks = np.round(np.linspace(0, 1.2, 13), 2)
    k = ks[int(np.argmin([np.mean([rel(v["last"] + k * (v["tfm"] - v["last"]), v) for v in d]) for k in ks]))]
    return w["last"] + k * (w["tfm"] - w["last"])


def per_series(w):
    d = past(w)
    if len(d) < 5:
        return w["tfm"]
    best = lambda ws: GRID[int(np.argmin([pooled(ws, lambda v, s=s: (1 - s) * v["tfm"] + s * v["laws"]) for s in GRID]))]
    mine = [v for v in d if v["sid"] == w["sid"]]
    sd = best(d)
    s = (len(mine) * (best(mine) if mine else sd) + 4 * sd) / (len(mine) + 4)
    return (1 - s) * w["tfm"] + s * w["laws"]


def inverse_mse(w):
    d = past(w)
    if len(d) < 5:
        return w["tfm"]
    fs = [naive, lambda v: v["tfm"], lambda v: v["laws"]]
    e = np.array([np.mean([rel(f(v), v) ** 2 for v in d]) for f in fs])
    wt = (1 / e) / np.sum(1 / e)
    return sum(wt[i] * fs[i](w) for i in range(3))


def bias_fix(w):
    d = [v for v in past(w) if (v["tfm"] > 0).all() and (v["a"] > 0).all()]
    f = w["tfm"].copy()
    if len(d) < 5 or not (w["tfm"] > 0).all():
        return f
    for lo, hi in ((0, 7), (7, 14), (14, 99)):
        parts = [np.log(v["a"][lo:hi] / v["tfm"][lo:hi]) for v in d if len(v["a"]) > lo]
        if parts:
            f[lo:hi] *= np.exp(0.5 * np.median(np.concatenate(parts)))
    return f


def gate(w):
    d = past(w)
    opts = {"tfm": lambda v: v["tfm"], "laws": lambda v: v["laws"], "naive": naive, "eq": lambda v: (v["tfm"] + v["laws"]) / 2}
    if len(d) < 10:
        return w["tfm"]
    e = {k: pooled(d, f) for k, f in opts.items()}
    k = min(e, key=e.get)
    return opts[k](w) if e[k] <= e["tfm"] * 0.97 else w["tfm"]


def log_blend(w):
    d = [v for v in past(w) if (v["tfm"] > 0).all() and (v["laws"] > 0).all() and (v["a"] > 0).all()]
    if len(d) < 10 or not ((w["tfm"] > 0).all() and (w["laws"] > 0).all()):
        return w["tfm"]
    g = lambda v, s: np.exp((1 - s) * np.log(v["tfm"]) + s * np.log(v["laws"]))
    e = [pooled(d, lambda v, s=s: g(v, s)) for s in GRID]
    i = int(np.argmin(e))
    return g(w, GRID[i] if e[i] <= e[0] * 0.98 else 0.0)


CANDIDATES = {
    "TimesFM": lambda w: w["tfm"],
    "Crowd laws alone": lambda w: w["laws"],
    '"No change"': naive,
    "Seldon, old share rule": old_rule,
    "Seldon, new share rule (in use)": new_rule,
    "Per-series share, shrunk to the area's": per_series,
    "Shrink TimesFM's predicted move": shrink_move,
    "Inverse-MSE weights (no change, TimesFM, laws)": inverse_mse,
    "Median of the three": lambda w: np.median(np.vstack([w["tfm"], w["laws"], naive(w)]), axis=0),
    "TimesFM and the laws, half each": lambda w: (w["tfm"] + w["laws"]) / 2,
    "TimesFM with its median bias halved": bias_fix,
    "Best of four per area, 3% margin": gate,
    "Log-space blend": log_blend,
    "Radiant (behavioural core + exponential weights)": lambda w: RADIANT[(w["sid"], w["origin"])],
    "Radiant's behavioural core alone": lambda w: radiant.core_predict(
        _context(w), len(w["a"]))[0].q(0.5),
}


def _context(w):
    return SERIES[w["sid"]][SERIES[w["sid"]].index <= w["origin"]].to_numpy(float)


def main() -> None:
    print(f"{len(W)} windows. Average miss per day of the median (lower is better):\n")
    print(f"{'forecaster':<48} {'all':>7} {'to Mar':>7} {'Apr on':>7} {'markets':>8} {'news':>7} {'tech':>7}")
    rows = []
    for name, f in CANDIDATES.items():
        per = [(w, float(np.mean(miss(f(w), w)))) for w in W]
        pick = lambda keep: 100 * np.mean([e for w, e in per if keep(w)])
        rows.append((pick(lambda w: True), name, pick(lambda w: w["origin"] < SPLIT), pick(lambda w: w["origin"] >= SPLIT),
                     *(pick(lambda w, d=d: w["dom"] == d) for d in ("markets", "news", "tech"))))
    for r in sorted(rows):
        print(f"{r[1]:<48} {r[0]:6.2f}% {r[2]:6.2f}% {r[3]:6.2f}% {r[4]:7.2f}% {r[5]:6.2f}% {r[6]:6.2f}%")


if __name__ == "__main__":
    main()
