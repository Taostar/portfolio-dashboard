from datetime import date

import pandas as pd
from fastapi import APIRouter, HTTPException

from app.api.v1.schemas.holdings import OptionHoldingItem, OptionsResponse, OptionsSummary
from app.providers.classifier import split_holdings
from app.services.fx_utils import derive_usd_cad_rate
from app.services.holdings_service import get_holdings_dataframe
from app.services.options_service import calculate_notional_exposure_cad, get_cash_like_reserves_cad

router = APIRouter(prefix="/options", tags=["options"])


def _none_if_nan(value):
    return None if pd.isna(value) else value


def _build_option_items(options_df: pd.DataFrame) -> list[OptionHoldingItem]:
    today = date.today()
    items: list[OptionHoldingItem] = []
    for _, row in options_df.iterrows():
        expiry = row.get("expiry_date")
        if expiry is None or pd.isna(expiry):
            # Unparseable symbol — skip rather than show a broken row.
            continue
        dte = (expiry - today).days
        items.append(
            OptionHoldingItem(
                symbol=row.get("symbol", ""),
                underlying=row.get("underlying", ""),
                currency=row.get("currency", ""),
                quantity=int(row.get("quantity", 0)),
                option_type=row.get("option_type", ""),
                strike=float(row.get("strike", 0)),
                expiry_date=str(expiry),
                dte=dte,
                current_price=float(row.get("current_price", 0)),
                market_value=float(row.get("current_market_value", 0)),
                market_value_cad=float(row.get("current_market_value_CAD", 0)),
                underlying_price=_none_if_nan(row.get("underlying_price")),
                itm_otm=_none_if_nan(row.get("itm_otm")),
                probability_materialized=_none_if_nan(row.get("delta")),
            )
        )
    items.sort(key=lambda i: i.dte)
    return items


@router.get("", response_model=OptionsResponse)
async def get_options():
    """Option positions ranked by DTE ascending, plus notional exposure and
    cash-like reserves (SGOV/PSA.TO) computed against the full holdings set."""
    holdings_df = await get_holdings_dataframe()
    if holdings_df.empty:
        raise HTTPException(status_code=503, detail="Unable to fetch holdings data")

    _, options_df = split_holdings(holdings_df)

    items = _build_option_items(options_df)

    fx_rate = derive_usd_cad_rate(holdings_df)
    notional_cad = calculate_notional_exposure_cad(options_df, fx_rate)
    reserves = get_cash_like_reserves_cad(holdings_df)

    return OptionsResponse(
        options=items,
        summary=OptionsSummary(
            notional_exposure_cad=notional_cad,
            sgov_value_cad=reserves["sgov_value_cad"],
            psa_to_value_cad=reserves["psa_to_value_cad"],
            cash_like_reserves_cad=reserves["total_cad"],
        ),
    )
