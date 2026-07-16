import pytest
import os
import uuid
import json
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock
from app.main import app
from app.utils.dependencies import require_customer, get_current_user
from app.models.user import User

ONION_PRODUCE_ID = "45be8807-7a54-47ed-b062-8147d1dfcff8"

def get_client():
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy.pool import NullPool
    from app.config import settings
    from app.database import get_db

    # Create a new engine with NullPool to avoid InterfaceError in tests
    test_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    TestingSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with TestingSessionLocal() as session:
            yield session
            
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")

async def get_test_customer():
    from app.database import AsyncSessionLocal
    from sqlalchemy import select
    test_user_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.user_id == test_user_id))
        user = result.scalars().first()
        if not user:
            user = User(
                user_id=test_user_id,
                phone="+910000000002",
                name="Integration Test Customer",
                role="customer",
                verified=True
            )
            session.add(user)
            await session.commit()
    return user

async def mock_customer_dependency() -> User:
    return await get_test_customer()

# Ensure get_current_user resolves to customer during these tests where needed
# But realistically, the endpoints explicitly use require_customer.
app.dependency_overrides[require_customer] = mock_customer_dependency

async def seed_data():
    from app.database import AsyncSessionLocal
    from app.models.produce import Listing, ListingStatus, ProduceCatalog, PriceTable, VisionGrade, UnitType
    from app.models.user import User
    from datetime import date
    
    async with AsyncSessionLocal() as db:
        customer_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
        farmer_id = uuid.UUID("33333333-3333-3333-3333-333333333333")
        
        # Ensure users
        if not await db.get(User, farmer_id):
            db.add(User(user_id=farmer_id, phone="9998", name="F", role="farmer", verified=True))
            await db.commit()
            
        # Ensure catalog
        produce_id = uuid.UUID(ONION_PRODUCE_ID)
        if not await db.get(ProduceCatalog, produce_id):
            db.add(ProduceCatalog(produce_id=produce_id, name_en="Onion", name_te="ఉల్లిపాయ", unit=UnitType.kg))
            await db.commit()
            
        # Ensure price
        today = date.today()
        from sqlalchemy import select, delete
        stmt = select(PriceTable).where(PriceTable.produce_id == produce_id, PriceTable.valid_date == today)
        if not (await db.execute(stmt)).scalars().first():
            db.add(PriceTable(
                produce_id=produce_id, valid_date=today, region_pincode_prefix="530", 
                base_price=50.00, platform_margin_pct=10.0
            ))
            await db.commit()
            
        # Clean listings and orders for a fresh test
        from app.models.transaction import Order
        await db.execute(delete(Order).where(Order.customer_id == customer_id))
        await db.execute(delete(Listing).where(Listing.farmer_id == farmer_id))
        await db.commit()
        
        # Insert a valid listing
        listing_id = uuid.uuid4()
        db.add(Listing(
            listing_id=listing_id, farmer_id=farmer_id, produce_id=produce_id,
            quantity=100.0, status=ListingStatus.accepted, vision_grade=VisionGrade.A
        ))
        await db.commit()
        
        # Need to clear redis cache for catalog
        from app.database import get_redis
        redis = None
        async for r in get_redis():
            redis = r
            break
        if redis:
            await redis.delete(f"catalog:all:{today}")
            await redis.delete(f"cart:{customer_id}")

@pytest.mark.asyncio
@pytest.mark.integration
async def test_catalog_returns_accepted_graded():
    """
    Catalog should only return listings with status=accepted and vision_grade A or B.
    """
    await seed_data()
    async with get_client() as async_client:
        response = await async_client.get("/api/v1/catalog")
        assert response.status_code == 200
        data = response.json()
        items = data.get("items", data) if isinstance(data, dict) else data
        assert isinstance(items, list)
        assert len(items) > 0
        
        for item in items:
            assert item["vision_grade"] in ["A", "B"]

@pytest.mark.asyncio
@pytest.mark.integration
async def test_cart_and_order_flow():
    """
    Test flow: Add to cart -> get cart -> place order -> listing is sold
    """
    await seed_data()
    async with get_client() as async_client:
        cat_resp = await async_client.get("/api/v1/catalog")
        assert cat_resp.status_code == 200
        catalog = cat_resp.json()
        items = catalog.get("items", catalog) if isinstance(catalog, dict) else catalog
        
        if not items:
            pytest.fail("Catalog is empty despite seeding data")
        
        target_item = items[0]
        listing_id = target_item["listing_id"]
        
        await async_client.delete("/api/v1/cart")

        add_resp = await async_client.post("/api/v1/cart/items", json={
            "listing_id": listing_id,
            "quantity": 1.0
        })
        assert add_resp.status_code == 200

        get_cart_resp = await async_client.get("/api/v1/cart")
        assert get_cart_resp.status_code == 200
        cart_data = get_cart_resp.json()
        assert len(cart_data) == 1
        assert cart_data[0]["listing_id"] == listing_id

        order_resp = await async_client.post("/api/v1/orders")
        assert order_resp.status_code == 200
        order_data = order_resp.json()
        assert "total_amount" in order_data
        assert len(order_data["orders"]) == 1

        get_cart_again = await async_client.get("/api/v1/cart")
        assert len(get_cart_again.json()) == 0

        cat_resp_again = await async_client.get("/api/v1/catalog")
        new_catalog = cat_resp_again.json()
        new_items = new_catalog.get("items", new_catalog) if isinstance(new_catalog, dict) else new_catalog
        assert not any(i["listing_id"] == listing_id for i in new_items)

@pytest.mark.asyncio
@pytest.mark.integration
@patch("app.services.llm_gateway.smart_shopper_chat", new_callable=AsyncMock)
async def test_smart_shopper_regex_filter(mock_llm):
    """
    Test flow: Smart Shopper returns reply without specific delivery time
    """
    # Force the mock to return a string containing illegal time phrases
    mock_llm.return_value = "Yes, we have tomatoes! We can deliver tonight in 2 hours."

    async with get_client() as async_client:
        response = await async_client.post("/api/v1/chat/smart-shopper", json={
            "message": "When will it arrive?",
            "history": []
        })
        assert response.status_code == 200
        data = response.json()
        reply = data["reply"]
        
        # The regex should have destroyed "tonight" and "2 hours"
        assert "tonight" not in reply.lower()
        assert "2 hours" not in reply.lower()
        assert "Please contact our team for delivery details." in reply

async def mock_farmer_dependency():
    from fastapi import HTTPException
    raise HTTPException(status_code=403, detail="Only customers can access this endpoint")

@pytest.mark.asyncio
@pytest.mark.integration
async def test_unauthorised_farmer():
    """
    Test flow: Farmer token on /api/v1/cart -> 403
    """
    # Temporarily override the require_customer dependency to simulate a farmer token block
    app.dependency_overrides[require_customer] = mock_farmer_dependency
    
    try:
        async with get_client() as async_client:
            response = await async_client.get("/api/v1/cart")
            assert response.status_code == 403
    finally:
        # Clean up
        app.dependency_overrides = {}
