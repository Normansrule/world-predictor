"""World events in the news, from the GDELT Project DOC 2.0 API (https://www.gdeltproject.org/).

``timelinevol`` returns, per day, the share of all worldwide online news coverage that matched
the query. It is a measure of collective attention: how much of humanity's news diet a topic
occupies, which is as close to a psychohistorical aggregate as public data gets.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from .http import get

API = "https://api.gdeltproject.org/api/v2/doc/doc"


def fetch(query: str, start: str = "2017-01-01", mode: str = "timelinevol") -> pd.Series:
    start_dt = pd.Timestamp(start).strftime("%Y%m%d%H%M%S")
    end_dt = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    params = {
        "query": query,
        "mode": mode,
        "format": "json",
        "STARTDATETIME": start_dt,
        "ENDDATETIME": end_dt,
        "TIMELINESMOOTH": 0,
    }
    payload = get(API, params=params).json()
    timeline = payload.get("timeline") or []
    if not timeline:
        raise ValueError(f"GDELT returned no timeline for query {query!r}")
    points = timeline[0]["data"]
    index = pd.to_datetime([p["date"] for p in points], format="%Y%m%dT%H%M%SZ").tz_localize(None)
    series = pd.Series([float(p["value"]) for p in points], index=index)
    # Resample to calendar days in case GDELT returned a finer resolution.
    return series.resample("D").mean().dropna()
