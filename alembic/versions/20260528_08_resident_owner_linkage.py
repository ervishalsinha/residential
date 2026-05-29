"""add owner linkage columns to residents

Revision ID: 20260528_08
Revises: 20260528_07
Create Date: 2026-05-28
"""

from alembic import op
import sqlalchemy as sa


revision = "20260528_08"
down_revision = "20260528_07"
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

    if _table_exists(inspector, "residents") and not _column_exists(inspector, "residents", "owner_user_id"):
        op.add_column("residents", sa.Column("owner_user_id", sa.String(length=36), nullable=True))
        op.create_foreign_key(
            "fk_residents_owner_user_id_users",
            "residents",
            "users",
            ["owner_user_id"],
            ["id"],
        )

    if _table_exists(inspector, "residents") and not _column_exists(inspector, "residents", "owner_mobile"):
        op.add_column("residents", sa.Column("owner_mobile", sa.String(length=20), nullable=True))

    if _table_exists(inspector, "residents") and not _index_exists(inspector, "residents", "ix_residents_owner_user_id"):
        op.create_index("ix_residents_owner_user_id", "residents", ["owner_user_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "residents") and _index_exists(inspector, "residents", "ix_residents_owner_user_id"):
        op.drop_index("ix_residents_owner_user_id", table_name="residents")

    if _table_exists(inspector, "residents") and _column_exists(inspector, "residents", "owner_mobile"):
        op.drop_column("residents", "owner_mobile")

    if _table_exists(inspector, "residents") and _column_exists(inspector, "residents", "owner_user_id"):
        op.drop_constraint("fk_residents_owner_user_id_users", "residents", type_="foreignkey")
        op.drop_column("residents", "owner_user_id")
