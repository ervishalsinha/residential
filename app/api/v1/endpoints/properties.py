from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import ensure_property_access, get_current_user, get_role_name, owned_property_ids, resident_property_ids
from app.db.session import get_db
from app.models import Property, PropertyType, ResidentProfile, User
from app.repositories.domain import properties_repo
from app.schemas.domain import PropertyCreate, PropertyUpdate

router = APIRouter()


def _normalize_property_name(name: str) -> str:
    return " ".join(name.strip().split())


def _normalize_property_type(raw_value: str | None) -> str:
    value = (raw_value or "").strip().lower().replace("_", " ")
    if value in {"pg", "hostel"}:
        return "pg"
    if value in {"building", "apartment", "building/apartment", "building apartment", "society", "gated society", "standalone building"}:
        return "building"
    raise HTTPException(status_code=400, detail="property_type must be either 'pg' or 'building/apartment'")


def _type_candidates(normalized: str) -> list[str]:
    if normalized == "pg":
        return ["pg", "hostel"]
    return ["apartment", "standalone_building", "gated_society", "building", "society"]


def _resolve_property_type_id(db: Session, normalized_type: str) -> str:
    candidates = _type_candidates(normalized_type)
    row = db.query(PropertyType).filter(func.lower(PropertyType.name).in_(candidates)).order_by(PropertyType.name.asc()).first()
    if row:
        return str(row.id)
    fallback_name = "pg" if normalized_type == "pg" else "apartment"
    created = PropertyType(name=fallback_name)
    db.add(created)
    db.flush()
    return str(created.id)


def _property_type_label(item: Property, property_type_by_id: dict[str, str]) -> str:
    if item.property_type:
        return _normalize_property_type(item.property_type)
    if item.property_type_id and str(item.property_type_id) in property_type_by_id:
        return _normalize_property_type(property_type_by_id[str(item.property_type_id)])
    return "building"


def _property_payload(item: Property, property_type_by_id: dict[str, str]) -> dict:
    return {
        "id": str(item.id),
        "name": item.name,
        "owner_user_id": str(item.owner_user_id) if item.owner_user_id else None,
        "property_type": _property_type_label(item, property_type_by_id),
        "property_type_id": str(item.property_type_id),
        "is_primary": bool(item.is_primary),
        "address_line1": item.address_line1,
        "city": item.city,
        "state": item.state,
        "pincode": item.pincode,
        "total_units": item.total_units,
        "created_at": item.created_at,
    }


def _owner_name_exists(db: Session, owner_id: str, name: str, exclude_property_id: str | None = None) -> bool:
    query = db.query(Property.id).filter(
        Property.owner_user_id == owner_id,
        func.lower(Property.name) == name.lower(),
    )
    if exclude_property_id:
        query = query.filter(Property.id != exclude_property_id)
    return query.first() is not None


