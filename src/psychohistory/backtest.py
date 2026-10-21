"""Rolling-origin backtesting: pretend it is a past date, forecast, then check against what happened.

For each series we pick ``windows`` forecast origins in the past, spaced ``horizon`` steps apart
and ending ``horizon`` steps before the latest data point. At each origin the model only sees
data up to that day. No future information leaks into any forecast.
"""

from __future__ import annotations

import logging
from typing import Sequence

import numpy as np
import pandas as pd

from . import seldon
from .catalog import SeriesSpec
from .metrics import naive_scale, score
from .models import ENSEMBLE, Forecaster, combine, load_model

log = logging.getLogger(__name__)

MAX_CONTEXT = 1024


def origins(n: int, horizon: int, windows: int, min_train: int) -> list[int]:
    """Indices t such that y[:t] is the training data and y[t:t+horizon] is the test data."""
    last = n - horizon
    out = [last - i * horizon for i in range(windows)]
    return sorted(t for t in out if t >= min_train)


def backtest_series(
    spec: SeriesSpec,
    series: pd.Series,
    models: list[Forecaster],
    windows: int = 12,
    max_context: int = MAX_CONTEXT,
    step_rows: list[dict] | None = None,
    ensemble_of: list[str] | None = None,
    path_rows: list[dict] | None = None,
    paths_for: str | Sequence[str] | None = None,
    seldon_of: str | None = None,
) -> pd.DataFrame:
    """Backtest one series. If ``step_rows`` is given, per-step errors are appended to it for
    the horizon analysis (how fast does skill decay the further ahead we look?). If
    ``ensemble_of`` names models, their quantile-averaged ensemble is scored too. If
    ``path_rows`` is given, the full forecast paths of model ``paths_for`` are appended to it,
    which is what the animated "replay" of forecasts versus reality is drawn from. If ``seldon_of``
    names a model, Seldon's self-calibrated version of it is scored too, learning window by window
    only from windows that had already finished (see ``seldon.py``)."""
    y = series.to_numpy(dtype=float)
    horizon = spec.horizon
    cuts = origins(len(y), horizon, windows, min_train=max(2 * horizon, 16))
    if not cuts:
        log.warning("%s: too short to backtest (%d points)", spec.id, len(y))
        return pd.DataFrame()

    contexts = [y[max(0, t - max_context) : t] for t in cuts]
    names = {m.name for m in models}
    models = models + [load_model(m) for m in spec.extra_models if m not in names]
    by_model = {model.name: model.forecast(contexts, horizon) for model in models}
    members = [m for m in (ensemble_of or []) if m in by_model]
    if len(members) >= 2:
        by_model[ENSEMBLE] = [combine(group) for group in zip(*(by_model[m] for m in members))]
    if seldon_of in by_model:
        corrected = seldon.online(by_model[seldon_of], [float(c[-1]) for c in contexts],
                                  [y[t : t + horizon] for t in cuts], [t + horizon for t in cuts], cuts)
        by_model[seldon.NAME] = [f for f, _ in corrected]
    wanted = {paths_for} if isinstance(paths_for, str) else set(paths_for or ())

    rows = []
    for name, forecasts in by_model.items():
        for t, context, forecast in zip(cuts, contexts, forecasts):
            actual = y[t : t + horizon]
            if path_rows is not None and name in wanted:
                path_rows.extend(
                    {
                        "series_id": spec.id, "model": name, "origin": series.index[t - 1].date(),
                        "date": series.index[t + k].date(), "step": k + 1, "q10": float(forecast.q(0.1)[k]),
                        "q50": float(forecast.q(0.5)[k]), "q90": float(forecast.q(0.9)[k]), "actual": float(actual[k]),
                    }
                    for k in range(len(actual))
                )
            if step_rows is not None and spec.freq != "YS":  # yearly series are too short
                errors = np.abs(actual - forecast.point[:horizon]) / naive_scale(context)
                step_rows.extend(
                    {"series_id": spec.id, "domain": spec.domain, "model": name, "step": k + 1, "scaled_error": float(e)}
                    for k, e in enumerate(errors)
                )
            rows.append(
                {
                    "series_id": spec.id,
                    "domain": spec.domain,
                    "scale": spec.scale,
                    "model": name,
                    "origin": series.index[t - 1].date(),
                    "horizon": horizon,
                    **score(context, actual, forecast),
                }
            )
    return pd.DataFrame(rows)


