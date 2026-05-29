import json
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import ensure_property_access, get_current_user, get_role_name, owned_property_ids
from app.core.security import hash_password
from app.core.socket_server import emit_event
from app.db.session import get_db
from app.models import AuthSession, Notification, Payment, Property, PropertyType, ResidentProfile, Role, Unit, User
from app.repositories.domain import residents_repo
from app.schemas.domain import ManagedTenantCreate, ResidentCreate, ResidentUpdate
from app.services.notification_service import send_push_notification
from app.services.whatsapp_service import build_tenant_registration_message, send_whatsapp_message

router = APIRouter()


def _charge_breakdown(item: ResidentProfile) -> dict[str, float]:
    return {
        "rent": float(item.monthly_rent or 0),
        "electricity_bill": float(item.electricity_bill or 0),
        "maintenance_bill": float(item.maintenance_bill or 0),
        "parking_charges": float(item.parking_charges or 0),
        "wifi_charges": float(item.wifi_charges or 0),
        "cleaning_bill": float(item.cleaning_bill or 0),
        "water_bill": float(item.water_bill or 0),
    }


def _total_monthly_due(item: ResidentProfile) -> float:
    return sum(_charge_breakdown(item).values())


def _charge_lines_for_message(item: ResidentProfile) -> list[str]:
    breakdown = _charge_breakdown(item)
    labels = {
        "rent": "Rent",
        "electricity_bill": "Electricity",
        "maintenance_bill": "Maintenance",
        "parking_charges": "Parking",
        "wifi_charges": "WiFi",
        "cleaning_bill": "Cleaning",
        "water_bill": "Water",
    }
    return [f"{labels[key]} INR {value:,.2f}" for key, value in breakdown.items() if value > 0]


def _normalize_joining_date(value: datetime | None):
    if value is None:
        return None
    return value.date()


def _normalize_vacated_on(value: datetime | None):
    if value is None:
        return None
    return value.date()


def _normalize_mobile_number(raw_mobile_number: str) -> str:
    return raw_mobile_number.strip().replace(" ", "")


def _send_tenant_registration_whatsapp(
    db: Session,
    tenant_user: User,
    owner_user: User,
    property_row: Property | None,
    resident_profile: ResidentProfile,
):
    from app.core.config import get_settings

    settings = get_settings()
    joining_date_label = resident_profile.joining_date.isoformat() if resident_profile.joining_date else "Not provided"
    pg_name = property_row.name if property_row else "Your PG"
    message = build_tenant_registration_message(
        tenant_name=tenant_user.full_name,
        pg_name=pg_name,
        owner_name=owner_user.full_name,
        joining_date=resident_profile.joining_date,
        android_link=settings.tenant_app_android_url,
        ios_link=settings.tenant_app_ios_url,
    )
    template_params = [
        tenant_user.full_name,
        pg_name,
        owner_user.full_name,
        joining_date_label,
        settings.tenant_app_android_url,
        settings.tenant_app_ios_url,
    ]
    wa_result = send_whatsapp_message(tenant_user.mobile_number, message, template_params=template_params)
    status = wa_result.get("status", "queued")

    notification = Notification(
        user_id=str(tenant_user.id),
        notification_type="tenant_registration_whatsapp",
        title="Tenant registration message",
        body="WhatsApp registration message processed for tenant onboarding.",
        metadata_json=json.dumps(
            {
                "mobile_number": tenant_user.mobile_number,
                "property_id": str(resident_profile.property_id),
                "property_name": property_row.name if property_row else None,
                "message": message,
                "delivery": wa_result,
            }
        ),
        channel="whatsapp",
        status=status,
        is_read=False,
    )
    db.add(notification)
    db.commit()
    return wa_result


def _validate_due_day(payment_due_day: int | None):
    if payment_due_day is None:
        return
    if payment_due_day < 1 or payment_due_day > 31:
        raise HTTPException(status_code=400, detail="payment_due_day must be between 1 and 31")


