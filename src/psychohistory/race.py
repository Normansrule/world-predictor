"""The race: TimesFM, Radiant and Seldon against what really happened, over years.

The app's main charts show what really happened and, beside it, what each forecaster had said each
day would be, so the gap between them can be followed through the years. Two kinds of record are
drawn, and labelled apart:

- **replayed**: rolling-origin forecasts over the last ``YEARS`` years. Each one starts from the
  data up to its origin only and runs one horizon ahead (28 days for most daily series, 21 market
  days for markets); the next starts where it ended, so every day is covered once. TimesFM is the
  expensive part, so its windows are kept in ``results/race/<year>.csv`` and the weekly run adds at
  most ``GROW`` new ones per series, newest first, until ten years are filled; after that only the
  windows that have just finished. Radiant and Seldon are mixes of cheap forecasters with weights
  learned per area only from windows that had finished by each origin (``radiant.py``,
  ``seldon.py``); they are replayed from the kept TimesFM windows on every run, so a newly added
  older window also teaches every later one. Chronos-Bolt is not run here, so it sits out of both
  mixes.
- **sealed**: the forecasts written down before the day in the prediction ledger, from the first
  forecast on (18 October 2026), which keep coming in.

``summary`` scores each forecaster in both, so the chart can say how it did in the past and how it is
doing now: the typical miss (median absolute percentage error, so one wild day cannot dominate),
how often it was the closest of the three, and by year.
"""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from . import catalog, radiant, seldon
from .models import Forecast, Forecaster

log = logging.getLogger(__name__)

MODEL = "timesfm-2.5"
SHOW = (MODEL, radiant.NAME, seldon.NAME)
YEARS = 10
GROW = 48  # new TimesFM windows per series per run: about two to four years
BUDGET = 25 * 60  # seconds of TimesFM per run at most; the workflow step stops at 45 minutes
MAX_CONTEXT = 1024
CACHE = Path("results/race")
WEB = Path("results/web/race")
COLS = ["series_id", "origin", "date", "step", "q10", "q50", "q90", "actual"]


def eligible(spec: catalog.SeriesSpec) -> bool:
    """Daily and market-day series; yearly adoption curves have too few points to race."""
    return spec.freq in ("D", "B")


def _sig(x) -> float | None:
    return None if x is None or not np.isfinite(x) else float(f"{float(x):.6g}")


# ---------- the kept TimesFM windows ----------

def load_cache(folder: Path = CACHE) -> pd.DataFrame:
    files = sorted(Path(folder).glob("*.csv")) if Path(folder).exists() else []
    if not files:
        return pd.DataFrame(columns=COLS)
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    return df.drop_duplicates(["series_id", "origin", "step"], keep="last")[COLS]


