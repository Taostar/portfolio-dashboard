"""Feature-flag routing layer between endpoints and the two holdings/market-data
backends: the legacy `external_api.py` (ngrok-tunneled Questrade-API project)
and the new in-process `QuestradeProvider` (Task 2).

Every endpoint should import from this module instead of `external_api.py`
going forward. Exposes the same four function names/signatures that
`external_api.py` exposes today, so switching imports is a no-op while
`settings.FEATURE_USE_QUESTRADE_PROVIDER` is False (the default).

The flag is read at call time (via the module-level `settings` object's
attribute, which always reflects the current value — `get_settings()` itself
is `lru_cache`'d so it returns the same `Settings` instance, but the boolean
field on that instance is read fresh on every call), so tests can flip it
with monkeypatch and see routing change without reloading this module.
"""

from typing import Optional

import pandas as pd

from app.config import get_settings
from app.core.cache import cached
from app.providers.questrade import QuestradeProvider
from app.services import external_api

settings = get_settings()
_provider = QuestradeProvider()


@cached(cache_type="holdings")
async def fetch_portfolio_data() -> tuple[Optional[list], Optional[dict]]:
    """
    Fetches portfolio holdings + metrics, routed by FEATURE_USE_QUESTRADE_PROVIDER.

    Returns:
        Tuple of (portfolio_holdings, portfolio_metrics) or (None, None) on error
        (flag-off path only; the provider path raises on failure rather than
        swallowing errors into (None, None)).
    """
    if settings.FEATURE_USE_QUESTRADE_PROVIDER:
        return await _provider.get_holdings()
    return await external_api.fetch_portfolio_data()


@cached(cache_type="performance")
async def load_performance() -> pd.DataFrame:
    """
    Fetches historical OHLCV performance data, routed by FEATURE_USE_QUESTRADE_PROVIDER.

    Returns:
        DataFrame with columns: symbol, date, open, high, low, close, volume
    """
    if settings.FEATURE_USE_QUESTRADE_PROVIDER:
        holdings, _ = await fetch_portfolio_data()
        symbols = [h["symbol"] for h in (holdings or [])]
        return await _provider.get_market_data(symbols)
    return await external_api.load_performance()


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
