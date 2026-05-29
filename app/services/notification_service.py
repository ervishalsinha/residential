from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Notification


def queue_notification(db: Session, user_id: str, title: str, body: str, channel: str = "push") -> Notification:
    item = Notification(user_id=user_id, title=title, body=body, channel=channel, status="queued")
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def send_push_notification(title: str, body: str, token: str | None = None) -> dict:
    settings = get_settings()
    if not settings.fcm_enabled:
        return {"status": "skipped", "reason": "fcm_disabled"}

    try:
        import firebase_admin
        from firebase_admin import credentials, messaging

        if not firebase_admin._apps:
            cred = credentials.Certificate(settings.firebase_credentials_path) if settings.firebase_credentials_path else credentials.ApplicationDefault()
            firebase_admin.initialize_app(cred)

        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            token=token,
        )
        result = messaging.send(message)
        return {"status": "sent", "message_id": result}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}
