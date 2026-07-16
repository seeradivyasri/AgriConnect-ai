from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from decimal import Decimal
from uuid import UUID
from datetime import datetime
from app.models.produce import ListingStatus, VisionGrade

class ListingCreate(BaseModel):
    produce_id: Optional[UUID] = None
    produce_name: Optional[str] = None
    quantity: Decimal = Field(..., gt=0)

class ListingResponse(BaseModel):
    listing_id: UUID
    farmer_id: UUID
    produce_id: UUID
    quantity: Decimal
    photo_url: Optional[str] = None
    vision_grade: Optional[VisionGrade] = None
    status: ListingStatus
    created_at: datetime
    produce_name: Optional[str] = None
    final_price: Optional[Decimal] = None
    
    model_config = ConfigDict(from_attributes=True)
