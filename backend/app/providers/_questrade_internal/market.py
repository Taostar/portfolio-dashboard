"""Market data retrieval — ported from Questrade-API/utils/market.py
(per-symbol `get_symbol_id`/`get_market_data`) and the thread-pool
parallelization pattern from
Questrade-API/utils/collect_performance.py::collect_all_performance_data.

Unlike the old code, this skips the `MarketPerformance`/`MarketCandle`
Pydantic wrapping and the CSV round trip — `fetch_symbols_market_data` builds
the long-format DataFrame (symbol, date, open, high, low, close, volume)
directly, which is what `QuestradeProvider.get_market_data()` returns.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import List, Optional

import pandas as pd
from qtrade import Questrade

logger = logging.getLogger(__name__)


def get_symbol_id(client: Questrade, symbol: str) -> int:
    """Get the symbol ID for a given ticker symbol.

    Returns 0 as a fallback if the symbol can't be looked up (matches the old
    behavior — callers that need the ID treat 0 as "unknown").
    """
    logger.info(f"Looking up symbol ID for {symbol}")
    try:
        ticker_info = client.ticker_information([symbol])
        if not ticker_info or len(ticker_info) == 0:
            logger.error(f"Symbol '{symbol}' not found in ticker_information response")
            raise ValueError(f"Symbol '{symbol}' not found")

        symbol_id = ticker_info[0].get("symbolId")
        if not symbol_id:
            logger.error(f"Symbol ID not found in ticker_information response for '{symbol}'")
            raise ValueError(f"Symbol ID not found for '{symbol}'")

        logger.info(f"Found symbol ID {symbol_id} for {symbol}")
        return symbol_id
    except Exception as e:
        logger.error(f"Error getting symbol ID for {symbol}: {e}")
        logger.info(f"Returning 0 as a fallback symbol ID for {symbol}")
        return 0


def get_market_data(
    client: Questrade,
    symbol: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    interval: str = "OneDay",
) -> List[dict]:
    """Get historical candles for a single symbol via
    `client.get_historical_data`. Returns a list of raw candle dicts as
    returned by qtrade (keys: start, end, open, high, low, close, volume) —
    empty list on any failure (logged, not raised).
    """
    if not end_date:
        end_date = datetime.now()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")

    try:
        candles_data = client.get_historical_data(symbol, start_date_str, end_date_str, interval)
        return candles_data or []
    except Exception as e:
        logger.error(f"Error getting historical data for {symbol}: {e}")
        return []


def _candle_to_row(symbol: str, candle: dict) -> Optional[dict]:
    """Convert one raw qtrade candle dict into a long-format row. Returns None
    if the candle is missing a usable date (skipped, not raised)."""
    raw_date = candle.get("start") or candle.get("date")
    if not raw_date:
        return None
    try:
        date_str = str(raw_date).replace("Z", "+00:00")
        date = datetime.fromisoformat(date_str).strftime("%Y-%m-%d")
    except Exception:
        return None

    return {
        "symbol": symbol,
        "date": date,
        "open": candle.get("open"),
        "high": candle.get("high"),
        "low": candle.get("low"),
        "close": candle.get("close"),
        "volume": candle.get("volume"),
    }


def fetch_symbols_market_data(
    client: Questrade,
    symbols: List[str],
    start_date: datetime,
    end_date: datetime,
    interval: str = "OneDay",
) -> pd.DataFrame:
    """Fetch candles for multiple symbols in parallel via a ThreadPoolExecutor
    (same pattern as collect_all_performance_data: max_workers =
    min(len(symbols), 10)), and build a long-format DataFrame directly
    (columns: symbol, date, open, high, low, close, volume).

    A symbol whose fetch fails or returns no data is skipped (logged) so one
    bad symbol doesn't fail the whole batch. Missing OHLCV values are
    forward-filled per-symbol, then the result is sorted by symbol, date.
    """
    if not symbols:
        return pd.DataFrame(columns=["symbol", "date", "open", "high", "low", "close", "volume"])

    max_workers = min(len(symbols), 10)

    def fetch_one(symbol: str):
        try:
            candles = get_market_data(client, symbol, start_date, end_date, interval)
            if not candles:
                logger.warning(f"No historical data found for {symbol}")
            return symbol, candles
        except Exception as e:
            logger.error(f"Error fetching market data for {symbol}: {e}")
            return symbol, []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(fetch_one, symbols))

    rows = []
    for symbol, candles in results:
        for candle in candles:
            row = _candle_to_row(symbol, candle)
            if row is not None:
                rows.append(row)

    df = pd.DataFrame(rows, columns=["symbol", "date", "open", "high", "low", "close", "volume"])

    if df.empty:
        return df

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.sort_values(by=["symbol", "date"]).reset_index(drop=True)

    cols_to_fill = ["open", "high", "low", "close", "volume"]
    df[cols_to_fill] = df.groupby("symbol", sort=False)[cols_to_fill].ffill()

    return df
