from uuid import UUID
import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import ensure_property_access, get_current_user, get_role_name, owned_property_ids, resident_property_ids
from app.core.socket_server import emit_event
from app.db.session import get_db
from app.models import Notice, Notification, OwnerExpense, Property, ResidentProfile, User
from app.repositories.domain import notices_repo
from app.schemas.domain import NoticeCreate, NoticeUpdate

router = APIRouter()


def _normalize_image_urls(image_url: str | None, image_urls: list[str] | None) -> list[str]:
    values = [*(image_urls or [])]
    if image_url:
        values.insert(0, image_url)
    normalized: list[str] = []
    for raw in values:
        item = str(raw).strip()
        if item and item not in normalized:
            normalized.append(item)
    return normalized


def _notice_to_payload(item: Notice) -> dict:
    urls: list[str] = []
    if item.image_urls_json:
        try:
            decoded = json.loads(item.image_urls_json)
            if isinstance(decoded, list):
                urls.extend([str(value).strip() for value in decoded if str(value).strip()])
        except json.JSONDecodeError:
            pass
    if item.image_url and item.image_url not in urls:
        urls.insert(0, item.image_url)

    return {
        "id": str(item.id),
        "property_id": str(item.property_id),
        "title": item.title,
        "content": item.content,
        "image_url": urls[0] if urls else None,
        "image_urls": urls,
        "published_by": str(item.published_by),
        "created_at": item.created_at,
    }


def _stay_owner_user_ids(db: Session, property_id: str) -> set[str]:
    notice_owner_ids = {str(item[0]) for item in db.query(Notice.published_by).filter(Notice.property_id == property_id).all()}
    expense_owner_ids = {str(item[0]) for item in db.query(OwnerExpense.created_by).filter(OwnerExpense.property_id == property_id).all()}
    return {value for value in notice_owner_ids.union(expense_owner_ids) if value}


@router.get("")
def list_notices(
    skip: int = 0,
    limit: int = 50,
    property_id: UUID | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Notice)
    if property_id:
        ensure_property_access(db, user, str(property_id))
        query = query.filter(Notice.property_id == str(property_id))
    else:
        role_name = get_role_name(user)
        if role_name == "property_admin":
            allowed_ids = owned_property_ids(db, user)
            if not allowed_ids:
                return []
            query = query.filter(Notice.property_id.in_(allowed_ids))
        elif role_name == "resident":
            allowed_ids = resident_property_ids(db, user)
            if not allowed_ids:
                return []
            query = query.filter(Notice.property_id.in_(allowed_ids))
    items = query.order_by(Notice.created_at.desc()).offset(skip).limit(limit).all()
    return [_notice_to_payload(item) for item in items]


@router.post("")
def create_notice(
    payload: NoticeCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_property_access(db, user, str(payload.property_id), owner_only=True)
    data = payload.model_dump()
    image_urls = _normalize_image_urls(payload.image_url, payload.image_urls)
    data["image_url"] = image_urls[0] if image_urls else None
    data["image_urls_json"] = json.dumps(image_urls) if image_urls else None
    data.pop("image_urls", None)
    item = notices_repo.create(db, data)

    property_id = str(item.property_id)
    resident_user_ids = {
        str(value[0])
        for value in db.query(ResidentProfile.user_id).filter(ResidentProfile.property_id == property_id, ResidentProfile.occupancy_status != "deleted").all()
    }
    owner_user_ids = _stay_owner_user_ids(db, property_id)
    target_user_ids = resident_user_ids.union(owner_user_ids)
    target_user_ids.add(str(user.id))

    property_row = db.query(Property).filter(Property.id == property_id).first()
    property_name = property_row.name if property_row else "your property"
    publisher_name = user.full_name if user and user.full_name else "Owner"
    content_preview = (item.content or "").strip().replace("\n", " ")[:90]
    content_suffix = f" Details: {content_preview}." if content_preview else ""

    for target_user_id in target_user_ids:
        db.add(
            Notification(
                user_id=target_user_id,
                notification_type="notice_published",
                title="New notice published",
                body=f"{item.title} has been posted for {property_name} by {publisher_name}.{content_suffix}",
                metadata_json=json.dumps({"notice_id": str(item.id), "property_name": property_name, "publisher_name": publisher_name}),
                channel="push",
                status="queued",
                is_read=False,
            )
        )
    db.commit()

    background_tasks.add_task(emit_event, "notice.published", {"id": str(item.id), "title": item.title})
    return _notice_to_payload(item)


@router.get("/{notice_id}")
def get_notice(notice_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = notices_repo.get(db, notice_id)
    if not item:
        raise HTTPException(status_code=404, detail="Notice not found")
    ensure_property_access(db, user, str(item.property_id))
    return _notice_to_payload(item)


@router.put("/{notice_id}")
def update_notice(notice_id: UUID, payload: NoticeUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = notices_repo.get(db, notice_id)
    if not item:
        raise HTTPException(status_code=404, detail="Notice not found")
    ensure_property_access(db, user, str(item.property_id), owner_only=True)
    data = payload.model_dump(exclude_none=True)
    if "image_urls" in data or "image_url" in data:
        image_urls = _normalize_image_urls(data.get("image_url"), data.get("image_urls"))
        data["image_url"] = image_urls[0] if image_urls else None
        data["image_urls_json"] = json.dumps(image_urls) if image_urls else None
        data.pop("image_urls", None)
    updated = notices_repo.update(db, item, data)
    return _notice_to_payload(updated)


@router.delete("/{notice_id}")
def delete_notice(notice_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = notices_repo.get(db, notice_id)
    if not item:
        raise HTTPException(status_code=404, detail="Notice not found")
    ensure_property_access(db, user, str(item.property_id), owner_only=True)
    notices_repo.delete(db, item)
    return {"message": "Notice deleted"}
