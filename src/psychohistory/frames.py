"""Time frames, rise alerts and confident calls: what the forecasts say about the next day, week,
month, year, 5 years and 10 years, how sure they are, and how often that kind of sureness was right.

* **Short frames** (day, week, month) come straight from the sealed weekly forecasts of TimesFM and
  Radiant: the chance the series is higher on that day than on the last day the model saw.
* **Long frames** (year, 5 years, 10 years) come from the *long view*: a random walk with drift fitted
  to each series' yearly averages (or yearly values), in logs when the series is always positive. Its
  range includes the uncertainty of the drift itself and uses Student's t, because a few dozen years
  say little about the next ten. No foundation model is asked for ten years of daily values.
* **Alert tiers**: a 75% or higher chance of going higher is a priority, 85% a big priority and 95%
  "tell the world". Every tier carries its record: how often, in the backtest and in sealed forecasts
  already opened, a call in that tier really did end higher.
* **Confident calls**: for each model and area, the smallest lean (distance of the chance from 50%)
  at which its direction calls were right at least 70% of the time on the *earlier* backtest windows.
  The rule is then checked on the *later* windows it never saw. Calls inside the lean are abstentions,
  and the share of windows that get a call is always reported beside the hit rate.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import catalog, radiant
from .monitor import t_sf

FRAMES = (("day", "Next day"), ("week", "Next week"), ("month", "Next month"),
          ("year", "Next year"), ("y5", "Next 5 years"), ("y10", "Next 10 years"))
SHORT = {"D": {"day": 1, "week": 7, "month": 28}, "B": {"day": 1, "week": 5, "month": 21}, "YS": {"year": 1}}
LONG = {"year": 1, "y5": 5, "y10": 10}
TIERS = ((0.95, "world", "Tell the world"), (0.85, "major", "Big priority"), (0.75, "watch", "Priority"))
TARGET = 0.70  # the hit rate a confident call has to reach on the earlier windows
LEANS = tuple(round(x, 2) for x in np.arange(0.0, 0.46, 0.05))
MIN_CALLS = 20
MIN_YEARS = 6  # yearly values needed before the long view says anything
LATE = {"daily": pd.Timestamp("2026-04-01"), "yearly": pd.Timestamp("2008-01-01")}
P_CAP = 0.99  # the long view never claims certainty


def tier(p: float | None) -> str | None:
    if p is None or not math.isfinite(p):
        return None
    for floor, key, _ in TIERS:
        if p >= floor:
            return key
    return None


def p_up3(q10: float, q50: float, q90: float, last: float) -> float:
    """Chance of ending above ``last`` from three quantiles, read the way the ledger reads all nine:
    straight lines between them and the tails capped at 5% and 95%."""
    lo, mid, hi = sorted((q10, q50, q90))
    cdf = np.interp(last, [lo, mid, hi], [0.1, 0.5, 0.9], left=0.05, right=0.95)
    return float(1 - cdf)


def is_late(origin, freq: str) -> bool:
    return pd.Timestamp(origin) >= LATE["yearly" if freq == "YS" else "daily"]


# ---------- the long view ----------

def annual(series: pd.Series, freq: str) -> pd.Series:
    """One value a year: the series itself when it is yearly, else the mean of each complete year."""
    s = series.dropna()
    if s.empty:
        return s
    if freq == "YS":
        return s.groupby(s.index.year).last()
    full = {"D": 330, "B": 230}.get(freq, 330)
    counts = s.groupby(s.index.year).size()
    means = s.groupby(s.index.year).mean()
    return means[counts >= full]


def long_view(values: np.ndarray, years: int) -> dict | None:
    """Random walk with drift on yearly values. Returns the chance of being higher ``years`` from the
    last value, the middle and the 80% range (as changes from the last value)."""
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    if len(v) < MIN_YEARS:
        return None
    logs = bool(np.all(v > 0))
    x = np.log(v) if logs else v
    d = np.diff(x)
    n = len(d)
    mu, sd = float(np.mean(d)), float(np.std(d, ddof=1))
    if not math.isfinite(sd) or sd <= 0:
        return None
    scale = sd * math.sqrt(years * (1 + years / n))  # the walk's own spread plus the doubt about the drift
    df = n - 1
    p = t_sf(-mu * years / scale, df)
    p = min(max(p, 1 - P_CAP), P_CAP)
    width = 1.2816 * scale * (math.sqrt(df / (df - 2)) if df > 2 else 2.0)
    centre = mu * years

    def change(z):
        return math.expm1(z) if logs else z / abs(v[-1]) if v[-1] else float("nan")
    return {"p": p, "mid": change(centre), "low": change(centre - width), "high": change(centre + width), "years": int(len(v)),
            "last": float(v[-1])}


def long_backtest(series: pd.Series, spec) -> list[dict]:
    """Every past origin where the long view could have spoken and the answer is now known."""
    a = annual(series, spec.freq)
    rows = []
    vals = a.to_numpy(dtype=float)
    for frame, years in LONG.items():
        if frame == "year" and spec.freq == "YS":
            continue  # yearly series get their next year from the models
        for i in range(MIN_YEARS - 1, len(vals) - years):
            out = long_view(vals[: i + 1], years)
            if out is None:
                continue
            rows.append({"series_id": spec.id, "area": radiant.area(spec), "frame": frame, "model": "long-view",
                         "origin": int(a.index[i]), "p": out["p"], "up": float(vals[i + years] > vals[i]),
                         "late": int(a.index[i]) >= (2008 if spec.freq == "YS" else 2018)})
    return rows


# ---------- short frames: backtest and sealed ----------

def _levels(paths: pd.DataFrame, data: dict[str, pd.Series]) -> dict[str, dict]:
    """Each series' known values by date: the data, filled in from the backtest's own actuals."""
    out: dict[str, dict] = {}
    for sid, g in paths.drop_duplicates(["series_id", "date"]).groupby("series_id"):
        out[sid] = dict(zip(pd.to_datetime(g["date"]), g["actual"].astype(float)))
    for sid, s in data.items():
        if s is not None:
            out.setdefault(sid, {}).update({pd.Timestamp(k): float(v) for k, v in s.dropna().items()})
    return out


def short_backtest(paths: pd.DataFrame | None, data: dict[str, pd.Series], models: list[str]) -> pd.DataFrame:
    """For each backtest window, model and frame: the chance of rising it gave and whether it rose."""
    if paths is None or paths.empty:
        return pd.DataFrame()
    part = paths[paths["model"].isin(models)].copy()
    part["origin"] = pd.to_datetime(part["origin"])
    levels = _levels(paths, data)
    rows = []
    for spec in catalog.CATALOG:
        want = {s: f for f, s in SHORT.get(spec.freq, {}).items() if s <= spec.horizon}
        if not want:
            continue
        g = part[(part["series_id"] == spec.id) & part["step"].isin(want)]
        known = levels.get(spec.id, {})
        for r in g.itertuples():
            last = known.get(r.origin)
            if last is None or not math.isfinite(r.actual):
                continue
            rows.append({"series_id": spec.id, "area": radiant.area(spec), "frame": want[r.step], "model": r.model,
                         "origin": r.origin, "p": p_up3(r.q10, r.q50, r.q90, last), "up": float(r.actual > last),
                         "late": is_late(r.origin, spec.freq)})
    return pd.DataFrame(rows)


def sealed_rows(scored: pd.DataFrame | None, models: list[str]) -> pd.DataFrame:
    """Sealed forecasts already opened, at the frame steps: the live record."""
    if scored is None or scored.empty:
        return pd.DataFrame()
    rows = []
    specs = {s.id: s for s in catalog.CATALOG}
    for r in scored[scored["model"].isin(models)].itertuples():
        spec = specs.get(r.series_id)
        if spec is None:
            continue
        frame = {s: f for f, s in SHORT.get(spec.freq, {}).items()}.get(int(r.step))
        if frame is None or pd.isna(r.p_up):
            continue
        if pd.Timestamp(r.target_date) <= pd.to_datetime(r.made_on, errors="coerce"):
            continue  # sealed after its own date (Wikipedia and GDELT run behind): not a forecast
        rows.append({"series_id": r.series_id, "area": radiant.area(spec), "frame": frame, "model": r.model,
                     "origin": str(r.made_on), "p": float(r.p_up), "up": float(r.actual > r.last_value), "late": True})
    return pd.DataFrame(rows)


# ---------- records ----------

def tier_record(rows: pd.DataFrame) -> dict:
    """Per model and tier: calls made in that tier and how many ended higher, for all frames together
    and for each frame."""
    out: dict = {}
    if rows is None or rows.empty:
        return out
    rows = rows.assign(tier=[tier(p) for p in rows["p"]]).dropna(subset=["tier"])
    for model, g in rows.groupby("model"):
        m = out.setdefault(model, {})
        for key, t in g.groupby("tier"):
            m.setdefault("all", {})[key] = [int(len(t)), int(t["up"].sum())]
            for frame, f in t.groupby("frame"):
                m.setdefault(frame, {})[key] = [int(len(f)), int(f["up"].sum())]
    return out


def _calls(rows: pd.DataFrame, lean: float) -> pd.DataFrame:
    c = rows[(rows["p"] - 0.5).abs() >= lean - 1e-9]
    c = c[c["p"] != 0.5]
    return c.assign(right=((c["p"] > 0.5) == (c["up"] > 0.5)).astype(float))


def tune(rows: pd.DataFrame, target: float = TARGET) -> list[dict]:
    """Per model and area, the smallest lean whose direction calls were right ``target`` of the time on
    the earlier windows (at least ``MIN_CALLS`` of them), then its record on the later windows. When
    no lean reaches the target, the best one is kept and marked ``reached: False``."""
    out = []
    if rows is None or rows.empty:
        return out
    for (model, area), g in rows.groupby(["model", "area"]):
        early, late = g[~g["late"].astype(bool)], g[g["late"].astype(bool)]
        if early.empty or late.empty:
            continue
        best, chosen = None, None
        for lean in LEANS:
            c = _calls(early, lean)
            if len(c) < MIN_CALLS:
                break
            rate = float(c["right"].mean())
            if best is None or rate > best[1]:
                best = (lean, rate)
            if rate >= target:
                chosen = (lean, rate)
                break
        pick = chosen or best
        if pick is None:
            continue
        lean = pick[0]
        base = _calls(late, 0.0)
        c = _calls(late, lean)
        out.append({"model": model, "area": area, "lean": float(lean), "reached": chosen is not None,
                    "early_rate": round(pick[1], 4), "early_calls": int(len(_calls(early, lean))),
                    "late_rate": round(float(c["right"].mean()), 4) if len(c) else None, "late_calls": int(len(c)),
                    "late_windows": int(len(late)), "late_all_rate": round(float(base["right"].mean()), 4) if len(base) else None})
    return out


# ---------- this week's frames and alerts ----------

def current(ledger: pd.DataFrame | None, data: dict[str, pd.Series], models: list[str], rules: list[dict]) -> list[dict]:
    """Each series' newest sealed forecast read at every frame, plus the long view."""
    lean = {(r["model"], r["area"]): r["lean"] for r in rules}
    reached = {(r["model"], r["area"]): r["reached"] for r in rules}
    out = []
    newest = None
    if ledger is not None and not ledger.empty:
        newest = ledger[ledger["made_on"] == ledger["made_on"].max()]
    for spec in catalog.CATALOG:
        area = radiant.area(spec)
        cells = {}
        if newest is not None:
            mine = newest[newest["series_id"] == spec.id]
            for frame, step in SHORT.get(spec.freq, {}).items():
                if step > spec.horizon:
                    continue
                for model in models:
                    r = mine[(mine["model"] == model) & (mine["step"] == step)]
                    if r.empty:
                        continue
                    r = r.iloc[0]
                    last = float(r["last_value"])
                    p = float(r["p_up"])
                    key = (model, area)
                    sure = key in lean and reached.get(key) and abs(p - 0.5) >= lean[key] and p != 0.5
                    cells.setdefault(frame, {})[model] = {
                        "p": round(p, 4), "mid": _chg(r["q50"], last), "low": _chg(r["q10"], last), "high": _chg(r["q90"], last),
                        "date": str(r["target_date"])[:10], "sure": bool(sure)}
        series = data.get(spec.id)
        if series is not None and not series.empty:
            vals = annual(series, spec.freq).to_numpy(dtype=float)
            for frame, years in LONG.items():
                if frame == "year" and spec.freq == "YS":
                    continue
                lv = long_view(vals, years)
                if lv:
                    cells.setdefault(frame, {})["long-view"] = {
                        "p": round(lv["p"], 4), "mid": round(lv["mid"], 5), "low": round(lv["low"], 5), "high": round(lv["high"], 5),
                        "years": lv["years"], "sure": False}
        if cells:
            out.append({"id": spec.id, "domain": spec.domain, "area": area, "title": spec.description, "freq": spec.freq,
                        "frames": cells})
    return out


