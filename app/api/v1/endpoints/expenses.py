from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import ensure_property_access, get_current_user, get_role_name, owned_property_ids
from app.db.session import get_db
from app.models import User
from app.repositories.domain import expenses_repo
from app.schemas.domain import OwnerExpenseCreate, OwnerExpenseUpdate

router = APIRouter()


@router.get("")
def list_expenses(
    property_id: UUID | None = Query(default=None),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = expenses_repo.list(db, skip=skip, limit=limit)
    role_name = get_role_name(user)

    if role_name == "property_admin":
        allowed_ids = owned_property_ids(db, user)
        items = [item for item in items if str(item.property_id) in allowed_ids]

    if property_id is None:
        return items
    ensure_property_access(db, user, str(property_id))
    property_id_str = str(property_id)
    return [item for item in items if item.property_id == property_id_str]


@router.post("")
def create_expense(payload: OwnerExpenseCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_property_access(db, user, str(payload.property_id), owner_only=True)
    data = payload.model_dump()
    data["created_by"] = user.id
    return expenses_repo.create(db, data)


@router.get("/{expense_id}")
def get_expense(expense_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = expenses_repo.get(db, expense_id)
    if not item:
        raise HTTPException(status_code=404, detail="Expense not found")
    ensure_property_access(db, user, str(item.property_id))
    return item


@router.put("/{expense_id}")
def update_expense(expense_id: UUID, payload: OwnerExpenseUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = expenses_repo.get(db, expense_id)
    if not item:
        raise HTTPException(status_code=404, detail="Expense not found")
    ensure_property_access(db, user, str(item.property_id), owner_only=True)
    return expenses_repo.update(db, item, payload.model_dump(exclude_none=True))


@router.delete("/{expense_id}")
def delete_expense(expense_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = expenses_repo.get(db, expense_id)
    if not item:
        raise HTTPException(status_code=404, detail="Expense not found")
    ensure_property_access(db, user, str(item.property_id), owner_only=True)
    expenses_repo.delete(db, item)
    return {"message": "Expense deleted"}
