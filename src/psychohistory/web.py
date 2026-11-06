"""The World Predictor web app: one static app in ``site/``, two ways to run it.

* **Web** - GitHub Pages serves ``site/`` with the newest ``data.js`` (no server, no Python).
* **Download** - ``psychohistory app`` runs the full pipeline locally, writes the same ``data.js``
  from your own results and serves the identical app on http://localhost.

Everything the app shows comes from one file, ``app/data/data.js``, which sets
``window.WP_DATA``. Loading data as a script rather than with ``fetch`` keeps the app working
when opened straight from disk (``file://``), and keeps the browser to two small requests.
Charts are drawn as plain SVG by ``site/app/js/app.js``: no chart library to download.
"""

from __future__ import annotations

import json
import math
import shutil
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from . import __version__, brief, catalog, events, frames, monitor, radiant, seldon, volatility, yearbook
from .backtest import MAX_CONTEXT, calibration, domain_table, head_to_head, summarize
from .ledger import latest as ledger_latest
from .simulate import CROWD_SIZES, crowd_predictability, simulate_crowd
from .story import OUTLOOK_SERIES, SHORT_TITLES, headlines, pick_headline_series, scorecard, track_record

SITE_SRC = Path(__file__).resolve().parents[2] / "site"
REPO_URL = "https://github.com/Normansrule/world-predictor"
HISTORY_POINTS = 120  # history shown behind each forecast; raw data stays out of the repo


def _num(x, digits: int = 6):
    if x is None:
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(x) or math.isinf(x) else round(x, digits)


def _date(x) -> str:
    return pd.Timestamp(x).date().isoformat()


def _history(series: pd.Series, points: int = HISTORY_POINTS) -> list:
    tail = series.dropna().iloc[-points:]
    return [[_date(i), _num(v)] for i, v in tail.items()]


def crowd_payload(seed: int = 0) -> dict:
    tide, people = simulate_crowd(seed=seed)
    table = crowd_predictability(tide, people).set_index("crowd_size")["predictable_share"]
    return {
        "tide": [_num(v, 3) for v in tide],
        "people": [[_num(v, 3) for v in people[:, j]] for j in range(12)],
        "sizes": [int(n) for n in CROWD_SIZES],
        "averages": {str(n): [_num(v, 3) for v in people[:, :n].mean(axis=1)] for n in CROWD_SIZES},
        "share": {str(n): _num(table[n], 4) for n in CROWD_SIZES},
    }


def _with_radiant(paths: pd.DataFrame | None, data: dict[str, pd.Series], model: str, domains: dict[str, str]) -> pd.DataFrame | None:
    """The backtest paths with Radiant's, replayed from the recorded ones when the run predates it."""
    if paths is None or paths.empty or radiant.NAME in set(paths["model"]):
        return paths
    extra = radiant.replay(paths, data, model, {k: v for k, v in radiant.domains_of(catalog.CATALOG).items() if k in data})
    return paths if extra.empty else pd.concat([paths, extra], ignore_index=True)


RADIANT_EXPERTS = {"model": "TimesFM", "laws": "Crowd laws", "core": "Behavioural core", "naive": "No change", "rival": "Chronos-Bolt"}
RADIANT_AREAS = (("markets", "Markets"), ("news", "World news"), ("politics", "Politics"), ("tech", "Technology"),
                 ("weather", "Weather and Earth"), (radiant.YEARLY, "Yearly adoption"))


def radiant_vote_payload(paths: pd.DataFrame | None, data: dict[str, pd.Series], model: str, points: int = 60) -> dict | None:
    """How Radiant splits its vote in each area, and how that split moved: its weights after each
    finished backtest window (at most ``points`` of them per area), and the weights in use now, which
    are the ones this week's sealed Radiant forecasts were mixed with."""
    windows = radiant.windows_from_paths(paths, data, model, radiant.domains_of(catalog.CATALOG))
    if not windows:
        return None
    areas = []
    for key, title in RADIANT_AREAS:
        mine = [w for w in windows if w.domain == key]
        if not mine:
            continue
        ends = sorted({w.end for w in mine})
        pick = [ends[round(i)] for i in np.linspace(0, len(ends) - 1, min(points, len(ends)))]
        rival = any("rival" in w.paths for w in mine)
        ran = set(radiant.EXPERTS) if rival else set(radiant.EXPERTS) - {"rival"}  # as the mix uses them: absent experts drop out

        def split(at=None):
            return [_num(v, 3) for v in radiant.present(radiant.weights(windows, key, at, rival), ran)]
        areas.append({"key": key, "title": title, "windows": len(mine), "rival": rival,
                      "start": [_num(v, 3) for v in radiant.present(radiant.prior(rival), ran)],
                      "points": [[d.date().isoformat(), split(d)] for d in pick], "now": split()})
    return {"experts": [RADIANT_EXPERTS[e] for e in radiant.EXPERTS], "keys": list(radiant.EXPERTS), "eta": radiant.ETA, "areas": areas}


