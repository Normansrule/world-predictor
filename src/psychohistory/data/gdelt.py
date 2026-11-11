"""World events in the news, from the GDELT Project DOC 2.0 API (https://www.gdeltproject.org/).

``timelinevol`` returns, per day, the share of all worldwide online news coverage that matched
the query. It is a measure of collective attention: how much of humanity's news diet a topic
occupies, which is as close to a psychohistorical aggregate as public data gets.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import pandas as pd
import requests

from .http import get

API = "https://api.gdeltproject.org/api/v2/doc/doc"
MIN_GAP = 6.0  # GDELT asks for at most one request every 5 seconds
BACKOFF = (15.0, 30.0, 60.0, 120.0)
BUDGET = 600.0  # seconds one process may spend waiting on GDELT's back-off; after that a busy answer is final

log = logging.getLogger(__name__)
_last_call = 0.0
_waited = 0.0  # back-off seconds spent so far in this process


class Busy(RuntimeError):
    """GDELT is still rate-limiting and the back-off budget is spent."""


def _request(params: dict) -> dict:
    """GET with GDELT's pacing. When rate-limited it answers 429, or 200 with a plain-text
    notice instead of JSON, so both are retried after a growing pause, until the process has
    spent ``BUDGET`` seconds of back-off in all; after that a busy answer raises ``Busy`` at once
    (the caller falls back to its cached copy)."""
    global _last_call, _waited
    for attempt, pause in enumerate((0.0, *BACKOFF)):
        if pause:
            if _waited + pause > BUDGET:  # a long run must not spend its hours waiting on one source
                raise Busy(f"GDELT still busy after {_waited:.0f}s of back-off this run (budget {BUDGET:.0f}s)")
            log.info("GDELT busy, retrying in %.0fs", pause)
            time.sleep(pause)
            _waited += pause
        time.sleep(max(0.0, _last_call + MIN_GAP - time.monotonic()))
        _last_call = time.monotonic()
        try:
            return get(API, params=params, retries=1).json()
        except (requests.HTTPError, ValueError) as error:
            status = getattr(getattr(error, "response", None), "status_code", None)
            if isinstance(error, requests.HTTPError) and status != 429:
                raise
            if attempt == len(BACKOFF):
                raise
    raise RuntimeError("unreachable")


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
    payload = _request(params)
    timeline = payload.get("timeline") or []
    if not timeline:
        raise ValueError(f"GDELT returned no timeline for query {query!r}")
    points = timeline[0]["data"]
    index = pd.to_datetime([p["date"] for p in points], format="%Y%m%dT%H%M%SZ").tz_localize(None)
    series = pd.Series([float(p["value"]) for p in points], index=index)
    # Resample to calendar days in case GDELT returned a finer resolution.
    return series.resample("D").mean().dropna()


def headlines(query: str, records: int = 6, timespan: str = "4d") -> list[dict]:
    """The newest English-language articles matching ``query`` (GDELT's ``ArtList`` mode): title,
    link, site, source country and when GDELT first saw it (UTC)."""
    params = {"query": f"{query} sourcelang:english", "mode": "ArtList", "format": "json",
              "maxrecords": records, "timespan": timespan, "sort": "DateDesc"}
    out = []
    for item in _request(params).get("articles") or []:
        title, url = (item.get("title") or "").strip(), item.get("url") or ""
        if not title or not url.startswith(("http://", "https://")):
            continue
        seen = item.get("seendate") or ""
        try:
            seen = datetime.strptime(seen, "%Y%m%dT%H%M%SZ").strftime("%Y-%m-%dT%H:%MZ")
        except ValueError:
            seen = ""
        out.append({"title": title, "url": url, "domain": item.get("domain") or "",
                    "country": item.get("sourcecountry") or "", "seen": seen})
    return out
