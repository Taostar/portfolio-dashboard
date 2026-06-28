"""Classifies holdings as options vs. stocks/ETFs.

Prefers the `security_type` field that `QuestradeProvider.get_holdings()` stashes on each holding
(Questrade's `ticker_information()` `securityType`, e.g. `"Option"` or `"Stock"`), falling back to a
regex match on the symbol format for holdings that don't carry that field (e.g. a future broker that
doesn't supply it, or a row that predates this field).
"""

from __future__ import annotations

import re

import pandas as pd

_OPTION_SYMBOL_RE = re.compile(r"^[A-Z]+\d{1,2}[A-Za-z]{3}\d{2}[CP]\d+(\.\d+)?$")


def is_option_symbol(symbol: str, symbol_info: dict | None = None) -> bool:
    """True if `symbol` is an options contract, not a stock/ETF.

    Prefers Questrade's `securityType` field (passed via `symbol_info`, e.g.
    `{"security_type": "Option"}` — matching the key QuestradeProvider stashes on each holding) when
    available, falling back to a regex match on the symbol format for holdings that don't carry it.
    """
    if symbol_info and symbol_info.get("security_type"):
        return symbol_info["security_type"] == "Option"
    return bool(_OPTION_SYMBOL_RE.match(symbol))


def split_holdings(holdings_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (stocks_etfs_df, options_df), splitting on is_option_symbol per row."""
    if "security_type" in holdings_df.columns:
        is_option = holdings_df.apply(
            lambda row: is_option_symbol(row["symbol"], {"security_type": row["security_type"]}),
            axis=1,
        )
    else:
        is_option = holdings_df["symbol"].apply(is_option_symbol)

    options_df = holdings_df[is_option]
    stocks_etfs_df = holdings_df[~is_option]
    return stocks_etfs_df, options_df
