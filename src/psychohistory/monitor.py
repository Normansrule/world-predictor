"""The long-term monitor: every sealed forecast against what really happened, month after month.

The backtest says how a model *would* have done; the sealed ledger says how it *did*, on a future
nobody had seen. This module turns the scored ledger (``predictions/scored.csv``) into the record
you would want after one year or ten:

* ``by_month``: skill against "no change", the share of reality inside the 80% range, direction hit
  rate and Brier score for every model, area and month the forecasts came due in, plus the running
  totals since the first seal;
* ``vs_naive``: is the model really better than "no change", or just lucky? A Diebold-Mariano test
  (Diebold & Mariano, 1995) on the weekly batches, with a Newey-West variance because the batches'
  28-day forecasts overlap;
* ``alarms``: drift detection. A forecaster is flagged when its recent 80% range catches reality
  much less (or much more) often than 80%, when an edge it showed in the backtest has gone in the
  live record, or when it is now doing significantly worse than "no change".

Nothing is re-forecast or re-fitted here: it only reads what was sealed and what then happened.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

TARGET = 0.80  # an honest 80% range catches reality 80% of the time
EDGE = 0.02  # skill under 2% is no edge (as in the backtest's scoreboard)
RECENT_WEEKS = 13  # "recent" means the forecasts that came due in the last quarter
MIN_BATCHES = 4  # weekly batches a test needs before it says anything
ALPHA = 0.05


def _prepare(scored: pd.DataFrame) -> pd.DataFrame:
    rows = scored.dropna(subset=["actual"]).copy()
    rows["target_date"] = pd.to_datetime(rows["target_date"])
    rows["month"] = rows["target_date"].dt.to_period("M").astype(str)
    # Each series' errors are scaled by its own typical "no change" miss, so gold in dollars and
    # news attention in percent can be pooled.
    scale = rows.groupby("series_id")["naive_abs_error"].transform("mean").replace(0, np.nan)
    rows["scaled"] = rows["abs_error"] / scale
    rows["scaled_naive"] = rows["naive_abs_error"] / scale
    rows["inside"] = rows["in_band80"].astype(float)
    return rows


def _skill(part: pd.DataFrame) -> float:
    """Median over series of 1 - (sum of errors) / (sum of "no change" errors)."""
    per = part.groupby("series_id")[["abs_error", "naive_abs_error"]].sum()
    per = per[per["naive_abs_error"] > 0]
    return float((1 - per["abs_error"] / per["naive_abs_error"]).median()) if len(per) else float("nan")


def _summary(part: pd.DataFrame) -> dict:
    return {"forecasts": int(len(part)), "series": int(part["series_id"].nunique()), "batches": int(part["made_on"].nunique()),
            "skill": _skill(part), "coverage80": float(part["inside"].mean()),
            "direction": float(part["direction_correct"].mean()), "brier": float(part["brier"].mean())}


def by_month(scored: pd.DataFrame | None) -> pd.DataFrame:
    """One row per model, area ("all" too) and month the forecasts came due in, with the running
    record since the first seal beside the month's own (``cum_*`` columns)."""
    if scored is None or scored.empty:
        return pd.DataFrame()
    rows = _prepare(scored)
    out = []
    for (model, domain), part in rows.groupby(["model", "domain"]):
        out += _months(part, model, domain)
    for model, part in rows.groupby("model"):
        out += _months(part, model, "all")
    return pd.DataFrame(out).sort_values(["model", "domain", "month"]).reset_index(drop=True)


def _months(part: pd.DataFrame, model: str, domain: str) -> list[dict]:
    out = []
    for month in sorted(part["month"].unique()):
        now, upto = part[part["month"] == month], part[part["month"] <= month]
        row = {"model": model, "domain": domain, "month": month, **_summary(now)}
        row |= {f"cum_{k}": v for k, v in _summary(upto).items() if k in ("forecasts", "skill", "coverage80", "direction", "brier")}
        out.append(row)
    return out


