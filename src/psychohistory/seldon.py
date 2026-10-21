"""Seldon: TimesFM that learns from its own track record.

TimesFM is a general model: it has never seen how well its own forecasts did on a given series.
Seldon wraps it with two corrections, each learned only from forecast windows that had already
finished before the new forecast is made (so it never peeks at the future):

1. **Shrink toward "no change".** Where TimesFM's predicted moves have not paid off before (most
   markets), its median is pulled back toward the last value; where they have (technology
   attention), it is left alone. ``shrink`` is the share of TimesFM's move that is kept.
2. **Recalibrate the range.** The band around the median is stretched or narrowed until it would
   have caught reality about 8 times in 10 in the earlier windows. ``spread`` is that factor.

Both are chosen on a small grid, separately for every series. A shrink is only used when it
would have cut the earlier error by at least ``MARGIN``, so noise in a handful of windows does not
move the forecast. With fewer than ``MIN_WINDOWS`` finished windows there is nothing to learn from
yet and Seldon returns TimesFM unchanged.

It is a challenger, scored on exactly the same windows as TimesFM, and it is allowed to lose.

The same functions run in three places: the backtest (one window after another, in order), the
weekly sealed forecasts (learning from the saved backtest paths), and the web app's Lab export.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
import pandas as pd

from .models import QUANTILES, Forecast

NAME = "seldon"
MIN_WINDOWS = 2
MARGIN = 0.03  # a shrink must have cut past error by 3% to be used
SHRINK_GRID = np.round(np.linspace(0.0, 1.0, 11), 2)
SPREAD_GRID = np.round(np.linspace(0.5, 3.0, 26), 2)
TARGET = 0.8  # share of reality the 80% range should catch
_MID = QUANTILES.index(0.5)


@dataclass
class Window:
    """One finished forecast window of the base model: the value at the origin, its deciles
    (or just q10 / q50 / q90) for each step, and what really happened."""

    last: float
    q10: np.ndarray
    q50: np.ndarray
    q90: np.ndarray
    actual: np.ndarray


@dataclass
class Correction:
    shrink: float = 1.0
    spread: float = 1.0
    windows: int = 0


def learn(windows: Sequence[Window]) -> Correction:
    """Pick the shrink and spread that would have done best on these finished windows."""
    windows = [w for w in windows if len(w.actual) and np.isfinite(w.last)]
    if len(windows) < MIN_WINDOWS:
        return Correction(windows=len(windows))
    # Shrink: minimise mean absolute error of last + shrink * (median - last).
    errors = [
        np.mean([np.mean(np.abs(w.last + s * (w.q50[: len(w.actual)] - w.last) - w.actual)) / _scale(w) for w in windows])
        for s in SHRINK_GRID
    ]
    best_i = int(np.argmin(errors))
    shrink = float(SHRINK_GRID[best_i]) if errors[best_i] <= errors[-1] * (1 - MARGIN) else 1.0
    # Spread: the factor whose stretched 80% range comes closest to catching reality 80% of the time;
    # ties go to the narrower range, which is the more useful forecast.
    best, spread = np.inf, 1.0
    for f in SPREAD_GRID:
        inside = []
        for w in windows:
            h = len(w.actual)
            mid = w.last + shrink * (w.q50[:h] - w.last)
            lo = mid + f * (w.q10[:h] - w.q50[:h])
            hi = mid + f * (w.q90[:h] - w.q50[:h])
            inside.append(np.mean((w.actual >= lo) & (w.actual <= hi)))
        gap = abs(float(np.mean(inside)) - TARGET)
        if gap < best - 1e-9:
            best, spread = gap, float(f)
    return Correction(shrink, spread, len(windows))


def _scale(w: Window) -> float:
    """Normalise errors so a series with big numbers does not dominate the choice."""
    return max(float(np.abs(w.last)), 1e-9)


def apply(forecast: Forecast, last: float, c: Correction) -> Forecast:
    """Seldon's forecast: the base forecast with the learned correction applied to every decile."""
    mid = forecast.quantiles[:, _MID]
    new_mid = last + c.shrink * (mid - last)
    quantiles = new_mid[:, None] + c.spread * (forecast.quantiles - mid[:, None])
    point = last + c.shrink * (forecast.point - last)
    return Forecast(point, np.sort(quantiles, axis=1))


def apply_bands(last: float, q10, q50, q90, c: Correction) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The same correction on a saved q10 / q50 / q90 path (what the backtest paths keep)."""
    q10, q50, q90 = (np.asarray(a, dtype=float) for a in (q10, q50, q90))
    mid = last + c.shrink * (q50 - last)
    return mid + c.spread * (q10 - q50), mid, mid + c.spread * (q90 - q50)


def online(base: Sequence[Forecast], lasts: Sequence[float], actuals: Sequence[np.ndarray],
           ends: Sequence[int], starts: Sequence[int]) -> list[tuple[Forecast, Correction]]:
    """Walk the backtest windows in time order. Window k may learn only from windows whose
    actual values were all known by its origin (``ends[j] <= starts[k]``)."""
    out = []
    for k, forecast in enumerate(base):
        done = [
            Window(lasts[j], base[j].q(0.1), base[j].q(0.5), base[j].q(0.9), actuals[j])
            for j in range(len(base)) if ends[j] <= starts[k] and j != k
        ]
        c = learn(done)
        out.append((apply(forecast, lasts[k], c), c))
    return out


def windows_from_paths(paths: pd.DataFrame, series_id: str, model: str, before: str | None = None) -> list[Window]:
    """Finished windows of ``model`` for one series from ``results/backtest_paths.csv``. The value
    at each origin is the last actual of the window before it (the windows are back to back);
    the first window has no known origin value and is skipped."""
    rows = paths[(paths["series_id"] == series_id) & (paths["model"] == model)]
    if before is not None:
        rows = rows[rows["date"].astype(str) <= str(before)]
    groups = [g.sort_values("step") for _, g in rows.groupby("origin", sort=True)]
    out = []
    for prev, cur in zip(groups, groups[1:]):
        out.append(Window(float(prev["actual"].iloc[-1]), cur["q10"].to_numpy(float), cur["q50"].to_numpy(float),
                          cur["q90"].to_numpy(float), cur["actual"].to_numpy(float)))
    return out


def correction_for(paths: pd.DataFrame | None, series_id: str, model: str) -> Correction:
    """The correction for a new, live forecast: learned from every finished backtest window."""
    if paths is None or paths.empty:
        return Correction()
    return learn(windows_from_paths(paths, series_id, model))
