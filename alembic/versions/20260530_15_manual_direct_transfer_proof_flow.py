"""manual direct transfer proof flow fields

Revision ID: 20260530_15
Revises: 20260530_14
Create Date: 2026-05-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260530_15"
down_revision = "20260530_14"
branch_labels = None
depends_on = None


def _table_exists(inspector, table_name: str) -> bool:
    return table_name in set(inspector.get_table_names())


def _column_exists(inspector, table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if _table_exists(inspector, "payments"):
        if not _column_exists(inspector, "payments", "manual_payment_utr"):
            op.add_column("payments", sa.Column("manual_payment_utr", sa.String(length=80), nullable=True))
        if not _column_exists(inspector, "payments", "manual_payment_proof_url"):
            op.add_column("payments", sa.Column("manual_payment_proof_url", sa.String(length=500), nullable=True))
        if not _column_exists(inspector, "payments", "manual_payment_submitted_at"):
            op.add_column("payments", sa.Column("manual_payment_submitted_at", sa.DateTime(), nullable=True))
        if not _column_exists(inspector, "payments", "manual_review_status"):
            op.add_column("payments", sa.Column("manual_review_status", sa.String(length=30), nullable=True))
        if not _column_exists(inspector, "payments", "manual_review_note"):
            op.add_column("payments", sa.Column("manual_review_note", sa.String(length=500), nullable=True))
        if not _column_exists(inspector, "payments", "manual_reviewed_at"):
            op.add_column("payments", sa.Column("manual_reviewed_at", sa.DateTime(), nullable=True))
        if not _column_exists(inspector, "payments", "manual_reviewed_by"):
            op.add_column("payments", sa.Column("manual_reviewed_by", sa.String(length=36), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if _table_exists(inspector, "payments"):
        if _column_exists(inspector, "payments", "manual_reviewed_by"):
            op.drop_column("payments", "manual_reviewed_by")
        if _column_exists(inspector, "payments", "manual_reviewed_at"):
            op.drop_column("payments", "manual_reviewed_at")
        if _column_exists(inspector, "payments", "manual_review_note"):
            op.drop_column("payments", "manual_review_note")
        if _column_exists(inspector, "payments", "manual_review_status"):
            op.drop_column("payments", "manual_review_status")
        if _column_exists(inspector, "payments", "manual_payment_submitted_at"):
            op.drop_column("payments", "manual_payment_submitted_at")
        if _column_exists(inspector, "payments", "manual_payment_proof_url"):
            op.drop_column("payments", "manual_payment_proof_url")
        if _column_exists(inspector, "payments", "manual_payment_utr"):
            op.drop_column("payments", "manual_payment_utr")