def build_payload(
    model: str,
    results: pd.DataFrame | None,
    by_step: pd.DataFrame | None,
    paths: pd.DataFrame | None,
    ledger: pd.DataFrame | None,
    scored: pd.DataFrame | None,
    data: dict[str, pd.Series],
    demo: bool = False,
    run_status: dict | None = None,
    seals: pd.DataFrame | None = None,
    vol: dict | None = None,
    wire: dict | None = None,
    events: dict | None = None,
) -> dict:
    """Everything the app needs, as plain JSON-ready values."""
    summary = summarize(results) if results is not None and not results.empty else None
    domains = {s.id: s.domain for s in catalog.CATALOG}
    windows = seldon.windows_from_paths(paths, data, model, domains)  # what the full Seldon learns from
    payload: dict = {
        "meta": {
            "model": model, "generated": date.today().isoformat(), "version": __version__,
            "demo": demo, "repo": REPO_URL,
        },
        "headlines": headlines(summary, model, results, by_step) if summary is not None else [],
        "scorecard": scorecard(summary, model, by_step, results),
        "domains": [], "horizon": [], "calibration": [], "series": [],
        "outlook": [], "replay": None, "vault": [], "crowd": crowd_payload(),
        "run": run_status or {}, "evidence": evidence(results, model),
        "lab": lab_payload(paths, model, data, windows), "duel": duel_payload(results, model),
        "duel_laws": duel_payload(results, model, seldon.LAWS_NAME),
        "duel_radiant": duel_payload(results, model, radiant.NAME),
        "leaderboard": leaderboard_payload(summary, model),
        "track": track_payload(paths, model), "opened": opened_payload(scored, model),
        "track_radiant": track_payload(paths, radiant.NAME, bands=False),
        "frames": frames.payload(paths, ledger, scored, data, model),
        "brief": brief.build(ledger, scored, model, _title),
        "markets": markets_payload(summary),
        "monitor": monitor.payload(scored, summary, seals),
        "volatility": volatility_payload(**(vol or {}), data=data),
        "wire": wire_payload(wire),
        "events": events_payload(**(events or {})),
        "radiant_vote": radiant_vote_payload(paths, data, model) if not demo else None,
        "year": yearbook.build(data, _with_radiant(paths, data, model, domains), ledger, model) if not demo else None,
    }
    if not payload["duel"] and payload["lab"]:
        payload["duel"] = payload["lab"].pop("duel", [])  # a run from before Seldon joined the backtest
    elif payload["lab"]:
        payload["lab"].pop("duel", None)
    if summary is not None:
        table = domain_table(summary)
        payload["domains"] = [
            {"domain": r.domain, "model": r.model, "skill": _num(r.median_skill), "direction": _num(r.direction),
             "coverage80": _num(r.coverage80), "brier": _num(r.brier), "series": int(r.series)}
            for r in table.itertuples()
        ]
        mine = summary[summary["model"] == model]
        payload["series"] = [
            {"id": r.series_id, "domain": r.domain, "scale": r.scale, "title": _title(r.series_id),
             "skill": _num(r.skill), "direction": _num(r.direction), "coverage80": _num(r.coverage80),
             "mase": _num(r.mase), "brier": _num(r.brier)}
            for r in mine.sort_values(["domain", "series_id"]).itertuples()
        ]
        cal = calibration(results, model)
        payload["calibration"] = [
            {"domain": r.domain, "said": _num(r.said), "happened": _num(r.happened), "forecasts": int(r.forecasts)}
            for r in cal.itertuples()
        ] if not cal.empty else []
    if by_step is not None and not by_step.empty:
        part = by_step[by_step["model"] == model].sort_values(["domain", "step"])
        payload["horizon"] = [{"domain": r.domain, "step": int(r.step), "skill": _num(r.skill)} for r in part.itertuples()]
    if paths is not None and not paths.empty:
        headline = pick_headline_series(paths)
        if headline in data:
            rows = paths[paths["series_id"] == headline]
            first = pd.Timestamp(rows["origin"].min())
            end = pd.Timestamp(rows["date"].max())
            window = data[headline][(data[headline].index >= first - (end - first) * 0.6) & (data[headline].index <= end)]
            payload["replay"] = {
                "id": headline, "title": _title(headline),
                "history": [[_date(i), _num(v)] for i, v in window.items()],
                "forecasts": [
                    {"origin": _date(origin), "path": [
                        [_date(r.date), _num(r.q10), _num(r.q50), _num(r.q90), _num(r.actual)]
                        for r in group.sort_values("step").itertuples()
                    ]}
                    for origin, group in rows.groupby("origin")
                ],
            }
    if ledger is not None and not ledger.empty:
        rows = ledger[ledger["model"] == model]
        rows = rows[rows["made_on"] == rows.groupby("series_id")["made_on"].transform("max")]
        newest = ledger_latest(rows)
        order = {sid: i for i, sid in enumerate(OUTLOOK_SERIES)}  # headline series first
        newest = newest.assign(_o=newest["series_id"].map(lambda sid: order.get(sid, len(order)))).sort_values(["_o", "domain", "series_id"])
        for item in newest.itertuples():
            if item.series_id not in data:
                continue
            fan = rows[rows["series_id"] == item.series_id].sort_values("step")
            payload["outlook"].append({
                "id": item.series_id, "domain": item.domain, "title": _title(item.series_id),
                "description": catalog.by_id(item.series_id).description if _known(item.series_id) else item.series_id,
                "made_on": str(fan["made_on"].iloc[0]), "target_date": item.target_date,
                "p_up": _num(item.p_up, 4), "change": _num(item.median_change, 5),
                "low": _num(item.low_change, 5), "high": _num(item.high_change, 5),
                "history": _history(data[item.series_id], max(3 * len(fan), 60)),
                "fan": [[r.target_date, _num(r.q10), _num(r.q50), _num(r.q90)] for r in fan.itertuples()],
                "seldon": _seldon_outlook(ledger, data[item.series_id], item.series_id, item.domain, fan, windows, model),
                "radiant": _sealed_fan(ledger, radiant.NAME, item.series_id, fan["made_on"].iloc[0]),
            })
    if scored is not None and not scored.empty:
        record = track_record(scored, model)
        payload["vault"] = [
            {"date": _date(r.target_date), "opened": int(r.opened), "inside80": _num(r.inside80, 4),
             "brier": _num(r.brier, 4), "skill": _num(r.skill, 4)}
            for r in record.itertuples()
        ]
    return payload


