"""add complaint visibility

Revision ID: 20260528_11
Revises: 20260528_10
Create Date: 2026-05-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260528_11"
down_revision = "20260528_10"
branch_labels = None
depends_on = None


def _column_exists(inspector, table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _index_exists(inspector, table_name: str, index_name: str) -> bool:
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not _column_exists(inspector, "complaints", "visibility"):
        op.add_column(
            "complaints",
            sa.Column("visibility", sa.String(length=30), nullable=False, server_default="owner_and_tenants"),
        )
        op.execute("UPDATE complaints SET visibility = 'owner_and_tenants' WHERE visibility IS NULL")
        op.alter_column("complaints", "visibility", server_default=None)

    inspector = inspect(bind)
    if not _index_exists(inspector, "complaints", "ix_complaints_visibility"):
        op.create_index("ix_complaints_visibility", "complaints", ["visibility"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if _index_exists(inspector, "complaints", "ix_complaints_visibility"):
        op.drop_index("ix_complaints_visibility", table_name="complaints")

    inspector = inspect(bind)
    if _column_exists(inspector, "complaints", "visibility"):
        op.drop_column("complaints", "visibility")