def _chg(value, last: float) -> float | None:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(v) or not last:
        return None
    return round(v / last - 1, 5)


def alerts(items: list[dict], lead: list[str]) -> list[dict]:
    """Every series and frame where a model gives a 75% or higher chance of going higher, highest
    first. ``lead`` is the order in which models speak for a cell (the first one present wins)."""
    out = []
    for item in items:
        for frame, cells in item["frames"].items():
            model = next((m for m in lead if m in cells), None)
            if model is None:
                continue
            c = cells[model]
            t = tier(c["p"])
            if t:
                out.append({"id": item["id"], "title": item["title"], "domain": item["domain"], "frame": frame, "model": model,
                            "tier": t, "p": c["p"], "mid": c["mid"], "low": c["low"], "high": c["high"], "sure": c.get("sure", False),
                            "others": {m: v["p"] for m, v in cells.items() if m != model}})
    order = {k: i for i, (_, k, _) in enumerate(TIERS)}
    return sorted(out, key=lambda a: (order[a["tier"]], -a["p"]))


def payload(paths: pd.DataFrame | None, ledger: pd.DataFrame | None, scored: pd.DataFrame | None,
            data: dict[str, pd.Series], model: str) -> dict:
    models = [m for m in (model, radiant.NAME, radiant.RIVAL, "seldon") if paths is None or m in set(paths.get("model", []))]
    back = short_backtest(paths, data, models)
    longs = pd.DataFrame([r for spec in catalog.CATALOG if data.get(spec.id) is not None
                          for r in long_backtest(data[spec.id], spec)])
    everything = pd.concat([f for f in (back, longs) if not f.empty], ignore_index=True) if not (back.empty and longs.empty) else pd.DataFrame()
    rules = tune(back) + tune(longs)
    live = sealed_rows(scored, [model, radiant.NAME])
    items = current(ledger, data, [model, radiant.NAME], rules)
    return {
        "frames": [list(f) for f in FRAMES],
        "tiers": [[floor, key, name] for floor, key, name in TIERS],
        "target": TARGET,
        "items": items,
        "alerts": alerts(items, [radiant.NAME, model, "long-view"]),
        "record": {"backtest": tier_record(everything), "live": tier_record(live)},
        "rules": rules,
    }