def _sealed_fan(ledger: pd.DataFrame, name: str, series_id: str, made_on) -> list | None:
    """Model ``name``'s forecast for one series sealed in the same weekly batch, as [date, q10, q50,
    q90] rows, or None when that batch has none (Radiant is sealed only by runs since it joined)."""
    rows = ledger[(ledger["model"] == name) & (ledger["series_id"] == series_id) & (ledger["made_on"] == made_on)]
    if rows.empty:
        return None
    return [[r.target_date, _num(r.q10), _num(r.q50), _num(r.q90)] for r in rows.sort_values("step").itertuples()]


def _seldon_at(series: pd.Series, at, horizon: int) -> tuple:
    """Seldon's forecast from the data up to and including ``at``, exactly as the backtest and
    ``predict`` make it (the same context length), and the council behind it."""
    context = series[series.index <= pd.Timestamp(at)].to_numpy(dtype=float)[-MAX_CONTEXT:]
    return seldon.predict(context, horizon)


def _seldon_outlook(ledger: pd.DataFrame, series: pd.Series, series_id: str, domain: str, fan: pd.DataFrame,
                    windows: list, model: str) -> dict:
    """The full Seldon's newest forecast for one outlook series. Runs since Seldon joined the ledger
    carry their own sealed ``seldon`` rows; for older runs it is built here from the sealed TimesFM
    range and the crowd laws run on the same data, and marked ``computed`` (made later, so not
    sealed in advance)."""
    made_on, last_date = fan["made_on"].iloc[0], fan["last_date"].iloc[0]
    laws, council = _seldon_at(series, last_date, len(fan))
    share = seldon.share_for(windows, domain, last_date)
    sealed = ledger[(ledger["model"] == seldon.NAME) & (ledger["series_id"] == series_id) & (ledger["made_on"] == made_on)]
    if not sealed.empty:
        rows, source = sealed.sort_values("step"), "sealed"
        q10, q50, q90 = (rows[k].to_numpy(float) for k in ("q10", "q50", "q90"))
    else:
        rows, source = fan, "computed"
        q10, q50, q90 = seldon.blend_bands([fan[k].to_numpy(float) for k in ("q10", "q50", "q90")], laws, share)
    return {"source": source, "council": seldon.full_council(council, share, model),
            "fan": [[d, _num(a), _num(b), _num(e)] for d, a, b, e in zip(rows["target_date"], q10, q50, q90)]}