def save_cache(cache: pd.DataFrame, folder: Path = CACHE) -> list[Path]:
    """One file per year of origin, rows in a fixed order, so a finished year never changes."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    out = []
    if cache.empty:
        return out
    c = cache.copy()
    for col in ("q10", "q50", "q90", "actual"):
        c[col] = [_sig(v) for v in c[col]]
    c = c.sort_values(["series_id", "origin", "step"])
    for year, g in c.groupby(c["origin"].astype(str).str[:4]):
        path = folder / f"{year}.csv"
        g[COLS].to_csv(path, index=False)
        out.append(path)
    return out


def seed(paths: pd.DataFrame | None, model: str = MODEL) -> pd.DataFrame:
    """The kept windows from a saved backtest's paths (``results/backtest_paths.csv``), so the race
    starts with the windows the monthly backtest already ran."""
    if paths is None or paths.empty:
        return pd.DataFrame(columns=COLS)
    ids = {s.id for s in catalog.CATALOG if eligible(s)}
    p = paths[(paths["model"] == model) & paths["series_id"].isin(ids)]
    return p[COLS].copy()


def grid(index: pd.DatetimeIndex, horizon: int, anchor: pd.Timestamp | None = None, years: int = YEARS) -> list[int]:
    """Origin positions p (forecast days p+1 .. p+horizon all in the data), ``horizon`` apart, on a
    grid through ``anchor`` (a kept origin) so kept windows stay valid, back to ``years`` ago."""
    n = len(index)
    if n < 3 * horizon:
        return []
    start = index[-1] - pd.DateOffset(years=years)
    a = n - 1 - horizon if anchor is None else int(index.searchsorted(pd.Timestamp(anchor), side="right")) - 1
    a = a % horizon + ((n - 1 - horizon - a % horizon) // horizon) * horizon  # the newest grid point that has finished
    out, p = [], a
    while p >= 2 * horizon and index[p] >= start:
        out.append(p)
        p -= horizon
    return sorted(out)


def grow(series: dict[str, pd.Series], model: Forecaster, cache: pd.DataFrame, limit: int = GROW,
         years: int = YEARS, max_context: int = MAX_CONTEXT, budget: float | None = BUDGET) -> tuple[pd.DataFrame, int]:
    """Add up to ``limit`` missing windows per series, newest first, stopping between series once
    ``budget`` seconds have gone, so a slow runner adds fewer windows rather than losing them all.
    Returns the cache and how many windows were added."""
    import time
    began = time.monotonic()
    new, added = [], 0
    kept = {sid: set(g["origin"].astype(str)) for sid, g in cache.groupby("series_id")} if len(cache) else {}
    for spec in catalog.CATALOG:
        if not eligible(spec) or spec.id not in series:
            continue
        if budget is not None and time.monotonic() - began > budget:
            log.warning("race: time budget used; the rest of the windows wait for the next run")
            break
        s = series[spec.id].dropna()
        y, idx, h = s.to_numpy(float), s.index, spec.horizon
        have = kept.get(spec.id, set())
        anchor = max(have) if have else None
        todo = [p for p in grid(idx, h, anchor, years) if f"{idx[p].date()}" not in have][::-1][:limit]
        if not todo:
            continue
        contexts = [y[max(0, p + 1 - max_context): p + 1] for p in todo]
        forecasts = model.forecast(contexts, h)
        for p, f in zip(todo, forecasts):
            for k in range(h):
                new.append({"series_id": spec.id, "origin": f"{idx[p].date()}", "date": f"{idx[p + 1 + k].date()}",
                            "step": k + 1, "q10": float(f.q(0.1)[k]), "q50": float(f.q(0.5)[k]),
                            "q90": float(f.q(0.9)[k]), "actual": float(y[p + 1 + k])})
        added += len(todo)
    if not new:
        return cache, 0
    out = pd.concat([cache, pd.DataFrame(new)], ignore_index=True)
    return out.drop_duplicates(["series_id", "origin", "step"], keep="last").reset_index(drop=True), added


# ---------- Radiant and Seldon replayed on the kept windows ----------

def _deciles(q10, q50, q90) -> np.ndarray:
    z = np.array([-1.2816, -0.8416, -0.5244, -0.2533, 0.0, 0.2533, 0.5244, 0.8416, 1.2816]) / 1.2816
    q10, q50, q90 = (np.asarray(v, float) for v in (q10, q50, q90))
    lower, upper = (q50 - q10)[:, None], (q90 - q50)[:, None]
    return np.sort(q50[:, None] + np.where(z < 0, lower, upper) * z, axis=1)


def windows(series: dict[str, pd.Series], cache: pd.DataFrame, max_context: int = MAX_CONTEXT) -> list[dict]:
    """Every kept window with its context and the cheap forecasters' forecasts from it."""
    specs = {s.id: s for s in catalog.CATALOG}
    out = []
    for (sid, origin), g in cache.groupby(["series_id", "origin"]):
        if sid not in series or sid not in specs:
            continue
        s = series[sid].dropna()
        g = g.sort_values("step")
        o = pd.Timestamp(origin)
        p = int(s.index.searchsorted(o, side="right")) - 1
        h = len(g)
        if p < 1 or s.index[p] != o or p + h > len(s) - 1:
            continue
        actual = s.to_numpy(float)[p + 1: p + 1 + h]
        if len(actual) != h:
            continue
        c = s.to_numpy(float)[max(0, p + 1 - max_context): p + 1]
        q = [g[x].to_numpy(float) for x in ("q10", "q50", "q90")]
        f = {"model": Forecast(q[1], _deciles(*q)), "laws": seldon.predict(c, h)[0],
             "core": radiant.core_predict(c, h)[0], "naive": radiant.naive_forecast(c, h)}
        out.append({"spec": replace(specs[sid], horizon=h), "sid": sid, "origin": o, "end": s.index[p + h],
                    "dates": s.index[p + 1: p + 1 + h], "actual": actual, "f": f, "area": radiant.area(specs[sid])})
    return out


def _miss(path, actual) -> float:
    a = np.asarray(actual, float)
    ok = np.isfinite(a) & (a != 0)
    return float(np.mean(np.abs(np.asarray(path, float)[ok] - a[ok]) / np.abs(a[ok]))) if ok.any() else np.nan


