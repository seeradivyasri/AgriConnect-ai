from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.database import get_db
from app.utils.dependencies import require_farmer
from app.models.user import User
from app.schemas.negotiation import NegotiateRequest, NegotiationResponse, RespondRequest
from app.services import negotiation_service

router = APIRouter(prefix="/listings", tags=["Negotiation"])

@router.post("/{listing_id}/negotiate", response_model=NegotiationResponse)
async def negotiate_price(
    listing_id: UUID,
    payload: NegotiateRequest,
    current_farmer: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    response = await negotiation_service.handle_negotiate_offer(
        listing_id=listing_id,
        farmer_ask=payload.farmer_ask,
        user=current_farmer,
        db=db
    )
    
    # Broadcast to websocket
    from app.utils.websocket import manager
    from fastapi.encoders import jsonable_encoder
    
    # Ensure it's serialized properly (Decimal -> float, UUID -> str)
    if hasattr(response, 'model_dump'):
        data = jsonable_encoder(response.model_dump())
    else:
        data = jsonable_encoder(response)
        
    await manager.send_update(str(listing_id), data)
    
    return response

@router.post("/{listing_id}/respond")
async def respond_to_offer(
    listing_id: UUID,
    payload: RespondRequest, 
    current_farmer: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    return await negotiation_service.handle_farmer_response(
        listing_id=listing_id,
        farmer_response=payload.farmer_response,
        user=current_farmer,
        db=db
    )
