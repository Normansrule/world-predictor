"""The series this project forecasts, grouped into the three domains.

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
    domain: str  # "news" | "markets" | "tech"
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


def _owid(id_, slug, desc):
    # Adoption curves also get the Bass diffusion model as a theory-driven rival.
    return SeriesSpec(id_, "tech", "owid", {"slug": slug}, "YS", 3, "aggregate", desc, ("bass",))


NEWS = [
    _news("news_war", '"war"', "Share of world news coverage mentioning war"),
    _news("news_election", '"election"', "Share of world news coverage mentioning elections"),
    _news("news_inflation", '"inflation"', "Share of world news coverage mentioning inflation"),
    _news("news_climate", '"climate change"', "Share of world news coverage mentioning climate change"),
    _news("news_pandemic", '(pandemic OR outbreak OR epidemic)', "Share of coverage about disease outbreaks"),
    _news("news_protest", '(protest OR protests)', "Share of world news coverage mentioning protests"),
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
    _stock("gold", "GC=F", "Gold futures (USD/oz)"),
    _stock("silver", "SI=F", "Silver futures (USD/oz)"),
    _stock("oil_wti", "CL=F", "WTI crude oil futures"),
    _stock("copper", "HG=F", "Copper futures"),
    SeriesSpec("bitcoin", "markets", "yahoo", {"ticker": "BTC-USD", "start": "2015-01-01"}, "D", 28, "individual", "Bitcoin in USD"),
]

TECH = [
    _wiki("wiki_llm", "Large_language_model", "Wikipedia views: Large language model"),
    _wiki("wiki_ai", "Artificial_intelligence", "Wikipedia views: Artificial intelligence"),
    _wiki("wiki_quantum", "Quantum_computing", "Wikipedia views: Quantum computing"),
    _wiki("wiki_crispr", "CRISPR", "Wikipedia views: CRISPR"),
    _wiki("wiki_ev", "Electric_vehicle", "Wikipedia views: Electric vehicle"),
    _wiki("wiki_fusion", "Fusion_power", "Wikipedia views: Fusion power"),
    _wiki("wiki_humanoid", "Humanoid_robot", "Wikipedia views: Humanoid robot"),
    _owid("adoption_solar", "share-electricity-solar", "Share of world electricity from solar (OWID)"),
    _owid("adoption_wind", "share-electricity-wind", "Share of world electricity from wind (OWID)"),
    _owid("adoption_internet", "share-of-individuals-using-the-internet", "Share of people using the internet (OWID)"),
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

CATALOG: list[SeriesSpec] = NEWS + MARKETS + TECH
DOMAINS = ("news", "markets", "tech")


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
