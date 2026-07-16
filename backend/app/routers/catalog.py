from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.database import get_db, get_redis
from app.services import catalog_service
from app.schemas.catalog import CatalogResponse

router = APIRouter(tags=["catalog"])

@router.get("/catalog", response_model=CatalogResponse)
async def get_catalog(
    pincode: str | None = Query(None, description="Filter by pincode"),
    produce_name: str | None = Query(None, description="Filter by produce name"),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    items = await catalog_service.fetch_customer_catalog(
        pincode=pincode, 
        produce_name=produce_name, 
        db=db, 
        redis=redis
    )
    return CatalogResponse(items=items)

from sqlalchemy import select
from app.models.produce import ProduceCatalog

@router.get("/produce")
async def get_produce_list(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ProduceCatalog))
    produce = result.scalars().all()
    return [{"produce_id": str(p.produce_id), "name_en": p.name_en, "name_te": p.name_te, "unit": p.unit.value} for p in produce]
