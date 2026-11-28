"""Rehearse the weekly run's offline steps on long synthetic history, before pushing.

The sandbox a change is made in usually holds about a year of history, but the weekly run on
GitHub reads ten years or more. A step that loops over history can be quick on one year and take
an hour on eleven (the spike backtest once did). This script builds a throwaway copy of the
project's ledgers and results, fills its data cache with seeded synthetic series as long as the
real ones (daily series from mid-2015, market days from 2015, yearly series from 1990), runs every
step of the weekly run that needs no download and no model, and times each one against a budget.

    python scripts/rehearse.py                 # every step, default budgets
    python scripts/rehearse.py --keep          # keep the temporary folder to look inside
    python scripts/rehearse.py --years 15      # longer still

Exit status 1 if any step failed or ran over its budget. The numbers it prints are timings, not
results: the series are synthetic, so nothing here says anything about the world.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from psychohistory import catalog, data  # noqa: E402

# The weekly run's offline steps in their order in .github/workflows/predict.yml, each with the
# most seconds it may take here. GitHub's runners are slower than most laptops, so the budgets
# leave room; a step that needs a download (fetch, bets, wire) or a model (predict, backtest)
# is not rehearsed, and the race grows its ten years with a cheap model in TimesFM's place.
STEPS = [
    ("verify", ["verify"], 60),
    ("score", ["score"], 300),
    ("spikes", ["spikes", "--seal", "--save", "results/spike_backtest.csv"], 180),
    ("monitor", ["monitor", "--save", "results/monitor.csv"], 300),
    ("brief", ["brief", "--write"], 120),
    ("report", ["report"], 300),
    ("vol", ["vol", "--backtest"], 600),
    ("events", ["events", "--backtest"], 600),
    ("hype", ["hype", "--save", "results/hype_backtest.csv"], 180),
    ("race", ["race", "--stand-in", "naive", "--grow", "400"], 600),
    ("fastlane", ["fastlane"], 180),  # the lead-lag scan, fear clock and move sizes over every market  # ten years at once, a cheap model in TimesFM's place
    ("export", ["export"], 300),
]


def synthetic(spec: catalog.SeriesSpec, years: int, end: pd.Timestamp, rng: np.random.Generator) -> pd.Series:
    """One positive series shaped roughly like its kind: attention with bursts that fade, prices as
    a random walk, weather with seasons, yearly series as slow trends."""
    if spec.freq == "YS":
        index = pd.date_range("1990-01-01", end, freq="YS")
        values = 100 * np.exp(np.cumsum(rng.normal(0.02, 0.05, len(index))))
        return pd.Series(values, index)
    start = end - pd.DateOffset(years=years)
    index = pd.bdate_range(start, end) if spec.freq == "B" else pd.date_range(start, end, freq="D")
    n = len(index)
    if spec.domain in ("news", "politics", "tech"):
        level = np.exp(np.cumsum(rng.normal(0, 0.03, n)) * 0.3) * 1000
        bursts = np.zeros(n)
        for day in rng.choice(n, size=max(1, n // 90), replace=False):
            size = rng.uniform(1.5, 8)
            tail = np.arange(n - day)
            bursts[day:] += size * np.exp(-tail / rng.uniform(1, 6))
        return pd.Series(level * (1 + bursts) * np.exp(rng.normal(0, 0.15, n)), index)
    if spec.domain == "weather":
        season = np.sin(2 * np.pi * index.dayofyear / 365.25)
        return pd.Series(20 + 10 * season + rng.normal(0, 2, n), index)
    return pd.Series(100 * np.exp(np.cumsum(rng.normal(0.0003, 0.012, n))), index)


def build(work: Path, years: int, seed: int = 0) -> int:
    """Copy the ledgers and results into ``work`` and write a synthetic cache for every series."""
    for folder in ("predictions", "results"):
        if (ROOT / folder).exists():
            shutil.copytree(ROOT / folder, work / folder)
    end = pd.Timestamp.now().normalize() - pd.Timedelta(days=1)
    rng = np.random.default_rng(seed)
    for spec in catalog.CATALOG:
        path = data.cache_path(spec, work / "data")
        path.parent.mkdir(parents=True, exist_ok=True)
        synthetic(spec, years, end, rng).to_frame("value").to_csv(path, index_label="date")
    return len(catalog.CATALOG)


def run(work: Path, steps=STEPS, scale: float = 1.0) -> list[dict]:
    """Run each step in ``work`` and time it. A step is over budget past ``budget * scale`` seconds."""
    out = []
    for name, argv, budget in steps:
        began = time.perf_counter()
        try:
            done = subprocess.run([sys.executable, "-m", "psychohistory.cli", *argv], cwd=work,
                                  capture_output=True, text=True, timeout=budget * scale * 3)
            code, tail = done.returncode, (done.stderr or done.stdout).strip().splitlines()[-3:]
        except subprocess.TimeoutExpired:
            code, tail = "timeout", []
        seconds = time.perf_counter() - began
        out.append({"step": name, "seconds": round(seconds, 1), "budget": budget * scale,
                    "ok": code == 0 and seconds <= budget * scale, "code": code, "tail": tail})
    return out


def describe(rows: list[dict]) -> str:
    lines = [f"{'step':<10}{'seconds':>9}{'budget':>9}  result"]
    for r in rows:
        if r["ok"]:
            verdict = "ok"
        elif r["code"] == "timeout":
            verdict = "OVER BUDGET (stopped at three times the budget)"
        elif r["code"] != 0:
            verdict = "FAILED " + " | ".join(r["tail"])
        else:
            verdict = "OVER BUDGET"
        lines.append(f"{r['step']:<10}{r['seconds']:>9.1f}{r['budget']:>9.0f}  {verdict}")
    lines.append(f"\nTotal {sum(r['seconds'] for r in rows):.0f} s. "
                 + ("Every step finished within its budget." if all(r["ok"] for r in rows)
                    else "Fix the steps marked above before pushing."))
    return "\n".join(lines)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--years", type=int, default=11, help="years of daily history (default 11)")
    p.add_argument("--keep", action="store_true", help="keep the temporary folder and print where it is")
    p.add_argument("--only", action="append", help="rehearse only this step (repeatable)")
    args = p.parse_args(argv)
    steps = [s for s in STEPS if not args.only or s[0] in args.only]
    work = Path(tempfile.mkdtemp(prefix="rehearse-"))
    try:
        print(f"Writing {build(work, args.years)} synthetic series ({args.years} years) in {work} ...")
        rows = run(work, steps)
        print(describe(rows))
        return 0 if all(r["ok"] for r in rows) else 1
    finally:
        if args.keep:
            print(f"Kept {work}")
        else:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
