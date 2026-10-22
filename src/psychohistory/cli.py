"""Command line interface: ``psychohistory run | fetch | backtest | predict | ask | score | report | simulate | export | site | app``."""

from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from . import ask, backtest, catalog, dashboard, data, ledger, report, seldon, simulate, story, web
from .models import BASELINES, classical_available, load_model

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
    names += [b for b in BASELINES if b not in names]
    if classical_available() and "auto-ets" not in names:
        names.append("auto-ets")  # the strongest classical baseline, when statsforecast is installed
    models = [load_model(name) for name in names]
    members = ensemble_members(args) if args.ensemble else None
    frames, step_rows, path_rows = [], [], []
    for spec in specs:
        if spec.id in series:
            log.info("backtesting %s", spec.id)
            frames.append(
                backtest.backtest_series(
                    spec, series[spec.id], models, windows=args.windows, step_rows=step_rows, ensemble_of=members,
                    path_rows=path_rows, paths_for=(args.model, seldon.NAME), seldon_of=args.model,
                )
            )
    frames = [f for f in frames if not f.empty]
    if not frames:
        print("No series had enough data to backtest. Try `psychohistory fetch` first.")
        return
    results = pd.concat(frames, ignore_index=True)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    results.to_csv(args.out_dir / "backtest_windows.csv", index=False)
    summary = backtest.summarize(results)
    summary.to_csv(args.out_dir / "backtest_summary.csv", index=False)
    by_step = backtest.skill_by_step(pd.DataFrame(step_rows))
    by_step.to_csv(args.out_dir / "skill_by_step.csv", index=False)
    pd.DataFrame(path_rows).to_csv(args.out_dir / "backtest_paths.csv", index=False)
    print(backtest.domain_table(summary).to_string(index=False))
    _write_report(args, results, summary)


def cmd_predict(args) -> None:
    specs = catalog.select(args.domain, args.series)
    series = _load(specs, args.data_dir, refresh=args.refresh, status=args.out_dir / "run_status.json", stage="predict")
    # The model under test plus any --compare rivals, so the ledger becomes a head-to-head record.
    names = list(dict.fromkeys([args.model, *args.compare]))
    if args.ensemble:
        names = list(dict.fromkeys(names + ensemble_members(args)))
    # Seldon is derived from the model under test, learning from its saved backtest paths.
    paths_file = args.out_dir / "backtest_paths.csv"
    paths = pd.read_csv(paths_file) if paths_file.exists() and paths_file.stat().st_size > 1 else None
    corrector = {seldon.NAME: lambda spec, base, last: seldon.apply(base, last, seldon.correction_for(paths, spec.id, args.model))}
    rows = pd.concat([ledger.predict(specs, series, load_model(name), extras=corrector if name == args.model else None)
                      for name in names], ignore_index=True)
    if args.ensemble:
        rows = pd.concat([rows, ledger.ensemble_rows(rows, ensemble_members(args))], ignore_index=True)
    ledger.append(rows, args.ledger)
    print(f"Recorded {len(rows)} predictions for {rows['series_id'].nunique()} series in {args.ledger}")
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
    paths_file = args.out_dir / "backtest_paths.csv"
    correction = None
    if spec is not None and paths_file.exists() and paths_file.stat().st_size > 1:
        correction = seldon.correction_for(pd.read_csv(paths_file), spec.id, args.model)
    model = load_model(args.model)
    table = ask.ask(series, model, horizon, freq, correction=correction, above=args.above)
    name = "TimesFM" if args.model.startswith("timesfm") else args.model
    print(f"{spec.description if spec else series_id}: {len(series)} values up to {series.index[-1].date()}\n")
    print(ask.describe(table, float(series.iloc[-1]), name, args.above))
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


