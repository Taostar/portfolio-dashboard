"""CBOE Volatility Index (VIX) daily closes + fear-zone label, via yfinance."""

import logging
from typing import Optional

import pandas as pd
import yfinance as yf

from app.core.cache import cached

logger = logging.getLogger(__name__)


def classify_vix_zone(value: float) -> str:
    """Map a VIX level to a market-mood label."""
    if value < 20:
        return "Calm"
    if value < 30:
        return "Elevated Fear"
    if value < 40:
        return "High Fear"
    return "Extreme Fear"


@cached(cache_type="vix")
def load_vix_data() -> Optional[dict]:
    """1 year of daily VIX closes plus the current level and zone label.
    Returns None (never raises) when yfinance has no data."""
    try:
        raw = yf.download(
            "^VIX", period="1y", interval="1d", progress=False, auto_adjust=True
        )
    except Exception as e:
        logger.error(f"Error fetching VIX data: {e}")
        return None

    if raw is None or raw.empty:
        return None

    if isinstance(raw.columns, pd.MultiIndex):
        close_cols = [col for col in raw.columns if col[0] == "Close"]
        if not close_cols:
            return None
        close = raw[close_cols[0]]
    else:
        if "Close" not in raw.columns:
            return None
        close = raw["Close"]

    close = pd.to_numeric(close, errors="coerce").dropna()
    if close.empty:
        return None

    current = float(close.iloc[-1])
    return {
        "dates": [d.strftime("%Y-%m-%d") for d in close.index],
        "close_prices": [float(v) for v in close.values],
        "current": current,
        "zone": classify_vix_zone(current),
    }
