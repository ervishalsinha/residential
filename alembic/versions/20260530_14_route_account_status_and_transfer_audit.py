"""route account status and transfer audit fields

Revision ID: 20260530_14
Revises: 20260530_13
Create Date: 2026-05-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260530_14"
down_revision = "20260530_13"
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
        if not _column_exists(inspector, "users", "razorpay_linked_account_status"):
            op.add_column("users", sa.Column("razorpay_linked_account_status", sa.String(length=30), nullable=True))

    inspector = inspect(bind)
    if _table_exists(inspector, "payments"):
        if not _column_exists(inspector, "payments", "razorpay_order_id"):
            op.add_column("payments", sa.Column("razorpay_order_id", sa.String(length=64), nullable=True))
        if not _column_exists(inspector, "payments", "razorpay_payment_id"):
            op.add_column("payments", sa.Column("razorpay_payment_id", sa.String(length=64), nullable=True))
        if not _column_exists(inspector, "payments", "razorpay_transfer_id"):
            op.add_column("payments", sa.Column("razorpay_transfer_id", sa.String(length=64), nullable=True))
        if not _column_exists(inspector, "payments", "razorpay_transfer_status"):
            op.add_column("payments", sa.Column("razorpay_transfer_status", sa.String(length=30), nullable=True))
        if not _column_exists(inspector, "payments", "transfer_updated_at"):
            op.add_column("payments", sa.Column("transfer_updated_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if _table_exists(inspector, "payments"):
        if _column_exists(inspector, "payments", "transfer_updated_at"):
            op.drop_column("payments", "transfer_updated_at")
        if _column_exists(inspector, "payments", "razorpay_transfer_status"):
            op.drop_column("payments", "razorpay_transfer_status")
        if _column_exists(inspector, "payments", "razorpay_transfer_id"):
            op.drop_column("payments", "razorpay_transfer_id")
        if _column_exists(inspector, "payments", "razorpay_payment_id"):
            op.drop_column("payments", "razorpay_payment_id")
        if _column_exists(inspector, "payments", "razorpay_order_id"):
            op.drop_column("payments", "razorpay_order_id")

    inspector = inspect(bind)
    if _table_exists(inspector, "users") and _column_exists(inspector, "users", "razorpay_linked_account_status"):
        op.drop_column("users", "razorpay_linked_account_status")
