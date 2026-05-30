"""manual proof multiple images

Revision ID: 20260530_16
Revises: 20260530_15
Create Date: 2026-05-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260530_16"
down_revision = "20260530_15"
branch_labels = None
depends_on = None


def _table_exists(inspector, table_name: str) -> bool:
    return table_name in set(inspector.get_table_names())


def _column_exists(inspector, table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if _table_exists(inspector, "payments") and not _column_exists(inspector, "payments", "manual_payment_proof_urls_json"):
        op.add_column("payments", sa.Column("manual_payment_proof_urls_json", sa.String(length=5000), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if _table_exists(inspector, "payments") and _column_exists(inspector, "payments", "manual_payment_proof_urls_json"):
        op.drop_column("payments", "manual_payment_proof_urls_json")
