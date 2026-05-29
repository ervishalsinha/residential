"""add resident extra charge fields

Revision ID: 20260527_06
Revises: 20260527_05
Create Date: 2026-05-27
"""

from alembic import op
import sqlalchemy as sa


revision = "20260527_06"
down_revision = "20260527_05"
branch_labels = None
depends_on = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _column_exists(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    return column_name in {col["name"] for col in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    extra_columns = [
        "electricity_bill",
        "maintenance_bill",
        "parking_charges",
        "wifi_charges",
        "cleaning_bill",
        "water_bill",
    ]

    for column_name in extra_columns:
        if _table_exists(inspector, "residents") and not _column_exists(inspector, "residents", column_name):
            op.add_column("residents", sa.Column(column_name, sa.Numeric(10, 2), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    extra_columns = [
        "water_bill",
        "cleaning_bill",
        "wifi_charges",
        "parking_charges",
        "maintenance_bill",
        "electricity_bill",
    ]

    for column_name in extra_columns:
        if _table_exists(inspector, "residents") and _column_exists(inspector, "residents", column_name):
            op.drop_column("residents", column_name)
