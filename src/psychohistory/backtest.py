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

from . import radiant, seldon
from .catalog import SeriesSpec
from .metrics import naive_scale, prob_above, score
from .models import CHALLENGER, ENSEMBLE, LAWS, QUANTILES, Forecast, Forecaster, combine, load_model

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
    keep: list[dict] | None = None,
) -> pd.DataFrame:
    """Backtest one series. If ``step_rows`` is given, per-step errors are appended to it for
    the horizon analysis (how fast does skill decay the further ahead we look?). If
    ``ensemble_of`` names models, their quantile-averaged ensemble is scored too. If
    ``path_rows`` is given, the full forecast paths of model ``paths_for`` are appended to it,
    which is what the animated "replay" of forecasts versus reality is drawn from. If ``keep`` is
    given, every window's forecasts are appended to it, for ``add_seldon``."""
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
    wanted = {paths_for} if isinstance(paths_for, str) else set(paths_for or ())
    if keep is not None:
        keep.extend({"spec": spec, "series": series, "t": t, "context": c,
                     "forecasts": {name: f[i] for name, f in by_model.items()}}
                    for i, (t, c) in enumerate(zip(cuts, contexts)))

    rows = []
    for name, forecasts in by_model.items():
        for t, context, forecast in zip(cuts, contexts, forecasts):
            rows.append(score_window(spec, series, t, context, name, forecast, step_rows,
                                     path_rows if name in wanted else None))
    return pd.DataFrame(rows)


def score_window(spec: SeriesSpec, series: pd.Series, t: int, context: np.ndarray, name: str, forecast: Forecast,
                 step_rows: list[dict] | None = None, path_rows: list[dict] | None = None) -> dict:
    """Score one model's forecast for the window starting at index ``t``, and record its per-step
    errors and path when asked."""
    horizon = spec.horizon
    actual = series.to_numpy(dtype=float)[t : t + horizon]
    if path_rows is not None:
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
    return {
        "series_id": spec.id, "domain": spec.domain, "scale": spec.scale, "model": name,
        "origin": series.index[t - 1].date(), "horizon": horizon, **score(context, actual, forecast),
    }


def seldon_windows(kept: list[dict], model: str) -> list[seldon.Window]:
    """The kept windows as the full Seldon learns from them: ``model``'s and the laws' middles."""
    windows = []
    for k in kept:
        f = k["forecasts"]
        if model in f and LAWS in f:
            spec, series, t = k["spec"], k["series"], k["t"]
            actual = series.to_numpy(dtype=float)[t : t + spec.horizon]
            windows.append(seldon.Window(spec.domain, series.index[t + len(actual) - 1], float(k["context"][-1]),
                                         f[model].q(0.5)[: len(actual)], f[LAWS].q(0.5)[: len(actual)], actual))
    return windows


def add_seldon(kept: list[dict], model: str, step_rows: list[dict] | None = None,
               path_rows: list[dict] | None = None, paths_for: Sequence[str] = ()) -> pd.DataFrame:
    """Score the full Seldon on every kept window: ``model`` and the crowd laws in one council, the
    laws' share learned per area only from windows (of any series in that area) that had finished
    by this window's origin. See ``seldon.py``."""
    windows = seldon_windows(kept, model)
    rows = []
    for k in kept:
        f = k["forecasts"]
        if model not in f or LAWS not in f:
            continue
        spec, series, t = k["spec"], k["series"], k["t"]
        share = seldon.share_for(windows, spec.domain, series.index[t - 1])
        rows.append(score_window(spec, series, t, k["context"], seldon.NAME, seldon.blend(f[model], f[LAWS], share),
                                 step_rows, path_rows if seldon.NAME in paths_for else None) | {"share": share})
    return pd.DataFrame(rows)


def add_radiant(kept: list[dict], model: str, step_rows: list[dict] | None = None,
                path_rows: list[dict] | None = None, paths_for: Sequence[str] = ()) -> pd.DataFrame:
    """Score the full Radiant on every kept window: ``model``, the crowd laws, Radiant's core and
    no change mixed with exponential weights learned per area (yearly series apart) only from windows that
    had finished by this window's origin. See ``radiant.py``."""
    need = dict(zip(radiant.EXPERTS, (model, LAWS, radiant.CORE, "naive", radiant.RIVAL)))
    must = [need[e] for e in radiant.EXPERTS if e != "rival"]  # the rival joins only when it ran

    def experts(f: dict) -> dict:
        return {e: f[n] for e, n in need.items() if n in f}

    windows = []
    for k in kept:
        f = k["forecasts"]
        if all(n in f for n in must):
            spec, series, t = k["spec"], k["series"], k["t"]
            actual = series.to_numpy(dtype=float)[t : t + spec.horizon]
            windows.append(radiant.Window(radiant.area(spec), series.index[t + len(actual) - 1],
                                          {e: x.q(0.5)[: len(actual)] for e, x in experts(f).items()}, actual))
    rows = []
    for k in kept:
        f = k["forecasts"]
        if not all(n in f for n in must):
            continue
        spec, series, t = k["spec"], k["series"], k["t"]
        x = experts(f)
        w = radiant.present(radiant.weights(windows, radiant.area(spec), series.index[t - 1], rival="rival" in x), x)
        mixed = radiant.mix(x, w)
        rows.append(score_window(spec, series, t, k["context"], radiant.NAME, mixed, step_rows,
                                 path_rows if radiant.NAME in paths_for else None)
                    | {"weight_model": float(w[0]), "weight_rival": float(w[-1])})
    return pd.DataFrame(rows)


