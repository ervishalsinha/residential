import random
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password, verify_password
from app.models import OTPCode


def generate_otp() -> str:
    settings = get_settings()
    min_value = 10 ** (settings.otp_length - 1)
    max_value = (10 ** settings.otp_length) - 1
    return str(random.randint(min_value, max_value))


def create_otp(db: Session, mobile_number: str) -> str:
    settings = get_settings()
    raw_otp = generate_otp()
    record = OTPCode(
        mobile_number=mobile_number,
        code_hash=hash_password(raw_otp),
        expires_at=datetime.utcnow() + timedelta(minutes=settings.otp_expire_minutes),
        is_used=False,
    )
    db.add(record)
    db.commit()
    return raw_otp


def validate_otp(db: Session, mobile_number: str, otp: str) -> bool:
    record = (
        db.query(OTPCode)
        .filter(OTPCode.mobile_number == mobile_number, OTPCode.is_used.is_(False))
        .order_by(OTPCode.created_at.desc())
        .first()
    )
    if not record:
        return False
    if record.expires_at < datetime.utcnow():
        return False
    if not verify_password(otp, record.code_hash):
        return False
    record.is_used = True
    db.commit()
    return True