def overall(scored: pd.DataFrame | None) -> pd.DataFrame:
    """The live record since the first seal: one row per model and area ("all" too)."""
    if scored is None or scored.empty:
        return pd.DataFrame()
    rows = _prepare(scored)
    out = [{"model": m, "domain": d, **_summary(p)} for (m, d), p in rows.groupby(["model", "domain"])]
    out += [{"model": m, "domain": "all", **_summary(p)} for m, p in rows.groupby("model")]
    return pd.DataFrame(out).sort_values(["domain", "model"]).reset_index(drop=True)


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the regularized incomplete beta function (modified Lentz)."""
    tiny, qab, qap, qam = 1e-300, a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        for aa in (m * (b - m) * x / ((qam + m2) * (a + m2)), -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))):
            d = 1.0 + aa * d
            d = 1.0 / (d if abs(d) > tiny else tiny)
            c = 1.0 + aa / c
            c = c if abs(c) > tiny else tiny
            h *= d * c
        if abs(d * c - 1.0) < 1e-14:
            break
    return h


def _betainc(a: float, b: float, x: float) -> float:
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    front = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1) / (a + b + 2):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def t_sf(t: float, df: float) -> float:
    """Upper tail of Student's t with ``df`` degrees of freedom. With four or five weekly batches the
    normal curve's tails are far too thin, and every test here runs on a handful of batches."""
    if not math.isfinite(t) or df <= 0:
        return float("nan")
    tail = 0.5 * _betainc(df / 2, 0.5, df / (df + t * t))
    return tail if t >= 0 else 1.0 - tail


def diebold_mariano(d: np.ndarray, lag: int) -> tuple[float, float]:
    """The Diebold-Mariano statistic for a mean loss difference of zero, with a Newey-West
    (Bartlett) long-run variance over ``lag`` autocovariances, made fit for short records by the
    Harvey-Leybourne-Newbold correction and read off Student's t with n - 1 degrees of freedom
    (Harvey, Leybourne & Newbold, 1997). Without lags it is exactly the one-sample t-test. Too few
    batches for the overlap (the correction turns non-positive) gives NaN: no verdict. Negative
    means the first forecaster's loss was lower."""
    d = np.asarray(d, float)
    d = d[np.isfinite(d)]
    n = len(d)
    if n < 2:
        return float("nan"), float("nan")
    e = d - d.mean()
    var = float(e @ e) / n
    for k in range(1, min(lag, n - 1) + 1):
        var += 2 * (1 - k / (lag + 1)) * float(e[k:] @ e[:-k]) / n
    h = lag + 1
    correction = (n + 1 - 2 * h + h * (h - 1) / n) / n
    if var <= 0 or correction <= 0:
        return float("nan"), float("nan")
    stat = d.mean() / math.sqrt(var / n) * math.sqrt(correction)
    return float(stat), float(2 * t_sf(abs(stat), n - 1))


def false_discoveries(p: list[float], alpha: float = ALPHA) -> float:
    """The Benjamini-Hochberg cut-off: the largest p-value that still passes when ``len(p)`` tests
    run at once, so that on average at most ``alpha`` of the alarms raised are false
    (Benjamini & Hochberg, 1995). Returns -1 when none passes."""
    ranked = sorted(x for x in p if math.isfinite(x))
    m = len(ranked)
    cut = -1.0
    for k, value in enumerate(ranked, 1):
        if value <= alpha * k / m:
            cut = value
    return cut


def batch_differences(rows: pd.DataFrame) -> pd.Series:
    """Per weekly batch (``made_on``), the model's mean scaled error minus "no change"'s."""
    return (rows["scaled"] - rows["scaled_naive"]).groupby(rows["made_on"]).mean().sort_index()


