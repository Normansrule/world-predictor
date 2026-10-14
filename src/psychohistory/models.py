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


MODELS = {
    "timesfm-2.5": TimesFM25Forecaster,
    "timesfm-3": TimesFM3Forecaster,
    "naive": NaiveForecaster,
    "drift": DriftForecaster,
    "mean": MeanForecaster,
}

BASELINES = ("naive", "drift", "mean")


def load_model(name: str) -> Forecaster:
    try:
        return MODELS[name]()
    except KeyError:
        raise ValueError(f"Unknown model {name!r}. Choose from: {', '.join(MODELS)}") from None