def replay(wins: list[dict]) -> pd.DataFrame:
    """Radiant and Seldon on every window, each with weights from that area's windows finished by
    its origin: the same rules as ``backtest.add_radiant`` and ``backtest.add_seldon``, with running
    totals so ten years of windows take seconds rather than hours."""
    rows = []
    for area in sorted({w["area"] for w in wins}):
        mine = [w for w in wins if w["area"] == area]
        done = sorted(mine, key=lambda w: w["end"])
        ends = np.array([w["end"].value for w in done])
        rad = np.zeros((len(done) + 1, len(radiant.EXPERTS)))
        own = np.zeros((len(done) + 1, len(seldon.OWN)))
        ratios = []
        for i, w in enumerate(done):
            f, a = w["f"], w["actual"]
            miss = np.array([_miss(f[e].q(0.5), a) if e in f else np.nan for e in radiant.EXPERTS])
            ch = miss / max(miss[0], 1e-12) - 1
            rad[i + 1] = rad[i] + np.where(np.isfinite(ch), ch, 0.0)
            om = np.array([_miss(f[e].q(0.5), a) if e in f else np.nan for e in seldon.OWN])
            if np.isfinite(om).any():
                mean = float(np.nanmean(om))
                own[i + 1] = own[i] + np.where(np.isfinite(om), om / max(mean, 1e-12), 1.0)
            else:
                own[i + 1] = own[i]
            m = f["model"]
            ratios.append(radiant.band_ratios(m.q(0.1), m.q(0.5), m.q(0.9), a))
        scales: dict[int, float] = {}  # windows on the same grid date share a cut-off: work each widening out once
        for w in mine:
            k = int(np.searchsorted(ends, w["origin"].value, side="right"))  # windows finished by the origin
            if k not in scales:
                scales[k] = radiant.band_scale(ratios[:k])
            x = {e: w["f"][e] for e in ("model", "laws", "core", "naive")}
            logits = np.log(radiant.prior(False)) - radiant.ETA * rad[k]
            wt = np.exp(logits - logits.max())
            wt = radiant.present(wt / wt.sum(), x)
            mixed = radiant.widen(radiant.mix(x, wt), scales[k])
            logits = -seldon.OWN_ETA * own[k]
            ow = np.exp(logits - logits.max())
            sel, _ = seldon.own_mix({e: w["f"][e] for e in seldon.OWN if e in w["f"]}, ow / ow.sum())
            for name, fc in ((radiant.NAME, mixed), (seldon.NAME, sel)):
                q50 = fc.q(0.5)
                rows += [{"series_id": w["sid"], "model": name, "origin": f"{w['origin'].date()}", "date": f"{d.date()}",
                          "step": j + 1, "q50": float(q50[j]), "actual": float(w["actual"][j])} for j, d in enumerate(w["dates"])]
    return pd.DataFrame(rows, columns=["series_id", "model", "origin", "date", "step", "q50", "actual"])


def paths(series: dict[str, pd.Series], cache: pd.DataFrame) -> pd.DataFrame:
    """TimesFM's kept windows and Radiant's and Seldon's replays, as one table of middle paths."""
    tfm = cache.assign(model=MODEL)[["series_id", "model", "origin", "date", "step", "q50", "actual"]]
    out = pd.concat([tfm, replay(windows(series, cache))], ignore_index=True)
    return dedupe(out.astype({"q50": float, "actual": float, "step": int}))


def dedupe(p: pd.DataFrame) -> pd.DataFrame:
    """One forecast per forecaster per day: where two kept windows overlap (an older backtest's grid
    a day off), the newer origin's."""
    if p.empty:
        return p
    return p.sort_values(["origin", "step"]).drop_duplicates(["series_id", "model", "date"], keep="last").reset_index(drop=True)


# ---------- what the app draws ----------

def sealed(scored: pd.DataFrame | None, show=SHOW) -> pd.DataFrame:
    """The sealed record: for each series and settled day, each forecaster's newest call made before it."""
    from . import tally
    out = []
    for m in show:
        c = tally.standing(scored, m) if scored is not None else pd.DataFrame()
        if "q50" in c and len(c):
            out.append(pd.DataFrame({"series_id": c["series_id"], "model": m, "date": c["target_date"].dt.strftime("%Y-%m-%d"),
                                     "q50": c["q50"], "actual": c["actual"], "right": c["right"]}))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=["series_id", "model", "date", "q50", "actual", "right"])


def _score(g: pd.DataFrame) -> dict | None:
    """Typical miss (median absolute % error), the mean miss, and days, for one forecaster's rows."""
    a, q = g["actual"].to_numpy(float), g["q50"].to_numpy(float)
    ok = np.isfinite(a) & np.isfinite(q) & (a != 0)
    if not ok.any():
        return None
    e = np.abs(q[ok] - a[ok]) / np.abs(a[ok])
    return {"n": int(ok.sum()), "typical": round(float(np.median(e)), 5), "mean": round(float(np.mean(e)), 5)}


