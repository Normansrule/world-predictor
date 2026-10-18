"""Technology adoption curves from Our World in Data (https://ourworldindata.org/), CC BY 4.0.

These are slow, annual series (e.g. share of electricity from solar, share of people online).
They test the other half of Seldon's claim: long-run, large-scale trends.
"""

from __future__ import annotations

import io

import pandas as pd

from .http import get

GRAPHER = "https://ourworldindata.org/grapher"


def fetch(slug: str, entity: str = "World", column: str | None = None) -> pd.Series:
    text = get(f"{GRAPHER}/{slug}.csv", params={"v": 1, "csvType": "full", "useColumnShortNames": "true"}).text
    frame = pd.read_csv(io.StringIO(text))
    frame = frame[frame["Entity"] == entity]
    if frame.empty:
        raise ValueError(f"OWID chart {slug!r} has no rows for {entity!r}")
    if column is None:
        candidates = [c for c in frame.columns if c not in ("Entity", "Code", "Year", "Day")]
        numeric = [c for c in candidates if pd.api.types.is_numeric_dtype(frame[c])]
        if not numeric:
            raise ValueError(f"OWID chart {slug!r} has no numeric column")
        column = numeric[0]
    index = pd.to_datetime(frame["Year"].astype(int).astype(str), format="%Y")
    return pd.Series(frame[column].astype(float).to_numpy(), index=index)
