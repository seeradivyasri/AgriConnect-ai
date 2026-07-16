import asyncio
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from redis.asyncio import Redis

from app.database import AsyncSessionLocal, get_redis
from app.models.user import User
from app.models.produce import Listing, ListingStatus, ProduceCatalog, PriceTable, VisionGrade, UnitType
from app.models.transaction import Order
from app.services import cart_service, order_service, chat_service

async def test_phase9():
    async with AsyncSessionLocal() as db:
        # Get redis client directly since get_redis is a dependency generator
        redis = None
        async for r in get_redis():
            redis = r
            break
            
        print("\n--- Setup Dummy Data ---")
        customer_id = uuid4()
        farmer_id = uuid4()
        produce_id = uuid4()
        listing_id = uuid4()
        
        from datetime import date
        today = date.today()
        
        db.add(User(user_id=customer_id, phone="9999", name="C", role="customer", verified=True))
        db.add(User(user_id=farmer_id, phone="8888", name="F", role="farmer", verified=True))
        db.add(ProduceCatalog(produce_id=produce_id, name_en="Tomato", name_te="టమోటా", unit=UnitType.kg))
        await db.commit()
        
        db.add(PriceTable(
            produce_id=produce_id, valid_date=today, region_pincode_prefix="530", 
            base_price=50.00, platform_margin_pct=10.0
        ))
        await db.commit()
        
        db.add(Listing(
            listing_id=listing_id, farmer_id=farmer_id, produce_id=produce_id,
            quantity=100.0, status=ListingStatus.accepted, vision_grade=VisionGrade.A
        ))
        await db.commit()
        
        try:
            print("\n--- Testing 9.2 Cart ---")
            print("Adding to cart...")
            cart = await cart_service.add_to_cart(customer_id, listing_id, 10.0, db, redis)
            print(f"Cart after add: {cart}")
            
            print("Fetching cart...")
            fetched = await cart_service.fetch_cart(customer_id, redis)
            print(f"Fetched Cart: {fetched}")
            
            print("\n--- Testing 9.3 Orders ---")
            print("Checking out cart...")
            checkout_res = await order_service.checkout_cart(customer_id, db, redis)
            print(f"Checkout Response: {checkout_res}")
            
            print("Verifying Listing status in DB...")
            listing = await db.get(Listing, listing_id)
            print(f"Listing status is now: {listing.status.value}")
            
            print("Verifying Redis is cleared...")
            empty_cart = await cart_service.fetch_cart(customer_id, redis)
            print(f"Cart after checkout: {empty_cart}")
            
            print("\n--- Testing 9.4 Smart Shopper Chat ---")
            msg = "Can you deliver tomatoes in 2 hours?"
            print(f"Sending message: {msg}")
            
            # Monkeypatch LLM to avoid real API limits and guarantee a bad time promise
            from app.services import llm_gateway
            async def fake_llm(*args, **kwargs):
                return "Yes, we can deliver tomatoes in 2 hours!"
            llm_gateway.smart_shopper_chat = fake_llm
            
            reply = await chat_service.process_smart_shopper_chat(customer_id, msg, [], db, redis)
            print(f"Regex Filtered Reply: {reply}")
            
        finally:
            print("\n--- Cleanup ---")
            await db.execute(delete(Order).where(Order.customer_id == customer_id))
            await db.execute(delete(Listing).where(Listing.listing_id == listing_id))
            await db.execute(delete(PriceTable).where(PriceTable.produce_id == produce_id))
            await db.execute(delete(ProduceCatalog).where(ProduceCatalog.produce_id == produce_id))
            await db.execute(delete(User).where(User.user_id.in_([customer_id, farmer_id])))
            await db.commit()

if __name__ == "__main__":
    asyncio.run(test_phase9())