def vs_naive(scored: pd.DataFrame | None, horizon_weeks: int = 4) -> pd.DataFrame:
    """Is each model really better than "no change" on its sealed forecasts? One row per model and
    area ("all" too): the mean scaled loss difference (negative favours the model), the DM statistic,
    its p-value and a plain verdict. Batches overlap by about ``horizon_weeks`` weeks, so that many
    autocovariances go into the variance."""
    if scored is None or scored.empty:
        return pd.DataFrame()
    rows = _prepare(scored)
    out = []
    groups = [*rows.groupby(["model", "domain"]), *(((m, "all"), p) for m, p in rows.groupby("model"))]
    for (model, domain), part in groups:
        d = batch_differences(part)
        stat, p = diebold_mariano(d.to_numpy(), horizon_weeks - 1) if len(d) >= MIN_BATCHES else (float("nan"), float("nan"))
        if len(d) < MIN_BATCHES:
            verdict = f"too early: {len(d)} of {MIN_BATCHES} weekly batches"
        elif p < ALPHA:
            verdict = "better than no change" if stat < 0 else "worse than no change"
        else:
            verdict = "not distinguishable from no change"
        out.append({"model": model, "domain": domain, "batches": int(len(d)), "loss_diff": float(d.mean()) if len(d) else float("nan"),
                    "dm": stat, "p": p, "verdict": verdict})
    return pd.DataFrame(out).sort_values(["domain", "model"]).reset_index(drop=True)


def alarms(scored: pd.DataFrame | None, backtest_summary: pd.DataFrame | None = None,
           today: pd.Timestamp | None = None) -> pd.DataFrame:
    """Drift detection, one row per raised alarm: model, series, the kind of alarm, and the numbers
    behind it. Looks at forecasts that came due in the last ``RECENT_WEEKS`` weeks.

    * ``range too narrow`` / ``range too wide``: the recent share inside the 80% range differs from
      80% by more than chance allows (a t-test on the weekly batches' shares, as the forecasts within
      one batch are not independent);
    * ``edge lost``: the backtest showed skill of 2% or more on this series, the live record since
      has none, over at least ``MIN_BATCHES`` batches;
    * ``worse than no change``: the Diebold-Mariano test says the model's recent errors are
      significantly larger than "no change"'s."""
    columns = ["model", "series_id", "domain", "alarm", "batches", "recent", "expected", "p"]
    if scored is None or scored.empty:
        return pd.DataFrame(columns=columns)
    rows = _prepare(scored)
    today = pd.Timestamp(today) if today is not None else rows["target_date"].max()
    recent = rows[rows["target_date"] > today - pd.Timedelta(weeks=RECENT_WEEKS)]
    expected = {}
    if backtest_summary is not None and not backtest_summary.empty:
        expected = {(r.model, r.series_id): r.skill for r in backtest_summary.itertuples()}
    out, tested = [], []
    for (model, series_id), part in recent.groupby(["model", "series_id"]):
        domain = part["domain"].iloc[0]
        shares = part.groupby("made_on")["inside"].mean()
        n = len(shares)
        if n >= MIN_BATCHES:
            mean, sd = float(shares.mean()), float(shares.std(ddof=1))
            if sd > 0:
                t = (mean - TARGET) / (sd / math.sqrt(n))
                p = 2 * t_sf(abs(t), n - 1)
                tested.append(({"model": model, "series_id": series_id, "domain": domain,
                                "alarm": "range too narrow" if t < 0 else "range too wide",
                                "batches": n, "recent": mean, "expected": TARGET, "p": p}, t))
            elif mean < TARGET - 0.3 or mean > 0.99:  # every batch identical: no variance to test, but plainly off
                out.append({"model": model, "series_id": series_id, "domain": domain,
                            "alarm": "range too narrow" if mean < TARGET else "range too wide",
                            "batches": n, "recent": mean, "expected": TARGET, "p": float("nan")})
        backtest = expected.get((model, series_id))
        live = rows[(rows["model"] == model) & (rows["series_id"] == series_id)]
        if backtest is not None and backtest >= EDGE and live["made_on"].nunique() >= MIN_BATCHES and _skill(live) <= 0:
            out.append({"model": model, "series_id": series_id, "domain": domain, "alarm": "edge lost",
                        "batches": int(live["made_on"].nunique()), "recent": _skill(live), "expected": float(backtest),
                        "p": float("nan")})
        d = batch_differences(part)
        if len(d) >= MIN_BATCHES:
            stat, p = diebold_mariano(d.to_numpy(), 3)
            if math.isfinite(p):
                tested.append(({"model": model, "series_id": series_id, "domain": domain, "alarm": "worse than no change",
                                "batches": int(len(d)), "recent": float(d.mean()), "expected": 0.0, "p": p}, stat))
    # Hundreds of tests run at once (every forecaster on every series), so 5% of them would ring by
    # chance alone; only the ones that pass the false-discovery cut are raised.
    cut = false_discoveries([row["p"] for row, _ in tested])
    out += [row for row, stat in tested if row["p"] <= cut and (row["alarm"] != "worse than no change" or stat > 0)]
    return pd.DataFrame(out, columns=columns)


