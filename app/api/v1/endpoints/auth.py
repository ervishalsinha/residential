import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_current_user
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.db.session import get_db
from app.models import AuthSession, Role, User
from app.schemas.auth import (
    AuthenticatedUser,
    ForgotPasswordRequest,
    LoginRequest,
    OTPRequest,
    OTPVerifyRequest,
    OwnerPaymentSettingsUpdate,
    RefreshTokenRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenPair,
)
from app.schemas.common import APIMessage
from app.services.otp_service import create_otp, validate_otp

router = APIRouter()


def _normalize_mobile_number(raw_mobile_number: str) -> str:
    return raw_mobile_number.strip().replace(" ", "")


def _normalize_role_name(raw_role_name: str | None) -> str:
    if not raw_role_name:
        return "resident"
    return raw_role_name.strip().lower()


def _normalize_account_number(raw_value: str | None) -> str | None:
    if raw_value is None:
        return None
    value = raw_value.strip().replace(" ", "")
    return value or None


def _normalize_ifsc(raw_value: str | None) -> str | None:
    if raw_value is None:
        return None
    value = raw_value.strip().upper().replace(" ", "")
    return value or None


def _normalize_upi(raw_value: str | None) -> str | None:
    if raw_value is None:
        return None
    value = raw_value.strip().lower()
    return value or None


def _owner_payment_settings_payload(user: User) -> dict:
    return {
        "payment_upi_id": user.payment_upi_id,
        "payment_bank_account_number": user.payment_bank_account_number,
        "payment_bank_ifsc": user.payment_bank_ifsc,
        "active_payment_method": user.active_payment_method,
    }


@router.post("/register", response_model=APIMessage)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> APIMessage:
    mobile_number = _normalize_mobile_number(payload.mobile_number)
    role_name = _normalize_role_name(payload.role)

    if role_name != "property_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owners can self-register")

    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        role = Role(name=role_name)
        db.add(role)
        db.commit()
        db.refresh(role)

    user = db.query(User).filter(User.mobile_number == mobile_number).first()
    if user:
        user_role_name = user.role.name if user.role else "resident"

        if not user.password_hash:
            user.full_name = payload.full_name
            user.email = payload.email
            user.password_hash = hash_password(payload.password)
            user.role_id = role.id
            user.is_active = True
            db.commit()
            return APIMessage(message=f"Password set for existing account {mobile_number} as {role_name}")

        return APIMessage(message="Mobile number already registered")

    user = User(
        full_name=payload.full_name,
        mobile_number=mobile_number,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role_id=role.id,
    )
    db.add(user)
    db.commit()
    return APIMessage(message=f"Account created for {mobile_number} as {role_name}")


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenPair:
    mobile_number = _normalize_mobile_number(payload.mobile_number)
    user = db.query(User).filter(User.mobile_number == mobile_number).first()

    if not user or not user.password_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    role_name = user.role.name if user.role else "resident"
    access = create_token(str(user.id), 60, {"role": role_name, "type": "access"})
    refresh = create_token(str(user.id), 1440, {"role": role_name, "type": "refresh"})
    return TokenPair(access_token=access, refresh_token=refresh, role=role_name)


@router.post("/request-otp", response_model=APIMessage)
def request_otp(payload: OTPRequest, db: Session = Depends(get_db)) -> APIMessage:
    mobile_number = _normalize_mobile_number(payload.mobile_number)
    otp = create_otp(db, mobile_number)
    return APIMessage(message=f"OTP generated for {mobile_number}. Demo OTP: {otp}")


