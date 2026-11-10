"""Can Seldon be its own forecaster, not TimesFM with a few votes on top?

Seldon was first built as a council with TimesFM in it, and under the November 2026 share rule the
crowd laws rarely earned a share, so it ended up almost exactly TimesFM. This script is the test that
chose its own council (``seldon.own_weights``), which ships now. This replays every
recorded daily backtest window (results/backtest_paths.csv) with councils that leave TimesFM out, so
whatever they say is their own view, and asks two questions of each: how far off was it (the year
ledger's average absolute percentage miss of the median per day), and how different is it from TimesFM
(the average gap between the two medians, as a share of the real value, and how often the two
expected moves point opposite ways). Every learned weight comes only from windows of the same area that
had finished before the forecast's origin, so nothing peeks.

    python scripts/seldon_perspective.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

from rebuild_app_data import rebuild_series  # noqa: E402

from psychohistory import catalog, radiant, seldon  # noqa: E402

MODELS = {"tfm": "timesfm-2.5", "seldon": "seldon", "laws": "seldon-laws", "core": "radiant-core", "chronos": "chronos-bolt", "radiant": "radiant"}
SPLIT = pd.Timestamp("2026-04-01")


def windows() -> list[dict]:
    paths = pd.read_csv(ROOT / "results" / "backtest_paths.csv", parse_dates=["origin", "date"])
    text = (ROOT / "results" / "web" / "data.js").read_text()
    series = rebuild_series(paths, "timesfm-2.5", json.loads(text[text.index("{"): text.rindex("}") + 1]))
    domain = {s.id: s.domain for s in catalog.CATALOG if s.source != "owid"}  # daily series only
    by = {m: {k: g.sort_values("step") for k, g in paths[paths["model"] == name].groupby(["series_id", "origin"])} for m, name in MODELS.items()}
    out = []
    for key, g in by["tfm"].items():
        sid, origin = key
        if sid not in domain or any(key not in by[m] or len(by[m][key]) != len(g) for m in MODELS):
            continue
        before = series[sid][series[sid].index <= origin]
        if not len(before):
            continue
        w = {"sid": sid, "dom": domain[sid], "origin": origin, "end": g["date"].max(), "a": g["actual"].to_numpy(float), "last": float(before.iloc[-1])}
        w.update({m: by[m][key]["q50"].to_numpy(float) for m in MODELS})
        w["bands"] = {m: (by[m][key]["q10"].to_numpy(float), by[m][key]["q90"].to_numpy(float)) for m in ("laws", "core", "chronos", "tfm", "seldon")}
        nf = radiant.naive_forecast(before.to_numpy(float)[-2048:], len(g))
        w["bands"]["naive"] = (nf.q(0.1), nf.q(0.9))
        w["naive"] = np.full(len(w["a"]), w["last"])
        out.append(w)
    return sorted(out, key=lambda w: w["origin"])


W = windows()


def miss(f, w):
    return np.abs(f - w["a"]) / np.abs(w["a"])


def past(w):
    return [v for v in W if v["end"] <= w["origin"] and v["dom"] == w["dom"]]


def hedge(experts, eta=2.0):
    """Exponential weights over ``experts`` per area (Littlestone & Warmuth, 1994; the rule Radiant uses
    with TimesFM in it): equal at first, each finished window charges every expert its average miss
    relative to the experts' mean miss on that window, and its weight shrinks by e^(-eta * charge)."""
    def f(w):
        lw = np.zeros(len(experts))
        for v in past(w):
            e = np.array([np.mean(miss(v[k], v)) for k in experts])
            lw -= eta * e / max(float(np.mean(e)), 1e-12)
        p = np.exp(lw - lw.max()); p /= p.sum()
        return p @ np.vstack([w[k] for k in experts])
    return f


def inverse(experts, power=2):
    """Inverse-error weights per area from the finished windows (Bates & Granger, 1969), equal before any."""
    def f(w):
        d = past(w)
        if not d:
            return np.mean(np.vstack([w[k] for k in experts]), axis=0)
        e = np.array([np.mean(np.concatenate([miss(v[k], v) for v in d])) for k in experts])
        p = 1 / np.maximum(e, 1e-12) ** power; p /= p.sum()
        return p @ np.vstack([w[k] for k in experts])
    return f


RW = {id(w): radiant.Window(w["dom"], w["end"], {"laws": w["laws"], "core": w["core"], "naive": w["naive"], "rival": w["chronos"]}, w["a"]) for w in W}


