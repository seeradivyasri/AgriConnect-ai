from uuid import UUID
from typing import List
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.produce import Listing, ListingStatus
from app.models.user import User

async def create_listing(farmer_id: UUID, produce_id: UUID, quantity: float, db: AsyncSession) -> Listing:
    listing = Listing(
        farmer_id=farmer_id,
        produce_id=produce_id,
        quantity=quantity,
        status=ListingStatus.pending
    )
    db.add(listing)
    await db.commit()
    await db.refresh(listing)
    return listing

async def get_farmer_listings(farmer_id: UUID, db: AsyncSession) -> List[dict]:
    from app.models.produce import ProduceCatalog
    from app.models.transaction import NegotiationSession
    from sqlalchemy import func
    
    # We need a subquery for the latest negotiation session per listing
    latest_session_sq = select(
        NegotiationSession.listing_id,
        func.max(NegotiationSession.round_number).label("max_round")
    ).group_by(NegotiationSession.listing_id).subquery()
    
    latest_session_details = select(
        NegotiationSession.listing_id,
        NegotiationSession.final_price
    ).join(
        latest_session_sq,
        (NegotiationSession.listing_id == latest_session_sq.c.listing_id) &
        (NegotiationSession.round_number == latest_session_sq.c.max_round)
    ).subquery()
    
    stmt = select(
        Listing,
        ProduceCatalog.name_en,
        latest_session_details.c.final_price
    ).outerjoin(
        ProduceCatalog, Listing.produce_id == ProduceCatalog.produce_id
    ).outerjoin(
        latest_session_details, Listing.listing_id == latest_session_details.c.listing_id
    ).where(
        Listing.farmer_id == farmer_id
    ).order_by(Listing.created_at.desc())
    
    result = await db.execute(stmt)
    rows = result.all()
    
    listings = []
    for row in rows:
        listing_obj = row.Listing
        # convert to dict to easily add properties
        listing_dict = {
            "listing_id": listing_obj.listing_id,
            "farmer_id": listing_obj.farmer_id,
            "produce_id": listing_obj.produce_id,
            "quantity": listing_obj.quantity,
            "photo_url": listing_obj.photo_url,
            "vision_grade": listing_obj.vision_grade,
            "status": listing_obj.status,
            "created_at": listing_obj.created_at,
            "produce_name": row.name_en,
            "final_price": row.final_price
        }
        listings.append(listing_dict)
        
    return listings

async def get_listing_by_id_for_user(listing_id: UUID, user: User, db: AsyncSession) -> Listing:
    stmt = select(Listing).where(Listing.listing_id == listing_id)
    result = await db.execute(stmt)
    listing = result.scalars().first()
    
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
        
    if user.role != "admin" and listing.farmer_id != user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to view this listing")
        
    return listing
