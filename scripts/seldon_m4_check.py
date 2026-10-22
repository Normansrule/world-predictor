"""Check Seldon on public data it was not built for: the M4 competition's daily series.

The M4 competition (Makridakis, Spiliotis & Assimakopoulos, 2020) published 4,227 daily series with
a fixed 14-day test period. Seldon's few settings were chosen on series 0-499; this scores it on
series 500-1,999, which it never saw, against "no change", drift and (if statsforecast is
installed) AutoETS, with the same metrics as the backtest. TimesFM is not run here: compare with
the published leaderboards instead.

    python scripts/seldon_m4_check.py               # downloads about 96 MB from GitHub once
    python scripts/seldon_m4_check.py --first 500 --last 2000
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import requests

from psychohistory.metrics import score
from psychohistory.models import MODELS, classical_available

BASE = "https://raw.githubusercontent.com/Mcompetitions/M4-methods/master/Dataset"
HORIZON = 14


def download(name: str, cache: Path) -> Path:
    path = cache / name
    if not path.exists():
        cache.mkdir(parents=True, exist_ok=True)
        folder = "Train" if "train" in name else "Test"
        with requests.get(f"{BASE}/{folder}/{name}", stream=True, timeout=120) as r:
            r.raise_for_status()
            path.write_bytes(r.content)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--first", type=int, default=500)
    parser.add_argument("--last", type=int, default=2000)
    parser.add_argument("--cache", type=Path, default=Path("data/m4"))
    args = parser.parse_args()
    skip = range(1, args.first + 1)
    train = pd.read_csv(download("Daily-train.csv", args.cache), skiprows=skip, nrows=args.last - args.first)
    test = pd.read_csv(download("Daily-test.csv", args.cache), skiprows=skip, nrows=args.last - args.first)
    contexts = [row.iloc[1:].dropna().to_numpy(float)[-1024:] for _, row in train.iterrows()]
    actuals = [row.iloc[1:].to_numpy(float)[:HORIZON] for _, row in test.iterrows()]
    names = ["seldon", "naive", "drift"] + (["auto-ets"] if classical_available() else [])
    rows = []
    for name in names:
        forecasts = MODELS[name]().forecast(contexts, HORIZON)
        rows += [{"model": name, "series": i, **score(c, a, f)} for i, (c, a, f) in enumerate(zip(contexts, actuals, forecasts))]
    frame = pd.DataFrame(rows)
    naive = frame[frame["model"] == "naive"].set_index("series")["mase"]
    table = frame.groupby("model")[["mase", "pinball", "coverage80", "brier"]].mean()
    table["beat_naive"] = [(frame[frame["model"] == m].set_index("series")["mase"] < naive).mean() for m in table.index]
    print(f"M4 daily series {args.first}-{args.last - 1}, {HORIZON} days ahead (lower MASE and pinball are better):\n")
    print(table.sort_values("pinball").round(4).to_string())


if __name__ == "__main__":
    main()
