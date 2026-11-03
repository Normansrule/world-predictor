"""The year ledger: every day of the year, each model's most likely value against what happened.

For every tracked series and every day from 1 January to 31 December, the ledger shows the real value
(once it exists), the median ("most likely") forecast of TimesFM, of Seldon and of Seldon's crowd laws
alone, and how far each one was from reality in percent. Days nobody forecast, or that have not
happened yet, stay empty and are drawn as dashes.

Where a forecast for a day comes from, newest first:

* a **sealed** forecast from the prediction ledger, written down before the day (the newest one
  sealed before it, so the shortest lead);
* otherwise a **backtest** forecast from the saved rolling-origin paths: made with only the data up
  to its origin, but replayed afterwards rather than sealed at the time. The app labels the two.

The summary compares the models only on days where all of them forecast, from the same kind of
record (all sealed, or all backtest), and the real value is in, so no model is helped by skipping
hard days or by a shorter lead: mean absolute percentage error, bias, and how often each
was the closest. The goal it keeps in view is the project's: a forecaster of our own that beats
TimesFM.
"""

from __future__ import annotations

import math
from datetime import date

import numpy as np
import pandas as pd

from . import catalog, monitor

LAWS = "seldon-laws"
SELDON = "seldon"
RADIANT = "radiant"

# One table per tracked part of the world, in the order the app shows them. Yearly adoption curves
# have one value a year, so they are left out.
GROUPS = [
    ("gold", "Gold", ["gold"]),
    ("silver", "Silver", ["silver"]),
    ("bonds", "Bonds", ["us10y", "tlt"]),
    ("fear", "Fear gauge", ["vix"]),
    ("indices", "Stock indices", ["sp500", "nasdaq100", "msci_world"]),
    ("stocks", "Stocks", ["aapl", "nvda", "tsla", "xom"]),
    ("commodities", "Oil and copper", ["oil_wti", "copper"]),
    ("crypto", "Bitcoin", ["bitcoin"]),
    ("news", "World news", [s.id for s in catalog.NEWS]),
    ("tech", "Technology", [s.id for s in catalog.TECH if s.source != "owid"]),
]


def _sig(x: float | None, digits: int = 5):
    if x is None or not math.isfinite(x):
        return None
    return float(f"{x:.{digits}g}")


def _days(year: int) -> pd.DatetimeIndex:
    return pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D")


def forecasts(paths: pd.DataFrame | None, entries: pd.DataFrame | None, series_id: str, models: list[str],
              days: pd.DatetimeIndex, data: pd.Series | None) -> dict[str, dict]:
    """For one series and each model, the median forecast for every day, the value it started from and
    where it came from ("s" sealed, "b" backtest). Sealed forecasts win over backtest ones; among
    several, the one made last before the day."""
    out = {m: {"value": {}, "origin": {}, "source": {}} for m in models}
    lo, hi = days[0], days[-1]
    if paths is not None and not paths.empty:
        part = paths[(paths["series_id"] == series_id) & paths["model"].isin(models)].copy()
        part["date"] = pd.to_datetime(part["date"])
        part = part[(part["date"] >= lo) & (part["date"] <= hi)]
        part["origin"] = pd.to_datetime(part["origin"])
        part = part[part["origin"] < part["date"]].sort_values("origin")
        for r in part.itertuples(index=False):
            start = None
            if data is not None:
                before = data[data.index <= r.origin]
                start = float(before.iloc[-1]) if len(before) else None
            book = out[r.model]
            book["value"][r.date] = float(r.q50)
            book["origin"][r.date] = start
            book["source"][r.date] = "b"
    if entries is not None and not entries.empty:
        part = entries[(entries["series_id"] == series_id) & entries["model"].isin(models)].copy()
        part["target_date"] = pd.to_datetime(part["target_date"])
        part["made_on"] = pd.to_datetime(part["made_on"])
        part = part[(part["target_date"] >= lo) & (part["target_date"] <= hi) & (part["made_on"] < part["target_date"])]
        for r in part.sort_values("made_on").itertuples(index=False):
            book = out[r.model]
            book["value"][r.target_date] = float(r.q50)
            book["origin"][r.target_date] = float(r.last_value)
            book["source"][r.target_date] = "s"
    return out


