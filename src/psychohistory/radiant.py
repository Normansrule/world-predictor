"""Radiant: the project's own attempt at a forecaster better than TimesFM.

Named after the Prime Radiant, the device in Asimov's *Second Foundation* (1953) that holds the
Seldon Plan and shows where it is going wrong. Radiant has two parts.

**The core (``radiant-core``): market psychology as statistics.** Five behavioural signals, each a
documented pattern in how crowds of traders and readers behave, measured from the series' own past:

* **Momentum and herding** - a crowd that has been moving one way keeps moving, as late arrivals
  follow the early ones (Jegadeesh & Titman, 1993; Moskowitz et al., 2012; Bikhchandani et al., 1992).
* **Overreaction** - after an extreme run, measured in its own volatility, prices tend to give some
  of it back (De Bondt & Thaler, 1985).
* **Short-term reversal** - last week's move partly undoes itself (Lehmann, 1990).
* **Momentum crashes** - when markets turn wild, momentum stops working and can flip, so the
  momentum signal is scaled by how volatile the last month was against the last year (Daniel &
  Moskowitz, 2016).
* **Attention spikes** - a series far above its recent normal (a news story, a burst of interest)
  tends to fade back (Barber & Odean, 2008; Da et al., 2011).

How much each signal counts is learned for every series from its own history before the forecast
date: at many earlier dates the signals are measured and set against what happened over the
following steps, and a ridge regression (Hoerl & Kennard, 1970), shrunk hard toward "no change",
turns them into a forecast of the log change. Nothing after the forecast date is used.

**The full Radiant (``radiant``): a mix that has to earn its moves.** TimesFM, Seldon's crowd laws,
the core, "no change" and a rival model (Chronos-Bolt, when it ran) are mixed decile by decile with exponential weights (Freund & Schapire,
1997; Cesa-Bianchi & Lugosi, 2006): every finished forecast window of an area (markets, news,
technology, and the yearly adoption series on their own) charges each one its miss relative to TimesFM's, and its weight shrinks by
``exp(-ETA * charge)``. It starts with TimesFM and Chronos-Bolt level (``PRIOR``; most of the weight on TimesFM when
Chronos does not run), so a signal only
gains a say by being right on forecasts it never saw while learning.

It is scored on exactly the same windows, metrics and sealed ledger as TimesFM, and reported whether
it wins or not.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
import pandas as pd

from .models import Forecast

NAME = "radiant"  # the full mix
CORE = "radiant-core"  # the behavioural core alone
EXPERTS = ("model", "laws", "core", "naive", "rival")  # TimesFM, Seldon's laws, the core, no change, a rival model
RIVAL = "chronos-bolt"  # the rival: best single model in the first official backtest, strongest on slow series
# Starting weights. With the rival running, the two foundation models start level: the backtest of
# 4 November 2026 gave each a track record (TimesFM 10.07%, Chronos-Bolt 9.39% sMAPE), and neither
# should be favoured before an area's own windows have spoken. Replayed on that run, this start
# beat the old one on the early windows (10.07% against 10.41%) and made no difference later, once
# the weights had learned (8.78% both). Without the rival Radiant starts as it always did:
# PRIOR_SOLO renormalises to exactly 0.7 / 0.1 / 0.1 / 0.1.
PRIOR = (0.35, 0.10, 0.10, 0.10, 0.35)
PRIOR_SOLO = (0.63, 0.09, 0.09, 0.09, 0.10)
ETA = 2.0  # how fast a weight shrinks per unit of extra miss, relative to the model's own
LAMBDA = 10.0  # ridge penalty: the core is shrunk hard toward "no change"
MIN_TRAIN = 60  # points of history a core training date needs before it
MAX_HISTORY = 2520  # the core learns from at most the last ten years of trading days
SIGNALS = ("momentum", "overreaction", "reversal", "momentum x volatility", "attention spike")
_Z = np.array([-1.2816, -0.8416, -0.5244, -0.2533, 0.0, 0.2533, 0.5244, 0.8416, 1.2816])


def signals(z: np.ndarray, t: int, horizon: int) -> np.ndarray:
    """The five behavioural signals at index ``t`` of a (log) series, from ``z[: t + 1]`` only."""
    r = np.diff(z[max(0, t - 251): t + 1])  # the last 250 changes are all any signal looks at
    lag = min(horizon, t)
    momentum = z[t] - z[t - lag] if lag >= 3 else 0.0
    sd = float(np.std(r[-60:])) if len(r) >= 10 else 0.0
    extreme = abs(momentum / (sd * np.sqrt(lag))) > 1.5 if sd > 0 and lag > 0 else False
    reversal = z[t] - z[t - min(5, t)]
    wild = 0.0
    if len(r) >= 40:
        recent, long = float(np.std(r[-20:])), float(np.std(r[-250:]))
        wild = float(np.log(recent / long)) if recent > 0 and long > 0 else 0.0
    spike = z[t] - float(np.median(z[max(0, t - horizon + 1): t + 1]))
    return np.array([momentum, momentum * extreme, reversal, momentum * wild, spike])


def fit(z: np.ndarray, horizon: int, lam: float = LAMBDA) -> tuple[np.ndarray, np.ndarray] | None:
    """The core's weights on the signals and its residuals per step ahead, learned from earlier
    dates of this series. None when the history is too short to learn anything."""
    z = z[-MAX_HISTORY:]
    n = len(z)
    rows, targets, steps = [], [], []
    for t in range(MIN_TRAIN, n - horizon, max(1, horizon // 4)):
        s = signals(z, t, horizon)
        for h in range(1, horizon + 1):
            rows.append(s * h / horizon)
            targets.append(z[t + h] - z[t])
            steps.append(h)
    if len(targets) < 4 * horizon:
        return None
    x, y = np.array(rows), np.array(targets)
    scale = np.sqrt((x ** 2).mean(axis=0)) + 1e-12
    xs = x / scale
    beta = np.linalg.solve(xs.T @ xs + lam * len(y) * np.eye(x.shape[1]), xs.T @ y) / scale
    resid = y - x @ beta
    steps = np.array(steps)
    spread = np.array([np.std(resid[steps == h]) if np.any(steps == h) else np.std(resid) for h in range(1, horizon + 1)])
    return beta, spread


def core_predict(context: np.ndarray, horizon: int) -> tuple[Forecast, np.ndarray | None]:
    """The core's forecast for one series, and the signal weights it used (None: no change)."""
    y = np.asarray(context, dtype=np.float64)
    y = y[np.isfinite(y)]
    if len(y) == 0:
        raise ValueError("Radiant needs at least one value")
    use_log = bool(np.all(y > 0)) and len(y) > 1
    z = np.log(y) if use_log else y
    learned = fit(z, horizon) if use_log else None
    h = np.arange(1, horizon + 1) / horizon
    if learned is None:
        r = np.diff(z) if len(z) > 1 else np.zeros(1)
        mid = np.full(horizon, z[-1])
        spread = (np.std(r) if len(r) > 1 else abs(z[-1]) * 0.01 + 1e-9) * np.sqrt(np.arange(1, horizon + 1))
        beta = None
    else:
        beta, spread = learned
        mid = z[-1] + np.outer(h, signals(z, len(z) - 1, horizon)) @ beta
    quantiles = np.sort(mid[:, None] + spread[:, None] * _Z[None, :], axis=1)
    point = mid.copy()
    if use_log:
        quantiles, point = np.exp(quantiles), np.exp(point)
    return Forecast(point, quantiles), beta


