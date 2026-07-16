import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete
from app.database import AsyncSessionLocal
from app.models.produce import ProduceCatalog, PriceTable

async def delete_fake_produce():
    fake_ids = [
        '45be8807-7a54-47ed-b062-8147d1dfcff8', # Fake Onion
        'f6e77369-7bf1-4315-84a9-417f97afbd99'  # Fake Carrot
    ]
    
    async with AsyncSessionLocal() as db:
        # Delete prices first (foreign key constraint)
        await db.execute(delete(PriceTable).where(PriceTable.produce_id.in_(fake_ids)))
        # Then delete the produce
        await db.execute(delete(ProduceCatalog).where(ProduceCatalog.produce_id.in_(fake_ids)))
        await db.commit()
        print("Successfully deleted the fake Onion and Carrot from the database!")

if __name__ == "__main__":
    asyncio.run(delete_fake_produce())
