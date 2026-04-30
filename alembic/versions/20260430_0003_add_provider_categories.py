"""add provider categories

Revision ID: 20260430_0003
Revises: 20260430_0002
Create Date: 2026-04-30 15:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260430_0003"
down_revision: Union[str, None] = "20260430_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "provider_categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider_profile_id", sa.Integer(), nullable=False),
        sa.Column("category_slug", sa.String(length=80), nullable=False),
        sa.ForeignKeyConstraint(
            ["provider_profile_id"],
            ["provider_profiles.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider_profile_id",
            "category_slug",
            name="uq_provider_categories_profile_slug",
        ),
    )
    op.create_index(
        op.f("ix_provider_categories_category_slug"),
        "provider_categories",
        ["category_slug"],
        unique=False,
    )
    op.create_index(
        op.f("ix_provider_categories_id"),
        "provider_categories",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_provider_categories_provider_profile_id"),
        "provider_categories",
        ["provider_profile_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_provider_categories_provider_profile_id"),
        table_name="provider_categories",
    )
    op.drop_index(
        op.f("ix_provider_categories_id"),
        table_name="provider_categories",
    )
    op.drop_index(
        op.f("ix_provider_categories_category_slug"),
        table_name="provider_categories",
    )
    op.drop_table("provider_categories")
