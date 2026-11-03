"""Command line interface: ``psychohistory run | fetch | backtest | predict | ask | desk | monitor | vol | events | wire | verify | score | report | simulate | export | site | app``."""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from . import ask, backtest, catalog, dashboard, data, desk, events, ledger, monitor, radiant, report, seldon, simulate, story, volatility, web, wire, yearbook
from .models import BASELINES, LAWS, classical_available, load_model

log = logging.getLogger("psychohistory")


def _load(specs, cache: Path, refresh: bool = False, status: Path | None = None, stage: str | None = None) -> dict[str, pd.Series]:
    loaded, skipped = {}, {}
    for spec in specs:
        try:
            loaded[spec.id] = data.fetch(spec, cache, refresh=refresh)
        except Exception as exc:  # one broken source should not stop the whole run
            log.warning("skipping %s: %s", spec.id, exc)
            skipped[spec.id] = f"{type(exc).__name__}: {exc}"[:300]
    if status is not None and stage:
        record_status(status, stage, loaded, skipped)
    return loaded


def record_status(path: Path, stage: str, loaded: dict, skipped: dict[str, str]) -> None:
    """Note which series got through a stage and why the others did not, for the app's
    "Follow one result" view. A skipped series is a visible gap, never silently filled in."""
    current = json.loads(path.read_text()) if path.exists() else {}
    current.setdefault("stages", {})[stage] = {
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ok": sorted(loaded), "skipped": dict(sorted(skipped.items())),
    }
    if os.environ.get("GITHUB_RUN_ID"):
        current["run_id"] = os.environ["GITHUB_RUN_ID"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(current, indent=1) + "\n")


def ensemble_members(args) -> list[str]:
    """Models averaged by --ensemble: the model under test, its rivals and AutoETS if available."""
    members = list(dict.fromkeys([args.model, *args.compare]))
    if classical_available() and "auto-ets" not in members:
        members.append("auto-ets")
    return members


def cmd_fetch(args) -> None:
    specs = catalog.select(args.domain, args.series)
    loaded = _load(specs, args.data_dir, refresh=True, status=args.out_dir / "run_status.json", stage="fetch")
    print(f"Fetched {len(loaded)}/{len(specs)} series into {args.data_dir}/")


def cmd_backtest(args) -> None:
    specs = catalog.select(args.domain, args.series)
    series = _load(specs, args.data_dir, status=args.out_dir / "run_status.json", stage="backtest")
    names = [args.model] + [m for m in args.compare if m != args.model]
    names += [m for m in (LAWS, radiant.CORE, *BASELINES) if m not in names]  # Seldon and Radiant face every model on the same windows
    if classical_available() and "auto-ets" not in names:
        names.append("auto-ets")  # the strongest classical baseline, when statsforecast is installed
    models = [load_model(name) for name in names]
    members = ensemble_members(args) if args.ensemble else None
    frames, step_rows, path_rows, kept = [], [], [], []
    for spec in specs:
        if spec.id in series:
            log.info("backtesting %s", spec.id)
            frames.append(
                backtest.backtest_series(
                    spec, series[spec.id], models, windows=args.windows, step_rows=step_rows, ensemble_of=members,
                    path_rows=path_rows, paths_for=(args.model, seldon.NAME, LAWS, radiant.CORE), keep=kept,
                )
            )
    # The full Seldon learns across series (per area), so it is scored once every series is in.
    frames.append(backtest.add_seldon(kept, args.model, step_rows, path_rows, paths_for=(seldon.NAME,)))
    frames.append(backtest.add_radiant(kept, args.model, step_rows, path_rows, paths_for=(radiant.NAME,)))
    frames = [f for f in frames if not f.empty]
    if not frames:
        print("No series had enough data to backtest. Try `psychohistory fetch` first.")
        return
    results = pd.concat(frames, ignore_index=True)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    results.to_csv(args.out_dir / "backtest_windows.csv", index=False)
    summary = backtest.summarize(results)
    summary.to_csv(args.out_dir / "backtest_summary.csv", index=False)
    # Each backtest overwrites the last, so its verdict is also kept by date: how the record evolves over the years.
    (args.out_dir / "history").mkdir(parents=True, exist_ok=True)
    summary.assign(run=date.today().isoformat()).to_csv(args.out_dir / "history" / f"backtest-{date.today().isoformat()}.csv", index=False)
    by_step = backtest.skill_by_step(pd.DataFrame(step_rows))
    by_step.to_csv(args.out_dir / "skill_by_step.csv", index=False)
    pd.DataFrame(path_rows).to_csv(args.out_dir / "backtest_paths.csv", index=False)
    print(backtest.domain_table(summary).to_string(index=False))
    _write_report(args, results, summary)


