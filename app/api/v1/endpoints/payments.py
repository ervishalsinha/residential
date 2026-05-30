import json
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import case, extract, func
from sqlalchemy.orm import Session

from app.core.deps import ensure_property_access, get_current_user, get_role_name, owned_property_ids, resident_property_ids
from app.core.socket_server import emit_event
from app.db.session import get_db
from app.models import Notice, Notification, OwnerExpense, Payment, Property, PropertyType, ResidentProfile, Unit, User
from app.repositories.domain import payments_repo
from app.schemas.domain import PaymentCreate, PaymentUpdate

router = APIRouter()


def _resident_charge_breakdown(resident: ResidentProfile) -> dict[str, float]:
    return {
        "rent": float(resident.monthly_rent or 0),
        "electricity_bill": float(resident.electricity_bill or 0),
        "maintenance_bill": float(resident.maintenance_bill or 0),
        "parking_charges": float(resident.parking_charges or 0),
        "wifi_charges": float(resident.wifi_charges or 0),
        "cleaning_bill": float(resident.cleaning_bill or 0),
        "water_bill": float(resident.water_bill or 0),
    }


def _resident_total_due(resident: ResidentProfile) -> float:
    return sum(_resident_charge_breakdown(resident).values())


def _charge_lines(resident: ResidentProfile) -> list[str]:
    labels = {
        "rent": "Rent",
        "electricity_bill": "Electricity",
        "maintenance_bill": "Maintenance",
        "parking_charges": "Parking",
        "wifi_charges": "WiFi",
        "cleaning_bill": "Cleaning",
        "water_bill": "Water",
    }
    return [f"{labels[key]} INR {value:,.2f}" for key, value in _resident_charge_breakdown(resident).items() if value > 0]


