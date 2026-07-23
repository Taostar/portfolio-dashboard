import pandas as pd


def derive_usd_cad_rate(holdings_df: pd.DataFrame) -> float:
    """USD->CAD rate implied by a holdings row's own current_market_value_CAD
    / current_market_value ratio.

    Samples a nonzero-value USD row to avoid divide-by-zero on a row whose
    quote lookup failed (e.g. a personal-data-patch holding defaulted to
    0.0); falls back to 1.0 if no such row exists.
    """
    usd_rows = holdings_df[
        (holdings_df["currency"] == "USD") & (holdings_df["current_market_value"] != 0)
    ]
    sample = usd_rows.head(1)
    if sample.empty:
        return 1.0
    return float(sample["current_market_value_CAD"].iloc[0] / sample["current_market_value"].iloc[0])
