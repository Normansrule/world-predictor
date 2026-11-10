"""The prediction ledger: forecasts written down *before* the future happens, then scored.

Backtests can be fooled (a model may have been trained on the very period it is tested on;
TimesFM's pretraining corpus includes public data up to its release). The only fully honest
test of foresight is to publish predictions with a timestamp and check them later, which is
exactly what Seldon did with his recorded messages in the Time Vault.

``predict`` appends rows to ``predictions/ledger.csv``; ``score`` matches them with actual values
once those dates have passed and writes ``predictions/scored.csv``.
"""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from .catalog import SeriesSpec
from .metrics import prob_above
from .models import Forecast, Forecaster

LEDGER = Path("predictions/ledger.csv")
SCORED = Path("predictions/scored.csv")
SEALS = Path("predictions/seals.csv")  # a SHA-256 fingerprint of every batch, so years later no edit goes unseen

COLUMNS = [
    "made_on", "model", "series_id", "domain", "scale", "last_date", "last_value",
    "step", "target_date", "q10", "q50", "q90", "point", "p_up",
]


def future_dates(last: pd.Timestamp, horizon: int, freq: str) -> pd.DatetimeIndex:
    offset = pd.tseries.frequencies.to_offset(freq)
    return pd.date_range(last + offset, periods=horizon, freq=freq)


def predict(
    specs: list[SeriesSpec],
    data: dict[str, pd.Series],
    model: Forecaster,
    max_context: int = 1024,
    made_on: date | None = None,
    extras: dict[str, Callable[[SeriesSpec, Forecast, np.ndarray], Forecast]] | None = None,
) -> pd.DataFrame:
    """Seal ``model``'s forecasts: one row per series and step ahead. ``extras`` maps another
    model's name to a function that builds its forecast from this one and the context (the full
    Seldon, which gives this model a vote), so the model runs once for both."""
    made_on = made_on or date.today()
    specs = [s for s in specs if s.id in data]
    rows = []
    # Group by horizon so each model call is one batch.
    for horizon in sorted({s.horizon for s in specs}):
        group = [s for s in specs if s.horizon == horizon]
        contexts = [data[s.id].to_numpy(dtype=float)[-max_context:] for s in group]
        for spec, context, base in zip(group, contexts, model.forecast(contexts, horizon)):
            series = data[spec.id]
            dates = future_dates(series.index[-1], horizon, spec.freq)
            versions = [(model.name, base)] + [(name, fn(spec, base, context)) for name, fn in (extras or {}).items()]
            for (name, forecast), (step, target) in ((v, d) for v in versions for d in enumerate(dates)):
                rows.append(
                    {
                        "made_on": made_on.isoformat(),
                        "model": name,
                        "series_id": spec.id,
                        "domain": spec.domain,
                        "scale": spec.scale,
                        "last_date": series.index[-1].date().isoformat(),
                        "last_value": float(series.iloc[-1]),
                        "step": step + 1,
                        "target_date": target.date().isoformat(),
                        "q10": float(forecast.q(0.1)[step]),
                        "q50": float(forecast.q(0.5)[step]),
                        "q90": float(forecast.q(0.9)[step]),
                        "point": float(forecast.point[step]),
                        "p_up": prob_above(forecast.quantiles[step], float(series.iloc[-1])),
                    }
                )
    return pd.DataFrame(rows, columns=COLUMNS)


def ensemble_rows(rows: pd.DataFrame, members: list[str], name: str = "ensemble") -> pd.DataFrame:
    """Quantile-averaged ensemble of the members' ledger rows. Averaging ``p_up`` gives the
    probability under an equal-weight mixture of the members."""
    part = rows[rows["model"].isin(members)]
    if part["model"].nunique() < 2:
        return pd.DataFrame(columns=COLUMNS)
    keys = ["made_on", "series_id", "domain", "scale", "last_date", "last_value", "step", "target_date"]
    combined = part.groupby(keys, as_index=False)[["q10", "q50", "q90", "point", "p_up"]].mean()
    combined["model"] = name
    return combined[COLUMNS]


def read(path: Path) -> pd.DataFrame | None:
    """A ledger or scored file as written, or None if there is none yet (see ``name_by_maker``)."""
    return name_by_maker(pd.read_csv(path)) if path.exists() and path.stat().st_size > 1 else None


def name_by_maker(rows: pd.DataFrame) -> pd.DataFrame:
    """Name every sealed row for the forecaster that made it. Before the full Seldon (the crowd laws
    then with TimesFM as one more voter, and since November 2026 its own council without TimesFM), ``seldon`` was the crowd laws alone; a day sealed since then
    always carries ``seldon-laws`` rows too, so a day with ``seldon`` rows and none of those was
    sealed by the laws. The file itself is never edited."""
    if rows.empty or "made_on" not in rows:
        return rows
    laws_days = set(rows.loc[rows["model"] == "seldon-laws", "made_on"])
    old = (rows["model"] == "seldon") & ~rows["made_on"].isin(laws_days)
    return rows.assign(model=rows["model"].where(~old, "seldon-laws")) if old.any() else rows


def append(rows: pd.DataFrame, path: Path = LEDGER) -> pd.DataFrame:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = pd.read_csv(path)
        rows = pd.concat([existing, rows], ignore_index=True)
        # Re-running on the same day replaces that day's predictions instead of duplicating them.
        rows = rows.drop_duplicates(["made_on", "model", "series_id", "step"], keep="last")
    rows.to_csv(path, index=False)
    return rows


