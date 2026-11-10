"""``psychohistory desk``: a forecast desk note for any market, the way an analyst would want it.

Name a catalog series (``gold``), any Yahoo Finance ticker (``MSFT``, ``^FTSE``, ``EURUSD=X``,
``ETH-USD``) or your own CSV. For each one the desk

1. forecasts the next ``horizon`` steps with the model under test and with Seldon (its own council
   without the model: crowd laws, behavioural core and no change, weighted by this asset's past windows),
2. reads the odds of ending above price levels off each forecast's deciles,
3. sets the volatility the forecast implies beside the volatility the market has shown, and
4. backtests every model on this asset's own past windows, so you can see which one has earned
   your trust here before you read its forecast.

It writes a Markdown note, a CSV of every step and a JSON file for your own tools. Nothing here is
investment advice: markets sit close to a random walk, and the track record says how close.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from . import backtest, catalog, seldon, volatility
from .catalog import SeriesSpec
from .ledger import future_dates
from .metrics import prob_above
from .models import LAWS, Forecast, Forecaster
from .volatility import periods_per_year

CHECKPOINTS = (1, 5, 10, 20, 60)  # steps the outlook table always shows, when within the horizon
LEVEL_MOVES = (-0.10, -0.05, 0.05, 0.10)  # default price levels, as moves from the last value
REALIZED_DAYS = 63  # about three months of trading days
_Z90 = 1.2816  # the 90th percentile of a standard normal


@dataclass
class Desk:
    """Everything one desk note says about one asset."""

    spec: SeriesSpec
    model: str
    last: float
    last_date: pd.Timestamp
    table: pd.DataFrame  # one row per step: date, each forecaster's deciles and chance of rising
    share: float  # the crowd laws' share of Seldon's own vote
    levels: pd.DataFrame  # level, each forecaster's chance of ending above it
    vol: dict  # annualised volatility: realized, and implied by each forecaster's range
    record: pd.DataFrame  # one row per model: skill and calibration on this asset's past windows
    windows: int = 0
    notes: list[str] = field(default_factory=list)


def spec_for(target: str, horizon: int | None = None) -> SeriesSpec:
    """A catalog series by id, or any Yahoo Finance ticker as a market series of its own."""
    try:
        spec = catalog.by_id(target)
    except KeyError:
        ticker = target.strip()
        slug = re.sub(r"[^a-z0-9]+", "_", ticker.lower()).strip("_") or "asset"
        daily = ticker.upper().endswith("-USD")  # crypto trades every day; everything else on weekdays
        spec = SeriesSpec(f"desk_{slug}", "markets", "yahoo", {"ticker": ticker}, "D" if daily else "B", 20,
                          "individual", ticker)
    if horizon:
        spec = SeriesSpec(spec.id, spec.domain, spec.source, spec.params, spec.freq, horizon, spec.scale,
                          spec.description, spec.extra_models)
    return spec


def end_steps(desk: "Desk") -> int:
    return len(desk.table)


def realized_vol(series: pd.Series, freq: str, days: int = REALIZED_DAYS) -> float | None:
    """Annualised standard deviation of the last ``days`` log returns (None for non-positive data)."""
    values = series.to_numpy(dtype=float)[-(days + 1):]
    if len(values) < 3 or (values <= 0).any():
        return None
    return float(np.std(np.diff(np.log(values)), ddof=1) * math.sqrt(periods_per_year(freq)))


def implied_vol(q10: float, q90: float, steps: int, freq: str) -> float | None:
    """The annualised volatility a forecast's 80% range implies at ``steps`` ahead, reading the range
    as a log-normal one: (ln q90 - ln q10) / (2 x 1.2816) per sqrt(step)."""
    if q10 <= 0 or q90 <= 0 or steps < 1:
        return None
    return float((math.log(q90) - math.log(q10)) / (2 * _Z90) / math.sqrt(steps) * math.sqrt(periods_per_year(freq)))


def default_levels(last: float, extra: list[float] | None = None) -> list[float]:
    """Round price levels around the last value, plus any the user named."""
    def round_nice(x: float) -> float:
        if x == 0:
            return 0.0
        digits = max(0, 2 - int(math.floor(math.log10(abs(x)))))
        return round(x, digits)
    levels = {round_nice(last * (1 + m)) for m in LEVEL_MOVES} | set(extra or [])
    return sorted(levels)


def forecast_table(series: pd.Series, spec: SeriesSpec, versions: dict[str, Forecast]) -> pd.DataFrame:
    """One row per step: its date and, for every forecaster, q10..q90 and the chance of ending higher."""
    last = float(series.iloc[-1])
    rows = []
    for step, target in enumerate(future_dates(series.index[-1], spec.horizon, spec.freq)):
        row = {"step": step + 1, "date": target.date().isoformat()}
        for name, fc in versions.items():
            for level, value in zip((10, 20, 30, 40, 50, 60, 70, 80, 90), fc.quantiles[step]):
                row[f"{name}_q{level}"] = float(value)
            row[f"{name}_p_up"] = prob_above(fc.quantiles[step], last)
        rows.append(row)
    return pd.DataFrame(rows)


def track_record(spec: SeriesSpec, series: pd.Series, model: Forecaster, others: list[Forecaster],
                 windows: int) -> tuple[pd.DataFrame, np.ndarray, int]:
    """Backtest every model on this asset's own past windows. Returns one row per model (skill and
    calibration, best first), the weights of Seldon's own voters for a forecast made now, and how many windows
    were scored."""
    kept = []
    results = backtest.backtest_series(spec, series, [model, *others], windows=windows, keep=kept)
    if results.empty:
        return pd.DataFrame(), 0.0, 0
    full = backtest.add_seldon(kept, model.name)
    results = pd.concat([results, full], ignore_index=True)
    from . import radiant
    weights = seldon.own_weights(backtest.own_windows(backtest.own_voters(kept, model.name)), radiant.area(spec))
    summary = backtest.summarize(results)
    cols = ["model", "skill", "prob_skill", "coverage80", "direction", "brier", "mase"]
    record = summary[cols].sort_values("skill", ascending=False).reset_index(drop=True)
    return record, weights, int(results["origin"].nunique())


def build(spec: SeriesSpec, series: pd.Series, model: Forecaster, others: list[Forecaster],
          levels: list[float] | None = None, windows: int = 8, max_context: int = 1024) -> Desk:
    """The whole desk note for one asset, from its history alone."""
    context = series.to_numpy(dtype=float)[-max_context:]
    record, weights, scored = track_record(spec, series, model, others, windows)
    base = model.forecast([context], spec.horizon)[0]
    laws, _ = seldon.predict(context, spec.horizon)
    own, used = seldon.own_mix(seldon.own_voters(context, spec.horizon, None, laws), weights)
    share = float(used[0])
    versions = {model.name: base, seldon.NAME: own, LAWS: laws}
    table = forecast_table(series, spec, versions)
    last = float(series.iloc[-1])
    end = len(table) - 1
    level_rows = []
    for level in default_levels(last, levels):
        row = {"level": level, "move": level / last - 1 if last else float("nan")}
        for name, fc in versions.items():
            row[name] = prob_above(fc.quantiles[end], level)
        level_rows.append(row)
    vol = {"realized": realized_vol(series, spec.freq)}
    for name in versions:
        vol[name] = implied_vol(table[f"{name}_q10"].iloc[end], table[f"{name}_q90"].iloc[end], end + 1, spec.freq)
    returns = volatility.log_returns(series.to_numpy(dtype=float))
    if returns is not None and len(returns) >= 60:  # GARCH and EWMA over the same horizon
        for name, by_h in volatility.built_in(returns, spec.freq, [end + 1]).items():
            vol[name] = volatility.annual(by_h[end + 1], spec.freq)
    notes = []
    if scored < 3:
        notes.append(f"Only {scored} past windows fitted in this history, so the track record is thin.")
    return Desk(spec, model.name, last, series.index[-1], table, share, pd.DataFrame(level_rows), vol, record, scored, notes)


# ------------------------------------------------------------------------------------------
# Writing it down
# ------------------------------------------------------------------------------------------

def _num(v: float | None) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    a = abs(v)
    return f"{v:,.0f}" if a >= 10000 else f"{v:,.2f}" if a >= 1 else f"{v:.4g}"


def _pct(v: float | None, signed: bool = False) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    return f"{v:+.1%}" if signed else f"{v:.0%}"


def display_name(name: str) -> str:
    return {"seldon": "Seldon", LAWS: "Seldon laws", "naive": '"No change"'}.get(
        name, "TimesFM 2.5" if name == "timesfm-2.5" else "TimesFM 3" if name == "timesfm-3" else name)


def verdict(desk: Desk) -> str:
    """One sentence on whom to trust on this asset, from its own track record."""
    r = desk.record
    if r.empty:
        return "There is not enough history here to backtest, so no model has a track record on this asset yet."
    rivals = r[r["model"] != "naive"]
    best = rivals.iloc[0]
    name = display_name(best["model"])
    if best["skill"] < 0.02:
        return (f"Nothing beat \"no change\" by 2% or more on the last {desk.windows} windows (best: {name}, "
                f"{best['skill']:+.1%}): read the forecasts as ranges, not calls.")
    return (f"{name} had the least error on the last {desk.windows} windows ({best['skill']:+.1%} against "
            f"\"no change\", {best['coverage80']:.0%} of reality inside its 80% range).")


def note(desk: Desk) -> str:
    """The desk note as Markdown."""
    spec, t, last, m = desk.spec, desk.table, desk.last, desk.model
    ticker = spec.params.get("ticker", spec.id)
    out = [f"# Forecast desk: {spec.description or ticker} ({ticker})", "",
           f"Data through {desk.last_date.date()}, last value **{_num(last)}**. Forecasts by {display_name(m)} and "
           f"Seldon (its own council without {display_name(m)}: crowd laws, behavioural core and no change; the laws hold "
           f"{desk.share:.0%} of the vote, learned from this asset's past windows).", "", "## Outlook", "",
           f"| Ahead | Date | {display_name(m)} middle | Move | 80% range | Chance higher | Seldon middle | Seldon chance higher |",
           "|---|---|---|---|---|---|---|---|"]
    steps = sorted({s for s in CHECKPOINTS if s <= len(t)} | {len(t)})
    for s in steps:
        r = t.iloc[s - 1]
        out.append(f"| {s} | {r['date']} | {_num(r[f'{m}_q50'])} | {_pct(r[f'{m}_q50'] / last - 1, True)} | "
                   f"{_num(r[f'{m}_q10'])} to {_num(r[f'{m}_q90'])} | {_pct(r[f'{m}_p_up'])} | "
                   f"{_num(r['seldon_q50'])} | {_pct(r['seldon_p_up'])} |")
    v = desk.vol
    out += ["", "## Volatility", "",
            f"Over the last {REALIZED_DAYS} steps the market moved with **{_pct(v['realized'])}** annualised "
            f"volatility. {display_name(m)}'s range implies {_pct(v.get(m))}, Seldon's {_pct(v.get(seldon.NAME))}. "
            "A forecast calmer than the market has been is betting on calm."
            + (f" Over the same {end_steps(desk)} steps GARCH(1,1) expects {_pct(v.get(volatility.GARCH))} and EWMA "
               f"{_pct(v.get(volatility.EWMA))}; volatility, unlike price, clusters, so these are the forecasts with a "
               "record of beating last month's (`psychohistory vol`)." if v.get(volatility.GARCH) is not None else ""), "",
            f"## Price levels on {t['date'].iloc[-1]}", "",
            f"| Level | Move | {display_name(m)}: chance above | Seldon: chance above | Seldon laws: chance above |", "|---|---|---|---|---|"]
    for _, r in desk.levels.iterrows():
        out.append(f"| {_num(r['level'])} | {_pct(r['move'], True)} | {_pct(r[m])} | {_pct(r[seldon.NAME])} | {_pct(r[LAWS])} |")
    out += ["", f"## Track record on this asset ({desk.windows} past windows of {spec.horizon} steps)", ""]
    if desk.record.empty:
        out.append("_Not enough history to backtest._")
    else:
        out += ["| Model | Skill vs \"no change\" | Range skill | In 80% range | Right direction | Odds score (Brier) |",
                "|---|---|---|---|---|---|"]
        for r in desk.record.itertuples(index=False):
            out.append(f"| {display_name(r.model)} | {_pct(r.skill, True)} | {_pct(r.prob_skill, True)} | {_pct(r.coverage80)} | "
                       f"{_pct(r.direction)} | {r.brier:.3f} |")
    out += ["", verdict(desk), *desk.notes, "",
            "_Skill is the share of error removed against \"tomorrow looks like today\"; an honest 80% range "
            "catches reality about 80% of the time; a Brier score of 0.25 is a coin flip. Chances are read off "
            "each forecast's deciles, with tails capped at 5% and 95%. Not investment advice._", ""]
    return "\n".join(out)


def payload(desk: Desk) -> dict:
    """The desk as plain JSON-ready values."""
    def clean(v):
        return None if v is None or (isinstance(v, float) and math.isnan(v)) else v
    return {
        "asset": desk.spec.id, "ticker": desk.spec.params.get("ticker"), "description": desk.spec.description,
        "model": desk.model, "last": desk.last, "last_date": desk.last_date.date().isoformat(), "share": desk.share,
        "horizon": desk.spec.horizon, "freq": desk.spec.freq, "volatility": {k: clean(v) for k, v in desk.vol.items()},
        "steps": json.loads(desk.table.to_json(orient="records")),
        "levels": json.loads(desk.levels.to_json(orient="records")),
        "track_record": json.loads(desk.record.to_json(orient="records")), "windows": desk.windows,
        "verdict": verdict(desk),
    }


def write(desk: Desk, out_dir: Path) -> list[Path]:
    """desk_<asset>.md, .csv (every step) and .json in ``out_dir``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = out_dir / desk.spec.id.removeprefix("desk_")
    paths = [stem.with_suffix(".md"), stem.with_suffix(".csv"), stem.with_suffix(".json")]
    paths[0].write_text(note(desk))
    desk.table.to_csv(paths[1], index=False)
    paths[2].write_text(json.dumps(payload(desk), indent=1) + "\n")
    return paths
