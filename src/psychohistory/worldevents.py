"""The world event predictor: what is likely to happen next in the news, with probabilities.

For every topic the app follows in world news, politics and technology (elections, war, inflation,
protests, sanctions, tariffs, ceasefires, coups, AI, quantum computing and the rest), three questions
in plain words, each a week and four weeks ahead:

* **Flares up**: will coverage reach a level it reaches only one day in ten (the 90th percentile of
  the last two years)?
* **Fades**: will it fall to a low it falls to only one day in ten?
* **Grows**: will it be higher than today?

The answers come from the sealed forecasts, not from reading the headlines: the forecast's 10/50/90%
quantiles read as a split normal (``events.probability``), with the threshold fixed from the history
up to the forecast's last day. The 4-week odds are sealed in the event ledger; the 1-week odds are
read from the same sealed forecasts (main ledger, step 7), so neither can be edited after the fact.
The headlines the World wire fetched for each topic sit beside the odds, as context: they say *why*
coverage is where it is, while the odds say where it is likely to go.

Which forecaster speaks for each event is chosen by the backtest: the model with the lowest Brier
score on that event over every past window (Seldon on the 7 November 2026 backtest, by a hair).
Every topic carries that model's record a week and four weeks ahead, as Brier skill against
"it happens one day in ten".
"""

from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd

from . import catalog, events
from .frames import p_up3

WEEK = 7
TREND_DAYS = 90
HEADLINES = 4
CANDIDATES = ("seldon", "timesfm-2.5", "radiant", "chronos-bolt")  # who may speak for an event


def lead_models(summary: pd.DataFrame | None, present: set[str], model: str) -> dict[str, str]:
    """Per event, the forecaster with the lowest backtest Brier over all topics (among those with odds now)."""
    out = {}
    for event in events.EVENTS:
        best = None
        if summary is not None and not summary.empty:
            part = summary[(summary["scope"] == "all") & (summary["event"] == event) & summary["model"].isin(present)
                           & summary["model"].isin(CANDIDATES + (model,))]
            if not part.empty:
                best = str(part.sort_values("brier").iloc[0]["model"])
        out[event] = best or (model if model in present else sorted(present)[0])
    return out


def _r(x, digits: int = 3):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return round(v, digits) if np.isfinite(v) else None


def _headlines(wire: dict | None, series_id: str) -> list[dict]:
    topic = ((wire or {}).get("topics") or {}).get(series_id) or {}
    return [{k: a.get(k) for k in ("title", "url", "domain", "seen")} for a in (topic.get("articles") or [])[:HEADLINES]
            if str(a.get("url", "")).startswith(("http://", "https://")) and a.get("title")]


def build(ledger: pd.DataFrame | None, now: pd.DataFrame | None, summary: pd.DataFrame | None,
          by_step: pd.DataFrame | None, wire: dict | None, data: dict[str, pd.Series], model: str,
          title: Callable[[str], str] = str) -> dict | None:
    if now is None or now.empty:
        return None
    present = set(now["model"]) - set(events.BASELINES)
    if not present:
        return None
    lead = lead_models(summary, present, model)
    latest = None
    if ledger is not None and not ledger.empty:
        latest = ledger[ledger["made_on"].astype(str) == str(ledger["made_on"].astype(str).max())]
    record = {}
    for event, m in lead.items():
        r = {}
        if summary is not None and not summary.empty:
            s = summary[(summary["scope"] == "all") & (summary["event"] == event) & (summary["model"] == m)]
            if not s.empty:
                r["month"] = [_r(s.iloc[0]["skill_clim"]), int(s.iloc[0]["forecasts"])]
        if by_step is not None and not by_step.empty:
            s = by_step[(by_step["step"] == WEEK) & (by_step["event"] == event) & (by_step["model"] == m)]
            if not s.empty:
                r["week"] = [_r(s.iloc[0]["skill_clim"]), int(s.iloc[0]["forecasts"])]
        record[event] = r
    items = []
    for sid, g in now.groupby("series_id", sort=True):
        try:
            spec = catalog.by_id(sid)
        except KeyError:
            continue
        first = g.iloc[0]
        last = float(first["last_value"])
        item = {"id": sid, "title": title(sid), "area": spec.domain, "last": _r(last, 4), "last_date": str(first["last_date"]),
                "month_target": str(first["target_date"]), "cut": {}, "month": {}, "week": {}, "base": {}, "models": {"month": {}, "week": {}}}
        for event, eg in g.groupby("event"):
            item["cut"][event] = _r(eg["threshold"].iloc[0], 4)
            odds = {r.model: _r(r.p) for r in eg.itertuples()}
            item["models"]["month"][event] = {k: v for k, v in odds.items() if k not in events.BASELINES}
            item["base"][event] = {k: odds.get(k) for k in events.BASELINES}
            item["month"][event] = odds.get(lead[event])
        if latest is not None:
            mine = latest[latest["series_id"] == sid]
            wk = mine[mine["step"] == WEEK]
            if not wk.empty:
                item["week_target"] = str(wk["target_date"].iloc[0])
                for event, (_, above) in events.EVENTS.items():
                    cut = item["cut"].get(event)
                    if cut is None:
                        continue
                    odds = {r.model: _r(events.probability(r.q10, r.q50, r.q90, cut, above)) for r in wk.itertuples()}
                    item["models"]["week"][event] = odds
                    item["week"][event] = odds.get(lead[event])
            for frame, part in (("week", wk), ("month", mine[mine["step"] == mine["step"].max()] if not mine.empty else mine)):
                speaker = "radiant" if (part["model"] == "radiant").any() else model
                row = part[part["model"] == speaker]
                if not row.empty:
                    r = row.iloc[0]
                    item[frame]["higher"] = _r(p_up3(r.q10, r.q50, r.q90, float(r.last_value)))
                    item[frame]["mid"] = _r((r.q50 - r.last_value) / abs(r.last_value)) if r.last_value else None
        s = data.get(sid)
        if s is not None and len(s):
            tail = s.dropna().iloc[-TREND_DAYS:]
            item["trend"] = [[d.date().isoformat(), _r(v, 4)] for d, v in tail.items()]
            if len(tail) >= 35:
                item["momentum"] = _r(tail.iloc[-7:].mean() / max(tail.iloc[-35:-7].mean(), 1e-12) - 1)
        item["news"] = _headlines(wire, sid)
        items.append(item)
    return {"made_on": str(now["made_on"].iloc[0]), "lead": lead, "record": record, "items": items,
            "wire": (wire or {}).get("fetched")}
