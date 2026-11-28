"""The series this project forecasts, grouped into five domains: world news, politics, markets,
technology, and weather and the planet.

``scale`` tags each series as an ``individual`` (one company, one topic, one article) or an
``aggregate`` (an index or a composite of many members). Seldon's central claim is that
aggregates are more predictable than individuals; the report compares the two directly.

Edit this file to add your own series.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SeriesSpec:
    id: str
    domain: str  # "news" | "politics" | "markets" | "tech" | "weather"
    source: str  # key of psychohistory.data.SOURCES, or "composite"
    params: dict = field(default_factory=dict)
    freq: str = "D"  # pandas frequency used to date future forecasts: "D", "B" or "YS"
    horizon: int = 28  # steps ahead to forecast
    scale: str = "individual"  # "individual" | "aggregate"
    description: str = ""
    extra_models: tuple[str, ...] = ()  # models that only make sense for this kind of series


def _news(id_, query, desc):
    return SeriesSpec(id_, "news", "gdelt", {"query": query}, "D", 28, "individual", desc)


def _stock(id_, ticker, desc, scale="individual"):
    return SeriesSpec(id_, "markets", "yahoo", {"ticker": ticker}, "B", 21, scale, desc)


def _wiki(id_, article, desc):
    return SeriesSpec(id_, "tech", "wikipedia", {"article": article}, "D", 28, "individual", desc)


def _politics(id_, query, desc):
    return SeriesSpec(id_, "politics", "gdelt", {"query": query}, "D", 28, "individual", desc)


def _city(id_, name, latitude, longitude):
    return SeriesSpec(id_, "weather", "openmeteo", {"latitude": latitude, "longitude": longitude}, "D", 14, "individual",
                      f"Daily high temperature in {name} (deg C, Open-Meteo)")


def _rain(id_, name, latitude, longitude):
    return SeriesSpec(id_, "weather", "openmeteo", {"latitude": latitude, "longitude": longitude, "variable": "precipitation_sum"},
                      "D", 14, "individual", f"Daily rain in {name} (mm, Open-Meteo)")


def _owid(id_, slug, desc):
    # Adoption curves also get the Bass diffusion model as a theory-driven rival.
    return SeriesSpec(id_, "tech", "owid", {"slug": slug}, "YS", 3, "aggregate", desc, ("bass",))


NEWS = [
    # A bare "war" never downloaded once in 18 runs (Oct to Nov 2026): GDELT kept refusing it, so
    # war coverage is matched on longer terms instead (see results/source_health.json).
    _news("news_war", '(warfare OR "armed conflict" OR airstrike OR "military offensive")',
          "Share of world news coverage about war: warfare, armed conflict, airstrikes, military offensives"),
    _news("news_election", '"election"', "Share of world news coverage mentioning elections"),
    _news("news_inflation", '"inflation"', "Share of world news coverage mentioning inflation"),
    _news("news_climate", '"climate change"', "Share of world news coverage mentioning climate change"),
    _news("news_pandemic", '(pandemic OR outbreak OR epidemic)', "Share of coverage about disease outbreaks"),
    _news("news_protest", '(protest OR protests)', "Share of world news coverage mentioning protests"),
    _news("news_ai", '"artificial intelligence"', "Share of world news mentioning artificial intelligence (GDELT)"),
    _news("news_housing", '("housing market" OR "house prices")', "Share of world news about housing markets and house prices (GDELT)"),
    _news("news_cyber", "(cyberattack OR ransomware)", "Share of world news about cyberattacks and ransomware (GDELT)"),
    _news("news_wildfire", "(wildfire OR drought)", "Share of world news about wildfires and droughts (GDELT)"),
    _news("news_energy", '("energy prices" OR "energy crisis")', "Share of world news about energy prices and energy crises (GDELT)"),
    _news("news_jobs", '(layoffs OR unemployment)', "Share of world news about layoffs and unemployment (GDELT)"),
    SeriesSpec(
        "news_composite",
        "news",
        "composite",
        {"members": ["news_war", "news_election", "news_inflation", "news_climate", "news_pandemic", "news_protest"]},
        "D",
        28,
        "aggregate",
        "Average of the news topics above, each scaled to its own mean",
    ),
]

MARKETS = [
    _stock("sp500", "^GSPC", "S&P 500 index", "aggregate"),
    _stock("msci_world", "URTH", "iShares MSCI World ETF (global equities)", "aggregate"),
    _stock("nasdaq100", "^NDX", "Nasdaq-100 index", "aggregate"),
    _stock("aapl", "AAPL", "Apple Inc."),
    _stock("nvda", "NVDA", "NVIDIA Corp."),
    _stock("tsla", "TSLA", "Tesla Inc."),
    _stock("xom", "XOM", "Exxon Mobil Corp."),
    _stock("msft", "MSFT", "Microsoft Corp."),
    _stock("amzn", "AMZN", "Amazon.com Inc."),
    _stock("googl", "GOOGL", "Alphabet Inc. (Google)"),
    _stock("meta", "META", "Meta Platforms Inc."),
    _stock("jpm", "JPM", "JPMorgan Chase & Co."),
    _stock("amd", "AMD", "Advanced Micro Devices Inc."),
    _stock("nflx", "NFLX", "Netflix Inc."),
    _stock("visa", "V", "Visa Inc."),
    _stock("wmt", "WMT", "Walmart Inc."),
    _stock("intc", "INTC", "Intel Corporation"),
    _stock("ko", "KO", "The Coca-Cola Company"),
    _stock("hsi", "^HSI", "Hang Seng (Hong Kong stocks)", "aggregate"),
    _stock("brk", "BRK-B", "Berkshire Hathaway (class B)"),
    _stock("nikkei", "^N225", "Nikkei 225 (Tokyo stocks)", "aggregate"),
    _stock("ftse", "^FTSE", "FTSE 100 (London stocks)", "aggregate"),
    _stock("dax", "^GDAXI", "DAX (Frankfurt stocks)", "aggregate"),
    _stock("gold", "GC=F", "Gold futures (USD/oz)"),
    _stock("silver", "SI=F", "Silver futures (USD/oz)"),
    # Bonds: the 10-year US Treasury yield (in percent, CBOE's ^TNX) and a long-Treasury fund's price.
    _stock("us10y", "^TNX", "US 10-year Treasury yield (%)", "aggregate"),
    _stock("tlt", "TLT", "iShares 20+ Year Treasury Bond ETF"),
    # Fear: the CBOE Volatility Index, the market's own price for the next month's swings.
    _stock("vix", "^VIX", "CBOE Volatility Index (VIX, the fear gauge)", "aggregate"),
    _stock("oil_wti", "CL=F", "WTI crude oil futures"),
    _stock("copper", "HG=F", "Copper futures"),
    SeriesSpec("bitcoin", "markets", "yahoo", {"ticker": "BTC-USD", "start": "2015-01-01"}, "D", 28, "individual", "Bitcoin in USD"),
    SeriesSpec("ethereum", "markets", "yahoo", {"ticker": "ETH-USD", "start": "2017-11-09"}, "D", 28, "individual", "Ether in USD"),
    _stock("natgas", "NG=F", "Natural gas futures (Henry Hub, front month)"),
    _stock("eurusd", "EURUSD=X", "Euro in US dollars"),
    _stock("wheat", "ZW=F", "Wheat futures (Chicago, front month)"),
    _stock("corn", "ZC=F", "Corn futures (Chicago, front month)"),
    _stock("usdjpy", "JPY=X", "US dollar in Japanese yen"),
    _stock("gbpusd", "GBPUSD=X", "British pound in US dollars"),
    _stock("audusd", "AUDUSD=X", "Australian dollar in US dollars"),
    _stock("platinum", "PL=F", "Platinum futures (USD/oz)"),
    _stock("soybeans", "ZS=F", "Soybean futures (Chicago, front month)"),
    _stock("cocoa", "CC=F", "Cocoa futures (New York, front month)"),
    SeriesSpec("xrp", "markets", "yahoo", {"ticker": "XRP-USD", "start": "2017-11-09"}, "D", 28, "individual", "XRP in USD"),
    SeriesSpec("solana", "markets", "yahoo", {"ticker": "SOL-USD", "start": "2020-04-10"}, "D", 28, "individual", "Solana in USD"),
]

TECH = [
    _wiki("wiki_llm", "Large_language_model", "Wikipedia views: Large language model"),
    _wiki("wiki_ai", "Artificial_intelligence", "Wikipedia views: Artificial intelligence"),
    _wiki("wiki_quantum", "Quantum_computing", "Wikipedia views: Quantum computing"),
    _wiki("wiki_crispr", "CRISPR", "Wikipedia views: CRISPR"),
    _wiki("wiki_ev", "Electric_vehicle", "Wikipedia views: Electric vehicle"),
    _wiki("wiki_fusion", "Fusion_power", "Wikipedia views: Fusion power"),
    _wiki("wiki_humanoid", "Humanoid_robot", "Wikipedia views: Humanoid robot"),
    # Technological advances: the next wave, followed the same way as the ones above.
    _wiki("wiki_battery", "Solid-state_battery", "Wikipedia views: Solid-state battery"),
    _wiki("wiki_gene_therapy", "Gene_therapy", "Wikipedia views: Gene therapy"),
    _wiki("wiki_self_driving", "Self-driving_car", "Wikipedia views: Self-driving car"),
    _wiki("wiki_starship", "SpaceX_Starship", "Wikipedia views: SpaceX Starship"),
    _wiki("wiki_smr", "Small_modular_reactor", "Wikipedia views: small modular reactors"),
    _wiki("wiki_ar", "Augmented_reality", "Wikipedia views: augmented reality"),
    _wiki("wiki_drones", "Unmanned_aerial_vehicle", "Wikipedia views: drones (unmanned aerial vehicles)"),
    _wiki("wiki_vr", "Virtual_reality", "Wikipedia views: virtual reality"),
    _wiki("wiki_6g", "6G", "Wikipedia views: 6G (next mobile networks)"),
    _wiki("wiki_mrna", "MRNA_vaccine", "Wikipedia views: mRNA vaccines"),
    _wiki("wiki_cultured_meat", "Cultured_meat", "Wikipedia views: cultured (lab-grown) meat"),
    _wiki("wiki_semaglutide", "Semaglutide", "Wikipedia views: semaglutide (Ozempic, Wegovy)"),
    _wiki("wiki_neuralink", "Neuralink", "Wikipedia views: Neuralink (brain implants)"),
    _owid("adoption_solar", "share-electricity-solar", "Share of world electricity from solar (OWID)"),
    _owid("adoption_wind", "share-electricity-wind", "Share of world electricity from wind (OWID)"),
    _owid("adoption_internet", "share-of-individuals-using-the-internet", "Share of people using the internet (OWID)"),
    _owid("adoption_ev", "electric-car-sales-share", "Share of new cars sold that are electric (OWID, IEA)"),
    _owid("space_launches", "yearly-number-of-objects-launched-into-outer-space", "Objects launched into space each year (OWID, UNOOSA)"),
    SeriesSpec(
        "tech_composite",
        "tech",
        "composite",
        {"members": ["wiki_llm", "wiki_ai", "wiki_quantum", "wiki_crispr", "wiki_ev", "wiki_fusion", "wiki_humanoid"]},
        "D",
        28,
        "aggregate",
        "Average of the technology pageview series above, each scaled to its own mean",
    ),
]

POLITICS = [
    _politics("politics_sanctions", '"sanctions"', "Share of world news coverage mentioning sanctions"),
    _politics("politics_tariffs", "(tariff OR tariffs)", "Share of world news coverage mentioning tariffs"),
    _politics("politics_ceasefire", '(ceasefire OR "peace talks")', "Share of coverage about ceasefires and peace talks"),
    _politics("politics_coup", '(coup OR "martial law")', "Share of coverage about coups and martial law"),
    _politics("politics_impeachment", '(impeachment OR "no-confidence")', "Share of coverage about impeachments and no-confidence votes"),
    _politics("politics_referendum", "(referendum OR referendums)", "Share of world news coverage mentioning referendums"),
    _politics("politics_un", '("United Nations" OR "Security Council")', "Share of world news coverage mentioning the United Nations"),
    _politics("politics_summits", '("G7 summit" OR "G20 summit")', "Share of world news coverage mentioning G7 or G20 summits"),
    _politics("politics_nato", "NATO", "Share of world news coverage mentioning NATO"),
    _politics("politics_immigration", "(immigration OR migrants)", "Share of world news coverage about immigration and migrants"),
    SeriesSpec(
        "politics_composite",
        "politics",
        "composite",
        {"members": ["politics_sanctions", "politics_tariffs", "politics_ceasefire", "politics_coup",
                     "politics_impeachment", "politics_referendum"]},
        "D",
        28,
        "aggregate",
        "Average of the political topics above, each scaled to its own mean",
    ),
]

# Weather is forecast two weeks ahead: past that, every forecaster is reading the season, not the weather.
WEATHER = [
    SeriesSpec("weather_world_air", "weather", "reanalyzer", {"dataset": "air"}, "D", 14, "aggregate",
               "World mean surface air temperature (deg C, ERA5 via Climate Reanalyzer)"),
    SeriesSpec("weather_world_sea", "weather", "reanalyzer", {"dataset": "sst"}, "D", 14, "aggregate",
               "World sea surface temperature, 60S-60N (deg C, NOAA OISST via Climate Reanalyzer)"),
    SeriesSpec("weather_arctic_ice", "weather", "seaice", {"hemisphere": "north"}, "D", 14, "aggregate",
               "Arctic sea ice extent (million km2, NSIDC Sea Ice Index)"),
    _city("weather_london", "London", 51.51, -0.13),
    _city("weather_new_delhi", "New Delhi", 28.61, 77.21),
    _city("weather_tokyo", "Tokyo", 35.68, 139.69),
    _city("weather_sydney", "Sydney", -33.87, 151.21),
    _city("weather_los_angeles", "Los Angeles", 34.05, -118.24),
    _city("weather_new_york", "New York", 40.71, -74.01),
    _city("weather_paris", "Paris", 48.86, 2.35),
    _city("weather_sao_paulo", "São Paulo", -23.55, -46.63),
    _city("weather_mumbai", "Mumbai", 19.08, 72.88),
    _city("weather_cape_town", "Cape Town", -33.92, 18.42),
    _city("weather_singapore", "Singapore", 1.35, 103.82),
    _rain("rain_london", "London", 51.51, -0.13),
    _rain("rain_new_delhi", "New Delhi", 28.61, 77.21),
    _rain("rain_tokyo", "Tokyo", 35.68, 139.69),
    _rain("rain_sydney", "Sydney", -33.87, 151.21),
    _rain("rain_los_angeles", "Los Angeles", 34.05, -118.24),
    _rain("rain_new_york", "New York", 40.71, -74.01),
    _rain("rain_paris", "Paris", 48.86, 2.35),
    _rain("rain_sao_paulo", "São Paulo", -23.55, -46.63),
    _rain("rain_mumbai", "Mumbai", 19.08, 72.88),
    _rain("rain_cape_town", "Cape Town", -33.92, 18.42),
    _rain("rain_singapore", "Singapore", 1.35, 103.82),
    SeriesSpec("quakes_m45", "weather", "usgs", {"min_magnitude": 4.5}, "D", 14, "aggregate",
               "Earthquakes of magnitude 4.5 or more per day, worldwide (USGS)"),
]

CATALOG: list[SeriesSpec] = NEWS + POLITICS + MARKETS + TECH + WEATHER
DOMAINS = ("news", "politics", "markets", "tech", "weather")
LABELS = {"news": "World news", "politics": "Politics", "markets": "Markets", "tech": "Technology", "weather": "Weather and Earth"}


def select(domains: list[str] | None = None, ids: list[str] | None = None) -> list[SeriesSpec]:
    specs = [s for s in CATALOG if not domains or s.domain in domains]
    if ids:
        specs = [s for s in specs if s.id in ids]
    return specs


def by_id(series_id: str) -> SeriesSpec:
    for spec in CATALOG:
        if spec.id == series_id:
            return spec
    raise KeyError(series_id)
