"""Seldon's first look at a recorded run, without downloading anything.

A run from before Seldon joined the backtest has no Seldon rows, and the raw data is not committed
(Yahoo's terms). But the run's saved backtest windows sit back to back, so their actual values are a
continuous stretch of each series (about a year of daily data), and the app's data file carries the
newest values behind every sealed forecast. Together they rebuild each series well enough to run
Seldon on every past window from only the values before it, exactly as the backtest would.

This rebuilds ``results/web/data.js`` that way and prints the duel. Seldon is handicapped here: it
sees at most the windows before each one (TimesFM saw up to 1,024 values), and the first window
has nothing before it, so it is left out. The next full backtest replaces all of this with the
official head-to-head.

    python scripts/seldon_first_look.py            # from the repository root
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from psychohistory import web

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


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


def main() -> None:
    data_js = RESULTS / "web" / "data.js"
    text = data_js.read_text()
    previous = json.loads(text[text.index("{"): text.rindex("}") + 1])
    model = previous["meta"]["model"]
    paths = read_csv(RESULTS / "backtest_paths.csv")
    series = rebuild_series(paths, model, previous)
    status = RESULTS / "run_status.json"
    payload = web.build_payload(
        model, read_csv(RESULTS / "backtest_windows.csv"), read_csv(RESULTS / "skill_by_step.csv"), paths,
        read_csv(ROOT / "predictions" / "ledger.csv"), read_csv(ROOT / "predictions" / "scored.csv"), series,
        run_status=json.loads(status.read_text()) if status.exists() else None,
    )
    payload["meta"]["generated"] = previous["meta"]["generated"]  # the run's date, not today's
    web.write_data_js(payload, data_js)
    print(f"Rebuilt {data_js.relative_to(ROOT)} with Seldon on {len(series)} series.\n")
    print(f"{'area':<8} {'series':>6} {'Seldon won':>10} {model + ' won':>16}   skill {model} / Seldon   in 80% range")
    for r in payload["duel"]:
        print(f"{r['domain']:<8} {r['series']:>6} {r['wins']:>10} {r['losses']:>16}   "
              f"{r['skill'][0]:+.1%} / {r['skill'][1]:+.1%}          {r['coverage80'][0]:.0%} / {r['coverage80'][1]:.0%}")


if __name__ == "__main__":
    main()