def summary(p: pd.DataFrame, models=SHOW) -> dict:
    """Per forecaster: the score overall, by year, and how often it was the closest of those that
    forecast the same day."""
    out: dict = {}
    if p.empty:
        return out
    wide = p.pivot_table(index="date", columns="model", values="q50", aggfunc="last")
    act = p.groupby("date")["actual"].last()
    have = [m for m in models if m in wide]
    if have:
        gap = wide[have].sub(act.reindex(wide.index), axis=0).abs()
        both = gap.dropna()
        best = both.idxmin(axis=1) if len(both) else pd.Series(dtype=object)
    for m in have:
        g = p[p["model"] == m]
        s = _score(g)
        if s is None:
            continue
        years = {}
        for y, gy in g.groupby(g["date"].str[:4]):
            sy = _score(gy)
            if sy:
                years[y] = sy["typical"]
        s["years"] = years
        s["closest"] = round(float((best == m).mean()), 4) if len(best) else None
        s["from"], s["to"] = str(g["date"].min()), str(g["date"].max())
        out[m] = s
    return out


def series_payload(sid: str, replayed: pd.DataFrame, live: pd.DataFrame, models=SHOW) -> dict | None:
    """One series for the race chart: dates, what happened, each forecaster's middle for each day
    (replayed before the sealed record starts, sealed from then on), and the scores of both."""
    r = replayed[replayed["series_id"] == sid]
    s = live[live["series_id"] == sid]
    if r.empty and s.empty:
        return None
    live_from = str(s["date"].min()) if len(s) else None
    if live_from:
        r = r[r["date"] < live_from]  # where both exist, the sealed record wins
    both = pd.concat([r.assign(kind="replayed"), s.assign(kind="sealed")], ignore_index=True)
    dates = sorted(both["date"].unique())
    act = both.groupby("date")["actual"].last().reindex(dates)
    out = {"id": sid, "dates": dates, "actual": [_sig(v) for v in act], "live_from": live_from, "m": {},
           "origins": sorted(r["origin"].unique().tolist()) if "origin" in r and len(r) else []}
    for m in models:
        v = both[both["model"] == m].groupby("date")["q50"].last().reindex(dates)
        if v.notna().any():
            out["m"][m] = [_sig(x) for x in v]
    out["past"] = summary(r, models)
    out["now"] = summary(s, models)
    if len(s) and "right" in s:
        for m in out["now"]:
            g = s[s["model"] == m]
            out["now"][m]["right"], out["now"][m]["calls"] = int(g["right"].sum()), int(len(g))
    return out


def build(replayed: pd.DataFrame, scored: pd.DataFrame | None, ids=None) -> dict[str, dict]:
    live = sealed(scored)
    ids = ids or sorted(set(replayed["series_id"]) | set(live["series_id"]))
    out = {}
    for sid in ids:
        item = series_payload(sid, replayed, live)
        if item:
            out[sid] = item
    return out


def index(book: dict[str, dict]) -> dict:
    """The small table data.js carries: per series, how far back the race goes and the scores, so
    pages can show the past and present without loading the full race."""
    return {sid: {"from": b["dates"][0], "to": b["dates"][-1], "live_from": b["live_from"], "past": b["past"], "now": b["now"]}
            for sid, b in book.items() if b["dates"]}


def write(book: dict[str, dict], folder: Path = WEB) -> int:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for sid, item in book.items():
        (folder / f"{sid}.json").write_text(json.dumps(item, separators=(",", ":")))
    (folder / "index.json").write_text(json.dumps(index(book), separators=(",", ":")))
    return len(book)


def describe(book: dict[str, dict]) -> str:
    if not book:
        return "No race yet: it starts with the first backtest or race run."
    lines = [f"The race: {len(book)} series. Typical miss (median absolute % error), replayed past and sealed present:"]
    for sid, b in list(book.items())[:60]:
        part = []
        for m in SHOW:
            p, n = b["past"].get(m), b["now"].get(m)
            part.append(f"{m.split('-')[0]} {p['typical']:.1%}" if p else f"{m.split('-')[0]} –")
            part[-1] += f" / {n['typical']:.1%}" if n else " / –"
        lines.append(f"  {sid:<22} {b['dates'][0]}..{b['dates'][-1]}  " + "   ".join(part))
    return "\n".join(lines)