def markets_payload(summary: pd.DataFrame | None) -> dict[str, dict]:
    """For the app's Markets desk: each market's ticker and trading calendar, and every model's
    record on it ([model, skill, range skill, share inside the 80% range, right direction, Brier],
    best skill first), so an analyst sees whom to trust on that asset before reading a forecast."""
    out = {}
    for spec in catalog.CATALOG:
        if spec.domain != "markets":
            continue
        item = {"ticker": spec.params.get("ticker", spec.id), "freq": spec.freq, "scale": spec.scale, "models": []}
        if summary is not None:
            rows = summary[summary["series_id"] == spec.id].sort_values("skill", ascending=False)
            item["models"] = [[r.model, _num(r.skill, 4), _num(r.prob_skill, 4), _num(r.coverage80, 4),
                               _num(r.direction, 4), _num(r.brier, 4)] for r in rows.itertuples()]
        out[spec.id] = item
    return out


def wire_payload(wire: dict | None, per_topic: int = 6) -> dict:
    """The world wire for the app: when it was fetched and each topic's newest headlines
    ([title, link, site, country, seen]), marked stale when they are from an earlier week."""
    if not wire:
        return {"fetched": None, "topics": {}}
    topics = {sid: {"stale": bool(t.get("stale")), "articles": [[a["title"][:180], a["url"], a.get("domain", ""), a.get("country", ""), a.get("seen", "")]
                                                               for a in t.get("articles", [])[:per_topic]]}
              for sid, t in (wire.get("topics") or {}).items()}
    return {"fetched": wire.get("fetched"), "topics": topics}


def volatility_payload(summary: pd.DataFrame | None = None, ledger: pd.DataFrame | None = None,
                       scored: pd.DataFrame | None = None, seals: pd.DataFrame | None = None,
                       data: dict[str, pd.Series] | None = None) -> dict:
    """For the Markets desk and the Monitor: the volatility backtest across markets and per market
    ([model, span, skill, windows, typical miss, p], plus how many markets each beat last month's
    volatility in), each market's latest sealed volatility forecasts and the sealed record so far.
    ``now`` is GARCH's, EWMA's and last month's forecast from the newest data ([model, span,
    annualised volatility]); the app adds what each model's range implies."""
    out: dict = {"backtest": [], "first": None, "last": None, "markets": {}, "live": [], "seals": None}
    for spec in catalog.CATALOG:
        series = (data or {}).get(spec.id)
        steps = volatility.horizons(spec.freq)
        r = volatility.log_returns(series.to_numpy(dtype=float)) if spec.domain == "markets" and series is not None and steps else None
        if r is None or len(r) < 60:
            continue
        fc = volatility.built_in(r, spec.freq, steps)
        out["markets"].setdefault(spec.id, {})["now"] = {
            "date": series.index[-1].date().isoformat(), "steps": list(steps),
            "rows": [[m, volatility.label(h, spec.freq), _num(volatility.annual(v, spec.freq), 4)] for m, by in fc.items() for h, v in by.items()]}
    if summary is not None and not summary.empty:
        part = summary[summary["series_id"] == "all"]
        out["backtest"] = [[r.model, r.span, _num(r.skill, 4), int(r.windows), int(r.beaten), int(r.markets),
                            _num(r.miss, 4), _num(r.p, 4)] for r in part.itertuples()]
        out["first"], out["last"] = str(summary["first"].min()), str(summary["last"].max())
        for series_id, g in summary[summary["series_id"] != "all"].groupby("series_id"):
            out["markets"].setdefault(series_id, {})["record"] = [
                [r.model, r.span, _num(r.skill, 4), int(r.windows), _num(r.miss, 4)] for r in g.itertuples()]
    if ledger is not None and not ledger.empty:
        freq = {s.id: s.freq for s in catalog.CATALOG}
        for series_id, g in ledger.groupby("series_id"):
            last = g[g["made_on"] == g["made_on"].max()]
            out["markets"].setdefault(series_id, {})["sealed"] = {
                "made_on": str(last["made_on"].iloc[0]), "last_date": str(last["last_date"].iloc[0]),
                "rows": [[r.model, volatility.label(int(r.horizon), freq.get(series_id, "B")), _num(r.vol, 4), str(r.target_date)]
                         for r in last.itertuples()]}
    live = volatility.live_record(scored)
    if not live.empty:
        out["live"] = [[r.model, r.span, int(r.windows), int(r.batches), _num(r.skill, 4), _num(r.miss, 4), r.verdict]
                       for r in live.itertuples()]
    if seals is not None and not seals.empty:
        out["seals"] = {"batches": int(len(seals)), "ok": int((seals["status"] == "ok").sum()),
                        "rows": int(seals["rows"].sum())}
    return out


