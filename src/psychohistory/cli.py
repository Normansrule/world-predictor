"""Command line interface: ``psychohistory fetch | backtest | predict | score | report``."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

from . import backtest, catalog, data, ledger, report
from .models import BASELINES, load_model

log = logging.getLogger("psychohistory")


def _load(specs, cache: Path, refresh: bool = False) -> dict[str, pd.Series]:
    loaded = {}
    for spec in specs:
        try:
            loaded[spec.id] = data.fetch(spec, cache, refresh=refresh)
        except Exception as exc:  # one broken source should not stop the whole run
            log.warning("skipping %s: %s", spec.id, exc)
    return loaded


def cmd_fetch(args) -> None:
    specs = catalog.select(args.domain, args.series)
    loaded = _load(specs, args.data_dir, refresh=True)
    print(f"Fetched {len(loaded)}/{len(specs)} series into {args.data_dir}/")


def cmd_backtest(args) -> None:
    specs = catalog.select(args.domain, args.series)
    series = _load(specs, args.data_dir)
    names = [args.model] + [b for b in BASELINES if b != args.model]
    models = [load_model(name) for name in names]
    frames = []
    for spec in specs:
        if spec.id in series:
            log.info("backtesting %s", spec.id)
            frames.append(backtest.backtest_series(spec, series[spec.id], models, windows=args.windows))
    results = pd.concat([f for f in frames if not f.empty], ignore_index=True)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    results.to_csv(args.out_dir / "backtest_windows.csv", index=False)
    summary = backtest.summarize(results)
    summary.to_csv(args.out_dir / "backtest_summary.csv", index=False)
    print(backtest.domain_table(summary).to_string(index=False))
    _write_report(args, results, summary)


def cmd_predict(args) -> None:
    specs = catalog.select(args.domain, args.series)
    series = _load(specs, args.data_dir, refresh=args.refresh)
    model = load_model(args.model)
    rows = ledger.predict(specs, series, model)
    ledger.append(rows, args.ledger)
    print(f"Recorded {len(rows)} predictions for {rows['series_id'].nunique()} series in {args.ledger}")
    for series_id, group in rows.groupby("series_id"):
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
    table = ledger.ledger_summary(scored)
    print(table.to_string(index=False) if not table.empty else "No predictions have reached their target date yet.")


def cmd_report(args) -> None:
    results = pd.read_csv(args.out_dir / "backtest_windows.csv")
    summary = backtest.summarize(results)
    _write_report(args, results, summary)


def _write_report(args, results: pd.DataFrame, summary: pd.DataFrame) -> None:
    ledger_table = None
    if args.scored.exists():
        ledger_table = ledger.ledger_summary(pd.read_csv(args.scored))
    report.plot_skill(summary, args.out_dir)
    path = report.write_report(results, summary, args.model, ledger_table, args.out_dir)
    print(f"Report written to {path}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="psychohistory", description=__doc__)
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p):
        p.add_argument("--domain", action="append", choices=catalog.DOMAINS, help="limit to a domain (repeatable)")
        p.add_argument("--series", action="append", help="limit to a series id (repeatable)")
        p.add_argument("--model", default="timesfm-2.5", help="timesfm-2.5 (default), timesfm-3, naive, drift, mean")
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

    p = sub.add_parser("report", help="rebuild results/REPORT.md from saved backtest results")
    common(p)
    p.set_defaults(func=cmd_report)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s %(message)s")
    args.func(args)


if __name__ == "__main__":
    main()