def seldon_shares(args, data: dict[str, pd.Series]) -> list:
    """The finished windows the full Seldon learns its per-area shares from: the model under
    test's saved backtest paths, with the crowd laws rerun on the data up to each origin."""
    paths_file = args.out_dir / "backtest_paths.csv"
    paths = pd.read_csv(paths_file) if paths_file.exists() and paths_file.stat().st_size > 1 else None
    domains = {s.id: s.domain for s in catalog.CATALOG}
    return seldon.windows_from_paths(paths, data, args.model, domains)


def seldon_builder(args, data: dict[str, pd.Series]):
    """For ``ledger.predict``: the full Seldon from the model's forecast and the same context."""
    windows = seldon_shares(args, data)

    def build(spec, base, context):
        laws, _ = seldon.predict(context, len(base.point))
        return seldon.blend(base, laws, seldon.share_for(windows, spec.domain))
    return build


def radiant_builder(args, data: dict[str, pd.Series]):
    """For ``ledger.predict``: the full Radiant from the model's forecast and the same context,
    mixed with the weights its area's finished backtest windows earned."""
    paths_file = args.out_dir / "backtest_paths.csv"
    paths = pd.read_csv(paths_file) if paths_file.exists() and paths_file.stat().st_size > 1 else None
    windows = radiant.windows_from_paths(paths, data, args.model, radiant.domains_of(catalog.CATALOG))

    def build(spec, base, context):
        h = len(base.point)
        experts = {"model": base, "laws": seldon.predict(context, h)[0], "core": radiant.core_predict(context, h)[0],
                   "naive": radiant.naive_forecast(context, h)}
        return radiant.mix(experts, radiant.weights(windows, spec.domain))
    return build


def cmd_predict(args) -> None:
    specs = catalog.select(args.domain, args.series)
    series = _load(specs, args.data_dir, refresh=args.refresh, status=args.out_dir / "run_status.json", stage="predict")
    # The model under test, both Seldons and any --compare rivals, so the ledger becomes a head-to-head record.
    names = list(dict.fromkeys([args.model, LAWS, radiant.CORE, *args.compare]))
    if args.ensemble:
        names = list(dict.fromkeys(names + ensemble_members(args)))
    full = {seldon.NAME: seldon_builder(args, series), radiant.NAME: radiant_builder(args, series)}
    rows = pd.concat([ledger.predict(specs, series, load_model(name), extras=full if name == args.model else None)
                      for name in names], ignore_index=True)
    if args.ensemble:
        rows = pd.concat([rows, ledger.ensemble_rows(rows, ensemble_members(args))], ignore_index=True)
    entries = ledger.append(rows, args.ledger)
    ledger.write_seals(entries, args.ledger.parent / ledger.SEALS.name)
    print(f"Recorded {len(rows)} predictions for {rows['series_id'].nunique()} series in {args.ledger}")
    # Volatility: GARCH, EWMA, last month's and what each model's fresh range implies, sealed beside it.
    vol_rows = volatility.forecast_rows(specs, series, rows)
    if not vol_rows.empty:
        vol_entries = volatility.append(vol_rows, _vol_path(args, "ledger"))
        ledger.write_seals(vol_entries, _vol_path(args, "seals"), **volatility.LAYOUT)
        print(f"Recorded {len(vol_rows)} volatility forecasts for {vol_rows['series_id'].nunique()} markets in {_vol_path(args, 'ledger')}")
    # Event odds: the chance of a spike or a lull four weeks ahead, read off the same sealed ranges.
    event_rows = events.forecast_rows(specs, series, rows)
    if not event_rows.empty:
        event_entries = events.append(event_rows, _event_path(args, "ledger"))
        ledger.write_seals(event_entries, _event_path(args, "seals"), **events.LAYOUT)
        print(f"Recorded {len(event_rows)} event odds for {event_rows['series_id'].nunique()} series in {_event_path(args, 'ledger')}")
    for series_id, group in rows[rows["model"] == args.model].groupby("series_id"):
        spec = catalog.by_id(series_id)
        report.plot_fan(series[series_id], group, spec.description, args.out_dir)
    story.plot_outlook(series, rows, args.model, args.out_dir,
                       titles={s.id: s.description for s in specs})