def fingerprint(rows: pd.DataFrame, columns: list[str] = COLUMNS, order: tuple[str, ...] = ("series_id", "step", "target_date")) -> str:
    """SHA-256 of one batch's rows in a fixed order and number format, so the same rows always give
    the same fingerprint and any changed digit gives another."""
    rows = rows[columns].sort_values(list(order)).reset_index(drop=True)
    text = rows.to_csv(index=False, float_format="%.10g", lineterminator="\n")
    return hashlib.sha256(text.encode()).hexdigest()


def batches(entries: pd.DataFrame, columns: list[str] = COLUMNS, order: tuple[str, ...] = ("series_id", "step", "target_date")) -> pd.DataFrame:
    """One row per batch (a day and a model): how many rows it has and their fingerprint."""
    out = [{"made_on": str(made_on), "model": model, "rows": len(g), "sha256": fingerprint(g, columns, order)}
           for (made_on, model), g in entries.groupby(["made_on", "model"], sort=True)]
    return pd.DataFrame(out, columns=["made_on", "model", "rows", "sha256"])


def write_seals(entries: pd.DataFrame, path: Path = SEALS, today: str | None = None, **layout) -> pd.DataFrame:
    """Fingerprint every batch not yet in ``path`` (and today's, which a same-day re-run may replace).
    Earlier fingerprints are never rewritten, so ``verify`` can tell if an old batch was edited."""
    today = today or date.today().isoformat()
    current = batches(entries, **layout).assign(fingerprinted_on=today)
    if path.exists():
        old = pd.read_csv(path, dtype=str)
        keep = old[old["made_on"] != today]
        fresh = current[~current.set_index(["made_on", "model"]).index.isin(keep.set_index(["made_on", "model"]).index)]
        current = pd.concat([keep, fresh.astype(str)], ignore_index=True)
    current = current.sort_values(["made_on", "model"]).reset_index(drop=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    current.to_csv(path, index=False)
    return current


def verify(entries: pd.DataFrame, path: Path = SEALS, **layout) -> pd.DataFrame:
    """Every fingerprinted batch checked against the ledger as it is now: one row per batch with
    ``status`` "ok", "changed" (its rows differ from when they were fingerprinted) or "missing"."""
    if not path.exists():
        return pd.DataFrame(columns=["made_on", "model", "rows", "status"])
    seals = pd.read_csv(path, dtype=str)
    now = batches(entries, **layout).set_index(["made_on", "model"])
    out = []
    for r in seals.itertuples(index=False):
        key = (r.made_on, r.model)
        status = "missing" if key not in now.index else "ok" if now.loc[key, "sha256"] == r.sha256 else "changed"
        out.append({"made_on": r.made_on, "model": r.model, "rows": int(r.rows), "status": status,
                    "fingerprinted_on": getattr(r, "fingerprinted_on", "")})
    return pd.DataFrame(out)


def score(ledger: pd.DataFrame, data: dict[str, pd.Series]) -> pd.DataFrame:
    """Attach the actual value to every ledger row whose target date has arrived."""
    actuals = []
    for _, row in ledger.iterrows():
        series = data.get(row["series_id"])
        value = np.nan
        if series is not None:
            target = pd.Timestamp(row["target_date"])
            if target in series.index:
                value = float(series.loc[target])
        actuals.append(value)
    scored = ledger.assign(actual=actuals).dropna(subset=["actual"])
    scored["abs_error"] = (scored["actual"] - scored["point"]).abs()
    scored["naive_abs_error"] = (scored["actual"] - scored["last_value"]).abs()
    scored["in_band80"] = (scored["actual"] >= scored["q10"]) & (scored["actual"] <= scored["q90"])
    true_move = np.sign(scored["actual"] - scored["last_value"])
    pred_move = np.sign(scored["point"] - scored["last_value"])
    scored["direction_correct"] = np.where((true_move != 0) & (pred_move != 0), (true_move == pred_move).astype(float), np.nan)
    scored["brier"] = (scored["p_up"] - (scored["actual"] > scored["last_value"]).astype(float)) ** 2
    return scored


def ledger_summary(scored: pd.DataFrame) -> pd.DataFrame:
    """Per domain and model. Skill is computed per series first (so a big-number series such as
    Bitcoin cannot dominate), then the median across series is reported."""
    if scored.empty:
        return pd.DataFrame()
    per_series = scored.groupby(["domain", "model", "series_id"]).agg(
        predictions=("actual", "size"),
        mae=("abs_error", "mean"),
        naive_mae=("naive_abs_error", "mean"),
        direction=("direction_correct", "mean"),
        coverage80=("in_band80", "mean"),
        brier=("brier", "mean"),
    )
    per_series["skill"] = 1 - per_series["mae"] / per_series["naive_mae"].replace(0, np.nan)
    return (
        per_series.groupby(["domain", "model"])
        .agg(
            series=("mae", "size"),
            predictions=("predictions", "sum"),
            median_skill=("skill", "median"),
            direction=("direction", "mean"),
            coverage80=("coverage80", "mean"),
            brier=("brier", "mean"),
        )
        .reset_index()
    )


def latest(entries: pd.DataFrame) -> pd.DataFrame:
    """The most recent forecast for each series and model, at its furthest horizon."""
    if entries.empty:
        return entries
    newest = entries[entries["made_on"] == entries.groupby(["model", "series_id"])["made_on"].transform("max")]
    final = newest[newest["step"] == newest.groupby(["model", "series_id"])["step"].transform("max")].copy()
    final["median_change"] = final["q50"] / final["last_value"] - 1
    final["low_change"] = final["q10"] / final["last_value"] - 1
    final["high_change"] = final["q90"] / final["last_value"] - 1
    columns = ["domain", "series_id", "model", "last_date", "last_value", "target_date",
               "q10", "q50", "q90", "low_change", "median_change", "high_change", "p_up"]
    return final[columns].sort_values(["domain", "series_id"]).reset_index(drop=True)
