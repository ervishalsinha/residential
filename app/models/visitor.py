import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class VisitorStatus(str, enum.Enum):
    requested = "requested"
    approved = "approved"
    denied = "denied"
    entered = "entered"
    exited = "exited"


class Visitor(Base):
    __tablename__ = "visitors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    property_id: Mapped[str] = mapped_column(String(36), ForeignKey("properties.id"), index=True)
    resident_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    mobile_number: Mapped[str] = mapped_column(String(20))
    purpose: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default=VisitorStatus.requested.value)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