def cmd_ask(args) -> None:
    """Run the model live on one series (from the catalog or your own CSV) and print its forecast."""
    if bool(args.target) == bool(args.csv):
        raise SystemExit("Name one catalog series (e.g. `psychohistory ask sp500`) or pass --csv FILE.")
    if args.csv:
        series, series_id, spec = ask.read_csv(args.csv), args.csv.stem, None
        freq, horizon = args.freq or ask.guess_freq(series), args.horizon or 28
    else:
        try:
            spec = catalog.by_id(args.target)
        except KeyError:
            raise SystemExit(f"No series called {args.target!r}. Known ids: " + ", ".join(s.id for s in catalog.CATALOG)) from None
        try:
            series = data.fetch(spec, args.data_dir, refresh=args.refresh)
        except Exception as exc:  # no cache and no network: say so instead of a traceback
            raise SystemExit(f"Could not load {spec.id}: {exc}. Run `psychohistory fetch` with a network connection first.") from None
        series_id, freq, horizon = spec.id, args.freq or spec.freq, args.horizon or spec.horizon
    model = load_model(args.model)
    share = seldon.share_for(seldon_shares(args, {spec.id: series}), spec.domain) if spec is not None else 0.0
    table, council = ask.ask(series, model, horizon, freq, share=share, above=args.above)
    name = "TimesFM" if args.model.startswith("timesfm") else args.model
    print(f"{spec.description if spec else series_id}: {len(series)} values up to {series.index[-1].date()}\n")
    print(ask.describe(table, float(series.iloc[-1]), name, args.above))
    print("\n" + seldon.explain_full(council, share, name))
    if args.save:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        table.to_csv(args.save, index=False)
        print(f"\nSaved every step to {args.save}")
    if args.seal:
        if spec is None:
            raise SystemExit("--seal needs a catalog series: the scorer re-downloads it to check the forecast.")
        rows = ask.ledger_rows(table, series, spec.id, spec.domain, spec.scale, args.model, date.today().isoformat())
        ledger.append(rows, args.ledger)
        print(f"Sealed {len(rows)} rows in {args.ledger}; `psychohistory score` checks them as the dates pass.")


def cmd_desk(args) -> None:
    """A forecast desk note for each named market: catalog ids, Yahoo tickers or --csv files."""
    targets = [(t, None) for t in args.targets] + [(p.stem, p) for p in args.csv or []]
    if not targets:
        raise SystemExit("Name at least one market, e.g. `psychohistory desk gold MSFT ETH-USD`, or pass --csv FILE.")
    model = load_model(args.model)
    others = [load_model(name) for name in dict.fromkeys([LAWS, "naive", "drift", *args.compare]) if name != args.model]
    for target, path in targets:
        if path is not None:
            series = ask.read_csv(path)
            spec = catalog.SeriesSpec(f"desk_{target}", "markets", "csv", {"ticker": path.name},
                                      ask.guess_freq(series), args.horizon or 20, "individual", path.stem)
        else:
            spec = desk.spec_for(target, args.horizon)
            cached = data.cache_path(spec, args.data_dir)
            stale = cached.exists() and time.time() - cached.stat().st_mtime > 12 * 3600  # a desk wants today's prices
            try:
                series = data.fetch(spec, args.data_dir, refresh=args.refresh or stale)
            except Exception as exc:  # no cache and no network, or an unknown ticker
                print(f"Could not load {target}: {exc}")
                continue
        note = desk.build(spec, series, model, others, levels=args.level, windows=args.windows)
        files = desk.write(note, args.desk_dir)
        print(desk.note(note))
        print("Wrote " + ", ".join(str(f) for f in files) + "\n")


def cmd_monitor(args) -> None:
    """The long-term record: every sealed forecast that came due, by model and area, the test
    against "no change" and the drift alarms."""
    scored = ledger.read(args.scored)
    results, _ = _results(args)
    summary = backtest.summarize(results) if results is not None else None
    print(monitor.describe(scored, args.model, summary))
    if args.save and scored is not None:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        monitor.by_month(scored).to_csv(args.save, index=False)
        print(f"\nSaved the month-by-month record to {args.save}")


