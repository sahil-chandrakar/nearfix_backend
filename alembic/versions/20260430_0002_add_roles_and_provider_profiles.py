"""add roles and provider profiles

Revision ID: 20260430_0002
Revises: 20260430_0001
Create Date: 2026-04-30 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260430_0002"
down_revision: Union[str, None] = "20260430_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("phone", sa.String(length=20), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "role",
            sa.String(length=32),
            server_default="customer",
            nullable=False,
        ),
    )
    op.alter_column(
        "users",
        "email",
        existing_type=sa.String(length=255),
        nullable=True,
    )
    op.create_index(op.f("ix_users_phone"), "users", ["phone"], unique=True)

    op.create_table(
        "provider_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("shop_company_name", sa.String(length=255), nullable=False),
        sa.Column("owner_name", sa.String(length=255), nullable=False),
        sa.Column("whatsapp_mobile_number", sa.String(length=20), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("aadhaar_front_path", sa.String(length=500), nullable=False),
        sa.Column("aadhaar_back_path", sa.String(length=500), nullable=False),
        sa.Column("payment_bill_path", sa.String(length=500), nullable=False),
        sa.Column("electricity_bill_path", sa.String(length=500), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column(
            "verification_status",
            sa.String(length=32),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_provider_profiles_id"),
        "provider_profiles",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_provider_profiles_user_id"),
        "provider_profiles",
        ["user_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_provider_profiles_verification_status"),
        "provider_profiles",
        ["verification_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_provider_profiles_verification_status"),
        table_name="provider_profiles",
    )
    op.drop_index(op.f("ix_provider_profiles_user_id"), table_name="provider_profiles")
    op.drop_index(op.f("ix_provider_profiles_id"), table_name="provider_profiles")
    op.drop_table("provider_profiles")

    op.drop_index(op.f("ix_users_phone"), table_name="users")
    op.alter_column(
        "users",
        "email",
        existing_type=sa.String(length=255),
        nullable=False,
    )
    op.drop_column("users", "role")
    op.drop_column("users", "phone")
