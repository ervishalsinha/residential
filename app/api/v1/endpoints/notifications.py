import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.socket_server import emit_event
from app.db.session import get_db
from app.models import Notification, User
from app.services.notification_service import queue_notification, send_push_notification

router = APIRouter()


@router.get("")
def list_notifications(skip: int = 0, limit: int = 50, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    items = (
        db.query(Notification)
        .filter(Notification.user_id == str(user.id))
        .order_by(Notification.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": str(item.id),
            "user_id": str(item.user_id),
            "notification_type": item.notification_type,
            "title": item.title,
            "body": item.body,
            "metadata": json.loads(item.metadata_json) if item.metadata_json else None,
            "channel": item.channel,
            "status": item.status,
            "is_read": bool(item.is_read),
            "read_at": item.read_at,
            "created_at": item.created_at,
        }
        for item in items
    ]


@router.get("/unread-count")
def unread_count(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    count = db.query(Notification).filter(Notification.user_id == str(user.id), Notification.is_read.is_(False)).count()
    return {"unread": count}


@router.post("")
def create_notification(
    target_user_id: str,
    title: str,
    body: str,
    notification_type: str = "general",
    metadata_json: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    role_name = user.role.name if user.role else "resident"
    if role_name not in {"property_admin", "super_admin"}:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    item = Notification(
        user_id=target_user_id,
        notification_type=notification_type,
        title=title,
        body=body,
        metadata_json=metadata_json,
        channel="push",
        status="queued",
        is_read=False,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    push = send_push_notification(title, body)
    return {
        "id": str(item.id),
        "status": item.status,
        "push": push,
    }


@router.put("/{notification_id}/read")
async def mark_notification_read(notification_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.query(Notification).filter(Notification.id == notification_id, Notification.user_id == str(user.id)).first()
    if not item:
        raise HTTPException(status_code=404, detail="Notification not found")

    if not item.is_read:
        item.is_read = True
        item.read_at = datetime.utcnow()
        db.commit()

    unread = db.query(Notification).filter(Notification.user_id == str(user.id), Notification.is_read.is_(False)).count()
    await emit_event("notification.unread_count", {"user_id": str(user.id), "unread": unread})
    return {"message": "Notification marked as read", "unread": unread}


@router.put("/mark-all-read")
async def mark_all_notifications_read(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    (
        db.query(Notification)
        .filter(Notification.user_id == str(user.id), Notification.is_read.is_(False))
        .update({"is_read": True, "read_at": datetime.utcnow()}, synchronize_session=False)
    )
    db.commit()
    await emit_event("notification.unread_count", {"user_id": str(user.id), "unread": 0})
    return {"message": "All notifications marked as read", "unread": 0}


@router.delete("/{notification_id}")
async def delete_notification(notification_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.query(Notification).filter(Notification.id == notification_id, Notification.user_id == str(user.id)).first()
    if not item:
        raise HTTPException(status_code=404, detail="Notification not found")

    db.delete(item)
    db.commit()

    unread = db.query(Notification).filter(Notification.user_id == str(user.id), Notification.is_read.is_(False)).count()
    await emit_event("notification.unread_count", {"user_id": str(user.id), "unread": unread})
    return {"message": "Notification deleted", "unread": unread}


@router.delete("")
async def clear_all_notifications(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    deleted = (
        db.query(Notification)
        .filter(Notification.user_id == str(user.id))
        .delete(synchronize_session=False)
    )
    db.commit()

    await emit_event("notification.unread_count", {"user_id": str(user.id), "unread": 0})
    return {"message": "All notifications cleared", "deleted": deleted, "unread": 0}


@router.post("/test")
def test_notification(title: str, body: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = queue_notification(db, str(user.id), title, body)
    push = send_push_notification(title, body)
    return {"notification": {"id": str(item.id), "status": item.status}, "push": push}
