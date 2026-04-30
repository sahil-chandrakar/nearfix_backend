"""add bookings and provider document requests

Revision ID: 20260430_0005
Revises: 20260430_0004
Create Date: 2026-04-30 18:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260430_0005"
down_revision: Union[str, None] = "20260430_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bookings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("provider_profile_id", sa.Integer(), nullable=False),
        sa.Column("category_slug", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("customer_latitude", sa.Float(), nullable=True),
        sa.Column("customer_longitude", sa.Float(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("declined_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["customer_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["provider_profile_id"],
            ["provider_profiles.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_bookings_id"), "bookings", ["id"], unique=False)
    op.create_index(
        op.f("ix_bookings_customer_id"),
        "bookings",
        ["customer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bookings_provider_profile_id"),
        "bookings",
        ["provider_profile_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bookings_category_slug"),
        "bookings",
        ["category_slug"],
        unique=False,
    )
    op.create_index(op.f("ix_bookings_status"), "bookings", ["status"], unique=False)

    op.create_table(
        "provider_document_change_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider_profile_id", sa.Integer(), nullable=False),
        sa.Column("document_type", sa.String(length=64), nullable=False),
        sa.Column("document_path", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["provider_profile_id"],
            ["provider_profiles.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_provider_document_change_requests_id"),
        "provider_document_change_requests",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_provider_document_change_requests_provider_profile_id"),
        "provider_document_change_requests",
        ["provider_profile_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_provider_document_change_requests_document_type"),
        "provider_document_change_requests",
        ["document_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_provider_document_change_requests_status"),
        "provider_document_change_requests",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_provider_document_change_requests_status"),
        table_name="provider_document_change_requests",
    )
    op.drop_index(
        op.f("ix_provider_document_change_requests_document_type"),
        table_name="provider_document_change_requests",
    )
    op.drop_index(
        op.f("ix_provider_document_change_requests_provider_profile_id"),
        table_name="provider_document_change_requests",
    )
    op.drop_index(
        op.f("ix_provider_document_change_requests_id"),
        table_name="provider_document_change_requests",
    )
    op.drop_table("provider_document_change_requests")
    op.drop_index(op.f("ix_bookings_status"), table_name="bookings")
    op.drop_index(op.f("ix_bookings_category_slug"), table_name="bookings")
    op.drop_index(op.f("ix_bookings_provider_profile_id"), table_name="bookings")
    op.drop_index(op.f("ix_bookings_customer_id"), table_name="bookings")
    op.drop_index(op.f("ix_bookings_id"), table_name="bookings")
    op.drop_table("bookings")
