"""add user phone history

Revision ID: 20260430_0004
Revises: 20260430_0003
Create Date: 2026-04-30 17:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260430_0004"
down_revision: Union[str, None] = "20260430_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_phone_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("old_phone", sa.String(length=20), nullable=True),
        sa.Column("new_phone", sa.String(length=20), nullable=False),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_user_phone_history_id"),
        "user_phone_history",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_phone_history_user_id"),
        "user_phone_history",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_user_phone_history_user_id"), table_name="user_phone_history")
    op.drop_index(op.f("ix_user_phone_history_id"), table_name="user_phone_history")
    op.drop_table("user_phone_history")
