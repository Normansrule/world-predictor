"""Seldon: our own psychohistory forecaster, built to compete with TimesFM head to head.

TimesFM is a 200-million-parameter neural network trained on billions of time points. Seldon is
the opposite bet, the one Hari Seldon made in *Foundation*: a handful of simple laws of mass
behaviour, each weighed by how well it has predicted this very crowd before. No neural network,
no pretraining, nothing but the series' own past. It runs in milliseconds with numpy alone.

**The laws.** Each one is a complete forecast on its own:

* **Inertia** - a crowd keeps doing what it is doing: tomorrow looks like today.
* **Drift** - the long arc: whatever course the crowd has held across its whole history continues.
* **Momentum** - a crowd that is moving keeps moving, but the push fades (a damped trend).
* **Reversion** - excitement wears off: a series pulled away from its recent normal drifts back.
* **Rhythm** - crowds keep calendars: the weekly rhythm of news and attention repeats. When a
  series has one, Seldon takes it out first, lets the four laws above vote on what is left, and
  lays the rhythm back on top of their forecast.

**The council.** Before every forecast Seldon replays the series' own recent past: it stands at
``REPLAYS`` earlier dates, lets each law forecast the same number of steps ahead, and checks what
really happened. Each law's vote is then weighted by the inverse square of its past error (the
Bates-Granger combination), shrunk a little toward equal votes so one lucky replay does not
decide everything. Everything it learns comes from data before the forecast date: it never peeks.

**The range.** The same replays say how wrong the council has been at each distance ahead. Seldon's
80% range is those errors (their spread grows with a fitted power of the steps ahead), stretched
or narrowed by how volatile the series is right now compared with the replayed period. A calm
market gets a narrow range, a crisis a wide one.

Prices, pageviews and news volumes are positive and move in proportions, so Seldon works on their
logarithm and converts back at the end. Series that can be zero or negative stay as they are.

It is scored on exactly the same backtest windows, metrics and sealed ledger as TimesFM, and it is
allowed to lose: the point is to find out whether a few laws of crowd behaviour can match a
foundation model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

from .models import QUANTILES, Forecast

NAME = "seldon"
LAWS = ("inertia", "drift", "momentum", "reversion")  # the laws that vote; the weekly rhythm is laid on top
REPLAYS = 16  # earlier dates the council replays before every forecast
MIN_TRAIN = 24  # points a replay needs before its date
POWER = 4  # votes go as 1 / error ** POWER: Bates-Granger inverse-variance weights (2), sharpened
EQUAL_SHARE = 0.2  # share of each vote that stays equal, whatever the replays said
DAMPING = 0.9  # per-step fade of momentum
CYCLES = (7, 5)  # weekly rhythm for daily data, and for weekday-only data
MIN_CYCLE_STRENGTH = 0.15  # autocorrelation a rhythm needs before it is used
VOL_CLIP = (0.6, 1.8)  # how far the current volatility may stretch the replayed range
STRETCH = 1.1  # replays are a small sample, so the range they imply is widened by this much
_Q = np.asarray(QUANTILES)
_Z = np.array([-1.2816, -0.8416, -0.5244, -0.2533, 0.0, 0.2533, 0.5244, 0.8416, 1.2816])


@dataclass
class Council:
    """What Seldon learned for one forecast: each law's vote, how its range was set, and on what."""

    weights: dict[str, float] = field(default_factory=dict)
    errors: dict[str, float] = field(default_factory=dict)  # each law's replayed error, scaled like MASE
    replays: int = 0
    log: bool = False
    cycle: int = 0  # length of the weekly rhythm laid on top (7 or 5 steps), 0 if none
    growth: float = 0.5  # range grows like (steps ahead) ** growth
    vol_ratio: float = 1.0  # current volatility / volatility in the replayed period

    def leader(self) -> str:
        return max(self.weights, key=self.weights.get) if self.weights else "inertia"


# --------------------------------------------------------------------------------------------
# The laws. Each takes the (possibly logged, de-rhythmed) history z and returns a path of `h` steps.
# --------------------------------------------------------------------------------------------


def _inertia(z: np.ndarray, h: int) -> np.ndarray:
    return np.full(h, z[-1])


def _drift(z: np.ndarray, h: int) -> np.ndarray:
    slope = (z[-1] - z[0]) / (len(z) - 1) if len(z) > 1 else 0.0
    return z[-1] + slope * np.arange(1, h + 1)


def _momentum(z: np.ndarray, h: int) -> np.ndarray:
    # Slope over a lookback of a few horizons, so a single jump does not count as a trend.
    look = int(min(len(z) - 1, max(4 * h, 20)))
    slope = (z[-1] - z[-1 - look]) / look if look > 0 else 0.0
    fade = np.cumsum(DAMPING ** np.arange(1, h + 1))
    return z[-1] + slope * fade


