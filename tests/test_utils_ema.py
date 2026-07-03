import pandas as pd
import pytest
from utils import _compute_ema_last_value


def make_close_df(n, start=100.0):
    """Build a minimal yfinance-style DataFrame with n monthly rows."""
    dates = pd.date_range("2020-01-01", periods=n, freq="MS")
    prices = [start + i for i in range(n)]
    return pd.DataFrame({"Close": prices}, index=dates)


def test_compute_ema_returns_float_with_sufficient_data():
    df = make_close_df(25)
    result = _compute_ema_last_value(df, span=21)
    assert isinstance(result, float)


def test_compute_ema_returns_none_with_insufficient_data():
    df = make_close_df(20)  # < 21 rows
    result = _compute_ema_last_value(df, span=21)
    assert result is None


def test_compute_ema_returns_none_for_empty_df():
    result = _compute_ema_last_value(pd.DataFrame(), span=21)
    assert result is None


def test_compute_ema_flat_price_equals_that_price():
    # Constant prices → EMA converges to that price
    df = make_close_df(25, start=150.0)
    df["Close"] = 150.0
    result = _compute_ema_last_value(df, span=21)
    assert abs(result - 150.0) < 0.01


def test_compute_ema_handles_multiindex_close():
    dates = pd.date_range("2020-01-01", periods=25, freq="MS")
    prices = [100.0 + i for i in range(25)]
    cols = pd.MultiIndex.from_tuples([("Close", "AAPL")])
    df = pd.DataFrame([[p] for p in prices], index=dates, columns=cols)
    result = _compute_ema_last_value(df, span=21)
    assert isinstance(result, float)


def test_compute_ema_returns_none_when_no_close_column():
    dates = pd.date_range("2020-01-01", periods=25, freq="MS")
    df = pd.DataFrame({"Open": [100.0] * 25}, index=dates)
    result = _compute_ema_last_value(df, span=21)
    assert result is None
