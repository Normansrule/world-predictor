"""Which model has been best on each series, and whether that is worth anything.

Every series page shows how each forecaster did on that series in the backtest: its average error
(sMAPE of the middle forecast), how often reality landed inside its 80% range, and over how many
windows. It is tempting to read the top row as "use this model here". This module also tests that
idea honestly, on the same backtest: for every series, pick the model with the lowest error on the
first half of its windows, then score that pick on the second half against simply using Radiant (or
the main model) everywhere. The answer is shown beside the table, whichever way it goes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

DEFAULT = "radiant"


def _windows(paths: pd.DataFrame) -> pd.DataFrame:
    p = paths.dropna(subset=["q50", "actual"]).copy()
    p["ape"] = 2 * (p["q50"] - p["actual"]).abs() / (p["q50"].abs() + p["actual"].abs()).replace(0, np.nan)
    p["inside"] = ((p["actual"] >= p["q10"]) & (p["actual"] <= p["q90"])).astype(float)
    return p.groupby(["series_id", "origin", "model"], as_index=False)[["ape", "inside"]].mean()


def table(paths: pd.DataFrame | None) -> dict[str, list]:
    """Per series: [model, sMAPE, share inside 80%, windows], best first."""
    if paths is None or paths.empty:
        return {}
    w = _windows(paths)
    agg = w.groupby(["series_id", "model"]).agg(smape=("ape", "mean"), inside=("inside", "mean"), n=("origin", "nunique")).reset_index()
    out = {}
    for sid, g in agg.groupby("series_id"):
        g = g.dropna(subset=["smape"]).sort_values("smape")
        out[sid] = [[r.model, round(float(r.smape), 5), round(float(r.inside), 4), int(r.n)] for r in g.itertuples()]
    return out


def holdout(paths: pd.DataFrame | None, default: str = DEFAULT) -> dict | None:
    """Pick each series' best model on its first half of windows, score it on the second half.
    Only windows every model forecast count, so the comparison is like for like."""
    if paths is None or paths.empty:
        return None
    w = _windows(paths).pivot_table(index=["series_id", "origin"], columns="model", values="ape").dropna()
    if default not in w.columns:
        default = w.columns[0] if len(w.columns) else default
    rows = []
    for sid, g in w.groupby(level="series_id"):
        g = g.sort_index(level="origin")
        k = len(g) // 2
        if k < 2:
            continue
        early, late = g.iloc[:k], g.iloc[k:]
        pick, late_best = early.mean().idxmin(), late.mean().idxmin()
        rows.append((sid, pick, late_best, float(late[pick].mean()), float(late[default].mean())))
    if len(rows) < 3:
        return None
    r = pd.DataFrame(rows, columns=["series", "pick", "late_best", "pick_err", "default_err"])
    d = r["pick_err"] - r["default_err"]
    t = float(d.mean() / (d.std(ddof=1) / np.sqrt(len(d)))) if d.std(ddof=1) > 0 else 0.0
    return {"default": default, "series": int(len(r)), "pick_smape": round(float(r["pick_err"].mean()), 5),
            "default_smape": round(float(r["default_err"].mean()), 5), "better": int((d < -1e-12).sum()),
            "worse": int((d > 1e-12).sum()), "kept": int((r["pick"] == r["late_best"]).sum()), "t": round(t, 2)}


def payload(paths: pd.DataFrame | None, model: str = DEFAULT) -> dict | None:
    by_series = table(paths)
    if not by_series:
        return None
    default = DEFAULT if DEFAULT in set(paths["model"]) else model  # Radiant once it is in the backtest
    return {"series": by_series, "holdout": holdout(paths, default)}
