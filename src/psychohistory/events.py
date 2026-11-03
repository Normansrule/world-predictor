"""Event odds: the chance that something unusual happens, not just where a series goes.

"World news attention to elections will be about 5.8 in four weeks" is hard to act on. "The chance
election coverage reaches a level it hits only one day in ten" is a question people ask. This
module turns every sealed news and technology forecast into the odds of two such events, four
weeks (the forecast's horizon) ahead:

* ``spike``: the value on the target date is above the 90th percentile of the last two years;
* ``lull``: it is below the 10th percentile.

Each threshold is fixed from the history up to the forecast's last observed day, so it is sealed
with the forecast. A model's odds are read off its sealed 10% / 50% / 90% quantiles as a split
normal (one spread above the middle, another below), in log space for positive series, so the tails
where events live are not cut off at the 10% and 90% levels.

Two baselines keep the odds honest:

* ``climatology``: the share of the last two years that was past the threshold (about 10% by
  construction: "it happens one day in ten");
* ``persistence``: how often, over the last two years, the series was past the threshold four weeks
  after a day in the same state as today. Attention is sticky, so this is the hard one to beat.

Odds are scored with the Brier score (Brier, 1950) and the Brier skill score against each baseline,
``1 - Brier(model) / Brier(baseline)``; above zero means better odds than the baseline gave. A
Diebold-Mariano test on the per-origin Brier differences says whether the edge over climatology is
more than luck. ``backtest`` replays this over the saved backtest paths; ``forecast_rows`` seals the
live odds in ``predictions/event_ledger.csv`` and ``score`` opens them once their day has passed.
"""

from __future__ import annotations

import math
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from .catalog import SeriesSpec

EVENTS = {"spike": (0.9, True), "lull": (0.1, False)}  # event: (quantile of the past, above it?)
CLIMATOLOGY = "climatology"
PERSISTENCE = "persistence"
BASELINES = (CLIMATOLOGY, PERSISTENCE)
LOOKBACK = 730  # two years of daily values set the thresholds
MIN_HISTORY = 180  # half a year before any odds are given
MIN_BATCHES = 4
Z90 = 1.2815515655446004  # the standard normal's 90% quantile

EVENT_LEDGER = Path("predictions/event_ledger.csv")
EVENT_SCORED = Path("predictions/event_scored.csv")
EVENT_SEALS = Path("predictions/event_seals.csv")
COLUMNS = ["made_on", "model", "series_id", "event", "last_date", "last_value", "threshold", "horizon", "target_date", "p"]
LAYOUT = {"columns": COLUMNS, "order": ("series_id", "event")}  # how ledger.fingerprint reads a batch

WORDS = {"spike": "a level it reaches only one day in ten", "lull": "a low it falls to only one day in ten"}


def eligible(spec: SeriesSpec) -> bool:
    """News and technology attention series (daily); markets have the desk's level odds instead."""
    return spec.domain in ("news", "tech") and spec.freq == "D"


def _norm_cdf(z: float) -> float:
    return 0.5 * math.erfc(-z / math.sqrt(2))


def probability(q10: float, q50: float, q90: float, threshold: float, above: bool) -> float | None:
    """The chance the outcome lands past ``threshold``, from three quantiles read as a split normal:
    the spread above the middle comes from q50 to q90, the one below from q10 to q50. Positive series
    are read in logs, where attention's long right tail is closer to normal."""
    values = [q10, q50, q90, threshold]
    if not all(math.isfinite(v) for v in values):
        return None
    if min(values) > 0:
        q10, q50, q90, threshold = (math.log(v) for v in values)
    lo, hi = max(q50 - q10, 1e-12) / Z90, max(q90 - q50, 1e-12) / Z90
    z = (threshold - q50) / (hi if threshold >= q50 else lo)
    below = _norm_cdf(z)
    p = 1.0 - below if above else below
    return float(min(max(p, 0.001), 0.999))


def threshold(history: np.ndarray, event: str) -> float | None:
    """The event's threshold: a quantile of the last two years."""
    h = history[np.isfinite(history)][-LOOKBACK:]
    if len(h) < MIN_HISTORY:
        return None
    return float(np.quantile(h, EVENTS[event][0]))


def baselines(history: np.ndarray, cut: float, event: str, steps: int) -> dict[str, float]:
    """Climatology and persistence odds from the last two years alone."""
    h = history[np.isfinite(history)][-LOOKBACK:]
    above = EVENTS[event][1]
    past = (h > cut) if above else (h < cut)
    out = {CLIMATOLOGY: float(past.mean())}
    if len(h) > steps + 30:
        now, later = past[:-steps], past[steps:]
        same = now == past[-1]
        if same.sum() >= 10:
            # Laplace's rule of succession, so a state seen rarely never gives odds of exactly 0 or 1.
            out[PERSISTENCE] = float((later[same].sum() + 1) / (same.sum() + 2))
    out.setdefault(PERSISTENCE, out[CLIMATOLOGY])
    return out


def happened(value: float, cut: float, event: str) -> float:
    return float(value > cut) if EVENTS[event][1] else float(value < cut)