def series_table(series_id: str, data: pd.Series | None, paths: pd.DataFrame | None, entries: pd.DataFrame | None,
                 models: list[str], year: int) -> dict:
    """One series' year: a value per day for the actual and each model (None where there is none),
    the forecast's starting value and its source, all as arrays from 1 January."""
    days = _days(year)
    actual = [None] * len(days)
    if data is not None and not data.empty:
        s = data[(data.index >= days[0]) & (data.index <= days[-1])].dropna()
        index = {d: i for i, d in enumerate(days)}
        for d, v in s.items():
            i = index.get(pd.Timestamp(d).normalize())
            if i is not None:
                actual[i] = _sig(float(v))
    fc = forecasts(paths, entries, series_id, models, days, data)
    table = {"a": actual}
    lead = models[0]
    for m in models:
        table[m] = [_sig(fc[m]["value"].get(d)) for d in days]
    table["o"] = [_sig(fc[lead]["origin"].get(d)) for d in days]
    # Each model's own source per day, so models are only compared on like forecasts: a sealed
    # forecast made days before against another sealed one, a backtest against a backtest.
    table["by"] = {m: "".join(fc[m]["source"].get(d) or "-" for d in days) for m in models}
    table["src"] = "".join(fc[lead]["source"].get(d) or ("b" if any(fc[m]["source"].get(d) == "b" for m in models) else
                                                          "s" if any(fc[m]["source"].get(d) == "s" for m in models) else "-")
                           for d in days)
    return table


def compare(table: dict, models: list[str], lag: int = 0) -> dict:
    """The models on the days where all of them forecast and the real value is in: days, mean
    absolute percentage error, mean signed error (bias), and the share of days each was closest.
    Each challenger also gets a Diebold-Mariano test of its daily absolute percentage error against
    the first model's (TimesFM's): ``dm`` (negative: the challenger missed less) and its two-sided
    ``p``. Forecasts up to ``lag + 1`` steps ahead overlap, so their errors are correlated over
    ``lag`` days; the test's long-run variance allows for that (Newey-West, with the
    Harvey-Leybourne-Newbold small-sample correction)."""
    a = np.array([np.nan if v is None else v for v in table["a"]], float)
    f = {m: np.array([np.nan if v is None else v for v in table[m]], float) for m in models}
    ok = np.isfinite(a) & (a != 0)
    for m in models:
        ok &= np.isfinite(f[m])
    by = table.get("by")
    if by:  # only days where every model's forecast came from the same kind of record
        first = np.array(list(by[models[0]]))
        for m in models[1:]:
            ok &= np.array(list(by[m])) == first
    n = int(ok.sum())
    out = {"days": n, "models": {}}
    if not n:
        return out
    err = {m: (f[m][ok] - a[ok]) / np.abs(a[ok]) for m in models}
    stack = np.vstack([np.abs(err[m]) for m in models])
    best = stack.argmin(axis=0)
    for k, m in enumerate(models):
        out["models"][m] = {"mape": float(np.mean(np.abs(err[m]))), "bias": float(np.mean(err[m])),
                            "closest": float(np.mean(best == k))}
        if k:
            stat, p = monitor.diebold_mariano(np.abs(err[m]) - np.abs(err[models[0]]), lag)
            out["models"][m]["dm"] = _sig(stat, 4)
            out["models"][m]["p"] = _sig(p, 4)
    return out


