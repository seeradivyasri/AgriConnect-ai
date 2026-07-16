from decimal import Decimal
import decimal
import uuid
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from redis.asyncio import Redis

from app.models.produce import Listing, ListingStatus
from app.models.user import User
from app.models.transaction import NegotiationSession, EngineDecision
from app.services.price_service import get_today_price

# Define rounding context for precise currency calculations
ctx = decimal.getcontext()
ctx.rounding = decimal.ROUND_HALF_UP

QUALITY_FACTORS = {
    "A": Decimal("1.00"),
    "B": Decimal("0.90"),
    "C": Decimal("0.75"),
    "REJECTED": Decimal("0.00")
}

def round_to_half_step(value: Decimal) -> Decimal:
    """
    Rounds a decimal down to the nearest 0.5 step.
    If decimal part is < 0.5 -> .0
    If decimal part is >= 0.5 -> .5
    """
    return (value * Decimal("2")).quantize(Decimal("1"), rounding=decimal.ROUND_DOWN) / Decimal("2")

def compute_effective_ceiling(base_price: Decimal, margin_pct: Decimal, grade: str) -> Decimal:
    """
    Computes the Effective Price (EP) ceiling based on base_price, platform margin, and crop grade.
    Formula: round(base_price * (1 - margin_pct/100) * QUALITY_FACTORS[grade])
    """
    q_factor = QUALITY_FACTORS.get(grade, Decimal("0.00"))
    margin = margin_pct / Decimal("100")
    
    # Calculate EP
    ep = base_price * (Decimal("1.00") - margin) * q_factor
    
    # Round to nearest 0.5 step
    return round_to_half_step(ep)

def evaluate_ask(farmer_ask: Decimal, base_price: Decimal, ep: Decimal, round_num: int) -> dict:
    """
    Evaluates a farmer's price ask based on the strict rules:
    - Ethical floor protection
    - Overbids push to round 3
    - Mapped safely back to the database enum (ACCEPT/COUNTER/REJECT)
    """
    decision = {
        "action": None,
        "counter_price": None,
        "final_price": None,
        "ceiling_shown": None
    }
    
    # Rule 1: Anti-Exploitation Floor Check
    # If farmer asks for less than 60% of the ceiling, enforce 92% ethical floor
    if farmer_ask < (ep * Decimal("0.60")):
        ethical_floor = ep * Decimal("0.92")
        decision["action"] = "COUNTER"
        decision["counter_price"] = round_to_half_step(ethical_floor)
        return decision
        
    # Rule 2: Overbidding Paths
    if farmer_ask > ep:
        if round_num == 1:
            counter = ep * Decimal("0.95")
            decision["action"] = "COUNTER"
            decision["counter_price"] = round_to_half_step(counter)
            return decision
        elif round_num == 2:
            decision["action"] = "COUNTER"
            decision["counter_price"] = round_to_half_step(ep * Decimal("0.96"))
            return decision
        else:
            # Round 3 Final Counter Offer
            decision["action"] = "COUNTER"
            decision["counter_price"] = round_to_half_step(ep)
            return decision
            
    # Rule 3: Valid Bid / Reverse-Bid Optimization (Round 2)
    if farmer_ask <= ep and round_num == 2:
        reverse_bid = farmer_ask * Decimal("0.97")
        decision["action"] = "COUNTER"
        decision["counter_price"] = round_to_half_step(reverse_bid)
        return decision
        
    # Default: Accept valid bids in Round 1 or Round 3
    decision["action"] = "ACCEPT"
    decision["final_price"] = round_to_half_step(farmer_ask)
    return decision

async def process_negotiation_round(listing_id: uuid.UUID, farmer_ask: Decimal, db: AsyncSession, redis: Redis) -> Dict[str, Any]:
    """
    Database wrapper that processes a single round of negotiation.
    Fetches the listing, today's price, existing sessions, and delegates to the math engine.
    """
    # 1. Fetch listing and farmer pincode
    stmt = (
        select(Listing, User.location_pincode)
        .join(User, Listing.farmer_id == User.user_id)
        .where(Listing.listing_id == listing_id)
    )
    result = await db.execute(stmt)
    row = result.first()
    
    if not row:
        raise ValueError("Listing not found")
        
    listing, pincode = row
    
    if listing.status not in (ListingStatus.pending, ListingStatus.negotiating):
        raise ValueError(f"Cannot negotiate on listing with status: {listing.status}")
        
    # 2. Get today's market price
    pincode_prefix = pincode[:3] if pincode else "000"
    price_record = await get_today_price(listing.produce_id, pincode_prefix, db, redis)
    
    if not price_record and pincode_prefix != "000":
        # Try national fallback
        price_record = await get_today_price(listing.produce_id, "000", db, redis)
        
    if not price_record:
        raise ValueError("MISSING_PRICE")
        
    base_price = price_record.base_price
    
    # 3. Determine round number
    count_stmt = select(func.count()).select_from(NegotiationSession).where(NegotiationSession.listing_id == listing_id)
    count_res = await db.execute(count_stmt)
    existing_sessions = count_res.scalar() or 0
    round_num = existing_sessions + 1
    
    # 4. Math Engine
    # Assume a standard 12% platform margin for now
    margin_pct = Decimal("12.00")
    grade = getattr(listing.vision_grade, "name", listing.vision_grade) if listing.vision_grade else "A"
    ep = compute_effective_ceiling(base_price, margin_pct, grade)
    
    decision = evaluate_ask(farmer_ask, base_price, ep, round_num)
    
    # 5. Save to DB
    engine_decision_enum = getattr(EngineDecision, decision["action"])
    
    new_session = NegotiationSession(
        listing_id=listing_id,
        round_number=round_num,
        farmer_ask=farmer_ask,
        engine_decision=engine_decision_enum,
        counter_price=decision.get("counter_price"),
        final_price=decision.get("final_price")
    )
    db.add(new_session)
    
    # Update listing status
    if decision["action"] == "ACCEPT":
        listing.status = ListingStatus.accepted
    elif decision["action"] == "REJECT":
        listing.status = ListingStatus.rejected
    else:
        listing.status = ListingStatus.negotiating
        
    await db.commit()
    
    decision["round_number"] = round_num
    return decision