def summarize(results: pd.DataFrame, baseline: str = "naive") -> pd.DataFrame:
    """One row per (series, model): average metrics plus skill versus the baseline.

    ``skill`` = 1 - MAE(model) / MAE(baseline) over the same windows. Positive means the model
    beat the baseline; 0.2 means 20% less error.
    """
    metrics = ["mae", "mase", "smape", "direction", "coverage80", "pinball", "brier"]  # p_up/went_up feed calibration()
    per_series = results.groupby(["series_id", "domain", "scale", "model"], as_index=False)[metrics].mean()
    base = per_series[per_series["model"] == baseline][["series_id", "mae", "pinball"]]
    base = base.rename(columns={"mae": "baseline_mae", "pinball": "baseline_pinball"})
    per_series = per_series.merge(base, on="series_id", how="left")
    per_series["skill"] = 1 - per_series["mae"] / per_series["baseline_mae"]
    per_series["prob_skill"] = 1 - per_series["pinball"] / per_series["baseline_pinball"]
    return per_series.drop(columns=["baseline_mae", "baseline_pinball"])


def crises(results: pd.DataFrame, model: str, threshold: float = 0.5, top: int = 15) -> pd.DataFrame:
    """"Seldon crises": windows where reality left the model's 80% band most of the time,
    i.e. events the model did not see coming."""
    subset = results[(results["model"] == model) & (results["coverage80"] <= 1 - threshold)]
    return subset.sort_values(["coverage80", "mase"], ascending=[True, False]).head(top)[
        ["series_id", "domain", "origin", "coverage80", "mase"]
    ]


def domain_table(summary: pd.DataFrame) -> pd.DataFrame:
    return (
        summary.groupby(["domain", "model"])
        .agg(
            series=("series_id", "nunique"),
            median_skill=("skill", "median"),
            median_mase=("mase", "median"),
            direction=("direction", "mean"),
            coverage80=("coverage80", "mean"),
            brier=("brier", "mean"),
        )
        .reset_index()
    )


def scale_table(summary: pd.DataFrame) -> pd.DataFrame:
    """Seldon's law of large numbers: are aggregates easier to forecast than individuals?"""
    return (
        summary.groupby(["domain", "scale", "model"])
        .agg(series=("series_id", "nunique"), median_skill=("skill", "median"), median_mase=("mase", "median"))
        .reset_index()
    )



STEP_BUCKETS = [(1, 1, "1 step"), (2, 5, "2-5"), (6, 10, "6-10"), (11, 20, "11-20"), (21, 10**9, "21+")]


def skill_by_step(steps: pd.DataFrame, baseline: str = "naive") -> pd.DataFrame:
    """Skill versus the baseline at each forecast step: per series, then the median per domain.

    This is the "Seldon horizon": the step at which skill falls to zero is as far ahead as the
    model can genuinely see in that domain."""
    mean_err = steps.groupby(["domain", "series_id", "model", "step"], as_index=False)["scaled_error"].mean()
    base = mean_err[mean_err["model"] == baseline].rename(columns={"scaled_error": "baseline_error"})
    merged = mean_err.merge(base.drop(columns="model"), on=["domain", "series_id", "step"])
    merged = merged[merged["baseline_error"] > 0]
    merged["skill"] = 1 - merged["scaled_error"] / merged["baseline_error"]
    return merged.groupby(["domain", "model", "step"], as_index=False)["skill"].median()


def horizon_table(by_step: pd.DataFrame, model: str) -> pd.DataFrame:
    """Median skill in step buckets (rows: domain, columns: how far ahead)."""
    rows = by_step[by_step["model"] == model].copy()
    if rows.empty:
        return pd.DataFrame()
    labels = []
    for step in rows["step"]:
        labels.append(next(label for lo, hi, label in STEP_BUCKETS if lo <= step <= hi))
    rows["ahead"] = labels
    order = [label for _, _, label in STEP_BUCKETS if label in set(labels)]
    table = rows.pivot_table(index="domain", columns="ahead", values="skill", aggfunc="median")
    return table[order].reset_index()


PROBABILITY_BINS = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]


def calibration(results: pd.DataFrame, model: str) -> pd.DataFrame:
    """Reliability table for the "chance it ends higher" odds: group forecasts by the
    probability they gave, then count how often the series really did end higher.

    An honest forecaster's "60-80%" bucket goes up about 70% of the time."""
    rows = results[(results["model"] == model)].dropna(subset=["p_up", "went_up"])
    if rows.empty:
        return pd.DataFrame()
    labels = [f"{lo:.0%}-{hi:.0%}" for lo, hi in zip(PROBABILITY_BINS[:-1], PROBABILITY_BINS[1:])]
    bucket = pd.cut(rows["p_up"], PROBABILITY_BINS, labels=labels, include_lowest=True)
    table = (
        rows.groupby([rows["domain"], bucket], observed=True)
        .agg(forecasts=("p_up", "size"), said=("p_up", "mean"), happened=("went_up", "mean"))
        .reset_index()
        .rename(columns={"p_up": "odds given"})
    )
    return table
