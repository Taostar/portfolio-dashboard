from pydantic import BaseModel
from typing import Optional


class HoldingItem(BaseModel):
    symbol: str
    currency: str
    quantity: int
    current_price: float
    market_value: float
    market_value_cad: float
    portfolio_pct: float
    ema_21m: Optional[float] = None  # EMA(21) of monthly closes
    ema_21q: Optional[float] = None  # EMA(21) of quarterly closes
    change_1d: Optional[float] = None
    change_1w: Optional[float] = None
    change_1m: Optional[float] = None
    change_6m: Optional[float] = None
    change_1y: Optional[float] = None


class HoldingsResponse(BaseModel):
    holdings: list[HoldingItem]
    options: list[HoldingItem] = []
    prev_day_change_pct: Optional[float] = None