def cmd_record(args) -> None:
    """Print one series' track record: every backtest window and every opened sealed forecast."""
    windows_file = args.out_dir / "backtest_windows.csv"
    windows = pd.read_csv(windows_file) if windows_file.exists() else None
    scored = pd.read_csv(args.scored) if args.scored.exists() else None
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
    entries = pd.read_csv(args.ledger)
    specs = [s for s in catalog.CATALOG if s.id in set(entries["series_id"])]
    series = _load(specs, args.data_dir, refresh=args.refresh)
    scored = ledger.score(entries, series)
    args.scored.parent.mkdir(parents=True, exist_ok=True)
    scored.to_csv(args.scored, index=False)
    story.plot_track_record(scored, args.model, args.out_dir)
    table = ledger.ledger_summary(scored)
    print(table.to_string(index=False) if not table.empty else "No predictions have reached their target date yet.")


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
    args.demo = False
    cmd_export(args)


def cmd_report(args) -> None:
    path = args.out_dir / "backtest_windows.csv"
    if not path.exists():
        print(f"No backtest results at {path}; run `psychohistory backtest` first.")
        return
    results = pd.read_csv(path)
    summary = backtest.summarize(results)
    _write_report(args, results, summary)


def _write_report(args, results: pd.DataFrame, summary: pd.DataFrame) -> None:
    ledger_table = None
    if args.scored.exists():
        ledger_table = ledger.ledger_summary(pd.read_csv(args.scored))
    latest = ledger.latest(pd.read_csv(args.ledger)) if args.ledger.exists() else None
    steps_path = args.out_dir / "skill_by_step.csv"
    by_step = pd.read_csv(steps_path) if steps_path.exists() else None
    report.plot_skill(summary, args.out_dir, args.model)
    story.write_scorecards(
        args.out_dir, story.scorecard(summary, args.model, by_step, results), args.model, date.today().isoformat()
    )
    paths_file = args.out_dir / "backtest_paths.csv"
    paths = pd.read_csv(paths_file) if paths_file.exists() and paths_file.stat().st_size > 1 else pd.DataFrame()
    headline = story.pick_headline_series(paths)
    headline_data = _load([catalog.by_id(headline)], args.data_dir) if headline else {}
    if headline in headline_data:
        story.replay_gif(
            headline_data[headline], paths[paths["series_id"] == headline], catalog.by_id(headline).description,
            args.out_dir / "plots" / "replay.gif",
        )
    if by_step is not None:
        report.plot_horizon(by_step, args.model, args.out_dir)
    path = report.write_report(results, summary, args.model, ledger_table, args.out_dir, latest, by_step)
    print(f"Report written to {path}")
    entries = pd.read_csv(args.ledger) if args.ledger.exists() else None
    data_for_fans = {}
    if latest is not None and not latest.empty:
        specs = [s for s in catalog.CATALOG if s.id in set(latest["series_id"])]
        data_for_fans = _load(specs, args.data_dir)
    if headline in headline_data:
        data_for_fans.setdefault(headline, headline_data[headline])
    board = dashboard.write_dashboard(
        results, summary, args.model, args.out_dir, by_step, latest, entries, data_for_fans,
        paths=paths[paths["series_id"] == headline] if headline else None, headline=headline,
        scored=pd.read_csv(args.scored) if args.scored.exists() else None,
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
    results, by_step, paths = read(windows), read(args.out_dir / "skill_by_step.csv"), read(args.out_dir / "backtest_paths.csv")
    entries, scored = read(args.ledger), read(args.scored)
    ids = set()
    for frame in (paths, entries):
        if frame is not None:
            ids |= set(frame["series_id"])
    specs = [s for s in catalog.CATALOG if s.id in ids]
    status = args.out_dir / "run_status.json"
    run = json.loads(status.read_text()) if status.exists() else None
    return web.build_payload(args.model, results, by_step, paths, entries, scored, _load(specs, args.data_dir), run_status=run)


def cmd_export(args) -> None:
    """Write the web app's data file from local results (run after backtest/predict/score)."""
    payload = _payload(args, args.demo)
    if payload is None:
        print("No results yet; run `psychohistory run` first (or use --demo).")
        return
    path = web.write_data_js(payload, args.out_dir / "web" / "data.js")
    print(f"App data written to {path}")


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
        p.add_argument("--model", default="timesfm-2.5", help="model under test: timesfm-2.5 (default), timesfm-3, chronos-bolt, chronos-2, auto-ets, auto-arima, naive, drift, mean")
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
