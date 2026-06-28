"""TDD test for calculate_market_value_changes' CAD exchange-rate sampling.

Uncovered via live verification: a USD holding with current_market_value == 0
(e.g. a personal-data-patch row like BDX whose quote lookup failed and
defaulted price/value to 0.0) can land as the first USD row sampled for the
CAD exchange rate, causing a division by zero that produces inf/NaN and
breaks JSON serialization downstream."""

import pandas as pd
import pytest

from app.services.market_value_service import calculate_market_value_changes


def test_cad_exchange_rate_skips_zero_value_usd_row():
    holdings_df = pd.DataFrame(
        [
            {
                "symbol": "BDX", "currency": "USD", "quantity": 10,
                "current_price": 0.0, "current_market_value": 0.0,
                "current_market_value_CAD": 0.0,
            },
            {
                "symbol": "AAPL", "currency": "USD", "quantity": 5,
                "current_price": 200.0, "current_market_value": 1000.0,
                "current_market_value_CAD": 1350.0,
            },
        ]
    )
    performance_df = pd.DataFrame(
        [
            {"symbol": "AAPL", "date": "2024-01-01", "close": 190.0},
            {"symbol": "AAPL", "date": "2024-01-02", "close": 200.0},
        ]
    )

    result_df, prev_day_change = calculate_market_value_changes(holdings_df, performance_df)

    # AAPL's change_1d must reflect a real (non-NaN, non-inf) computation —
    # a divide-by-zero exchange rate (from BDX's zero-value USD row being
    # sampled) would corrupt this into NaN even though AAPL itself has
    # perfectly good data.
    import numpy as np
    aapl_change = result_df[result_df["symbol"] == "AAPL"]["change_1d"].iloc[0]
    assert aapl_change is not None
    assert np.isfinite(aapl_change)


def test_cad_exchange_rate_uses_correct_rate_skipping_zero_value_row():
    """The exchange rate sample must skip BDX (current_market_value == 0)
    and use AAPL's real 1350/1000 = 1.35 ratio, not divide by zero."""
    holdings_df = pd.DataFrame(
        [
            {
                "symbol": "BDX", "currency": "USD", "quantity": 10,
                "current_price": 0.0, "current_market_value": 0.0,
                "current_market_value_CAD": 0.0,
            },
            {
                "symbol": "AAPL", "currency": "USD", "quantity": 5,
                "current_price": 200.0, "current_market_value": 1000.0,
                "current_market_value_CAD": 1350.0,
            },
        ]
    )
    performance_df = pd.DataFrame(
        [
            {"symbol": "AAPL", "date": "2024-01-01", "close": 100.0},
            {"symbol": "AAPL", "date": "2024-01-02", "close": 200.0},
        ]
    )

    result_df, prev_day_change = calculate_market_value_changes(holdings_df, performance_df)

    # AAPL: current=1000 (200*5), prev=100*5=500 -> change_1d = (1000-500)/500 = 1.0
    aapl_change = result_df[result_df["symbol"] == "AAPL"]["change_1d"].iloc[0]
    assert aapl_change == pytest.approx(1.0)

    # Portfolio-level prev_day_change uses the correct (1.35, not NaN/0) CAD
    # rate: prev_market_value_cad = 500 * 1.35 = 675; current = 1000*1.35=1350
    # (BDX contributes 0 to both since it has no performance row).
    assert prev_day_change == pytest.approx((1350.0 - 675.0) / 675.0)
