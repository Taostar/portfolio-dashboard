"""Endpoint tests for GET /portfolio/overview and GET /portfolio/allocation —
Task 7: exclude options from total_value_cad and allocation percentages.
fetch_portfolio_data/get_holdings_dataframe/load_performance are mocked (I/O
boundary); the split/aggregation logic runs for real against synthetic data.
"""

from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _holdings_list():
    # A negative-value short option position alongside two normal stocks.
    return [
        {
            "symbol": "AAPL",
            "currency": "USD",
            "quantity": 10,
            "current_price": 150.0,
            "current_market_value": 1500.0,
            "current_market_value_CAD": 2000.0,
            "percentage": 50.0,
            "security_type": "Stock",
        },
        {
            "symbol": "MSFT",
            "currency": "USD",
            "quantity": 5,
            "current_price": 300.0,
            "current_market_value": 1500.0,
            "current_market_value_CAD": 2000.0,
            "percentage": 50.0,
            "security_type": "Stock",
        },
        {
            "symbol": "NVDA10Jul26P180.00",
            "currency": "USD",
            "quantity": -1,
            "current_price": 50.0,
            "current_market_value": -500.0,
            "current_market_value_CAD": -650.0,
            "percentage": -16.25,
            "security_type": "Option",
        },
    ]


def _holdings_df():
    return pd.DataFrame(_holdings_list())


def _metrics():
    # Upstream naive total includes the negative option value, so it's lower
    # than the stocks/ETF-only total.
    return {
        "Total Market Value (CAD)": 3350.0,  # 2000 + 2000 - 650
        "Cumulative Return": 0.1,
        "Average Daily Return": 0.01,
        "Sharpe Ratio": 1.2,
        "Symbols": ["AAPL", "MSFT", "NVDA10Jul26P180.00"],
        "Allocations": ["50%", "50%", "-16.25%"],
    }


def _performance_df():
    dates = pd.date_range(end="2024-06-30", periods=40, freq="D")
    rows = []
    for symbol, base in [("AAPL", 150.0), ("MSFT", 300.0), ("NVDA10Jul26P180.00", 50.0)]:
        for i, d in enumerate(dates):
            # Small deterministic wiggle so pct_change/corr isn't degenerate
            # (constant prices produce NaN correlations, which aren't valid JSON).
            price = base + (i % 5)
            rows.append(
                {
                    "symbol": symbol,
                    "date": d.strftime("%Y-%m-%d"),
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "volume": 1000,
                }
            )
    return pd.DataFrame(rows)


def test_portfolio_overview_total_value_excludes_options():
    with patch.multiple(
        "app.api.v1.endpoints.portfolio",
        fetch_portfolio_data=AsyncMock(return_value=(_holdings_list(), _metrics())),
        get_holdings_dataframe=AsyncMock(return_value=_holdings_df()),
        load_performance=AsyncMock(return_value=_performance_df()),
    ):
        response = client.get("/api/v1/portfolio/overview")

    assert response.status_code == 200
    body = response.json()

    naive_upstream_total = _metrics()["Total Market Value (CAD)"]
    stocks_etfs_only_total = 2000.0 + 2000.0  # AAPL + MSFT, option excluded

    assert body["total_value_cad"] == stocks_etfs_only_total
    assert body["total_value_cad"] > naive_upstream_total


def test_portfolio_allocation_excludes_options_and_percentages_sum_to_100():
    with patch.multiple(
        "app.api.v1.endpoints.portfolio",
        fetch_portfolio_data=AsyncMock(return_value=(_holdings_list(), _metrics())),
    ):
        response = client.get("/api/v1/portfolio/allocation")

    assert response.status_code == 200
    body = response.json()

    symbols = {item["symbol"] for item in body["items"]}
    assert symbols == {"AAPL", "MSFT"}

    total_pct = sum(item["percentage"] for item in body["items"])
    assert total_pct == pytest.approx(100.0, rel=1e-6)
