"""Tests for app.services.ema_service — EMA(21) on monthly/quarterly candles.

_compute_ema_last_value runs for real against synthetic series;
fetch_ema_indicators mocks yf.download (I/O boundary).
"""

from unittest.mock import patch

import pandas as pd
import pytest

from app.core.cache import clear_cache
from app.services.ema_service import _compute_ema_last_value, fetch_ema_indicators


@pytest.fixture(autouse=True)
def _clear_ema_cache():
    clear_cache("ema")
    yield
    clear_cache("ema")


def make_close_series(n, start=100.0):
    dates = pd.date_range("2020-01-01", periods=n, freq="MS")
    return pd.Series([start + i for i in range(n)], index=dates)


def test_compute_ema_returns_float_with_sufficient_data():
    result = _compute_ema_last_value(make_close_series(25), span=21)
    assert isinstance(result, float)


def test_compute_ema_returns_none_with_insufficient_data():
    result = _compute_ema_last_value(make_close_series(20), span=21)
    assert result is None


def test_compute_ema_returns_none_for_empty_series():
    result = _compute_ema_last_value(pd.Series(dtype=float), span=21)
    assert result is None


def test_compute_ema_flat_price_equals_that_price():
    series = make_close_series(25)
    series[:] = 150.0
    result = _compute_ema_last_value(series, span=21)
    assert abs(result - 150.0) < 0.01


def test_compute_ema_ignores_non_numeric_values():
    series = make_close_series(25).astype(object)
    series.iloc[0] = "not-a-number"
    result = _compute_ema_last_value(series, span=21)
    assert isinstance(result, float)


def _multiindex_download(symbols, n=30):
    """Synthetic yf.download batch result: MultiIndex columns (Field, Symbol)."""
    dates = pd.date_range("2020-01-01", periods=n, freq="MS")
    cols = pd.MultiIndex.from_product([["Close", "Open"], symbols])
    data = {col: [100.0 + i for i in range(n)] for col in cols}
    return pd.DataFrame(data, index=dates)


def test_fetch_ema_indicators_returns_values_per_symbol():
    with patch(
        "app.services.ema_service.yf.download",
        return_value=_multiindex_download(["AAPL", "MSFT"]),
    ):
        result = fetch_ema_indicators(("AAPL", "MSFT"))

    for symbol in ("AAPL", "MSFT"):
        assert isinstance(result[symbol]["ema_21m"], float)
        assert isinstance(result[symbol]["ema_21q"], float)


def test_fetch_ema_indicators_skips_option_symbols():
    with patch(
        "app.services.ema_service.yf.download",
        return_value=_multiindex_download(["AAPL"]),
    ) as mock_download:
        result = fetch_ema_indicators(("AAPL", "NVDA10Jul26P180.00"))

    assert result["NVDA10Jul26P180.00"] == {"ema_21m": None, "ema_21q": None}
    for call in mock_download.call_args_list:
        assert "NVDA10Jul26P180.00" not in call.args[0]


def test_fetch_ema_indicators_returns_none_when_download_fails():
    with patch(
        "app.services.ema_service.yf.download", side_effect=Exception("network down")
    ):
        result = fetch_ema_indicators(("AAPL",))

    assert result["AAPL"] == {"ema_21m": None, "ema_21q": None}


def test_fetch_ema_indicators_returns_none_for_symbol_missing_from_batch():
    with patch(
        "app.services.ema_service.yf.download",
        return_value=_multiindex_download(["AAPL"]),
    ):
        result = fetch_ema_indicators(("AAPL", "DELISTED"))

    assert isinstance(result["AAPL"]["ema_21m"], float)
    assert result["DELISTED"] == {"ema_21m": None, "ema_21q": None}
