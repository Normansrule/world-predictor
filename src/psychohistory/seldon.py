"""Seldon: our own psychohistory forecaster, built to compete with TimesFM head to head.

Seldon comes in two forms, both scored on the same windows as TimesFM:

* ``seldon-laws`` - the crowd laws alone (below): no neural network, nothing but the series' past.
* ``seldon`` - the full Seldon: the crowd laws *and* the model under test (TimesFM) as voters in
  one council. How much say TimesFM gets is learned per area (news, markets, technology) from every
  finished forecast window of every series in that area: Seldon's law of large numbers applied to
  its own track record, since one series' dozen windows are too few to learn from but a whole area's
  are not. Until an area has enough finished windows, TimesFM keeps the whole vote, so Seldon starts
  as TimesFM and only moves away from it where the laws have earned a share.

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
import pandas as pd

from .models import QUANTILES, Forecast

NAME = "seldon"  # the full Seldon: crowd laws plus the model under test
LAWS_NAME = "seldon-laws"  # the crowd laws alone
SHARES = np.round(np.linspace(0.0, 1.0, 11), 1)  # candidate shares of the vote for the crowd laws
MIN_POOL = 10  # finished windows an area needs before the laws can earn any share
MARGIN = 0.02  # a share is only used if it beat the model alone by this much on those windows
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
    """Seldon's crowd laws as a model like any other: same inputs and outputs as TimesFM.
    ``councils`` keeps how each of the last batch of forecasts was made."""

    name = LAWS_NAME

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


# --------------------------------------------------------------------------------------------
# The full Seldon: the crowd laws and the model under test in one council.
# --------------------------------------------------------------------------------------------


@dataclass
class Window:
    """One finished forecast window, as the share is learned from it."""

    domain: str
    end: pd.Timestamp  # the date of its last value: it counts as finished from then on
    last: float  # the value at its origin
    model: np.ndarray  # the model under test's middle path
    laws: np.ndarray  # the crowd laws' middle path
    actual: np.ndarray


def learn_share(windows: Sequence[Window]) -> float:
    """The laws' share of the vote that would have given the lowest error on these windows: the
    mean absolute percentage error over every finished day, the measure the year ledger keeps. Zero
    (all to the model) with fewer than ``MIN_POOL`` windows, or unless the best share beat the model
    alone by ``MARGIN``.

    Until November 2026 the error of each window was measured against "no change" and averaged, and
    five windows were enough. Replayed on every recorded window, learning only from the windows
    finished before each forecast, that rule moved away from TimesFM too early and too often: it
    missed by 8.97% on an average day against TimesFM's 8.83%. This one ties TimesFM on the same
    replay (scripts/seldon_bakeoff.py)."""
    if len(windows) < MIN_POOL:
        return 0.0
    actual = np.concatenate([w.actual for w in windows])
    model = np.concatenate([w.model for w in windows])
    laws = np.concatenate([w.laws for w in windows])
    ok = np.isfinite(actual) & np.isfinite(model) & np.isfinite(laws) & (actual != 0)
    if not ok.any():
        return 0.0
    actual, model, laws = actual[ok], model[ok], laws[ok]
    errors = [float(np.mean(np.abs((1 - share) * model + share * laws - actual) / np.abs(actual))) for share in SHARES]
    best = int(np.argmin(errors))
    return float(SHARES[best]) if errors[best] <= errors[0] * (1 - MARGIN) else 0.0


def share_for(windows: Sequence[Window], domain: str, at=None) -> float:
    """The laws' share for a forecast in ``domain`` made at date ``at`` (None: now), learned only
    from that area's windows that had finished by then."""
    at = None if at is None else pd.Timestamp(at)
    return learn_share([w for w in windows if w.domain == domain and (at is None or w.end <= at)])


def blend(model: Forecast, laws: Forecast, share: float) -> Forecast:
    """The council's forecast: every decile averaged with the laws' share (quantile averaging)."""
    point = (1 - share) * model.point + share * laws.point
    quantiles = np.sort((1 - share) * model.quantiles + share * laws.quantiles, axis=1)
    return Forecast(point, quantiles)


