from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from redis.asyncio import Redis

from app.models.produce import PriceTable, Listing
from app.models.transaction import Order

async def upsert_price(
    produce_id, region_pincode_prefix, base_price, platform_margin_pct, valid_date, db: AsyncSession, redis: Redis
) -> dict:
    
    # 1. Database Check: Does a price already exist for this region?
    stmt = select(PriceTable).where(
        PriceTable.produce_id == produce_id,
        PriceTable.region_pincode_prefix == region_pincode_prefix
    )
    result = await db.execute(stmt)
    price_row = result.scalars().first()

    if price_row:
        # Update existing price
        price_row.base_price = base_price
        price_row.platform_margin_pct = platform_margin_pct
        price_row.valid_date = valid_date
    else:
        # Create brand new price
        price_row = PriceTable(
            produce_id=produce_id, region_pincode_prefix=region_pincode_prefix,
            base_price=base_price, platform_margin_pct=platform_margin_pct, valid_date=valid_date
        )
        db.add(price_row)
        
    await db.commit()

    # 2. CACHE INVALIDATION (Nuclear Wipe)
    # Because prices changed, we must delete ALL cached customer catalogs so they don't see old prices
    price_keys = await redis.keys("price:*")
    catalog_keys = await redis.keys("catalog:*")
    
    keys_to_delete = price_keys + catalog_keys
    if keys_to_delete:
        await redis.delete(*keys_to_delete)
        
    return {"message": "Price saved and cache invalidated"}

async def fetch_prices(db: AsyncSession):
    from app.models.produce import ProduceCatalog
    stmt = select(ProduceCatalog, PriceTable).join(
        PriceTable, ProduceCatalog.produce_id == PriceTable.produce_id
    ).order_by(PriceTable.valid_date.desc())
    result = await db.execute(stmt)
    
    seen = set()
    output = []
    for p, pr in result.all():
        if p.produce_id not in seen:
            seen.add(p.produce_id)
            output.append({
                "produce_id": p.produce_id,
                "name_en": p.name_en,
                "name_te": p.name_te,
                "region_pincode_prefix": pr.region_pincode_prefix,
                "base_price": float(pr.base_price),
                "platform_margin_pct": float(pr.platform_margin_pct),
                "valid_date": pr.valid_date
            })
    return output

async def fetch_transactions(date_from: date | None, date_to: date | None, db: AsyncSession):
    # 1. Fetch Orders and "Join" the Customer, Listing, Farmer, and Produce tables
    stmt = select(Order).options(
        selectinload(Order.customer),
        selectinload(Order.listing).selectinload(Listing.farmer),
        selectinload(Order.listing).selectinload(Listing.produce)
    )
    
    # 2. Apply optional Date Filters
    if date_from:
        stmt = stmt.where(Order.created_at >= date_from)
    if date_to:
        stmt = stmt.where(Order.created_at <= date_to)
        
    result = await db.execute(stmt)
    orders = result.scalars().all()
    
    # 3. Format into a clean list for the Admin Dashboard frontend
    return [{
        "order_id": order.order_id,
        "status": order.status,
        "customer_name": order.customer.name,
        "farmer_name": order.listing.farmer.name,
        "produce_name": order.listing.produce.name_en,
        "quantity": float(order.quantity),
        "total_amount": float(order.quantity * order.unit_price),
        "created_at": order.created_at
    } for order in orders]

async def fetch_all_listings(db: AsyncSession):
    # 1. Fetch Listings and join the Negotiation history
    stmt = select(Listing).options(
        selectinload(Listing.farmer),
        selectinload(Listing.produce),
        selectinload(Listing.negotiation_sessions)
    )
    result = await db.execute(stmt)
    listings = result.scalars().all()
    
    return [{
        "listing_id": listing.listing_id,
        "farmer_name": listing.farmer.name,
        "produce_name": listing.produce.name_en,
        "status": listing.status,
        "negotiation_sessions_count": len(listing.negotiation_sessions)
    } for listing in listings]
