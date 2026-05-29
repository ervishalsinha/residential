"""add multi-image fields for notices and complaints

Revision ID: 20260528_09
Revises: 20260528_08
Create Date: 2026-05-28
"""

from alembic import op
import sqlalchemy as sa


revision = "20260528_09"
down_revision = "20260528_08"
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

    if _table_exists(inspector, "notices") and not _column_exists(inspector, "notices", "image_urls_json"):
        op.add_column("notices", sa.Column("image_urls_json", sa.Text(), nullable=True))

    if _table_exists(inspector, "complaints") and not _column_exists(inspector, "complaints", "image_urls_json"):
        op.add_column("complaints", sa.Column("image_urls_json", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "complaints") and _column_exists(inspector, "complaints", "image_urls_json"):
        op.drop_column("complaints", "image_urls_json")

    if _table_exists(inspector, "notices") and _column_exists(inspector, "notices", "image_urls_json"):
        op.drop_column("notices", "image_urls_json")
