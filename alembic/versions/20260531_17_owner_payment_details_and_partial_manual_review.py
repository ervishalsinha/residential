"""owner payment detail fields and partial manual review

Revision ID: 20260531_17
Revises: 20260530_16
Create Date: 2026-05-31
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260531_17"
down_revision = "20260530_16"
branch_labels = None
depends_on = None


def _table_exists(inspector, table_name: str) -> bool:
    return table_name in set(inspector.get_table_names())


def _column_exists(inspector, table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if _table_exists(inspector, "users"):
        if not _column_exists(inspector, "users", "payment_upi_account_holder_name"):
            op.add_column("users", sa.Column("payment_upi_account_holder_name", sa.String(length=150), nullable=True))
        if not _column_exists(inspector, "users", "payment_bank_account_holder_name"):
            op.add_column("users", sa.Column("payment_bank_account_holder_name", sa.String(length=150), nullable=True))
        if not _column_exists(inspector, "users", "payment_bank_name"):
            op.add_column("users", sa.Column("payment_bank_name", sa.String(length=150), nullable=True))

    inspector = inspect(bind)
    if _table_exists(inspector, "payments") and not _column_exists(inspector, "payments", "manual_partial_amount"):
        op.add_column("payments", sa.Column("manual_partial_amount", sa.Numeric(10, 2), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if _table_exists(inspector, "payments") and _column_exists(inspector, "payments", "manual_partial_amount"):
        op.drop_column("payments", "manual_partial_amount")

    inspector = inspect(bind)
    if _table_exists(inspector, "users"):
        if _column_exists(inspector, "users", "payment_bank_name"):
            op.drop_column("users", "payment_bank_name")
        if _column_exists(inspector, "users", "payment_bank_account_holder_name"):
            op.drop_column("users", "payment_bank_account_holder_name")
        if _column_exists(inspector, "users", "payment_upi_account_holder_name"):
            op.drop_column("users", "payment_upi_account_holder_name")
