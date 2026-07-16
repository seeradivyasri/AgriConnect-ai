import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.produce import ProduceCatalog, PriceTable

async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(ProduceCatalog, PriceTable).join(PriceTable, ProduceCatalog.produce_id == PriceTable.produce_id))
        print("\n--- VEGETABLE DATABASE ---")
        for p, pr in res.all():
            print(f"Name: {p.name_en} | Area: {pr.region_pincode_prefix} | Base Price: Rs {pr.base_price}")
            print(f"UUID: {p.produce_id}")
            print("-" * 50)
            
if __name__ == "__main__":
    asyncio.run(main())
