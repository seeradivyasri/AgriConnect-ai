import asyncio
import os
import uuid
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from app.database import AsyncSessionLocal
from app.models.transaction import NegotiationSession
from app.models.produce import Listing
from app.utils.dependencies import require_farmer
from app.models.user import User

ONION_PRODUCE_ID = "45be8807-7a54-47ed-b062-8147d1dfcff8"
TEST_FARMER_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")

async def override_get_user():
    return User(
        user_id=TEST_FARMER_ID,
        phone="+910000000001",
        name="Test Farmer",
        role="farmer",
        verified=True
    )

app.dependency_overrides[require_farmer] = override_get_user

async def run_ac_tests():
    # Setup test farmer and fetch produce in DB
    async with AsyncSessionLocal() as session:
        # Get produce ID
        from app.models.produce import ProduceCatalog
        produce_res = await session.execute(select(ProduceCatalog).where(ProduceCatalog.name_en == "Onions"))
        onion = produce_res.scalars().first()
        ONION_PRODUCE_ID = str(onion.produce_id) if onion else str(uuid.uuid4())

        result = await session.execute(select(User).where(User.user_id == TEST_FARMER_ID))
        if not result.scalars().first():
            session.add(User(
                user_id=TEST_FARMER_ID,
                phone="+910000000001",
                name="Test Farmer",
                role="farmer",
                verified=True
            ))
            await session.commit()

    print("--- STARTING MANUAL FLOW (AC-8.2) ---")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create Listing
        response = await client.post("/api/v1/listings", json={
            "produce_id": ONION_PRODUCE_ID,
            "quantity": 50
        })
        listing_id = response.json()["listing_id"]
        print(f"Created Listing: {listing_id}, Status: {response.json()['status']}")
        
        # 2. Negotiate (Sweet Spot -> Counter)
        print("\nSubmitting Farmer Ask of 47 (Base is 30, EP is ~28.5)")
        # Let's ask for 28.0 to get ACCEPT, or 28.5 to get COUNTER if it's R1?
        # If ask(29.0) <= EP(28.5)? No, 29 > 28.5, so it triggers COUNTER? Wait, evaluating 29 > 28.5 gives REJECT or COUNTER based on logic.
        response = await client.post(f"/api/v1/listings/{listing_id}/negotiate", json={"farmer_ask": 29.0})
        neg_data = response.json()
        print(f"Negotiation Round 1 Response (AC-8.4 AI Message): {neg_data.get('ai_message')}")
        print(f"Decision: {neg_data.get('engine_decision')}")
        
        # 3. Respond
        if neg_data.get("engine_decision") == "COUNTER":
            response = await client.post(f"/api/v1/listings/{listing_id}/respond", json={"farmer_response": "ACCEPT"})
            print(f"Respond to Counter: {response.json()}")

        # 4. Get final listing
        response = await client.get(f"/api/v1/listings/{listing_id}")
        print(f"Final Listing Status: {response.json()['status']}")

    print("\n--- CHECKING DB (AC-8.3) ---")
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(NegotiationSession).where(NegotiationSession.listing_id == uuid.UUID(listing_id))
        )
        sessions = result.scalars().all()
        for s in sessions:
            print(f"Round {s.round_number}: Ask={s.farmer_ask}, Decision={s.engine_decision}, Counter={s.counter_price}, FarmerResponse={s.farmer_response}")

if __name__ == "__main__":
    asyncio.run(run_ac_tests())
