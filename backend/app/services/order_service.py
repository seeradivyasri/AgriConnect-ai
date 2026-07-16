import json
from uuid import UUID
from datetime import date
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from redis.asyncio import Redis

from app.models.produce import Listing, ListingStatus, PriceTable, VisionGrade
from app.models.transaction import Order, OrderStatus

async def checkout_cart(customer_id: UUID, db: AsyncSession, redis: Redis) -> dict:
    # 1. Fetch the cart from Redis
    cart_key = f"cart:{customer_id}"
    cart_data = await redis.get(cart_key)
    if not cart_data:
        raise HTTPException(status_code=400, detail="Cart is empty")
        
    cart_items = json.loads(cart_data)
    if len(cart_items) == 0:
        raise HTTPException(status_code=400, detail="Cart is empty")

    orders = []
    total_amount = Decimal("0.00")
    today = date.today()

    # 2. Process each item in the cart
    for item in cart_items:
        listing_id = UUID(item["listing_id"])
        quantity = Decimal(str(item["quantity"]))

        # Check if the listing is still available
        listing = await db.get(Listing, listing_id)
        if not listing or listing.status != ListingStatus.accepted:
            raise HTTPException(status_code=400, detail=f"Item {listing_id} is no longer available")
        if quantity > listing.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for {listing_id}")

        # Fetch today's price and add the 5% margin
        stmt = select(PriceTable).where(
            PriceTable.produce_id == listing.produce_id,
            PriceTable.valid_date == today
        )
        price_result = await db.execute(stmt)
        price_table = price_result.scalars().first()
        
        if not price_table:
            raise HTTPException(status_code=400, detail="Price not available for this produce today")

        markup = Decimal("1.05")
        if listing.vision_grade == VisionGrade.B:
            markup = Decimal("0.945")

        customer_price = round(price_table.base_price * markup, 2)

        # Create the Order Record
        new_order = Order(
            customer_id=customer_id,
            listing_id=listing_id,
            quantity=quantity,
            unit_price=customer_price,
            status=OrderStatus.confirmed
        )
        db.add(new_order)
        orders.append(new_order)
        
        # Add to the receipt total
        total_amount += (customer_price * quantity)

        # Mark the farmer's listing as SOLD
        listing.status = ListingStatus.sold

    # 3. Save everything to the database AT THE SAME TIME
    await db.commit()
    
    # 4. Empty the customer's cart
    await redis.delete(cart_key)

    return {
        "total_amount": float(total_amount),
        "orders": [
            {
                "order_id": str(o.order_id),
                "listing_id": str(o.listing_id),
                "quantity": float(o.quantity),
                "unit_price": float(o.unit_price)
            } for o in orders
        ]
    }

async def fetch_customer_orders(customer_id: UUID, db: AsyncSession):
    stmt = select(Order).where(Order.customer_id == customer_id)
    result = await db.execute(stmt)
    return result.scalars().all()
