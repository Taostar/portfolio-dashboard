"""Options summary metrics: notional exposure and cash-like reserves."""

import pandas as pd

# Questrade's standard equity-option contract multiplier (100 shares/contract).
# Source: qtrade.Questrade.get_option_chain docstring example ("multiplier": 100).
OPTION_CONTRACT_MULTIPLIER = 100

# Cash-like reserve symbols held specifically to fund option assignment:
# SGOV (USD T-bill ETF) for USD exposure, PSA.TO (CAD high-interest savings
# ETF) for CAD exposure. Hardcoded per explicit user instruction — a config
# system is overkill for two symbols. Precedent: fix_average_entry_price()'s
# "PERSONAL DATA PATCH" comment block in
# app/providers/_questrade_internal/holdings.py.
CASH_LIKE_SYMBOLS: dict[str, str] = {"SGOV": "USD", "PSA.TO": "CAD"}


def calculate_notional_exposure_cad(options_df: pd.DataFrame, fx_rate_usd_to_cad: float) -> float:
    """Sum of strike_price * 100 * |quantity| across all option rows,
    converted to CAD (USD-denominated contracts x fx_rate_usd_to_cad,
    CAD-denominated as-is).

    This is the standard "notional value" definition (upper-bound cash
    exposure if every contract were assigned) — it intentionally does not
    net calls against puts or distinguish covered vs. naked positions; it's
    a conservative summary figure, not a risk model.
    """
    if options_df.empty or "strike" not in options_df.columns:
        return 0.0
    notional_local = (
        options_df["strike"].fillna(0) * OPTION_CONTRACT_MULTIPLIER * options_df["quantity"].abs()
    )
    is_usd = options_df["currency"] == "USD"
    notional_cad = notional_local.where(~is_usd, notional_local * fx_rate_usd_to_cad)
    return float(notional_cad.sum())


def get_cash_like_reserves_cad(full_holdings_df: pd.DataFrame) -> dict:
    """Looks up CASH_LIKE_SYMBOLS rows in the FULL holdings DataFrame (stocks
    + ETFs + options + manual rows, pre-split_holdings) — SGOV/PSA.TO are
    ordinary stock/ETF rows and already carry current_market_value_CAD, no
    extra fetch needed.

    Returns {"sgov_value_cad": float, "psa_to_value_cad": float,
             "total_cad": float}.
    """
    result = {"sgov_value_cad": 0.0, "psa_to_value_cad": 0.0}
    if not full_holdings_df.empty:
        for symbol, key in [("SGOV", "sgov_value_cad"), ("PSA.TO", "psa_to_value_cad")]:
            match = full_holdings_df[full_holdings_df["symbol"] == symbol]
            if not match.empty:
                result[key] = float(match["current_market_value_CAD"].sum())
    result["total_cad"] = result["sgov_value_cad"] + result["psa_to_value_cad"]
    return result
