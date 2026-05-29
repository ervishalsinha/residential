from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import ensure_property_access, get_current_user, get_role_name, owned_property_ids, resident_property_ids
from app.db.session import get_db
from app.models import Unit, User
from app.repositories.domain import units_repo
from app.schemas.domain import UnitCreate, UnitUpdate

router = APIRouter()


@router.get("")
def list_units(
    property_id: UUID | None = Query(default=None),
    skip: int = 0,
    limit: int = 200,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Unit)
    if property_id:
        ensure_property_access(db, user, str(property_id))
        query = query.filter(Unit.property_id == str(property_id))
    else:
        role_name = get_role_name(user)
        if role_name == "property_admin":
            allowed_ids = owned_property_ids(db, user)
            if not allowed_ids:
                return []
            query = query.filter(Unit.property_id.in_(allowed_ids))
        elif role_name == "resident":
            allowed_ids = resident_property_ids(db, user)
            if not allowed_ids:
                return []
            query = query.filter(Unit.property_id.in_(allowed_ids))
    return query.order_by(Unit.unit_number.asc()).offset(skip).limit(limit).all()


@router.post("")
def create_unit(payload: UnitCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_property_access(db, user, str(payload.property_id), owner_only=True)
    return units_repo.create(db, payload.model_dump())


@router.put("/{unit_id}")
def update_unit(unit_id: UUID, payload: UnitUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = units_repo.get(db, unit_id)
    if not item:
        raise HTTPException(status_code=404, detail="Unit not found")
    ensure_property_access(db, user, str(item.property_id), owner_only=True)
    return units_repo.update(db, item, payload.model_dump(exclude_none=True))


@router.delete("/{unit_id}")
def delete_unit(unit_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = units_repo.get(db, unit_id)
    if not item:
        raise HTTPException(status_code=404, detail="Unit not found")
    ensure_property_access(db, user, str(item.property_id), owner_only=True)
    units_repo.delete(db, item)
    return {"message": "Unit deleted"}