def build(data: dict[str, pd.Series], paths: pd.DataFrame | None, entries: pd.DataFrame | None, model: str,
          year: int | None = None, today: date | None = None) -> dict:
    """Everything the app's year ledger needs: per group and series the daily arrays and the
    comparison, and the leaderboard over all of them."""
    year = year or (today or date.today()).year
    present = set()
    for frame in (paths, entries):
        if frame is not None and not frame.empty:
            present |= set(frame["model"])
    models = [m for m in (model, RADIANT, SELDON, LAWS) if m == model or m in present]  # a challenger with no forecasts yet is left out
    groups, board = [], {m: {"days": 0, "abs": 0.0, "closest": 0.0, "series": 0, "beats": 0} for m in models}
    for key, title, ids in GROUPS:
        items = []
        for sid in ids:
            spec = next((s for s in catalog.CATALOG if s.id == sid), None)
            if spec is None:
                continue
            table = series_table(sid, data.get(sid), paths, entries, models, year)
            stats = compare(table, models, lag=max(0, spec.horizon - 1))
            items.append({"id": sid, "title": spec.description, "freq": spec.freq, "domain": spec.domain,
                          "table": table, "stats": stats})
            if stats["days"]:
                base = stats["models"][model]["mape"]
                for m in models:
                    s = stats["models"][m]
                    b = board[m]
                    b["days"] += stats["days"]
                    b["abs"] += s["mape"] * stats["days"]
                    b["closest"] += s["closest"] * stats["days"]
                    b["series"] += 1
                    b["beats"] += int(m != model and s["mape"] < base)
        groups.append({"key": key, "title": title, "series": items})
    # Which leads are real: per challenger, its series whose Diebold-Mariano p-value survives the
    # Benjamini-Hochberg cut for testing every series at once (on average at most 5% false calls).
    for m in models[1:]:
        tests = [(x["stats"]["models"][m]["dm"], x["stats"]["models"][m]["p"]) for g in groups for x in g["series"]
                 if x["stats"]["days"] and x["stats"]["models"][m].get("p") is not None]
        cut = monitor.false_discoveries([p for _, p in tests])
        board[m]["better"] = sum(1 for d, p in tests if cut >= 0 and p <= cut and d < 0)
        board[m]["worse"] = sum(1 for d, p in tests if cut >= 0 and p <= cut and d > 0)
        board[m]["cut"] = cut
        for g in groups:
            for x in g["series"]:
                st = x["stats"]["models"].get(m) if x["stats"]["days"] else None
                if st is not None and st.get("p") is not None:
                    st["real"] = bool(cut >= 0 and st["p"] <= cut)
    leaders = [{"model": m, "days": b["days"], "series": b["series"],
                "mape": b["abs"] / b["days"] if b["days"] else None,
                "closest": b["closest"] / b["days"] if b["days"] else None,
                "beats": b["beats"] if m != model else None,
                "better": b.get("better"), "worse": b.get("worse")} for m, b in board.items()]
    return {"year": year, "start": f"{year}-01-01", "today": (today or date.today()).isoformat(),
            "models": models, "groups": groups, "leaders": leaders}


def table_frame(book: dict) -> pd.DataFrame:
    """The year ledger as one long table for the books: a row per series and day that has a real
    value or a forecast, with each model's median, its miss in percent (forecast − real) / real and
    the forecast's source. Days with neither are left out; in the app they are the dashes."""
    rows = []
    days = _days(book["year"])
    for g in book["groups"]:
        for item in g["series"]:
            t = item["table"]
            for i, d in enumerate(days):
                a, fc = t["a"][i], {m: t[m][i] for m in book["models"]}
                if a is None and all(v is None for v in fc.values()):
                    continue
                row = {"date": d.date().isoformat(), "group": g["key"], "series_id": item["id"], "actual": a}
                for m, v in fc.items():
                    row[m] = v
                    row[f"{m}_off_pct"] = _sig(100 * (v - a) / abs(a), 4) if v is not None and a else None
                row["source"] = {"s": "sealed", "b": "backtest"}.get(t["src"][i], "")
                rows.append(row)
    return pd.DataFrame(rows)


def write_csv(book: dict | None, out_dir) -> object:
    """Write results/year_ledger.csv (see `table_frame`); returns the path, or None without a ledger."""
    from pathlib import Path

    if not book:
        return None
    path = Path(out_dir) / "year_ledger.csv"
    table_frame(book).to_csv(path, index=False)
    return path
