"""Classifies holdings as options vs. stocks/ETFs.

Prefers the `security_type` field that `QuestradeProvider.get_holdings()` stashes on each holding
(Questrade's `ticker_information()` `securityType`, e.g. `"Option"` or `"Stock"`), falling back to a
regex match on the symbol format for holdings that don't carry that field (e.g. a future broker that
doesn't supply it, or a row that predates this field).
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

import pandas as pd

_OPTION_SYMBOL_RE = re.compile(
    r"^(?P<underlying>[A-Z]+)(?P<day>\d{1,2})(?P<month>[A-Za-z]{3})"
    r"(?P<year>\d{2})(?P<option_type>[CP])(?P<strike>\d+(?:\.\d+)?)$"
)


def is_option_symbol(symbol: str, symbol_info: dict | None = None) -> bool:
    """True if `symbol` is an options contract, not a stock/ETF.

    Prefers Questrade's `securityType` field (passed via `symbol_info`, e.g.
    `{"security_type": "Option"}` — matching the key QuestradeProvider stashes on each holding) when
    available, falling back to a regex match on the symbol format for holdings that don't carry it.
    """
    if symbol_info and symbol_info.get("security_type"):
        return symbol_info["security_type"] == "Option"
    return bool(_OPTION_SYMBOL_RE.match(symbol))


def get_option_mask(holdings_df: pd.DataFrame) -> pd.Series:
    """Per-row boolean mask of which holdings are options, via is_option_symbol
    (security_type-aware where available). Factored out of split_holdings so
    other callers (e.g. the option-enrichment pass) classify identically —
    two independently-computed masks disagreeing would silently drop or
    misclassify rows.
    """
    if "security_type" in holdings_df.columns:
        return holdings_df.apply(
            lambda row: is_option_symbol(row["symbol"], {"security_type": row["security_type"]}),
            axis=1,
        )
    return holdings_df["symbol"].apply(is_option_symbol)


def split_holdings(holdings_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (stocks_etfs_df, options_df), splitting on is_option_symbol per row."""
    is_option = get_option_mask(holdings_df)
    options_df = holdings_df[is_option]
    stocks_etfs_df = holdings_df[~is_option]
    return stocks_etfs_df, options_df


def parse_option_symbol(symbol: str) -> Optional[dict]:
    """Parses a Questrade compact option symbol into its components.

    Worked example: "NVDA10Jul26P180.00" ->
        {"underlying": "NVDA", "expiry_date": date(2026, 7, 10),
         "option_type": "Put", "strike": 180.0}

    Returns None if `symbol` doesn't match the option symbol format, or if it
    matches structurally but the day/month/year isn't a real calendar date
    (e.g. day 31 of a 30-day month) — mirrors is_option_symbol's regex
    fallback, so callers can treat None the same way as "not an option"
    rather than crash on a single malformed/unexpected symbol.
    """
    match = _OPTION_SYMBOL_RE.match(symbol)
    if not match:
        return None
    try:
        expiry_date = datetime.strptime(
            f"{match.group('day')}{match.group('month')}{match.group('year')}", "%d%b%y"
        ).date()
    except ValueError:
        return None
    return {
        "underlying": match.group("underlying"),
        "expiry_date": expiry_date,
        "option_type": "Call" if match.group("option_type") == "C" else "Put",
        "strike": float(match.group("strike")),
    }
