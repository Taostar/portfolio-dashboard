"""EMA(21) indicators on monthly and quarterly candles, sourced from yfinance
(same rationale as app.providers._questrade_internal.market — Questrade's
market-data rate limits make yfinance the historical-data source of choice)."""

import logging
from typing import Optional

import pandas as pd
import yfinance as yf

from app.core.cache import cached
from app.providers.classifier import is_option_symbol

logger = logging.getLogger(__name__)

EMA_SPAN = 21

# field name -> (yfinance period, yfinance interval)
_TIMEFRAMES = {
    "ema_21m": ("3y", "1mo"),   # 21-month EMA needs ≥21 monthly candles
    "ema_21q": ("10y", "3mo"),  # 21-quarter EMA needs ≥21 quarterly candles
}


def _compute_ema_last_value(close: pd.Series, span: int = EMA_SPAN) -> Optional[float]:
    """Latest EMA(span) of a close-price series, or None with fewer than
    `span` usable values. adjust=False gives the standard recursive EMA."""
    close = pd.to_numeric(close, errors="coerce").dropna()
    if len(close) < span:
        return None
    return float(close.ewm(span=span, adjust=False).mean().iloc[-1])


def _close_series_by_symbol(raw, symbols: list[str]) -> dict[str, pd.Series]:
    """Split a yf.download result into per-symbol Close series, handling both
    MultiIndex (batch) and flat (single-ticker) column layouts."""
    out: dict[str, pd.Series] = {}
    if raw is None or raw.empty:
        return out
    if isinstance(raw.columns, pd.MultiIndex):
        for symbol in symbols:
            if symbol not in raw.columns.get_level_values(1):
                continue
            close = raw.xs(symbol, axis=1, level=1).get("Close")
            if close is not None:
                out[symbol] = close
    elif "Close" in raw.columns and len(symbols) == 1:
        out[symbols[0]] = raw["Close"]
    return out


@cached(cache_type="ema")
def fetch_ema_indicators(symbols: tuple) -> dict:
    """EMA(21) on monthly and quarterly closes for each symbol.

    Returns {symbol: {"ema_21m": float | None, "ema_21q": float | None}}.
    Option contracts aren't yfinance tickers and always get None; any
    download or per-symbol failure degrades to None rather than raising.
    Cached for 1 day — pass symbols as a sorted tuple for stable cache keys.
    """
    result = {s: {"ema_21m": None, "ema_21q": None} for s in symbols}
    stock_etf_symbols = [s for s in symbols if not is_option_symbol(s)]
    if not stock_etf_symbols:
        return result

    for field, (period, interval) in _TIMEFRAMES.items():
        try:
            raw = yf.download(
                stock_etf_symbols,
                period=period,
                interval=interval,
                progress=False,
                auto_adjust=True,
            )
        except Exception as e:
            logger.error(f"Error fetching {interval} candles for EMA: {e}")
            continue
        for symbol, close in _close_series_by_symbol(raw, stock_etf_symbols).items():
            result[symbol][field] = _compute_ema_last_value(close)

    return result
