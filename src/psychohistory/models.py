"""Forecasting models: Google's TimesFM plus simple baselines to measure it against.

Every model returns a :class:`Forecast` per input series with a point forecast and the
deciles 0.1 ... 0.9, so models can be scored identically (accuracy *and* calibration).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

import numpy as np

QUANTILES = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)

# Hugging Face checkpoints published by Google Research (https://github.com/google-research/timesfm).
TIMESFM_2P5_CHECKPOINT = "google/timesfm-2.5-200m-pytorch"  # Apache-2.0 weights
TIMESFM_3_CHECKPOINT = "google/timesfm-3.0-pytorch"  # non-commercial weights, see CREDITS.md
# Amazon's rival foundation models (https://github.com/amazon-science/chronos-forecasting).
CHRONOS_BOLT_CHECKPOINT = "amazon/chronos-bolt-small"
CHRONOS_2_CHECKPOINT = "amazon/chronos-2"


@dataclass
class Forecast:
    """A forecast for one series: ``point`` has shape (h,), ``quantiles`` has shape (h, 9)."""

    point: np.ndarray
    quantiles: np.ndarray

    def q(self, level: float) -> np.ndarray:
        return self.quantiles[:, QUANTILES.index(level)]


class Forecaster(Protocol):
    name: str

    def forecast(self, contexts: Sequence[np.ndarray], horizon: int) -> list[Forecast]: ...


def _clean(context: np.ndarray) -> np.ndarray:
    arr = np.asarray(context, dtype=np.float64)
    return arr[np.isfinite(arr)]


# --------------------------------------------------------------------------------------------
# Baselines. A forecasting model is only interesting if it beats these.
# --------------------------------------------------------------------------------------------


class NaiveForecaster:
    """Random walk: tomorrow looks like today. Intervals come from the series' own history of
    k-step changes, so the baseline is calibrated rather than a strawman."""

    name = "naive"

    def forecast(self, contexts: Sequence[np.ndarray], horizon: int) -> list[Forecast]:
        out = []
        for context in contexts:
            y = _clean(context)
            last = y[-1]
            point = np.full(horizon, last)
            quantiles = np.empty((horizon, len(QUANTILES)))
            for k in range(1, horizon + 1):
                diffs = y[k:] - y[:-k] if len(y) > k else np.array([0.0])
                quantiles[k - 1] = last + np.quantile(diffs, QUANTILES)
            # Center the band on the random-walk point forecast.
            quantiles += (point - quantiles[:, QUANTILES.index(0.5)])[:, None]
            out.append(Forecast(point, np.sort(quantiles, axis=1)))
        return out


class DriftForecaster:
    """Random walk with drift: extend the average historical slope."""

    name = "drift"

    def forecast(self, contexts: Sequence[np.ndarray], horizon: int) -> list[Forecast]:
        naive = NaiveForecaster().forecast(contexts, horizon)
        out = []
        for context, base in zip(contexts, naive):
            y = _clean(context)
            slope = (y[-1] - y[0]) / max(len(y) - 1, 1)
            trend = slope * np.arange(1, horizon + 1)
            out.append(Forecast(base.point + trend, base.quantiles + trend[:, None]))
        return out


class MeanForecaster:
    """Historical mean of the recent window: the "nothing ever changes" baseline."""

    name = "mean"

    def __init__(self, window: int = 90):
        self.window = window

    def forecast(self, contexts: Sequence[np.ndarray], horizon: int) -> list[Forecast]:
        out = []
        for context in contexts:
            y = _clean(context)[-self.window :]
            point = np.full(horizon, y.mean())
            quantiles = np.tile(np.quantile(y, QUANTILES), (horizon, 1))
            out.append(Forecast(point, quantiles))
        return out


# --------------------------------------------------------------------------------------------
# TimesFM (Google Research). Imported lazily so the rest of the project works without torch.
# --------------------------------------------------------------------------------------------


class TimesFM25Forecaster:
    """TimesFM 2.5 (200M parameters, Apache-2.0 weights). The default model of this project."""

    name = "timesfm-2.5"

    def __init__(self, max_context: int = 1024, max_horizon: int = 256, checkpoint: str = TIMESFM_2P5_CHECKPOINT):
        try:
            import timesfm
        except ImportError as exc:  # pragma: no cover - depends on optional install
            raise ImportError('TimesFM is not installed. Run: pip install "timesfm[torch]"') from exc

        self._model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(checkpoint)
        self._model.compile(
            timesfm.ForecastConfig(
                max_context=max_context,
                max_horizon=max_horizon,
                normalize_inputs=True,
                use_continuous_quantile_head=True,
                force_flip_invariance=True,
                infer_is_positive=False,
                fix_quantile_crossing=True,
            )
        )

    def forecast(self, contexts: Sequence[np.ndarray], horizon: int) -> list[Forecast]:
        inputs = [_clean(c).astype(np.float32) for c in contexts]
        point, quantiles = self._model.forecast(horizon=horizon, inputs=inputs)
        # TimesFM 2.5 returns (n, h, 10): index 0 is the mean, 1..9 are the deciles 0.1..0.9.
        return [
            Forecast(np.asarray(point[i], dtype=np.float64), np.asarray(quantiles[i, :, 1:10], dtype=np.float64))
            for i in range(len(inputs))
        ]


class TimesFM3Forecaster:
    """TimesFM 3.0. Strongest model, but its weights are licensed for non-commercial use only."""

    name = "timesfm-3"

    def __init__(self, checkpoint: str = TIMESFM_3_CHECKPOINT, device: str | None = None):
        try:
            from timesfm3 import TimesFM3Forecaster as _TimesFM3
        except ImportError as exc:  # pragma: no cover - depends on optional install
            raise ImportError('TimesFM 3 is not installed. Run: pip install "timesfm[torch]>=3"') from exc

        self._model = _TimesFM3.from_pretrained(checkpoint, device=device)

    def forecast(self, contexts: Sequence[np.ndarray], horizon: int) -> list[Forecast]:
        out = []
        for context in contexts:
            result = self._model.predict(_clean(context).astype(np.float32), horizon=horizon, return_quantiles=True)
            out.append(Forecast(np.asarray(result.forecast, dtype=np.float64), np.asarray(result.quantiles, dtype=np.float64)))
        return out


class ChronosForecaster:
    """Amazon Chronos, the most common head-to-head rival to TimesFM. Chronos-Bolt (small) is
    the default because it is fast on a CPU; ``chronos-2`` is the newer, larger model."""

    def __init__(self, checkpoint: str = CHRONOS_BOLT_CHECKPOINT, name: str = "chronos-bolt"):
        try:
            import torch
            from chronos import BaseChronosPipeline
        except ImportError as exc:  # pragma: no cover - depends on optional install
            raise ImportError('Chronos is not installed. Run: pip install "chronos-forecasting"') from exc
        self.name = name
        self._torch = torch
        self._pipeline = BaseChronosPipeline.from_pretrained(checkpoint, device_map="cpu")

    def forecast(self, contexts: Sequence[np.ndarray], horizon: int) -> list[Forecast]:
        torch = self._torch
        inputs = [torch.tensor(_clean(c), dtype=torch.float32) for c in contexts]
        quantiles, mean = self._pipeline.predict_quantiles(inputs, prediction_length=horizon, quantile_levels=list(QUANTILES))
        out = []
        for i in range(len(inputs)):
            # Chronos-Bolt returns one batched tensor (n, h, q); Chronos-2 a list of (variates, h, q).
            q = np.asarray(quantiles[i], dtype=np.float64)
            m = np.asarray(mean[i], dtype=np.float64)
            if q.ndim == 3:
                q, m = q[0], m[0]
            out.append(Forecast(m[:horizon], np.sort(q[:horizon], axis=1)))
        return out


# --------------------------------------------------------------------------------------------
# Theory-driven model: Bass diffusion (Frank Bass, "A New Product Growth Model", 1969).
# --------------------------------------------------------------------------------------------

# Standard normal quantiles for the deciles 0.1 ... 0.9.
_Z = np.array([-1.2816, -0.8416, -0.5244, -0.2533, 0.0, 0.2533, 0.5244, 0.8416, 1.2816])


def bass_curve(t: np.ndarray, p: float, q: float) -> np.ndarray:
    """Cumulative share of eventual adopters at time t: innovation p, imitation q."""
    e = np.exp(-(p + q) * t)
    return (1 - e) / (1 + (q / p) * e)


class BassForecaster:
    """Fits the Bass S-curve to an adoption series (share of electricity from solar, share of
    people online) and extends it. A theory-driven rival: if TimesFM cannot beat the textbook
    diffusion curve on technology adoption, its "pattern recognition" adds little there.

    Fitting is a grid search over innovation p, imitation q and how many periods before the
    data the diffusion started; market size m is then solved exactly by least squares."""

    name = "bass"

    P_GRID = np.geomspace(1e-4, 0.3, 28)
    Q_GRID = np.linspace(0.02, 1.2, 40)
    START_GRID = (0, 3, 6, 10, 15, 25)

    def fit(self, y: np.ndarray) -> tuple[float, float, int, float]:
        n = len(y)
        best = (np.inf, 0.01, 0.3, 0, float(y.max()))
        for start in self.START_GRID:
            t = np.arange(1, n + 1) + start
            for p in self.P_GRID:
                for q in self.Q_GRID:
                    f = bass_curve(t, p, q)
                    m = float(f @ y / (f @ f)) if f @ f > 0 else 0.0
                    if m < y.max():  # the market cannot be smaller than adoption already seen
                        m = float(y.max())
                    sse = float(np.sum((y - m * f) ** 2))
                    if sse < best[0]:
                        best = (sse, p, q, start, m)
        return best[1], best[2], best[3], best[4]

    def forecast(self, contexts: Sequence[np.ndarray], horizon: int) -> list[Forecast]:
        out = []
        for context in contexts:
            y = _clean(context)
            p, q, start, m = self.fit(y)
            n = len(y)
            fitted = m * bass_curve(np.arange(1, n + 1) + start, p, q)
            sigma = float(np.std(y - fitted)) or 1e-9
            point = m * bass_curve(np.arange(n + 1, n + horizon + 1) + start, p, q)
            # Uncertainty widens with the square root of the steps ahead.
            spread = sigma * np.sqrt(np.arange(1, horizon + 1))[:, None] * _Z[None, :]
            out.append(Forecast(point, point[:, None] + spread))
        return out


# --------------------------------------------------------------------------------------------
# Ensembles (quantile averaging, as in GluonTS and the fev / GIFT-Eval leaderboards).
# --------------------------------------------------------------------------------------------


def combine(forecasts: Sequence[Forecast]) -> Forecast:
    """Average point forecasts and each quantile across models ("Vincentization"). Ensembles
    of diverse forecasters are among the most reliable wins in forecasting competitions."""
    point = np.mean([f.point for f in forecasts], axis=0)
    quantiles = np.sort(np.mean([f.quantiles for f in forecasts], axis=0), axis=1)
    return Forecast(point, quantiles)


ENSEMBLE = "ensemble"


# --------------------------------------------------------------------------------------------
# Classical statistics (Nixtla statsforecast, https://github.com/Nixtla/statsforecast). Optional:
# pip install "world-predictor[classical]". ETS and ARIMA are the workhorses that won or
# anchored the M-competitions, so a foundation model should beat them, not just the naive walk.
# --------------------------------------------------------------------------------------------


class StatsForecastForecaster:
    """AutoETS or AutoARIMA from statsforecast, with deciles from its prediction intervals."""

    LEVELS = (20, 40, 60, 80)

    def __init__(self, kind: str = "ets"):
        try:
            from statsforecast.models import AutoARIMA, AutoETS
        except ImportError as exc:  # pragma: no cover - depends on optional install
            raise ImportError('statsforecast is not installed. Run: pip install "statsforecast"') from exc
        self.name = "auto-" + kind
        self._model = AutoETS() if kind == "ets" else AutoARIMA()

    def forecast(self, contexts: Sequence[np.ndarray], horizon: int) -> list[Forecast]:
        import pandas as pd
        from statsforecast import StatsForecast

        frames = []
        for i, context in enumerate(contexts):
            y = _clean(context)
            frames.append(pd.DataFrame({"unique_id": i, "ds": np.arange(len(y)), "y": y}))
        sf = StatsForecast(models=[self._model], freq=1)
        out = sf.forecast(df=pd.concat(frames, ignore_index=True), h=horizon, level=list(self.LEVELS))
        col = type(self._model).__name__
        results = []
        for i in range(len(contexts)):
            rows = out[out["unique_id"] == i]
            point = rows[col].to_numpy(dtype=float)
            # Level L% interval = quantiles (50 - L/2)% and (50 + L/2)%.
            lows = [rows[f"{col}-lo-{level}"].to_numpy(dtype=float) for level in reversed(self.LEVELS)]
            highs = [rows[f"{col}-hi-{level}"].to_numpy(dtype=float) for level in self.LEVELS]
            quantiles = np.column_stack(lows + [point] + highs)
            results.append(Forecast(point, np.sort(quantiles, axis=1)))
        return results


MODELS = {
    "timesfm-2.5": TimesFM25Forecaster,
    "timesfm-3": TimesFM3Forecaster,
    "chronos-bolt": ChronosForecaster,
    "chronos-2": lambda: ChronosForecaster(CHRONOS_2_CHECKPOINT, "chronos-2"),
    "bass": BassForecaster,
    "naive": NaiveForecaster,
    "drift": DriftForecaster,
    "mean": MeanForecaster,
    "auto-ets": lambda: StatsForecastForecaster("ets"),
    "auto-arima": lambda: StatsForecastForecaster("arima"),
}

BASELINES = ("naive", "drift", "mean")


def classical_available() -> bool:
    try:
        import statsforecast  # noqa: F401
    except ImportError:
        return False
    return True


_LOADED: dict[str, Forecaster] = {}


def load_model(name: str) -> Forecaster:
    """Load a model once per process; TimesFM checkpoints are slow to load."""
    if name not in MODELS:
        raise ValueError(f"Unknown model {name!r}. Choose from: {', '.join(MODELS)}")
    if name not in _LOADED:
        _LOADED[name] = MODELS[name]()
    return _LOADED[name]
