from uuid import UUID
import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import ensure_property_access, get_current_user, get_role_name, owned_property_ids, resident_property_ids
from app.core.socket_server import emit_event
from app.db.session import get_db
from app.models import Complaint, ComplaintComment, Notice, Notification, OwnerExpense, ResidentProfile, Unit, User
from app.repositories.domain import complaint_comments_repo, complaints_repo
from app.schemas.domain import ComplaintCommentCreate, ComplaintCreate, ComplaintUpdate

router = APIRouter()

VISIBILITY_OWNER_ONLY = "owner_only"
VISIBILITY_OWNER_AND_TENANTS = "owner_and_tenants"


def _normalized_visibility(raw: str | None) -> str:
    value = (raw or "").strip().lower()
    if value == VISIBILITY_OWNER_ONLY:
        return VISIBILITY_OWNER_ONLY
    return VISIBILITY_OWNER_AND_TENANTS


def _normalize_image_urls(image_urls: list[str] | None) -> list[str]:
    normalized: list[str] = []
    for raw in image_urls or []:
        item = str(raw).strip()
        if item and item not in normalized:
            normalized.append(item)
    return normalized


def _complaint_image_urls(item: Complaint) -> list[str]:
    if not item.image_urls_json:
        return []
    try:
        decoded = json.loads(item.image_urls_json)
        if isinstance(decoded, list):
            return [str(value).strip() for value in decoded if str(value).strip()]
    except json.JSONDecodeError:
        return []
    return []


def _stay_owner_user_ids(db: Session, property_id: str) -> set[str]:
    notice_owner_ids = {str(item[0]) for item in db.query(Notice.published_by).filter(Notice.property_id == property_id).all()}
    expense_owner_ids = {str(item[0]) for item in db.query(OwnerExpense.created_by).filter(OwnerExpense.property_id == property_id).all()}
    return {value for value in notice_owner_ids.union(expense_owner_ids) if value}


def _can_resident_access_complaint(user: User, complaint: Complaint) -> bool:
    visibility = _normalized_visibility(getattr(complaint, "visibility", None))
    if visibility == VISIBILITY_OWNER_ONLY and str(complaint.resident_id) != str(user.id):
        return False
    return True


def _complaint_payload(item: Complaint, user_by_id: dict[str, User], unit_by_user_id: dict[str, Unit]) -> dict:
    resident_user = user_by_id.get(str(item.resident_id))
    unit = unit_by_user_id.get(str(item.resident_id))
    return {
        "id": str(item.id),
        "title": item.title,
        "category": item.category,
        "visibility": _normalized_visibility(getattr(item, "visibility", None)),
        "description": item.description,
        "image_urls": _complaint_image_urls(item),
        "priority": item.priority,
        "status": item.status,
        "resident_id": str(item.resident_id),
        "property_id": str(item.property_id),
        "created_at": item.created_at,
        "resident_name": resident_user.full_name if resident_user else None,
        "raised_unit": unit.unit_number if unit else None,
    }


