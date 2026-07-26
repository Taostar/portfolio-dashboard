"""Option-specific enrichment: parses contract metadata from the symbol
string, then fetches Greeks (delta) and underlying price in two batched
Questrade calls. Kept separate from holdings.py because this is options-only
post-processing that runs once on the already-grouped DataFrame, not a
per-row holding transform.
"""

import logging
from typing import Optional

import pandas as pd
from qtrade import Questrade

from app.providers.classifier import get_option_mask, parse_option_symbol

logger = logging.getLogger(__name__)


def enrich_option_rows(df: pd.DataFrame, client: Questrade) -> pd.DataFrame:
    """Adds underlying/expiry_date/option_type/strike/delta/underlying_price/
    itm_otm columns to option rows in `df` (stock/ETF rows are left untouched
    — those columns simply don't get set for them).

    Must run after symbol-level grouping/dedup so each option contract
    appears once (avoids duplicate get_option_quotes/get_quote calls for the
    same contract held across multiple accounts). Requires `symbol_id`
    already present on `df` (stashed by get_account_positions from
    ticker_information's symbolId) to fetch Greeks.

    The whole body runs under a catch-all: this is options-only enrichment
    layered on top of the holdings pipeline that both GET /holdings and
    GET /options depend on, so any unexpected failure here (a live Greeks
    call erroring, an unforeseen data shape) must degrade to "options show
    without extra detail" rather than take down holdings/prices for every
    other position too.
    """
    try:
        return _enrich_option_rows(df, client)
    except Exception as e:
        logger.warning(f"Error enriching option rows, returning holdings unenriched: {e}")
        return df


def _enrich_option_rows(df: pd.DataFrame, client: Questrade) -> pd.DataFrame:
    if df.empty or "symbol" not in df.columns:
        return df

    option_mask = get_option_mask(df)
    if not option_mask.any():
        return df

    # 1. Parse symbol strings — no API call.
    parsed = df.loc[option_mask, "symbol"].apply(parse_option_symbol)
    df.loc[option_mask, "underlying"] = parsed.apply(lambda p: p["underlying"] if p else None)
    df.loc[option_mask, "expiry_date"] = parsed.apply(lambda p: p["expiry_date"] if p else None)
    df.loc[option_mask, "option_type"] = parsed.apply(lambda p: p["option_type"] if p else None)
    df.loc[option_mask, "strike"] = parsed.apply(lambda p: p["strike"] if p else None)

    # 2. Batch delta fetch via get_option_quotes (one call, all option symbolIds).
    delta_by_symbol: dict[str, float] = {}
    if "symbol_id" in df.columns:
        option_ids = [int(sid) for sid in df.loc[option_mask, "symbol_id"].dropna().tolist()]
        if option_ids:
            try:
                resp = client.get_option_quotes(filters=[], option_ids=option_ids)
                for q in resp.get("optionQuotes", []):
                    if q.get("delta") is not None:
                        delta_by_symbol[q["symbol"]] = abs(q["delta"])
            except Exception as e:
                logger.warning(f"Error getting option Greeks: {e}")
    df.loc[option_mask, "delta"] = df.loc[option_mask, "symbol"].map(delta_by_symbol)

    # 3. Batch underlying price fetch via get_quote (one call, unique underlyings).
    underlyings = sorted({u for u in df.loc[option_mask, "underlying"].dropna()})
    price_by_underlying: dict[str, float] = {}
    if underlyings:
        try:
            quotes = client.get_quote(underlyings)
            if isinstance(quotes, dict):
                quotes = [quotes]
            price_by_underlying = {q["symbol"]: q.get("lastTradePrice") for q in quotes}
        except Exception as e:
            logger.warning(f"Error getting underlying quotes: {e}")
    df.loc[option_mask, "underlying_price"] = df.loc[option_mask, "underlying"].map(price_by_underlying)

    # 4. ITM/OTM derived locally from strike vs. underlying price.
    def _itm_otm(row) -> Optional[str]:
        if pd.isna(row.get("underlying_price")) or pd.isna(row.get("strike")):
            return None
        if row["option_type"] == "Call":
            return "ITM" if row["underlying_price"] > row["strike"] else "OTM"
        return "ITM" if row["underlying_price"] < row["strike"] else "OTM"

    df.loc[option_mask, "itm_otm"] = df[option_mask].apply(_itm_otm, axis=1)
    return df
