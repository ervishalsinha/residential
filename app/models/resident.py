import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ResidentProfile(Base):
    __tablename__ = "residents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), unique=True, index=True)
    owner_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    owner_mobile: Mapped[str | None] = mapped_column(String(20), nullable=True)
    property_id: Mapped[str] = mapped_column(String(36), ForeignKey("properties.id"), index=True)
    unit_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("units.id"), nullable=True)
    occupancy_status: Mapped[str] = mapped_column(String(40), default="active")
    monthly_rent: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    security_deposit: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    electricity_bill: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    maintenance_bill: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    parking_charges: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    wifi_charges: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    cleaning_bill: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    water_bill: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    payment_due_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    joining_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    vacated_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    aadhaar_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    emergency_contact_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    emergency_contact_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
