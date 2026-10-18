"""Shared HTTP helper with a descriptive User-Agent (required by Wikimedia) and polite retries."""

from __future__ import annotations

import time

import requests

USER_AGENT = "world-predictor/0.1 (https://github.com/Normansrule/world-predictor; research project)"


def get(url: str, params: dict | None = None, retries: int = 4, timeout: float = 60.0) -> requests.Response:
    delay = 2.0
    for attempt in range(retries):
        response = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        if response.status_code not in (429, 500, 502, 503, 504) or attempt == retries - 1:
            response.raise_for_status()
            return response
        time.sleep(delay)
        delay *= 2
    raise RuntimeError("unreachable")