def _vol_path(args, kind: str) -> Path:
    """The volatility ledger's files sit beside the main ledger."""
    name = {"ledger": volatility.VOL_LEDGER, "scored": volatility.VOL_SCORED, "seals": volatility.VOL_SEALS}[kind].name
    return args.ledger.parent / name


def _vol_seals(args) -> pd.DataFrame | None:
    entries = volatility.read(_vol_path(args, "ledger"))
    return ledger.verify(entries, _vol_path(args, "seals"), **volatility.LAYOUT) if entries is not None else None


def cmd_vol(args) -> None:
    """Volatility forecasts: the backtest across markets (``--backtest`` reruns it from the data and
    the saved paths) and the sealed volatility record so far."""
    if args.backtest:
        specs = [s for s in catalog.select(args.domain, args.series) if volatility.horizons(s.freq) and s.domain == "markets"]
        series = _load(specs, args.data_dir)
        paths = _results(args)[1]
        frames = [volatility.backtest(spec, series[spec.id], paths) for spec in specs if spec.id in series]
        rows = pd.concat([f for f in frames if not f.empty], ignore_index=True) if frames else pd.DataFrame()
        if rows.empty:
            print("No market had enough data for a volatility backtest. Try `psychohistory fetch` first.")
            return
        args.out_dir.mkdir(parents=True, exist_ok=True)
        rows.to_csv(args.out_dir / "vol_backtest.csv", index=False)
        volatility.summarize(rows).to_csv(args.out_dir / "vol_summary.csv", index=False)
    summary_file = args.out_dir / "vol_summary.csv"
    summary = pd.read_csv(summary_file) if summary_file.exists() else None
    print(volatility.describe(summary, volatility.live_record(volatility.read(_vol_path(args, "scored")))))


def _event_path(args, kind: str) -> Path:
    """The event ledger's files sit beside the main ledger."""
    name = {"ledger": events.EVENT_LEDGER, "scored": events.EVENT_SCORED, "seals": events.EVENT_SEALS}[kind].name
    return args.ledger.parent / name


def _event_seals(args) -> pd.DataFrame | None:
    entries = events.read(_event_path(args, "ledger"))
    return ledger.verify(entries, _event_path(args, "seals"), **events.LAYOUT) if entries is not None else None


def _event_now(args, data: dict[str, pd.Series] | None = None) -> pd.DataFrame | None:
    """The newest sealed event odds; before the first sealed batch, the odds the newest sealed
    forecasts imply (computed from the same sealed quantiles and the history up to their last day)."""
    entries = events.read(_event_path(args, "ledger"))
    if entries is not None and not entries.empty:
        return entries[entries["made_on"] == entries["made_on"].max()]
    main = ledger.read(args.ledger)
    if main is None or main.empty:
        return None
    latest = main[main["made_on"] == main["made_on"].max()]
    specs = [s for s in catalog.CATALOG if events.eligible(s) and s.id in set(latest["series_id"])]
    data = data if data is not None else _load(specs, args.data_dir)
    return events.forecast_rows(specs, data, latest)


def cmd_events(args) -> None:
    """Event odds: the chance of a spike or a lull in world news and technology attention four weeks
    ahead, the backtest (``--backtest`` reruns it from the data and the saved paths) and the sealed
    record so far."""
    specs = [s for s in catalog.select(args.domain, args.series) if events.eligible(s)]
    series = _load(specs, args.data_dir)
    if args.backtest:
        paths = _results(args)[1]
        frames = [events.backtest(spec, series[spec.id], paths) for spec in specs if spec.id in series]
        rows = pd.concat([f for f in frames if not f.empty], ignore_index=True) if frames else pd.DataFrame()
        if rows.empty:
            print("No series had enough data and saved backtest paths for event odds. Run `psychohistory backtest` first.")
        else:
            args.out_dir.mkdir(parents=True, exist_ok=True)
            rows.to_csv(args.out_dir / "event_backtest.csv", index=False)
            events.summarize(rows).to_csv(args.out_dir / "event_summary.csv", index=False)
    summary_file = args.out_dir / "event_summary.csv"
    summary = pd.read_csv(summary_file) if summary_file.exists() else None
    print(events.describe(summary, events.live_record(events.read(_event_path(args, "scored"))), _event_now(args, series)))


