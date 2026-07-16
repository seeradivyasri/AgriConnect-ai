import json
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from redis.asyncio import Redis

from app.models.produce import Listing, ListingStatus

async def fetch_cart(customer_id: UUID, redis: Redis) -> list:
    cart_key = f"cart:{customer_id}"
    data = await redis.get(cart_key)
    return json.loads(data) if data else []

async def add_to_cart(customer_id: UUID, listing_id: UUID, quantity: float, db: AsyncSession, redis: Redis):
    # 1. Check Database to ensure listing is valid and has enough stock
    result = await db.execute(select(Listing).where(Listing.listing_id == listing_id))
    listing = result.scalar_one_or_none()
    
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.status != ListingStatus.accepted:
        raise HTTPException(status_code=400, detail="This listing is not currently available for sale")
    if quantity > float(listing.quantity):
        raise HTTPException(status_code=400, detail=f"Only {listing.quantity} available in stock")

    # 2. Update Redis Cart
    cart_key = f"cart:{customer_id}"
    cart = await fetch_cart(customer_id, redis)
    
    # If item already exists in cart, add to its quantity, else append new item
    found = False
    for item in cart:
        if item["listing_id"] == str(listing_id):
            item["quantity"] += quantity
            found = True
            break
            
    if not found:
        cart.append({
            "listing_id": str(listing_id),
            "quantity": quantity
        })
        
    await redis.set(cart_key, json.dumps(cart))
    return cart

async def remove_from_cart(customer_id: UUID, listing_id: UUID, redis: Redis):
    cart_key = f"cart:{customer_id}"
    cart = await fetch_cart(customer_id, redis)
    
    # Filter out the listing we want to delete
    new_cart = [item for item in cart if item["listing_id"] != str(listing_id)]
    
    await redis.set(cart_key, json.dumps(new_cart))
    return new_cart

async def clear_cart(customer_id: UUID, redis: Redis):
    cart_key = f"cart:{customer_id}"
    await redis.delete(cart_key)
    return {"message": "Cart cleared successfully"}
