from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.database import get_db, get_redis
from app.utils.dependencies import require_customer
from app.services import chat_service
from app.models.user import User
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])

@router.post("/smart-shopper", response_model=ChatResponse)
async def smart_shopper(
    payload: ChatRequest,
    current_user: User = Depends(require_customer),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    reply = await chat_service.process_smart_shopper_chat(
        customer_id=current_user.user_id,
        message=payload.message,
        history=payload.history,
        db=db,
        redis=redis
    )
    return ChatResponse(reply=reply)
