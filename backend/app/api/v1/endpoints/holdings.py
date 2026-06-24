from fastapi import APIRouter, HTTPException, Query
from app.api.v1.schemas.holdings import HoldingsResponse, HoldingItem
from app.providers.classifier import split_holdings
from app.services.holdings_service import get_holdings_dataframe, load_performance
from app.services.market_value_service import calculate_market_value_changes

router = APIRouter(prefix="/holdings", tags=["holdings"])


def _build_holding_items(df) -> list[HoldingItem]:
    items = []
    for _, row in df.iterrows():
        items.append(
            HoldingItem(
                symbol=row.get("symbol", ""),
                currency=row.get("currency", ""),
                quantity=int(row.get("quantity", 0)),
                current_price=float(row.get("current_price", 0)),
                market_value=float(row.get("current_market_value", 0)),
                market_value_cad=float(row.get("current_market_value_CAD", 0)),
                portfolio_pct=float(row.get("percentage", 0)),
                change_1d=row.get("change_1d"),
                change_1w=row.get("change_1w"),
                change_1m=row.get("change_1m"),
                change_6m=row.get("change_6m"),
                change_1y=row.get("change_1y"),
            )
        )
    return items


@router.get("", response_model=HoldingsResponse)
async def get_holdings():
    """Get all holdings with market value changes, split into stocks/ETFs and options."""
    holdings_df = await get_holdings_dataframe()
    performance_df = await load_performance()

    if holdings_df.empty:
        raise HTTPException(status_code=503, detail="Unable to fetch holdings data")

    stocks_etfs_df, options_df = split_holdings(holdings_df)

    # Calculate market value changes separately for each group; only the
    # stocks/ETF group's prev_day_change feeds the response, matching
    # today's behavior since options shouldn't affect that figure either.
    updated_stocks_etfs_df, prev_day_change = calculate_market_value_changes(
        stocks_etfs_df, performance_df
    )
    updated_options_df, _ = calculate_market_value_changes(options_df, performance_df)

    holdings = _build_holding_items(updated_stocks_etfs_df)
    options = _build_holding_items(updated_options_df)

    return HoldingsResponse(
        holdings=holdings, options=options, prev_day_change_pct=prev_day_change
    )


@router.get("/top/{n}", response_model=HoldingsResponse)
async def get_top_holdings(n: int = 10):
    """Get top N holdings by market value (stocks/ETFs only — options excluded)."""
    holdings_df = await get_holdings_dataframe()
    performance_df = await load_performance()

    if holdings_df.empty:
        raise HTTPException(status_code=503, detail="Unable to fetch holdings data")

    stocks_etfs_df, _ = split_holdings(holdings_df)

    # Calculate market value changes
    updated_df, prev_day_change = calculate_market_value_changes(
        stocks_etfs_df, performance_df
    )

    # Sort by market value and take top N
    updated_df["current_market_value_CAD"] = updated_df["current_market_value_CAD"].astype(float)
    sorted_df = updated_df.sort_values(
        by="current_market_value_CAD", ascending=False
    ).head(n)

    holdings = _build_holding_items(sorted_df)

    return HoldingsResponse(holdings=holdings, prev_day_change_pct=prev_day_change)
