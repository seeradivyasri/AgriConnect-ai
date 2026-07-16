import asyncio
import uuid
import json
from decimal import Decimal
from datetime import date
from sqlalchemy import select
from redis.asyncio import Redis

from app.database import AsyncSessionLocal
from app.config import settings
from app.models.user import User, UserRole
from app.models.produce import ProduceCatalog, Listing, ListingStatus
from app.services.negotiation_engine import process_negotiation_round

async def main():
    async with AsyncSessionLocal() as db:
        redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
        
        # Seed user
        farmer_id = uuid.uuid4()
        user = User(user_id=farmer_id, phone=str(uuid.uuid4())[:15], role=UserRole.farmer, location_pincode="400001")
        db.add(user)
        await db.commit()
        
        # Seed produce
        produce_id = uuid.uuid4()
        produce = ProduceCatalog(produce_id=produce_id, name_en="Test Tomato", name_te="Tomato Te", unit="kg")
        db.add(produce)
        await db.commit()
        
        # Seed listing
        listing_id = uuid.uuid4()
        listing = Listing(listing_id=listing_id, farmer_id=farmer_id, produce_id=produce_id, quantity=Decimal("100"), vision_grade="A", status=ListingStatus.pending)
        db.add(listing)
        await db.commit()
        
        # Seed today price in redis directly to mock price_service
        today = date.today().isoformat()
        cache_key = f"price:{produce_id}:400:{today}"
        await redis.setex(cache_key, 3600, json.dumps({"price_id": str(uuid.uuid4()), "produce_id": str(produce_id), "region_pincode_prefix": "400", "base_price": "45.00", "platform_margin_pct": "12.00", "valid_date": today, "updated_at": today}))
        
        print(f"Testing on Listing {listing.listing_id} (Grade: {listing.vision_grade})")
        
        # Test farmer ask 50
        decision = await process_negotiation_round(listing.listing_id, Decimal("50"), db, redis)
        print("Decision:", decision)
        
        await redis.close()

if __name__ == "__main__":
    asyncio.run(main())
