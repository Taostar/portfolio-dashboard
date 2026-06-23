"""Smoke tests for QuestradeProvider itself: confirms it satisfies the
BrokerProvider interface and wires its internal helpers together correctly.
Live Questrade auth/API calls are mocked (unavoidable — no real credentials
in this environment); the orchestration logic (which functions get called,
in what order, with what data flowing between them) is what's under test."""

import pandas as pd
import pytest

from app.providers.base import BrokerProvider
from app.providers.questrade import QuestradeProvider


def test_questrade_provider_is_a_broker_provider():
    provider = QuestradeProvider()
    assert isinstance(provider, BrokerProvider)


@pytest.mark.asyncio
async def test_get_holdings_wires_market_data_into_metrics(monkeypatch):
    holdings_df = pd.DataFrame(
        [
            {"symbol": "AAPL", "currency": "USD", "current_market_value": 1000.0,
             "current_market_value_CAD": 1350.0, "percentage": 60.0, "security_type": "Stock"},
            {"symbol": "MSFT", "currency": "USD", "current_market_value": 500.0,
             "current_market_value_CAD": 675.0, "percentage": 40.0, "security_type": "Stock"},
        ]
    )
    performance_df = pd.DataFrame(
        [
            {"symbol": "AAPL", "date": "2024-01-01", "open": 1, "high": 1, "low": 1, "close": 100.0, "volume": 10},
            {"symbol": "AAPL", "date": "2024-01-02", "open": 1, "high": 1, "low": 1, "close": 110.0, "volume": 10},
            {"symbol": "MSFT", "date": "2024-01-01", "open": 1, "high": 1, "low": 1, "close": 200.0, "volume": 10},
            {"symbol": "MSFT", "date": "2024-01-02", "open": 1, "high": 1, "low": 1, "close": 210.0, "volume": 10},
        ]
    )

    monkeypatch.setattr(
        "app.providers.questrade.get_questrade_clients", lambda: ["fake-client"]
    )
    monkeypatch.setattr(
        "app.providers.questrade.get_all_accounts_holdings_multi",
        lambda clients, as_dataframe, group_by_symbol: holdings_df,
    )
    monkeypatch.setattr(
        QuestradeProvider, "_get_market_data_sync", lambda self, symbols, days=365, interval="OneDay": performance_df
    )

    provider = QuestradeProvider()
    holdings, metrics = await provider.get_holdings()

    assert holdings == holdings_df.to_dict(orient="records")
    assert metrics["Total Market Value (CAD)"] == pytest.approx(1350.0 + 675.0)
    assert set(metrics["Symbols"]) == {"AAPL", "MSFT"}
    assert "Sharpe Ratio" in metrics
    assert "Cumulative Return" in metrics


@pytest.mark.asyncio
async def test_get_market_data_uses_single_client(monkeypatch):
    captured = {}

    def fake_client_factory():
        captured["called"] = True
        return "fake-client"

    def fake_fetch(client, symbols, start_date, end_date, interval):
        captured["symbols"] = symbols
        captured["interval"] = interval
        return pd.DataFrame([{"symbol": "AAPL", "date": "2024-01-01", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}])

    monkeypatch.setattr("app.providers.questrade.get_questrade_client", fake_client_factory)
    monkeypatch.setattr("app.providers.questrade.fetch_symbols_market_data", fake_fetch)

    provider = QuestradeProvider()
    df = await provider.get_market_data(["AAPL"], days=30, interval="OneDay")

    assert captured["called"] is True
    assert captured["symbols"] == ["AAPL"]
    assert captured["interval"] == "OneDay"
    assert list(df.columns) == ["symbol", "date", "open", "high", "low", "close", "volume"]
