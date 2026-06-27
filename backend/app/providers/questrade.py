"""QuestradeProvider — the first real BrokerProvider implementation, backed by
the Questrade brokerage API via the `qtrade` package.

Ported from the standalone Questrade-API reference project (see
`app/providers/_questrade_internal/` for the ported auth/holdings/market/metrics
helpers). `QuestradeProvider` is the only public export of this module; the
private helper modules should not be imported directly by other code outside
this package.

No constructor arguments are needed — it reads `get_settings()` internally,
matching the rest of this codebase's pattern (e.g. `external_api.py`'s
module-level `settings = get_settings()`).
"""

import asyncio
import logging

import pandas as pd

from app.config import get_settings
from app.providers.base import BrokerProvider
from app.providers._questrade_internal.auth import get_questrade_clients
from app.providers._questrade_internal.holdings import get_all_accounts_holdings_multi
from app.providers._questrade_internal.market import fetch_symbols_market_data_yf
from app.providers._questrade_internal.metrics import calc_portfolio_metrics

logger = logging.getLogger(__name__)

settings = get_settings()

DEFAULT_ANNUAL_RISK_FREE_RATE = 0.03


class QuestradeProvider(BrokerProvider):
    """BrokerProvider implementation backed by the Questrade brokerage API."""

    async def get_holdings(self) -> tuple[list[dict], dict]:
        return await asyncio.to_thread(self._get_holdings_sync)

    def _get_holdings_sync(self) -> tuple[list[dict], dict]:
        clients = get_questrade_clients()
        holdings_df = get_all_accounts_holdings_multi(clients, as_dataframe=True, group_by_symbol=True)

        symbols = [str(s) for s in holdings_df["symbol"].tolist()]
        performance_df = self._get_market_data_sync(symbols, days=365)

        portfolio_metrics = calc_portfolio_metrics(
            performance_df,
            annual_risk_free_rate=DEFAULT_ANNUAL_RISK_FREE_RATE,
            holdings_df=holdings_df,
            symbols_allocs=None,
        )

        current_market_value_cad = holdings_df["current_market_value_CAD"].sum()
        portfolio_metrics["Total Market Value (CAD)"] = current_market_value_cad

        return holdings_df.to_dict(orient="records"), portfolio_metrics

    async def get_market_data(
        self, symbols: list[str], days: int = 365, interval: str = "OneDay"
    ) -> pd.DataFrame:
        return await asyncio.to_thread(self._get_market_data_sync, symbols, days, interval)

    def _get_market_data_sync(
        self, symbols: list[str], days: int = 365, interval: str = "OneDay"
    ) -> pd.DataFrame:
        return fetch_symbols_market_data_yf(symbols, days, interval)
