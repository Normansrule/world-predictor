"""Radiant's lab: replay its mix on a recorded full backtest, with every window learning only from
the windows of its area that had finished before it, and try changes to it honestly.

A full CI backtest records the forecast paths of TimesFM, Chronos-Bolt, the crowd laws and Radiant's
core (``results/backtest_paths.csv``), so the whole mix can be rebuilt here without a GPU or a
download. Every variant is scored on the same windows by average sMAPE per series, then per area
(markets, news, daily technology, yearly adoption), and split in time: an "early" half, where the
weights have little to learn from, and a "late" half, where they have learned. A change is only
worth shipping if it helps on the late half, or on both. The interval check asks the same of a
learned band width (adaptive, in the spirit of Gibbs & Candès, 2021).

    python scripts/radiant_replay.py

Run on the 4 November 2026 backtest, nothing beat the shipped mix overall (see README, "Radiant's
lab").
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

from psychohistory import catalog, radiant  # noqa: E402

MODEL = "timesfm-2.5"
AREAS = ("markets", "news", "tech", radiant.YEARLY)
LATE = {"yearly": pd.Timestamp("2008-01-01"), "daily": pd.Timestamp("2026-04-01")}


def load():
    paths = pd.read_csv(ROOT / "results" / "backtest_paths.csv")
    text = (ROOT / "results" / "web" / "data.js").read_text()
    data = rebuild_series(paths, MODEL, json.loads(text[text.index("{"): text.rindex("}") + 1]))
    domains = radiant.domains_of(catalog.CATALOG)
    windows = radiant.windows_from_paths(paths, data, MODEL, domains)
    keys = [k for k, _ in paths[paths["model"] == MODEL].groupby(["series_id", "origin"])
            if k[0] in data and k[0] in domains and (data[k[0]].index <= pd.Timestamp(k[1])).any()]
    assert len(keys) == len(windows)
    for (sid, origin), w in zip(keys, windows):
        w.series_id, w.origin = sid, pd.Timestamp(origin)
    return paths, windows


def is_late(w) -> bool:
    return w.origin >= LATE["yearly" if w.domain == radiant.YEARLY else "daily"]


def smape(f, a) -> float:
    f, a = np.asarray(f, float), np.asarray(a, float)
    return float(np.mean(2 * np.abs(f - a) / (np.abs(f) + np.abs(a))))


def mixer(start=None, eta=radiant.ETA, share=0.0, floor=0.0):
    """Radiant's mix with one thing changed: its start, learning rate, fixed-share forgetting
    (Herbster & Warmuth, 1998), or a floor that always keeps part of the vote on the two foundation
    models."""
    def forecast(w, windows):
        past = sorted((v for v in windows if v.domain == w.domain and v.end <= w.origin), key=lambda v: v.end)
        rival = "rival" in w.paths
        p0 = radiant.prior(rival) if start is None else np.array(start, float)
        lw = np.log(p0)
        for v in past:
            lw = lw - eta * radiant.charges(v)
            if share:
                p = np.exp(lw - lw.max())
                lw = np.log((1 - share) * p / p.sum() + share * p0)
        p = np.exp(lw - lw.max())
        p = radiant.present(p / p.sum(), w.paths)
        if floor:
            anchor = radiant.present(np.array([0.5, 0, 0, 0, 0.5]), w.paths)
            p = (1 - floor) * p + floor * anchor
        return sum(p[k] * np.asarray(w.paths[e], float) for k, e in enumerate(radiant.EXPERTS) if e in w.paths)
    return forecast


def table(windows, variants: dict) -> pd.DataFrame:
    rows = []
    for name, f in variants.items():
        for w in windows:
            rows.append({"variant": name, "area": w.domain, "series": w.series_id, "late": is_late(w),
                         "smape": smape(f(w, windows), w.actual)})
    d = pd.DataFrame(rows)

    def avg(x):  # per series first, then over series, as the backtest summary does
        return 100 * x.groupby(["variant", "series"]).smape.mean().groupby("variant").mean()
    out = pd.DataFrame({"all": avg(d), "early": avg(d[~d.late]), "late": avg(d[d.late])})
    for a in AREAS:
        out[a] = avg(d[d.area == a])
    return out.loc[list(variants)].round(2)


def bands(paths: pd.DataFrame, model: str = radiant.NAME, target: float = 0.8, min_points: int = 20) -> pd.DataFrame:
    """Coverage of the 80% range and average pinball loss (in % of the level), as recorded and with
    a band width learned per area from the finished windows' misses, on the late windows."""
    domains = radiant.domains_of(catalog.CATALOG)
    ws = []
    for (sid, origin), g in paths[paths["model"] == model].groupby(["series_id", "origin"]):
        if sid in domains:
            g = g.sort_values("step")
            ws.append({"area": domains[sid], "origin": pd.Timestamp(origin), "end": pd.Timestamp(g["date"].max()),
                       "lo": g["q10"].to_numpy(float), "mid": g["q50"].to_numpy(float),
                       "hi": g["q90"].to_numpy(float), "a": g["actual"].to_numpy(float)})

    def ratio(w):
        down, up = np.maximum(w["mid"] - w["lo"], 1e-12), np.maximum(w["hi"] - w["mid"], 1e-12)
        return np.where(w["a"] < w["mid"], (w["mid"] - w["a"]) / down, (w["a"] - w["mid"]) / up)

    def pinball(q, a, t):
        return np.mean(np.maximum(t * (a - q), (t - 1) * (a - q)))
    rows = []
    for w in ws:
        late = w["origin"] >= LATE["yearly" if w["area"] == radiant.YEARLY else "daily"]
        if not late:
            continue
        past = [ratio(v) for v in ws if v["area"] == w["area"] and v["end"] <= w["origin"]]
        r = np.concatenate(past) if past else np.array([])
        for kind, s in (("as recorded", 1.0), ("learned width", float(np.quantile(r, target)) if len(r) >= min_points else 1.0)):
            lo, hi = w["mid"] - s * (w["mid"] - w["lo"]), w["mid"] + s * (w["hi"] - w["mid"])
            level = np.mean(np.abs(w["a"])) + 1e-12
            rows.append({"area": w["area"], "kind": kind, "cover": float(np.mean((w["a"] >= lo) & (w["a"] <= hi))),
                         "pinball": 100 * (pinball(lo, w["a"], 0.1) + pinball(w["mid"], w["a"], 0.5) + pinball(hi, w["a"], 0.9)) / 3 / level})
    d = pd.DataFrame(rows)
    return pd.concat([d.groupby("kind")[["cover", "pinball"]].mean().assign(area="all"),
                      d.groupby(["kind", "area"])[["cover", "pinball"]].mean().reset_index("area")]).round(3)


def main() -> None:
    paths, windows = load()
    if not any("rival" in w.paths for w in windows):
        print("This run did not record Chronos-Bolt's paths; the variants below run without it.")
    variants = {
        "TimesFM": lambda w, _: w.paths["model"],
        "Chronos-Bolt": lambda w, _: w.paths.get("rival", w.paths["model"]),
        "Radiant as shipped": mixer(),
        "Old start (63% TimesFM, 10% Chronos)": mixer(start=radiant.PRIOR_SOLO),
        "Learning rate 1": mixer(eta=1.0),
        "Learning rate 4": mixer(eta=4.0),
        "Fixed share 3% (forgets)": mixer(share=0.03),
        "25% always on the two foundations": mixer(floor=0.25),
        "50% always on the two foundations": mixer(floor=0.5),
    }
    print(f"{len(windows)} recorded windows. Average sMAPE per series (lower is better); early and late split in time:\n")
    print(table(windows, variants).to_string())
    print("\nThe 80% range on the late windows, Radiant as recorded and with a learned width:\n")
    print(bands(paths).to_string())


if __name__ == "__main__":
    main()
