"""TDD tests for enrich_option_rows — Greeks/underlying-price enrichment for
option rows in the grouped holdings DataFrame, using a mocked Questrade
client (no network calls)."""

from datetime import date
from unittest.mock import MagicMock

import pandas as pd
import pytest

from app.providers._questrade_internal.options import enrich_option_rows


def _grouped_df():
    return pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "currency": "USD",
                "quantity": 10,
                "current_price": 150.0,
                "symbol_id": 111,
                "security_type": "Stock",
            },
            {
                "symbol": "NVDA10Jul26P180.00",
                "currency": "USD",
                "quantity": -1,
                "current_price": 5.0,
                "symbol_id": 222,
                "security_type": "Option",
            },
        ]
    )


def _make_client(delta=-0.35, underlying_price=190.0):
    client = MagicMock(spec=["get_option_quotes", "get_quote"])
    client.get_option_quotes.return_value = {
        "optionQuotes": [
            {"symbol": "NVDA10Jul26P180.00", "underlying": "NVDA", "delta": delta}
        ]
    }
    client.get_quote.return_value = [{"symbol": "NVDA", "lastTradePrice": underlying_price}]
    return client


def test_enrich_option_rows_parses_symbol_fields():
    df = _grouped_df()
    client = _make_client()

    result = enrich_option_rows(df, client)

    option_row = result[result["symbol"] == "NVDA10Jul26P180.00"].iloc[0]
    assert option_row["underlying"] == "NVDA"
    assert option_row["expiry_date"] == date(2026, 7, 10)
    assert option_row["option_type"] == "Put"
    assert option_row["strike"] == pytest.approx(180.0)


def test_enrich_option_rows_stock_rows_untouched():
    df = _grouped_df()
    client = _make_client()

    result = enrich_option_rows(df, client)

    stock_row = result[result["symbol"] == "AAPL"].iloc[0]
    assert pd.isna(stock_row.get("underlying"))
    assert pd.isna(stock_row.get("strike"))


def test_enrich_option_rows_fetches_delta_and_underlying_price():
    df = _grouped_df()
    client = _make_client(delta=-0.35, underlying_price=190.0)

    result = enrich_option_rows(df, client)

    option_row = result[result["symbol"] == "NVDA10Jul26P180.00"].iloc[0]
    # abs(delta) — probability of assignment is reported as a positive figure.
    assert option_row["delta"] == pytest.approx(0.35)
    assert option_row["underlying_price"] == pytest.approx(190.0)

    client.get_option_quotes.assert_called_once_with(filters=[], option_ids=[222])
    client.get_quote.assert_called_once_with(["NVDA"])


def test_enrich_option_rows_put_itm_when_underlying_below_strike():
    df = _grouped_df()
    # Strike is 180; underlying at 150 -> a put is ITM.
    client = _make_client(underlying_price=150.0)

    result = enrich_option_rows(df, client)

    option_row = result[result["symbol"] == "NVDA10Jul26P180.00"].iloc[0]
    assert option_row["itm_otm"] == "ITM"


def test_enrich_option_rows_put_otm_when_underlying_above_strike():
    df = _grouped_df()
    client = _make_client(underlying_price=200.0)

    result = enrich_option_rows(df, client)

    option_row = result[result["symbol"] == "NVDA10Jul26P180.00"].iloc[0]
    assert option_row["itm_otm"] == "OTM"


def test_enrich_option_rows_call_itm_when_underlying_above_strike():
    df = pd.DataFrame(
        [
            {
                "symbol": "AAPL2Jul26C150.00",
                "currency": "USD",
                "quantity": 1,
                "current_price": 5.0,
                "symbol_id": 333,
                "security_type": "Option",
            },
        ]
    )
    client = MagicMock(spec=["get_option_quotes", "get_quote"])
    client.get_option_quotes.return_value = {
        "optionQuotes": [{"symbol": "AAPL2Jul26C150.00", "underlying": "AAPL", "delta": 0.6}]
    }
    client.get_quote.return_value = [{"symbol": "AAPL", "lastTradePrice": 160.0}]

    result = enrich_option_rows(df, client)

    option_row = result.iloc[0]
    assert option_row["itm_otm"] == "ITM"
    assert option_row["delta"] == pytest.approx(0.6)


def test_enrich_option_rows_no_options_returns_df_unchanged():
    df = pd.DataFrame([{"symbol": "AAPL", "currency": "USD", "quantity": 10, "symbol_id": 111}])
    client = MagicMock(spec=["get_option_quotes", "get_quote"])

    result = enrich_option_rows(df, client)

    pd.testing.assert_frame_equal(result, df)
    client.get_option_quotes.assert_not_called()
    client.get_quote.assert_not_called()


def test_enrich_option_rows_greeks_fetch_failure_leaves_delta_null():
    df = _grouped_df()
    client = MagicMock(spec=["get_option_quotes", "get_quote"])
    client.get_option_quotes.side_effect = Exception("rate limited")
    client.get_quote.return_value = [{"symbol": "NVDA", "lastTradePrice": 190.0}]

    result = enrich_option_rows(df, client)

    option_row = result[result["symbol"] == "NVDA10Jul26P180.00"].iloc[0]
    assert pd.isna(option_row["delta"])
    # Underlying price fetch still succeeds independently.
    assert option_row["underlying_price"] == pytest.approx(190.0)
