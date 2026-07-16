from fastapi import APIRouter
from pydantic import BaseModel
import uuid

router = APIRouter(prefix="/api/v1/auth", tags=["Auth (Mock)"])

class SendOtpRequest(BaseModel):
    phone: str

class VerifyOtpRequest(BaseModel):
    phone: str
    otp: str
    name: str | None = None

@router.post("/otp/send")
async def send_otp(payload: SendOtpRequest):
    return {"message": "Mock OTP sent successfully"}

@router.post("/otp/verify")
async def verify_otp(payload: VerifyOtpRequest):
    return {
        "access_token": "fake-jwt-token-for-testing",
        "token_type": "bearer",
        "user": {
            "user_id": str(uuid.uuid4()),
            "phone": payload.phone,
            "name": payload.name or "Mock Farmer",
            "role": "farmer",
            "verified": True
        }
    }
