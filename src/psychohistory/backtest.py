"""Rolling-origin backtesting: pretend it is a past date, forecast, then check against what happened.

For each series we pick ``windows`` forecast origins in the past, spaced ``horizon`` steps apart
and ending ``horizon`` steps before the latest data point. At each origin the model only sees
data up to that day. No future information leaks into any forecast.
"""

from __future__ import annotations

import logging

import pandas as pd

from .catalog import SeriesSpec
from .metrics import score
from .models import Forecaster

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
) -> pd.DataFrame:
    y = series.to_numpy(dtype=float)
    horizon = spec.horizon
    cuts = origins(len(y), horizon, windows, min_train=max(2 * horizon, 16))
    if not cuts:
        log.warning("%s: too short to backtest (%d points)", spec.id, len(y))
        return pd.DataFrame()

    contexts = [y[max(0, t - max_context) : t] for t in cuts]
    rows = []
    for model in models:
        forecasts = model.forecast(contexts, horizon)
        for t, context, forecast in zip(cuts, contexts, forecasts):
            actual = y[t : t + horizon]
            rows.append(
                {
                    "series_id": spec.id,
                    "domain": spec.domain,
                    "scale": spec.scale,
                    "model": model.name,
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
    metrics = ["mae", "mase", "smape", "direction", "coverage80", "pinball"]
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

