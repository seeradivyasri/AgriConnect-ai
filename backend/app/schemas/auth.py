from pydantic import BaseModel
from app.models.user import UserRole
from uuid import UUID

class OTPSendRequest(BaseModel):
    phone: str
    name: str
    role: UserRole

class OTPVerifyRequest(BaseModel):
    phone: str
    otp: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: UUID
    role: UserRole
