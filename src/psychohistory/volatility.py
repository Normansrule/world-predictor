"""Volatility forecasts: not where a market goes, but how far it is likely to swing.

Prices are close to a random walk, so a level forecast rarely beats "no change". The size of the
moves is different: calm weeks follow calm weeks and storms follow storms (Mandelbrot, 1963), which
is why volatility is the part of a market that can really be forecast. This module forecasts the
volatility of every market over the next week and month four ways:

* ``garch``: GARCH(1,1) (Bollerslev, 1986), fitted by maximum likelihood on up to four years of daily
  log returns, with the long-run variance fixed to the sample's ("variance targeting");
* ``ewma``: RiskMetrics' exponentially weighted average of squared returns, lambda = 0.94;
* the model under test and Seldon: the volatility their sealed 80% range implies, read as a
  log-normal range (the same reading as the Markets desk);
* ``last-month``, the baseline: the volatility of the last month's returns, carried forward.

Each is scored against the volatility that then happened (the mean squared daily log return over
the window) with QLIKE, the loss that ranks volatility forecasts the same way whatever the noise in
the realized measure (Patton, 2011): ``realized / forecast - ln(realized / forecast) - 1``, zero
for a perfect forecast. Skill is ``1 - QLIKE(model) / QLIKE(last-month)`` on the same windows.

``backtest`` replays this over past origins; ``forecast_rows`` seals the live forecasts in
``predictions/vol_ledger.csv`` (fingerprinted like the main ledger) and ``score`` opens them once
their window has passed, so the volatility record builds itself week by week, for years.
"""

from __future__ import annotations

import math
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from .catalog import SeriesSpec

GARCH = "garch"
EWMA = "ewma"
NAIVE = "last-month"
BUILT_IN = (GARCH, EWMA, NAIVE)
HORIZONS = {"B": (5, 21), "D": (7, 28)}  # one week and one month, in trading or calendar days
MONTH = {"B": 21, "D": 30}
LAMBDA = 0.94
MIN_TRAIN = 250  # about a year of returns before the first backtest origin
MAX_TRAIN = 1000  # GARCH is fitted on up to four years
EVERY = 5  # a backtest origin every week
MIN_BATCHES = 4
_Z90 = 1.2815515655446004

VOL_LEDGER = Path("predictions/vol_ledger.csv")
VOL_SCORED = Path("predictions/vol_scored.csv")
VOL_SEALS = Path("predictions/vol_seals.csv")
COLUMNS = ["made_on", "model", "series_id", "last_date", "last_value", "horizon", "target_date", "vol"]
LAYOUT = {"columns": COLUMNS, "order": ("series_id", "horizon")}  # how ledger.fingerprint reads a batch

_ALPHAS, _BETAS = np.meshgrid(np.arange(0.01, 0.31, 0.01), np.arange(0.50, 0.995, 0.01))
_GRID = (_ALPHAS + _BETAS) < 0.999
_ALPHAS, _BETAS = _ALPHAS[_GRID], _BETAS[_GRID]


def periods_per_year(freq: str) -> int:
    return {"B": 252, "D": 365, "YS": 1}.get(freq, 252)


def horizons(freq: str) -> tuple[int, ...]:
    return HORIZONS.get(freq, ())


def label(horizon: int, freq: str) -> str:
    return "1 week" if horizon == horizons(freq)[0] else "1 month"


def log_returns(values: np.ndarray) -> np.ndarray | None:
    values = np.asarray(values, dtype=float)
    if len(values) < 3 or not np.isfinite(values).all() or (values <= 0).any():
        return None
    return np.diff(np.log(values))


def annual(variance: float, freq: str) -> float:
    """A per-step variance as an annualised volatility."""
    return float(math.sqrt(max(variance, 0.0) * periods_per_year(freq)))


def ewma_variance(r: np.ndarray, lam: float = LAMBDA) -> float:
    v = float(np.mean(r[:20] ** 2))
    for x in r:
        v = lam * v + (1 - lam) * x * x
    return v


