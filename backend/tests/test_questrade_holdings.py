"""TDD tests for the ported holdings helpers (fix_average_entry_price etc.),
using real (non-mocked) DataFrame data — no network/broker calls involved."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.providers._questrade_internal.holdings import (
    add_additional_rows,
    fix_average_entry_price,
    get_account_positions,
    get_all_accounts_holdings_multi,
)


def _multiindex_yf_frame(symbols, closes):
    """Mirrors test_questrade_market.py's helper: yfinance's (Price, Ticker)
    MultiIndex column shape for a multi-symbol yf.download call."""
    dates = pd.date_range("2024-01-01", periods=len(next(iter(closes.values()))))
    arrays = []
    data = {}
    for symbol in symbols:
        for field in ["Open", "High", "Low", "Close", "Volume"]:
            col = (field, symbol)
            arrays.append(col)
            data[col] = closes[symbol] if field == "Close" else [1000] * len(dates)
    columns = pd.MultiIndex.from_tuples(arrays)
    return pd.DataFrame(data, index=pd.DatetimeIndex(dates), columns=columns)


def test_fix_average_entry_price_overwrites_known_symbol_only():
    df = pd.DataFrame(
        [
            {"symbol": "AAPL", "average_entry_price": 999.0, "quantity": 5},
            {"symbol": "ZZZZ", "average_entry_price": 42.0, "quantity": 1},
        ]
    )

    result = fix_average_entry_price(df)

    # AAPL has a hardcoded correct price (130) that must overwrite the
    # passed-in (deliberately wrong, 999.0) value.
    aapl_row = result[result["symbol"] == "AAPL"].iloc[0]
    assert aapl_row["average_entry_price"] == pytest.approx(130.0)

    # Unknown symbol ZZZZ is left untouched.
    zzzz_row = result[result["symbol"] == "ZZZZ"].iloc[0]
    assert zzzz_row["average_entry_price"] == pytest.approx(42.0)

    # Other columns/row count are unaffected.
    assert len(result) == 2
    assert set(result["symbol"]) == {"AAPL", "ZZZZ"}


def test_fix_average_entry_price_no_symbol_column_returns_df_unchanged():
    df = pd.DataFrame([{"foo": "bar"}])
    result = fix_average_entry_price(df)
    pd.testing.assert_frame_equal(result, df)


def test_add_additional_rows_fetches_price_from_yfinance_not_questrade():
    """Manual holdings are explicitly "not reachable via the Questrade API" —
    their current price must come from yfinance, not client.get_quote. This
    is also what actually fixed a real bug: Questrade's quote lookup for
    these symbols was unreliable (shares the same rate-limit bucket already
    documented as tripping 403s in market.py, and/or doesn't recognize every
    manually-tracked symbol), silently leaving current_price at 0 for newly
    added manual holdings — recalculating market value as 0 downstream."""
    df = pd.DataFrame([{"symbol": "AAPL", "current_price": 150.0, "current_market_value": 1500.0}])
    fake_yf_df = _multiindex_yf_frame(["SGOV", "PSA.TO"], {"SGOV": [100.5, 100.55], "PSA.TO": [50.1, 50.2]})
    client = MagicMock(spec=["get_quote"])

    with patch("app.providers._questrade_internal.holdings.yf.download", return_value=fake_yf_df) as mock_download, \
         patch("app.providers._questrade_internal.holdings.load_manual_holdings") as mock_load:
        from app.api.v1.schemas.manual_holdings import ManualHolding, ManualHoldingsConfig

        mock_load.return_value = ManualHoldingsConfig(
            holdings=[
                ManualHolding(symbol="SGOV", currency="USD", quantity=100, open_quantity=100, average_entry_price=100.0),
                ManualHolding(symbol="PSA.TO", currency="CAD", quantity=200, open_quantity=200, average_entry_price=50.0),
            ]
        )
        result = add_additional_rows(df, client)

    sgov_row = result[result["symbol"] == "SGOV"].iloc[0]
    psa_row = result[result["symbol"] == "PSA.TO"].iloc[0]

    assert sgov_row["current_price"] == pytest.approx(100.55)
    assert sgov_row["current_market_value"] == pytest.approx(100.55 * 100)
    assert psa_row["current_price"] == pytest.approx(50.2)
    assert psa_row["current_market_value"] == pytest.approx(50.2 * 200)
    client.get_quote.assert_not_called()
    mock_download.assert_called_once()


def test_add_additional_rows_missing_yfinance_data_defaults_to_zero_price():
    """A symbol yfinance has no data for (delisted, typo, etc.) must default
    to price 0 rather than raise — matches this module's existing
    fail-soft convention for external data lookups."""
    df = pd.DataFrame([{"symbol": "AAPL", "current_price": 150.0, "current_market_value": 1500.0}])
    client = MagicMock(spec=["get_quote"])

    with patch("app.providers._questrade_internal.holdings.yf.download", side_effect=Exception("network error")):
        with patch("app.providers._questrade_internal.holdings.load_manual_holdings") as mock_load:
            from app.api.v1.schemas.manual_holdings import ManualHolding, ManualHoldingsConfig

            mock_load.return_value = ManualHoldingsConfig(
                holdings=[
                    ManualHolding(symbol="UNKNOWNTICKER", currency="USD", quantity=10, open_quantity=10, average_entry_price=5.0),
                ]
            )
            result = add_additional_rows(df, client)

    row = result[result["symbol"] == "UNKNOWNTICKER"].iloc[0]
    assert row["current_price"] == 0.0
    assert row["current_market_value"] == 0.0


def _make_fake_client(positions_by_account):
    """Mimics the REAL qtrade contract: ticker_information/get_quote called
    with a single-item list collapse to a bare dict, not a list wrapping one
    dict — this call site (get_account_positions) always passes [symbol], a
    single-item list, so that's the shape it must handle."""
    client = MagicMock(spec=["get_account_id", "get_account_positions", "ticker_information", "get_quote"])
    client.get_account_id.return_value = list(positions_by_account.keys())
    client.get_account_positions.side_effect = lambda account_id: positions_by_account[account_id]
    client.ticker_information.side_effect = lambda symbols: {
        "description": symbols[0], "securityType": "Stock", "symbolId": 999
    }
    client.get_quote.side_effect = lambda symbols: {"lastTradePrice": 100.0}
    return client


