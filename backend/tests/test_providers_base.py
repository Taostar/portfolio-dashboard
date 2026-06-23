import pytest
import pandas as pd

from app.providers.base import BrokerProvider


def test_broker_provider_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        BrokerProvider()


class _FakeProvider(BrokerProvider):
    async def get_holdings(self) -> tuple[list[dict], dict]:
        return ([{"symbol": "AAPL", "quantity": 10}], {"Total Market Value (CAD)": 1000})

    async def get_market_data(
        self, symbols: list[str], days: int = 365, interval: str = "OneDay"
    ) -> pd.DataFrame:
        return pd.DataFrame(
            [{"symbol": symbols[0], "date": "2024-01-01", "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 100}]
        )


def test_concrete_subclass_can_be_instantiated():
    provider = _FakeProvider()
    assert isinstance(provider, BrokerProvider)


@pytest.mark.asyncio
async def test_concrete_subclass_get_holdings_returns_defined_value():
    provider = _FakeProvider()
    holdings, metrics = await provider.get_holdings()
    assert holdings == [{"symbol": "AAPL", "quantity": 10}]
    assert metrics == {"Total Market Value (CAD)": 1000}


@pytest.mark.asyncio
async def test_concrete_subclass_get_market_data_returns_defined_value():
    provider = _FakeProvider()
    result = await provider.get_market_data(["AAPL"])
    assert list(result.columns) == ["symbol", "date", "open", "high", "low", "close", "volume"]
    assert result.iloc[0]["symbol"] == "AAPL"
