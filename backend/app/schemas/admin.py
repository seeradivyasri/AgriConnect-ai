from pydantic import BaseModel
from uuid import UUID
from datetime import date
from decimal import Decimal

class PriceCreate(BaseModel):
    produce_id: UUID
    region_pincode_prefix: str
    base_price: Decimal
    platform_margin_pct: Decimal
    valid_date: date
