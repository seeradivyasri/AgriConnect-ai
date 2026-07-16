import pytest
import os
import uuid
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock
from app.main import app
from app.utils.dependencies import require_farmer
from app.models.user import User

# This UUID corresponds to Onion in the seed script
import pytest_asyncio

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

async def get_test_farmer():
    from app.database import AsyncSessionLocal
    from sqlalchemy import select
    # Create or get a test user to satisfy foreign key constraints
    test_user_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.user_id == test_user_id))
        user = result.scalars().first()
        if not user:
            user = User(
                user_id=test_user_id,
                phone="+910000000001",
                name="Integration Test Farmer",
                role="farmer",
                verified=True
            )
            session.add(user)
            await session.commit()
    return user

async def mock_farmer_dependency() -> User:
    return await get_test_farmer()

# Override the farmer dependency with our database-backed test farmer
app.dependency_overrides[require_farmer] = mock_farmer_dependency

@pytest.mark.asyncio
@pytest.mark.integration
@patch("app.services.vision_service.grade_produce_photo", new_callable=AsyncMock)
@patch("app.services.llm_gateway.generate_negotiation_response", new_callable=AsyncMock)
async def test_happy_path_underbid(mock_generate, mock_grade):
    """
    Test flow: create listing -> upload photo -> submit low ask -> listing gets accepted
    """
    mock_grade.return_value = {"grade": "A", "reason": "Looks good"}
    mock_generate.return_value = "I am happy to accept this offer!"

    async with get_client() as async_client:
        # 1. Create listing
        response = await async_client.post("/api/v1/listings", json={
            "produce_id": ONION_PRODUCE_ID,
            "quantity": 50
        })
        assert response.status_code == 200
        data = response.json()
        listing_id = data["listing_id"]
        assert data["status"] == "pending"

        # 2. Upload photo
        filepath = os.path.join(os.path.dirname(__file__), "fixtures", "sample_onion.jpg")
        with open(filepath, "rb") as f:
            file_data = f.read()
        
        response = await async_client.post(
            f"/api/v1/listings/{listing_id}/photo",
            files={"photo": ("sample_onion.jpg", file_data, "image/jpeg")}
        )
        assert response.status_code == 200
        assert response.json()["vision_grade"] == "A"

        # 3. Submit ask (underbid) - assuming base price is 48, so 5 is very low.
        response = await async_client.post(
            f"/api/v1/listings/{listing_id}/negotiate",
            json={"farmer_ask": 5.0}
        )
        assert response.status_code == 200
        neg_data = response.json()
        assert neg_data["engine_decision"] == "ACCEPT"
        assert neg_data["final_price"] == 5.0


@pytest.mark.asyncio
@pytest.mark.integration
@patch("app.services.llm_gateway.generate_negotiation_response", new_callable=AsyncMock)
async def test_counter_flow_sweet_spot(mock_generate):
    """
    Test flow: create listing -> submit medium ask -> get counter -> respond ACCEPT -> listing accepted
    """
    mock_generate.return_value = "I can offer you a counter price."

    async with get_client() as async_client:
        # 1. Create listing
        response = await async_client.post("/api/v1/listings", json={
            "produce_id": ONION_PRODUCE_ID,
            "quantity": 50
        })
        assert response.status_code == 200
        listing_id = response.json()["listing_id"]

        # 2. Submit ask (sweet spot) - Base price is 48, so 47 is slightly high, will trigger counter
        response = await async_client.post(
            f"/api/v1/listings/{listing_id}/negotiate",
            json={"farmer_ask": 47.0}
        )
        assert response.status_code == 200
        neg_data = response.json()
        assert neg_data["engine_decision"] == "COUNTER"
        assert "counter_price" in neg_data

        # 3. Accept counter
        response = await async_client.post(
            f"/api/v1/listings/{listing_id}/respond",
            json={"farmer_response": "ACCEPT"}
        )
        assert response.status_code == 200
        resp_data = response.json()
        assert resp_data["status"] == "accepted"
        assert resp_data["final_price"] == neg_data["counter_price"]


@pytest.mark.asyncio
@pytest.mark.integration
@patch("app.services.llm_gateway.generate_negotiation_response", new_callable=AsyncMock)
async def test_overbid_reject(mock_generate):
    """
    Test flow: create listing -> submit huge ask -> rejected
    """
    mock_generate.return_value = "That is far too expensive, I must decline."

    async with get_client() as async_client:
        # 1. Create listing
        response = await async_client.post("/api/v1/listings", json={
            "produce_id": ONION_PRODUCE_ID,
            "quantity": 50
        })
        assert response.status_code == 200
        listing_id = response.json()["listing_id"]

        # 2. Submit huge overbid
        response = await async_client.post(
            f"/api/v1/listings/{listing_id}/negotiate",
            json={"farmer_ask": 999.0}
        )
        assert response.status_code == 200
        neg_data = response.json()
        assert neg_data["engine_decision"] == "REJECT"
        
        # 3. Verify listing status is now rejected
        response = await async_client.get(f"/api/v1/listings/{listing_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "rejected"


async def mock_customer_dependency():
    from fastapi import HTTPException
    raise HTTPException(status_code=403, detail="Only farmers can access this endpoint")

@pytest.mark.asyncio
@pytest.mark.integration
async def test_unauthorised_customer():
    """
    Test flow: Customer tries to access farmer endpoint -> 403
    """
    # Overriding the dependency to simulate the Auth layer blocking a customer token
    app.dependency_overrides[require_farmer] = mock_customer_dependency
    
    try:
        async with get_client() as async_client:
            response = await async_client.post("/api/v1/listings", json={
                "produce_id": ONION_PRODUCE_ID,
                "quantity": 50
            })
            assert response.status_code == 403
    finally:
        # Clean up override
        app.dependency_overrides = {}
