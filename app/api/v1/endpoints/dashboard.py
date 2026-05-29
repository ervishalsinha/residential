from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import ensure_property_access, get_current_user, get_role_name, owned_property_ids, resident_property_ids
from app.db.session import get_db
from app.models import Complaint, EmergencyAlert, Notice, Payment, User, Visitor

router = APIRouter()


def _month_floor(source: datetime) -> datetime:
    return source.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _shift_month(source: datetime, offset: int) -> datetime:
    month_index = (source.month - 1) + offset
    year = source.year + month_index // 12
    month = (month_index % 12) + 1
    return source.replace(year=year, month=month)


def _summary(db: Session, property_id: UUID | None = None):
    complaint_query = db.query(func.count(Complaint.id)).filter(Complaint.status.in_(["pending", "in_progress"]))
    visitor_query = db.query(func.count(Visitor.id)).filter(Visitor.status.in_(["requested", "approved"]))
    payment_query = db.query(func.count(Payment.id)).filter(Payment.status == "pending")
    emergency_query = db.query(func.count(EmergencyAlert.id)).filter(EmergencyAlert.status == "active")
    notice_query = db.query(func.count(Notice.id))

    if property_id:
        property_id_str = str(property_id)
        complaint_query = complaint_query.filter(Complaint.property_id == property_id_str)
        visitor_query = visitor_query.filter(Visitor.property_id == property_id_str)
        payment_query = payment_query.filter(Payment.property_id == property_id_str)
        emergency_query = emergency_query.filter(EmergencyAlert.property_id == property_id_str)
        notice_query = notice_query.filter(Notice.property_id == property_id_str)

    open_complaints = complaint_query.scalar() or 0
    pending_visitors = visitor_query.scalar() or 0
    due_payments = payment_query.scalar() or 0
    active_emergencies = emergency_query.scalar() or 0
    recent_notices = notice_query.scalar() or 0

    return {
        "open_complaints": open_complaints,
        "pending_visitors": pending_visitors,
        "due_payments": due_payments,
        "active_emergencies": active_emergencies,
        "recent_notices": recent_notices,
    }


@router.get("/public-summary")
def dashboard_public_summary(property_id: UUID | None = None, db: Session = Depends(get_db)):
    return _summary(db, property_id)


@router.get("/summary")
def dashboard_summary(property_id: UUID | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if property_id:
        ensure_property_access(db, user, str(property_id))
        return _summary(db, property_id)

    role_name = get_role_name(user)
    if role_name == "super_admin":
        return _summary(db, None)

    if role_name == "property_admin":
        owned_ids = owned_property_ids(db, user)
        if not owned_ids:
            return {"open_complaints": 0, "pending_visitors": 0, "due_payments": 0, "active_emergencies": 0, "recent_notices": 0}
        aggregate = {"open_complaints": 0, "pending_visitors": 0, "due_payments": 0, "active_emergencies": 0, "recent_notices": 0}
        for item in owned_ids:
            result = _summary(db, UUID(item))
            for key in aggregate:
                aggregate[key] += int(result[key])
        return aggregate

    resident_ids = resident_property_ids(db, user)
    if not resident_ids:
        return {"open_complaints": 0, "pending_visitors": 0, "due_payments": 0, "active_emergencies": 0, "recent_notices": 0}
    target_id = next(iter(resident_ids))
    return _summary(db, UUID(target_id))


@router.get("/public-complaint-trend")
def dashboard_public_complaint_trend(months: int = 6, db: Session = Depends(get_db)):
    bounded_months = max(1, min(months, 24))
    current_month = _month_floor(datetime.utcnow())
    first_month = _shift_month(current_month, -(bounded_months - 1))

    complaint_rows = (
        db.query(func.date_trunc("month", Complaint.created_at).label("month"), func.count(Complaint.id).label("count"))
        .filter(Complaint.created_at >= first_month)
        .group_by(func.date_trunc("month", Complaint.created_at))
        .all()
    )
    month_map = {
        item.month.strftime("%b %Y"): item.count
        for item in complaint_rows
        if item.month is not None
    }

    trend = []
    for offset in range(bounded_months):
        month = _shift_month(first_month, offset)
        label = month.strftime("%b %Y")
        trend.append({"month": label, "count": int(month_map.get(label, 0))})
    return {"months": bounded_months, "points": trend}
