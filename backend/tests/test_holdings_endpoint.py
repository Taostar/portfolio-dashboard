"""Endpoint tests for GET /holdings and GET /holdings/top/{n} — Task 7: split
stocks/ETFs from options via app.providers.classifier.split_holdings, run
calculate_market_value_changes on each half separately, and return options
under HoldingsResponse.options. get_holdings_dataframe/load_performance are
mocked (I/O boundary); calculate_market_value_changes runs for real against
synthetic DataFrames.
"""

from unittest.mock import AsyncMock, patch

import pandas as pd
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _holdings_df():
    return pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "currency": "USD",
                "quantity": 10,
                "current_price": 150.0,
                "current_market_value": 1500.0,
                "current_market_value_CAD": 2000.0,
                "percentage": 60.0,
                "security_type": "Stock",
            },
            {
                "symbol": "MSFT",
                "currency": "USD",
                "quantity": 5,
                "current_price": 300.0,
                "current_market_value": 1500.0,
                "current_market_value_CAD": 2000.0,
                "percentage": 30.0,
                "security_type": "Stock",
            },
            {
                "symbol": "NVDA10Jul26P180.00",
                "currency": "USD",
                "quantity": -1,
                "current_price": 50.0,
                "current_market_value": -500.0,
                "current_market_value_CAD": -650.0,
                "percentage": 10.0,
                "security_type": "Option",
            },
        ]
    )


def _performance_df():
    dates = pd.date_range(end="2024-06-30", periods=10, freq="D")
    rows = []
    for symbol, base in [("AAPL", 150.0), ("MSFT", 300.0), ("NVDA10Jul26P180.00", 50.0)]:
        for d in dates:
            rows.append(
                {
                    "symbol": symbol,
                    "date": d.strftime("%Y-%m-%d"),
                    "open": base,
                    "high": base,
                    "low": base,
                    "close": base,
                    "volume": 1000,
                }
            )
    return pd.DataFrame(rows)


def _mock_io():
    return patch.multiple(
        "app.api.v1.endpoints.holdings",
        get_holdings_dataframe=AsyncMock(return_value=_holdings_df()),
        load_performance=AsyncMock(return_value=_performance_df()),
    )


def test_get_holdings_splits_stocks_and_options():
    with _mock_io():
        response = client.get("/api/v1/holdings")

    assert response.status_code == 200
    body = response.json()

    holdings_symbols = {h["symbol"] for h in body["holdings"]}
    options_symbols = {h["symbol"] for h in body["options"]}

    assert holdings_symbols == {"AAPL", "MSFT"}
    assert options_symbols == {"NVDA10Jul26P180.00"}


def test_get_top_holdings_excludes_options_even_with_higher_value():
    # Give the option a market value higher than the stocks so a naive
    # top-N by value would otherwise surface it.
    df = _holdings_df()
    df.loc[df["symbol"] == "NVDA10Jul26P180.00", "current_market_value_CAD"] = 999999.0

    with patch.multiple(
        "app.api.v1.endpoints.holdings",
        get_holdings_dataframe=AsyncMock(return_value=df),
        load_performance=AsyncMock(return_value=_performance_df()),
    ):
        response = client.get("/api/v1/holdings/top/2")

    assert response.status_code == 200
    body = response.json()
    symbols = {h["symbol"] for h in body["holdings"]}
    assert symbols == {"AAPL", "MSFT"}
    assert "NVDA10Jul26P180.00" not in symbols
