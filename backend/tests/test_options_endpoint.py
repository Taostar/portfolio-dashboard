"""Endpoint tests for GET /options — options ranked by DTE ascending, plus a
notional-exposure / cash-like-reserves summary. get_holdings_dataframe is
mocked (I/O boundary); DTE/notional/reserves math runs for real."""

from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pandas as pd
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _holdings_df():
    near_expiry = date.today() + timedelta(days=5)
    far_expiry = date.today() + timedelta(days=45)
    return pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "currency": "USD",
                "quantity": 10,
                "current_price": 150.0,
                "current_market_value": 1500.0,
                "current_market_value_CAD": 2025.0,
                "percentage": 40.0,
                "security_type": "Stock",
            },
            {
                "symbol": "SGOV",
                "currency": "USD",
                "quantity": 100,
                "current_price": 100.0,
                "current_market_value": 10000.0,
                "current_market_value_CAD": 13500.0,
                "percentage": 30.0,
                "security_type": "Stock",
            },
            {
                "symbol": "PSA.TO",
                "currency": "CAD",
                "quantity": 200,
                "current_price": 50.0,
                "current_market_value": 10000.0,
                "current_market_value_CAD": 10000.0,
                "percentage": 20.0,
                "security_type": "Stock",
            },
            {
                # Farther expiry — should sort AFTER the near-dated option below.
                "symbol": "NVDA10Jul26P180.00",
                "currency": "USD",
                "quantity": -1,
                "current_price": 5.0,
                "current_market_value": -500.0,
                "current_market_value_CAD": -675.0,
                "percentage": 5.0,
                "security_type": "Option",
                "underlying": "NVDA",
                "expiry_date": far_expiry,
                "option_type": "Put",
                "strike": 180.0,
                "delta": 0.35,
                "underlying_price": 190.0,
                "itm_otm": "OTM",
            },
            {
                # Near expiry — should sort FIRST.
                "symbol": "AAPL2Jul26C155.00",
                "currency": "USD",
                "quantity": 2,
                "current_price": 3.0,
                "current_market_value": 600.0,
                "current_market_value_CAD": 810.0,
                "percentage": 5.0,
                "security_type": "Option",
                "underlying": "AAPL",
                "expiry_date": near_expiry,
                "option_type": "Call",
                "strike": 155.0,
                "delta": 0.6,
                "underlying_price": 160.0,
                "itm_otm": "ITM",
            },
        ]
    )


def _mock_io():
    return patch.multiple(
        "app.api.v1.endpoints.options",
        get_holdings_dataframe=AsyncMock(return_value=_holdings_df()),
    )


def test_get_options_sorts_by_dte_ascending():
    with _mock_io():
        response = client.get("/api/v1/options")

    assert response.status_code == 200
    body = response.json()

    dtes = [o["dte"] for o in body["options"]]
    assert dtes == sorted(dtes)
    assert body["options"][0]["strike"] == 155.0  # near-dated call sorts first


def test_get_options_reports_itm_otm_and_probability():
    with _mock_io():
        response = client.get("/api/v1/options")

    body = response.json()
    near = next(o for o in body["options"] if o["strike"] == 155.0)

    assert near["itm_otm"] == "ITM"
    assert near["underlying_price"] == 160.0
    assert near["probability_materialized"] == 0.6


def test_get_options_summary_includes_notional_and_reserves():
    with _mock_io():
        response = client.get("/api/v1/options")

    body = response.json()
    summary = body["summary"]

    # NVDA put: 180*100*1 USD; AAPL call: 155*100*2 USD -> fx ~1.35 (2025/1500)
    fx_rate = 2025.0 / 1500.0
    expected_notional = (180.0 * 100 * 1 + 155.0 * 100 * 2) * fx_rate
    assert summary["notional_exposure_cad"] == expected_notional

    assert summary["sgov_value_cad"] == 13500.0
    assert summary["psa_to_value_cad"] == 10000.0
    assert summary["cash_like_reserves_cad"] == 23500.0


def test_get_options_returns_503_when_holdings_empty():
    with patch.multiple(
        "app.api.v1.endpoints.options",
        get_holdings_dataframe=AsyncMock(return_value=pd.DataFrame()),
    ):
        response = client.get("/api/v1/options")

    assert response.status_code == 503
