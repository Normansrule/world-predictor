"""Rebuild the web app's data from a recorded run, without downloading anything.

The raw data is not committed (Yahoo's terms), so ``psychohistory export`` needs a fresh fetch. But
a run's saved backtest windows sit back to back, so their actual values are a continuous stretch of
each series (about a year of daily data), and the app's data file carries the newest values behind
every sealed forecast. Together they rebuild each series well enough for everything the app shows.

A run recorded before the full Seldon (its ``seldon`` rows were the crowd laws alone) is brought up
to date first, exactly as ``psychohistory report`` does it: those rows become ``seldon-laws`` and
the full Seldon is replayed from the recorded TimesFM and laws paths (``backtest.upgrade_run``).
This prints both duels.

A run scored before Seldon had its own council (its ``seldon`` rows blended TimesFM with the laws)
is brought up to date the same way: Seldon is replayed from the recorded paths of the laws, the
behavioural core and Chronos-Bolt plus "no change", learning its weights only from windows finished
before each origin (``backtest.replay_own_seldon``), and the run's CSV files are rewritten to match.

If the run has no volatility backtest yet, one is made from the same rebuilt series. With only a
year of data, its first origin comes after 120 trading days instead of a year (``REBUILT_TRAIN``);
the next ``psychohistory vol --backtest`` on the full history replaces it. The event-odds backtest is
made the same way (its thresholds need half a year of history, so only the later origins count);
``psychohistory events --backtest`` replaces it.

    python scripts/rebuild_app_data.py            # from the repository root
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from psychohistory import backtest, catalog, events, ledger, radiant, seldon, volatility, web, wire, yearbook

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
REBUILT_TRAIN = 120


def read_csv(path: Path) -> pd.DataFrame | None:
    return pd.read_csv(path) if path.exists() and path.stat().st_size > 1 else None


def rebuild_series(paths: pd.DataFrame, model: str, previous: dict) -> dict[str, pd.Series]:
    """Each series from the run's own files: backtest actuals, then the newest sealed history."""
    out = {}
    rows = paths[paths["model"] == model]
    for series_id, part in rows.groupby("series_id"):
        actual = part.drop_duplicates("date").set_index("date")["actual"]
        out[series_id] = actual
    for item in previous.get("outlook", []):
        history = pd.Series({d: v for d, v in item["history"] if v is not None})
        known = out.get(item["id"])
        out[item["id"]] = history if known is None else pd.concat([known, history[~history.index.isin(known.index)]])
    return {k: pd.Series(v.to_numpy(float), index=pd.to_datetime(v.index)).sort_index() for k, v in out.items()}


def print_duel(rows: list[dict], model: str, who: str) -> None:
    print(f"{'area':<8} {'series':>6} {who + ' won':>12} {model + ' won':>16}  error vs {model[:7]}   skill {model} / {who}")
    for r in rows:
        print(f"{r['domain']:<8} {r['series']:>6} {r['wins']:>12} {r['losses']:>16}  {r['error_change']:>+10.1%}   "
              f"{r['skill'][0]:+.1%} / {r['skill'][1]:+.1%}")


def reprice_seldon(paths: pd.DataFrame) -> None:
    """Seldon's rows in the saved event-odds and volatility backtests, read again off its replayed
    paths. Every other row stays as the run made it, and so do the thresholds and realized
    volatility Seldon is scored against (the run computed those on the full history)."""
    mine = paths[paths["model"] == seldon.NAME].set_index(["series_id", "origin", "step"])
    specs = {s.id: s for s in catalog.CATALOG}
    ev = read_csv(RESULTS / "event_backtest.csv")
    if ev is not None:
        rows = []
        for r in ev[ev["model"] == seldon.NAME].itertuples(index=False):
            key = (r.series_id, str(r.origin), specs[r.series_id].horizon) if r.series_id in specs else None
            if key is None or key not in mine.index:
                continue
            q = mine.loc[key]
            p = events.probability(q["q10"], q["q50"], q["q90"], r.threshold, events.EVENTS[r.event][1])
            if p is not None:
                rows.append(r._asdict() | {"p": p, "brier": (p - r.outcome) ** 2})
        ev = pd.concat([ev[ev["model"] != seldon.NAME], pd.DataFrame(rows)], ignore_index=True)
        ev.to_csv(RESULTS / "event_backtest.csv", index=False)
        events.summarize(ev).to_csv(RESULTS / "event_summary.csv", index=False)
    vol = read_csv(RESULTS / "vol_backtest.csv")
    if vol is not None:
        rows = []
        for r in vol[vol["model"] == seldon.NAME].itertuples(index=False):
            key = (r.series_id, str(r.origin), int(r.horizon))
            if r.series_id not in specs or key not in mine.index:
                continue
            q, freq = mine.loc[key], specs[r.series_id].freq
            variance = volatility.implied_variance(float(q["q10"]), float(q["q90"]), int(r.horizon))
            if variance:
                realized = r.realized ** 2 / volatility.periods_per_year(freq)
                rows.append(r._asdict() | {"vol": volatility.annual(variance, freq), "qlike": float(volatility.qlike(realized, variance))})
        vol = pd.concat([vol[vol["model"] != seldon.NAME], pd.DataFrame(rows)], ignore_index=True)
        vol.to_csv(RESULTS / "vol_backtest.csv", index=False)
        volatility.summarize(vol).to_csv(RESULTS / "vol_summary.csv", index=False)