def _normalize_due_date(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        # Store naive UTC in DB to match timestamp columns without timezone.
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _days_in_month(year: int, month: int) -> int:
    return monthrange(year, month)[1]


def _safe_due_datetime(year: int, month: int, due_day: int) -> datetime:
    clamped_day = max(1, min(due_day, _days_in_month(year, month)))
    return datetime(year, month, clamped_day)


def _shift_month(year: int, month: int, delta: int = 1) -> tuple[int, int]:
    total = (year * 12 + (month - 1)) + delta
    return total // 12, (total % 12) + 1


def _is_advance_rent_stay_type(stay_type: str | None) -> bool:
    normalized = (stay_type or "").strip().lower()
    return normalized in {"pg", "hostel"}


def _first_charge_month(join_date: date, is_advance_rent: bool) -> date:
    del is_advance_rent
    return date(join_date.year, join_date.month, 1)


def _cycle_start_for_month(year: int, month: int, anchor_day: int) -> date:
    day = max(1, min(anchor_day, _days_in_month(year, month)))
    return date(year, month, day)


def _cycle_range_for_month(year: int, month: int, anchor_day: int) -> tuple[date, date]:
    start = _cycle_start_for_month(year, month, anchor_day)
    next_year, next_month = _shift_month(year, month, 1)
    next_start = _cycle_start_for_month(next_year, next_month, anchor_day)
    return start, next_start - timedelta(days=1)


def _due_date_for_cycle(year: int, month: int, due_day: int, is_advance_rent: bool) -> datetime:
    if is_advance_rent:
        return _safe_due_datetime(year, month, due_day)
    if month == 12:
        return _safe_due_datetime(year + 1, 1, due_day)
    return _safe_due_datetime(year, month + 1, due_day)


def _cycle_status(payment: Payment, now: datetime) -> str:
    if str(payment.status).lower() == "paid":
        return "paid"
    if payment.due_date and now < payment.due_date:
        return "upcoming"
    if payment.due_date and now > (payment.due_date + timedelta(days=5)):
        return "overdue"
    return "due"


def _resident_joining_date(resident: ResidentProfile) -> date:
    return resident.joining_date or resident.created_at.date()


def _resident_vacated_date(resident: ResidentProfile) -> date | None:
    if resident.vacated_on:
        return resident.vacated_on
    if resident.occupancy_status in {"vacated", "deleted"}:
        return resident.updated_at.date()
    return None


def _is_resident_visible_for_year(resident: ResidentProfile, year: int) -> bool:
    if resident.occupancy_status == "deleted":
        return False
    join_date = _resident_joining_date(resident)
    if join_date.year > year:
        return False
    vacated_on = _resident_vacated_date(resident)
    if vacated_on and vacated_on.year < year:
        return False
    return True


def _is_month_applicable(resident: ResidentProfile, year: int, month: int, is_advance_rent: bool) -> bool:
    join_date = _resident_joining_date(resident)
    month_start = date(year, month, 1)
    month_end = date(year, month, _days_in_month(year, month))
    first_charge_month = _first_charge_month(join_date, is_advance_rent)

    if month_end < first_charge_month:
        return False

    vacated_on = _resident_vacated_date(resident)
    if vacated_on and month_start > vacated_on:
        return False
    return True


def _ensure_monthly_rent_rows(db: Session, residents: list[ResidentProfile], year: int) -> list[Payment]:
    resident_user_ids = [str(item.user_id) for item in residents]
    property_ids = list({str(item.property_id) for item in residents})
    if not resident_user_ids or not property_ids:
        return []

    existing_rows = (
        db.query(Payment)
        .filter(
            Payment.payment_type == "rent",
            Payment.rent_year == year,
            Payment.resident_id.in_(resident_user_ids),
            Payment.property_id.in_(property_ids),
        )
        .all()
    )
    existing_by_key: dict[tuple[str, int, int], Payment] = {
        (str(item.resident_id), int(item.rent_year), int(item.rent_month)): item
        for item in existing_rows
        if item.rent_year is not None and item.rent_month is not None
    }

    property_type_rows = (
        db.query(Property.id, PropertyType.name)
        .join(PropertyType, Property.property_type_id == PropertyType.id)
        .filter(Property.id.in_(property_ids))
        .all()
        if property_ids
        else []
    )
    stay_type_by_property_id = {str(row[0]): row[1] for row in property_type_rows}

    created_any = False
    for resident in residents:
        total_due = _resident_total_due(resident)
        if total_due <= 0:
            continue

        join_date = _resident_joining_date(resident)
        due_day = join_date.day or resident.payment_due_day or 5
        is_advance_rent = _is_advance_rent_stay_type(stay_type_by_property_id.get(str(resident.property_id)))
        resident_user_id = str(resident.user_id)
        property_id = str(resident.property_id)
        for month in range(1, 13):
            if not _is_month_applicable(resident, year, month, is_advance_rent):
                continue
            key = (resident_user_id, year, month)
            if key in existing_by_key:
                continue

            item = Payment(
                resident_id=resident_user_id,
                property_id=property_id,
                amount=total_due,
                payment_type="rent",
                status="pending",
                due_date=_due_date_for_cycle(year, month, due_day, is_advance_rent),
                rent_year=year,
                rent_month=month,
                paid_at=None,
            )
            db.add(item)
            existing_by_key[key] = item
            created_any = True

    if created_any:
        db.commit()

    return (
        db.query(Payment)
        .filter(
            Payment.payment_type == "rent",
            Payment.rent_year == year,
            Payment.resident_id.in_(resident_user_ids),
            Payment.property_id.in_(property_ids),
        )
        .all()
    )


def _month_label(year: int, month: int) -> str:
    return date(year, month, 1).strftime("%b %Y")


def _property_owner_user_ids(db: Session, property_id: str) -> set[str]:
    notice_owner_ids = {
        str(item[0]) for item in db.query(Notice.published_by).filter(Notice.property_id == property_id).all()
    }
    expense_owner_ids = {
        str(item[0]) for item in db.query(OwnerExpense.created_by).filter(OwnerExpense.property_id == property_id).all()
    }
    return {value for value in notice_owner_ids.union(expense_owner_ids) if value}


def _mask_account_number(account_number: str | None) -> str:
    value = (account_number or "").strip()
    if len(value) <= 4:
        return value
    return f"{'*' * (len(value) - 4)}{value[-4:]}"


def _resolve_owner_payment_destination(
    db: Session,
    resident_profile: ResidentProfile,
    property_row: Property,
) -> tuple[str | None, str | None, str | None]:
    owner_user_id = str(resident_profile.owner_user_id) if resident_profile.owner_user_id else None
    if not owner_user_id and property_row.owner_user_id:
        owner_user_id = str(property_row.owner_user_id)
    if not owner_user_id:
        return None, None, None

    owner = db.query(User).filter(User.id == owner_user_id).first()
    if not owner:
        return None, None, None

    active_method = (owner.active_payment_method or "").strip().lower() or None
    if active_method == "upi" and owner.payment_upi_id:
        return active_method, owner.payment_upi_id, owner_user_id
    if active_method == "bank" and owner.payment_bank_account_number and owner.payment_bank_ifsc:
        destination = f"{owner.payment_bank_account_number}|{owner.payment_bank_ifsc}"
        return active_method, destination, owner_user_id
    return active_method, None, owner_user_id


def _owner_destination_display(method: str | None, destination: str | None) -> str | None:
    if not method or not destination:
        return None
    if method == "upi":
        return destination
    if method == "bank":
        parts = destination.split("|", 1)
        account_number = parts[0] if parts else ""
        ifsc = parts[1] if len(parts) > 1 else ""
        return f"A/C {_mask_account_number(account_number)} • IFSC {ifsc}"
    return None


@router.get("")
def list_payments(
    skip: int = 0,
    limit: int = 100,
    property_id: UUID | None = None,
    resident_id: UUID | None = None,
    year: int | None = None,
    month: int | None = None,
    last_days: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    role_name = get_role_name(user)
    query = db.query(Payment)

    if role_name == "resident":
        query = query.filter(Payment.resident_id == str(user.id))

    if property_id:
        ensure_property_access(db, user, str(property_id))
        query = query.filter(Payment.property_id == str(property_id))
    elif role_name == "property_admin":
        allowed_ids = owned_property_ids(db, user)
        if not allowed_ids:
            return []
        query = query.filter(Payment.property_id.in_(allowed_ids))
    elif role_name == "resident":
        allowed_ids = resident_property_ids(db, user)
        if not allowed_ids:
            return []
        query = query.filter(Payment.property_id.in_(allowed_ids))

    if resident_id:
        if role_name == "resident" and str(resident_id) != str(user.id):
            raise HTTPException(status_code=403, detail="Residents can only access their own payments")
        query = query.filter(Payment.resident_id == str(resident_id))

    base_date = func.coalesce(Payment.due_date, Payment.created_at)
    if last_days is not None and last_days > 0:
        query = query.filter(base_date >= datetime.utcnow() - timedelta(days=last_days))
    else:
        if year is not None:
            query = query.filter(extract("year", base_date) == year)
        if month is not None:
            query = query.filter(extract("month", base_date) == month)

    # Show recent transactions first for owner transaction view.
    due_date_missing = case((Payment.due_date.is_(None), 1), else_=0)
    return query.order_by(Payment.created_at.desc(), due_date_missing.asc(), Payment.due_date.desc()).offset(skip).limit(limit).all()


@router.get("/owner-rent-tracker")
def owner_rent_tracker(
    property_id: UUID,
    year: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_property_access(db, user, str(property_id), owner_only=True)
    property_type_name = (
        db.query(PropertyType.name)
        .join(Property, Property.property_type_id == PropertyType.id)
        .filter(Property.id == str(property_id))
        .scalar()
    )
    is_advance_rent = _is_advance_rent_stay_type(property_type_name)
    residents = db.query(ResidentProfile).filter(ResidentProfile.property_id == str(property_id)).all()
    visible_residents = [item for item in residents if _is_resident_visible_for_year(item, year)]
    if not visible_residents:
        return {"year": year, "months": list(range(1, 13)), "tenants": []}

    now = datetime.utcnow()
    years_to_sync: set[int] = set()
    for resident in visible_residents:
        join_year = _resident_joining_date(resident).year
        for target_year in range(join_year, max(now.year, year) + 1):
            years_to_sync.add(target_year)
    for target_year in sorted(years_to_sync):
        _ensure_monthly_rent_rows(db, visible_residents, target_year)

    resident_user_ids = [str(item.user_id) for item in visible_residents]
    rent_rows = (
        db.query(Payment)
        .filter(
            Payment.payment_type == "rent",
            Payment.property_id == str(property_id),
            Payment.resident_id.in_(resident_user_ids),
            Payment.rent_year.isnot(None),
            Payment.rent_month.isnot(None),
            Payment.rent_year <= max(now.year, year),
        )
        .all()
    )
    rent_by_resident: dict[str, list[Payment]] = {}
    for item in rent_rows:
        key = str(item.resident_id)
        rent_by_resident.setdefault(key, []).append(item)

    user_ids = [str(item.user_id) for item in visible_residents]
    users = db.query(User).filter(User.id.in_(user_ids)).all() if user_ids else []
    user_by_id = {str(item.id): item for item in users}

    unit_ids = [str(item.unit_id) for item in visible_residents if item.unit_id]
    units = db.query(Unit).filter(Unit.id.in_(unit_ids)).all() if unit_ids else []
    unit_by_id = {str(item.id): item for item in units}

    tenant_rows: list[dict] = []
    for resident in visible_residents:
        resident_user_id = str(resident.user_id)
        due_months: list[dict] = []
        billing_cycles: list[dict] = []
        actionable_cycles: list[dict] = []
        months_payload: list[dict] = []
        sorted_rows = sorted(
            [
                item
                for item in rent_by_resident.get(resident_user_id, [])
                if item.rent_year is not None
                and item.rent_month is not None
                and _is_month_applicable(resident, int(item.rent_year), int(item.rent_month), is_advance_rent)
            ],
            key=lambda row: (int(row.rent_year), int(row.rent_month)),
        )
        join_date = _resident_joining_date(resident)
        anchor_day = join_date.day

        for payment in sorted_rows:
            cycle_year = int(payment.rent_year)
            cycle_month = int(payment.rent_month)
            cycle_start, cycle_end = _cycle_range_for_month(cycle_year, cycle_month, anchor_day)
            status = _cycle_status(payment, now)
            cycle_payload = {
                "cycle_key": f"{cycle_year:04d}-{cycle_month:02d}",
                "cycle_label": f"{cycle_start.strftime('%d %b')} -> {cycle_end.strftime('%d %b')}",
                "cycle_start_date": cycle_start,
                "cycle_end_date": cycle_end,
                "due_date": payment.due_date,
                "status": status,
                "payment_id": str(payment.id),
                "amount": float(payment.amount) if payment.amount is not None else _resident_total_due(resident),
                "paid_at": payment.paid_at,
                "breakdown": _resident_charge_breakdown(resident),
            }

            include_in_selected_year = cycle_start.year == year
            include_carry_forward_unpaid = cycle_start.year < year and status in {"due", "overdue"}
            include_active_upcoming = status != "upcoming" or cycle_start <= now.date()
            if (include_in_selected_year or include_carry_forward_unpaid) and include_active_upcoming:
                billing_cycles.append(cycle_payload)

            if cycle_year == year:
                month_payload = {
                    "month": cycle_month,
                    "label": _month_label(cycle_year, cycle_month),
                    "status": status,
                    "payment_id": str(payment.id),
                    "amount": float(payment.amount) if payment.amount is not None else _resident_total_due(resident),
                    "due_date": payment.due_date,
                    "paid_at": payment.paid_at,
                    "breakdown": _resident_charge_breakdown(resident),
                }
                months_payload.append(month_payload)
                if status in {"due", "overdue"}:
                    due_months.append(month_payload)

            if status in {"due", "overdue"}:
                actionable_cycles.append(cycle_payload)

        month_by_index = {item["month"]: item for item in months_payload}
        normalized_months_payload: list[dict] = []
        for month in range(1, 13):
            existing = month_by_index.get(month)
            if existing:
                normalized_months_payload.append(existing)
            elif _is_month_applicable(resident, year, month, is_advance_rent):
                normalized_months_payload.append(
                    {
                        "month": month,
                        "label": _month_label(year, month),
                        "status": "upcoming",
                        "payment_id": None,
                        "amount": _resident_total_due(resident),
                        "due_date": _due_date_for_cycle(year, month, anchor_day, is_advance_rent),
                        "paid_at": None,
                        "breakdown": _resident_charge_breakdown(resident),
                    }
                )
            else:
                normalized_months_payload.append(
                    {
                        "month": month,
                        "label": _month_label(year, month),
                        "status": "vacated",
                        "payment_id": None,
                        "amount": None,
                        "due_date": None,
                        "paid_at": None,
                    }
                )

        user = user_by_id.get(resident_user_id)
        unit = unit_by_id.get(str(resident.unit_id)) if resident.unit_id else None
        tenant_rows.append(
            {
                "resident_id": str(resident.id),
                "resident_user_id": resident_user_id,
                "resident_name": user.full_name if user else resident_user_id,
                "mobile_number": user.mobile_number if user else None,
                "unit": unit.unit_number if unit else None,
                "joining_date": resident.joining_date,
                "vacated_on": resident.vacated_on,
                "monthly_rent": float(resident.monthly_rent) if resident.monthly_rent is not None else None,
                "months": normalized_months_payload,
                "due_months": due_months,
                "billing_cycles": billing_cycles,
                "actionable_cycles": actionable_cycles,
            }
        )

    return {"year": year, "months": list(range(1, 13)), "tenants": tenant_rows}


@router.get("/tenant-due-breakdown")
def tenant_due_breakdown(
    resident_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    role_name = get_role_name(current_user)
    if resident_id and role_name == "resident" and str(resident_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Residents can only access their own due breakdown")

    resident_user_id = str(resident_id) if resident_id else str(current_user.id)

    resident_profile = (
        db.query(ResidentProfile)
        .filter(ResidentProfile.user_id == resident_user_id)
        .order_by(ResidentProfile.updated_at.desc())
        .first()
    )
    if not resident_profile:
        raise HTTPException(status_code=404, detail="Resident profile not found")
    ensure_property_access(db, current_user, str(resident_profile.property_id))
    property_row = db.query(Property).filter(Property.id == str(resident_profile.property_id)).first()
    if not property_row:
        raise HTTPException(status_code=404, detail="Property not found")

    owner_method, owner_destination, _owner_user_id = _resolve_owner_payment_destination(db, resident_profile, property_row)
    owner_destination_display = _owner_destination_display(owner_method, owner_destination)
    property_type_name = (
        db.query(PropertyType.name)
        .join(Property, Property.property_type_id == PropertyType.id)
        .filter(Property.id == str(resident_profile.property_id))
        .scalar()
    )
    is_advance_rent = _is_advance_rent_stay_type(property_type_name)

    join_date = _resident_joining_date(resident_profile)
    current_year = datetime.utcnow().year
    years = list(range(join_date.year, current_year + 1))

    all_rows: list[Payment] = []
    for year in years:
        all_rows.extend(_ensure_monthly_rent_rows(db, [resident_profile], year))

    target_rows = [
        item
        for item in all_rows
        if str(item.resident_id) == resident_user_id
        and str(item.property_id) == str(resident_profile.property_id)
        and item.rent_year is not None
        and item.rent_month is not None
        and _is_month_applicable(resident_profile, int(item.rent_year), int(item.rent_month), is_advance_rent)
    ]

    target_rows.sort(key=lambda item: (int(item.rent_year), int(item.rent_month)))

    due_items: list[dict] = []
    paid_items: list[dict] = []
    pending_total = 0.0
    last_payment_date: datetime | None = None
    upcoming_due_date: datetime | None = None
    now = datetime.utcnow()

    for item in target_rows:
        amount = float(item.amount)
        month_payload = {
            "payment_id": str(item.id),
            "year": int(item.rent_year),
            "month": int(item.rent_month),
            "label": _month_label(int(item.rent_year), int(item.rent_month)),
            "amount": amount,
            "due_date": item.due_date,
            "paid_at": item.paid_at,
            "status": _cycle_status(item, now),
            "breakdown": _resident_charge_breakdown(resident_profile),
            "owner_active_payment_method": owner_method,
            "owner_payment_destination": owner_destination_display,
            "amount_editable": False,
        }

        if month_payload["status"] == "paid":
            paid_items.append(month_payload)
            if item.paid_at and (last_payment_date is None or item.paid_at > last_payment_date):
                last_payment_date = item.paid_at
            continue

        if month_payload["status"] == "upcoming":
            continue

        item_year = int(item.rent_year)
        item_month = int(item.rent_month)
        is_future_cycle = (item_year > now.year) or (item_year == now.year and item_month > now.month)
        if is_future_cycle:
            continue

        due_items.append(month_payload)
        pending_total += amount
        if item.due_date and (upcoming_due_date is None or item.due_date < upcoming_due_date):
            upcoming_due_date = item.due_date

    current_month_row = next(
        (
            item
            for item in target_rows
            if int(item.rent_year) == now.year and int(item.rent_month) == now.month
        ),
        None,
    )
    if not _is_month_applicable(resident_profile, now.year, now.month, is_advance_rent):
        current_month_status = "vacated"
    elif current_month_row:
        current_month_status = _cycle_status(current_month_row, now)
    else:
        current_month_status = "upcoming"

    return {
        "resident_id": str(resident_profile.id),
        "resident_user_id": resident_user_id,
        "property_id": str(resident_profile.property_id),
        "cards": {
            "current_month_rent_status": current_month_status,
            "total_pending_amount": pending_total,
            "last_payment_date": last_payment_date,
            "upcoming_due_date": upcoming_due_date,
        },
        "due_items": due_items,
        "paid_items": paid_items,
    }


@router.post("/{payment_id}/send-reminder")
async def send_payment_reminder(
    payment_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    payment = payments_repo.get(db, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    ensure_property_access(db, user, str(payment.property_id), owner_only=True)

    if str(payment.status).lower() == "paid":
        raise HTTPException(status_code=400, detail="Payment already marked as paid")

    label = "Rent due"
    if payment.rent_year and payment.rent_month:
        label = f"Rent due for {_month_label(int(payment.rent_year), int(payment.rent_month))}"

    resident = (
        db.query(ResidentProfile)
        .filter(ResidentProfile.user_id == str(payment.resident_id), ResidentProfile.property_id == str(payment.property_id))
        .order_by(ResidentProfile.updated_at.desc())
        .first()
    )

    due_label = payment.due_date.strftime("%Y-%m-%d") if payment.due_date else None
    breakdown = _resident_charge_breakdown(resident) if resident else {"rent": float(payment.amount)}
    line_items = _charge_lines(resident) if resident else [f"Rent INR {float(payment.amount):,.2f}"]
    body = (
        f"{label}: INR {float(payment.amount):,.2f}"
        + (f". Please pay by {due_label}." if due_label else ".")
        + (f" Breakdown: {', '.join(line_items)}." if line_items else "")
    )

    notification = Notification(
        user_id=str(payment.resident_id),
        notification_type="payment_reminder",
        title="Payment reminder",
        body=body,
        metadata_json=json.dumps({"payment_id": str(payment.id), "breakdown": breakdown}),
        channel="push",
        status="queued",
        is_read=False,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)

    await emit_event("notification.created", {"user_id": str(payment.resident_id), "type": "payment_reminder"})
    return {"message": "Payment reminder sent", "notification_id": str(notification.id)}


@router.post("")
def create_payment(
    payload: PaymentCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_property_access(db, user, str(payload.property_id), owner_only=True)
    data = payload.model_dump()
    data["due_date"] = _normalize_due_date(payload.due_date)
    if payload.rent_year is None and payload.due_date is not None:
        data["rent_year"] = payload.due_date.year
    if payload.rent_month is None and payload.due_date is not None:
        data["rent_month"] = payload.due_date.month
    item = payments_repo.create(db, data)
    background_tasks.add_task(
        emit_event,
        "payment.updated",
        {"id": str(item.id), "status": item.status.value if hasattr(item.status, "value") else str(item.status)},
    )
    return item


@router.get("/{payment_id}")
def get_payment(payment_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = payments_repo.get(db, payment_id)
    if not item:
        raise HTTPException(status_code=404, detail="Payment not found")
    ensure_property_access(db, user, str(item.property_id))
    if get_role_name(user) == "resident" and str(item.resident_id) != str(user.id):
        raise HTTPException(status_code=403, detail="Residents can only access their own payments")
    return item


@router.put("/{payment_id}")
def update_payment(
    payment_id: UUID,
    payload: PaymentUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = payments_repo.get(db, payment_id)
    if not item:
        raise HTTPException(status_code=404, detail="Payment not found")
    ensure_property_access(db, current_user, str(item.property_id))
    role_name = get_role_name(current_user)
    if role_name == "resident":
        if str(item.resident_id) != str(current_user.id):
            raise HTTPException(status_code=403, detail="Residents can only update their own payments")
        allowed_resident_fields = {"status", "gateway_channel"}
        requested_fields = set(payload.model_dump(exclude_none=True).keys())
        if not requested_fields:
            raise HTTPException(status_code=400, detail="No payment fields provided")
        if not requested_fields.issubset(allowed_resident_fields):
            raise HTTPException(status_code=403, detail="Residents can only mark payment status")
        if payload.status != "paid":
            raise HTTPException(status_code=403, detail="Residents can only mark due cycle as paid")
    elif role_name not in {"property_admin", "super_admin"}:
        raise HTTPException(status_code=403, detail="Role not permitted")

    data = payload.model_dump(exclude_none=True)
    if "due_date" in data:
        data["due_date"] = _normalize_due_date(payload.due_date)
    if data.get("rent_year") is None and data.get("due_date") is not None:
        data["rent_year"] = data["due_date"].year
    if data.get("rent_month") is None and data.get("due_date") is not None:
        data["rent_month"] = data["due_date"].month

    previous_status = str(item.status)

    if data.get("status") == "paid":
        resident_profile = (
            db.query(ResidentProfile)
            .filter(
                ResidentProfile.user_id == str(item.resident_id),
                ResidentProfile.property_id == str(item.property_id),
                ResidentProfile.occupancy_status != "deleted",
            )
            .order_by(ResidentProfile.updated_at.desc())
            .first()
        )
        property_row = db.query(Property).filter(Property.id == str(item.property_id)).first()
        if not resident_profile or not property_row:
            raise HTTPException(status_code=400, detail="Resident/property mapping not found for this payment")

        payout_method, payout_destination, _owner_user_id = _resolve_owner_payment_destination(db, resident_profile, property_row)
        if payout_method not in {"upi", "bank"} or not payout_destination:
            raise HTTPException(
                status_code=400,
                detail="Owner payment destination is not configured. Please ask owner to update Payment Settings.",
            )
        data["payout_method"] = payout_method
        data["payout_destination"] = payout_destination
        data["paid_at"] = datetime.utcnow()
    elif "status" in data and data.get("status") != "paid":
        data["paid_at"] = None

    updated = payments_repo.update(db, item, data)

    if data.get("status") == "paid" and previous_status != "paid":
        resident_notification = Notification(
            user_id=str(updated.resident_id),
            notification_type="payment_status_update",
            title="Payment marked as paid",
            body=f"Your {updated.payment_type} payment of INR {float(updated.amount):,.2f} is marked paid.",
            channel="push",
            status="queued",
            is_read=False,
        )
        db.add(resident_notification)

        owner_user_ids = _property_owner_user_ids(db, str(updated.property_id))
        if current_user and current_user.role and current_user.role.name in {"property_admin", "super_admin"}:
            owner_user_ids.add(str(current_user.id))

        if str(updated.resident_id) != str(current_user.id):
            resident_user = db.query(User).filter(User.id == str(updated.resident_id)).first()
        else:
            resident_user = current_user
        resident_name = resident_user.full_name if resident_user and resident_user.full_name else "Resident"

        for owner_user_id in owner_user_ids:
            if owner_user_id == str(updated.resident_id):
                continue
            db.add(
                Notification(
                    user_id=owner_user_id,
                    notification_type="resident_payment_received",
                    title="Payment received",
                    body=f"{resident_name} paid INR {float(updated.amount):,.2f} for {updated.payment_type}.",
                    channel="push",
                    status="queued",
                    is_read=False,
                )
            )
        db.commit()

    background_tasks.add_task(
        emit_event,
        "payment.updated",
        {"id": str(updated.id), "status": updated.status.value if hasattr(updated.status, "value") else str(updated.status)},
    )
    return updated


@router.delete("/{payment_id}")
def delete_payment(payment_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = payments_repo.get(db, payment_id)
    if not item:
        raise HTTPException(status_code=404, detail="Payment not found")
    ensure_property_access(db, user, str(item.property_id), owner_only=True)
    payments_repo.delete(db, item)
    return {"message": "Payment deleted"}