def fit_garch(r: np.ndarray) -> dict:
    """GARCH(1,1) by maximum likelihood over a grid of (alpha, beta), every point run at once.
    The long-run variance is the sample's, so omega = var x (1 - alpha - beta)."""
    r = r[-MAX_TRAIN:]
    var = float(np.mean(r ** 2)) or 1e-12
    omega = var * (1 - _ALPHAS - _BETAS)
    h = np.full(len(_ALPHAS), var)
    nll = np.zeros(len(_ALPHAS))
    for x in r:
        nll += np.log(h) + x * x / h
        h = omega + _ALPHAS * x * x + _BETAS * h
    best = int(np.argmin(nll))
    return {"alpha": float(_ALPHAS[best]), "beta": float(_BETAS[best]), "var": var, "next": float(h[best])}


def garch_variance(fit: dict, steps: int) -> float:
    """Mean expected per-step variance over the next ``steps``: it decays from tomorrow's towards
    the long-run variance at the rate alpha + beta."""
    persist = fit["alpha"] + fit["beta"]
    k = np.arange(steps)
    return float(np.mean(fit["var"] + persist ** k * (fit["next"] - fit["var"])))


def implied_variance(q10: float, q90: float, steps: int) -> float | None:
    """The per-step variance an 80% range ``steps`` ahead implies, read as log-normal."""
    if not (q10 > 0 and q90 > 0) or steps < 1 or q90 <= q10:
        return None
    return float(((math.log(q90) - math.log(q10)) / (2 * _Z90)) ** 2 / steps)


def built_in(r: np.ndarray, freq: str, steps: list[int] | tuple[int, ...]) -> dict[str, dict[int, float]]:
    """The three built-in forecasts of the per-step variance over each horizon."""
    fit = fit_garch(r)
    ewma = ewma_variance(r)
    naive = float(np.mean(r[-MONTH.get(freq, 21):] ** 2))
    return {GARCH: {h: garch_variance(fit, h) for h in steps}, EWMA: {h: ewma for h in steps}, NAIVE: {h: naive for h in steps}}


def qlike(realized: np.ndarray | float, forecast: np.ndarray | float) -> np.ndarray | float:
    ratio = np.asarray(realized, dtype=float) / np.asarray(forecast, dtype=float)
    return ratio - np.log(ratio) - 1


def backtest(spec: SeriesSpec, series: pd.Series, paths: pd.DataFrame | None = None,
             every: int = EVERY, min_train: int = MIN_TRAIN) -> pd.DataFrame:
    """Rolling-origin volatility backtest of one market: at every origin each forecaster sees only
    the returns up to it. ``paths`` (the saved backtest paths) gives the model under test's and
    Seldon's ranges at their own origins, read as implied volatility."""
    steps = horizons(spec.freq)
    r = log_returns(series.to_numpy(dtype=float)) if steps else None
    if r is None or len(r) < min_train + max(steps):
        return pd.DataFrame()
    dates = series.index
    implied = {}
    if paths is not None and not paths.empty:
        mine = paths[(paths["series_id"] == spec.id) & paths["step"].isin(steps)]
        for row in mine.itertuples(index=False):
            v = implied_variance(row.q10, row.q90, int(row.step))
            if v is not None:
                implied[(pd.Timestamp(row.origin), int(row.step), row.model)] = v
    rows = []
    position = {d: i for i, d in enumerate(dates)}
    origins = set(range(min_train, len(r) - min(steps) + 1, every))
    origins |= {position[o] for o, _, _ in implied if o in position and position[o] >= 20}  # every implied origin too
    for t in sorted(origins):
        # returns r[:t] end at price t; the window ahead is r[t:t + h]
        fits = built_in(r[:t], spec.freq, steps) if t >= min_train else {}
        for h in steps:
            if t + h > len(r):
                continue
            realized = float(np.mean(r[t:t + h] ** 2))
            if realized <= 0:
                continue
            forecasts = {name: f[h] for name, f in fits.items()}
            origin = pd.Timestamp(dates[t])
            forecasts |= {m: v for (o, s, m), v in implied.items() if o == origin and s == h}
            if NAIVE not in forecasts:  # an implied-only origin still needs its baseline
                forecasts[NAIVE] = float(np.mean(r[max(0, t - MONTH.get(spec.freq, 21)):t] ** 2))
            for name, variance in forecasts.items():
                if variance > 0:
                    rows.append({"series_id": spec.id, "origin": origin.date().isoformat(), "horizon": h,
                                 "span": label(h, spec.freq), "model": name,
                                 "vol": annual(variance, spec.freq), "realized": annual(realized, spec.freq),
                                 "qlike": float(qlike(realized, variance))})
    return pd.DataFrame(rows)


