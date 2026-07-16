from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.database import get_db, get_redis
from app.utils.dependencies import require_customer
from app.services import order_service
from app.models.user import User
from app.schemas.order import CheckoutResponse

router = APIRouter(prefix="/orders", tags=["orders"])

@router.post("", response_model=CheckoutResponse)
async def place_order(
    current_user: User = Depends(require_customer), 
    db: AsyncSession = Depends(get_db), 
    redis: Redis = Depends(get_redis)
):
    return await order_service.checkout_cart(
        customer_id=current_user.user_id, 
        db=db, 
        redis=redis
    )

@router.get("/my")
async def get_my_orders(
    current_user: User = Depends(require_customer), 
    db: AsyncSession = Depends(get_db)
):
    return await order_service.fetch_customer_orders(
        customer_id=current_user.user_id, 
        db=db
    )
