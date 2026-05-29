"""add owner expenses table and notice image column

Revision ID: 20260525_02
Revises: 20260524_01
Create Date: 2026-05-25
"""

from alembic import op
import sqlalchemy as sa


revision = "20260525_02"
down_revision = "20260524_01"
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

    if not _table_exists(inspector, "owner_expenses"):
        op.create_table(
            "owner_expenses",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("property_id", sa.String(length=36), sa.ForeignKey("properties.id"), nullable=False),
            sa.Column("amount", sa.Numeric(10, 2), nullable=False),
            sa.Column("spent_on", sa.String(length=120), nullable=False),
            sa.Column("note", sa.String(length=300), nullable=True),
            sa.Column("created_by", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_owner_expenses_property_id", "owner_expenses", ["property_id"], unique=False)
        op.create_index("ix_owner_expenses_created_by", "owner_expenses", ["created_by"], unique=False)

    if _table_exists(inspector, "notices") and not _column_exists(inspector, "notices", "image_url"):
        op.add_column("notices", sa.Column("image_url", sa.String(length=500), nullable=True))

    # Complaint comments are already used by API endpoints.
    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "complaint_comments"):
        op.create_table(
            "complaint_comments",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("complaint_id", sa.String(length=36), sa.ForeignKey("complaints.id"), nullable=False),
            sa.Column("author_user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("message", sa.String(length=500), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_complaint_comments_complaint_id", "complaint_comments", ["complaint_id"], unique=False)
        op.create_index("ix_complaint_comments_author_user_id", "complaint_comments", ["author_user_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "complaint_comments"):
        op.drop_index("ix_complaint_comments_author_user_id", table_name="complaint_comments")
        op.drop_index("ix_complaint_comments_complaint_id", table_name="complaint_comments")
        op.drop_table("complaint_comments")

    inspector = sa.inspect(bind)
    if _column_exists(inspector, "notices", "image_url"):
        op.drop_column("notices", "image_url")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "owner_expenses"):
        op.drop_index("ix_owner_expenses_created_by", table_name="owner_expenses")
        op.drop_index("ix_owner_expenses_property_id", table_name="owner_expenses")
        op.drop_table("owner_expenses")