class RadiantCoreForecaster:
    """Radiant's behavioural core as a model like any other: same inputs and outputs as TimesFM."""

    name = CORE

    def forecast(self, contexts: Sequence[np.ndarray], horizon: int) -> list[Forecast]:
        return [core_predict(c, horizon)[0] for c in contexts]


@dataclass
class Window:
    """One finished forecast window as the mix learns from it: each expert's middle path."""

    domain: str
    end: pd.Timestamp
    paths: dict  # expert -> middle path
    actual: np.ndarray


def charges(window: Window) -> np.ndarray:
    """Each expert's mean absolute percentage miss on a window, relative to the model's, minus one."""
    a = np.asarray(window.actual, float)
    ok = np.isfinite(a) & (a != 0)
    if not ok.any():
        return np.zeros(len(EXPERTS))
    miss = np.array([float(np.mean(np.abs(np.asarray(window.paths[e], float)[ok] - a[ok]) / np.abs(a[ok])))
                     if e in window.paths else np.nan for e in EXPERTS])
    out = miss / max(miss[0], 1e-12) - 1
    return np.where(np.isfinite(out), out, 0.0)  # an expert that did not run on a window is neither charged nor credited


def prior(rival: bool = True) -> np.ndarray:
    """Where the weights start: level between TimesFM and the rival when the rival runs, else on TimesFM."""
    return np.array(PRIOR if rival else PRIOR_SOLO, dtype=float)


