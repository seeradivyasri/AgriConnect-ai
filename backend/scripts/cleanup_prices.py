import asyncio
import sys
from pathlib import Path

# Add backend directory to sys.path so we can import app modules
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.produce import PriceTable

async def main():
    async with AsyncSessionLocal() as session:
        # Fetch all prices
        result = await session.execute(select(PriceTable))
        prices = result.scalars().all()
        
        # Group by (produce_id, region_pincode_prefix)
        groups = {}
        for p in prices:
            key = (p.produce_id, p.region_pincode_prefix)
            if key not in groups:
                groups[key] = []
            groups[key].append(p)
            
        # Find duplicates and delete older ones
        deleted_count = 0
        for key, group in groups.items():
            if len(group) > 1:
                # Sort by valid_date descending, then by price_id (as tiebreaker)
                # This ensures the most recent price is at index 0
                group.sort(key=lambda x: (x.valid_date, str(x.price_id)), reverse=True)
                
                # Keep the first one (most recent), delete the rest
                to_keep = group[0]
                to_delete = group[1:]
                
                for p in to_delete:
                    print(f"Deleting duplicate PriceTable row: produce_id={p.produce_id}, valid_date={p.valid_date}, base_price={p.base_price}")
                    await session.delete(p)
                    deleted_count += 1
                    
        if deleted_count > 0:
            await session.commit()
            print(f"Cleanup completed. Deleted {deleted_count} duplicate records.")
        else:
            print("No duplicate records found.")

if __name__ == "__main__":
    asyncio.run(main())
