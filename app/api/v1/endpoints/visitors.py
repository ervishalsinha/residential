from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import ensure_property_access, get_current_user, get_role_name, owned_property_ids
from app.core.socket_server import emit_event
from app.db.session import get_db
from app.models import ResidentProfile, User
from app.repositories.domain import visitors_repo
from app.schemas.domain import VisitorCreate, VisitorUpdate

router = APIRouter()


@router.get("")
def list_visitors(skip: int = 0, limit: int = 50, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    items = visitors_repo.list(db, skip=skip, limit=limit)
    role_name = get_role_name(user)
    if role_name == "property_admin":
        allowed_ids = owned_property_ids(db, user)
        return [item for item in items if str(item.property_id) in allowed_ids]
    if role_name == "resident":
        resident_profile = (
            db.query(ResidentProfile)
            .filter(ResidentProfile.user_id == str(user.id), ResidentProfile.occupancy_status != "deleted")
            .first()
        )
        if not resident_profile:
            return []
        return [item for item in items if str(item.property_id) == str(resident_profile.property_id) and str(item.resident_id) == str(user.id)]
    return items


@router.post("")
def create_visitor(
    payload: VisitorCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_property_access(db, user, str(payload.property_id))
    if get_role_name(user) == "resident" and str(payload.resident_id) != str(user.id):
        raise HTTPException(status_code=403, detail="Residents can only create their own visitors")
    item = visitors_repo.create(db, payload.model_dump())
    background_tasks.add_task(
        emit_event,
        "visitor.updated",
        {"id": str(item.id), "status": item.status.value if hasattr(item.status, "value") else str(item.status)},
    )
    return item


@router.get("/{visitor_id}")
def get_visitor(visitor_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = visitors_repo.get(db, visitor_id)
    if not item:
        raise HTTPException(status_code=404, detail="Visitor not found")
    ensure_property_access(db, user, str(item.property_id))
    if get_role_name(user) == "resident" and str(item.resident_id) != str(user.id):
        raise HTTPException(status_code=403, detail="Residents can only access their own visitors")
    return item


@router.put("/{visitor_id}")
def update_visitor(
    visitor_id: UUID,
    payload: VisitorUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = visitors_repo.get(db, visitor_id)
    if not item:
        raise HTTPException(status_code=404, detail="Visitor not found")
    ensure_property_access(db, user, str(item.property_id))
    if get_role_name(user) == "resident" and str(item.resident_id) != str(user.id):
        raise HTTPException(status_code=403, detail="Residents can only update their own visitors")
    updated = visitors_repo.update(db, item, payload.model_dump(exclude_none=True))
    background_tasks.add_task(
        emit_event,
        "visitor.updated",
        {"id": str(updated.id), "status": updated.status.value if hasattr(updated.status, "value") else str(updated.status)},
    )
    return updated


@router.delete("/{visitor_id}")
def delete_visitor(visitor_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = visitors_repo.get(db, visitor_id)
    if not item:
        raise HTTPException(status_code=404, detail="Visitor not found")
    ensure_property_access(db, user, str(item.property_id))
    if get_role_name(user) == "resident" and str(item.resident_id) != str(user.id):
        raise HTTPException(status_code=403, detail="Residents can only delete their own visitors")
    visitors_repo.delete(db, item)
    return {"message": "Visitor deleted"}