def weights(windows: Sequence[Window], domain: str | None = None, at=None, rival: bool = True) -> np.ndarray:
    """The experts' weights for a forecast in ``domain`` made at ``at`` (None: now), from that
    area's windows that had finished by then. ``rival``: whether the rival runs for this forecast,
    which sets where the weights start (``prior``)."""
    at = None if at is None else pd.Timestamp(at)
    total = np.zeros(len(EXPERTS))
    for w in windows:
        if (domain is None or w.domain == domain) and (at is None or w.end <= at):
            total += charges(w)
    logits = np.log(prior(rival)) - ETA * total
    logits -= logits.max()
    out = np.exp(logits)
    return out / out.sum()


def mix(forecasts: dict, weight: np.ndarray) -> Forecast:
    """The experts' forecasts averaged decile by decile with these weights. An expert missing from
    ``forecasts`` (the rival, when it did not run) drops out and the rest are scaled up to sum to one."""
    weight = present(weight, forecasts)
    use = [(k, e) for k, e in enumerate(EXPERTS) if e in forecasts]
    point = sum(weight[k] * np.asarray(forecasts[e].point, float) for k, e in use)
    quantiles = np.sort(sum(weight[k] * np.asarray(forecasts[e].quantiles, float) for k, e in use), axis=1)
    return Forecast(point, quantiles)


def present(weight: np.ndarray, forecasts) -> np.ndarray:
    """The weights with every expert absent from ``forecasts`` set to zero, rescaled to sum to one."""
    w = np.array([weight[k] if e in forecasts else 0.0 for k, e in enumerate(EXPERTS)])
    return w / w.sum()


def naive_forecast(context: np.ndarray, horizon: int) -> Forecast:
    from .models import NaiveForecaster

    return NaiveForecaster().forecast([context], horizon)[0]


YEARLY = "yearly"  # the area of the yearly adoption series, which learn their weights apart from the daily ones


def area(spec) -> str:
    """The area a series' Radiant weights are learned in: its domain (markets, news, technology),
    or ``"yearly"`` for the yearly adoption series. Those move on a different clock (a handful of
    points, three years ahead), so one of their windows would swamp a month of daily ones, and what
    works on daily attention data says little about them: in the first official backtest Chronos-Bolt
    had almost all of its technology lead on these three series and none on the daily ones."""
    return YEARLY if spec.source == "owid" else spec.domain


def domains_of(catalog_specs) -> dict[str, str]:
    """The area Radiant learns in, per series (see ``area``)."""
    return {s.id: area(s) for s in catalog_specs}


def windows_from_paths(paths: pd.DataFrame | None, data: dict[str, pd.Series], model: str, domains: dict[str, str],
                       laws_names: Sequence[str] = ("seldon-laws",), max_context: int = 2048) -> list[Window]:
    """Finished windows from the saved backtest paths: ``model``'s middle path, the laws' and the
    core's when the run kept them (else rerun on the data up to the origin), and no change."""
    from . import seldon

    if paths is None or paths.empty:
        return []
    kept = {}
    for name in (*laws_names, CORE, RIVAL):
        part = paths[paths["model"] == name]
        kept[name] = {k: g.sort_values("step")["q50"].to_numpy(float) for k, g in part.groupby(["series_id", "origin"])}
    out = []
    for (series_id, origin), g in paths[paths["model"] == model].groupby(["series_id", "origin"]):
        if series_id not in data or series_id not in domains:
            continue
        g = g.sort_values("step")
        series = data[series_id]
        context = series[series.index <= pd.Timestamp(origin)].to_numpy(dtype=float)[-max_context:]
        if len(context) == 0:
            continue
        h = len(g)
        laws = next((kept[n][(series_id, origin)] for n in laws_names if (series_id, origin) in kept[n]), None)
        if laws is None or len(laws) != h:
            laws = seldon.predict(context, h)[0].q(0.5)
        core = kept[CORE].get((series_id, origin))
        if core is None or len(core) != h:
            core = core_predict(context, h)[0].q(0.5)
        experts = {"model": g["q50"].to_numpy(float), "laws": laws, "core": core, "naive": np.full(h, context[-1])}
        rival = kept[RIVAL].get((series_id, origin))
        if rival is not None and len(rival) == h:
            experts["rival"] = rival
        out.append(Window(domains[series_id], pd.Timestamp(g["date"].max()), experts, g["actual"].to_numpy(float)))
    return out


