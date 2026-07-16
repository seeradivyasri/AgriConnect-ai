from pydantic import BaseModel, Field
from uuid import UUID

class CartItemAdd(BaseModel):
    listing_id: UUID
    quantity: float = Field(..., gt=0, description="Quantity to add must be greater than zero")