@router.post("/verify-otp", response_model=TokenPair)
def verify_otp(payload: OTPVerifyRequest, db: Session = Depends(get_db)) -> TokenPair:
    mobile_number = _normalize_mobile_number(payload.mobile_number)
    if not validate_otp(db, mobile_number, payload.otp):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP")

    settings = get_settings()

    user = db.query(User).filter(User.mobile_number == mobile_number).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User account not found")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive")

    if payload.role:
        requested_role_name = _normalize_role_name(payload.role)
        user_role_name = user.role.name if user.role else "resident"
        if requested_role_name != user_role_name:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role mismatch for account")

    session = AuthSession(
        user_id=user.id,
        refresh_token_jti=str(uuid.uuid4()),
        expires_at=datetime.utcnow() + timedelta(minutes=settings.refresh_token_expire_minutes),
        is_active=True,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    role_name = user.role.name if user.role else "resident"
    access = create_token(str(user.id), settings.access_token_expire_minutes, {"role": role_name, "type": "access", "session_id": str(session.id)})
    refresh = create_token(str(user.id), settings.refresh_token_expire_minutes, {"role": role_name, "type": "refresh", "jti": session.refresh_token_jti, "session_id": str(session.id)})
    return TokenPair(access_token=access, refresh_token=refresh, role=role_name)


@router.post("/refresh", response_model=TokenPair)
def refresh_tokens(payload: RefreshTokenRequest, db: Session = Depends(get_db)) -> TokenPair:
    try:
        token_payload = decode_token(payload.refresh_token)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")
    if token_payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token type")

    session_id = token_payload.get("session_id")
    session = db.query(AuthSession).filter(AuthSession.id == session_id, AuthSession.is_active.is_(True)).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session not active")

    if session.refresh_token_jti != token_payload.get("jti"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token mismatch")

    settings = get_settings()
    new_session = AuthSession(
        user_id=session.user_id,
        refresh_token_jti=str(uuid.uuid4()),
        expires_at=datetime.utcnow() + timedelta(minutes=settings.refresh_token_expire_minutes),
        is_active=True,
    )
    db.add(new_session)
    db.flush()

    session.is_active = False
    session.revoked_at = datetime.utcnow()
    session.replaced_by_session_id = new_session.id
    db.commit()
    db.refresh(new_session)

    user = db.query(User).filter(User.id == session.user_id).first()
    role_name = user.role.name if user and user.role else "resident"
    access = create_token(str(session.user_id), settings.access_token_expire_minutes, {"role": role_name, "type": "access", "session_id": str(new_session.id)})
    refresh = create_token(str(session.user_id), settings.refresh_token_expire_minutes, {"role": role_name, "type": "refresh", "jti": new_session.refresh_token_jti, "session_id": str(new_session.id)})
    return TokenPair(access_token=access, refresh_token=refresh, role=role_name)


@router.post("/logout", response_model=APIMessage)
def logout(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> APIMessage:
    db.query(AuthSession).filter(AuthSession.user_id == user.id, AuthSession.is_active.is_(True)).update({"is_active": False, "revoked_at": datetime.utcnow()})
    db.commit()
    return APIMessage(message="Logged out and all active sessions revoked")


@router.get("/me", response_model=AuthenticatedUser)
def me(user: User = Depends(get_current_user)) -> AuthenticatedUser:
    role_name = user.role.name if user.role else "resident"
    return AuthenticatedUser(
        id=str(user.id),
        full_name=user.full_name,
        mobile_number=user.mobile_number,
        role=role_name,
        payment_upi_id=user.payment_upi_id,
        payment_bank_account_number=user.payment_bank_account_number,
        payment_bank_ifsc=user.payment_bank_ifsc,
        active_payment_method=user.active_payment_method,
    )


@router.get("/payment-settings")
def get_owner_payment_settings(user: User = Depends(get_current_user)):
    role_name = user.role.name if user.role else "resident"
    if role_name not in {"property_admin", "super_admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owners can access payment settings")
    return _owner_payment_settings_payload(user)


@router.put("/payment-settings")
def update_owner_payment_settings(payload: OwnerPaymentSettingsUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    role_name = user.role.name if user.role else "resident"
    if role_name not in {"property_admin", "super_admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owners can update payment settings")

    if payload.payment_upi_id is not None:
        user.payment_upi_id = _normalize_upi(payload.payment_upi_id)
    if payload.payment_bank_account_number is not None:
        user.payment_bank_account_number = _normalize_account_number(payload.payment_bank_account_number)
    if payload.payment_bank_ifsc is not None:
        user.payment_bank_ifsc = _normalize_ifsc(payload.payment_bank_ifsc)

    if payload.active_payment_method is not None:
        active_method = (payload.active_payment_method or "").strip().lower()
        if active_method not in {"upi", "bank"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="active_payment_method must be 'upi' or 'bank'")
        user.active_payment_method = active_method

    if user.active_payment_method == "upi" and not user.payment_upi_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="UPI ID is required when active_payment_method is 'upi'")

    if user.active_payment_method == "bank" and (not user.payment_bank_account_number or not user.payment_bank_ifsc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bank account number and IFSC are required when active_payment_method is 'bank'",
        )

    if user.active_payment_method is None:
        if user.payment_upi_id:
            user.active_payment_method = "upi"
        elif user.payment_bank_account_number and user.payment_bank_ifsc:
            user.active_payment_method = "bank"

    db.commit()
    db.refresh(user)
    return _owner_payment_settings_payload(user)


@router.post("/forgot-password/request", response_model=APIMessage)
def request_password_reset(payload: ForgotPasswordRequest, db: Session = Depends(get_db)) -> APIMessage:
    mobile_number = _normalize_mobile_number(payload.mobile_number)
    user = db.query(User).filter(User.mobile_number == mobile_number).first()

    if not user or not user.is_active:
        return APIMessage(message="If an active account exists for this mobile number, an OTP has been sent")

    otp = create_otp(db, mobile_number)
    return APIMessage(message=f"OTP generated for {mobile_number}. Demo OTP: {otp}")


@router.post("/forgot-password/reset", response_model=APIMessage)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> APIMessage:
    mobile_number = _normalize_mobile_number(payload.mobile_number)
    user = db.query(User).filter(User.mobile_number == mobile_number).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User account not found")

    if not validate_otp(db, mobile_number, payload.otp):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP")

    user.password_hash = hash_password(payload.new_password)
    db.query(AuthSession).filter(AuthSession.user_id == user.id, AuthSession.is_active.is_(True)).update(
        {"is_active": False, "revoked_at": datetime.utcnow()},
        synchronize_session=False,
    )
    db.commit()
    return APIMessage(message="Password updated successfully. Please login again")
