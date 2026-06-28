"""Historical market data — sourced from yfinance rather than Questrade's
own `/markets/candles` endpoint.

Questrade enforces a separate, easily-exhausted rate-limit bucket for
market-data endpoints (quotes/candles/ticker info) distinct from
account-data endpoints — a single `QuestradeProvider.get_holdings()` call
already fetches per-symbol quotes/ticker info for current pricing, and
piling a year of historical candles for every symbol on top of that
repeatedly tripped 403s in practice. yfinance has no such quota and is
already a backend dependency (see `app/services/exchange_service.py`), so
historical performance data is fetched from there instead — current
price/quote data for holdings still comes from Questrade (unaffected by
this change).
"""

import logging
from datetime import datetime, timedelta
from typing import List

import pandas as pd
import yfinance as yf

from app.providers.classifier import is_option_symbol

logger = logging.getLogger(__name__)

# Questrade interval names -> yfinance interval strings. Anything not listed
# here falls back to "1d" (the only interval actually exercised today).
_INTERVAL_MAP = {
    "OneDay": "1d",
    "OneWeek": "1wk",
    "OneMonth": "1mo",
}


def fetch_symbols_market_data_yf(
    symbols: List[str], days: int = 365, interval: str = "OneDay"
) -> pd.DataFrame:
    """Fetch historical candles for multiple symbols via yfinance, returning
    a long-format DataFrame (columns: symbol, date, open, high, low, close,
    volume) — same shape `fetch_symbols_market_data` (the old qtrade-backed
    version) produced.

    Option contracts (e.g. `NVDA10Jul26P180.00`) aren't real yfinance
    tickers and are filtered out before calling `yf.download` — they
    already have no representation in correlation/benchmark calculations
    (see `app.providers.classifier`), and `calc_portfolio_metrics` already
    tolerates symbols with no historical data.
    """
    stock_etf_symbols = [s for s in symbols if not is_option_symbol(s)]

    if not stock_etf_symbols:
        return pd.DataFrame(columns=["symbol", "date", "open", "high", "low", "close", "volume"])

    yf_interval = _INTERVAL_MAP.get(interval, "1d")
    period = f"{days}d"

    try:
        raw = yf.download(stock_etf_symbols, period=period, interval=yf_interval, progress=False)
    except Exception as e:
        logger.error(f"Error fetching yfinance data for {stock_etf_symbols}: {e}")
        return pd.DataFrame(columns=["symbol", "date", "open", "high", "low", "close", "volume"])

    if raw is None or raw.empty:
        return pd.DataFrame(columns=["symbol", "date", "open", "high", "low", "close", "volume"])

    rows = []
    field_map = {"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}

    if isinstance(raw.columns, pd.MultiIndex):
        for symbol in stock_etf_symbols:
            if symbol not in raw.columns.get_level_values(1):
                logger.warning(f"No yfinance data found for {symbol}")
                continue
            symbol_df = raw.xs(symbol, axis=1, level=1)
            if symbol_df.get("Close") is None or symbol_df["Close"].isna().all():
                # Delisted/no-data ticker: yf.download still emits a row per
                # date in a multi-ticker batch, just filled with NaN. Drop it
                # entirely rather than feeding NaN rows downstream — one
                # all-NaN symbol poisons every other symbol's common-date
                # intersection in correlation/benchmark calculations.
                logger.warning(f"No real yfinance data found for {symbol} (all-NaN)")
                continue
            for date, row in symbol_df.iterrows():
                rows.append(
                    {
                        "symbol": symbol,
                        "date": date.strftime("%Y-%m-%d"),
                        **{field_map[f]: row.get(f) for f in field_map},
                    }
                )
    elif raw.get("Close") is not None and not raw["Close"].isna().all():
        # Single ticker -> flat columns, no per-symbol selection needed.
        symbol = stock_etf_symbols[0]
        for date, row in raw.iterrows():
            rows.append(
                {
                    "symbol": symbol,
                    "date": date.strftime("%Y-%m-%d"),
                    **{field_map[f]: row.get(f) for f in field_map},
                }
            )

    df = pd.DataFrame(rows, columns=["symbol", "date", "open", "high", "low", "close", "volume"])

    if df.empty:
        return df

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.sort_values(by=["symbol", "date"]).reset_index(drop=True)

    cols_to_fill = ["open", "high", "low", "close", "volume"]
    df[cols_to_fill] = df.groupby("symbol", sort=False)[cols_to_fill].ffill()

    return df
