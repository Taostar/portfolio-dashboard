"""TDD tests for the ported holdings helpers (fix_average_entry_price etc.),
using real (non-mocked) DataFrame data — no network/broker calls involved."""

import pandas as pd
import pytest

from app.providers._questrade_internal.holdings import fix_average_entry_price


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
