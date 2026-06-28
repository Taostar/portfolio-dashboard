"""Tests for app/services/correlation_service.py — Task 7 fix: filter out
option symbols before deriving portfolio_symbols, so a short-lived option's
sparse price history doesn't collapse the common-trading-day intersection
across all symbols below the 30-day minimum.
"""

import pandas as pd
import pytest

from app.services.correlation_service import calculate_portfolio_correlation


def _make_performance_df(symbol: str, n_days: int, start_price: float = 100.0) -> pd.DataFrame:
    dates = pd.date_range(end="2024-06-30", periods=n_days, freq="D")
    rows = []
    price = start_price
    for i, d in enumerate(dates):
        # Small deterministic wiggle so pct_change/corr isn't degenerate.
        price = start_price + (i % 5)
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


@pytest.fixture(autouse=True)
def clear_correlation_cache():
    from app.core.cache import clear_cache
    clear_cache("correlation")
    yield
    clear_cache("correlation")


def _build_holdings_df():
    return pd.DataFrame(
        [
            {"symbol": "AAPL", "percentage": 40, "security_type": "Stock"},
            {"symbol": "MSFT", "percentage": 40, "security_type": "Stock"},
            {"symbol": "NVDA10Jul26P180.00", "percentage": 20, "security_type": "Option"},
        ]
    )


def _build_performance_df():
    # Stocks have 60+ days of shared history; the option only has ~10 days,
    # all within the stocks' date range, so if it were included in
    # portfolio_symbols, the intersection of common dates would collapse to
    # ~10 (< 30).
    aapl_df = _make_performance_df("AAPL", 65)
    msft_df = _make_performance_df("MSFT", 65, start_price=200.0)
    option_df = _make_performance_df("NVDA10Jul26P180.00", 10, start_price=5.0)
    return pd.concat([aapl_df, msft_df, option_df], ignore_index=True)


def test_correlation_excludes_options_so_matrix_is_populated():
    holdings_df = _build_holdings_df()
    performance_df = _build_performance_df()

    corr_matrix, weighted_corr_matrix, weighted_corr = calculate_portfolio_correlation(
        holdings_df, performance_df
    )

    assert corr_matrix is not None
    assert weighted_corr_matrix is not None
    assert weighted_corr is not None
    # Only the stock symbols should appear — the option must be excluded.
    assert set(corr_matrix.columns) == {"AAPL", "MSFT"}
    assert set(corr_matrix.index) == {"AAPL", "MSFT"}


def test_correlation_excludes_options_even_when_only_symbol_is_regex_classified():
    # No security_type column at all -> split_holdings falls back to regex.
    holdings_df = pd.DataFrame(
        [
            {"symbol": "AAPL", "percentage": 40},
            {"symbol": "MSFT", "percentage": 40},
            {"symbol": "NVDA10Jul26P180.00", "percentage": 20},
        ]
    )
    performance_df = _build_performance_df()

    corr_matrix, _, _ = calculate_portfolio_correlation(holdings_df, performance_df)

    assert corr_matrix is not None
    assert "NVDA10Jul26P180.00" not in corr_matrix.columns
