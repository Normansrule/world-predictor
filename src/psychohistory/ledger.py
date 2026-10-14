"""The prediction ledger: forecasts written down *before* the future happens, then scored.

Backtests can be fooled (a model may have been trained on the very period it is tested on;
TimesFM's pretraining corpus includes public data up to its release). The only fully honest
test of foresight is to publish predictions with a timestamp and check them later, which is
exactly what Seldon did with his recorded messages in the Time Vault.

``predict`` appends rows to ``predictions/ledger.csv``; ``score`` matches them with actual values
once those dates have passed and writes ``predictions/scored.csv``.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from .catalog import SeriesSpec
from .models import Forecaster

LEDGER = Path("predictions/ledger.csv")
SCORED = Path("predictions/scored.csv")

COLUMNS = [
    "made_on", "model", "series_id", "domain", "scale", "last_date", "last_value",
    "step", "target_date", "q10", "q50", "q90", "point",
]


def future_dates(last: pd.Timestamp, horizon: int, freq: str) -> pd.DatetimeIndex:
    offset = pd.tseries.frequencies.to_offset(freq)
    return pd.date_range(last + offset, periods=horizon, freq=freq)


def predict(
    specs: list[SeriesSpec],
    data: dict[str, pd.Series],
    model: Forecaster,
    max_context: int = 1024,
    made_on: date | None = None,
) -> pd.DataFrame:
    made_on = made_on or date.today()
    specs = [s for s in specs if s.id in data]
    rows = []
    # Group by horizon so each model call is one batch.
    for horizon in sorted({s.horizon for s in specs}):
        group = [s for s in specs if s.horizon == horizon]
        contexts = [data[s.id].to_numpy(dtype=float)[-max_context:] for s in group]
        for spec, forecast in zip(group, model.forecast(contexts, horizon)):
            series = data[spec.id]
            dates = future_dates(series.index[-1], horizon, spec.freq)
            for step, target in enumerate(dates):
                rows.append(
                    {
                        "made_on": made_on.isoformat(),
                        "model": model.name,
                        "series_id": spec.id,
                        "domain": spec.domain,
                        "scale": spec.scale,
                        "last_date": series.index[-1].date().isoformat(),
                        "last_value": float(series.iloc[-1]),
                        "step": step + 1,
                        "target_date": target.date().isoformat(),
                        "q10": float(forecast.q(0.1)[step]),
                        "q50": float(forecast.q(0.5)[step]),
                        "q90": float(forecast.q(0.9)[step]),
                        "point": float(forecast.point[step]),
                    }
                )
    return pd.DataFrame(rows, columns=COLUMNS)


def append(rows: pd.DataFrame, path: Path = LEDGER) -> pd.DataFrame:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = pd.read_csv(path)
        rows = pd.concat([existing, rows], ignore_index=True)
        # Re-running on the same day replaces that day's predictions instead of duplicating them.
        rows = rows.drop_duplicates(["made_on", "model", "series_id", "step"], keep="last")
    rows.to_csv(path, index=False)
    return rows


def score(ledger: pd.DataFrame, data: dict[str, pd.Series]) -> pd.DataFrame:
    """Attach the actual value to every ledger row whose target date has arrived."""
    actuals = []
    for _, row in ledger.iterrows():
        series = data.get(row["series_id"])
        value = np.nan
        if series is not None:
            target = pd.Timestamp(row["target_date"])
            if target in series.index:
                value = float(series.loc[target])
        actuals.append(value)
    scored = ledger.assign(actual=actuals).dropna(subset=["actual"])
    scored["abs_error"] = (scored["actual"] - scored["point"]).abs()
    scored["naive_abs_error"] = (scored["actual"] - scored["last_value"]).abs()
    scored["in_band80"] = (scored["actual"] >= scored["q10"]) & (scored["actual"] <= scored["q90"])
    true_move = np.sign(scored["actual"] - scored["last_value"])
    pred_move = np.sign(scored["point"] - scored["last_value"])
    scored["direction_correct"] = np.where((true_move != 0) & (pred_move != 0), (true_move == pred_move).astype(float), np.nan)
    return scored


def ledger_summary(scored: pd.DataFrame) -> pd.DataFrame:
    """Per domain and model. Skill is computed per series first (so a big-number series such as
    Bitcoin cannot dominate), then the median across series is reported."""
    if scored.empty:
        return pd.DataFrame()
    per_series = scored.groupby(["domain", "model", "series_id"]).agg(
        predictions=("actual", "size"),
        mae=("abs_error", "mean"),
        naive_mae=("naive_abs_error", "mean"),
        direction=("direction_correct", "mean"),
        coverage80=("in_band80", "mean"),
    )
    per_series["skill"] = 1 - per_series["mae"] / per_series["naive_mae"].replace(0, np.nan)
    return (
        per_series.groupby(["domain", "model"])
        .agg(
            series=("mae", "size"),
            predictions=("predictions", "sum"),
            median_skill=("skill", "median"),
            direction=("direction", "mean"),
            coverage80=("coverage80", "mean"),
        )
        .reset_index()
    )
