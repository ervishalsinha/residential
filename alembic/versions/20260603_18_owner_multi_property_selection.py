"""owner multi-property selection and primary flag

Revision ID: 20260603_18
Revises: 20260531_17
Create Date: 2026-06-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260603_18"
down_revision = "20260531_17"
branch_labels = None
depends_on = None


def _table_exists(inspector, table_name: str) -> bool:
    return table_name in set(inspector.get_table_names())


def _column_exists(inspector, table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _index_exists(inspector, table_name: str, index_name: str) -> bool:
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if _table_exists(inspector, "properties"):
        if not _column_exists(inspector, "properties", "property_type"):
            op.add_column("properties", sa.Column("property_type", sa.String(length=50), nullable=True))
        if not _column_exists(inspector, "properties", "is_primary"):
            op.add_column("properties", sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()))

    inspector = inspect(bind)
    if _table_exists(inspector, "properties") and not _index_exists(inspector, "properties", "ix_properties_property_type"):
        op.create_index("ix_properties_property_type", "properties", ["property_type"], unique=False)

    if _table_exists(inspector, "users") and not _column_exists(inspector, "users", "selected_property_id"):
        op.add_column("users", sa.Column("selected_property_id", sa.String(length=36), nullable=True))
        op.create_foreign_key(
            "fk_users_selected_property_id_properties",
            "users",
            "properties",
            ["selected_property_id"],
            ["id"],
        )

    inspector = inspect(bind)
    if _table_exists(inspector, "users") and not _index_exists(inspector, "users", "ix_users_selected_property_id"):
        op.create_index("ix_users_selected_property_id", "users", ["selected_property_id"], unique=False)

    inspector = inspect(bind)
    if _table_exists(inspector, "properties") and _table_exists(inspector, "property_types"):
        bind.execute(
            sa.text(
                """
                UPDATE properties p
                SET property_type = pt.name
                FROM property_types pt
                WHERE p.property_type_id = pt.id
                  AND (p.property_type IS NULL OR p.property_type = '')
                """
            )
        )

    inspector = inspect(bind)
    if _table_exists(inspector, "properties"):
        rows = bind.execute(
            sa.text(
                """
                SELECT id, owner_user_id
                FROM properties
                WHERE owner_user_id IS NOT NULL
                ORDER BY owner_user_id, created_at, id
                """
            )
        ).fetchall()
        primary_by_owner: dict[str, str] = {}
        for property_id, owner_user_id in rows:
            owner_key = str(owner_user_id)
            if owner_key not in primary_by_owner:
                primary_by_owner[owner_key] = str(property_id)

        for property_id in primary_by_owner.values():
            bind.execute(sa.text("UPDATE properties SET is_primary = true WHERE id = :property_id"), {"property_id": property_id})

    inspector = inspect(bind)
    if _table_exists(inspector, "users") and _table_exists(inspector, "properties"):
        bind.execute(
            sa.text(
                """
                UPDATE users u
                SET selected_property_id = p.id
                FROM properties p
                WHERE p.owner_user_id = u.id
                  AND p.is_primary = true
                  AND u.selected_property_id IS NULL
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if _table_exists(inspector, "users") and _index_exists(inspector, "users", "ix_users_selected_property_id"):
        op.drop_index("ix_users_selected_property_id", table_name="users")

    inspector = inspect(bind)
    if _table_exists(inspector, "users") and _column_exists(inspector, "users", "selected_property_id"):
        op.drop_constraint("fk_users_selected_property_id_properties", "users", type_="foreignkey")
        op.drop_column("users", "selected_property_id")

    inspector = inspect(bind)
    if _table_exists(inspector, "properties") and _index_exists(inspector, "properties", "ix_properties_property_type"):
        op.drop_index("ix_properties_property_type", table_name="properties")

    inspector = inspect(bind)
    if _table_exists(inspector, "properties") and _column_exists(inspector, "properties", "is_primary"):
        op.drop_column("properties", "is_primary")

    inspector = inspect(bind)
    if _table_exists(inspector, "properties") and _column_exists(inspector, "properties", "property_type"):
        op.drop_column("properties", "property_type")
