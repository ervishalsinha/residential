from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import ensure_property_access, get_current_user, get_role_name, owned_property_ids
from app.db.session import get_db
from app.models import User
from app.repositories.domain import staff_repo
from app.schemas.domain import StaffCreate, StaffUpdate

router = APIRouter()


@router.get("")
def list_staff(skip: int = 0, limit: int = 50, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    items = staff_repo.list(db, skip=skip, limit=limit)
    if get_role_name(user) == "property_admin":
        allowed_ids = owned_property_ids(db, user)
        return [item for item in items if str(item.property_id) in allowed_ids]
    return items


@router.post("")
def create_staff(payload: StaffCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_property_access(db, user, str(payload.property_id), owner_only=True)
    return staff_repo.create(db, payload.model_dump())


@router.get("/{staff_id}")
def get_staff(staff_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = staff_repo.get(db, staff_id)
    if not item:
        raise HTTPException(status_code=404, detail="Staff not found")
    ensure_property_access(db, user, str(item.property_id))
    return item


@router.put("/{staff_id}")
def update_staff(staff_id: UUID, payload: StaffUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = staff_repo.get(db, staff_id)
    if not item:
        raise HTTPException(status_code=404, detail="Staff not found")
    ensure_property_access(db, user, str(item.property_id), owner_only=True)
    return staff_repo.update(db, item, payload.model_dump(exclude_none=True))


@router.delete("/{staff_id}")
def delete_staff(staff_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = staff_repo.get(db, staff_id)
    if not item:
        raise HTTPException(status_code=404, detail="Staff not found")
    ensure_property_access(db, user, str(item.property_id), owner_only=True)
    staff_repo.delete(db, item)
    return {"message": "Staff deleted"}