def _reversion(z: np.ndarray, h: int) -> np.ndarray:
    # Ornstein-Uhlenbeck toward the recent normal; the pull is the AR(1) coefficient of the gaps.
    look = int(min(len(z), max(3 * h, 30)))
    recent = z[-look:]
    normal = float(np.mean(recent))
    gap = recent - normal
    denom = float(gap[:-1] @ gap[:-1])
    rho = float(gap[1:] @ gap[:-1]) / denom if denom > 0 else 0.0
    rho = float(np.clip(rho, 0.0, 0.995))
    return normal + (z[-1] - normal) * rho ** np.arange(1, h + 1)


_LAW = {"inertia": _inertia, "drift": _drift, "momentum": _momentum, "reversion": _reversion}


def _profile(z: np.ndarray, cycle: int, cycles_used: int = 8) -> np.ndarray:
    """Average deviation from a centred moving average at each phase of the rhythm."""
    tail = z[-cycle * min(cycles_used, len(z) // cycle):]
    offset = len(z) - len(tail)
    smooth = np.convolve(tail, np.ones(cycle) / cycle, mode="same")
    half = cycle // 2
    dev = (tail - smooth)[half: len(tail) - half]
    phase = (offset + half + np.arange(len(dev))) % cycle
    profile = np.array([dev[phase == p].mean() if np.any(phase == p) else 0.0 for p in range(cycle)])
    return profile - profile.mean()


def find_cycle(z: np.ndarray) -> int:
    """The rhythm (7 or 5 steps) with the strongest autocorrelation in the day-to-day changes,
    or 0 when neither is strong enough to trust."""
    d = np.diff(z)
    best, strength = 0, MIN_CYCLE_STRENGTH
    for p in CYCLES:
        if len(d) < 4 * p:
            continue
        a, b = d[p:] - d[p:].mean(), d[:-p] - d[:-p].mean()
        denom = float(np.sqrt((a @ a) * (b @ b)))
        r = float(a @ b) / denom if denom > 0 else 0.0
        if r > strength:
            best, strength = p, r
    return best


# --------------------------------------------------------------------------------------------
# The council: replay the past, weigh the laws, set the range.
# --------------------------------------------------------------------------------------------


def _scale(z: np.ndarray) -> float:
    d = np.abs(np.diff(z))
    s = float(np.mean(d)) if len(d) else 0.0
    return s if s > 0 else 1.0


def replay_dates(n: int, h: int) -> list[int]:
    """Up to REPLAYS earlier forecast dates whose whole window is already known, spaced half a
    horizon apart. Index t means "forecast from z[:t], check against z[t:t+h]"."""
    gap = max(1, h // 2)
    return sorted(t for t in (n - h - i * gap for i in range(REPLAYS)) if t >= MIN_TRAIN)


def _paths(z: np.ndarray, h: int, cycle: int, laws: Sequence[str]) -> np.ndarray:
    """Every law's path, shape (laws, h). With a rhythm, the laws see the series with the rhythm
    taken out (learned from z alone), and the rhythm is added back to each path."""
    if not cycle or len(z) < 3 * cycle:
        return np.stack([_LAW[name](z, h) for name in laws])
    profile = _profile(z, cycle)
    flat = z - profile[np.arange(len(z)) % cycle]
    ahead = profile[(len(z) + np.arange(h)) % cycle]
    return np.stack([_LAW[name](flat, h) + ahead for name in laws])


def convene(z: np.ndarray, h: int) -> tuple[Council, np.ndarray, list[str]]:
    """Weigh the laws on the series' own past and collect the council's replayed errors.

    Returns the council, the replayed residuals (actual - council) with shape (replays, h) in z
    units, and the laws that voted."""
    cycle = find_cycle(z)
    laws = list(LAWS)
    dates = replay_dates(len(z), h)
    council = Council(cycle=cycle, replays=len(dates))
    if not dates:
        council.weights = {name: 1 / len(laws) for name in laws}
        return council, np.empty((0, h)), laws
    errors = np.zeros(len(laws))
    paths, actuals = [], []
    for t in dates:
        past, actual = z[:t], z[t: t + h]
        p = _paths(past, h, cycle, laws)
        errors += np.mean(np.abs(p - actual), axis=1) / _scale(past)
        paths.append(p)
        actuals.append(actual)
    errors /= len(dates)
    votes = 1 / np.maximum(errors, 1e-9) ** POWER
    weights = (1 - EQUAL_SHARE) * votes / votes.sum() + EQUAL_SHARE / len(laws)
    council.weights = {name: float(w) for name, w in zip(laws, weights)}
    council.errors = {name: float(e) for name, e in zip(laws, errors)}
    residuals = np.stack([a - weights @ p for p, a in zip(paths, actuals)])
    return council, residuals, laws


def _growth(residuals: np.ndarray) -> float:
    """Fit how the replayed error grows with the steps ahead: |error| ~ step ** growth."""
    h = residuals.shape[1]
    if h < 3 or len(residuals) < 2:
        return 0.5
    mean_abs = np.mean(np.abs(residuals), axis=0)
    ok = mean_abs > 0
    if ok.sum() < 3:
        return 0.5
    slope = float(np.polyfit(np.log(np.arange(1, h + 1)[ok]), np.log(mean_abs[ok]), 1)[0])
    return float(np.clip(slope, 0.2, 1.0))


def _range(z: np.ndarray, h: int, residuals: np.ndarray, council: Council) -> np.ndarray:
    """Offsets from the council's path for each decile at each step, shape (h, 9)."""
    steps = np.arange(1, h + 1, dtype=float)
    if len(residuals) >= 2:
        council.growth = _growth(residuals)
        unit = (residuals / steps[None, :] ** council.growth).ravel()  # errors as if one step ahead
        shape = np.quantile(unit, _Q) - np.quantile(unit, 0.5)
        # Volatility now versus volatility across the replayed stretch.
        span = min(len(z) - 1, len(residuals) * max(1, h // 2) + h)
        # The recent window is two horizons long and the ratio is square-rooted: a short burst of
        # calm or panic moves the range, but does not dominate it.
        recent_n = min(len(z) - 1, max(2 * h, 20))
        recent = float(np.std(np.diff(z[-(recent_n + 1):]))) if recent_n >= 2 else 0.0
        before = float(np.std(np.diff(z[-(span + 1):]))) if span >= 2 else 0.0
        ratio = np.sqrt(recent / before) if before > 0 and recent > 0 else 1.0
        council.vol_ratio = float(np.clip(ratio, *VOL_CLIP))
    else:
        # Too little history to replay: the spread of day-to-day changes, growing like a random walk.
        d = np.diff(z)
        sd = float(np.std(d)) if len(d) > 1 else abs(float(z[-1])) * 0.01 + 1e-9
        shape = sd * _Z
    return STRETCH * council.vol_ratio * steps[:, None] ** council.growth * shape[None, :]


def predict(context: np.ndarray, horizon: int) -> tuple[Forecast, Council]:
    """Seldon's forecast for one series, and the council that made it."""
    y = np.asarray(context, dtype=np.float64)
    y = y[np.isfinite(y)]
    if len(y) == 0:
        raise ValueError("Seldon needs at least one value")
    use_log = bool(np.all(y > 0)) and len(y) > 1
    z = np.log(y) if use_log else y
    if len(z) < 3:
        council = Council(weights={"inertia": 1.0}, log=use_log)
        mid = np.full(horizon, z[-1])
        spread = _range(z, horizon, np.empty((0, horizon)), council)
    else:
        council, residuals, laws = convene(z, horizon)
        council.log = use_log
        w = np.array([council.weights[name] for name in laws])
        mid = w @ _paths(z, horizon, council.cycle, laws)
        spread = _range(z, horizon, residuals, council)
    quantiles = np.sort(mid[:, None] + spread, axis=1)
    point = mid.copy()
    if use_log:
        quantiles, point = np.exp(quantiles), np.exp(point)
    return Forecast(point, quantiles), council


class SeldonForecaster:
    """Seldon as a model like any other: same inputs and outputs as TimesFM, scored the same way.
    ``councils`` keeps how each of the last batch of forecasts was made."""

    name = NAME

    def __init__(self) -> None:
        self.councils: list[Council] = []

    def forecast(self, contexts: Sequence[np.ndarray], horizon: int) -> list[Forecast]:
        out, self.councils = [], []
        for context in contexts:
            forecast, council = predict(context, horizon)
            out.append(forecast)
            self.councils.append(council)
        return out


def explain(council: Council) -> str:
    """One sentence on how Seldon reached a forecast."""
    if not council.replays:
        return "Seldon had too little history to replay, so every law got an equal vote."
    votes = ", ".join(f"{name} {w:.0%}" for name, w in sorted(council.weights.items(), key=lambda kv: -kv[1]))
    mood = "calmer" if council.vol_ratio < 0.95 else "wilder" if council.vol_ratio > 1.05 else "about as calm"
    rhythm = f", with a {council.cycle}-step weekly rhythm laid on top" if council.cycle else ""
    return (f"Seldon replayed {council.replays} earlier dates and split its vote: {votes}{rhythm}. "
            f"The series is {mood} than usual right now, so its range is scaled {council.vol_ratio:.2f}x.")


def council_json(council: Council) -> dict:
    """The council in the shape the web app reads."""
    return {"weights": {k: round(v, 3) for k, v in council.weights.items()}, "replays": council.replays,
            "cycle": council.cycle, "vol": round(council.vol_ratio, 3)}
