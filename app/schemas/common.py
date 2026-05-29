from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class APIMessage(BaseModel):
    message: str


class TimestampMixin(BaseModel):
    created_at: datetime


class UUIDMixin(BaseModel):
    id: UUID
