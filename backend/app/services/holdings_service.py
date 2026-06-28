from typing import Optional

import pandas as pd

from app.core.cache import cached
from app.providers.questrade import QuestradeProvider

_provider = QuestradeProvider()


@cached(cache_type="holdings")
async def fetch_portfolio_data() -> tuple[Optional[list], Optional[dict]]:
    """Fetch portfolio holdings and metrics from Questrade."""
    return await _provider.get_holdings()


@cached(cache_type="performance")
async def load_performance() -> pd.DataFrame:
    """Fetch historical OHLCV data for all current holdings from yfinance.

    Returns a DataFrame with columns: symbol, date, open, high, low, close, volume.
    """
    holdings, _ = await fetch_portfolio_data()
    symbols = [h["symbol"] for h in (holdings or [])]
    return await _provider.get_market_data(symbols)


async def get_holdings_dataframe() -> pd.DataFrame:
    """Get holdings data as a DataFrame."""
    holdings, _ = await fetch_portfolio_data()
    if holdings is None:
        return pd.DataFrame()
    return pd.DataFrame(holdings)


async def get_portfolio_metrics() -> Optional[dict]:
    """Get portfolio metrics."""
    _, metrics = await fetch_portfolio_data()
    return metrics
