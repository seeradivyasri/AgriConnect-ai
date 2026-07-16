from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.database import get_db, get_redis
from app.utils.dependencies import require_customer
from app.services import cart_service
from app.models.user import User
from app.schemas.cart import CartItemAdd

router = APIRouter(prefix="/cart", tags=["cart"])

@router.get("")
async def get_cart(current_user: User = Depends(require_customer), redis: Redis = Depends(get_redis)):
    return await cart_service.fetch_cart(customer_id=current_user.user_id, redis=redis)

@router.post("/items")
async def add_item_to_cart(
    payload: CartItemAdd, 
    current_user: User = Depends(require_customer), 
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    return await cart_service.add_to_cart(
        customer_id=current_user.user_id, 
        listing_id=payload.listing_id, 
        quantity=payload.quantity, 
        db=db, 
        redis=redis
    )

@router.delete("/items/{listing_id}")
async def remove_cart_item(
    listing_id: UUID, 
    current_user: User = Depends(require_customer), 
    redis: Redis = Depends(get_redis)
):
    return await cart_service.remove_from_cart(
        customer_id=current_user.user_id, 
        listing_id=listing_id, 
        redis=redis
    )

@router.delete("")
async def clear_customer_cart(current_user: User = Depends(require_customer), redis: Redis = Depends(get_redis)):
    return await cart_service.clear_cart(customer_id=current_user.user_id, redis=redis)
