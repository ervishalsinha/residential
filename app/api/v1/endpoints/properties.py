from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import ensure_property_access, get_current_user, get_role_name, owned_property_ids, resident_property_ids
from app.db.session import get_db
from app.models import User
from app.repositories.domain import properties_repo
from app.schemas.domain import PropertyCreate, PropertyUpdate

router = APIRouter()


@router.get("")
def list_properties(skip: int = 0, limit: int = 50, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    role_name = get_role_name(user)
    query = db.query(properties_repo.model)

    if role_name == "property_admin":
        query = query.filter(properties_repo.model.owner_user_id == str(user.id))
    elif role_name == "resident":
        allowed_ids = resident_property_ids(db, user)
        if not allowed_ids:
            return []
        query = query.filter(properties_repo.model.id.in_(allowed_ids))

    return query.order_by(properties_repo.model.created_at.desc()).offset(skip).limit(limit).all()


@router.post("")
def create_property(payload: PropertyCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    role_name = get_role_name(user)
    if role_name not in {"property_admin", "super_admin"}:
        raise HTTPException(status_code=403, detail="Only owners can create properties")
    data = payload.model_dump()
    data["owner_user_id"] = str(user.id)
    return properties_repo.create(db, data)


@router.get("/{property_id}")
def get_property(property_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_property_access(db, user, str(property_id))
    item = properties_repo.get(db, property_id)
    if not item:
        raise HTTPException(status_code=404, detail="Property not found")
    return item


@router.put("/{property_id}")
def update_property(property_id: UUID, payload: PropertyUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_property_access(db, user, str(property_id), owner_only=True)
    item = properties_repo.get(db, property_id)
    if not item:
        raise HTTPException(status_code=404, detail="Property not found")
    return properties_repo.update(db, item, payload.model_dump(exclude_none=True))


@router.delete("/{property_id}")
def delete_property(property_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_property_access(db, user, str(property_id), owner_only=True)
    item = properties_repo.get(db, property_id)
    if not item:
        raise HTTPException(status_code=404, detail="Property not found")
    properties_repo.delete(db, item)
    return {"message": "Property deleted"}
