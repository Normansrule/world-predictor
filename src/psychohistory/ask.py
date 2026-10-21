"""``psychohistory ask``: run a model live on one series and read the answer off its forecast.

Works on any series in the catalog (from the local data cache) or on your own CSV of dates and
values. Prints the middle and the 80% range for every step ahead, Seldon's corrected range when
backtest paths exist for that series, and the chance of ending above a level you name. With
``--seal`` the forecast is also written to the prediction ledger, so ``psychohistory score``
checks it once the dates pass.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from . import seldon
from .ledger import future_dates
from .metrics import prob_above
from .models import Forecast, Forecaster


def read_csv(path: Path) -> pd.Series:
    """A CSV whose first two columns are date and value (a header row is optional), as a sorted series."""
    frame = pd.read_csv(path, header=None, usecols=[0, 1], names=["date", "value"], dtype=str)
    dates = pd.to_datetime(frame["date"], errors="coerce", format="mixed")
    series = pd.Series(pd.to_numeric(frame["value"], errors="coerce").to_numpy(), index=dates)
    series = series[series.index.notna()].dropna().sort_index()  # drops a header row too
    series = series[~series.index.duplicated(keep="last")]
    if len(series) < 8:
        raise ValueError(f"{path} has {len(series)} usable rows of date,value; a forecast needs at least 8")
    return series


def guess_freq(series: pd.Series) -> str:
    """"B" for weekday-only data such as prices, "D" otherwise (good enough for dating the steps)."""
    days = series.index[-60:].dayofweek
    return "B" if len(days) > 10 and (days >= 5).sum() == 0 else "D"


def ask(series: pd.Series, model: Forecaster, horizon: int, freq: str,
        correction: seldon.Correction | None = None, above: float | None = None,
        max_context: int = 1024) -> pd.DataFrame:
    """One row per step ahead: the model's q10 / q50 / q90, Seldon's (when a correction is given)
    and, with ``above``, each one's chance of ending above that level."""
    last = float(series.iloc[-1])
    base: Forecast = model.forecast([series.to_numpy(dtype=float)[-max_context:]], horizon)[0]
    versions = {"model": base}
    if correction is not None:
        versions["seldon"] = seldon.apply(base, last, correction)
    rows = []
    for step, target in enumerate(future_dates(series.index[-1], horizon, freq)):
        row = {"step": step + 1, "date": target.date().isoformat()}
        for key, fc in versions.items():
            row[f"{key}_q10"], row[f"{key}_q50"], row[f"{key}_q90"] = (float(fc.q(lv)[step]) for lv in (0.1, 0.5, 0.9))
            if above is not None:
                row[f"{key}_p_above"] = prob_above(fc.quantiles[step], above)
        rows.append(row)
    return pd.DataFrame(rows)


def describe(table: pd.DataFrame, last: float, model_name: str, above: float | None) -> str:
    """The table as plain text, ending with a one-line answer about the last step."""
    has_seldon = "seldon_q50" in table
    head = f"{'step':>4}  {'date':<10}  {model_name + ' middle':>16}  {'80% range':>23}"
    if has_seldon:
        head += f"  {'Seldon middle':>14}  {'Seldon 80% range':>23}"
    lines = [head]
    for r in table.itertuples(index=False):
        line = f"{r.step:>4}  {r.date:<10}  {_num(r.model_q50):>16}  {_num(r.model_q10) + ' to ' + _num(r.model_q90):>23}"
        if has_seldon:
            line += f"  {_num(r.seldon_q50):>14}  {_num(r.seldon_q10) + ' to ' + _num(r.seldon_q90):>23}"
        lines.append(line)
    end = table.iloc[-1]
    move = end["model_q50"] / last - 1 if last else float("nan")
    lines.append("")
    lines.append(f"By {end['date']} {model_name} expects {_num(end['model_q50'])} ({move:+.1%} from {_num(last)}), "
                 f"80% sure it lands between {_num(end['model_q10'])} and {_num(end['model_q90'])}.")
    if above is not None:
        answer = f"Chance it ends above {_num(above)}: {model_name} {end['model_p_above']:.0%}"
        if has_seldon:
            answer += f", Seldon {end['seldon_p_above']:.0%}"
        lines.append(answer + " (read off the forecast's deciles; tails are capped at 5% and 95%).")
    return "\n".join(lines)


def _num(v: float) -> str:
    a = abs(v)
    return f"{v:,.0f}" if a >= 1000 else f"{v:,.2f}" if a >= 1 else f"{v:.4g}"


def ledger_rows(table: pd.DataFrame, series: pd.Series, series_id: str, domain: str, scale: str,
                model_name: str, made_on: str) -> pd.DataFrame:
    """The asked forecast in the ledger's own columns, so ``psychohistory score`` can check it."""
    last = float(series.iloc[-1])
    out = []
    for key, name in (("model", model_name), ("seldon", seldon.NAME)):
        if f"{key}_q50" not in table:
            continue
        for r in table.itertuples(index=False):
            q10, q50, q90 = getattr(r, f"{key}_q10"), getattr(r, f"{key}_q50"), getattr(r, f"{key}_q90")
            out.append({
                "made_on": made_on, "model": name, "series_id": series_id, "domain": domain, "scale": scale,
                "last_date": series.index[-1].date().isoformat(), "last_value": last, "step": r.step,
                "target_date": r.date, "q10": q10, "q50": q50, "q90": q90, "point": q50,
                "p_up": prob_above(np.interp(np.linspace(0.1, 0.9, 9), [0.1, 0.5, 0.9], [q10, q50, q90]), last),
            })
    return pd.DataFrame(out)
