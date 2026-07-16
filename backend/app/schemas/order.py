from pydantic import BaseModel
from uuid import UUID
from typing import List

class OrderItem(BaseModel):
    order_id: UUID
    listing_id: UUID
    quantity: float
    unit_price: float

class CheckoutResponse(BaseModel):
    total_amount: float
    orders: List[OrderItem]