def events_payload(summary: pd.DataFrame | None = None, now: pd.DataFrame | None = None,
                   scored: pd.DataFrame | None = None, seals: pd.DataFrame | None = None) -> dict:
    """For the World terminal and the Monitor: today's odds of a spike and a lull per news and tech
    series ([series, event, threshold, last value, target date, {model: odds}]), the backtest record
    ([scope, event, model, forecasts, happened, said, Brier, skill vs climatology, vs persistence,
    p]) and the sealed record so far."""
    out: dict = {"made_on": None, "sealed": False, "now": [], "backtest": [], "live": [], "seals": None}
    if now is not None and not now.empty:
        out["made_on"] = str(now["made_on"].iloc[0])
        out["sealed"] = seals is not None and not seals.empty and out["made_on"] in set(seals["made_on"].astype(str))
        for (series_id, event), g in now.groupby(["series_id", "event"], sort=True):
            first = g.iloc[0]
            out["now"].append([series_id, event, _sig(first["threshold"]), _sig(first["last_value"]), str(first["target_date"]),
                               {r.model: _num(r.p, 3) for r in g.itertuples()}])
    if summary is not None and not summary.empty:
        part = summary[~summary["scope"].isin(set(summary["scope"]) - {"all", *events.ATTENTION})]
        out["backtest"] = [[r.scope, r.event, r.model, int(r.forecasts), _num(r.happened, 3), _num(r.said, 3), _num(r.brier, 4),
                            _num(r.skill_clim, 4), _num(r.skill_pers, 4), _num(r.p, 4), int(r.origins)] for r in part.itertuples()]
        out["series"] = {sid: {r.event + "|" + r.model: [_num(r.skill_clim, 3), int(r.forecasts)] for r in g.itertuples()}
                         for sid, g in summary[~summary["scope"].isin(["all", *events.ATTENTION])].groupby("scope")}
    live = events.live_record(scored)
    if not live.empty:
        out["live"] = [[r.event, r.model, int(r.forecasts), int(r.origins), _num(r.skill_clim, 4), _num(r.skill_pers, 4), r.verdict]
                       for r in live.itertuples()]
    if seals is not None and not seals.empty:
        out["seals"] = {"batches": int(len(seals)), "ok": int((seals["status"] == "ok").sum()), "rows": int(seals["rows"].sum())}
    return out


def duel_payload(results: pd.DataFrame | None, model: str, challenger: str = seldon.NAME) -> list[dict]:
    """The model under test against Seldon (or its crowd laws alone) per domain, see
    ``backtest.head_to_head``."""
    if results is None or results.empty:
        return []
    table = head_to_head(results, model, challenger)
    return [{"domain": r.domain, "series": int(r.series), "wins": int(r.wins), "losses": int(r.losses),
             "error_change": _num(r.error_change, 4), "skill": [_num(r.model_skill, 4), _num(r.challenger_skill, 4)],
             "prob_skill": [_num(r.model_prob_skill, 4), _num(r.challenger_prob_skill, 4)],
             "coverage80": [_num(r.model_coverage80, 4), _num(r.challenger_coverage80, 4)], "winner": r.winner}
            for r in table.itertuples()]


def leaderboard_payload(summary: pd.DataFrame | None, model: str) -> dict | None:
    """Every model of the newest backtest on one board: average sMAPE per series, overall and per
    area (yearly adoption series apart, as Radiant learns them), median skill against "no change",
    how often reality landed in its 80% range, and on how many series it beat ``model``. A model
    that forecast fewer than half the series (the Bass curve, which only fits adoption) is left out."""
    if summary is None or summary.empty or model not in set(summary["model"]):
        return None
    yearly = {s.id for s in catalog.CATALOG if s.source == "owid"}
    s = summary.assign(area=[radiant.YEARLY if i in yearly else d for i, d in zip(summary["series_id"], summary["domain"])])
    base = s[s["model"] == model].set_index("series_id")["smape"]
    n = s["series_id"].nunique()
    rows = []
    for m, g in s.groupby("model"):
        if g["series_id"].nunique() < n / 2:
            continue
        mine = g.set_index("series_id")["smape"]
        common = mine.index.intersection(base.index)
        rows.append({
            "model": m, "series": int(len(g)), "smape": _num(g["smape"].mean(), 5),
            "areas": {a: _num(x["smape"].mean(), 5) for a, x in g.groupby("area")},
            "skill": _num(g["skill"].median(), 4), "coverage80": _num(g["coverage80"].mean(), 4),
            "beats": None if m == model else int((mine[common] < base[common]).sum()), "of": int(len(common)),
        })
    rows.sort(key=lambda r: (r["smape"] is None, r["smape"]))
    return {"model": model, "areas": [a for a, _ in RADIANT_AREAS if a in set(s["area"])], "rows": rows}