def backtest(spec: SeriesSpec, series: pd.Series, paths: pd.DataFrame | None) -> pd.DataFrame:
    """Every saved backtest origin of one series: each model's odds of both events at the horizon,
    the two baselines', what happened and the Brier score. The thresholds and baselines see only
    the history up to the origin."""
    if paths is None or paths.empty or not eligible(spec):
        return pd.DataFrame()
    steps = spec.horizon
    mine = paths[(paths["series_id"] == spec.id) & (paths["step"] == steps)]
    if mine.empty:
        return pd.DataFrame()
    values = series.dropna()
    rows = []
    for origin, part in mine.groupby("origin"):
        history = values[values.index <= pd.Timestamp(origin)].to_numpy(float)
        actual = float(part["actual"].iloc[0])
        if not math.isfinite(actual):
            continue
        for event in EVENTS:
            cut = threshold(history, event)
            if cut is None:
                continue
            odds = baselines(history, cut, event, steps)
            for row in part.itertuples(index=False):
                p = probability(row.q10, row.q50, row.q90, cut, EVENTS[event][1])
                if p is not None:
                    odds[row.model] = p
            outcome = happened(actual, cut, event)
            for model, p in odds.items():
                rows.append({"series_id": spec.id, "domain": spec.domain, "origin": str(origin), "event": event,
                             "model": model, "threshold": cut, "p": p, "outcome": outcome, "brier": (p - outcome) ** 2})
    return pd.DataFrame(rows)


def _dm(g: pd.DataFrame, key: str, lag: int) -> float:
    from .monitor import diebold_mariano
    d = g.groupby(key).apply(lambda x: (x["brier"] - x["clim_brier"]).mean(), include_groups=False)
    if len(d) < MIN_BATCHES:
        return float("nan")
    return diebold_mariano(d.to_numpy(), lag)[1]


def summarize(rows: pd.DataFrame | None, key: str = "origin", lag: int = 0) -> pd.DataFrame:
    """Per scope ("all", each area, each series), event and forecaster: forecasts, how often the
    event happened, the mean odds given, the Brier score, the skill against climatology and against
    persistence on the same forecasts, and the Diebold-Mariano p-value of the edge over climatology."""
    if rows is None or rows.empty:
        return pd.DataFrame()
    ids = ["series_id", key, "event"]
    base = rows[rows["model"].isin(BASELINES)].pivot_table(index=ids, columns="model", values="brier").reset_index()
    base = base.rename(columns={CLIMATOLOGY: "clim_brier", PERSISTENCE: "pers_brier"})
    paired = rows.merge(base, on=ids)
    out = []
    scopes = [("all", paired), *((d, p) for d, p in paired.groupby("domain")), *paired.groupby("series_id")]
    for scope, part in scopes:
        for (event, model), g in part.groupby(["event", "model"]):
            out.append({"scope": scope, "event": event, "model": model, "forecasts": int(len(g)),
                        "series": int(g["series_id"].nunique()), "origins": int(g[key].nunique()),
                        "happened": float(g["outcome"].mean()), "said": float(g["p"].mean()), "brier": float(g["brier"].mean()),
                        "skill_clim": float(1 - g["brier"].mean() / g["clim_brier"].mean()) if g["clim_brier"].mean() > 0 else float("nan"),
                        "skill_pers": float(1 - g["brier"].mean() / g["pers_brier"].mean()) if g["pers_brier"].mean() > 0 else float("nan"),
                        "p": _dm(g, key, lag) if model != CLIMATOLOGY else float("nan")})
    table = pd.DataFrame(out)
    return table.sort_values(["scope", "event", "brier"]).reset_index(drop=True)


def forecast_rows(specs: list[SeriesSpec], data: dict[str, pd.Series], sealed: pd.DataFrame | None,
                  made_on: date | str | None = None) -> pd.DataFrame:
    """The odds to seal from a batch of sealed forecasts (``sealed``: one day's main-ledger rows):
    every model's, at the horizon, plus the two baselines, with each threshold fixed from the
    history up to the forecast's last day."""
    if sealed is None or sealed.empty:
        return pd.DataFrame(columns=COLUMNS)
    made_on = str(made_on or sealed["made_on"].iloc[0])
    rows = []
    for spec in specs:
        series = data.get(spec.id)
        if not eligible(spec) or series is None:
            continue
        mine = sealed[(sealed["series_id"] == spec.id) & (sealed["step"] == spec.horizon)]
        if mine.empty:
            continue
        last_date = pd.Timestamp(mine["last_date"].iloc[0])
        history = series[series.index <= last_date].dropna().to_numpy(float)
        target = str(mine["target_date"].iloc[0])
        for event in EVENTS:
            cut = threshold(history, event)
            if cut is None:
                continue
            odds = baselines(history, cut, event, spec.horizon)
            for row in mine.itertuples(index=False):
                p = probability(row.q10, row.q50, row.q90, cut, EVENTS[event][1])
                if p is not None:
                    odds[row.model] = p
            for model, p in odds.items():
                rows.append({"made_on": made_on, "model": model, "series_id": spec.id, "event": event,
                             "last_date": last_date.date().isoformat(), "last_value": float(mine["last_value"].iloc[0]),
                             "threshold": cut, "horizon": int(spec.horizon), "target_date": target, "p": p})
    return pd.DataFrame(rows, columns=COLUMNS)


