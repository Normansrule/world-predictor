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

from . import __version__, catalog
from .backtest import calibration, domain_table, summarize
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
) -> dict:
    """Everything the app needs, as plain JSON-ready values."""
    summary = summarize(results) if results is not None and not results.empty else None
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
    }
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
            })
    if scored is not None and not scored.empty:
        record = track_record(scored, model)
        payload["vault"] = [
            {"date": _date(r.target_date), "opened": int(r.opened), "inside80": _num(r.inside80, 4),
             "brier": _num(r.brier, 4), "skill": _num(r.skill, 4)}
            for r in record.itertuples()
        ]
    return payload


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
    from .backtest import backtest_series, skill_by_step
    from .ledger import predict, score
    from .models import BASELINES, load_model

    rng = np.random.default_rng(seed)
    specs = [catalog.by_id(i) for i in ("sp500", "gold", "silver", "bitcoin", "aapl", "news_composite",
                                         "news_war", "wiki_ai", "wiki_llm")]
    data = {}
    for k, spec in enumerate(specs):
        n = 700
        index = pd.date_range(end=pd.Timestamp(date.today() - timedelta(days=1)), periods=n, freq=spec.freq)
        t = np.arange(n)
        level = 100 * (1 + 0.15 * k)
        walk = np.cumsum(rng.normal(0.02 * (k % 3), 1.0, n))
        season = 3 * np.sin(2 * np.pi * t / (7 if spec.domain != "markets" else 63))
        data[spec.id] = pd.Series(level + walk + season, index=index, name=spec.id)
    models = [load_model(name) for name in ("drift", *BASELINES)]
    models = list({m.name: m for m in models}.values())
    step_rows, path_rows, frames = [], [], []
    for spec in specs:
        frames.append(backtest_series(spec, data[spec.id], models, windows=8, step_rows=step_rows,
                                      path_rows=path_rows, paths_for="drift"))
    results = pd.concat(frames, ignore_index=True)
    by_step = skill_by_step(pd.DataFrame(step_rows))
    drift = load_model("drift")
    sealed = []
    for cut in range(420, 690, 10):  # predictions "sealed" in the past, opened since
        sealed.append(predict(specs, {s: v.iloc[:cut] for s, v in data.items()}, drift).assign(made_on=f"demo-{cut}"))
    scored = score(pd.concat(sealed, ignore_index=True), data)
    ledger = predict(specs, data, drift)
    return build_payload("drift", results, by_step, pd.DataFrame(path_rows), ledger, scored, data, demo=True)
