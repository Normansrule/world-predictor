"""Weather and the state of the planet, from three free, keyless sources.

* Open-Meteo's historical weather API (https://open-meteo.com/, CC BY 4.0) gives each city's daily
  high, read from the ERA5 reanalysis and national weather services, a few days behind real time.
* Climate Reanalyzer (Climate Change Institute, University of Maine) publishes the whole world's
  daily mean surface air temperature (ERA5) and sea surface temperature (NOAA OISST v2.1).
* The National Snow and Ice Data Center's Sea Ice Index gives the Arctic's daily ice extent from
  satellites.

Every value is a measurement, so a forecast made today is settled against what the thermometers
and satellites record, the same way a market forecast is settled against the closing price.
"""

from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone

import pandas as pd

from .http import get

OPEN_METEO = "https://archive-api.open-meteo.com/v1/archive"
REANALYZER = "https://climatereanalyzer.org/clim"
REANALYZER_FILES = {
    "air": "t2_daily/json/era5_world_t2_day.json",
    "sst": "sst_daily/json_2clim/oisst2.1_world2_sst_day.json",
}
NSIDC = "https://noaadata.apps.nsidc.org/NOAA/G02135/{hemi}/daily/data/{h}_seaice_extent_daily_v{version}.csv"
NSIDC_VERSIONS = ("4.0", "3.0")  # the newest version first; the index moved to 4.0 in 2025


def city(latitude: float, longitude: float, variable: str = "temperature_2m_max", start: str = "2015-01-01") -> pd.Series:
    """One city's daily weather (by default the day's high in degrees Celsius)."""
    end = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    payload = get(OPEN_METEO, params={"latitude": latitude, "longitude": longitude, "start_date": start,
                                      "end_date": end, "daily": variable, "timezone": "UTC"}).json()
    daily = payload.get("daily") or {}
    if variable not in daily:
        raise ValueError(f"Open-Meteo returned no {variable!r} for ({latitude}, {longitude})")
    series = pd.Series(pd.to_numeric(daily[variable], errors="coerce"), index=pd.to_datetime(daily["time"]))
    # The archive answers with empty values for the last few days until the reanalysis catches up.
    return series.dropna()


def parse_reanalyzer(payload: list[dict], start: str = "2015-01-01") -> pd.Series:
    """Climate Reanalyzer's files hold one entry per year (``name`` "1979" ... and a few climatology
    lines such as "1982-2011 mean"), each with 366 daily values and nulls past the end."""
    parts = []
    for entry in payload:
        name = str(entry.get("name", ""))
        if not (len(name) == 4 and name.isdigit()):
            continue
        year = int(name)
        values = pd.to_numeric(pd.Series(entry.get("data") or [], dtype="object"), errors="coerce")
        days = pd.date_range(f"{year}-01-01", periods=len(values), freq="D")
        keep = days.year == year  # day 366 of a common year is padding
        parts.append(pd.Series(values.to_numpy()[keep], index=days[keep]))
    if not parts:
        raise ValueError("Climate Reanalyzer file has no yearly entries")
    series = pd.concat(parts).dropna().sort_index()
    return series[series.index >= pd.Timestamp(start)]


def world(dataset: str = "air", start: str = "2015-01-01") -> pd.Series:
    """The world's daily mean surface air temperature ("air") or sea surface temperature ("sst"), in degrees C."""
    return parse_reanalyzer(get(f"{REANALYZER}/{REANALYZER_FILES[dataset]}").json(), start)


def parse_sea_ice(text: str, start: str = "2015-01-01") -> pd.Series:
    """The Sea Ice Index CSV: a header row, a units row, then ``Year, Month, Day, Extent, ...``."""
    frame = pd.read_csv(io.StringIO(text), skipinitialspace=True)
    frame.columns = [str(c).strip().lower() for c in frame.columns]
    frame = frame[pd.to_numeric(frame["year"], errors="coerce").notna()]
    index = pd.to_datetime(dict(year=frame["year"].astype(int), month=frame["month"].astype(int), day=frame["day"].astype(int)))
    extent = pd.to_numeric(frame["extent"], errors="coerce")
    series = pd.Series(extent.to_numpy(), index=pd.DatetimeIndex(index)).dropna()
    series = series[series > 0]  # missing days are written as -9999
    return series[series.index >= pd.Timestamp(start)]


def sea_ice(hemisphere: str = "north", start: str = "2015-01-01") -> pd.Series:
    """Daily sea ice extent in millions of square kilometres."""
    error: Exception | None = None
    for version in NSIDC_VERSIONS:
        url = NSIDC.format(hemi=hemisphere, h=hemisphere[0].upper(), version=version)
        try:
            return parse_sea_ice(get(url, retries=2).text, start)
        except Exception as exc:  # noqa: BLE001 - try the older file name before giving up
            error = exc
    raise ValueError(f"Sea Ice Index unavailable: {error}")


def sea_ice_url(hemisphere: str = "north") -> str:
    return NSIDC.format(hemi=hemisphere, h=hemisphere[0].upper(), version=NSIDC_VERSIONS[0])
