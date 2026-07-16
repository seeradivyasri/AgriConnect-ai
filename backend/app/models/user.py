import uuid
import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Boolean, TIMESTAMP, func, text, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.models import Base

class UserRole(str, enum.Enum):
    farmer = "farmer"
    customer = "customer"
    admin = "admin"

class User(Base):
    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        server_default=text("gen_random_uuid()")
    )
    phone: Mapped[str] = mapped_column(String(15), unique=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole, name="user_role"),
        nullable=False
    )
    location_pincode: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    verified: Mapped[bool] = mapped_column(
        Boolean, 
        default=False, 
        server_default=text("false"),
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), 
        server_default=func.now(),
        nullable=False
    )
