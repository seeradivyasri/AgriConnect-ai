from pydantic import BaseModel, ConfigDict
from decimal import Decimal
from typing import List, Optional
from uuid import UUID
from app.models.produce import UnitType, VisionGrade

class ProduceItem(BaseModel):
    listing_id: UUID
    produce_name: str
    unit: UnitType
    customer_price: Decimal
    photo_url: Optional[str] = None
    vision_grade: Optional[VisionGrade] = None
    
    model_config = ConfigDict(from_attributes=True)

class CatalogResponse(BaseModel):
    items: List[ProduceItem]
