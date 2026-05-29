"""add property ownership mapping

Revision ID: 20260528_07
Revises: 20260527_06
Create Date: 2026-05-28
"""

from alembic import op
import sqlalchemy as sa


revision = "20260528_07"
down_revision = "20260527_06"
branch_labels = None
depends_on = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _column_exists(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    return column_name in {col["name"] for col in inspector.get_columns(table_name)}


def _index_exists(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    return index_name in {idx["name"] for idx in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "properties") and not _column_exists(inspector, "properties", "owner_user_id"):
        op.add_column("properties", sa.Column("owner_user_id", sa.String(length=36), nullable=True))
        op.create_foreign_key(
            "fk_properties_owner_user_id_users",
            "properties",
            "users",
            ["owner_user_id"],
            ["id"],
        )

    if _table_exists(inspector, "properties") and not _index_exists(inspector, "properties", "ix_properties_owner_user_id"):
        op.create_index("ix_properties_owner_user_id", "properties", ["owner_user_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "properties") and _index_exists(inspector, "properties", "ix_properties_owner_user_id"):
        op.drop_index("ix_properties_owner_user_id", table_name="properties")

    if _table_exists(inspector, "properties") and _column_exists(inspector, "properties", "owner_user_id"):
        op.drop_constraint("fk_properties_owner_user_id_users", "properties", type_="foreignkey")
        op.drop_column("properties", "owner_user_id")