def describe(scored: pd.DataFrame | None, model: str, backtest_summary: pd.DataFrame | None = None) -> str:
    """The monitor as plain text for the terminal."""
    record = overall(scored)
    if record.empty:
        return "No sealed forecast has come due yet. The monitor fills in as `psychohistory score` opens them."
    rows = _prepare(scored)
    first, last = rows["target_date"].min().date(), rows["target_date"].max().date()
    lines = [f"Sealed forecasts scored: {len(rows)} ({rows['made_on'].nunique()} weekly batches), due {first} to {last}.", ""]
    lines.append(f"{'model':<14} {'area':<8} {'forecasts':>9} {'skill':>7} {'in 80%':>7} {'direction':>9} {'Brier':>6}")
    for r in record.itertuples():
        lines.append(f"{r.model:<14} {r.domain:<8} {r.forecasts:>9} {r.skill:>+7.1%} {r.coverage80:>7.0%} {r.direction:>9.0%} {r.brier:>6.3f}")
    tests = vs_naive(scored)
    mine = tests[(tests["model"] == model)]
    if not mine.empty:
        lines += ["", f"Is {model} really better than \"no change\"? (Diebold-Mariano on weekly batches)"]
        for r in mine.itertuples():
            p = "" if math.isnan(r.p) else f", p = {r.p:.2f}"
            lines.append(f"  {r.domain:<8} {r.verdict}{p}")
    raised = alarms(scored, backtest_summary)
    lines += ["", f"Drift alarms (forecasts due in the last {RECENT_WEEKS} weeks): {len(raised) or 'none'}"]
    for r in raised.itertuples():
        lines.append(f"  {r.model} on {r.series_id}: {r.alarm} (recent {r.recent:.0%} against {r.expected:.0%}, {r.batches} batches)"
                     if r.alarm.startswith("range") or r.alarm == "edge lost"
                     else f"  {r.model} on {r.series_id}: {r.alarm} (p = {r.p:.3f}, {r.batches} batches)")
    return "\n".join(lines)


CALIBRATION_BINS = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]


def calibration(scored: pd.DataFrame | None) -> pd.DataFrame:
    """Live reliability of the "chance it ends higher" odds: per model and odds bucket, how often
    the series really did end higher."""
    if scored is None or scored.empty:
        return pd.DataFrame()
    rows = _prepare(scored).dropna(subset=["p_up"])
    rows["rose"] = (rows["actual"] > rows["last_value"]).astype(float)
    labels = [f"{lo:.0%}-{hi:.0%}" for lo, hi in zip(CALIBRATION_BINS[:-1], CALIBRATION_BINS[1:])]
    rows["bucket"] = pd.cut(rows["p_up"], CALIBRATION_BINS, labels=labels, include_lowest=True)
    return (rows.groupby(["model", "bucket"], observed=True)
            .agg(forecasts=("p_up", "size"), said=("p_up", "mean"), happened=("rose", "mean")).reset_index())


