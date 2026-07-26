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
    prev_day_change_pct: Optional[float] = None


class OptionHoldingItem(BaseModel):
    symbol: str
    underlying: str
    currency: str
    quantity: int
    option_type: str  # "Call" | "Put"
    strike: float
    expiry_date: str  # ISO "YYYY-MM-DD"
    dte: int
    current_price: float  # option premium
    market_value: float
    market_value_cad: float
    underlying_price: Optional[float] = None
    itm_otm: Optional[str] = None  # "ITM" | "OTM", None if underlying_price unavailable
    probability_materialized: Optional[float] = None  # abs(delta) from Questrade Greeks


class OptionsSummary(BaseModel):
    notional_exposure_cad: float
    sgov_value_cad: float
    psa_to_value_cad: float
    cash_like_reserves_cad: float


class OptionsResponse(BaseModel):
    options: list[OptionHoldingItem]
    summary: OptionsSummary
