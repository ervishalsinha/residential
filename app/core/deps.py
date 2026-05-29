from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models import AuthSession, Property, ResidentProfile, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = decode_token(token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account is inactive")

    if payload.get("session_id"):
        session = db.query(AuthSession).filter(AuthSession.id == payload["session_id"], AuthSession.is_active.is_(True)).first()
        if not session:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session revoked")

    return user


def require_roles(allowed_roles: set[str]):
    def role_checker(user: User = Depends(get_current_user)) -> User:
        role_name = user.role.name if user.role else ""
        if role_name not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
        return user

    return role_checker


def get_role_name(user: User) -> str:
    return user.role.name if user.role else ""


def owned_property_ids(db: Session, user: User) -> set[str]:
    return {str(item[0]) for item in db.query(Property.id).filter(Property.owner_user_id == str(user.id)).all()}


def resident_property_ids(db: Session, user: User) -> set[str]:
    rows = (
        db.query(ResidentProfile.property_id)
        .filter(ResidentProfile.user_id == str(user.id), ResidentProfile.occupancy_status != "deleted")
        .all()
    )
    return {str(item[0]) for item in rows}


def ensure_property_access(db: Session, user: User, property_id: str, owner_only: bool = False) -> None:
    role_name = get_role_name(user)
    if role_name == "super_admin":
        return

    if role_name == "property_admin":
        is_owner = db.query(Property.id).filter(Property.id == property_id, Property.owner_user_id == str(user.id)).first()
        if not is_owner:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Property access denied")
        return

    if role_name == "resident":
        if owner_only:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owners can perform this action")
        is_assigned = (
            db.query(ResidentProfile.id)
            .filter(
                ResidentProfile.property_id == property_id,
                ResidentProfile.user_id == str(user.id),
                ResidentProfile.occupancy_status != "deleted",
            )
            .first()
        )
        if not is_assigned:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Property access denied")
        return

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role not permitted")