def blend_bands(model_bands: Sequence[np.ndarray], laws: Forecast, share: float) -> tuple[np.ndarray, ...]:
    """The same blend on a saved 10th / 50th / 90th percentile path (what the backtest paths keep)."""
    return tuple((1 - share) * np.asarray(b, float) + share * laws.q(level)
                 for b, level in zip(model_bands, (0.1, 0.5, 0.9)))


def windows_from_paths(paths: pd.DataFrame | None, data: dict[str, pd.Series], model: str,
                       domains: dict[str, str], max_context: int = 1024) -> list[Window]:
    """Finished windows of ``model`` from the backtest paths, with the crowd laws' recorded path for
    the same window when the run kept one, or else the laws run on the data up to each window's
    origin (exactly what they would have said then)."""
    if paths is None or paths.empty:
        return []
    recorded = {key: g.sort_values("step")["q50"].to_numpy(float)
                for key, g in paths[paths["model"] == LAWS_NAME].groupby(["series_id", "origin"])}
    out = []
    for (series_id, origin), g in paths[paths["model"] == model].groupby(["series_id", "origin"]):
        if series_id not in data or series_id not in domains:
            continue
        g = g.sort_values("step")
        series = data[series_id]
        context = series[series.index <= pd.Timestamp(origin)].to_numpy(dtype=float)[-max_context:]
        if len(context) == 0:
            continue
        laws = recorded.get((series_id, origin))
        if laws is None or len(laws) != len(g):
            laws = predict(context, len(g))[0].q(0.5)
        out.append(Window(domains[series_id], pd.Timestamp(g["date"].max()), float(context[-1]),
                          g["q50"].to_numpy(float), laws, g["actual"].to_numpy(float)))
    return out


def full_council(council: Council, share: float, model: str) -> dict:
    """The council the app shows: the model's vote next to each law's, all adding up to one."""
    out = council_json(council)
    key = "timesfm" if model.startswith("timesfm") else model
    out["weights"] = {key: round(1 - share, 3), **{k: round(share * v, 3) for k, v in council.weights.items()}}
    out["share"] = round(share, 3)
    return out


def explain_full(council: Council, share: float, model_name: str) -> str:
    """One sentence on how the full Seldon reached a forecast."""
    if share == 0:
        return (f"Seldon gave {model_name} the whole vote here: in this area its crowd laws have not yet beaten "
                f"{model_name} on the finished windows, so it does not move away from it.")
    return (f"Seldon gave {model_name} {1 - share:.0%} of the vote and its crowd laws {share:.0%}, the split that "
            f"did best on this area's finished windows. " + explain(council))


# --------------------------------------------------------------------------------------------
# Seldon's own council (from November 2026): no TimesFM in it.
#
# With TimesFM as a voter, the share rule above handed it the vote almost everywhere, so the full
# Seldon sat 0.19% from TimesFM on an average day and pointed the other way on 6% of windows: a
# second copy, not a second opinion. Seldon now votes without it. Its council is the four crowd laws
# (``predict``), Radiant's behavioural core (overreaction, momentum, reversal, attention spikes),
# "no change", and Chronos-Bolt when the run has it, each weighted per area by exponential weights
# (Littlestone & Warmuth, 1994): level at first, and after every finished window each voter's weight
# shrinks by e^(-OWN_ETA x its miss relative to the council's average miss on that window). Replayed on
# the 319 recorded daily windows (scripts/seldon_perspective.py), it missed by 8.77% on an average day
# against TimesFM's 8.46%: a little better in markets (4.91% against 4.97%), worse in news and
# technology, and pointing the other way from TimesFM on 25% of windows.
# --------------------------------------------------------------------------------------------