def append(rows: pd.DataFrame, path: Path = EVENT_LEDGER) -> pd.DataFrame:
    """Add a batch to the event ledger (a same-day re-run replaces that day's rows)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 1:
        rows = pd.concat([pd.read_csv(path), rows], ignore_index=True)
        rows = rows.drop_duplicates(["made_on", "model", "series_id", "event"], keep="last")
    rows.to_csv(path, index=False)
    return rows


def read(path: Path) -> pd.DataFrame | None:
    return pd.read_csv(path) if path.exists() and path.stat().st_size > 1 else None


def score(entries: pd.DataFrame | None, data: dict[str, pd.Series], domain_of: dict[str, str]) -> pd.DataFrame:
    """Open every sealed event forecast whose day has passed: did the event happen, and its Brier."""
    columns = COLUMNS + ["domain", "outcome", "brier"]
    if entries is None or entries.empty:
        return pd.DataFrame(columns=columns)
    out = []
    for row in entries.itertuples(index=False):
        series = data.get(row.series_id)
        target = pd.Timestamp(row.target_date)
        if series is None or target > series.index[-1]:
            continue
        near = series[(series.index >= target - pd.Timedelta(days=3)) & (series.index <= target)].dropna()
        if near.empty:
            continue
        outcome = happened(float(near.iloc[-1]), float(row.threshold), row.event)
        out.append({**row._asdict(), "domain": domain_of.get(row.series_id, ""), "outcome": outcome, "brier": (row.p - outcome) ** 2})
    return pd.DataFrame(out, columns=columns)


def live_record(scored: pd.DataFrame | None) -> pd.DataFrame:
    """The sealed record so far, scored like the backtest over the weekly batches."""
    if scored is None or scored.empty:
        return pd.DataFrame()
    table = summarize(scored, key="made_on", lag=3)
    table = table[table["scope"] == "all"].drop(columns="scope")
    table["verdict"] = table.apply(_verdict, axis=1)
    return table.reset_index(drop=True)


def _verdict(row) -> str:
    if row["model"] in BASELINES:
        return "a baseline"
    if row["origins"] < MIN_BATCHES:
        return f"too early: {row['origins']} of {MIN_BATCHES} weekly batches"
    if row["p"] < 0.05:
        return "better odds than climatology" if row["skill_clim"] > 0 else "worse odds than climatology"
    return "not distinguishable from climatology"


def describe(summary: pd.DataFrame | None, live: pd.DataFrame | None, now: pd.DataFrame | None = None) -> str:
    """Terminal text: today's odds, the backtest verdict and the live record."""
    lines = []
    if now is not None and not now.empty:
        lines.append(f"Event odds, {now['made_on'].iloc[0]}, for the forecasts' target dates (four weeks ahead):")
        lines.append(f"{'series':18} {'event':6} {'threshold':>11} {'last':>10} " + " ".join(f"{m[:11]:>11}" for m in _models(now)))
        for (sid, event), g in now.groupby(["series_id", "event"], sort=True):
            p = g.set_index("model")["p"]
            lines.append(f"{sid:18} {event:6} {g['threshold'].iloc[0]:>11.4g} {g['last_value'].iloc[0]:>10.4g} "
                         + " ".join(f"{p.get(m, float('nan')):>11.0%}" for m in _models(now)))
        lines.append("")
    if summary is not None and not summary.empty:
        part = summary[summary["scope"] == "all"]
        lines.append("Event odds backtest, news and technology (Brier skill: above 0 beats the baseline):")
        lines.append(f"{'event':6} {'forecaster':14} {'forecasts':>9} {'happened':>9} {'said':>6} {'Brier':>7} {'vs climatology':>15} {'vs persistence':>15} {'p':>6}")
        for r in part.itertuples(index=False):
            p = "" if pd.isna(r.p) else f"{r.p:.3f}"
            lines.append(f"{r.event:6} {r.model:14} {r.forecasts:>9} {r.happened:>9.0%} {r.said:>6.0%} {r.brier:>7.4f} "
                         f"{r.skill_clim:>+15.1%} {r.skill_pers:>+15.1%} {p:>6}")
    if live is not None and not live.empty:
        lines += ["", "Sealed event odds scored so far:"]
        for r in live.itertuples(index=False):
            lines.append(f"  {r.event:6} {r.model:14} {r.forecasts:>4} forecasts  vs climatology {r.skill_clim:+.1%}  {r.verdict}")
    elif summary is not None:
        lines += ["", "No sealed event odds have come due yet; `psychohistory predict` seals them every week."]
    return "\n".join(lines)


def _models(frame: pd.DataFrame) -> list[str]:
    models = list(dict.fromkeys(frame["model"]))
    return [m for m in models if m not in BASELINES] + [m for m in BASELINES if m in models]
