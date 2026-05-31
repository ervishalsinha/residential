import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(50), unique=True, index=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    full_name: Mapped[str] = mapped_column(String(150))
    mobile_number: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payment_upi_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payment_upi_account_holder_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    payment_bank_account_holder_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    payment_bank_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    payment_bank_account_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    payment_bank_ifsc: Mapped[str | None] = mapped_column(String(20), nullable=True)
    active_payment_method: Mapped[str | None] = mapped_column(String(10), nullable=True)
    razorpay_linked_account_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    razorpay_linked_account_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    role_id: Mapped[str] = mapped_column(String(36), ForeignKey("roles.id"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    role = relationship("Role")
