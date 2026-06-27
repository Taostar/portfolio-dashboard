"""TDD tests for the ported holdings helpers (fix_average_entry_price etc.),
using real (non-mocked) DataFrame data — no network/broker calls involved."""

from unittest.mock import MagicMock

import pandas as pd
import pytest

from app.providers._questrade_internal.holdings import (
    fix_average_entry_price,
    get_account_positions,
    get_all_accounts_holdings_multi,
)


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


def _make_fake_client(positions_by_account):
    client = MagicMock(spec=["get_account_id", "get_account_positions", "ticker_information", "get_quote"])
    client.get_account_id.return_value = list(positions_by_account.keys())
    client.get_account_positions.side_effect = lambda account_id: positions_by_account[account_id]
    client.ticker_information.side_effect = lambda symbols: [
        {"description": symbols[0], "securityType": "Stock"}
    ]
    client.get_quote.side_effect = lambda symbols: [{"lastTradePrice": 100.0}]
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
