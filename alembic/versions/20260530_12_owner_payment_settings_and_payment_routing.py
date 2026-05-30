"""owner payment settings and payment routing fields

Revision ID: 20260530_12
Revises: 20260528_11
Create Date: 2026-05-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260530_12"
down_revision = "20260528_11"
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
        if not _column_exists(inspector, "users", "payment_upi_id"):
            op.add_column("users", sa.Column("payment_upi_id", sa.String(length=120), nullable=True))
        if not _column_exists(inspector, "users", "payment_bank_account_number"):
            op.add_column("users", sa.Column("payment_bank_account_number", sa.String(length=40), nullable=True))
        if not _column_exists(inspector, "users", "payment_bank_ifsc"):
            op.add_column("users", sa.Column("payment_bank_ifsc", sa.String(length=20), nullable=True))
        if not _column_exists(inspector, "users", "active_payment_method"):
            op.add_column("users", sa.Column("active_payment_method", sa.String(length=10), nullable=True))

    inspector = inspect(bind)
    if _table_exists(inspector, "payments"):
        if not _column_exists(inspector, "payments", "payout_method"):
            op.add_column("payments", sa.Column("payout_method", sa.String(length=10), nullable=True))
        if not _column_exists(inspector, "payments", "payout_destination"):
            op.add_column("payments", sa.Column("payout_destination", sa.String(length=255), nullable=True))
        if not _column_exists(inspector, "payments", "gateway_channel"):
            op.add_column("payments", sa.Column("gateway_channel", sa.String(length=30), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if _table_exists(inspector, "payments"):
        if _column_exists(inspector, "payments", "gateway_channel"):
            op.drop_column("payments", "gateway_channel")
        if _column_exists(inspector, "payments", "payout_destination"):
            op.drop_column("payments", "payout_destination")
        if _column_exists(inspector, "payments", "payout_method"):
            op.drop_column("payments", "payout_method")

    inspector = inspect(bind)
    if _table_exists(inspector, "users"):
        if _column_exists(inspector, "users", "active_payment_method"):
            op.drop_column("users", "active_payment_method")
        if _column_exists(inspector, "users", "payment_bank_ifsc"):
            op.drop_column("users", "payment_bank_ifsc")
        if _column_exists(inspector, "users", "payment_bank_account_number"):
            op.drop_column("users", "payment_bank_account_number")
        if _column_exists(inspector, "users", "payment_upi_id"):
            op.drop_column("users", "payment_upi_id")