OWN = ("laws", "core", "naive", "rival")  # Seldon's own voters; "rival" is Chronos-Bolt when it ran
OWN_LABELS = {"laws": "crowd laws", "core": "behavioural core", "naive": "no change", "rival": "Chronos-Bolt"}
OWN_ETA = 2.0
OWN_SINCE = "2026-11-10"  # forecasts sealed before this day came from the old council, with TimesFM in it


def own_weights(windows: Sequence, area: str | None = None, at=None) -> np.ndarray:
    """The own council's weights (in ``OWN`` order) for a forecast in ``area`` made at ``at`` (None:
    now), from that area's finished windows (``radiant.Window``: each voter's middle path). A voter
    missing from a window is charged the council's average there, so it neither gains nor loses."""
    at = None if at is None else pd.Timestamp(at)
    total = np.zeros(len(OWN))
    for w in windows:
        if (area is not None and w.domain != area) or (at is not None and w.end > at):
            continue
        a = np.asarray(w.actual, float)
        ok = np.isfinite(a) & (a != 0)
        if not ok.any():
            continue
        miss = np.array([float(np.mean(np.abs(np.asarray(w.paths[e], float)[ok] - a[ok]) / np.abs(a[ok])))
                         if e in w.paths else np.nan for e in OWN])
        if not np.isfinite(miss).any():
            continue
        mean = float(np.nanmean(miss))
        total += np.where(np.isfinite(miss), miss / max(mean, 1e-12), 1.0)
    logits = -OWN_ETA * total
    out = np.exp(logits - logits.max())
    return out / out.sum()


def own_mix(forecasts: dict, weight: np.ndarray) -> tuple[Forecast, np.ndarray]:
    """The voters' forecasts averaged decile by decile with these weights; a voter absent from
    ``forecasts`` (Chronos, when it did not run) drops out and the rest are scaled up. Returns the
    forecast and the weights actually used."""
    used = np.array([weight[k] if e in forecasts else 0.0 for k, e in enumerate(OWN)])
    used = used / used.sum()
    keys = [(k, e) for k, e in enumerate(OWN) if e in forecasts]
    point = sum(used[k] * np.asarray(forecasts[e].point, float) for k, e in keys)
    quantiles = np.sort(sum(used[k] * np.asarray(forecasts[e].quantiles, float) for k, e in keys), axis=1)
    return Forecast(point, quantiles), used


def own_voters(context: np.ndarray, horizon: int, rival: Forecast | None = None, laws: Forecast | None = None) -> dict:
    """Every voter's forecast from this context: the laws, the core and no change, plus the rival."""
    from . import radiant

    out = {"laws": laws if laws is not None else predict(context, horizon)[0],
           "core": radiant.core_predict(context, horizon)[0], "naive": radiant.naive_forecast(context, horizon)}
    if rival is not None:
        out["rival"] = rival
    return out


def own_forecast(context: np.ndarray, horizon: int, windows: Sequence, area: str, at=None,
                 rival: Forecast | None = None) -> tuple[Forecast, np.ndarray, Council]:
    """Seldon's forecast from its own council, the weights it used and the crowd laws' council."""
    laws, council = predict(context, horizon)
    return (*own_mix(own_voters(context, horizon, rival, laws), own_weights(windows, area, at)), council)


def own_council(council: Council, used: np.ndarray) -> dict:
    """The council the app shows for Seldon's own vote: each voter's share, and how the laws split."""
    out = council_json(council)
    out["laws"] = out.pop("weights")
    out["weights"] = {OWN_LABELS[e]: round(float(w), 3) for e, w in zip(OWN, used) if w > 0}
    out["own"] = True
    return out


def explain_own(used: np.ndarray) -> str:
    """One sentence on how Seldon's own council voted."""
    votes = ", ".join(f"{OWN_LABELS[e]} {w:.0%}" for e, w in sorted(zip(OWN, used), key=lambda kv: -kv[1]) if w > 0)
    return (f"Seldon votes without TimesFM: {votes}, each share earned on this area's finished windows.")
