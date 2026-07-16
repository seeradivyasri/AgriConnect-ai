import uuid
import enum
from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from sqlalchemy import String, TIMESTAMP, Date, Numeric, func, text, ForeignKey, UniqueConstraint, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.models import Base

class UnitType(str, enum.Enum):
    kg = "kg"
    dozen = "dozen"
    bundle = "bundle"

class VisionGrade(str, enum.Enum):
    A = "A"
    B = "B"
    C = "C"
    REJECTED = "REJECTED"

class ListingStatus(str, enum.Enum):
    pending = "pending"
    negotiating = "negotiating"
    accepted = "accepted"
    rejected = "rejected"
    sold = "sold"

class ProduceCatalog(Base):
    __tablename__ = "produce_catalog"

    produce_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        server_default=text("gen_random_uuid()")
    )
    name_en: Mapped[str] = mapped_column(String(100), nullable=False)
    name_te: Mapped[str] = mapped_column(String(100), nullable=False)
    unit: Mapped[UnitType] = mapped_column(
        SQLEnum(UnitType, name="unit_type"),
        nullable=False
    )
    image_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class PriceTable(Base):
    __tablename__ = "price_table"

    price_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        server_default=text("gen_random_uuid()")
    )
    produce_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("produce_catalog.produce_id"),
        nullable=False
    )
    region_pincode_prefix: Mapped[str] = mapped_column(String(3), nullable=False)
    base_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    platform_margin_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    valid_date: Mapped[date] = mapped_column(Date, nullable=False)

    __table_args__ = (
        UniqueConstraint("produce_id", "region_pincode_prefix", "valid_date", name="uix_produce_region_date"),
    )


class Listing(Base):
    __tablename__ = "listings"

    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        server_default=text("gen_random_uuid()")
    )
    farmer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"), 
        nullable=False
    )
    produce_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("produce_catalog.produce_id"),
        nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    photo_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    vision_grade: Mapped[Optional[VisionGrade]] = mapped_column(
        SQLEnum(VisionGrade, name="vision_grade"),
        nullable=True
    )
    status: Mapped[ListingStatus] = mapped_column(
        SQLEnum(ListingStatus, name="listing_status"),
        nullable=False,
        default=ListingStatus.pending,
        server_default=text("'pending'")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), 
        server_default=func.now(),
        nullable=False
    )