def _versus_naive(part: pd.DataFrame, key: str) -> pd.DataFrame:
    """Every forecast with the "last month" forecast for the same window beside it."""
    naive = part[part["model"] == NAIVE][["series_id", key, "horizon", "qlike"]].rename(columns={"qlike": "naive_qlike"})
    naive = naive.drop_duplicates(["series_id", key, "horizon"])
    return part.merge(naive, on=["series_id", key, "horizon"])


def _dm(paired: pd.DataFrame, key: str, lag: int) -> float:
    from .monitor import diebold_mariano  # the monitor's test, on the same kind of overlapping windows
    d = paired.groupby(key).apply(lambda g: (g["qlike"] - g["naive_qlike"]).mean(), include_groups=False)
    if len(d) < MIN_BATCHES:
        return float("nan")
    _, p = diebold_mariano(d.to_numpy(), lag)
    return p


def summarize(rows: pd.DataFrame, key: str = "origin", every: int = EVERY) -> pd.DataFrame:
    """Per market (and "all"), span (a week or a month ahead) and forecaster: windows, QLIKE, skill
    against last month's volatility on the same windows, the typical miss (median |forecast /
    realized - 1|), the Diebold-Mariano p-value of that skill and, for "all", in how many markets
    the forecaster beat last month's volatility."""
    if rows is None or rows.empty:
        return pd.DataFrame()
    paired = _versus_naive(rows, key)
    out = []
    for scope, part in [("all", paired), *paired.groupby("series_id")]:
        for (span, model), g in part.groupby(["span", "model"]):
            h = int(g["horizon"].max())
            lag = max(0, math.ceil(h / every) - 1)
            per = g.groupby("series_id")[["qlike", "naive_qlike"]].mean()
            out.append({"series_id": scope, "span": span, "horizon": h if scope != "all" else None, "model": model,
                        "windows": int(len(g)), "markets": int(len(per)), "beaten": int((per["qlike"] < per["naive_qlike"]).sum()),
                        "first": str(g[key].min()), "last": str(g[key].max()),
                        "qlike": float(g["qlike"].mean()), "skill": float(1 - g["qlike"].mean() / g["naive_qlike"].mean()),
                        "miss": float((g["vol"] / g["realized"] - 1).abs().median()),
                        "p": _dm(g, key, lag) if model != NAIVE else float("nan")})
    order = {"1 week": 0, "1 month": 1}
    table = pd.DataFrame(out)
    table["_o"] = table["span"].map(order)
    table = table.sort_values(["series_id", "_o", "skill"], ascending=[True, True, False]).drop(columns="_o")
    return table.reset_index(drop=True)


def forecast_rows(specs: list[SeriesSpec], data: dict[str, pd.Series], sealed: pd.DataFrame | None = None,
                  made_on: date | None = None) -> pd.DataFrame:
    """Today's volatility forecasts for every market, to seal: the built-in three, plus the volatility
    each model's freshly sealed range implies (``sealed``: today's main-ledger rows)."""
    made_on = (made_on or date.today()).isoformat()
    from .ledger import future_dates
    rows = []
    for spec in specs:
        steps = horizons(spec.freq)
        series = data.get(spec.id)
        r = log_returns(series.to_numpy(dtype=float)) if series is not None and steps else None
        if r is None or len(r) < 60:
            continue
        dates = future_dates(series.index[-1], max(steps), spec.freq)
        forecasts = built_in(r, spec.freq, steps)
        if sealed is not None and not sealed.empty:
            mine = sealed[(sealed["series_id"] == spec.id) & sealed["step"].isin(steps)]
            for row in mine.itertuples(index=False):
                v = implied_variance(row.q10, row.q90, int(row.step))
                if v is not None:
                    forecasts.setdefault(row.model, {})[int(row.step)] = v
        for name, by_h in forecasts.items():
            for h, variance in sorted(by_h.items()):
                rows.append({"made_on": made_on, "model": name, "series_id": spec.id,
                             "last_date": series.index[-1].date().isoformat(), "last_value": float(series.iloc[-1]),
                             "horizon": int(h), "target_date": dates[h - 1].date().isoformat(), "vol": annual(variance, spec.freq)})
    return pd.DataFrame(rows, columns=COLUMNS)