def replay(paths: pd.DataFrame, data: dict[str, pd.Series], model: str, domains: dict[str, str],
           laws_names: Sequence[str] = ("seldon-laws", "seldon")) -> pd.DataFrame:
    """Radiant's backtest paths rebuilt from a run that kept ``model``'s paths but not Radiant's:
    for every window, the mix with weights learned only from the area's windows finished before
    its origin, and the core rerun on the data up to the origin. Rows shaped like the paths file."""
    from . import seldon

    if paths is None or paths.empty or NAME in set(paths["model"]):
        return pd.DataFrame()
    laws_kept = paths[paths["model"].isin(laws_names)]
    rival_kept = paths[paths["model"] == RIVAL]
    windows = windows_from_paths(paths, data, model, domains, laws_names=laws_names)
    rows = []
    for (series_id, origin), g in paths[paths["model"] == model].groupby(["series_id", "origin"]):
        if series_id not in data or series_id not in domains:
            continue
        g = g.sort_values("step")
        context = data[series_id][data[series_id].index <= pd.Timestamp(origin)].to_numpy(dtype=float)
        if len(context) == 0:
            continue
        h = len(g)
        base = Forecast(g["q50"].to_numpy(float), _three(g))
        lk = laws_kept[(laws_kept["series_id"] == series_id) & (laws_kept["origin"] == origin)].sort_values("step")
        laws = Forecast(lk["q50"].to_numpy(float), _three(lk)) if len(lk) == h else seldon.predict(context, h)[0]
        experts = {"model": base, "laws": laws, "core": core_predict(context, h)[0], "naive": naive_forecast(context, h)}
        rk = rival_kept[(rival_kept["series_id"] == series_id) & (rival_kept["origin"] == origin)].sort_values("step")
        if len(rk) == h:
            experts["rival"] = Forecast(rk["q50"].to_numpy(float), _three(rk))
        for e in experts:
            experts[e] = _as_three(experts[e])
        f = mix(experts, weights(windows, domains[series_id], origin, rival="rival" in experts))
        for (_, r), mid, q in zip(g.iterrows(), f.point, f.quantiles):
            rows.append({"series_id": series_id, "model": NAME, "origin": r["origin"], "date": r["date"], "step": r["step"],
                         "q10": q[0], "q50": mid, "q90": q[-1], "actual": r["actual"]})
    return pd.DataFrame(rows)


def _three(g: pd.DataFrame) -> np.ndarray:
    return np.column_stack([g["q10"].to_numpy(float), g["q50"].to_numpy(float), g["q90"].to_numpy(float)])


def _as_three(f: Forecast) -> Forecast:
    """A forecast with only its 10%, 50% and 90% levels, so recorded paths and fresh forecasts mix."""
    q = np.asarray(f.quantiles, float)
    if q.shape[1] == 3:
        return Forecast(np.asarray(f.point, float), q)
    return Forecast(np.asarray(f.point, float), np.column_stack([f.q(0.1), f.q(0.5), f.q(0.9)]))


def explain(weight: np.ndarray, beta: np.ndarray | None = None) -> str:
    """One sentence on how Radiant mixed a forecast."""
    names = {"model": "TimesFM", "laws": "the crowd laws", "core": "the behavioural core", "naive": "no change", "rival": "Chronos-Bolt"}
    parts = ", ".join(f"{names[e]} {w:.0%}" for e, w in sorted(zip(EXPERTS, weight), key=lambda kv: -kv[1]))
    out = f"Radiant mixed {parts}."
    if beta is not None:
        top = SIGNALS[int(np.argmax(np.abs(beta)))]
        out += f" The core leaned most on {top}."
    return out
