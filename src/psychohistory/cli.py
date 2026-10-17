"""Command line interface: ``psychohistory run | fetch | backtest | predict | score | report | simulate``."""

from __future__ import annotations

import argparse
import logging
from datetime import date
from pathlib import Path

import pandas as pd

from . import backtest, catalog, dashboard, data, ledger, report, simulate, story
from .models import BASELINES, classical_available, load_model

log = logging.getLogger("psychohistory")


def _load(specs, cache: Path, refresh: bool = False) -> dict[str, pd.Series]:
    loaded = {}
    for spec in specs:
        try:
            loaded[spec.id] = data.fetch(spec, cache, refresh=refresh)
        except Exception as exc:  # one broken source should not stop the whole run
            log.warning("skipping %s: %s", spec.id, exc)
    return loaded


def ensemble_members(args) -> list[str]:
    """Models averaged by --ensemble: the model under test, its rivals and AutoETS if available."""
    members = list(dict.fromkeys([args.model, *args.compare]))
    if classical_available() and "auto-ets" not in members:
        members.append("auto-ets")
    return members


def cmd_fetch(args) -> None:
    specs = catalog.select(args.domain, args.series)
    loaded = _load(specs, args.data_dir, refresh=True)
    print(f"Fetched {len(loaded)}/{len(specs)} series into {args.data_dir}/")


def cmd_backtest(args) -> None:
    specs = catalog.select(args.domain, args.series)
    series = _load(specs, args.data_dir)
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
                    path_rows=path_rows, paths_for=args.model,
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
    series = _load(specs, args.data_dir, refresh=args.refresh)
    # The model under test plus any --compare rivals, so the ledger becomes a head-to-head record.
    names = list(dict.fromkeys([args.model, *args.compare]))
    if args.ensemble:
        names = list(dict.fromkeys(names + ensemble_members(args)))
    rows = pd.concat([ledger.predict(specs, series, load_model(name)) for name in names], ignore_index=True)
    if args.ensemble:
        rows = pd.concat([rows, ledger.ensemble_rows(rows, ensemble_members(args))], ignore_index=True)
    ledger.append(rows, args.ledger)
    print(f"Recorded {len(rows)} predictions for {rows['series_id'].nunique()} series in {args.ledger}")
    for series_id, group in rows[rows["model"] == args.model].groupby("series_id"):
        spec = catalog.by_id(series_id)
        report.plot_fan(series[series_id], group, spec.description, args.out_dir)


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

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s %(message)s")
    args.func(args)


if __name__ == "__main__":
    main()
