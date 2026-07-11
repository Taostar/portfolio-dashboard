from pydantic import BaseModel


class VixData(BaseModel):
    dates: list[str]
    close_prices: list[float]
    current: float
    zone: str
