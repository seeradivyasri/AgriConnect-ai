import re
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.services import catalog_service, llm_gateway

async def process_smart_shopper_chat(
    customer_id: UUID, 
    message: str, 
    history: list, 
    db: AsyncSession, 
    redis: Redis
) -> str:
    
    # 1. Look up what vegetables we actually have for sale today
    catalog_items = await catalog_service.fetch_customer_catalog(
        pincode=None, produce_name=None, db=db, redis=redis
    )
    
    # 2. Build a context string from the top 5 items so the AI knows what to sell
    top_items = catalog_items[:5]
    context_string = "Current Produce Available:\n"
    for item in top_items:
        context_string += f"- {item['produce_name']} at ₹{item['customer_price']} per {item['unit']}\n"

    # 3. Convert Pydantic history objects into standard dictionaries for the AI
    history_dicts = [{"role": h.role, "content": h.content} for h in history]

    # 4. Ask the Groq AI for a response
    reply = await llm_gateway.smart_shopper_chat(
        message=message, 
        history=history_dicts, 
        catalog_context=context_string
    )

    # 5. STRICT SAFETY FILTER (The Regex)
    # This prevents the AI from accidentally promising delivery times
    pattern = r"\d+\s*(hour|minute|day)s?|tonight|tomorrow|by\s*\d"
    filtered_reply = re.sub(
        pattern, 
        "Please contact our team for delivery details.", 
        reply, 
        flags=re.IGNORECASE
    )

    return filtered_reply
