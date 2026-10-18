"""Public interest in technologies, from Wikimedia's Pageviews API
(https://wikitech.wikimedia.org/wiki/Analytics/AQS/Pageviews). Data starts July 2015.

Daily views of an English Wikipedia article are a free, long-running proxy for how much the
world is paying attention to a technology, similar to Google Trends but with absolute counts.
"""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import quote

import pandas as pd

from .http import get

API = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article"


def fetch(article: str, project: str = "en.wikipedia", start: str = "2015-07-01") -> pd.Series:
    start_s = pd.Timestamp(start).strftime("%Y%m%d00")
    end_s = datetime.now(timezone.utc).strftime("%Y%m%d00")
    url = f"{API}/{project}/all-access/user/{quote(article, safe='')}/daily/{start_s}/{end_s}"
    items = get(url).json().get("items", [])
    if not items:
        raise ValueError(f"No pageviews for {article!r}")
    index = pd.to_datetime([item["timestamp"][:8] for item in items], format="%Y%m%d")
    return pd.Series([float(item["views"]) for item in items], index=index)
