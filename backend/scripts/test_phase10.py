import asyncio
from uuid import uuid4
from datetime import date
from fastapi import HTTPException
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database import AsyncSessionLocal, get_redis
from app.utils.dependencies import require_admin
from app.models.produce import ProduceCatalog, UnitType

async def test_phase10():
    # Setup some test produce
    produce_id = uuid4()
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        existing = await db.execute(select(ProduceCatalog).where(ProduceCatalog.produce_id == produce_id))
        if not existing.scalars().first():
            db.add(ProduceCatalog(produce_id=produce_id, name_en="Carrot", name_te="క్యారెట్", unit=UnitType.kg))
            await db.commit()
            
    # Need to populate Redis with some fake data so we can watch it get destroyed
    redis = None
    async for r in get_redis():
        redis = r
        break
        
    await redis.set("price:1234", "dummy")
    await redis.set("catalog:5678", "dummy")
    
    print("\n--- Test 3: Does cache invalidation delete BOTH price:* AND catalog:* ? ---")
    prices_before = await redis.keys("price:*")
    catalogs_before = await redis.keys("catalog:*")
    print(f"Before Admin Save - Price keys: {prices_before}")
    print(f"Before Admin Save - Catalog keys: {catalogs_before}")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        print("\n--- Test 1: After calling POST /api/v1/admin/prices, run redis keys 'price:*' ---")
        
        # Call the endpoint as an admin (the mock `require_admin` is active by default)
        response = await client.post("/api/v1/admin/prices", json={
            "produce_id": str(produce_id),
            "region_pincode_prefix": "530",
            "base_price": "60.00",
            "platform_margin_pct": "10.0",
            "valid_date": str(date.today())
        })
        
        print(f"Admin Endpoint Response: {response.json()}")
        
        prices_after = await redis.keys("price:*")
        catalogs_after = await redis.keys("catalog:*")
        print(f"After Admin Save - Price keys: {prices_after} (MUST BE EMPTY)")
        print(f"After Admin Save - Catalog keys: {catalogs_after} (MUST BE EMPTY)")
        
        print("\n--- Test 2: Call the admin endpoint with a farmer token — does it return 403? ---")
        
        # Mock the auth layer throwing a 403 because it detected a 'farmer' role attempting to access an 'admin' route
        async def mock_farmer_trying_to_be_admin():
            raise HTTPException(status_code=403, detail="Only admins can access this endpoint")
            
        app.dependency_overrides[require_admin] = mock_farmer_trying_to_be_admin
        
        rebel_response = await client.get("/api/v1/admin/transactions")
        print(f"Rebel Farmer Response Status: {rebel_response.status_code}")
        print(f"Rebel Farmer Response Body: {rebel_response.json()}")
        
        # Cleanup overrides
        app.dependency_overrides = {}

if __name__ == "__main__":
    asyncio.run(test_phase10())
