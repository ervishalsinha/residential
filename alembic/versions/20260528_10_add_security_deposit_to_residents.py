"""add security deposit to residents

Revision ID: 20260528_10
Revises: 20260528_09
Create Date: 2026-05-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260528_10"
down_revision = "20260528_09"
branch_labels = None
depends_on = None


def _column_exists(inspector, table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if not _column_exists(inspector, "residents", "security_deposit"):
        op.add_column("residents", sa.Column("security_deposit", sa.Numeric(10, 2), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if _column_exists(inspector, "residents", "security_deposit"):
        op.drop_column("residents", "security_deposit")