def cmd_wire(args) -> None:
    """The world wire: the newest headlines for every topic, for the app's World terminal."""
    specs = catalog.select(args.domain, args.series)
    news = wire.fetch(specs, records=args.records)
    path = wire.write(news, args.out_dir / wire.WIRE.name)
    count = sum(len(t["articles"]) for t in news["topics"].values())
    print(f"Wrote {count} headlines for {len(news['topics'])} topics to {path}" + (f"; {len(news['failed'])} topics failed" if news["failed"] else ""))


def cmd_verify(args) -> None:
    """Check every fingerprinted batch of the ledgers is exactly as it was sealed."""
    entries = ledger.read(args.ledger)
    seals = args.ledger.parent / ledger.SEALS.name
    if entries is None:
        raise SystemExit(f"No ledger at {args.ledger}.")
    raw = pd.read_csv(args.ledger)  # the file as written, not renamed for display
    checks = [("forecast", ledger.verify(raw, seals), seals), ("volatility", _vol_seals(args), _vol_path(args, "seals")),
              ("event", _event_seals(args), _event_path(args, "seals"))]
    failed = False
    for kind, checked, path in checks:
        if checked is None or checked.empty:
            print(f"No {kind} fingerprints yet in {path}; `psychohistory predict` writes them with every batch.")
            continue
        bad = checked[checked["status"] != "ok"]
        print(f"{len(checked) - len(bad)} of {len(checked)} sealed {kind} batches match their fingerprints ({checked['rows'].sum()} rows).")
        for r in bad.itertuples():
            print(f"  {r.made_on} {r.model}: {r.status}")
        failed |= not bad.empty
    if failed:
        raise SystemExit(1)


def cmd_record(args) -> None:
    """Print one series' track record: every backtest window and every opened sealed forecast."""
    windows, _ = _results(args)
    scored = ledger.read(args.scored)
    known = set(windows["series_id"]) if windows is not None else set()
    if scored is not None:
        known |= set(scored["series_id"])
    if args.target not in known:
        hint = ", ".join(sorted(known)) if known else "none yet; run `psychohistory run` first"
        raise SystemExit(f"No record for {args.target!r}. Series with a record: {hint}")
    print(story.series_record(args.target, windows, scored, args.model))


def cmd_score(args) -> None:
    if not args.ledger.exists():
        print(f"No ledger at {args.ledger}; run `psychohistory predict` first.")
        return
    entries = ledger.read(args.ledger)
    specs = [s for s in catalog.CATALOG if s.id in set(entries["series_id"])]
    series = _load(specs, args.data_dir, refresh=args.refresh)
    scored = ledger.score(entries, series)
    args.scored.parent.mkdir(parents=True, exist_ok=True)
    scored.to_csv(args.scored, index=False)
    story.plot_track_record(scored, args.model, args.out_dir)
    table = ledger.ledger_summary(scored)
    print(table.to_string(index=False) if not table.empty else "No predictions have reached their target date yet.")
    vol_entries = volatility.read(_vol_path(args, "ledger"))
    if vol_entries is not None:
        vol_specs = [s for s in catalog.CATALOG if s.id in set(vol_entries["series_id"])]
        vol_data = {**series, **_load([s for s in vol_specs if s.id not in series], args.data_dir)}
        vol_scored = volatility.score(vol_entries, vol_data, {s.id: s.freq for s in vol_specs})
        vol_scored.to_csv(_vol_path(args, "scored"), index=False)
        print(f"Scored {len(vol_scored)} sealed volatility forecasts.")
    event_entries = events.read(_event_path(args, "ledger"))
    if event_entries is not None:
        event_specs = [s for s in catalog.CATALOG if s.id in set(event_entries["series_id"])]
        event_data = {**series, **_load([s for s in event_specs if s.id not in series], args.data_dir)}
        event_scored = events.score(event_entries, event_data, {s.id: s.domain for s in event_specs})
        event_scored.to_csv(_event_path(args, "scored"), index=False)
        print(f"Scored {len(event_scored)} sealed event odds.")


def cmd_run(args) -> None:
    """Everything in order: fetch fresh data, record forecasts, score old ones, backtest."""
    cmd_fetch(args)
    cmd_predict(args)
    cmd_score(args)
    if args.skip_backtest:
        if (args.out_dir / "backtest_windows.csv").exists():
            cmd_report(args)
    else:
        cmd_backtest(args)
    args.backtest = True
    cmd_vol(args)
    cmd_events(args)
    args.records = wire.RECORDS
    cmd_wire(args)
    args.demo = False
    cmd_export(args)


