"""add customer brand services

Revision ID: 20260430_0008
Revises: 20260430_0007
Create Date: 2026-05-31 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260430_0008"
down_revision: str | None = "20260430_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CUSTOMER_BRANDS = (
    ("samsung-service", "Samsung Service (Mobile + AC/Fridge/TV)"),
    ("lg-whirlpool-ifb-service", "LG / Whirlpool / IFB Service (Home Appliances)"),
    ("maruti-suzuki-hyundai-car-service", "Maruti Suzuki & Hyundai Car Service"),
    ("hero-honda-bike-service", "Hero & Honda Bike Service"),
)


def upgrade() -> None:
    op.create_table(
        "customer_brands",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_customer_brands_id"), "customer_brands", ["id"], unique=False)
    op.create_index(op.f("ix_customer_brands_slug"), "customer_brands", ["slug"], unique=True)
    op.create_index(op.f("ix_customer_brands_is_active"), "customer_brands", ["is_active"], unique=False)
    op.create_index(op.f("ix_customer_brands_display_order"), "customer_brands", ["display_order"], unique=False)

    customer_brands = sa.table(
        "customer_brands",
        sa.column("slug", sa.String),
        sa.column("name", sa.String),
        sa.column("display_order", sa.Integer),
    )
    op.bulk_insert(
        customer_brands,
        [
            {"slug": slug, "name": name, "display_order": index}
            for index, (slug, name) in enumerate(CUSTOMER_BRANDS, start=1)
        ],
    )

    op.create_table(
        "customer_brand_services",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("brand_id", sa.Integer(), nullable=False),
        sa.Column("category_slug", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["customer_brands.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("brand_id", "category_slug", name="uq_customer_brand_services_brand_slug"),
    )
    op.create_index(op.f("ix_customer_brand_services_id"), "customer_brand_services", ["id"], unique=False)
    op.create_index(op.f("ix_customer_brand_services_brand_id"), "customer_brand_services", ["brand_id"], unique=False)
    op.create_index(op.f("ix_customer_brand_services_category_slug"), "customer_brand_services", ["category_slug"], unique=False)
    op.create_index(op.f("ix_customer_brand_services_is_active"), "customer_brand_services", ["is_active"], unique=False)
    op.create_index(op.f("ix_customer_brand_services_display_order"), "customer_brand_services", ["display_order"], unique=False)

    op.create_table(
        "customer_brand_stores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("brand_service_id", sa.Integer(), nullable=False),
        sa.Column("provider_profile_id", sa.Integer(), nullable=True),
        sa.Column("shop_name", sa.String(length=255), nullable=True),
        sa.Column("contact_name", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["brand_service_id"], ["customer_brand_services.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["provider_profile_id"], ["provider_profiles.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("brand_service_id", "provider_profile_id", name="uq_customer_brand_stores_service_provider"),
    )
    op.create_index(op.f("ix_customer_brand_stores_id"), "customer_brand_stores", ["id"], unique=False)
    op.create_index(op.f("ix_customer_brand_stores_brand_service_id"), "customer_brand_stores", ["brand_service_id"], unique=False)
    op.create_index(op.f("ix_customer_brand_stores_provider_profile_id"), "customer_brand_stores", ["provider_profile_id"], unique=False)
    op.create_index(op.f("ix_customer_brand_stores_is_active"), "customer_brand_stores", ["is_active"], unique=False)
    op.create_index(op.f("ix_customer_brand_stores_display_order"), "customer_brand_stores", ["display_order"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_customer_brand_stores_display_order"), table_name="customer_brand_stores")
    op.drop_index(op.f("ix_customer_brand_stores_is_active"), table_name="customer_brand_stores")
    op.drop_index(op.f("ix_customer_brand_stores_provider_profile_id"), table_name="customer_brand_stores")
    op.drop_index(op.f("ix_customer_brand_stores_brand_service_id"), table_name="customer_brand_stores")
    op.drop_index(op.f("ix_customer_brand_stores_id"), table_name="customer_brand_stores")
    op.drop_table("customer_brand_stores")

    op.drop_index(op.f("ix_customer_brand_services_display_order"), table_name="customer_brand_services")
    op.drop_index(op.f("ix_customer_brand_services_is_active"), table_name="customer_brand_services")
    op.drop_index(op.f("ix_customer_brand_services_category_slug"), table_name="customer_brand_services")
    op.drop_index(op.f("ix_customer_brand_services_brand_id"), table_name="customer_brand_services")
    op.drop_index(op.f("ix_customer_brand_services_id"), table_name="customer_brand_services")
    op.drop_table("customer_brand_services")

    op.drop_index(op.f("ix_customer_brands_display_order"), table_name="customer_brands")
    op.drop_index(op.f("ix_customer_brands_is_active"), table_name="customer_brands")
    op.drop_index(op.f("ix_customer_brands_slug"), table_name="customer_brands")
    op.drop_index(op.f("ix_customer_brands_id"), table_name="customer_brands")
    op.drop_table("customer_brands")
