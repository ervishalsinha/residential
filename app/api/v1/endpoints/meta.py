from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import PropertyType

router = APIRouter()


@router.get("/property-types")
def list_property_types(db: Session = Depends(get_db)):
    items = db.query(PropertyType).order_by(PropertyType.name.asc()).all()
    if items:
        return items

    defaults = ["apartment", "gated_society", "hostel", "pg", "standalone_building"]
    for name in defaults:
        db.add(PropertyType(name=name))
    db.commit()

    return db.query(PropertyType).order_by(PropertyType.name.asc()).all()
