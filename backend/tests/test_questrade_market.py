"""TDD test for the market-data DataFrame shape. Mocking the qtrade client is
unavoidable here (it's a live broker API) — kept to the minimum surface
needed: a fake client exposing only `get_historical_data`."""

from datetime import datetime, timedelta

import pandas as pd
import pytest

from app.providers._questrade_internal.market import fetch_symbols_market_data


class _FakeClient:
    """Exposes only get_historical_data, returning fixed candle dicts per
    symbol, with one symbol deliberately missing a day (to exercise ffill)
    and one symbol returning no data at all (to exercise the skip-on-failure
    behavior)."""

    def get_historical_data(self, symbol, start_date_str, end_date_str, interval):
        if symbol == "AAPL":
            return [
                {"start": "2024-01-01T00:00:00.000000-05:00", "open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 1000},
                # 2024-01-02 missing on purpose -> exercised via the second AAPL row's gap below
                {"start": "2024-01-03T00:00:00.000000-05:00", "open": None, "high": None, "low": None, "close": None, "volume": None},
            ]
        if symbol == "MSFT":
            return [
                {"start": "2024-01-01T00:00:00.000000-05:00", "open": 200, "high": 201, "low": 199, "close": 200.5, "volume": 500},
            ]
        if symbol == "BADSYMBOL":
            raise RuntimeError("simulated upstream failure")
        return []


def test_fetch_symbols_market_data_has_expected_columns_and_ffill():
    client = _FakeClient()
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2024, 1, 3)

    df = fetch_symbols_market_data(client, ["AAPL", "MSFT", "BADSYMBOL"], start_date, end_date)

    assert list(df.columns) == ["symbol", "date", "open", "high", "low", "close", "volume"]

    # BADSYMBOL raised inside get_historical_data -> skipped, not raised.
    assert "BADSYMBOL" not in set(df["symbol"])
    assert set(df["symbol"]) == {"AAPL", "MSFT"}

    # AAPL's second row had None values -> forward-filled from the first row.
    aapl = df[df["symbol"] == "AAPL"].sort_values("date")
    assert aapl.iloc[1]["close"] == pytest.approx(100.5)
    assert aapl.iloc[1]["open"] == pytest.approx(100)

    # Sorted by symbol, date.
    assert list(df["symbol"]) == sorted(df["symbol"])


def test_fetch_symbols_market_data_empty_symbols_returns_empty_df_with_columns():
    client = _FakeClient()
    df = fetch_symbols_market_data(client, [], datetime.now() - timedelta(days=1), datetime.now())
    assert df.empty
    assert list(df.columns) == ["symbol", "date", "open", "high", "low", "close", "volume"]