LAB_ROUNDS = 3  # past windows per series offered in the Lab


def _sig(x, digits: int = 4):
    """A number rounded to ``digits`` significant figures, to keep the data file small."""
    x = _num(x, 12)
    if x is None or x == 0:
        return x
    return float(f"{x:.{digits}g}")


def lab_payload(paths: pd.DataFrame | None, model: str, data: dict[str, pd.Series] | None = None,
                windows: list | None = None) -> dict | None:
    """The Lab: past forecast windows where a visitor can make a blind call, then compare it with
    the model under test and Seldon, our own forecaster (see ``seldon.py``).

    The windows come from the backtest paths and sit back to back, so the actual values of earlier
    windows are the history a visitor sees before each round. Seldon's band for each round is its
    backtest path for that window, or, for runs from before the full Seldon joined the backtest,
    rebuilt here exactly as the backtest would have: the crowd laws run on the data up to that
    window's origin, blended with the model's band at the share learned from the area's windows
    finished by then. ``board`` scores both on every window after the first."""
    if paths is None or paths.empty:
        return None
    rows = paths[paths["model"] == model]
    if rows.empty:
        return None
    data = data or {}
    mine = paths[paths["model"] == seldon.NAME]
    out, scores = [], []
    for series_id, part in rows.groupby("series_id"):
        groups = [g.sort_values("step") for _, g in part.groupby("origin", sort=True)]
        if len(groups) < 2:
            continue
        domain = catalog.by_id(series_id).domain if _known(series_id) else "other"
        rounds_from = max(1, len(groups) - LAB_ROUNDS)
        h = len(groups[-1])
        start = max(0, rounds_from - 1)  # history: one window before the first round
        history = [[_date(r.date), _sig(r.actual)] for g in groups[start:] for r in g.itertuples()]
        rounds = []
        for k in range(1, len(groups)):
            g, origin = groups[k], groups[k]["origin"].iloc[0]
            last = float(groups[k - 1]["actual"].iloc[-1])  # windows are back to back
            q10, q50, q90, a = (g[c].to_numpy(float) for c in ("q10", "q50", "q90", "actual"))
            council = None
            path = mine[(mine["series_id"] == series_id) & (mine["origin"] == origin)].sort_values("step")
            if series_id in data:
                laws, c = _seldon_at(data[series_id], origin, len(g))
                share = seldon.share_for(windows or [], domain, origin)
                council = seldon.full_council(c, share, model)
                lo, mid, hi = seldon.blend_bands((q10, q50, q90), laws, share)
            if len(path) == len(g):  # the backtest's own Seldon path, when this run has one
                lo, mid, hi = (path[c].to_numpy(float) for c in ("q10", "q50", "q90"))
            elif series_id not in data:
                continue
            for name, (l, m, u) in ((model, (q10, q50, q90)), (seldon.NAME, (lo, mid, hi))):
                scores.append({"series_id": series_id, "domain": domain, "model": name,
                               "mae": float(np.mean(np.abs(m - a))), "naive": float(np.mean(np.abs(last - a))),
                               "inside": float(np.mean((a >= l) & (a <= u))),
                               # "no change" makes no directional call, so it is not scored on direction
                               "direction": float(np.sign(m[-1] - last) == np.sign(a[-1] - last))
                               if np.sign(m[-1] - last) != 0 and np.sign(a[-1] - last) != 0 else np.nan})
            if k >= rounds_from:
                rounds.append({
                    "origin": str(origin), "at": sum(len(x) for x in groups[start:k]),
                    "model": [[_sig(x), _sig(y), _sig(z)] for x, y, z in zip(q10, q50, q90)],
                    "seldon": [[_sig(x), _sig(y), _sig(z)] for x, y, z in zip(lo, mid, hi)],
                    "council": council,
                })
        if rounds:
            out.append({"id": series_id, "domain": domain, "title": _title(series_id), "horizon": h,
                        "history": history, "rounds": rounds})
    board = []
    if scores:
        frame = pd.DataFrame(scores)
        per = frame.groupby(["domain", "model", "series_id"]).mean(numeric_only=True)
        per["skill"] = 1 - per["mae"] / per["naive"].replace(0, np.nan)
        table = per.groupby(["domain", "model"]).agg(skill=("skill", "median"), inside=("inside", "mean"),
                                                     direction=("direction", "mean"), series=("skill", "size"))
        board = [{"domain": d, "model": m, "skill": _num(r.skill, 4), "inside": _num(r.inside, 4),
                  "direction": _num(r.direction, 4), "series": int(r.series)} for (d, m), r in table.iterrows()]
    return {"model": model, "challenger": seldon.NAME, "series": out, "board": board, "duel": _lab_duel(scores, model)}