def _resident_payload(
    item: ResidentProfile,
    user_by_id: dict[str, User],
    unit_by_id: dict[str, Unit],
    stay_type_by_property_id: dict[str, str | None],
    payment_status_by_user_id: dict[str, str | None],
):
    user = user_by_id.get(str(item.user_id))
    unit = unit_by_id.get(str(item.unit_id)) if item.unit_id else None
    owner_mobile = item.owner_mobile
    if not owner_mobile and item.owner_user_id:
        owner = user_by_id.get(str(item.owner_user_id))
        owner_mobile = owner.mobile_number if owner else None
    return {
        "id": str(item.id),
        "user_id": str(item.user_id),
        "owner_user_id": str(item.owner_user_id) if item.owner_user_id else None,
        "owner_mobile": owner_mobile,
        "property_id": str(item.property_id),
        "unit_id": str(item.unit_id) if item.unit_id else None,
        "assigned_unit": unit.unit_number if unit else None,
        "stay_type": stay_type_by_property_id.get(str(item.property_id)),
        "occupancy_status": item.occupancy_status,
        "monthly_rent": float(item.monthly_rent) if item.monthly_rent is not None else None,
        "security_deposit": float(item.security_deposit) if item.security_deposit is not None else None,
        "electricity_bill": float(item.electricity_bill) if item.electricity_bill is not None else None,
        "maintenance_bill": float(item.maintenance_bill) if item.maintenance_bill is not None else None,
        "parking_charges": float(item.parking_charges) if item.parking_charges is not None else None,
        "wifi_charges": float(item.wifi_charges) if item.wifi_charges is not None else None,
        "cleaning_bill": float(item.cleaning_bill) if item.cleaning_bill is not None else None,
        "water_bill": float(item.water_bill) if item.water_bill is not None else None,
        "payment_due_day": item.payment_due_day,
        "joining_date": item.joining_date,
        "vacated_on": item.vacated_on,
        "aadhaar_image_url": item.aadhaar_image_url,
        "emergency_contact_name": item.emergency_contact_name,
        "emergency_contact_number": item.emergency_contact_number,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "full_name": user.full_name if user else None,
        "mobile_number": user.mobile_number if user else None,
        "email": user.email if user else None,
        "user_active": bool(user.is_active) if user else None,
        "payment_status": payment_status_by_user_id.get(str(item.user_id)),
    }


def _resident_payload_for_single(db: Session, item: ResidentProfile):
    user = db.query(User).filter(User.id == str(item.user_id)).first()
    unit = db.query(Unit).filter(Unit.id == str(item.unit_id)).first() if item.unit_id else None
    property_row = (
        db.query(Property.id, PropertyType.name)
        .join(PropertyType, Property.property_type_id == PropertyType.id)
        .filter(Property.id == str(item.property_id))
        .first()
    )
    latest_payment = (
        db.query(Payment)
        .filter(Payment.resident_id == str(item.user_id))
        .order_by(Payment.created_at.desc())
        .first()
    )
    return _resident_payload(
        item,
        user_by_id={str(user.id): user} if user else {},
        unit_by_id={str(unit.id): unit} if unit else {},
        stay_type_by_property_id={str(property_row[0]): property_row[1]} if property_row else {},
        payment_status_by_user_id={str(item.user_id): latest_payment.status if latest_payment else None},
    )