def main() -> None:
    data_js = RESULTS / "web" / "data.js"
    text = data_js.read_text()
    previous = json.loads(text[text.index("{"): text.rindex("}") + 1])
    model = previous["meta"]["model"]
    results, paths = read_csv(RESULTS / "backtest_windows.csv"), read_csv(RESULTS / "backtest_paths.csv")
    results, paths, upgraded = backtest.upgrade_run(results, paths, model)
    series = rebuild_series(paths, model, previous)
    results, paths, own = backtest.replay_own_seldon(results, paths, series, model, radiant.domains_of(catalog.CATALOG))
    if own:  # keep the run's files in step with the app: Seldon's rows are its own council's from here on
        results.to_csv(RESULTS / "backtest_windows.csv", index=False)
        paths.to_csv(RESULTS / "backtest_paths.csv", index=False)
        backtest.summarize(results).to_csv(RESULTS / "backtest_summary.csv", index=False)
        reprice_seldon(paths)
    if not (RESULTS / "vol_summary.csv").exists():
        specs = [s for s in catalog.CATALOG if s.domain == "markets" and s.id in series]
        frames = [volatility.backtest(s, series[s.id], paths, min_train=REBUILT_TRAIN) for s in specs]
        rows = pd.concat([f for f in frames if not f.empty], ignore_index=True)
        rows.to_csv(RESULTS / "vol_backtest.csv", index=False)
        volatility.summarize(rows).to_csv(RESULTS / "vol_summary.csv", index=False)
    if not (RESULTS / "event_summary.csv").exists():
        specs = [s for s in catalog.CATALOG if events.eligible(s) and s.id in series]
        frames = [events.backtest(s, series[s.id], paths) for s in specs]
        rows = pd.concat([f for f in frames if not f.empty], ignore_index=True)
        rows.to_csv(RESULTS / "event_backtest.csv", index=False)
        events.summarize(rows).to_csv(RESULTS / "event_summary.csv", index=False)
    event_ledger = events.read(ROOT / "predictions" / "event_ledger.csv")
    if event_ledger is not None and not event_ledger.empty:
        now = event_ledger[event_ledger["made_on"] == event_ledger["made_on"].max()]
    else:  # no sealed odds yet: the odds the newest sealed forecasts imply
        main = pd.read_csv(ROOT / "predictions" / "ledger.csv")
        latest = ledger.name_by_maker(main[main["made_on"] == main["made_on"].max()])
        now = events.forecast_rows([s for s in catalog.CATALOG if events.eligible(s)], series, latest)
    event = {"summary": read_csv(RESULTS / "event_summary.csv"), "now": now,
             "scored": events.read(ROOT / "predictions" / "event_scored.csv"),
             "seals": ledger.verify(event_ledger, ROOT / "predictions" / "event_seals.csv", **events.LAYOUT) if event_ledger is not None else None}
    vol_ledger = volatility.read(ROOT / "predictions" / "vol_ledger.csv")
    vol = {"summary": read_csv(RESULTS / "vol_summary.csv"), "ledger": vol_ledger,
           "scored": volatility.read(ROOT / "predictions" / "vol_scored.csv"),
           "seals": ledger.verify(vol_ledger, ROOT / "predictions" / "vol_seals.csv", **volatility.LAYOUT) if vol_ledger is not None else None}
    status = RESULTS / "run_status.json"
    payload = web.build_payload(
        model, results, read_csv(RESULTS / "skill_by_step.csv"), paths,
        ledger.read(ROOT / "predictions" / "ledger.csv"), ledger.read(ROOT / "predictions" / "scored.csv"), series,
        run_status=json.loads(status.read_text()) if status.exists() else None,
        seals=ledger.verify(pd.read_csv(ROOT / "predictions" / "ledger.csv"), ROOT / "predictions" / "seals.csv"), vol=vol,
        wire=wire.read(RESULTS / "wire.json"), events=event,
    )
    payload["meta"]["generated"] = previous["meta"]["generated"]  # the run's date, not today's
    web.write_data_js(payload, data_js)
    yearbook.write_csv(payload.get("year"), RESULTS)
    note = " (full Seldon replayed from the recorded paths)" if upgraded else ""
    note += " (Seldon's own council replayed from the recorded paths)" if own else ""
    print(f"Rebuilt {data_js.relative_to(ROOT)} from {len(series)} series{note}.\n")
    print_duel(payload["duel"], model, "Seldon")
    print()
    print_duel(payload["duel_laws"], model, "Laws")
    print()
    print(volatility.describe(read_csv(RESULTS / "vol_summary.csv"), None))
    print()
    print(events.describe(read_csv(RESULTS / "event_summary.csv"), None, now))


if __name__ == "__main__":
    main()