def shipped(w):
    """Seldon's own council exactly as seldon.own_weights ships it (bands: decile-averaged 10th/90th)."""
    wt = seldon.own_weights([RW[id(v)] for v in W], w["dom"], w["origin"])
    keys = {"laws": "laws", "core": "core", "naive": "naive", "rival": "chronos"}
    mid = sum(wt[k] * w[keys[e]] for k, e in enumerate(seldon.OWN))
    w["_band"] = tuple(sum(wt[k] * w["bands"][keys[e]][j] for k, e in enumerate(seldon.OWN)) for j in (0, 1))
    return mid


CANDIDATES = {
    "Seldon's own council, as shipped (seldon.own_weights)": shipped,
    "TimesFM": lambda w: w["tfm"],
    "Seldon as recorded in this run": lambda w: w["seldon"],
    "Radiant (TimesFM in its council)": lambda w: w["radiant"],
    "Chronos-Bolt alone": lambda w: w["chronos"],
    '"No change"': lambda w: w["naive"],
    "Crowd laws alone": lambda w: w["laws"],
    "Behavioural core alone": lambda w: w["core"],
    "Laws + core + no change, exponential weights": hedge(["laws", "core", "naive"]),
    "Laws + core + no change, inverse-error weights": inverse(["laws", "core", "naive"]),
    "Laws + core + no change + Chronos, exponential weights": hedge(["laws", "core", "naive", "chronos"]),
    "Laws + core + no change + Chronos, inverse-error weights": inverse(["laws", "core", "naive", "chronos"]),
    "Laws + Chronos, half each": lambda w: (w["laws"] + w["chronos"]) / 2,
}


def score(f) -> dict:
    rows = []
    for w in W:
        p = f(w)
        move, tmove = p[-1] - w["last"], w["tfm"][-1] - w["last"]
        rows.append({"dom": w["dom"], "early": w["origin"] < SPLIT, "miss": float(np.mean(miss(p, w))),
                     "gap": float(np.mean(np.abs(p - w["tfm"]) / np.abs(w["a"]))), "opposite": bool(move * tmove < 0)})
    d = pd.DataFrame(rows)
    pick = lambda m: 100 * d.loc[m, "miss"].mean()
    return {"all": pick(d.index == d.index), "early": pick(d["early"]), "late": pick(~d["early"]),
            **{k: pick(d["dom"] == k) for k in ("markets", "news", "tech")},
            "gap": 100 * d["gap"].mean(), "opposite": 100 * d["opposite"].mean(), "per": d["miss"].to_numpy()}


def main() -> None:
    print(f"{len(W)} daily windows. Average miss per day of the median, and how far each is from TimesFM:\n")
    print(f"{'forecaster':<58} {'all':>6} {'to Mar':>7} {'Apr on':>7} {'markets':>8} {'news':>6} {'tech':>6} {'gap':>6} {'opp.':>5}")
    base = score(CANDIDATES["TimesFM"])
    out = []
    for name, f in CANDIDATES.items():
        s = score(f)
        diff = s["per"] - base["per"]
        t = float(np.mean(diff) / (np.std(diff, ddof=1) / np.sqrt(len(diff)))) if np.any(diff) else 0.0
        out.append((s["all"], name, s, t))
    for _, name, s, t in sorted(out, key=lambda r: r[0]):
        print(f"{name:<58} {s['all']:5.2f}% {s['early']:6.2f}% {s['late']:6.2f}% {s['markets']:7.2f}% {s['news']:5.2f}% {s['tech']:5.2f}% {s['gap']:5.2f}% {s['opposite']:4.0f}%  t {t:+.1f}")
    inside = lambda m: np.mean(np.concatenate([(w["a"] >= w["bands"][m][0]) & (w["a"] <= w["bands"][m][1]) for w in W]))
    [shipped(w) for w in W]
    own = np.mean(np.concatenate([(w["a"] >= w["_band"][0]) & (w["a"] <= w["_band"][1]) for w in W]))
    print(f"\nInside the 80% range: TimesFM {inside('tfm'):.1%}, Seldon as recorded {inside('seldon'):.1%}, Seldon's own council {own:.1%}.")
    print("\ngap: average |forecast - TimesFM| / real value per day. opp.: windows whose expected move points the other way from TimesFM's."
          "\nt: paired t of the per-window miss against TimesFM's (negative is better; beyond about -2 is unlikely to be luck, windows overlap so read it loosely).")


if __name__ == "__main__":
    main()