def _lab_duel(scores: list[dict], model: str) -> list[dict]:
    """The duel from the Lab's windows, in ``duel_payload``'s shape (the Lab keeps only the 10th,
    50th and 90th percentiles, so there is no range skill here)."""
    if not scores:
        return []
    per = pd.DataFrame(scores).groupby(["domain", "series_id", "model"]).mean(numeric_only=True)
    per["skill"] = 1 - per["mae"] / per["naive"].replace(0, np.nan)
    wide = per[["mae", "skill", "inside"]].unstack("model").dropna()
    if wide.empty or seldon.NAME not in wide["mae"] or model not in wide["mae"]:
        return []
    out = []
    for domain, part in [*wide.groupby(level="domain"), ("all", wide)]:
        wins = int((part[("mae", seldon.NAME)] < part[("mae", model)]).sum())
        losses = int((part[("mae", seldon.NAME)] > part[("mae", model)]).sum())
        out.append({"domain": domain, "series": len(part), "wins": wins, "losses": losses,
                    "error_change": _num(float((part[("mae", seldon.NAME)] / part[("mae", model)]).mean() - 1), 4),
                    "skill": [_num(part[("skill", model)].median(), 4), _num(part[("skill", seldon.NAME)].median(), 4)],
                    "prob_skill": [None, None],
                    "coverage80": [_num(part[("inside", model)].mean(), 4), _num(part[("inside", seldon.NAME)].mean(), 4)],
                    "winner": seldon.NAME if wins > losses else model if losses > wins else "tie", "source": "lab"})
    return out


def track_payload(paths: pd.DataFrame | None, model: str, bands: bool = True) -> dict[str, dict]:
    """Every backtest window of every series, for its series page: what the model said each time
    and what really happened. The windows sit back to back, so the actual values are stored once
    (``actual``, on the dates ``start`` plus ``days`` calendar days) and each window keeps its origin,
    the index of its first step and its 10th, 50th and 90th percentiles."""
    if paths is None or paths.empty:
        return {}
    rows = paths[paths["model"] == model]
    out = {}
    for series_id, part in rows.groupby("series_id"):
        days = part.drop_duplicates("date").sort_values("date")
        stamps = pd.to_datetime(days["date"])
        dates = [_date(d) for d in stamps]
        at = {d: i for i, d in enumerate(dates)}
        windows = []
        for origin, g in part.groupby("origin", sort=True):
            g = g.sort_values("step")
            mid = [_sig(v) for v in g["q50"]]
            windows.append([str(origin), at[_date(g["date"].iloc[0])],
                            [_sig(v) for v in g["q10"]] if bands else None, mid, [_sig(v) for v in g["q90"]] if bands else None])
        out[series_id] = {"start": dates[0], "days": [int((d - stamps.iloc[0]).days) for d in stamps],
                          "actual": [_sig(v) for v in days["actual"]], "windows": windows}
    return out


OPENED_PER_SERIES = 60  # newest opened predictions kept per series


def _sealed_after(target, made_on) -> int:
    """1 when a forecast was sealed on or after its own date (its value not yet published), else 0.
    Labels that are not dates (the demo's runs) count as sealed in advance."""
    made = pd.to_datetime(made_on, errors="coerce")
    return int(not pd.isna(made) and pd.Timestamp(target) <= made)


def opened_payload(scored: pd.DataFrame | None, model: str) -> list[list]:
    """Sealed predictions whose date has arrived, newest first: [series, sealed on, date, steps
    ahead, 10th, middle, 90th, actual, chance higher it gave, whether it was higher, whether the
    date had already passed when it was sealed]. These are forecasts the model made without the
    answer and scored after the fact; none of them is a backtest. The last flag marks a value that
    was not published yet when the forecast was sealed (Wikipedia and GDELT run a day or two
    behind), so the app can say so rather than call it a forecast of the future."""
    if scored is None or scored.empty:
        return []
    rows = scored[scored["model"].isin([model, seldon.NAME])].copy()
    rows = rows.sort_values(["target_date", "made_on", "series_id"], ascending=[False, False, True])
    rows = rows.groupby(["series_id", "model"], sort=False).head(OPENED_PER_SERIES)
    return [[r.series_id, r.model, str(r.made_on), _date(r.target_date), int(r.step), _sig(r.q10), _sig(r.q50), _sig(r.q90),
             _sig(r.actual), _num(r.p_up, 3), None if pd.isna(r.actual) or pd.isna(r.last_value) else int(r.actual > r.last_value),
             _sealed_after(r.target_date, r.made_on)]
            for r in rows.itertuples()]


