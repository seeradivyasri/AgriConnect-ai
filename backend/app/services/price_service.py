import json
import structlog
from datetime import date
from uuid import UUID
from typing import Optional
from decimal import Decimal
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.produce import PriceTable

logger = structlog.get_logger(__name__)

async def get_today_price(produce_id: UUID, pincode: str, db: AsyncSession, redis: Redis) -> Optional[PriceTable]:
    today = date.today()
    prefix = pincode[:3]
    cache_key = f"price:{produce_id}:{prefix}:{today}"
    
    # Check cache first
    cached_data = await redis.get(cache_key)
    if cached_data:
        logger.info("price_cache_hit", produce_id=str(produce_id), pincode_prefix=prefix)
        data = json.loads(cached_data)
        return PriceTable(
            price_id=UUID(data["price_id"]),
            produce_id=UUID(data["produce_id"]),
            region_pincode_prefix=data["region_pincode_prefix"],
            base_price=Decimal(data["base_price"]),
            platform_margin_pct=Decimal(data["platform_margin_pct"]),
            valid_date=date.fromisoformat(data["valid_date"])
        )
        
    logger.info("price_cache_miss", produce_id=str(produce_id), pincode_prefix=prefix)
    
    # Query Database
    stmt = select(PriceTable).where(
        PriceTable.produce_id == produce_id,
        PriceTable.region_pincode_prefix == prefix,
        PriceTable.valid_date == today
    )
    result = await db.execute(stmt)
    price = result.scalar_one_or_none()
    
    if price:
        # Cache it
        cache_data = {
            "price_id": str(price.price_id),
            "produce_id": str(price.produce_id),
            "region_pincode_prefix": price.region_pincode_prefix,
            "base_price": str(price.base_price),
            "platform_margin_pct": str(price.platform_margin_pct),
            "valid_date": price.valid_date.isoformat()
        }
        await redis.setex(cache_key, 3600, json.dumps(cache_data))
        
    return price
