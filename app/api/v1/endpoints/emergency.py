from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.socket_server import emit_event
from app.db.session import get_db
from app.models import User
from app.repositories.domain import emergency_repo
from app.schemas.domain import EmergencyCreate, EmergencyUpdate

router = APIRouter()


@router.get("")
def list_alerts(skip: int = 0, limit: int = 50, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return emergency_repo.list(db, skip=skip, limit=limit)


@router.post("")
def create_alert(
    payload: EmergencyCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    item = emergency_repo.create(db, payload.model_dump())
    background_tasks.add_task(
        emit_event,
        "emergency.raised",
        {"id": str(item.id), "type": item.alert_type, "status": item.status},
    )
    return item


@router.get("/{alert_id}")
def get_alert(alert_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    item = emergency_repo.get(db, alert_id)
    if not item:
        raise HTTPException(status_code=404, detail="Alert not found")
    return item


@router.put("/{alert_id}")
def update_alert(alert_id: UUID, payload: EmergencyUpdate, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    item = emergency_repo.get(db, alert_id)
    if not item:
        raise HTTPException(status_code=404, detail="Alert not found")
    return emergency_repo.update(db, item, payload.model_dump(exclude_none=True))


@router.delete("/{alert_id}")
def delete_alert(alert_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    item = emergency_repo.get(db, alert_id)
    if not item:
        raise HTTPException(status_code=404, detail="Alert not found")
    emergency_repo.delete(db, item)
    return {"message": "Alert deleted"}
