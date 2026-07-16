import json
from datetime import date
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.models.produce import Listing, ProduceCatalog, PriceTable, ListingStatus, VisionGrade

async def fetch_customer_catalog(
    pincode: Optional[str],
    produce_name: Optional[str],
    db: AsyncSession,
    redis: Redis
) -> List[dict]:
    # 1. Determine region
    region = pincode[:3] if pincode else "all"
    today = date.today()
    cache_key = f"catalog:{pincode or 'all'}:{today}"
    
    # 2. Check cache
    cached = await redis.get(cache_key)
    if cached:
        items = json.loads(cached)
    else:
        # 3. Fetch from DB
        query = (
            select(Listing, ProduceCatalog, PriceTable)
            .join(ProduceCatalog, Listing.produce_id == ProduceCatalog.produce_id)
            .join(PriceTable, PriceTable.produce_id == ProduceCatalog.produce_id)
            .where(
                Listing.status == ListingStatus.accepted,
                Listing.vision_grade.in_([VisionGrade.A, VisionGrade.B]),
                PriceTable.valid_date == today
            )
        )
        
        if region != "all":
            query = query.where(PriceTable.region_pincode_prefix == region)

        result = await db.execute(query)
        rows = result.all()

        items = []
        for listing, catalog, price in rows:
            # Apply 1.05 markup for Grade A, and a 10% discount on that (0.945) for Grade B
            markup = Decimal("1.05")
            if listing.vision_grade == VisionGrade.B:
                markup = Decimal("0.945")
                
            customer_price = round(price.base_price * markup, 2)
            items.append({
                "listing_id": str(listing.listing_id),
                "produce_name": catalog.name_en,
                "unit": catalog.unit.value,
                "customer_price": float(customer_price),
                "photo_url": listing.photo_url,
                "vision_grade": listing.vision_grade.value if listing.vision_grade else None
            })
            
        # Cache for 15 mins (900 seconds)
        await redis.setex(cache_key, 900, json.dumps(items))
        
    # 4. Apply produce_name filter if provided
    if produce_name:
        search_str = produce_name.lower()
        items = [item for item in items if search_str in item["produce_name"].lower()]
        
    return items
