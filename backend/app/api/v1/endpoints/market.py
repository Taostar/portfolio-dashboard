import asyncio

from fastapi import APIRouter, HTTPException

from app.api.v1.schemas.market import VixData
from app.services.vix_service import load_vix_data

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/vix", response_model=VixData)
async def get_vix():
    """Get 1 year of daily VIX closes with the current level and fear zone."""
    data = await asyncio.to_thread(load_vix_data)
    if data is None:
        raise HTTPException(status_code=503, detail="Unable to fetch VIX data")
    return VixData(**data)
