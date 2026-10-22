"""What each stage of the pipeline is, in one place: the source of the app's pipeline explorer and
of ``docs/ARCHITECTURE.md``.

Every stage names the real files and functions that do the work, the tests that check them, and
how it behaves when something goes wrong. ``scripts/make_readme_art.py`` turns this list into
``site/app/data/pipeline.js`` (with line numbers, so links land on the right function) and the
architecture page; a test fails if a path, symbol or test named here stops existing.

The arrows between stages are data flow: what is handed on, not what causes what.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from . import catalog
from .data import source_url

ROOT = Path(__file__).resolve().parents[2]
REPO = "https://github.com/Normansrule/world-predictor"
COMMIT = "__COMMIT__"  # the Pages workflow swaps in the deployed commit; links fall back to main

CADENCE = {
    "weekly": "Every Monday 06:00 UTC (.github/workflows/predict.yml), or on demand",
    "monthly": "1st of each month 07:00 UTC, or on demand with the backtest box ticked",
}

STAGES = [
    {
        "id": "catalog", "name": "Series catalog",
        "plain": "The list of everything World Predictor forecasts, and where each series comes from.",
        "code": [("src/psychohistory/catalog.py", "SeriesSpec"), ("src/psychohistory/catalog.py", "CATALOG")],
        "input": "Nothing: edited by hand.",
        "output": "SeriesSpec(id, domain, source, params, freq, horizon, scale)",
        "rule": "One entry per series. Horizons: 28 days (news, Wikipedia), 21 trading days (markets), 3 years (OWID).",
        "cadence": "Changes only with a commit.",
        "failure": "An unknown id raises KeyError; composites must name series that exist.",
        "tests": ["test_catalog_ids_are_unique_and_composites_resolve"],
        "runs": "Python, anywhere",
    },
    {
        "id": "fetch", "name": "Fetch and cache",
        "plain": "Downloads each series from its public source and keeps a dated copy on disk.",
        "code": [("src/psychohistory/data/__init__.py", "fetch"), ("src/psychohistory/data/http.py", "get"),
                 ("src/psychohistory/data/gdelt.py", "fetch"), ("src/psychohistory/data/markets.py", "fetch"),
                 ("src/psychohistory/data/wikipedia.py", "fetch"), ("src/psychohistory/data/owid.py", "fetch"),
                 ("src/psychohistory/cli.py", "_load")],
        "input": "SeriesSpec",
        "output": "Date-indexed values, cached as data/<domain>/<id>.csv (not committed: Yahoo's terms)",
        "rule": "Drop missing values, sort by date, keep the last of any duplicate date. Missing stays missing, never zero.",
        "cadence": CADENCE["weekly"],
        "failure": "A source that fails is skipped and the run carries on; the reason is written to results/run_status.json. "
                   "GDELT calls are paced 6 s apart and back off on HTTP 429. A composite needs at least two members.",
        "tests": ["test_gdelt_retries_when_rate_limited", "test_owid_reads_short_lowercase_columns",
                  "test_composite_survives_a_missing_member", "test_composite_scales_members_to_their_mean",
                  "test_skipped_series_are_recorded"],
        "runs": "GitHub Actions (predict workflow) or your computer",
    },
    {
        "id": "context", "name": "Context window",
        "plain": "Cuts the history down to the part the model is allowed to read: the past only.",
        "code": [("src/psychohistory/ledger.py", "predict"), ("src/psychohistory/backtest.py", "MAX_CONTEXT")],
        "input": "The full cached series",
        "output": "The last 1,024 values or fewer",
        "rule": "Live forecasts read everything up to the newest value; backtests read only up to each past origin.",
        "cadence": "Every forecast",
        "failure": "Too-short series are not backtested (logged as a warning).",
        "tests": ["test_backtest_never_sees_the_future"],
        "runs": "Python",
    },
    {
        "id": "model", "name": "TimesFM 2.5",
        "plain": "Google Research's pretrained forecasting model reads the context and returns a range for every step ahead.",
        "code": [("src/psychohistory/models.py", "TimesFM25Forecaster"), ("src/psychohistory/models.py", "load_model")],
        "input": "Context arrays and a horizon",
        "output": "Forecast: a middle path and nine deciles (10%..90%) per step",
        "rule": "Zero-shot: checkpoint google/timesfm-2.5-200m-pytorch, never trained on this project's data.",
        "cadence": "Every forecast",
        "failure": "Stops with an install hint if TimesFM is missing. Nothing is shown about its internal reasoning: only inputs and outputs.",
        "tests": ["test_timesfm25_wrapper_maps_deciles", "test_load_model_is_cached"],
        "runs": "GitHub Actions on CPU, or your computer",
    },
    {
        "id": "seldon", "name": "Seldon, our own forecaster",
        "plain": "The challenger: four simple laws of crowd behaviour plus a weekly rhythm, each law voting by how well it predicted this series before.",
        "code": [("src/psychohistory/seldon.py", "predict"), ("src/psychohistory/seldon.py", "convene"),
                 ("src/psychohistory/seldon.py", "find_cycle"), ("src/psychohistory/seldon.py", "SeldonForecaster")],
        "input": "The same context arrays and horizon TimesFM gets",
        "output": "Forecast rows with model = seldon, sealed and scored next to the TimesFM rows",
        "rule": "Inertia, drift, momentum and reversion each forecast the series with its weekly rhythm taken out; 16 replays "
                "of the series' own past set their votes (1 / error^4) and the 80% range, and the rhythm is laid back on top. "
                "Learns only from data before the forecast date.",
        "cadence": CADENCE["weekly"],
        "failure": "With too little history to replay, every law gets an equal vote and the range is a random walk's.",
        "tests": ["test_seldon_follows_a_weekly_rhythm_and_a_trend", "test_seldon_never_peeks_past_the_forecast_date",
                  "test_seldon_range_is_honest_on_a_random_walk", "test_seldon_handles_short_and_negative_series",
                  "test_head_to_head_counts_series_won_on_the_same_windows"],
        "runs": "Python (numpy only), beside TimesFM",
    },
    {
        "id": "seal", "name": "Seal the forecast",
        "plain": "Writes the forecast down with today's date before the future happens.",
        "code": [("src/psychohistory/ledger.py", "predict"), ("src/psychohistory/ledger.py", "append"),
                 ("src/psychohistory/metrics.py", "prob_above")],
        "input": "Forecast and the newest observed value",
        "output": "Rows in predictions/ledger.csv: made_on, last_date, last_value, step, target_date, q10, q50, q90, p_up",
        "rule": "The chance of ending higher is read off the deciles by interpolation, capped at 5% and 95%.",
        "cadence": CADENCE["weekly"],
        "failure": "Rows are only appended, never edited, so a sealed forecast cannot be changed after the fact.",
        "tests": ["test_ledger_predict_then_score", "test_prob_above_reads_the_deciles", "test_latest_picks_newest_run_and_final_step"],
        "runs": "GitHub Actions; the ledger is committed to the repository",
    },
    {
        "id": "score", "name": "Open the vault",
        "plain": "When a target date arrives, puts what really happened next to what was sealed.",
        "code": [("src/psychohistory/ledger.py", "score"), ("src/psychohistory/story.py", "track_record"),
                 ("src/psychohistory/web.py", "opened_payload")],
        "input": "Ledger rows and the newest data",
        "output": "predictions/scored.csv: actual, abs_error, in_band80, direction_correct, brier",
        "rule": "A row is scored only once its target date is in the data. Brier compares the chance it gave with what happened.",
        "cadence": CADENCE["weekly"],
        "failure": "Rows whose date has not arrived, or whose value is missing, wait unscored.",
        "tests": ["test_ledger_predict_then_score", "test_time_vault_track_record", "test_opened_forecasts_flag_values_sealed_before_release"],
        "runs": "GitHub Actions",
    },
    {
        "id": "backtest", "name": "Backtest",
        "plain": "Replays the past: forecasts from old dates, scored against what followed, next to simple guesses.",
        "code": [("src/psychohistory/backtest.py", "backtest_series"), ("src/psychohistory/backtest.py", "origins"),
                 ("src/psychohistory/backtest.py", "summarize"), ("src/psychohistory/metrics.py", "score")],
        "input": "Cached series and the models",
        "output": "results/backtest_windows.csv, backtest_summary.csv, skill_by_step.csv, backtest_paths.csv",
        "rule": "12 origins spaced one horizon apart. Skill = 1 - MAE(model) / MAE(naive). Under 2% either way counts as no edge.",
        "cadence": CADENCE["monthly"],
        "failure": "Series too short for the windows are left out, and a test checks no window sees its own future.",
        "tests": ["test_backtest_never_sees_the_future", "test_drift_beats_naive_on_a_trend",
                  "test_skill_by_step_shows_drift_advantage_growing_with_horizon", "test_perfect_forecast_scores_zero_error",
                  "test_brier_rewards_confident_correct_calls"],
        "runs": "GitHub Actions or your computer",
    },
    {
        "id": "publish", "name": "Publish to the app",
        "plain": "Packs the results into one file the web app reads, and GitHub Pages serves it.",
        "code": [("src/psychohistory/web.py", "build_payload"), ("src/psychohistory/web.py", "track_payload"),
                 ("src/psychohistory/web.py", "write_data_js"), ("src/psychohistory/story.py", "EDGE"), (".github/workflows/pages.yml", None)],
        "input": "Results, ledger, scores and run status",
        "output": "results/web/data.js (window.WP_DATA), copied to app/data/data.js on Pages",
        "rule": "Only numbers produced by a run are shown; demo data is marked as demo everywhere it appears.",
        "cadence": "After every predict run, and on every push to main",
        "failure": "With no results yet the app shows labelled demo data instead.",
        "tests": ["test_web_app_data_and_site", "test_demo_payload_is_marked_and_complete", "test_scorecard_shows_numbers_or_placeholders"],
        "runs": "GitHub Actions, then GitHub Pages",
    },
]

# Data flow between stages, for the explorer's arrows.
EDGES = [("catalog", "fetch"), ("fetch", "context"), ("context", "model"), ("context", "seldon"), ("model", "seal"),
         ("seldon", "seal"), ("seal", "score"), ("score", "publish"), ("fetch", "backtest"), ("backtest", "publish")]

FREQ = {"D": "daily", "B": "trading days", "YS": "yearly"}


def line_of(path: str, symbol: str | None) -> int | None:
    """Line where ``symbol`` is defined in ``path`` (a def, class or top-level name), or None."""
    if symbol is None:
        return None
    pattern = re.compile(rf"^(?:def {symbol}\(|class {symbol}\b|{symbol}\s*[:=])")
    for number, text in enumerate((ROOT / path).read_text().splitlines(), start=1):
        if pattern.match(text):
            return number
    return None


def test_lines() -> dict[str, int]:
    text = (ROOT / "tests" / "test_pipeline.py").read_text().splitlines()
    return {m.group(1): i for i, line in enumerate(text, start=1) if (m := re.match(r"def (test_\w+)", line))}


def payload() -> dict:
    tests = test_lines()
    stages = []
    for stage in STAGES:
        code = [{"path": p, "symbol": s, "line": line_of(p, s)} for p, s in stage["code"]]
        stages.append({**stage, "code": code, "tests": [{"name": t, "line": tests.get(t)} for t in stage["tests"]]})
    series = [
        {"id": s.id, "domain": s.domain, "source": s.source, "params": s.params, "freq": FREQ.get(s.freq, s.freq),
         "horizon": s.horizon, "scale": s.scale, "description": s.description, "url": source_url(s)}
        for s in catalog.CATALOG
    ]
    return {"repo": REPO, "commit": COMMIT, "stages": stages, "edges": EDGES, "catalog": series}


def write_pipeline_js(path: Path) -> Path:
    path.write_text("// Generated by scripts/make_readme_art.py from src/psychohistory/inventory.py. Do not edit.\n"
                    f"window.WP_PIPELINE={json.dumps(payload(), separators=(',', ':'))};\n")
    return path


def architecture_md() -> str:
    """docs/ARCHITECTURE.md: the same inventory as a page you can read on GitHub."""
    data = payload()
    test_link = lambda t: f"[`{t['name']}`]({REPO}/blob/main/tests/test_pipeline.py#L{t['line']})"  # noqa: E731
    link = lambda c: f"[`{c['path']}`{' · ' + c['symbol'] if c['symbol'] else ''}]({REPO}/blob/main/{c['path']}{'#L' + str(c['line']) if c['line'] else ''})"  # noqa: E731
    out = [
        "# Architecture",
        "",
        "<!-- Generated by scripts/make_readme_art.py from src/psychohistory/inventory.py. Edit that file, not this one. -->",
        "",
        "Every forecast World Predictor shows passes through the stages below. The web app's",
        "[Follow one result](https://normansrule.github.io/world-predictor/app/#trace) view walks one real series",
        "through the same stages, with links pinned to the deployed commit.",
        "",
        "```mermaid",
        "flowchart LR",
        *[f"  {s['id']}[{s['name']}]" for s in data["stages"]],
        *[f"  {a} --> {b}" for a, b in data["edges"]],
        "```",
        "",
        "Arrows show data being handed on, not cause and effect.",
        "",
    ]
    for i, s in enumerate(data["stages"], start=1):
        out += [
            f"## {i}. {s['name']}",
            "",
            s["plain"],
            "",
            "| | |",
            "|---|---|",
            f"| **Code** | {'<br>'.join(link(c) for c in s['code'])} |",
            f"| **Takes** | {s['input']} |",
            f"| **Gives** | {s['output']} |",
            f"| **Rule** | {s['rule']} |",
            f"| **When** | {s['cadence']} |",
            f"| **If it fails** | {s['failure']} |",
            f"| **Runs in** | {s['runs']} |",
            f"| **Tests** | {', '.join(test_link(t) for t in s['tests'])} |",
            "| **Status** | Implemented |",
            "",
        ]
    out += [
        "## Not built",
        "",
        "These ideas from the design brief have no engine behind them yet, so the app does not pretend to run them:",
        "scenario comparisons (\"what if\"), maps (no series here is tied to a place), and agent simulations beyond the",
        "labelled toy crowd in the Crowd lab.",
        "",
    ]
    return "\n".join(out)