@router.get("")
def list_residents(
    skip: int = 0,
    limit: int = 100,
    property_id: UUID | None = None,
    include_deleted: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    role_name = get_role_name(user)
    query = db.query(ResidentProfile)
    if property_id:
        ensure_property_access(db, user, str(property_id))
        query = query.filter(ResidentProfile.property_id == str(property_id))
    elif role_name == "property_admin":
        allowed_ids = owned_property_ids(db, user)
        if not allowed_ids:
            return []
        query = query.filter(ResidentProfile.property_id.in_(allowed_ids))
    elif role_name == "resident":
        query = query.filter(ResidentProfile.user_id == str(user.id))
    if not include_deleted:
        query = query.filter(ResidentProfile.occupancy_status != "deleted")
    residents = query.offset(skip).limit(limit).all()

    property_ids = list({str(item.property_id) for item in residents})
    unit_ids = [str(item.unit_id) for item in residents if item.unit_id]
    user_ids = [str(item.user_id) for item in residents]
    owner_user_ids = [str(item.owner_user_id) for item in residents if item.owner_user_id]

    stay_type_by_property_id: dict[str, str | None] = {}
    if property_ids:
        rows = (
            db.query(Property.id, PropertyType.name)
            .join(PropertyType, Property.property_type_id == PropertyType.id)
            .filter(Property.id.in_(property_ids))
            .all()
        )
        stay_type_by_property_id = {str(row[0]): row[1] for row in rows}

    units = db.query(Unit).filter(Unit.id.in_(unit_ids)).all() if unit_ids else []
    unit_by_id = {str(item.id): item for item in units}

    users = db.query(User).filter(User.id.in_(list(set(user_ids + owner_user_ids)))).all() if (user_ids or owner_user_ids) else []
    user_by_id = {str(user.id): user for user in users}

    payments = (
        db.query(Payment)
        .filter(Payment.resident_id.in_(user_ids))
        .order_by(Payment.created_at.desc())
        .all()
        if user_ids
        else []
    )
    payment_status_by_user_id: dict[str, str | None] = {}
    for item in payments:
        resident_id = str(item.resident_id)
        if resident_id not in payment_status_by_user_id:
            payment_status_by_user_id[resident_id] = item.status

    return [
        _resident_payload(
            item,
            user_by_id=user_by_id,
            unit_by_id=unit_by_id,
            stay_type_by_property_id=stay_type_by_property_id,
            payment_status_by_user_id=payment_status_by_user_id,
        )
        for item in residents
    ]


@router.post("")
def create_resident(payload: ResidentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_property_access(db, current_user, str(payload.property_id), owner_only=True)
    resident_user = db.query(User).filter(User.id == str(payload.user_id)).first()
    if not resident_user:
        raise HTTPException(status_code=404, detail="User not found")

    _validate_due_day(payload.payment_due_day)

    existing = (
        db.query(ResidentProfile)
        .filter(ResidentProfile.user_id == str(payload.user_id), ResidentProfile.property_id == str(payload.property_id))
        .first()
    )
    data = payload.model_dump()
    data["owner_user_id"] = str(current_user.id)
    data["owner_mobile"] = current_user.mobile_number
    data["joining_date"] = _normalize_joining_date(payload.joining_date)
    data["vacated_on"] = _normalize_vacated_on(payload.vacated_on)

    if existing:
        for key, value in data.items():
            setattr(existing, key, str(value) if isinstance(value, UUID) else value)
        existing.occupancy_status = data.get("occupancy_status") or "active"
        resident_user.is_active = True
        db.commit()
        db.refresh(existing)
        return _resident_payload_for_single(db, existing)

    item = residents_repo.create(db, data)
    resident_user.is_active = True
    db.commit()
    return _resident_payload_for_single(db, item)


@router.post("/managed-tenant")
def create_managed_tenant(payload: ManagedTenantCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_property_access(db, user, str(payload.property_id), owner_only=True)
    _validate_due_day(payload.payment_due_day)
    property_row = db.query(Property).filter(Property.id == str(payload.property_id)).first()

    role = db.query(Role).filter(Role.name == "resident").first()
    if not role:
        role = Role(name="resident")
        db.add(role)
        db.flush()

    mobile_number = _normalize_mobile_number(payload.mobile_number)
    tenant_user = db.query(User).filter(User.mobile_number == mobile_number).first()

    if tenant_user and tenant_user.role and tenant_user.role.name not in {"resident"}:
        raise HTTPException(status_code=409, detail="Mobile number already belongs to a non-tenant account")

    if not tenant_user:
        tenant_user = User(
            full_name=payload.full_name.strip(),
            mobile_number=mobile_number,
            email=payload.email,
            password_hash=hash_password(payload.password),
            role_id=role.id,
            is_active=True,
        )
        db.add(tenant_user)
        db.flush()
    else:
        tenant_user.full_name = payload.full_name.strip()
        tenant_user.email = payload.email
        tenant_user.password_hash = hash_password(payload.password)
        tenant_user.role_id = role.id
        tenant_user.is_active = True

    profile_data = payload.model_dump(exclude={"full_name", "mobile_number", "password", "email"})
    profile_data["user_id"] = tenant_user.id
    profile_data["owner_user_id"] = str(user.id)
    profile_data["owner_mobile"] = user.mobile_number
    profile_data["joining_date"] = _normalize_joining_date(payload.joining_date)
    profile_data["vacated_on"] = _normalize_vacated_on(payload.vacated_on)

    existing_profile = db.query(ResidentProfile).filter(ResidentProfile.user_id == str(tenant_user.id)).first()
    if existing_profile and str(existing_profile.property_id) != str(payload.property_id) and existing_profile.occupancy_status != "deleted":
        raise HTTPException(status_code=409, detail="Tenant is already assigned to another property")

    if existing_profile:
        for key, value in profile_data.items():
            setattr(existing_profile, key, str(value) if isinstance(value, UUID) else value)
        existing_profile.occupancy_status = profile_data.get("occupancy_status") or "active"
        db.commit()
        db.refresh(existing_profile)
        whatsapp_result = {"status": "skipped", "reason": "not_attempted"}
        try:
            whatsapp_result = _send_tenant_registration_whatsapp(
                db=db,
                tenant_user=tenant_user,
                owner_user=user,
                property_row=property_row,
                resident_profile=existing_profile,
            )
        except Exception:
            whatsapp_result = {"status": "failed", "reason": "unexpected_error"}

        response_payload = _resident_payload_for_single(db, existing_profile)
        if whatsapp_result.get("status") != "sent":
            reason = (
                whatsapp_result.get("reason")
                or whatsapp_result.get("error")
                or whatsapp_result.get("provider_response")
                or "unknown_error"
            )
            response_payload["whatsapp_message"] = f"Whatsapp message not sent ({reason})"
        else:
            response_payload["whatsapp_message"] = "Whatsapp message sent"
        return response_payload

    created_profile = residents_repo.create(db, profile_data)
    db.commit()
    whatsapp_result = {"status": "skipped", "reason": "not_attempted"}
    try:
        whatsapp_result = _send_tenant_registration_whatsapp(
            db=db,
            tenant_user=tenant_user,
            owner_user=user,
            property_row=property_row,
            resident_profile=created_profile,
        )
    except Exception:
        whatsapp_result = {"status": "failed", "reason": "unexpected_error"}

    response_payload = _resident_payload_for_single(db, created_profile)
    if whatsapp_result.get("status") != "sent":
        reason = (
            whatsapp_result.get("reason")
            or whatsapp_result.get("error")
            or whatsapp_result.get("provider_response")
            or "unknown_error"
        )
        response_payload["whatsapp_message"] = f"Whatsapp message not sent ({reason})"
    else:
        response_payload["whatsapp_message"] = "Whatsapp message sent"
    return response_payload


@router.get("/{resident_id}")
def get_resident(resident_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = residents_repo.get(db, resident_id)
    if not item:
        raise HTTPException(status_code=404, detail="Resident not found")
    ensure_property_access(db, user, str(item.property_id))

    users = db.query(User).filter(User.id == str(item.user_id)).all()
    user_by_id = {str(user.id): user for user in users}
    units = db.query(Unit).filter(Unit.id == str(item.unit_id)).all() if item.unit_id else []
    unit_by_id = {str(unit.id): unit for unit in units}
    property_row = (
        db.query(Property.id, PropertyType.name)
        .join(PropertyType, Property.property_type_id == PropertyType.id)
        .filter(Property.id == str(item.property_id))
        .first()
    )
    stay_type_by_property_id = {str(property_row[0]): property_row[1]} if property_row else {}
    latest_payment = (
        db.query(Payment)
        .filter(Payment.resident_id == str(item.user_id))
        .order_by(Payment.created_at.desc())
        .first()
    )
    payment_status_by_user_id = {str(item.user_id): latest_payment.status if latest_payment else None}

    return _resident_payload(
        item,
        user_by_id=user_by_id,
        unit_by_id=unit_by_id,
        stay_type_by_property_id=stay_type_by_property_id,
        payment_status_by_user_id=payment_status_by_user_id,
    )


@router.put("/{resident_id}")
async def update_resident(resident_id: UUID, payload: ResidentUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = residents_repo.get(db, resident_id)
    if not item:
        raise HTTPException(status_code=404, detail="Resident not found")
    ensure_property_access(db, user, str(item.property_id), owner_only=True)

    data = payload.model_dump(exclude_none=True)
    if "payment_due_day" in data:
        _validate_due_day(data["payment_due_day"])
    if "joining_date" in data:
        data["joining_date"] = _normalize_joining_date(payload.joining_date)
    if "vacated_on" in data:
        data["vacated_on"] = _normalize_vacated_on(payload.vacated_on)

    previous_unit_id = str(item.unit_id) if item.unit_id else None
    updated = residents_repo.update(db, item, data)
    role_name = user.role.name if user.role else "resident"

    next_unit_id = str(updated.unit_id) if updated.unit_id else None
    if next_unit_id and next_unit_id != previous_unit_id:
        unit = db.query(Unit).filter(Unit.id == next_unit_id).first()
        title = "Allocation updated"
        body = f"Your unit has been transferred to {unit.unit_number if unit else 'a new unit'}."
        notification = Notification(
            user_id=str(updated.user_id),
            notification_type="room_transfer_update",
            title=title,
            body=body,
            metadata_json=json.dumps({"resident_id": str(updated.id), "unit_id": next_unit_id}),
            channel="push",
            status="queued",
            is_read=False,
        )
        db.add(notification)
        db.commit()
        await emit_event("notification.created", {"user_id": str(updated.user_id), "type": "room_transfer_update"})

    if data and role_name in {"property_admin", "super_admin"}:
        profile_notification = Notification(
            user_id=str(updated.user_id),
            notification_type="resident_profile_updated",
            title="Profile updated",
            body="Your resident details were updated by the owner.",
            channel="push",
            status="queued",
            is_read=False,
        )
        db.add(profile_notification)
        db.commit()
        await emit_event("notification.created", {"user_id": str(updated.user_id), "type": "resident_profile_updated"})

    charge_fields = {
        "monthly_rent",
        "electricity_bill",
        "maintenance_bill",
        "parking_charges",
        "wifi_charges",
        "cleaning_bill",
        "water_bill",
    }
    if any(field in data for field in charge_fields):
        total_due = _total_monthly_due(updated)
        if total_due > 0:
            pending_payment = (
                db.query(Payment)
                .filter(
                    Payment.resident_id == str(updated.user_id),
                    Payment.property_id == str(updated.property_id),
                    Payment.status == "pending",
                )
                .order_by(Payment.created_at.desc())
                .first()
            )
            if pending_payment:
                pending_payment.amount = total_due
                db.commit()
            else:
                db.add(
                    Payment(
                        resident_id=str(updated.user_id),
                        property_id=str(updated.property_id),
                        amount=total_due,
                        payment_type="rent",
                        status="pending",
                        due_date=datetime.utcnow(),
                        paid_at=None,
                    )
                )
                db.commit()

    return _resident_payload_for_single(db, updated)


@router.delete("/{resident_id}")
def delete_resident(resident_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = residents_repo.get(db, resident_id)
    if not item:
        raise HTTPException(status_code=404, detail="Resident not found")
    ensure_property_access(db, user, str(item.property_id), owner_only=True)

    user = db.query(User).filter(User.id == str(item.user_id)).first()
    if user:
        user.is_active = False

    item.occupancy_status = "deleted"
    if not item.vacated_on:
        item.vacated_on = datetime.utcnow().date()
    item.unit_id = None

    db.query(AuthSession).filter(AuthSession.user_id == str(item.user_id), AuthSession.is_active.is_(True)).update(
        {"is_active": False},
        synchronize_session=False,
    )
    db.commit()
    return {"message": "Tenant removed and user login blocked"}


@router.post("/{resident_id}/send-payment-reminder")
async def send_payment_reminder(
    resident_id: UUID,
    amount: float | None = None,
    due_date: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = residents_repo.get(db, resident_id)
    if not item:
        raise HTTPException(status_code=404, detail="Resident not found")
    ensure_property_access(db, user, str(item.property_id), owner_only=True)

    latest_pending = (
        db.query(Payment)
        .filter(Payment.resident_id == str(item.user_id), Payment.status == "pending")
        .order_by(Payment.created_at.desc())
        .first()
    )
    resolved_amount = amount
    if resolved_amount is None and latest_pending is not None:
        resolved_amount = float(latest_pending.amount)
    total_due = _total_monthly_due(item)
    if resolved_amount is None and total_due > 0:
        resolved_amount = total_due
    if resolved_amount is None:
        resolved_amount = 0.0

    due_label = due_date or (str(latest_pending.due_date)[:10] if latest_pending and latest_pending.due_date else None)
    title = "Payment reminder"
    line_items = _charge_lines_for_message(item)
    breakdown_text = f" Breakdown: {', '.join(line_items)}." if line_items else ""
    body = f"Your total due is INR {resolved_amount:,.2f}" + (f". Due by {due_label}." if due_label else ".") + breakdown_text

    notification = Notification(
        user_id=str(item.user_id),
        notification_type="payment_reminder",
        title=title,
        body=body,
        metadata_json=json.dumps({
            "resident_id": str(item.id),
            "amount": resolved_amount,
            "due_date": due_label,
            "breakdown": _charge_breakdown(item),
        }),
        channel="push",
        status="queued",
        is_read=False,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)

    push = send_push_notification(title, body)
    await emit_event("notification.created", {"user_id": str(item.user_id), "type": "payment_reminder"})
    return {"message": "Payment reminder sent", "notification_id": str(notification.id), "push": push}
