"""add admin dashboard support

Revision ID: 20260430_0006
Revises: 20260430_0005
Create Date: 2026-04-30 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260430_0006"
down_revision: str | None = "20260430_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SERVICE_CATEGORIES = (
    ("mens-grooming", "Men's grooming", "Personal Care"),
    ("spa-massage-at-home", "Spa & massage at home", "Personal Care"),
    ("salon-at-home", "Salon at home", "Personal Care"),
    ("spa-at-home", "Spa at home", "Personal Care"),
    ("makeup-services", "Makeup Services", "Personal Care"),
    ("hair-care", "Hair Care", "Personal Care"),
    ("skincare-advanced-treatments", "Skincare Advanced Treatments", "Personal Care"),
    ("mehndi-services", "Mehndi Services", "Personal Care"),
    ("plumber", "Plumber", "Cleaning & Handyman"),
    ("house-cleaning", "House Cleaning", "Cleaning & Handyman"),
    ("carpenter-service", "Carpenter Service", "Cleaning & Handyman"),
    ("pest-control", "Pest Control", "Cleaning & Handyman"),
    ("painter-service", "Painter Service", "Cleaning & Handyman"),
    ("bike-mechanic", "Bike Mechanic", "Home Repairs & Maintenance"),
    ("car-mechanic", "Car Mechanic", "Home Repairs & Maintenance"),
    ("mobile-servicing", "Mobile Servicing", "Home Repairs & Maintenance"),
    ("electronic-mechanic", "Electronic Mechanic", "Home Repairs & Maintenance"),
    ("electrician", "Electrician", "Home Repairs & Maintenance"),
    ("ac-fridge-service", "AC/Fridge Service", "Home Repairs & Maintenance"),
    ("ro-servicing", "RO Servicing", "Home Repairs & Maintenance"),
    ("battery-servicing", "Battery Servicing", "Home Repairs & Maintenance"),
    ("computer-service", "Computer Service", "Home Repairs & Maintenance"),
    ("gas-stove-service", "Gas Stove Service", "Home Repairs & Maintenance"),
    ("second-hand-device", "Second Hand Device", "Other Services"),
    ("camera-servicing", "Camera Servicing", "Other Services"),
    ("cctv-servicing", "CCTV Servicing", "Other Services"),
    ("printer-servicing", "Printer Servicing", "Other Services"),
    ("e-rickshaw-mechanic", "E-Rickshaw Mechanic", "Other Services"),
    ("water-tank-cleaning", "Water Tank Cleaning", "Other Services"),
    ("laundry-dry-cleaning", "Laundry & Dry Cleaning", "Other Services"),
    ("packers-movers", "Packers & Movers", "Other Services"),
    ("car-bike-wash", "Car/Bike Wash", "Other Services"),
    ("home-tutors", "Home Tutors", "Other Services"),
    ("computer-training", "Computer Training", "Other Services"),
)


def upgrade() -> None:
    op.create_table(
        "service_categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("group", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_service_categories_id"), "service_categories", ["id"], unique=False)
    op.create_index(op.f("ix_service_categories_slug"), "service_categories", ["slug"], unique=True)
    op.create_index(op.f("ix_service_categories_group"), "service_categories", ["group"], unique=False)
    op.create_index(op.f("ix_service_categories_is_active"), "service_categories", ["is_active"], unique=False)
    op.create_index(op.f("ix_service_categories_display_order"), "service_categories", ["display_order"], unique=False)

    service_categories = sa.table(
        "service_categories",
        sa.column("slug", sa.String),
        sa.column("label", sa.String),
        sa.column("group", sa.String),
        sa.column("display_order", sa.Integer),
    )
    op.bulk_insert(
        service_categories,
        [
            {
                "slug": slug,
                "label": label,
                "group": group,
                "display_order": index,
            }
            for index, (slug, label, group) in enumerate(SERVICE_CATEGORIES, start=1)
        ],
    )

    op.create_table(
        "customer_home_banners",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("image_path", sa.String(length=500), nullable=False),
        sa.Column("alt_text", sa.String(length=255), nullable=False, server_default="NearFix banner"),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_customer_home_banners_id"), "customer_home_banners", ["id"], unique=False)
    op.create_index(op.f("ix_customer_home_banners_display_order"), "customer_home_banners", ["display_order"], unique=False)
    op.create_index(op.f("ix_customer_home_banners_is_active"), "customer_home_banners", ["is_active"], unique=False)

    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    app_settings = sa.table(
        "app_settings",
        sa.column("key", sa.String),
        sa.column("value", sa.Text),
    )
    op.bulk_insert(app_settings, [{"key": "customer_home_banner_limit", "value": "2"}])

    op.create_table(
        "admin_audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("admin_user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=100), nullable=False),
        sa.Column("target_id", sa.String(length=100), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["admin_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_admin_audit_logs_id"), "admin_audit_logs", ["id"], unique=False)
    op.create_index(op.f("ix_admin_audit_logs_admin_user_id"), "admin_audit_logs", ["admin_user_id"], unique=False)
    op.create_index(op.f("ix_admin_audit_logs_action"), "admin_audit_logs", ["action"], unique=False)
    op.create_index(op.f("ix_admin_audit_logs_target_type"), "admin_audit_logs", ["target_type"], unique=False)
    op.create_index(op.f("ix_admin_audit_logs_target_id"), "admin_audit_logs", ["target_id"], unique=False)
    op.create_index(op.f("ix_admin_audit_logs_created_at"), "admin_audit_logs", ["created_at"], unique=False)

    op.add_column("provider_profiles", sa.Column("rejection_reason", sa.String(length=500), nullable=True))
    op.add_column(
        "provider_document_change_requests",
        sa.Column("rejection_reason", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "provider_document_change_requests",
        sa.Column("reviewed_by_admin_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_provider_document_change_requests_reviewed_by_admin_id_users",
        "provider_document_change_requests",
        "users",
        ["reviewed_by_admin_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_provider_document_change_requests_reviewed_by_admin_id_users",
        "provider_document_change_requests",
        type_="foreignkey",
    )
    op.drop_column("provider_document_change_requests", "reviewed_by_admin_id")
    op.drop_column("provider_document_change_requests", "rejection_reason")
    op.drop_column("provider_profiles", "rejection_reason")

    op.drop_index(op.f("ix_admin_audit_logs_created_at"), table_name="admin_audit_logs")
    op.drop_index(op.f("ix_admin_audit_logs_target_id"), table_name="admin_audit_logs")
    op.drop_index(op.f("ix_admin_audit_logs_target_type"), table_name="admin_audit_logs")
    op.drop_index(op.f("ix_admin_audit_logs_action"), table_name="admin_audit_logs")
    op.drop_index(op.f("ix_admin_audit_logs_admin_user_id"), table_name="admin_audit_logs")
    op.drop_index(op.f("ix_admin_audit_logs_id"), table_name="admin_audit_logs")
    op.drop_table("admin_audit_logs")

    op.drop_table("app_settings")

    op.drop_index(op.f("ix_customer_home_banners_is_active"), table_name="customer_home_banners")
    op.drop_index(op.f("ix_customer_home_banners_display_order"), table_name="customer_home_banners")
    op.drop_index(op.f("ix_customer_home_banners_id"), table_name="customer_home_banners")
    op.drop_table("customer_home_banners")

    op.drop_index(op.f("ix_service_categories_display_order"), table_name="service_categories")
    op.drop_index(op.f("ix_service_categories_is_active"), table_name="service_categories")
    op.drop_index(op.f("ix_service_categories_group"), table_name="service_categories")
    op.drop_index(op.f("ix_service_categories_slug"), table_name="service_categories")
    op.drop_index(op.f("ix_service_categories_id"), table_name="service_categories")
    op.drop_table("service_categories")