def evidence(results: pd.DataFrame | None, model: str) -> dict[str, list]:
    """Each series' backtest windows for the model under test: [origin, MASE, share inside the
    80% range, chance of rising it gave, whether it rose]. The record behind every skill number."""
    if results is None or results.empty:
        return {}
    rows = results[results["model"] == model].sort_values(["series_id", "origin"])
    return {
        sid: [[str(r.origin), _num(r.mase, 4), _num(r.coverage80, 4), _num(r.p_up, 4), _num(r.went_up, 1)]
              for r in group.itertuples()]
        for sid, group in rows.groupby("series_id")
    }


def _known(series_id: str) -> bool:
    try:
        catalog.by_id(series_id)
        return True
    except KeyError:
        return False


def _title(series_id: str) -> str:
    if series_id in SHORT_TITLES:
        return SHORT_TITLES[series_id]
    return catalog.by_id(series_id).description if _known(series_id) else series_id


def write_data_js(payload: dict, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, separators=(",", ":"), allow_nan=False)
    path.write_text(f"window.WP_DATA={body};\n")
    return path


def build_site(out: Path, data_js: Path | None = None, payload: dict | None = None) -> Path:
    """Copy the static app from ``site/`` to ``out`` and put the data next to it."""
    if not SITE_SRC.exists():
        raise FileNotFoundError(f"App source not found at {SITE_SRC}; run from a checkout of the repository.")
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(SITE_SRC, out)
    target = out / "app" / "data" / "data.js"
    if payload is not None:
        write_data_js(payload, target)
    elif data_js is not None and data_js.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(data_js, target)
    else:
        write_data_js(demo_payload(), target)
    return out


def demo_payload(seed: int = 0) -> dict:
    """Illustrative data for the app before the first real run: synthetic series and simple
    baseline models, clearly marked as a demo in the app. No downloads needed."""
    from .backtest import add_seldon, backtest_series, skill_by_step
    from .ledger import predict, score
    from .models import BASELINES, load_model

    rng = np.random.default_rng(seed)
    specs = [catalog.by_id(i) for i in ("sp500", "gold", "silver", "bitcoin", "aapl", "news_composite",
                                         "news_war", "wiki_ai", "wiki_llm", "politics_composite",
                                         "weather_world_air", "weather_london")]
    data = {}
    for k, spec in enumerate(specs):
        n = 700
        index = pd.date_range(end=pd.Timestamp(date.today() - timedelta(days=1)), periods=n, freq=spec.freq)
        t = np.arange(n)
        level = 100 * (1 + 0.15 * k)
        walk = np.cumsum(rng.normal(0.02 * (k % 3), 1.0, n))
        season = 3 * np.sin(2 * np.pi * t / (7 if spec.domain != "markets" else 63))
        data[spec.id] = pd.Series(level + walk + season, index=index, name=spec.id)
    models = [load_model(name) for name in ("drift", "seldon-laws", *BASELINES)]
    models = list({m.name: m for m in models}.values())
    step_rows, path_rows, frames, kept = [], [], [], []
    for spec in specs:
        frames.append(backtest_series(spec, data[spec.id], models, windows=8, step_rows=step_rows,
                                      path_rows=path_rows, paths_for=("drift",), keep=kept))
    frames.append(add_seldon(kept, "drift", step_rows, path_rows, paths_for=("seldon",)))
    results = pd.concat(frames, ignore_index=True)
    by_step = skill_by_step(pd.DataFrame(step_rows))
    drift = load_model("drift")
    windows = seldon.windows_from_paths(pd.DataFrame(path_rows), data, "drift", {s.id: s.domain for s in specs})

    def full(spec, base, context):
        laws, _ = seldon.predict(context, len(base.point))
        return seldon.blend(base, laws, seldon.share_for(windows, spec.domain))
    sealed = []
    for cut in range(420, 690, 10):  # predictions "sealed" in the past, opened since
        past = {s: v.iloc[:cut] for s, v in data.items()}
        sealed.append(predict(specs, past, drift, extras={"seldon": full}).assign(made_on=f"demo-{cut}"))
    scored = score(pd.concat(sealed, ignore_index=True), data)
    ledger = predict(specs, data, drift, extras={"seldon": full})
    return build_payload("drift", results, by_step, pd.DataFrame(path_rows), ledger, scored, data, demo=True)