@router.get("")
def list_complaints(
    skip: int = 0,
    limit: int = 50,
    property_id: UUID | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    role_name = get_role_name(user)
    query = db.query(Complaint)
    if property_id:
        ensure_property_access(db, user, str(property_id))
        query = query.filter(Complaint.property_id == str(property_id))
    elif role_name == "property_admin":
        allowed_ids = owned_property_ids(db, user)
        if not allowed_ids:
            return []
        query = query.filter(Complaint.property_id.in_(allowed_ids))
    elif role_name == "resident":
        allowed_ids = resident_property_ids(db, user)
        if not allowed_ids:
            return []
        query = query.filter(Complaint.property_id.in_(allowed_ids))

    if role_name == "resident":
        query = query.filter((Complaint.visibility != VISIBILITY_OWNER_ONLY) | (Complaint.resident_id == str(user.id)))
    complaints = query.order_by(Complaint.created_at.desc()).offset(skip).limit(limit).all()

    resident_ids = [item.resident_id for item in complaints]
    users = db.query(User).filter(User.id.in_(resident_ids)).all() if resident_ids else []
    user_by_id = {str(user.id): user for user in users}
    resident_profiles_query = db.query(ResidentProfile).filter(ResidentProfile.user_id.in_(resident_ids)) if resident_ids else None
    if resident_profiles_query is None:
        resident_profiles = []
    else:
        if property_id:
            resident_profiles_query = resident_profiles_query.filter(ResidentProfile.property_id == str(property_id))
        resident_profiles = resident_profiles_query.all()
    unit_ids = [str(item.unit_id) for item in resident_profiles if item.unit_id]
    units = db.query(Unit).filter(Unit.id.in_(unit_ids)).all() if unit_ids else []
    unit_by_id = {str(item.id): item for item in units}
    unit_by_user_id = {
        str(profile.user_id): unit_by_id.get(str(profile.unit_id))
        for profile in resident_profiles
        if profile.unit_id
    }

    return [_complaint_payload(item, user_by_id=user_by_id, unit_by_user_id=unit_by_user_id) for item in complaints]


@router.post("")
def create_complaint(
    payload: ComplaintCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    role_name = get_role_name(user)
    ensure_property_access(db, user, str(payload.property_id))
    if role_name == "resident" and str(payload.resident_id) != str(user.id):
        raise HTTPException(status_code=403, detail="Residents can only create complaints for their own account")

    data = payload.model_dump()
    data["category"] = (payload.category or "general").strip() or "general"
    data["visibility"] = _normalized_visibility(payload.visibility)
    image_urls = _normalize_image_urls(payload.image_urls)
    data["image_urls_json"] = json.dumps(image_urls) if image_urls else None
    data.pop("image_urls", None)
    item = complaints_repo.create(db, data)

    property_id = str(item.property_id)
    resident_user_ids = {
        str(value[0])
        for value in db.query(ResidentProfile.user_id).filter(ResidentProfile.property_id == property_id, ResidentProfile.occupancy_status != "deleted").all()
    }
    owner_user_ids = _stay_owner_user_ids(db, property_id)
    visibility = data["visibility"]
    if visibility == VISIBILITY_OWNER_ONLY:
        target_user_ids = owner_user_ids.union({str(user.id)})
        visibility_label = "owner only"
    else:
        target_user_ids = resident_user_ids.union(owner_user_ids).union({str(user.id)})
        visibility_label = "owner + all tenants"

    for target_user_id in target_user_ids:
        db.add(
            Notification(
                user_id=target_user_id,
                notification_type="complaint_raised",
                title="New complaint raised",
                body=f"{item.title} ({item.priority}) has been raised in your stay ({visibility_label}).",
                channel="push",
                status="queued",
                is_read=False,
            )
        )
    db.commit()

    background_tasks.add_task(
        emit_event,
        "complaint.updated",
        {"id": str(item.id), "status": item.status.value if hasattr(item.status, "value") else str(item.status)},
    )
    resident = db.query(User).filter(User.id == item.resident_id).first()
    resident_profile = db.query(ResidentProfile).filter(ResidentProfile.user_id == str(item.resident_id), ResidentProfile.property_id == str(item.property_id)).first()
    unit = db.query(Unit).filter(Unit.id == str(resident_profile.unit_id)).first() if resident_profile and resident_profile.unit_id else None
    return _complaint_payload(item, user_by_id={str(resident.id): resident} if resident else {}, unit_by_user_id={str(item.resident_id): unit} if unit else {})


@router.get("/{complaint_id}")
def get_complaint(complaint_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = complaints_repo.get(db, complaint_id)
    if not item:
        raise HTTPException(status_code=404, detail="Complaint not found")
    ensure_property_access(db, user, str(item.property_id))
    if get_role_name(user) == "resident" and not _can_resident_access_complaint(user, item):
        raise HTTPException(status_code=403, detail="This complaint is visible only to owner and author")
    resident = db.query(User).filter(User.id == item.resident_id).first()
    resident_profile = db.query(ResidentProfile).filter(ResidentProfile.user_id == str(item.resident_id), ResidentProfile.property_id == str(item.property_id)).first()
    unit = db.query(Unit).filter(Unit.id == str(resident_profile.unit_id)).first() if resident_profile and resident_profile.unit_id else None
    return _complaint_payload(item, user_by_id={str(resident.id): resident} if resident else {}, unit_by_user_id={str(item.resident_id): unit} if unit else {})


@router.put("/{complaint_id}")
def update_complaint(
    complaint_id: UUID,
    payload: ComplaintUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = complaints_repo.get(db, complaint_id)
    if not item:
        raise HTTPException(status_code=404, detail="Complaint not found")
    ensure_property_access(db, user, str(item.property_id), owner_only=True)
    data = payload.model_dump(exclude_none=True)
    if "visibility" in data:
        data["visibility"] = _normalized_visibility(data.get("visibility"))
    if "category" in data and data.get("category") is not None:
        data["category"] = (str(data["category"]).strip() or "general")
    if "image_urls" in data:
        image_urls = _normalize_image_urls(data.get("image_urls"))
        data["image_urls_json"] = json.dumps(image_urls) if image_urls else None
        data.pop("image_urls", None)
    updated = complaints_repo.update(db, item, data)
    background_tasks.add_task(
        emit_event,
        "complaint.updated",
        {"id": str(updated.id), "status": updated.status.value if hasattr(updated.status, "value") else str(updated.status)},
    )
    resident = db.query(User).filter(User.id == updated.resident_id).first()
    resident_profile = db.query(ResidentProfile).filter(ResidentProfile.user_id == str(updated.resident_id), ResidentProfile.property_id == str(updated.property_id)).first()
    unit = db.query(Unit).filter(Unit.id == str(resident_profile.unit_id)).first() if resident_profile and resident_profile.unit_id else None
    return _complaint_payload(updated, user_by_id={str(resident.id): resident} if resident else {}, unit_by_user_id={str(updated.resident_id): unit} if unit else {})


@router.delete("/{complaint_id}")
def delete_complaint(complaint_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = complaints_repo.get(db, complaint_id)
    if not item:
        raise HTTPException(status_code=404, detail="Complaint not found")
    ensure_property_access(db, user, str(item.property_id), owner_only=True)
    complaints_repo.delete(db, item)
    return {"message": "Complaint deleted"}


@router.get("/{complaint_id}/comments")
def list_complaint_comments(complaint_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    complaint = complaints_repo.get(db, complaint_id)
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    ensure_property_access(db, user, str(complaint.property_id))
    if get_role_name(user) == "resident" and not _can_resident_access_complaint(user, complaint):
        raise HTTPException(status_code=403, detail="This complaint is visible only to owner and author")

    comments = (
        db.query(ComplaintComment)
        .filter(ComplaintComment.complaint_id == str(complaint_id))
        .order_by(ComplaintComment.created_at.asc())
        .all()
    )
    author_ids = [item.author_user_id for item in comments]
    authors = db.query(User).filter(User.id.in_(author_ids)).all() if author_ids else []
    author_by_id = {str(author.id): author for author in authors}

    return [
        {
            "id": str(item.id),
            "complaint_id": str(item.complaint_id),
            "author_user_id": str(item.author_user_id),
            "message": item.message,
            "created_at": item.created_at,
            "author_name": author_by_id.get(str(item.author_user_id)).full_name if author_by_id.get(str(item.author_user_id)) else None,
        }
        for item in comments
    ]


@router.post("/{complaint_id}/comments")
def add_complaint_comment(
    complaint_id: UUID,
    payload: ComplaintCommentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    complaint = complaints_repo.get(db, complaint_id)
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    ensure_property_access(db, user, str(complaint.property_id))
    if get_role_name(user) == "resident" and not _can_resident_access_complaint(user, complaint):
        raise HTTPException(status_code=403, detail="This complaint is visible only to owner and author")
    created = complaint_comments_repo.create(
        db,
        {
            "complaint_id": complaint_id,
            "author_user_id": user.id,
            "message": payload.message,
        },
    )
    return {
        "id": str(created.id),
        "complaint_id": str(created.complaint_id),
        "author_user_id": str(created.author_user_id),
        "message": created.message,
        "created_at": created.created_at,
        "author_name": user.full_name,
    }
