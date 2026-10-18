"""Stock indices, single stocks and commodities (gold, silver, oil) via the open-source
``yfinance`` library (https://github.com/ranaroussi/yfinance), which reads Yahoo Finance data.

Yahoo Finance data is for personal and research use; see CREDITS.md.
"""

from __future__ import annotations

import pandas as pd


def fetch(ticker: str, start: str = "2005-01-01") -> pd.Series:
    import yfinance as yf

    frame = yf.download(ticker, start=start, interval="1d", auto_adjust=True, progress=False)
    if frame is None or frame.empty:
        raise ValueError(f"yfinance returned no data for {ticker!r}")
    close = frame["Close"]
    if isinstance(close, pd.DataFrame):  # newer yfinance returns one column per ticker
        close = close.iloc[:, 0]
    close.index = pd.to_datetime(close.index).tz_localize(None)
    return close.astype(float)