def test_get_account_positions_reuses_shared_symbol_cache_across_accounts():
    """A symbol held in two accounts must only trigger one ticker_information
    and one get_quote call when a shared symbol_cache dict is passed in —
    this is what keeps a multi-account fetch from tripping Questrade's rate
    limit on overlapping symbols."""
    positions_by_account = {
        "111": [{"symbol": "AAPL", "currentMarketValue": 1000.0, "openQuantity": 10}],
        "222": [{"symbol": "AAPL", "currentMarketValue": 500.0, "openQuantity": 5}],
    }
    client = _make_fake_client(positions_by_account)

    symbol_cache = {}
    get_account_positions(client, "111", symbol_cache=symbol_cache)
    get_account_positions(client, "222", symbol_cache=symbol_cache)

    assert client.ticker_information.call_count == 1
    assert client.get_quote.call_count == 1


def test_get_account_positions_without_cache_fetches_every_time():
    """Default (no shared cache passed) preserves today's per-call behavior —
    callers like the MCP single-account tool that don't share a cache across
    multiple get_account_positions calls aren't affected."""
    positions_by_account = {
        "111": [{"symbol": "AAPL", "currentMarketValue": 1000.0, "openQuantity": 10}],
        "222": [{"symbol": "AAPL", "currentMarketValue": 500.0, "openQuantity": 5}],
    }
    client = _make_fake_client(positions_by_account)

    get_account_positions(client, "111")
    get_account_positions(client, "222")

    assert client.ticker_information.call_count == 2
    assert client.get_quote.call_count == 2


def test_get_account_positions_populates_security_type_from_cache():
    positions_by_account = {
        "111": [{"symbol": "AAPL", "currentMarketValue": 1000.0, "openQuantity": 10}],
    }
    client = _make_fake_client(positions_by_account)

    result = get_account_positions(client, "111", symbol_cache={})

    assert result["holdings"][0]["security_type"] == "Stock"


def test_get_account_positions_populates_symbol_id_from_bare_dict_ticker_info():
    """Regression: ticker_information([symbol]) returns a bare dict (real
    qtrade behavior for a single-item list), not a list wrapping one dict.
    The old code did `ticker_info[0]` unconditionally, which raised KeyError
    on a dict and was silently swallowed by the surrounding except — leaving
    symbol_id (and security_type) always empty in production. This must now
    populate correctly from the dict shape."""
    positions_by_account = {
        "111": [{"symbol": "AAPL", "currentMarketValue": 1000.0, "openQuantity": 10}],
    }
    client = _make_fake_client(positions_by_account)

    result = get_account_positions(client, "111", symbol_cache={})

    assert result["holdings"][0]["symbol_id"] == 999
    assert result["holdings"][0]["security_type"] == "Stock"


def test_get_account_positions_current_price_falls_back_to_bare_dict_quote():
    """Regression: get_quote([symbol]) also collapses to a bare dict for a
    single symbol. The old code only unwrapped a list return
    (`quotes[0] if isinstance(quotes, list) else {}`), so a real dict return
    was discarded into `quote = {}` — meaning the current_price fallback
    (used whenever the position itself has no currentPrice) silently never
    worked. Position deliberately omits currentPrice to force the fallback."""
    positions_by_account = {
        "111": [{"symbol": "AAPL", "currentMarketValue": 1000.0, "openQuantity": 10}],
    }
    client = _make_fake_client(positions_by_account)

    result = get_account_positions(client, "111", symbol_cache={})

    assert result["holdings"][0]["current_price"] == 100.0


def test_get_all_accounts_holdings_multi_shares_symbol_cache_across_clients_and_accounts():
    """End-to-end: two logins (clients), each with two accounts, all holding
    the same symbol — must only call ticker_information/get_quote once total
    for that symbol, not once per (client, account) pair."""
    positions_by_account_1 = {
        "111": [{"symbol": "AAPL", "currentMarketValue": 1000.0, "openQuantity": 10}],
        "222": [{"symbol": "AAPL", "currentMarketValue": 500.0, "openQuantity": 5}],
    }
    positions_by_account_2 = {
        "333": [{"symbol": "AAPL", "currentMarketValue": 750.0, "openQuantity": 7}],
    }
    client_1 = _make_fake_client(positions_by_account_1)
    client_2 = _make_fake_client(positions_by_account_2)

    # as_dataframe=False, group_by_symbol=False: skips the DataFrame/FX path
    # entirely (no get_account_balances/add_additional_rows calls to mock).
    get_all_accounts_holdings_multi([client_1, client_2], as_dataframe=False, group_by_symbol=False)

    total_ticker_calls = client_1.ticker_information.call_count + client_2.ticker_information.call_count
    assert total_ticker_calls == 1
