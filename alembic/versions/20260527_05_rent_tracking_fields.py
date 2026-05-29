"""add rent tracking fields

Revision ID: 20260527_05
Revises: 20260527_04
Create Date: 2026-05-27
"""

from alembic import op
import sqlalchemy as sa


revision = "20260527_05"
down_revision = "20260527_04"
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
    return any(item.get("name") == index_name for item in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "payments") and not _column_exists(inspector, "payments", "rent_year"):
        op.add_column("payments", sa.Column("rent_year", sa.Integer(), nullable=True))

    if _table_exists(inspector, "payments") and not _column_exists(inspector, "payments", "rent_month"):
        op.add_column("payments", sa.Column("rent_month", sa.Integer(), nullable=True))

    if _table_exists(inspector, "payments") and not _index_exists(inspector, "payments", "ix_payments_rent_year"):
        op.create_index("ix_payments_rent_year", "payments", ["rent_year"], unique=False)

    if _table_exists(inspector, "payments") and not _index_exists(inspector, "payments", "ix_payments_rent_month"):
        op.create_index("ix_payments_rent_month", "payments", ["rent_month"], unique=False)

    if _table_exists(inspector, "residents") and not _column_exists(inspector, "residents", "vacated_on"):
        op.add_column("residents", sa.Column("vacated_on", sa.Date(), nullable=True))

    if _table_exists(inspector, "payments"):
        op.execute(
            sa.text(
                """
                UPDATE payments
                SET rent_year = EXTRACT(YEAR FROM due_date)::INT,
                    rent_month = EXTRACT(MONTH FROM due_date)::INT,
                    payment_type = CASE WHEN payment_type = 'maintenance' THEN 'rent' ELSE payment_type END
                WHERE due_date IS NOT NULL AND (rent_year IS NULL OR rent_month IS NULL)
                """
            )
        )

    if _table_exists(inspector, "residents"):
        op.execute(
            sa.text(
                """
                UPDATE residents
                SET vacated_on = DATE(updated_at)
                WHERE vacated_on IS NULL AND occupancy_status IN ('vacated', 'deleted')
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "payments") and _index_exists(inspector, "payments", "ix_payments_rent_month"):
        op.drop_index("ix_payments_rent_month", table_name="payments")

    if _table_exists(inspector, "payments") and _index_exists(inspector, "payments", "ix_payments_rent_year"):
        op.drop_index("ix_payments_rent_year", table_name="payments")

    if _table_exists(inspector, "payments") and _column_exists(inspector, "payments", "rent_month"):
        op.drop_column("payments", "rent_month")

    if _table_exists(inspector, "payments") and _column_exists(inspector, "payments", "rent_year"):
        op.drop_column("payments", "rent_year")

    if _table_exists(inspector, "residents") and _column_exists(inspector, "residents", "vacated_on"):
        op.drop_column("residents", "vacated_on")
