"""add paid_at to payments

Revision ID: 20260527_04
Revises: 20260526_03
Create Date: 2026-05-27
"""

from alembic import op
import sqlalchemy as sa


revision = "20260527_04"
down_revision = "20260526_03"
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

    if _table_exists(inspector, "payments") and not _column_exists(inspector, "payments", "paid_at"):
        op.add_column("payments", sa.Column("paid_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "payments") and _column_exists(inspector, "payments", "paid_at"):
        op.drop_column("payments", "paid_at")