def _results(args) -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
    """The saved backtest windows and paths, a run from before the full Seldon brought up to date
    (``backtest.upgrade_run``)."""
    read = lambda p: pd.read_csv(p) if p.exists() and p.stat().st_size > 1 else None  # noqa: E731
    results, paths = read(args.out_dir / "backtest_windows.csv"), read(args.out_dir / "backtest_paths.csv")
    if results is not None and paths is not None:
        results, paths, upgraded = backtest.upgrade_run(results, paths, args.model)
        if upgraded:
            log.info("this run's Seldon was the crowd laws alone: renamed seldon-laws, full Seldon replayed from its paths")
    return results, paths


def cmd_report(args) -> None:
    results, _ = _results(args)
    if results is None:
        print(f"No backtest results in {args.out_dir}; run `psychohistory backtest` first.")
        return
    summary = backtest.summarize(results)
    _write_report(args, results, summary)


def _write_report(args, results: pd.DataFrame, summary: pd.DataFrame) -> None:
    ledger_table = None
    scored, entries = ledger.read(args.scored), ledger.read(args.ledger)
    if scored is not None:
        ledger_table = ledger.ledger_summary(scored)
    latest = ledger.latest(entries) if entries is not None else None
    steps_path = args.out_dir / "skill_by_step.csv"
    by_step = pd.read_csv(steps_path) if steps_path.exists() else None
    report.plot_skill(summary, args.out_dir, args.model)
    story.write_scorecards(
        args.out_dir, story.scorecard(summary, args.model, by_step, results), args.model, date.today().isoformat()
    )
    paths = _results(args)[1]
    paths = pd.DataFrame() if paths is None else paths
    headline = story.pick_headline_series(paths)
    headline_data = _load([catalog.by_id(headline)], args.data_dir) if headline else {}
    if headline in headline_data:
        story.replay_gif(
            headline_data[headline], paths[paths["series_id"] == headline], catalog.by_id(headline).description,
            args.out_dir / "plots" / "replay.gif",
        )
    if by_step is not None:
        report.plot_horizon(by_step, args.model, args.out_dir)
    path = report.write_report(results, summary, args.model, ledger_table, args.out_dir, latest, by_step, scored)
    print(f"Report written to {path}")
    data_for_fans = {}
    if latest is not None and not latest.empty:
        specs = [s for s in catalog.CATALOG if s.id in set(latest["series_id"])]
        data_for_fans = _load(specs, args.data_dir)
    if headline in headline_data:
        data_for_fans.setdefault(headline, headline_data[headline])
    board = dashboard.write_dashboard(
        results, summary, args.model, args.out_dir, by_step, latest, entries, data_for_fans,
        paths=paths[paths["series_id"] == headline] if headline else None, headline=headline,
        scored=scored,
    )
    if board:
        print(f"Dashboard written to {board}")


def cmd_simulate(args) -> None:
    """Seldon's law in a toy world: no downloads, runs in seconds."""
    tide, people = simulate.simulate_crowd(seed=args.seed)
    table = simulate.crowd_predictability(tide, people)
    print(table.assign(predictable_share=table["predictable_share"].map("{:.0%}".format)).to_string(index=False))
    gif = simulate.crowd_gif(args.out_dir / "plots" / "seldon_crowd.gif", seed=args.seed)
    if gif:
        print(f"Animation written to {gif}")


def _payload(args, demo: bool = False) -> dict | None:
    """The web app's data from local results, or None when there is nothing to show yet."""
    if demo:
        return web.demo_payload()
    windows = args.out_dir / "backtest_windows.csv"
    if not windows.exists() and not args.ledger.exists():
        return None
    read = lambda p: pd.read_csv(p) if p.exists() and p.stat().st_size > 1 else None  # noqa: E731
    (results, paths), by_step = _results(args), read(args.out_dir / "skill_by_step.csv")
    entries, scored = ledger.read(args.ledger), ledger.read(args.scored)
    ids = set()
    for frame in (paths, entries):
        if frame is not None:
            ids |= set(frame["series_id"])
    specs = [s for s in catalog.CATALOG if s.id in ids]
    status = args.out_dir / "run_status.json"
    run = json.loads(status.read_text()) if status.exists() else None
    seals = ledger.verify(pd.read_csv(args.ledger), args.ledger.parent / ledger.SEALS.name) if args.ledger.exists() else None
    vol = {"summary": read(args.out_dir / "vol_summary.csv"), "ledger": volatility.read(_vol_path(args, "ledger")),
           "scored": volatility.read(_vol_path(args, "scored")), "seals": _vol_seals(args)}
    data = _load(specs, args.data_dir)
    event = {"summary": read(args.out_dir / "event_summary.csv"), "now": _event_now(args, data),
             "scored": events.read(_event_path(args, "scored")), "seals": _event_seals(args)}
    return web.build_payload(args.model, results, by_step, paths, entries, scored, data, run_status=run,
                             seals=seals, vol=vol, wire=wire.read(args.out_dir / wire.WIRE.name), events=event)


