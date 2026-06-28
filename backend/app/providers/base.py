from abc import ABC, abstractmethod
import pandas as pd


class BrokerProvider(ABC):
    @abstractmethod
    async def get_holdings(self) -> tuple[list[dict], dict]:
        """Returns (portfolio_holdings, portfolio_metrics)."""
        ...

    @abstractmethod
    async def get_market_data(
        self, symbols: list[str], days: int = 365, interval: str = "OneDay"
    ) -> pd.DataFrame:
        """Returns a long-format DataFrame with columns: symbol, date, open, high, low, close, volume."""
        ...
