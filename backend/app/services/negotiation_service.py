from uuid import UUID
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.produce import Listing, ListingStatus
from app.models.user import User
from app.models.transaction import NegotiationSession, FarmerResponse
from app.schemas.negotiation import NegotiationResponse
from app.services import negotiation_engine, llm_gateway
import redis.asyncio as aioredis
from app.config import settings

redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

async def handle_negotiate_offer(
    listing_id: UUID, farmer_ask: Decimal, user: User, db: AsyncSession
) -> dict:
    
    # 1. SECURITY: Fetch the listing and ensure this farmer actually owns it
    from app.models.produce import ProduceCatalog
    stmt = select(Listing, ProduceCatalog.name_te).outerjoin(ProduceCatalog, Listing.produce_id == ProduceCatalog.produce_id).where(Listing.listing_id == listing_id)
    result = await db.execute(stmt)
    row = result.first()
    
    if not row:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    listing = row.Listing
    produce_name_te = row.name_te
    if listing.farmer_id != user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to negotiate this listing")
        
    # 2. VALIDATION: Ensure the crop is still open for negotiation
    if listing.status not in [ListingStatus.pending, ListingStatus.negotiating]:
        raise HTTPException(status_code=409, detail=f"Cannot negotiate a listing that is {listing.status.value}")
        
    # 3. MATH ENGINE: Pass the numbers to pure Python to calculate the AI's counter-offer
    try:
        decision = await negotiation_engine.process_negotiation_round(
            listing_id=listing_id,
            farmer_ask=farmer_ask,
            db=db,
            redis=redis_client
        )
    except ValueError as e:
        if str(e) == "MISSING_PRICE":
            listing.status = ListingStatus.rejected
            await db.commit()
            return NegotiationResponse(
                ai_message="I apologize, but the Admin panel has not yet set a base market price for this vegetable. I am not authorized to negotiate without an official price. Please try again later.",
                action="REJECT",
                status="rejected",
                round_number=1,
                ceiling_shown=False
            )
        raise e
        
    # Update the listing status if the engine made a final decision
    if decision["action"] == "ACCEPT":
        listing.status = ListingStatus.accepted
        await db.commit()
    elif decision["action"] == "REJECT":
        if decision.get("round_number", 1) >= 3 or "ceiling_shown" in decision:
            listing.status = ListingStatus.rejected
        else:
            # Round 2 Push-to-Round-3 (Soft Reject)
            listing.status = ListingStatus.negotiating
        await db.commit()
    else:
        listing.status = ListingStatus.negotiating
        await db.commit()
    
    # 4. LLM GATEWAY: Ask Groq to turn the math numbers into a polite Telugu message
    decision["produce_name"] = produce_name_te
    ai_message = await llm_gateway.generate_negotiation_response(decision, language="te")
    
    # 5. Output the combined result
    return {
        "engine_decision": decision["action"],
        "counter_price": decision.get("counter_price"),
        "final_price": decision.get("final_price"),
        "ceiling_shown": decision.get("ceiling_shown"),
        "ai_message": ai_message,
        "round_number": decision["round_number"]
    }

async def handle_farmer_response(
    listing_id: UUID, farmer_response: str, user: User, db: AsyncSession
) -> dict:
    
    # 1. SECURITY CHECK
    result = await db.execute(select(Listing).where(Listing.listing_id == listing_id))
    listing = result.scalars().first()
    
    if not listing or listing.farmer_id != user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    # 2. Fetch the latest negotiation session
    stmt = select(NegotiationSession).where(
        NegotiationSession.listing_id == listing_id
    ).order_by(NegotiationSession.round_number.desc())
    session_result = await db.execute(stmt)
    latest_session = session_result.scalars().first()
    
    if not latest_session:
        raise HTTPException(status_code=404, detail="No active negotiation found")

    # 3. Update the database based on if the farmer clicked "Accept" or "Reject"
    if farmer_response == "ACCEPT":
        latest_session.farmer_response = FarmerResponse.ACCEPT
        latest_session.final_price = latest_session.counter_price
        listing.status = ListingStatus.accepted
    elif farmer_response == "REJECT":
        latest_session.farmer_response = FarmerResponse.REJECT
        listing.status = ListingStatus.rejected
    else:
        raise HTTPException(status_code=400, detail="Response must be ACCEPT or REJECT")
        
    await db.commit()
    
    return {
        "status": listing.status.value,
        "final_price": latest_session.final_price
    }