def cmd_export(args) -> None:
    """Write the web app's data file from local results (run after backtest/predict/score)."""
    payload = _payload(args, args.demo)
    if payload is None:
        print("No results yet; run `psychohistory run` first (or use --demo).")
        return
    path = web.write_data_js(payload, args.out_dir / "web" / "data.js")
    print(f"App data written to {path}")
    if not args.demo and payload.get("year"):
        print(f"Year ledger written to {yearbook.write_csv(payload['year'], args.out_dir)}")


def cmd_site(args) -> None:
    """Build the static app (the same one GitHub Pages serves) into a folder."""
    data_js = args.out_dir / "web" / "data.js"
    payload = web.demo_payload() if args.demo else None
    out = web.build_site(args.site_dir, data_js=None if args.demo else data_js, payload=payload)
    print(f"Site built in {out}/ (open {out / 'app' / 'index.html'})")


def cmd_app(args) -> None:
    """The full local version: refresh the app's data from your own results and open it."""
    import functools
    import http.server
    import threading
    import webbrowser

    payload = _payload(args, args.demo)
    out = web.build_site(args.site_dir, payload=payload)
    if payload is None:
        print("No local results yet, so the app shows demo data. Run `psychohistory run` for real forecasts.")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(out))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    url = f"http://127.0.0.1:{args.port}/app/"
    print(f"World Predictor is running at {url}  (Ctrl+C to stop)")
    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="psychohistory", description=__doc__)
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p):
        p.add_argument("--domain", action="append", choices=catalog.DOMAINS, help="limit to a domain (repeatable)")
        p.add_argument("--series", action="append", help="limit to a series id (repeatable)")
        p.add_argument("--model", default="timesfm-2.5", help="model under test: timesfm-2.5 (default), timesfm-3, chronos-bolt, chronos-2, seldon, auto-ets, auto-arima, naive, drift, mean")
        p.add_argument("--compare", action="append", default=[], metavar="MODEL",
                       help="rival model to run alongside, e.g. --compare chronos-bolt (repeatable)")
        p.add_argument("--ensemble", action="store_true",
                       help="also score the average of the model, its rivals and AutoETS (quantile averaging)")
        p.add_argument("--data-dir", type=Path, default=Path("data"))
        p.add_argument("--out-dir", type=Path, default=Path("results"))
        p.add_argument("--ledger", type=Path, default=ledger.LEDGER)
        p.add_argument("--scored", type=Path, default=ledger.SCORED)
        p.add_argument("--refresh", action="store_true", help="re-download data instead of using the cache")

    p = sub.add_parser("fetch", help="download all series into the data cache")
    common(p)
    p.set_defaults(func=cmd_fetch)

    p = sub.add_parser("backtest", help="rolling-origin backtest against baselines, then write the report")
    common(p)
    p.add_argument("--windows", type=int, default=12, help="forecast origins per series")
    p.set_defaults(func=cmd_backtest)

    p = sub.add_parser("predict", help="forecast the future and record it in the prediction ledger")
    common(p)
    p.set_defaults(func=cmd_predict)

    p = sub.add_parser("ask", help="run the model live on one series or your own CSV and print its forecast")
    common(p)
    p.add_argument("target", nargs="?", help="a catalog series id, e.g. sp500 (see src/psychohistory/catalog.py)")
    p.add_argument("--csv", type=Path, help="your own series instead: a CSV of date,value rows")
    p.add_argument("--horizon", type=int, help="steps ahead (default: the series' own, or 28)")
    p.add_argument("--freq", help='step size for dating the forecast: "D" days, "B" weekdays (default: guessed)')
    p.add_argument("--above", type=float, metavar="LEVEL", help="also give the chance of ending above LEVEL")
    p.add_argument("--save", type=Path, metavar="FILE", help="write every step to a CSV")
    p.add_argument("--seal", action="store_true", help="write the forecast to the prediction ledger to be scored later")
    p.set_defaults(func=cmd_ask)

    p = sub.add_parser("desk", help="forecast desk note for any market: catalog id or Yahoo ticker, with odds, volatility and a track record")
    common(p)
    p.add_argument("targets", nargs="*", help="catalog ids or Yahoo Finance tickers, e.g. gold MSFT ^FTSE ETH-USD EURUSD=X")
    p.add_argument("--csv", type=Path, nargs="+", help="your own price history: CSVs of date,value rows")
    p.add_argument("--horizon", type=int, help="steps ahead (default: the series' own, 20 trading days for a ticker)")
    p.add_argument("--level", type=float, nargs="+", help="price levels to give the chance of ending above")
    p.add_argument("--windows", type=int, default=8, help="past windows to backtest each model on (default 8)")
    p.add_argument("--desk-dir", type=Path, default=Path("results/desk"), help="where the notes go (default results/desk)")
    p.set_defaults(func=cmd_desk)

    p = sub.add_parser("monitor", help="the long-term record of sealed forecasts against reality, with drift alarms")
    common(p)
    p.add_argument("--save", type=Path, metavar="FILE", help="also write the month-by-month record to a CSV")
    p.set_defaults(func=cmd_monitor)

    p = sub.add_parser("vol", help="volatility forecasts (GARCH, EWMA, TimesFM-implied) against what happened")
    common(p)
    p.add_argument("--backtest", action="store_true", help="rerun the volatility backtest from the data and the saved paths")
    p.set_defaults(func=cmd_vol)

    p = sub.add_parser("events", help="event odds: the chance of a spike or a lull in news and tech attention, against climatology")
    common(p)
    p.add_argument("--backtest", action="store_true", help="rerun the event-odds backtest from the data and the saved paths")
    p.set_defaults(func=cmd_events)

    p = sub.add_parser("wire", help="the newest headlines for every topic, from GDELT, for the World terminal")
    common(p)
    p.add_argument("--records", type=int, default=wire.RECORDS, help="headlines per topic (default 6)")
    p.set_defaults(func=cmd_wire)

    p = sub.add_parser("verify", help="check every sealed batch of the ledgers still matches its fingerprint")
    common(p)
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("record", help="print one series' track record: past windows and opened sealed forecasts")
    common(p)
    p.add_argument("target", help="a series id, e.g. gold")
    p.set_defaults(func=cmd_record)

    p = sub.add_parser("score", help="score ledger predictions whose target dates have passed")
    common(p)
    p.set_defaults(func=cmd_score)

    p = sub.add_parser("run", help="fetch, predict, score and backtest in one go")
    common(p)
    p.add_argument("--windows", type=int, default=12, help="forecast origins per series")
    p.add_argument("--skip-backtest", action="store_true", help="only fetch, predict and score")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("report", help="rebuild results/REPORT.md from saved backtest results")
    common(p)
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("simulate", help="toy agent-based world showing why crowds are more predictable than people")
    p.add_argument("--out-dir", type=Path, default=Path("results"))
    p.add_argument("--seed", type=int, default=0)
    p.set_defaults(func=cmd_simulate)

    p = sub.add_parser("export", help="write the web app's data file (results/web/data.js) from local results")
    common(p)
    p.add_argument("--demo", action="store_true", help="write illustrative demo data instead")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("site", help="build the static web app (what GitHub Pages serves) into a folder")
    common(p)
    p.add_argument("--site-dir", type=Path, default=Path("build/site"))
    p.add_argument("--demo", action="store_true", help="use illustrative demo data")
    p.set_defaults(func=cmd_site)

    p = sub.add_parser("app", help="open the World Predictor app on this computer with your own results")
    common(p)
    p.add_argument("--site-dir", type=Path, default=Path("build/site"))
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--demo", action="store_true", help="use illustrative demo data")
    p.add_argument("--no-browser", action="store_true", help="do not open a browser window")
    p.set_defaults(func=cmd_app)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s %(message)s")
    args.func(args)


if __name__ == "__main__":
    main()
