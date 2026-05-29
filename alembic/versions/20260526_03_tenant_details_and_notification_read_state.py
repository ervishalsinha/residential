"""tenant details and notification read state

Revision ID: 20260526_03
Revises: 20260525_02
Create Date: 2026-05-26
"""

from alembic import op
import sqlalchemy as sa


revision = "20260526_03"
down_revision = "20260525_02"
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

    if _table_exists(inspector, "residents"):
        if not _column_exists(inspector, "residents", "monthly_rent"):
            op.add_column("residents", sa.Column("monthly_rent", sa.Numeric(10, 2), nullable=True))
        if not _column_exists(inspector, "residents", "payment_due_day"):
            op.add_column("residents", sa.Column("payment_due_day", sa.Integer(), nullable=True))
        if not _column_exists(inspector, "residents", "joining_date"):
            op.add_column("residents", sa.Column("joining_date", sa.Date(), nullable=True))
        if not _column_exists(inspector, "residents", "aadhaar_image_url"):
            op.add_column("residents", sa.Column("aadhaar_image_url", sa.String(length=500), nullable=True))

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "notifications"):
        if not _column_exists(inspector, "notifications", "notification_type"):
            op.add_column(
                "notifications",
                sa.Column("notification_type", sa.String(length=50), nullable=False, server_default="general"),
            )
        if not _column_exists(inspector, "notifications", "metadata_json"):
            op.add_column("notifications", sa.Column("metadata_json", sa.Text(), nullable=True))
        if not _column_exists(inspector, "notifications", "is_read"):
            op.add_column(
                "notifications",
                sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
            )
        if not _column_exists(inspector, "notifications", "read_at"):
            op.add_column("notifications", sa.Column("read_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "notifications"):
        if _column_exists(inspector, "notifications", "read_at"):
            op.drop_column("notifications", "read_at")
        if _column_exists(inspector, "notifications", "is_read"):
            op.drop_column("notifications", "is_read")
        if _column_exists(inspector, "notifications", "metadata_json"):
            op.drop_column("notifications", "metadata_json")
        if _column_exists(inspector, "notifications", "notification_type"):
            op.drop_column("notifications", "notification_type")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "residents"):
        if _column_exists(inspector, "residents", "aadhaar_image_url"):
            op.drop_column("residents", "aadhaar_image_url")
        if _column_exists(inspector, "residents", "joining_date"):
            op.drop_column("residents", "joining_date")
        if _column_exists(inspector, "residents", "payment_due_day"):
            op.drop_column("residents", "payment_due_day")
        if _column_exists(inspector, "residents", "monthly_rent"):
            op.drop_column("residents", "monthly_rent")