def weekly(scored: pd.DataFrame | None) -> pd.DataFrame:
    """Per model, area ("all" too) and weekly batch: its skill against "no change" (as in
    ``by_month``) and the share of reality inside its range. The finest-grained line the monitor draws."""
    if scored is None or scored.empty:
        return pd.DataFrame()
    rows = _prepare(scored)
    out = []
    groups = [*rows.groupby(["model", "domain"]), *(((m, "all"), p) for m, p in rows.groupby("model"))]
    for (model, domain), part in groups:
        for made_on, g in part.groupby("made_on", sort=True):
            out.append({"model": model, "domain": domain, "made_on": str(made_on), "forecasts": len(g),
                        "skill": _skill(g), "coverage80": float(g["inside"].mean())})
    return pd.DataFrame(out)


def payload(scored: pd.DataFrame | None, summary: pd.DataFrame | None = None, seals: pd.DataFrame | None = None) -> dict:
    """The monitor for the web app, as compact JSON-ready lists."""
    def num(v, digits=4):
        return None if v is None or (isinstance(v, float) and not math.isfinite(v)) else round(float(v), digits)
    out: dict = {"months": [], "weeks": [], "overall": [], "tests": [], "alarms": [], "calibration": [], "expected": [],
                 "seals": None, "first": None, "last": None, "forecasts": 0}
    if seals is not None and not seals.empty:
        out["seals"] = {"batches": int(len(seals)), "rows": int(seals["rows"].sum()), "ok": int((seals["status"] == "ok").sum()),
                        "first": str(seals["made_on"].min()), "last": str(seals["made_on"].max()),
                        "bad": [[r.made_on, r.model, r.status] for r in seals[seals["status"] != "ok"].itertuples()]}
    if summary is not None and not summary.empty:
        both = pd.concat([summary, summary.assign(domain="all")], ignore_index=True)
        exp = both.groupby(["model", "domain"]).agg(skill=("skill", "median"), coverage80=("coverage80", "mean")).reset_index()
        out["expected"] = [[r.model, r.domain, num(r.skill), num(r.coverage80)] for r in exp.itertuples()]
    if scored is None or scored.empty:
        return out
    rows = _prepare(scored)
    out |= {"first": str(rows["target_date"].min().date()), "last": str(rows["target_date"].max().date()), "forecasts": int(len(rows))}
    out["months"] = [[r.model, r.domain, r.month, r.forecasts, num(r.skill), num(r.coverage80), num(r.direction), num(r.brier),
                      num(r.cum_skill), num(r.cum_coverage80), num(r.cum_direction), num(r.cum_brier)] for r in by_month(scored).itertuples()]
    out["weeks"] = [[r.model, r.domain, r.made_on, r.forecasts, num(r.skill), num(r.coverage80)] for r in weekly(scored).itertuples()]
    out["overall"] = [[r.model, r.domain, r.forecasts, r.batches, r.series, num(r.skill), num(r.coverage80), num(r.direction), num(r.brier)]
                      for r in overall(scored).itertuples()]
    out["tests"] = [[r.model, r.domain, r.batches, num(r.loss_diff), num(r.dm, 3), num(r.p, 4), r.verdict] for r in vs_naive(scored).itertuples()]
    out["alarms"] = [[r.model, r.series_id, r.domain, r.alarm, r.batches, num(r.recent), num(r.expected), num(r.p)]
                     for r in alarms(scored, summary).itertuples()]
    out["calibration"] = [[r.model, str(r.bucket), int(r.forecasts), num(r.said), num(r.happened)] for r in calibration(scored).itertuples()]
    return out
