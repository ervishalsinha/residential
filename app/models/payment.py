import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    failed = "failed"


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    resident_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    property_id: Mapped[str] = mapped_column(String(36), ForeignKey("properties.id"), index=True)
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    payment_type: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default=PaymentStatus.pending.value)
    due_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rent_year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    rent_month: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    payout_method: Mapped[str | None] = mapped_column(String(10), nullable=True)
    payout_destination: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gateway_channel: Mapped[str | None] = mapped_column(String(30), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
