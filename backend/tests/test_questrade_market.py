"""TDD tests for the market-data DataFrame shape, sourced from yfinance
instead of Questrade's historical-candles endpoint (Questrade enforces a
separate, easily-exhausted rate-limit bucket for market data; yfinance is
free and already a backend dependency — see exchange_service.py). Mocking
`yf.download` is unavoidable here (it's a live external API)."""

from datetime import datetime, timedelta
from unittest.mock import patch

import pandas as pd
import pytest

from app.providers._questrade_internal.market import fetch_symbols_market_data_yf


def _multiindex_yf_frame(symbols, dates, closes):
    """Builds a yfinance-shaped multi-ticker DataFrame: columns are a
    (Price, Ticker) MultiIndex, index is a DatetimeIndex — matching what
    `yf.download([...])` returns for more than one ticker."""
    arrays = []
    data = {}
    for symbol in symbols:
        for field in ["Open", "High", "Low", "Close", "Volume"]:
            col = (field, symbol)
            arrays.append(col)
            if field == "Close":
                data[col] = closes[symbol]
            elif field == "Volume":
                data[col] = [1000] * len(dates)
            else:
                data[col] = closes[symbol]
    columns = pd.MultiIndex.from_tuples(arrays)
    df = pd.DataFrame(data, index=pd.DatetimeIndex(dates), columns=columns)
    return df


def test_fetch_symbols_market_data_yf_reshapes_multiindex_to_long_format():
    dates = [datetime(2024, 1, 1), datetime(2024, 1, 2)]
    closes = {"AAPL": [100.5, 101.0], "MSFT": [200.5, 201.0]}
    fake_df = _multiindex_yf_frame(["AAPL", "MSFT"], dates, closes)

    with patch("app.providers._questrade_internal.market.yf.download", return_value=fake_df) as mock_download:
        result = fetch_symbols_market_data_yf(["AAPL", "MSFT"], days=30)

    assert list(result.columns) == ["symbol", "date", "open", "high", "low", "close", "volume"]
    assert set(result["symbol"]) == {"AAPL", "MSFT"}
    aapl = result[result["symbol"] == "AAPL"].sort_values("date")
    assert aapl.iloc[0]["close"] == pytest.approx(100.5)
    assert aapl.iloc[1]["close"] == pytest.approx(101.0)
    mock_download.assert_called_once()


def test_fetch_symbols_market_data_yf_excludes_option_symbols_before_download():
    """Option contracts (e.g. NVDA10Jul26P180.00) aren't real yfinance
    tickers — they must be filtered out before calling yf.download, not
    passed through and left to fail/return empty per-symbol."""
    dates = [datetime(2024, 1, 1)]
    closes = {"AAPL": [100.5]}
    fake_df = _multiindex_yf_frame(["AAPL"], dates, closes)

    with patch("app.providers._questrade_internal.market.yf.download", return_value=fake_df) as mock_download:
        fetch_symbols_market_data_yf(["AAPL", "NVDA10Jul26P180.00"], days=30)

    called_symbols = mock_download.call_args[0][0]
    assert "NVDA10Jul26P180.00" not in called_symbols
    assert called_symbols == ["AAPL"]


def test_fetch_symbols_market_data_yf_empty_symbols_returns_empty_df_with_columns():
    with patch("app.providers._questrade_internal.market.yf.download") as mock_download:
        result = fetch_symbols_market_data_yf([], days=30)

    mock_download.assert_not_called()
    assert result.empty
    assert list(result.columns) == ["symbol", "date", "open", "high", "low", "close", "volume"]


def test_fetch_symbols_market_data_yf_all_options_returns_empty_without_calling_download():
    with patch("app.providers._questrade_internal.market.yf.download") as mock_download:
        result = fetch_symbols_market_data_yf(["NVDA10Jul26P180.00"], days=30)

    mock_download.assert_not_called()
    assert result.empty


def test_fetch_symbols_market_data_yf_single_symbol_flat_columns():
    """yf.download returns flat (non-MultiIndex) columns for a single
    ticker — must be handled without crashing."""
    dates = [datetime(2024, 1, 1), datetime(2024, 1, 2)]
    fake_df = pd.DataFrame(
        {
            "Open": [100.0, 101.0],
            "High": [101.0, 102.0],
            "Low": [99.0, 100.0],
            "Close": [100.5, 101.5],
            "Volume": [1000, 1100],
        },
        index=pd.DatetimeIndex(dates),
    )

    with patch("app.providers._questrade_internal.market.yf.download", return_value=fake_df):
        result = fetch_symbols_market_data_yf(["AAPL"], days=30)

    assert set(result["symbol"]) == {"AAPL"}
    assert list(result.columns) == ["symbol", "date", "open", "high", "low", "close", "volume"]


def test_fetch_symbols_market_data_yf_drops_symbols_with_no_real_data():
    """yf.download still returns a row per date for a delisted/no-data ticker
    in a multi-ticker batch — just filled with NaN, not omitted entirely.
    A symbol with all-NaN close prices must be dropped from the result, or
    it silently poisons every downstream date-intersection (one all-NaN
    column turns pct_change().dropna() into an empty frame for everyone)."""
    dates = [datetime(2024, 1, 1), datetime(2024, 1, 2)]
    closes = {"AAPL": [100.5, 101.0], "DELISTED": [float("nan"), float("nan")]}
    fake_df = _multiindex_yf_frame(["AAPL", "DELISTED"], dates, closes)

    with patch("app.providers._questrade_internal.market.yf.download", return_value=fake_df):
        result = fetch_symbols_market_data_yf(["AAPL", "DELISTED"], days=30)

    assert set(result["symbol"]) == {"AAPL"}
