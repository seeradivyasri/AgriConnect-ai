from pydantic import BaseModel, ConfigDict
from decimal import Decimal
from typing import Optional

class NegotiateRequest(BaseModel):
    farmer_ask: Decimal

class RespondRequest(BaseModel):
    farmer_response: str

class NegotiationResponse(BaseModel):
    engine_decision: str
    counter_price: Optional[Decimal] = None
    final_price: Optional[Decimal] = None
    ceiling_shown: Optional[Decimal] = None
    ai_message: str
    round_number: int
    
    model_config = ConfigDict(from_attributes=True)
