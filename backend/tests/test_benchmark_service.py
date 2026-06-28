"""Tests for app/services/benchmark_service.py — Task 7 fix: exclude option
symbols from portfolio_metrics["Symbols"]/["Allocations"] before computing
normalized_allocs_positions, so the "Portfolio" benchmark line reflects only
stock/ETF exposure.
"""

import pandas as pd
import pytest

from app.services.benchmark_service import calculate_normalized_benchmark_data


@pytest.fixture(autouse=True)
def clear_benchmark_cache():
    from app.core.cache import clear_cache
    clear_cache("benchmark")
    yield
    clear_cache("benchmark")


def _make_price_rows(symbol: str, prices: list[float]) -> list[dict]:
    dates = pd.date_range(start="2024-01-01", periods=len(prices), freq="D")
    return [
        {
            "symbol": symbol,
            "date": d.strftime("%Y-%m-%d"),
            "open": p,
            "high": p,
            "low": p,
            "close": p,
            "volume": 1000,
        }
        for d, p in zip(dates, prices)
    ]


def _build_performance_df():
    # AAPL doubles, QQQ/VOO stay flat-ish, the option's price swings wildly
    # (as short-lived contracts do) so including it would visibly move the
    # "Portfolio" series away from what AAPL alone would produce.
    rows = []
    rows += _make_price_rows("AAPL", [100, 110, 120, 130, 140])
    rows += _make_price_rows("QQQ", [400, 401, 402, 403, 404])
    rows += _make_price_rows("VOO", [300, 301, 302, 303, 304])
    rows += _make_price_rows("NVDA10Jul26P180.00", [5, 50, 5, 50, 5])
    return pd.DataFrame(rows)


def test_benchmark_excludes_option_allocation_from_portfolio_series():
    performance_df = _build_performance_df()
    portfolio_metrics = {
        "Symbols": ["AAPL", "NVDA10Jul26P180.00"],
        "Allocations": ["80%", "20%"],
    }

    result = calculate_normalized_benchmark_data(performance_df, portfolio_metrics)

    assert result is not None

    # Compute what the "Portfolio" series would be excluding the option
    # entirely (100% allocated to AAPL, normalized to start at 80 to match
    # the AAPL-only contribution magnitude used by the implementation).
    aapl_prices = pd.Series([100.0, 110.0, 120.0, 130.0, 140.0])
    expected_excluding_option = (aapl_prices / aapl_prices.iloc[0] * 80.0).tolist()

    # Compute what it would be if the option's allocation were wrongly
    # included alongside AAPL's (this is the buggy pre-fix behavior).
    option_prices = pd.Series([5.0, 50.0, 5.0, 50.0, 5.0])
    including_option_contribution = (option_prices / option_prices.iloc[0] * 20.0)
    buggy_with_option = (
        (aapl_prices / aapl_prices.iloc[0] * 80.0) + including_option_contribution
    ).tolist()

    assert result["portfolio"] == pytest.approx(expected_excluding_option)
    assert result["portfolio"] != pytest.approx(buggy_with_option)
