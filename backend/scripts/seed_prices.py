import asyncio
from datetime import date
from decimal import Decimal
import sys
import os

# Add the backend directory to sys.path so we can import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal
from app.models.produce import ProduceCatalog, PriceTable, UnitType

async def seed_data():
    async with AsyncSessionLocal() as session:
        # Create Produce Items
        items = [
            ProduceCatalog(
                name_en="Onions",
                name_te="ఉల్లిపాయలు",
                unit=UnitType.kg,
                image_url=None
            ),
            ProduceCatalog(
                name_en="Tomatoes",
                name_te="టమోటాలు",
                unit=UnitType.kg,
                image_url=None
            ),
            ProduceCatalog(
                name_en="Potatoes",
                name_te="బంగాళాదుంపలు",
                unit=UnitType.kg,
                image_url=None
            ),
            ProduceCatalog(
                name_en="Chillies",
                name_te="మిర్చి",
                unit=UnitType.kg,
                image_url=None
            ),
            ProduceCatalog(
                name_en="Brinjal",
                name_te="వంకాయ",
                unit=UnitType.kg,
                image_url=None
            ),
            ProduceCatalog(
                name_en="Coriander",
                name_te="కొత్తిమీర",
                unit=UnitType.bundle,
                image_url=None
            )
        ]
        
        session.add_all(items)
        await session.flush() # flush to get the UUIDs
        
        # Create Price Tables for region '530'
        today = date.today()
        base_prices = [
            Decimal("30.00"),  # Onions
            Decimal("40.00"),  # Tomatoes
            Decimal("35.00"),  # Potatoes
            Decimal("50.00"),  # Chillies
            Decimal("45.00"),  # Brinjal
            Decimal("10.00")   # Coriander
        ]
        
        prices = []
        for i, item in enumerate(items):
            prices.append(
                PriceTable(
                    produce_id=item.produce_id,
                    region_pincode_prefix="530",
                    base_price=base_prices[i],
                    platform_margin_pct=Decimal("5.00"),
                    valid_date=today
                )
            )
            
        session.add_all(prices)
        await session.commit()
        print(f"Successfully seeded {len(items)} produce items and {len(prices)} prices for region 530.")

if __name__ == "__main__":
    asyncio.run(seed_data())
