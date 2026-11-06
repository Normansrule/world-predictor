"""Data loaders for every domain. Every loader returns a ``pandas.Series`` indexed by date."""

from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import quote

import pandas as pd

from ..catalog import SeriesSpec, by_id
from . import gdelt, markets, owid, quakes, weather, wikipedia

log = logging.getLogger(__name__)

SOURCES = {
    "gdelt": gdelt.fetch,
    "yahoo": markets.fetch,
    "wikipedia": wikipedia.fetch,
    "owid": owid.fetch,
    "openmeteo": weather.city,
    "reanalyzer": weather.world,
    "seaice": weather.sea_ice,
    "usgs": quakes.fetch,
}

DEFAULT_CACHE = Path("data")


def cache_path(spec: SeriesSpec, cache_dir: Path = DEFAULT_CACHE) -> Path:
    return Path(cache_dir) / spec.domain / f"{spec.id}.csv"


def source_url(spec: SeriesSpec) -> str | None:
    """A public page where anyone can look at the same numbers this series is built from."""
    p = spec.params
    if spec.source == "gdelt":
        return f"{gdelt.API}?query={quote(p['query'])}&mode=timelinevol&format=html"
    if spec.source == "yahoo":
        return f"https://finance.yahoo.com/quote/{quote(p['ticker'], safe='')}"
    if spec.source == "wikipedia":
        return f"https://pageviews.wmcloud.org/?project=en.wikipedia.org&pages={quote(p['article'])}"
    if spec.source == "owid":
        return f"{owid.GRAPHER}/{p['slug']}"
    if spec.source == "openmeteo":
        return f"https://open-meteo.com/en/docs/historical-weather-api#latitude={p['latitude']}&longitude={p['longitude']}"
    if spec.source == "reanalyzer":
        return "https://climatereanalyzer.org/clim/t2_daily/" if p.get("dataset", "air") == "air" else "https://climatereanalyzer.org/clim/sst_daily/"
    if spec.source == "seaice":
        return "https://nsidc.org/arcticseaicenews/charctic-interactive-sea-ice-graph/"
    if spec.source == "usgs":
        return f"https://earthquake.usgs.gov/earthquakes/map/?extent=-89,-180&extent=89,180&magnitude={p.get('min_magnitude', 4.5)}"
    return None  # composites are built from the member series


def fetch(spec: SeriesSpec, cache_dir: Path = DEFAULT_CACHE, refresh: bool = False) -> pd.Series:
    """Fetch one series, reading from / writing to a CSV cache so runs are reproducible."""
    path = cache_path(spec, cache_dir)
    if path.exists() and not refresh:
        return load_csv(path)
    if spec.source == "composite":
        # Members come earlier in the catalog, so a refresh has already updated their caches.
        series = composite(_members(spec, cache_dir))
    else:
        series = SOURCES[spec.source](**spec.params)
    series = series.dropna().sort_index()
    series = series[~series.index.duplicated(keep="last")]
    series.name = spec.id
    path.parent.mkdir(parents=True, exist_ok=True)
    series.to_frame("value").to_csv(path, index_label="date")
    log.info("fetched %s: %d points (%s .. %s)", spec.id, len(series), series.index[0].date(), series.index[-1].date())
    return series


def _members(spec: SeriesSpec, cache_dir: Path) -> list[pd.Series]:
    """Members that could be fetched; a composite still means something if one topic is missing."""
    members = []
    for member in spec.params["members"]:
        try:
            members.append(fetch(by_id(member), cache_dir))
        except Exception as error:  # noqa: BLE001 - one bad member should not sink the aggregate
            log.warning("composite %s: leaving out %s (%s)", spec.id, member, error)
    if len(members) < 2:
        raise ValueError(f"composite {spec.id} needs at least two members, got {len(members)}")
    return members


def composite(members: list[pd.Series]) -> pd.Series:
    """Average of member series over their common dates, each divided by its own mean so that
    no single member dominates. This is the "aggregate" Seldon says should be predictable."""
    frame = pd.concat(members, axis=1, join="inner").dropna()
    if frame.empty:
        raise ValueError("composite members have no dates in common")
    return (frame / frame.mean()).mean(axis=1)


def load_csv(path: Path) -> pd.Series:
    frame = pd.read_csv(path, parse_dates=["date"], index_col="date")
    series = frame["value"].astype(float)
    series.name = Path(path).stem
    return series
