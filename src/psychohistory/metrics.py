"""Forecast accuracy and calibration metrics.

* MAE / RMSE / sMAPE - plain accuracy of the point forecast.
* MASE - MAE divided by the in-sample MAE of a one-step naive forecast, so series of very
  different sizes (gold in dollars, news share in percent) can be averaged together.
  Below 1 means "better than guessing yesterday's value would have been in the past".
* Direction - did the forecast get the sign of the change over the horizon right?
* Coverage80 - share of actual values inside the forecast's 10%-90% band. A calibrated model
  scores about 0.80; much lower means overconfident, much higher means vague.
* Brier - squared error of the forecast's probability that the series ends the horizon higher
  than it started (0 is perfect, 0.25 is a coin flip). Turns forecasts into checkable odds.
* Pinball - mean quantile loss across the deciles (scaled like MASE). Rewards forecasts that
  are both sharp and honest about uncertainty.
"""

from __future__ import annotations

import numpy as np

from .models import QUANTILES, Forecast


def prob_above(deciles: np.ndarray, threshold: float) -> float:
    """Probability that the outcome exceeds ``threshold``, read off the forecast's deciles by
    linear interpolation. Tails beyond the 10% / 90% deciles are capped at 5% / 95% because the
    forecast says nothing more precise about them."""
    cdf = np.interp(threshold, np.asarray(deciles, dtype=float), np.asarray(QUANTILES), left=0.05, right=0.95)
    return float(1 - cdf)


def naive_scale(train: np.ndarray) -> float:
    diffs = np.abs(np.diff(train))
    scale = float(np.mean(diffs)) if len(diffs) else 0.0
    return scale if scale > 0 else 1.0


def score(train: np.ndarray, actual: np.ndarray, forecast: Forecast) -> dict[str, float]:
    h = len(actual)
    point = forecast.point[:h]
    quantiles = forecast.quantiles[:h]
    err = actual - point
    scale = naive_scale(train)
    last = train[-1]

    denom = np.abs(actual) + np.abs(point)
    smape = float(np.mean(np.where(denom > 0, 2 * np.abs(err) / np.where(denom > 0, denom, 1), 0.0)))

    true_move = np.sign(actual[-1] - last)
    pred_move = np.sign(point[-1] - last)
    # A forecast of "no change" makes no directional call, so it is not scored on direction.
    direction = float(true_move == pred_move) if true_move != 0 and pred_move != 0 else np.nan

    q = np.asarray(QUANTILES)
    diff = actual[:, None] - quantiles
    pinball = float(np.mean(np.maximum(q * diff, (q - 1) * diff))) / scale

    lo, hi = forecast.q(0.1)[:h], forecast.q(0.9)[:h]
    coverage = float(np.mean((actual >= lo) & (actual <= hi)))

    p_up = prob_above(quantiles[-1], last)
    brier = (p_up - float(actual[-1] > last)) ** 2

    return {
        "mae": float(np.mean(np.abs(err))),
        "rmse": float(np.sqrt(np.mean(err**2))),
        "smape": smape,
        "mase": float(np.mean(np.abs(err))) / scale,
        "direction": direction,
        "coverage80": coverage,
        "pinball": pinball,
        "brier": brier,
    }
