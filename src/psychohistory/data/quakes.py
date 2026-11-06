"""Earthquakes worldwide, from the U.S. Geological Survey's ComCat catalogue
(https://earthquake.usgs.gov/fdsnws/event/1/), public domain.

The series is the number of quakes of a given magnitude or more each day, anywhere on Earth. It is
a hard test: single quakes are famously unpredictable, so a forecaster should only be able to learn
the average rate and the clustering of aftershocks. Any skill beyond that would be news.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone

import pandas as pd

from .http import get

API = "https://earthquake.usgs.gov/fdsnws/event/1/query"


def daily_counts(times: pd.Series, start: str, end: str) -> pd.Series:
    """Quakes per UTC day, with the quiet days (no quake at all) written as zero."""
    days = pd.to_datetime(times, utc=True).dt.tz_localize(None).dt.normalize()
    counts = days.value_counts().sort_index()
    index = pd.date_range(pd.Timestamp(start), pd.Timestamp(end), freq="D")
    return counts.reindex(index, fill_value=0).astype(float)


def fetch(min_magnitude: float = 4.5, start: str = "2016-01-01") -> pd.Series:
    """Daily count of quakes of ``min_magnitude`` or more. One request per year keeps each answer
    under ComCat's 20,000-event limit."""
    today = datetime.now(timezone.utc).date()
    end = pd.Timestamp(today) - pd.Timedelta(days=1)  # today is not over yet
    frames = []
    for year in range(pd.Timestamp(start).year, today.year + 1):
        lo = max(pd.Timestamp(start), pd.Timestamp(f"{year}-01-01"))
        hi = min(end + pd.Timedelta(days=1), pd.Timestamp(f"{year + 1}-01-01"))
        if lo >= hi:
            continue
        text = get(API, params={"format": "csv", "starttime": lo.strftime("%Y-%m-%d"), "endtime": hi.strftime("%Y-%m-%d"),
                                "minmagnitude": min_magnitude, "orderby": "time-asc", "limit": 20000}).text
        frame = pd.read_csv(io.StringIO(text), usecols=["time"]) if text.strip() else pd.DataFrame({"time": []})
        frames.append(frame)
    times = pd.concat(frames, ignore_index=True)["time"] if frames else pd.Series([], dtype=str)
    if times.empty:
        raise ValueError("USGS returned no earthquakes")
    return daily_counts(times, start, end.strftime("%Y-%m-%d"))