def _deciles(q10: np.ndarray, q50: np.ndarray, q90: np.ndarray) -> np.ndarray:
    """All nine deciles from the three a backtest path keeps, each half spread like a normal curve."""
    z = np.array([-1.2816, -0.8416, -0.5244, -0.2533, 0.0, 0.2533, 0.5244, 0.8416, 1.2816]) / 1.2816
    lower, upper = (q50 - q10)[:, None], (q90 - q50)[:, None]
    return np.sort(q50[:, None] + np.where(z < 0, lower, upper) * z, axis=1)


def replay_seldon(results: pd.DataFrame, paths: pd.DataFrame, model: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The full Seldon on a run that only recorded ``model`` and the crowd laws (``seldon-laws``).

    Both left their 10th / 50th / 90th percentile paths, and the full Seldon is a blend of the two
    with the laws' share learned per area from windows finished before each origin, so it can be
    rebuilt without the data: exactly as ``add_seldon`` would for the point forecast (error, skill,
    direction) and the 80% range. Range skill (pinball) and the odds of a rise use all nine deciles,
    which the paths do not keep; they are read off a normal-shaped spread through the three that are,
    and range skill is anchored to ``model``'s recorded value. Returns window rows and path rows."""
    cols = ["series_id", "origin", "step"]
    mine = paths[paths["model"] == model].sort_values(cols)
    laws = paths[paths["model"] == LAWS].set_index(cols)
    rows = results[results["model"] == model].set_index(["series_id", "origin"])
    naive = results[results["model"] == "naive"].set_index(["series_id", "origin"])
    after = mine.set_index(["series_id", "date"])["actual"]  # each window starts where the one before ended
    kept = []
    for (series_id, origin), g in mine.groupby(["series_id", "origin"]):
        if (series_id, origin) not in rows.index:
            continue
        try:
            l = laws.loc[[(series_id, origin, s) for s in g["step"]]]
        except KeyError:
            continue
        row = rows.loc[(series_id, origin)]
        actual = g["actual"].to_numpy(float)
        if (series_id, origin) in after.index:
            last = float(after.loc[(series_id, origin)])
        else:  # the first window: the value at its origin is the one "no change" had to have used
            target = float(naive.loc[(series_id, origin), "mae"])
            grid = np.linspace(actual.min() - 3 * target, actual.max() + 3 * target, 4001)
            gap = np.abs(np.abs(grid[:, None] - actual).mean(axis=1) - target)
            ups = (actual[-1] > grid) == bool(row["went_up"])
            last = float(grid[np.argmin(np.where(ups, gap, np.inf))])
        kept.append({"row": row, "g": g, "laws": l, "last": last, "actual": actual,
                     "window": seldon.Window(row["domain"], pd.Timestamp(g["date"].max()), last,
                                             g["q50"].to_numpy(float), l["q50"].to_numpy(float), actual)})
    windows = [k["window"] for k in kept]
    out_rows, out_paths = [], []
    for k in kept:
        row, g, l, last, actual = k["row"], k["g"], k["laws"], k["last"], k["actual"]
        series_id, origin = g["series_id"].iloc[0], g["origin"].iloc[0]
        share = seldon.share_for(windows, row["domain"], origin)
        bands = [(1 - share) * g[c].to_numpy(float) + share * l[c].to_numpy(float) for c in ("q10", "q50", "q90")]
        lo, mid, hi = bands
        out_paths += [{"series_id": series_id, "model": seldon.NAME, "origin": origin, "date": d, "step": s,
                       "q10": a, "q50": b, "q90": c, "actual": y}
                      for d, s, a, b, c, y in zip(g["date"], g["step"], lo, mid, hi, actual)]
        if share == 0:  # the full Seldon gave the model the whole vote: its forecast, its scores
            out_rows.append(row.to_dict() | {"series_id": series_id, "origin": origin, "model": seldon.NAME, "share": 0.0})
            continue
        scale = row["mae"] / row["mase"] if row["mase"] else 1.0
        err = actual - mid
        q = np.asarray(QUANTILES)
        pinball = lambda d: float(np.mean(np.maximum(q * d, (q - 1) * d))) / scale  # noqa: E731
        mine_d = _deciles(*(g[c].to_numpy(float) for c in ("q10", "q50", "q90")))
        blend_d = _deciles(lo, mid, hi)
        true_move, pred_move = np.sign(actual[-1] - last), np.sign(mid[-1] - last)
        p_up = prob_above(blend_d[-1], last)
        denom = np.abs(actual) + np.abs(mid)
        out_rows.append({
            "series_id": series_id, "domain": row["domain"], "scale": row["scale"], "model": seldon.NAME,
            "origin": origin, "horizon": row["horizon"], "mae": float(np.mean(np.abs(err))),
            "rmse": float(np.sqrt(np.mean(err ** 2))),
            "smape": float(np.mean(np.where(denom > 0, 2 * np.abs(err) / np.where(denom > 0, denom, 1), 0.0))),
            "mase": float(np.mean(np.abs(err))) / scale,
            "direction": float(true_move == pred_move) if true_move != 0 and pred_move != 0 else np.nan,
            "coverage80": float(np.mean((actual >= lo) & (actual <= hi))),
            "pinball": row["pinball"] + pinball(actual[:, None] - blend_d) - pinball(actual[:, None] - mine_d),
            "brier": (p_up - row["went_up"]) ** 2, "p_up": p_up, "went_up": row["went_up"], "share": share,
        })
    return pd.DataFrame(out_rows), pd.DataFrame(out_paths)


def upgrade_run(results: pd.DataFrame, paths: pd.DataFrame, model: str) -> tuple[pd.DataFrame, pd.DataFrame, bool]:
    """Bring a run recorded before the full Seldon (its ``seldon`` rows were the crowd laws alone,
    and carry no ``share``) up to date: those rows become ``seldon-laws`` and the full Seldon is
    replayed from the recorded paths (``replay_seldon``). Newer runs come back unchanged."""
    legacy = seldon.NAME in set(results["model"]) and LAWS not in set(results["model"]) and "share" not in results
    if not legacy:
        return results, paths, False
    rename = {seldon.NAME: LAWS}
    results, paths = results.replace({"model": rename}), paths.replace({"model": rename})
    rows, extra = replay_seldon(results, paths, model)
    results = pd.concat([results, rows], ignore_index=True)
    results.attrs["replayed"] = True
    return results, pd.concat([paths, extra], ignore_index=True), True


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


def head_to_head(results: pd.DataFrame, model: str, challenger: str = CHALLENGER) -> pd.DataFrame:
    """The duel: ``model`` (TimesFM) against ``challenger`` (Seldon), one row per domain plus "all".

    Only series both of them forecast count, on exactly the same windows. A series is won by
    whichever had the lower average error there (``wins`` / ``losses`` are the challenger's);
    ``skill`` and ``prob_skill`` are medians against the naive baseline, as in the scoreboard,
    and ``coverage80`` is the share of reality inside each 80% range (0.80 is honest). The
    ``winner`` of a row is whoever won more of its series; ``error_change`` is the challenger's
    average error relative to the model's, series by series (-0.05 means 5% less error)."""
    columns = ["domain", "series", "wins", "losses", "error_change", "model_skill", "challenger_skill", "model_prob_skill",
               "challenger_prob_skill", "model_coverage80", "challenger_coverage80", "winner"]
    if results is None or results.empty or not {model, challenger} <= set(results["model"]):
        return pd.DataFrame(columns=columns)
    summary = summarize(results)
    both = summary[summary["model"].isin([model, challenger])]
    wide = both.pivot_table(index=["series_id", "domain"], columns="model",
                            values=["mae", "skill", "prob_skill", "coverage80"]).dropna()
    rows = []
    for domain, part in [*wide.groupby(level="domain"), ("all", wide)]:
        wins = int((part[("mae", challenger)] < part[("mae", model)]).sum())
        losses = int((part[("mae", challenger)] > part[("mae", model)]).sum())
        rows.append({
            "domain": domain, "series": len(part), "wins": wins, "losses": losses,
            "error_change": float((part[("mae", challenger)] / part[("mae", model)]).mean() - 1),
            "model_skill": part[("skill", model)].median(), "challenger_skill": part[("skill", challenger)].median(),
            "model_prob_skill": part[("prob_skill", model)].median(),
            "challenger_prob_skill": part[("prob_skill", challenger)].median(),
            "model_coverage80": part[("coverage80", model)].mean(),
            "challenger_coverage80": part[("coverage80", challenger)].mean(),
            "winner": challenger if wins > losses else model if losses > wins else "tie",
        })
    return pd.DataFrame(rows, columns=columns)


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
