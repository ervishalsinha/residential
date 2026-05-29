from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User

router = APIRouter()


@router.get("/tables")
def list_tables(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    inspector = inspect(db.bind)
    tables = sorted(inspector.get_table_names())
    rows: list[dict[str, int | str]] = []
    for table_name in tables:
        count = db.execute(text(f'SELECT COUNT(*) FROM "{table_name}"')).scalar_one()
        rows.append({"table": table_name, "rows": int(count)})
    return {"tables": rows}


@router.get("/tables/{table_name}")
def preview_table(
    table_name: str,
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    inspector = inspect(db.bind)
    available = set(inspector.get_table_names())
    if table_name not in available:
        raise HTTPException(status_code=404, detail="Table not found")

    columns = [column["name"] for column in inspector.get_columns(table_name)]
    result = db.execute(text(f'SELECT * FROM "{table_name}" LIMIT :limit'), {"limit": limit})
    data = [dict(row) for row in result.mappings().all()]
    return {"table": table_name, "columns": columns, "rows": data}
