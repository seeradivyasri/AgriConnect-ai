from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.database import get_db, get_redis
from app.utils.dependencies import require_admin
from app.services import admin_service
from app.schemas.admin import PriceCreate

router = APIRouter(prefix="/admin", tags=["admin"])

@router.post("/prices")
async def upsert_price(
    payload: PriceCreate,
    admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    return await admin_service.upsert_price(
        payload.produce_id, payload.region_pincode_prefix,
        payload.base_price, payload.platform_margin_pct,
        payload.valid_date, db, redis
    )

@router.get("/prices")
async def get_prices(
    admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    return await admin_service.fetch_prices(db)

@router.get("/transactions")
async def get_transactions(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    return await admin_service.fetch_transactions(date_from, date_to, db)

@router.get("/listings")
async def get_listings(
    admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    return await admin_service.fetch_all_listings(db)
