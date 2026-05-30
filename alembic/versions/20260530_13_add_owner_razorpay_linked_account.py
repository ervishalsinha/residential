"""add owner razorpay linked account id

Revision ID: 20260530_13
Revises: 20260530_12
Create Date: 2026-05-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260530_13"
down_revision = "20260530_12"
branch_labels = None
depends_on = None


def _table_exists(inspector, table_name: str) -> bool:
    return table_name in set(inspector.get_table_names())


def _column_exists(inspector, table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if _table_exists(inspector, "users") and not _column_exists(inspector, "users", "razorpay_linked_account_id"):
        op.add_column("users", sa.Column("razorpay_linked_account_id", sa.String(length=40), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if _table_exists(inspector, "users") and _column_exists(inspector, "users", "razorpay_linked_account_id"):
        op.drop_column("users", "razorpay_linked_account_id")