@router.get("")
def list_properties(skip: int = 0, limit: int = 50, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    role_name = get_role_name(user)
    query = db.query(properties_repo.model)

    if role_name == "property_admin":
        owner_ids = owned_property_ids(db, user, include_all=True)
        if not owner_ids:
            return []
        query = query.filter(properties_repo.model.id.in_(owner_ids))
    elif role_name == "resident":
        allowed_ids = resident_property_ids(db, user)
        if not allowed_ids:
            return []
        query = query.filter(properties_repo.model.id.in_(allowed_ids))

    properties = query.order_by(properties_repo.model.created_at.desc()).offset(skip).limit(limit).all()
    property_type_ids = {str(item.property_type_id) for item in properties if item.property_type_id}
    type_rows = db.query(PropertyType.id, PropertyType.name).filter(PropertyType.id.in_(property_type_ids)).all() if property_type_ids else []
    property_type_by_id = {str(row[0]): row[1] for row in type_rows}
    return [_property_payload(item, property_type_by_id) for item in properties]


@router.post("")
def create_property(payload: PropertyCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    role_name = get_role_name(user)
    if role_name not in {"property_admin", "super_admin"}:
        raise HTTPException(status_code=403, detail="Only owners can create properties")

    normalized_name = _normalize_property_name(payload.name)
    if not normalized_name:
        raise HTTPException(status_code=400, detail="Property name is required")

    if _owner_name_exists(db, str(user.id), normalized_name):
        raise HTTPException(status_code=409, detail="Property name already exists for this owner")

    if payload.property_type:
        normalized_type = _normalize_property_type(payload.property_type)
        property_type_id = _resolve_property_type_id(db, normalized_type)
    elif payload.property_type_id:
        property_type_row = db.query(PropertyType).filter(PropertyType.id == str(payload.property_type_id)).first()
        if not property_type_row:
            raise HTTPException(status_code=400, detail="Invalid property_type_id")
        normalized_type = _normalize_property_type(property_type_row.name)
        property_type_id = str(property_type_row.id)
    else:
        raise HTTPException(status_code=400, detail="Either property_type or property_type_id is required")

    owner_property_count = db.query(func.count(Property.id)).filter(Property.owner_user_id == str(user.id)).scalar() or 0
    data = payload.model_dump(exclude_none=True)
    data["name"] = normalized_name
    data["owner_user_id"] = str(user.id)
    data["property_type_id"] = property_type_id
    data["property_type"] = normalized_type
    data["is_primary"] = owner_property_count == 0
    data["address_line1"] = (payload.address_line1 or "").strip()
    data["city"] = (payload.city or "").strip()
    data["state"] = (payload.state or "").strip()
    data["pincode"] = (payload.pincode or "").strip()

    item = properties_repo.create(db, data)
    if user.selected_property_id is None:
        user.selected_property_id = str(item.id)
        db.commit()
        db.refresh(item)

    type_map = {str(property_type_id): normalized_type}
    return _property_payload(item, type_map)


@router.get("/active")
def get_active_property(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    role_name = get_role_name(user)
    if role_name != "property_admin":
        return {"selected_property_id": None}

    owner_ids = owned_property_ids(db, user, include_all=True)
    selected_property_id = str(user.selected_property_id) if user.selected_property_id else None
    if selected_property_id and selected_property_id in owner_ids:
        return {"selected_property_id": selected_property_id}

    primary_row = (
        db.query(Property.id)
        .filter(Property.owner_user_id == str(user.id), Property.is_primary.is_(True))
        .order_by(Property.created_at.asc())
        .first()
    )
    if primary_row:
        selected_property_id = str(primary_row[0])
        user.selected_property_id = selected_property_id
        db.commit()
        return {"selected_property_id": selected_property_id}

    return {"selected_property_id": None}


@router.post("/{property_id}/switch")
def switch_active_property(property_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_property_access(db, user, str(property_id), owner_only=True)
    user.selected_property_id = str(property_id)
    db.commit()
    return {"selected_property_id": str(property_id)}


@router.get("/{property_id}")
def get_property(property_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_property_access(db, user, str(property_id))
    item = properties_repo.get(db, property_id)
    if not item:
        raise HTTPException(status_code=404, detail="Property not found")
    property_type_name = db.query(PropertyType.name).filter(PropertyType.id == str(item.property_type_id)).scalar()
    type_map = {str(item.property_type_id): property_type_name} if property_type_name else {}
    return _property_payload(item, type_map)


@router.put("/{property_id}")
def update_property(property_id: UUID, payload: PropertyUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_property_access(db, user, str(property_id), owner_only=True)
    item = properties_repo.get(db, property_id)
    if not item:
        raise HTTPException(status_code=404, detail="Property not found")

    update_data = payload.model_dump(exclude_none=True)
    if "name" in update_data:
        normalized_name = _normalize_property_name(str(update_data["name"]))
        if not normalized_name:
            raise HTTPException(status_code=400, detail="Property name is required")
        if _owner_name_exists(db, str(user.id), normalized_name, exclude_property_id=str(item.id)):
            raise HTTPException(status_code=409, detail="Property name already exists for this owner")
        update_data["name"] = normalized_name

    if "property_type" in update_data:
        normalized_type = _normalize_property_type(str(update_data["property_type"]))
        update_data["property_type"] = normalized_type
        update_data["property_type_id"] = _resolve_property_type_id(db, normalized_type)

    updated = properties_repo.update(db, item, update_data)
    property_type_name = db.query(PropertyType.name).filter(PropertyType.id == str(updated.property_type_id)).scalar()
    type_map = {str(updated.property_type_id): property_type_name} if property_type_name else {}
    return _property_payload(updated, type_map)


@router.delete("/{property_id}")
def delete_property(property_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_property_access(db, user, str(property_id), owner_only=True)
    item = properties_repo.get(db, property_id)
    if not item:
        raise HTTPException(status_code=404, detail="Property not found")

    owner_property_count = db.query(func.count(Property.id)).filter(Property.owner_user_id == str(user.id)).scalar() or 0
    if owner_property_count <= 1:
        raise HTTPException(status_code=400, detail="Cannot delete the last remaining property")

    if item.is_primary:
        raise HTTPException(status_code=400, detail="Primary property cannot be deleted")

    active_residents = (
        db.query(func.count(ResidentProfile.id))
        .filter(ResidentProfile.property_id == str(property_id), ResidentProfile.occupancy_status == "active")
        .scalar()
        or 0
    )
    if active_residents > 0:
        raise HTTPException(status_code=400, detail="Cannot delete property with active residents")

    is_selected_property = str(user.selected_property_id) == str(property_id)
    properties_repo.delete(db, item)

    if is_selected_property:
        fallback_property = (
            db.query(Property)
            .filter(Property.owner_user_id == str(user.id), Property.is_primary.is_(True))
            .order_by(Property.created_at.asc())
            .first()
        )
        user.selected_property_id = str(fallback_property.id) if fallback_property else None
        db.commit()

    return {"message": "Property deleted"}
