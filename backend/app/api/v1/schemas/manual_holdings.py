from pydantic import BaseModel


class ManualHolding(BaseModel):
    symbol: str
    currency: str
    quantity: int
    open_quantity: int
    average_entry_price: float


class ManualHoldingsConfig(BaseModel):
    holdings: list[ManualHolding] = []
