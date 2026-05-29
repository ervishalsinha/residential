from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy.orm import Session

ModelT = TypeVar("ModelT")


class BaseRepository(Generic[ModelT]):
    def __init__(self, model: type[ModelT]):
        self.model = model

    def list(self, db: Session, skip: int = 0, limit: int = 50) -> list[ModelT]:
        return db.query(self.model).offset(skip).limit(limit).all()

    def get(self, db: Session, item_id: str | UUID) -> ModelT | None:
        normalized_id = str(item_id) if isinstance(item_id, UUID) else item_id
        return db.query(self.model).filter(self.model.id == normalized_id).first()

    def create(self, db: Session, payload: dict) -> ModelT:
        obj = self.model(**self._normalize_payload(payload))
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def update(self, db: Session, obj: ModelT, payload: dict) -> ModelT:
        normalized = self._normalize_payload(payload)
        for key, value in normalized.items():
            setattr(obj, key, value)
        db.commit()
        db.refresh(obj)
        return obj

    def delete(self, db: Session, obj: ModelT) -> None:
        db.delete(obj)
        db.commit()

    @staticmethod
    def _normalize_payload(payload: dict) -> dict:
        normalized: dict = {}
        for key, value in payload.items():
            normalized[key] = str(value) if isinstance(value, UUID) else value
        return normalized
