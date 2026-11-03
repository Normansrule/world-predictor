"""The world wire: what the news says right now about every topic the project forecasts.

The forecasts are numbers; the wire puts words beside them. Once a week (``psychohistory wire``,
run by the weekly workflow) the newest English-language headlines for each topic are taken from
the GDELT Project's article list and written to ``results/wire.json``, which the app's World
terminal shows beside each series. Headlines are context, not inputs: no model reads them.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from . import catalog
from .data import gdelt

WIRE = Path("results/wire.json")
RECORDS = 6

# What to ask GDELT for each series that is not itself a news query.
QUERIES = {
    "sp500": '"S&P 500"', "msci_world": '"global stocks"', "nasdaq100": "Nasdaq", "aapl": '("Apple Inc" OR iPhone)',
    "nvda": "Nvidia", "tsla": "Tesla", "xom": '"Exxon Mobil"', "gold": '"gold price"', "silver": '"silver price"',
    "oil_wti": '"oil prices"', "copper": '"copper price"', "bitcoin": "bitcoin",
    "us10y": '"Treasury yields"', "tlt": '"bond market"', "vix": '"stock market" fear',
    "wiki_llm": '"language model"', "wiki_ai": '"artificial intelligence"', "wiki_quantum": '"quantum computing"',
    "wiki_crispr": "CRISPR", "wiki_ev": '"electric vehicles"', "wiki_fusion": '"fusion energy"',
    "wiki_humanoid": '"humanoid robot"', "adoption_solar": '"solar power"', "adoption_wind": '"wind power"',
}

log = logging.getLogger(__name__)


def query_for(spec: catalog.SeriesSpec) -> str | None:
    if spec.source == "gdelt":
        return spec.params.get("query")
    return QUERIES.get(spec.id)


BUDGET = 600.0  # seconds the whole wire may take: GDELT's back-off can otherwise stall a run for hours


def fetch(specs: list[catalog.SeriesSpec], records: int = RECORDS, fetcher=gdelt.headlines,
          budget: float = BUDGET, clock=time.monotonic) -> dict:
    """Headlines per series; a topic GDELT cannot answer is left out, never filled in. Once
    ``budget`` seconds have gone, the remaining topics are skipped (and keep their last headlines
    when the wire is written with ``keep_old``)."""
    topics, failed = {}, {}
    start = clock()
    for spec in specs:
        query = query_for(spec)
        if not query:
            continue
        if clock() - start > budget:
            failed[spec.id] = "skipped: the wire's time budget ran out"
            continue
        try:
            articles = fetcher(query, records=records)
        except Exception as exc:  # one busy query should not stop the wire
            log.warning("wire: skipping %s: %s", spec.id, exc)
            failed[spec.id] = f"{type(exc).__name__}: {exc}"[:200]
            continue
        if articles:
            topics[spec.id] = {"query": query, "articles": articles}
    return {"fetched": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "topics": topics, "failed": failed}


def write(wire: dict, path: Path = WIRE, keep_old: bool = True) -> Path:
    """Save the wire. A topic that failed this time keeps last week's headlines, marked as such."""
    if keep_old and path.exists():
        try:
            old = json.loads(path.read_text())
        except ValueError:
            old = {}
        for sid, topic in (old.get("topics") or {}).items():
            if sid in wire["failed"] and sid not in wire["topics"]:
                wire["topics"][sid] = {**topic, "stale": True}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(wire, indent=1, ensure_ascii=False) + "\n")
    return path


def read(path: Path = WIRE) -> dict | None:
    try:
        return json.loads(path.read_text()) if path.exists() else None
    except ValueError:
        return None
