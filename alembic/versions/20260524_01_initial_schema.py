"""initial schema

Revision ID: 20260524_01
Revises:
Create Date: 2026-05-24
"""

from alembic import op
import sqlalchemy as sa


revision = "20260524_01"
down_revision = None
branch_labels = None
depends_on = None


def _uuid_col(name: str, pk: bool = False, nullable: bool = False):
    return sa.Column(name, sa.String(36), primary_key=pk, nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "roles",
        _uuid_col("id", pk=True),
        sa.Column("name", sa.String(length=50), nullable=False),
    )
    op.create_index("ix_roles_name", "roles", ["name"], unique=True)

    op.create_table(
        "users",
        _uuid_col("id", pk=True),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("mobile_number", sa.String(length=20), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("role_id", sa.String(36), sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_users_mobile_number", "users", ["mobile_number"], unique=True)

    op.create_table("property_types", _uuid_col("id", pk=True), sa.Column("name", sa.String(length=50), nullable=False))
    op.create_index("ix_property_types_name", "property_types", ["name"], unique=True)

    op.create_table(
        "properties",
        _uuid_col("id", pk=True),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("property_type_id", sa.String(36), sa.ForeignKey("property_types.id"), nullable=False),
        sa.Column("address_line1", sa.String(length=255), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("state", sa.String(length=100), nullable=False),
        sa.Column("pincode", sa.String(length=12), nullable=False),
        sa.Column("total_units", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "units",
        _uuid_col("id", pk=True),
        sa.Column("property_id", sa.String(36), sa.ForeignKey("properties.id"), nullable=False),
        sa.Column("unit_number", sa.String(length=30), nullable=False),
        sa.Column("floor", sa.Integer(), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=False, server_default="1"),
    )

    op.create_table(
        "residents",
        _uuid_col("id", pk=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("property_id", sa.String(36), sa.ForeignKey("properties.id"), nullable=False),
        sa.Column("unit_id", sa.String(36), sa.ForeignKey("units.id"), nullable=True),
        sa.Column("occupancy_status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("emergency_contact_name", sa.String(length=120), nullable=True),
        sa.Column("emergency_contact_number", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "complaints",
        _uuid_col("id", pk=True),
        sa.Column("resident_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("property_id", sa.String(36), sa.ForeignKey("properties.id"), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "visitors",
        _uuid_col("id", pk=True),
        sa.Column("property_id", sa.String(36), sa.ForeignKey("properties.id"), nullable=False),
        sa.Column("resident_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("mobile_number", sa.String(length=20), nullable=False),
        sa.Column("purpose", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="requested"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "payments",
        _uuid_col("id", pk=True),
        sa.Column("resident_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("property_id", sa.String(36), sa.ForeignKey("properties.id"), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("payment_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("due_date", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "staff",
        _uuid_col("id", pk=True),
        sa.Column("property_id", sa.String(36), sa.ForeignKey("properties.id"), nullable=False),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("mobile_number", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "notices",
        _uuid_col("id", pk=True),
        sa.Column("property_id", sa.String(36), sa.ForeignKey("properties.id"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("published_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "emergency_alerts",
        _uuid_col("id", pk=True),
        sa.Column("property_id", sa.String(36), sa.ForeignKey("properties.id"), nullable=False),
        sa.Column("raised_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("alert_type", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=300), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "otp_codes",
        _uuid_col("id", pk=True),
        sa.Column("mobile_number", sa.String(length=20), nullable=False),
        sa.Column("code_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("is_used", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "auth_sessions",
        _uuid_col("id", pk=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("refresh_token_jti", sa.String(length=120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("replaced_by_session_id", sa.String(36), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_auth_sessions_refresh_token_jti", "auth_sessions", ["refresh_token_jti"], unique=True)

    op.create_table(
        "notifications",
        _uuid_col("id", pk=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("body", sa.String(length=300), nullable=False),
        sa.Column("channel", sa.String(length=30), nullable=False, server_default="push"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="queued"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    for table in [
        "notifications",
        "auth_sessions",
        "otp_codes",
        "emergency_alerts",
        "notices",
        "staff",
        "payments",
        "visitors",
        "complaints",
        "residents",
        "units",
        "properties",
        "property_types",
        "users",
        "roles",
    ]:
        op.drop_table(table)
