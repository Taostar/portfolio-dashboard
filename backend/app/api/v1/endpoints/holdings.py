import asyncio
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from app.api.v1.schemas.holdings import HoldingsResponse, HoldingItem
from app.providers.classifier import split_holdings
from app.services.ema_service import fetch_ema_indicators
from app.services.holdings_service import get_holdings_dataframe, load_performance
from app.services.market_value_service import calculate_market_value_changes

router = APIRouter(prefix="/holdings", tags=["holdings"])


def _none_if_nan(value):
    """A symbol missing performance data gets `None` assigned into a column
    that already holds floats for other rows — pandas silently upcasts that
    `None` to NaN, which FastAPI's JSON encoder rejects outright. Convert
    back to `None` here, at the boundary where the value leaves pandas."""
    return None if pd.isna(value) else value


def _build_holding_items(df, ema_map: Optional[dict] = None) -> list[HoldingItem]:
    ema_map = ema_map or {}
    items = []
    for _, row in df.iterrows():
        ema = ema_map.get(row.get("symbol", ""), {})
        items.append(
            HoldingItem(
                symbol=row.get("symbol", ""),
                currency=row.get("currency", ""),
                quantity=int(row.get("quantity", 0)),
                current_price=float(row.get("current_price", 0)),
                market_value=float(row.get("current_market_value", 0)),
                market_value_cad=float(row.get("current_market_value_CAD", 0)),
                portfolio_pct=float(row.get("percentage", 0)),
                ema_21m=ema.get("ema_21m"),
                ema_21q=ema.get("ema_21q"),
                change_1d=_none_if_nan(row.get("change_1d")),
                change_1w=_none_if_nan(row.get("change_1w")),
                change_1m=_none_if_nan(row.get("change_1m")),
                change_6m=_none_if_nan(row.get("change_6m")),
                change_1y=_none_if_nan(row.get("change_1y")),
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

    stocks_etfs_df, _ = split_holdings(holdings_df)

    # Calculate market value changes for stocks/ETFs; options are served by
    # the dedicated GET /options endpoint instead.
    updated_stocks_etfs_df, prev_day_change = calculate_market_value_changes(
        stocks_etfs_df, performance_df
    )

    # EMA indicators only apply to stocks/ETFs — option contracts aren't
    # yfinance tickers. Runs in a thread: yfinance is blocking and the
    # first uncached call downloads two candle batches.
    symbols = tuple(sorted(updated_stocks_etfs_df.get("symbol", pd.Series(dtype=str))))
    ema_map = await asyncio.to_thread(fetch_ema_indicators, symbols)

    holdings = _build_holding_items(updated_stocks_etfs_df, ema_map)

    return HoldingsResponse(holdings=holdings, prev_day_change_pct=prev_day_change)


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
