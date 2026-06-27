from fastapi import APIRouter

from app.api.v1.schemas.manual_holdings import ManualHoldingsConfig
from app.core.cache import clear_cache
from app.services.manual_holdings_service import load_manual_holdings, save_manual_holdings

router = APIRouter(prefix="/manual-holdings", tags=["manual-holdings"])


@router.get("", response_model=ManualHoldingsConfig)
async def get_manual_holdings():
    """Get the current list of manually-configured holdings."""
    return load_manual_holdings()


@router.put("", response_model=ManualHoldingsConfig)
async def update_manual_holdings(config: ManualHoldingsConfig):
    """Replace the list of manually-configured holdings and invalidate caches that depend on it."""
    save_manual_holdings(config)
    clear_cache("holdings")
    clear_cache("performance")
    return config