def append(rows: pd.DataFrame, path: Path = VOL_LEDGER) -> pd.DataFrame:
    """Add a batch to the volatility ledger (a same-day re-run replaces that day's rows)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 1:
        rows = pd.concat([pd.read_csv(path), rows], ignore_index=True)
        rows = rows.drop_duplicates(["made_on", "model", "series_id", "horizon"], keep="last")
    rows.to_csv(path, index=False)
    return rows


def read(path: Path) -> pd.DataFrame | None:
    return pd.read_csv(path) if path.exists() and path.stat().st_size > 1 else None


def score(entries: pd.DataFrame | None, data: dict[str, pd.Series], freq_of: dict[str, str]) -> pd.DataFrame:
    """Open every sealed volatility forecast whose window has passed: the realized volatility of the
    returns after ``last_date`` up to ``target_date``, and the forecast's QLIKE."""
    if entries is None or entries.empty:
        return pd.DataFrame(columns=COLUMNS + ["span", "realized", "qlike"])
    out = []
    for row in entries.itertuples(index=False):
        series = data.get(row.series_id)
        if series is None or pd.Timestamp(row.target_date) > series.index[-1]:
            continue
        window = series[(series.index >= pd.Timestamp(row.last_date)) & (series.index <= pd.Timestamp(row.target_date))]
        r = log_returns(window.to_numpy(dtype=float))
        if r is None or len(r) < max(2, row.horizon // 2) or row.vol <= 0:
            continue
        freq = freq_of.get(row.series_id, "B")
        realized = annual(float(np.mean(r ** 2)), freq)
        if realized <= 0:
            continue
        out.append({**row._asdict(), "span": label(int(row.horizon), freq), "realized": realized,
                    "qlike": float(qlike(realized ** 2, row.vol ** 2))})
    return pd.DataFrame(out, columns=COLUMNS + ["span", "realized", "qlike"])


def live_record(scored: pd.DataFrame | None) -> pd.DataFrame:
    """The sealed record so far, per forecaster and horizon, scored like the backtest but over the
    weekly batches (``made_on``), with the test saying "too early" until four batches are in."""
    if scored is None or scored.empty:
        return pd.DataFrame()
    table = summarize(scored, key="made_on")
    table = table[table["series_id"] == "all"].drop(columns="series_id")
    batches = scored.groupby(["model", "span"])["made_on"].nunique().rename("batches").reset_index()
    table = table.drop(columns="horizon").merge(batches, on=["model", "span"])
    table["verdict"] = table.apply(_verdict, axis=1)
    return table.reset_index(drop=True)


def _verdict(row) -> str:
    if row["model"] == NAIVE:
        return "the baseline"
    if row["batches"] < MIN_BATCHES:
        return f"too early: {row['batches']} of {MIN_BATCHES} weekly batches"
    if row["p"] < 0.05:
        return "better than last month's volatility" if row["skill"] > 0 else "worse than last month's volatility"
    return "not distinguishable from last month's volatility"


def describe(summary: pd.DataFrame | None, live: pd.DataFrame | None) -> str:
    """Terminal text: the backtest verdict across markets and the live record so far."""
    lines = []
    if summary is not None and not summary.empty:
        part = summary[summary["series_id"] == "all"]
        lines.append("Volatility backtest, all markets (skill = 1 - QLIKE / QLIKE of last month's volatility):")
        lines.append(f"{'forecaster':14} {'ahead':>8} {'windows':>8} {'skill':>7} {'beat it in':>11} {'typical miss':>13} {'p':>7}")
        for r in part.itertuples(index=False):
            p = "" if pd.isna(r.p) else f"{r.p:.3f}"
            beat = "" if r.model == NAIVE else f"{r.beaten}/{r.markets}"
            lines.append(f"{r.model:14} {r.span:>8} {r.windows:>8} {r.skill:>+7.1%} {beat:>11} {r.miss:>13.0%} {p:>7}")
    if live is not None and not live.empty:
        lines.append("")
        lines.append("Sealed volatility forecasts scored so far:")
        for r in live.itertuples(index=False):
            lines.append(f"  {r.model:14} {r.span:8} {r.windows:>4} forecasts  skill {r.skill:+.1%}  {r.verdict}")
    elif summary is not None:
        lines.append("")
        lines.append("No sealed volatility forecast has come due yet; `psychohistory predict` seals them every week.")
    return "\n".join(lines)
